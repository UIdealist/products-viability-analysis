from pyspark.ml.feature import PCA, PCAModel
from pyspark.sql import DataFrame

class PCAEncoder:
    def __init__(
        self,
        input_col: str = "tfidf",
        output_col: str = "pca_features",
        k: int = 150
    ):
        self.input_col = input_col
        self.output_col = output_col
        self.k = k
        self.model: PCAModel = None

    def fit(self, df: DataFrame):
        pca = PCA(k=self.k, inputCol=self.input_col, outputCol=self.output_col)
        self.model = pca.fit(df)
        return self

    def transform(self, df: DataFrame) -> DataFrame:
        if self.model is None:
            raise ValueError("You must call `.fit()` before `.transform()`")
        return self.model.transform(df)

    def save(self, path: str):
        if self.model is None:
            raise ValueError("No fitted model to save. Call `.fit()` first.")
        self.model.write().overwrite().save(path)

    def load(self, path: str):
        self.model = PCAModel.load(path)
        return self
