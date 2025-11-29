from pyspark.sql.dataframe import DataFrame


from src.utils.spark import SparkUtils
from pyspark.sql import DataFrame, functions as F
from pyspark.sql import types as T
import numpy as np
import pandas as pd

schema = T.StructType([
    T.StructField("id", T.IntegerType()),
    T.StructField("text_embeddings", T.ArrayType(T.DoubleType()))
])

@F.pandas_udf(schema, functionType=F.PandasUDFType.GROUPED_MAP)
def sum_weighted_embeddings(pdf):
    weighted_embeds = np.stack(pdf['weighted_embedding'].values)
    
    summed = weighted_embeds.sum(axis=0)
    
    return pd.DataFrame({
        'id': [pdf['id'].iloc[0]],
        'text_embeddings': [summed.tolist()]
    })
    
@F.pandas_udf(schema, functionType=F.PandasUDFType.GROUPED_MAP)
def avg_weighted_embeddings(pdf):
    weighted_embeds = np.stack(pdf['weighted_embedding'].values)
    
    summed = weighted_embeds.mean(axis=0)
    
    return pd.DataFrame({
        'id': [pdf['id'].iloc[0]],
        'text_embeddings': [summed.tolist()]
    })

class SummarizeEncoding:
    def __init__(
        self,
        spark_utils: SparkUtils,
    ):
        self.spark = spark_utils.spark
        self.spark_utils = spark_utils
        self.gold_schema = "gold.premodeling"

    def summarize_encodings_by_component(
        self, id_col: str,
        dfs: list[DataFrame],
        weights: list[float],
        embedding_col: str,
    ):
        summary_dfs = []
        for df_it, weight in zip(dfs, weights):
            df = df_it.withColumn(
                "weighted_embedding",
                F.transform(
                    F.col(embedding_col), 
                    lambda x: x * F.lit(weight)
                )
            )
            df = df.select(
                F.col(id_col).alias("id"),
                F.col("weighted_embedding"),
            ).filter(
                F.col("id").isNotNull()
            ).groupBy("id").apply(
                sum_weighted_embeddings
            ).select(
                F.col("id").alias(id_col).cast(T.IntegerType()),
                F.col("text_embeddings").cast(T.ArrayType(T.DoubleType())),
            )
            summary_dfs.append(df)
        return summary_dfs

    def simple_summarize_encoding(
        self, 
        summarized_encodings: list[DataFrame],
        id_col: str,
    ):
        union_df = summarized_encodings[0]
        for df in summarized_encodings[1:]:
            union_df = union_df.union(df)
        union_df = union_df.select(
            F.col(id_col).alias("id"),
            F.col("text_embeddings").alias("weighted_embedding"),
        ).groupBy(
            "id"
        ).apply(
            sum_weighted_embeddings
        ).select(
            F.col("id").alias(id_col),
            F.col("text_embeddings"),
        )
        return union_df
        