import os
import tensorflow as tf
from typing import Optional, Any, Tuple
from src.utils.models.base import BaseModel
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
import numpy as np
import mlflow


class BinaryModel(BaseModel):
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
        random_seed: int = 42
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

    def _build_model(self) -> tf.keras.Model:
        model = tf.keras.Sequential([
            tf.keras.layers.Input(shape=(self.input_shape,), name='input'),
            tf.keras.layers.Dense(256, activation='relu', name='dense_0'),
            tf.keras.layers.Dropout(0.4, name='dropout_0'),
            tf.keras.layers.Dense(128, activation='relu', name='dense_1'),
            tf.keras.layers.Dropout(0.3, name='dropout_1'),
            tf.keras.layers.Dense(64, activation='relu', name='dense_2'),
            tf.keras.layers.Dropout(0.2, name='dropout_2'),
            tf.keras.layers.Dense(32, activation='relu', name='dense_3'),
            tf.keras.layers.Dense(1, activation='sigmoid', name='output')
        ])
        
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        return model

    def prediction_simple(self, x):
        predictions = self.model.predict(x, verbose=0)
        return np.where(predictions > 0.5, 1, 0)