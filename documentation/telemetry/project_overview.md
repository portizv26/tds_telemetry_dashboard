# Telemetry Health Evaluation Framework - Project Overview

**Version**: 2.0.0  
**Last Updated**: May 24, 2026  
**Component**: Multi-Technique Telemetry Analytics  
**Project Phase**: Proof of Concept

---

## 📋 Table of Contents

1. [Project Vision](#project-vision)
2. [Architectural Philosophy](#architectural-philosophy)
3. [Multi-Technique Framework](#multi-technique-framework)
4. [Evaluation Hierarchy](#evaluation-hierarchy)
5. [Analytical Techniques](#analytical-techniques)
6. [Scoring Methodology](#scoring-methodology)
7. [Baseline Strategy](#baseline-strategy)
8. [Output Architecture](#output-architecture)
9. [Key Differentiators](#key-differentiators)

---

## 🎯 Project Vision

### Mission Statement

Build a **multi-technique analytical framework** that transforms minute-level telemetry from mining equipment into explainable, confidence-scored health assessments by orchestrating independent analytical methods operating at their natural time scales.

### Core Philosophy

**Traditional Approach** (what we're NOT doing):
- Single weekly evaluation cycle
- One scoring methodology for all phenomena
- Black-box "anomaly score"
- Dashboard-first design

**Our Approach** (what we ARE doing):
- Multiple evaluation cadences (6-hourly, daily, weekly)
- Technique-specific methodologies for different risk types
- Explainable risk + confidence scoring
- Analytics-first design with future dashboard consumption

### Scope

**In Scope**:
- ✅ Multi-technique telemetry analytics framework
- ✅ Signal → System → Unit health aggregation
- ✅ Explainable risk and confidence scoring
- ✅ State-specific baseline generation
- ✅ Event detection and trend analysis
- ✅ Diagnostic rule evaluation
- ✅ Historical backtesting and validation
- ✅ Analytical outputs (Parquet/JSON)

**Out of Scope** (POC):
- ❌ Dashboard/UI development
- ❌ Real-time streaming analytics
- ❌ Maintenance system integration
- ❌ Oil analysis or multi-data-source fusion
- ❌ Automated alerting workflows
- ❌ Production deployment infrastructure

### Value Proposition

This framework enables:

1. **Early Detection**: Identify degradation before failure (≥3 days advance warning target)
2. **Explainability**: Every assessment traces to specific signals and observations
3. **Prioritization**: Rank units by maintenance urgency with confidence scores
4. **Flexibility**: Add/remove techniques without redesigning the system
5. **Auditability**: Full traceability from raw data to final assessment

---

## 🏗️ Architectural Philosophy

### Single Fixed Input: Silver Layer

The framework starts from **minute-level cleaned telemetry**:

```
client: str
unit_id: str
timestamp: datetime (UTC, 1-minute resolution)
operational_state: str (Operacional, Ralenti, Apagada, ND)
<signal_1>: float (nullable)
<signal_2>: float (nullable)
...
<signal_n>: float (nullable)
```

Optional but valuable:
- GPS coordinates (latitude, longitude, elevation)
- Payload state
- Sub-state information
- Data quality flags

**Assumption**: Silver layer is already cleaned and validated by upstream pipeline. All units have ≥90 days of historical data.

### Technique Independence

**Design Principle**: Each analytical technique is an autonomous module that:

- Declares its own evaluation window and cadence
- Consumes Silver data (or intermediate aggregates)
- Produces standardized `TechniqueResult` objects
- Calculates independent risk and confidence scores
- Stores technique-specific evidence

**Benefits**:
- Add/remove techniques without affecting others
- Iterate on techniques independently
- Compare technique effectiveness
- Support heterogeneous evaluation schedules

### Separation of Risk and Confidence

**Every assessment produces TWO scores**:

**Risk Score (0-100)**: How severe is the evidence of abnormality or degradation?
- 0-30: Low risk / Normal variation
- 30-60: Moderate risk / Monitoring recommended
- 60-80: High risk / Inspection recommended
- 80-100: Critical risk / Immediate action required

**Confidence Score (0-100)**: How reliable is this assessment?
- Based on: data coverage, baseline quality, sample size, state matching
- Low confidence ≠ low risk (missing data should not imply healthy state)
- Enables `InsufficientData` classification when confidence < 50

**Why separate them?**
- Data quality issues reduce confidence, not risk
- Prevents false sense of security from sparse data
- Enables transparent "we don't know" status

### Explainability as First-Class Requirement

**Non-negotiable**: Every score must include evidence.

```json
{
  "unit_id": "T15",
  "system": "Engine",
  "signal": "EngCoolTemp",
  "technique": "threshold_deviation",
  "risk_score": 82,
  "confidence_score": 91,
  "status": "Anormal",
  "evidence": {
    "abnormal_percentage": 12.4,
    "longest_event_minutes": 46,
    "observed_max": 104.5,
    "upper_limit_p99": 98.0,
    "event_count": 3,
    "state": "Operacional"
  }
}
```

**Design rule**: If you can't explain a score, don't generate it.

---

## 🔄 Multi-Technique Framework

### The Core Innovation

**Not a single model. A coordinated analytical framework.**

Different techniques observe different phenomena over different time scales:

| Technique | Cadence | Lookback Window | Purpose | Output Level |
|-----------|---------|-----------------|---------|--------------|
| **Threshold Deviation** | Daily | 24 hours | Detect repeated limit violations | Signal |
| **Event Detection** | Daily | 24 hours | Identify persistent abnormal episodes | Signal |
| **Trend Analysis** | Weekly | 4-12 weeks | Detect progressive degradation | Signal/System |
| **Diagnostic Rules** | Daily/Weekly | Rule-specific | Capture known mechanical patterns | System |
| **Peer Deviation** | Weekly | 7 days | Compare unit against fleet | Signal/System |
| **AutoEncoder** | Every 6 hours | 6 hours | Detect multivariate abnormality | System |

### Why Multiple Cadences Matter

**Example scenario**: Engine coolant temperature

- **6-hour AutoEncoder** detects: Unusual multivariate pattern in last 6 hours (EngCoolTemp + TCOutTemp + EngOilPres)
- **Daily threshold** detects: 12% of yesterday's operational minutes exceeded P95
- **Weekly trend** detects: P95 coolant temp increasing by 1.2°C/week over last 8 weeks
- **Diagnostic rule** detects: High coolant + low oil pressure concurrent for 28 minutes

**Key insight**: These are all different types of evidence. Forcing them into a single weekly evaluation would lose critical information.

### Technique Validity Periods

Each technique result has a **validity period** - how long it remains relevant:

| Technique | Validity Period | Rationale |
|-----------|----------------|-----------|
| AutoEncoder (6h) | 12 hours | Short-term behavior changes quickly |
| Daily threshold | 2 days | Recent patterns more relevant than old |
| Weekly summary | 1 week | Aggregated view, slower to change |
| Trend (8-week) | 4 weeks | Long-term patterns are persistent |
| Diagnostic rule | Rule-specific | Depends on rule nature |

**Impact on aggregation**: When combining evidence at system/unit level, older results are down-weighted within their validity period. Results beyond validity period are ignored.

### Metadata Preservation

Every technique result stores:

```python
technique: str  # "threshold_deviation", "trend_analysis", etc.
execution_timestamp: datetime  # When analysis ran
evaluation_start: datetime  # Start of analysis window
evaluation_end: datetime  # End of analysis window
lookback_window: str  # "24h", "7d", "8w"
cadence: str  # "daily", "weekly", "6h"
baseline_version: str  # "20260524"
model_version: Optional[str]  # For ML techniques
```

**Why this matters**: You can always trace a score back to its temporal context and methodology.

---

## 📊 Evaluation Hierarchy

The framework aggregates evidence through a **three-level hierarchy**:

```
┌─────────────────────────────────────────────────────────────┐
│                 SIGNAL-LEVEL EVALUATION                      │
│  • Each signal evaluated independently by multiple techniques│
│  • Technique-specific risk and confidence scores             │
│  • Native evidence preserved (exceedance %, trend slope, etc)│
│  • State-matched baseline comparison                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 SYSTEM-LEVEL AGGREGATION                     │
│  • Collect recent technique results (within validity period) │
│  • Apply time-decay weighting                                │
│  • Weight by signal criticality                              │
│  • Boost for multi-technique evidence                        │
│  • Cannot average away critical findings                     │
│  • Generate system explanation                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  UNIT-LEVEL AGGREGATION                      │
│  • Aggregate system assessments                              │
│  • Weight by system criticality (Engine>Electrical)          │
│  • Calculate priority score for fleet ranking                │
│  • Overall status (worst system drives classification)       │
│  • Generate executive summary                                │
└─────────────────────────────────────────────────────────────┘
```

### Level 1: Signal-Level Evaluation

**Input**: Minute-level Silver telemetry for specific signal

**Process**:
1. Load evaluation window (technique-specific)
2. Retrieve applicable baseline (match operational state)
3. Execute technique logic
4. Calculate native metrics (exceedance %, slope, reconstruction error, etc.)
5. Normalize to risk score (0-100)
6. Calculate confidence score from data quality
7. Classify status: Normal, Alerta, Anormal, InsufficientData

**Output**: `TechniqueResult` object with full evidence

### Level 2: System-Level Aggregation

**Input**: Recent technique results for all signals in system (e.g., Engine)

**Process**:
1. Filter results within validity period
2. Apply time-decay weighting (recent results weighted higher)
3. Apply signal criticality weighting (important signals weighted higher)
4. Detect multi-technique agreement (boost score if multiple techniques flag same signal)
5. Ensure critical findings are not averaged away (use max + weighted mean hybrid)
6. Calculate system_score and system_status
7. Extract top evidence (triggering signals, techniques, severity drivers)
8. Generate human-readable explanation

**Aggregation formula**:
```python
system_score = (
    0.4 * max_recent_critical_score +  # Cannot ignore severe evidence
    0.3 * weighted_mean_score +         # Captures broad patterns
    0.2 * persistence_bonus +           # Rewards multi-technique agreement
    0.1 * diagnostic_rule_bonus         # Boosts known mechanical patterns
)
```

**Output**: `SystemHealth` object per unit-system pair

### Level 3: Unit-Level Aggregation

**Input**: System health assessments for all systems in unit

**Process**:
1. Aggregate system scores weighted by system criticality
2. Determine overall_status (worst system drives classification with override logic)
3. Calculate priority_score for fleet ranking
4. Identify top_risk_systems
5. Extract top evidence across all systems
6. Generate executive summary

**Priority score formula**:
```python
priority_score = (
    100 * n_anormal_critical_systems +  # Engine, Trans, Brakes
    50 * n_anormal_other_systems +
    20 * n_alerta_critical_systems +
    10 * n_alerta_other_systems +
    5 * any_negative_trends +
    unit_score
)
```

**Status logic**:
- **Anormal**: Any critical system is Anormal OR ≥2 systems Anormal
- **Alerta**: Any system is Alerta and none are Anormal
- **Observation**: Mild evidence not meeting Alerta threshold (POC may merge into Normal/Alerta)
- **Normal**: All systems Normal
- **InsufficientData**: Confidence too low for reliable assessment

**Output**: `UnitHealth` object per unit

---

## 🔬 Analytical Techniques

### 1. Threshold Deviation Analysis

**Purpose**: Detect when signals repeatedly exceed state-specific normal ranges.

**Cadence**: Daily (with weekly summary)

**Lookback**: 24 hours (daily) or 7 days (weekly summary)

**Methodology**:
1. Load minute-level data for evaluation window
2. Filter by operational state
3. Retrieve state-specific baseline (P1, P5, P95, P99)
4. Classify each minute:
   - Normal: P5 ≤ value ≤ P95
   - Warning: P1 ≤ value < P5 OR P95 < value ≤ P99
   - Abnormal: value < P1 OR value > P99
5. Calculate:
   - `abnormal_pct`: % of minutes abnormal
   - `warning_pct`: % of minutes in warning zone
   - `max_deviation`: Furthest excursion from limit
   - `event_count`: Number of distinct abnormal episodes

**Risk score formula**:
```python
base_score = min(abnormal_pct * 6, 100)  # 10% abnormal → 60
if max_deviation > limit * 1.2:
    base_score *= 1.3  # Boost for severe excursions
risk_score = min(base_score, 100)
```

**Status thresholds**:
- Normal: risk_score < 40
- Alerta: 40 ≤ risk_score < 70
- Anormal: risk_score ≥ 70

**Output**: TechniqueResult per signal per day

### 2. Event Detection

**Purpose**: Convert point-level threshold violations into operationally meaningful abnormal episodes.

**Cadence**: Daily (runs after threshold deviation)

**Methodology**:
1. Load minute-level abnormal flags from threshold deviation
2. Group consecutive abnormal minutes (with <5min gaps allowed)
3. Calculate per event:
   - Start/end timestamps
   - Duration
   - Peak value and deviation
   - Average deviation
   - Operational state
4. Classify event type:
   - Spike: <5 minutes
   - Episode: 5-60 minutes
   - Sustained: >60 minutes
5. Calculate severity score (function of duration × deviation)

**Why this matters**: A single abnormal point (spike) is very different from a persistent 45-minute abnormal episode (sustained).

**Output**: Event records stored separately, referenced in technique results

### 3. Trend Analysis

**Purpose**: Detect progressive degradation over multiple weeks.

**Cadence**: Weekly

**Lookback**: 4, 8, and 12 weeks (configurable)

**Methodology**:
1. Generate weekly signal aggregates:
   - Per unit + signal + state + week: mean, median, P5, P50, P95, P99, std
   - Hours in state, sample count, coverage
2. For each lookback window (e.g., 8 weeks):
   - Fit linear regression: metric ~ week
   - Calculate slope (change per week)
   - Calculate robust slope (Theil-Sen, outlier-resistant)
   - Test statistical significance (p-value < 0.05 required)
   - Calculate delta: recent_value - baseline_value
3. Classify trend direction: improving, stable, degrading

**Risk score formula**:
```python
# For degrading trends (appropriate direction per signal)
magnitude_score = min(abs(delta_pct) * 2, 50)  # 20% delta → 40
persistence_score = min(r_squared * 50, 30)     # R²=0.8 → 24
significance_bonus = 20 if p_value < 0.01 else 0
risk_score = min(magnitude_score + persistence_score + significance_bonus, 100)
```

**Confidence factors**:
- Reduce if <50% weeks have sufficient data
- Reduce if R² < 0.5 (noisy trend)
- Reduce if p-value > 0.05 (not statistically significant)

**Output**: TechniqueResult per signal per lookback window per week

### 4. Diagnostic Rules

**Purpose**: Capture known multi-signal mechanical failure patterns using domain expertise.

**Cadence**: Daily and/or weekly (rule-specific)

**Examples**:

**Engine Thermal + Lubrication Stress**:
- Condition: High EngCoolTemp (>P95) AND Low EngOilPres (<P5)
- Duration: Concurrent for ≥15 minutes
- Valid state: Operacional
- Risk: High engine failure probability

**Brake Imbalance**:
- Condition: max(4 brake temps) - min(4 brake temps) > 20°C
- Duration: ≥20 minutes
- Valid state: Operacional
- Risk: Uneven brake wear, potential failure

**Transmission Stress**:
- Condition: High TrnLubeTemp (>P95) AND Low TrnOilPres (<P10)
- Duration: Concurrent for ≥10 minutes
- Risk: Transmission component degradation

**Methodology**:
1. Load rule definitions from configuration (YAML)
2. For each rule:
   - Check if all required signals are available
   - Verify operational state is valid for rule
   - Evaluate trigger conditions
   - Measure concurrent duration (if applicable)
   - Calculate rule-specific severity
3. Normalize to risk score

**Risk score formula**:
```python
base_severity = rule.severity_weight  # 0.7-1.0 per rule
duration_factor = min(concurrent_duration / rule.min_duration, 2.0)
deviation_factor = mean(signal_deviations)
risk_score = min(base_severity * duration_factor * deviation_factor * 100, 100)
```

**Output**: TechniqueResult per triggered rule per unit per evaluation

### 5. Peer Deviation Analysis

**Purpose**: Identify units behaving abnormally relative to similar equipment in the fleet.

**Cadence**: Weekly

**Lookback**: 7 days

**Methodology**:
1. Define peer groups: client + equipment_model + signal
2. Calculate weekly aggregated metric per unit (e.g., mean, P95)
3. For each unit, calculate:
   - Peer percentile (position in fleet distribution)
   - Robust z-score: (unit_value - fleet_median) / MAD
   - Deviation percentage: (unit_value - fleet_median) / fleet_median
4. Flag outliers: units at >P90 (for high-risk signals) or <P10 (for low-risk signals)

**Risk score formula**:
```python
if peer_percentile > 90:
    base_score = (peer_percentile - 50) * 2  # P95 → 90
    if abs(robust_z) > 3:
        base_score *= 1.2  # Boost for extreme outliers
    risk_score = min(base_score, 100)
```

**Confidence factors**:
- Require ≥10 units in peer group (otherwise InsufficientData)
- Reduce if unit has <80% data coverage
- Reduce if fleet-wide event (e.g., seasonal temperature spike affecting all units)

**Output**: TechniqueResult per signal per week

### 6. AutoEncoder (Optional - Phase 5)

**Purpose**: Detect short-term multivariate abnormality within each system using unsupervised learning.

**Cadence**: Every 6 hours

**Lookback**: 6 hours (360 minutes)

**Methodology**:
1. Train system-specific AutoEncoders (Engine, Transmission, Brakes, etc.)
2. Engineer window-level features per signal:
   - Statistical: mean, median, std, min, max, range, IQR
   - Percentiles: P5, P95, P99
   - Trend: slope within window
   - Quality: missing%, abnormal%
3. Each 6h window → one feature vector
4. Model architecture: Simple 3-layer fully-connected AE (no LSTM initially)
5. At inference:
   - Encode-decode feature vector
   - Calculate reconstruction error
   - Convert to percentile (vs. historical reconstruction errors)
   - Identify top contributing features (signals with highest reconstruction error)

**Risk score formula**:
```python
# Reconstruction error percentile is already 0-100
risk_score = reconstruction_error_percentile
```

**Confidence factors**:
- Reduce if <70% of signals in system have data in window
- Reduce if model age >90 days (staleness)
- Reduce if training data was low quality

**Output**: TechniqueResult per system per 6h window

**Note**: AutoEncoder is highest complexity technique. Defer to Phase 5 unless validation of simpler techniques proves insufficient.

---

## 📏 Scoring Methodology

### Risk Score Normalization

**Goal**: Convert technique-native metrics into comparable 0-100 scores.

**General bands**:
- **0-30 (Low)**: Normal variation, no action required
- **30-60 (Moderate)**: Elevated risk, monitoring recommended
- **60-80 (High)**: Significant risk, inspection recommended
- **80-100 (Critical)**: Severe risk, immediate action required

**Technique-specific mappings**:

**Threshold Deviation**:
```python
def normalize_threshold(abnormal_pct, max_deviation_pct):
    base = min(abnormal_pct * 6, 100)
    if max_deviation_pct > 20:  # >20% beyond limit
        base *= 1.3
    return min(base, 100)
```

**Trend Analysis**:
```python
def normalize_trend(delta_pct, r_squared, p_value):
    magnitude = min(abs(delta_pct) * 2, 50)
    persistence = min(r_squared * 50, 30)
    significance = 20 if p_value < 0.01 else 0
    return min(magnitude + persistence + significance, 100)
```

**Diagnostic Rules**:
```python
def normalize_rule(rule_severity, duration_factor, deviation_factor):
    return min(rule_severity * duration_factor * deviation_factor * 100, 100)
```

**AutoEncoder**:
```python
def normalize_autoencoder(reconstruction_error_percentile):
    return reconstruction_error_percentile  # Already 0-100
```

**Peer Deviation**:
```python
def normalize_peer(peer_percentile, robust_z):
    base = (peer_percentile - 50) * 2  # P75 → 50, P90 → 80
    if abs(robust_z) > 3:
        base *= 1.2
    return min(base, 100)
```

### Confidence Score Calculation

**Factors** (all 0-1 scale, multiplicative):

**Data Coverage**:
```python
coverage_factor = min(valid_samples / expected_samples, 1.0)
if coverage_factor < 0.5:
    confidence_penalty = (0.5 - coverage_factor) * 100  # <50% → large penalty
```

**Baseline Quality**:
```python
baseline_factor = min(baseline_sample_count / 1000, 1.0)
if baseline_factor < 0.5:
    confidence_penalty = (0.5 - baseline_factor) * 40
```

**State Matching**:
```python
if current_state != baseline_state:
    confidence_penalty = 40  # Using wrong baseline → large penalty
```

**Sample Size**:
```python
if sample_count < technique.min_required_samples:
    confidence_penalty = 30
```

**Combined**:
```python
confidence_score = 100.0
confidence_score -= coverage_penalty
confidence_score -= baseline_penalty
confidence_score -= state_mismatch_penalty
confidence_score -= sample_size_penalty
confidence_score = max(confidence_score, 0)
```

### Status Classification

**Per technique result**:
- **Normal**: risk_score < technique.normal_threshold (typically 40)
- **Alerta**: technique.normal_threshold ≤ risk_score < technique.abnormal_threshold (typically 70)
- **Anormal**: risk_score ≥ technique.abnormal_threshold
- **InsufficientData**: confidence_score < 50

**Per system** (aggregated):
- **Normal**: system_score < 40 AND no techniques triggered
- **Alerta**: 40 ≤ system_score < 70 OR ≥1 technique triggered moderate
- **Anormal**: system_score ≥ 70 OR ≥1 technique triggered critical OR diagnostic rule triggered
- **InsufficientData**: confidence_score < 50

**Per unit** (aggregated):
- **Anormal**: ≥1 critical system Anormal OR ≥2 systems Anormal
- **Alerta**: ≥1 system Alerta and no Anormal
- **Normal**: All systems Normal
- **InsufficientData**: Insufficient confidence across systems

---

## 🧮 Baseline Strategy

### State-Specific Baselines

**Granularity**: `client + equipment_model + signal + operational_state`

**Why state-specific?**
- Engine speed at "Operacional" (~1800 RPM) vs. "Ralenti" (~600 RPM) vs. "Apagada" (~0 RPM)
- Using aggregate baseline would flag normal behavior as abnormal

**Operational states**:
- **Operacional**: High load, typical mining operations
- **Ralenti**: Idle, low load
- **Apagada**: Engine off, near-zero readings
- **ND**: Not Determined / transitional (exclude from baseline training)

### Baseline Calculation

**Training window**: 90 days (adjustable per signal)

**Per baseline entity** (client + model + signal + state):

Calculate percentiles: P1, P2, P5, P10, P50, P90, P95, P98, P99  
Calculate moments: mean, std, MAD  
Store metadata: sample_count, training_start, training_end  
Calculate quality: quality_score = f(sample_count, distribution_shape)

**Minimum requirements**:
- ≥1000 valid samples per state
- ≥60 days of history (at least 2/3 of training window)
- <30% missing data

### Fallback Hierarchy

If unit-specific baseline unavailable or poor quality:

1. **Unit + signal + state**: Ideal (not implemented in POC)
2. **Model + signal + state**: Default POC approach
3. **Client + signal + state**: Fallback if <3 units of model type
4. **Global + signal + state**: Last resort

**Flagging**: Store which fallback level was used in technique result metadata.

### Baseline Versioning

**Format**: `baseline_YYYYMMDD.parquet`

**Refresh cadence**: Monthly (first Sunday of month)

**Process**:
1. Drop oldest 30 days of training data
2. Add newest 30 days of training data (rolling 90-day window)
3. Recalculate percentiles
4. Version as `baseline_YYYYMMDD.parquet`
5. Validate: no sudden shifts >20% in P50 (flag for manual review if detected)

**Staleness tracking**:
- Flag baselines >45 days old
- Auto-refresh triggered if staleness detected
- Store baseline version with every technique result

### Baseline Invalidation

**Triggers** (manual flag in system):
- Major component replacement (e.g., engine overhaul)
- Equipment reconfiguration
- Change in operational profile (e.g., new haul route with different elevation)

**Action**: Create new baseline excluding pre-event data, or flag unit for expert review.

---

## 📦 Output Architecture

### Output Directory Structure

```
data/telemetry/analytical_results/
├── baselines/
│   ├── baseline_20260524.parquet
│   └── baseline_metadata.json
├── technique_results/
│   ├── threshold_deviation/
│   │   └── year=2026/month=05/day=24/results.parquet
│   ├── trend_analysis/
│   │   └── year=2026/week=21/results.parquet
│   ├── diagnostic_rules/
│   │   └── year=2026/week=21/results.parquet
│   ├── peer_deviation/
│   │   └── year=2026/week=21/results.parquet
│   └── autoencoder/  [Optional]
│       └── year=2026/month=05/day=24/hour=06/results.parquet
├── events/
│   └── year=2026/month=05/day=24/events.parquet
├── aggregates/
│   └── weekly/
│       └── year=2026/week=21/weekly_aggregates.parquet
├── system_health/
│   └── year=2026/week=21/client=cda/system_health.parquet
└── unit_health/
    └── year=2026/week=21/client=cda/unit_health.parquet
```

### Storage Strategy

**Format**: Parquet (columnar, efficient for analytics)

**Partitioning**:
- Technique results: By technique, then temporal (year/month/day or year/week)
- System/Unit health: By temporal (year/week), then client
- Events: By temporal (year/month/day)

**Retention**:
- Technique results: 1 year
- System/Unit health: 2 years (historical tracking)
- Events: 1 year
- Baselines: All versions (storage is minimal)

**Versioning**: All outputs include schema_version column for backward compatibility.

### Output Schemas

See [data_contracts.md](data_contracts.md) for complete schemas.

**Key outputs**:

1. **technique_results/**: Per-technique evaluations with risk, confidence, and evidence
2. **system_health/**: Aggregated system-level assessments per unit
3. **unit_health/**: Top-level fleet ranking and prioritization
4. **events/**: Detailed abnormal episode records
5. **baselines/**: Reference statistics for threshold comparison

### Consumption Patterns

**Future dashboard queries** (out of POC scope but designed for):

```python
# Get latest unit assessment
unit_health = pd.read_parquet(
    'data/telemetry/analytical_results/unit_health/',
    filters=[('unit_id', '=', 'T15')]
).sort_values('assessment_timestamp').iloc[-1]

# Get system health history for trend chart
system_history = pd.read_parquet(
    'data/telemetry/analytical_results/system_health/',
    filters=[
        ('unit_id', '=', 'T15'),
        ('system', '=', 'Engine')
    ]
).sort_values('assessment_timestamp')

# Get technique results for explanation drill-down
technique_detail = pd.read_parquet(
    'data/telemetry/analytical_results/technique_results/threshold_deviation/',
    filters=[
        ('unit_id', '=', 'T15'),
        ('signal', '=', 'EngCoolTemp')
    ]
).sort_values('execution_timestamp')
```

---

## 🎯 Key Differentiators

### 1. Multi-Temporal by Design

**Traditional**: Force all analytics into weekly batch  
**This framework**: Each technique runs when it's meaningful (6h, daily, weekly)

**Benefit**: Capture both short-term events and long-term trends without compromise.

### 2. Risk and Confidence Separation

**Traditional**: Single "anomaly score" or "health score"  
**This framework**: Risk score (severity) + Confidence score (reliability)

**Benefit**: Transparency about data quality; "we don't know" is a valid answer.

### 3. Explainability-First

**Traditional**: Black-box model outputs score, hard to explain  
**This framework**: Every score includes evidence (what, when, how much, how confident)

**Benefit**: Maintenance teams can trust and act on recommendations.

### 4. Technique Independence

**Traditional**: Monolithic pipeline, hard to iterate  
**This framework**: Modular techniques, easy to add/remove/improve

**Benefit**: Rapid iteration; compare technique effectiveness; incremental value delivery.

### 5. Configuration-Driven

**Traditional**: Hard-coded thresholds and logic  
**This framework**: Signal registry, baseline versioning, tunable parameters in YAML/JSON

**Benefit**: Adapt to different equipment types, tune without code changes, audit decisions.

### 6. Time-Aware Aggregation

**Traditional**: Average all scores equally  
**This framework**: Weight by recency, criticality, confidence, and persistence

**Benefit**: Critical findings not averaged away; recent evidence weighted higher.

### 7. State-Specific Baselines

**Traditional**: Compare all readings to single threshold  
**This framework**: Match operational state to appropriate baseline

**Benefit**: Avoid false positives from normal state transitions (Ralenti→Operacional).

### 8. Progressive Complexity

**Traditional**: Start with complex ML models  
**This framework**: Simple explainable techniques first (threshold, trend), complex techniques later (AutoEncoder) if needed

**Benefit**: Prove value quickly; add complexity only when justified.

---

## 📚 Related Documentation

- [Implementation Plan](implementation_plan.md) - Detailed phased development roadmap
- [Data Contracts](data_contracts.md) - Complete schema specifications

---

## 📝 Version History

### Version 2.0.0 (May 24, 2026)
- **Complete redesign**: Multi-technique analytical framework
- Replaced single weekly evaluation with technique-specific cadences
- Added risk/confidence score separation
- Introduced technique independence and time-aware aggregation
- Expanded from signal-component-machine to signal-system-unit hierarchy
- Removed dashboard-focused design; now analytics-first
- Added diagnostic rules, peer deviation, and optional AutoEncoder
- State-specific baselines emphasized
- Explainability as first-class requirement
- Designed for POC scope (no production infrastructure)

### Version 1.x (February-April 2026)
- Legacy single-technique weekly batch approach
- Deprecated and replaced by Version 2.0.0
