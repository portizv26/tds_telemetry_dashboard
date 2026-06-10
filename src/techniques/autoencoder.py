"""
Anomaly Detection — LSTM Autoencoder for multivariate pattern anomalies.

Trains system-specific autoencoders on normal sequences and detects deviations
from learned patterns using reconstruction error.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

from src.config.settings import (
    UNIT_COLNAME,
    STATE_COLNAME,
    TIME_COLNAME,
    AutoencoderConfig,
)
from src.utils.data_utils import (
    get_system_signals,
    get_all_systems,
    classify_status,
    calculate_confidence,
)

logger = logging.getLogger(__name__)

ENG_SPD_BINS = [0, 300, 600, 900, 1200, float("inf")]
ENG_SPD_LABELS = ["lt300", "300_600", "600_900", "900_1200", "gt1200"]


def _encode_categorical(df: pd.DataFrame) -> pd.DataFrame:
    """Encode Estado and EngSpd bins as one-hot features."""
    out = df.copy()

    if STATE_COLNAME in out.columns:
        dummies = pd.get_dummies(out[STATE_COLNAME], prefix="Estado")
        out = pd.concat([out, dummies], axis=1)

    if "EngSpd" in out.columns:
        out["EngSpd_bin"] = pd.cut(
            out["EngSpd"], bins=ENG_SPD_BINS, labels=ENG_SPD_LABELS, include_lowest=True
        )
        dummies = pd.get_dummies(out["EngSpd_bin"], prefix="EngSpd")
        out = pd.concat([out, dummies], axis=1)
        out.drop(columns=["EngSpd_bin"], inplace=True)

    return out


def _prepare_sequences(
    unit_data: pd.DataFrame,
    system_features: list[str],
    config: AutoencoderConfig,
) -> tuple[Optional[np.ndarray], list[str]]:
    """
    Create quality-filtered sequences from unit data.

    Returns:
        (sequences array [n, seq_len, features], feature_columns list) or (None, [])
    """
    encoded = _encode_categorical(unit_data)

    # Build feature column list
    numeric_cols = [f for f in system_features if f in encoded.columns]
    estado_cols = [c for c in encoded.columns if c.startswith("Estado_")]
    engspd_cols = [c for c in encoded.columns if c.startswith("EngSpd_")]
    feature_cols = numeric_cols + estado_cols + engspd_cols

    if not feature_cols:
        return None, []

    # Track missing before imputation
    missing_mask = encoded[feature_cols].isna()

    # Impute
    if numeric_cols:
        encoded[numeric_cols] = encoded[numeric_cols].interpolate(method="time", limit_direction="both")
    cat_cols = estado_cols + engspd_cols
    if cat_cols:
        encoded[cat_cols] = encoded[cat_cols].ffill().bfill()

    # Fill any remaining NaN
    encoded[feature_cols] = encoded[feature_cols].fillna(0)

    seq_len = config.sequence_length
    sequences = []

    for i in range(len(encoded) - seq_len + 1):
        # Quality check: imputation ratio
        missing_count = missing_mask[feature_cols].iloc[i : i + seq_len].sum().sum()
        total = seq_len * len(feature_cols)
        if (missing_count / total) >= config.quality_threshold:
            continue
        sequences.append(encoded[feature_cols].iloc[i : i + seq_len].values)

    if not sequences:
        return None, []

    return np.array(sequences, dtype=np.float32), feature_cols


def build_autoencoder(input_shape: tuple, encoding_dim: int = 32):
    """Build LSTM autoencoder model. Requires TensorFlow."""
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers

    inputs = keras.Input(shape=input_shape)
    # Encoder
    x = layers.LSTM(64, activation="relu", return_sequences=True)(inputs)
    x = layers.LSTM(encoding_dim, activation="relu", return_sequences=False)(x)
    # Decoder
    x = layers.RepeatVector(input_shape[0])(x)
    x = layers.LSTM(encoding_dim, activation="relu", return_sequences=True)(x)
    x = layers.LSTM(64, activation="relu", return_sequences=True)(x)
    outputs = layers.TimeDistributed(layers.Dense(input_shape[1]))(x)

    model = keras.Model(inputs, outputs, name="lstm_autoencoder")
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=0.001), loss="mse")
    return model


def train_model(
    df: pd.DataFrame,
    df_labeled: pd.DataFrame,
    unit: str,
    system: str,
    system_features: list[str],
    config: AutoencoderConfig,
) -> Optional[dict]:
    """
    Train autoencoder for one unit-system pair using normal data only.

    Parameters:
        df: Raw telemetry data (indexed or with Unit/Fecha columns)
        df_labeled: Deviation results (to filter normal sequences)
        unit: Unit identifier
        system: System name
        system_features: Signal names in this system
        config: Autoencoder configuration

    Returns:
        Dict with model, scaler, and baseline stats or None.
    """
    import tensorflow as tf
    from tensorflow import keras

    # Get normal timestamps for this unit
    if isinstance(df_labeled.index, pd.MultiIndex):
        try:
            unit_labels = df_labeled.loc[unit]
        except KeyError:
            return None
    else:
        unit_labels = df_labeled[df_labeled[UNIT_COLNAME] == unit]

    risk_cols = [f"risk_level_{f}" for f in system_features if f"risk_level_{f}" in unit_labels.columns]
    if not risk_cols:
        return None

    normal_mask = (unit_labels[risk_cols] == "normal").all(axis=1)
    normal_timestamps = normal_mask[normal_mask].index

    # Get raw unit data
    if isinstance(df.index, pd.MultiIndex):
        try:
            unit_raw = df.loc[unit].copy()
        except KeyError:
            return None
    else:
        unit_raw = df[df[UNIT_COLNAME] == unit].copy()
        if TIME_COLNAME in unit_raw.columns:
            unit_raw = unit_raw.set_index(TIME_COLNAME)

    # Filter to normal timestamps
    normal_data = unit_raw[unit_raw.index.isin(normal_timestamps)]
    if len(normal_data) < config.sequence_length * 4:
        return None

    sequences, feature_cols = _prepare_sequences(normal_data, system_features, config)
    if sequences is None or len(sequences) < 100:
        return None

    # Normalize
    scaler = StandardScaler()
    n_samples, n_steps, n_feats = sequences.shape
    flat = sequences.reshape(-1, n_feats)
    scaled = scaler.fit_transform(flat).reshape(n_samples, n_steps, n_feats)

    # Split
    X_train, X_val = train_test_split(scaled, test_size=config.validation_split, random_state=42)

    # Build and train
    model = build_autoencoder((n_steps, n_feats), config.encoding_dim)
    early_stop = keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=config.early_stopping_patience, restore_best_weights=True
    )

    model.fit(
        X_train, X_train,
        epochs=config.epochs,
        batch_size=config.batch_size,
        validation_data=(X_val, X_val),
        callbacks=[early_stop],
        verbose=0,
    )

    # Baseline reconstruction errors
    train_recon = model.predict(X_train, verbose=0)
    train_mse = np.mean(np.square(X_train - train_recon), axis=(1, 2))

    return {
        "unit": unit,
        "system": system,
        "model": model,
        "scaler": scaler,
        "feature_columns": feature_cols,
        "n_features": n_feats,
        "n_sequences": len(sequences),
        "baseline_mean": float(np.mean(train_mse)),
        "baseline_std": float(np.std(train_mse)),
        "baseline_p95": float(np.percentile(train_mse, 95)),
        "baseline_p99": float(np.percentile(train_mse, 99)),
    }


def score_sequences(
    df: pd.DataFrame,
    unit: str,
    model_info: dict,
    config: AutoencoderConfig,
) -> list[dict]:
    """
    Score new sequences against trained model.

    Returns:
        List of scoring result dicts per sequence window.
    """
    # Get unit data
    if isinstance(df.index, pd.MultiIndex):
        try:
            unit_data = df.loc[unit].copy()
        except KeyError:
            return []
    else:
        unit_data = df[df[UNIT_COLNAME] == unit].copy()
        if TIME_COLNAME in unit_data.columns:
            unit_data = unit_data.set_index(TIME_COLNAME)

    sequences, _ = _prepare_sequences(unit_data, model_info["feature_columns"], config)
    if sequences is None:
        return []

    model = model_info["model"]
    scaler = model_info["scaler"]

    n_samples, n_steps, n_feats = sequences.shape
    scaled = scaler.transform(sequences.reshape(-1, n_feats)).reshape(n_samples, n_steps, n_feats)

    reconstructions = model.predict(scaled, verbose=0)
    mse_per_seq = np.mean(np.square(scaled - reconstructions), axis=(1, 2))

    baseline_mean = model_info["baseline_mean"]
    baseline_std = model_info["baseline_std"]
    baseline_p95 = model_info["baseline_p95"]
    baseline_p99 = model_info["baseline_p99"]

    results = []
    for i, mse in enumerate(mse_per_seq):
        z = (mse - baseline_mean) / max(baseline_std, 1e-10)

        if mse < baseline_p95:
            percentile = min(50 + (mse - baseline_mean) / max(baseline_p95 - baseline_mean, 1e-10) * 45, 95)
            severity = "normal" if mse < baseline_mean + baseline_std else "minor"
        elif mse < baseline_p99:
            percentile = 95 + (mse - baseline_p95) / max(baseline_p99 - baseline_p95, 1e-10) * 4
            severity = "moderate"
        else:
            percentile = min(99 + (mse - baseline_p99) / max(baseline_p99, 1e-10), 100)
            severity = "severe"

        risk_score = max(0, min(percentile, 100))
        confidence = calculate_confidence(valid_samples=n_steps, expected_samples=n_steps)

        results.append({
            "unit": unit,
            "system": model_info["system"],
            "sequence_index": i,
            "reconstruction_error": float(mse),
            "z_score": float(z),
            "percentile_score": round(float(percentile), 1),
            "severity": severity,
            "risk_score": round(risk_score, 1),
            "confidence_score": round(confidence, 1),
            "status": classify_status(risk_score, confidence),
            "execution_timestamp": datetime.utcnow(),
        })

    return results


def save_model(model_info: dict, output_dir: Path) -> None:
    """Persist trained model, scaler, and metadata."""
    unit = model_info["unit"]
    system = model_info["system"]
    version = datetime.utcnow().strftime("%Y%m%d")

    model_dir = output_dir / f"{unit}_{system}_{version}"
    model_dir.mkdir(parents=True, exist_ok=True)

    model_info["model"].save(model_dir / "model.keras")
    joblib.dump(model_info["scaler"], model_dir / "scaler.pkl")

    import json
    metadata = {
        "unit": unit,
        "system": system,
        "model_version": version,
        "n_features": model_info["n_features"],
        "n_sequences": model_info["n_sequences"],
        "baseline_mean": model_info["baseline_mean"],
        "baseline_std": model_info["baseline_std"],
        "baseline_p95": model_info["baseline_p95"],
        "baseline_p99": model_info["baseline_p99"],
        "feature_columns": model_info["feature_columns"],
    }
    with open(model_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Saved model: {model_dir}")
