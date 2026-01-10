import os
import shutil
import re
from pyspark.sql import DataFrame
import tensorflow as tf
import tensorflow_io as tfio
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Optional, Union
from ..mlflow_logger import MLflowModelLogger
from tensorflow.keras.utils import plot_model as plot_keras_model
import pyarrow.parquet as pq
from graphviz import Digraph
from tensorflow.keras.utils import model_to_dot
import pydot
import pyspark.sql.functions as F
from .dataset_splitter import DatasetSplitter
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import mlflow
from sklearn.metrics import confusion_matrix


class BaseModel(ABC):
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
        is_binary: bool = False,
        is_sparse: bool = False
    ):
        self.model_name = model_name
        self.metastore_path = metastore_path
        self.model = None
        self.input_shape = None
        self.train_dataset = None
        self.val_dataset = None
        self.test_dataset = None
        self.run_id = None
        self.y_true = None
        self.y_pred = None
        self.mlflow_logger = MLflowModelLogger(
            experiment_name=model_name,
            tracking_uri=tracking_uri
        )
        
        self.dataset_splitter = None
        if spark_utils is not None and target_path is not None:
            self.dataset_splitter = DatasetSplitter(
                spark_utils=spark_utils,
                delta_table_path=target_path,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
                test_ratio=test_ratio,
                max_partitions=max_partitions,
                random_seed=random_seed
            )
        self.is_binary = is_binary
        self.num_classes = 2
        self.is_sparse = is_sparse
        
    def generate_io_dataset(
        self, 
        dst_path: Optional[str] = None,
        target_columns: Optional[list[bytes]] = None,
        dataset_type: Optional[str] = None
    ) -> tf.data.Dataset:
        if self.dataset_splitter is not None and dataset_type is not None:
            return self.dataset_splitter.generate_io_dataset(dataset_type, target_columns)
        
        if dst_path is None or target_columns is None:
            raise ValueError("Either dataset_splitter with dataset_type must be provided, or dst_path and target_columns must be provided")
        
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

        dataset = (
            dataset.map(split_xy, num_parallel_calls=tf.data.AUTOTUNE)
        )
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
        max_records: Optional[int] = None,
        **dataset_kwargs
    ) -> Tuple[tf.data.Dataset, tf.data.Dataset, tf.data.Dataset, int]:
        original_parquet = spark.read.parquet(dst_path)
        total_records = original_parquet.count()
        
        if max_records is not None:
            total_records = min(total_records, max_records)
            print(f"Limited dataset size to {total_records} records (max_records={max_records})")
        
        sample_batch = next(iter(dataset.take(1)))
        X_sample, _ = sample_batch
        print(X_sample.shape)
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
        spark: Optional[Any] = None,
        dst_dir: Optional[str] = None,
        target_columns: Optional[list[bytes]] = None,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        max_records: Optional[int] = None,
        overwrite: bool = False,
        **dataset_kwargs
    ) -> None:
        if self.dataset_splitter is not None:
            train_dataset = self.generate_io_dataset(dataset_type='train', target_columns=target_columns)
            val_dataset = self.generate_io_dataset(dataset_type='val', target_columns=target_columns)
            test_dataset = self.generate_io_dataset(dataset_type='test', target_columns=target_columns)
            
            sample_batch = next(iter(train_dataset.take(1)))
            X_sample, _ = sample_batch
            self.input_shape = X_sample.shape[0]
            
            self.train_dataset = self.configure_dataset(train_dataset, **dataset_kwargs)
            self.val_dataset = self.configure_dataset(val_dataset, **dataset_kwargs)
            self.test_dataset = self.configure_dataset(test_dataset, **dataset_kwargs)
        else:
            if dst_dir is None or target_columns is None or spark is None:
                raise ValueError("Either dataset_splitter must be initialized, or spark, dst_dir and target_columns must be provided")
            
            dataset = self.generate_io_dataset(dst_dir, target_columns)
            
            self.train_dataset, self.val_dataset, self.test_dataset, self.input_shape = self.split_dataset(
                spark, dst_dir, dataset, train_ratio, val_ratio, max_records=max_records, **dataset_kwargs
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

    def predict(self, df: DataFrame):
        if self.model is None:
            raise ValueError("Model not created. Call create_model() first.")
        features = df.toPandas().values
        predictions = self.model.predict(features)
        return predictions

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
        self.run_id = run_id
        self.history = self.get_training_history()
    
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
    
    def plot_training_history(
        self, save_path: Optional[str] = None,
        direction: Optional[str] = 'vertical',
        legend_size: Optional[float] = None,
        tick_size: Optional[float] = None,
        label_size: Optional[float] = None,
        title_size: Optional[float] = None,
        figure_size: Optional[tuple] = None,
        loss_title: Optional[str] = None,
        accuracy_title: Optional[str] = None,
        loss_xlabel: Optional[str] = None,
        loss_ylabel: Optional[str] = None,
        accuracy_xlabel: Optional[str] = None,
        accuracy_ylabel: Optional[str] = None,
        loss_train_label: Optional[str] = None,
        loss_val_label: Optional[str] = None,
        accuracy_train_label: Optional[str] = None,
        accuracy_val_label: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        font_family: Optional[str] = None,
        grid: Optional[bool] = None
    ):
        if self.run_id is None:
            raise ValueError("Model not logged. Call log_training_history() first.")
        return self.mlflow_logger.plot_training_history(
            self.run_id, save_path, direction,
            legend_size=legend_size,
            tick_size=tick_size,
            label_size=label_size,
            title_size=title_size,
            figure_size=figure_size,
            loss_title=loss_title,
            accuracy_title=accuracy_title,
            loss_xlabel=loss_xlabel,
            loss_ylabel=loss_ylabel,
            accuracy_xlabel=accuracy_xlabel,
            accuracy_ylabel=accuracy_ylabel,
            loss_train_label=loss_train_label,
            loss_val_label=loss_val_label,
            accuracy_train_label=accuracy_train_label,
            accuracy_val_label=accuracy_val_label,
            primary_color=primary_color,
            secondary_color=secondary_color,
            font_family=font_family,
            grid=grid
        )
    
    def list_available_models(self, model_name: str = None, limit: int = 10) -> None:
        target_model_name = model_name or self.model_name
        self.mlflow_logger.print_model_versions(target_model_name, limit)
    
    def get_model_versions(self, model_name: str = None) -> list:
        target_model_name = model_name or self.model_name
        return self.mlflow_logger.list_model_versions(target_model_name)
    
    def load_latest_model(self) -> None:
        self.model = self.mlflow_logger.load_latest_model(self.model_name)
        self.history = self.get_latest_model_history()
        self.run_id = self.mlflow_logger.get_latest_model_run_id(self.model_name)
    
    def get_latest_model_history(self) -> Dict[str, list]:
        return self.mlflow_logger.get_latest_model_history(self.model_name)
    
    def plot_latest_model_history(
        self, save_path: Optional[str] = None,
        direction: Optional[str] = 'vertical',
        legend_size: Optional[float] = None,
        tick_size: Optional[float] = None,
        label_size: Optional[float] = None,
        title_size: Optional[float] = None,
        figure_size: Optional[tuple] = None,
        loss_title: Optional[str] = None,
        accuracy_title: Optional[str] = None,
        loss_xlabel: Optional[str] = None,
        loss_ylabel: Optional[str] = None,
        accuracy_xlabel: Optional[str] = None,
        accuracy_ylabel: Optional[str] = None,
        loss_train_label: Optional[str] = None,
        loss_val_label: Optional[str] = None,
        accuracy_train_label: Optional[str] = None,
        accuracy_val_label: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        font_family: Optional[str] = None,
        grid: Optional[bool] = None
    ):
        return self.mlflow_logger.plot_latest_model_history(
            self.model_name, save_path, direction,
            legend_size=legend_size,
            tick_size=tick_size,
            label_size=label_size,
            title_size=title_size,
            figure_size=figure_size,
            loss_title=loss_title,
            accuracy_title=accuracy_title,
            loss_xlabel=loss_xlabel,
            loss_ylabel=loss_ylabel,
            accuracy_xlabel=accuracy_xlabel,
            accuracy_ylabel=accuracy_ylabel,
            loss_train_label=loss_train_label,
            loss_val_label=loss_val_label,
            accuracy_train_label=accuracy_train_label,
            accuracy_val_label=accuracy_val_label,
            primary_color=primary_color,
            secondary_color=secondary_color,
            font_family=font_family,
            grid=grid
        )

    def plot_model(self, save_path="model_tiered_lr.png", levels=3, cluster_sizes=None):
        import pydot

        dot = model_to_dot(
            self.model,
            show_shapes=True,
            show_layer_names=True,
            rankdir="LR",
            expand_nested=True
        )

        dot.set_name("")

        dot.set_graph_defaults(
            rankdir="LR",
            ranksep="1.2",
            nodesep="0.8",
            splines="ortho",
            concentrate="false",
            newrank="true",
            bgcolor="#ffffff"
        )

        dot.set_node_defaults(
            style="filled",
            fillcolor="#ffffff",
            fontcolor="#000000",
            fontname="Times New Roman",
            fontsize="12",
            color="#ffffff",
            penwidth="1.0"
        )

        nodes = [n for n in dot.get_node_list() if n.get_name() not in ("node",)]

        for node in nodes:
            label = node.get_label()
            if label:
                if 'bgcolor="black"' in label:
                    label = label.replace('bgcolor="black"', 'bgcolor="#193169"')
                if '<font' in label:
                    if 'face="Times New Roman"' in label:
                        pass
                    elif 'face=' in label:
                        label = re.sub(r'face="[^"]*"', 'face="Times New Roman"', label)
                    else:
                        label = label.replace('<font', '<font face="Times New Roman"')
                node.set_label(label)
            node.set_style("filled")
            node.set_fillcolor("#ffffff")
            node.set_fontcolor("#000000")
            node.set_fontname("Times New Roman")
            node.set_fontsize("12")
            node.set_color("#ffffff")
            node.set_penwidth("1.0")

        for edge in dot.get_edge_list():
            edge.set_constraint("false")

        clusters = []
        node_idx = 0

        if cluster_sizes:
            for size in cluster_sizes:
                if node_idx >= len(nodes):
                    break
                if size <= 0:
                    continue
                actual = min(size, len(nodes) - node_idx)
                clusters.append(nodes[node_idx:node_idx + actual])
                node_idx += actual

        while node_idx < len(nodes):
            actual = min(levels, len(nodes) - node_idx)
            clusters.append(nodes[node_idx:node_idx + actual])
            node_idx += actual

        cluster_graphs = []
        for i, group in enumerate(clusters):
            sg = pydot.Cluster(
                f"cluster_{i}",
                label="",
                style="invis",
                rank="same"
            )
            for n in group:
                sg.add_node(n)
            dot.add_subgraph(sg)
            cluster_graphs.append(group)

        for i in range(len(cluster_graphs) - 1):
            a = cluster_graphs[i][0]
            b = cluster_graphs[i + 1][0]
            dot.add_edge(pydot.Edge(a, b, style="invis", label=""))

        last_cluster_idx = len(cluster_graphs) - 1
        current_cluster_idx = 0
        
        for sg in dot.get_subgraph_list():
            is_last_cluster = (current_cluster_idx == last_cluster_idx)
            for n in sg.get_node_list():
                if n.get_name() == 'node':
                    continue
                label = n.get_label()
                if label:
                    if 'bgcolor="black"' in label:
                        if is_last_cluster:
                            label = label.replace('bgcolor="black"', 'bgcolor="white"')
                        else:
                            label = label.replace('bgcolor="black"', 'bgcolor="#193169"')
                    if '<font' in label:
                        if 'face="Times New Roman"' in label:
                            pass
                        elif 'face=' in label:
                            label = re.sub(r'face="[^"]*"', 'face="Times New Roman"', label)
                        else:
                            label = label.replace('<font', '<font face="Times New Roman"')
                    n.set_label(label)
            current_cluster_idx += 1

        dot.set_label("")

        if "label" in dot.obj_dict["attributes"]:
            del dot.obj_dict["attributes"]["label"]

        for n in dot.get_node_list():
            if n.get_name() == "graph":
                dot.del_node(n.get_name())

        dot_str = dot.to_string()
        dot_str = re.sub(r'\s+label\s*=\s*"[^"]*graph[^"]*"', '', dot_str, flags=re.IGNORECASE)
        dot_str = re.sub(r'\s+xlabel\s*=\s*"[^"]*graph[^"]*"', '', dot_str, flags=re.IGNORECASE)
        dot_str = re.sub(r'[^\n]*->\s*"graph"[^\n]*;', '', dot_str)
        dot_str = re.sub(r'[^\n]*->\s*graph[^\n]*;', '', dot_str)
        dot_str = re.sub(r'graph\s*\[[^\]]*\][^\n]*', '', dot_str)
        dot_str = re.sub(r'subgraph\s+cluster_cluster_\d+\s*\{[^}]*graph\s*\[[^\]]*\][^}]*\}', '', dot_str, flags=re.DOTALL)
        dot = pydot.graph_from_dot_data(dot_str)[0]
    
        dot.write_png(save_path)
        print(f"model plot saved to {save_path}")
        return save_path

    def prediction_simple(self, x):
        predictions = self.model.predict(x, verbose=0)
        return predictions

    def evaluate_test_dataset(
        self,
        dataset: Optional[tf.data.Dataset] = None,
        force_recalculate: bool = False
    ) -> Tuple[np.ndarray, np.ndarray]:
        if self.model is None:
            raise ValueError("Model not created. Call create_model() or load_model() first.")
        
        if not force_recalculate and self.y_true is not None and self.y_pred is not None:
            print("Using cached evaluation results")
            return self.y_true, self.y_pred
        
        if dataset is None:
            dataset = self.test_dataset
            if dataset is None:
                raise ValueError("No test dataset available. Please provide a dataset or ensure test_dataset is set.")
        
        print("Calculating predictions on test dataset...")
        y_true_list = []
        y_pred_list = []
        
        for x, y in dataset:
            predictions = self.prediction_simple(x)
            y_true_list.append(y)
            y_pred_list.append(predictions)
        
        self.y_true = np.concatenate(y_true_list, axis=0)
        self.y_pred = np.concatenate(y_pred_list, axis=0)
        
        print(f"Evaluation complete: {len(self.y_true)} samples")
        print(f"y_true shape: {self.y_true.shape}, y_pred shape: {self.y_pred.shape}")
        
        return self.y_true, self.y_pred

    def plot_confusion_matrix(
        self,
        dataset: Optional[tf.data.Dataset] = None,
        y_true: Optional[np.ndarray] = None,
        y_pred: Optional[np.ndarray] = None,
        class_names: Optional[list] = None,
        save_path: Optional[str] = None,
        figsize: Optional[Tuple[int, int]] = None,
        square_size: Optional[float] = None,
        normalize: bool = False,
        title: Optional[str] = None,
        xlabel: Optional[str] = None,
        ylabel: Optional[str] = None,
        title_fontsize: int = 16,
        label_fontsize: int = 12,
        tick_fontsize: Optional[int] = None,
        annot_fontsize: Optional[int] = None,
        x_tick_rotation: float = 45,
        y_tick_rotation: float = 0,
        x_tick_ha: Optional[str] = 'right',
        y_tick_ha: Optional[str] = None,
        x_tick_labels: Optional[list] = None,
        y_tick_labels: Optional[list] = None,
        square: bool = True,
        linewidths: float = 0.5,
        linecolor: str = 'white',
        cmap: str = 'Blues',
        cbar: bool = True,
        cbar_kws: Optional[dict] = None,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        center: Optional[float] = None,
        robust: bool = False
    ):
        if self.model is None:
            raise ValueError("Model not created. Call create_model() or load_model() first.")
        
        if save_path is None:
            save_path = f"{self.metastore_path}/warehouse/gold.premodeling/{self.model_name}/confusion_matrix.png"
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        if y_true is not None and y_pred is not None:
            y_true = np.copy(y_true)
            y_pred = np.copy(y_pred)
        elif dataset is not None or self.test_dataset is not None:
            y_true, y_pred = self.evaluate_test_dataset(dataset=dataset)
            y_true = np.copy(y_true)
            y_pred = np.copy(y_pred)
        else:
            raise ValueError("Either provide y_true and y_pred, a dataset, or ensure test_dataset is set.")
        
        if y_true.ndim > 1 and not self.is_binary and not self.is_sparse:
            y_true = np.argmax(y_true, axis=1)
        
        if y_pred.ndim > 1 and not self.is_binary:
            y_pred = np.argmax(y_pred, axis=1)
        
        cm = confusion_matrix(y_true, y_pred)
        
        if normalize:
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        
        if class_names is None:
            class_names = [f'Class {i}' for i in range(self.num_classes)]
        
        x_tick_labels_final = x_tick_labels if x_tick_labels is not None else class_names
        y_tick_labels_final = y_tick_labels if y_tick_labels is not None else class_names
        
        if title is None:
            title = f'Confusion Matrix - {self.model_name}'
        
        if xlabel is None:
            xlabel = 'Predicted Label'
        
        if ylabel is None:
            ylabel = 'True Label'
        
        num_classes = cm.shape[0]
        
        if square_size is not None:
            figsize = (square_size * num_classes, square_size * num_classes)
        elif figsize is None:
            figsize = (10, 8)
        
        plt.figure(figsize=figsize)
        
        annot_kws = {}
        if annot_fontsize is not None:
            annot_kws['fontsize'] = annot_fontsize
        
        if cbar_kws is None:
            cbar_kws = {'label': 'Normalized Count' if normalize else 'Count'}
        elif 'label' not in cbar_kws:
            cbar_kws['label'] = 'Normalized Count' if normalize else 'Count'
        
        sns.heatmap(
            cm,
            annot=True,
            fmt='.2f' if normalize else 'd',
            cmap=cmap,
            square=square,
            linewidths=linewidths,
            linecolor=linecolor,
            cbar=cbar,
            cbar_kws=cbar_kws,
            xticklabels=x_tick_labels_final,
            yticklabels=y_tick_labels_final,
            annot_kws=annot_kws if annot_kws else None,
            vmin=vmin,
            vmax=vmax,
            center=center,
            robust=robust
        )
        
        plt.title(title, fontsize=title_fontsize, fontweight='bold')
        plt.xlabel(xlabel, fontsize=label_fontsize)
        plt.ylabel(ylabel, fontsize=label_fontsize)
        
        xtick_kwargs = {'rotation': x_tick_rotation}
        ytick_kwargs = {'rotation': y_tick_rotation}
        
        if x_tick_ha is not None:
            xtick_kwargs['ha'] = x_tick_ha
        if y_tick_ha is not None:
            ytick_kwargs['ha'] = y_tick_ha
        if tick_fontsize is not None:
            xtick_kwargs['fontsize'] = tick_fontsize
            ytick_kwargs['fontsize'] = tick_fontsize
        
        plt.xticks(**xtick_kwargs)
        plt.yticks(**ytick_kwargs)
        
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