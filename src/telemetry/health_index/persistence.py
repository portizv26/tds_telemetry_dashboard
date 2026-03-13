"""
Persistence module.

Single responsibility: save and load model artifacts (weights,
scalers, encoder, metadata) to/from disk.
"""

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from sklearn.preprocessing import OneHotEncoder, RobustScaler
from tensorflow.keras import Model

from src.utils.logger import get_logger

from .config import HealthIndexConfig

logger = get_logger(__name__)


def save_model_artifacts(
    model: Model,
    scalers: Dict[str, RobustScaler],
    ohe: OneHotEncoder,
    best_params: dict,
    signal_cols: List[str],
    cfg: HealthIndexConfig,
    component: str,
) -> Path:
    """Persist model, scalers, encoder, and metadata to *models_dir*."""
    out_dir = cfg.models_dir / cfg.client / component
    out_dir.mkdir(parents=True, exist_ok=True)

    model.save(out_dir / "model.keras")
    with open(out_dir / "scalers.pkl", "wb") as f:
        pickle.dump(scalers, f)
    with open(out_dir / "ohe.pkl", "wb") as f:
        pickle.dump(ohe, f)

    metadata = {
        "signal_cols": signal_cols,
        "cat_cols": cfg.cat_cols,
        "window_size": cfg.window_size,
        "best_params": best_params,
        "trained_at": datetime.now().isoformat(),
    }
    with open(out_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Artifacts saved → {out_dir}")
    return out_dir


def load_model_artifacts(
    cfg: HealthIndexConfig,
    component: str,
) -> dict:
    """
    Load model and supporting artifacts from disk.

    Returns a dict with keys: ``model``, ``scalers``, ``ohe``, ``metadata``.
    """
    import tensorflow as tf  # deferred to avoid eager-init side effects

    base = cfg.models_dir / cfg.client / component
    if not base.exists():
        raise FileNotFoundError(f"No artifacts found at {base}")

    model = tf.keras.models.load_model(base / "model.keras")
    with open(base / "scalers.pkl", "rb") as f:
        scalers = pickle.load(f)
    with open(base / "ohe.pkl", "rb") as f:
        ohe = pickle.load(f)
    with open(base / "metadata.json", "r") as f:
        metadata = json.load(f)

    logger.info(f"Artifacts loaded ← {base}")
    return {"model": model, "scalers": scalers, "ohe": ohe, "metadata": metadata}
