from pandas import DataFrame
from src.gold.training.pca import PCAEncoder
from src.utils.spark import SparkUtils
import pyspark.sql.functions as F
import pyspark.ml.functions as Fm
import numpy as np
from pyspark.ml.feature import Normalizer
import pyspark.sql.types as T


class JTBDBased:
    def __init__(self, spark_utils: SparkUtils):
        self.spark_utils = spark_utils
        self.spark = spark_utils.spark
        self.phi = 0.03
        self.reviews_pca_encoder_test = PCAEncoder(
            id_cols=["review_id"],
            input_col="features",
            output_col="features_pca",
            k=250
        )
        self.gold_premodeling_schema = 'gold.premodeling'
        self.gold_encoding_schema = 'gold.encoding'
        self.silver_preprocess_schema = 'silver.preprocess'
        self.reviews_pca_encoder_test.load(
            spark_utils.path('reviews_pca_encoder_test', catalog = self.gold_premodeling_schema)
        )
        self.reviews_encoded = self.spark.read.format('delta').load(self.spark_utils.path(
            'reviews_embeddings_equi_test', catalog = self.gold_encoding_schema
        ))
        self.reviews_indexed = self.spark.read.format('delta').load(self.spark_utils.path(
            'reviews_indexed', catalog = self.silver_preprocess_schema
        ))
        self.normalizer = Normalizer(inputCol="text_embeddings", outputCol="text_embeddings_normalized", p=2)
        

    def predict(
        self, df_features: DataFrame, df_paired: DataFrame
    ):
        self.df_reviews_paired = df_paired.alias('A').join(
            self.reviews_indexed.alias('B'),
            F.col('A.entity_id') == F.col('B.parent_asin'),
            how = 'inner'
        ).join(
            self.reviews_encoded.alias('C'),
            F.col('B.review_id') == F.col('C.review_id'),
            how = 'inner'
        ).select(
            'B.review_id',
            'B.parent_asin', 
            'C.text_embeddings',
            'B.helpful_vote',
            'B.rating'
        )

        self.df_reviews_votes_per_product = self.df_reviews_paired.groupBy('parent_asin').agg(
            F.sum('helpful_vote').alias('product_helpful_vote')
        )

        self.df_features_normalized = self.normalizer.transform(
            df_features
                .withColumn('text_embeddings', Fm.array_to_vector(F.col('text_embeddings')))
        )

        self.df_reviews_features_normalized = self.normalizer.transform(
            self.df_reviews_paired
                .withColumn('text_embeddings', Fm.array_to_vector(F.col('text_embeddings')))
        )

        @F.udf(returnType=T.FloatType())
        def dot_udf(arr1, arr2):
            if arr1 is not None and arr2 is not None:
                return float(np.dot(arr1, arr2))
            
        self.df_cosine_similarity_features = self.df_features_normalized.alias('A').crossJoin(
            self.df_reviews_features_normalized.alias('B')
        ).select(
            'B.review_id',
            dot_udf(
                F.col('A.text_embeddings_normalized'), F.col('B.text_embeddings_normalized')
            ).alias('dot_product')
        ).groupBy('review_id').agg(
            (1 - F.avg(F.col('dot_product'))).alias('features_factor')
        )

        self.df_reviews_relevance = self.df_reviews_paired.alias('A').join(
            self.df_reviews_votes_per_product.alias('B'),
            F.col('A.parent_asin') == F.col('B.parent_asin'),
            how = 'inner'
        ).join(
            self.df_cosine_similarity_features.alias('C'),
            F.col('A.review_id') == F.col('C.review_id'),
            how = 'inner'
        ).select(
            'A.review_id',
            (
                1 + self.phi * (
                    F.col('B.product_helpful_vote') / F.sqrt(F.col('A.helpful_vote'))
                ) + F.col('C.features_factor')
            ).alias('relevance_factor'),
            F.col('A.rating')
        ).select(
            '*',
            (F.col('relevance_factor') * F.col('rating')).alias('score')
        )

        score_sum = self.df_reviews_relevance.agg(
            F.sum(F.col('score')).alias('score_sum')
        ).collect()[0]['score_sum']

        relevance_sum = self.df_reviews_relevance.agg(
            F.sum(F.col('relevance_factor')).alias('relevance_sum')
        ).collect()[0]['relevance_sum']

        return score_sum / (5 * relevance_sum)
