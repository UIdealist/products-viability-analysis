from pyspark.sql import DataFrame
from pyspark.ml.evaluation import ClusteringEvaluator

def evaluate_clustering(df: DataFrame, column: str, prediction_column: str) -> float:
    silhouette_score = ClusteringEvaluator(
        featuresCol=column,
        predictionCol=prediction_column,
        metricName="silhouette",
        distanceMeasure="cosine"
    ).evaluate(df)
    return silhouette_score