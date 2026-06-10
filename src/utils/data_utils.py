"""
Shared utility functions used across all techniques.
Data loading, preprocessing, model specification computation, and validation.
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.config.settings import (
    UNIT_COLNAME,
    STATE_COLNAME,
    TIME_COLNAME,
    PipelineConfig,
)

logger = logging.getLogger(__name__)


# ─── Data Loading ──────────────────────────────────────────────────────────────

def load_telemetry_files(
    telemetry_path: Path,
    weeks: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Load telemetry parquet files from the Silver layer.

    Parameters:
        telemetry_path: Path to Telemetry_Wide_With_States directory
        weeks: Optional list of file stems to load (e.g., ["Week22Year2026"]).
               If None, loads all .parquet files.

    Returns:
        Combined DataFrame sorted by Unit and Fecha.
    """
    parquet_files = sorted(telemetry_path.glob("*.parquet"))

    if weeks:
        parquet_files = [f for f in parquet_files if f.stem in weeks]

    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found in {telemetry_path}")

    frames = []
    for fp in parquet_files:
        df = pd.read_parquet(fp)
        frames.append(df)
        logger.debug(f"Loaded {fp.name}: {len(df)} rows")

    combined = pd.concat(frames, ignore_index=True)
    combined.sort_values([UNIT_COLNAME, TIME_COLNAME], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    logger.info(f"Loaded {len(combined)} rows from {len(parquet_files)} files")
    return combined


def load_baseline(baselines_path: Path, version: Optional[str] = None) -> pd.DataFrame:
    """
    Load baseline parquet file (latest version if not specified).

    Parameters:
        baselines_path: Path to baselines directory
        version: Specific version string (e.g., "20260225"). If None, uses latest.

    Returns:
        Baseline DataFrame.
    """
    if version:
        path = baselines_path / f"baseline_{version}.parquet"
    else:
        files = sorted(baselines_path.glob("baseline_*.parquet"))
        if not files:
            raise FileNotFoundError(f"No baseline files in {baselines_path}")
        path = files[-1]  # Latest by sorted name

    df = pd.read_parquet(path)
    logger.info(f"Loaded baseline: {path.name} ({len(df)} rows)")
    return df


# ─── Preprocessing ─────────────────────────────────────────────────────────────

def compute_model_specification(
    df: pd.DataFrame,
    equipment_metadata: dict,
) -> pd.DataFrame:
    """
    Add model_specification column based on equipment metadata.

    Parameters:
        df: Input telemetry DataFrame
        equipment_metadata: Equipment registry dict

    Returns:
        DataFrame with model_specification column (rows without mapping are dropped).
    """
    unit_to_model = {}
    for equip in equipment_metadata["equipments"]:
        spec = f'{equip["model"]}_with_silencer' if equip.get("has_silencer", False) else equip["model"]
        unit_to_model[equip["name"]] = spec

    df = df.copy()
    df["model_specification"] = df[UNIT_COLNAME].map(unit_to_model)
    n_before = len(df)
    df = df.dropna(subset=["model_specification"])
    n_dropped = n_before - len(df)

    if n_dropped > 0:
        logger.warning(f"Dropped {n_dropped} rows with unmapped units")

    return df


def get_features_for_computation(signal_registry: dict) -> list[str]:
    """Get list of signal names with threshold_compute=True."""
    return [
        s["name"] for s in signal_registry["signals"]
        if s.get("threshold_compute", False)
    ]


def get_signal_metadata(signal_registry: dict, signal_name: str) -> Optional[dict]:
    """Get metadata dict for a specific signal."""
    return next(
        (s for s in signal_registry["signals"] if s["name"] == signal_name),
        None,
    )


def get_system_signals(signal_registry: dict, system_name: str) -> list[str]:
    """Get all signal names belonging to a system with threshold_compute=True."""
    return [
        s["name"] for s in signal_registry["signals"]
        if s.get("system") == system_name and s.get("threshold_compute", False)
    ]


def get_all_systems(signal_registry: dict) -> list[str]:
    """Get unique system names from signal registry."""
    systems = set()
    for s in signal_registry["signals"]:
        system = s.get("system")
        if system and s.get("threshold_compute", False):
            systems.add(system)
    return sorted(systems)


# ─── Validation ────────────────────────────────────────────────────────────────

def validate_telemetry_data(df: pd.DataFrame) -> dict:
    """
    Run data quality checks on telemetry data.

    Returns:
        dict with 'valid' bool and 'issues' list.
    """
    issues = []

    required_cols = [UNIT_COLNAME, TIME_COLNAME, STATE_COLNAME]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        issues.append(f"Missing required columns: {missing_cols}")

    if TIME_COLNAME in df.columns:
        duplicates = df.duplicated(subset=[UNIT_COLNAME, TIME_COLNAME]).sum()
        if duplicates > 0:
            issues.append(f"{duplicates} duplicate (Unit, Fecha) pairs")

    missing_rates = df.isnull().mean()
    high_missing = missing_rates[missing_rates > 0.5].index.tolist()
    # Filter out non-signal columns
    high_missing = [c for c in high_missing if c not in required_cols + ["model_specification"]]
    if high_missing:
        issues.append(f"Signals with >50% missing: {high_missing}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "n_rows": len(df),
        "n_units": df[UNIT_COLNAME].nunique() if UNIT_COLNAME in df.columns else 0,
        "time_range": (
            str(df[TIME_COLNAME].min()),
            str(df[TIME_COLNAME].max()),
        )
        if TIME_COLNAME in df.columns
        else None,
    }


# ─── Scoring Utilities ─────────────────────────────────────────────────────────

def classify_status(risk_score: float, confidence_score: float, normal_max: int = 40, alerta_max: int = 70) -> str:
    """Classify status from risk and confidence scores."""
    if confidence_score < 50:
        return "InsufficientData"
    if risk_score < normal_max:
        return "Normal"
    if risk_score < alerta_max:
        return "Alerta"
    return "Anormal"


def calculate_confidence(
    valid_samples: int,
    expected_samples: int,
    baseline_sample_count: int = 1000,
    state_matched: bool = True,
    min_required_samples: int = 10,
) -> float:
    """
    Calculate confidence score based on data quality factors.

    Returns:
        Confidence score 0-100.
    """
    score = 100.0

    # Coverage penalty
    coverage = min(valid_samples / max(expected_samples, 1), 1.0)
    if coverage < 0.5:
        score -= (0.5 - coverage) * 100

    # Baseline quality
    baseline_factor = min(baseline_sample_count / 1000, 1.0)
    if baseline_factor < 0.5:
        score -= (0.5 - baseline_factor) * 40

    # State matching
    if not state_matched:
        score -= 40

    # Sample size
    if valid_samples < min_required_samples:
        score -= 30

    return max(score, 0.0)
