from pyspark.sql import functions as F

def check_null_values( df, column ):
    total = df.count()
    null_count = df.filter( F.col(column).isNull() ).count()
    non_null_count = total - null_count
    return (null_count, non_null_count, total)

def check_empty_arrays( df, column ):
    total = df.count()
    empty_count = df.filter(
        F.col(column).isNull() |
        (F.size(F.col(column)) == F.lit(0))
    ).count()
    non_null_count = total - empty_count
    return (empty_count, non_null_count, total)