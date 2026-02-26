"""
Aggregation Module

Aggregates signal evaluations to component and machine levels.
"""

from typing import Dict, List, Optional
from pathlib import Path
import pandas as pd
import numpy as np

from src.utils.logger import logger


# Aggregation configuration
SEVERITY_MAP = {
    'Normal': 0.0,
    'Alerta': 0.3,
    'Anormal': 1.0,
    'InsufficientData': 0.0
}

COMPONENT_SCORE_THRESHOLD_NORMAL = 0.15
COMPONENT_SCORE_THRESHOLD_ANORMAL = 0.45
MIN_SIGNAL_COVERAGE = 0.5


def aggregate_to_components(
    signal_evaluation_df: pd.DataFrame,
    component_mapping: Dict,
    current_df: pd.DataFrame,
    evaluation_week: int,
    evaluation_year: int,
    baseline_version: str
) -> pd.DataFrame:
    """
    Aggregate signal evaluations to component-level status.
    
    Uses severity-weighted scoring approach:
    - Maps signal statuses to severity scores (non-linear)
    - Computes weighted average across signals
    - Applies thresholds to determine component status
    
    Parameters
    ----------
    signal_evaluation_df : pd.DataFrame
        Signal evaluation results from scoring module
    component_mapping : dict
        Component-to-signals mapping with criticality weights
    current_df : pd.DataFrame
        Current evaluation week data (for coverage calculation)
    evaluation_week : int
        Evaluation week number
    evaluation_year : int
        Evaluation year
    baseline_version : str
        Baseline version identifier (YYYYMMDD)
    
    Returns
    -------
    pd.DataFrame
        Component evaluation results with columns:
        - unit_id
        - component
        - component_score
        - component_status
        - triggering_signals
        - signals_evaluation (nested dict)
        - signal_coverage
        - sample_count_avg
        - criticality
    """
    logger.info("Aggregating signals to components")
    
    component_results = []
    units = signal_evaluation_df['unit_id'].unique()
    
    for unit in units:
        unit_signals = signal_evaluation_df[signal_evaluation_df['unit_id'] == unit]
        
        for component_name, config in component_mapping.items():
            component_signals = config.get('signals', [])
            criticality = config.get('criticality', 1)
            
            # Filter to signals in this component
            component_signal_evals = unit_signals[
                unit_signals['signal_name'].isin(component_signals)
            ]
            
            if component_signal_evals.empty:
                # No signals evaluated for this component
                continue
            
            # Calculate signal coverage
            total_signals = len(component_signals)
            evaluated_signals = len(component_signal_evals)
            signal_coverage = evaluated_signals / total_signals if total_signals > 0 else 0
            
            # Check minimum coverage
            if signal_coverage < MIN_SIGNAL_COVERAGE:
                logger.debug(f"  {unit} - {component_name}: Insufficient coverage ({signal_coverage:.1%})")
                # Still process but mark as limited coverage
            
            # Compute severity-weighted component score
            severity_scores = []
            weights = []
            
            for _, signal_row in component_signal_evals.iterrows():
                status = signal_row['signal_status']
                severity = SEVERITY_MAP.get(status, 0.0)
                
                # Weight based on data quality (sample count)
                sample_count = signal_row['sample_count']
                weight = 1.0 if sample_count > 0 else 0.0
                
                severity_scores.append(severity)
                weights.append(weight)
            
            # Weighted average
            if sum(weights) > 0:
                component_score = np.average(severity_scores, weights=weights)
            else:
                component_score = 0.0
            
            # Classify component status
            if signal_coverage < MIN_SIGNAL_COVERAGE:
                component_status = 'InsufficientData'
            elif component_score >= COMPONENT_SCORE_THRESHOLD_ANORMAL:
                component_status = 'Anormal'
            elif component_score >= COMPONENT_SCORE_THRESHOLD_NORMAL:
                component_status = 'Alerta'
            else:
                component_status = 'Normal'
            
            # Identify triggering signals (non-Normal)
            triggering_signals = component_signal_evals[
                component_signal_evals['signal_status'] != 'Normal'
            ]['signal_name'].tolist()
            
            # Build detailed signal evaluation dict
            signals_evaluation = {}
            for _, signal_row in component_signal_evals.iterrows():
                signal_name = signal_row['signal_name']
                signals_evaluation[signal_name] = {
                    'status': signal_row['signal_status'],
                    'window_score': signal_row['window_score_normalized'],
                    'anomaly_percentage': signal_row['anomaly_percentage'],
                    'sample_count': signal_row['sample_count']
                }
            
            # Average sample count
            sample_count_avg = component_signal_evals['sample_count'].mean()
            
            # Create component record
            component_record = {
                'unit_id': unit,
                'component': component_name,
                'evaluation_week': evaluation_week,
                'evaluation_year': evaluation_year,
                'component_score': component_score,
                'component_status': component_status,
                'triggering_signals': triggering_signals,
                'signals_evaluation': signals_evaluation,
                'signal_coverage': signal_coverage,
                'sample_count_avg': sample_count_avg,
                'criticality': criticality,
                'baseline_version': baseline_version
            }
            
            component_results.append(component_record)
    
    component_df = pd.DataFrame(component_results)
    
    logger.info(f"Component aggregation complete: {len(component_df)} component-unit combinations")
    
    if not component_df.empty:
        status_counts = component_df['component_status'].value_counts()
        logger.info(f"  Status distribution: {status_counts.to_dict()}")
    
    return component_df

criticality_mapping = {
    'High' : 1.0,
    'Medium' : 0.4,
    'Low' : 0.2
}

component_status_mapping = {
    'Normal': 0.0,
    'Alerta': 0.3,
    'Anormal': 1.0,
}

def get_expected_fleet(
    baseline_df: pd.DataFrame,
    previous_machine_status_path: Optional[Path] = None
) -> List[str]:
    """
    Get list of units that should be evaluated (fleet registry).
    
    Falls back in this order:
    1. Previous machine_status file (most recent week)
    2. Baseline units
    
    Parameters
    ----------
    baseline_df : pd.DataFrame
        Baseline percentiles dataframe
    previous_machine_status_path : Path, optional
        Path to previous machine_status file
    
    Returns
    -------
    list of str
        List of unit IDs that should be monitored
    """
    # Try loading from previous machine_status
    if previous_machine_status_path and previous_machine_status_path.exists():
        try:
            prev_status = pd.read_parquet(previous_machine_status_path)
            if not prev_status.empty:
                return sorted(prev_status['unit_id'].unique().tolist())
        except Exception as e:
            logger.warning(f"Could not load previous machine_status: {e}")
    
    # Fallback to baseline units
    if not baseline_df.empty:
        return sorted(baseline_df['Unit'].unique().tolist())
    
    return []


def aggregate_to_machines(
    component_df: pd.DataFrame,
    evaluation_week: int,
    evaluation_year: int,
    baseline_version: str,
    expected_units: Optional[List[str]] = None,
    component_mapping: Optional[Dict] = None
) -> pd.DataFrame:
    """
    Aggregate component evaluations to machine-level status.
    
    Machine status is determined by worst component status.
    Machine score is sum of weighted component scores.
    
    Handles edge case: Units with no data in evaluation week are marked as InsufficientData.
    
    Parameters
    ----------
    component_df : pd.DataFrame
        Component evaluation results
    evaluation_week : int
        Evaluation week number
    evaluation_year : int
        Evaluation year
    baseline_version : str
        Baseline version identifier (YYYYMMDD)
    expected_units : list of str, optional
        Fleet registry - units that should be monitored
    component_mapping : dict, optional
        Component configuration for creating placeholder records
    
    Returns
    -------
    pd.DataFrame
        Machine evaluation results with columns:
        - unit_id
        - overall_status
        - machine_score
        - priority_score
        - components_normal
        - components_alerta
        - components_anormal
        - total_components
        - evaluation_week
        - evaluation_year
        - baseline_version
        - component_details (nested list)
    """
    logger.info("Aggregating components to machines")
    
    machine_results = []
    
    # Units that have data
    units_with_data = component_df['unit_id'].unique() if not component_df.empty else []
    
    for unit in units_with_data:
        unit_components = component_df[component_df['unit_id'] == unit]
        
        # Count components by status
        status_counts = unit_components['component_status'].value_counts()
        components_normal = status_counts.get('Normal', 0)
        components_alerta = status_counts.get('Alerta', 0)
        components_anormal = status_counts.get('Anormal', 0)
        components_insufficient = status_counts.get('InsufficientData', 0)
        total_components = len(unit_components)
                
        # Compute machine score (weighted sum of component scores)
        machine_score = 0.0
        for _, comp_row in unit_components.iterrows():
            criticality = criticality_mapping.get(comp_row['criticality'], 1)
            component_score = component_status_mapping.get(comp_row['component_status'], 0)
            machine_score += criticality * component_score
        
        # Determine overall status (ponderation of component statuses)
        if machine_score > 1.4:
            overall_status = 'Anormal'
        elif machine_score > 0.6:
            overall_status = 'Alerta'
        else:
            overall_status = 'Normal'
        
        # Compute priority score for fleet ranking
        priority_score = (
            100 * components_anormal + 
            10 * components_alerta + 
            machine_score
        )
        
        # Build component details list
        component_details = []
        for _, comp_row in unit_components.iterrows():
            component_detail = {
                'component': comp_row['component'],
                'status': comp_row['component_status'],
                'score': comp_row['component_score'],
                'triggering_signals': comp_row['triggering_signals'],
                'signal_coverage': comp_row['signal_coverage']
            }
            component_details.append(component_detail)
        
        # Create machine record
        machine_record = {
            'unit_id': unit,
            'overall_status': overall_status,
            'machine_score': machine_score,
            'priority_score': priority_score,
            'components_normal': components_normal,
            'components_alerta': components_alerta,
            'components_anormal': components_anormal,
            'components_insufficient': components_insufficient,
            'total_components': total_components,
            'evaluation_week': evaluation_week,
            'evaluation_year': evaluation_year,
            'baseline_version': baseline_version,
            'component_details': component_details
        }
        
        machine_results.append(machine_record)
    
    # Handle missing units (edge case: no data for this evaluation week)
    if expected_units:
        missing_units = set(expected_units) - set(units_with_data)
        
        if missing_units:
            logger.warning(f"Found {len(missing_units)} units with no data: {sorted(missing_units)}")
            
            for unit in missing_units:
                # Determine expected components from mapping
                expected_component_count = len(component_mapping) if component_mapping else 0
                
                # Create placeholder record for missing unit
                missing_unit_record = {
                    'unit_id': unit,
                    'overall_status': 'InsufficientData',
                    'machine_score': 0.0,
                    'priority_score': 0.0,
                    'components_normal': 0,
                    'components_alerta': 0,
                    'components_anormal': 0,
                    'components_insufficient': expected_component_count,
                    'total_components': expected_component_count,
                    'evaluation_week': evaluation_week,
                    'evaluation_year': evaluation_year,
                    'baseline_version': baseline_version,
                    'component_details': []
                }
                
                machine_results.append(missing_unit_record)
    
    machine_df = pd.DataFrame(machine_results)
    
    logger.info(f"Machine aggregation complete: {len(machine_df)} machines evaluated")
    logger.info(f"  Units with data: {len(units_with_data)}")
    if expected_units:
        logger.info(f"  Units without data: {len(expected_units) - len(units_with_data)}")
    
    if not machine_df.empty:
        status_counts = machine_df['overall_status'].value_counts()
        logger.info(f"  Overall status distribution: {status_counts.to_dict()}")
        logger.info(f"  Normal: {status_counts.get('Normal', 0)}")
        logger.info(f"  Alerta: {status_counts.get('Alerta', 0)}")
        logger.info(f"  Anormal: {status_counts.get('Anormal', 0)}")
        logger.info(f"  InsufficientData: {status_counts.get('InsufficientData', 0)}")
    
    return machine_df
