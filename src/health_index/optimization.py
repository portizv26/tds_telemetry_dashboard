"""
Optimization Module

Hyperparameter optimization using Optuna with MLflow tracking.
"""

import optuna
from optuna.samplers import TPESampler
import numpy as np
from typing import Dict, Any, Callable
import json
from pathlib import Path
from datetime import datetime
import tensorflow as tf

from .config import (
    OPTUNA_N_TRIALS,
    OPTUNA_TIMEOUT,
    OPTUNA_SEARCH_SPACE,
)
from .modeling import build_lstm_autoencoder


class OptunaObjective:
    """Objective function for Optuna optimization."""
    
    def __init__(self, X_train: np.ndarray, X_val: np.ndarray, 
                 n_features: int, window_size: int, max_epochs: int = 30, patience: int = 3):
        """
        Initialize optimization objective.
        
        Args:
            X_train: Training data
            X_val: Validation data
            n_features: Number of features
            window_size: Fixed window size (not optimized)
            max_epochs: Maximum epochs for each trial
            patience: Early stopping patience
        """
        self.X_train = X_train
        self.X_val = X_val
        self.n_features = n_features
        self.window_size = window_size
        self.max_epochs = max_epochs
        self.patience = patience
    
    def __call__(self, trial: optuna.Trial) -> float:
        """
        Objective function for a single trial.
        
        Args:
            trial: Optuna trial object
        
        Returns:
            Validation loss (to minimize)
        """
        # Sample hyperparameters (window_size is fixed, not optimized)
        lstm_units_1 = trial.suggest_int("lstm_units_1", *OPTUNA_SEARCH_SPACE["lstm_units_1"])
        lstm_units_2 = trial.suggest_int("lstm_units_2", *OPTUNA_SEARCH_SPACE["lstm_units_2"])
        dropout_rate = trial.suggest_float("dropout_rate", *OPTUNA_SEARCH_SPACE["dropout_rate"])
        learning_rate = trial.suggest_float("learning_rate", *OPTUNA_SEARCH_SPACE["learning_rate"], log=True)
        batch_size = trial.suggest_categorical("batch_size", OPTUNA_SEARCH_SPACE["batch_size"])
        
        # Build model with fixed window_size
        model = build_lstm_autoencoder(
            window_size=self.window_size,
            n_features=self.n_features,
            lstm_units_1=lstm_units_1,
            lstm_units_2=lstm_units_2,
            dropout_rate=dropout_rate,
            learning_rate=learning_rate,
        )
        
        # Early stopping
        early_stopping = tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=self.patience,
            restore_best_weights=True,
        )
        
        # Train
        history = model.fit(
            self.X_train, self.X_train,
            validation_data=(self.X_val, self.X_val),
            epochs=self.max_epochs,
            batch_size=batch_size,
            callbacks=[early_stopping],
            verbose=0,
        )
        
        # Return best validation loss
        best_val_loss = min(history.history['val_loss'])
        
        return best_val_loss


def optimize_hyperparameters(X_train: np.ndarray, X_val: np.ndarray, 
                             n_features: int, window_size: int, n_trials: int = None,
                             timeout: int = None) -> Dict[str, Any]:
    """
    Optimize hyperparameters using Optuna.
    
    Args:
        X_train: Training data
        X_val: Validation data
        n_features: Number of features
        window_size: Fixed window size (not optimized)
        n_trials: Number of Optuna trials (defaults to OPTUNA_N_TRIALS)
        timeout: Timeout in seconds (defaults to OPTUNA_TIMEOUT)
    
    Returns:
        Dictionary with best parameters and study results
    """
    if n_trials is None:
        n_trials = OPTUNA_N_TRIALS
    if timeout is None:
        timeout = OPTUNA_TIMEOUT
    
    # Create study
    study = optuna.create_study(
        direction="minimize",
        sampler=TPESampler(seed=42),
    )
    
    # Optimize
    objective = OptunaObjective(X_train, X_val, n_features, window_size)
    
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout,
        show_progress_bar=True,
    )
    
    # Extract results
    results = {
        "best_params": study.best_params,
        "best_value": study.best_value,
        "n_trials": len(study.trials),
        "best_trial": study.best_trial.number,
        "optimization_timestamp": datetime.now().isoformat(),
    }
    
    # Add trial history
    results["trials"] = []
    for trial in study.trials:
        trial_info = {
            "number": trial.number,
            "value": trial.value,
            "params": trial.params,
            "state": trial.state.name,
        }
        results["trials"].append(trial_info)
    
    print(f"\nOptimization completed!")
    print(f"Best trial: {study.best_trial.number}")
    print(f"Best value: {study.best_value:.6f}")
    print(f"Best params: {study.best_params}")
    
    return results


def save_optimization_results(results: Dict[str, Any], path: Path):
    """Save optimization results as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Saved optimization results to: {path}")


def load_optimization_results(path: Path) -> Dict[str, Any]:
    """Load optimization results from JSON."""
    with open(path, 'r') as f:
        return json.load(f)
