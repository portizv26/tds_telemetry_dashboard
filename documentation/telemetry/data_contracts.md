# Telemetry Analysis - Data Contracts

**Version**: 2.0  
**Created**: February 18, 2026  
**Owner**: Patricio Ortiz - Data Team
**Purpose**: Define schemas and data structures for telemetry analysis

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Input Data Contracts](#input-data-contracts)
3. [Intermediate Data Contracts](#intermediate-data-contracts)
4. [Output Data Contracts](#output-data-contracts)
5. [Data Quality Requirements](#data-quality-requirements)

---

## 🎯 Overview

This document defines the data contracts for all inputs and outputs in the telemetry analysis pipeline. All files use **Parquet** or **JSON** format for efficiency and type safety.

### Data Flow
```
INPUT (Silver Layer)
    ↓
PROCESSING (Analysis Pipeline)
    ↓
INTERMEDIATE (Internal structures)
    ↓
OUTPUT (Golden Layer)
```

---

## 📥 Input Data Contracts

### 1. Telemetry Weekly Files

**Location**: `data/telemetry/silver/{client}/Telemetry_Wide_With_States/Week{WW}Year{YYYY}.parquet`

**File Naming Convention**:
- Pattern: `Week{WW}Year{YYYY}.parquet`
- Examples: `Week10Year2025.parquet`, `Week52Year2024.parquet`
- WW: Zero-padded week number (01-52)
- YYYY: Four-digit year

**Description**: Pre-processed telemetry data with 5-minute moving window aggregation

**Schema**:

| Column | Type | Description | Example | Constraints |
|--------|------|-------------|---------|-------------|
| `Fecha` | datetime64[ns] | Timestamp of reading | 2025-03-10 14:35:00 | Not null, monotonic |
| `Unit` | string | Equipment identifier | "Unit_247" | Not null |
| `Estado` | string | Operational state | "Operacional", "Ralenti" | Not null |
| `EstadoMaquina` | string | Machine state | "En Tarea", "Disponible" | Not null |
| `EstadoCarga` | string | Load state | "Cargado", "Descargado" | Not null |
| `GPSLat` | float64 | GPS Latitude | -33.456789 | -90 to 90 |
| `GPSLon` | float64 | GPS Longitude | -70.123456 | -180 to 180 |
| `GPSElevation` | float64 | GPS Elevation (meters) | 2847.5 | >= 0 |
| `AirFltr` | float64 | Air filter pressure (kPa) | 3.2 | >= 0 |
| `CnkcasePres` | float64 | Crankcase pressure (kPa) | 0.8 | >= 0 |
| `DiffLubePres` | float64 | Differential lube pressure (kPa) | 250.5 | >= 0 |
| `DiffTemp` | float64 | Differential temperature (°C) | 85.3 | -50 to 200 |
| `EngCoolTemp` | float64 | Engine coolant temp (°C) | 88.5 | -50 to 150 |
| `EngOilFltr` | float64 | Engine oil filter pressure (kPa) | 4.1 | >= 0 |
| `EngOilPres` | float64 | Engine oil pressure (kPa) | 420.3 | >= 0 |
| `EngSpd` | float64 | Engine speed (RPM) | 1850.0 | 0 to 3000 |
| `GroundSpd` | float64 | Ground speed (km/h) | 35.2 | >= 0 |
| `LtExhTemp` | float64 | Left exhaust temp (°C) | 485.2 | 0 to 800 |
| `LtFBrkTemp` | float64 | Left front brake temp (°C) | 125.8 | -50 to 500 |
| `LtRBrkTemp` | float64 | Left rear brake temp (°C) | 132.4 | -50 to 500 |
| `Payload` | float64 | Payload weight (tonnes) | 220.5 | >= 0 |
| `RAftrclrTemp` | float64 | Right aftercooler temp (°C) | 55.3 | -50 to 150 |
| `RtExhTemp` | float64 | Right exhaust temp (°C) | 490.1 | 0 to 800 |
| `RtFBrkTemp` | float64 | Right front brake temp (°C) | 128.3 | -50 to 500 |
| `RtLtExhTemp` | float64 | Right-left exhaust temp (°C) | 487.6 | 0 to 800 |
| `RtRBrkTemp` | float64 | Right rear brake temp (°C) | 135.7 | -50 to 500 |
| `StrgOilTemp` | float64 | Steering oil temp (°C) | 65.2 | -50 to 150 |
| `TCOutTemp` | float64 | Turbocharger outlet temp (°C) | 210.5 | 0 to 500 |
| `TrnLubeTemp` | float64 | Transmission lube temp (°C) | 95.8 | -50 to 200 |

**Data Characteristics**:
- **Pre-processed**: Values are 5-minute moving window averages
- **Frequency**: Approximately one reading every 5 minutes (when equipment is operating)
- **Missing Data**: Some signals may be null if sensor not available
- **Row Count**: Varies by week and unit activity (typically 10,000-50,000 rows per week per unit)

---

### 2. Component-Signal Mapping

**Location**: `data/telemetry/component_signals_mapping.json`

**Description**: Defines which sensor signals belong to each mechanical component

**Schema**:

```json
{
  "Motor": ["string"],           // Array of signal names for Motor component
  "Tren de fuerza": ["string"],  // Array of signal names for Powertrain component
  "Frenos": ["string"],          // Array of signal names for Brakes component
  "Direccion": ["string"]        // Array of signal names for Steering component
}
```

**Example**:

```json
{
  "Motor": [
    "EngCoolTemp",
    "RAftrclrTemp",
    "EngOilPres",
    "EngSpd",
    "EngOilFltr",
    "CnkcasePres",
    "RtLtExhTemp",
    "RtExhTemp",
    "LtExhTemp",
    "AirFltr"
  ],
  "Tren de fuerza": [
    "DiffLubePres",
    "DiffTemp",
    "TrnLubeTemp",
    "TCOutTemp"
  ],
  "Frenos": [
    "RtRBrkTemp",
    "RtFBrkTemp",
    "LtRBrkTemp",
    "LtFBrkTemp"
  ],
  "Direccion": [
    "StrgOilTemp"
  ]
}
```

**Constraints**:
- All signals must be unique (no signal in multiple components)
- Signal names must match column names in telemetry files
- At least one signal per component

---

## 🔄 Intermediate Data Contracts

These structures are used internally during processing and may not be persisted.

### 1. Signal Baselines

**Location**: `data/telemetry/golden/{client}/signal_baselines.parquet`

**Description**: Pre-computed percentile baselines for statistical analysis

**Schema**:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `signal` | string | Signal name | "EngCoolTemp" |
| `state` | string | Operational state combination | "Operacional-Cargado" |
| `P1` | float64 | 1st percentile | 75.2 |
| `P5` | float64 | 5th percentile | 78.5 |
| `P25` | float64 | 25th percentile (Q1) | 83.1 |
| `P50` | float64 | 50th percentile (median) | 88.2 |
| `P75` | float64 | 75th percentile (Q3) | 93.5 |
| `P95` | float64 | 95th percentile | 98.1 |
| `P99` | float64 | 99th percentile | 101.3 |
| `sample_count` | int64 | Number of samples used | 15847 |
| `baseline_start` | datetime64[ns] | Start of baseline period | 2025-01-01 00:00:00 |
| `baseline_end` | datetime64[ns] | End of baseline period | 2025-02-28 23:55:00 |

**Update Frequency**: Recalculated weekly using last 4-8 weeks of data

---

### 2. Signal Evaluation (Internal Structure)

**Description**: Internal Python dict structure used during signal evaluation (not persisted as separate file)

**Structure**:

```python
{
    'unit': 'Unit_247',
    'timestamp': datetime(2025, 3, 10, 14, 35, 0),
    'signal': 'EngCoolTemp',
    'component': 'Motor',
    'value': 103.5,
    'state': 'Operacional-Cargado',
    'grade': 'Anormal',           # 'Normal', 'Alerta', 'Anormal'
    'score': 10,                   # 0, 5, or 10
    'baseline_P50': 88.2,
    'baseline_P95': 98.1,
    'baseline_P99': 101.3,
    'deviation': 'Exceeded P99 by 2.2°C',
    'detection_methods': ['percentile_baseline']  # Methods that triggered alert
}
```

---

## 📤 Output Data Contracts

### 1. Machine Status

**Location**: `data/telemetry/golden/{client}/machine_status.parquet`

**Description**: Overall health status per unit (one row per unit)

**Schema**:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `unit_id` | string | Equipment identifier | "Unit_247" |
| `client` | string | Client identifier | "cda" |
| `latest_sample_date` | datetime64[ns] | Last evaluation timestamp | 2025-03-10 20:35:00 |
| `overall_status` | string | Machine health grade | "Anormal" |
| `machine_score` | float64 | Total criticality score | 35.0 |
| `total_components` | int64 | Number of components monitored | 4 |
| `components_normal` | int64 | Count of Normal components | 1 |
| `components_alerta` | int64 | Count of Alerta components | 1 |
| `components_anormal` | int64 | Count of Anormal components | 2 |
| `priority_score` | float64 | Weighted maintenance priority | 62.5 |
| `component_details` | object (list[dict]) | Details per component | See below |

**`component_details` Structure**:

```python
[
    {
        'component': 'Motor',
        'status': 'Anormal',
        'score': 25.0,
        'critical_signals': ['EngCoolTemp', 'LtExhTemp']
    },
    {
        'component': 'Frenos',
        'status': 'Alerta',
        'score': 10.0,
        'critical_signals': ['RtRBrkTemp']
    },
    {
        'component': 'Tren de fuerza',
        'status': 'Normal',
        'score': 0.0,
        'critical_signals': []
    },
    {
        'component': 'Direccion',
        'status': 'Normal',
        'score': 0.0,
        'critical_signals': []
    }
]
```

**Constraints**:
- One row per unit
- `overall_status` ∈ {'Normal', 'Alerta', 'Anormal'}
- `total_components` = `components_normal` + `components_alerta` + `components_anormal`
- `priority_score` uses weighted sum (Motor: 2x, Brakes: 1.5x, Powertrain: 1.5x, Steering: 1x)

---

### 2. Classified Components

**Location**: `data/telemetry/golden/{client}/classified.parquet`

**Description**: Component-level evaluation with signal details (multiple rows per unit)

**Schema**:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `unit` | string | Equipment identifier | "Unit_247" |
| `date` | datetime64[ns] | Evaluation timestamp | 2025-03-10 20:35:00 |
| `component` | string | Component name | "Motor" |
| `component_status` | string | Component health grade | "Anormal" |
| `component_score` | float64 | Component criticality score | 25.0 |
| `signals_evaluation` | object (dict) | Signal-level details (JSON) | See below |
| `ai_recommendation` | string (optional) | AI-generated recommendation | "Inspect cooling system..." |

**`signals_evaluation` Structure**:

```python
{
    'EngCoolTemp': {
        'grade': 'Anormal',
        'score': 10,
        'value': 103.5,
        'baseline_P50': 88.2,
        'baseline_P95': 98.1,
        'baseline_P99': 101.3,
        'deviation': 'Exceeded P99 by 2.2°C',
        'detection_methods': ['percentile_baseline']
    },
    'LtExhTemp': {
        'grade': 'Anormal',
        'score': 10,
        'value': 502.0,
        'baseline_P50': 460.5,
        'baseline_P95': 485.0,
        'baseline_P99': 495.0,
        'deviation': 'Exceeded P99 by 7.0°C',
        'detection_methods': ['percentile_baseline']
    },
    'EngOilPres': {
        'grade': 'Normal',
        'score': 0,
        'value': 425.3,
        'baseline_P50': 420.0,
        'baseline_P95': 445.0,
        'baseline_P99': 460.0,
        'deviation': 'Within normal range'
    }
    // ... other signals in component
}
```

**`ai_recommendation` Example** (added in Phase 1 enhancement):

```text
"Engine coolant temperature and left exhaust temperature have both exceeded 
normal ranges consistently over the past 48 hours. This pattern suggests 
potential cooling system degradation or thermostat malfunction. 

Recommended Action: Inspect cooling system, check coolant levels, and test 
thermostat function. Verify radiator is not blocked.

Urgency: Within 24 hours"
```

**Constraints**:
- Multiple rows per unit (one per component)
- `component_status` ∈ {'Normal', 'Alerta', 'Anormal'}
- `signals_evaluation` must contain all signals for that component
- `ai_recommendation` is null/empty in MVP, populated in Phase 1

---

## ✅ Data Quality Requirements

### Input Data Quality

**Required Validations**:
1. ✅ `Fecha` must be monotonic increasing within each unit
2. ✅ No duplicate (Unit, Fecha) combinations
3. ✅ `Unit` must not be null
4. ✅ Sensor values must be within physically possible ranges
5. ✅ GPS coordinates must be valid (if present)

**Handling Missing Data**:
- **Missing sensors**: Skip evaluation for that sensor (don't fail entire analysis)
- **Missing states**: Use "Unknown" state category
- **Missing GPS**: GPS-based features disabled for that reading

**Data Freshness**:
- Weekly files should be available within 24h of week end
- Analysis runs typically use most recent complete week

---

### Output Data Quality

**Guarantees**:
1. ✅ Every unit in input appears in `machine_status.parquet`
2. ✅ Every component per unit appears in `classified.parquet`
3. ✅ All grades are one of: Normal, Alerta, Anormal
4. ✅ Scores are internally consistent (machine_score = sum of component_scores)
5. ✅ No null values in required fields

---

## 📊 Data Volume Estimates

### Typical Sizes (per client, per week)

| File | Rows | Size (compressed) | Size (uncompressed) |
|------|------|-------------------|---------------------|
| Input: Telemetry week file | 50,000 - 200,000 | 5-20 MB | 20-80 MB |
| Output: machine_status.parquet | 30-50 (one per unit) | <100 KB | <500 KB |
| Output: classified.parquet | 120-200 (4 per unit) | <500 KB | <2 MB |
| Intermediate: signal_baselines.parquet | 500-1000 | <200 KB | <1 MB |

**Storage Requirements** (per client):
- Silver layer (52 weeks): ~1-2 GB
- Golden layer (52 weeks): ~50-100 MB
- Total: ~2 GB per client per year

---

## 🔄 Data Versioning

### Schema Evolution

**Version History**:

- **v1.0** (MVP): Basic grades without AI recommendations
- **v2.0** (Phase 1): Added `ai_recommendation` column to classified.parquet
- **v2.1** (Phase 2): Added `detection_methods` array to signals_evaluation
- **v3.0** (Phase 3): Added forecasting and clustering outputs (TBD)

**Backward Compatibility**:
- New columns are always optional
- Old columns never removed
- Dashboard supports reading both old and new schemas

---

## 📚 Related Documentation

- **[Project Overview](project_overview.md)**: Analysis methods and approach
- **[Dashboard Proposal](dashboard_proposal.md)**: How data is visualized
- **[Final Implementation Plan](final_implementation_plan.md)**: Build roadmap

---

## 🛠️ Data Access Examples

### Reading Telemetry Data

```python
import pandas as pd

# Load specific week
week = 10
year = 2025
client = 'cda'

df = pd.read_parquet(
    f'data/telemetry/silver/{client}/Telemetry_Wide_With_States/Week{week:02d}Year{year}.parquet'
)

# Load only needed columns for performance
df = pd.read_parquet(
    f'data/telemetry/silver/{client}/Telemetry_Wide_With_States/Week{week:02d}Year{year}.parquet',
    columns=['Fecha', 'Unit', 'Estado', 'EngCoolTemp', 'EngOilPres']
)
```

### Reading Component Mapping

```python
import json

with open('data/telemetry/component_signals_mapping.json', 'r') as f:
    component_mapping = json.load(f)

# Get all signals for Motor
motor_signals = component_mapping['Motor']
# ['EngCoolTemp', 'RAftrclrTemp', ...]
```

### Reading Machine Status

```python
df_status = pd.read_parquet(
    f'data/telemetry/golden/{client}/machine_status.parquet'
)

# Filter to Anormal units only
anormal_units = df_status[df_status['overall_status'] == 'Anormal']

# Sort by priority
priority_units = df_status.sort_values('priority_score', ascending=False)
```

### Reading Classified Components

```python
df_classified = pd.read_parquet(
    f'data/telemetry/golden/{client}/classified.parquet'
)

# Get Motor evaluations for specific unit
unit_motor = df_classified[
    (df_classified['unit'] == 'Unit_247') & 
    (df_classified['component'] == 'Motor')
].iloc[0]

# Access signal details
signal_details = unit_motor['signals_evaluation']
coolant_temp_grade = signal_details['EngCoolTemp']['grade']
```

---

**Document Status**: ✅ Approved (Version 2.0)  
**Last Updated**: February 18, 2026
