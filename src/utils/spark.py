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

# Check if env is on windows
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
                    "com.amazonaws:aws-java-sdk-bundle:1.11.375,"
                    "com.databricks:spark-tensorflow-connector_2.12:1.0.0"
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


""" 

.config("spark.driver.memory","16G")\
                .config("spark.driver.maxResultSize", "0") \
                .config("spark.kryoserializer.buffer.max", "2000M")\
                .config("spark.hadoop.hadoop.native.lib", "false") \
                .config("spark.hadoop.io.nativeio.disable","true") \
                .config("spark.hadoop.fs.defaultFS", "file:///") \
                .config("spark.hadoop.fs.AbstractFileSystem.file.impl", "org.apache.hadoop.fs.local.LocalFs") \
                .config("spark.hadoop.fs.file.impl.disable.cache", "true") \
                    .config("spark.driver.extraJavaOptions", 
"--add-opens=java.base/java.lang=ALL-UNNAMED "
"--add-opens=java.base/java.lang.invoke=ALL-UNNAMED "
"--add-opens=java.base/java.lang.reflect=ALL-UNNAMED "
"--add-opens=java.base/java.io=ALL-UNNAMED "
"--add-opens=java.base/java.net=ALL-UNNAMED "
"--add-opens=java.base/java.nio=ALL-UNNAMED "
"--add-opens=java.base/java.util=ALL-UNNAMED "
"--add-opens=java.base/java.util.concurrent=ALL-UNNAMED "
"--add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED "
"--add-opens=java.base/sun.nio.ch=ALL-UNNAMED "
"--add-opens=java.base/sun.nio.cs=ALL-UNNAMED "
"--add-opens=java.base/sun.security.action=ALL-UNNAMED "
"--add-opens=java.base/sun.util.calendar=ALL-UNNAMED "
"--add-opens=java.security.jgss/sun.security.krb5=ALL-UNNAMED "
"--add-opens=java.base/sun.misc=ALL-UNNAMED "
"--add-opens=java.base/jdk.internal.misc=ALL-UNNAMED "
"--add-exports=java.base/sun.nio.ch=ALL-UNNAMED "
"--add-exports=java.base/sun.misc=ALL-UNNAMED "
"--illegal-access=permit "
"-Djdk.reflect.useDirectMethodHandle=false "
"-Dcom.sun.management.jmxremote "
"-Dcom.sun.management.jmxremote.authenticate=false "
"-Dcom.sun.management.jmxremote.ssl=false") \
.config("spark.executor.extraJavaOptions", 
"--add-opens=java.base/java.lang=ALL-UNNAMED "
"--add-opens=java.base/java.lang.invoke=ALL-UNNAMED "
"--add-opens=java.base/java.lang.reflect=ALL-UNNAMED "
"--add-opens=java.base/java.io=ALL-UNNAMED "
"--add-opens=java.base/java.net=ALL-UNNAMED "
"--add-opens=java.base/java.nio=ALL-UNNAMED "
"--add-opens=java.base/java.util=ALL-UNNAMED "
"--add-opens=java.base/java.util.concurrent=ALL-UNNAMED "
"--add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED "
"--add-opens=java.base/sun.nio.ch=ALL-UNNAMED "
"--add-opens=java.base/sun.nio.cs=ALL-UNNAMED "
"--add-opens=java.base/sun.security.action=ALL-UNNAMED "
"--add-opens=java.base/sun.util.calendar=ALL-UNNAMED "
"--add-opens=java.security.jgss/sun.security.krb5=ALL-UNNAMED "
"--add-opens=java.base/sun.misc=ALL-UNNAMED "
"--add-opens=java.base/jdk.internal.misc=ALL-UNNAMED "
"--add-exports=java.base/sun.nio.ch=ALL-UNNAMED "
"--add-exports=java.base/sun.misc=ALL-UNNAMED "
"--illegal-access=permit "
"-Djdk.reflect.useDirectMethodHandle=false "
"-Dcom.sun.management.jmxremote "
"-Dcom.sun.management.jmxremote.authenticate=false "
"-Dcom.sun.management.jmxremote.ssl=false") \ """