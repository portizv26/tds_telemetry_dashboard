"""
Cycles Module

Handles cycle detection, validation, and interpolation for temporal continuity.
"""

from typing import List
import pandas as pd
import numpy as np
from tqdm.auto import tqdm

from .config import (
    UNIT_COL,
    TIME_COL,
    CAT_COLS,
    FREQ,
    GAP_THRESHOLD,
    MIN_CYCLE_DURATION,
    MIN_COVERAGE,
    INTERP_LIMIT,
)


def detect_cycles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect operating cycles based on time gaps.
    
    A new cycle starts when:
    - It's a new unit
    - Time gap exceeds GAP_THRESHOLD
    
    Args:
        df: Input DataFrame with Unit and Fecha columns
    
    Returns:
        DataFrame with added 'cycle_id' column
    """
    df_out = df.copy()
    
    # Calculate time difference within each unit
    dt = df_out.groupby(UNIT_COL)[TIME_COL].diff()
    
    # New cycle marker
    new_cycle = dt.isna() | (dt > GAP_THRESHOLD)
    
    # Assign cycle IDs
    df_out["cycle_id"] = new_cycle.groupby(df_out[UNIT_COL]).cumsum().astype("int64")
    
    return df_out


def is_valid_cycle(cycle_df: pd.DataFrame) -> bool:
    """
    Check if a cycle is valid for training/analysis.
    
    Valid if:
    - Duration >= MIN_CYCLE_DURATION
    - Coverage (actual samples / expected samples) >= MIN_COVERAGE
    
    Args:
        cycle_df: DataFrame for a single cycle
    
    Returns:
        True if cycle is valid, False otherwise
    """
    start = cycle_df[TIME_COL].iloc[0]
    end = cycle_df[TIME_COL].iloc[-1]
    duration = end - start
    
    n_actual = len(cycle_df)
    freq_td = pd.to_timedelta(FREQ)
    n_expected = int(round(duration / freq_td)) + 1
    
    coverage = n_actual / n_expected if n_expected > 0 else 0.0
    
    return (duration >= MIN_CYCLE_DURATION) and (coverage >= MIN_COVERAGE)


def interpolate_cycle(cycle_df: pd.DataFrame, num_cols: List[str]) -> pd.DataFrame:
    """
    Interpolate missing values within a single cycle.
    
    Process:
    1. Build complete 1-minute time index
    2. Reindex to create missing timestamps
    3. Forward-fill categorical columns
    4. Time-based interpolation for numeric columns
    5. Flag created and imputed rows
    
    Args:
        cycle_df: DataFrame for a single cycle
        num_cols: List of numeric column names to interpolate
    
    Returns:
        Interpolated DataFrame
    """
    out = cycle_df.copy()
    out = out.sort_values(TIME_COL).reset_index(drop=True)
    
    # Store original timestamps
    original_timestamps = set(out[TIME_COL])
    
    # Build full 1-minute index
    full_time_index = pd.date_range(
        start=out[TIME_COL].min(),
        end=out[TIME_COL].max(),
        freq=FREQ
    )
    
    # Reindex
    out = out.set_index(TIME_COL).reindex(full_time_index)
    out.index.name = TIME_COL
    
    # Reconstruct metadata
    if UNIT_COL in cycle_df.columns:
        out[UNIT_COL] = cycle_df[UNIT_COL].iloc[0]
    
    if "cycle_id" in cycle_df.columns:
        out["cycle_id"] = cycle_df["cycle_id"].iloc[0]
    
    # Forward-fill categoricals
    for col in CAT_COLS:
        if col in out.columns:
            out[col] = out[col].ffill().bfill()
    
    # Filter to existing numeric columns
    valid_num_cols = [c for c in num_cols if c in out.columns]
    
    # Convert to numeric if needed
    for col in valid_num_cols:
        if out[col].dtype == "object" or pd.api.types.is_string_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce")
    
    # Flag created rows
    out["created_by_reindex"] = (~out.index.isin(original_timestamps)).astype("int8")
    
    # Track missing before interpolation
    before_na = out[valid_num_cols].isna()
    
    # Time-based interpolation
    out[valid_num_cols] = out[valid_num_cols].interpolate(
        method="time",
        limit=INTERP_LIMIT,
        limit_area="inside",
    )
    
    # Flag imputed rows
    out["imputed_any"] = (
        (before_na & ~out[valid_num_cols].isna()).any(axis=1)
    ).astype("int8")
    
    return out.reset_index()


def process_cycles(df: pd.DataFrame, num_cols: List[str]) -> pd.DataFrame:
    """
    Process all cycles: filter valid cycles and interpolate.
    
    Args:
        df: DataFrame with cycle_id column
        num_cols: List of numeric columns to interpolate
    
    Returns:
        DataFrame with only valid, interpolated cycles
    """
    cycles = []
    
    grouped = df.groupby([UNIT_COL, "cycle_id"], sort=False)
    
    for (unit, cycle_id), cycle_df in tqdm(grouped, desc="Processing cycles"):
        if is_valid_cycle(cycle_df):
            interpolated = interpolate_cycle(cycle_df, num_cols)
            cycles.append(interpolated)
    
    if cycles:
        result = pd.concat(cycles, ignore_index=True)
        print(f"Valid cycles: {len(cycles)}, Total rows: {len(result)/1e6:.3f}M")
        return result
    else:
        print("Warning: No valid cycles found")
        return df.head(0).copy()
