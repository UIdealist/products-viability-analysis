from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from pyspark.sql.types import StructType, StructField, StringType, MapType, IntegerType
from pyspark.ml.feature import StringIndexer, OneHotEncoder
from pyspark.ml import Pipeline
import re
import json

class JsonNormalizer:
    def __init__(self):
        pass
    
    def normalize_json_column(self, df: DataFrame, json_column: str, parent_asin_column: str = 'parent_asin') -> DataFrame:
        def extract_json_pairs(json_str):
            if json_str is None or json_str == "":
                return []
            
            try:
                json_obj = json.loads(json_str)
                if isinstance(json_obj, dict):
                    return [(k, str(v)) for k, v in json_obj.items()]
                return []
            except:
                return []
        
        from pyspark.sql.types import ArrayType
        
        extract_udf = F.udf(extract_json_pairs, 
                           ArrayType(StructType([
                               StructField("key", StringType(), True),
                               StructField("value", StringType(), True)
                           ])))
        
        normalized_df = (
            df
            .select(
                F.col(parent_asin_column),
                F.explode(extract_udf(F.col(json_column))).alias("json_data")
            )
            .select(
                F.col(parent_asin_column),
                F.col("json_data.key").alias("clave"),
                F.col("json_data.value").alias("valor")
            )
            .filter(F.col("clave").isNotNull())
        )
        
        return normalized_df
    
    def normalize_json_column_simple(self, df: DataFrame, json_column: str, parent_asin_column: str = 'parent_asin') -> DataFrame:
        def extract_pairs(json_str):
            if not json_str:
                return []
            try:
                data = json.loads(json_str)
                return [(k, str(v)) for k, v in data.items()] if isinstance(data, dict) else []
            except:
                return []
        
        from pyspark.sql.types import ArrayType
        
        pairs_udf = F.udf(extract_pairs, 
                         ArrayType(StructType([
                             StructField("key", StringType()),
                             StructField("value", StringType())
                         ])))
        
        return (df
                .select(parent_asin_column, F.explode(pairs_udf(json_column)).alias("pair"))
                .select(parent_asin_column, F.col("pair.key").alias("clave"), F.col("pair.value").alias("valor"))
                .filter(F.col("clave").isNotNull()))

class OneHotColumnEncoder:
    def __init__(self):
        pass
    
    def _standardize_column_name(self, name):
        name = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')
        if name and name[0].isdigit():
            name = 'col_' + name
        return name.lower() if name else 'unnamed_column'
    
    def one_hot_encode(self, df, input_column, output_prefix=None):
        if output_prefix is None:
            output_prefix = input_column

        def standarize_value(value):
            name = re.sub(r'[^a-zA-Z0-9_]', '_', str(value))
            name = re.sub(r'_+', '_', name)
            name = name.strip('_')
            if name and name[0].isdigit():
                name = 'col_' + name
            return name.lower() if name else 'unnamed_column'

        standarize_value_udf = F.udf(standarize_value, StringType())

        df = df.withColumn(input_column, standarize_value_udf(F.col(input_column)))
        
        categories = [row[0] for row in df.select(input_column).distinct().collect()]
        exprs = [
            (F.when(F.col(input_column) == cat, 1).otherwise(0)).alias(f"{output_prefix}_{self._standardize_column_name(cat)}")
            for cat in categories
        ]
        return df.select("*", *exprs)
    
    def one_hot_encode_ml(self, df, input_column, output_prefix=None, drop_last=False):
        if output_prefix is None:
            output_prefix = input_column
        
        string_indexer = StringIndexer(
            inputCol=input_column,
            outputCol=f"{input_column}_indexed"
        )
        
        one_hot_encoder = OneHotEncoder(
            inputCol=f"{input_column}_indexed",
            outputCol=f"{output_prefix}_encoded",
            dropLast=drop_last
        )
        
        pipeline = Pipeline(stages=[string_indexer, one_hot_encoder])
        model = pipeline.fit(df)
        result_df = model.transform(df)
        
        return result_df
    
    def one_hot_encode_simple(self, df, input_column, output_prefix=None):
        if output_prefix is None:
            output_prefix = input_column
        
        unique_values = df.select(input_column).distinct().rdd.map(lambda x: x[0]).collect()
        unique_values = [v for v in unique_values if v is not None]
        
        result_df = df
        
        for i, value in enumerate(unique_values):
            col_name = f"{output_prefix}_{self._standardize_column_name(str(value))}"
            result_df = result_df.withColumn(
                col_name,
                F.when(F.col(input_column) == value, 1).otherwise(0)
            )
        
        return result_df

class MultiColumnOneHotEncoder:
    def __init__(self):
        pass
    
    def _standardize_column_name(self, name):
        name = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')
        if name and name[0].isdigit():
            name = 'col_' + name
        return name.lower() if name else 'unnamed_column'
    
    def multi_one_hot_encode(self, df, input_column, output_prefix=None):
        if output_prefix is None:
            output_prefix = input_column

        def standarize_value(value):
            return self._standardize_column_name(str(value))

        standarize_value_udf = F.udf(standarize_value, StringType())

        df = df.withColumn(input_column, standarize_value_udf(F.col(input_column)))

        categories = [row[0] for row in df.select(F.col(input_column)).distinct().collect()]
        print(categories)

        df_multihot = df
        for column in categories:
            df_multihot = df_multihot.withColumn(
                f"{output_prefix}_{column}",
                F.when(F.col(input_column) == column, 1).otherwise(0)
            )
        return df_multihot
    
    def multi_one_hot_encode_udf(self, df, input_column, output_prefix=None):
        if output_prefix is None:
            output_prefix = input_column
        
        def create_one_hot_vector(array_col, target_value):
            if array_col is None:
                return 0
            return 1 if target_value in array_col else 0
        
        all_values = set()
        for row in df.select(input_column).rdd.collect():
            if row[0] is not None and isinstance(row[0], list):
                all_values.update(row[0])
        
        all_values = [v for v in all_values if v is not None]
        
        if not all_values:
            return df
        
        result_df = df
        
        for value in all_values:
            col_name = f"{output_prefix}_{self._standardize_column_name(str(value))}"
            one_hot_udf = F.udf(
                lambda arr: create_one_hot_vector(arr, value),
                IntegerType()
            )
            result_df = result_df.withColumn(col_name, one_hot_udf(F.col(input_column)))
        
        return result_df

class SampleDataset:
    def __init__(self):
        pass
    
    def sample_dataset_weighted(
        self, df: DataFrame, 
        based_column: str,
        scale : float = 1.0
    ):

        counts = df.groupBy(based_column).count().collect()

        print("Counts:", counts)

        total = sum([r["count"] for r in counts])
        freqs = {r[based_column]: r["count"] / total for r in counts}

        max_freq = max(freqs.values())
        sampling_ratios = {cls: max_freq / f for cls, f in freqs.items()}        

        print("Sampling ratios:", sampling_ratios)

        scale = min(1.0, scale / max(sampling_ratios.values()))
        sampling_fractions = {cls: min(1.0, v * scale) for cls, v in sampling_ratios.items()}

        df_balanced = df.sampleBy(based_column, fractions=sampling_fractions, seed=42)

        return df_balanced