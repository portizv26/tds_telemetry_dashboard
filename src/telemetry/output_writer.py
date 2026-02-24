"""
Output Writer Module

Handles writing Golden layer outputs.
"""

from pathlib import Path
from typing import Optional
import pandas as pd

from src.utils.logger import logger


def write_golden_outputs(
    machine_df: pd.DataFrame,
    component_df: pd.DataFrame,
    signal_evaluation_df: pd.DataFrame,
    client: str,
    base_dir: Optional[Path] = None
) -> None:
    """
    Write Golden layer outputs for telemetry analysis.
    
    Generates two main output files:
    1. machine_status.parquet - Machine-level summary
    2. classified.parquet - Component-level detail
    
    Parameters
    ----------
    machine_df : pd.DataFrame
        Machine aggregation results
    component_df : pd.DataFrame
        Component aggregation results
    signal_evaluation_df : pd.DataFrame
        Signal evaluation results
    client : str
        Client identifier
    base_dir : Path, optional
        Base directory path
    
    Notes
    -----
    Outputs are written to data/telemetry/golden/{client}/
    Files are overwritten each run (idempotent).
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / 'data' / 'telemetry'
    
    # Output directory
    output_dir = base_dir / 'golden' / client
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Writing Golden layer outputs to {output_dir}")
    
    # === Write machine_status.parquet ===
    machine_output_path = output_dir / 'machine_status.parquet'
    
    # Select and order columns for machine status
    machine_output_cols = [
        'unit_id',
        'overall_status',
        'machine_score',
        'priority_score',
        'components_normal',
        'components_alerta',
        'components_anormal',
        'components_insufficient',
        'total_components',
        'evaluation_week',
        'evaluation_year',
        'baseline_version',
        'component_details'
    ]
    
    machine_output = machine_df[machine_output_cols].copy()
    machine_output.to_parquet(machine_output_path, index=False)
    
    logger.info(f"Wrote machine_status: {machine_output_path}")
    logger.info(f"  Records: {len(machine_output)}")
    
    # === Write classified.parquet ===
    classified_output_path = output_dir / 'classified.parquet'
    
    # Merge component and signal data for detailed output
    classified_output = component_df.copy()
    
    # Add signal details
    classified_output_cols = [
        'unit_id',
        'component',
        'component_status',
        'component_score',
        'triggering_signals',
        'signals_evaluation',
        'signal_coverage',
        'sample_count_avg',
        'criticality'
    ]
    
    classified_output = classified_output[classified_output_cols]
    classified_output.to_parquet(classified_output_path, index=False)
    
    logger.info(f"Wrote classified: {classified_output_path}")
    logger.info(f"  Records: {len(classified_output)}")
    
    # === Write signal_evaluations.parquet (detailed signal-level data) ===
    signal_output_path = output_dir / 'signal_evaluations.parquet'
    signal_evaluation_df.to_parquet(signal_output_path, index=False)
    
    logger.info(f"Wrote signal_evaluations: {signal_output_path}")
    logger.info(f"  Records: {len(signal_evaluation_df)}")
    
    logger.info("Golden layer outputs complete")


def write_baseline_metadata(
    baseline_df: pd.DataFrame,
    client: str,
    evaluation_week: int,
    evaluation_year: int,
    lookback_days: int,
    base_dir: Optional[Path] = None
) -> None:
    """
    Write metadata about baseline computation.
    
    Parameters
    ----------
    baseline_df : pd.DataFrame
        Baseline percentiles dataframe
    client : str
        Client identifier
    evaluation_week : int
        Evaluation week number
    evaluation_year : int
        Evaluation year
    lookback_days : int
        Number of lookback days used
    base_dir : Path, optional
        Base directory path
    """
    import json
    from datetime import datetime
    
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / 'data' / 'telemetry'
    
    baseline_dir = base_dir / 'golden' / client / 'baselines'
    baseline_dir.mkdir(parents=True, exist_ok=True)
    
    baseline_version = baseline_df['baseline_version'].iloc[0]
    
    metadata = {
        'baseline_version': baseline_version,
        'created_at': datetime.now().isoformat(),
        'evaluation_week': int(evaluation_week),
        'evaluation_year': int(evaluation_year),
        'lookback_days': int(lookback_days),
        'total_records': int(len(baseline_df)),
        'units': int(baseline_df['Unit'].nunique()),
        'signals': int(baseline_df['Signal'].nunique()),
        'state_specific_baselines': int((baseline_df['EstadoMaquina'] != 'All').sum()),
        'aggregate_baselines': int((baseline_df['EstadoMaquina'] == 'All').sum())
    }
    
    metadata_path = baseline_dir / 'baseline_metadata.json'
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Wrote baseline metadata: {metadata_path}")
