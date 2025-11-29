import os
import tensorflow as tf
import tensorflow_io as tfio
from typing import Tuple, List
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from src.utils.spark import SparkUtils


class DatasetSplitter:
    def __init__(
        self,
        spark_utils: SparkUtils,
        delta_table_path: str,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        max_partitions: int = 10,
        random_seed: int = 42
    ):
        if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-6:
            raise ValueError("train_ratio + val_ratio + test_ratio must equal 1.0")
        
        self.spark_utils = spark_utils
        self.spark = spark_utils.spark
        self.delta_table_path = delta_table_path
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.max_partitions = max_partitions
        self.random_seed = random_seed
        
        base_path = self.delta_table_path.rstrip('/')
        self.train_path = f"{base_path}_train"
        self.val_path = f"{base_path}_val"
        self.test_path = f"{base_path}_test"

    def split(self, overwrite: bool = False) -> Tuple[str, str, str]:
        df = self.spark.read.format('delta').load(self.delta_table_path)
        
        df_with_rand = df.withColumn('_split_rand', F.rand(self.random_seed))
        
        train_threshold = self.train_ratio
        val_threshold = self.train_ratio + self.val_ratio
        
        train_df = df_with_rand.filter(F.col('_split_rand') < train_threshold).drop('_split_rand')
        val_df = df_with_rand.filter(
            (F.col('_split_rand') >= train_threshold) & 
            (F.col('_split_rand') < val_threshold)
        ).drop('_split_rand')
        test_df = df_with_rand.filter(F.col('_split_rand') >= val_threshold).drop('_split_rand')
        
        mode = "overwrite" if overwrite else "errorifexists"
        
        train_df.coalesce(self.max_partitions).write.format('parquet').mode(mode).save(self.train_path)
        val_df.coalesce(self.max_partitions).write.format('parquet').mode(mode).save(self.val_path)
        test_df.coalesce(self.max_partitions).write.format('parquet').mode(mode).save(self.test_path)
        
        return self.train_path, self.val_path, self.test_path

    def generate_io_dataset(
        self,
        dataset_type: str,
        target_columns: List[bytes]
    ) -> tf.data.Dataset:
        if dataset_type == 'train':
            path = self.train_path
        elif dataset_type == 'val':
            path = self.val_path
        elif dataset_type == 'test':
            path = self.test_path
        else:
            raise ValueError("dataset_type must be 'train', 'val', or 'test'")
        
        
        files = tf.io.gfile.glob(f"{path}/*.parquet")
        if not files:
            return tf.data.Dataset.from_tensor_slices(([], []))
        
        datasets = []
        dataset = None
        for i, f in enumerate(files):
            datasets.append(tfio.IODataset.from_parquet(f))
            if i > 0:
                dataset = dataset.concatenate(datasets[i])
            else:
                dataset = datasets[i]
        
        def split_xy(row):
            target_cols = [k for k in row.keys() if k in target_columns]
            y = tf.stack([tf.cast(row[k], tf.float32) for k in target_cols], axis=-1)
            feature_cols = [k for k in row.keys() if k not in target_cols]
            x = tf.stack([tf.cast(row[k], tf.float32) for k in feature_cols], axis=-1)
            return x, y
        
        dataset = dataset.map(split_xy, num_parallel_calls=tf.data.AUTOTUNE)
        return dataset

    def get_train_path(self) -> str:
        return self.train_path

    def get_val_path(self) -> str:
        return self.val_path

    def get_test_path(self) -> str:
        return self.test_path

