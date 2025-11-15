from pyspark.ml.clustering import KMeans, KMeansModel
from pyspark.ml.evaluation import ClusteringEvaluator
import numpy as np
from pyspark.sql import SparkSession, DataFrame

from src.utils.spark import SparkUtils

class KMeansParameter:
    def __init__(self, comb_id: str, n_clusters: int, max_iter: int = 300, random_state: int = 42):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.random_state = random_state
        self.comb_id = comb_id

class KMeansClustering:
    def __init__(
        self, k_parameters: list[KMeansParameter], spark_utils: SparkUtils,
        table_prefix: str, catalog: str, id_col: str, features_col: str, prediction_col: str
    ):
        self.table_prefix = table_prefix
        self.id_col = id_col
        self.features_col = features_col
        self.prediction_col = prediction_col
        self.catalog = catalog
        self.k_parameters = k_parameters
        self.spark_utils = spark_utils
        self.spark = spark_utils.spark
        self.models = {}
        self.transformed_dfs = {}
        self.eval_results = {}
        self.loaded_model = None
        self.chosen_comb_id = None
        self.train_df = None

    def fit(self, df: DataFrame) -> np.ndarray:
        self.train_df = df
        for k_parameter in self.k_parameters:
            print(f"Training K-Means: {k_parameter.comb_id} - K: {k_parameter.n_clusters} | Iters: {k_parameter.max_iter}")
            kmeans = KMeans(
                k=k_parameter.n_clusters, maxIter=k_parameter.max_iter, 
                seed=k_parameter.random_state,
                featuresCol=self.features_col,
                predictionCol=self.prediction_col,
                distanceMeasure="cosine"
            )
            kmeans = kmeans.fit(df)
            transformed_df = kmeans.transform(df)
            self.models[k_parameter.comb_id] = kmeans
            print(f"Saving K-Means: {k_parameter.comb_id} - K: {k_parameter.n_clusters} | Iters: {k_parameter.max_iter}")
            (
                self.models[k_parameter.comb_id]
                    .write().overwrite()
                    .save(
                        self.spark_utils.path(
                            f'kmeans_model_{k_parameter.comb_id}', catalog = self.catalog)
                        )
            )
            (
                transformed_df
                    .select(self.id_col, self.prediction_col)
                        .write
                        .format('delta')
                        .mode('overwrite')
                        .option('overwriteSchema', 'true')
                        .save(
                            self.spark_utils.path(
                                f'kmeans_transformed_{self.table_prefix}_fit_{k_parameter.comb_id}', catalog = self.catalog)
                            )
            )
            print(f"Reading back transformed K-Means: {k_parameter.comb_id} - K: {k_parameter.n_clusters} | Iters: {k_parameter.max_iter}")
            transformed_df = self.spark.read.format('delta').load(self.spark_utils.path(
                f'kmeans_transformed_{self.table_prefix}_fit_{k_parameter.comb_id}', catalog = self.catalog)
            )
            self.transformed_dfs[k_parameter.comb_id] = transformed_df
    
    def load(self, comb_id: str) -> KMeansModel:
        self.chosen_comb_id = comb_id
        self.loaded_model = KMeansModel.load(self.spark_utils.path(f'kmeans_model_{comb_id}', catalog = self.catalog))
        return self.loaded_model

    def transform(self, df: DataFrame) -> DataFrame:
        transformed_df = self.loaded_model.transform(df)
        (
            transformed_df
                .select(self.id_col, self.prediction_col)
                    .write
                    .format('delta')
                    .mode('overwrite')
                    .option('overwriteSchema', 'true')
                    .save(self.spark_utils.path(
                        f'kmeans_transformed_{self.table_prefix}_{self.chosen_comb_id}', 
                        catalog = self.catalog
                    ))
        )

        transformed_df = self.spark.read.format('delta').load(self.spark_utils.path(
            f'kmeans_transformed_{self.table_prefix}_{self.chosen_comb_id}', catalog = self.catalog)
        )
        return transformed_df

    def evaluate(self) -> float:
        for k_parameter in self.k_parameters:
            print(f"Evaluating K-Means: {k_parameter.comb_id} - K: {k_parameter.n_clusters} | Iters: {k_parameter.max_iter}")
            silhouette_score = ClusteringEvaluator(
                featuresCol=self.features_col,
                predictionCol=self.prediction_col,
                metricName="silhouette",
                distanceMeasure="cosine"
            ).evaluate(
                self.train_df.join(
                    self.transformed_dfs[k_parameter.comb_id],
                    self.id_col,
                    "left"
                ).select(
                    self.features_col,
                    self.prediction_col
                )
            )
            self.eval_results[k_parameter.comb_id] = silhouette_score
        return self.eval_results    
    
    def evaluate_current(self, df_train: str, df_clusters: str) -> float:
        silhouette_score = ClusteringEvaluator(
            featuresCol=self.features_col,
            predictionCol=self.prediction_col,
            metricName="silhouette",
            distanceMeasure="cosine"
        ).evaluate(
            df_train.join(
                df_clusters,
                self.id_col,
                "left"
            ).select(
                self.features_col,
                self.prediction_col
            )
        )
        return silhouette_score