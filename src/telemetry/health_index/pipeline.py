"""
Pipeline orchestrator.

Coordinates the full training or inference workflow for all
components defined in the component mapping.
"""

from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.utils.logger import get_logger

from .config import HealthIndexConfig, load_config
from .estimator import ComponentHealthEstimator
from .preprocessing import run_preprocessing, split_train_test

logger = get_logger(__name__)


# ── Data loading helper ─────────────────────────────────────────────────────


def _load_silver_data(cfg: HealthIndexConfig) -> pd.DataFrame:
    """Load all parquet files under the silver data directory."""
    silver_path = cfg.data_silver / cfg.client / "Telemetry_Wide_With_States"
    parquet_files = sorted(silver_path.glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files in {silver_path}")
    dfs = [pd.read_parquet(f) for f in parquet_files]
    df = pd.concat(dfs, ignore_index=True)
    df[cfg.time_col] = pd.to_datetime(df[cfg.time_col])
    df.sort_values([cfg.unit_col, cfg.time_col], inplace=True)
    df.reset_index(drop=True, inplace=True)
    logger.info(
        f"Loaded {len(df):,} rows from {len(parquet_files)} files  "
        f"({df[cfg.time_col].min()} → {df[cfg.time_col].max()})"
    )
    return df


# ── Training pipeline ───────────────────────────────────────────────────────


def run_training(
    cfg: HealthIndexConfig,
    components: Optional[List[str]] = None,
) -> dict:
    """
    Full training pipeline for one or more components.

    1. Load silver data.
    2. Preprocess (clean → cycles → impute → label).
    3. Split train / test.
    4. For each component: ``estimator.fit(df_train)``.

    Returns a dict mapping component → ComponentHealthEstimator.
    """
    df_raw = _load_silver_data(cfg)
    df = run_preprocessing(df_raw, cfg)
    df_train, _ = split_train_test(df, cfg)

    if components is None:
        components = list(cfg.component_mapping["components"].keys())

    estimators = {}
    for comp in components:
        logger.info(f"{'=' * 60}\n  Training component: {comp}\n{'=' * 60}")
        est = ComponentHealthEstimator(cfg, comp)
        est.fit(df_train)
        estimators[comp] = est

    logger.info("All components trained ✓")
    return estimators


# ── Inference pipeline ──────────────────────────────────────────────────────


def run_inference(
    cfg: HealthIndexConfig,
    components: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Full inference pipeline for one or more components.

    1. Load silver data.
    2. Preprocess.
    3. Split train / test.
    4. For each component: ``estimator.predict(df_test)`` → ``estimator.compute()``.
    5. Merge and save golden outputs.

    Returns the combined health-index DataFrame.
    """
    df_raw = _load_silver_data(cfg)
    df = run_preprocessing(df_raw, cfg)
    _, df_test = split_train_test(df, cfg)

    if components is None:
        components = list(cfg.component_mapping["components"].keys())

    all_health = []
    for comp in components:
        logger.info(f"{'=' * 60}\n  Inference component: {comp}\n{'=' * 60}")
        est = ComponentHealthEstimator.from_pretrained(cfg, comp)
        inferences = est.predict(df_test)
        health = est.compute(inferences)
        health["component"] = comp
        all_health.append(health)

    combined = pd.concat(all_health, ignore_index=True)

    # ── Save golden outputs ──
    out_dir = cfg.data_golden / cfg.client
    out_dir.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_dir / "health_index.parquet", index=False)
    logger.info(f"Golden output saved → {out_dir / 'health_index.parquet'}")

    return combined
