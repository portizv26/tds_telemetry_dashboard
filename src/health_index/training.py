"""
Training Module

Handles model training with MLflow tracking.
"""

import numpy as np
from typing import Dict, Any, Tuple
import tensorflow as tf
from tensorflow import keras
from pathlib import Path
import mlflow
import mlflow.tensorflow
from datetime import datetime

from .config import (
    MLFLOW_TRACKING_URI,
    MLFLOW_ARTIFACT_LOCATION,
    get_experiment_name,
)
from .modeling import build_lstm_autoencoder


def setup_mlflow(experiment_name: str):
    """
    Setup MLflow tracking.
    
    Args:
        experiment_name: Name of the experiment
    """
    # Set tracking URI to local directory (not SQLite)
    mlflow.set_tracking_uri(f"file://{MLFLOW_TRACKING_URI}")
    
    # Set or create experiment
    try:
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            mlflow.create_experiment(
                experiment_name,
                artifact_location=MLFLOW_ARTIFACT_LOCATION
            )
        mlflow.set_experiment(experiment_name)
    except Exception as e:
        print(f"Warning: MLflow setup issue: {e}")


def train_model(
    X_train: np.ndarray,
    X_val: np.ndarray,
    hyperparams: Dict[str, Any],
    n_features: int,
    component: str,
    client: str,
    experiment_name: str = None,
    use_mlflow: bool = True,
) -> Tuple[keras.Model, Dict[str, Any]]:
    """
    Train LSTM autoencoder with MLflow tracking.
    
    Args:
        X_train: Training data
        X_val: Validation data
        hyperparams: Dictionary of hyperparameters
        n_features: Number of features
        component: Component name
        client: Client name
        experiment_name: MLflow experiment name
        use_mlflow: Whether to use MLflow tracking
    
    Returns:
        Tuple of (trained model, training history dict)
    """
    window_size = hyperparams['window_size']
    
    # Generate experiment name if not provided
    if experiment_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_name = get_experiment_name(component, window_size, timestamp)
    
    # Setup MLflow
    if use_mlflow:
        setup_mlflow(experiment_name)
        mlflow.start_run()
        
        # Log hyperparameters
        mlflow.log_params(hyperparams)
        mlflow.log_param("component", component)
        mlflow.log_param("client", client)
        mlflow.log_param("n_features", n_features)
        mlflow.log_param("n_train_samples", len(X_train))
        mlflow.log_param("n_val_samples", len(X_val))
    
    # Build model
    model = build_lstm_autoencoder(
        window_size=window_size,
        n_features=n_features,
        lstm_units_1=hyperparams.get('lstm_units_1', 16),
        lstm_units_2=hyperparams.get('lstm_units_2', 8),
        dropout_rate=hyperparams.get('dropout_rate', 0.2),
        learning_rate=hyperparams.get('learning_rate', 0.001),
    )
    
    print(f"\nModel architecture:")
    model.summary()
    
    # Callbacks
    callbacks = []
    
    # Early stopping
    early_stopping = tf.keras.callbacks.EarlyStopping(
        monitor='val_loss',
        patience=hyperparams.get('early_stopping_patience', 5),
        restore_best_weights=True,
        verbose=1,
    )
    callbacks.append(early_stopping)
    
    # MLflow callback
    if use_mlflow:
        mlflow_callback = mlflow.tensorflow.autolog(
            log_models=False,  # We'll save manually
            disable=False,
        )
    
    # Train
    print(f"\nTraining model...")
    history = model.fit(
        X_train, X_train,
        validation_data=(X_val, X_val),
        epochs=hyperparams.get('epochs', 50),
        batch_size=hyperparams.get('batch_size', 32),
        callbacks=callbacks,
        verbose=1,
    )
    
    # Extract metrics
    train_loss = float(history.history['loss'][-1])
    val_loss = float(history.history['val_loss'][-1])
    best_val_loss = float(min(history.history['val_loss']))
    
    print(f"\nTraining completed:")
    print(f"  Final train loss: {train_loss:.6f}")
    print(f"  Final val loss: {val_loss:.6f}")
    print(f"  Best val loss: {best_val_loss:.6f}")
    
    # Log final metrics to MLflow
    if use_mlflow:
        mlflow.log_metric("final_train_loss", train_loss)
        mlflow.log_metric("final_val_loss", val_loss)
        mlflow.log_metric("best_val_loss", best_val_loss)
        mlflow.log_metric("epochs_trained", len(history.history['loss']))
        
        mlflow.end_run()
    
    # Convert history to serializable format
    history_dict = {
        key: [float(v) for v in values]
        for key, values in history.history.items()
    }
    
    return model, history_dict


def save_model(model: keras.Model, path: Path):
    """Save trained model to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save(path)
    print(f"Saved model to: {path}")


def load_model(path: Path) -> keras.Model:
    """Load trained model from disk."""
    return keras.models.load_model(path)
