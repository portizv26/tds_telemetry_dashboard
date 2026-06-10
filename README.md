# Telemetry Health Evaluation Framework

Multi-technique analytical framework that transforms minute-level telemetry from mining equipment into explainable, confidence-scored health assessments.

## Overview

This framework processes raw telemetry signals from CAT 789C/D mining trucks and applies **five complementary analysis techniques** to detect equipment anomalies, degradation patterns, and operational issues. Results are aggregated into a fleet-level priority ranking with LLM-generated natural language explanations.

### Techniques

| Technique | Cadence | What It Detects |
|-----------|---------|-----------------|
| **Deviation Analysis** | Daily | Threshold violations per signal |
| **Event Analysis** | Daily | Persistent abnormal episodes |
| **Trend Analysis** | Weekly | Progressive degradation over 4–12 weeks |
| **Distribution Shift** | Weekly | Statistical changes in signal behavior |
| **LSTM Autoencoder** | 6-hourly | Multi-signal pattern anomalies |

### Hierarchy

```
Signal-Level (per technique) → System-Level (Engine, Brakes, etc.) → Unit-Level (fleet ranking)
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Dependencies: `pip install -r requirements.txt`
- `.env` file with `OPENAI_API_KEY` (for LLM explanations)

### Installation

```bash
git clone <repository-url>
cd telemetry_dashboard
pip install -r requirements.txt
```

### Create `.env` File

```env
OPENAI_API_KEY=sk-your-key-here
```

### Run the Pipeline

```bash
# Full pipeline (all techniques + LLM)
python -m src.main --client cda

# Process specific weeks only
python -m src.main --client cda --weeks Week22Year2026 Week23Year2026

# Fast mode: skip autoencoder training and LLM calls
python -m src.main --client cda --skip-autoencoder --skip-llm

# Debug mode
python -m src.main --client cda --log-level DEBUG
```

### Output

Results are written to `data/telemetry/golden/{client}/` as partitioned Parquet files:
- `technique_results/` — Per-technique detailed results
- `system_health/` — System-level aggregated assessments
- `unit_health/` — Fleet-level priority ranking

A JSON summary is also written to the working directory after each run.

---

## Project Structure

```
telemetry_dashboard/
├── src/                          # Production pipeline code
│   ├── main.py                   # CLI entry point
│   ├── pipeline.py               # Orchestrator (coordinates all phases)
│   ├── config/
│   │   └── settings.py           # Configuration dataclasses + loading
│   ├── techniques/
│   │   ├── deviation.py          # Threshold-based risk classification
│   │   ├── events.py             # Temporal pattern detection
│   │   ├── trend.py              # Linear regression trend analysis
│   │   ├── distribution.py       # Mann-Whitney U distribution shifts
│   │   ├── autoencoder.py        # LSTM autoencoder anomaly detection
│   │   ├── aggregation.py        # Signal → System → Unit health
│   │   └── llm_explain.py        # OpenAI natural language explanations
│   └── utils/
│       └── data_utils.py         # Shared loading, preprocessing, scoring
├── data/
│   └── telemetry/
│       ├── config/{client}/      # YAML configuration files
│       ├── silver/{client}/      # Input: cleaned telemetry (parquet)
│       └── golden/{client}/      # Output: analytical results (parquet)
├── documentation/
│   └── telemetry/
│       ├── telemetry_processing_documentation.md  # Full technical docs
│       ├── data_contracts.md     # Schema specifications
│       └── programming_rules.md  # Engineering standards
├── notebooks/                    # Research & exploration notebooks
├── requirements.txt
└── README.md
```

---

## Configuration

### Signal Registry (`data/telemetry/config/{client}/signal_registry.yaml`)

Defines each telemetry signal's properties:
- `system` — Grouping (Engine, Transmission, Brakes, Steering)
- `risk_direction` — Which direction is dangerous (`high`, `low`, `both`)
- `threshold_compute` — Whether to include in deviation analysis
- `criticality` — Importance weight (1=safety-critical, 3=monitoring)

### Equipment Registry (`data/telemetry/config/{client}/equipment_registry.yaml`)

Maps unit identifiers (T_09, T_15, etc.) to equipment models and hardware variants.

### Analysis Config (optional)

Override default parameters by creating `data/telemetry/config/{client}/analysis_config.yaml`. See [data_contracts.md](documentation/telemetry/data_contracts.md) for full schema.

---

## Data Requirements

### Input (Silver Layer)

Weekly parquet files at `data/telemetry/silver/{client}/Telemetry_Wide_With_States/`:

| Column | Type | Description |
|--------|------|-------------|
| `Unit` | string | Equipment ID (e.g., "T_09") |
| `Fecha` | datetime | Timestamp (1-minute resolution) |
| `Estado` | string | Operational state |
| Signal columns | float64 | Telemetry readings |

**Minimum data**: ≥12 weeks for reliable baselines, ≥90 days recommended.

### Output (Golden Layer)

Partitioned Parquet files at `data/telemetry/golden/{client}/`:
- Technique results partitioned by `year/week`
- System/Unit health with LLM explanations
- Trained autoencoder models with metadata

---

## Usage Examples

### Programmatic Usage

```python
from src.pipeline import TelemetryPipeline

# Initialize and run
pipeline = TelemetryPipeline(client="cda")
summary = pipeline.run(skip_autoencoder=True, skip_llm=True)

# Access results
print(f"Units processed: {summary['units_processed']}")
print(f"Anormal units: {summary['units_anormal']}")

# Access DataFrames directly
print(pipeline.unit_health[['unit', 'overall_status', 'priority_score']])
print(pipeline.system_health[['unit', 'system', 'system_status', 'system_score']])
```

### Process Specific Weeks

```python
pipeline = TelemetryPipeline(
    client="cda",
    weeks=["Week20Year2026", "Week21Year2026", "Week22Year2026"]
)
summary = pipeline.run()
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [Technical Documentation](documentation/telemetry/telemetry_processing_documentation.md) | Full methodology, formulas, and architecture |
| [Data Contracts](documentation/telemetry/data_contracts.md) | Schema specifications for all data files |
| [Programming Rules](documentation/telemetry/programming_rules.md) | Engineering standards and conventions |

---

## Key Dependencies

- **pandas / numpy / pyarrow** — Data processing
- **scipy / scikit-learn** — Statistical analysis and ML
- **tensorflow** — LSTM autoencoder (optional, can skip)
- **openai** — LLM explanations (optional, requires API key)
- **pyyaml / python-dotenv** — Configuration

---

## License

Internal project — Coddi / Patricio Ortiz.
