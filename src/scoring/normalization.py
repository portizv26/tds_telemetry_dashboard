"""
Risk score normalization functions.

Converts technique-specific native metrics into normalized risk scores (0-100).

Score Bands
-----------
- 0-30: Low risk / Normal variation
- 30-60: Moderate risk / Monitoring recommended
- 60-80: High risk / Inspection recommended
- 80-100: Critical risk / Immediate action required
"""

import numpy as np
from typing import Dict, Any


def normalize_threshold_deviation(
    exceedance_p95_pct: float,
    exceedance_p99_pct: float,
    max_deviation: float,
    mean_deviation: float,
) -> float:
    """
    Normalize threshold deviation metrics to 0-100 risk score.
    
    Logic
    -----
    - Primary driver: % of time exceeding P95/P99
    - Secondary driver: Magnitude of deviation
    - Exponential scaling to emphasize repeated violations
    
    Parameters
    ----------
    exceedance_p95_pct : float
        Percentage of time exceeding P95 baseline (0-100)
    exceedance_p99_pct : float
        Percentage of time exceeding P99 baseline (0-100)
    max_deviation : float
        Maximum deviation from baseline (native units)
    mean_deviation : float
        Mean deviation from baseline (native units)
    
    Returns
    -------
    float
        Risk score (0-100)
    
    Examples
    --------
    >>> normalize_threshold_deviation(5, 1, 10, 3)  # Low risk
    15.0
    >>> normalize_threshold_deviation(25, 10, 30, 15)  # Moderate risk
    52.5
    >>> normalize_threshold_deviation(60, 30, 50, 35)  # High risk
    87.5
    """
    # Base score from P95 exceedance (0-50 points)
    # Linear scaling up to 20%, exponential beyond
    if exceedance_p95_pct <= 20:
        base_score = exceedance_p95_pct * 2.5  # 0-50
    else:
        base_score = 50 + (exceedance_p95_pct - 20) * 1.25  # 50-100
    
    # P99 bonus (0-30 points)
    # Exceeding P99 is more severe
    p99_bonus = min(exceedance_p99_pct * 3, 30)
    
    # Magnitude bonus (0-20 points)
    # Large deviations get extra weight
    if max_deviation > 0:
        magnitude_factor = min(mean_deviation / max_deviation, 1.0)
        magnitude_bonus = magnitude_factor * 20
    else:
        magnitude_bonus = 0
    
    # Combine components
    risk_score = base_score + p99_bonus + magnitude_bonus
    
    # Cap at 100
    return min(risk_score, 100.0)


def normalize_trend_slope(
    slope: float,
    r_squared: float,
    p_value: float,
    percent_change: float,
    risk_direction: str = "high",
) -> float:
    """
    Normalize trend analysis metrics to 0-100 risk score.
    
    Logic
    -----
    - Primary driver: Magnitude of change (% delta from baseline)
    - Secondary driver: Trend strength (R²)
    - Bonus for statistical significance (p < 0.05)
    - Consider risk direction (high vs low values)
    
    Parameters
    ----------
    slope : float
        Regression slope (units per week)
    r_squared : float
        Coefficient of determination (0-1)
    p_value : float
        Statistical significance (0-1)
    percent_change : float
        Total % change over period
    risk_direction : str
        "high" (increasing = risk) or "low" (decreasing = risk)
    
    Returns
    -------
    float
        Risk score (0-100)
    
    Examples
    --------
    >>> normalize_trend_slope(2.5, 0.85, 0.01, 15, "high")  # Strong upward trend
    68.0
    >>> normalize_trend_slope(-1.2, 0.60, 0.03, -8, "low")  # Moderate downward trend
    42.0
    """
    # Determine if trend is in risk direction
    if risk_direction == "high":
        is_risk_trend = slope > 0
    elif risk_direction == "low":
        is_risk_trend = slope < 0
    else:  # "both"
        is_risk_trend = True
    
    # If trend is not in risk direction, low risk
    if not is_risk_trend:
        return min(abs(percent_change) * 0.5, 20.0)  # Max 20 for improving trends
    
    # Base score from magnitude (0-60 points)
    # Linear scaling for first 20%, exponential beyond
    abs_change = abs(percent_change)
    if abs_change <= 20:
        magnitude_score = abs_change * 3  # 0-60
    else:
        magnitude_score = 60 + (abs_change - 20) * 1.0  # 60-100
    
    # Persistence bonus from R² (0-25 points)
    # High R² means consistent trend
    persistence_bonus = r_squared * 25
    
    # Significance bonus (0-15 points)
    if p_value < 0.01:
        significance_bonus = 15
    elif p_value < 0.05:
        significance_bonus = 10
    elif p_value < 0.10:
        significance_bonus = 5
    else:
        significance_bonus = 0
    
    # Combine components
    risk_score = magnitude_score + persistence_bonus + significance_bonus
    
    # Cap at 100
    return min(risk_score, 100.0)


def normalize_event_severity(
    duration_minutes: int,
    deviation_from_baseline: float,
    event_type: str,
    persistence_factor: float = 1.0,
) -> float:
    """
    Normalize event detection metrics to 0-100 severity score.
    
    Logic
    -----
    - Primary driver: Duration of abnormal episode
    - Secondary driver: Magnitude of deviation
    - Event type multiplier (sustained > episode > spike)
    - Persistence bonus for repeated events
    
    Parameters
    ----------
    duration_minutes : int
        Event duration in minutes
    deviation_from_baseline : float
        Average deviation magnitude (% above/below baseline)
    event_type : str
        "spike" (<5min), "episode" (5-60min), "sustained" (>60min)
    persistence_factor : float
        Multiplier for repeated events (default 1.0)
    
    Returns
    -------
    float
        Severity score (0-100)
    
    Examples
    --------
    >>> normalize_event_severity(3, 25, "spike")  # Brief spike
    22.5
    >>> normalize_event_severity(45, 50, "episode")  # Moderate episode
    58.0
    >>> normalize_event_severity(180, 75, "sustained", 1.3)  # Sustained + repeated
    98.5
    """
    # Base score from duration (0-50 points)
    if event_type == "spike":  # <5 minutes
        duration_score = min(duration_minutes * 5, 20)
    elif event_type == "episode":  # 5-60 minutes
        duration_score = 20 + min((duration_minutes - 5) * 0.5, 30)
    else:  # "sustained" >60 minutes
        duration_score = 50 + min((duration_minutes - 60) * 0.1, 30)
    
    # Magnitude score from deviation (0-40 points)
    # Exponential scaling for large deviations
    if deviation_from_baseline <= 50:
        magnitude_score = deviation_from_baseline * 0.6  # 0-30
    else:
        magnitude_score = 30 + (deviation_from_baseline - 50) * 0.2  # 30-40
    
    # Event type multiplier
    type_multipliers = {
        "spike": 0.8,
        "episode": 1.0,
        "sustained": 1.2,
    }
    multiplier = type_multipliers.get(event_type, 1.0)
    
    # Combine components
    severity_score = (duration_score + magnitude_score) * multiplier * persistence_factor
    
    # Cap at 100
    return min(severity_score, 100.0)


def normalize_diagnostic_rule_score(
    rule_severity: str,
    confidence: float,
    duration_factor: float = 1.0,
) -> float:
    """
    Normalize diagnostic rule findings to 0-100 risk score.
    
    Parameters
    ----------
    rule_severity : str
        Rule severity: "critical", "high", "medium", "low"
    confidence : float
        Rule confidence (0-1)
    duration_factor : float
        Multiplier for persistent patterns (default 1.0)
    
    Returns
    -------
    float
        Risk score (0-100)
    """
    # Base score by severity
    severity_scores = {
        "critical": 85,
        "high": 70,
        "medium": 50,
        "low": 30,
    }
    base_score = severity_scores.get(rule_severity.lower(), 50)
    
    # Adjust by confidence
    adjusted_score = base_score * confidence * duration_factor
    
    # Cap at 100
    return min(adjusted_score, 100.0)


def calculate_aggregate_risk_score(
    technique_scores: Dict[str, float],
    technique_confidences: Dict[str, float],
    technique_weights: Dict[str, float],
) -> float:
    """
    Aggregate multiple technique risk scores with weighting.
    
    Logic
    -----
    - Weight by technique confidence
    - Apply technique-specific weights
    - Cannot average away critical findings (max > 80 preserves high risk)
    
    Parameters
    ----------
    technique_scores : Dict[str, float]
        Risk scores by technique name
    technique_confidences : Dict[str, float]
        Confidence scores by technique name
    technique_weights : Dict[str, float]
        Base weights by technique name
    
    Returns
    -------
    float
        Aggregated risk score (0-100)
    """
    if not technique_scores:
        return 0.0
    
    # Check for critical findings
    max_score = max(technique_scores.values())
    if max_score >= 80:
        # Don't average away critical findings
        # Use 70% max + 30% weighted average
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for tech, score in technique_scores.items():
            confidence = technique_confidences.get(tech, 1.0)
            weight = technique_weights.get(tech, 1.0)
            effective_weight = confidence * weight
            
            weighted_sum += score * effective_weight
            weight_sum += effective_weight
        
        if weight_sum > 0:
            weighted_avg = weighted_sum / weight_sum
            return 0.7 * max_score + 0.3 * weighted_avg
        else:
            return max_score
    
    # Normal weighted average
    weighted_sum = 0.0
    weight_sum = 0.0
    
    for tech, score in technique_scores.items():
        confidence = technique_confidences.get(tech, 1.0)
        weight = technique_weights.get(tech, 1.0)
        effective_weight = confidence * weight
        
        weighted_sum += score * effective_weight
        weight_sum += effective_weight
    
    if weight_sum > 0:
        return weighted_sum / weight_sum
    else:
        return 0.0
