import pyspark.sql.functions as F
from pyspark.sql import SQLContext, SparkSession, types as T, DataFrame
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import BinaryType
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

import os
import logging
logger = logging.getLogger('SimpleSparkCreator')
logger.setLevel(logging.DEBUG)

from delta import configure_spark_with_delta_pip

# Check if env is on windows
if os.name == 'nt':
    METASTORE_PATH = "D:\\Maestría\\Amazon Reviews Code\\data"
    WAREHOUSE_PATH = "D:\\Maestría\\Amazon Reviews Code\\data\\warehouse"
else:
    METASTORE_PATH = "/mnt/d/Maestría/Amazon Reviews Code/data"
    WAREHOUSE_PATH = "/mnt/d/Maestría/Amazon Reviews Code/data/warehouse"

class SimpleSparkUtils:
    def __init__(self, name='metastore_db'):
        self.metastore_schema_path = METASTORE_PATH
        self.name = name

        active_spark = SparkSession.getActiveSession()
        if active_spark is not None:
            logger.info("[SimpleSparkUtils] Stopping existing SparkSession...")
            active_spark.stop()

        # Minimal Spark configuration to avoid Java issues
        builder = (
            SparkSession.builder \
                .appName(name) \
                .config("spark.jars.packages", "io.delta:delta-spark_2.12:3.0.0") \
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
                .config("spark.sql.warehouse.dir", f"{self.metastore_schema_path}/.warehouse") \
                .config("spark.driver.memory", "8G") \
                .config("spark.driver.maxResultSize", "2G") \
                .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
                .config("spark.kryoserializer.buffer.max", "1G") \
                .config("javax.jdo.option.ConnectionURL", f"jdbc:derby:{self.metastore_schema_path}/{self.name};create=true") \
                .config("spark.sql.adaptive.enabled", "false") \
                .config("spark.sql.adaptive.coalescePartitions.enabled", "false") \
                .master("local[1]")
        )

        logger.info("Starts creating minimal environment")
        self.spark = configure_spark_with_delta_pip(builder).getOrCreate()
        logger.info("Ends creating minimal environment")

        self.spark.sparkContext.setLogLevel("ERROR")

    def get_meta_items(self):
        return self.spark.read.parquet(self.path('meta_items'))

    def get_meta_items_sample(self, n=10_000):
        return (
            self.get_meta_items()
                .limit(n)
                .toPandas()
        )

    def close(self): 
        self.spark.stop()

    def path(self, name, catalog='silver'):
        return f'{WAREHOUSE_PATH}/{catalog}/{name}'
