"""
Baseline Computation Module

Computes historical percentile baselines for anomaly detection.
"""

from typing import List, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

from src.utils.logger import logger


# Baseline configuration constants
PERCENTILES = [0.02, 0.05, 0.95, 0.98]
MIN_SAMPLES_FOR_BASELINE = 100


def compute_baseline_percentiles(
    training_df: pd.DataFrame,
    signal_cols: List[str],
    percentiles: List[float] = None,
    baseline_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Compute historical baseline percentiles for each signal.
    
    Calculates percentiles per (Unit, Signal, EstadoMaquina) combination
    to create state-aware baselines.
    
    Parameters
    ----------
    training_df : pd.DataFrame
        Historical telemetry data for baseline training
    signal_cols : list of str
        List of signal column names to compute baselines for
    percentiles : list of float, optional
        Percentile values to compute (default: [0.02, 0.05, 0.95, 0.98])
    baseline_date : str, optional
        Date identifier for this baseline (YYYYMMDD format)
    
    Returns
    -------
    pd.DataFrame
        Baseline dataframe with columns:
        - Unit: Unit identifier
        - Signal: Signal name
        - EstadoMaquina: Operational state
        - P2, P5, P95, P98: Percentile values
        - sample_count: Number of samples used
        - baseline_version: Date identifier
    
    Notes
    -----
    - Requires minimum samples (default 100) per combination
    - Falls back to aggregate across states if insufficient per-state data
    - Filters out combinations with too few samples
    """
    if percentiles is None:
        percentiles = PERCENTILES
    
    if baseline_date is None:
        baseline_date = datetime.now().strftime('%Y%m%d')
    
    logger.info(f"Computing baseline percentiles for {len(signal_cols)} signals")
    logger.info(f"  Percentiles: {percentiles}")
    logger.info(f"  Training data: {len(training_df)} rows, {training_df['Unit'].nunique()} units")
    
    baselines = []
    
    # Compute per unit, per signal, per state
    units = training_df['Unit'].unique()
    
    for unit in units:
        unit_df = training_df[training_df['Unit'] == unit]
        
        for signal in signal_cols:
            if signal not in unit_df.columns:
                continue
            
            # Try state-specific baselines first
            if 'EstadoMaquina' in unit_df.columns:
                states = unit_df['EstadoMaquina'].unique()
                
                for state in states:
                    state_df = unit_df[unit_df['EstadoMaquina'] == state]
                    values = state_df[signal].dropna()
                    
                    if len(values) >= MIN_SAMPLES_FOR_BASELINE:
                        percentile_values = np.percentile(values, [p * 100 for p in percentiles])
                        
                        baseline_record = {
                            'Unit': unit,
                            'Signal': signal,
                            'EstadoMaquina': state,
                            'P2': percentile_values[0],
                            'P5': percentile_values[1],
                            'P95': percentile_values[2],
                            'P98': percentile_values[3],
                            'sample_count': len(values),
                            'baseline_version': baseline_date
                        }
                        baselines.append(baseline_record)
            
            # Fallback: aggregate across all states if no state-specific baselines
            values_all_states = unit_df[signal].dropna()
            
            if len(values_all_states) >= MIN_SAMPLES_FOR_BASELINE:
                # Check if we already have state-specific baselines
                has_state_baselines = any(
                    b['Unit'] == unit and b['Signal'] == signal 
                    for b in baselines
                )
                
                if not has_state_baselines:
                    percentile_values = np.percentile(values_all_states, [p * 100 for p in percentiles])
                    
                    baseline_record = {
                        'Unit': unit,
                        'Signal': signal,
                        'EstadoMaquina': 'All',  # Aggregate baseline
                        'P2': percentile_values[0],
                        'P5': percentile_values[1],
                        'P95': percentile_values[2],
                        'P98': percentile_values[3],
                        'sample_count': len(values_all_states),
                        'baseline_version': baseline_date
                    }
                    baselines.append(baseline_record)
    
    baseline_df = pd.DataFrame(baselines)
    
    logger.info(f"Computed {len(baseline_df)} baseline combinations")
    logger.info(f"  Units with baselines: {baseline_df['Unit'].nunique()}")
    logger.info(f"  Signals with baselines: {baseline_df['Signal'].nunique()}")
    
    # Log state-specific vs aggregate
    state_specific = (baseline_df['EstadoMaquina'] != 'All').sum()
    aggregate = (baseline_df['EstadoMaquina'] == 'All').sum()
    logger.info(f"  State-specific: {state_specific}, Aggregate: {aggregate}")
    
    return baseline_df


def save_baseline(baseline_df: pd.DataFrame, client: str, base_dir: Optional[Path] = None) -> Path:
    """
    Save baseline dataframe to Golden layer.
    
    Parameters
    ----------
    baseline_df : pd.DataFrame
        Baseline percentiles dataframe
    client : str
        Client identifier
    base_dir : Path, optional
        Base directory path
    
    Returns
    -------
    Path
        Path to saved baseline file
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / 'data' / 'telemetry'
    
    # Get baseline version from dataframe
    baseline_version = baseline_df['baseline_version'].iloc[0]
    
    # Output directory
    baseline_dir = base_dir / 'golden' / client / 'baselines'
    baseline_dir.mkdir(parents=True, exist_ok=True)
    
    # Output file
    output_file = baseline_dir / f'baseline_{baseline_version}.parquet'
    
    # Save
    baseline_df.to_parquet(output_file, index=False)
    
    logger.info(f"Saved baseline to {output_file}")
    logger.info(f"  Baseline version: {baseline_version}")
    logger.info(f"  Total records: {len(baseline_df)}")
    
    return output_file


def load_baseline(
    client: str,
    baseline_version: Optional[str] = None,
    base_dir: Optional[Path] = None
) -> pd.DataFrame:
    """
    Load existing baseline from Golden layer.
    
    Parameters
    ----------
    client : str
        Client identifier
    baseline_version : str, optional
        Specific baseline version to load (YYYYMMDD format).
        If None, loads the most recent baseline.
    base_dir : Path, optional
        Base directory path
    
    Returns
    -------
    pd.DataFrame
        Baseline percentiles dataframe
    
    Raises
    ------
    FileNotFoundError
        If no baseline file is found
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / 'data' / 'telemetry'
    
    baseline_dir = base_dir / 'golden' / client / 'baselines'
    
    if not baseline_dir.exists():
        raise FileNotFoundError(f"Baseline directory not found: {baseline_dir}")
    
    if baseline_version is not None:
        # Load specific version
        baseline_file = baseline_dir / f'baseline_{baseline_version}.parquet'
        if not baseline_file.exists():
            raise FileNotFoundError(f"Baseline file not found: {baseline_file}")
    else:
        # Load most recent
        baseline_files = sorted(baseline_dir.glob('baseline_*.parquet'))
        if not baseline_files:
            raise FileNotFoundError(f"No baseline files found in {baseline_dir}")
        baseline_file = baseline_files[-1]
    
    logger.info(f"Loading baseline from {baseline_file}")
    baseline_df = pd.read_parquet(baseline_file)
    
    logger.info(f"  Loaded {len(baseline_df)} baseline records")
    
    return baseline_df
