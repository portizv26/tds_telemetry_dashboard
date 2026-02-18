# Telemetry Analysis - Implementation Plan (MVP)

**Version**: 1.0  
**Created**: February 18, 2026  
**Owner**: Telemetry Analysis Team  
**Goal**: Build a working MVP using percentile-based, state-conditioned analysis

---

## 📋 Table of Contents

1. [MVP Scope](#mvp-scope)
2. [Architecture Overview](#architecture-overview)
3. [Implementation Phases](#implementation-phases)
4. [Data Structures](#data-structures)
5. [Pseudo-Code](#pseudo-code)
6. [File Organization](#file-organization)
7. [Testing Strategy](#testing-strategy)

---

## 🎯 MVP Scope

### What's Included ✅

**Analysis Methods**:
- ✅ **Method 4**: Percentile-Based Baseline (P1, P5, P25, P50, P75, P95, P99)
- ✅ **Method 5**: State-Conditioned Analysis (evaluate per operational state)
- ✅ Signal → Component → Machine grading hierarchy

**Outputs**:
- ✅ `machine_status.parquet`: Overall machine health
- ✅ `classified.parquet`: Component and signal details
- ✅ `signal_baselines.parquet`: Pre-computed percentiles for visualization

**Data Sources**:
- ✅ Input: `data/telemetry/silver/cda/Telemetry_Wide_With_States/Week{WW}Year{YYYY}.parquet`
- ✅ Mapping: `data/telemetry/component_signals_mapping.json`
- ✅ Output: `data/telemetry/golden/cda/`

### What's Excluded ❌

- ❌ AI-generated recommendations (Phase 2)
- ❌ Advanced ML models (Isolation Forest, etc.)
- ❌ Rate of change detection
- ❌ Multivariate correlation analysis

**Rationale**: Deliver working system fast, then iterate

---

## 🏗️ Architecture Overview

### Processing Pipeline

```
┌─────────────────────────────────────────────────────────┐
│ STEP 1: Data Loading                                   │
│ - Read latest week + historical weeks (for baseline)   │
│ - Read component mapping JSON                           │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 2: Data Cleaning & Validation                     │
│ - Handle missing values                                 │
│ - Remove duplicates                                     │
│ - Validate sensor ranges                                │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 3: Baseline Calculation                           │
│ - Compute percentiles per signal + state               │
│ - Use historical weeks (4-8 weeks lookback)            │
│ - Save to signal_baselines.parquet                     │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 4: Signal Evaluation                              │
│ - For each signal in current week:                     │
│   - Compare against state-specific baseline            │
│   - Assign grade (Normal/Alerta/Anormal)               │
│   - Calculate score                                     │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 5: Component Aggregation                          │
│ - Group signals by component (using mapping JSON)      │
│ - Aggregate signal grades                              │
│ - Assign component grade + score                       │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 6: Machine Aggregation                            │
│ - Aggregate component grades per unit                  │
│ - Calculate machine score + priority score             │
│ - Assign overall status                                │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 7: Output Generation                              │
│ - Write machine_status.parquet                         │
│ - Write classified.parquet                             │
│ - Log summary statistics                               │
└─────────────────────────────────────────────────────────┘
```

---

## 📅 Implementation Phases

### **Phase 1: Foundation** (Week 1)

**Goal**: Set up project structure and data loading

#### **Task 1.1: Project Setup**
- Create folder structure
- Set up logging configuration
- Create utility modules

#### **Task 1.2: Data Loaders**
- Implement `load_telemetry_week()` function
- Implement `load_historical_weeks()` function
- Implement `load_component_mapping()` function
- Add error handling for missing files

**Deliverables**:
- `src/telemetry/data_loaders.py`
- `src/utils/logger.py` (if not exists)
- Test data loading with sample week

---

### **Phase 2: Data Cleaning** (Week 1)

**Goal**: Ensure data quality before analysis

#### **Task 2.1: Validation Functions**
- Check for required columns
- Validate datetime format
- Validate Unit identifiers
- Validate sensor value ranges (e.g., no negative temps in Kelvin)

#### **Task 2.2: Cleaning Functions**
- Remove duplicates (same Unit + Fecha)
- Handle missing values (forward fill for short gaps, drop for long gaps)
- Filter out invalid states

**Deliverables**:
- `src/telemetry/data_cleaning.py`
- Unit tests for each cleaning function

---

### **Phase 3: Baseline Calculation** (Week 1-2)

**Goal**: Build statistical baselines for grading

#### **Task 3.1: Percentile Calculator**
- Calculate percentiles (P1, P5, P25, P50, P75, P95, P99) per signal
- **State-conditioned**: Separate baselines for each unique operational state
- Use historical weeks (4-8 weeks recommended)

#### **Task 3.2: Baseline Storage**
- Save baselines to `signal_baselines.parquet`
- Schema: `signal`, `state`, `P1`, `P5`, `P25`, `P50`, `P75`, `P95`, `P99`, `sample_count`, `date_range`
- Include metadata: baseline date range, sample counts

**Deliverables**:
- `src/telemetry/baseline_calculator.py`
- `data/telemetry/golden/cda/signal_baselines.parquet`

---

### **Phase 4: Signal Evaluation** (Week 2)

**Goal**: Grade individual sensor readings

#### **Task 4.1: Grading Logic**
- Implement percentile-based grading:
  - **Anormal**: < P1 or > P99
  - **Alerta**: < P5 or > P95 (but not Anormal)
  - **Normal**: Between P5 and P95
- **State-aware**: Match signal's state to correct baseline
- Assign scores: Normal=0, Alerta=5, Anormal=10

#### **Task 4.2: Evaluation Engine**
- Process all signals for all units in current week
- Store results with metadata (which percentile violated, by how much)

**Deliverables**:
- `src/telemetry/signal_evaluator.py`
- Signal evaluation results (intermediate)

---

### **Phase 5: Component Aggregation** (Week 2)

**Goal**: Roll up signal grades to component level

#### **Task 5.1: Aggregation Logic**
- Group signals by component using `component_signals_mapping.json`
- Calculate component score = sum(signal scores)
- Assign component grade using rules:
  - **Anormal**: 2+ signals Anormal OR component_score ≥ 20
  - **Alerta**: 1 signal Anormal OR 2+ signals Alerta OR component_score ≥ 10
  - **Normal**: Otherwise

#### **Task 5.2: Detail Capture**
- Store which signals contributed to component grade
- Include signal-level details in `signals_evaluation` field

**Deliverables**:
- `src/telemetry/component_aggregator.py`
- Component evaluation results (intermediate)

---

### **Phase 6: Machine Aggregation** (Week 2-3)

**Goal**: Create overall machine health status

#### **Task 6.1: Machine Scoring**
- Calculate machine_score = sum(all component scores)
- Calculate priority_score = weighted sum (weight critical components higher):
  - Motor: 2x weight
  - Brakes: 1.5x weight
  - Powertrain: 1.5x weight
  - Steering: 1x weight
- Assign overall_status using rules:
  - **Anormal**: Any component Anormal
  - **Alerta**: Any component Alerta (and no Anormal)
  - **Normal**: All components Normal

#### **Task 6.2: Summary Statistics**
- Count: total_components, components_normal, components_alerta, components_anormal
- Capture component_details as list of dicts

**Deliverables**:
- `src/telemetry/machine_aggregator.py`
- Machine-level evaluation results

---

### **Phase 7: Output Generation** (Week 3)

**Goal**: Write final parquet files

#### **Task 7.1: machine_status.parquet**
- Schema: `unit_id`, `client`, `latest_sample_date`, `overall_status`, `machine_score`, `total_components`, `components_normal`, `components_alerta`, `components_anormal`, `priority_score`, `component_details`
- One row per unit

#### **Task 7.2: classified.parquet**
- Schema: `unit`, `date`, `component`, `component_status`, `signals_evaluation`, (no `ai_recommendation` in MVP)
- Multiple rows per unit (one per component)
- `signals_evaluation`: JSON/dict with signal-level details

#### **Task 7.3: Logging & Monitoring**
- Log processing summary: units processed, grades assigned, errors
- Generate execution report

**Deliverables**:
- `src/telemetry/output_writer.py`
- `data/telemetry/golden/cda/machine_status.parquet`
- `data/telemetry/golden/cda/classified.parquet`

---

### **Phase 8: Orchestration** (Week 3)

**Goal**: Tie everything together in a runnable script

#### **Task 8.1: Main Script**
- Create `main.py` that executes Steps 1-7 sequentially
- Add configuration file for parameters (e.g., baseline_weeks, percentile_thresholds)
- Add command-line arguments (e.g., `--week`, `--year`, `--client`)

#### **Task 8.2: Scheduling**
- Set up cron job or task scheduler for execution every 8-12 hours
- Add error notifications (email/Slack on failure)

**Deliverables**:
- `src/telemetry/main.py`
- `config/telemetry_config.yaml`
- Deployment documentation

---

### **Phase 9: Testing & Validation** (Week 3-4)

**Goal**: Ensure system works correctly

#### **Task 9.1: Unit Tests**
- Test each module independently
- Use sample data fixtures
- Cover edge cases (missing data, all Normal, all Anormal)

#### **Task 9.2: Integration Tests**
- Run full pipeline on historical weeks
- Compare output against manual inspection
- Validate grade assignments

#### **Task 9.3: Validation**
- Work with domain experts to review flagged units
- Adjust percentile thresholds if needed
- Document false positives/negatives

**Deliverables**:
- `tests/` folder with comprehensive tests
- Validation report with accuracy metrics

---

## 📊 Data Structures

### Input: Telemetry Week File

```python
# Schema: Telemetry_Wide_With_States/WeekXXYearYYYY.parquet
columns = [
    'Fecha',           # datetime: timestamp of reading
    'Unit',            # str: unit identifier
    'Estado',          # str: operational state
    'EstadoMaquina',   # str: machine state
    'EstadoCarga',     # str: load state
    'GPSLat',          # float: GPS latitude
    'GPSLon',          # float: GPS longitude
    'GPSElevation',    # float: GPS elevation (meters)
    # Sensor signals (19 signals):
    'AirFltr', 'CnkcasePres', 'DiffLubePres', 'DiffTemp', 
    'EngCoolTemp', 'EngOilFltr', 'EngOilPres', 'EngSpd',
    'GroundSpd', 'LtExhTemp', 'LtFBrkTemp', 'LtRBrkTemp',
    'Payload', 'RAftrclrTemp', 'RtExhTemp', 'RtFBrkTemp',
    'RtLtExhTemp', 'RtRBrkTemp', 'StrgOilTemp', 'TCOutTemp',
    'TrnLubeTemp'
]
```

### Input: Component Mapping

```python
# component_signals_mapping.json
{
  "Motor": [
    "EngCoolTemp", "RAftrclrTemp", "EngOilPres", "EngSpd",
    "EngOilFltr", "CnkcasePres", "RtLtExhTemp", "RtExhTemp",
    "LtExhTemp", "AirFltr"
  ],
  "Tren de fuerza": [
    "DiffLubePres", "DiffTemp", "TrnLubeTemp", "TCOutTemp"
  ],
  "Frenos": [
    "RtRBrkTemp", "RtFBrkTemp", "LtRBrkTemp", "LtFBrkTemp"
  ],
  "Direccion": [
    "StrgOilTemp"
  ]
}
```

### Intermediate: Signal Baselines

```python
# signal_baselines.parquet
columns = [
    'signal',          # str: signal name (e.g., 'EngCoolTemp')
    'state',           # str: operational state (e.g., 'Operacional-Cargado')
    'P1', 'P5', 'P25', 'P50', 'P75', 'P95', 'P99',  # float: percentiles
    'sample_count',    # int: number of samples in baseline
    'baseline_start',  # datetime: start of baseline period
    'baseline_end'     # datetime: end of baseline period
]
```

### Intermediate: Signal Evaluation

```python
# Internal structure (not saved directly)
signal_evaluation = {
    'signal': 'EngCoolTemp',
    'value': 103.5,
    'state': 'Operacional-Cargado',
    'grade': 'Anormal',
    'score': 10,
    'baseline_P50': 85.2,
    'baseline_P95': 95.1,
    'baseline_P99': 98.3,
    'deviation': 'Exceeded P99 by 5.2°C'
}
```

### Output: machine_status.parquet

```python
columns = [
    'unit_id',                  # str: unit identifier
    'client',                   # str: client name (e.g., 'cda')
    'latest_sample_date',       # datetime: last evaluation timestamp
    'overall_status',           # str: 'Normal', 'Alerta', 'Anormal'
    'machine_score',            # float: total criticality score
    'total_components',         # int: number of components monitored (4)
    'components_normal',        # int: count of Normal components
    'components_alerta',        # int: count of Alerta components
    'components_anormal',       # int: count of Anormal components
    'priority_score',           # float: weighted score for sorting
    'component_details'         # list[dict]: details per component
]

# Example component_details structure:
component_details = [
    {
        'component': 'Motor',
        'status': 'Anormal',
        'score': 25,
        'critical_signals': ['EngCoolTemp', 'LtExhTemp']
    },
    # ... other components
]
```

### Output: classified.parquet

```python
columns = [
    'unit',                     # str: unit identifier
    'date',                     # datetime: evaluation timestamp
    'component',                # str: component name
    'component_status',         # str: 'Normal', 'Alerta', 'Anormal'
    'signals_evaluation'        # dict/JSON: signal-level details
]

# Example signals_evaluation structure:
signals_evaluation = {
    'Motor': {
        'EngCoolTemp': {
            'grade': 'Anormal',
            'score': 10,
            'value': 103.5,
            'baseline_P99': 98.3,
            'deviation': 'Exceeded P99 by 5.2°C'
        },
        'EngOilPres': {
            'grade': 'Normal',
            'score': 0,
            'value': 45.2,
            'baseline_P50': 46.1
        },
        # ... other signals
    }
}
```

---

## 💻 Pseudo-Code

### Main Execution Flow

```python
# main.py

def main(client='cda', week=None, year=None):
    """
    Main telemetry analysis pipeline
    
    Args:
        client: Client identifier (e.g., 'cda')
        week: Week number (if None, use current week)
        year: Year (if None, use current year)
    """
    
    # STEP 1: Initialize
    logger = setup_logger()
    config = load_config('config/telemetry_config.yaml')
    
    if week is None or year is None:
        week, year = get_current_week_year()
    
    logger.info(f"Starting telemetry analysis for Week {week}, Year {year}")
    
    # STEP 2: Load Data
    logger.info("Loading data...")
    component_mapping = load_component_mapping()
    current_week_data = load_telemetry_week(client, week, year)
    historical_data = load_historical_weeks(
        client, 
        week, 
        year, 
        lookback_weeks=config['baseline_weeks']
    )
    
    # STEP 3: Clean Data
    logger.info("Cleaning data...")
    current_week_clean = clean_telemetry_data(current_week_data)
    historical_clean = clean_telemetry_data(historical_data)
    
    # STEP 4: Calculate Baselines
    logger.info("Calculating baselines...")
    baselines = calculate_baselines(
        historical_clean,
        signals=get_all_signals(component_mapping),
        percentiles=[1, 5, 25, 50, 75, 95, 99]
    )
    save_baselines(baselines, client)
    
    # STEP 5: Evaluate Signals
    logger.info("Evaluating signals...")
    signal_evaluations = evaluate_signals(
        current_week_clean,
        baselines,
        component_mapping
    )
    
    # STEP 6: Aggregate Components
    logger.info("Aggregating components...")
    component_evaluations = aggregate_components(
        signal_evaluations,
        component_mapping
    )
    
    # STEP 7: Aggregate Machines
    logger.info("Aggregating machines...")
    machine_status = aggregate_machines(
        component_evaluations,
        weights=config['component_weights']
    )
    
    # STEP 8: Write Outputs
    logger.info("Writing outputs...")
    write_machine_status(machine_status, client)
    write_classified(component_evaluations, client)
    
    # STEP 9: Summary
    summary = generate_summary(machine_status)
    logger.info(f"Analysis complete: {summary}")
    
    return machine_status
```

---

### Step 4: Calculate Baselines

```python
# baseline_calculator.py

def calculate_baselines(historical_data, signals, percentiles):
    """
    Calculate state-conditioned percentile baselines
    
    Args:
        historical_data: DataFrame with historical telemetry
        signals: List of signal names to process
        percentiles: List of percentiles to calculate (e.g., [1, 5, 95, 99])
    
    Returns:
        DataFrame with baselines per signal + state combination
    """
    
    baselines = []
    
    # Create composite state column
    historical_data['CompositeState'] = (
        historical_data['Estado'] + '-' + 
        historical_data['EstadoMaquina'] + '-' + 
        historical_data['EstadoCarga']
    )
    
    # For each signal
    for signal in signals:
        # Skip if signal not in data
        if signal not in historical_data.columns:
            logger.warning(f"Signal {signal} not found in historical data")
            continue
        
        # For each unique operational state
        for state in historical_data['CompositeState'].unique():
            # Filter data for this signal + state
            state_data = historical_data[
                historical_data['CompositeState'] == state
            ][signal].dropna()
            
            # Skip if insufficient samples
            if len(state_data) < MIN_SAMPLES_FOR_BASELINE:
                logger.warning(
                    f"Insufficient samples for {signal} in state {state}: "
                    f"{len(state_data)} < {MIN_SAMPLES_FOR_BASELINE}"
                )
                continue
            
            # Calculate percentiles
            percentile_values = np.percentile(state_data, percentiles)
            
            # Store baseline
            baseline_record = {
                'signal': signal,
                'state': state,
                'sample_count': len(state_data),
                'baseline_start': historical_data['Fecha'].min(),
                'baseline_end': historical_data['Fecha'].max()
            }
            
            # Add percentile columns
            for p, val in zip(percentiles, percentile_values):
                baseline_record[f'P{p}'] = val
            
            baselines.append(baseline_record)
    
    return pd.DataFrame(baselines)
```

---

### Step 5: Evaluate Signals

```python
# signal_evaluator.py

def evaluate_signals(current_data, baselines, component_mapping):
    """
    Grade each signal reading against state-specific baselines
    
    Args:
        current_data: DataFrame with current week telemetry
        baselines: DataFrame with percentile baselines
        component_mapping: Dict mapping components to signals
    
    Returns:
        List of signal evaluation dicts (one per Unit + timestamp + signal)
    """
    
    evaluations = []
    
    # Create composite state
    current_data['CompositeState'] = (
        current_data['Estado'] + '-' + 
        current_data['EstadoMaquina'] + '-' + 
        current_data['EstadoCarga']
    )
    
    # Get all signals to evaluate
    all_signals = [
        sig for signals in component_mapping.values() for sig in signals
    ]
    
    # For each row in current data
    for idx, row in current_data.iterrows():
        unit = row['Unit']
        timestamp = row['Fecha']
        state = row['CompositeState']
        
        # For each signal
        for signal in all_signals:
            if signal not in current_data.columns:
                continue
            
            value = row[signal]
            
            # Skip NaN values
            if pd.isna(value):
                continue
            
            # Find matching baseline
            baseline = baselines[
                (baselines['signal'] == signal) & 
                (baselines['state'] == state)
            ]
            
            # If no exact state match, try falling back to main state
            if baseline.empty:
                main_state = state.split('-')[0]  # e.g., 'Operacional'
                baseline = baselines[
                    (baselines['signal'] == signal) & 
                    (baselines['state'].str.startswith(main_state))
                ]
            
            # If still no match, use global baseline (all states)
            if baseline.empty:
                baseline = baselines[
                    (baselines['signal'] == signal)
                ].groupby('signal').mean()  # Average across states
            
            # If still no baseline, skip (insufficient historical data)
            if baseline.empty:
                logger.warning(
                    f"No baseline found for {signal} in state {state}"
                )
                continue
            
            baseline = baseline.iloc[0]  # Take first match
            
            # Grade the signal
            grade, score = grade_signal_value(value, baseline)
            
            # Calculate deviation
            deviation = calculate_deviation(value, baseline, grade)
            
            # Store evaluation
            evaluation = {
                'unit': unit,
                'timestamp': timestamp,
                'signal': signal,
                'component': get_component_for_signal(signal, component_mapping),
                'value': value,
                'state': state,
                'grade': grade,
                'score': score,
                'baseline_P50': baseline['P50'],
                'baseline_P95': baseline['P95'],
                'baseline_P99': baseline['P99'],
                'deviation': deviation
            }
            
            evaluations.append(evaluation)
    
    return evaluations


def grade_signal_value(value, baseline):
    """
    Assign grade based on percentile thresholds
    
    Args:
        value: Current sensor reading
        baseline: Series with percentile values (P1, P5, P95, P99, etc.)
    
    Returns:
        Tuple of (grade, score)
    """
    
    # Anormal: Outside P1-P99 range
    if value < baseline['P1'] or value > baseline['P99']:
        return 'Anormal', 10
    
    # Alerta: Outside P5-P95 range (but inside P1-P99)
    elif value < baseline['P5'] or value > baseline['P95']:
        return 'Alerta', 5
    
    # Normal: Inside P5-P95 range
    else:
        return 'Normal', 0


def calculate_deviation(value, baseline, grade):
    """
    Describe how the value deviates from baseline
    
    Args:
        value: Current sensor reading
        baseline: Series with percentile values
        grade: Assigned grade
    
    Returns:
        String description of deviation
    """
    
    if grade == 'Normal':
        return 'Within normal range'
    
    median = baseline['P50']
    
    if value > baseline['P99']:
        excess = value - baseline['P99']
        return f"Exceeded P99 by {excess:.2f} ({value:.2f} vs {baseline['P99']:.2f})"
    
    elif value < baseline['P1']:
        deficit = baseline['P1'] - value
        return f"Below P1 by {deficit:.2f} ({value:.2f} vs {baseline['P1']:.2f})"
    
    elif value > baseline['P95']:
        excess = value - baseline['P95']
        return f"Exceeded P95 by {excess:.2f} ({value:.2f} vs {baseline['P95']:.2f})"
    
    elif value < baseline['P5']:
        deficit = baseline['P5'] - value
        return f"Below P5 by {deficit:.2f} ({value:.2f} vs {baseline['P5']:.2f})"
    
    else:
        return 'Unknown deviation'


def get_component_for_signal(signal, component_mapping):
    """Find which component a signal belongs to"""
    for component, signals in component_mapping.items():
        if signal in signals:
            return component
    return 'Unknown'
```

---

### Step 6: Aggregate Components

```python
# component_aggregator.py

def aggregate_components(signal_evaluations, component_mapping):
    """
    Roll up signal grades to component level
    
    Args:
        signal_evaluations: List of signal evaluation dicts
        component_mapping: Dict mapping components to signals
    
    Returns:
        List of component evaluation dicts (one per Unit + component)
    """
    
    # Convert to DataFrame for easier grouping
    df = pd.DataFrame(signal_evaluations)
    
    component_evaluations = []
    
    # Group by unit and component
    for (unit, component), group in df.groupby(['unit', 'component']):
        
        # Get latest timestamp for this unit
        latest_date = group['timestamp'].max()
        
        # Calculate component score
        component_score = group['score'].sum()
        
        # Count grade distribution
        grade_counts = group['grade'].value_counts().to_dict()
        num_anormal = grade_counts.get('Anormal', 0)
        num_alerta = grade_counts.get('Alerta', 0)
        num_normal = grade_counts.get('Normal', 0)
        
        # Assign component grade
        component_grade = assign_component_grade(
            num_anormal, num_alerta, component_score
        )
        
        # Build signals_evaluation dict (details for dashboard)
        signals_eval_dict = {}
        for _, signal_row in group.iterrows():
            signals_eval_dict[signal_row['signal']] = {
                'grade': signal_row['grade'],
                'score': signal_row['score'],
                'value': signal_row['value'],
                'baseline_P50': signal_row['baseline_P50'],
                'baseline_P95': signal_row['baseline_P95'],
                'baseline_P99': signal_row['baseline_P99'],
                'deviation': signal_row['deviation']
            }
        
        # Store component evaluation
        component_eval = {
            'unit': unit,
            'date': latest_date,
            'component': component,
            'component_status': component_grade,
            'component_score': component_score,
            'signals_evaluation': signals_eval_dict,
            'num_signals_anormal': num_anormal,
            'num_signals_alerta': num_alerta,
            'num_signals_normal': num_normal
        }
        
        component_evaluations.append(component_eval)
    
    return component_evaluations


def assign_component_grade(num_anormal, num_alerta, component_score):
    """
    Assign component grade based on signal grades
    
    Rules:
    - Anormal: 2+ signals Anormal OR total score >= 20
    - Alerta: 1 signal Anormal OR 2+ signals Alerta OR score >= 10
    - Normal: Otherwise
    """
    
    if num_anormal >= 2 or component_score >= 20:
        return 'Anormal'
    
    elif num_anormal >= 1 or num_alerta >= 2 or component_score >= 10:
        return 'Alerta'
    
    else:
        return 'Normal'
```

---

### Step 7: Aggregate Machines

```python
# machine_aggregator.py

def aggregate_machines(component_evaluations, weights):
    """
    Roll up component grades to machine level
    
    Args:
        component_evaluations: List of component evaluation dicts
        weights: Dict mapping component names to weights
    
    Returns:
        DataFrame with machine status (one row per unit)
    """
    
    # Convert to DataFrame
    df = pd.DataFrame(component_evaluations)
    
    machine_status_list = []
    
    # Group by unit
    for unit, group in df.groupby('unit'):
        
        # Get latest date
        latest_date = group['date'].max()
        
        # Calculate machine score (unweighted sum)
        machine_score = group['component_score'].sum()
        
        # Calculate priority score (weighted sum)
        priority_score = 0
        for _, comp_row in group.iterrows():
            component = comp_row['component']
            comp_score = comp_row['component_score']
            weight = weights.get(component, 1.0)
            priority_score += comp_score * weight
        
        # Count component grades
        grade_counts = group['component_status'].value_counts().to_dict()
        total_components = len(group)
        components_normal = grade_counts.get('Normal', 0)
        components_alerta = grade_counts.get('Alerta', 0)
        components_anormal = grade_counts.get('Anormal', 0)
        
        # Assign overall machine status
        overall_status = assign_machine_status(grade_counts)
        
        # Build component_details list
        component_details = []
        for _, comp_row in group.iterrows():
            # Find critical signals (Anormal or Alerta)
            critical_signals = [
                signal 
                for signal, details in comp_row['signals_evaluation'].items()
                if details['grade'] in ['Anormal', 'Alerta']
            ]
            
            component_details.append({
                'component': comp_row['component'],
                'status': comp_row['component_status'],
                'score': comp_row['component_score'],
                'critical_signals': critical_signals
            })
        
        # Store machine status
        machine_status = {
            'unit_id': unit,
            'client': 'cda',  # TODO: Make configurable
            'latest_sample_date': latest_date,
            'overall_status': overall_status,
            'machine_score': machine_score,
            'total_components': total_components,
            'components_normal': components_normal,
            'components_alerta': components_alerta,
            'components_anormal': components_anormal,
            'priority_score': priority_score,
            'component_details': component_details
        }
        
        machine_status_list.append(machine_status)
    
    return pd.DataFrame(machine_status_list)


def assign_machine_status(grade_counts):
    """
    Assign overall machine status based on component grades
    
    Rules:
    - Anormal: Any component Anormal
    - Alerta: Any component Alerta (and no Anormal)
    - Normal: All components Normal
    """
    
    if grade_counts.get('Anormal', 0) > 0:
        return 'Anormal'
    
    elif grade_counts.get('Alerta', 0) > 0:
        return 'Alerta'
    
    else:
        return 'Normal'
```

---

## 📁 File Organization

```
telemetry_dashboard/
├── config/
│   └── telemetry_config.yaml          # Configuration parameters
├── data/
│   └── telemetry/
│       ├── component_signals_mapping.json
│       ├── silver/
│       │   └── cda/
│       │       └── Telemetry_Wide_With_States/
│       │           └── Week{WW}Year{YYYY}.parquet
│       └── golden/
│           └── cda/
│               ├── machine_status.parquet       # Output 1
│               ├── classified.parquet           # Output 2
│               └── signal_baselines.parquet     # Output 3 (for viz)
├── src/
│   ├── telemetry/
│   │   ├── __init__.py
│   │   ├── main.py                    # Main orchestration script
│   │   ├── data_loaders.py            # Step 1: Load data
│   │   ├── data_cleaning.py           # Step 2: Clean data
│   │   ├── baseline_calculator.py     # Step 3: Calculate baselines
│   │   ├── signal_evaluator.py        # Step 4: Evaluate signals
│   │   ├── component_aggregator.py    # Step 5: Aggregate components
│   │   ├── machine_aggregator.py      # Step 6: Aggregate machines
│   │   └── output_writer.py           # Step 7: Write outputs
│   └── utils/
│       ├── date_utils.py              # Date/week utilities
│       └── logger.py                  # Logging setup
├── tests/
│   ├── test_data_loaders.py
│   ├── test_baseline_calculator.py
│   ├── test_signal_evaluator.py
│   ├── test_component_aggregator.py
│   └── test_machine_aggregator.py
├── notebooks/
│   └── telemetry_analysis_prototype.ipynb  # Jupyter prototype
└── requirements.txt
```

---

## 🧪 Testing Strategy

### Unit Tests

**Test each module independently**:

```python
# tests/test_signal_evaluator.py

def test_grade_signal_value_normal():
    baseline = pd.Series({
        'P1': 50, 'P5': 55, 'P50': 70, 'P95': 85, 'P99': 90
    })
    grade, score = grade_signal_value(value=70, baseline=baseline)
    assert grade == 'Normal'
    assert score == 0


def test_grade_signal_value_alerta_high():
    baseline = pd.Series({
        'P1': 50, 'P5': 55, 'P50': 70, 'P95': 85, 'P99': 90
    })
    grade, score = grade_signal_value(value=87, baseline=baseline)
    assert grade == 'Alerta'
    assert score == 5


def test_grade_signal_value_anormal_high():
    baseline = pd.Series({
        'P1': 50, 'P5': 55, 'P50': 70, 'P95': 85, 'P99': 90
    })
    grade, score = grade_signal_value(value=95, baseline=baseline)
    assert grade == 'Anormal'
    assert score == 10
```

---

### Integration Tests

**Test full pipeline on sample data**:

```python
# tests/test_integration.py

def test_full_pipeline():
    """Test end-to-end pipeline on sample week"""
    
    # Load sample data (Week 10, 2025)
    client = 'cda'
    week = 10
    year = 2025
    
    # Run pipeline
    result = main(client=client, week=week, year=year)
    
    # Validate outputs exist
    assert os.path.exists(
        f'data/telemetry/golden/{client}/machine_status.parquet'
    )
    assert os.path.exists(
        f'data/telemetry/golden/{client}/classified.parquet'
    )
    
    # Validate output structure
    machine_status = pd.read_parquet(
        f'data/telemetry/golden/{client}/machine_status.parquet'
    )
    assert 'unit_id' in machine_status.columns
    assert 'overall_status' in machine_status.columns
    assert machine_status['overall_status'].isin(['Normal', 'Alerta', 'Anormal']).all()
    
    # Validate at least some units graded
    assert len(machine_status) > 0
```

---

### Validation with Domain Experts

1. **Sample Review**: Pick 10 units (mix of Normal, Alerta, Anormal)
2. **Show Evidence**: Display time series charts with grades
3. **Expert Assessment**: Do experts agree with grades?
4. **Iterate**: Adjust thresholds if needed (e.g., P98 instead of P99 for Anormal)

---

## 📝 Configuration File

```yaml
# config/telemetry_config.yaml

# Baseline calculation
baseline_weeks: 6              # Number of historical weeks to use
min_samples_for_baseline: 100  # Minimum samples required per signal+state

# Percentiles to calculate
percentiles: [1, 5, 25, 50, 75, 95, 99]

# Grading thresholds
thresholds:
  anormal:
    lower: 1   # P1
    upper: 99  # P99
  alerta:
    lower: 5   # P5
    upper: 95  # P95

# Scoring
signal_scores:
  normal: 0
  alerta: 5
  anormal: 10

component_grade_rules:
  anormal:
    min_anormal_signals: 2
    min_score: 20
  alerta:
    min_anormal_signals: 1
    min_alerta_signals: 2
    min_score: 10

# Component weights for priority scoring
component_weights:
  Motor: 2.0
  Frenos: 1.5
  Tren de fuerza: 1.5
  Direccion: 1.0

# Data paths
paths:
  silver_base: 'data/telemetry/silver'
  golden_base: 'data/telemetry/golden'
  component_mapping: 'data/telemetry/component_signals_mapping.json'

# Logging
logging:
  level: 'INFO'
  format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  file: 'logs/telemetry_analysis.log'
```

---

## 🚀 Execution

### Command-Line Usage

```bash
# Run for current week (auto-detect)
python src/telemetry/main.py --client cda

# Run for specific week
python src/telemetry/main.py --client cda --week 10 --year 2025

# Run with custom config
python src/telemetry/main.py --client cda --config config/custom_config.yaml
```

---

### Scheduling (Cron)

```bash
# Run every 8 hours
0 */8 * * * cd /path/to/telemetry_dashboard && python src/telemetry/main.py --client cda >> logs/cron.log 2>&1
```

---

## ✅ MVP Success Criteria

### Technical
- ✅ Processes 1 week of data in <5 minutes
- ✅ Handles missing data gracefully (no crashes)
- ✅ Outputs valid parquet files with correct schema
- ✅ All tests pass

### Functional
- ✅ Grades match manual inspection for 80%+ of units
- ✅ False positive rate <20%
- ✅ Flags known problematic units correctly

### Business
- ✅ Maintenance team can use dashboard to prioritize work
- ✅ Evidence (time series charts) validates grades

---

## 📚 Next Steps

1. ✅ **Review this plan** with team
2. 🛠️ **Implement Phase 1-3** (Foundation + Cleaning + Baselines)
3. 🧪 **Test on sample week** 
4. 📊 **Prototype visualizations** in Jupyter (before Dash)
5. 🚀 **Deploy MVP** 
6. 📈 **Iterate** based on feedback (see `improvement_plan.md`)

---

**Document Status**: ✅ Ready for Implementation  
**Estimated MVP Duration**: 3-4 weeks  
**Recommended Starting Point**: `data_loaders.py` + `baseline_calculator.py`
