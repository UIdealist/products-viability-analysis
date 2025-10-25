import tensorflow as tf
from src.utils.models.base import BaseModel
import tensorflow_io as tfio
import os

class CategoryPredictionModel(BaseModel):
    def __init__(self, model_name: str, metastore_path: str, num_classes: int = 5, tracking_uri: str = "file:///tmp/mlruns"):
        super().__init__(model_name, metastore_path, tracking_uri)
        self.num_classes = num_classes

    def generate_io_dataset(
        self, 
        dst_path: str, 
        target_columns: list[bytes]
    ) -> tf.data.Dataset:
        dataset = tfio.IODataset.from_parquet(dst_path)
        
        def split_xy(row):
            target_cols = [k for k in row.keys() if k in target_columns]
            y = tf.stack([tf.cast(row[k], tf.float32) for k in target_cols], axis=-1)
            feature_cols = [k for k in row.keys() if k not in target_cols]
            x = tf.stack([tf.cast(row[k], tf.float32) for k in feature_cols], axis=-1)
            return x, y

        dataset = dataset.map(split_xy)

        return dataset

    def prepare_data(
        self,
        spark,
        src_dir: str,
        dst_dir: str,
        dst_path: str,
        target_columns: list[bytes],
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        **dataset_kwargs
    ) -> None:
        self.copy_dataset_parquet(src_dir, dst_dir, dst_path)
        
        dataset = self.generate_io_dataset(dst_path, target_columns)
        
        self.train_dataset, self.val_dataset, self.test_dataset, self.input_shape = self.split_dataset(
            spark, dst_path, dataset, train_ratio, val_ratio, **dataset_kwargs
        )

    def make_model_callbacks(self) -> list:
        os.makedirs(f"{self.metastore_path}/warehouse/gold.premodeling/{self.model_name}/model_checkpoints", exist_ok=True)

        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=7,
                restore_best_weights=True,
                verbose=1
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=2,
                min_lr=1e-7,
                verbose=1
            ),
            tf.keras.callbacks.ModelCheckpoint(
                filepath=f"{self.metastore_path}/warehouse/gold.premodeling/{self.model_name}/model_checkpoints/rating_model_epoch_{{epoch:02d}}.h5",
                monitor='val_loss',
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
            tf.keras.layers.Dropout(0.4),
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.Dropout(0.4),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(128, activation='relu'),
            tf.keras.layers.Dense(128, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dropout(0.1),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dropout(0.05),
            tf.keras.layers.Dense(16, activation='relu'),
            tf.keras.layers.Dense(8, activation='relu'),
            tf.keras.layers.Dense(self.num_classes, activation='softmax')
        ])
        
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
