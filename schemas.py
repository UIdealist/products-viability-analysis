from pyspark.sql import types as T

item_schema = T.StructType([
    T.StructField("title", T.StringType(), True),
    T.StructField("main_category", T.StringType(), True),
    T.StructField("main_category", T.StringType(), True),
    T.StructField("main_category", T.StringType(), True),
    T.StructField("main_category", T.StringType(), True),
    T.StructField("main_category", T.StringType(), True),
    T.StructField("main_category", T.StringType(), True),
])