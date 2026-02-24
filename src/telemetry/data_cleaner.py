"""
Data Cleaning and Validation Module

Handles validation and cleaning of telemetry data.
"""

from typing import List
import pandas as pd
import numpy as np

from src.utils.logger import logger


def validate_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and clean timestamp data.
    
    - Ensures 'Fecha' is datetime type
    - Removes rows with null timestamps
    - Sorts by Unit and Fecha for determinism
    
    Parameters
    ----------
    df : pd.DataFrame
        Input telemetry dataframe
    
    Returns
    -------
    pd.DataFrame
        Cleaned dataframe with valid timestamps
    """
    initial_count = len(df)
    
    # Ensure datetime type
    if not pd.api.types.is_datetime64_any_dtype(df['Fecha']):
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    
    # Remove null timestamps
    df = df[df['Fecha'].notna()].copy()
    
    null_count = initial_count - len(df)
    if null_count > 0:
        logger.warning(f"Removed {null_count} rows with invalid timestamps")
    
    # Sort for determinism
    df = df.sort_values(['Unit', 'Fecha']).reset_index(drop=True)
    
    logger.info(f"Timestamp validation: {len(df)} valid rows")
    
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate telemetry readings.
    
    Duplicates are identified by (Unit, Fecha) combination.
    Keeps the first occurrence.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input telemetry dataframe
    
    Returns
    -------
    pd.DataFrame
        Deduplicated dataframe
    """
    initial_count = len(df)
    
    df = df.drop_duplicates(subset=['Unit', 'Fecha'], keep='first').reset_index(drop=True)
    
    duplicates_removed = initial_count - len(df)
    if duplicates_removed > 0:
        logger.warning(f"Removed {duplicates_removed} duplicate readings")
    
    return df


def handle_missing_values(df: pd.DataFrame, signal_cols: List[str]) -> pd.DataFrame:
    """
    Handle missing values in signal columns.
    
    Strategy:
    - Missing values (NaN) are kept as-is for now
    - They will be handled during scoring (excluded from window calculations)
    - Tracks missingness statistics per signal
    
    Parameters
    ----------
    df : pd.DataFrame
        Input telemetry dataframe
    signal_cols : list of str
        List of signal column names
    
    Returns
    -------
    pd.DataFrame
        Dataframe with missingness handled
    """
    # Calculate missingness statistics
    missing_stats = {}
    for col in signal_cols:
        if col in df.columns:
            missing_pct = (df[col].isna().sum() / len(df)) * 100
            if missing_pct > 0:
                missing_stats[col] = missing_pct
    
    if missing_stats:
        high_missing = {k: v for k, v in missing_stats.items() if v > 50}
        if high_missing:
            logger.warning(f"Signals with >50% missing data: {high_missing}")
        else:
            logger.info(f"{len(missing_stats)} signals have missing data (all <50%)")
    
    return df


def flag_extreme_outliers(
    df: pd.DataFrame,
    signal_cols: List[str],
    z_threshold: float = 10
) -> pd.DataFrame:
    """
    Flag extreme outliers that may indicate sensor errors.
    
    Uses z-score threshold to identify readings far outside normal range.
    Extreme outliers are replaced with NaN.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input telemetry dataframe
    signal_cols : list of str
        List of signal column names
    z_threshold : float, default 10
        Z-score threshold for flagging extreme outliers
    
    Returns
    -------
    pd.DataFrame
        Dataframe with extreme outliers replaced by NaN
    """
    outliers_flagged = 0
    
    for col in signal_cols:
        if col not in df.columns:
            continue
        
        # Calculate z-scores (ignoring NaN)
        values = df[col].values
        if np.isnan(values).all():
            continue
        mean = np.nanmean(values)
        std = np.nanstd(values)
        
        if std > 0:
            z_scores = np.abs((values - mean) / std)
            extreme_mask = z_scores > z_threshold
            
            n_extreme = np.sum(extreme_mask)
            if n_extreme > 0:
                df.loc[extreme_mask, col] = np.nan
                outliers_flagged += n_extreme
                logger.debug(f"  {col}: Flagged {n_extreme} extreme outliers (z > {z_threshold})")
    
    if outliers_flagged > 0:
        logger.warning(f"Flagged {outliers_flagged} extreme outliers as NaN")
    
    return df


def validate_operational_states(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and standardize operational state values.
    
    Ensures:
    - EstadoMaquina contains valid values
    - Invalid states are logged and filtered
    
    Parameters
    ----------
    df : pd.DataFrame
        Input telemetry dataframe
    
    Returns
    -------
    pd.DataFrame
        Dataframe with validated operational states
    """
    valid_states = {'ND', 'Operacional Bajo', 'Operacional Alto',
                    'Ralenti Alto', 'Ralenti', 'Ralenti Bajo'}
    
    if 'EstadoMaquina' not in df.columns:
        logger.warning("EstadoMaquina column not found - skipping state validation")
        return df
    
    initial_count = len(df)
    
    # Filter to valid states
    df = df[df['EstadoMaquina'].isin(valid_states)].copy()
    
    invalid_count = initial_count - len(df)
    if invalid_count > 0:
        logger.warning(f"Removed {invalid_count} rows with invalid EstadoMaquina values")
    
    return df


def clean_telemetry_data(df: pd.DataFrame, signal_cols: List[str]) -> pd.DataFrame:
    """
    Complete data cleaning pipeline.
    
    Applies all cleaning and validation steps in sequence:
    1. Timestamp validation
    2. Duplicate removal
    3. Operational state validation
    4. Missing value handling
    5. Extreme outlier flagging
    
    Parameters
    ----------
    df : pd.DataFrame
        Raw telemetry dataframe
    signal_cols : list of str
        List of signal column names
    
    Returns
    -------
    pd.DataFrame
        Cleaned telemetry dataframe
    """
    logger.info("Starting data cleaning pipeline")
    initial_count = len(df)
    
    # Step 1: Validate timestamps
    df = validate_timestamps(df)
    
    # Step 2: Remove duplicates
    df = remove_duplicates(df)
    
    # Step 3: Validate operational states
    df = validate_operational_states(df)
    
    # Step 4: Handle missing values
    df = handle_missing_values(df, signal_cols)
    
    # Step 5: Flag extreme outliers
    df = flag_extreme_outliers(df, signal_cols)
    
    final_count = len(df)
    removed_pct = ((initial_count - final_count) / initial_count) * 100 if initial_count > 0 else 0
    
    logger.info(f"Data cleaning complete: {final_count} rows ({removed_pct:.1f}% removed)")
    
    return df
