from pyspark.ml.feature import PCA, PCAModel, Normalizer
from pyspark.sql import DataFrame
import matplotlib.pyplot as plt
import numpy as np
import os
import json

class PCAEncoder:
    def __init__(
        self,
        id_cols: list[str] = [],
        input_col: str = "tfidf",
        output_col: str = "pca_features",
        k: int = 150,
    ):
        self.id_cols = id_cols
        self.input_col = input_col
        self.output_col = output_col
        self.pca_output_col = f"{output_col}_pca"
        self.k = k
        self.pca: PCA = None
        self.model: PCAModel = None
        self.normalizer: Normalizer = None

    def fit(self, df: DataFrame):
        self.pca = PCA(k=self.k, inputCol=self.input_col, outputCol=self.pca_output_col)
        self.model = self.pca.fit(df)
        self.normalizer = Normalizer(inputCol=self.pca_output_col, outputCol=self.output_col, p=2)
        return self

    def transform(self, df: DataFrame) -> DataFrame:
        if self.model is None or self.normalizer is None:
            raise ValueError("You must call `.fit()` or `.load()` before `.transform()`")
        df_pca = self.model.transform(df)
        df_norm = self.normalizer.transform(df_pca)
        return df_norm.select(
            *self.id_cols,
            self.output_col
        )

    def save(self, path: str):
        if self.model is None:
            raise ValueError("No fitted model to save. Call `.fit()` first.")
        os.makedirs(path, exist_ok=True)
        self.model.write().overwrite().save(os.path.join(path, "pca_model"))
        config = {
            "k": self.k,
            "p": 2
        }
        with open(os.path.join(path, "config.json"), "w") as f:
            json.dump(config, f)

    def load(self, path: str):
        self.model = PCAModel.load(os.path.join(path, "pca_model"))
        with open(os.path.join(path, "config.json"), "r") as f:
            cfg = json.load(f)
        self.k = cfg["k"]
        self.normalizer = Normalizer(inputCol=self.pca_output_col, outputCol=self.output_col, p=cfg["p"])
        return self

    def plot_explained_variance_cumsum_binned(
        self,
        bins: int = 10,
        title: str = 'Varianza explicada acumulada (agrupada por rangos de componentes)',
        xlabel: str = 'Rangos de componentes principales',
        ylabel: str = 'Varianza explicada acumulada'
    ):
        if self.model is None:
            raise ValueError("No PCA model fitted or loaded.")
        variance = self.model.explainedVariance.toArray()
        n_components = len(variance)
        group_size = int(np.ceil(n_components / bins))
        cumsum_variance = np.cumsum(variance)
        grouped_cumsum = [cumsum_variance[min((i + 1) * group_size, n_components) - 1] for i in range(bins)]
        x_labels = [f'{i*group_size+1}-{min((i+1)*group_size, n_components)}' for i in range(bins)]
        plt.figure(figsize=(10, 6))
        bars = plt.bar(range(1, bins + 1), grouped_cumsum, tick_label=x_labels)
        plt.xticks(rotation=45)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(title)
        for bar, value in zip(bars, grouped_cumsum):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f'{value:.2f}', ha='center', va='bottom', fontsize=9)
        plt.tight_layout()
        plt.show()
