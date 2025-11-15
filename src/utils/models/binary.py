import tensorflow as tf
from src.utils.models.base import BaseModel


class BinaryModel(BaseModel):
    def __init__(self, model_name: str, metastore_path: str, tracking_uri: str = "file:///tmp/mlruns"):
        super().__init__(model_name, metastore_path, tracking_uri)

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
