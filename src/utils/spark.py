import pyspark.sql.functions as F
from pyspark.sql import SQLContext, SparkSession, types as T, DataFrame
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import BinaryType
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

import requests

from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

import tensorflow as tf
import numpy as np

import pandas as pd

from matplotlib.ticker import FuncFormatter

import tensorflow_hub as hub

import os
import dotenv
import re
import html

import logging
logger = logging.getLogger('SparkCreator')
logger.setLevel(logging.DEBUG)

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
    def __init__( self, name = 'metastore_db' ):

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
                    "org.tensorflow:tensorflow-core-api:0.4.4,"
                    "org.tensorflow:tensorflow-core-platform:0.4.4,"
                    "com.amazonaws:aws-java-sdk-bundle:1.11.375"
                    #"org.tensorflow:spark-tensorflow-connector_2.12:1.15.0"
                    # "com.databricks:spark-tensorflow-connector_2.12:1.0.0"
                ) \
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
                .config("spark.sql.warehouse.dir", f"{self.metastore_schema_path}/.warehouse") \
                .config("javax.jdo.option.ConnectionURL", f"jdbc:derby:{self.metastore_schema_path}/{self.name};create=true") \
                .master("local[2]")
        )

        logger.info("Starts creating environment")
        self.spark = configure_spark_with_delta_pip(builder).getOrCreate()
        logger.info("Ends creating environment")

        self.spark.sparkContext.setLogLevel("ERROR")

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