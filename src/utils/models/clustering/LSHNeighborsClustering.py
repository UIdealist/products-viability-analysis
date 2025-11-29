import itertools
import uuid
from pyspark.ml.feature import BucketedRandomProjectionLSH, BucketedRandomProjectionLSHModel
import numpy as np
from pyspark.sql import SparkSession, DataFrame, Window
from pyspark.sql import types as T, functions as F, Column

from src.utils.spark import SparkUtils

schema_matches = T.StructType([
    T.StructField("parent_asin_a", T.StringType(), True),
    T.StructField("parent_asin_b", T.StringType(), True),
    T.StructField("cosine_sim", T.DoubleType(), True)
])

schema_batches_processed = T.StructType([
    T.StructField("batch_idx_a", T.IntegerType(), True),
    T.StructField("batch_idx_b", T.IntegerType(), True),
])

class LSHNeighborsClusteringParameter:
    def __init__(self, comb_id: str, n_neighbors: int, min_cosine_similarity: float, bucket_length: float, num_hash_tables: int):
        self.n_neighbors = n_neighbors
        self.min_cosine_similarity = min_cosine_similarity
        self.comb_id = comb_id
        self.bucket_length = bucket_length
        self.num_hash_tables = num_hash_tables

class LSHNeighborsClustering:
    def __init__(
        self, lsh_parameters: LSHNeighborsClusteringParameter, spark_utils: SparkUtils,
        table_prefix: str, catalog: str, id_col: str, features_col: str, hashes_col: str,
        batch_size: int = 1000
    ):
        self.table_prefix = table_prefix
        self.id_col = id_col
        self.features_col = features_col
        self.hashes_col = hashes_col
        self.catalog = catalog
        self.lsh_parameters = lsh_parameters
        self.spark_utils = spark_utils
        self.spark = spark_utils.spark
        self.models = {}
        self.transformed_dfs = {}
        self.eval_results = {}
        self.loaded_model = None
        self.chosen_comb_id = None
        self.train_df = None
        self.lsh_model : BucketedRandomProjectionLSHModel = None

        self.lsh = BucketedRandomProjectionLSH(
            inputCol=features_col,
            outputCol=hashes_col,
            bucketLength=1.0,
            numHashTables=5
        )

        self.baching_df = None
        self.batch_size = batch_size

        self.pairs_path = self.spark_utils.path(
            f"lsh_pairs_{self.table_prefix}_{self.lsh_parameters.comb_id}",
            catalog = self.catalog
        )

    def prepare_batching(self, df: DataFrame) -> DataFrame:
        batching_df = df.select(
            F.col(self.id_col),
            F.floor(F.row_number().over(
                Window.orderBy(F.col(self.id_col).asc())
            ) / self.batch_size).alias('batch_idx')
        )

        (
            batching_df
                .write
                .format('delta')
                .mode('overwrite')
                .option('overwriteSchema', 'true')
                .save(self.spark_utils.path(
                    f"lsh_pairs_batching_{self.table_prefix}_{self.lsh_parameters.comb_id}",
                    catalog = self.catalog
                ))
        )

        self.baching_df = self.spark.read.format('delta').load(self.spark_utils.path(
            f"lsh_pairs_batching_{self.table_prefix}_{self.lsh_parameters.comb_id}",
            catalog = self.catalog
        ))

        return self.baching_df

    def prepare_possible_batch_pairs(self) -> DataFrame:
        n = self.baching_df.agg(
            F.max(F.col('batch_idx')).alias('max_batch_idx')
        ).collect()[0]['max_batch_idx']
        print(f"[INFO] Total batches: {n}")
        combos = list(itertools.combinations_with_replacement(range(1, n + 1), 2))
        print(f"[INFO] Total possible batch pairs: {len(combos)}")
        schema_possible_batch_pairs = T.StructType([
            T.StructField("batch_idx_a", T.IntegerType(), True),
            T.StructField("batch_idx_b", T.IntegerType(), True),
        ])
        df = self.spark.createDataFrame(combos, schema_possible_batch_pairs)
        df.write.format('delta').mode('overwrite').save(self.spark_utils.path(
            f"lsh_pairs_possible_batch_pairs_{self.table_prefix}_{self.lsh_parameters.comb_id}",
            catalog = self.catalog
        ))

    def load_batching(self) -> DataFrame:
        self.baching_df = self.spark.read.format('delta').load(self.spark_utils.path(
            f"lsh_pairs_batching_{self.table_prefix}_{self.lsh_parameters.comb_id}",
            catalog = self.catalog
        ))
        return self.baching_df
    
    def load_possible_batch_pairs(self) -> DataFrame:
        self.possible_batch_pairs_df = self.spark.read.format('delta').load(self.spark_utils.path(
            f"lsh_pairs_possible_batch_pairs_{self.table_prefix}_{self.lsh_parameters.comb_id}",
            catalog = self.catalog
        ))
        return self.possible_batch_pairs_df

    def fit(self, df: DataFrame) -> np.ndarray:
        self.train_df = df
        self.lsh_model = self.lsh.fit(df)
        return self.lsh_model

    def COSINE_TO_EUCLIDEAN_DISTANCES(self, cosine_distance: Column) -> Column:
        return (2 * cosine_distance) ** 0.5

    def EUCLIDEAN_TO_COSINE_DISTANCES(self, euclidean_distance: Column) -> Column:
        return (euclidean_distance ** 2) / 2

    def _find_pairs(
        self, df_x: DataFrame, df_y: DataFrame
    ) -> DataFrame:
        euclidean_threshold = self.COSINE_TO_EUCLIDEAN_DISTANCES(1 - self.lsh_parameters.min_cosine_similarity)
        similar_pairs = self.lsh_model.approxSimilarityJoin(
            df_x.alias("a"),
            df_y.alias("b"),
            euclidean_threshold,
            distCol="distance"
        ).filter(
            (F.col('distance') > -euclidean_threshold) &
            (F.col('datasetA.parent_asin') != F.col('datasetB.parent_asin'))
        ).select(
            F.col("datasetA.parent_asin").alias("parent_asin_a"),
            F.col("datasetB.parent_asin").alias("parent_asin_b"),
            (1 - self.EUCLIDEAN_TO_COSINE_DISTANCES(F.col("distance"))).alias("cosine_sim")
        )

        tmp_table_name = self.spark_utils.path(
            f"tmp_table_{str(uuid.uuid4()).replace('-', '_')}",
            catalog = self.catalog
        )
        similar_pairs.write.format('delta').mode('overwrite').save(tmp_table_name)
        similar_pairs = self.spark.read.format('delta').load(tmp_table_name)
        return similar_pairs, tmp_table_name

    def find_pairs(
        self, df: DataFrame,
        overwrite_full: bool = False
    ) -> DataFrame:
        target_path = self.pairs_path

        processed_target_path = self.spark_utils.path(
            f"lsh_pairs_processed_{self.table_prefix}_{self.lsh_parameters.comb_id}",
            catalog = self.catalog
        )

        if overwrite_full:
            print("[IMPORTANT] Cleaning up existing pairs")
            df_empty = self.spark.createDataFrame([], schema_matches)
            df_empty_processed = self.spark.createDataFrame([], schema_batches_processed)
            (
                df_empty
                    .write.format('delta')
                    .mode('overwrite').option('overwriteSchema', 'true')
                    .save(target_path)
            )
            (
                df_empty_processed
                    .write.format('delta')
                    .mode('overwrite').option('overwriteSchema', 'true')
                    .save(processed_target_path)
            )
        
        total_batches = self.baching_df.agg(
            F.max(F.col('batch_idx')).alias('max_batch_idx')
        ).collect()[0]['max_batch_idx']

        while True:
            existing_batches_processed = self.spark.read.format('delta').load(processed_target_path)

            print(f"[INFO] Existing batches processed: {existing_batches_processed.count()}")

            missing_batch_pairs = self.possible_batch_pairs_df.subtract(existing_batches_processed).orderBy(
                F.col('batch_idx_a').asc(), F.col('batch_idx_b').asc()
            ).limit(1)
            if missing_batch_pairs.count() == 0:
                print(f"[INFO] All batches have been processed")
                return
                
            batches_to_process_a = missing_batch_pairs.collect()[0]['batch_idx_a']
            batches_to_process_b = missing_batch_pairs.collect()[0]['batch_idx_b']

            print(f"[INFO] Saving batch A: {batches_to_process_a} and batch B: {batches_to_process_b}")

            batch_a = (
                df.alias('A').join(
                    self.baching_df.alias('B'),
                    F.col('A.parent_asin') == F.col('B.parent_asin'),
                    'inner'
                )
                .filter(F.col('B.batch_idx') == F.lit(batches_to_process_a))
                .select(F.col('A.*'))
            )
            
            batch_a.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').save(self.spark_utils.path(
                f"lsh_pairs_batch_a_tmp_{self.table_prefix}_{self.lsh_parameters.comb_id}",
                catalog = self.catalog
            ))

            batch_a = self.spark.read.format('delta').load(self.spark_utils.path(
                f"lsh_pairs_batch_a_tmp_{self.table_prefix}_{self.lsh_parameters.comb_id}",
                catalog = self.catalog
            ))

            batch_b = (
                df.alias('A').join(
                    self.baching_df.alias('B'),
                    F.col('A.parent_asin') == F.col('B.parent_asin'),
                    'inner'
                )
                .filter(F.col('B.batch_idx') == F.lit(batches_to_process_b))
                .select(F.col('A.*'))
            )

            batch_b.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').save(self.spark_utils.path(
                f"lsh_pairs_batch_b_tmp_{self.table_prefix}_{self.lsh_parameters.comb_id}",
                catalog = self.catalog
            ))

            batch_b = self.spark.read.format('delta').load(self.spark_utils.path(
                f"lsh_pairs_batch_b_tmp_{self.table_prefix}_{self.lsh_parameters.comb_id}",
                catalog = self.catalog
            ))

            print(f"[INFO] Finding missing pairs for batch A: {batches_to_process_a} (size: {batch_a.count()}) and batch B: {batches_to_process_b} (size: {batch_b.count()})")
            
            similar_pairs, tmp_table_name = self._find_pairs(batch_a, batch_b)
            print(f"[INFO] Found {similar_pairs.count()} pairs")
            similar_pairs.write.format('delta').mode('append').save(target_path)
            print(f"[INFO] Deleting temporary tables")
            self.spark_utils.drop_table(tmp_table_name)

            df_processed_records = self.spark.createDataFrame([
                {
                    'batch_idx_a': batches_to_process_a,
                    'batch_idx_b': batches_to_process_b
                }
            ], schema_batches_processed)
            (
                df_processed_records
                    .write.format('delta')
                    .mode('append').option('overwriteSchema', 'true')
                    .save(processed_target_path)
            )

    def find_pairs_for_df(
        self,
        source_df: DataFrame,
        target_df: DataFrame,
    ) -> DataFrame:
        euclidean_threshold = self.COSINE_TO_EUCLIDEAN_DISTANCES(1 - self.lsh_parameters.min_cosine_similarity)
        print(f"[INFO] Euclidean threshold: {euclidean_threshold}")
        self.similar_pairs = self.lsh_model.approxSimilarityJoin(
            source_df.alias("a"),
            target_df.alias("b"),
            euclidean_threshold,
            distCol="distance"
        )

        self.similar_pairs_filtered = self.similar_pairs.filter(
            (F.col('distance') > -euclidean_threshold)
        ).select(
            F.col(f"datasetB.{self.id_col}").alias(f"{self.id_col}"),
            F.col(f"datasetB.{self.features_col}").alias(f"{self.features_col}"),
            (1 - self.EUCLIDEAN_TO_COSINE_DISTANCES(F.col("distance"))).alias("cosine_sim")
        )

        return self.similar_pairs_filtered