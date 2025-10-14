from pyspark.ml.feature import Tokenizer, HashingTF, IDF, IDFModel
from pyspark.sql import DataFrame

class TfidfEncoder:
    def __init__(
        self,
        should_tokenize: bool = False,
        input_col: str = "text",
        output_col: str = "tfidf",
        num_features: int = 100_000,
    ):
        self.should_tokenize = should_tokenize
        self.input_col = input_col
        self.output_col = output_col
        self.num_features = num_features
        self.tokenizer = Tokenizer(inputCol=self.input_col, outputCol="words")
        self.hashing_tf = HashingTF(
            inputCol="words" if self.should_tokenize else self.input_col,
            outputCol="raw_features",
            numFeatures=self.num_features,
        )
        self.idf = IDF(inputCol="raw_features", outputCol=self.output_col)
        self.idf_model: IDFModel = None

    def fit(self, df: DataFrame):
        if self.should_tokenize:
            df = self.tokenizer.transform(df)
        df = self.hashing_tf.transform(df)
        self.idf_model = self.idf.fit(df)
        return self

    def transform(self, df: DataFrame) -> DataFrame:
        if self.idf_model is None:
            raise ValueError("You must call `.fit()` before `.transform()`")
        if self.should_tokenize:
            df = self.tokenizer.transform(df)
        df = self.hashing_tf.transform(df)
        df = self.idf_model.transform(df)
        return df

    def save(self, path: str):
        if self.idf_model is None:
            raise ValueError("No fitted model to save. Call `.fit()` first.")
        self.idf_model.write().overwrite().save(path)

    def load(self, path: str):
        self.idf_model = IDFModel.load(path)
        return self
