# Telemetry Analysis Techniques - Technical Documentation

**Author**: Patricio Ortiz  
**Last Updated**: June 2026  
**Version**: 1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Data Pipeline Architecture](#data-pipeline-architecture)
3. [Analysis Techniques](#analysis-techniques)
   - [1. Deviation Analysis](#1-deviation-analysis)
   - [2. Event Analysis](#2-event-analysis)
   - [3. Trend Analysis](#3-trend-analysis)
   - [4. Distribution Shift Analysis](#4-distribution-shift-analysis)
   - [5. Anomaly Detection (LSTM Autoencoder)](#5-anomaly-detection-lstm-autoencoder)
4. [Implementation Best Practices](#implementation-best-practices)
5. [Performance Considerations](#performance-considerations)
6. [Troubleshooting Guide](#troubleshooting-guide)

---

## Overview

This document describes the end-to-end telemetry analysis pipeline designed to detect equipment anomalies, degradation patterns, and operational issues across mining equipment fleets. The pipeline processes raw telemetry signals and applies multiple complementary analysis techniques to provide comprehensive equipment health insights.

### Input Data Requirements

The pipeline requires three data sources:

1. **Telemetry Data** (`../data/telemetry/silver/{client}/Telemetry_Wide_With_States/`)
   - Format: Parquet files with naming convention `{ww-yyyy}.parquet`
   - Structure: `unitId | timeStart | state | feature_1 | ... | feature_n`
   - Temporal Resolution: 1-minute intervals
   
2. **Signal Metadata** (`../data/telemetry/config/{client}/signal_registry.yaml`)
   - Defines feature characteristics (risk direction, system grouping, threshold computation flags)
   
3. **Equipment Metadata** (`../data/telemetry/config/{client}/equipment_registry.yaml`)
   - Defines equipment specifications (model, silencer status, unit identifiers)

### Column Name Configuration

Standard column names used throughout the pipeline:

```python
UNIT_COLNAME = 'Unit'      # Equipment identifier
STATE_COLNAME = 'Estado'   # Operational state (Operating, Idle, etc.)
TIME_COLNAME = 'Fecha'     # Timestamp
```

---

## Data Pipeline Architecture

### Phase 1: Data Loading and Preprocessing

```python
import pandas as pd
import numpy as np
import yaml

def read_telemetry_data(file_path: str) -> pd.DataFrame:
    """Load telemetry data from parquet file."""
    try:
        df = pd.read_parquet(file_path)
        return df
    except Exception as e:
        print(f"Error reading telemetry data: {e}")
        return None

def read_yaml(file_path: str) -> dict:
    """Load YAML metadata files."""
    try:
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)
        return data
    except Exception as e:
        print(f"Error reading YAML file: {e}")
        return None
```

**Operational Considerations:**
- Validate data completeness before processing (check for missing columns)
- Monitor memory usage when loading large parquet files
- Implement data validation checks (timestamp ordering, expected column presence)

### Phase 2: Model Specification Computation

Equipment analysis requires grouping by model specifications to ensure valid statistical comparisons.

```python
def compute_model_specification(
    df_in: pd.DataFrame,
    equipment_metadata: dict,
    colname: str = UNIT_COLNAME
) -> pd.DataFrame:
    """Map units to model specifications (model + silencer configuration)."""
    df_out = df_in.copy()
    
    # Create mapping: unit_identifier -> model_specification
    unit_to_model = {}
    for equipment in equipment_metadata['equipments']:
        model_spec = f'{equipment["model"]}_with_silencer' if equipment.get('has_silencer', False) else equipment['model']
        unit_to_model[equipment['name']] = model_spec
    
    # Apply mapping
    df_out.loc[:, 'model_specification'] = df_out[colname].map(unit_to_model)
    df_out = df_out.dropna(subset=['model_specification'])
    
    return df_out
```

**Technical Considerations:**
- Model specifications must account for hardware variations (silencer presence affects thermal behavior)
- Unmapped units are dropped automatically
- Ensure equipment_metadata is up-to-date with current fleet composition

---

## Analysis Techniques

## 1. Deviation Analysis

### Purpose

Identify when telemetry features exceed statistical thresholds derived from historical normal operation, categorizing severity into **Normal**, **Alert**, **Anormal**, and **Critical** levels.

### Methodology

**Statistical Approach:**
- Compute percentiles (P1, P2, P5, P10, P25, P50, P75, P90, P95, P98, P99) for each:
  - `model_specification` (equipment variant)
  - `state` (operational mode: Operating, Idle, Hauling, etc.)
  - `feature` (signal with `threshold_compute: true` in metadata)

**Risk Direction Logic:**

| Risk Direction | Threshold Mapping | Interpretation |
|----------------|-------------------|----------------|
| `high` | Alert: P95, Anormal: P98, Critical: P99 | Higher values are worse (e.g., temperature, pressure) |
| `low` | Alert: P5, Anormal: P2, Critical: P1 | Lower values are worse (e.g., oil pressure, battery voltage) |
| `both` | Alert: [P5, P95], Anormal: [P2, P98], Critical: [P1, P99] | Values outside range are worse (e.g., RPM deviation) |

### Implementation

#### Step 1: Compute Historical Limits

```python
def compute_limits(
    df_in: pd.DataFrame,
    telemetry_metadata: dict,
    equipment_metadata: dict
) -> dict:
    """
    Compute percentile-based limits for threshold computation.
    
    Returns:
        dict: Format {model_specification: {feature: {state: {percentiles}}}}
    """
    limits = {}
    
    # Get valid (model, state) pairs
    valid_pairs = df_in[['model_specification', 'Estado']].drop_duplicates().dropna(how='any')
    valid_pairs = [tuple(x) for x in valid_pairs.to_numpy() if 'nan' not in x]
    
    # Get features requiring threshold computation
    features_to_compute = [
        signal['name'] for signal in telemetry_metadata['signals'] 
        if signal.get('threshold_compute', False)
    ]
    
    for model_specification, state in valid_pairs:
        if model_specification not in limits:
            limits[model_specification] = {}
        
        for feature in features_to_compute:
            feature_values = df_in[
                (df_in['model_specification'] == model_specification) & 
                (df_in['Estado'] == state)
            ][feature].dropna()
            
            # Require at least 10 unique values for reliable percentiles
            if feature_values.unique().size > 9:
                if feature not in limits[model_specification]:
                    limits[model_specification][feature] = {}
                if state not in limits[model_specification][feature]:
                    limits[model_specification][feature][state] = {}
                
                p = np.percentile(feature_values, [1, 2, 5, 10, 25, 50, 75, 90, 95, 98, 99])
                limits[model_specification][feature][state] = {
                    'P1': np.round(p[0], 1), 'P2': np.round(p[1], 1),
                    'P5': np.round(p[2], 1), 'P10': np.round(p[3], 1),
                    'P25': np.round(p[4], 1), 'P50': np.round(p[5], 1),
                    'P75': np.round(p[6], 1), 'P90': np.round(p[7], 1),
                    'P95': np.round(p[8], 1), 'P98': np.round(p[9], 1),
                    'P99': np.round(p[10], 1)
                }
    
    return limits
```

**Statistical Considerations:**
- **Minimum Data Requirement**: 10 unique values per (model, state, feature) combination
- **Baseline Period**: Use ≥12 weeks of historical data for stable percentile estimates
- **State Separation**: Critical to prevent confounding (e.g., idle temperatures differ from operating temperatures)

#### Step 2: Select Thresholds by Risk Direction

```python
def select_limits(limits_per_model: dict, feature: str, risk_direction: str) -> dict:
    """
    Extract thresholds based on risk direction.
    
    Returns:
        dict: {state: {alert_threshold, anormal_threshold, critical_threshold}}
    """
    if risk_direction == 'high':
        return {
            state: {
                'alert_threshold': [limits_per_model[feature][state]['P95']],
                'anormal_threshold': [limits_per_model[feature][state]['P98']],
                'critical_threshold': [limits_per_model[feature][state]['P99']]
            } for state in limits_per_model[feature].keys()
        }
    elif risk_direction == 'low':
        return {
            state: {
                'alert_threshold': [limits_per_model[feature][state]['P5']],
                'anormal_threshold': [limits_per_model[feature][state]['P2']],
                'critical_threshold': [limits_per_model[feature][state]['P1']]
            } for state in limits_per_model[feature].keys()
        }
    else:  # 'both'
        return {
            state: {
                'alert_threshold': [limits_per_model[feature][state]['P5'], 
                                   limits_per_model[feature][state]['P95']],
                'anormal_threshold': [limits_per_model[feature][state]['P2'], 
                                     limits_per_model[feature][state]['P98']],
                'critical_threshold': [limits_per_model[feature][state]['P1'], 
                                      limits_per_model[feature][state]['P99']]
            } for state in limits_per_model[feature].keys()
        }
```

#### Step 3: Apply Thresholds to Production Data

```python
def compare_limits_unit_feature_time(
    df_in: pd.DataFrame,
    feature_name: str,
    thresholds: dict,
    risk_direction: str
) -> pd.DataFrame:
    """
    Categorize feature values into risk levels.
    
    Returns:
        pd.DataFrame: With column 'risk_level_{feature}' containing categories
    """
    df_out = df_in.copy()
    
    def categorize_value(row):
        state = row[STATE_COLNAME]
        value = row[feature_name]
        
        # Handle missing data
        if pd.isna(value) or state not in thresholds:
            return 'unknown'
        
        state_thresholds = thresholds[state]
        alert_threshold = state_thresholds['alert_threshold']
        anormal_threshold = state_thresholds['anormal_threshold']
        critical_threshold = state_thresholds['critical_threshold']
        
        if risk_direction == 'high':
            if value < alert_threshold[0]:
                return 'normal'
            elif value < anormal_threshold[0]:
                return 'alert'
            elif value < critical_threshold[0]:
                return 'anormal'
            else:
                return 'critical'
        
        elif risk_direction == 'low':
            if value > alert_threshold[0]:
                return 'normal'
            elif value > anormal_threshold[0]:
                return 'alert'
            elif value > critical_threshold[0]:
                return 'anormal'
            else:
                return 'critical'
        
        else:  # 'both'
            lower_critical, upper_critical = critical_threshold
            lower_anormal, upper_anormal = anormal_threshold
            lower_alert, upper_alert = alert_threshold
            
            if value <= lower_critical or value >= upper_critical:
                return 'critical'
            elif value <= lower_anormal or value >= upper_anormal:
                return 'anormal'
            elif value <= lower_alert or value >= upper_alert:
                return 'alert'
            else:
                return 'normal'
    
    df_out[f'risk_level_{feature_name}'] = df_out.apply(categorize_value, axis=1)
    df_out.set_index([UNIT_COLNAME, TIME_COLNAME], inplace=True)
    
    return df_out[[f'risk_level_{feature_name}']]
```

### Operational Considerations

**When to Recompute Limits:**
- After fleet composition changes (new equipment models)
- Seasonally (quarterly) to account for environmental variations
- After major maintenance campaigns that alter baseline performance

**False Positive Management:**
- P95/P98/P99 thresholds naturally allow 5%/2%/1% false positive rates
- Combine with Event Analysis (next section) to filter transient spikes
- Review alerts with maintenance logs to validate threshold appropriateness

**Computational Performance:**
- Limit computation: O(n × m × s × f) where n=data points, m=models, s=states, f=features
- Production inference: O(n) — very fast once limits are computed
- Cache computed limits for real-time applications

---

## 2. Event Analysis

### Purpose

Identify **temporal patterns** in deviation data by grouping consecutive non-normal readings into discrete events. This filters transient spikes and highlights sustained anomalies requiring attention.

### Methodology

Two parallel approaches capture different aspects of event severity:

#### Approach 1: Binary Non-Normal Model
- **Logic**: All non-normal readings (alert/anormal/critical) treated equally
- **Metric**: Duration in **minutes**
- **Classification**:
  - 🔸 **Spike**: < 5 minutes (transient, low priority)
  - 🟡 **Anomaly**: 5-30 minutes (investigate if recurring)
  - 🔴 **Warning**: ≥ 30 minutes (requires immediate attention)

#### Approach 2: Weighted Severity Model
- **Logic**: Severity levels weighted by criticality
- **Scoring**: Alert=1 pt/min, Anormal=3 pts/min, Critical=5 pts/min
- **Classification**:
  - 🔸 **Spike**: < 10 points
  - 🟡 **Anomaly**: 10-30 points
  - 🔴 **Warning**: ≥ 30 points

**Example**: A 6-minute event with 2 min Alert + 2 min Anormal + 2 min Critical scores:  
`(2×1) + (2×3) + (2×5) = 20 points` → **Anomaly** (weighted) vs. **Anomaly** (binary, 6 min)

### Implementation

#### Event Identification

```python
def identify_events_unit_feature(
    df_in: pd.DataFrame,
    unit: str,
    feature: str,
    time_col: str = TIME_COLNAME
) -> pd.DataFrame:
    """
    Identify consecutive non-normal events for a specific unit-feature pair.
    
    Returns:
        pd.DataFrame: Event groups with timestamps
    """
    risk_col = f'risk_level_{feature}'
    
    # Filter for specific unit
    if isinstance(df_in.index, pd.MultiIndex):
        unit_data = df_in.loc[unit].copy()
    else:
        unit_data = df_in[df_in[UNIT_COLNAME] == unit].copy()
    
    if risk_col not in unit_data.columns:
        return pd.DataFrame()
    
    # Sort by time
    unit_data = unit_data.sort_index() if isinstance(unit_data.index, pd.DatetimeIndex) else unit_data.sort_values(time_col)
    
    # Create binary indicator for non-normal readings
    unit_data['is_non_normal'] = ~unit_data[risk_col].isin(['normal', 'unknown'])
    
    # Create event groups (consecutive non-normal readings)
    # New group when: (1) status changes, OR (2) time gap > 1 minute
    unit_data['event_group'] = (
        (unit_data['is_non_normal'] != unit_data['is_non_normal'].shift()) |
        (unit_data['is_non_normal'] & (unit_data.index.to_series().diff() > pd.Timedelta(minutes=1)))
    ).cumsum()
    
    # Filter only non-normal events
    events = unit_data[unit_data['is_non_normal']].copy()
    events['unit'] = unit
    events['feature'] = feature
    
    return events[[risk_col, 'event_group', 'unit', 'feature']]
```

**Technical Consideration — Time Gap Detection:**
- Events separated by >1 minute gaps are treated as distinct occurrences
- Prevents merging unrelated anomalies during data collection interruptions
- Adjustable threshold based on telemetry sampling frequency

#### Binary Model Metrics

```python
def calculate_binary_event_metrics(events_df: pd.DataFrame, feature: str) -> pd.DataFrame:
    """Calculate event metrics using duration-based classification."""
    if events_df.empty:
        return pd.DataFrame()
    
    risk_col = f'risk_level_{feature}'
    
    event_summary = events_df.groupby(['unit', 'feature', 'event_group']).agg(
        start_time=('event_group', lambda x: x.index.min()),
        end_time=('event_group', lambda x: x.index.max()),
        duration_minutes=('event_group', lambda x: len(x)),
        max_severity=(risk_col, lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0])
    ).reset_index()
    
    # Classify based on duration
    def classify_binary(duration):
        if duration < 5:
            return 'spike'
        elif duration < 30:
            return 'anomaly'
        else:
            return 'warning'
    
    event_summary['event_type_binary'] = event_summary['duration_minutes'].apply(classify_binary)
    
    return event_summary
```

#### Weighted Model Metrics

```python
def calculate_weighted_event_metrics(events_df: pd.DataFrame, feature: str) -> pd.DataFrame:
    """Calculate event metrics using severity-weighted classification."""
    if events_df.empty:
        return pd.DataFrame()
    
    risk_col = f'risk_level_{feature}'
    
    # Define severity weights
    severity_weights = {
        'alert': 1,
        'anormal': 3,
        'critical': 5
    }
    
    events_df['severity_points'] = events_df[risk_col].map(severity_weights).fillna(0)
    
    event_summary = events_df.groupby(['unit', 'feature', 'event_group']).agg(
        start_time=('event_group', lambda x: x.index.min()),
        end_time=('event_group', lambda x: x.index.max()),
        total_points=('severity_points', 'sum'),
        duration_minutes=('event_group', lambda x: len(x)),
        alert_minutes=(risk_col, lambda x: (x == 'alert').sum()),
        anormal_minutes=(risk_col, lambda x: (x == 'anormal').sum()),
        critical_minutes=(risk_col, lambda x: (x == 'critical').sum())
    ).reset_index()
    
    # Classify based on severity points
    def classify_weighted(points):
        if points < 10:
            return 'spike'
        elif points < 30:
            return 'anomaly'
        else:
            return 'warning'
    
    event_summary['event_type_weighted'] = event_summary['total_points'].apply(classify_weighted)
    
    return event_summary
```

### Operational Considerations

**Choosing Between Models:**
- **Binary Model**: Simpler to explain to operators, focuses on duration
- **Weighted Model**: Better for prioritizing events with high-severity components
- **Recommendation**: Use weighted model for alerting, binary for trending/reporting

**Alert Prioritization Strategy:**
1. Weighted warnings (≥30 points) → Immediate investigation
2. Binary warnings (≥30 minutes) → Schedule inspection within shift
3. Recurring anomalies (same unit/feature, >3 occurrences/week) → Root cause analysis
4. Spikes → Suppress unless part of a pattern

**Normal Period Analysis:**
The pipeline also tracks consecutive normal operation periods to:
- Quantify equipment uptime and reliability
- Identify units with unusually short normal periods (chronic issues)
- Validate maintenance effectiveness (longer normal periods post-maintenance)

```python
def identify_normal_periods_unit_feature(
    df_in: pd.DataFrame,
    unit: str,
    feature: str,
    time_col: str = TIME_COLNAME
) -> pd.DataFrame:
    """Identify consecutive normal operating periods."""
    risk_col = f'risk_level_{feature}'
    
    # [Similar structure to identify_events_unit_feature]
    # Filter for unit, create 'is_normal' indicator
    # Group consecutive normal readings
    
    # Return normal_periods with period_group, unit, feature
    pass
```

---

## 3. Trend Analysis

### Purpose

Detect **statistically significant changes** in feature behavior over time that may indicate progressive degradation, improvement, or drift in equipment performance.

### Methodology

**Statistical Approach:**
- Apply 30-minute **rolling mean** to smooth short-term fluctuations
- Fit **linear regression** model: `y = mx + b` where:
  - `x` = time (hours since window start)
  - `y` = rolling mean of feature
- Evaluate significance using:
  - **p-value < 0.05**: Statistically significant trend
  - **R² > 0.3**: Good model fit (trend explains >30% of variance)
  - **Slope magnitude**: Rate of change per day

**Multi-Window Analysis:**
Analyze trends across three time periods to capture different temporal patterns:
- **4 weeks**: Short-term trends (recent changes, operator-driven)
- **8 weeks**: Medium-term trends (seasonal patterns)
- **12 weeks**: Long-term trends (degradation patterns)

### Implementation

```python
from sklearn.linear_model import LinearRegression
from scipy import stats

R2_THRESHOLD = 0.3
P_VALUE_THRESHOLD = 0.05

def analyze_trend_unit_feature(
    df_in: pd.DataFrame,
    unit: str,
    feature: str,
    window_weeks: int = 4,
    rolling_window_minutes: int = 30,
    time_col: str = TIME_COLNAME
) -> dict:
    """
    Analyze trend for a specific unit-feature combination over a time window.
    
    Returns:
        dict: Trend analysis results with slope, R², p-value, interpretation
    """
    # Filter for specific unit
    if isinstance(df_in.index, pd.MultiIndex):
        unit_data = df_in.loc[unit].copy()
    else:
        unit_data = df_in[df_in[UNIT_COLNAME] == unit].copy()
    
    if feature not in unit_data.columns:
        return None
    
    # Sort by time
    unit_data = unit_data.sort_index() if isinstance(unit_data.index, pd.DatetimeIndex) else unit_data.sort_values(time_col)
    
    # Filter data for the specified time window
    if isinstance(unit_data.index, pd.DatetimeIndex):
        max_time = unit_data.index.max()
        min_time = max_time - pd.Timedelta(weeks=window_weeks)
        window_data = unit_data[unit_data.index >= min_time]
    else:
        max_time = unit_data[time_col].max()
        min_time = max_time - pd.Timedelta(weeks=window_weeks)
        window_data = unit_data[unit_data[time_col] >= min_time].copy()
        window_data = window_data.set_index(time_col)
    
    # Apply rolling mean
    feature_series = window_data[feature].dropna()
    
    if len(feature_series) < rolling_window_minutes * 2:
        return None
    
    smoothed = feature_series.rolling(window=rolling_window_minutes, min_periods=1).mean()
    
    # Prepare data for regression
    valid_data = smoothed.dropna()
    if len(valid_data) < 10:
        return None
    
    # Convert timestamps to numeric (hours since start)
    X = (valid_data.index - valid_data.index[0]).total_seconds() / 3600
    X = X.values.reshape(-1, 1)
    y = valid_data.values
    
    # Fit linear regression
    model = LinearRegression()
    model.fit(X, y)
    
    # Calculate statistics
    y_pred = model.predict(X)
    slope = model.coef_[0]
    intercept = model.intercept_
    r2 = model.score(X, y)
    
    # Calculate p-value for slope
    n = len(X)
    residuals = y - y_pred
    mse = np.sum(residuals**2) / (n - 2)
    se_slope = np.sqrt(mse / np.sum((X - X.mean())**2))
    t_stat = slope / se_slope
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))
    
    return {
        'unit': unit,
        'feature': feature,
        'window_weeks': window_weeks,
        'slope': slope,  # Change per hour
        'slope_per_day': slope * 24,  # Change per day (more interpretable)
        'intercept': intercept,
        'r2': r2,
        'p_value': p_value,
        'is_significant': p_value < P_VALUE_THRESHOLD,
        'is_good_fit': r2 > R2_THRESHOLD,
        'data_points': n,
        'start_time': valid_data.index.min(),
        'end_time': valid_data.index.max()
    }
```

### Statistical Considerations

**Interpreting Trend + Risk Direction:**

| Risk Direction | Slope Sign | Interpretation |
|----------------|------------|----------------|
| `high` | Positive (+) | **Worsening** — values increasing toward danger zone |
| `high` | Negative (-) | **Improving** — values decreasing toward safety |
| `low` | Positive (+) | **Improving** — values increasing toward safety |
| `low` | Negative (-) | **Worsening** — values decreasing toward danger zone |
| `both` | Any | **Drifting** — values moving away from normal range |

**Implementation Example:**

```python
# Add trend interpretation based on risk direction
feature_metadata = next((s for s in telemetry_metadata['signals'] if s['name'] == feature), None)
if feature_metadata:
    trend_result['risk_direction'] = feature_metadata.get('risk_direction', 'unknown')
    
    slope_per_day = trend_result['slope_per_day']
    risk_dir = trend_result['risk_direction']
    
    if risk_dir == 'high' and slope_per_day > 0:
        trend_result['trend_interpretation'] = 'worsening'
    elif risk_dir == 'low' and slope_per_day < 0:
        trend_result['trend_interpretation'] = 'worsening'
    elif risk_dir == 'both' and abs(slope_per_day) > 0:
        trend_result['trend_interpretation'] = 'drifting'
    else:
        trend_result['trend_interpretation'] = 'improving'
```

**Significance Thresholds:**
- **p-value < 0.05**: 95% confidence that trend is not due to random variation
- **R² > 0.3**: Trend explains >30% of variance (adjust based on signal noise levels)
- **Minimum data points**: 10 (after rolling mean), ideally >100 for reliable statistics

### Operational Considerations

**When Trends Matter:**
- **Worsening + Significant + Good Fit**: Schedule preventive maintenance before threshold breach
- **Improving trends post-maintenance**: Validate repair effectiveness
- **Drifting trends on stable signals**: Investigate sensor calibration or environmental changes

**Computational Performance:**
- Rolling mean: O(n) using efficient windowing
- Linear regression: O(n) for single feature
- Bottleneck: Iterating over (units × features × windows) combinations
- **Optimization**: Parallelize across units using multiprocessing

**False Positive Management:**
- Trends may reflect seasonal environmental changes (temperature, humidity)
- Cross-reference with weather data or operational schedule changes
- Require multiple consecutive windows showing same trend for confirmation

**Example Use Case:**
```
Engine Coolant Temperature (EngCoolTemp)
- 4-week trend: +0.3°C/day, p=0.08, R²=0.25 → Not significant yet
- 8-week trend: +0.4°C/day, p=0.02, R²=0.42 → Significant + good fit
- 12-week trend: +0.5°C/day, p=0.001, R²=0.61 → Highly significant

Interpretation: Progressive cooling system degradation over 12 weeks.
Action: Schedule radiator inspection and coolant system pressure test.
```

---

## 4. Distribution Shift Analysis

### Purpose

Detect **statistically significant shifts in feature distributions** over time that may indicate progressive degradation, improved performance, or drift. Unlike trend analysis (which detects changes in mean), this technique identifies changes in the **entire distribution shape**.

### Methodology

**Statistical Approach:**
- **Test**: Mann-Whitney U test (two-tailed, non-parametric)
- **Why Mann-Whitney**: 
  - Detects distribution shifts without assuming normality
  - Robust to outliers
  - Sensitive to changes in central tendency, spread, and shape
  
**Comparison Strategy:**
- **Baseline Period**: 1 year of historical data (excluding observation period)
- **Observation Periods**: Recent 4, 8, or 12 weeks
- **Null Hypothesis**: Recent data distribution = Historical baseline distribution
- **Alternative Hypothesis**: Distributions differ significantly

**State Control:**
Analysis performed separately for each operational state (Operating, Idle, Hauling, etc.) to prevent confounding factors.

### Implementation

```python
from scipy.stats import mannwhitneyu

BASELINE_WEEKS = 52  # 1 year baseline

def calculate_cohens_d(baseline, observation):
    """Calculate Cohen's d effect size for quantifying distribution difference."""
    pooled_std = np.sqrt(
        ((len(baseline) - 1) * baseline.std()**2 + 
         (len(observation) - 1) * observation.std()**2) / 
        (len(baseline) + len(observation) - 2)
    )
    if pooled_std == 0:
        return 0
    return (observation.mean() - baseline.mean()) / pooled_std


def analyze_distribution_shift_unit_feature_state(
    df_in: pd.DataFrame,
    unit: str,
    feature: str,
    state: str,
    observation_weeks: int = 4,
    baseline_weeks: int = BASELINE_WEEKS,
    time_col: str = TIME_COLNAME
) -> dict:
    """
    Analyze distribution shift for a specific unit-feature-state combination.
    
    Returns:
        dict: Distribution shift analysis results or None if insufficient data
    """
    # Filter for specific unit and state
    if isinstance(df_in.index, pd.MultiIndex):
        unit_data = df_in.loc[unit].copy()
    else:
        unit_data = df_in[df_in[UNIT_COLNAME] == unit].copy()
    
    if feature not in unit_data.columns or STATE_COLNAME not in unit_data.columns:
        return None
    
    state_data = unit_data[unit_data[STATE_COLNAME] == state].copy()
    
    if len(state_data) == 0:
        return None
    
    # Sort by time
    state_data = state_data.sort_index() if isinstance(state_data.index, pd.DatetimeIndex) else state_data.sort_values(time_col)
    
    # Define time windows
    if isinstance(state_data.index, pd.DatetimeIndex):
        max_time = state_data.index.max()
    else:
        state_data = state_data.set_index(time_col)
        max_time = state_data.index.max()
    
    observation_start = max_time - pd.Timedelta(weeks=observation_weeks)
    baseline_end = observation_start
    baseline_start = max_time - pd.Timedelta(weeks=baseline_weeks)
    
    # Extract observation and baseline data
    observation_data = state_data[
        (state_data.index >= observation_start) & 
        (state_data.index <= max_time)
    ][feature].dropna()
    
    baseline_data = state_data[
        (state_data.index >= baseline_start) & 
        (state_data.index < baseline_end)
    ][feature].dropna()
    
    # Check minimum data requirements
    if len(observation_data) < 30 or len(baseline_data) < 100:
        return None
    
    # Perform Mann-Whitney U test
    try:
        u_statistic, p_value = mannwhitneyu(
            baseline_data, 
            observation_data, 
            alternative='two-sided'
        )
    except Exception as e:
        return None
    
    # Calculate effect size (Cohen's d)
    cohens_d = calculate_cohens_d(baseline_data.values, observation_data.values)
    
    # Calculate medians
    baseline_median = baseline_data.median()
    observation_median = observation_data.median()
    median_diff = observation_median - baseline_median
    median_pct_change = (median_diff / baseline_median * 100) if baseline_median != 0 else 0
    
    return {
        'unit': unit,
        'feature': feature,
        'state': state,
        'observation_weeks': observation_weeks,
        'p_value': p_value,
        'u_statistic': u_statistic,
        'cohens_d': cohens_d,
        'effect_size_category': (
            'large' if abs(cohens_d) > 0.8 else 
            'medium' if abs(cohens_d) > 0.5 else 
            'small' if abs(cohens_d) > 0.2 else 
            'negligible'
        ),
        'is_significant': p_value < 0.05,
        'baseline_median': baseline_median,
        'observation_median': observation_median,
        'median_diff': median_diff,
        'median_pct_change': median_pct_change,
        'baseline_n': len(baseline_data),
        'observation_n': len(observation_data),
        'baseline_start': baseline_start,
        'baseline_end': baseline_end,
        'observation_start': observation_start,
        'observation_end': max_time
    }
```

### Statistical Considerations

**Effect Size Interpretation (Cohen's d):**

| Effect Size | Cohen's d | Practical Meaning |
|-------------|-----------|-------------------|
| Negligible | < 0.2 | Statistically detectable but not operationally significant |
| Small | 0.2 - 0.5 | Noticeable change, monitor trend |
| Medium | 0.5 - 0.8 | Significant change, investigate cause |
| Large | > 0.8 | Major shift, requires immediate attention |

**Minimum Sample Requirements:**
- **Observation period**: ≥30 samples (ensures test power)
- **Baseline period**: ≥100 samples (stable reference distribution)
- **Rule of thumb**: Need ~10× more baseline than observation data for robust comparison

**State Control Rationale:**
Consider engine oil pressure:
- **Without state control**: Mixing "Operating" (high pressure) and "Idle" (low pressure) data creates artificial distribution shift
- **With state control**: Compare "Operating now" vs. "Operating historically" — true performance change

### Operational Considerations

**Interpreting Shift + Risk Direction:**

| Shift Interpretation | Criteria | Action |
|----------------------|----------|--------|
| **Critical** | p<0.05, large effect, worsening direction | Immediate investigation |
| **Warning** | p<0.05, medium effect, worsening direction | Schedule inspection within week |
| **Monitor** | p<0.05, small effect | Track in next analysis cycle |
| **Non-significant** | p≥0.05 | No action, distribution stable |

**Example Scenario:**
```
Feature: EngOilPress (Engine Oil Pressure)
Unit: T-107
State: Operating
Observation: Last 8 weeks

Results:
- Baseline median: 45.2 psi (n=4,320 samples)
- Observation median: 42.1 psi (n=806 samples)
- Median difference: -3.1 psi (-6.9%)
- Mann-Whitney U: p=0.003 (highly significant)
- Cohen's d: -0.72 (medium-to-large effect)
- Risk direction: low (lower is worse)
- Interpretation: WORSENING

Diagnosis: Oil pump degradation or increased bearing clearances.
Recommendation: Oil analysis, pressure sensor validation, pump inspection.
```

**When Distribution Analysis Outperforms Trend Analysis:**
- **Bimodal distributions**: Equipment switching between two operating modes
- **Increased variability**: Same mean but higher variance indicates instability
- **Non-linear changes**: Sudden shifts that linear regression misses
- **Intermittent issues**: Occasional extreme values without clear trend

**Computational Considerations:**
- Mann-Whitney U: O(n log n) complexity — efficient even for large datasets
- Bottleneck: (units × features × states × observation_windows) combinations
- **Optimization**: Filter to features/states with sufficient data before testing

---

## 5. Anomaly Detection (LSTM Autoencoder)

### Purpose

Detect **complex multi-signal anomalies** using deep learning to identify equipment operating patterns that deviate from learned "normal operational signatures." Unlike threshold-based methods, this approach identifies **pattern anomalies** across multiple correlated signals.

### Methodology

**Architecture:**
- **Model Type**: LSTM (Long Short-Term Memory) Autoencoder
- **Input**: 30-minute sequences of multi-signal telemetry data
- **Training Objective**: Minimize reconstruction error for normal operation patterns
- **Inference**: High reconstruction error → Anomaly

**Data Preparation:**

1. **Feature Grouping by System:**
   - Engine signals (EngCoolTemp, EngOilPress, EngSpd, etc.)
   - Hydraulic signals (HydOilTemp, HydOilPress, etc.)
   - Transmission signals (TransOilTemp, TransOilPress, etc.)
   - Group defined by `system` field in signal_registry.yaml

2. **Categorical Feature Encoding:**
   - `Estado` (State) → One-Hot Encoding
   - `EngSpd` (Engine Speed) → Binned into 300 RPM intervals
     - Bins: <300, 300-600, 600-900, 900-1200, >1200 RPM

3. **Missing Value Handling:**
   - Numerical features: Linear interpolation based on timestamps
   - Categorical features: Forward fill then backward fill
   - **Data Quality Rule**: Only sequences with <10% imputed values used for training/inference

4. **Normalization:**
   - StandardScaler applied to all features (zero mean, unit variance)
   - Scaler fitted on training data, applied consistently to inference data

**Training Strategy:**
- **Training Data**: Sequences labeled as "normal" (from Deviation Analysis)
- **Validation Split**: 20% hold-out for early stopping
- **Sequence Length**: 30 minutes (30 samples at 1-min resolution)
- **Quality Threshold**: Exclude sequences with >10% missing values

### Implementation

#### Data Preparation Functions

```python
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.preprocessing import StandardScaler

SEQUENCE_LENGTH = 30  # 30-minute sequences
QUALITY_THRESHOLD = 0.10  # <10% imputed values
ENG_SPD_BINS = [0, 300, 600, 900, 1200, float('inf')]
ENG_SPD_LABELS = ['<300', '300-600', '600-900', '900-1200', '>1200']


def get_system_features(telemetry_metadata: dict, system_name: str) -> list:
    """Extract all features belonging to a specific system."""
    return [
        signal['name'] for signal in telemetry_metadata['signals'] 
        if signal.get('system', '') == system_name and signal.get('threshold_compute', False)
    ]


def encode_categorical_features(df_in: pd.DataFrame) -> pd.DataFrame:
    """
    Encode categorical features for LSTM input.
    
    Encodings:
    - Estado (State): One-Hot Encoding
    - EngSpd (Engine Speed): Binned into 300 RPM intervals
    """
    df_encoded = df_in.copy()
    
    # One-hot encode Estado (State)
    if STATE_COLNAME in df_encoded.columns:
        estado_dummies = pd.get_dummies(df_encoded[STATE_COLNAME], prefix='Estado')
        df_encoded = pd.concat([df_encoded, estado_dummies], axis=1)
    
    # Bin EngSpd if it exists
    if 'EngSpd' in df_encoded.columns:
        df_encoded['EngSpd_binned'] = pd.cut(
            df_encoded['EngSpd'], 
            bins=ENG_SPD_BINS, 
            labels=ENG_SPD_LABELS,
            include_lowest=True
        )
        engspd_dummies = pd.get_dummies(df_encoded['EngSpd_binned'], prefix='EngSpd')
        df_encoded = pd.concat([df_encoded, engspd_dummies], axis=1)
    
    return df_encoded


def prepare_sequences(
    df_in: pd.DataFrame,
    unit: str,
    system_features: list,
    sequence_length: int = SEQUENCE_LENGTH,
    quality_threshold: float = QUALITY_THRESHOLD
) -> tuple:
    """
    Prepare 30-minute sequences with quality checks.
    
    Returns:
        tuple: (sequences, quality_flags) or (None, None) if insufficient data
    """
    # Filter for specific unit
    if isinstance(df_in.index, pd.MultiIndex):
        unit_data = df_in.loc[unit].copy()
    else:
        unit_data = df_in[df_in[UNIT_COLNAME] == unit].copy()
    
    # Sort by time
    unit_data = unit_data.sort_index() if isinstance(unit_data.index, pd.DatetimeIndex) else unit_data.sort_values(TIME_COLNAME).set_index(TIME_COLNAME)
    
    # Encode categorical features
    unit_data = encode_categorical_features(unit_data)
    
    # Get encoded feature columns
    encoded_estado_cols = [col for col in unit_data.columns if col.startswith('Estado_')]
    encoded_engspd_cols = [col for col in unit_data.columns if col.startswith('EngSpd_')]
    
    # Select features for the system + encoded categoricals
    numerical_cols = [f for f in system_features if f in unit_data.columns]
    feature_cols = numerical_cols + encoded_estado_cols + encoded_engspd_cols
    
    if len(feature_cols) == 0:
        return None, None
    
    # Track missing values before imputation
    missing_mask = unit_data[feature_cols].isna()
    
    # Linear interpolation for numerical features
    if len(numerical_cols) > 0:
        unit_data[numerical_cols] = unit_data[numerical_cols].interpolate(method='time', limit_direction='both')
    
    # Forward fill for categorical encoded features
    categorical_cols = encoded_estado_cols + encoded_engspd_cols
    if len(categorical_cols) > 0:
        unit_data[categorical_cols] = unit_data[categorical_cols].ffill().bfill()
    
    # Create sequences
    sequences = []
    quality_flags = []
    
    for i in range(len(unit_data) - sequence_length + 1):
        sequence = unit_data[feature_cols].iloc[i:i + sequence_length].values
        
        # Calculate imputation ratio for this sequence
        missing_count = missing_mask[feature_cols].iloc[i:i + sequence_length].sum().sum()
        total_values = sequence_length * len(feature_cols)
        imputation_ratio = missing_count / total_values if total_values > 0 else 1.0
        
        # Only include high-quality sequences
        if imputation_ratio < quality_threshold:
            sequences.append(sequence)
            quality_flags.append(imputation_ratio)
    
    if len(sequences) == 0:
        return None, None
    
    return np.array(sequences), np.array(quality_flags)
```

#### Model Architecture

```python
def build_lstm_autoencoder(input_shape: tuple, encoding_dim: int = 32) -> keras.Model:
    """
    Build LSTM Autoencoder model.
    
    Architecture:
    - Encoder: 2 LSTM layers (64 → encoding_dim)
    - Latent space: encoding_dim dimensional representation
    - Decoder: 2 LSTM layers (encoding_dim → 64) + TimeDistributed Dense
    
    Parameters:
        - input_shape (tuple): (sequence_length, n_features)
        - encoding_dim (int): Dimension of latent representation (default: 32)
        
    Returns:
        - keras.Model: Compiled LSTM autoencoder
    """
    # Encoder
    encoder_inputs = keras.Input(shape=input_shape)
    x = layers.LSTM(64, activation='relu', return_sequences=True)(encoder_inputs)
    x = layers.LSTM(encoding_dim, activation='relu', return_sequences=False)(x)
    encoder = keras.Model(encoder_inputs, x, name='encoder')
    
    # Decoder
    decoder_inputs = keras.Input(shape=(encoding_dim,))
    x = layers.RepeatVector(input_shape[0])(decoder_inputs)
    x = layers.LSTM(encoding_dim, activation='relu', return_sequences=True)(x)
    x = layers.LSTM(64, activation='relu', return_sequences=True)(x)
    decoder_outputs = layers.TimeDistributed(layers.Dense(input_shape[1]))(x)
    decoder = keras.Model(decoder_inputs, decoder_outputs, name='decoder')
    
    # Autoencoder
    autoencoder_inputs = keras.Input(shape=input_shape)
    encoded = encoder(autoencoder_inputs)
    decoded = decoder(encoded)
    autoencoder = keras.Model(autoencoder_inputs, decoded, name='autoencoder')
    
    # Compile
    autoencoder.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss='mse'
    )
    
    return autoencoder
```

#### Training Procedure

```python
from sklearn.model_selection import train_test_split

def train_autoencoder_unit_system(
    df_in: pd.DataFrame,
    deviation_results: pd.DataFrame,
    unit: str,
    system_name: str,
    system_features: list,
    epochs: int = 50,
    batch_size: int = 32,
    validation_split: float = 0.2
) -> dict:
    """
    Train LSTM autoencoder for a specific unit and system.
    
    Returns:
        dict: Training results including model, scaler, and baseline metrics
    """
    # Filter for normal sequences based on deviation analysis
    if isinstance(deviation_results.index, pd.MultiIndex):
        unit_deviations = deviation_results.loc[unit].copy()
    else:
        unit_deviations = deviation_results[deviation_results[UNIT_COLNAME] == unit].copy()
    
    # Check if all system features are normal
    risk_cols = [f'risk_level_{f}' for f in system_features if f'risk_level_{f}' in unit_deviations.columns]
    
    if len(risk_cols) == 0:
        return None
    
    # Filter normal data (all features normal)
    normal_mask = (unit_deviations[risk_cols] == 'normal').all(axis=1)
    normal_timestamps = normal_mask[normal_mask].index
    
    # Get unit data from df_in and filter for normal timestamps
    if isinstance(df_in.index, pd.MultiIndex):
        unit_raw_data = df_in.loc[unit].copy()
    else:
        unit_raw_data = df_in[df_in[UNIT_COLNAME] == unit].copy()
        if TIME_COLNAME in unit_raw_data.columns:
            unit_raw_data = unit_raw_data.set_index(TIME_COLNAME)
    
    normal_data = unit_raw_data[unit_raw_data.index.isin(normal_timestamps)]
    
    # Prepare sequences
    sequences, quality_flags = prepare_sequences(normal_data, unit, system_features)
    
    if sequences is None or len(sequences) < 100:
        return None
    
    # Normalize features
    scaler = StandardScaler()
    n_samples, n_timesteps, n_features = sequences.shape
    sequences_flat = sequences.reshape(-1, n_features)
    sequences_scaled = scaler.fit_transform(sequences_flat).reshape(n_samples, n_timesteps, n_features)
    
    # Split train/validation
    X_train, X_val = train_test_split(sequences_scaled, test_size=validation_split, random_state=42)
    
    # Build model
    input_shape = (n_timesteps, n_features)
    model = build_lstm_autoencoder(input_shape)
    
    # Early stopping callback
    early_stopping = keras.callbacks.EarlyStopping(
        monitor='val_loss',
        patience=10,
        restore_best_weights=True
    )
    
    # Train
    history = model.fit(
        X_train, X_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(X_val, X_val),
        callbacks=[early_stopping],
        verbose=0
    )
    
    # Calculate baseline reconstruction errors
    train_reconstructions = model.predict(X_train, verbose=0)
    train_mse = np.mean(np.square(X_train - train_reconstructions), axis=(1, 2))
    
    val_reconstructions = model.predict(X_val, verbose=0)
    val_mse = np.mean(np.square(X_val - val_reconstructions), axis=(1, 2))
    
    # Establish baseline statistics for anomaly scoring
    baseline_mean = np.mean(train_mse)
    baseline_std = np.std(train_mse)
    baseline_p95 = np.percentile(train_mse, 95)
    baseline_p99 = np.percentile(train_mse, 99)
    
    return {
        'unit': unit,
        'system': system_name,
        'model': model,
        'scaler': scaler,
        'n_features': n_features,
        'n_sequences': len(sequences),
        'train_loss': history.history['loss'][-1],
        'val_loss': history.history['val_loss'][-1],
        'baseline_mean': baseline_mean,
        'baseline_std': baseline_std,
        'baseline_p95': baseline_p95,
        'baseline_p99': baseline_p99,
        'feature_columns': system_features
    }
```

#### Inference and Anomaly Scoring

```python
def score_anomaly(
    model: keras.Model,
    scaler: StandardScaler,
    sequence: np.ndarray,
    baseline_mean: float,
    baseline_std: float,
    baseline_p95: float,
    baseline_p99: float
) -> dict:
    """
    Score a sequence for anomaly likelihood.
    
    Returns:
        dict: Anomaly score, percentile rank, and severity category
    """
    # Normalize sequence
    n_timesteps, n_features = sequence.shape
    sequence_flat = sequence.reshape(-1, n_features)
    sequence_scaled = scaler.transform(sequence_flat).reshape(1, n_timesteps, n_features)
    
    # Reconstruct
    reconstruction = model.predict(sequence_scaled, verbose=0)
    
    # Calculate reconstruction error
    mse = np.mean(np.square(sequence_scaled - reconstruction))
    
    # Calculate z-score
    z_score = (mse - baseline_mean) / baseline_std if baseline_std > 0 else 0
    
    # Calculate percentile rank (approximation)
    if mse < baseline_p95:
        percentile = 50 + (mse - baseline_mean) / (baseline_p95 - baseline_mean) * 45
        severity = 'normal' if mse < baseline_mean + baseline_std else 'minor'
    elif mse < baseline_p99:
        percentile = 95 + (mse - baseline_p95) / (baseline_p99 - baseline_p95) * 4
        severity = 'moderate'
    else:
        percentile = 99 + min((mse - baseline_p99) / baseline_p99 * 1, 1)
        severity = 'severe'
    
    return {
        'reconstruction_error': mse,
        'z_score': z_score,
        'percentile_score': percentile,
        'severity': severity,
        'baseline_mean': baseline_mean,
        'baseline_p95': baseline_p95,
        'baseline_p99': baseline_p99
    }
```

### Statistical and Technical Considerations

**Anomaly Score Interpretation:**

| Percentile Score | Severity | Action |
|------------------|----------|--------|
| 0-70 | Normal | No action, typical operation |
| 70-90 | Minor | Monitor, log for trending |
| 90-95 | Moderate | Investigate if recurring |
| 95-99 | Severe | Immediate investigation |
| >99 | Critical | Urgent attention, potential failure |

**Training Data Requirements:**
- **Minimum sequences**: 100 per (unit, system) combination
- **Recommended**: 1,000+ sequences for robust pattern learning
- **Normal data filtering**: Use Deviation Analysis to ensure training data represents normal operation
- **Validation split**: 20% to prevent overfitting

**Hyperparameter Tuning:**
- **Encoding dimension** (default 32): 
  - Lower (16) → Stronger compression, may miss subtle patterns
  - Higher (64) → Richer representation, risk of overfitting
- **LSTM units** (default 64): 
  - Scale with number of input features
  - Rule of thumb: 2-4× the number of features
- **Sequence length** (default 30 min):
  - Shorter (15 min) → Faster inference, less temporal context
  - Longer (60 min) → More context, requires more training data

### Operational Considerations

**When to Use LSTM Anomaly Detection:**
- Multi-signal coordination issues (e.g., temperature-pressure-speed relationships)
- Operator misuse patterns (rapid cycling, improper shutdown sequences)
- Early failure signatures before individual thresholds are breached
- Novel failure modes not represented in historical threshold data

**When NOT to Use:**
- Simple single-feature threshold violations (use Deviation Analysis instead)
- Insufficient training data (<100 sequences)
- High-noise signals with poor temporal correlation
- Real-time applications with <1 second latency requirements (inference ~50-100ms per sequence)

**Model Lifecycle Management:**

1. **Initial Training** (Quarter 1):
   - Collect 3-6 months of labeled "normal" data
   - Train models for each (unit, system) combination
   - Establish baseline error distributions
   - Deploy to production monitoring

2. **Production Monitoring** (Ongoing):
   - Score incoming 30-minute windows in real-time
   - Log high-severity anomalies (>95th percentile)
   - Collect feedback from operators/analysts on true vs. false positives

3. **Periodic Retraining** (Quarterly):
   - Add confirmed normal data from recent months
   - Retrain models to adapt to seasonal variations
   - Update baseline statistics
   - A/B test new models against current production models

4. **Failure Mode Analysis** (Continuous):
   - Archive sequences preceding confirmed failures
   - Analyze reconstruction errors to identify precursor patterns
   - Consider supervised learning if failure mode corpus grows large

**Computational Requirements:**
- **Training**: ~1-5 minutes per (unit, system) on GPU, ~10-30 minutes on CPU
- **Inference**: ~50-100ms per 30-minute sequence on CPU
- **Storage**: ~1-5 MB per trained model (small, easily deployable)
- **Scalability**: Train models in parallel across units (embarrassingly parallel)

**Integration with Other Techniques:**

```
Recommended Analysis Flow:
1. Deviation Analysis → Identify individual feature threshold violations
2. Event Analysis → Group consecutive deviations, filter transient spikes
3. Trend Analysis → Detect progressive degradation over weeks
4. Distribution Shift Analysis → Identify changes in feature behavior
5. LSTM Anomaly Detection → Catch complex multi-signal patterns missed by 1-4

Use LSTM alerts to:
- Trigger deeper investigation when other methods show no issues
- Validate threshold-based alerts (confirm pattern anomaly, not just value anomaly)
- Discover new feature combinations predictive of failures
```

---

## Implementation Best Practices

### 1. Data Quality Checks

Always validate input data before analysis:

```python
def validate_telemetry_data(df: pd.DataFrame) -> dict:
    """Run data quality checks on telemetry data."""
    issues = []
    
    # Check for required columns
    required_cols = [UNIT_COLNAME, TIME_COLNAME, STATE_COLNAME]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        issues.append(f"Missing columns: {missing_cols}")
    
    # Check timestamp ordering
    if TIME_COLNAME in df.columns:
        if not df[TIME_COLNAME].is_monotonic_increasing:
            issues.append("Timestamps not in ascending order")
    
    # Check for duplicate timestamps per unit
    if UNIT_COLNAME in df.columns and TIME_COLNAME in df.columns:
        duplicates = df.duplicated(subset=[UNIT_COLNAME, TIME_COLNAME]).sum()
        if duplicates > 0:
            issues.append(f"{duplicates} duplicate (unit, timestamp) pairs")
    
    # Check missing value rates
    missing_rates = df.isnull().mean()
    high_missing = missing_rates[missing_rates > 0.5].index.tolist()
    if high_missing:
        issues.append(f"Features with >50% missing: {high_missing}")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'n_rows': len(df),
        'n_features': len(df.columns),
        'time_range': (df[TIME_COLNAME].min(), df[TIME_COLNAME].max()) if TIME_COLNAME in df.columns else None
    }
```

### 2. Incremental Processing

For large datasets, process in chunks:

```python
def process_telemetry_in_chunks(
    file_paths: list,
    process_func: callable,
    chunk_weeks: int = 4
) -> pd.DataFrame:
    """Process telemetry data in weekly chunks to manage memory."""
    results = []
    
    for file_path in file_paths:
        df_chunk = pd.read_parquet(file_path)
        result_chunk = process_func(df_chunk)
        results.append(result_chunk)
        
        # Free memory
        del df_chunk
    
    return pd.concat(results, ignore_index=True)
```

### 3. Parallel Processing

Leverage multiprocessing for unit-level analyses:

```python
from multiprocessing import Pool, cpu_count

def analyze_unit_wrapper(args):
    """Wrapper for parallel unit analysis."""
    unit, df_unit, metadata = args
    # Run analysis for single unit
    return analyze_unit(df_unit, metadata)

def parallel_unit_analysis(df, metadata, n_workers=None):
    """Analyze units in parallel."""
    if n_workers is None:
        n_workers = cpu_count() - 1
    
    # Prepare arguments
    units = df[UNIT_COLNAME].unique()
    args = [(unit, df[df[UNIT_COLNAME] == unit], metadata) for unit in units]
    
    # Execute in parallel
    with Pool(n_workers) as pool:
        results = pool.map(analyze_unit_wrapper, args)
    
    return pd.concat(results, ignore_index=True)
```

### 4. Configuration Management

Store analysis parameters in configuration files:

```yaml
# analysis_config.yaml
deviation_analysis:
  baseline_weeks: 12
  percentiles: [1, 2, 5, 10, 25, 50, 75, 90, 95, 98, 99]
  min_unique_values: 10

event_analysis:
  binary_thresholds:
    spike_max_minutes: 5
    anomaly_max_minutes: 30
  weighted_thresholds:
    spike_max_points: 10
    anomaly_max_points: 30
  severity_weights:
    alert: 1
    anormal: 3
    critical: 5

trend_analysis:
  window_weeks: [4, 8, 12]
  rolling_window_minutes: 30
  p_value_threshold: 0.05
  r2_threshold: 0.3
  min_data_points: 10

distribution_analysis:
  baseline_weeks: 52
  observation_weeks: [4, 8, 12]
  p_value_threshold: 0.05
  min_baseline_samples: 100
  min_observation_samples: 30

anomaly_detection:
  sequence_length: 30
  quality_threshold: 0.10
  encoding_dim: 32
  epochs: 50
  batch_size: 32
  validation_split: 0.2
  early_stopping_patience: 10
```

### 5. Logging and Monitoring

Implement comprehensive logging:

```python
import logging

def setup_logger(log_file='telemetry_analysis.log'):
    """Configure logger for analysis pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logger()

# Usage in pipeline
logger.info(f"Starting deviation analysis for {len(units)} units")
logger.warning(f"Insufficient data for unit {unit}, skipping")
logger.error(f"Failed to compute limits: {str(e)}")
```

---

## Performance Considerations

### Computational Complexity

| Technique | Complexity | Bottleneck | Optimization |
|-----------|------------|------------|--------------|
| Deviation Analysis | O(n × m × s × f) | Percentile computation | Cache limits, vectorize |
| Event Analysis | O(n × u × f) | Grouping consecutive readings | Use NumPy cumsum |
| Trend Analysis | O(n × u × f × w) | Linear regression | Parallelize by unit |
| Distribution Shift | O(n log n × u × f × s × w) | Mann-Whitney U test | Filter low-data pairs |
| LSTM Anomaly Detection | O(n × u × sys) training<br>O(n) inference | Model training | GPU acceleration, parallelize |

**Legend:**
- n = data points
- m = models
- s = states
- f = features
- u = units
- w = time windows
- sys = systems

### Memory Management

**Guidelines:**
- **Small datasets** (<1M rows): Load entire dataset into memory
- **Medium datasets** (1-10M rows): Process in weekly/monthly chunks
- **Large datasets** (>10M rows): Use Dask or PySpark for distributed processing

**Memory Estimation:**
```python
# Estimate memory usage
n_rows = 1_000_000
n_features = 50
memory_mb = (n_rows * n_features * 8) / (1024 ** 2)  # 8 bytes per float64
print(f"Estimated memory: {memory_mb:.1f} MB")
```

### Caching Strategies

```python
import joblib
from pathlib import Path

def load_or_compute_limits(df, metadata, cache_file='limits_cache.pkl'):
    """Load cached limits or compute if not available."""
    cache_path = Path(cache_file)
    
    if cache_path.exists():
        logger.info("Loading cached limits")
        return joblib.load(cache_path)
    else:
        logger.info("Computing limits (this may take a few minutes)")
        limits = compute_limits(df, metadata)
        joblib.dump(limits, cache_path)
        return limits
```

---

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue 1: Insufficient Data for Limits Computation

**Symptom**: Few or no limits computed for certain (model, state, feature) combinations

**Causes:**
- Unit operated in specific state for <10 unique values
- Feature has constant value (e.g., sensor malfunction)
- Incorrect model_specification mapping

**Solutions:**
```python
# Diagnose missing limits
for model in limits.keys():
    for feature in telemetry_metadata['signals']:
        feature_name = feature['name']
        if feature_name not in limits[model]:
            logger.warning(f"No limits for {model} | {feature_name}")
            # Check data availability
            data = df[(df['model_specification'] == model)][feature_name].dropna()
            print(f"  Unique values: {data.nunique()}, Total samples: {len(data)}")
```

#### Issue 2: Event Analysis Produces Too Many Spikes

**Symptom**: Overwhelming number of short-duration events

**Causes:**
- Noisy sensors causing frequent threshold crossings
- Thresholds too tight (P95 catches normal variability)

**Solutions:**
- Increase spike threshold from 5 to 10 minutes
- Apply hysteresis to threshold comparisons
- Use weighted model to filter low-severity spikes

#### Issue 3: Trend Analysis Shows No Significant Trends

**Symptom**: Most trends have p-value > 0.05 or R² < 0.3

**Causes:**
- High signal noise overwhelming linear signal
- Equipment in steady-state operation (expected)
- Rolling window too small (increase from 30 to 60 minutes)

**Solutions:**
- Increase rolling window size to reduce noise
- Lower R² threshold for exploratory analysis (e.g., 0.2)
- Focus on worsening trends even if R² is moderate

#### Issue 4: Distribution Shift Analysis Requires Too Much Data

**Symptom**: Many unit-feature-state combinations skipped due to insufficient baseline data

**Causes:**
- New equipment with <1 year history
- State rarely occupied (e.g., "Maintenance" mode)

**Solutions:**
```python
# Reduce baseline requirement for new equipment
def adaptive_baseline_weeks(unit, df):
    """Use shorter baseline for new units."""
    unit_data = df[df[UNIT_COLNAME] == unit]
    data_weeks = (unit_data[TIME_COLNAME].max() - unit_data[TIME_COLNAME].min()).days / 7
    
    if data_weeks < 52:
        return max(12, data_weeks * 0.7)  # Use 70% as baseline, minimum 12 weeks
    else:
        return 52
```

#### Issue 5: LSTM Autoencoder Training Fails

**Symptom**: Model training returns None or validation loss doesn't decrease

**Causes:**
- Insufficient normal sequences (<100)
- All features in system have same value (no variability)
- NaN values not properly handled

**Solutions:**
```python
# Debug LSTM training
logger.info(f"Training {unit} | {system}: {len(sequences)} sequences")
if len(sequences) < 100:
    logger.warning(f"  Insufficient sequences, need ≥100, got {len(sequences)}")
    return None

# Check for zero variance
feature_stds = sequences.std(axis=(0, 1))
zero_variance_features = np.where(feature_stds == 0)[0]
if len(zero_variance_features) > 0:
    logger.warning(f"  Zero variance features: {zero_variance_features}")
    # Remove constant features
    sequences = np.delete(sequences, zero_variance_features, axis=2)
```

---

## 6. Multi-Technique Aggregation

### Purpose

Combine results from all individual techniques into a **coherent, hierarchical health assessment** using a Signal → System → Unit evaluation framework. This produces a single prioritized fleet view with full explainability.

### Evaluation Hierarchy

```
Signal-Level Results (per technique)
        │
        ▼
System-Level Aggregation (Engine, Transmission, Brakes, Steering)
        │
        ▼
Unit-Level Aggregation (Fleet ranking & prioritization)
```

### Signal-Level Scoring

Each technique result is normalized into a standardized structure:

```python
@dataclass
class TechniqueResult:
    unit: str
    signal: str
    system: str
    technique: str  # "deviation", "event", "trend", "distribution", "autoencoder"
    risk_score: float  # 0-100
    confidence_score: float  # 0-100
    status: str  # "Normal", "Alerta", "Anormal", "InsufficientData"
    evidence: dict  # Technique-specific evidence
    evaluation_start: datetime
    evaluation_end: datetime
    execution_timestamp: datetime
    baseline_version: str
```

**Risk Score Bands:**
- 0-30: Low risk / Normal variation
- 30-60: Moderate risk / Monitoring recommended
- 60-80: High risk / Inspection recommended
- 80-100: Critical risk / Immediate action required

**Confidence Score Factors:**
- Data coverage: `min(valid_samples / expected_samples, 1.0)`
- Baseline quality: `min(baseline_sample_count / 1000, 1.0)`
- State matching: Penalty if using wrong baseline state
- Sample size: Penalty if below technique minimum

**Status Classification:**
- **Normal**: risk_score < 40
- **Alerta**: 40 ≤ risk_score < 70
- **Anormal**: risk_score ≥ 70
- **InsufficientData**: confidence_score < 50

### System-Level Aggregation

Combine recent technique results for all signals within a system.

**Process:**
1. Filter results within validity period (technique-dependent)
2. Apply time-decay weighting (recent results weighted higher)
3. Apply signal criticality weighting (from signal_registry)
4. Detect multi-technique agreement (boost score if multiple techniques flag same signal)
5. Ensure critical findings are not averaged away

**Aggregation Formula:**
```python
system_score = (
    0.4 * max_recent_critical_score +  # Cannot ignore severe evidence
    0.3 * weighted_mean_score +         # Captures broad patterns
    0.2 * persistence_bonus +           # Rewards multi-technique agreement
    0.1 * trend_penalty                 # Worsening trends add urgency
)
```

**Validity Periods:**
| Technique | Validity Period |
|-----------|----------------|
| AutoEncoder (6h) | 12 hours |
| Deviation (daily) | 2 days |
| Event (daily) | 2 days |
| Distribution (weekly) | 1 week |
| Trend (weekly) | 4 weeks |

### Unit-Level Aggregation

Aggregate system assessments into a fleet-level priority score.

**Priority Score:**
```python
priority_score = (
    100 * n_anormal_critical_systems +  # Engine, Transmission, Brakes
    50 * n_anormal_other_systems +
    20 * n_alerta_critical_systems +
    10 * n_alerta_other_systems +
    5 * any_negative_trends +
    unit_score
)
```

**Unit Status Logic:**
- **Anormal**: Any critical system Anormal OR ≥2 systems Anormal
- **Alerta**: Any system Alerta and none Anormal
- **Normal**: All systems Normal
- **InsufficientData**: Confidence too low across systems

### Implementation

```python
def aggregate_system_health(
    technique_results: list[dict],
    signal_registry: dict,
    system_name: str,
    unit: str,
    evaluation_timestamp: datetime
) -> dict:
    """
    Aggregate technique results into system-level health assessment.
    
    Parameters:
        - technique_results: List of TechniqueResult dicts for signals in this system
        - signal_registry: Signal metadata with criticality weights
        - system_name: Name of system (Engine, Transmission, etc.)
        - unit: Unit identifier
        - evaluation_timestamp: Current evaluation time
        
    Returns:
        - dict: System health assessment with score, status, and evidence
    """
    if not technique_results:
        return {
            'unit': unit,
            'system': system_name,
            'system_score': 0,
            'system_status': 'InsufficientData',
            'confidence': 0,
            'top_evidence': [],
            'evaluation_timestamp': evaluation_timestamp
        }
    
    # Filter by validity period
    valid_results = filter_by_validity(technique_results, evaluation_timestamp)
    
    if not valid_results:
        return {
            'unit': unit,
            'system': system_name,
            'system_score': 0,
            'system_status': 'InsufficientData',
            'confidence': 0,
            'top_evidence': [],
            'evaluation_timestamp': evaluation_timestamp
        }
    
    # Calculate component scores
    max_critical = max(r['risk_score'] for r in valid_results if get_signal_criticality(r['signal'], signal_registry) >= 3)
    
    weighted_scores = []
    for r in valid_results:
        criticality = get_signal_criticality(r['signal'], signal_registry)
        time_weight = calculate_time_decay(r['execution_timestamp'], evaluation_timestamp)
        weighted_scores.append(r['risk_score'] * criticality * time_weight)
    
    weighted_mean = np.mean(weighted_scores) if weighted_scores else 0
    
    # Multi-technique agreement bonus
    persistence_bonus = calculate_persistence_bonus(valid_results)
    
    # Trend penalty
    trend_penalty = calculate_trend_penalty(valid_results)
    
    # Aggregate
    system_score = min(
        0.4 * max_critical +
        0.3 * weighted_mean +
        0.2 * persistence_bonus +
        0.1 * trend_penalty,
        100
    )
    
    # Classify
    system_status = classify_status(system_score, valid_results)
    
    # Extract top evidence
    top_evidence = sorted(valid_results, key=lambda x: x['risk_score'], reverse=True)[:5]
    
    return {
        'unit': unit,
        'system': system_name,
        'system_score': round(system_score, 1),
        'system_status': system_status,
        'confidence': np.mean([r['confidence_score'] for r in valid_results]),
        'top_evidence': top_evidence,
        'evaluation_timestamp': evaluation_timestamp
    }


def aggregate_unit_health(
    system_results: list[dict],
    system_registry: dict
) -> dict:
    """
    Aggregate system-level results into unit-level health assessment.
    
    Parameters:
        - system_results: List of system health dicts for all systems in unit
        - system_registry: System metadata with criticality weights
        
    Returns:
        - dict: Unit health assessment with priority score and fleet ranking
    """
    unit = system_results[0]['unit'] if system_results else 'unknown'
    
    # Count system statuses
    critical_systems = [s for s in system_results if get_system_criticality(s['system'], system_registry) >= 3]
    
    n_anormal_critical = sum(1 for s in critical_systems if s['system_status'] == 'Anormal')
    n_anormal_other = sum(1 for s in system_results if s['system_status'] == 'Anormal') - n_anormal_critical
    n_alerta_critical = sum(1 for s in critical_systems if s['system_status'] == 'Alerta')
    n_alerta_other = sum(1 for s in system_results if s['system_status'] == 'Alerta') - n_alerta_critical
    
    # Priority score
    unit_score = np.mean([s['system_score'] for s in system_results])
    priority_score = (
        100 * n_anormal_critical +
        50 * n_anormal_other +
        20 * n_alerta_critical +
        10 * n_alerta_other +
        unit_score
    )
    
    # Overall status
    if n_anormal_critical >= 1 or (n_anormal_critical + n_anormal_other) >= 2:
        overall_status = 'Anormal'
    elif n_alerta_critical + n_alerta_other >= 1:
        overall_status = 'Alerta'
    else:
        overall_status = 'Normal'
    
    # Top risk systems
    top_risk_systems = sorted(system_results, key=lambda x: x['system_score'], reverse=True)[:3]
    
    return {
        'unit': unit,
        'overall_status': overall_status,
        'priority_score': round(priority_score, 1),
        'unit_score': round(unit_score, 1),
        'n_anormal_systems': n_anormal_critical + n_anormal_other,
        'n_alerta_systems': n_alerta_critical + n_alerta_other,
        'top_risk_systems': [s['system'] for s in top_risk_systems],
        'system_details': system_results
    }
```

---

## 7. LLM Integration for Natural Language Explanations

### Purpose

Transform numerical health assessments into **human-readable natural language explanations** that maintenance teams can understand and act upon without needing to interpret scores and statistical metrics.

### Architecture

The LLM integration uses the OpenAI API (configured via `.env` file) to generate contextual explanations at both system and unit levels.

```
Technique Results + System/Unit Health
        │
        ▼
  Prompt Builder (structured context)
        │
        ▼
  OpenAI API (gpt-4o-mini or gpt-4o)
        │
        ▼
  Natural Language Explanation
```

### Configuration

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LLM_CONFIG = {
    "model": "gpt-4o-mini",
    "temperature": 0.3,  # Low temperature for consistent, factual outputs
    "max_tokens": 1000,
}
```

### Implementation

#### System-Level Explanation

```python
def generate_system_explanation(
    system_health: dict,
    technique_results: list[dict],
    signal_registry: dict
) -> str:
    """
    Generate natural language explanation for a system health assessment.
    
    Parameters:
        - system_health: System aggregation result
        - technique_results: Detailed technique results for context
        - signal_registry: Signal metadata for display names
        
    Returns:
        - str: Natural language explanation
    """
    # Build structured context for the LLM
    context = build_system_context(system_health, technique_results, signal_registry)
    
    prompt = f"""You are a mining equipment health analyst. Based on the following telemetry analysis results, 
provide a concise explanation of the system health status for maintenance teams.

**System**: {system_health['system']}
**Unit**: {system_health['unit']}
**Status**: {system_health['system_status']}
**Score**: {system_health['system_score']}/100

**Evidence Summary**:
{context}

Provide:
1. A one-sentence summary of the system condition
2. Key findings (bullet points, max 3)
3. Recommended action (one sentence)

Keep language clear and actionable. Use signal display names, not codes.
Do not speculate beyond what the data shows."""

    response = client.chat.completions.create(
        model=LLM_CONFIG["model"],
        temperature=LLM_CONFIG["temperature"],
        max_tokens=LLM_CONFIG["max_tokens"],
        messages=[
            {"role": "system", "content": "You are a technical analyst for mining equipment health monitoring. Be concise, factual, and actionable."},
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content


def build_system_context(system_health: dict, technique_results: list[dict], signal_registry: dict) -> str:
    """Build structured text context from technique results."""
    lines = []
    
    for result in sorted(technique_results, key=lambda x: x['risk_score'], reverse=True)[:5]:
        signal_display = get_signal_display_name(result['signal'], signal_registry)
        lines.append(
            f"- {signal_display}: {result['technique']} detected {result['status']} "
            f"(risk={result['risk_score']}, confidence={result['confidence_score']}). "
            f"Evidence: {format_evidence(result['evidence'])}"
        )
    
    return "\n".join(lines)
```

#### Unit-Level Executive Summary

```python
def generate_unit_summary(
    unit_health: dict,
    system_healths: list[dict]
) -> str:
    """
    Generate executive summary for a unit health assessment.
    
    Parameters:
        - unit_health: Unit aggregation result
        - system_healths: All system health results for this unit
        
    Returns:
        - str: Executive summary for fleet management
    """
    
    systems_context = "\n".join([
        f"- {sh['system']}: {sh['system_status']} (score={sh['system_score']})"
        for sh in sorted(system_healths, key=lambda x: x['system_score'], reverse=True)
    ])
    
    prompt = f"""You are a fleet health analyst for mining equipment. Generate a brief executive summary.

**Unit**: {unit_health['unit']}
**Overall Status**: {unit_health['overall_status']}
**Priority Score**: {unit_health['priority_score']}

**System Breakdown**:
{systems_context}

Provide a 2-3 sentence executive summary suitable for a maintenance planning meeting.
Focus on: what's wrong, how urgent, and what to do next."""

    response = client.chat.completions.create(
        model=LLM_CONFIG["model"],
        temperature=LLM_CONFIG["temperature"],
        max_tokens=500,
        messages=[
            {"role": "system", "content": "You are a fleet health analyst. Be concise and actionable."},
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content
```

#### Batch Processing with Rate Limiting

```python
import time

def generate_fleet_explanations(
    unit_healths: list[dict],
    system_healths: dict,
    technique_results: dict,
    signal_registry: dict,
    rate_limit_delay: float = 0.5
) -> dict:
    """
    Generate explanations for all units in the fleet.
    
    Parameters:
        - unit_healths: List of unit health assessments
        - system_healths: Dict keyed by unit of system health lists
        - technique_results: Dict keyed by (unit, system) of technique results
        - signal_registry: Signal metadata
        - rate_limit_delay: Seconds between API calls (default: 0.5)
        
    Returns:
        - dict: {unit: {'unit_summary': str, 'system_explanations': {system: str}}}
    """
    explanations = {}
    
    for unit_health in unit_healths:
        unit = unit_health['unit']
        explanations[unit] = {'system_explanations': {}}
        
        # Generate system-level explanations (only for non-Normal systems)
        for system_health in system_healths.get(unit, []):
            if system_health['system_status'] != 'Normal':
                key = (unit, system_health['system'])
                results = technique_results.get(key, [])
                
                explanation = generate_system_explanation(
                    system_health, results, signal_registry
                )
                explanations[unit]['system_explanations'][system_health['system']] = explanation
                time.sleep(rate_limit_delay)
        
        # Generate unit-level summary
        explanations[unit]['unit_summary'] = generate_unit_summary(
            unit_health, system_healths.get(unit, [])
        )
        time.sleep(rate_limit_delay)
    
    return explanations
```

### Operational Considerations

**When to Generate Explanations:**
- After each aggregation cycle (weekly for full fleet)
- On-demand for specific units with status changes
- For fleet reports and maintenance planning meetings

**Cost Management:**
- Use `gpt-4o-mini` for routine explanations (low cost)
- Reserve `gpt-4o` for complex multi-system anomalies
- Batch requests and cache explanations for unchanged statuses
- Skip explanation generation for Normal units

**Quality Guidelines:**
- Temperature = 0.3 ensures factual, consistent outputs
- System prompt constrains analyst role and prevents speculation
- Evidence-based prompts ensure traceability
- Output validation: reject explanations that contradict scores

---

## Comprehensive Analysis Flow

### Orchestration Strategy

The complete analysis pipeline runs in a coordinated sequence:

```
Phase 1: Data Loading & Preprocessing
  └─ Load Silver telemetry data
  └─ Load configuration (signal_registry, equipment_registry)
  └─ Compute model specifications
  └─ Validate data quality

Phase 2: Baseline Management
  └─ Check baseline freshness (>45 days → refresh)
  └─ Load or compute baselines per model/state/signal
  └─ Store baseline version metadata

Phase 3: Technique Execution (parallelizable per unit)
  ├─ Deviation Analysis (daily cadence)
  ├─ Event Analysis (depends on deviation results)
  ├─ Trend Analysis (weekly cadence, 4/8/12 week windows)
  ├─ Distribution Shift Analysis (weekly cadence)
  └─ Autoencoder Inference (6-hour cadence)

Phase 4: Aggregation
  └─ Signal-level: Normalize technique results to risk/confidence
  └─ System-level: Aggregate signals within each system
  └─ Unit-level: Aggregate systems to fleet priority

Phase 5: Explanation Generation
  └─ Generate LLM explanations for non-Normal systems
  └─ Generate unit executive summaries
  └─ Compile fleet report

Phase 6: Output Persistence
  └─ Store technique results (partitioned by technique/time)
  └─ Store system/unit health (partitioned by week/client)
  └─ Store events (partitioned by day)
  └─ Store explanations (JSON alongside health outputs)
```

### Technique Interdependencies

```
                    Silver Data
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
     Deviation      Trend      Distribution
     Analysis      Analysis      Shift
            │                        
            ▼                        
       Event                    
       Analysis                 
            │                        
            ▼                        
     Autoencoder ◄── Uses normal labels from Deviation
            │
            ▼
    ┌───────────────┐
    │  Aggregation  │◄── All technique results
    └───────────────┘
            │
            ▼
    ┌───────────────┐
    │ LLM Explain   │◄── Aggregated health + evidence
    └───────────────┘
```

### Execution Cadences

| Component | Cadence | Trigger |
|-----------|---------|---------|
| Baseline Refresh | Monthly | First Sunday of month |
| Deviation + Events | Daily | New day boundary |
| Autoencoder Inference | Every 6 hours | Fixed schedule |
| Trend Analysis | Weekly | End of ISO week |
| Distribution Analysis | Weekly | End of ISO week |
| System/Unit Aggregation | After each technique run | Technique completion |
| LLM Explanations | Weekly (or on status change) | Aggregation completion |

---

## Implementation Best Practices

### 1. Data Quality Checks

Always validate input data before analysis:

```python
def validate_telemetry_data(df: pd.DataFrame) -> dict:
    """Run data quality checks on telemetry data."""
    issues = []
    
    # Check for required columns
    required_cols = [UNIT_COLNAME, TIME_COLNAME, STATE_COLNAME]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        issues.append(f"Missing columns: {missing_cols}")
    
    # Check timestamp ordering
    if TIME_COLNAME in df.columns:
        if not df[TIME_COLNAME].is_monotonic_increasing:
            issues.append("Timestamps not in ascending order")
    
    # Check for duplicate timestamps per unit
    if UNIT_COLNAME in df.columns and TIME_COLNAME in df.columns:
        duplicates = df.duplicated(subset=[UNIT_COLNAME, TIME_COLNAME]).sum()
        if duplicates > 0:
            issues.append(f"{duplicates} duplicate (unit, timestamp) pairs")
    
    # Check missing value rates
    missing_rates = df.isnull().mean()
    high_missing = missing_rates[missing_rates > 0.5].index.tolist()
    if high_missing:
        issues.append(f"Features with >50% missing: {high_missing}")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'n_rows': len(df),
        'n_features': len(df.columns),
        'time_range': (df[TIME_COLNAME].min(), df[TIME_COLNAME].max()) if TIME_COLNAME in df.columns else None
    }
```

### 2. Incremental Processing

For large datasets, process in chunks:

```python
def process_telemetry_in_chunks(
    file_paths: list,
    process_func: callable,
    chunk_weeks: int = 4
) -> pd.DataFrame:
    """Process telemetry data in weekly chunks to manage memory."""
    results = []
    
    for file_path in file_paths:
        df_chunk = pd.read_parquet(file_path)
        result_chunk = process_func(df_chunk)
        results.append(result_chunk)
        
        # Free memory
        del df_chunk
    
    return pd.concat(results, ignore_index=True)
```

### 3. Parallel Processing

Leverage multiprocessing for unit-level analyses:

```python
from multiprocessing import Pool, cpu_count

def analyze_unit_wrapper(args):
    """Wrapper for parallel unit analysis."""
    unit, df_unit, metadata = args
    # Run analysis for single unit
    return analyze_unit(df_unit, metadata)

def parallel_unit_analysis(df, metadata, n_workers=None):
    """Analyze units in parallel."""
    if n_workers is None:
        n_workers = cpu_count() - 1
    
    # Prepare arguments
    units = df[UNIT_COLNAME].unique()
    args = [(unit, df[df[UNIT_COLNAME] == unit], metadata) for unit in units]
    
    # Execute in parallel
    with Pool(n_workers) as pool:
        results = pool.map(analyze_unit_wrapper, args)
    
    return pd.concat(results, ignore_index=True)
```

### 4. Configuration Management

Store analysis parameters in configuration files:

```yaml
# analysis_config.yaml
deviation_analysis:
  baseline_weeks: 12
  percentiles: [1, 2, 5, 10, 25, 50, 75, 90, 95, 98, 99]
  min_unique_values: 10

event_analysis:
  binary_thresholds:
    spike_max_minutes: 5
    anomaly_max_minutes: 30
  weighted_thresholds:
    spike_max_points: 10
    anomaly_max_points: 30
  severity_weights:
    alert: 1
    anormal: 3
    critical: 5

trend_analysis:
  window_weeks: [4, 8, 12]
  rolling_window_minutes: 30
  p_value_threshold: 0.05
  r2_threshold: 0.3
  min_data_points: 10

distribution_analysis:
  baseline_weeks: 52
  observation_weeks: [4, 8, 12]
  p_value_threshold: 0.05
  min_baseline_samples: 100
  min_observation_samples: 30

anomaly_detection:
  sequence_length: 30
  quality_threshold: 0.10
  encoding_dim: 32
  epochs: 50
  batch_size: 32
  validation_split: 0.2
  early_stopping_patience: 10

aggregation:
  validity_periods:
    autoencoder_hours: 12
    deviation_days: 2
    event_days: 2
    distribution_days: 7
    trend_weeks: 4
  system_weights:
    max_critical: 0.4
    weighted_mean: 0.3
    persistence: 0.2
    trend: 0.1

llm:
  model: "gpt-4o-mini"
  temperature: 0.3
  max_tokens: 1000
  rate_limit_delay: 0.5
  skip_normal_units: true
```

### 5. Logging and Monitoring

Implement comprehensive logging:

```python
import logging

def setup_logger(log_file='telemetry_analysis.log'):
    """Configure logger for analysis pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logger()

# Usage in pipeline
logger.info(f"Starting deviation analysis for {len(units)} units")
logger.warning(f"Insufficient data for unit {unit}, skipping")
logger.error(f"Failed to compute limits: {str(e)}")
```

---

## Performance Considerations

### Computational Complexity

| Technique | Complexity | Bottleneck | Optimization |
|-----------|------------|------------|--------------|
| Deviation Analysis | O(n × m × s × f) | Percentile computation | Cache limits, vectorize |
| Event Analysis | O(n × u × f) | Grouping consecutive readings | Use NumPy cumsum |
| Trend Analysis | O(n × u × f × w) | Linear regression | Parallelize by unit |
| Distribution Shift | O(n log n × u × f × s × w) | Mann-Whitney U test | Filter low-data pairs |
| LSTM Anomaly Detection | O(n × u × sys) training<br>O(n) inference | Model training | GPU acceleration, parallelize |
| LLM Explanations | O(u × sys) | API latency | Batch, cache unchanged |

**Legend:**
- n = data points
- m = models
- s = states
- f = features
- u = units
- w = time windows
- sys = systems

### Memory Management

**Guidelines:**
- **Small datasets** (<1M rows): Load entire dataset into memory
- **Medium datasets** (1-10M rows): Process in weekly/monthly chunks
- **Large datasets** (>10M rows): Use Dask or PySpark for distributed processing

**Memory Estimation:**
```python
# Estimate memory usage
n_rows = 1_000_000
n_features = 50
memory_mb = (n_rows * n_features * 8) / (1024 ** 2)  # 8 bytes per float64
print(f"Estimated memory: {memory_mb:.1f} MB")
```

### Caching Strategies

```python
import joblib
from pathlib import Path

def load_or_compute_limits(df, metadata, cache_file='limits_cache.pkl'):
    """Load cached limits or compute if not available."""
    cache_path = Path(cache_file)
    
    if cache_path.exists():
        logger.info("Loading cached limits")
        return joblib.load(cache_path)
    else:
        logger.info("Computing limits (this may take a few minutes)")
        limits = compute_limits(df, metadata)
        joblib.dump(limits, cache_path)
        return limits
```

---

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue 1: Insufficient Data for Limits Computation

**Symptom**: Few or no limits computed for certain (model, state, feature) combinations

**Causes:**
- Unit operated in specific state for <10 unique values
- Feature has constant value (e.g., sensor malfunction)
- Incorrect model_specification mapping

**Solutions:**
```python
# Diagnose missing limits
for model in limits.keys():
    for feature in telemetry_metadata['signals']:
        feature_name = feature['name']
        if feature_name not in limits[model]:
            logger.warning(f"No limits for {model} | {feature_name}")
            # Check data availability
            data = df[(df['model_specification'] == model)][feature_name].dropna()
            print(f"  Unique values: {data.nunique()}, Total samples: {len(data)}")
```

#### Issue 2: Event Analysis Produces Too Many Spikes

**Symptom**: Overwhelming number of short-duration events

**Causes:**
- Noisy sensors causing frequent threshold crossings
- Thresholds too tight (P95 catches normal variability)

**Solutions:**
- Increase spike threshold from 5 to 10 minutes
- Apply hysteresis to threshold comparisons
- Use weighted model to filter low-severity spikes

#### Issue 3: Trend Analysis Shows No Significant Trends

**Symptom**: Most trends have p-value > 0.05 or R² < 0.3

**Causes:**
- High signal noise overwhelming linear signal
- Equipment in steady-state operation (expected)
- Rolling window too small (increase from 30 to 60 minutes)

**Solutions:**
- Increase rolling window size to reduce noise
- Lower R² threshold for exploratory analysis (e.g., 0.2)
- Focus on worsening trends even if R² is moderate

#### Issue 4: Distribution Shift Analysis Requires Too Much Data

**Symptom**: Many unit-feature-state combinations skipped due to insufficient baseline data

**Causes:**
- New equipment with <1 year history
- State rarely occupied (e.g., "Maintenance" mode)

**Solutions:**
```python
# Reduce baseline requirement for new equipment
def adaptive_baseline_weeks(unit, df):
    """Use shorter baseline for new units."""
    unit_data = df[df[UNIT_COLNAME] == unit]
    data_weeks = (unit_data[TIME_COLNAME].max() - unit_data[TIME_COLNAME].min()).days / 7
    
    if data_weeks < 52:
        return max(12, data_weeks * 0.7)  # Use 70% as baseline, minimum 12 weeks
    else:
        return 52
```

#### Issue 5: LSTM Autoencoder Training Fails

**Symptom**: Model training returns None or validation loss doesn't decrease

**Causes:**
- Insufficient normal sequences (<100)
- All features in system have same value (no variability)
- NaN values not properly handled

**Solutions:**
```python
# Debug LSTM training
logger.info(f"Training {unit} | {system}: {len(sequences)} sequences")
if len(sequences) < 100:
    logger.warning(f"  Insufficient sequences, need ≥100, got {len(sequences)}")
    return None

# Check for zero variance
feature_stds = sequences.std(axis=(0, 1))
zero_variance_features = np.where(feature_stds == 0)[0]
if len(zero_variance_features) > 0:
    logger.warning(f"  Zero variance features: {zero_variance_features}")
    # Remove constant features
    sequences = np.delete(sequences, zero_variance_features, axis=2)
```

#### Issue 6: LLM Explanations Are Inconsistent

**Symptom**: Generated explanations contradict scores or hallucinate issues

**Solutions:**
- Lower temperature to 0.1-0.2 for more deterministic outputs
- Validate output against input scores (reject if contradictory)
- Include explicit constraints in system prompt
- Use structured output format (JSON) and parse programmatically

---

## Summary

This telemetry analysis pipeline implements five complementary techniques combined with multi-level aggregation and LLM-powered explanations to provide comprehensive equipment health monitoring:

1. **Deviation Analysis**: Real-time threshold-based anomaly detection
2. **Event Analysis**: Temporal pattern recognition and alert prioritization
3. **Trend Analysis**: Progressive degradation and improvement tracking
4. **Distribution Shift Analysis**: Population-level behavior change detection
5. **LSTM Anomaly Detection**: Multi-signal pattern anomaly identification
6. **Multi-Technique Aggregation**: Signal → System → Unit health hierarchy
7. **LLM Integration**: Natural language explanations for maintenance teams

**Execution Flow:**
1. Establish baselines using 12+ weeks of historical data
2. Apply Deviation Analysis for daily monitoring
3. Use Event Analysis to filter and prioritize alerts
4. Run Trend/Distribution Analysis weekly for proactive maintenance
5. Deploy LSTM models for 6-hourly multivariate pattern monitoring
6. Aggregate all results into system and unit health scores
7. Generate LLM explanations for non-Normal assessments
8. Output fleet priority ranking for maintenance planning

---

**Document Version**: 2.0  
**Last Updated**: June 2026  
**Maintained by**: Patricio Ortiz
