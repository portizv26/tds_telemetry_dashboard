# Telemetry Analysis - Final Implementation Plan

**Version**: 2.0  
**Created**: February 18, 2026  
**Owner**: Patricio Ortiz - Data Team
**Purpose**: Complete roadmap from MVP to advanced AI-powered system

---

## 📋 Table of Contents

1. [Implementation Overview](#implementation-overview)
2. [SHORT-TERM: MVP Development](#short-term-mvp-development)
3. [MEDIUM-TERM: AI & Advanced Features](#medium-term-ai--advanced-features)
4. [Testing Strategy](#testing-strategy)
5. [Deployment & Operations](#deployment--operations)

---

## 🎯 Implementation Overview

### Timeline

```
Week 0-4:    SHORT-TERM (MVP)
             ├─ Percentile-based baseline analysis
             ├─ State-conditioned grading
             └─ Dashboard with 3 tabs

Week 5-8:    MEDIUM-TERM Phase 1 (AI Integration)
             └─ LLM-powered recommendations

Week 9-14:   MEDIUM-TERM Phase 2 (Enhanced Detection)
             └─ Autoencoder neural network

Week 15-20:  MEDIUM-TERM Phase 3 (New Features)
             ├─ Time series forecasting
             └─ Operational clustering
```

**Total Duration**: 16-20 weeks

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│ INPUT: Silver Layer                                     │
│ - Weekly parquet files (pre-processed, 5-min windows)  │
│ - Component mapping JSON                                │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ PROCESSING PIPELINE                                     │
│ 1. Load data (no cleaning needed - data pre-processed) │
│ 2. Calculate baselines (percentiles per state)         │
│ 3. Evaluate signals                                     │
│ 4. Aggregate components                                 │
│ 5. Aggregate machines                                   │
│ 6. [AI] Generate recommendations (Phase 1+)            │
│ 7. [ML] ANN anomaly detection (Phase 2+)              │
│ 8. [ML] Forecasting & clustering (Phase 3+)           │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ OUTPUT: Golden Layer                                    │
│ - machine_status.parquet                                │
│ - classified.parquet                                    │
│ - signal_baselines.parquet                              │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 SHORT-TERM: MVP Development

**Duration**: 4 weeks  
**Goal**: Functional grading system with dashboard

### Phase Overview

**Methods**: 
- ✅ Percentile-Based Baseline (P1, P5, P25, P50, P75, P95, P99)
- ✅ State-Conditioned Analysis (separate baselines per operational state)

**Deliverables**:
- Signal → Component → Machine grading
- machine_status.parquet
- classified.parquet (without AI recommendations)
- Dashboard with 3 tabs and visualizations

---

### Week 1: Foundation

#### **Task 1.1: Project Setup**

**Objective**: Establish project structure and configuration

**Actions**:
- Create folder structure (see File Organization section)
- Set up logging configuration
- Create `telemetry_config.yaml` with parameters
- Initialize Git repository (if not exists)

**Deliverables**:
- Complete folder structure
- `config/telemetry_config.yaml`
- `src/utils/logger.py`

---

#### **Task 1.2: Data Loaders**

**Objective**: Implement data loading functions

**Implementation**:

```python
# src/telemetry/data_loaders.py

import pandas as pd
import json
from pathlib import Path

def load_telemetry_week(client, week, year):
    """
    Load telemetry data for specific week
    
    Args:
        client: Client identifier (e.g., 'cda')
        week: Week number (1-52)
        year: Year (e.g., 2025)
    
    Returns:
        DataFrame with telemetry data
    """
    file_path = (
        f'data/telemetry/silver/{client}/'
        f'Telemetry_Wide_With_States/Week{week:02d}Year{year}.parquet'
    )
    
    return pd.read_parquet(file_path)


def load_historical_weeks(client, current_week, current_year, lookback_weeks=6):
    """
    Load historical telemetry for baseline calculation
    
    Args:
        client: Client identifier
        current_week: Current week number
        current_year: Current year
        lookback_weeks: Number of weeks to look back
    
    Returns:
        DataFrame with historical data
    """
    dfs = []
    
    # Calculate week range (handling year boundaries)
    for i in range(1, lookback_weeks + 1):
        week = current_week - i
        year = current_year
        
        if week < 1:
            week += 52
            year -= 1
        
        try:
            df = load_telemetry_week(client, week, year)
            dfs.append(df)
        except FileNotFoundError:
            logger.warning(f"Week {week} Year {year} not found, skipping")
    
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def load_component_mapping():
    """
    Load component-signal mapping from JSON
    
    Returns:
        Dict mapping component names to signal lists
    """
    with open('data/telemetry/component_signals_mapping.json', 'r') as f:
        return json.load(f)
```

**Testing**:
- Test with sample week file
- Verify all columns present
- Test historical week loading across year boundary

**Deliverables**:
- `src/telemetry/data_loaders.py`
- Unit tests for each function

---

### Week 2: Baseline Calculation

#### **Task 2.1: Baseline Calculator**

**Objective**: Calculate state-conditioned percentile baselines

**Implementation**:

```python
# src/telemetry/baseline_calculator.py

import pandas as pd
import numpy as np

MIN_SAMPLES_FOR_BASELINE = 100  # Configurable

def calculate_baselines(historical_data, signals, percentiles=[1, 5, 25, 50, 75, 95, 99]):
    """
    Calculate state-conditioned percentile baselines
    
    Args:
        historical_data: DataFrame with historical telemetry
        signals: List of signal names to process
        percentiles: List of percentiles to calculate
    
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
        if signal not in historical_data.columns:
            logger.warning(f"Signal {signal} not in data")
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
                    f"Insufficient samples for {signal} in {state}: "
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


def save_baselines(baselines_df, client):
    """Save baselines to golden layer"""
    output_path = f'data/telemetry/golden/{client}/signal_baselines.parquet'
    baselines_df.to_parquet(output_path, index=False, compression='snappy')
    logger.info(f"Saved {len(baselines_df)} baselines to {output_path}")
```

**Deliverables**:
- `src/telemetry/baseline_calculator.py`
- `signal_baselines.parquet` output
- Validation: Baselines exist for all signal+state combinations with sufficient data

---

### Week 3: Signal & Component Evaluation

#### **Task 3.1: Signal Evaluator**

**Objective**: Grade signals against baselines

**Implementation**:

```python
# src/telemetry/signal_evaluator.py

def grade_signal_value(value, baseline):
    """
    Assign grade based on percentile thresholds
    
    Args:
        value: Current sensor reading
        baseline: Series with percentile values (P1, P5, P95, P99)
    
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
    """Describe how value deviates from baseline"""
    if grade == 'Normal':
        return 'Within normal range'
    
    if value > baseline['P99']:
        excess = value - baseline['P99']
        return f"Exceeded P99 by {excess:.2f}"
    elif value < baseline['P1']:
        deficit = baseline['P1'] - value
        return f"Below P1 by {deficit:.2f}"
    elif value > baseline['P95']:
        excess = value - baseline['P95']
        return f"Exceeded P95 by {excess:.2f}"
    elif value < baseline['P5']:
        deficit = baseline['P5'] - value
        return f"Below P5 by {deficit:.2f}"
    
    return 'Unknown deviation'


def evaluate_signals(current_data, baselines, component_mapping):
    """
    Grade each signal reading against baselines
    
    Returns:
        List of signal evaluation dicts
    """
    evaluations = []
    
    # Create composite state
    current_data['CompositeState'] = (
        current_data['Estado'] + '-' + 
        current_data['EstadoMaquina'] + '-' + 
        current_data['EstadoCarga']
    )
    
    # Get all signals
    all_signals = [
        sig for signals in component_mapping.values() for sig in signals
    ]
    
    # For each row
    for idx, row in current_data.iterrows():
        unit = row['Unit']
        timestamp = row['Fecha']
        state = row['CompositeState']
        
        # For each signal
        for signal in all_signals:
            if signal not in current_data.columns or pd.isna(row[signal]):
                continue
            
            value = row[signal]
            
            # Find matching baseline
            baseline = baselines[
                (baselines['signal'] == signal) & 
                (baselines['state'] == state)
            ]
            
            # Fallback if no exact state match
            if baseline.empty:
                main_state = state.split('-')[0]
                baseline = baselines[
                    (baselines['signal'] == signal) & 
                    (baselines['state'].str.startswith(main_state))
                ]
            
            if baseline.empty:
                continue
            
            baseline = baseline.iloc[0]
            
            # Grade signal
            grade, score = grade_signal_value(value, baseline)
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
                'deviation': deviation,
                'detection_methods': ['percentile_baseline']
            }
            
            evaluations.append(evaluation)
    
    return evaluations
```

**Deliverables**:
- `src/telemetry/signal_evaluator.py`
- Tested on sample week

---

#### **Task 3.2: Component Aggregator**

**Objective**: Roll up signal grades to components

**Implementation**:

```python
# src/telemetry/component_aggregator.py

def assign_component_grade(num_anormal, num_alerta, component_score):
    """
    Assign component grade based on signal grades
    
    Rules:
    - Anormal: 2+ signals Anormal OR score >= 20
    - Alerta: 1 signal Anormal OR 2+ signals Alerta OR score >= 10
    - Normal: Otherwise
    """
    if num_anormal >= 2 or component_score >= 20:
        return 'Anormal'
    elif num_anormal >= 1 or num_alerta >= 2 or component_score >= 10:
        return 'Alerta'
    else:
        return 'Normal'


def aggregate_components(signal_evaluations, component_mapping):
    """
    Roll up signal grades to component level
    
    Returns:
        List of component evaluation dicts
    """
    df = pd.DataFrame(signal_evaluations)
    component_evaluations = []
    
    # Group by unit and component
    for (unit, component), group in df.groupby(['unit', 'component']):
        latest_date = group['timestamp'].max()
        component_score = group['score'].sum()
        
        # Count grades
        grade_counts = group['grade'].value_counts().to_dict()
        num_anormal = grade_counts.get('Anormal', 0)
        num_alerta = grade_counts.get('Alerta', 0)
        num_normal = grade_counts.get('Normal', 0)
        
        # Assign component grade
        component_grade = assign_component_grade(
            num_anormal, num_alerta, component_score
        )
        
        # Build signals_evaluation dict
        signals_eval_dict = {}
        for _, signal_row in group.iterrows():
            signals_eval_dict[signal_row['signal']] = {
                'grade': signal_row['grade'],
                'score': signal_row['score'],
                'value': signal_row['value'],
                'baseline_P50': signal_row['baseline_P50'],
                'baseline_P95': signal_row['baseline_P95'],
                'baseline_P99': signal_row['baseline_P99'],
                'deviation': signal_row['deviation'],
                'detection_methods': signal_row['detection_methods']
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
```

**Deliverables**:
- `src/telemetry/component_aggregator.py`

---

### Week 4: Machine Aggregation & Output

#### **Task 4.1: Machine Aggregator**

**Objective**: Roll up component grades to machine level

**Implementation**:

```python
# src/telemetry/machine_aggregator.py

def assign_machine_status(grade_counts):
    """
    Assign overall machine status
    
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


def aggregate_machines(component_evaluations, weights):
    """
    Roll up component grades to machine level
    
    Args:
        component_evaluations: List of component dicts
        weights: Dict of component weights for priority scoring
    
    Returns:
        DataFrame with machine status
    """
    df = pd.DataFrame(component_evaluations)
    machine_status_list = []
    
    # Group by unit
    for unit, group in df.groupby('unit'):
        latest_date = group['date'].max()
        machine_score = group['component_score'].sum()
        
        # Calculate priority score (weighted)
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
        
        # Assign overall status
        overall_status = assign_machine_status(grade_counts)
        
        # Build component_details list
        component_details = []
        for _, comp_row in group.iterrows():
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
            'client': 'cda',  # TODO: parameterize
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
```

**Deliverables**:
- `src/telemetry/machine_aggregator.py`

---

#### **Task 4.2: Output Writer**

**Objective**: Write final parquet files

**Implementation**:

```python
# src/telemetry/output_writer.py

def write_machine_status(machine_status_df, client):
    """Write machine_status.parquet"""
    output_path = f'data/telemetry/golden/{client}/machine_status.parquet'
    machine_status_df.to_parquet(output_path, index=False, compression='snappy')
    logger.info(f"Wrote {len(machine_status_df)} machines to {output_path}")


def write_classified(component_evaluations, client):
    """Write classified.parquet"""
    df = pd.DataFrame(component_evaluations)
    
    # Add empty ai_recommendation column (for Phase 1)
    df['ai_recommendation'] = None
    
    output_path = f'data/telemetry/golden/{client}/classified.parquet'
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.info(f"Wrote {len(df)} components to {output_path}")
```

**Deliverables**:
- `src/telemetry/output_writer.py`
- `machine_status.parquet`
- `classified.parquet`

---

#### **Task 4.3: Main Orchestration**

**Objective**: Tie everything together

**Implementation**:

```python
# src/telemetry/main.py

def main(client='cda', week=None, year=None):
    """Main telemetry analysis pipeline"""
    
    # Setup
    logger = setup_logger()
    config = load_config('config/telemetry_config.yaml')
    
    if week is None or year is None:
        week, year = get_current_week_year()
    
    logger.info(f"Starting analysis for Week {week}, Year {year}")
    
    # STEP 1: Load Data
    component_mapping = load_component_mapping()
    current_week_data = load_telemetry_week(client, week, year)
    historical_data = load_historical_weeks(
        client, week, year, 
        lookback_weeks=config['baseline_weeks']
    )
    
    # STEP 2: Calculate Baselines
    baselines = calculate_baselines(
        historical_data,
        signals=get_all_signals(component_mapping),
        percentiles=config['percentiles']
    )
    save_baselines(baselines, client)
    
    # STEP 3: Evaluate Signals
    signal_evaluations = evaluate_signals(
        current_week_data, baselines, component_mapping
    )
    
    # STEP 4: Aggregate Components
    component_evaluations = aggregate_components(
        signal_evaluations, component_mapping
    )
    
    # STEP 5: Aggregate Machines
    machine_status = aggregate_machines(
        component_evaluations,
        weights=config['component_weights']
    )
    
    # STEP 6: Write Outputs
    write_machine_status(machine_status, client)
    write_classified(component_evaluations, client)
    
    # Summary
    summary = generate_summary(machine_status)
    logger.info(f"Analysis complete: {summary}")
    
    return machine_status
```

**Deliverables**:
- `src/telemetry/main.py`
- Complete working pipeline

---

### MVP Success Criteria

- ✅ Processes 1 week of data in <5 minutes
- ✅ Outputs valid parquet files with correct schema
- ✅ All tests pass
- ✅ Dashboard displays data correctly
- ✅ Grades match manual inspection for 80%+ of units

---

## 🤖 MEDIUM-TERM: AI & Advanced Features

**Duration**: 12-16 weeks  
**Goal**: Enhance MVP with AI recommendations and advanced detection

---

## Phase 1: AI Integration (Weeks 5-8)

**Duration**: 2-3 weeks  
**Goal**: Add human-readable AI-generated maintenance recommendations

### Overview

Enhance the classified.parquet output with AI-powered insights that explain:
- Why a component is flagged
- What maintenance action to take
- Urgency level

---

### Week 5-6: LLM Integration

#### **Task 1.1: Design Prompt Templates**

**Objective**: Create structured prompts for consistent recommendations

**Implementation**:

```python
# src/telemetry/ai_prompts.py

def build_recommendation_prompt(component_eval, signal_details, historical_context=None):
    """
    Build LLM prompt for component recommendation
    
    Args:
        component_eval: Dict with component status, score
        signal_details: Dict with signal evaluations
        historical_context: Optional dict with trend info
    
    Returns:
        String prompt for LLM
    """
    
    # Extract critical signals (Anormal or Alerta)
    critical_signals = [
        (signal, details) 
        for signal, details in signal_details.items()
        if details['grade'] in ['Anormal', 'Alerta']
    ]
    
    # Build signal evidence section
    evidence_lines = []
    for signal, details in critical_signals:
        evidence_lines.append(
            f"- {signal}: {details['value']:.2f} "
            f"(Baseline P99: {details['baseline_P99']:.2f}) - "
            f"{details['deviation']}"
        )
    
    evidence_text = "\n".join(evidence_lines)
    
    # Build prompt
    prompt = f"""You are a mining equipment maintenance expert analyzing telemetry data.

Component: {component_eval['component']} (Unit {component_eval['unit']})
Status: {component_eval['component_status']} (Score: {component_eval['component_score']})

Signal Evidence:
{evidence_text}

Task: Provide a concise maintenance recommendation (2-3 sentences) that explains:
1. What likely caused these readings
2. What maintenance action should be taken
3. Urgency level (Immediate, Within 24h, Within Week, Monitor)

Keep response professional and actionable for field technicians."""
    
    return prompt
```

**Deliverables**:
- `src/telemetry/ai_prompts.py`
- Validated prompts with sample data

---

#### **Task 1.2: LLM API Integration**

**Implementation**:

```python
# src/telemetry/ai_recommender.py

import openai  # or anthropic, etc.
from functools import lru_cache
import hashlib
import json

# Initialize API client
openai.api_key = os.getenv('OPENAI_API_KEY')


def generate_ai_recommendation(component_eval, signal_details, historical_context=None):
    """
    Generate AI recommendation for component
    
    Returns:
        String with AI recommendation
    """
    
    # Skip if component is Normal (save API costs)
    if component_eval['component_status'] == 'Normal':
        return "Component operating normally."
    
    # Build prompt
    prompt = build_recommendation_prompt(
        component_eval, signal_details, historical_context
    )
    
    # Check cache first
    recommendation = get_cached_recommendation(prompt)
    if recommendation:
        return recommendation
    
    # Call LLM
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a mining equipment maintenance expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        recommendation = response.choices[0].message.content.strip()
        
        # Cache result
        cache_recommendation(prompt, recommendation)
        
        return recommendation
    
    except Exception as e:
        logger.error(f"AI recommendation failed: {e}")
        return "AI recommendation unavailable. Please review signal details manually."


def get_cached_recommendation(prompt):
    """Check cache for similar prompt"""
    # Simple hash-based caching (can use Redis for production)
    cache_key = hashlib.md5(prompt.encode()).hexdigest()
    # Load from cache file/database
    return None  # Implement caching logic


def cache_recommendation(prompt, recommendation):
    """Store recommendation in cache"""
    # Implement caching logic
    pass
```

**Deliverables**:
- `src/telemetry/ai_recommender.py`
- API integration tested
- Caching implemented

---

### Week 7-8: Integration & Dashboard Updates

#### **Task 1.3: Enhance Component Aggregator**

**Modification**:

```python
# Update src/telemetry/component_aggregator.py

def aggregate_components(signal_evaluations, component_mapping, enable_ai=True):
    """Roll up signals to components, optionally add AI recommendations"""
    
    # ... existing aggregation logic ...
    
    # Add AI recommendations
    for component_eval in component_evaluations:
        if enable_ai:
            recommendation = generate_ai_recommendation(
                component_eval,
                component_eval['signals_evaluation']
            )
            component_eval['ai_recommendation'] = recommendation
        else:
            component_eval['ai_recommendation'] = None
    
    return component_evaluations
```

**Deliverables**:
- Updated `component_aggregator.py`
- classified.parquet now includes `ai_recommendation` column

---

#### **Task 1.4: Dashboard Integration**

**Objective**: Display AI recommendations in dashboard

**Updates**:
- Tab 2 (Component Analysis): Add "AI Insights" card
- Tab 3 (Signal Trends): Show recommendation in sidebar

**Example Display**:
```
┌────────────────────────────────────────┐
│ 💡 AI Recommendation - Motor          │
│                                        │
│ "Engine coolant temperature has        │
│  exceeded normal range consistently... │
│                                        │
│  Recommended Action: Inspect cooling   │
│  system and thermostat.                │
│                                        │
│  Urgency: Within 24 hours"            │
└────────────────────────────────────────┘
```

**Deliverables**:
- Updated Dash components
- AI recommendations visible in UI

---

### Phase 1 Success Metrics

- ✅ AI recommendations generated for 100% of Alerta/Anormal components
- ✅ Average generation time <2 seconds per recommendation
- ✅ User survey: 80%+ find recommendations helpful
- ✅ API cost: <$0.10 per analysis run

---

## Phase 2: Enhanced Detection - Autoencoder Neural Network (Weeks 9-14)

**Duration**: 4-6 weeks  
**Goal**: Implement ANN-based anomaly detection using encoder-decoder architecture

### Overview

Train autoencoder neural networks to learn normal signal patterns and detect anomalies through reconstruction error. This provides a more sophisticated detection method that captures complex, multivariate patterns.

---

### Week 9-10: ANN Architecture Design & Training

#### **Task 2.1: Define Autoencoder Architecture**

**Objective**: Design encoder-decoder network structure

**Architecture**:
```
Component: Motor (10 signals)
Input Layer:    [10 neurons] ← Normalized signal values
    ↓
Encoder:
    Dense(12, activation='relu')
    Dense(8, activation='relu')  
    Dense(4, activation='relu')  ← Latent space
    ↓
Decoder:
    Dense(8, activation='relu')
    Dense(12, activation='relu')
    Dense(10, activation='linear') ← Reconstructed signals
    ↓
Output: Reconstruction Error = MSE(Input, Output)
```

**Implementation**:

```python
# src/telemetry/autoencoder_model.py

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

def build_autoencoder(input_dim, latent_dim=4):
    """
    Build encoder-decoder autoencoder
    
    Args:
        input_dim: Number of input signals (e.g., 10 for Motor)
        latent_dim: Dimension of latent space
    
    Returns:
        Compiled Keras model
    """
    # Input
    input_layer = layers.Input(shape=(input_dim,))
    
    # Encoder
    encoder = layers.Dense(12, activation='relu', name='encoder_1')(input_layer)
    encoder = layers.Dense(8, activation='relu', name='encoder_2')(encoder)
    latent = layers.Dense(latent_dim, activation='relu', name='latent')(encoder)
    
    # Decoder
    decoder = layers.Dense(8, activation='relu', name='decoder_1')(latent)
    decoder = layers.Dense(12, activation='relu', name='decoder_2')(decoder)
    output_layer = layers.Dense(input_dim, activation='linear', name='output')(decoder)
    
    # Model
    autoencoder = keras.Model(inputs=input_layer, outputs=output_layer, name='autoencoder')
    
    # Compile
    autoencoder.compile(
        optimizer='adam',
        loss='mse',
        metrics=['mae']
    )
    
    return autoencoder
```

**Deliverables**:
- `src/telemetry/autoencoder_model.py`
- Architecture validated

---

#### **Task 2.2: Training Pipeline**

**Objective**: Train separate autoencoders per component and operational state

**Implementation**:

```python
# src/telemetry/autoencoder_trainer.py

from sklearn.preprocessing import StandardScaler
import joblib

def prepare_training_data(historical_data, component, signals, state):
    """
    Prepare training data for autoencoder
    
    Args:
        historical_data: DataFrame with historical telemetry
        component: Component name (e.g., 'Motor')
        signals: List of signal names for this component
        state: Operational state to filter by
    
    Returns:
        Tuple of (X_train, scaler)
    """
    # Filter to specific state
    state_data = historical_data[
        historical_data['CompositeState'] == state
    ]
    
    # Extract signal columns
    X = state_data[signals].dropna()
    
    # Only use "Normal" graded data for training (if available)
    # This requires joining with previous grades - optional for first iteration
    
    # Normalize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    return X_scaled, scaler


def train_autoencoder(X_train, input_dim, epochs=50, validation_split=0.2):
    """
    Train autoencoder on normal data
    
    Args:
        X_train: Normalized training data
        input_dim: Number of input features
        epochs: Training epochs
        validation_split: Validation data percentage
    
    Returns:
        Tuple of (model, history)
    """
    # Build model
    model = build_autoencoder(input_dim)
    
    # Early stopping
    early_stop = keras.callbacks.EarlyStopping(
        monitor='val_loss',
        patience=5,
        restore_best_weights=True
    )
    
    # Train (input = output for autoencoders)
    history = model.fit(
        X_train, X_train,
        epochs=epochs,
        batch_size=32,
        validation_split=validation_split,
        callbacks=[early_stop],
        verbose=1
    )
    
    return model, history


def calculate_reconstruction_error_thresholds(model, X_train):
    """
    Calculate P95 and P99 of reconstruction errors for thresholds
    
    Args:
        model: Trained autoencoder
        X_train: Training data
    
    Returns:
        Dict with threshold values
    """
    # Get predictions
    X_pred = model.predict(X_train, verbose=0)
    
    # Calculate reconstruction error (MSE per sample)
    reconstruction_errors = np.mean((X_train - X_pred) ** 2, axis=1)
    
    # Calculate thresholds
    thresholds = {
        'P95': np.percentile(reconstruction_errors, 95),  # Alerta threshold
        'P99': np.percentile(reconstruction_errors, 99),  # Anormal threshold
        'mean': np.mean(reconstruction_errors),
        'std': np.std(reconstruction_errors)
    }
    
    return thresholds


def train_all_autoencoders(historical_data, component_mapping):
    """
    Train autoencoders for all components and states
    
    Returns:
        Dict of models and metadata
    """
    models = {}
    
    for component, signals in component_mapping.items():
        # Get unique states for this component's data
        states = historical_data['CompositeState'].unique()
        
        for state in states:
            # Prepare training data
            X_train, scaler = prepare_training_data(
                historical_data, component, signals, state
            )
            
            # Skip if insufficient data
            if len(X_train) < 500:
                logger.warning(
                    f"Insufficient data for {component}-{state}: {len(X_train)}"
                )
                continue
            
            # Train autoencoder
            model, history = train_autoencoder(X_train, input_dim=len(signals))
            
            # Calculate thresholds
            thresholds = calculate_reconstruction_error_thresholds(model, X_train)
            
            # Store
            model_key = f"{component}_{state}"
            models[model_key] = {
                'model': model,
                'scaler': scaler,
                'thresholds': thresholds,
                'signals': signals,
                'training_samples': len(X_train)
            }
            
            logger.info(
                f"Trained autoencoder for {model_key}: "
                f"P99 threshold = {thresholds['P99']:.6f}"
            )
    
    return models
```

**Deliverables**:
- `src/telemetry/autoencoder_trainer.py`
- Trained models saved (`models/autoencoders/{component}_{state}.h5`)
- Scaler objects saved
- Threshold values stored

---

### Week 11-12: Inference & Integration

#### **Task 2.3: ANN Anomaly Detection**

**Objective**: Use trained autoencoders to detect anomalies in new data

**Implementation**:

```python
# src/telemetry/autoencoder_detector.py

def load_autoencoder_models(model_dir='models/autoencoders'):
    """Load all trained autoencoder models"""
    models = {}
    
    for model_file in Path(model_dir).glob('*.h5'):
        model_key = model_file.stem  # e.g., 'Motor_Operacional-Cargado'
        
        # Load model
        model = keras.models.load_model(model_file)
        
        # Load associated scaler and thresholds
        scaler = joblib.load(model_file.with_suffix('.scaler.pkl'))
        thresholds = joblib.load(model_file.with_suffix('.thresholds.pkl'))
        
        models[model_key] = {
            'model': model,
            'scaler': scaler,
            'thresholds': thresholds
        }
    
    return models


def detect_anomalies_with_autoencoder(data_row, component, state, signals, autoencoder_models):
    """
    Detect anomalies using autoencoder reconstruction error
    
    Args:
        data_row: Series with signal values
        component: Component name
        state: Operational state
        signals: List of signals for this component
        autoencoder_models: Dict of loaded models
    
    Returns:
        Dict with anomaly detection results
    """
    model_key = f"{component}_{state}"
    
    # Check if model exists for this component-state
    if model_key not in autoencoder_models:
        return None
    
    model_data = autoencoder_models[model_key]
    model = model_data['model']
    scaler = model_data['scaler']
    thresholds = model_data['thresholds']
    
    # Extract signal values
    try:
        X = np.array([data_row[sig] for sig in signals]).reshape(1, -1)
    except KeyError:
        return None
    
    # Normalize
    X_scaled = scaler.transform(X)
    
    # Predict (reconstruct)
    X_pred = model.predict(X_scaled, verbose=0)
    
    # Calculate reconstruction error
    reconstruction_error = np.mean((X_scaled - X_pred) ** 2)
    
    # Grade based on error
    if reconstruction_error > thresholds['P99']:
        grade = 'Anormal'
        score = 10
    elif reconstruction_error > thresholds['P95']:
        grade = 'Alerta'
        score = 5
    else:
        grade = 'Normal'
        score = 0
    
    return {
        'grade': grade,
        'score': score,
        'reconstruction_error': reconstruction_error,
        'threshold_P95': thresholds['P95'],
        'threshold_P99': thresholds['P99'],
        'detection_method': 'autoencoder'
    }
```

**Deliverables**:
- `src/telemetry/autoencoder_detector.py`
- Inference pipeline tested

---

#### **Task 2.4: Ensemble Detection (Combine Methods)**

**Objective**: Integrate autoencoder results with percentile baseline

**Strategy**: Use ensemble approach where both methods contribute to final grade

**Implementation**:

```python
# src/telemetry/enhanced_signal_evaluator.py

def evaluate_signal_ensemble(
    signal, value, state, baselines, 
    autoencoder_models, component, signals,
    data_row
):
    """
    Enhanced signal evaluation using ensemble of methods
    
    Strategy:
    1. Run percentile baseline detection (Method 1)
    2. Run autoencoder detection (Method 2) - component level
    3. Combine results: Take most severe grade
    
    Returns:
        Dict with grade, score, and detection methods used
    """
    results = {
        'signal': signal,
        'value': value,
        'state': state,
        'grade': 'Normal',
        'score': 0,
        'triggered_by': []
    }
    
    # Method 1: Percentile baseline (signal-level)
    baseline = find_matching_baseline(baselines, signal, state)
    if baseline is not None:
        percentile_grade, percentile_score = grade_signal_value(value, baseline)
        if percentile_grade != 'Normal':
            results['grade'] = percentile_grade
            results['score'] = max(results['score'], percentile_score)
            results['triggered_by'].append('percentile_baseline')
    
    # Method 2: Autoencoder (component-level, run once per component)
    # Only evaluate at component level, not per signal
    # This is handled separately in component aggregation
    
    return results


def aggregate_components_with_ann(signal_evaluations, component_mapping, autoencoder_models, current_data):
    """
    Enhanced component aggregation with autoencoder detection
    
    Strategy:
    1. Aggregate signal grades (percentile baseline) - existing logic
    2. Run autoencoder detection per component
    3. Combine: Take most severe grade
    """
    component_evaluations = []
    df = pd.DataFrame(signal_evaluations)
    
    # Group by unit and component
    for (unit, component), group in df.groupby(['unit', 'component']):
        # Get component data row
        latest_timestamp = group['timestamp'].max()
        data_row = current_data[
            (current_data['Unit'] == unit) & 
            (current_data['Fecha'] == latest_timestamp)
        ].iloc[0]
        
        state = data_row['CompositeState']
        signals = component_mapping[component]
        
        # Standard aggregation (percentile baseline)
        component_score_baseline = group['score'].sum()
        grade_counts = group['grade'].value_counts().to_dict()
        component_grade_baseline = assign_component_grade(
            grade_counts.get('Anormal', 0),
            grade_counts.get('Alerta', 0),
            component_score_baseline
        )
        
        # Autoencoder detection (component-level)
        ann_result = detect_anomalies_with_autoencoder(
            data_row, component, state, signals, autoencoder_models
        )
        
        # Combine results (take most severe)
        if ann_result:
            final_grade = max_severity(component_grade_baseline, ann_result['grade'])
            final_score = max(component_score_baseline, ann_result['score'])
            
            detection_methods = ['percentile_baseline']
            if ann_result['grade'] != 'Normal':
                detection_methods.append('autoencoder')
        else:
            final_grade = component_grade_baseline
            final_score = component_score_baseline
            detection_methods = ['percentile_baseline']
        
        # Build component evaluation
        component_eval = {
            'unit': unit,
            'date': latest_timestamp,
            'component': component,
            'component_status': final_grade,
            'component_score': final_score,
            'signals_evaluation': {},  # Build as before
            'detection_methods': detection_methods,
            'autoencoder_result': ann_result  # Store for debugging
        }
        
        component_evaluations.append(component_eval)
    
    return component_evaluations
```

**Deliverables**:
- `src/telemetry/enhanced_signal_evaluator.py`
- Ensemble detection working

---

### Week 13-14: Validation & Optimization

#### **Task 2.5: Model Validation**

**Objective**: Validate autoencoder performance

**Actions**:
- Test on historical weeks with known issues
- Calculate precision/recall metrics
- Tune thresholds if needed
- Document false positives/negatives

**Metrics**:
- Precision: % of flagged components that are true issues
- Recall: % of true issues that were flagged
- F1 Score: Harmonic mean of precision and recall

**Deliverables**:
- Validation report
- Tuned hyperparameters

---

#### **Task 2.6: Retraining Pipeline**

**Objective**: Enable periodic model retraining

**Implementation**:
- Schedule: Retrain autoencoders monthly with latest data
- Use last 2-3 months of "Normal" graded data
- Version models (e.g., `Motor_Operacional_v2.h5`)

**Deliverables**:
- `src/telemetry/autoencoder_retrainer.py`
- Scheduling script

---

### Phase 2 Success Metrics

- ✅ Autoencoder models trained for all component-state combinations
- ✅ Precision: 90%+ (low false positives)
- ✅ Recall: 85%+ (catches most true issues)
- ✅ Ensemble detection improves MVP by 15%+ in accuracy
- ✅ Inference time: <1 second per component

---

## Phase 3: New Features - Forecasting & Clustering (Weeks 15-20)

**Duration**: 4-6 weeks  
**Goal**: Add predictive and behavioral analysis capabilities

### Overview

Implement two advanced features:
1. **Time Series Forecasting**: Predict future sensor values and time-to-failure
2. **Operational Clustering**: Identify operational modes and measure deviations

---

### Week 15-17: Time Series Forecasting

#### **Task 3.1: Forecasting Implementation**

**Objective**: Predict sensor trajectories 24-72 hours ahead

**Method Options**:
- **LSTM**: Deep learning approach, best for complex patterns
- **Prophet**: Facebook's time series lib, handles seasonality well
- **ARIMA**: Statistical approach, simpler and faster

**Recommended**: Start with Prophet for ease of use

**Implementation**:

```python
# src/telemetry/forecasting.py

from prophet import Prophet
import pandas as pd

def prepare_forecast_data(historical_data, signal, unit):
    """
    Prepare data for Prophet forecasting
    
    Args:
        historical_data: DataFrame with historical telemetry
        signal: Signal name to forecast
        unit: Unit identifier
    
    Returns:
        DataFrame in Prophet format (ds, y columns)
    """
    # Filter to specific unit
    unit_data = historical_data[historical_data['Unit'] == unit].copy()
    
    # Prepare for Prophet
    df_prophet = unit_data[['Fecha', signal]].rename(
        columns={'Fecha': 'ds', signal: 'y'}
    ).dropna()
    
    return df_prophet


def train_forecast_model(df_prophet, signal_name):
    """
    Train Prophet model for signal forecasting
    
    Args:
        df_prophet: DataFrame with ds, y columns
        signal_name: Name of signal (for logging)
    
    Returns:
        Trained Prophet model
    """
    model = Prophet(
        changepoint_prior_scale=0.05,
        seasonality_mode='multiplicative',
        daily_seasonality=True,
        weekly_seasonality=False  # Adjust based on data
    )
    
    model.fit(df_prophet)
    logger.info(f"Trained forecast model for {signal_name}")
    
    return model


def forecast_signal(model, periods=72, freq='H'):
    """
    Generate forecast for next N hours
    
    Args:
        model: Trained Prophet model
        periods: Number of periods to forecast (default: 72 hours)
        freq: Frequency ('H' for hourly)
    
    Returns:
        DataFrame with forecasted values and confidence intervals
    """
    # Make future dataframe
    future = model.make_future_dataframe(periods=periods, freq=freq)
    
    # Forecast
    forecast = model.predict(future)
    
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]


def predict_time_to_failure(forecast, baselines, signal):
    """
    Estimate when forecasted values will exceed thresholds
    
    Args:
        forecast: DataFrame from forecast_signal
        baselines: Baseline percentiles for signal
        signal: Signal name
    
    Returns:
        Dict with time-to-threshold estimates
    """
    # Get future forecasts only (exclude historical)
    now = pd.Timestamp.now()
    future_forecast = forecast[forecast['ds'] > now]
    
    results = {}
    
    # Check when yhat exceeds P95 (Alerta threshold)
    alerta_threshold = baselines[baselines['signal'] == signal]['P95'].values[0]
    alerta_violations = future_forecast[future_forecast['yhat'] > alerta_threshold]
    
    if not alerta_violations.empty:
        first_violation = alerta_violations.iloc[0]['ds']
        hours_until = (first_violation - now).total_seconds() / 3600
        results['time_to_alerta_hours'] = hours_until
        results['time_to_alerta'] = first_violation
    else:
        results['time_to_alerta_hours'] = None
        results['time_to_alerta'] = None
    
    # Check when yhat exceeds P99 (Anormal threshold)
    anormal_threshold = baselines[baselines['signal'] == signal]['P99'].values[0]
    anormal_violations = future_forecast[future_forecast['yhat'] > anormal_threshold]
    
    if not anormal_violations.empty:
        first_violation = anormal_violations.iloc[0]['ds']
        hours_until = (first_violation - now).total_seconds() / 3600
        results['time_to_anormal_hours'] = hours_until
        results['time_to_anormal'] = first_violation
    else:
        results['time_to_anormal_hours'] = None
        results['time_to_anormal'] = None
    
    return results


def generate_forecasts_for_critical_signals(historical_data, current_status, baselines):
    """
    Generate forecasts for signals in components flagged as Alerta or Anormal
    
    Args:
        historical_data: Historical telemetry (last 4-8 weeks)
        current_status: Current machine status DataFrame
        baselines: Baseline percentiles
    
    Returns:
        Dict of forecasts keyed by (unit, signal)
    """
    forecasts = {}
    
    # Get units with issues
    problem_units = current_status[
        current_status['overall_status'].isin(['Alerta', 'Anormal'])
    ]
    
    for _, unit_row in problem_units.iterrows():
        unit = unit_row['unit_id']
        
        # Get critical signals for this unit
        for comp_detail in unit_row['component_details']:
            if comp_detail['status'] != 'Normal':
                for signal in comp_detail['critical_signals']:
                    # Prepare data
                    df_prophet = prepare_forecast_data(
                        historical_data, signal, unit
                    )
                    
                    if len(df_prophet) < 100:  # Need sufficient history
                        continue
                    
                    # Train and forecast
                    model = train_forecast_model(df_prophet, f"{unit}_{signal}")
                    forecast = forecast_signal(model, periods=72)
                    
                    # Predict time to failure
                    ttf = predict_time_to_failure(forecast, baselines, signal)
                    
                    forecasts[(unit, signal)] = {
                        'forecast': forecast,
                        'time_to_failure': ttf
                    }
                    
                    logger.info(
                        f"Forecast for {unit}-{signal}: "
                        f"Alerta in {ttf.get('time_to_alerta_hours', 'N/A')} hours"
                    )
    
    return forecasts
```

**Deliverables**:
- `src/telemetry/forecasting.py`
- Forecasts generated for critical signals
- Time-to-failure estimates

---

#### **Task 3.2: Dashboard Integration**

**Objective**: Visualize forecasts in dashboard

**New Dashboard Tab**: "Forecasting" (or add to Tab 3)

**Visualizations**:
- Line chart: Historical + Forecasted signal values
- Confidence interval shading
- Threshold lines (P95, P99)
- Time-to-failure countdown cards

**Example**:
```
┌────────────────────────────────────────────────────────┐
│ 📈 Forecast: EngCoolTemp (Unit 247)                   │
│                                                        │
│ [Line Chart]                                           │
│ - Historical values (solid line)                      │
│ - Forecasted values (dashed line)                     │
│ - Confidence interval (shaded area)                   │
│ - P95 threshold (yellow horizontal line)              │
│ - P99 threshold (red horizontal line)                 │
│                                                        │
│ ⚠️  Projected to exceed Alerta threshold in 36 hours │
└────────────────────────────────────────────────────────┘
```

**Deliverables**:
- Updated dashboard components
- Forecast visualization functional

---

### Week 18-20: Operational Clustering

#### **Task 3.3: Clustering Implementation**

**Objective**: Identify operational modes and measure deviations

**Implementation**:

```python
# src/telemetry/operational_clustering.py

from sklearn.cluster import DBSCAN, KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

def prepare_clustering_features(historical_data, feature_columns):
    """
    Prepare features for clustering
    
    Args:
        historical_data: DataFrame with telemetry
        feature_columns: Signals + operational features to use
    
    Returns:
        Tuple of (X_scaled, scaler, feature_names)
    """
    # Select features (signals + derived features)
    features = feature_columns.copy()
    
    # Add derived features
    historical_data['Payload_Norm'] = (
        historical_data['Payload'] / historical_data['Payload'].max()
    )
    historical_data['Speed_Norm'] = (
        historical_data['GroundSpd'] / historical_data['GroundSpd'].max()
    )
    
    features.extend(['Payload_Norm', 'Speed_Norm', 'GPSElevation'])
    
    # Extract
    X = historical_data[features].dropna()
    
    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    return X_scaled, scaler, features


def train_clustering_model(X_scaled, method='kmeans', n_clusters=5):
    """
    Train clustering model to identify operational modes
    
    Args:
        X_scaled: Scaled feature matrix
        method: 'kmeans' or 'dbscan'
        n_clusters: Number of clusters (for k-means)
    
    Returns:
        Trained clustering model
    """
    if method == 'kmeans':
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        model.fit(X_scaled)
    elif method == 'dbscan':
        model = DBSCAN(eps=0.5, min_samples=50)
        model.fit(X_scaled)
    else:
        raise ValueError(f"Unknown clustering method: {method}")
    
    return model


def analyze_cluster_characteristics(clustered_data, cluster_id):
    """
    Describe what defines a cluster
    
    Args:
        clustered_data: DataFrame with cluster labels
        cluster_id: Cluster to analyze
    
    Returns:
        Dict with cluster statistics
    """
    cluster_data = clustered_data[
        clustered_data['operational_cluster'] == cluster_id
    ]
    
    characteristics = {
        'cluster_id': cluster_id,
        'sample_count': len(cluster_data),
        'avg_payload': cluster_data['Payload'].mean(),
        'std_payload': cluster_data['Payload'].std(),
        'avg_speed': cluster_data['GroundSpd'].mean(),
        'avg_elevation': cluster_data['GPSElevation'].mean(),
        'predominant_state': cluster_data['Estado'].mode()[0] if len(cluster_data) > 0 else 'Unknown',
        'name': assign_cluster_name(cluster_data)  # Human-readable name
    }
    
    return characteristics


def assign_cluster_name(cluster_data):
    """Assign human-readable name to cluster based on characteristics"""
    avg_payload = cluster_data['Payload'].mean()
    avg_speed = cluster_data['GroundSpd'].mean()
    avg_elevation = cluster_data['GPSElevation'].mean()
    
    # Simple heuristic naming
    if avg_payload > 200 and avg_speed > 20:
        return "Heavy Load Transport"
    elif avg_payload > 200 and avg_speed < 10:
        return "Heavy Load Stopped/Slow"
    elif avg_payload < 50 and avg_speed > 20:
        return "Unloaded Travel"
    elif avg_speed < 5:
        return "Idle/Stationary"
    else:
        return "Mixed Operation"


def calculate_deviation_from_clusters(new_data, clustering_model, scaler, features):
    """
    Calculate how far new data is from cluster centers
    
    Args:
        new_data: DataFrame with new readings
        clustering_model: Trained clustering model
        scaler: Fitted scaler
        features: Feature names
    
    Returns:
        DataFrame with cluster assignments and deviation scores
    """
    # Prepare new data
    X_new = new_data[features].dropna()
    X_new_scaled = scaler.transform(X_new)
    
    # Predict cluster assignment
    clusters = clustering_model.predict(X_new_scaled)
    
    # Calculate distance to assigned cluster center
    if hasattr(clustering_model, 'cluster_centers_'):  # K-Means
        centers = clustering_model.cluster_centers_
        deviations = []
        
        for i, cluster_id in enumerate(clusters):
            center = centers[cluster_id]
            point = X_new_scaled[i]
            distance = np.linalg.norm(point - center)
            deviations.append(distance)
        
        new_data['operational_cluster'] = clusters
        new_data['cluster_deviation'] = deviations
    
    return new_data
```

**Deliverables**:
- `src/telemetry/operational_clustering.py`
- Clustering models trained
- Cluster characteristics documented

---

#### **Task 3.4: Dashboard Integration**

**Objective**: Display clustering insights

**New Visualizations**:
- **Cluster Membership Card**: Show which operational mode unit is in
- **Deviation Gauge**: How far from cluster center
- **Cluster Scatter Plot**: PCA projection showing clusters and current position

**Example**:
```
┌────────────────────────────────────────┐
│ 🎯 Operational Mode: Unit 247         │
│                                        │
│ Current Cluster: Heavy Load Transport │
│ Deviation: 0.45 (Normal range)        │
│                                        │
│ Cluster Characteristics:               │
│ - Avg Payload: 215 tonnes             │
│ - Avg Speed: 28 km/h                  │
│ - Typical Route: Main haul road       │
└────────────────────────────────────────┘
```

**Deliverables**:
- Updated dashboard with clustering visualizations
- Deviation alerts for units operating outside expected modes

---

### Phase 3 Success Metrics

- ✅ **Forecasting**: 70%+ accuracy for 48h predictions
- ✅ **Forecasting**: Time-to-failure estimates within ±6 hours
- ✅ **Clustering**: Identify 3-5 meaningful operational modes
- ✅ **Clustering**: 90%+ of operations fall within identified clusters
- ✅ **User Value**: Maintenance scheduling optimized using forecasts

---

## 🧪 Testing Strategy

### Unit Testing

**Per Module**:
- Test each function independently
- Use sample data fixtures
- Cover edge cases (missing data, outliers, boundary conditions)

**Example**:
```python
# tests/test_signal_evaluator.py

def test_grade_signal_value_normal():
    baseline = pd.Series({'P1': 50, 'P5': 55, 'P95': 85, 'P99': 90})
    grade, score = grade_signal_value(value=70, baseline=baseline)
    assert grade == 'Normal'
    assert score == 0

def test_grade_signal_value_anormal_high():
    baseline = pd.Series({'P1': 50, 'P5': 55, 'P95': 85, 'P99': 90})
    grade, score = grade_signal_value(value=95, baseline=baseline)
    assert grade == 'Anormal'
    assert score == 10
```

---

### Integration Testing

**Full Pipeline Tests**:
- Test end-to-end on historical weeks
- Validate output files generated correctly
- Cross-check machine_score calculations

**Example**:
```python
# tests/test_integration.py

def test_full_pipeline():
    result = main(client='cda', week=10, year=2025)
    
    # Validate outputs exist
    assert os.path.exists('data/telemetry/golden/cda/machine_status.parquet')
    assert os.path.exists('data/telemetry/golden/cda/classified.parquet')
    
    # Validate output structure
    machine_status = pd.read_parquet(
        'data/telemetry/golden/cda/machine_status.parquet'
    )
    assert 'unit_id' in machine_status.columns
    assert machine_status['overall_status'].isin(['Normal', 'Alerta', 'Anormal']).all()
    assert len(machine_status) > 0
```

---

### Validation Testing

**With Domain Experts**:
1. Select 10 units (mix of Normal, Alerta, Anormal)
2. Show evidence (time series, grades, AI recommendations)
3. Expert assessment: Do they agree?
4. Iterate and tune thresholds

**Metrics**:
- Agreement rate > 85%
- False positive rate < 15%

---

## 🚀 Deployment & Operations

### File Organization

```
telemetry_dashboard/
├── config/
│   └── telemetry_config.yaml
├── data/
│   └── telemetry/
│       ├── component_signals_mapping.json
│       ├── silver/{client}/Telemetry_Wide_With_States/
│       └── golden/{client}/
│           ├── machine_status.parquet
│           ├── classified.parquet
│           └── signal_baselines.parquet
├── models/
│   └── autoencoders/
│       └── {component}_{state}.h5
├── src/
│   ├── telemetry/
│   │   ├── main.py
│   │   ├── data_loaders.py
│   │   ├── baseline_calculator.py
│   │   ├── signal_evaluator.py
│   │   ├── component_aggregator.py
│   │   ├── machine_aggregator.py
│   │   ├── output_writer.py
│   │   ├── ai_prompts.py (Phase 1+)
│   │   ├── ai_recommender.py (Phase 1+)
│   │   ├── autoencoder_model.py (Phase 2+)
│   │   ├── autoencoder_trainer.py (Phase 2+)
│   │   ├── autoencoder_detector.py (Phase 2+)
│   │   ├── forecasting.py (Phase 3+)
│   │   └── operational_clustering.py (Phase 3+)
│   └── utils/
│       ├── date_utils.py
│       └── logger.py
├── tests/
├── notebooks/
│   └── telemetry_analysis_prototype.ipynb
├── requirements.txt
└── README.md
```

---

### Execution

**Command-Line**:
```bash
# Run for current week
python src/telemetry/main.py --client cda

# Run for specific week
python src/telemetry/main.py --client cda --week 10 --year 2025

# Enable AI recommendations
python src/telemetry/main.py --client cda --enable-ai

# Enable all methods
python src/telemetry/main.py --client cda --enable-ai --enable-ann --enable-forecast
```

**Scheduling** (every 8-12 hours):
```bash
# Cron job (Linux)
0 */8 * * * cd /path/to/project && python src/telemetry/main.py --client cda >> logs/cron.log 2>&1

# Task Scheduler (Windows)
# Create scheduled task to run script twice daily
```

---

### Configuration

**config/telemetry_config.yaml**:
```yaml
# Baseline calculation
baseline_weeks: 6
min_samples_for_baseline: 100

# Percentiles
percentiles: [1, 5, 25, 50, 75, 95, 99]

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

# Paths
paths:
  silver_base: 'data/telemetry/silver'
  golden_base: 'data/telemetry/golden'
  component_mapping: 'data/telemetry/component_signals_mapping.json'
  models: 'models/autoencoders'

# AI settings (Phase 1+)
ai:
  enabled: true
  model: 'gpt-4'
  temperature: 0.3
  max_tokens: 200
  cache_enabled: true

# Autoencoder settings (Phase 2+)
autoencoder:
  enabled: false
  latent_dim: 4
  epochs: 50
  retrain_frequency_days: 30

# Forecasting settings (Phase 3+)
forecasting:
  enabled: false
  periods: 72  # hours
  frequency: 'H'  # hourly

# Clustering settings (Phase 3+)
clustering:
  enabled: false
  method: 'kmeans'
  n_clusters: 5

# Logging
logging:
  level: 'INFO'
  file: 'logs/telemetry_analysis.log'
```

---

## ✅ Success Criteria Summary

### SHORT-TERM (MVP)
- ✅ Processing time < 5 minutes per week
- ✅ Grade accuracy: 80%+ agreement with experts
- ✅ All outputs generated correctly
- ✅ Dashboard functional and responsive

### MEDIUM-TERM (Phase 1-3)
- ✅ **Phase 1**: AI recommendations helpful (80%+ user satisfaction)
- ✅ **Phase 2**: ANN detection improves accuracy by 15%+
- ✅ **Phase 3**: Forecasts enable proactive scheduling

### BUSINESS IMPACT
- ✅ Reduce unplanned downtime by 20%+
- ✅ Optimize maintenance costs
- ✅ Extend equipment lifespan
- ✅ Improve fleet availability

---

## 📚 Related Documentation

- **[Project Overview](project_overview.md)**: Analysis methods and roadmap
- **[Data Contracts](data_contracts.md)**: Input/output schemas
- **[Dashboard Proposal](dashboard_proposal.md)**: Visualization strategy

---

**Document Status**: ✅ Approved (Version 2.0)  
**Total Timeline**: 16-20 weeks (4 weeks MVP + 12-16 weeks enhancements)  
**Next Action**: Begin Week 1 - Foundation

