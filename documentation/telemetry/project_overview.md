# Telemetry Analysis Project - Overview

**Version**: 2.0  
**Created**: February 18, 2026  
**Updated**: February 18, 2026  
**Owner**: Patricio Ortiz - Data Team
**Project Goal**: Automated equipment health monitoring through sensor data analysis

---

## 📋 Table of Contents

1. [Project Goal](#project-goal)
2. [Problem Statement](#problem-statement)
3. [Approach Overview](#approach-overview)
4. [Approved Analysis Methods](#approved-analysis-methods)
5. [Implementation Roadmap](#implementation-roadmap)
6. [Success Metrics](#success-metrics)

---

## 🎯 Project Goal

**Primary Objective**: Develop an automated system that grades the operational health of mining equipment (trucks, bulldozers) based on sensor telemetry data, running every 8-12 hours to provide early warning of equipment degradation.

**Hierarchical Grading System**:
```
Signals (Sensors) → Components → Machine
     ↓                  ↓            ↓
Temperature,      Motor,        Overall
Pressure,         Brakes,       Equipment
Speed, etc.       Powertrain    Health
```

**Output**: 
- **Machine Status**: Normal | Alerta | Anormal
- **Component Grades**: Individual health scores per system
- **Signal Evaluations**: Detailed sensor behavior analysis

---

## 🔍 Problem Statement

### Challenge
Detect **problematic behavior** in mining equipment sensors without:
- ❌ Labeled historical failure data
- ❌ Predefined failure patterns
- ❌ Manual expert inspection for every reading

### Constraints
- ✅ **Lightweight**: Must run every 8-12 hours efficiently
- ✅ **Unsupervised**: No training labels available
- ✅ **Explainable**: Results must be interpretable by maintenance teams
- ✅ **Scalable**: Handle multiple units across weeks of data

### Data Characteristics
- **Temporal**: Weekly parquet files with datetime-indexed readings
- **Multi-state**: Equipment operates in different states (Operational, Idle, Loaded, Unloaded)
- **Multi-dimensional**: 19 sensor signals across 4 components
- **Spatial context**: GPS coordinates available
- **Pre-processed**: Data comes pre-processed and aggregated with 5-minute moving window trends

---

## 🛠️ Approach Overview

### Three-Level Evaluation Strategy

#### **Level 1: Signal Evaluation** (Lowest Level)
- Analyze individual sensor readings (e.g., EngCoolTemp, BrakeTemp)
- Detect anomalies, out-of-range values, unusual patterns
- Grade each signal: Normal, Alerta, Anormal

#### **Level 2: Component Evaluation** (Middle Level)
- Aggregate signal evaluations per component (Motor, Brakes, Powertrain, Steering)
- Apply component-specific logic using `component_signals_mapping.json`
- Grade each component: Normal, Alerta, Anormal

#### **Level 3: Machine Evaluation** (Highest Level)
- Synthesize component grades into overall machine health
- Calculate priority score for maintenance scheduling
- Grade machine: Normal, Alerta, Anormal

### Grading Logic Flow
```
1. Read weekly parquet file (pre-processed with 5-min moving window)
2. For each signal in each component:
   → Apply detection method(s)
   → Assign signal grade
3. For each component:
   → Aggregate signal grades
   → Assign component grade
4. For each machine:
   → Aggregate component grades
   → Assign machine grade + priority score
5. Output: machine_status.parquet + classified.parquet
```

---

## ✅ Approved Analysis Methods

The following methods have been approved for implementation in this project, organized by implementation phase.

---

### **Short-Term Methods (MVP)**

These methods forFor **trending analysis** when patterns evolve over time

---

#### **Method 1: Percentile-Based Baseline**

**Description**: Establish "normal" behavior using historical percentiles (e.g., 5th-95th percentile range).

**How it works**:
- Build baseline from past weeks: P5, P50 (median), P95
- Grade current reading:
  - Normal: Between P5 and P95
  - Alerta: Between [P2-P5] or [P95-P98]
  - Anormal: Below P1 or above P99

**Pros**:
- ✅ Simple and interpretable
- ✅ Handles non-normal distributions well
- ✅ Easy to visualize (boxplots!)

**Cons**:
- ❌ Static baseline doesn't adapt quickly
- ❌ Requires representative historical data

---

#### **Method 2: State-Conditioned Analysis**

**Description**: Evaluate sensors differently based on operational state (Operacional, Ralenti, Cargado, Descargado).

**How it works**:
- Segment data by `Estado`, `EstadoMaquina`, `EstadoCarga`
- Apply separate baselines/thresholds per state
- Example: EngSpd = 1800 RPM is normal when operational, anormal when idle

**Pros**:
- ✅ Highly accurate by honoring operational context
- ✅ Reduces false positives
- ✅ Aligns with physical equipment behavior

**Cons**:
- ❌ Requires more data per state
- ❌ Slightly more complex logic

**When to use**: **Essential** for meaningful analysis (combine with other methods)


### **Medium-Term Methods (Enhancements)**

These methods enhance the MVP with advanced detection capabilities.

---

#### **Method 3: Autoencoder Neural Network (ANN)** 🚀 ADVANCED DETECTION
---

**Document Status**: ✅ Ready for Review  
**Recommended Starting Point**: Method 4 (Percentile Baseline) + Method 5 (State Conditioning)
**Description**: Use encoder-decoder neural network architecture to learn normal signal patterns and detect anomalies through reconstruction error.

**How it works**:
- **Training Phase**: 
  - Train autoencoder on historical "normal" data
  - Network learns to compress (encode) and reconstruct (decode) normal patterns
  - Normal data has low reconstruction error
- **Detection Phase**:
  - Pass new signals through trained autoencoder
  - Calculate reconstruction error
  - High reconstruction error = Anomaly (signal doesn't match learned patterns)

**Architecture**:
```
Input Layer (19 signals) 
    ↓
Encoder (Dense layers: 19 → 12 → 8 → 4)
    ↓
Latent Space (4 dimensions)
    ↓
Decoder (Dense layers: 4 → 8 → 12 → 19)
    ↓
Reconstructed Output (19 signals)
    
Reconstruction Error = MSE(Input, Output)
```

**Advantages**:
- ✅ **Captures complex patterns**: Learns non-linear relationships between signals
- ✅ **Unsupervised**: No labeled failure data needed
- ✅ **Component-aware**: Can train separate autoencoders per component
- ✅ **Multivariate**: Considers all signals simultaneously
- ✅ **Adaptive**: Can retrain periodically with new data

**Implementation Details**:
- State-conditioned: Train separate autoencoders per operational state
- Use last 4-8 weeks of "Normal" graded data for training
- Reconstruction error threshold: P95 of training errors = Alerta, P99 = Anormal

**Why encoder-decoder approach**:
- ✅ More sophisticated than Isolation Forest
- ✅ Learns temporal and cross-signal patterns
- ✅ Interpretable through reconstruction error per signal
- ✅ Can identify which signals contribute most to anomaly

---

#### **Method 4: Time Series Forecasting** 📈 PREDICTIVE CAPABILITY

**Description**: Predict future sensor behavior to enable proactive maintenance.

**How it works**:
- Use Prophet, ARIMA, or LSTM to forecast sensor trajectories
- Project signal values 24-72 hours into future
- Identify when forecasted values will exceed thresholds
- Enable "Time to Failure" predictions

**Use Cases**:
- "Motor coolant temp projected to reach critical level in 48 hours"
- "Brake temperature trending upward, intervention recommended within 3 days"
- Schedule maintenance before failure occurs

**Implementation**:
- Per-signal forecasting with confidence intervals
- State-aware: Different forecasts for different operational states
- Update forecasts daily with new data

**Advantages**:
- ✅ **Proactive**: Predict failures before they occur
- ✅ **Maintenance scheduling**: Optimize intervention timing
- ✅ **Cost savings**: Prevent emergency repairs

---

#### **Method 5: Operational Clustering** 🎯 BEHAVIORAL ANALYSIS

**Description**: Automatically identify operational modes and measure deviation from expected behavior.

**How it works**:
- **Clustering Phase**:
  - Use K-Means or DBSCAN on historical data
  - Identify distinct operational profiles (e.g., loaded uphill, unloaded flat terrain)
  - Each cluster represents a "normal" operating mode
- **Deviation Detection**:
  - For new data, find nearest cluster
  - Measure distance to cluster center
  - Large distance = Operating outside expected parameters

**Use Cases**:
- "Unit is operating 2.5σ away from typical loaded operation profile"
- "Current behavior doesn't match any known operational mode"
- Identify unusual usage patterns that may indicate operator issues

**Advantages**:
- ✅ **Discovers hidden patterns**: May find modes beyond manual Estado labels
- ✅ **Holistic view**: Considers all signals + GPS + states together
- ✅ **Contextual anomalies**: Detects "right signals, wrong combination"

---

## 🗺️ Implementation Roadmap

### **Short-Term (MVP) - 3-4 weeks**

**Methods**: Percentile-Based Baseline + State-Conditioned Analysis

**Deliverables**:
- Signal → Component → Machine grading
- machine_status.parquet
- classified.parquet (without AI recommendations)
- Dashboard (3 tabs) with boxplot visualizations

**Goal**: Functional system with "good enough" accuracy

---

### **Medium-Term (Enhancements) - 12-16 weeks**

#### **Phase 1: AI Integration** (2-3 weeks)
- Add AI-generated recommendations to classified.parquet
- LLM integration for human-readable insights
- Enhanced dashboard with AI insights display

#### **Phase 2: Enhanced Detection** (4-6 weeks)
- Implement Autoencoder Neural Network (encoder-decoder)
- Train per-component, per-state models
- Integrate reconstruction error grading with percentile baseline
- Ensemble approach: Combine statistical + ML methods

#### **Phase 3: New Features** (4-6 weeks)
- **Time Series Forecasting**: 
  - Implement LSTM or Prophet models
  - Generate 24-72h predictions
  - Add "Time to Failure" metrics
  - Dashboard: Forecast visualization tab
- **Operational Clustering**:
  - Train clustering models on historical data
  - Calculate deviation metrics
  - Dashboard: Cluster membership and deviation cards

**Goal**: Advanced AI-powered diagnostic and predictive system

---

🎯 Success Metrics

### Short-Term (MVP)
- ✅ False Positive Rate < 15%
- ✅ Processing time < 5 minutes per week's data
- ✅ Grade changes correlate with maintenance events
- ✅ Dashboard functional with all visualizations

### Medium-Term (Enhancements)
- ✅ **AI Recommendations**: 80%+ user satisfaction
- ✅ **Autoencoder Detection**: False positive rate < 10%
- ✅ **Forecasting**: 70%+ accuracy for 48h predictions
- ✅ **Clustering**: Identify 3-5 meaningful operational modes

### Business Impact
- ✅ Early detection: Flag issues 24-48h before operator notice
- ✅ Maintenance optimization: Reduce reactive repairs by 30%
- ✅ Downtime prevention: Catch critical failures proactively
- ✅ Cost savings: $X per unit per year (to be measured)

---

## 📚 Related Documentation

- **[Data Contracts](data_contracts.md)**: Input/output schemas and data structures
- **[Dashboard Proposal](dashboard_proposal.md)**: Visualization strategy and layout
- **[Final Implementation Plan](final_implementation_plan.md)**: Complete build and enhancement roadmap

---

**Document Status**: ✅ Approved (Version 2.0)  
**Implementation Priority**: Short-term MVP → AI Integration → Enhanced Detection → New Features