# Telemetry Analysis - Integration Plan

**Version**: 1.0.0  
**Last Updated**: February 23, 2026  
**Component**: Implementation Roadmap

---

## 📋 Table of Contents

1. [Integration Overview](#integration-overview)
2. [Data Reading Strategy](#data-reading-strategy)
3. [Data Cleaning & Validation](#data-cleaning--validation)
4. [Phase 1: MVP Implementation](#phase-1-mvp-implementation)
5. [Phase 2: Advanced Integrations](#phase-2-advanced-integrations)
7. [Deployment & Operations](#deployment--operations)

---

## 🎯 Integration Overview

### Implementation Phases

```
Phase 1: MVP (Weeks 1-4)
├── Data reading and validation
├── Baseline percentile computation
├── Severity-weighted window scoring
├── Component & machine aggregation
└── Golden layer output generation

Phase 2: Advanced Integrations (Weeks 5-12)
├── 2A: LLM Integration (Weeks 5-6)
│   └── OpenAI-based AI recommendations
├── 2B: LSTM Autoencoder (Weeks 7-9)
│   └── Deep learning anomaly detection
└── 2C: Time Series Forecasting (Weeks 10-12)
    └── Predictive alert generation
```

### Success Criteria

**Phase 1 (MVP)**:
- ✅ Process 1 week of telemetry data in <5 minutes
- ✅ Generate `machine_status.parquet` and `classified.parquet`
- ✅ 100% of units evaluated (no crashes on missing data)
- ✅ Reproducible outputs (same inputs → same results)
- ✅ Dashboard can load and display all visualizations

**Phase 2**:
- ✅ AI recommendations generated for all Anormal/Alerta components
- ✅ LSTM model detects known failure patterns with >85% accuracy
- ✅ Forecasting predicts next-week status with >70% accuracy

---

## 📂 Data Reading Strategy

### Input Data Structure

**Silver Layer Partitioning**:
```
data/telemetry/silver/cda/Telemetry_Wide_With_States/
├── Week01Year2026.parquet
├── Week02Year2026.parquet
├── ...
├── Week08Year2026.parquet  ← Current evaluation week
└── ...
```

**Partition Naming Convention**:
- Format: `Week{WW:02d}Year{YYYY}.parquet`
- `WW`: Week number (01-52), zero-padded
- `YYYY`: 4-digit year

### Reading Current Evaluation Window

**Pseudocode**:
```python
def load_evaluation_week(client: str, week: int, year: int) -> pd.DataFrame:
    """
    Load telemetry data for a specific week.
    
    Args:
        client: Client identifier (e.g., 'cda')
        week: Week number (1-52)
        year: Year (e.g., 2026)
    
    Returns:
        DataFrame with columns: Fecha, Unit, EstadoMaquina, signal columns
    """
    file_path = (
        f"data/telemetry/silver/{client}/"
        f"Telemetry_Wide_With_States/Week{week:02d}Year{year}.parquet"
    )
    
    # Read parquet with explicit schema validation
    df = pd.read_parquet(file_path, engine='pyarrow')
    
    # Ensure required columns exist
    required_cols = ['Fecha', 'Unit', 'EstadoMaquina']
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Sort by timestamp for consistent processing
    df = df.sort_values(['Unit', 'Fecha']).reset_index(drop=True)
    
    return df
```

### Reading Historical Baseline Window

**Training Window**: 90 days (approximately 13 weeks) before evaluation week

**Pseudocode**:
```python
def load_baseline_training_window(
    client: str, 
    end_week: int, 
    end_year: int, 
    lookback_days: int = 90
) -> pd.DataFrame:
    """
    Load historical data for baseline computation.
    
    Args:
        client: Client identifier
        end_week: Last week to include (evaluation week - 1)
        end_year: Year of end_week
        lookback_days: Number of days to look back (default: 90)
    
    Returns:
        Concatenated DataFrame of all weeks in training window
    """
    from datetime import datetime, timedelta
    
    # Calculate start/end dates
    end_date = datetime.strptime(f"{end_year}-W{end_week:02d}-1", "%Y-W%W-%w")
    start_date = end_date - timedelta(days=lookback_days)
    
    # Identify week/year pairs to load
    weeks_to_load = []
    current_date = start_date
    while current_date < end_date:
        week = current_date.isocalendar()[1]
        year = current_date.year
        weeks_to_load.append((week, year))
        current_date += timedelta(weeks=1)
    
    # Read and concatenate all partitions
    dfs = []
    for week, year in weeks_to_load:
        file_path = (
            f"data/telemetry/silver/{client}/"
            f"Telemetry_Wide_With_States/Week{week:02d}Year{year}.parquet"
        )
        if os.path.exists(file_path):
            df = pd.read_parquet(file_path)
            dfs.append(df)
        else:
            logger.warning(f"Missing baseline file: {file_path}")
    
    if not dfs:
        raise ValueError("No baseline data available for training window")
    
    baseline_df = pd.concat(dfs, ignore_index=True)
    baseline_df = baseline_df.sort_values(['Unit', 'Fecha']).reset_index(drop=True)
    
    return baseline_df
```

### Loading Component-Signal Mapping

**Mapping File**: `data/telemetry/component_signals_mapping.json`

**Expected Format**:
```json
{
  "Engine": {
    "signals": ["EngCoolTemp", "EngOilPres", "EngSpeed", "EngOilTemp"],
    "criticality": 3
  },
  "Transmission": {
    "signals": ["TransOilTemp", "TransOilPres", "GearPos"],
    "criticality": 3
  },
  "Hydraulic": {
    "signals": ["HydOilTemp", "HydOilPres", "HydPumpSpeed"],
    "criticality": 2
  },
  "Brakes": {
    "signals": ["BrakePres", "BrakeTemp"],
    "criticality": 3
  },
  "Electrical": {
    "signals": ["BattVolt", "AltOutput"],
    "criticality": 1
  }
}
```

**Pseudocode**:
```python
def load_component_mapping(client: str) -> dict:
    """Load component-to-signals mapping."""
    file_path = "data/telemetry/component_signals_mapping.json"
    
    with open(file_path, 'r') as f:
        mapping = json.load(f)
    
    # Validate structure
    for component, config in mapping.items():
        if 'signals' not in config or 'criticality' not in config:
            raise ValueError(f"Invalid mapping for component: {component}")
    
    return mapping
```

---

## 🧹 Data Cleaning & Validation

### Validation Rules

**1. Timestamp Validation**

```python
def validate_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure timestamps are valid and chronologically ordered.
    """
    # Check for null timestamps
    null_timestamps = df['Fecha'].isnull().sum()
    if null_timestamps > 0:
        logger.warning(f"Found {null_timestamps} null timestamps, dropping rows")
        df = df.dropna(subset=['Fecha'])
    
    # Ensure datetime type
    if not pd.api.types.is_datetime64_any_dtype(df['Fecha']):
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])
    
    # Check for future timestamps
    max_date = df['Fecha'].max()
    if max_date > pd.Timestamp.now():
        logger.warning(f"Found future timestamps (max: {max_date}), likely data issue")
    
    # Sort by unit and timestamp
    df = df.sort_values(['Unit', 'Fecha']).reset_index(drop=True)
    
    return df
```

**2. Duplicate Detection**

```python
def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate rows based on (Unit, Fecha).
    """
    initial_count = len(df)
    
    # Identify duplicates
    duplicates = df.duplicated(subset=['Unit', 'Fecha'], keep='first')
    dup_count = duplicates.sum()
    
    if dup_count > 0:
        logger.warning(f"Found {dup_count} duplicate records, keeping first occurrence")
        df = df[~duplicates]
    
    logger.info(f"Rows after deduplication: {len(df)} (removed {initial_count - len(df)})")
    
    return df
```

**3. Missingness Handling**

```python
def handle_missing_values(df: pd.DataFrame, signal_cols: list) -> pd.DataFrame:
    """
    Handle missing values in signal columns.
    
    Strategy:
    - If >50% missing for a signal in a unit → exclude that signal from evaluation
    - If <50% missing → forward fill first, then backward fill, then drop remaining
    """
    for unit in df['Unit'].unique():
        unit_mask = df['Unit'] == unit
        
        for signal in signal_cols:
            if signal not in df.columns:
                continue
            
            missing_pct = df.loc[unit_mask, signal].isnull().mean()
            
            if missing_pct > 0.5:
                logger.warning(
                    f"Unit {unit}, Signal {signal}: {missing_pct*100:.1f}% missing, "
                    "excluding from evaluation"
                )
                df.loc[unit_mask, signal] = np.nan  # Mark for exclusion
            elif missing_pct > 0:
                # Forward fill then backward fill
                df.loc[unit_mask, signal] = (
                    df.loc[unit_mask, signal]
                    .fillna(method='ffill')
                    .fillna(method='bfill')
                )
    
    return df
```

**4. Outlier Detection (Extreme Values)**

```python
def flag_extreme_outliers(
    df: pd.DataFrame, 
    signal: str, 
    z_threshold: float = 10
) -> pd.DataFrame:
    """
    Flag physically impossible values (e.g., negative pressure, >200°C coolant).
    
    Uses z-score method with high threshold to catch only extreme sensor errors.
    """
    if signal not in df.columns:
        return df
    
    # Calculate z-scores
    mean_val = df[signal].mean()
    std_val = df[signal].std()
    
    if std_val > 0:
        z_scores = np.abs((df[signal] - mean_val) / std_val)
        outliers = z_scores > z_threshold
        
        outlier_count = outliers.sum()
        if outlier_count > 0:
            logger.warning(
                f"Signal {signal}: {outlier_count} extreme outliers detected "
                f"(z-score > {z_threshold}), replacing with NaN"
            )
            df.loc[outliers, signal] = np.nan
    
    return df
```

**5. State Validation**

```python
def validate_operational_states(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure EstadoMaquina contains valid states.
    """
    valid_states = ['Operacional', 'Ralenti', 'Apagada', 'Unknown']
    
    invalid_mask = ~df['EstadoMaquina'].isin(valid_states)
    invalid_count = invalid_mask.sum()
    
    if invalid_count > 0:
        logger.warning(
            f"Found {invalid_count} rows with invalid states, "
            "setting to 'Unknown'"
        )
        df.loc[invalid_mask, 'EstadoMaquina'] = 'Unknown'
    
    return df
```

### Complete Data Cleaning Pipeline

```python
def clean_telemetry_data(
    df: pd.DataFrame, 
    signal_cols: list
) -> pd.DataFrame:
    """
    Execute full data cleaning pipeline.
    """
    logger.info(f"Starting data cleaning: {len(df)} rows")
    
    # Step 1: Validate timestamps
    df = validate_timestamps(df)
    
    # Step 2: Remove duplicates
    df = remove_duplicates(df)
    
    # Step 3: Validate operational states
    df = validate_operational_states(df)
    
    # Step 4: Handle missing values
    df = handle_missing_values(df, signal_cols)
    
    # Step 5: Flag extreme outliers
    for signal in signal_cols:
        df = flag_extreme_outliers(df, signal, z_threshold=10)
    
    logger.info(f"Data cleaning complete: {len(df)} rows")
    
    return df
```

---

## 🚀 Phase 1: MVP Implementation

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT: Silver Layer (Week parquet)                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Data Loading & Cleaning                            │
│  • Load current week partition                              │
│  • Validate timestamps, deduplicate, handle missing         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Baseline Computation/Loading                       │
│  • Load historical 90-day window                            │
│  • Compute percentiles per (unit, signal, state)            │
│  • Save baseline file                                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Signal Evaluation                                  │
│  • For each (unit, signal):                                 │
│    - Score each reading against baseline percentiles        │
│    - Compute window_score_normalized                        │
│    - Classify: Normal / Alerta / Anormal                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Component Aggregation                              │
│  • Group signals by component                               │
│  • Compute component_score (max of signal scores)           │
│  • Determine component_status                               │
│  • Collect triggering signals                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Machine Aggregation                                │
│  • Aggregate components → machine_score                     │
│  • Determine overall_status                                 │
│  • Calculate priority_score                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 6: Output Generation                                  │
│  • Write machine_status.parquet                             │
│  • Write classified.parquet                                 │
└─────────────────────────────────────────────────────────────┘
```

---

### Step 1: Baseline Computation

**Objective**: Calculate historical percentiles for each signal

**Pseudocode**:
```python
def compute_baseline_percentiles(
    training_df: pd.DataFrame,
    component_mapping: dict,
    client: str,
    baseline_date: str
) -> pd.DataFrame:
    """
    Compute percentile thresholds for all signals.
    
    Returns:
        DataFrame with schema:
        [unit_id, signal, state, p2, p5, p95, p98, sample_count, 
         training_start, training_end]
    """
    signal_cols = []
    for comp_config in component_mapping.values():
        signal_cols.extend(comp_config['signals'])
    signal_cols = list(set(signal_cols))  # Deduplicate
    
    # Filter to existing columns
    signal_cols = [s for s in signal_cols if s in training_df.columns]
    
    baseline_records = []
    
    for unit in training_df['Unit'].unique():
        unit_data = training_df[training_df['Unit'] == unit]
        
        for signal in signal_cols:
            # Skip signals with too many missing values
            if unit_data[signal].isnull().mean() > 0.5:
                continue
            
            # Compute state-specific percentiles
            for state in ['Operacional', 'Ralenti', 'Apagada']:
                state_data = unit_data[unit_data['EstadoMaquina'] == state]
                
                if len(state_data) < 100:  # Minimum sample threshold
                    continue
                
                signal_values = state_data[signal].dropna()
                
                if len(signal_values) < 100:
                    continue
                
                # Compute percentiles
                p2 = signal_values.quantile(0.02)
                p5 = signal_values.quantile(0.05)
                p95 = signal_values.quantile(0.95)
                p98 = signal_values.quantile(0.98)
                
                baseline_records.append({
                    'unit_id': unit,
                    'signal': signal,
                    'state': state,
                    'p2': p2,
                    'p5': p5,
                    'p95': p95,
                    'p98': p98,
                    'sample_count': len(signal_values),
                    'training_start': training_df['Fecha'].min(),
                    'training_end': training_df['Fecha'].max()
                })
    
    baseline_df = pd.DataFrame(baseline_records)
    
    # Save to Golden layer
    output_path = f"data/telemetry/golden/{client}/baselines/baseline_{baseline_date}.parquet"
    baseline_df.to_parquet(output_path, index=False)
    
    return baseline_df
```

---

### Step 2: Signal Evaluation

**Objective**: Score each signal reading and classify status

**Pseudocode**:
```python
def evaluate_signals(
    current_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    component_mapping: dict
) -> pd.DataFrame:
    """
    Evaluate all signals against baselines.
    
    Returns:
        DataFrame with schema:
        [unit, signal, window_score_normalized, signal_status, 
         anomaly_percentage, observed_min, observed_max, baseline_info]
    """
    signal_cols = []
    for comp_config in component_mapping.values():
        signal_cols.extend(comp_config['signals'])
    signal_cols = list(set(signal_cols))
    
    evaluation_records = []
    
    for unit in current_df['Unit'].unique():
        unit_data = current_df[current_df['Unit'] == unit]
        
        for signal in signal_cols:
            if signal not in current_df.columns:
                continue
            
            # Get baseline for this unit-signal combination
            # Try state-specific baseline first, fall back to aggregate
            baseline_rows = baseline_df[
                (baseline_df['unit_id'] == unit) &
                (baseline_df['signal'] == signal)
            ]
            
            if len(baseline_rows) == 0:
                logger.warning(f"No baseline for {unit}/{signal}, skipping")
                continue
            
            # Score each reading
            point_scores = []
            
            for idx, row in unit_data.iterrows():
                value = row[signal]
                state = row['EstadoMaquina']
                
                if pd.isna(value):
                    continue
                
                # Get state-specific baseline if available
                state_baseline = baseline_rows[baseline_rows['state'] == state]
                if len(state_baseline) == 0:
                    # Fall back to any available baseline for this signal
                    state_baseline = baseline_rows.iloc[0:1]
                else:
                    state_baseline = state_baseline.iloc[0:1]
                
                p2 = state_baseline['p2'].values[0]
                p5 = state_baseline['p5'].values[0]
                p95 = state_baseline['p95'].values[0]
                p98 = state_baseline['p98'].values[0]
                
                # Assign severity score
                if p5 <= value <= p95:
                    score = 0  # Normal
                elif (p2 <= value < p5) or (p95 < value <= p98):
                    score = 1  # Alert
                else:  # value < p2 or value > p98
                    score = 3  # Alarm
                
                point_scores.append(score)
            
            if len(point_scores) == 0:
                continue
            
            # Compute window score
            window_score_normalized = np.mean(point_scores)
            
            # Classify signal status
            if window_score_normalized < 0.2:
                signal_status = 'Normal'
            elif window_score_normalized < 0.4:
                signal_status = 'Alerta'
            else:
                signal_status = 'Anormal'
            
            # Calculate anomaly percentage (% outside P5-P95)
            signal_values = unit_data[signal].dropna()
            baseline_primary = baseline_rows.iloc[0]
            p5_ref = baseline_primary['p5']
            p95_ref = baseline_primary['p95']
            anomaly_pct = ((signal_values < p5_ref) | (signal_values > p95_ref)).mean() * 100
            
            evaluation_records.append({
                'unit': unit,
                'signal': signal,
                'window_score_normalized': window_score_normalized,
                'signal_status': signal_status,
                'anomaly_percentage': anomaly_pct,
                'observed_min': signal_values.min(),
                'observed_max': signal_values.max(),
                'observed_mean': signal_values.mean(),
                'baseline': {
                    'p2': baseline_primary['p2'],
                    'p5': baseline_primary['p5'],
                    'p95': baseline_primary['p95'],
                    'p98': baseline_primary['p98']
                }
            })
    
    evaluation_df = pd.DataFrame(evaluation_records)
    return evaluation_df
```

---

### Step 3: Component Aggregation

**Objective**: Aggregate signal scores to component level using weighted severity approach

**Pseudocode**:
```python
def aggregate_to_components(
    signal_evaluation_df: pd.DataFrame,
    component_mapping: dict,
    current_df: pd.DataFrame  # Added: for coverage calculation
) -> pd.DataFrame:
    """
    Aggregate signals to component-level status using weighted severity scoring.
    
    Returns:
        DataFrame with schema:
        [unit, component, component_status, component_score, 
         component_coverage, triggering_signals, signals_evaluation]
    """
    # Severity mapping
    SEVERITY_MAP = {
        'Normal': 0.0,
        'Alerta': 0.3,
        'Anormal': 1.0
    }
    
    # Component score thresholds
    THRESHOLD_NORMAL = 0.15
    THRESHOLD_ANORMAL = 0.45
    MIN_COVERAGE = 0.5
    
    component_records = []
    
    for unit in signal_evaluation_df['unit'].unique():
        unit_signals = signal_evaluation_df[signal_evaluation_df['unit'] == unit]
        unit_raw_data = current_df[current_df['Unit'] == unit]
        
        for component, config in component_mapping.items():
            component_signals = config['signals']
            
            # Filter to signals in this component
            comp_signal_evals = unit_signals[
                unit_signals['signal'].isin(component_signals)
            ]
            
            if len(comp_signal_evals) == 0:
                continue
            
            # Calculate signal weights based on data coverage
            signal_weights = {}
            for signal in component_signals:
                if signal not in comp_signal_evals['signal'].values:
                    signal_weights[signal] = 0.0
                    continue
                
                # Check data coverage for this signal
                if signal in unit_raw_data.columns:
                    coverage = unit_raw_data[signal].notna().mean()
                    signal_weights[signal] = 1.0 if coverage >= 0.5 else 0.0
                else:
                    signal_weights[signal] = 0.0
            
            # Calculate component coverage
            total_mapped_signals = len(component_signals)
            signals_with_data = sum(1 for w in signal_weights.values() if w > 0)
            component_coverage = signals_with_data / total_mapped_signals if total_mapped_signals > 0 else 0.0
            
            # Calculate weighted severity score
            weighted_severity_sum = 0.0
            total_weight = 0.0
            
            for _, signal_row in comp_signal_evals.iterrows():
                signal_name = signal_row['signal']
                weight = signal_weights.get(signal_name, 0.0)
                
                if weight > 0:
                    severity = SEVERITY_MAP.get(signal_row['signal_status'], 0.0)
                    weighted_severity_sum += weight * severity
                    total_weight += weight
            
            # Compute component score
            if total_weight > 0:
                component_score = weighted_severity_sum / total_weight
            else:
                component_score = 0.0
            
            # Determine component status
            if component_coverage < MIN_COVERAGE:
                # Insufficient data: conservative approach
                component_status = 'Alerta'  # Or 'InsufficientData' if using that status
                logger.warning(
                    f"Unit {unit}, Component {component}: Low coverage ({component_coverage:.1%}), "
                    f"marking as Alerta"
                )
            elif component_score < THRESHOLD_NORMAL:
                component_status = 'Normal'
            elif component_score < THRESHOLD_ANORMAL:
                component_status = 'Alerta'
            else:
                component_status = 'Anormal'
            
            # Identify triggering signals (non-Normal)
            triggering = comp_signal_evals[
                comp_signal_evals['signal_status'] != 'Normal'
            ]['signal'].tolist()
            
            # Package signal evaluation details
            signals_evaluation = {}
            for _, signal_row in comp_signal_evals.iterrows():
                signal_name = signal_row['signal']
                signals_evaluation[signal_name] = {
                    'status': signal_row['signal_status'],
                    'window_score': signal_row['window_score_normalized'],
                    'severity': SEVERITY_MAP.get(signal_row['signal_status'], 0.0),
                    'weight': signal_weights.get(signal_name, 0.0),
                    'baseline': signal_row['baseline'],
                    'observed_range': [
                        signal_row['observed_min'],
                        signal_row['observed_max']
                    ],
                    'anomaly_percentage': signal_row['anomaly_percentage']
                }
            
            component_records.append({
                'unit': unit,
                'component': component,
                'component_status': component_status,
                'component_score': component_score,
                'component_coverage': component_coverage,
                'triggering_signals': triggering,
                'signals_evaluation': signals_evaluation,
                'signal_weights': signal_weights,
                'criticality': config['criticality']
            })
    
    component_df = pd.DataFrame(component_records)
    return component_df
```

---

### Step 4: Machine Aggregation

**Objective**: Aggregate all components to machine-level status

**Pseudocode**:
```python
def aggregate_to_machines(
    component_df: pd.DataFrame,
    client: str,
    week: int,
    year: int,
    latest_sample: pd.Timestamp,
    baseline_version: str
) -> pd.DataFrame:
    """
    Aggregate components to machine-level status.
    
    Returns:
        DataFrame with schema from machine_status specification
    """
    machine_records = []
    
    for unit in component_df['unit'].unique():
        unit_components = component_df[component_df['unit'] == unit]
        
        # Count components by status
        components_normal = (unit_components['component_status'] == 'Normal').sum()
        components_alerta = (unit_components['component_status'] == 'Alerta').sum()
        components_anormal = (unit_components['component_status'] == 'Anormal').sum()
        
        # Overall status = worst component
        if components_anormal > 0:
            overall_status = 'Anormal'
        elif components_alerta > 0:
            overall_status = 'Alerta'
        else:
            overall_status = 'Normal'
        
        # Machine score = sum of (criticality-weighted component scores)
        machine_score = (
            unit_components['component_score'] * 
            unit_components['criticality']
        ).sum()
        
        # Priority score = weighting formula
        priority_score = (
            100 * components_anormal +
            10 * components_alerta +
            machine_score
        )
        
        # Package component details
        component_details = []
        for _, comp_row in unit_components.iterrows():
            component_details.append({
                'component': comp_row['component'],
                'status': comp_row['component_status'],
                'score': comp_row['component_score'],
                'triggering_signals': comp_row['triggering_signals'],
                'signal_details': comp_row['signals_evaluation']
            })
        
        machine_records.append({
            'unit_id': unit,
            'client': client,
            'evaluation_week': week,
            'evaluation_year': year,
            'latest_sample_date': latest_sample,
            'overall_status': overall_status,
            'machine_score': machine_score,
            'total_components': len(unit_components),
            'components_normal': components_normal,
            'components_alerta': components_alerta,
            'components_anormal': components_anormal,
            'priority_score': priority_score,
            'component_details': component_details,
            'baseline_version': baseline_version
        })
    
    machine_df = pd.DataFrame(machine_records)
    return machine_df
```

---

### Step 5: Output Generation

**Objective**: Write Golden layer files

**Pseudocode**:
```python
def write_golden_outputs(
    machine_df: pd.DataFrame,
    component_df: pd.DataFrame,
    client: str
) -> None:
    """
    Write machine_status and classified outputs.
    """
    # Ensure golden directory exists
    golden_dir = f"data/telemetry/golden/{client}"
    os.makedirs(golden_dir, exist_ok=True)
    
    # Write machine_status.parquet
    machine_output_path = f"{golden_dir}/machine_status.parquet"
    machine_df.to_parquet(machine_output_path, index=False)
    logger.info(f"Wrote machine_status: {machine_output_path}")
    
    # Prepare classified.parquet (expand component_df with needed fields)
    classified_df = component_df.copy()
    classified_df.rename(columns={'unit': 'unit'}, inplace=True)
    classified_df['client'] = client
    classified_df['evaluation_week'] = machine_df['evaluation_week'].iloc[0]
    classified_df['evaluation_year'] = machine_df['evaluation_year'].iloc[0]
    classified_df['date'] = machine_df['latest_sample_date'].iloc[0]
    classified_df['ai_recommendation'] = None  # Phase 2
    classified_df['baseline_version'] = machine_df['baseline_version'].iloc[0]
    
    # Write classified.parquet
    classified_output_path = f"{golden_dir}/classified.parquet"
    classified_df.to_parquet(classified_output_path, index=False)
    logger.info(f"Wrote classified: {classified_output_path}")
```

---

### Main Pipeline Orchestration

**Complete MVP Pipeline**:

```python
def run_telemetry_pipeline(
    client: str,
    week: int,
    year: int,
    recompute_baseline: bool = False
) -> None:
    """
    Execute complete telemetry analysis pipeline.
    
    Args:
        client: Client identifier
        week: Evaluation week number
        year: Evaluation year
        recompute_baseline: If True, recompute baseline from scratch
    """
    logger.info(f"Starting telemetry pipeline: {client} Week {week}/{year}")
    
    # STEP 1: Load data
    logger.info("Step 1: Loading evaluation week data")
    current_df = load_evaluation_week(client, week, year)
    
    # Load component mapping
    component_mapping = load_component_mapping(client)
    
    # Clean data
    signal_cols = []
    for config in component_mapping.values():
        signal_cols.extend(config['signals'])
    signal_cols = list(set(signal_cols))
    
    current_df = clean_telemetry_data(current_df, signal_cols)
    
    # STEP 2: Baseline computation/loading
    logger.info("Step 2: Computing/loading baseline")
    baseline_date = f"{year}{week:02d}01"  # YYYYWWDD format
    baseline_path = f"data/telemetry/golden/{client}/baselines/baseline_{baseline_date}.parquet"
    
    if recompute_baseline or not os.path.exists(baseline_path):
        logger.info("Computing new baseline from historical data")
        training_df = load_baseline_training_window(client, week - 1, year, lookback_days=90)
        training_df = clean_telemetry_data(training_df, signal_cols)
        baseline_df = compute_baseline_percentiles(
            training_df, component_mapping, client, baseline_date
        )
    else:
        logger.info(f"Loading existing baseline: {baseline_path}")
        baseline_df = pd.read_parquet(baseline_path)
    
    # STEP 3: Signal evaluation
    logger.info("Step 3: Evaluating signals")
    signal_evaluation_df = evaluate_signals(
        current_df, baseline_df, component_mapping
    )
    
    # STEP 4: Component aggregation
    logger.info("Step 4: Aggregating to components")
    component_df = aggregate_to_components(
        signal_evaluation_df, component_mapping, current_df
    )
    
    # STEP 5: Machine aggregation
    logger.info("Step 5: Aggregating to machines")
    latest_sample = current_df['Fecha'].max()
    machine_df = aggregate_to_machines(
        component_df, client, week, year, latest_sample, baseline_date
    )
    
    # STEP 6: Write outputs
    logger.info("Step 6: Writing golden layer outputs")
    write_golden_outputs(machine_df, component_df, client)
    
    logger.info("Pipeline complete!")
    logger.info(f"  - Evaluated {len(machine_df)} units")
    logger.info(f"  - Total components: {len(component_df)}")
    logger.info(f"  - Status breakdown:")
    logger.info(f"      Normal: {(machine_df['overall_status'] == 'Normal').sum()}")
    logger.info(f"      Alerta: {(machine_df['overall_status'] == 'Alerta').sum()}")
    logger.info(f"      Anormal: {(machine_df['overall_status'] == 'Anormal').sum()}")
```

---

## 🧠 Phase 2: Advanced Integrations

### Phase 2A: LLM Integration (OpenAI)

**Objective**: Generate AI-powered maintenance recommendations

**Changes to Pipeline**:
- Add new step after component aggregation: `generate_ai_recommendations()`
- Populate `ai_recommendation` field in `classified.parquet`

**Implementation**:

```python
import openai

def generate_ai_recommendations(component_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate LLM-based recommendations for Alerta/Anormal components.
    
    Uses OpenAI GPT-4 to analyze signal deviations and suggest actions.
    """
    for idx, row in component_df.iterrows():
        if row['component_status'] == 'Normal':
            component_df.at[idx, 'ai_recommendation'] = None
            continue
        
        # Build prompt from evaluation evidence
        prompt = f"""
You are a mining equipment maintenance expert. Analyze the following component health data and provide a concise maintenance recommendation.

**Component**: {row['component']}
**Status**: {row['component_status']}
**Component Score**: {row['component_score']:.2f}
**Triggering Signals**: {', '.join(row['triggering_signals'])}

**Signal Details**:
"""
        for signal_name, signal_data in row['signals_evaluation'].items():
            if signal_data['status'] != 'Normal':
                prompt += f"""
- {signal_name}:
  - Status: {signal_data['status']}
  - Window Score: {signal_data['window_score']:.2f}
  - Observed Range: {signal_data['observed_range'][0]:.1f} to {signal_data['observed_range'][1]:.1f}
  - Baseline (P5-P95): {signal_data['baseline']['p5']:.1f} to {signal_data['baseline']['p95']:.1f}
  - Anomaly Percentage: {signal_data['anomaly_percentage']:.1f}%
"""
        
        prompt += """
Provide:
1. Likely root cause (1-2 sentences)
2. Recommended inspection actions (2-3 bullet points)
3. Urgency level (Routine / Prioritize / Immediate)

Keep response under 150 words.
"""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a mining equipment maintenance expert providing actionable recommendations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            recommendation = response['choices'][0]['message']['content'].strip()
            component_df.at[idx, 'ai_recommendation'] = recommendation
            
        except Exception as e:
            logger.error(f"LLM recommendation failed for {row['unit']}/{row['component']}: {e}")
            component_df.at[idx, 'ai_recommendation'] = "Recommendation generation failed."
    
    return component_df
```

**Integration Point**:
```python
# In run_telemetry_pipeline(), after Step 4:
if ENABLE_AI_RECOMMENDATIONS:
    logger.info("Step 4.5: Generating AI recommendations")
    component_df = generate_ai_recommendations(component_df)
```

**Monitoring**:
- Track LLM API costs per week
- Log recommendation generation times
- Validate recommendations don't contain hallucinations (manual spot-checks)

---

### Phase 2B: LSTM Autoencoder

**Objective**: Use deep learning to detect complex multivariate patterns

**Architecture**:
```
Encoder: [Signal Vector] → LSTM(128) → LSTM(64) → [Latent Representation]
Decoder: [Latent] → LSTM(64) → LSTM(128) → [Reconstructed Signals]

Anomaly Score = Reconstruction Error (MSE)
```

**Training Pipeline**:

```python
import tensorflow as tf
from tensorflow.keras import layers, Model

def build_lstm_autoencoder(n_signals: int, sequence_length: int):
    """
    Build LSTM autoencoder for multivariate telemetry.
    
    Args:
        n_signals: Number of input signals (features)
        sequence_length: Time steps in sequence (e.g., 168 hours for 1 week)
    """
    # Encoder
    encoder_inputs = layers.Input(shape=(sequence_length, n_signals))
    x = layers.LSTM(128, return_sequences=True)(encoder_inputs)
    x = layers.Dropout(0.2)(x)
    x = layers.LSTM(64, return_sequences=False)(x)
    encoder = Model(encoder_inputs, x, name='encoder')
    
    # Decoder
    decoder_input = layers.Input(shape=(64,))
    x = layers.RepeatVector(sequence_length)(decoder_input)
    x = layers.LSTM(64, return_sequences=True)(x)
    x = layers.Dropout(0.2)(x)
    x = layers.LSTM(128, return_sequences=True)(x)
    decoder_output = layers.TimeDistributed(layers.Dense(n_signals))(x)
    decoder = Model(decoder_input, decoder_output, name='decoder')
    
    # Full autoencoder
    autoencoder_input = layers.Input(shape=(sequence_length, n_signals))
    encoded = encoder(autoencoder_input)
    decoded = decoder(encoded)
    autoencoder = Model(autoencoder_input, decoded, name='autoencoder')
    
    autoencoder.compile(optimizer='adam', loss='mse')
    
    return autoencoder, encoder, decoder

def train_lstm_autoencoder(
    training_df: pd.DataFrame,
    component_mapping: dict,
    client: str,
    component: str
):
    """
    Train LSTM autoencoder on historical normal data for a component.
    """
    signal_cols = component_mapping[component]['signals']
    
    # Filter to Normal operation only (for training)
    normal_data = training_df[training_df['Label'] == 'Normal']  # Requires labeled historical data
    
    # Prepare sequences (sliding window)
    sequences = []
    for unit in normal_data['Unit'].unique():
        unit_data = normal_data[normal_data['Unit'] == unit][signal_cols].values
        
        # Normalize
        scaler = StandardScaler()
        unit_data_norm = scaler.fit_transform(unit_data)
        
        # Create sliding windows
        for i in range(len(unit_data_norm) - 168):
            sequences.append(unit_data_norm[i:i+168])
    
    X_train = np.array(sequences)
    
    # Build and train model
    model, encoder, decoder = build_lstm_autoencoder(
        n_signals=len(signal_cols),
        sequence_length=168
    )
    
    model.fit(
        X_train, X_train,
        epochs=50,
        batch_size=32,
        validation_split=0.2,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)
        ]
    )
    
    # Save model
    model_path = f"models/autoencoders/{client}/{component}_lstm_ae.h5"
    model.save(model_path)
    
    return model
```

**Inference in Pipeline**:

```python
def evaluate_with_lstm(
    current_df: pd.DataFrame,
    component: str,
    signal_cols: list,
    model_path: str
) -> pd.DataFrame:
    """
    Score component using LSTM autoencoder reconstruction error.
    """
    model = tf.keras.models.load_model(model_path)
    
    results = []
    
    for unit in current_df['Unit'].unique():
        unit_data = current_df[current_df['Unit'] == unit][signal_cols].values
        
        if len(unit_data) < 168:
            continue
        
        # Normalize
        scaler = StandardScaler()
        unit_data_norm = scaler.fit_transform(unit_data)
        
        # Prepare sequence
        sequence = unit_data_norm[-168:].reshape(1, 168, len(signal_cols))
        
        # Predict (reconstruct)
        reconstruction = model.predict(sequence)
        
        # Compute reconstruction error (MSE)
        mse = np.mean((sequence - reconstruction) ** 2)
        
        # Threshold-based classification
        if mse < 0.01:
            status = 'Normal'
        elif mse < 0.05:
            status = 'Alerta'
        else:
            status = 'Anormal'
        
        results.append({
            'unit': unit,
            'component': component,
            'lstm_score': mse,
            'lstm_status': status
        })
    
    return pd.DataFrame(results)
```

**Integration Strategy**:
- Train one model per component per client
- Run LSTM evaluation in parallel with percentile scoring
- Combine scores: `final_score = 0.6 * percentile_score + 0.4 * lstm_score`
- Use LSTM for components with complex multivariate dependencies (e.g., Engine)

**Monitoring**:
- Track reconstruction error distributions over time
- Retrain models monthly or when drift detected
- Validate on labeled failure cases

---

### Phase 2C: Time Series Forecasting

**Objective**: Predict next-week status to enable proactive maintenance

**Approach**: Use Prophet or ARIMA to forecast signal trends

**Implementation**:

```python
from prophet import Prophet

def forecast_signal_next_week(
    historical_df: pd.DataFrame,
    signal: str,
    unit: str
) -> dict:
    """
    Forecast signal values for next week using Prophet.
    
    Returns:
        {
            'forecast_mean': float,
            'forecast_lower': float,
            'forecast_upper': float,
            'predicted_status': str
        }
    """
    unit_data = historical_df[historical_df['Unit'] == unit][['Fecha', signal]].copy()
    unit_data.rename(columns={'Fecha': 'ds', signal: 'y'}, inplace=True)
    unit_data.dropna(inplace=True)
    
    if len(unit_data) < 100:
        return None
    
    # Fit Prophet model
    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=True
    )
    model.fit(unit_data)
    
    # Forecast 7 days ahead
    future = model.make_future_dataframe(periods=7 * 24, freq='H')  # Hourly forecast
    forecast = model.predict(future)
    
    # Extract next week's forecast
    next_week_forecast = forecast.iloc[-7*24:]
    forecast_mean = next_week_forecast['yhat'].mean()
    forecast_lower = next_week_forecast['yhat_lower'].mean()
    forecast_upper = next_week_forecast['yhat_upper'].mean()
    
    # Compare to baseline to predict status
    # (Requires baseline percentiles)
    baseline = get_baseline_for_signal(unit, signal)
    
    if forecast_mean < baseline['p5'] or forecast_mean > baseline['p95']:
        predicted_status = 'Alerta'
    else:
        predicted_status = 'Normal'
    
    return {
        'forecast_mean': forecast_mean,
        'forecast_lower': forecast_lower,
        'forecast_upper': forecast_upper,
        'predicted_status': predicted_status
    }
```

**Integration**:
- Run forecasting as optional analysis after main pipeline
- Store forecasts in separate table: `data/telemetry/golden/{client}/forecasts.parquet`
- Display in dashboard as "Predicted Next Week" column

**Use Case**:
- Identify machines likely to transition from Normal → Alerta next week
- Enable preventive interventions before issues become critical

---

## 🚢 Deployment & Operations

### Scheduled Execution

**Cadence**: Every Monday at 6 AM (weekly)

**Scheduler Options**:
1. **Cron Job** (Linux):
   ```bash
   0 6 * * 1 /usr/bin/python /path/to/pipeline/main.py --client cda --week auto --year auto
   ```

2. **Windows Task Scheduler**:
   - Trigger: Weekly, Monday 6:00 AM
   - Action: Run Python script

3. **Apache Airflow DAG**:
   ```python
   from airflow import DAG
   from airflow.operators.python import PythonOperator
   from datetime import datetime, timedelta
   
   dag = DAG(
       'telemetry_pipeline',
       default_args={'owner': 'data-team'},
       schedule_interval='0 6 * * 1',  # Weekly Monday 6 AM
       start_date=datetime(2026, 1, 1)
   )
   
   run_pipeline = PythonOperator(
       task_id='run_telemetry_analysis',
       python_callable=run_telemetry_pipeline,
       op_kwargs={'client': 'cda', 'week': 'auto', 'year': 'auto'},
       dag=dag
   )
   ```

### Monitoring & Alerting

**Metrics to Track**:
- Pipeline execution time
- Number of units processed
- Failure rate (units with errors)
- Output file sizes
- Baseline age (days since last recomputation)

**Alerting Rules**:
- Pipeline fails to complete → Email alert
- Execution time > 10 minutes → Warning
- >10% units failed processing → Critical alert
- Baseline > 30 days old → Recomputation reminder

**Logging Strategy**:
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/telemetry_pipeline_{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)
```

### Baseline Maintenance

**Monthly Baseline Refresh**:
- Schedule: First Monday of each month
- Action: Recompute baselines with updated 90-day window
- Validation: Compare new vs. old thresholds, flag large shifts

**Baseline Version Control**:
- Keep historical baselines for auditability
- Store in `data/telemetry/golden/{client}/baselines/archive/`

---

## 📚 Related Documentation

- [Project Overview](project_overview.md) - Methodology and architecture
- [Dashboard Proposal](dashboard_proposal.md) - Visualization specifications
- [Programming Rules](programming_rules.md) - Code standards and conventions
- [Dashboard Overview](../general/dashboard_overview.md) - Platform context

---

## 📝 Version History

### Version 1.0.0 (February 2026)
- Phase 1 MVP pipeline specification
- Phase 2 advanced integrations design (LLM, LSTM, Forecasting)
- Complete pseudo-code for all steps
