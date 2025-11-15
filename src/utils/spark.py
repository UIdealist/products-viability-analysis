import os
# Configure TensorFlow logging - but don't import TensorFlow yet
# We'll import TensorFlow AFTER Spark initializes to prevent CUDA conflicts
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')  # Suppress INFO and WARNING messages
os.environ.setdefault('TF_XLA_FLAGS', '--tf_xla_enable_xla_devices')
# Allow TensorFlow to use CUDA after Spark initializes
os.environ.setdefault('TF_FORCE_GPU_ALLOW_GROWTH', 'true')

import pyspark.sql.functions as F
from pyspark.sql import SQLContext, SparkSession, types as T, DataFrame
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import BinaryType
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

import requests

from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

import logging
logger = logging.getLogger('SparkCreator')
logger.setLevel(logging.DEBUG)

# DO NOT import TensorFlow here - we'll import it after Spark initializes
# This prevents CUDA initialization conflicts between Spark's Java libraries and Python TensorFlow
# TensorFlow will be imported lazily when needed

import numpy as np

import pandas as pd

from matplotlib.ticker import FuncFormatter
import dotenv
import re
import html
import shutil

from delta import configure_spark_with_delta_pip

from pyspark.ml.functions import predict_batch_udf

METASTORE_PATH = ''

if os.name == 'nt':
    METASTORE_PATH = "D:\\Maestría\\Amazon Reviews Code\\data"
    WAREHOUSE_PATH = "D:\\Maestría\\Amazon Reviews Code\\data\\warehouse"
else:
    METASTORE_PATH = "/mnt/d/Maestría/Amazon Reviews Code/data"
    WAREHOUSE_PATH = "/mnt/d/Maestría/Amazon Reviews Code/data/warehouse"

class SparkUtils:
    def __init__( self, name = 'metastore_db', memory_tuning = False):

        self.metastore_schema_path = METASTORE_PATH
        self.name = name

        active_spark = SparkSession.getActiveSession()
        if active_spark is not None:
            logger.info("[SparkUtils] Stopping existing SparkSession...")
            active_spark.stop()

        builder = (
            SparkSession.builder \
                .appName(name) \
                .config(
                    "spark.jars.packages", 
                    "io.delta:delta-spark_2.12:3.0.0,"
                    "mysql:mysql-connector-java:8.0.33,"
                    "com.johnsnowlabs.nlp:spark-nlp_2.12:5.1.4,"
                    "com.amazonaws:aws-java-sdk-bundle:1.11.375"
                    # Removed TensorFlow Java libraries to prevent CUDA initialization conflicts
                    # If needed, spark-nlp will load them automatically
                    # "org.tensorflow:tensorflow-core-api:0.4.4,"
                    # "org.tensorflow:tensorflow-core-platform:0.4.4,"
                    #"org.tensorflow:spark-tensorflow-connector_2.12:1.15.0"
                    # "com.databricks:spark-tensorflow-connector_2.12:1.0.0"
                ) \
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
                .config("spark.sql.warehouse.dir", f"{self.metastore_schema_path}/.warehouse") \
                .config("javax.jdo.option.ConnectionURL", f"jdbc:derby:{self.metastore_schema_path}/{self.name};create=true") \
                .master("local[2]")
        )

        builder_memory_tuning = (
            SparkSession.builder
                .appName(name)
                
                # ---- MEMORY TUNING ----
                .config("spark.driver.memory", "12g")                     # adjust based on your RAM
                .config("spark.storage.memoryFraction", "0.0")
                .config("spark.shuffle.memoryFraction", "0.1")
                .config("spark.driver.maxResultSize", "0")
                
                # ---- PARQUET STABILITY ----
                .config("spark.sql.parquet.enableVectorizedReader", "false")
                .config("spark.sql.parquet.recordLevelFilter.enabled", "true")
                .config("spark.sql.execution.arrow.maxRecordsPerBatch", "100")
                
                # ---- PARTITIONING ----
                .config("spark.sql.shuffle.partitions", "200")
                .config("spark.default.parallelism", "200")
                
                # ---- JARS ----
                .config(
                    "spark.jars.packages", 
                    "io.delta:delta-spark_2.12:3.0.0,"
                    "mysql:mysql-connector-java:8.0.33,"
                    "com.johnsnowlabs.nlp:spark-nlp_2.12:5.1.4,"
                    "com.amazonaws:aws-java-sdk-bundle:1.11.375"
                )
                
                # ---- DELTA ----
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
                .config("spark.sql.warehouse.dir", f"{self.metastore_schema_path}/.warehouse")
                .config("javax.jdo.option.ConnectionURL", f"jdbc:derby:{self.metastore_schema_path}/{self.name};create=true")

                # ---- LOCAL MODE ----
                # *** MOST IMPORTANT FIX ***
                .master("local[1]")
        )


        logger.info("Starts creating environment")
        # Spark initialization - let Spark's Java libraries initialize CUDA first
        self.spark = configure_spark_with_delta_pip(builder_memory_tuning if memory_tuning else builder).getOrCreate()
        logger.info("Ends creating environment")

        self.spark.sparkContext.setLogLevel("ERROR")
        
        import tensorflow as tf
        try:
            gpus = tf.config.list_physical_devices('GPU')
            if gpus:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(f"TensorFlow configured to use {len(gpus)} GPU(s) with memory growth after Spark initialization")
            else:
                logger.info("No GPUs found, TensorFlow will use CPU")
        except Exception as e:
            logger.warning(f"Could not configure TensorFlow GPU settings: {e}")
        
        self._tf = tf
        
        import tensorflow_hub as hub
        self._hub = hub

    def get_meta_items( self ):
        return self.spark.read.parquet(self.path('meta_items'))

    def get_meta_items_sample( self, n = 10_000 ):
        return (
            self.get_meta_items()
                .limit(n)
                .toPandas()
        )

    def close(self): self.spark.stop()

    def path(self, name, catalog = 'silver'):
        return f'{WAREHOUSE_PATH}/{catalog}/{name}'

    def drop_table(self, table_path: str):
        if os.path.exists(table_path):
            shutil.rmtree(table_path)