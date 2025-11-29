from typing import Any, Tuple, Optional
from pyspark.sql import DataFrame
import tensorflow as tf
from src.utils.models.base import BaseModel
import tensorflow_io as tfio
import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
import mlflow

@tf.autograph.experimental.do_not_convert
def read_parquet_file(filename):
    return tfio.IODataset.from_parquet(filename)

class CategoryPredictionModel(BaseModel):
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
        num_classes: int = 5
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
            random_seed=random_seed
        )
        self.num_classes = num_classes

    def make_model_callbacks(self) -> list:
        os.makedirs(f"{self.metastore_path}/warehouse/gold.premodeling/{self.model_name}/model_checkpoints", exist_ok=True)

        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor='val_accuracy',
                patience=20,
                restore_best_weights=True,
                verbose=1
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.3,
                patience=8,
                min_lr=1e-7,
                verbose=1
            ),
            tf.keras.callbacks.ModelCheckpoint(
                filepath=f"{self.metastore_path}/warehouse/gold.premodeling/{self.model_name}/model_checkpoints/rating_model_epoch_{{epoch:02d}}.h5",
                monitor='val_accuracy',
                save_best_only=True,
                save_weights_only=False,
                verbose=1
            )
        ]

        return callbacks

    def _build_model(self) -> tf.keras.Model:
        model = tf.keras.Sequential([
            tf.keras.layers.Input(shape=(self.input_shape,)),
            tf.keras.layers.Dense(1024, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dense(128, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dropout(0.25),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dropout(0.25),
            tf.keras.layers.Dense(self.num_classes, activation='softmax')
        ])
        
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model