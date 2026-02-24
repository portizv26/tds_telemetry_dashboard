# Telemetry Analysis - Programming Rules

**Version**: 1.0.0  
**Last Updated**: February 23, 2026  
**Component**: Engineering Standards & Conventions

---

## 📋 Table of Contents

1. [Core Principles](#core-principles)
2. [Naming Conventions](#naming-conventions)
3. [Directory Structure](#directory-structure)
4. [Code Standards](#code-standards)
5. [Schema Contracts](#schema-contracts)
6. [Error Handling](#error-handling)
7. [Logging Standards](#logging-standards)
8. [Dependencies & Stack](#dependencies--stack)
9. [Performance Guidelines](#performance-guidelines)

---

## 🎯 Core Principles

### 1. Determinism

**Rule**: Same inputs → same outputs, always.

**Requirements**:
- No random number generation without fixed seeds
- Avoid non-deterministic operations (e.g., dictionary iteration in Python <3.7)
- Sort dataframes consistently before processing
- Use explicit datetime handling (no `datetime.now()` for calculation logic)

**Example**:
```python
# ❌ BAD: Non-deterministic
df = df.sample(frac=1.0)  # Random shuffle without seed

# ✅ GOOD: Deterministic
df = df.sample(frac=1.0, random_state=42)
df = df.sort_values(['Unit', 'Fecha']).reset_index(drop=True)
```

---

### 2. Reproducibility

**Rule**: Pipeline runs must be reproducible weeks/months later.

**Requirements**:
- Version all inputs (baseline files, mappings)
- Store baseline version ID with outputs
- Log parameter values used in each run
- Pin dependency versions in `requirements.txt`

**Traceability Chain**:
```
Output File (machine_status.parquet)
  ├─ baseline_version: "20260201"
  ├─ evaluation_week: 8
  ├─ evaluation_year: 2026
  └─ Traceable to:
      ├─ Input: data/telemetry/silver/cda/Telemetry_Wide_With_States/Week08Year2026.parquet
      ├─ Baseline: data/telemetry/golden/cda/baselines/baseline_20260201.parquet
      └─ Mapping: data/telemetry/component_signals_mapping.json
```

---

### 3. Idempotency

**Rule**: Running the pipeline N times produces the same result as running once.

**Requirements**:
- Overwrite outputs (don't append)
- Use `mode='w'` for file writes
- Clear intermediate state before processing
- Avoid cumulative calculations across runs

**Example**:
```python
# ✅ GOOD: Idempotent write
df.to_parquet('output.parquet', index=False)  # Overwrites existing

# ❌ BAD: Non-idempotent append
df.to_parquet('output.parquet', index=False, append=True)  # Grows over time
```

---

### 4. Explicit Schema Contracts

**Rule**: Define and validate schemas for all inputs and outputs.

**Requirements**:
- Document expected columns, types, and constraints
- Validate schema on data load
- Fail fast if schema violations detected
- Version schemas alongside data

**Schema Validation Pattern**:
```python
from typing import List, Dict

def validate_schema(df: pd.DataFrame, expected_schema: Dict[str, type]) -> None:
    """
    Validate DataFrame schema against expected types.
    
    Args:
        df: DataFrame to validate
        expected_schema: Dict of {column_name: expected_type}
    
    Raises:
        ValueError: If schema validation fails
    """
    missing_cols = set(expected_schema.keys()) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    for col, expected_type in expected_schema.items():
        actual_type = df[col].dtype
        if not pd.api.types.is_dtype_equal(actual_type, expected_type):
            logger.warning(
                f"Column '{col}' type mismatch: expected {expected_type}, "
                f"got {actual_type}"
            )

# Usage
TELEMETRY_SCHEMA = {
    'Fecha': 'datetime64[ns]',
    'Unit': 'object',
    'EstadoMaquina': 'object',
    'EngCoolTemp': 'float64',
    # ... more columns
}

df = pd.read_parquet('input.parquet')
validate_schema(df, TELEMETRY_SCHEMA)
```

---

### 5. Fail-Safe Processing

**Rule**: Partial failures should not corrupt outputs or block other units.

**Requirements**:
- Process units independently
- Catch exceptions at unit level, log, and continue
- Generate partial outputs if some units succeed
- Provide summary of failures at end

**Pattern**:
```python
results = []
failures = []

for unit in df['Unit'].unique():
    try:
        result = process_unit(unit, df[df['Unit'] == unit])
        results.append(result)
    except Exception as e:
        logger.error(f"Failed to process unit {unit}: {e}", exc_info=True)
        failures.append({'unit': unit, 'error': str(e)})

# Write results even if some failed
if results:
    pd.DataFrame(results).to_parquet('output.parquet')

# Report failures
if failures:
    pd.DataFrame(failures).to_csv('failures.csv')
    logger.warning(f"Processing completed with {len(failures)} failures")
```

---

## 📝 Naming Conventions

### File Names

**Pattern**: `{purpose}_{scope}.{extension}`

| Type | Pattern | Example |
|------|---------|---------|
| Parquet data | `{entity}_{layer}.parquet` | `machine_status.parquet` |
| CSV reports | `{report_name}_{date}.csv` | `failures_20260223.csv` |
| Baseline files | `baseline_{YYYYMMDD}.parquet` | `baseline_20260201.parquet` |
| Log files | `{pipeline}_{YYYYMMDD}.log` | `telemetry_pipeline_20260223.log` |
| Config files | `{purpose}_config.json` | `component_signals_mapping.json` |

---

### Variable Names

**General Rules**:
- Use `snake_case` for variables and functions
- Use `SCREAMING_SNAKE_CASE` for constants
- Use descriptive names (avoid abbreviations unless standard)
- Prefix boolean variables with `is_`, `has_`, `should_`

**Examples**:
```python
# ✅ GOOD
current_evaluation_df = load_data(week, year)
baseline_percentiles = compute_baseline(training_df)
is_baseline_valid = validate_baseline(baseline_df)
WINDOW_SCORE_THRESHOLD_ALERT = 0.2

# ❌ BAD
df1 = load_data(week, year)  # Unclear name
bp = compute_baseline(training_df)  # Abbreviation
valid = validate_baseline(baseline_df)  # Missing prefix
t1 = 0.2  # Unclear constant
```

---

### Function Names

**Pattern**: `{verb}_{noun}` or `{verb}_{noun}_{context}`

| Pattern | Example | Purpose |
|---------|---------|---------|
| `load_*` | `load_evaluation_week()` | Data loading |
| `compute_*` | `compute_baseline_percentiles()` | Calculations |
| `validate_*` | `validate_schema()` | Validation checks |
| `aggregate_*` | `aggregate_to_components()` | Aggregation logic |
| `write_*` | `write_golden_outputs()` | Output generation |
| `clean_*` | `clean_telemetry_data()` | Data cleaning |
| `evaluate_*` | `evaluate_signals()` | Assessment/scoring |

---

### Column Names

**General Rules**:
- Use `snake_case` for new columns
- Preserve original column names from source systems (even if not snake_case)
- Use descriptive suffixes for derived columns

**Standard Suffixes**:
- `_id`: Identifiers (`unit_id`, `client_id`)
- `_date`, `_timestamp`: Temporal values (`evaluation_date`, `latest_sample_date`)
- `_score`: Numeric scores (`machine_score`, `component_score`)
- `_status`: Categorical status (`overall_status`, `signal_status`)
- `_count`: Counts (`sample_count`, `components_normal`)
- `_pct`, `_percentage`: Percentages (`anomaly_pct`)

---

## 📁 Directory Structure

### Required Structure

```
telemetry_dashboard/
├── data/
│   └── telemetry/
│       ├── silver/
│       │   └── {client}/
│       │       └── Telemetry_Wide_With_States/
│       │           └── Week{WW}Year{YYYY}.parquet
│       └── golden/
│           └── {client}/
│               ├── machine_status.parquet
│               ├── classified.parquet
│               └── baselines/
│                   ├── baseline_{YYYYMMDD}.parquet
│                   ├── baseline_metadata.json
│                   └── archive/
│                       └── baseline_{YYYYMMDD}.parquet.old
├── src/
│   └── telemetry/
│       ├── __init__.py
│       ├── pipeline.py           # Main orchestration
│       ├── data_loader.py        # Data reading functions
│       ├── data_cleaner.py       # Cleaning & validation
│       ├── baseline.py           # Baseline computation
│       ├── scoring.py            # Signal evaluation
│       ├── aggregation.py        # Component/machine aggregation
│       ├── output_writer.py      # Golden layer writing
│       └── utils.py              # Helper functions
├── models/
│   └── autoencoders/
│       └── {client}/
│           └── {component}_lstm_ae.h5
├── notebooks/
│   └── telemetry_validation.ipynb   # User testing notebook
├── logs/
│   └── telemetry_pipeline_{YYYYMMDD}.log
├── config/
│   ├── component_signals_mapping.json
│   └── pipeline_config.yaml
├── requirements.txt
├── README.md
└── main.py                       # Entry point
```

---

### Path Construction Rules

**Always use `pathlib` for path manipulation**:

```python
from pathlib import Path

# ✅ GOOD: Cross-platform, readable
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data' / 'telemetry'
SILVER_DIR = DATA_DIR / 'silver' / client / 'Telemetry_Wide_With_States'
input_file = SILVER_DIR / f'Week{week:02d}Year{year}.parquet'

# ❌ BAD: String concatenation, platform-specific
input_file = f'data/telemetry/silver/{client}/Telemetry_Wide_With_States/Week{week:02d}Year{year}.parquet'
```

**Directory Creation**:
```python
# Always ensure directories exist before writing
output_dir = DATA_DIR / 'golden' / client
output_dir.mkdir(parents=True, exist_ok=True)
```

---

## 💻 Code Standards

### General Style

**Follow PEP 8**:
- Line length: 100 characters (not 79)
- 4-space indentation
- Blank lines: 2 before top-level functions/classes, 1 between methods

**Type Hints**:
```python
from typing import List, Dict, Optional, Tuple
import pandas as pd

def evaluate_signals(
    current_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    component_mapping: Dict[str, Dict]
) -> pd.DataFrame:
    """
    Evaluate signals against baseline percentiles.
    
    Args:
        current_df: Current evaluation week data
        baseline_df: Historical baseline percentiles
        component_mapping: Component-to-signals mapping
    
    Returns:
        DataFrame with signal evaluations
    """
    pass
```

---

### Docstring Standard

**Use NumPy-style docstrings**:

```python
def compute_window_score(
    readings: np.ndarray,
    baseline: Dict[str, float]
) -> Tuple[float, str]:
    """
    Compute severity-weighted window score for a signal.
    
    Parameters
    ----------
    readings : np.ndarray
        Array of sensor readings in evaluation window
    baseline : dict
        Baseline percentiles with keys: 'p2', 'p5', 'p95', 'p98'
    
    Returns
    -------
    window_score : float
        Normalized anomaly score (0 = all normal, 3 = all alarm)
    status : str
        Classification: 'Normal', 'Alerta', or 'Anormal'
    
    Notes
    -----
    Implements Severity-Weighted Percentile Window Scoring:
    - Score 0: Reading in [P5, P95]
    - Score 1: Reading in [P2, P5) or (P95, P98]
    - Score 3: Reading < P2 or > P98
    
    Examples
    --------
    >>> readings = np.array([85, 90, 95, 92, 88])
    >>> baseline = {'p2': 70, 'p5': 75, 'p95': 95, 'p98': 100}
    >>> score, status = compute_window_score(readings, baseline)
    >>> print(f"Score: {score:.2f}, Status: {status}")
    Score: 0.20, Status: Alerta
    """
    pass
```

---

### Pandas Best Practices

#### Use Vectorized Operations (Avoid Loops)

```python
# ❌ BAD: Row-by-row iteration
for idx, row in df.iterrows():
    df.at[idx, 'score'] = calculate_score(row['value'], row['baseline'])

# ✅ GOOD: Vectorized operation
df['score'] = df.apply(
    lambda row: calculate_score(row['value'], row['baseline']),
    axis=1
)

# ✅ BETTER: Pure vectorized (no apply)
def vectorized_score(values: pd.Series, baselines: pd.DataFrame) -> pd.Series:
    scores = pd.Series(0, index=values.index)
    scores[(values < baselines['p5']) | (values > baselines['p95'])] = 1
    scores[(values < baselines['p2']) | (values > baselines['p98'])] = 3
    return scores

df['score'] = vectorized_score(df['value'], baseline_df)
```

#### Query Filtering

```python
# ✅ GOOD: Use query() for readable filters
df_filtered = df.query('EstadoMaquina == "Operacional" and EngCoolTemp > 90')

# ✅ ALSO GOOD: Boolean indexing
df_filtered = df[(df['EstadoMaquina'] == 'Operacional') & (df['EngCoolTemp'] > 90)]
```

#### Efficient Groupby

```python
# Compute multiple aggregations in one pass
summary = df.groupby(['Unit', 'Component']).agg({
    'signal_score': ['max', 'mean', 'count'],
    'signal_status': lambda x: (x != 'Normal').sum()  # Count non-normal
})
```

---

### Code Organization

**Module-Level Constants**:
```python
# At top of file, after imports
# Baseline configuration
BASELINE_LOOKBACK_DAYS = 90
MIN_SAMPLES_FOR_BASELINE = 100
PERCENTILES = [0.02, 0.05, 0.95, 0.98]

# Signal scoring thresholds
WINDOW_SCORE_THRESHOLD_ALERT = 0.2
WINDOW_SCORE_THRESHOLD_ANORMAL = 0.4

# Component scoring
SEVERITY_MAP = {
    'Normal': 0.0,
    'Alerta': 0.3,
    'Anormal': 1.0
}
COMPONENT_SCORE_THRESHOLD_NORMAL = 0.15
COMPONENT_SCORE_THRESHOLD_ANORMAL = 0.45
MIN_SIGNAL_COVERAGE = 0.5  # Minimum fraction of signals with valid data
```

**Function Length**:
- Target: <50 lines per function
- If longer, break into helper functions
- Use descriptive helper names

**Import Organization**:
```python
# Standard library
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional

# Third-party
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# Local modules
from src.telemetry import data_loader, scoring
from src.utils import logger, date_utils
```

---

## 📐 Schema Contracts

### Silver Layer Input Schema

**File**: `data/telemetry/silver/{client}/Telemetry_Wide_With_States/Week{WW}Year{YYYY}.parquet`

```python
SILVER_SCHEMA = {
    # Required columns
    'Fecha': 'datetime64[ns]',
    'Unit': 'object',  # string
    'EstadoMaquina': 'object',  # 'Operacional', 'Ralenti', 'Apagada', 'Unknown'
    
    # Optional GPS columns
    'GPSLat': 'float64',
    'GPSLon': 'float64',
    'GPSElevation': 'float64',
    
    # Signal columns (examples - actual list varies)
    'EngCoolTemp': 'float64',
    'EngOilPres': 'float64',
    'EngSpeed': 'float64',
    # ... more signals
}
```

**Constraints**:
- `Fecha`: Must be within evaluation week's date range
- `Unit`: No nulls allowed
- `EstadoMaquina`: Must be one of valid states
- Signal columns: Can contain NaN (handled by cleaning)

---

### Golden Layer Output Schemas

#### `machine_status.parquet`

```python
MACHINE_STATUS_SCHEMA = {
    'unit_id': 'object',                    # Unit identifier
    'client': 'object',                     # Client identifier
    'evaluation_week': 'int64',             # Week number (1-52)
    'evaluation_year': 'int64',             # Year (YYYY)
    'latest_sample_date': 'datetime64[ns]', # Most recent timestamp
    'overall_status': 'object',             # 'Normal', 'Alerta', 'Anormal'
    'machine_score': 'float64',             # Aggregate severity score
    'total_components': 'int64',            # Number of components evaluated
    'components_normal': 'int64',           # Count with Normal status
    'components_alerta': 'int64',           # Count with Alerta status
    'components_anormal': 'int64',          # Count with Anormal status
    'priority_score': 'float64',            # Fleet ranking score
    'component_details': 'object',          # JSON: list of component dicts
    'baseline_version': 'object'            # Baseline file ID (YYYYMMDD)
}
```

**Constraints**:
- `overall_status`: Must be one of ['Normal', 'Alerta', 'Anormal']
- `components_normal + components_alerta + components_anormal = total_components`
- `component_details`: Must be valid JSON list

---

#### `classified.parquet`

```python
CLASSIFIED_SCHEMA = {
    'unit': 'object',                       # Unit identifier
    'client': 'object',                     # Client identifier
    'evaluation_week': 'int64',             # Week number
    'evaluation_year': 'int64',             # Year
    'date': 'datetime64[ns]',               # Evaluation timestamp
    'component': 'object',                  # Component name
    'component_status': 'object',           # 'Normal', 'Alerta', 'Anormal', 'InsufficientData'
    'component_score': 'float64',           # Weighted severity score (0.0-1.0)
    'component_coverage': 'float64',        # Fraction of signals with valid data
    'signals_evaluation': 'object',         # JSON: dict of signal details
    'triggering_signals': 'object',         # JSON: list of signal names
    'signal_weights': 'object',             # JSON: dict of signal weights
    'ai_recommendation': 'object',          # LLM text (nullable in Phase 1)
    'baseline_version': 'object',           # Baseline file ID
    'criticality': 'int64'                  # Component criticality weight
}
```

---

### Baseline Schema

**File**: `baseline_{YYYYMMDD}.parquet`

```python
BASELINE_SCHEMA = {
    'unit_id': 'object',
    'signal': 'object',
    'state': 'object',                  # 'Operacional', 'Ralenti', 'Apagada'
    'p2': 'float64',                    # 2nd percentile
    'p5': 'float64',                    # 5th percentile
    'p95': 'float64',                   # 95th percentile
    'p98': 'float64',                   # 98th percentile
    'sample_count': 'int64',            # Number of samples used
    'training_start': 'datetime64[ns]', # Training window start
    'training_end': 'datetime64[ns]'    # Training window end
}
```

---

## 🚨 Error Handling

### Exception Hierarchy

```python
# Custom exceptions in src/telemetry/exceptions.py

class TelemetryPipelineError(Exception):
    """Base exception for telemetry pipeline."""
    pass

class DataLoadError(TelemetryPipelineError):
    """Raised when data loading fails."""
    pass

class SchemaValidationError(TelemetryPipelineError):
    """Raised when schema validation fails."""
    pass

class BaselineComputationError(TelemetryPipelineError):
    """Raised when baseline computation fails."""
    pass

class InsufficientDataError(TelemetryPipelineError):
    """Raised when not enough data for processing."""
    pass
```

---

### Error Handling Patterns

#### Pattern 1: Fail Fast (Critical Errors)

```python
def load_evaluation_week(client: str, week: int, year: int) -> pd.DataFrame:
    """Load data, fail fast if file missing."""
    file_path = get_silver_path(client, week, year)
    
    if not file_path.exists():
        raise DataLoadError(
            f"Evaluation data not found: {file_path}. "
            f"Ensure Silver layer data exists for Week {week}/{year}."
        )
    
    try:
        df = pd.read_parquet(file_path)
    except Exception as e:
        raise DataLoadError(f"Failed to read parquet file: {e}") from e
    
    return df
```

#### Pattern 2: Graceful Degradation (Non-Critical)

```python
def compute_state_baseline(
    data: pd.DataFrame,
    state: str,
    min_samples: int = 100
) -> Optional[Dict[str, float]]:
    """Compute baseline, return None if insufficient data."""
    state_data = data[data['EstadoMaquina'] == state]
    
    if len(state_data) < min_samples:
        logger.warning(
            f"Insufficient data for state '{state}': {len(state_data)} samples "
            f"(minimum: {min_samples}). Skipping state-specific baseline."
        )
        return None
    
    return {
        'p2': state_data.quantile(0.02),
        'p5': state_data.quantile(0.05),
        'p95': state_data.quantile(0.95),
        'p98': state_data.quantile(0.98)
    }
```

#### Pattern 3: Retry with Exponential Backoff (External Services)

```python
import time
from functools import wraps

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying functions with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay
            
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        raise
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
        
        return wrapper
    return decorator

@retry(max_attempts=3, delay=2.0)
def generate_llm_recommendation(component_data: dict) -> str:
    """Generate AI recommendation, retry on API failures."""
    return openai.ChatCompletion.create(...)
```

---

## 📊 Logging Standards

### Logger Configuration

```python
# src/utils/logger.py
import logging
from pathlib import Path
from datetime import datetime

def setup_logger(name: str, log_dir: Path = Path('logs')) -> logging.Logger:
    """
    Configure structured logger for pipeline.
    
    Args:
        name: Logger name (usually module name)
        log_dir: Directory for log files
    
    Returns:
        Configured logger instance
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # File handler (daily rotation)
    log_file = log_dir / f"telemetry_pipeline_{datetime.now():%Y%m%d}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
```

---

### Logging Levels

| Level | When to Use | Example |
|-------|-------------|---------|
| `DEBUG` | Detailed diagnostic info (verbose) | Variable values, loop iterations |
| `INFO` | High-level progress tracking | "Step 1 complete", "Processed 120 units" |
| `WARNING` | Unexpected but handled situations | Missing optional data, fallback used |
| `ERROR` | Errors that don't stop pipeline | Unit processing failed, continuing |
| `CRITICAL` | Errors that stop pipeline | Data file missing, schema invalid |

---

### Logging Best Practices

```python
logger = setup_logger(__name__)

def process_unit(unit: str, data: pd.DataFrame) -> dict:
    """Process a single unit."""
    logger.info(f"Processing unit: {unit}")
    
    # Log progress
    logger.debug(f"Unit {unit}: {len(data)} samples loaded")
    
    # Log warnings
    missing_pct = data['EngCoolTemp'].isnull().mean()
    if missing_pct > 0.1:
        logger.warning(
            f"Unit {unit}: High missingness in EngCoolTemp ({missing_pct*100:.1f}%)"
        )
    
    # Log errors with context
    try:
        result = evaluate_signals(data)
    except Exception as e:
        logger.error(
            f"Unit {unit}: Signal evaluation failed: {e}",
            exc_info=True  # Include traceback
        )
        raise
    
    logger.info(f"Unit {unit}: Processing complete (status: {result['status']})")
    return result
```

---

### Structured Logging for Monitoring

```python
import json

def log_pipeline_metrics(
    client: str,
    week: int,
    year: int,
    metrics: dict
) -> None:
    """Log structured metrics for monitoring dashboard."""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'client': client,
        'week': week,
        'year': year,
        'metrics': metrics
    }
    
    # Write to structured log file (JSON Lines)
    metrics_log = Path('logs') / 'pipeline_metrics.jsonl'
    with open(metrics_log, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
    
    logger.info(f"Pipeline metrics: {json.dumps(metrics, indent=2)}")

# Usage
metrics = {
    'units_processed': 120,
    'units_failed': 3,
    'execution_time_seconds': 245,
    'output_size_mb': 12.5,
    'baseline_age_days': 14
}
log_pipeline_metrics('cda', 8, 2026, metrics)
```

---

## 📦 Dependencies & Stack

### Required Dependencies

**File**: `requirements.txt`

```
# Core data processing
pandas==2.1.4
numpy==1.26.2
pyarrow==14.0.1

# Visualization
plotly==5.18.0
dash==2.14.2
dash-bootstrap-components==1.5.0

# File I/O
openpyxl==3.1.2  # For Excel exports

# Statistics
scipy==1.11.4

# Date/time utilities
python-dateutil==2.8.2

# Logging
colorlog==6.8.0  # Optional: colored console logs


# Type checking (development)
mypy==1.7.1

# Phase 2 dependencies (optional)
openai==1.6.1  # LLM integration
tensorflow==2.15.0  # LSTM autoencoder
prophet==1.1.5  # Time series forecasting
scikit-learn==1.3.2  # Data preprocessing
```

---

### Technology Constraints

**Pandas-First Approach**:
- Use pandas for all data manipulation
- Avoid PySpark unless dataset exceeds 10GB
- Prefer pandas vectorized operations over explicit loops

**No SQL Database Required**:
- Store data in Parquet files (columnar format)
- Use filesystem as data lake
- No runtime database dependencies

**Minimal External Services**:
- Phase 1: No external API calls
- Phase 2: OpenAI API only (optional)
- No cloud storage dependencies (local filesystem)

---

## ⚡ Performance Guidelines

### Memory Management

```python
# Read only needed columns
df = pd.read_parquet('data.parquet', columns=['Unit', 'Fecha', 'EngCoolTemp'])

# Process in chunks for large datasets
for chunk in pd.read_parquet('large_file.parquet', chunksize=10000):
    process_chunk(chunk)

# Clear memory after large operations
del large_df
import gc
gc.collect()
```

---

### Optimization Targets

| Operation | Target |
|-----------|--------|
| Data loading (1 week) | <10 seconds |
| Baseline computation | <30 seconds |
| Signal evaluation (100 units) | <60 seconds |
| Component aggregation | <5 seconds |
| Output writing | <10 seconds |
| **Total pipeline runtime** | **<5 minutes** |

---

### Profiling

```python
import cProfile
import pstats

def profile_pipeline():
    """Profile pipeline performance."""
    profiler = cProfile.Profile()
    profiler.enable()
    
    run_telemetry_pipeline('cda', 8, 2026)
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Top 20 slowest functions
```

---

## 📚 Additional Resources

- [Pandas Performance Tips](https://pandas.pydata.org/pandas-docs/stable/user_guide/enhancingperf.html)
- [PEP 8 Style Guide](https://peps.python.org/pep-0008/)
- [Type Hints (PEP 484)](https://peps.python.org/pep-0484/)

---

## 📝 Version History

### Version 1.0.0 (February 2026)
- Initial programming rules and standards
- Core principles and conventions defined
- Performance guidelines established

