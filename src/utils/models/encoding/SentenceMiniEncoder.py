import uuid
import numpy as np
from pyspark.sql import DataFrame, Window, functions as F, types as T
from sentence_transformers import SentenceTransformer
from src.utils.spark import SparkUtils

class SentenceMiniEncoder:
    def __init__(
        self,
        spark_utils: SparkUtils,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        gold_schema: str = "gold.premodeling",
        device: str = "cuda"
    ):
        self.model = SentenceTransformer(model_name, device=device)
        self.spark = spark_utils.spark
        self.spark_utils = spark_utils
        self.model_name = model_name
        self.gold_schema = gold_schema

    def embed_batch(self, texts, batch_size=1024):
        if len(texts) == 0:
            return np.array([])
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False
        )
        return embeddings

    def process_to_parquet(
        self,
        df: DataFrame,
        col: str,
        id_col: str,
        batch_size: int,
        tf_batch: int,
        parquet_path: str,
        overwrite_parquet: bool = False
    ):
        schema = T.StructType([
            T.StructField(id_col, T.StringType(), True),
            T.StructField("text_embeddings", T.ArrayType(T.DoubleType()), True),
        ])

        if not overwrite_parquet:
            df_target = self.spark.read.parquet(parquet_path)
            print("Original count", df_target.count())
            df = df.alias('A').join(
                df_target.alias('B'),
                on=id_col,
                how='left_anti'
            )

        w = Window.orderBy(id_col)
        df_idx = df.withColumn("rn", F.row_number().over(w))
        tmp_table_name = self.spark_utils.path(
            f"tmp_table_{str(uuid.uuid4()).replace('-', '_')}",
            catalog=self.gold_schema + '_tmp'
        )
        df_idx.write.format('delta').mode('overwrite').save(tmp_table_name)
        df_idx = self.spark.read.format('delta').load(tmp_table_name)

        count = df_idx.count()
        print("====Parquets to process=====", count)
        offset = 0
        batch_idx = 0

        while offset < count:
            print(f"====Processing batch {batch_idx} (offset {offset})====")
            batch_df = (
                df_idx
                .filter((F.col("rn") > offset) & (F.col("rn") <= offset + batch_size))
                .select(id_col, col)
            )

            batch_df = batch_df.withColumn(col, F.substring(F.col(col), 1, 120)).filter(
                F.trim(F.col(col)) != ""
            )
            pdf = batch_df.toPandas()
            texts = pdf[col].fillna("").astype(str).tolist()
            embs = self.embed_batch(texts, batch_size=tf_batch)
            emb_df = self.spark.createDataFrame(
                list(zip(pdf[id_col].tolist(), embs.tolist())),
                schema=schema
            )
            mode = "overwrite" if batch_idx == 0 and overwrite_parquet else "append"
            emb_df.write.mode(mode).parquet(parquet_path)
            offset += batch_size
            batch_idx += 1
