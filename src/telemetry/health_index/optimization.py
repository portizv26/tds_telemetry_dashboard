"""
Optuna hyper-parameter optimisation module.

Single responsibility: search for optimal LSTM autoencoder hyper-parameters
using Optuna and persist the results as JSON.
"""

import json
from datetime import datetime
from typing import List

import numpy as np
import optuna
import tensorflow as tf

from src.utils.logger import get_logger

from .config import HealthIndexConfig
from .model_builder import build_lstm_autoencoder

logger = get_logger(__name__)


def _suggest_encoder_units(trial: optuna.Trial) -> List[int]:
    """Suggest a variable-length list of descending LSTM layer sizes."""
    n_layers = trial.suggest_int("n_layers", 1, 4)
    units: List[int] = []
    prev = None
    for i in range(n_layers):
        hi = prev if prev else 128
        lo = max(4, hi // 4)
        u = trial.suggest_int(f"enc_units_L{i}", lo, hi, step=2)
        units.append(u)
        prev = u
    return units


def _create_objective(
    X_train: np.ndarray,
    n_features: int,
    window_size: int,
    cfg: HealthIndexConfig,
):
    """Return an Optuna objective closure."""

    def objective(trial: optuna.Trial) -> float:
        encoder_units = _suggest_encoder_units(trial)
        dropout_rate = trial.suggest_float("dropout_rate", 0.05, 0.4, step=0.025)
        lr = trial.suggest_float("learning_rate", 1e-5, 1e-2, log=True)
        batch_size = trial.suggest_categorical("batch_size", [16, 32, 64])

        ae, _, _ = build_lstm_autoencoder(
            n_features=n_features,
            sequence_length=window_size,
            encoder_units=encoder_units,
            dropout_rate=dropout_rate,
            learning_rate=lr,
        )
        history = ae.fit(
            X_train, X_train,
            epochs=cfg.optuna_epochs,
            batch_size=batch_size,
            validation_split=cfg.validation_split,
            callbacks=[
                tf.keras.callbacks.EarlyStopping(
                    patience=cfg.optuna_patience, restore_best_weights=True,
                ),
            ],
            verbose=0,
        )
        return min(history.history["val_loss"])

    return objective


def run_optuna_study(
    X_train: np.ndarray,
    n_features: int,
    component: str,
    cfg: HealthIndexConfig,
) -> dict:
    """
    Run an in-memory Optuna study and persist results as JSON.

    Returns the best hyper-parameters dict.
    """
    study_name = f"{component}_{cfg.window_size}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    study = optuna.create_study(study_name=study_name, direction="minimize")
    study.optimize(
        _create_objective(X_train, n_features, cfg.window_size, cfg),
        n_trials=cfg.n_trials,
        show_progress_bar=True,
    )

    # ── Extract best params ──
    bp = study.best_params
    n_layers = bp["n_layers"]
    encoder_units = [bp[f"enc_units_L{i}"] for i in range(n_layers)]

    best: dict = {
        "encoder_units": encoder_units,
        "dropout_rate": bp["dropout_rate"],
        "learning_rate": bp["learning_rate"],
        "batch_size": bp["batch_size"],
        "best_val_loss": study.best_value,
        "study_name": study_name,
    }

    # ── Persist ──
    out_dir = cfg.models_dir / cfg.client / component
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / f"best_params_{study_name}.json", "w") as f:
        json.dump(best, f, indent=2)

    trials_data = []
    for t in study.trials:
        n_l = t.params.get("n_layers", 1)
        trials_data.append({
            "number": t.number,
            "value": t.value,
            "params": t.params,
            "encoder_units": [t.params.get(f"enc_units_L{i}") for i in range(n_l)],
            "state": t.state.name,
        })
    with open(out_dir / f"optuna_trials_{study_name}.json", "w") as f:
        json.dump(trials_data, f, indent=2)

    logger.info(f"[{component}] Best val_loss={best['best_val_loss']:.6f}  units={encoder_units}")
    return best
