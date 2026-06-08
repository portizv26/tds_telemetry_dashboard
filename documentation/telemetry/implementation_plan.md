# Telemetry Health Evaluation — Implementation Plan

**Version**: 2.0.0  
**Last Updated**: May 24, 2026  
**Status**: Active Development  
**Project Phase**: Proof of Concept

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Objectives](#project-objectives)
3. [Core Design Principles](#core-design-principles)
4. [Architectural Overview](#architectural-overview)
5. [Implementation Phases](#implementation-phases)
6. [Technical Components](#technical-components)
7. [Success Criteria](#success-criteria)
8. [Risk Management](#risk-management)
9. [Glossary](#glossary)

---

## 1. Executive Summary

### 1.1 Project Vision

This project implements a **multi-technique telemetry analytics framework** that transforms minute-level sensor data from mining equipment into actionable health assessments. Unlike traditional single-model approaches, this framework orchestrates multiple analytical techniques, each operating at its natural time scale and contributing independent evidence to a unified health evaluation.

### 1.2 Key Innovation

**Different analytical techniques observe different phenomena:**

| Technique | Cadence | Window | Purpose |
|-----------|---------|--------|---------|
| Threshold Deviation | Daily | 24 hours | Detect repeated limit violations |
| Event Detection | Daily | 24 hours | Identify persistent abnormal episodes |
| Trend Analysis | Weekly | 4-12 weeks | Detect progressive degradation |
| Diagnostic Rules | Daily/Weekly | Rule-specific | Capture known mechanical patterns |
| Peer Deviation | Weekly | 7 days | Compare unit against fleet |
| AutoEncoder | Every 6 hours | 6 hours | Detect multivariate abnormality |

The framework respects these differences by:
- Running each technique at its optimal cadence
- Preserving technique-specific evidence
- Normalizing outputs for comparability
- Aggregating with time-aware weighting

### 1.3 Scope Statement

**In Scope** (POC):
- ✅ Minute-level Silver telemetry ingestion
- ✅ Multi-technique analytical framework
- ✅ Signal → System → Unit health aggregation
- ✅ Explainable risk and confidence scoring
- ✅ State-specific baseline generation
- ✅ Historical backtesting and validation
- ✅ Analytical outputs (Parquet/JSON)

**Out of Scope** (POC):
- ❌ Dashboard/UI development
- ❌ Real-time streaming analytics
- ❌ Integration with maintenance systems
- ❌ Oil analysis or multi-technique fusion
- ❌ Automated alerting workflows
- ❌ Production deployment infrastructure

### 1.4 Success Definition

The POC succeeds if it can:

1. **Detect**: Identify units with genuine operational issues before failure
2. **Explain**: Provide clear evidence of what is wrong and why
3. **Prioritize**: Rank units by maintenance urgency accurately
4. **Validate**: Demonstrate detection of historical known events
5. **Scale**: Process full fleet (50+ units) within acceptable time

Target metrics:
- **Detection rate**: ≥80% of historical failures flagged in advance
- **Advance warning**: ≥3 days before critical events
- **False positive rate**: ≤20% of flagged units require no action
- **Confidence accuracy**: Low-confidence scores correlate with data quality issues

---

## 2. Project Objectives

### 2.1 Primary Objectives

1. **Transform telemetry into health evidence**
   - Convert raw sensor readings into normalized risk assessments
   - Generate confidence-scored evaluations at signal, system, and unit level
   - Preserve full audit trail from raw data to final assessment

2. **Enable proactive maintenance**
   - Identify degradation trends before failure
   - Prioritize maintenance actions by risk and confidence
   - Provide actionable explanations for maintenance teams

3. **Build scalable analytical infrastructure**
   - Support multiple clients and equipment types
   - Allow addition of new signals and techniques without redesign
   - Enable historical backtesting and future forecasting

### 2.2 Technical Objectives

1. **Multi-temporal framework**
   - Each technique runs at its natural evaluation cadence
   - Results preserve their temporal context and validity period
   - Aggregation respects time-decay of evidence

2. **Separation of risk and confidence**
   - Every score includes both risk (severity) and confidence (reliability)
   - Data quality issues reduce confidence, not risk
   - InsufficientData is a valid classification

3. **Explainability-first design**
   - Every score traces to specific signals and observations
   - Evidence includes: what, when, how severe, how confident
   - Native metrics preserved alongside normalized scores

4. **Configuration-driven analytics**
   - Signal registry defines behavior, criticality, and valid techniques
   - Baselines are versioned and auditable
   - Thresholds and weights are tunable without code changes

---

## 3. Core Design Principles

### 3.1 Silver Layer as Foundation

**Input Contract**:
```
client: str
unit_id: str
timestamp: datetime (minute-level, UTC)
operational_state: str (Operacional, Ralenti, Apagada, ND)
<signal_1>: float (nullable)
<signal_2>: float (nullable)
...
<signal_n>: float (nullable)
```

**Assumptions**:
- ✅ Data is pre-cleaned and validated
- ✅ All units have ≥90 days of history
- ✅ Sampling rate is consistent (1/minute expected)
- ✅ Client-independent structure
- ⚠️ Missing values are explicit nulls (not 0 or -999)

### 3.2 Technique Independence

**Design Rule**: Each technique is an independent module that:
- Consumes Silver data (or intermediate aggregates)
- Produces standardized `TechniqueResult` objects
- Declares its own evaluation window and cadence
- Calculates its own risk and confidence scores
- Stores technique-specific evidence

**Benefits**:
- Add/remove techniques without affecting others
- Iterate on individual techniques independently
- Compare technique effectiveness
- Support heterogeneous evaluation cadences

### 3.3 Time-Aware Aggregation

**Design Rule**: Evidence is weighted by:
1. **Technique confidence**: Low-quality data reduces weight
2. **Time decay**: Older results within validity period lose weight
3. **Signal criticality**: Engine signals weighted higher than electrical
4. **Persistence**: Repeated evidence across techniques increases weight
5. **Severity**: Critical findings cannot be averaged away

**Formula** (conceptual):
```
system_score = weighted_sum(
    technique_results,
    weights=[confidence × time_decay × criticality × persistence]
)
```

### 3.4 Explainability as First-Class Output

**Design Rule**: Every score must include:

```json
{
  "risk_score": 82,
  "confidence_score": 91,
  "status": "Anormal",
  "evidence": {
    "technique": "threshold_deviation",
    "triggering_signals": ["EngCoolTemp"],
    "observation": "12.4% of operational time exceeded P95 limit",
    "severity_drivers": ["longest_event_46min", "peak_deviation_6.5C"],
    "data_quality": "coverage_98pct"
  }
}
```

**Non-negotiable**: If you can't explain a score, don't generate it.

### 3.5 Progressive Complexity

**Design Rule**: Implement simple, explainable techniques first:

**Phase 1-2** (Weeks 1-4):
- Threshold deviation (statistical, explainable)
- Event detection (rule-based, transparent)
- Trend analysis (linear regression, interpretable)

**Phase 3-4** (Weeks 5-6):
- Diagnostic rules (domain knowledge, explicit logic)
- System/unit aggregation (weighted, documented)

**Phase 5** (Week 7+, optional):
- Peer deviation (comparative analytics)
- AutoEncoder (black-box, requires extensive validation)

**Rationale**: Prove value with simple methods before investing in complex ones.

---

## 4. Architectural Overview

### 4.1 System Layers

```
┌──────────────────────────────────────────────────────────────┐
│                     SILVER LAYER                             │
│          Minute-level cleaned telemetry (input)              │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  ANALYTICAL METADATA                         │
│  • Signal Registry                                           │
│  • System Mapping                                            │
│  • Baseline Repository (state-specific percentiles)          │
│  • Technique Configuration                                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│               DATA QUALITY & PROFILING                       │
│  • Coverage analysis                                         │
│  • State distribution                                        │
│  • Signal availability                                       │
│  • Confidence scoring                                        │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│              TECHNIQUE EXECUTION LAYER                       │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  Threshold     │  │  Trend         │  │  Diagnostic  │  │
│  │  Deviation     │  │  Analysis      │  │  Rules       │  │
│  │  (Daily)       │  │  (Weekly)      │  │  (Daily)     │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  Event         │  │  Peer          │  │  AutoEncoder │  │
│  │  Detection     │  │  Deviation     │  │  (6-hourly)  │  │
│  │  (Daily)       │  │  (Weekly)      │  │  [Optional]  │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                 NORMALIZATION LAYER                          │
│  • Native metric → 0-100 risk score                          │
│  • Data quality → 0-100 confidence score                     │
│  • Evidence preservation                                     │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│              AGGREGATION LAYER                               │
│                                                              │
│  Signal Results ──→ System Health ──→ Unit Health           │
│                                                              │
│  • Time-aware weighting                                      │
│  • Criticality-based prioritization                          │
│  • Multi-technique evidence fusion                           │
│  • Explanation generation                                    │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  ANALYTICAL OUTPUTS                          │
│  • technique_results/ (per technique, per evaluation)        │
│  • system_health/ (per system, per assessment)               │
│  • unit_health/ (per unit, per assessment)                   │
│  • events/ (abnormal episodes)                               │
│  • baselines/ (reference statistics)                         │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Data Flow

#### 4.2.1 Ingestion Flow
1. Silver telemetry (minute-level) → Data quality profiling
2. Filter by operational state validity
3. Calculate window-level coverage and confidence

#### 4.2.2 Baseline Flow
1. Historical Silver data (90+ days)
2. Group by: client + model + signal + operational_state
3. Calculate: P1, P2, P5, P10, P50, P90, P95, P98, P99, mean, std, MAD
4. Store with metadata: version, training_window, sample_count
5. Refresh monthly

#### 4.2.3 Technique Execution Flow (Example: Threshold Deviation)
1. Load evaluation window (e.g., last 24 hours)
2. Retrieve applicable baseline (match state)
3. Compare observations vs. thresholds (P1, P5, P95, P99)
4. Calculate: exceedance%, max_deviation, event_count
5. Normalize to risk_score (0-100)
6. Calculate confidence_score from data quality
7. Store TechniqueResult with full evidence

#### 4.2.4 Aggregation Flow
1. Load recent technique results (within validity period)
2. Apply time-decay weighting
3. Group by system
4. Calculate weighted system_score
5. Classify system_status (Normal/Alerta/Anormal/InsufficientData)
6. Aggregate systems to unit level
7. Calculate priority_score for fleet ranking
8. Generate explanations

### 4.3 Execution Scheduling

**Orchestration**: Prefect (recommended for POC)

**Schedules**:

| Job | Cadence | Trigger | Duration (est.) |
|-----|---------|---------|-----------------|
| Silver data ingestion | Continuous | Real-time/batch | N/A (upstream) |
| Data quality profiling | Hourly | Cron | ~5 min |
| Threshold deviation (daily) | Daily at 01:00 | Cron | ~15 min |
| Event detection | Daily at 02:00 | After threshold | ~10 min |
| Weekly aggregation | Weekly Sun 03:00 | Cron | ~20 min |
| Trend analysis | Weekly Sun 04:00 | After aggregation | ~30 min |
| Diagnostic rules (daily) | Daily at 05:00 | Cron | ~10 min |
| Diagnostic rules (weekly) | Weekly Sun 06:00 | Cron | ~15 min |
| Peer deviation | Weekly Sun 07:00 | Cron | ~25 min |
| System aggregation (daily) | Daily at 08:00 | After techniques | ~10 min |
| System aggregation (weekly) | Weekly Sun 09:00 | After techniques | ~15 min |
| Unit aggregation | After system agg | Dependent | ~5 min |
| AutoEncoder [Optional] | Every 6 hours | Cron | ~20 min |

**Dependencies**:
- Event detection depends on threshold deviation results
- Trend analysis depends on weekly aggregation
- System aggregation depends on technique results
- Unit aggregation depends on system aggregation

---

## 5. Implementation Phases

**Overview**: The POC is structured into 5 phases over 8+ weeks. Phases 1-4 are required; Phase 5 is optional based on validation results.

### Phase Summary Table

| Phase | Duration | Objective | Key Deliverables | Status |
|-------|----------|-----------|------------------|--------|
| **Phase 1: Foundation** | Weeks 1-2 | Establish analytical infrastructure | Signal registry, baselines, data profiling, orchestration | Not Started |
| **Phase 2: Core Analytics** | Weeks 3-4 | Implement explainable techniques | Threshold deviation, event detection, trend analysis | Not Started |
| **Phase 3: Aggregation & Intelligence** | Weeks 5-6 | Build system & unit health scores | System/unit aggregation, diagnostic rules, explanations | Not Started |
| **Phase 4: Validation** | Week 7 | Prove framework detects real problems | Backtest, false positive analysis, calibration, validation report | Not Started |
| **Phase 5: Enhancements** | Week 8+ (Optional) | Add advanced techniques if needed | Peer deviation, AutoEncoder, advanced rules, change-point detection | Not Started |

---

### Phase 1: Foundation (Weeks 1-2)

**Objective**: Establish the analytical infrastructure required for all techniques.

**Key Deliverables**:
- Analytical data model (entities, schemas, storage strategy)
- Signal registry with metadata for 15+ signals
- Data quality profiling tools and reports
- Baseline generation system (state-specific percentiles)
- Evaluation window system
- Execution orchestration framework (Prefect)

**Exit Criteria**:
- Signal registry validates successfully
- Baselines generated for all client + model + signal + state combinations
- Orchestration framework can run dummy tasks
- Data quality issues identified and documented

📄 **[View Detailed Phase 1 Implementation Guide →](implementation_phase_1.md)**

---

### Phase 2: Core Analytics (Weeks 3-4)

**Objective**: Implement explainable, high-value analytical techniques.

**Key Deliverables**:
- Threshold Deviation technique (daily + weekly)
- Event Detection (abnormal episode grouping)
- Weekly Signal Aggregation
- Trend Analysis (4w, 8w, 12w windows)
- Score Normalization (risk + confidence)

**Exit Criteria**:
- All 3 techniques execute reliably (threshold, event, trend)
- Results stored with proper partitioning and schema versioning
- Scores in 0-100 range with explainable evidence
- Techniques integrated with Prefect flows

📄 **[View Detailed Phase 2 Implementation Guide →](implementation_phase_2.md)**

---

### Phase 3: Aggregation & Intelligence (Weeks 5-6)

**Objective**: Convert technique results into operational health assessments.

**Key Deliverables**:
- System-level aggregation (6 systems per unit)
- Unit-level aggregation with priority scoring
- Diagnostic Rules engine (5-8 multi-signal rules)
- Explanation generation (natural language summaries)

**Exit Criteria**:
- System and unit health scores generated for all units
- Diagnostic rules fire on known mechanical patterns
- Explanations are clear and actionable
- Priority rankings correctly identify high-risk units

📄 **[View Detailed Phase 3 Implementation Guide →](implementation_phase_3.md)**

---

### Phase 4: Validation (Week 7)

**Objective**: Prove the framework detects real problems.

**Key Deliverables**:
- Historical known-event collection (≥10 failures)
- Backtest execution and detection rate calculation
- False positive analysis
- Threshold calibration
- Comprehensive validation report

**Exit Criteria**:
- Detection rate ≥70% (stretch goal: 80%)
- Advance warning ≥3 days for critical events
- False positive rate ≤25% (stretch goal: 20%)
- Validation report approved by stakeholders

📄 **[View Detailed Phase 4 Implementation Guide →](implementation_phase_4.md)**

---

### Phase 5: Optional Enhancements (Week 8+)

**Objective**: Add advanced techniques based on Phase 4 validation gaps.

**Enhancement Options** (Pick 1-2):
1. **Peer Deviation Analysis** (2-3 days) — Compare unit against fleet
2. **AutoEncoder Anomaly Detection** (4-5 days) — Multivariate black-box technique
3. **Advanced Diagnostic Rules** (2-3 days) — 5-10 additional sophisticated rules
4. **Change-Point Detection** (3-4 days) — Detect sudden regime shifts

**Selection Criteria**:
- Only pursue if Phase 4 shows specific gaps
- Must add measurable incremental value
- Time and resources available

**Exit Criteria** (if pursued):
- Enhancement catches ≥1 failure missed by Phase 2-3 techniques
- False positive rate increase ≤10%
- Documented and explainable

📄 **[View Detailed Phase 5 Implementation Guide →](implementation_phase_5.md)**

---

## 6. Technical Components

### 6.1 Signal Registry

**Location**: `data/telemetry/config/signal_registry_v1.yaml`

**Structure**:
```yaml
version: "1.0"
last_updated: "2026-05-24"

signals:
  - name: "EngCoolTemp"
    display_name: "Engine Coolant Temperature"
    system: "Engine"
    subsystem: "Cooling"
    unit: "°C"
    risk_direction: "high"  # "high", "low", "both"
    valid_states:
      - "Operacional"
      - "Ralenti"
    physical_min: 0.0
    physical_max: 150.0
    criticality: 3  # 1=low, 2=medium, 3=high
    enabled_techniques:
      - "threshold_deviation"
      - "event_detection"
      - "trend_analysis"
      - "diagnostic_rules"
      - "autoencoder"
    baseline_required: true
    minimum_samples_per_day: 800

  - name: "EngOilPres"
    display_name: "Engine Oil Pressure"
    system: "Engine"
    subsystem: "Lubrication"
    unit: "kPa"
    risk_direction: "low"
    valid_states:
      - "Operacional"
    physical_min: 0.0
    physical_max: 800.0
    criticality: 3
    enabled_techniques:
      - "threshold_deviation"
      - "event_detection"
      - "trend_analysis"
      - "diagnostic_rules"
      - "autoencoder"
    baseline_required: true
    minimum_samples_per_day: 800

  # ... (additional signals)
```

**Usage**:
```python
from src.config.signal_registry import SignalRegistry

registry = SignalRegistry.load("data/telemetry/config/signal_registry_v1.yaml")

# Check if technique is enabled for signal
if registry.is_technique_enabled("EngCoolTemp", "threshold_deviation"):
    run_threshold_analysis()

# Get signal metadata
signal_meta = registry.get_signal("EngCoolTemp")
print(f"Criticality: {signal_meta.criticality}")
print(f"Valid states: {signal_meta.valid_states}")
```

---

### 6.2 Baseline Structure

**Location**: `data/telemetry/analytical_results/baselines/`

**Files**:
- `baseline_YYYYMMDD.parquet`: Baseline statistics
- `baseline_metadata.json`: Training window, quality, version info

**Schema**: `baseline_YYYYMMDD.parquet`

| Column | Type | Description |
|--------|------|-------------|
| client | string | Client identifier |
| equipment_model | string | Equipment model/family |
| signal | string | Signal name |
| operational_state | string | State this baseline applies to |
| p1 | float | 1st percentile (extreme low threshold) |
| p5 | float | 5th percentile (warning low threshold) |
| p50 | float | Median (typical value) |
| p95 | float | 95th percentile (warning high threshold) |
| p99 | float | 99th percentile (extreme high threshold) |
| mean | float | Mean value |
| std | float | Standard deviation |
| mad | float | Median absolute deviation |
| sample_count | int | Number of samples in training set |
| training_start | datetime | Start of training window |
| training_end | datetime | End of training window |
| quality_score | float | 0-1 confidence in baseline |
| created_at | datetime | Baseline generation timestamp |

**Metadata**: `baseline_metadata.json`
```json
{
  "version": "20260524",
  "training_window_days": 90,
  "min_samples_required": 1000,
  "clients_included": ["cda", "emin", "enex"],
  "state_specific": true,
  "fallback_enabled": true,
  "refresh_cadence": "monthly",
  "next_refresh_date": "2026-06-24"
}
```

---

### 6.3 Technique Result Schema

**Common fields** (all techniques):

```python
@dataclass
class TechniqueResult:
    technique: str  # "threshold_deviation", "trend_analysis", etc.
    execution_timestamp: datetime
    evaluation_start: datetime
    evaluation_end: datetime
    lookback_window: str  # "24h", "7d", "8w"
    
    unit_id: str
    client: str
    system: str
    signal: str  # or None for system-level techniques
    operational_state: str  # primary state during window
    
    risk_score: float  # 0-100
    confidence_score: float  # 0-100
    status: str  # "Normal", "Alerta", "Anormal", "InsufficientData"
    
    baseline_version: str  # "20260524"
    model_version: Optional[str]  # For ML techniques
    
    evidence: Dict[str, Any]  # Technique-specific evidence
    
    metadata: Dict[str, Any]  # Additional context
```

**Technique-specific evidence examples**:

**Threshold Deviation**:
```python
evidence = {
    "sample_count": 1440,
    "valid_sample_count": 1398,
    "coverage": 0.97,
    "state": "Operacional",
    "upper_limit_p95": 98.0,
    "upper_limit_p99": 105.0,
    "observed_max": 104.5,
    "warning_exceedance_pct": 15.2,
    "abnormal_exceedance_pct": 12.4,
    "max_deviation": 6.5,
    "mean_deviation": 3.2,
    "event_count": 3,
    "longest_event_duration_min": 46
}
```

**Trend Analysis**:
```python
evidence = {
    "metric": "weekly_p95",
    "windows_evaluated": ["4w", "8w"],
    "slope_4w": 1.2,  # units per week
    "slope_8w": 0.8,
    "r_squared_8w": 0.76,
    "p_value_8w": 0.012,
    "recent_value": 99.2,
    "baseline_value": 91.5,
    "delta": 7.7,
    "delta_pct": 8.4,
    "valid_weeks": 8,
    "direction": "degrading"
}
```

**Diagnostic Rule**:
```python
evidence = {
    "rule_id": "engine_thermal_lubrication_stress",
    "rule_name": "High coolant temp + Low oil pressure",
    "triggering_signals": ["EngCoolTemp", "EngOilPres"],
    "signal_values": {
        "EngCoolTemp": {"observed": 102.5, "limit": 98.0, "deviation": 4.5},
        "EngOilPres": {"observed": 285.0, "limit": 320.0, "deviation": -35.0}
    },
    "concurrent_duration_min": 28,
    "state": "Operacional",
    "rule_severity": 0.85
}
```

---

### 6.4 System Health Schema

**Location**: `data/telemetry/analytical_results/system_health/year=YYYY/week=WW/client=XXX/`

**File**: `system_health.parquet`

| Column | Type | Description |
|--------|------|-------------|
| unit_id | string | Unit identifier |
| client | string | Client identifier |
| system | string | System name (Engine, Transmission, etc.) |
| assessment_timestamp | datetime | When assessment was generated |
| evaluation_period_start | datetime | Earliest technique result included |
| evaluation_period_end | datetime | Latest technique result included |
| system_score | float | 0-100 aggregated risk score |
| confidence_score | float | 0-100 aggregated confidence |
| system_status | string | Normal, Alerta, Anormal, InsufficientData |
| criticality_weight | int | System importance (1-3) |
| techniques_evaluated | int | Number of techniques with valid results |
| techniques_triggered | List[string] | Techniques that flagged risk |
| triggering_signals | List[string] | Signals with non-Normal status |
| top_evidence | string (JSON) | Top 3 technique results by severity |
| explanation | string | Human-readable summary |

**Example row**:
```python
{
    "unit_id": "T15",
    "client": "cda",
    "system": "Engine",
    "assessment_timestamp": "2026-05-24 09:00:00",
    "evaluation_period_start": "2026-05-17 00:00:00",
    "evaluation_period_end": "2026-05-24 08:59:59",
    "system_score": 82.0,
    "confidence_score": 88.0,
    "system_status": "Anormal",
    "criticality_weight": 3,
    "techniques_evaluated": 5,
    "techniques_triggered": ["threshold_deviation", "trend_analysis", "diagnostic_rule"],
    "triggering_signals": ["EngCoolTemp", "EngOilPres"],
    "top_evidence": "[{...}, {...}, {...}]",
    "explanation": "Engine system shows high-risk evidence (score 82) driven by repeated coolant temperature exceedances during operational state (12.4% of time, 3 events >30min, longest 46min) and declining oil pressure trend (-0.8 kPa/week over 8 weeks). Diagnostic rule 'thermal_lubrication_stress' triggered concurrently for 28 minutes."
}
```

---

### 6.5 Unit Health Schema

**Location**: `data/telemetry/analytical_results/unit_health/year=YYYY/week=WW/client=XXX/`

**File**: `unit_health.parquet`

| Column | Type | Description |
|--------|------|-------------|
| unit_id | string | Unit identifier |
| client | string | Client identifier |
| assessment_timestamp | datetime | When assessment was generated |
| evaluation_period_start | datetime | Earliest evidence included |
| evaluation_period_end | datetime | Latest evidence included |
| overall_status | string | Normal, Observation, Alerta, Anormal, InsufficientData |
| unit_score | float | 0-100 aggregated risk score |
| priority_score | float | Fleet ranking score (higher = worse) |
| confidence_score | float | 0-100 aggregated confidence |
| total_systems | int | Number of systems evaluated |
| systems_normal | int | Count with Normal status |
| systems_observation | int | Count with Observation status |
| systems_alerta | int | Count with Alerta status |
| systems_anormal | int | Count with Anormal status |
| systems_insufficient_data | int | Count with InsufficientData status |
| top_risk_systems | List[string] | Systems ordered by severity |
| top_evidence | string (JSON) | Top 5 system-level findings |
| explanation | string | Executive summary |
| operational_context | string (JSON) | Hours operated, state distribution, etc. |

**Priority Score Formula**:
```python
priority_score = (
    100 * n_anormal_critical_systems +  # Engine, Transmission, Brakes
    50 * n_anormal_other_systems +
    20 * n_alerta_critical_systems +
    10 * n_alerta_other_systems +
    5 * (1 if any_negative_trends else 0) +
    unit_score
)
```

---

### 6.6 Event Schema

**Location**: `data/telemetry/analytical_results/events/year=YYYY/month=MM/day=DD/`

**File**: `events.parquet`

| Column | Type | Description |
|--------|------|-------------|
| event_id | string | Unique event identifier (UUID) |
| unit_id | string | Unit identifier |
| client | string | Client identifier |
| system | string | Affected system |
| signal | string | Primary triggering signal |
| event_start | datetime | First abnormal minute |
| event_end | datetime | Last abnormal minute |
| duration_minutes | int | Event duration |
| state | string | Operational state during event |
| max_value | float | Peak signal value |
| limit_value | float | Threshold that was exceeded |
| max_deviation | float | Peak deviation from limit |
| mean_deviation | float | Average deviation during event |
| severity_score | float | 0-100 event severity |
| event_type | string | spike, episode, sustained |
| preceding_status | string | Signal status before event |
| following_status | string | Signal status after event |
| recovery_time_minutes | int | Time to return to Normal |

---

## 7. Success Criteria

### 7.1 Functional Requirements

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Detection rate (known events) | ≥80% | Backtest validation |
| Advance warning time | ≥3 days | Time between first flag and failure |
| False positive rate | ≤20% | Expert review of flagged units |
| Confidence accuracy | ≥75% | Low-confidence scores correlate with data quality issues |
| Execution reliability | ≥99% | Scheduled jobs complete successfully |
| Technique coverage | ≥90% | % of unit-system pairs evaluated by ≥2 techniques |

### 7.2 Technical Requirements

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Daily execution time | <30 min | All daily techniques complete before 06:00 |
| Weekly execution time | <2 hours | All weekly techniques complete before 12:00 Sunday |
| Data latency | <4 hours | Silver→analytical results |
| Storage efficiency | <50 GB/month | Analytical results growth rate |
| Code coverage | ≥70% | Unit test coverage |
| Documentation completeness | 100% | All modules have docstrings and READMEs |

### 7.3 Operational Requirements

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Explainability | 100% | Every non-Normal status has explanation |
| Auditability | 100% | Every score traces to source data and technique |
| Reproducibility | 100% | Re-running analysis produces identical results |
| Configurability | 100% | Thresholds, weights, and rules externalized to config |
| Baseline freshness | <45 days | Age of oldest baseline in use |

---

## 8. Risk Management

### 8.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Silver data quality issues | High | High | Extensive profiling in Phase 1; adjust minimum requirements |
| Insufficient historical data | Medium | Medium | Implement fallback baselines; flag low confidence |
| Technique produces too many false positives | High | High | Tune thresholds in Phase 4; require expert validation |
| AutoEncoder too complex for POC | Medium | Low | Defer to Phase 5; use simpler anomaly detection |
| Aggregation logic too hard to explain | Medium | Medium | Start simple (max + weighted mean); iterate |
| Execution time exceeds limits | Low | Medium | Optimize queries; implement incremental processing |

### 8.2 Project Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Scope creep beyond POC | Medium | High | Strict phase gating; defer enhancements to Phase 5 |
| Validation shows poor performance | Medium | High | Treat as learning cycle; iterate on Phase 2-3 |
| Insufficient known events for validation | Medium | Medium | Supplement with expert-identified units of concern |
| Key stakeholder unavailable for reviews | Low | Medium | Schedule weekly check-ins; document decisions |

### 8.3 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Baseline becomes stale | High | Medium | Automated monthly refresh; staleness alerts |
| New equipment type lacks baseline | Medium | Low | Use peer baselines from similar equipment |
| Operational state misclassification | Medium | Medium | Validate state logic; flag state mismatches |
| Signal registry out of sync with Silver | Low | High | Validation on startup; fail fast if mismatch |

---

## 9. Glossary

**Analytical Results**: Outputs of the telemetry framework (technique results, system health, unit health, events).

**Baseline**: State-specific reference statistics (percentiles, mean, std) calculated from historical data.

**Confidence Score**: 0-100 measure of how reliable a risk assessment is, based on data quality, baseline quality, and sample size.

**Coverage**: Percentage of expected samples that are valid (not missing or out-of-range).

**Criticality**: Weight assigned to a signal or system reflecting its importance to unit operation (1=low, 2=medium, 3=high).

**Evaluation Window**: Time period over which a technique analyzes data (e.g., last 24 hours, last 8 weeks).

**Event**: A contiguous period where a signal exceeds thresholds, with metadata about duration, severity, and recovery.

**Evidence**: Technique-specific data that explains why a risk score was assigned (e.g., exceedance%, peak deviation, trend slope).

**Normalization**: Mapping a technique's native metric to a standardized 0-100 risk score.

**Operational State**: Equipment operational mode (Operacional, Ralenti, Apagada, ND) used to match appropriate baselines.

**Priority Score**: Fleet-wide ranking score used to order units by maintenance urgency (higher = worse).

**Risk Score**: 0-100 measure of abnormality severity or degradation magnitude.

**Signal Registry**: Configuration file defining metadata for all telemetry signals (system, criticality, valid states, enabled techniques).

**Silver Layer**: Cleaned, minute-level telemetry input to the analytics framework.

**System**: High-level equipment component (Engine, Transmission, Brakes, Differential, Hydraulics, Electrical, Cooling).

**Technique**: Independent analytical method (threshold deviation, trend analysis, diagnostic rule, etc.).

**Technique Result**: Standardized output from a technique execution (risk, confidence, evidence, metadata).

**Time Decay**: Reduction in weight applied to older evidence within its validity period.

**Validity Period**: How long a technique result remains relevant (e.g., 6h for AutoEncoder, 1 week for trend analysis).

---

## Appendix A: File Structure

```
telemetry_dashboard/
├── data/
│   ├── telemetry/
│   │   ├── silver/                    # Input: minute-level telemetry
│   │   │   └── {client}/
│   │   │       └── week_{WW}_{YYYY}.parquet
│   │   ├── config/
│   │   │   ├── signal_registry_v1.yaml
│   │   │   ├── technique_config.yaml
│   │   │   └── diagnostic_rules.yaml
│   │   └── analytical_results/        # Outputs
│   │       ├── baselines/
│   │       │   ├── baseline_YYYYMMDD.parquet
│   │       │   └── baseline_metadata.json
│   │       ├── technique_results/
│   │       │   ├── threshold_deviation/
│   │       │   │   └── year=YYYY/month=MM/day=DD/
│   │       │   ├── trend_analysis/
│   │       │   │   └── year=YYYY/week=WW/
│   │       │   ├── diagnostic_rules/
│   │       │   │   └── year=YYYY/week=WW/
│   │       │   └── autoencoder/  [Optional]
│   │       │       └── year=YYYY/month=MM/day=DD/hour=HH/
│   │       ├── events/
│   │       │   └── year=YYYY/month=MM/day=DD/
│   │       ├── aggregates/
│   │       │   └── weekly/
│   │       │       └── year=YYYY/week=WW/
│   │       ├── system_health/
│   │       │   └── year=YYYY/week=WW/client={client}/
│   │       └── unit_health/
│   │           └── year=YYYY/week=WW/client={client}/
├── src/
│   ├── config/
│   │   ├── __init__.py
│   │   ├── signal_registry.py
│   │   └── technique_config.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── profiler.py
│   │   ├── validator.py
│   │   └── loader.py
│   ├── techniques/
│   │   ├── __init__.py
│   │   ├── base.py  # Abstract base class
│   │   ├── threshold_deviation.py
│   │   ├── event_detection.py
│   │   ├── trend_analysis.py
│   │   ├── diagnostic_rules.py
│   │   ├── peer_deviation.py  [Optional]
│   │   └── autoencoder.py  [Optional]
│   ├── aggregation/
│   │   ├── __init__.py
│   │   ├── system_aggregator.py
│   │   ├── unit_aggregator.py
│   │   └── explanation_generator.py
│   ├── baselines/
│   │   ├── __init__.py
│   │   ├── baseline_generator.py
│   │   └── baseline_manager.py
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── normalization.py
│   │   ├── confidence.py
│   │   └── priority.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── flows.py  # Prefect flows
│   │   └── schedules.py
│   └── utils/
│       ├── __init__.py
│       ├── date_utils.py
│       ├── file_utils.py
│       └── logger.py
├── notebooks/
│   ├── 01_data_profiling.ipynb
│   ├── 02_baseline_exploration.ipynb
│   ├── 03_technique_prototyping.ipynb
│   └── 04_validation_analysis.ipynb
├── documentation/
│   ├── telemetry/
│   │   ├── implementation_plan.md  # This document
│   │   ├── project_overview.md
│   │   ├── data_contracts.md
│   │   └── design_decisions.md
│   └── general/
│       └── dashboard_overview.md
├── tests/
│   ├── unit/
│   ├── integration/
│   └── validation/
├── requirements.txt
└── README.md
```

---

## Appendix B: Key Design Decisions

Document major decisions here as they are made during implementation.

| Decision | Date | Rationale | Alternatives Considered |
|----------|------|-----------|-------------------------|
| Use P1/P99 instead of P2/P98 | 2026-05-24 | Stricter anomaly detection, reduced false positives | P5/P95 (too loose), P0.1/P99.9 (too data-hungry) |
| Separate risk and confidence | 2026-05-24 | Prevents masking real issues due to data quality | Combined score (loses transparency) |
| Multi-technique framework | 2026-05-24 | Flexibility, explainability, incremental value | Single model (less transparent, higher risk) |
| State-specific baselines | 2026-05-24 | Engine behavior differs by operational state | Aggregate baselines (less accurate) |
| Prefect for orchestration | 2026-05-24 | Lightweight, good for mixed cadences, easy dev | Airflow (too heavy), cron (too brittle) |

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-02-23 | Initial Team | Original weekly-batch approach |
| 2.0.0 | 2026-05-24 | Senior Data Scientist | Complete redesign: multi-technique framework |

---

**End of Implementation Plan**
