from typing import Any, Optional, List
from pyspark.sql import DataFrame
import tensorflow as tf
from src.utils.models.base import BaseModel
import tensorflow_io as tfio
import numpy as np


class BinaryModelCategory(BaseModel):
    def __init__(
        self, 
        model_name: str, 
        metastore_path: str, 
        tracking_uri: str = "file:///tmp/mlruns",
        spark_utils: Optional[Any] = None,
        target_path: Optional[str] = None,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        max_partitions: int = 10,
        random_seed: int = 42,
        n_categories: int = 5,
        n_main_features: int = 100
    ):
        super().__init__(
            model_name, 
            metastore_path, 
            tracking_uri,
            spark_utils=spark_utils,
            target_path=target_path,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            max_partitions=max_partitions,
            random_seed=random_seed,
            is_binary=True
        )
        self.n_categories = n_categories
        self.category_input_shape = n_categories
        self.n_main_features = n_main_features
        self.main_input_shape = n_main_features

    def generate_io_dataset(
        self,
        dataset_type: str,
        category_columns: List[bytes],
        target_columns: List[bytes]
    ) -> tf.data.Dataset:

        if dataset_type == 'train':
            path = self.dataset_splitter.train_path
        elif dataset_type == 'val':
            path = self.dataset_splitter.val_path
        elif dataset_type == 'test':
            path = self.dataset_splitter.test_path
        else:
            raise ValueError("dataset_type must be 'train', 'val', or 'test'")

        files = tf.io.gfile.glob(f"{path}/*.parquet")
        if not files:
            return tf.data.Dataset.from_tensor_slices(([], []))

        dataset = None
        for i, f in enumerate(files):
            ds = tfio.IODataset.from_parquet(f)
            dataset = ds if dataset is None else dataset.concatenate(ds)

        def split_xy(row):
            y = tf.stack([tf.cast(row[k], tf.float32) for k in target_columns], axis=-1)
            x_aux = tf.stack([tf.cast(row[k], tf.float32) for k in category_columns], axis=-1)
            x_main = tf.stack(
                [tf.cast(row[k], tf.float32) for k in row.keys() if k not in category_columns and k not in target_columns],
                axis=-1
            )
            return ({"main_input": x_main, "category_input": x_aux}, y)

        dataset = dataset.map(split_xy, num_parallel_calls=tf.data.AUTOTUNE)
        return dataset

    def prepare_data(
        self,
        spark: Optional[Any] = None,
        dst_dir: Optional[str] = None,
        target_columns: Optional[List[bytes]] = None,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        max_records: Optional[int] = None,
        overwrite: bool = False,
        category_columns: Optional[List[bytes]] = None,
        **dataset_kwargs
    ) -> None:
        train_dataset = self.generate_io_dataset(dataset_type='train', target_columns=target_columns, category_columns=category_columns)
        val_dataset = self.generate_io_dataset(dataset_type='val', target_columns=target_columns, category_columns=category_columns)
        test_dataset = self.generate_io_dataset(dataset_type='test', target_columns=target_columns, category_columns=category_columns)
        
        self.train_dataset = self.configure_dataset(train_dataset, **dataset_kwargs)
        self.val_dataset = self.configure_dataset(val_dataset, **dataset_kwargs)
        self.test_dataset = self.configure_dataset(test_dataset, **dataset_kwargs)

    def _build_model(self):
        main_input = tf.keras.layers.Input(shape=(self.main_input_shape,), name="main_input")
        category_input = tf.keras.layers.Input(shape=(self.category_input_shape,), name="category_input")

        d1 = tf.keras.layers.Dense(256, activation='relu', name="dense_256")(main_input)
        do1 = tf.keras.layers.Dropout(0.4, name="dropout_40")(d1)
        d2 = tf.keras.layers.Dense(128, activation='relu', name="dense_128")(do1)
        do2 = tf.keras.layers.Dropout(0.3, name="dropout_30")(d2)
        d3 = tf.keras.layers.Dense(64, activation='relu', name="dense_64")(do2)
        do3 = tf.keras.layers.Dropout(0.2, name="dropout_20")(d3)
        d4 = tf.keras.layers.Dense(32, activation='relu', name="dense_32")(do3)

        concat = tf.keras.layers.Concatenate(name="concat")([d4, category_input])
        d5 = tf.keras.layers.Dense(16, activation='relu', name="dense_16")(concat)
        d6 = tf.keras.layers.Dense(8, activation='relu', name="dense_8")(d5)

        output = tf.keras.layers.Dense(1, activation='sigmoid', name="output")(d6)

        model = tf.keras.Model(inputs=[main_input, category_input], outputs=output)

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss="binary_crossentropy",
            metrics=["accuracy"]
        )
        return model

    def prediction_simple(self, x):
        predictions = self.model.predict(x, verbose=0)
        return np.where(predictions > 0.5, 1, 0)

    def predict(self, df: DataFrame):
        if self.model is None:
            raise ValueError("Model not created. Call create_model() first.")

        pdf = df.toPandas()

        main_features = pdf.iloc[:, :self.n_main_features].values
        category_features = pdf.iloc[:, self.n_main_features:].values

        predictions = self.model.predict([main_features, category_features])

        return predictions
