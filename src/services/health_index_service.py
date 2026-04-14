"""
Health Index Service

Handles reconstruction error normalization, Health Index scoring, and artifact persistence.
"""

import os
import json
import numpy as np
import pandas as pd

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple


@dataclass
class HealthIndexConfig:
    """Configuration for Health Index computation."""
    alpha: float = 1.0
    time_agg: str = "mean"      # mean, median, max, p95
    signal_agg: str = "rms"     # mean, rms, max
    unit_agg: str = "mean"      # mean, median, min, p10
    percentile_low: int = 50
    percentile_high: int = 95
    eps: float = 1e-8


class HealthIndexService:
    """
    Service to:
    - compute reference reconstruction error percentiles
    - persist them
    - score predicted windows
    - consolidate health index tables
    """

    def __init__(
        self,
        signal_cols: List[str],
        config: Optional[HealthIndexConfig] = None,
        error_stats: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        self.signal_cols = signal_cols
        self.config = config or HealthIndexConfig()
        self.error_stats = error_stats

    def fit_error_stats(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute per-signal reference percentiles from training reconstruction errors.
        """
        if y_true.shape != y_pred.shape:
            raise ValueError("y_true and y_pred must have the same shape")

        if y_true.shape[-1] != len(self.signal_cols):
            raise ValueError("signal_cols length does not match tensor last dimension")

        abs_err = np.abs(y_true - y_pred)

        p_low = self.config.percentile_low
        p_high = self.config.percentile_high

        stats = {}
        for j, sig in enumerate(self.signal_cols):
            sig_err = abs_err[:, :, j].reshape(-1)

            low = float(np.percentile(sig_err, p_low))
            high = float(np.percentile(sig_err, p_high))

            stats[sig] = {
                f"p{p_low}": low,
                f"p{p_high}": high,
                "mean": float(np.mean(sig_err)),
                "std": float(np.std(sig_err)),
                "min": float(np.min(sig_err)),
                "max": float(np.max(sig_err)),
                "n": int(sig_err.shape[0]),
            }

        self.error_stats = stats
        return stats

    def save(self, artifact_dir: str) -> None:
        """Save Health Index configuration and error statistics."""
        if self.error_stats is None:
            raise RuntimeError("error_stats are not fitted yet.")

        os.makedirs(artifact_dir, exist_ok=True)

        with open(os.path.join(artifact_dir, "health_index_config.json"), "w", encoding="utf-8") as f:
            json.dump(asdict(self.config), f, indent=2)

        with open(os.path.join(artifact_dir, "error_stats.json"), "w", encoding="utf-8") as f:
            json.dump(self.error_stats, f, indent=2)

        with open(os.path.join(artifact_dir, "signal_cols.json"), "w", encoding="utf-8") as f:
            json.dump(self.signal_cols, f, indent=2)

    @classmethod
    def load(cls, artifact_dir: str) -> "HealthIndexService":
        """Load saved Health Index service artifacts."""
        with open(os.path.join(artifact_dir, "health_index_config.json"), "r", encoding="utf-8") as f:
            config = HealthIndexConfig(**json.load(f))

        with open(os.path.join(artifact_dir, "error_stats.json"), "r", encoding="utf-8") as f:
            error_stats = json.load(f)

        with open(os.path.join(artifact_dir, "signal_cols.json"), "r", encoding="utf-8") as f:
            signal_cols = json.load(f)

        return cls(
            signal_cols=signal_cols,
            config=config,
            error_stats=error_stats,
        )

    def score_windows(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        pred_meta: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Score windows and return:
        - signal_window_df: one row per window per signal
        - window_hi_df: one row per window
        - unit_hi_df: one row per unit
        """
        if self.error_stats is None:
            raise RuntimeError("error_stats not available. Fit or load them first.")

        if y_true.shape != y_pred.shape:
            raise ValueError("y_true and y_pred must have the same shape")

        if y_true.shape[0] != len(pred_meta):
            raise ValueError("pred_meta must have one row per window")

        if y_true.shape[-1] != len(self.signal_cols):
            raise ValueError("signal_cols length does not match tensor last dimension")

        abs_err = np.abs(y_true - y_pred)
        n_windows, seq_len, n_signals = abs_err.shape

        def agg_time(arr, method: str):
            if method == "mean":
                return float(np.mean(arr))
            elif method == "median":
                return float(np.median(arr))
            elif method == "max":
                return float(np.max(arr))
            elif method == "p95":
                return float(np.percentile(arr, 95))
            else:
                raise ValueError("Invalid time_agg")

        def agg_signals(arr, method: str):
            if method == "mean":
                return float(np.mean(arr))
            elif method == "rms":
                return float(np.sqrt(np.mean(np.square(arr))))
            elif method == "max":
                return float(np.max(arr))
            else:
                raise ValueError("Invalid signal_agg")

        def agg_unit(series: pd.Series, method: str):
            if method == "mean":
                return series.mean()
            elif method == "median":
                return series.median()
            elif method == "min":
                return series.min()
            elif method == "p10":
                return series.quantile(0.10)
            else:
                raise ValueError("Invalid unit_agg")

        p_low = self.config.percentile_low
        p_high = self.config.percentile_high
        eps = self.config.eps

        signal_rows = []
        window_rows = []

        for i in range(n_windows):
            base_meta = pred_meta.iloc[i].to_dict()

            norm_vals_window = []
            raw_vals_window = []

            for j, sig in enumerate(self.signal_cols):
                sig_stats = self.error_stats[sig]
                low = sig_stats[f"p{p_low}"]
                high = sig_stats[f"p{p_high}"]

                if high <= low:
                    raise ValueError(f"Invalid error stats for signal '{sig}'")

                err_ts = abs_err[i, :, j]
                norm_ts = np.clip((err_ts - low) / (high - low + eps), a_min=0.0, a_max=None)

                raw_err = agg_time(err_ts, self.config.time_agg)
                norm_err = agg_time(norm_ts, self.config.time_agg)

                raw_vals_window.append(raw_err)
                norm_vals_window.append(norm_err)

                signal_rows.append({
                    **base_meta,
                    "signal": sig,
                    "recon_error_raw": raw_err,
                    "recon_error_norm": norm_err,
                    f"p{p_low}_ref": low,
                    f"p{p_high}_ref": high,
                })

            reconstruction_error_raw = agg_signals(np.array(raw_vals_window), self.config.signal_agg)
            reconstruction_error_score = agg_signals(np.array(norm_vals_window), self.config.signal_agg)
            health_index_window = float(np.exp(-self.config.alpha * reconstruction_error_score))

            window_rows.append({
                **base_meta,
                "reconstruction_error_raw": reconstruction_error_raw,
                "reconstruction_error_score": reconstruction_error_score,
                "health_index": health_index_window,
                "n_signals": n_signals,
                "window_size": seq_len,
            })

        signal_window_df = pd.DataFrame(signal_rows)
        window_hi_df = pd.DataFrame(window_rows)

        unit_col = "Unit" if "Unit" in window_hi_df.columns else "unit"

        unit_hi_df = (
            window_hi_df.groupby(unit_col, as_index=False)
            .agg(
                health_index=("health_index", lambda s: agg_unit(s, self.config.unit_agg)),
                reconstruction_error=("reconstruction_error_score", lambda s: agg_unit(s, self.config.unit_agg)),
                n_windows=("health_index", "count"),
                start_time=("start_time", "min"),
                end_time=("end_time", "max"),
            )
        )

        return signal_window_df, window_hi_df, unit_hi_df

    def consolidate_window_health_index(
        self,
        window_hi_df: pd.DataFrame,
        unit_col: str = "Unit",
        start_col: str = "start_time",
        end_col: str = "end_time",
        hi_col: str = "health_index",
    ) -> pd.DataFrame:
        """
        Return the compact dataframe:
        unit U between T0 and Tf had HI H
        """
        cols = [unit_col, start_col, end_col, hi_col]
        optional_cols = [c for c in ["hour_idx", "reconstruction_error_score", "created_fraction", "imputed_fraction"] if c in window_hi_df.columns]
        return window_hi_df[cols + optional_cols].copy()
