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
    client : str
        Client identifier
    base_dir : Path, optional
        Base directory path
    
    Notes
    -----
    Outputs are written to data/telemetry/golden/{client}/
    Files are overwritten each run (idempotent).
    Signal-level details are embedded in classified.parquet JSON fields.
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / 'data' / 'telemetry'
    
    # Output directory
    output_dir = base_dir / 'golden' / client
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Writing Golden layer outputs to {output_dir}")
    
    # === Write machine_status.parquet (APPEND MODE for historical time-series) ===
    machine_output_path = output_dir / 'machine_status.parquet'
    
    # Select and order columns for machine status
    machine_output_cols = [
        'unit_id',
        'evaluation_week',
        'evaluation_year',
        'overall_status',
        'machine_score',
        'priority_score',
        'components_normal',
        'components_alerta',
        'components_anormal',
        'components_insufficient',
        'total_components',
        'baseline_version',
        'component_details'
    ]
    
    machine_output = machine_df[machine_output_cols].copy()
    
    # Load existing historical data if file exists
    if machine_output_path.exists():
        logger.info(f"Loading existing machine_status history from {machine_output_path}")
        existing_machine_status = pd.read_parquet(machine_output_path)
        
        # Append new records
        combined_machine_status = pd.concat([existing_machine_status, machine_output], ignore_index=True)
        
        # Deduplicate: Keep latest evaluation for same (unit_id, week, year)
        combined_machine_status = combined_machine_status.drop_duplicates(
            subset=['unit_id', 'evaluation_week', 'evaluation_year'],
            keep='last'
        )
        
        # Sort by unit, year, week for efficient querying
        combined_machine_status = combined_machine_status.sort_values(
            ['unit_id', 'evaluation_year', 'evaluation_week']
        ).reset_index(drop=True)
        
        logger.info(f"  Previous records: {len(existing_machine_status)}")
        logger.info(f"  New records: {len(machine_output)}")
        logger.info(f"  Total after deduplication: {len(combined_machine_status)}")
        
        machine_output = combined_machine_status
    else:
        logger.info("Creating new machine_status history file")
    
    # Write to parquet
    machine_output.to_parquet(machine_output_path, index=False)
    
    logger.info(f"Wrote machine_status: {machine_output_path}")
    logger.info(f"  Total historical records: {len(machine_output)}")
    
    # === Write classified.parquet (APPEND MODE for historical time-series) ===
    classified_output_path = output_dir / 'classified.parquet'
    
    # Prepare new records
    classified_output = component_df.copy()
    
    # Select and order columns for classified
    classified_output_cols = [
        'unit_id',
        'component',
        'evaluation_week',
        'evaluation_year',
        'component_status',
        'component_score',
        'triggering_signals',
        'signals_evaluation',
        'signal_coverage',
        'sample_count_avg',
        'criticality',
        'baseline_version'
    ]
    
    classified_output = classified_output[classified_output_cols]
    
    # Load existing historical data if file exists
    if classified_output_path.exists():
        logger.info(f"Loading existing classified history from {classified_output_path}")
        existing_classified = pd.read_parquet(classified_output_path)
        
        # Append new records
        combined_classified = pd.concat([existing_classified, classified_output], ignore_index=True)
        
        # Deduplicate: Keep latest evaluation for same (unit_id, component, week, year)
        combined_classified = combined_classified.drop_duplicates(
            subset=['unit_id', 'component', 'evaluation_week', 'evaluation_year'],
            keep='last'
        )
        
        # Sort by unit, component, year, week for efficient querying
        combined_classified = combined_classified.sort_values(
            ['unit_id', 'component', 'evaluation_year', 'evaluation_week']
        ).reset_index(drop=True)
        
        logger.info(f"  Previous records: {len(existing_classified)}")
        logger.info(f"  New records: {len(classified_output)}")
        logger.info(f"  Total after deduplication: {len(combined_classified)}")
        
        classified_output = combined_classified
    else:
        logger.info("Creating new classified history file")
    
    # Write to parquet
    classified_output.to_parquet(classified_output_path, index=False)
    
    logger.info(f"Wrote classified: {classified_output_path}")
    logger.info(f"  Total historical records: {len(classified_output)}")
    
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
