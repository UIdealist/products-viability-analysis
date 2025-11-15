import tensorflow as tf
from src.utils.models.base import BaseModel


class RegressionModel(BaseModel):
    def __init__(self, model_name: str, metastore_path: str, tracking_uri: str = "file:///tmp/mlruns"):
        super().__init__(model_name, metastore_path, tracking_uri)

    def _build_model(self) -> tf.keras.Model:
        model = tf.keras.Sequential([
            tf.keras.layers.Input(shape=(self.input_shape,), name='input_layer'),
            tf.keras.layers.Dense(512, activation='relu', name='hidden_layer_0'),
            tf.keras.layers.BatchNormalization(name='batch_norm_0'),
            tf.keras.layers.Dropout(0.4, name='dropout_0'),
            tf.keras.layers.Dense(256, activation='relu', name='hidden_layer_1'),
            tf.keras.layers.BatchNormalization(name='batch_norm_1'),
            tf.keras.layers.Dropout(0.3, name='dropout_1'),
            tf.keras.layers.Dense(128, activation='relu', name='hidden_layer_2'),
            tf.keras.layers.BatchNormalization(name='batch_norm_2'),
            tf.keras.layers.Dropout(0.25, name='dropout_2'),
            tf.keras.layers.Dense(64, activation='relu', name='hidden_layer_3'),
            tf.keras.layers.BatchNormalization(name='batch_norm_3'),
            tf.keras.layers.Dropout(0.2, name='dropout_3'),
            tf.keras.layers.Dense(32, activation='relu', name='hidden_layer_4'),
            tf.keras.layers.Dense(1, name='output_layer')
        ])
        
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='mean_squared_error',
            metrics=['mae', 'mse']
        )
        
        return model
