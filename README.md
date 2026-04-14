# Telemetry Dashboard - Pipeline

Multi-Technical Alerts Dashboard platform for processing sensor telemetry data from mining equipment.

## Overview

This repository implements the **Telemetry Analysis Pipeline** - a specialized component focused on processing sensor telemetry data using percentile-based anomaly detection and AI-powered maintenance insights.

### Key Features

✅ **Percentile-Based Anomaly Detection**: Statistical scoring using historical baselines (P1, P5, P95, P99)  
✅ **Hierarchical Evaluation**: Signal → Component → Machine health assessment  
✅ **AI-Powered Insights**: OpenAI-generated maintenance comments and health summaries  
✅ **Time-Series Analysis**: Weekly batch processing with historical tracking  
✅ **Golden Layer Outputs**: Structured parquet files for dashboard consumption  

## Quick Start

### Prerequisites

- Python 3.12+
- AWS credentials (for S3 data access)
- OpenAI API key (for AI maintenance comments)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd telemetry_dashboard

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY and AWS credentials
```

### Configuration

Create a `.env` file with the following variables:

```bash
# Required for AI-generated maintenance comments
OPENAI_API_KEY=sk-your-openai-api-key-here

# Required for S3 data access
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_DEFAULT_REGION=us-east-1
```

### Running the Pipeline

```python
# See notebooks/mvp_testing_v2.ipynb for complete example
from src.telemetry import data_loader, baseline, scoring, aggregation, output_writer

# 1. Load evaluation week
current_df = data_loader.load_evaluation_week(client='cda', week=8, year=2026)

# 2. Compute baseline percentiles
baseline_df = baseline.compute_baseline_percentiles(training_df, signal_cols)

# 3. Evaluate signals
signal_evaluation_df = scoring.evaluate_signals(current_df, baseline_df, signal_cols)

# 4. Aggregate to components (includes AI comments)
component_df = aggregation.aggregate_to_components(signal_evaluation_df, component_mapping, ...)

# 5. Aggregate to machines (includes AI summaries)
machine_df = aggregation.aggregate_to_machines(component_df, ...)

# 6. Write Golden layer outputs
output_writer.write_golden_outputs(machine_df, component_df, client)
```

## AI-Powered Maintenance Comments

The pipeline automatically generates expert maintenance insights using OpenAI API:

### Component-Level Comments

For components with anomalous conditions (Alerta or Anormal status):
- **What**: Describes the detected abnormal condition
- **Why**: Indicates possible root causes
- **Risk**: Explains operational risks if not addressed

**Example**:
```
Se detectó temperatura anormal del refrigerante del motor (EngCoolTemp) con 45.2% de lecturas 
fuera del rango histórico P1-P99. Esto puede indicar obstrucción en el sistema de enfriamiento, 
falla de termostato, o nivel bajo de refrigerante. Si no se atiende, existe riesgo de 
sobrecalentamiento del motor que puede causar daño severo a componentes internos.
```

### Machine-Level Summaries

Executive summary for overall equipment condition:
- General health assessment
- Critical affected components
- Operational risks
- Maintenance priority recommendation

**Example**:
```
El equipo presenta condición crítica con 3 componentes anormales detectados. El Motor muestra 
temperatura de refrigerante elevada y presión de aceite baja, la Transmisión registra temperatura 
de lubricante fuera de rango. Estos patrones indican alto riesgo de falla catastrófica si se 
mantiene operación sin intervención. Se recomienda inspección inmediata.
```

### Disabling AI Comments

If you don't have an OpenAI API key or want to disable AI comments:
- Remove or comment out `OPENAI_API_KEY` from `.env`
- Pipeline will continue to work normally
- AI comment columns will be `None`/`null` in output files
- Warnings logged but execution not blocked

## Project Structure

```
telemetry_dashboard/
├── data/
│   ├── telemetry/
│   │   ├── silver/          # Input: weekly telemetry data
│   │   └── golden/          # Output: evaluated health assessments
│   ├── mantentions/         # Maintenance records
│   └── oil/                 # Oil analysis data
├── src/
│   ├── telemetry/           # Core pipeline modules
│   │   ├── baseline.py      # Percentile baseline computation
│   │   ├── scoring.py       # Signal anomaly scoring
│   │   ├── aggregation.py   # Component/machine aggregation
│   │   └── output_writer.py # Golden layer writer
│   ├── services/
│   │   ├── ai_comment_service.py  # OpenAI integration
│   │   └── ...
│   └── utils/
├── notebooks/
│   ├── mvp_testing_v2.ipynb       # Pipeline testing
│   └── multi_week_validation.ipynb
├── documentation/
│   └── telemetry/
│       ├── project_overview.md        # Architecture & methodology
│       ├── telemetry_data_contracts.md # Schema specifications
│       └── ...
└── requirements.txt
```

## Documentation

- **[Project Overview](documentation/telemetry/project_overview.md)**: Architecture, methodology, and evaluation chain
- **[Data Contracts](documentation/telemetry/telemetry_data_contracts.md)**: Schema specifications and data quality rules
- **[Integration Plan](documentation/telemetry/integration_plan.md)**: Implementation roadmap
- **[Programming Rules](documentation/telemetry/programming_rules.md)**: Code standards

## Output Schemas

### machine_status.parquet
Machine-level health summary (one row per unit per week):
- Overall status classification
- Component status counts
- Priority score for fleet ranking
- **AI health summary** (executive overview)

### classified.parquet
Component-level evaluation detail (one row per unit-component-week):
- Component health status
- Triggering signals
- Signal evaluation details
- **AI maintenance recommendation** (technical insights)

## Cost Estimation

**AI Comment Generation** (using gpt-4o-mini):
- Fleet size: 50 units
- Components per unit: ~12
- API calls per week: ~600
- Estimated cost: **$1-2 USD/week**

For higher quality comments, use `gpt-4o` (2-3x cost increase).

## Version History

### Version 1.1.0 (April 2026)
- ✨ Added AI-powered maintenance comment generation
- ⚙️ Updated percentile thresholds (P1/P99 instead of P2/P98)
- 🔧 Stricter anomaly detection thresholds

### Version 1.0.0 (February 2026)
- 🎯 Initial telemetry analysis pipeline
- 📊 Percentile-based anomaly detection
- 🏗️ Hierarchical evaluation architecture

## License

[Add license information]

## Contact

[Add contact information]
