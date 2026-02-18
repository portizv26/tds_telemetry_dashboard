# Telemetry Analysis Project - Overview

**Version**: 1.0  
**Created**: February 18, 2026  
**Owner**: Telemetry Analysis Team  
**Project Goal**: Automated equipment health monitoring through sensor data analysis

---

## 📋 Table of Contents

1. [Project Goal](#project-goal)
2. [Problem Statement](#problem-statement)
3. [Approach Overview](#approach-overview)
4. [Analysis Methods Pool](#analysis-methods-pool)
5. [Method Evaluation Matrix](#method-evaluation-matrix)
6. [Recommended Prioritization](#recommended-prioritization)

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
1. Read weekly parquet file
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

## 💡 Analysis Methods Pool

Below are **10 methods** for detecting problematic behavior in sensor data, ranging from simple statistical approaches to more sophisticated techniques.

---

### **Method 1: Static Threshold Detection**

**Description**: Define fixed upper and lower limits for each sensor. Flag values exceeding thresholds.

**How it works**:
- Set domain-expert thresholds (e.g., EngCoolTemp > 95°C = Anormal)
- Compare each reading against limits
- Grade: Normal (within), Alerta (near limit), Anormal (exceeded)

**Pros**:
- ✅ Extremely simple to implement
- ✅ Fast execution
- ✅ Easy to explain to operators

**Cons**:
- ❌ Requires domain knowledge for threshold selection
- ❌ Doesn't adapt to equipment-specific baselines
- ❌ Ignores temporal patterns

**When to use**: As a **baseline** or when manufacturer specs are available

---

### **Method 2: Statistical Outlier Detection (IQR Method)**

**Description**: Use Interquartile Range (IQR) to identify outliers statistically without predefined thresholds.

**How it works**:
- Calculate Q1 (25th percentile) and Q3 (75th percentile) for each signal
- IQR = Q3 - Q1
- Flag values: 
  - Alerta: Outside `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`
  - Anormal: Outside `[Q1 - 3*IQR, Q3 + 3*IQR]`

**Pros**:
- ✅ No manual threshold setting
- ✅ Adapts to data distribution
- ✅ Robust to extreme values

**Cons**:
- ❌ Assumes normal-ish distribution
- ❌ Doesn't consider temporal dependencies

**When to use**: When you lack domain thresholds but have historical data

---

### **Method 3: Rolling Window Statistics**

**Description**: Compare current readings against recent historical behavior using rolling averages and standard deviations.

**How it works**:
- Calculate rolling mean (μ) and std (σ) over last N hours/days
- Flag current value if: `|value - μ| > k*σ` where k=2 (Alerta) or k=3 (Anormal)
- Adapts dynamically to recent trends

**Pros**:
- ✅ Captures temporal context
- ✅ Adapts to seasonal patterns
- ✅ Lightweight computation

**Cons**:
- ❌ Requires sufficient history
- ❌ Lag in detecting sudden shifts

**When to use**: For **trending analysis** when patterns evolve over time

---

### **Method 4: Percentile-Based Baseline**

**Description**: Establish "normal" behavior using historical percentiles (e.g., 5th-95th percentile range).

**How it works**:
- Build baseline from past weeks: P5, P50 (median), P95
- Grade current reading:
  - Normal: Between P5 and P95
  - Alerta: Between [P1-P5] or [P95-P99]
  - Anormal: Below P1 or above P99

**Pros**:
- ✅ Simple and interpretable
- ✅ Handles non-normal distributions well
- ✅ Easy to visualize (boxplots!)

**Cons**:
- ❌ Static baseline doesn't adapt quickly
- ❌ Requires representative historical data

**When to use**: For **week-over-week comparisons** (your initial boxplot idea!)

---

### **Method 5: State-Conditioned Analysis**

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

---

### **Method 6: Rate of Change Detection**

**Description**: Flag rapid changes in sensor values that indicate sudden degradation or failure.

**How it works**:
- Calculate first derivative: `Δvalue / Δtime`
- Flag if rate of change exceeds normal variation
- Example: Sudden 20°C jump in coolant temp over 5 minutes

**Pros**:
- ✅ Detects early signs of failure
- ✅ Catches transient events missed by static analysis
- ✅ Lightweight calculation

**Cons**:
- ❌ Sensitive to noise (requires smoothing)
- ❌ May miss gradual degradation

**When to use**: For **early warning** of acute failures (combine with baseline methods)

---

### **Method 7: Multivariate Correlation Analysis**

**Description**: Detect anomalies by identifying when sensor correlations deviate from normal patterns.

**How it works**:
- Build correlation matrix for component signals (e.g., Motor sensors)
- Compare current correlations against baseline
- Flag when correlations break (e.g., EngCoolTemp rises but EngOilPres doesn't)

**Pros**:
- ✅ Captures complex interdependencies
- ✅ Detects subtle failures
- ✅ Holistic component view

**Cons**:
- ❌ More computationally intensive
- ❌ Harder to explain to operators

**When to use**: For **component-level analysis** when signals should move together

---

### **Method 8: Isolation Forest (Unsupervised ML)**

**Description**: Use lightweight machine learning to identify multivariate outliers without labels.

**How it works**:
- Train Isolation Forest on historical "normal" data
- Score new readings: anomaly score between 0-1
- Flag high anomaly scores as Alerta/Anormal

**Pros**:
- ✅ Handles high-dimensional data well
- ✅ No manual threshold tuning
- ✅ Captures complex patterns

**Cons**:
- ❌ Requires training data (past weeks)
- ❌ Less interpretable ("black box")
- ❌ More computational overhead

**When to use**: When **simple methods fail** to catch known issues in testing

---

### **Method 9: Time Series Anomaly Detection (Z-score with Trend Removal)**

**Description**: Decompose time series into trend + seasonal + residual, then flag anomalies in residuals.

**How it works**:
- Apply seasonal decomposition (e.g., weekly patterns)
- Calculate z-scores on residuals
- Flag large z-score deviations

**Pros**:
- ✅ Handles seasonality elegantly
- ✅ Removes long-term drift
- ✅ Standard statistical method

**Cons**:
- ❌ Requires sufficient history (several weeks)
- ❌ More complex than basic methods

**When to use**: For **sensors with known daily/weekly cycles**

---

### **Method 10: Clustered Baseline Profiles**

**Description**: Group similar operating periods, then flag when current behavior doesn't match any cluster.

**How it works**:
- Use K-Means or DBSCAN to cluster historical operating profiles
- Assign each new reading to nearest cluster
- Flag if distance to nearest cluster is large

**Pros**:
- ✅ Identifies "never seen before" patterns
- ✅ Adapts to multiple normal modes
- ✅ Good for equipment with varying usage

**Cons**:
- ❌ Requires tuning (number of clusters)
- ❌ More complex implementation
- ❌ Higher computational cost

**When to use**: For **diverse operational patterns** (e.g., multiple routes/loads)

---

## 📊 Method Evaluation Matrix

Each method is evaluated on two axes:
- **Complexity** (1-5): 1 = Very Simple, 5 = Very Complex
- **Precision** (1-5): 1 = Low Accuracy, 5 = High Accuracy

| # | Method | Complexity | Precision | Complexity × Precision | Notes |
|---|--------|-----------|-----------|----------------------|-------|
| 1 | Static Threshold Detection | 1 | 2 | 2 | Best for MVP baseline |
| 2 | Statistical Outlier (IQR) | 1 | 3 | 3 | Easy wins without thresholds |
| 3 | Rolling Window Statistics | 2 | 3 | 6 | Good temporal awareness |
| 4 | Percentile-Based Baseline | 1 | 3 | 3 | **Perfect for week-over-week viz** |
| 5 | State-Conditioned Analysis | 2 | 4 | 8 | **Essential enhancement** |
| 6 | Rate of Change Detection | 2 | 3 | 6 | Catches acute failures |
| 7 | Multivariate Correlation | 3 | 4 | 12 | Component-level upgrade |
| 8 | Isolation Forest | 3 | 4 | 12 | ML fallback if needed |
| 9 | Time Series Decomposition | 3 | 4 | 12 | For seasonal patterns |
| 10 | Clustered Baseline Profiles | 4 | 4 | 16 | Advanced option |

### Evaluation Criteria

**Complexity** considers:
- Implementation effort (code complexity)
- Computational resources (runtime)
- Maintenance burden (tuning, updates)

**Precision** considers:
- Ability to detect true failures
- False positive rate
- Adaptability to equipment variations

---

## 🎯 Recommended Prioritization

### **Phase 1: MVP (Simple & Effective)**
**Goal**: Deliver working system quickly with "good enough" accuracy

1. **Method 4: Percentile-Based Baseline** ⭐ **START HERE**
   - Complexity: 1, Precision: 3
   - Why: Aligns with your boxplot idea, easy to implement/visualize
   - Implementation: Build weekly percentile baselines (P5, P25, P50, P75, P95, P99)

2. **Method 5: State-Conditioned Analysis** 🔥 **CRITICAL**
   - Complexity: 2, Precision: 4
   - Why: **Must-have** for accurate results
   - Implementation: Apply Method 4 separately per operational state

3. **Method 2: IQR Outlier Detection**
   - Complexity: 1, Precision: 3
   - Why: Backup for sensors without good baselines
   - Implementation: Fallback when insufficient history

**MVP Outcome**: Signal → Component → Machine grading working with state-aware percentile baselines

---

### **Phase 2: Enhancements (Moderate Complexity)**
**Goal**: Improve precision with temporal awareness

4. **Method 6: Rate of Change Detection**
   - Adds early warning for acute failures
   - Complements static baseline methods

5. **Method 3: Rolling Window Statistics**
   - Adapts to gradual trends
   - Smooths day-to-day variations

**Phase 2 Outcome**: Catches both gradual degradation and sudden failures

---

### **Phase 3: Advanced (Higher Complexity)**
**Goal**: Maximize precision with sophisticated techniques

6. **Method 7: Multivariate Correlation Analysis**
   - Component-level intelligence
   - Detects subtle interaction failures

7. **Method 8: Isolation Forest (Optional)**
   - Only if simpler methods miss known issues
   - Requires careful validation

**Phase 3 Outcome**: Near-expert-level diagnostic capability

---

## 📐 Scoring Strategy

### Signal-Level Scoring
```python
# Example: Percentile-based grading
if value < P1 or value > P99:
    grade = "Anormal"
    score = 10
elif value < P5 or value > P95:
    grade = "Alerta"
    score = 5
else:
    grade = "Normal"
    score = 0
```

### Component-Level Aggregation
```python
# Aggregate signal scores
component_score = sum(signal_scores)
component_grade = {
    "Normal": all signals Normal or max 1 Alerta,
    "Alerta": 2+ signals Alerta or 1 Anormal,
    "Anormal": 2+ signals Anormal
}
```

### Machine-Level Aggregation
```python
# Aggregate component scores
machine_score = sum(component_scores)
priority_score = weighted_sum(component_scores)  # Weight critical components higher
machine_grade = {
    "Normal": all components Normal,
    "Alerta": 1+ components Alerta,
    "Anormal": 1+ components Anormal
}
```

---

## 🚀 Success Metrics

### Technical Metrics
- ✅ False Positive Rate < 10%
- ✅ Processing time < 5 minutes per week's data
- ✅ Grade changes correlate with maintenance events

### Business Metrics
- ✅ Early detection: Flag issues 24-48h before operator notice
- ✅ Maintenance optimization: Reduce reactive repairs by 30%
- ✅ Downtime prevention: Catch critical failures proactively

---

## 📚 Next Steps

1. ✅ **Read this document** → Understand approach
2. 📊 **Review dashboard_proposal.md** → Visualization strategy
3. 🛠️ **Follow implementation_plan.md** → Build MVP
4. 🚀 **Execute improvement_plan.md** → Enhance precision

---

**Document Status**: ✅ Ready for Review  
**Recommended Starting Point**: Method 4 (Percentile Baseline) + Method 5 (State Conditioning)
