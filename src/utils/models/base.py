import os
import shutil
import tensorflow as tf
import tensorflow_io as tfio
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Optional, Union
from ..mlflow_logger import MLflowModelLogger
import pyarrow.parquet as pq


class BaseModel(ABC):
    def __init__(self, model_name: str, metastore_path: str, tracking_uri: str = "file:///tmp/mlruns"):
        self.model_name = model_name
        self.metastore_path = metastore_path
        self.model = None
        self.input_shape = None
        self.train_dataset = None
        self.val_dataset = None
        self.test_dataset = None
        self.run_id = None
        self.mlflow_logger = MLflowModelLogger(
            experiment_name=model_name,
            tracking_uri=tracking_uri
        )
        
    def copy_dataset_parquet(self, src_dir: str, dst_dir: str, dst_path: str) -> None:
        os.makedirs(dst_dir, exist_ok=True)

        parquet_files = [f for f in os.listdir(src_dir) if f.endswith(".parquet")]
        if len(parquet_files) == 0:
            raise FileNotFoundError(f"No parquet files found in {src_dir}")
        elif len(parquet_files) > 1:
            raise RuntimeError(f"Expected exactly one parquet file in {src_dir}, found {len(parquet_files)}")

        src_path = os.path.join(src_dir, parquet_files[0])
        shutil.copy(src_path, dst_path)

    def generate_io_dataset(
        self, 
        dst_path: str, 
        target_columns: list[bytes]
    ) -> tf.data.Dataset:
        files = tf.io.gfile.glob(f"{dst_path}/*.parquet")
        if not files:
            return tf.data.Dataset.from_tensor_slices(([], []))

        print("Files count:", len(files))
        datasets = []
        dataset = None
        for i, f in enumerate(files):
            print("Reading file:", f)
            datasets.append(tfio.IODataset.from_parquet(f))
            if i > 0:
                dataset = dataset.concatenate(datasets[i])
            else:
                dataset = datasets[i]

        def split_xy(row):
            target_cols = [k for k in row.keys() if k in target_columns]
            y = tf.stack([tf.cast(row[k], tf.float32) for k in target_cols], axis=-1)
            feature_cols = [k for k in row.keys() if k not in target_cols]
            x = tf.stack([tf.cast(row[k], tf.float32) for k in feature_cols], axis=-1)
            return x, y

        dataset = dataset.map(split_xy, num_parallel_calls=tf.data.AUTOTUNE)
        return dataset

    def configure_dataset(
        self, 
        dataset: tf.data.Dataset, 
        shuffle_buffer_size: int = 1000,
        batch_size: int = 128,
        prefetch_size: int = tf.data.AUTOTUNE
    ) -> tf.data.Dataset:
        if shuffle_buffer_size > 0:
            dataset = dataset.shuffle(shuffle_buffer_size)
        dataset = dataset.batch(batch_size)
        dataset = dataset.prefetch(prefetch_size)
        return dataset

    def split_dataset(
        self,
        spark,
        dst_path: str, 
        dataset: tf.data.Dataset,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        **dataset_kwargs
    ) -> Tuple[tf.data.Dataset, tf.data.Dataset, tf.data.Dataset, int]:
        original_parquet = spark.read.parquet(dst_path)
        total_records = original_parquet.count()
        
        sample_batch = next(iter(dataset.take(1)))
        X_sample, _ = sample_batch
        input_shape = X_sample.shape[0]
        
        train_size = int(total_records * train_ratio)
        val_size = int(total_records * val_ratio)
        test_size = total_records - train_size - val_size
        
        train_dataset = dataset.take(train_size)
        val_dataset = dataset.skip(train_size).take(val_size)
        test_dataset = dataset.skip(train_size + val_size)
        
        def _configure_dataset(dataset: tf.data.Dataset) -> tf.data.Dataset:
            return self.configure_dataset(
                dataset, 
                **dataset_kwargs
            )
        
        train_dataset = _configure_dataset(train_dataset)
        val_dataset = _configure_dataset(val_dataset)
        test_dataset = _configure_dataset(test_dataset)

        return train_dataset, val_dataset, test_dataset, input_shape

    def make_model_callbacks(self) -> list:
        os.makedirs(f"{self.metastore_path}/warehouse/gold.premodeling/{self.model_name}/model_checkpoints", exist_ok=True)

        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=3,
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

    def prepare_data(
        self,
        spark,
        dst_dir: str,
        target_columns: list[bytes],
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        **dataset_kwargs
    ) -> None:
        dataset = self.generate_io_dataset(dst_dir, target_columns)
        
        self.train_dataset, self.val_dataset, self.test_dataset, self.input_shape = self.split_dataset(
            spark, dst_dir, dataset, train_ratio, val_ratio, **dataset_kwargs
        )

    def create_model(self) -> tf.keras.Model:
        self.model = self._build_model()
        return self.model

    def train(
        self,
        epochs: int = 10,
        verbose: int = 1,
        **fit_kwargs
    ) -> tf.keras.callbacks.History:
        if self.model is None:
            self.create_model()
            
        callbacks = self.make_model_callbacks()
        
        self.history = self.model.fit(
            self.train_dataset,
            validation_data=self.val_dataset,
            epochs=epochs,
            callbacks=callbacks,
            verbose=verbose,
            **fit_kwargs
        )
        
        return self.history

    @abstractmethod
    def _build_model(self) -> tf.keras.Model:
        pass

    def predict(self, features):
        if self.model is None:
            raise ValueError("Model not created. Call create_model() first.")
        return self.model.predict(features)

    def save_model(self, path: str) -> None:
        if self.model is None:
            raise ValueError("Model not created. Call create_model() first.")
        self.model.save(path)

    def load_model(self, run_id: str = None, version: str = None, path: str = None) -> None:
        if path is not None:
            self.model = tf.keras.models.load_model(path)
        else:
            self.model = self.mlflow_logger.load_model(
                run_id=run_id,
                model_name=self.model_name,
                version=version
            )
    
    def log_training_history(self, run_name: str, parameters: Optional[Dict[str, Any]] = None, tags: Optional[Dict[str, str]] = None) -> str:
        if self.model is None:
            raise ValueError("Model not created. Call create_model() first.")
        
        if parameters is None:
            parameters = self._build_default_parameters()
        
        if tags is None:
            tags = self._build_default_tags()
        
        self.run_id = self.mlflow_logger.log_training_history(
            history=self.history,
            run_name=run_name,
            model_name=self.model_name,
            model=self.model,
            parameters=parameters,
            tags=tags
        )
        return self.run_id
    
    def _build_default_parameters(self) -> Dict[str, Any]:
        if self.model is None:
            return {}
        
        optimizer = self.model.optimizer
        optimizer_name = optimizer.__class__.__name__
        learning_rate = float(optimizer.learning_rate.numpy()) if hasattr(optimizer.learning_rate, 'numpy') else float(optimizer.learning_rate)
        
        parameters = {
            "input_shape": self.input_shape,
            "model_name": self.model_name,
            "optimizer": optimizer_name,
            "learning_rate": learning_rate,
            "loss": self.model.loss,
            "metrics": [metric for metric in self.model.metrics_names] if hasattr(self.model, 'metrics_names') else []
        }
        
        if hasattr(self, 'num_classes'):
            parameters["num_classes"] = self.num_classes
        
        return parameters
    
    def _build_default_tags(self) -> Dict[str, str]:
        return {
            "model_type": "neural_network",
            "task": "rating_prediction",
            "dataset": "amazon_reviews",
            "model_name": self.model_name
        }
    
    def get_training_history(self) -> Dict[str, list]:
        if self.run_id is None:
            raise ValueError("Model not logged. Call log_training_history() first.")
        return self.mlflow_logger.get_training_history(self.run_id)
    
    def plot_training_history(self, save_path: Optional[str] = None):
        if self.run_id is None:
            raise ValueError("Model not logged. Call log_training_history() first.")
        return self.mlflow_logger.plot_training_history(self.run_id, save_path)
    
    def list_available_models(self, model_name: str = None, limit: int = 10) -> None:
        target_model_name = model_name or self.model_name
        self.mlflow_logger.print_model_versions(target_model_name, limit)
    
    def get_model_versions(self, model_name: str = None) -> list:
        target_model_name = model_name or self.model_name
        return self.mlflow_logger.list_model_versions(target_model_name)
    
    def load_latest_model(self) -> None:
        self.model = self.mlflow_logger.load_latest_model(self.model_name)
        self.history = self.get_latest_model_history()
    
    def get_latest_model_history(self) -> Dict[str, list]:
        return self.mlflow_logger.get_latest_model_history(self.model_name)
    
    def plot_latest_model_history(self, save_path: Optional[str] = None):
        return self.mlflow_logger.plot_latest_model_history(self.model_name, save_path)
