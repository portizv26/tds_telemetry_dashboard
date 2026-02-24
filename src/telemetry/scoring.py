"""
Signal Scoring Module

Implements severity-weighted percentile window scoring for anomaly detection.
"""

from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

from src.utils.logger import logger


# Scoring thresholds
WINDOW_SCORE_THRESHOLD_ALERT = 0.35
WINDOW_SCORE_THRESHOLD_ANORMAL = 0.9


def score_single_reading(value: float, percentiles: Dict[str, float]) -> int:
    """
    Score a single sensor reading against baseline percentiles.
    
    Parameters
    ----------
    value : float
        Sensor reading value
    percentiles : dict
        Baseline percentiles with keys 'P2', 'P5', 'P95', 'P98'
    
    Returns
    -------
    int
        Severity score:
        - 0: Normal (within P5-P95 range)
        - 1: Alert (within P2-P5 or P95-P98 range)
        - 3: Alarm (outside P2-P98 range)
    """
    if pd.isna(value):
        return np.nan
    
    p2, p5, p95, p98 = percentiles['P2'], percentiles['P5'], percentiles['P95'], percentiles['P98']
    
    # Normal range
    if p5 <= value <= p95:
        return 0
    
    # Alert range
    if (p2 <= value < p5) or (p95 < value <= p98):
        return 1
    
    # Alarm range
    if value < p2 or value > p98:
        return 3
    
    return 0


def compute_window_score(values: pd.Series, percentiles: Dict[str, float]) -> Tuple[float, int, int]:
    """
    Compute window-normalized anomaly score for a signal.
    
    Parameters
    ----------
    values : pd.Series
        Series of sensor readings for the evaluation window
    percentiles : dict
        Baseline percentiles with keys 'P2', 'P5', 'P95', 'P98'
    
    Returns
    -------
    tuple of (float, int, int)
        - window_score_normalized: Normalized anomaly score
        - sample_count: Number of valid (non-NaN) samples
        - anomaly_count: Number of samples with score > 0
    """
    # Score each reading
    scores = values.apply(lambda x: score_single_reading(x, percentiles))
    
    # Remove NaN scores
    valid_scores = scores.dropna()
    
    if len(valid_scores) == 0:
        return np.nan, 0, 0
    
    # Compute normalized window score
    window_score_normalized = valid_scores.sum() / len(valid_scores)
    sample_count = len(valid_scores)
    anomaly_count = (valid_scores > 0).sum()
    
    return window_score_normalized, sample_count, anomaly_count


def classify_signal_status(window_score: float) -> str:
    """
    Classify signal status based on window score.
    
    Parameters
    ----------
    window_score : float
        Window-normalized anomaly score
    
    Returns
    -------
    str
        Signal status: 'Normal', 'Alerta', or 'Anormal'
    """
    if pd.isna(window_score):
        return 'InsufficientData'
    
    if window_score >= WINDOW_SCORE_THRESHOLD_ANORMAL:
        return 'Anormal'
    elif window_score >= WINDOW_SCORE_THRESHOLD_ALERT:
        return 'Alerta'
    else:
        return 'Normal'


def evaluate_signals(
    current_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    signal_cols: List[str],
    component_mapping: Dict
) -> pd.DataFrame:
    """
    Evaluate all signals for all units in the current evaluation window.
    
    Parameters
    ----------
    current_df : pd.DataFrame
        Current evaluation week telemetry data
    baseline_df : pd.DataFrame
        Baseline percentiles dataframe
    signal_cols : list of str
        List of signal column names
    component_mapping : dict
        Component-to-signals mapping
    
    Returns
    -------
    pd.DataFrame
        Signal evaluation results with columns:
        - unit_id
        - signal_name
        - component
        - window_score_normalized
        - signal_status
        - sample_count
        - anomaly_count
        - anomaly_percentage
        - max_score
        - p2, p5, p95, p98 (baseline values used)
    """
    logger.info("Starting signal evaluation")
    logger.info(f"  Units to evaluate: {current_df['Unit'].nunique()}")
    logger.info(f"  Signals to evaluate: {len(signal_cols)}")
    
    # Create signal-to-component reverse mapping
    signal_to_component = {}
    for component, config in component_mapping.items():
        for signal in config.get('signals', []):
            signal_to_component[signal] = component
    
    evaluations = []
    units = current_df['Unit'].unique()
    
    for unit in units:
        unit_df = current_df[current_df['Unit'] == unit]
        
        for signal in signal_cols:
            if signal not in unit_df.columns:
                continue
            
            # Get component for this signal
            component = signal_to_component.get(signal, 'Unknown')
            
            # Get baseline for this unit-signal combination
            # First try state-specific baseline matching current state
            baseline_records = baseline_df[
                (baseline_df['Unit'] == unit) & 
                (baseline_df['Signal'] == signal)
            ]
            
            if baseline_records.empty:
                # No baseline for this combination - skip
                logger.debug(f"  No baseline for {unit} - {signal}")
                continue
            
            # Use state-specific baseline if available, otherwise use 'All'
            if 'EstadoMaquina' in unit_df.columns:
                # For simplicity, use aggregate baseline or most common state
                # In production, you'd match state per reading
                baseline_record = baseline_records[
                    baseline_records['EstadoMaquina'] == 'All'
                ]
                
                if baseline_record.empty:
                    # Use first available state baseline
                    baseline_record = baseline_records.iloc[[0]]
            else:
                baseline_record = baseline_records.iloc[[0]]
            
            if baseline_record.empty:
                continue
            
            # Extract percentiles
            percentiles = {
                'P2': baseline_record['P2'].values[0],
                'P5': baseline_record['P5'].values[0],
                'P95': baseline_record['P95'].values[0],
                'P98': baseline_record['P98'].values[0]
            }
            
            # Compute window score
            values = unit_df[signal]
            window_score, sample_count, anomaly_count = compute_window_score(values, percentiles)
            
            # Classify status
            signal_status = classify_signal_status(window_score)
            
            # Calculate anomaly percentage
            anomaly_percentage = (anomaly_count / sample_count * 100) if sample_count > 0 else 0
            
            # Get max individual score
            scores = values.apply(lambda x: score_single_reading(x, percentiles))
            max_score = scores.max() if not scores.empty else np.nan
            
            # Create evaluation record
            evaluation_record = {
                'unit_id': unit,
                'signal_name': signal,
                'component': component,
                'window_score_normalized': window_score,
                'signal_status': signal_status,
                'sample_count': sample_count,
                'anomaly_count': anomaly_count,
                'anomaly_percentage': anomaly_percentage,
                'max_score': max_score,
                'p2': percentiles['P2'],
                'p5': percentiles['P5'],
                'p95': percentiles['P95'],
                'p98': percentiles['P98']
            }
            
            evaluations.append(evaluation_record)
    
    evaluation_df = pd.DataFrame(evaluations)
    
    logger.info(f"Signal evaluation complete: {len(evaluation_df)} signal-unit combinations")
    
    if not evaluation_df.empty:
        status_counts = evaluation_df['signal_status'].value_counts()
        logger.info(f"  Status distribution: {status_counts.to_dict()}")
    
    return evaluation_df
