from typing import Any, Optional
import tensorflow as tf
from src.utils.models.base import BaseModel


class CategoricalModel(BaseModel):
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
            random_seed=random_seed,
            is_sparse=True
        )
        self.num_classes = num_classes

    def _build_model(self) -> tf.keras.Model:
        model = tf.keras.Sequential([
            tf.keras.layers.Input(shape=(self.input_shape,)),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.Dropout(0.4),
            tf.keras.layers.Dense(128, activation='relu'),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dense(self.num_classes, activation='softmax')
        ])
        
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
