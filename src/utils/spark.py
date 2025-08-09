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

METASTORE_PATH = "C:\\Users\\User\\Documents\\Maestría\\Amazon Reviews Code\\data"
WAREHOUSE_PATH = "C:\\Users\\User\\Documents\\Maestría\\Amazon Reviews Code\\data\\warehouse"

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
                .config("spark.jars.packages", "io.delta:delta-spark_2.12:3.2.1,mysql:mysql-connector-java:8.0.33") \
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

    def path(self, name):
        return f'{WAREHOUSE_PATH}/{name}'