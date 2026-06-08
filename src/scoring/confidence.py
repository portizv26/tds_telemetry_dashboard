"""
Confidence score calculation for technique results.

Confidence reflects the reliability of the assessment based on data quality,
baseline quality, sample size, and state matching.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


def calculate_confidence_score(
    data_df: pd.DataFrame,
    expected_samples: int,
    baseline: Optional[Dict[str, Any]] = None,
    state_matched: bool = True,
) -> float:
    """
    Calculate confidence score (0-100) based on data quality factors.
    
    Factors
    -------
    1. Coverage: Actual samples / Expected samples
    2. Baseline quality: Sample count and quality score from baseline
    3. State matching: Whether operational state matches baseline
    4. Data completeness: Missing value ratio
    
    Parameters
    ----------
    data_df : pd.DataFrame
        Analysis window data
    expected_samples : int
        Expected number of samples (based on time window)
    baseline : Optional[Dict[str, Any]]
        Baseline statistics with 'sample_count' and 'quality_score'
    state_matched : bool
        Whether operational state matches baseline (default True)
    
    Returns
    -------
    float
        Confidence score (0-100)
        - <50: InsufficientData
        - 50-70: Low confidence
        - 70-85: Medium confidence
        - 85-100: High confidence
    
    Examples
    --------
    >>> data = pd.DataFrame({'value': [1, 2, 3, 4, 5] * 200})
    >>> calculate_confidence_score(data, 1000, {'sample_count': 5000, 'quality_score': 0.95})
    95.0
    
    >>> data = pd.DataFrame({'value': [1, 2, None, 4, None] * 100})
    >>> calculate_confidence_score(data, 1000)
    42.0
    """
    # Initialize confidence
    confidence = 100.0
    
    # Factor 1: Coverage penalty
    actual_samples = len(data_df)
    coverage_ratio = actual_samples / expected_samples if expected_samples > 0 else 0
    
    if coverage_ratio < 0.5:  # <50% coverage
        confidence *= 0.4  # Severe penalty
    elif coverage_ratio < 0.7:  # 50-70% coverage
        confidence *= 0.6
    elif coverage_ratio < 0.8:  # 70-80% coverage
        confidence *= 0.8
    elif coverage_ratio < 0.9:  # 80-90% coverage
        confidence *= 0.9
    # else: >=90% coverage, no penalty
    
    # Factor 2: Data completeness
    if actual_samples > 0:
        # Check for missing values in numeric columns
        numeric_cols = data_df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            missing_ratio = data_df[numeric_cols].isnull().sum().sum() / (len(data_df) * len(numeric_cols))
            
            if missing_ratio > 0.3:  # >30% missing
                confidence *= 0.5
            elif missing_ratio > 0.2:  # >20% missing
                confidence *= 0.7
            elif missing_ratio > 0.1:  # >10% missing
                confidence *= 0.85
    
    # Factor 3: Baseline quality
    if baseline is not None:
        baseline_sample_count = baseline.get('sample_count', 0)
        baseline_quality = baseline.get('quality_score', 0.5)
        
        # Penalty for small baseline
        if baseline_sample_count < 500:
            confidence *= 0.5
        elif baseline_sample_count < 1000:
            confidence *= 0.7
        elif baseline_sample_count < 2000:
            confidence *= 0.85
        
        # Apply baseline quality factor
        confidence *= baseline_quality
    
    # Factor 4: State matching penalty
    if not state_matched:
        confidence *= 0.7  # Comparing to wrong state reduces confidence
    
    # Factor 5: Sample size adequacy
    if actual_samples < 10:
        confidence *= 0.3  # Too few samples
    elif actual_samples < 30:
        confidence *= 0.6
    elif actual_samples < 100:
        confidence *= 0.8
    
    # Cap at 100
    return min(confidence, 100.0)


def calculate_trend_confidence(
    valid_weeks: int,
    required_weeks: int,
    r_squared: float,
    p_value: float,
) -> float:
    """
    Calculate confidence score for trend analysis.
    
    Parameters
    ----------
    valid_weeks : int
        Number of weeks with sufficient data
    required_weeks : int
        Minimum required weeks (4, 8, or 12)
    r_squared : float
        Coefficient of determination (0-1)
    p_value : float
        Statistical significance (0-1)
    
    Returns
    -------
    float
        Confidence score (0-100)
    """
    confidence = 100.0
    
    # Weeks coverage penalty
    weeks_ratio = valid_weeks / required_weeks if required_weeks > 0 else 0
    if weeks_ratio < 0.75:  # <75% of required weeks
        confidence *= 0.5
    elif weeks_ratio < 0.9:  # 75-90% of required weeks
        confidence *= 0.75
    
    # R² penalty (trend strength)
    if r_squared < 0.3:  # Weak trend
        confidence *= 0.5
    elif r_squared < 0.5:
        confidence *= 0.7
    elif r_squared < 0.7:
        confidence *= 0.85
    
    # p-value penalty (significance)
    if p_value >= 0.10:  # Not significant
        confidence *= 0.6
    elif p_value >= 0.05:
        confidence *= 0.8
    
    return min(confidence, 100.0)


def calculate_event_confidence(
    event_duration_minutes: int,
    baseline_quality: float,
    data_coverage: float,
) -> float:
    """
    Calculate confidence score for event detection.
    
    Parameters
    ----------
    event_duration_minutes : int
        Duration of detected event
    baseline_quality : float
        Quality of baseline (0-1)
    data_coverage : float
        Data coverage during event period (0-1)
    
    Returns
    -------
    float
        Confidence score (0-100)
    """
    confidence = 100.0
    
    # Duration factor (longer events more reliable)
    if event_duration_minutes < 3:
        confidence *= 0.6  # Very brief, could be noise
    elif event_duration_minutes < 5:
        confidence *= 0.8
    
    # Baseline quality factor
    confidence *= baseline_quality
    
    # Data coverage factor
    if data_coverage < 0.7:
        confidence *= 0.6
    elif data_coverage < 0.9:
        confidence *= 0.85
    
    return min(confidence, 100.0)
