"""
Sklearn-compatible estimator for component health assessment.

Single responsibility: provide a high-level ``.fit()`` / ``.predict()`` /
``.compute()`` interface that orchestrates the lower-level modules.

Usage
-----
>>> from src.telemetry.health_index import load_config, ComponentHealthEstimator
>>> cfg = load_config("configs/health_index_cda.yaml")
>>> est = ComponentHealthEstimator(cfg, component="Motor")
>>> est.fit(df_train)
>>> inferences = est.predict(df_test)
>>> health = est.compute(inferences)
"""

from typing import Dict, List

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import OneHotEncoder, RobustScaler

from src.utils.logger import get_logger

from .config import HealthIndexConfig
from .feature_engineering import build_sequences, fit_encoders
from .health_index import compute_health_index
from .inference import run_hourly_inference
from .model_builder import build_lstm_autoencoder
from .optimization import run_optuna_study
from .persistence import load_model_artifacts, save_model_artifacts

logger = get_logger(__name__)


class ComponentHealthEstimator:
    """
    Sklearn-compatible estimator for LSTM-based health assessment.

    Parameters
    ----------
    cfg : HealthIndexConfig
        Loaded pipeline configuration.
    component : str
        Component name (e.g. ``"Motor"``).
    """

    def __init__(self, cfg: HealthIndexConfig, component: str):
        self.cfg = cfg
        self.component = component
        self.is_fitted_: bool = False

        # populated after .fit()
        self.signal_cols_: List[str] = []
        self.scalers_: Dict[str, RobustScaler] = {}
        self.ohe_: OneHotEncoder | None = None
        self.model_: tf.keras.Model | None = None
        self.best_params_: dict = {}

    # ── sklearn interface ───────────────────────────────────────────────

    def fit(self, df: pd.DataFrame) -> "ComponentHealthEstimator":
        """
        Train the autoencoder on preprocessed and labelled data.

        Steps:
          1. Resolve signal columns for this component.
          2. Fit scalers (per-unit) and OHE (shared).
          3. Build training sequences (Normal only).
          4. Optionally run Optuna hyper-parameter search.
          5. Train the final model.
          6. Persist artifacts.
        """
        tf.keras.utils.set_random_seed(self.cfg.seed)

        self.signal_cols_ = self.cfg.signal_cols_for(self.component, list(df.columns))
        if not self.signal_cols_:
            raise ValueError(
                f"Component '{self.component}' has no matching signals in the data",
            )

        logger.info(
            f"[{self.component}] Fitting on {len(self.signal_cols_)} signals: "
            f"{self.signal_cols_}"
        )

        # 1. Encoders
        self.scalers_, self.ohe_ = fit_encoders(
            df, self.signal_cols_, self.cfg.cat_cols, self.cfg.unit_col,
        )

        # 2. Sequences
        X_train = build_sequences(
            df, self.signal_cols_, self.cfg.cat_cols,
            self.scalers_, self.ohe_, self.cfg,
            label_filter="Normal",
        )
        n_features = X_train.shape[2]

        # 3. Optimisation (optional)
        if self.cfg.optimization_enabled:
            self.best_params_ = run_optuna_study(
                X_train, n_features, self.component, self.cfg,
            )
        else:
            self.best_params_ = dict(self.cfg.default_params)

        # 4. Build & train final model
        ae, _, _ = build_lstm_autoencoder(
            n_features=n_features,
            sequence_length=self.cfg.window_size,
            encoder_units=self.best_params_["encoder_units"],
            dropout_rate=self.best_params_["dropout_rate"],
            learning_rate=self.best_params_["learning_rate"],
        )
        ae.fit(
            X_train, X_train,
            epochs=self.cfg.epochs,
            batch_size=self.best_params_["batch_size"],
            validation_split=self.cfg.validation_split,
            callbacks=[
                tf.keras.callbacks.EarlyStopping(
                    patience=self.cfg.patience, restore_best_weights=True,
                ),
            ],
            verbose=1,
        )
        self.model_ = ae

        # 5. Save
        save_model_artifacts(
            model=ae,
            scalers=self.scalers_,
            ohe=self.ohe_,
            best_params=self.best_params_,
            signal_cols=self.signal_cols_,
            cfg=self.cfg,
            component=self.component,
        )
        self.is_fitted_ = True
        logger.info(f"[{self.component}] Fit complete ✓")
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run hourly inference on an input DataFrame.

        Returns a DataFrame with columns:
        ``Unit, window_start, window_end, reconstruction_error, coverage``.
        """
        artifacts = self._get_artifacts()
        return run_hourly_inference(df, artifacts, self.cfg)

    def compute(self, inferences_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the 0–1 health index from inference results.

        Returns the input DataFrame augmented with ``error_norm`` and
        ``health_index`` columns.
        """
        return compute_health_index(
            inferences_df, error_quantile=self.cfg.error_quantile,
        )

    # ── helpers ─────────────────────────────────────────────────────────

    def _get_artifacts(self) -> dict:
        """Return in-memory artifacts if fitted, otherwise load from disk."""
        if self.is_fitted_ and self.model_ is not None:
            return {
                "model": self.model_,
                "scalers": self.scalers_,
                "ohe": self.ohe_,
                "metadata": {
                    "signal_cols": self.signal_cols_,
                    "cat_cols": self.cfg.cat_cols,
                    "window_size": self.cfg.window_size,
                },
            }
        return load_model_artifacts(self.cfg, self.component)

    @classmethod
    def from_pretrained(
        cls,
        cfg: HealthIndexConfig,
        component: str,
    ) -> "ComponentHealthEstimator":
        """Load a previously trained estimator from saved artifacts."""
        instance = cls(cfg, component)
        arts = load_model_artifacts(cfg, component)
        instance.model_ = arts["model"]
        instance.scalers_ = arts["scalers"]
        instance.ohe_ = arts["ohe"]
        instance.signal_cols_ = arts["metadata"]["signal_cols"]
        instance.best_params_ = arts["metadata"].get("best_params", {})
        instance.is_fitted_ = True
        logger.info(f"[{component}] Loaded from disk ✓")
        return instance
