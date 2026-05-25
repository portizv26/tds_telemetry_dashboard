# Telemetry Health Evaluation — Data Contracts

**Version**: 1.0.0  
**Last Updated**: May 24, 2026  
**Purpose**: Define all input and output data schemas for the telemetry health evaluation framework

---

## Table of Contents

1. [Overview](#overview)
2. [Input Data Contracts](#input-data-contracts)
3. [Configuration Data Contracts](#configuration-data-contracts)
4. [Baseline Data Contracts](#baseline-data-contracts)
5. [Technique Result Data Contracts](#technique-result-data-contracts)
6. [Aggregation Data Contracts](#aggregation-data-contracts)
7. [Event Data Contracts](#event-data-contracts)
8. [Supporting Data Contracts](#supporting-data-contracts)
9. [Schema Versioning](#schema-versioning)
10. [Data Quality Standards](#data-quality-standards)

---

## 1. Overview

### 1.1 Schema Design Principles

1. **Explicit Typing**: All fields have defined data types
2. **Mandatory Documentation**: Every schema includes field descriptions and constraints
3. **Versioning**: All outputs include schema_version field
4. **Partitioning**: Storage location includes partition keys
5. **Nullability**: Explicitly defined (required vs. optional)

### 1.2 Storage Format

**Primary Format**: Apache Parquet (columnar, compressed)

**Partitioning Strategy**:
- Time-based: `year=YYYY/month=MM/day=DD` or `year=YYYY/week=WW`
- Entity-based: `client=CLIENT_ID`

**Compression**: Snappy (balance between compression ratio and speed)

---

## 2. Input Data Contracts

### 2.1 Silver Layer Telemetry

**Location**: `data/telemetry/silver/{client}/week_*.parquet`

**Description**: Minute-level cleaned telemetry data from mining equipment

**Schema**:

| Field | Type | Nullable | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `timestamp` | datetime64[ns] | No | UTC timestamp of measurement | ISO 8601 format |
| `unit_id` | string | No | Unique equipment identifier | Format: CLIENT_UNIT_NNN |
| `client` | string | No | Client identifier | Uppercase, 3-4 letters |
| `equipment_model` | string | No | Equipment model | e.g., "CAT 789C", "CAT 789D" |
| `operational_state` | string | No | Operational state | One of: Operacional, Ralenti, Apagada, ND |
| `signal_name` | string | No | Telemetry signal name | Must exist in signal registry |
| `signal_value` | float64 | Yes | Signal measurement value | Null = missing/invalid |
| `signal_unit` | string | No | Unit of measurement | e.g., "°C", "kPa", "RPM" |
| `data_quality_flag` | string | Yes | Quality indicator | One of: GOOD, SUSPECT, BAD, NULL |

**Partitioning**: `client={client}/year={year}/week={week}`

**Example Record**:
```json
{
  "timestamp": "2026-05-20T14:23:00Z",
  "unit_id": "CDA_UNIT_042",
  "client": "CDA",
  "equipment_model": "CAT 789D",
  "operational_state": "Operacional",
  "signal_name": "EngCoolTemp",
  "signal_value": 87.5,
  "signal_unit": "°C",
  "data_quality_flag": "GOOD"
}
```

**Data Quality Requirements**:
- Minimum 80% coverage per unit per day
- Maximum 10% consecutive missing values
- Operational state valid for >90% of records

---

## 3. Configuration Data Contracts

### 3.1 Signal Registry

**Location**: `data/telemetry/config/signal_registry_v1.yaml`

**Description**: Metadata for all monitored telemetry signals

**Schema** (YAML):

```yaml
version: string              # Format: "X.Y"
last_updated: date           # Format: "YYYY-MM-DD"

signals:
  - name: string             # Unique signal identifier
    display_name: string     # Human-readable name
    system: string           # Parent system (Engine, Transmission, etc.)
    subsystem: string        # Subsystem (Cooling, Lubrication, etc.)
    unit: string             # Unit of measurement
    risk_direction: enum     # "high", "low", "both"
    valid_states: list       # Valid operational states
    physical_min: float      # Physical minimum possible value
    physical_max: float      # Physical maximum possible value
    criticality: int         # 1=low, 2=medium, 3=high
    enabled_techniques: list # Techniques to apply
    baseline_required: bool  # Whether baseline is needed
    minimum_samples_per_day: int  # Minimum daily samples
```

**Field Descriptions**:

| Field | Description | Example |
|-------|-------------|---------|
| `name` | Technical signal identifier | "EngCoolTemp" |
| `display_name` | User-friendly name | "Engine Coolant Temperature" |
| `system` | Primary system | "Engine" |
| `subsystem` | System component | "Cooling" |
| `risk_direction` | Risk interpretation | "high" (high values = risk) |
| `valid_states` | States where signal is meaningful | ["Operacional", "Ralenti"] |
| `physical_min` | Physical lower limit | 0.0 |
| `physical_max` | Physical upper limit | 150.0 |
| `criticality` | Signal importance | 3 |
| `enabled_techniques` | Active techniques | ["threshold_deviation", "trend_analysis"] |

**Example Entry**:
```yaml
signals:
  - name: "EngCoolTemp"
    display_name: "Engine Coolant Temperature"
    system: "Engine"
    subsystem: "Cooling"
    unit: "°C"
    risk_direction: "high"
    valid_states:
      - "Operacional"
      - "Ralenti"
    physical_min: 0.0
    physical_max: 150.0
    criticality: 3
    enabled_techniques:
      - "threshold_deviation"
      - "event_detection"
      - "trend_analysis"
      - "diagnostic_rules"
    baseline_required: true
    minimum_samples_per_day: 800
```

---

### 3.2 Technique Configuration

**Location**: `data/telemetry/config/technique_config.yaml`

**Description**: Execution parameters for each analytical technique

**Schema** (YAML):

```yaml
version: string
last_updated: date

techniques:
  - name: string              # Technique identifier
    cadence: string           # Execution frequency
    lookback_window: string   # Data window to analyze
    validity_period: string   # How long results are valid
    thresholds:               # Technique-specific thresholds
      [key: value]
```

**Example**:
```yaml
techniques:
  - name: "threshold_deviation"
    cadence: "daily"
    lookback_window: "24h"
    validity_period: "2d"
    thresholds:
      warning_percentile: 5    # P5 or P95
      abnormal_percentile: 1   # P1 or P99
      minimum_event_duration_minutes: 15
      
  - name: "trend_analysis"
    cadence: "weekly"
    lookback_window: "8w"
    validity_period: "1w"
    thresholds:
      minimum_weeks: 4
      p_value_threshold: 0.05
      min_slope_significance: 0.5
```

---

## 4. Baseline Data Contracts

### 4.1 Baseline Statistics Table

**Location**: `data/telemetry/analytical_results/baselines/baseline_{YYYYMMDD}.parquet`

**Description**: State-specific percentiles and statistics for anomaly detection

**Schema**:

| Field | Type | Nullable | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `baseline_version` | string | No | Baseline version identifier | Format: YYYYMMDD |
| `client` | string | No | Client identifier | Uppercase |
| `equipment_model` | string | No | Equipment model | e.g., "CAT 789D" |
| `unit_id` | string | Yes | Specific unit (if unit-level baseline) | Null for aggregate |
| `signal_name` | string | No | Signal identifier | Must exist in registry |
| `operational_state` | string | No | Operational state | One of: Operacional, Ralenti, Apagada, ND |
| `p1` | float64 | Yes | 1st percentile | Can be null if insufficient data |
| `p5` | float64 | Yes | 5th percentile | |
| `p50` | float64 | Yes | Median (50th percentile) | |
| `p95` | float64 | Yes | 95th percentile | |
| `p99` | float64 | Yes | 99th percentile | |
| `mean` | float64 | Yes | Arithmetic mean | |
| `std` | float64 | Yes | Standard deviation | |
| `mad` | float64 | Yes | Median Absolute Deviation | Robust alternative to std |
| `sample_count` | int64 | No | Number of observations | Must be ≥1000 for valid baseline |
| `training_window_start` | datetime64[ns] | No | Start of training period | |
| `training_window_end` | datetime64[ns] | No | End of training period | |
| `quality_score` | float64 | No | Baseline quality (0-1) | Based on sample count, distribution |
| `fallback_level` | string | No | Baseline granularity | "unit", "model", "client", "global" |

**Partitioning**: `year={year}/month={month}`

**Example Record**:
```json
{
  "baseline_version": "20260524",
  "client": "CDA",
  "equipment_model": "CAT 789D",
  "unit_id": "CDA_UNIT_042",
  "signal_name": "EngCoolTemp",
  "operational_state": "Operacional",
  "p1": 65.2,
  "p5": 68.5,
  "p50": 82.3,
  "p95": 95.8,
  "p99": 102.5,
  "mean": 83.1,
  "std": 8.7,
  "mad": 6.4,
  "sample_count": 45600,
  "training_window_start": "2026-02-24T00:00:00Z",
  "training_window_end": "2026-05-24T23:59:59Z",
  "quality_score": 0.92,
  "fallback_level": "unit"
}
```

**Fallback Hierarchy**:
1. **unit**: Baseline specific to unit_id + model + signal + state
2. **model**: Baseline for model + signal + state (across all units)
3. **client**: Baseline for client + signal + state (across all models)
4. **global**: Baseline for signal + state (across all clients)

---

### 4.2 Baseline Metadata

**Location**: `data/telemetry/analytical_results/baselines/baseline_metadata.json`

**Description**: Metadata about baseline generation process

**Schema** (JSON):

```json
{
  "baseline_version": "string",          // YYYYMMDD
  "generation_timestamp": "datetime",    // ISO 8601
  "training_window_days": "int",         // e.g., 90
  "total_baselines_generated": "int",
  "baselines_by_fallback_level": {
    "unit": "int",
    "model": "int",
    "client": "int",
    "global": "int"
  },
  "baselines_by_quality": {
    "high": "int",      // quality_score > 0.8
    "medium": "int",    // quality_score 0.5-0.8
    "low": "int"        // quality_score < 0.5
  },
  "signals_covered": ["string"],
  "clients_covered": ["string"],
  "refresh_schedule": "string"           // e.g., "monthly"
}
```

---

## 5. Technique Result Data Contracts

### 5.1 Common TechniqueResult Schema

**Description**: Standard fields present in all technique outputs

**Common Fields**:

| Field | Type | Nullable | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `result_id` | string | No | Unique result identifier | UUID v4 |
| `technique_name` | string | No | Technique identifier | e.g., "threshold_deviation" |
| `technique_version` | string | No | Technique version | Semantic versioning |
| `evaluation_timestamp` | datetime64[ns] | No | When evaluation was performed | ISO 8601 |
| `evaluation_window_start` | datetime64[ns] | No | Start of evaluated period | |
| `evaluation_window_end` | datetime64[ns] | No | End of evaluated period | |
| `unit_id` | string | No | Equipment identifier | |
| `client` | string | No | Client identifier | |
| `equipment_model` | string | No | Equipment model | |
| `signal_name` | string | No | Signal evaluated | |
| `system` | string | No | System classification | From signal registry |
| `risk_score` | float64 | No | Normalized risk (0-100) | 0=normal, 100=critical |
| `confidence_score` | float64 | No | Result confidence (0-100) | Based on data quality |
| `status` | string | No | Classification | "Normal", "Alerta", "Anormal", "InsufficientData" |
| `validity_period_days` | int64 | No | Days result is valid | |
| `baseline_version` | string | Yes | Baseline used (if applicable) | YYYYMMDD |
| `evidence` | JSON | No | Technique-specific evidence | See technique sections |
| `schema_version` | string | No | Data contract version | "1.0.0" |

---

### 5.2 Threshold Deviation Result

**Location**: `data/telemetry/analytical_results/technique_results/threshold_deviation/`

**Partitioning**: `year={year}/month={month}/day={day}`

**Additional Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `operational_state` | string | State during evaluation |
| `sample_count` | int64 | Valid samples in window |
| `coverage_pct` | float64 | % of expected samples present |

**Evidence Structure** (JSON):

```json
{
  "baseline_p1": 65.2,
  "baseline_p5": 68.5,
  "baseline_p95": 95.8,
  "baseline_p99": 102.5,
  "observed_mean": 88.3,
  "observed_max": 105.2,
  "observed_min": 72.1,
  "warning_exceedance_pct": 8.5,      // % beyond P5/P95
  "abnormal_exceedance_pct": 2.3,     // % beyond P1/P99
  "max_deviation": 12.7,               // Max distance from baseline
  "mean_deviation": 5.4,
  "event_count": 3,
  "longest_event_duration_minutes": 45,
  "data_quality": {
    "coverage": 0.94,
    "missing_pct": 6.0,
    "flatline_detected": false
  }
}
```

**Example Complete Record**:
```json
{
  "result_id": "f7c8d3a1-4b2e-4d9a-8f3c-1e5a6b7c8d9e",
  "technique_name": "threshold_deviation",
  "technique_version": "1.0.0",
  "evaluation_timestamp": "2026-05-24T02:15:00Z",
  "evaluation_window_start": "2026-05-23T00:00:00Z",
  "evaluation_window_end": "2026-05-23T23:59:59Z",
  "unit_id": "CDA_UNIT_042",
  "client": "CDA",
  "equipment_model": "CAT 789D",
  "signal_name": "EngCoolTemp",
  "system": "Engine",
  "risk_score": 72.5,
  "confidence_score": 94.0,
  "status": "Anormal",
  "validity_period_days": 2,
  "baseline_version": "20260524",
  "operational_state": "Operacional",
  "sample_count": 1356,
  "coverage_pct": 94.2,
  "evidence": { /* see above */ },
  "schema_version": "1.0.0"
}
```

---

### 5.3 Trend Analysis Result

**Location**: `data/telemetry/analytical_results/technique_results/trend_analysis/`

**Partitioning**: `year={year}/week={week}`

**Additional Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `lookback_weeks` | int64 | Number of weeks analyzed (4, 8, or 12) |
| `valid_weeks` | int64 | Weeks with sufficient data |

**Evidence Structure** (JSON):

```json
{
  "regression_method": "linear",        // "linear" or "theil_sen"
  "slope": -0.8,                        // Units per week
  "intercept": 85.2,
  "r_squared": 0.78,
  "p_value": 0.003,
  "statistically_significant": true,
  "trend_direction": "degrading",       // "improving", "stable", "degrading"
  "recent_mean": 79.3,                  // Last 2 weeks
  "baseline_mean": 83.1,                // Baseline from training
  "delta_pct": -4.6,                    // % change
  "weekly_values": [83.2, 82.5, 81.1, 79.8, 78.5, 77.9, 79.0, 79.6],
  "weeks_with_data": 8,
  "data_quality": {
    "valid_weeks": 8,
    "expected_weeks": 8,
    "min_coverage": 0.87
  }
}
```

---

### 5.4 Diagnostic Rules Result

**Location**: `data/telemetry/analytical_results/technique_results/diagnostic_rules/`

**Partitioning**: `year={year}/month={month}/day={day}` (daily) or `year={year}/week={week}` (weekly)

**Additional Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | string | Rule identifier from diagnostic_rules.yaml |
| `rule_name` | string | Human-readable rule name |
| `systems_affected` | list[string] | Systems involved in rule |

**Evidence Structure** (JSON):

```json
{
  "rule_description": "Engine Overheating Pattern",
  "rule_severity": "high",
  "conditions_met": [
    {
      "signal": "EngCoolTemp",
      "condition": "above_p95",
      "threshold": 95.8,
      "observed": 102.3,
      "duration_minutes": 120
    },
    {
      "signal": "TCOutTemp",
      "condition": "above_p95",
      "threshold": 88.5,
      "observed": 94.2,
      "duration_minutes": 115
    }
  ],
  "concurrent_duration_minutes": 115,
  "operational_state": "Operacional",
  "first_trigger": "2026-05-23T14:30:00Z",
  "last_trigger": "2026-05-23T16:25:00Z"
}
```

---

### 5.5 Event Detection Result

**Location**: `data/telemetry/analytical_results/events/`

**Description**: Individual abnormal episodes detected

**Partitioning**: `year={year}/month={month}/day={day}`

**Schema**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `event_id` | string | No | Unique event identifier |
| `unit_id` | string | No | Equipment identifier |
| `client` | string | No | Client identifier |
| `equipment_model` | string | No | Equipment model |
| `signal_name` | string | No | Signal with event |
| `system` | string | No | System classification |
| `event_start` | datetime64[ns] | No | Event start timestamp |
| `event_end` | datetime64[ns] | No | Event end timestamp |
| `duration_minutes` | int64 | No | Event duration |
| `event_type` | string | No | "spike", "episode", "sustained" |
| `max_value` | float64 | No | Peak value during event |
| `mean_value` | float64 | No | Average during event |
| `max_deviation` | float64 | No | Max distance from baseline |
| `mean_deviation` | float64 | No | Avg distance from baseline |
| `operational_state` | string | No | State during event |
| `severity_score` | float64 | No | Event severity (0-100) |
| `baseline_version` | string | Yes | Baseline used |
| `consecutive_minutes` | int64 | No | Uninterrupted abnormal minutes |
| `source_technique` | string | No | Technique that detected event |
| `schema_version` | string | No | Data contract version |

**Event Type Classification**:
- **spike**: Duration < 5 minutes
- **episode**: Duration 5-60 minutes
- **sustained**: Duration > 60 minutes

**Example Record**:
```json
{
  "event_id": "evt_20260523_cda042_engcooltemp_001",
  "unit_id": "CDA_UNIT_042",
  "client": "CDA",
  "equipment_model": "CAT 789D",
  "signal_name": "EngCoolTemp",
  "system": "Engine",
  "event_start": "2026-05-23T14:30:00Z",
  "event_end": "2026-05-23T16:25:00Z",
  "duration_minutes": 115,
  "event_type": "sustained",
  "max_value": 105.2,
  "mean_value": 102.8,
  "max_deviation": 12.7,
  "mean_deviation": 10.3,
  "operational_state": "Operacional",
  "severity_score": 78.5,
  "baseline_version": "20260524",
  "consecutive_minutes": 115,
  "source_technique": "threshold_deviation",
  "schema_version": "1.0.0"
}
```

---

## 6. Aggregation Data Contracts

### 6.1 System Health

**Location**: `data/telemetry/analytical_results/system_health/`

**Partitioning**: `year={year}/week={week}/client={client}`

**Description**: Aggregated health assessment per system per unit

**Schema**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `assessment_id` | string | No | Unique assessment identifier |
| `assessment_timestamp` | datetime64[ns] | No | When assessment was performed |
| `assessment_window_start` | datetime64[ns] | No | Period start |
| `assessment_window_end` | datetime64[ns] | No | Period end |
| `unit_id` | string | No | Equipment identifier |
| `client` | string | No | Client identifier |
| `equipment_model` | string | No | Equipment model |
| `system` | string | No | System name |
| `system_risk_score` | float64 | No | Aggregated risk (0-100) |
| `system_confidence_score` | float64 | No | Aggregated confidence (0-100) |
| `system_status` | string | No | "Normal", "Alerta", "Anormal", "InsufficientData" |
| `contributing_signals` | JSON | No | Top signals driving score |
| `technique_results_used` | JSON | No | Techniques contributing |
| `week_over_week_delta` | float64 | Yes | Change from previous week |
| `trend_direction` | string | Yes | "improving", "stable", "degrading" |
| `schema_version` | string | No | Data contract version |

**Contributing Signals Structure** (JSON):

```json
{
  "top_3_signals": [
    {
      "signal_name": "EngCoolTemp",
      "risk_score": 72.5,
      "confidence": 94.0,
      "contribution_weight": 0.45
    },
    {
      "signal_name": "EngOilPres",
      "risk_score": 65.3,
      "confidence": 88.0,
      "contribution_weight": 0.35
    },
    {
      "signal_name": "EngSpd",
      "risk_score": 42.1,
      "confidence": 91.0,
      "contribution_weight": 0.20
    }
  ]
}
```

**Technique Results Used Structure** (JSON):

```json
{
  "techniques": [
    {
      "technique": "threshold_deviation",
      "results_count": 15,
      "avg_risk": 68.2,
      "max_risk": 82.5
    },
    {
      "technique": "trend_analysis",
      "results_count": 3,
      "avg_risk": 55.7,
      "max_risk": 65.3
    },
    {
      "technique": "diagnostic_rules",
      "results_count": 1,
      "avg_risk": 78.0,
      "max_risk": 78.0
    }
  ]
}
```

**Example Record**:
```json
{
  "assessment_id": "syshealth_w21_2026_cda042_engine",
  "assessment_timestamp": "2026-05-25T06:00:00Z",
  "assessment_window_start": "2026-05-19T00:00:00Z",
  "assessment_window_end": "2026-05-25T23:59:59Z",
  "unit_id": "CDA_UNIT_042",
  "client": "CDA",
  "equipment_model": "CAT 789D",
  "system": "Engine",
  "system_risk_score": 68.5,
  "system_confidence_score": 91.3,
  "system_status": "Alerta",
  "contributing_signals": { /* see above */ },
  "technique_results_used": { /* see above */ },
  "week_over_week_delta": 12.3,
  "trend_direction": "degrading",
  "schema_version": "1.0.0"
}
```

---

### 6.2 Unit Health

**Location**: `data/telemetry/analytical_results/unit_health/`

**Partitioning**: `year={year}/week={week}/client={client}`

**Description**: Overall equipment health assessment with priority scoring

**Schema**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `assessment_id` | string | No | Unique assessment identifier |
| `assessment_timestamp` | datetime64[ns] | No | When assessment was performed |
| `assessment_window_start` | datetime64[ns] | No | Period start |
| `assessment_window_end` | datetime64[ns] | No | Period end |
| `unit_id` | string | No | Equipment identifier |
| `client` | string | No | Client identifier |
| `equipment_model` | string | No | Equipment model |
| `unit_risk_score` | float64 | No | Overall risk (0-100) |
| `unit_confidence_score` | float64 | No | Overall confidence (0-100) |
| `unit_status` | string | No | "Normal", "Alerta", "Anormal", "InsufficientData" |
| `priority_score` | float64 | No | Maintenance priority (0-100) |
| `maintenance_urgency` | string | No | "immediate", "this_week", "this_month", "monitor" |
| `fleet_percentile` | float64 | Yes | Percentile within fleet (0-100) |
| `systems_affected` | JSON | No | System-level breakdown |
| `top_risk_systems` | JSON | No | Top 3 systems by risk |
| `diagnostic_rules_fired` | JSON | Yes | Rules triggered this period |
| `week_over_week_delta` | float64 | Yes | Change from previous week |
| `health_velocity` | float64 | Yes | Points/week change rate |
| `explanation` | string | No | Natural language summary |
| `schema_version` | string | No | Data contract version |

**Systems Affected Structure** (JSON):

```json
{
  "systems": [
    {
      "system": "Engine",
      "risk_score": 68.5,
      "confidence": 91.3,
      "status": "Alerta"
    },
    {
      "system": "Transmission",
      "risk_score": 42.1,
      "confidence": 87.5,
      "status": "Normal"
    },
    {
      "system": "Brakes",
      "risk_score": 55.3,
      "confidence": 89.2,
      "status": "Alerta"
    },
    {
      "system": "Differential",
      "risk_score": 28.7,
      "confidence": 85.0,
      "status": "Normal"
    },
    {
      "system": "Hydraulics",
      "risk_score": 35.2,
      "confidence": 88.1,
      "status": "Normal"
    },
    {
      "system": "Electrical",
      "risk_score": 22.5,
      "confidence": 82.3,
      "status": "Normal"
    }
  ]
}
```

**Top Risk Systems** (JSON):

```json
{
  "top_3": [
    {
      "system": "Engine",
      "risk_score": 68.5,
      "primary_issue": "Elevated coolant temperature with degrading trend"
    },
    {
      "system": "Brakes",
      "risk_score": 55.3,
      "primary_issue": "Front left brake temperature imbalance"
    },
    {
      "system": "Transmission",
      "risk_score": 42.1,
      "primary_issue": "Lubrication temperature above normal range"
    }
  ]
}
```

**Example Explanation**:
```
"Unit CDA_UNIT_042 shows elevated risk (score 62, Alerta status) driven by Engine system (score 68) with repeated coolant temperature exceedances (8.5% of operational time, 3 events >30min) and declining oil pressure trend (-0.8 kPa/week over 8 weeks). Brakes system also shows concern (score 55) with front left brake running 15°C hotter than other corners. Recommend inspection within this week."
```

**Example Record**:
```json
{
  "assessment_id": "unithealth_w21_2026_cda042",
  "assessment_timestamp": "2026-05-25T06:30:00Z",
  "assessment_window_start": "2026-05-19T00:00:00Z",
  "assessment_window_end": "2026-05-25T23:59:59Z",
  "unit_id": "CDA_UNIT_042",
  "client": "CDA",
  "equipment_model": "CAT 789D",
  "unit_risk_score": 62.3,
  "unit_confidence_score": 89.7,
  "unit_status": "Alerta",
  "priority_score": 71.5,
  "maintenance_urgency": "this_week",
  "fleet_percentile": 87.5,
  "systems_affected": { /* see above */ },
  "top_risk_systems": { /* see above */ },
  "diagnostic_rules_fired": {
    "rules": [
      {
        "rule_id": "engine_overheating",
        "rule_name": "Engine Overheating Pattern",
        "severity": "high",
        "first_fired": "2026-05-23T14:30:00Z"
      }
    ]
  },
  "week_over_week_delta": 10.2,
  "health_velocity": -5.1,
  "explanation": "Unit CDA_UNIT_042 shows elevated risk...",
  "schema_version": "1.0.0"
}
```

**Maintenance Urgency Classification**:

| Urgency | Criteria |
|---------|----------|
| `immediate` | Unit status = Anormal AND critical system affected AND diagnostic rule fired |
| `this_week` | Unit status = Anormal OR (Alerta AND health_velocity < -5) |
| `this_month` | Unit status = Alerta AND health_velocity > -5 |
| `monitor` | Unit status = Normal OR InsufficientData |

---

### 6.3 Weekly Signal Aggregates

**Location**: `data/telemetry/analytical_results/aggregates/weekly/`

**Partitioning**: `year={year}/week={week}`

**Description**: Weekly statistical summaries per signal per unit

**Schema**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `unit_id` | string | No | Equipment identifier |
| `client` | string | No | Client identifier |
| `equipment_model` | string | No | Equipment model |
| `signal_name` | string | No | Signal identifier |
| `system` | string | No | System classification |
| `operational_state` | string | No | Operational state |
| `year` | int64 | No | ISO year |
| `week` | int64 | No | ISO week number |
| `week_start` | datetime64[ns] | No | Week start (Monday) |
| `week_end` | datetime64[ns] | No | Week end (Sunday) |
| `mean` | float64 | Yes | Weekly mean |
| `median` | float64 | Yes | Weekly median |
| `std` | float64 | Yes | Standard deviation |
| `p5` | float64 | Yes | 5th percentile |
| `p50` | float64 | Yes | 50th percentile |
| `p95` | float64 | Yes | 95th percentile |
| `p99` | float64 | Yes | 99th percentile |
| `min` | float64 | Yes | Minimum value |
| `max` | float64 | Yes | Maximum value |
| `hours_in_state` | float64 | No | Hours in this state |
| `sample_count` | int64 | No | Valid samples |
| `coverage_pct` | float64 | No | % of expected samples |
| `abnormal_pct` | float64 | Yes | % time beyond thresholds |
| `event_count` | int64 | Yes | Number of events |
| `longest_event_minutes` | int64 | Yes | Longest event duration |
| `schema_version` | string | No | Data contract version |

**Example Record**:
```json
{
  "unit_id": "CDA_UNIT_042",
  "client": "CDA",
  "equipment_model": "CAT 789D",
  "signal_name": "EngCoolTemp",
  "system": "Engine",
  "operational_state": "Operacional",
  "year": 2026,
  "week": 21,
  "week_start": "2026-05-19T00:00:00Z",
  "week_end": "2026-05-25T23:59:59Z",
  "mean": 85.3,
  "median": 83.7,
  "std": 9.2,
  "p5": 70.5,
  "p50": 83.7,
  "p95": 98.2,
  "p99": 104.1,
  "min": 65.2,
  "max": 108.3,
  "hours_in_state": 87.5,
  "sample_count": 5250,
  "coverage_pct": 92.3,
  "abnormal_pct": 8.5,
  "event_count": 3,
  "longest_event_minutes": 115,
  "schema_version": "1.0.0"
}
```

---

## 7. Event Data Contracts

**Covered in Section 5.5 above** — See Event Detection Result schema

---

## 8. Supporting Data Contracts

### 8.1 Fleet Summary

**Location**: `data/telemetry/analytical_results/fleet_summary/`

**Partitioning**: `year={year}/week={week}/client={client}`

**Description**: Fleet-level statistics for benchmarking

**Schema**:

| Field | Type | Description |
|-------|------|-------------|
| `client` | string | Client identifier |
| `year` | int64 | ISO year |
| `week` | int64 | ISO week number |
| `total_units` | int64 | Units in fleet |
| `units_evaluated` | int64 | Units with assessments |
| `mean_unit_health` | float64 | Average unit risk score |
| `median_unit_health` | float64 | Median unit risk score |
| `std_unit_health` | float64 | Standard deviation |
| `p25_unit_health` | float64 | 25th percentile |
| `p75_unit_health` | float64 | 75th percentile |
| `p90_unit_health` | float64 | 90th percentile |
| `units_normal` | int64 | Units with Normal status |
| `units_alerta` | int64 | Units with Alerta status |
| `units_anormal` | int64 | Units with Anormal status |
| `units_insufficient_data` | int64 | Units with InsufficientData |
| `top_10_priority_units` | JSON | Highest priority units |
| `systems_at_risk_count` | JSON | Systems showing elevated risk |
| `schema_version` | string | Data contract version |

---

## 9. Schema Versioning

### 9.1 Versioning Strategy

**Semantic Versioning**: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes (field removed, type changed)
- **MINOR**: Backward-compatible additions (new field)
- **PATCH**: Non-functional changes (documentation, constraints)

**Current Version**: All schemas are at `1.0.0`

### 9.2 Version Field

All output schemas include `schema_version` field:
```python
"schema_version": "1.0.0"
```

### 9.3 Schema Evolution

**Adding a field** (MINOR version bump):
```python
# v1.0.0
{
  "unit_id": "CDA_UNIT_042",
  "risk_score": 72.5
}

# v1.1.0 (added confidence_score)
{
  "unit_id": "CDA_UNIT_042",
  "risk_score": 72.5,
  "confidence_score": 94.0,  # NEW
  "schema_version": "1.1.0"
}
```

**Changing a field type** (MAJOR version bump):
```python
# v1.0.0
{
  "event_count": 3  # int
}

# v2.0.0 (changed to float)
{
  "event_count": 3.0,  # BREAKING: now float
  "schema_version": "2.0.0"
}
```

---

## 10. Data Quality Standards

### 10.1 Input Data Quality Requirements

| Metric | Threshold | Action if Failed |
|--------|-----------|------------------|
| Coverage per unit per day | ≥80% | Flag unit as InsufficientData |
| Consecutive missing values | ≤10% | Log warning, continue |
| Valid operational state | ≥90% | Filter invalid states |
| Signal value in physical range | ≥95% | Filter out-of-range values |

### 10.2 Output Data Quality Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| No null risk_score | All outputs have valid risk_score (0-100) or status=InsufficientData |
| No null confidence_score | All outputs have valid confidence_score (0-100) |
| Evidence always present | Evidence field is never null, may be empty JSON |
| Schema version present | All outputs include schema_version field |
| Timestamps in UTC | All datetime fields are UTC with timezone info |

### 10.3 Data Retention Policies

| Data Type | Retention Period | Rationale |
|-----------|------------------|-----------|
| Silver telemetry | Managed upstream | Input data |
| Baselines | 12 months (keep last 12 versions) | Need history for comparison |
| Technique results | 12 months | Sufficient for backtesting |
| System health | 24 months | Long-term trends |
| Unit health | 24 months | Long-term trends |
| Events | 24 months | Historical event analysis |
| Weekly aggregates | 24 months | Trend analysis requires long windows |

---

## Appendix A: Example Data Flow

**Input**: 1 day of Silver telemetry for CDA_UNIT_042, signal EngCoolTemp

**Processing**:
1. Load 24h window → 1440 minutes × 1 signal = 1440 records
2. Retrieve baseline (P1=65.2, P99=102.5)
3. Calculate exceedances → 2.3% beyond P99
4. Generate TechniqueResult (risk_score=72.5)
5. Aggregate to SystemHealth (Engine score=68.5)
6. Aggregate to UnitHealth (unit score=62.3, priority=71.5)

**Outputs**:
- 1 TechniqueResult record → `technique_results/threshold_deviation/year=2026/month=05/day=23/`
- 1 SystemHealth record → `system_health/year=2026/week=21/client=CDA/`
- 1 UnitHealth record → `unit_health/year=2026/week=21/client=CDA/`
- 3 Event records → `events/year=2026/month=05/day=23/`

---

## Appendix B: Schema Change Log

| Date | Schema | Version | Change | Type |
|------|--------|---------|--------|------|
| 2026-05-24 | All | 1.0.0 | Initial schema definitions | Initial |

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-05-24 | Senior Data Scientist | Initial data contracts documentation |

---

**Related Documents**
- [Implementation Plan](implementation_plan.md)
- [Project Overview](project_overview.md)
- [Implementation Guidelines](implementation_guidelines.md)
- Phase Implementation Guides (1-5)
