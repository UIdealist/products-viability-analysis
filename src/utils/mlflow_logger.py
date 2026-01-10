import os
import mlflow
import mlflow.tensorflow
import tensorflow as tf
from pathlib import Path
from typing import Dict, Any, Optional, Union


class MLflowModelLogger:
    def __init__(self, experiment_name: str = "tensorflow_models", tracking_uri: str = "file:///tmp/mlruns"):
        self.experiment_name = experiment_name
        self.tracking_uri = tracking_uri
        self._setup_mlflow()
    
    def _setup_mlflow(self):
        mlflow.set_tracking_uri(self.tracking_uri)
        experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if experiment is None:
            print("Creating experiment", self.experiment_name)
            mlflow.create_experiment(self.experiment_name)
            experiment = mlflow.get_experiment_by_name(self.experiment_name)
        self.experiment_id = experiment.experiment_id
        return self.experiment_id
    
    def log_model(
        self,
        model: tf.keras.Model,
        run_name: str,
        model_name: str,
        metrics: Optional[Dict[str, float]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        signature: Optional[mlflow.models.signature.ModelSignature] = None,
        input_example: Optional[Any] = None,
        model_path: str = "model"
    ) -> str:
        
        with mlflow.start_run(run_name=run_name) as run:
            if parameters:
                mlflow.log_params(parameters)
            
            if metrics:
                mlflow.log_metrics(metrics)
            
            if tags:
                mlflow.set_tags(tags)
            
            mlflow.tensorflow.log_model(
                model=model,
                artifact_path=model_path,
                signature=signature,
                input_example=input_example
            )
            
            return run.info.run_id
    
    def log_training_history(
        self,
        history: tf.keras.callbacks.History,
        run_name: str,
        model_name: str,
        model: tf.keras.Model,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        
        with mlflow.start_run(run_name=run_name, experiment_id=self.experiment_id) as run:
            if parameters:
                mlflow.log_params(parameters)
            
            if tags:
                mlflow.set_tags(tags)
            
            for epoch, (loss, val_loss) in enumerate(zip(history.history['loss'], history.history['val_loss'])):
                mlflow.log_metrics({
                    'epoch_loss': loss,
                    'epoch_val_loss': val_loss
                }, step=epoch)
            
            if 'accuracy' in history.history:
                for epoch, (acc, val_acc) in enumerate(zip(history.history['accuracy'], history.history['val_accuracy'])):
                    mlflow.log_metrics({
                        'epoch_accuracy': acc,
                        'epoch_val_accuracy': val_acc
                    }, step=epoch)
            final_metrics = {
                'final_loss': history.history['loss'][-1],
                'final_val_loss': history.history['val_loss'][-1]
            }
            
            if 'accuracy' in history.history:
                final_metrics['final_accuracy'] = history.history['accuracy'][-1]
                final_metrics['final_val_accuracy'] = history.history['val_accuracy'][-1]
            
            mlflow.log_metrics(final_metrics)
            mlflow.tensorflow.log_model(
                model=model,
                artifact_path="model"
            )
            
            return run.info.run_id
    
    def load_model(self, run_id: str = None, model_name: str = None, version: str = None, model_path: str = "model") -> tf.keras.Model:
        if run_id:
            model_uri = f"runs:/{run_id}/{model_path}"
        elif model_name:
            if version:
                # Try to load by version first, then by run_id
                try:
                    model_uri = f"models:/{model_name}/{version}"
                except:
                    model_uri = f"runs:/{version}/{model_path}"
            else:
                # Load latest version
                model_uri = f"models:/{model_name}/latest"
        else:
            raise ValueError("Either run_id or model_name must be provided")
        
        return mlflow.tensorflow.load_model(model_uri)
    
    def get_experiment_runs(self) -> list:
        runs = mlflow.search_runs(experiment_ids=[self.experiment_id])
        return runs.to_dict('records')
    
    def list_model_versions(self, model_name: str = None) -> list:
        runs = mlflow.search_runs(
            experiment_ids=[self.experiment_id], 
            order_by=["start_time desc"]
        )
        
        if runs.empty:
            return []
        
        versions = []
        for _, run in runs.iterrows():
            version_info = {
                'run_id': run['run_id'],
                'run_name': run.get('tags.mlflow.runName', ''),
                'model_name': run.get('tags.model_name', ''),
                'start_time': run['start_time'],
                'end_time': run['end_time'],
                'status': run['status'],
                'final_loss': run.get('metrics.final_loss', None),
                'final_val_loss': run.get('metrics.final_val_loss', None),
                'final_accuracy': run.get('metrics.final_accuracy', None),
                'final_val_accuracy': run.get('metrics.final_val_accuracy', None)
            }
            versions.append(version_info)
        
        return versions
    
    def print_model_versions(self, model_name: str = None, limit: int = 10) -> None:
        versions = self.list_model_versions(model_name)
        
        if not versions:
            print("No model versions found.")
            return
        
        print(f"\n{'='*80}")
        print(f"Available Model Versions{' (filtered by: ' + model_name + ')' if model_name else ''}")
        print(f"{'='*80}")
        
        for i, version in enumerate(versions[:limit]):
            print(f"\n{i+1}. Run ID: {version['run_id']}")
            print(f"   Run Name: {version['run_name']}")
            print(f"   Model Name: {version['model_name']}")
            print(f"   Status: {version['status']}")
            print(f"   Start Time: {version['start_time']}")
            if version['end_time']:
                print(f"   End Time: {version['end_time']}")
            
            # Print metrics if available
            metrics = []
            if version['final_loss'] is not None:
                metrics.append(f"Loss: {version['final_loss']:.4f}")
            if version['final_val_loss'] is not None:
                metrics.append(f"Val Loss: {version['final_val_loss']:.4f}")
            if version['final_accuracy'] is not None:
                metrics.append(f"Accuracy: {version['final_accuracy']:.4f}")
            if version['final_val_accuracy'] is not None:
                metrics.append(f"Val Accuracy: {version['final_val_accuracy']:.4f}")
            
            if metrics:
                print(f"   Metrics: {', '.join(metrics)}")
        
        if len(versions) > limit:
            print(f"\n... and {len(versions) - limit} more versions")
        
        print(f"{'='*80}\n")
    
    def get_run_details(self, run_id: str) -> Dict[str, Any]:
        run = mlflow.get_run(run_id)
        return {
            'run_id': run.info.run_id,
            'run_name': run.data.tags.get('mlflow.runName', ''),
            'status': run.info.status,
            'start_time': run.info.start_time,
            'end_time': run.info.end_time,
            'metrics': run.data.metrics,
            'params': run.data.params,
            'tags': run.data.tags
        }
    
    def get_training_history(self, run_id: str) -> Dict[str, list]:
        client = mlflow.tracking.MlflowClient()
        
        history = {
            'loss': [],
            'val_loss': [],
            'accuracy': [],
            'val_accuracy': []
        }
        
        try:
            metrics_history = client.get_metric_history(run_id, "epoch_loss")
            if metrics_history:
                history['loss'] = [m.value for m in metrics_history]
            
            metrics_history = client.get_metric_history(run_id, "epoch_val_loss")
            if metrics_history:
                history['val_loss'] = [m.value for m in metrics_history]
            
            metrics_history = client.get_metric_history(run_id, "epoch_accuracy")
            if metrics_history:
                history['accuracy'] = [m.value for m in metrics_history]
            
            metrics_history = client.get_metric_history(run_id, "epoch_val_accuracy")
            if metrics_history:
                history['val_accuracy'] = [m.value for m in metrics_history]
                
        except Exception as e:
            print(f"Error retrieving training history: {e}")
        
        return history
    
    def plot_training_history(
        self, run_id: str, save_path: Optional[str] = None, 
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
        import matplotlib.pyplot as plt
        
        history = self.get_training_history(run_id)
        
        if not history['loss']:
            print("No training history found for this run")
            return

        # Last result uses to be the same as the first result, so we need to remove the last result
        for key in history:
            history[key] = history[key][:-1]
        
        epochs = range(1, len(history['loss']) + 1)
        
        primary_color = primary_color if primary_color is not None else '#193169'
        secondary_color = secondary_color if secondary_color is not None else '#0000FF'
        font_family = font_family if font_family is not None else 'Times New Roman'
        grid = grid if grid is not None else True
        
        loss_title = loss_title if loss_title is not None else 'Pérdida - Modelo'
        accuracy_title = accuracy_title if accuracy_title is not None else 'Precisión - Modelo'
        loss_xlabel = loss_xlabel if loss_xlabel is not None else 'Época'
        loss_ylabel = loss_ylabel if loss_ylabel is not None else 'Pérdida'
        accuracy_xlabel = accuracy_xlabel if accuracy_xlabel is not None else 'Época'
        accuracy_ylabel = accuracy_ylabel if accuracy_ylabel is not None else 'Precisión'
        loss_train_label = loss_train_label if loss_train_label is not None else 'Pérdida - Entrenamiento'
        loss_val_label = loss_val_label if loss_val_label is not None else 'Pérdida - Validación'
        accuracy_train_label = accuracy_train_label if accuracy_train_label is not None else 'Precisión - Entrenamiento'
        accuracy_val_label = accuracy_val_label if accuracy_val_label is not None else 'Precisión - Validación'
        
        plt.rcParams['font.family'] = font_family
        
        if direction == 'vertical':
            figsize = figure_size if figure_size is not None else (12, 4)
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        elif direction == 'horizontal':
            figsize = figure_size if figure_size is not None else (12, 10)
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize)
        
        ax1.plot(epochs, history['loss'], color=primary_color, linestyle='-', label=loss_train_label)
        if history['val_loss']:
            ax1.plot(epochs, history['val_loss'], color=secondary_color, linestyle='-', label=loss_val_label)
        ax1.set_title(loss_title)
        ax1.set_xlabel(loss_xlabel)
        ax1.set_ylabel(loss_ylabel)
        
        if title_size is not None:
            ax1.title.set_fontsize(title_size)
        if label_size is not None:
            ax1.xaxis.label.set_fontsize(label_size)
            ax1.yaxis.label.set_fontsize(label_size)
        if tick_size is not None:
            ax1.tick_params(axis='both', labelsize=tick_size)
        
        if legend_size is not None:
            ax1.legend(fontsize=legend_size)
        else:
            ax1.legend()
        
        if grid:
            ax1.grid(True)
        
        if history['accuracy']:
            ax2.plot(epochs, history['accuracy'], color=primary_color, linestyle='-', label=accuracy_train_label)
        if history['val_accuracy']:
            ax2.plot(epochs, history['val_accuracy'], color=secondary_color, linestyle='-', label=accuracy_val_label)
        ax2.set_title(accuracy_title)
        ax2.set_xlabel(accuracy_xlabel)
        ax2.set_ylabel(accuracy_ylabel)
        
        if title_size is not None:
            ax2.title.set_fontsize(title_size)
        if label_size is not None:
            ax2.xaxis.label.set_fontsize(label_size)
            ax2.yaxis.label.set_fontsize(label_size)
        if tick_size is not None:
            ax2.tick_params(axis='both', labelsize=tick_size)
        
        if legend_size is not None:
            ax2.legend(fontsize=legend_size)
        else:
            ax2.legend()
        
        if grid:
            ax2.grid(True)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            print(f"Plot saved to {save_path}")
        
        plt.show()
    
    def delete_run(self, run_id: str) -> bool:
        try:
            mlflow.delete_run(run_id)
            return True
        except Exception:
            return False
    
    def create_model_signature(self, input_schema: Dict[str, Any], output_schema: Dict[str, Any]) -> mlflow.models.signature.ModelSignature:
        from mlflow.types.schema import Schema, ColSpec, TensorSpec
        
        input_schema_obj = Schema([
            ColSpec(type=spec.get('type', 'double'), name=name) 
            for name, spec in input_schema.items()
        ])
        
        output_schema_obj = Schema([
            ColSpec(type=spec.get('type', 'double'), name=name) 
            for name, spec in output_schema.items()
        ])
        
        return mlflow.models.signature.ModelSignature(
            inputs=input_schema_obj,
            outputs=output_schema_obj
        )

    def load_latest_model(self, model_name: str = "model") -> tf.keras.Model:
        runs = mlflow.search_runs(
            experiment_ids=[self.experiment_id], 
            order_by=["start_time desc"], 
            max_results=1
        )
        run_id = runs.iloc[0]['run_id']
        model_uri = f"runs:/{run_id}/model"
        loaded_model_mlflow = mlflow.tensorflow.load_model(model_uri)
        return loaded_model_mlflow

    def get_latest_model_run_id(self, model_name: str = "model") -> str:
        runs = mlflow.search_runs(experiment_ids=[self.experiment_id], order_by=["start_time desc"], max_results=1)
        return runs.iloc[0]['run_id']
    
    def get_latest_model_history(self, model_name: str = "model") -> Dict[str, list]:
        runs = mlflow.search_runs(experiment_ids=[self.experiment_id], order_by=["start_time desc"], max_results=1)
        run_id = runs.iloc[0]['run_id']
        return self.get_training_history(run_id)
    
    def plot_latest_model_history(
        self, model_name: str = "model", save_path: Optional[str] = None, 
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
        runs = mlflow.search_runs(experiment_ids=[self.experiment_id], order_by=["start_time desc"], max_results=1)
        run_id = runs.iloc[0]['run_id']
        return self.plot_training_history(
            run_id, save_path, direction,
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