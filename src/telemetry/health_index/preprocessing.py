"""
Preprocessing module.

Single responsibility: transform raw telemetry data into clean,
cycle-segmented, imputed, and labelled DataFrames ready for
feature engineering.
"""

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from src.utils.logger import get_logger

from .config import HealthIndexConfig

logger = get_logger(__name__)


# ── Outlier removal ─────────────────────────────────────────────────────────


def clean_outliers(
    df: pd.DataFrame,
    margins: Dict[str, Tuple[float, float]],
) -> pd.DataFrame:
    """Replace values outside *margins* with NaN."""
    df = df.copy()
    for col, (lo, hi) in margins.items():
        if col in df.columns:
            df[col] = df[col].where((df[col] >= lo) & (df[col] <= hi), other=pd.NA)
    return df


def drop_sparse_rows(
    df: pd.DataFrame,
    num_cols: List[str],
    min_present_ratio: float = 0.5,
) -> pd.DataFrame:
    """Drop rows where fewer than *min_present_ratio* of numerical signals present."""
    thresh = int(len(num_cols) * min_present_ratio)
    df = df.dropna(subset=num_cols, thresh=thresh)
    return df.reset_index(drop=True)


# ── Cycle detection & imputation ────────────────────────────────────────────


def assign_cycles(
    df: pd.DataFrame,
    cfg: HealthIndexConfig,
) -> pd.DataFrame:
    """Assign a *cycle_id* per unit based on temporal gaps > gap_threshold."""
    df = df.copy()
    gap = pd.Timedelta(minutes=cfg.gap_threshold_minutes)
    dt = df.groupby(cfg.unit_col)[cfg.time_col].diff()
    new_cycle = dt.isna() | (dt > gap)
    df["cycle_id"] = new_cycle.groupby(df[cfg.unit_col]).cumsum().astype("int64")
    return df


def _is_valid_cycle(
    cycle_df: pd.DataFrame,
    cfg: HealthIndexConfig,
) -> bool:
    """Return True if cycle meets duration and coverage requirements."""
    duration = cycle_df[cfg.time_col].iloc[-1] - cycle_df[cfg.time_col].iloc[0]
    freq_td = pd.to_timedelta(cfg.freq)
    expected_n = int(round(duration / freq_td)) + 1
    coverage = len(cycle_df) / expected_n if expected_n > 0 else 0.0
    min_dur = pd.Timedelta(hours=cfg.min_duration_hours)
    return (duration >= min_dur) and (coverage >= cfg.min_coverage)


def _impute_cycle(
    cycle_df: pd.DataFrame,
    num_cols: List[str],
    cfg: HealthIndexConfig,
) -> pd.DataFrame:
    """Interpolate numerical columns and forward-fill categoricals."""
    out = cycle_df.copy()
    out = out.set_index(cfg.time_col)

    before_na = out[num_cols].isna()
    out[num_cols] = out[num_cols].interpolate(
        method="time", limit=cfg.interpolation_limit, limit_area="inside",
    )
    out["imputed_any"] = (before_na & ~out[num_cols].isna()).any(axis=1).astype("int8")
    out = out.reset_index()

    for col in cfg.cat_cols:
        if col in out.columns:
            out[col] = out[col].ffill()
    out.fillna(cfg.default_cat_values, inplace=True)
    return out


def process_cycles(
    df: pd.DataFrame,
    num_cols: List[str],
    cfg: HealthIndexConfig,
) -> pd.DataFrame:
    """Split into cycles, keep valid ones, impute, and concatenate."""
    df = assign_cycles(df, cfg)
    cycles = []
    for (_, _), cdf in tqdm(
        df.groupby([cfg.unit_col, "cycle_id"], sort=False),
        desc="Processing cycles",
    ):
        if _is_valid_cycle(cdf, cfg):
            cycles.append(_impute_cycle(cdf, num_cols, cfg))
    if not cycles:
        raise ValueError("No valid cycles — check gap_threshold / min_duration settings")
    result = pd.concat(cycles, ignore_index=True)
    n_cycles = result[[cfg.unit_col, "cycle_id"]].drop_duplicates().shape[0]
    logger.info(f"Valid cycles: {n_cycles}  |  rows: {len(result):,}")
    return result


# ── Labelling ───────────────────────────────────────────────────────────────


def label_cycles(
    df: pd.DataFrame,
    num_cols: List[str],
    cfg: HealthIndexConfig,
) -> pd.DataFrame:
    """Label each (Unit, cycle_id) as Normal or Anomalous."""
    signal_cols = [c for c in num_cols if ("GPS" not in c) and ("Spd" not in c)]
    percentiles = {c: df[c].quantile([0.05, 0.95]) for c in signal_cols}

    out_cols = []
    for col, pcts in percentiles.items():
        ocol = f"{col}_out_range"
        df[ocol] = ~df[col].between(pcts[0.05], pcts[0.95])
        out_cols.append(ocol)

    summary = df.groupby([cfg.unit_col, "cycle_id"])[out_cols].sum()
    totals = df.groupby([cfg.unit_col, "cycle_id"]).size().rename("total_rows")
    summary["total_out_range"] = summary[out_cols].sum(axis=1)
    summary = summary.merge(totals, left_index=True, right_index=True)
    summary["total_ratio"] = summary["total_out_range"] / summary["total_rows"]
    summary["Label"] = np.where(
        summary["total_ratio"] < cfg.anomaly_ratio, "Normal", "Anomalous",
    )

    df = df.merge(summary[["Label"]], left_on=[cfg.unit_col, "cycle_id"], right_index=True)
    df.drop(columns=out_cols, inplace=True)
    return df


# ── Train / test split ──────────────────────────────────────────────────────


def split_train_test(
    df: pd.DataFrame,
    cfg: HealthIndexConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split by time: everything before the cutoff → train, rest → test."""
    cutoff = df[cfg.time_col].max() - pd.Timedelta(weeks=cfg.test_weeks)
    df_train = df[df[cfg.time_col] < cutoff].copy()
    df_test = df[df[cfg.time_col] >= cutoff].copy()
    logger.info(
        f"Train: {len(df_train):,} rows  "
        f"({df_train[cfg.time_col].min()} → {df_train[cfg.time_col].max()})"
    )
    logger.info(
        f"Test:  {len(df_test):,} rows  "
        f"({df_test[cfg.time_col].min()} → {df_test[cfg.time_col].max()})"
    )
    return df_train, df_test


# ── Full preprocessing pipeline ─────────────────────────────────────────────


def run_preprocessing(
    df_raw: pd.DataFrame,
    cfg: HealthIndexConfig,
) -> pd.DataFrame:
    """
    Execute the full preprocessing chain:
    clean → drop sparse → cycle detection → imputation → labelling.

    Returns a labelled DataFrame ready for feature engineering.
    """
    num_cols = [c for c in cfg.margins if c in df_raw.columns]
    logger.info(f"Raw rows: {len(df_raw):,}")

    df = clean_outliers(df_raw, cfg.margins)
    df = drop_sparse_rows(df, num_cols)

    cols_to_drop = [c for c in cfg.drop_columns if c in df.columns]
    if cols_to_drop:
        df.drop(columns=cols_to_drop, inplace=True, errors="ignore")

    logger.info(f"After cleaning: {len(df):,} rows")

    df = process_cycles(df, num_cols, cfg)
    df = label_cycles(df, num_cols, cfg)

    logger.info(f"Label distribution:\n{df['Label'].value_counts().to_string()}")
    return df
