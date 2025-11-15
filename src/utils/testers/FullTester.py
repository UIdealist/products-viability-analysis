from pandas import DataFrame
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.ml import functions as Fm
from pyspark.sql import Window
from pyspark.sql import types as T
import tensorflow_hub as hub

from src.utils.preprocessors.clean_words import CleanWords
from src.utils.models.encoding.SentenceEncoder import SentenceEncoder
from src.utils.models.encoding.SentenceMiniEncoder import SentenceMiniEncoder
from src.utils.constants import DESCRIPTION_WEIGHT, FEATURES_WEIGHT, TITLE_WEIGHT
from src.utils.models.clustering.LSHNeighborsClustering import LSHNeighborsClustering, LSHNeighborsClusteringParameter
from src.utils.models.encoding.SummarizeEncoding import SummarizeEncoding
from src.utils.spark import SparkUtils
from src.gold.training.pca import PCAEncoder
from src.utils.models.preparers.ReviewPredictorPreparer import ReviewPredictorPreparer
from src.utils.models import BinaryModel
import numpy as np
from src.utils.models.unsupervised.JTBDBased import JTBDBased

class FullTester:
    def __init__(
        self,
        spark: SparkSession,
        spark_utils: SparkUtils,
        use_mini_llm: bool = False,
        use_pca: bool = True,
    ):
        self.spark = spark
        self.spark_utils = spark_utils
        self.use_mini_llm = use_mini_llm
        self.use_pca = use_pca
        self.premodeling_schema = 'gold.premodeling'
        self.cluster_schema = 'gold.cluster'
        self.metastore_path = '/mnt/d/Maestría/Amazon Reviews Code/data'
        self.tracking_uri = 'file:///mnt/d/Maestría/Amazon Reviews Code/.mlflow'
        self.original_components = {
            "title": None,
            "description": None,
            "features": None,
        }
        self.encoded_components = {
            "title": None,
            "description": None,
            "features": None,
        }
        self.clean_words = CleanWords()
        self.sentence_encoder = SentenceEncoder(
            spark_utils=spark_utils
        ) if not self.use_mini_llm else SentenceMiniEncoder(
            spark_utils=spark_utils
        )
        self.summarize_encoding = SummarizeEncoding(spark_utils=spark_utils)
        _pca_encoder = PCAEncoder(
            id_cols=["entity_id"],
            input_col="features",
            output_col="pca_features",
            k=125
        )
        self.pca_encoder = _pca_encoder.load(
            self.spark_utils.path(
                f'pca_encoder{"_minillm" if self.use_mini_llm else ""}', 
                catalog = self.premodeling_schema
            )
        )
        self.lsh_neighbors_clustering = LSHNeighborsClustering(
            lsh_parameters=LSHNeighborsClusteringParameter(
                comb_id="pca_features_1000_300",
                n_neighbors=10,
                min_cosine_similarity=0.9,
                bucket_length=1.0,
                num_hash_tables=5
            ),
            spark_utils=spark_utils,
            table_prefix=f"lsh_pca_features_balanced{'_minillm' if self.use_mini_llm else ''}",
            catalog=self.cluster_schema,
            id_col="entity_id",
            features_col="features",
            hashes_col="hashes",
            batch_size=10_000
        )

        _df_vectorized_pca = self.spark.read.format('delta').load(self.spark_utils.path(
            f'df_vectorized_pca_balanced{"_minillm" if self.use_mini_llm else ""}', catalog = self.premodeling_schema
        )).select(
            F.col('parent_asin').alias('entity_id'),
            F.col('pca_features').alias('features'),
        )
        self.df_vectorized_pca = self._save_temp_table(_df_vectorized_pca, "df_vectorized_pca_tester")
        self.lsh_neighbors_clustering.fit(self.df_vectorized_pca)
        self.review_predictor_preparer = ReviewPredictorPreparer(spark_utils=self.spark_utils)
        self.binary_model = BinaryModel(
            model_name="binary_model",
            metastore_path=self.metastore_path,
            tracking_uri=self.tracking_uri,
        )
        self.binary_model.load_latest_model()
        self.predictions_by_model = {
            "binary_model": None,
            "regression_model": None,
            "unsupervised": None,
        }
        self.jtbdbased = JTBDBased(spark_utils=self.spark_utils)

    def input_components(self):
        self.original_components["title"] = input("Iphone 15 Pro Max") or "Iphone 15 Pro Max"
        self.original_components["description"] = input("Iphone 15 Pro Max") or "Iphone 15 Pro Max"
        self.original_components["features"] = input("Iphone 15 Pro Max") or "Iphone 15 Pro Max"
        self.set_components(self.original_components)
    
    def set_components(self, components: dict):
        self.original_components = components
        self.original_components_df = self.spark.createDataFrame([
            (
                1, self.original_components["title"],
                self.original_components["description"],
                self.original_components["features"]
            )
        ], T.StructType([
            T.StructField("entity_id", T.IntegerType(), True),
            T.StructField("title", T.StringType(), True),
            T.StructField("description", T.ArrayType(T.StringType()), True),
            T.StructField("features", T.ArrayType(T.StringType()), True),
        ]))

    def clean_components(self):
        def _clean_component(df, component: str):
            if component == "title":
                return self.clean_words.transform_default_no_tokenization(
                    df,
                    input_column="title",
                    output_column="title"
                )
            else:
                return self.clean_words.transform_default_no_tokenization_array(
                    df,
                    column_name="description"
                )

        self.clean_components_df = _clean_component(
            self.original_components_df,
            "title"
        )
        self.clean_components_df = _clean_component(
            self.clean_components_df,
            "description"
        )
        self.clean_components_df = _clean_component(
            self.clean_components_df,
            "features"
        )
        self.clean_components_df = self._save_temp_table(
            self.clean_components_df, "clean_components_df_tester"
        )
        return self.clean_components_df

    def _save_temp_table(self, df: DataFrame, table_name: str, schema: T.StructType = None):
        if schema is not None:
            df = df.select(
                *[
                    F.col(field.name).cast(field.dataType)
                    for field in schema.fields
                ]
            )
        df.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').save(
            self.spark_utils.path(table_name, catalog = self.premodeling_schema + '_tmp')
        )
        return self.spark.read.format('delta').load(
            self.spark_utils.path(table_name, catalog = self.premodeling_schema + '_tmp')
        )
    def _clear_all_temp_tables(self):
        for table in self.spark.sql(f"SHOW TABLES IN {self.premodeling_schema + '_tmp'}").collect():
            self.spark.sql(f"DROP TABLE IF EXISTS {table.tableName}")
        return True
    
    def separate_sentences_per_component(self):
        self.title_sentences_df = (
            self.clean_components_df
                .withColumn("sentence_number", F.row_number().over(Window.orderBy("title")))
                .withColumn("record_id", F.monotonically_increasing_id())
                .select("entity_id", "title", "sentence_number", "record_id")
        )
        self.description_sentences_df = (
            self.clean_components_df
                .filter(
                    F.col('description').isNotNull() &
                    (F.size(F.col('description')) > 0)
                )
                .withColumn(
                    'description_paragraph',
                    F.explode(F.col('description'))
                )
                .withColumn(
                    'paragraph_number',
                    F.row_number().over(
                        Window.partitionBy('entity_id').orderBy('entity_id')
                    ).alias('paragraph_number')
                )
                .withColumn(
                    'description_sentence',
                    F.explode(
                        F.transform(
                            F.split(F.col('description_paragraph'), r"[.!?]"),
                            lambda x: F.trim(x)
                        )
                    )
                )
                .filter(
                    F.col('description_sentence').isNotNull() &
                    (F.length(F.col('description_sentence')) > 1)
                )
                .withColumn(
                    'sentence_number',
                    F.row_number().over(
                        Window.partitionBy('entity_id', 'paragraph_number').orderBy('entity_id')
                    ).alias('sentence_number')
                )
                .withColumn("record_id", F.monotonically_increasing_id())
                .select(
                    "entity_id", "description_sentence", "paragraph_number", 
                    "sentence_number", "record_id"
                )
        )
        self.features_sentences_df = (
            self.clean_components_df
                .filter(
                    F.col('features').isNotNull() &
                    (F.size(F.col('features')) > 0)
                )
                .withColumn(
                    'feature',
                    F.explode(F.col('features'))
                )
                .withColumn(
                    'feature_number',
                    F.row_number().over(
                        Window.partitionBy('entity_id').orderBy('entity_id')
                    ).alias('feature_number')
                )
                .withColumn(
                    'feature_sentence',
                    F.explode(
                        F.transform(
                            F.split(F.col('feature'), r"[.!?]"),
                            lambda x: F.trim(x)
                        )
                    )
                )
                .filter(
                    F.col('feature_sentence').isNotNull() &
                    (F.length(F.col('feature_sentence')) > 1)
                )
                .withColumn(
                    'sentence_number',
                    F.row_number().over(
                        Window.partitionBy('entity_id', 'feature_number').orderBy('entity_id')
                    ).alias('sentence_number')
                )
                .withColumn("record_id", F.monotonically_increasing_id())
                .select(
                    "entity_id", "feature_sentence", "feature_number", 
                    "sentence_number", "record_id"
                )
        )
        self.title_sentences_df = self._save_temp_table(
            self.title_sentences_df, "title_sentences_df", T.StructType([
                T.StructField("entity_id", T.IntegerType(), True),
                T.StructField("title", T.StringType(), True),
                T.StructField("sentence_number", T.IntegerType(), True),
                T.StructField("record_id", T.LongType(), True),
            ])
        )
        self.description_sentences_df = self._save_temp_table(
            self.description_sentences_df, "description_sentences_df", T.StructType([
                T.StructField("entity_id", T.IntegerType(), True),
                T.StructField("description_sentence", T.StringType(), True),
                T.StructField("paragraph_number", T.IntegerType(), True),
                T.StructField("sentence_number", T.IntegerType(), True),
                T.StructField("record_id", T.LongType(), True),
            ])
        )
        self.features_sentences_df = self._save_temp_table(
            self.features_sentences_df, "features_sentences_df", T.StructType([
                T.StructField("entity_id", T.IntegerType(), True),
                T.StructField("feature_sentence", T.StringType(), True),
                T.StructField("feature_number", T.IntegerType(), True),
                T.StructField("sentence_number", T.IntegerType(), True),
                T.StructField("record_id", T.LongType(), True),
            ])
        )
        return (
            self.title_sentences_df,
            self.description_sentences_df,
            self.features_sentences_df,
        )

    def encode_sentences(self):
        self.sentence_encoder.process_to_parquet(
            self.title_sentences_df, "title", "record_id", 2500, 1024, 
            self.spark_utils.path("title_sentences_encoded_tester", catalog = self.premodeling_schema),
            overwrite_parquet=True
        )
        self.sentence_encoder.process_to_parquet(
            self.description_sentences_df, "description_sentence", "record_id", 2500, 1024, 
            self.spark_utils.path("description_sentences_encoded_tester", catalog = self.premodeling_schema),
            overwrite_parquet=True
        )
        self.sentence_encoder.process_to_parquet(
            self.features_sentences_df, "feature_sentence", "record_id", 2500, 1024, 
            self.spark_utils.path("features_sentences_encoded_tester", catalog = self.premodeling_schema),
            overwrite_parquet=True
        )
        self.title_sentences_encoded_df = self.spark.read.format('parquet').load(
            self.spark_utils.path("title_sentences_encoded_tester", catalog = self.premodeling_schema)
        )
        self.description_sentences_encoded_df = self.spark.read.format('parquet').load(
            self.spark_utils.path("description_sentences_encoded_tester", catalog = self.premodeling_schema)
        )
        self.features_sentences_encoded_df = self.spark.read.format('parquet').load(
            self.spark_utils.path("features_sentences_encoded_tester", catalog = self.premodeling_schema)
        )
        return self.title_sentences_encoded_df, self.description_sentences_encoded_df, self.features_sentences_encoded_df

    def summarize_sentences_by_component(self):
        _summarized_sentences_dfs = self.summarize_encoding.summarize_encodings_by_component(
            id_col="entity_id",
            dfs=[
                self.title_sentences_encoded_df.alias('A').join(
                    self.title_sentences_df.alias('B'),
                    on = "record_id",
                    how = "left"
                ).select('B.entity_id', 'A.text_embeddings'), 
                self.description_sentences_encoded_df.alias('A').join(
                    self.description_sentences_df.alias('B'),
                    on = "record_id",
                    how = "left"
                ).select('B.entity_id', 'A.text_embeddings'), 
                self.features_sentences_encoded_df.alias('A').join(
                    self.features_sentences_df.alias('B'),
                    on = "record_id",
                    how = "left"
                ).select('B.entity_id', 'A.text_embeddings'), 
            ],
            weights=[TITLE_WEIGHT, DESCRIPTION_WEIGHT, FEATURES_WEIGHT],
            embedding_col="text_embeddings"
        )
        summarized_sentences_dfs = [
            self._save_temp_table(_summarized_sentences_dfs[0], "title_summarized_sentences_df_tester"),
            self._save_temp_table(_summarized_sentences_dfs[1], "description_summarized_sentences_df_tester"),
            self._save_temp_table(_summarized_sentences_dfs[2], "features_summarized_sentences_df_tester"),
        ]
        self.summarized_sentences_df = self.summarize_encoding.simple_summarize_encoding(
            summarized_sentences_dfs,
            "entity_id",
        )
        self.summarized_sentences_df = self._save_temp_table(
            self.summarized_sentences_df, "summarized_sentences_df_tester"
        )
        return self.summarized_sentences_df

    def pca_encode(self):
        self.pca_encoded_item_df = self.pca_encoder.transform(
            self.summarized_sentences_df.select(
                "entity_id",
                Fm.array_to_vector(F.col('text_embeddings')).alias('features'),
            )
        ).select(
            "entity_id",
            F.col('pca_features').alias('features'),
        )
        self.pca_encoded_item_df = self._save_temp_table(
            self.pca_encoded_item_df, "pca_encoded_sentences_df_tester"
        )
        return self.pca_encoded_item_df

    def find_pairs(self):
        self.similar_pairs_df = self.lsh_neighbors_clustering.find_pairs_for_df(
            self.pca_encoded_item_df,
            self.df_vectorized_pca,
        )
        self.similar_pairs_df = self._save_temp_table(self.similar_pairs_df, "similar_pairs_df_tester")
        return self.similar_pairs_df

    def build_models_inputs(self):
        self.binary_review_prediction_df = self.review_predictor_preparer.prepare_models_inputs(
            self_representation_df=self.pca_encoded_item_df,
            similar_pairs_df=self.similar_pairs_df,
            id_col="entity_id",
        )
        self.binary_review_prediction_df = self._save_temp_table(
            self.binary_review_prediction_df, "binary_review_prediction_df_tester"
        )
        return self.binary_review_prediction_df
    
    def generate_prediction(self):
        # self.predictions_binary_model = self.binary_model.predict(
        #     self.binary_review_prediction_df
        # )
        # self.predictions_by_model["binary_model"] = np.average(self.predictions_binary_model, axis=0)
        self.predictions_jtbdbased = self.jtbdbased.predict(
            df_features=self.features_sentences_encoded_df,
            df_paired=self.similar_pairs_df,
        )
        self.predictions_by_model["unsupervised"] = self.predictions_jtbdbased
        return self.predictions_by_model