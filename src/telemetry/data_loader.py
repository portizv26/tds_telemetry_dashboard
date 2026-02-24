"""
Data Loading Module

Handles loading telemetry data from Silver layer partitions.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

from src.utils.logger import logger


def load_evaluation_week(client: str, week: int, year: int, base_dir: Optional[Path] = None) -> pd.DataFrame:
    """
    Load telemetry data for a specific evaluation week.
    
    Parameters
    ----------
    client : str
        Client identifier (e.g., 'cda', 'emin')
    week : int
        Week number (1-52)
    year : int
        Year (e.g., 2026)
    base_dir : Path, optional
        Base directory path. If None, uses default structure.
    
    Returns
    -------
    pd.DataFrame
        Telemetry data for the evaluation week with 'Fecha' as datetime
    
    Raises
    ------
    FileNotFoundError
        If the partition file doesn't exist
    ValueError
        If the data is empty or invalid
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / 'data' / 'telemetry'
    
    silver_dir = base_dir / 'silver' / client / 'Telemetry_Wide_With_States'
    input_file = silver_dir / f'Week{week:02d}Year{year}.parquet'
    
    if not input_file.exists():
        raise FileNotFoundError(f"Evaluation week file not found: {input_file}")
    
    logger.info(f"Loading evaluation week: {input_file}")
    df = pd.read_parquet(input_file)
    
    if df.empty:
        raise ValueError(f"Evaluation week file is empty: {input_file}")
    
    # Ensure Fecha is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['Fecha']):
        df['Fecha'] = pd.to_datetime(df['Fecha'])
    
    logger.info(f"Loaded {len(df)} rows, {df['Unit'].nunique()} units for Week {week:02d} Year {year}")
    
    return df


def load_baseline_training_window(
    client: str,
    evaluation_week: int,
    evaluation_year: int,
    lookback_days: int = 90,
    base_dir: Optional[Path] = None
) -> pd.DataFrame:
    """
    Load historical telemetry data for baseline computation.
    
    Loads data from the 'lookback_days' period before the evaluation week.
    
    Parameters
    ----------
    client : str
        Client identifier
    evaluation_week : int
        Current evaluation week number
    evaluation_year : int
        Current evaluation year
    lookback_days : int, default 90
        Number of days to look back for baseline training
    base_dir : Path, optional
        Base directory path
    
    Returns
    -------
    pd.DataFrame
        Historical telemetry data for baseline computation
    
    Raises
    ------
    ValueError
        If insufficient historical data is available
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / 'data' / 'telemetry'
    
    silver_dir = base_dir / 'silver' / client / 'Telemetry_Wide_With_States'
    
    # Calculate date range for baseline
    # Week number to date conversion (approximate - using Monday of the week)
    eval_date = datetime.strptime(f'{evaluation_year}-W{evaluation_week:02d}-1', '%Y-W%W-%w')
    baseline_start_date = eval_date - timedelta(days=lookback_days)
    baseline_end_date = eval_date - timedelta(days=1)  # Don't include evaluation week
    
    logger.info(f"Loading baseline data from {baseline_start_date.date()} to {baseline_end_date.date()}")
    
    # Load all available parquet files
    parquet_files = sorted(silver_dir.glob('Week*.parquet'))
    
    if not parquet_files:
        raise ValueError(f"No historical data files found in {silver_dir}")
    
    # Load and filter data
    dfs = []
    for file in parquet_files:
        try:
            df_chunk = pd.read_parquet(file)
            if 'Fecha' in df_chunk.columns:
                if not pd.api.types.is_datetime64_any_dtype(df_chunk['Fecha']):
                    df_chunk['Fecha'] = pd.to_datetime(df_chunk['Fecha'])
                
                # Filter to baseline window
                mask = (df_chunk['Fecha'] >= baseline_start_date) & (df_chunk['Fecha'] <= baseline_end_date)
                df_filtered = df_chunk[mask]
                
                if not df_filtered.empty:
                    dfs.append(df_filtered)
                    logger.debug(f"  Loaded {len(df_filtered)} rows from {file.name}")
        except Exception as e:
            logger.warning(f"  Could not load {file.name}: {e}")
            continue
    
    if not dfs:
        raise ValueError(f"No historical data found in baseline window ({lookback_days} days)")
    
    baseline_df = pd.concat(dfs, ignore_index=True)
    
    # Sort by date for determinism
    baseline_df = baseline_df.sort_values(['Unit', 'Fecha']).reset_index(drop=True)
    
    logger.info(f"Loaded {len(baseline_df)} rows, {baseline_df['Unit'].nunique()} units for baseline training")
    
    return baseline_df


def load_component_mapping(client: str, base_dir: Optional[Path] = None) -> Dict:
    """
    Load component-to-signals mapping configuration.
    
    Parameters
    ----------
    client : str
        Client identifier (used for potential client-specific mappings)
    base_dir : Path, optional
        Base directory path
    
    Returns
    -------
    dict
        Mapping structure: {component_name: {'signals': [...], 'criticality': int}}
    
    Raises
    ------
    FileNotFoundError
        If mapping file doesn't exist
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / 'data' / 'telemetry'
    
    mapping_file = base_dir / 'component_signals_mapping.json'
    
    if not mapping_file.exists():
        raise FileNotFoundError(f"Component mapping file not found: {mapping_file}")
    
    logger.info(f"Loading component mapping from {mapping_file}")
    
    with open(mapping_file, 'r') as f:
        mapping = json.load(f)
        
    mapping = mapping['components']
    
    logger.info(f"Loaded mapping for {len(mapping)} components")
    
    return mapping


def get_signal_columns(df: pd.DataFrame) -> List[str]:
    """
    Extract list of signal columns from telemetry dataframe.
    
    Excludes metadata columns like Fecha, Unit, Estado, EstadoMaquina, etc.
    
    Parameters
    ----------
    df : pd.DataFrame
        Telemetry dataframe
    
    Returns
    -------
    list of str
        List of signal column names
    """
    excluded_cols = {
        'Fecha', 'Unit', 'Estado', 'EstadoMaquina', 'EstadoCarga',
        'GPSLat', 'GPSLon', 'GPSElevation', 'Week-Year',
        'EngSpd', 'GroundSpd', 'Payload'
    }
    
    signal_cols = [col for col in df.columns if col not in excluded_cols]
    
    logger.debug(f"Identified {len(signal_cols)} signal columns")
    
    return signal_cols
