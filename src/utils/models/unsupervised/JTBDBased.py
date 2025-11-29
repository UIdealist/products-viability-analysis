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
        self.reviews_encoded = self.spark.read.format('delta').load(spark_utils.path(
            'reviews_embeddings_sample_balanced', catalog = self.gold_encoding_schema
        ))
        self.reviews_indexed = self.spark.read.format('delta').load(self.spark_utils.path(
            'reviews_indexed', catalog = self.silver_preprocess_schema
        ))
        self.normalizer = Normalizer(inputCol="text_embeddings", outputCol="text_embeddings_normalized", p=2)
        
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

    def predict(
        self, df_features: DataFrame, df_paired: DataFrame
    ):
        self.df_reviews_paired = self._save_temp_table( df_paired.alias('A').join(
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
        ), 'df_reviews_paired')

        self.df_reviews_votes_per_product = self._save_temp_table(self.df_reviews_paired.groupBy('parent_asin').agg(
            F.sum('helpful_vote').alias('product_helpful_vote')
        ), 'df_reviews_votes_per_product')

        self.df_features_normalized = self.normalizer.transform(
            df_features
                .withColumn('text_embeddings', Fm.array_to_vector(F.col('text_embeddings')))
        )

        self.df_reviews_features_normalized = self.normalizer.transform(
            self.df_reviews_paired
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
            (F.avg(F.col('dot_product'))).alias('features_factor')
        )

        self.df_reviews_relevance = self._save_temp_table(self.df_reviews_paired.alias('A').join(
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
        ), 'df_reviews_relevance')

        score_sum = self.df_reviews_relevance.agg(
            F.sum(F.col('score')).alias('score_sum')
        ).collect()[0]['score_sum']

        relevance_sum = self.df_reviews_relevance.agg(
            F.sum(F.col('relevance_factor')).alias('relevance_sum')
        ).collect()[0]['relevance_sum']

        return score_sum / (5 * relevance_sum)

    def calculate_preds_metrics(self, df_features_full: DataFrame, df_pairs_full: DataFrame):
        self.metrics_df_reviews_paired_a = df_pairs_full.alias('A').join(
            self.reviews_indexed.alias('B'),
            F.col('A.parent_asin_b') == F.col('B.parent_asin'),
            how = 'inner'
        ).join(
            self.reviews_encoded.alias('C'),
            F.col('B.review_id') == F.col('C.review_id'),
            how = 'inner'
        ).select(
            'B.review_id',
            F.col('A.parent_asin_a').alias('parent_asin_base'),
            F.col('A.parent_asin_b').alias('parent_asin_related'), 
            'C.text_embeddings',
            'B.helpful_vote',
            'B.rating'
        )

        self.metrics_df_reviews_paired_b = df_pairs_full.alias('A').join(
            self.reviews_indexed.alias('B'),
            F.col('A.parent_asin_a') == F.col('B.parent_asin'),
            how = 'inner'
        ).join(
            self.reviews_encoded.alias('C'),
            F.col('B.review_id') == F.col('C.review_id'),
            how = 'inner'
        ).select(
            'B.review_id',
            F.col('A.parent_asin_b').alias('parent_asin_base'),
            F.col('A.parent_asin_a').alias('parent_asin_related'), 
            'C.text_embeddings',
            'B.helpful_vote',
            'B.rating'
        )

        self.metrics_df_reviews_paired = self.metrics_df_reviews_paired_a.union(
            self.metrics_df_reviews_paired_b
        )

        self.metrics_df_reviews_votes_per_product = self.metrics_df_reviews_paired.groupBy('parent_asin_related').agg(
            F.sum('helpful_vote').alias('product_helpful_vote')
        )

        self.metrics_df_features_normalized = self.normalizer.transform(
            df_features_full
                .withColumn('text_embeddings', Fm.array_to_vector(F.col('text_embeddings')))
        )

        self.metrics_df_reviews_features_normalized = self.normalizer.transform(
            self.metrics_df_reviews_paired
        )

        @F.udf(returnType=T.FloatType())
        def dot_udf(arr1, arr2):
            if arr1 is not None and arr2 is not None:
                return float(np.dot(arr1, arr2))
            
        self.metrics_df_cosine_similarity_features = self.metrics_df_features_normalized.alias('A').join(
            self.metrics_df_reviews_features_normalized.alias('B'),
            F.col('A.parent_asin') == F.col('B.parent_asin_base'),
            how = 'inner'
        ).select(
            'B.review_id',
            dot_udf(
                F.col('A.text_embeddings_normalized'), F.col('B.text_embeddings_normalized')
            ).alias('dot_product')
        ).groupBy('review_id').agg(
            (F.avg(F.col('dot_product'))).alias('features_factor')
        )

        self.metrics_df_reviews_relevance = self.metrics_df_reviews_paired.alias('A').join(
            self.metrics_df_reviews_votes_per_product.alias('B'),
            F.col('A.parent_asin_related') == F.col('B.parent_asin_related'),
            how = 'inner'
        ).join(
            self.metrics_df_cosine_similarity_features.alias('C'),
            F.col('A.review_id') == F.col('C.review_id'),
            how = 'inner'
        ).select(
            'A.parent_asin_base',
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

        self.metrics_score_sum = self.metrics_df_reviews_relevance.groupBy('parent_asin_base').agg(
            F.sum(F.col('score')).alias('score_sum')
        )

        self.metrics_relevance_sum = self.metrics_df_reviews_relevance.groupBy('parent_asin_base').agg(
            F.sum(F.col('relevance_factor')).alias('relevance_sum')
        )

        self.metrics_by_product_predicted = self.metrics_score_sum.alias('A').join(
            self.metrics_relevance_sum.alias('B'),
            F.col('A.parent_asin_base') == F.col('B.parent_asin_base'),
            how = 'inner'
        ).select(
            'A.parent_asin_base',
            (F.col('A.score_sum') / (5 * F.col('B.relevance_sum'))).alias('score')
        )

        self.metrics_by_product_actual = self.metrics_by_product_predicted.alias('A').join(
            self.reviews_indexed.alias('B'),
            F.col('A.parent_asin_base') == F.col('B.parent_asin'),
            how = 'inner'
        ).groupBy('A.parent_asin_base').agg(
            F.avg(F.col('B.rating')).alias('rating'),
            F.avg(F.col('A.score')).alias('score')
        ).select(
            'parent_asin_base',
            F.col('score').alias('score_predicted'),
            (F.col('rating') / 5).alias('rating_actual')
        )
