from pandas import DataFrame
from src.utils.spark import SparkUtils
import pyspark.sql.functions as F
import pyspark.sql.types as T
import pyspark.ml.functions as Fm
import numpy as np

class ReviewPredictorPreparer:
    def __init__(self, spark_utils: SparkUtils):
        self.spark_utils = spark_utils
        self.spark = spark_utils.spark
        self.silver_preprocess_schema = 'silver.preprocess'
        self.gold_premodeling_schema = 'gold.premodeling'
        self.gold_encoding_schema = 'gold.encoding'
        self.reviews_indexed = self.spark.read.format('delta').load(self.spark_utils.path(
            'reviews_indexed', catalog = self.silver_preprocess_schema
        ))
        self.df_vectorized_pca = self.spark.read.format('delta').load(self.spark_utils.path(
            'df_vectorized_pca', catalog = self.gold_premodeling_schema
        ))
        self.df_reviews_vectorized_pca = self.spark.read.format('delta').load(self.spark_utils.path(
            'reviews_embeddings_equi_sample_balanced_pca_repartitioned', catalog = self.gold_encoding_schema
        ))
        self.main_category_encoded = self.spark.read.format('delta').load(self.spark_utils.path(
            'main_category_encoded', catalog = self.gold_premodeling_schema
        ))

    def _save_temp_table(self, df: DataFrame, table_name: str, schema: T.StructType = None):
        if schema is not None:
            df = df.select(
                *[
                    F.col(field.name).cast(field.dataType)
                    for field in schema.fields
                ]
            )
        df.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').save(
            self.spark_utils.path(table_name, catalog = self.gold_premodeling_schema + '_tmp')
        )
        return self.spark.read.format('delta').load(
            self.spark_utils.path(table_name, catalog = self.gold_premodeling_schema + '_tmp')
        )

    def prepare_models_inputs(
        self, self_representation_df: DataFrame, similar_pairs_df: DataFrame,
        id_col: str,
    ) -> DataFrame:
        if similar_pairs_df.count() == 0:
            print("No similar pairs found")
            return None
        
        self.general_review_prediction_df = self_representation_df.alias('A').crossJoin(
            similar_pairs_df.alias('B')
        ).join(
            self.df_vectorized_pca.alias('C'),
            F.col(f'B.{id_col}') == F.col('C.parent_asin'),
            how = 'inner'
        ).join(
            self.reviews_indexed.alias('D'),
            F.col(f'B.{id_col}') == F.col('D.parent_asin'),
            how = 'inner'
        ).join(
            self.df_reviews_vectorized_pca.alias('E'),
            F.col('D.review_id') == F.col('E.review_id'),
            how = 'inner'
        ).select(
            'D.parent_asin',
            'D.review_id',
            'D.helpful_vote',
            F.concat(
                Fm.vector_to_array(F.col('A.features')),
                Fm.vector_to_array(F.col('E.pca_features'))
            ).alias('combined_features'),
            Fm.vector_to_array(F.col('A.features')).alias('product_features')
        )

        self.item_representation_df = self_representation_df.select(
            '*', Fm.vector_to_array(F.col('features')).alias('product_features')
        )

        self.general_review_prediction_df = self._save_temp_table(
            self.general_review_prediction_df, "general_review_prediction_df"
        )

        self.general_review_prediction_weights_df = self.general_review_prediction_df.groupBy(
            'review_id'
        ).agg(
            F.sum(F.col('helpful_vote')).alias('helpful_vote_sum'),
        ).alias('A').join(
            self.general_review_prediction_df.alias('B'),
            F.col('A.review_id') == F.col('B.review_id'),
            how = 'inner'
        ).select(
            F.when(F.col('A.helpful_vote_sum') == 0, F.lit(1)).otherwise(
                F.col('B.helpful_vote') / F.sqrt(F.col('A.helpful_vote_sum'))
            ).alias('helpful_vote_weight')
        )

        self.general_review_prediction_weights = self.general_review_prediction_weights_df.toPandas().to_numpy()

        combined_features_size = 400

        select_exprs = []

        for i in range(combined_features_size):
            select_exprs.append(F.col("combined_features")[i].alias(f"combined_feat_{i}"))

        self.binary_review_prediction_df = self.general_review_prediction_df.select(
            *select_exprs
        )

        self.categorical_review_prediction_df = self.binary_review_prediction_df

        self.categorical_review_prediction_df = self._save_temp_table(
            self.categorical_review_prediction_df, "categorical_review_prediction_df"
        )

        products_features_size = 150

        select_exprs = []
        for i in range(products_features_size):
            select_exprs.append(F.col("product_features")[i].alias(f"product_features_{i}"))

        self.category_prediction_df = self.item_representation_df.select(
            *select_exprs
        )

        self.category_prediction_df = self._save_temp_table(
            self.category_prediction_df, "category_prediction_df"
        )

        return (
            self.binary_review_prediction_df,
            self.categorical_review_prediction_df,
            self.category_prediction_df
        )

    def prepare_models_inputs_binary_with_categorical(
        self, probs: np.array,
    ):
        one_hot = (probs == np.max(probs)).astype(int)
        df = self.binary_review_prediction_df

        for i, val in enumerate(one_hot):
            df = df.withColumn(f"cat_{i}", F.lit(int(val)))

        self.binary_review_prediction_df_with_categorical = self._save_temp_table(
            df, "binary_review_prediction_df_with_categorical"
        )

        return self.binary_review_prediction_df_with_categorical