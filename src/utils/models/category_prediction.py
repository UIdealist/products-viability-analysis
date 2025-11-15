from typing import Tuple, Optional
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
    def __init__(self, model_name: str, metastore_path: str, num_classes: int = 5, tracking_uri: str = "file:///tmp/mlruns"):
        super().__init__(model_name, metastore_path, tracking_uri)
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
    
    def plot_confusion_matrix(
        self,
        dataset: Optional[tf.data.Dataset] = None,
        y_true: Optional[np.ndarray] = None,
        y_pred: Optional[np.ndarray] = None,
        class_names: Optional[list] = None,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (10, 8),
        normalize: bool = False
    ):
        if self.model is None:
            raise ValueError("Model not created. Call create_model() or load_model() first.")
        
        if save_path is None:
            save_path = f"{self.metastore_path}/warehouse/gold.premodeling/{self.model_name}/confusion_matrix.png"
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        if dataset is None and y_true is None and y_pred is None:
            dataset = self.test_dataset
            if dataset is None:
                raise ValueError("No test dataset available. Please provide a dataset or ensure test_dataset is set.")
        
        if dataset is not None:
            y_true_list = []
            y_pred_list = []
            
            for x, y in dataset:
                predictions = self.model.predict(x, verbose=0)
                y_true_list.append(y.numpy())
                y_pred_list.append(predictions)
            
            y_true = np.concatenate(y_true_list, axis=0)
            y_pred = np.concatenate(y_pred_list, axis=0)

            print(len(y_true), len(y_pred))
        elif y_true is None or y_pred is None:
            raise ValueError("Either provide a dataset or both y_true and y_pred")
        
        if y_true.ndim > 1:
            y_true = np.argmax(y_true, axis=1)
        
        if y_pred.ndim > 1:
            y_pred = np.argmax(y_pred, axis=1)
        
        cm = confusion_matrix(y_true, y_pred)
        
        if normalize:
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        
        if class_names is None:
            class_names = [f'Class {i}' for i in range(self.num_classes)]
        
        plt.figure(figsize=figsize)
        sns.heatmap(
            cm,
            annot=True,
            fmt='.2f' if normalize else 'd',
            cmap='Blues',
            xticklabels=class_names,
            yticklabels=class_names,
            cbar_kws={'label': 'Normalized Count' if normalize else 'Count'}
        )
        
        plt.title(f'Confusion Matrix - {self.model_name}', fontsize=16, fontweight='bold')
        plt.xlabel('Predicted Label', fontsize=12)
        plt.ylabel('True Label', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Confusion matrix saved to {save_path}")
            
            # Log to MLflow if there's an active run
            try:
                if hasattr(self, 'run_id') and self.run_id:
                    mlflow.log_artifact(save_path, artifact_path="confusion_matrix")
                    print(f"Confusion matrix logged to MLflow run {self.run_id}")
                elif hasattr(self, 'mlflow_logger'):
                    # If no active run, start one or log to the latest
                    try:
                        runs = mlflow.search_runs(
                            experiment_ids=[self.mlflow_logger.experiment_id],
                            order_by=["start_time desc"],
                            max_results=1
                        )
                        if not runs.empty:
                            latest_run_id = runs.iloc[0]['run_id']
                            mlflow.log_artifact(save_path, artifact_path="confusion_matrix", run_id=latest_run_id)
                            print(f"Confusion matrix logged to MLflow run {latest_run_id}")
                    except Exception as e:
                        print(f"Could not log confusion matrix to MLflow: {e}")
            except Exception as e:
                print(f"Error logging confusion matrix to MLflow: {e}")
        
        plt.show()
        
        return cm
