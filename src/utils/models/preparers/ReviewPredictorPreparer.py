from pandas import DataFrame
from src.utils.spark import SparkUtils
import pyspark.sql.functions as F
import pyspark.ml.functions as Fm

class ReviewPredictorPreparer:
    def __init__(self, spark_utils: SparkUtils):
        self.spark_utils = spark_utils
        self.spark = spark_utils.spark
        self.silver_preprocess_schema = 'silver.preprocess'
        self.gold_premodeling_schema = 'gold.premodeling'
        self.reviews_indexed = self.spark.read.format('delta').load(self.spark_utils.path(
            'reviews_indexed', catalog = self.silver_preprocess_schema
        ))
        self.df_vectorized_pca = self.spark.read.format('delta').load(self.spark_utils.path(
            'df_vectorized_pca', catalog = self.gold_premodeling_schema
        ))
        self.df_reviews_vectorized_pca = self.spark.read.format('delta').load(self.spark_utils.path(
            'df_reviews_vectorized_pca_test', catalog = self.gold_premodeling_schema
        ))
        self.main_category_encoded = self.spark.read.format('delta').load(self.spark_utils.path(
            'main_category_encoded', catalog = self.gold_premodeling_schema
        ))

    def prepare_models_inputs(
        self, self_representation_df: DataFrame, similar_pairs_df: DataFrame,
        id_col: str,
    ) -> DataFrame:
        if similar_pairs_df.count() == 0:
            print("No similar pairs found")
            return None
        
        self.binary_review_prediction_df =self_representation_df.alias('A').crossJoin(
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
            'D.helpful_vote',
            F.concat(
                Fm.vector_to_array(F.col('C.pca_features')),
                Fm.vector_to_array(F.col('E.pca_features'))
            ).alias('combined_features')
        )

        sample_row = self.binary_review_prediction_df.limit(1).collect()[0]
        combined_features_size = len(sample_row['combined_features'])

        select_exprs = []

        for i in range(combined_features_size):
            select_exprs.append(F.col("combined_features")[i].alias(f"combined_feat_{i}"))

        self.binary_review_prediction_df = self.binary_review_prediction_df.select(
            F.col("helpful_vote").cast("int").alias("helpful_vote"),
            *select_exprs
        )

        return self.binary_review_prediction_df