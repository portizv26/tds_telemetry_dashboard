# Health Index Module - User Guide

## Overview

The `health_index` module is a production-ready Python package for telemetry-based health index modeling using LSTM autoencoders. It provides a modular, scalable pipeline for training models across multiple equipment components and generating health predictions over long time horizons.

## Architecture

The module is organized into the following components:

```
src/health_index/
├── __init__.py              # Package initialization
├── config.py                # Configuration and constants
├── io.py                    # Data loading and saving
├── preprocessing.py         # Outlier cleaning
├── cycles.py                # Cycle detection and interpolation
├── labeling.py              # Percentile-based labeling
├── scaling.py               # Per-unit scaling and encoding
├── windowing.py             # Sequence window creation
├── modeling.py              # LSTM autoencoder architecture
├── optimization.py          # Optuna hyperparameter optimization
├── training.py              # Model training with MLflow
├── inference.py             # Single and multi-window inference
├── health_index.py          # Health index computation
├── artifacts.py             # Artifact persistence
└── pipeline.py              # Pipeline orchestration
```

## Quick Start

### Command Line Usage

Run the full pipeline for all components:

```bash
python scripts/train_and_infer_health_index.py --client cda --run-optimization
```

Run for a specific component without optimization:

```bash
python scripts/train_and_infer_health_index.py --client cda --component Motor --no-optimization
```

Disable MLflow tracking:

```bash
python scripts/train_and_infer_health_index.py --client cda --no-mlflow
```

### Command Line Options

- `--client`: Client name (default: 'cda')
- `--component`: Specific component to process (if omitted, processes all)
- `--run-optimization`: Enable Optuna hyperparameter optimization
- `--no-optimization`: Skip optimization and use default hyperparameters
- `--use-mlflow`: Enable MLflow tracking (default: True)
- `--no-mlflow`: Disable MLflow tracking
- `--test-weeks`: Number of weeks for test set (default: 6)

## Programmatic Usage

### Single Component Pipeline

```python
from health_index import io, pipeline

# Load component mapping
component_mapping = io.load_component_mapping()

# Get signals for a specific component
component_info = component_mapping['components']['Motor']
signal_cols = component_info['signals']

# Run pipeline
result = pipeline.run_component_pipeline(
    client='cda',
    component='Motor',
    signal_cols=signal_cols,
    run_optimization=True,
    use_mlflow=True,
)

print(result)
```

### All Components Pipeline

```python
from health_index import io, pipeline

# Load mapping
component_mapping = io.load_component_mapping()

# Run all components
results = pipeline.run_all_components_pipeline(
    client='cda',
    component_mapping=component_mapping,
    run_optimization=True,
    use_mlflow=True,
)

for result in results:
    print(f"{result['component']}: {result['status']}")
```

### Custom Pipeline Steps

For more control, you can use individual modules:

```python
from health_index import (
    io, preprocessing, cycles, labeling, 
    scaling, windowing, modeling, training, inference, health_index
)

# 1. Load data
df = io.load_telemetry_data('cda')

# 2. Clean outliers
df = preprocessing.clean_outliers(df)

# 3. Detect and process cycles
df = cycles.detect_cycles(df)
df = cycles.process_cycles(df, signal_cols)

# 4. Create labels
df = labeling.create_labels(df, signal_cols)

# 5. Scale features
scalers = scaling.fit_scalers_per_unit(df, signal_cols)
df_scaled = scaling.apply_scalers_per_unit(df, signal_cols, scalers)

# 6. Create windows
X, meta = windowing.create_windows(df_scaled, feature_cols, window_size=60)

# 7. Build and train model
model = modeling.build_lstm_autoencoder(window_size=60, n_features=len(feature_cols))
# ... training code ...

# 8. Run inference
inference_results = inference.predict_over_horizon(
    df_test, model, feature_cols, window_size=60
)

# 9. Compute health index
hi_df = health_index.compute_health_index_from_inference(inference_results)
```

## Pipeline Workflow

### 1. Data Loading
- Loads telemetry data from parquet files
- Sorts and deduplicates by Unit and Fecha

### 2. Train/Test Split
- Splits data by time
- Test set = last N weeks (configurable, default: 6)

### 3. Preprocessing
- Replaces outliers with NaN based on predefined margins
- Fills missing categorical values

### 4. Cycle Detection
- Detects operating cycles based on time gaps
- Filters valid cycles (duration and coverage thresholds)

### 5. Cycle Interpolation
- Builds complete 1-minute time index per cycle
- Interpolates missing numeric values
- Forward-fills categorical values

### 6. Labeling
- Computes percentile thresholds (P5-P95) per signal
- Flags out-of-range values
- Labels cycles as Normal or Anomalous

### 7. Feature Preparation
- Fits RobustScaler **per unit** for numeric features
- Fits OneHotEncoder for categorical features
- Applies transformations to train and test data

### 8. Hyperparameter Optimization (Optional)
- Uses Optuna with TPE sampler
- Searches over window size, LSTM units, dropout, learning rate, batch size
- Saves results as JSON (not SQLite)

### 9. Window Creation
- Creates sliding windows for LSTM input
- Maintains temporal continuity within cycles
- Excludes synthetic/imputed data points

### 10. Model Training
- Trains LSTM autoencoder on normal behavior
- Uses early stopping on validation loss
- Tracks experiments with MLflow (optional)

### 11. Multi-Window Inference
- Slides window over full test set
- Generates reconstruction for each window
- Computes reconstruction errors

### 12. Health Index Computation
- Normalizes reconstruction errors
- Computes health index: HI = 100 * exp(-alpha * normalized_error)
- Categorizes into health statuses (Excellent, Good, Fair, Poor, Critical)

## Output Files

The pipeline generates the following outputs:

### Silver Layer (Processed Data)
```
data/telemetry/silver/{client}/processed_data.parquet
```

### Golden Layer (Results)
```
data/telemetry/golden/{client}/inferences.parquet
data/telemetry/golden/{client}/health_index.parquet
```

### Models and Artifacts
```
models/{client}/{component}/
├── model.keras                    # Trained model
├── scalers.pkl                    # Per-unit scalers
├── encoder.pkl                    # Categorical encoder
├── feature_cols.json              # Feature list
├── hyperparams.json               # Final hyperparameters
├── optimization_results.json      # Optuna results
├── training_history.json          # Training metrics
└── metadata.json                  # Pipeline metadata
```

### MLflow Logs
```
logs/mlflow/                       # Experiment tracking
logs/mlflow_artifacts/             # MLflow artifacts
```

## Configuration

All configuration is centralized in `config.py`:

- **Paths**: Data, models, logs directories
- **Preprocessing**: Outlier margins, cycle thresholds, interpolation limits
- **Labeling**: Percentile thresholds, anomaly ratios
- **Model**: Default hyperparameters, architecture settings
- **Optuna**: Search space, number of trials, sampler
- **MLflow**: Tracking URI, artifact location
- **Health Index**: Alpha parameter, aggregation method

To customize, edit `src/health_index/config.py` or override parameters when calling functions.

## Key Features

### Per-Unit Scaling
The pipeline fits a separate `RobustScaler` for each equipment unit, enabling the model to learn unit-specific baseline behavior.

### Cycle-Based Processing
Data is divided into operating cycles to ensure temporal continuity during preprocessing and training.

### Long-Horizon Inference
The `predict_over_horizon` function processes multi-week test sets by sliding windows, generating dense predictions across the full timeline.

### Hyperparameter Optimization
Optuna integration searches for optimal window size, LSTM architecture, and training parameters.

### Experiment Tracking
MLflow logs hyperparameters, metrics, and artifacts for reproducibility.

### Modular Design
Each module has a single responsibility and can be used independently or as part of the full pipeline.

## Advanced Usage

### Loading Trained Models for Inference Only

```python
from health_index import config, training, artifacts, inference, health_index

# Load model and artifacts
model_dir = config.get_model_dir('cda', 'Motor')
model = training.load_model(config.get_model_path('cda', 'Motor'))
arts = artifacts.load_artifacts(model_dir)

# Prepare new data with saved scalers/encoder
# ... preprocessing steps ...
df_scaled = scaling.apply_scalers_per_unit(df, feature_cols, arts['scalers'])
df_scaled = scaling.apply_categorical_encoder(df_scaled, arts['encoder'])

# Run inference
results = inference.predict_over_horizon(
    df_scaled, model, arts['feature_cols'], arts['hyperparams']['window_size']
)

# Compute health index
hi_df = health_index.compute_health_index_from_inference(results)
```

### Analyzing Health Trends

```python
from health_index import health_index as hi

# Compute trends
trends = hi.compute_trend(health_index_df)
print(trends[trends['trend_direction'] == 'degrading'])
```

### Custom Health Index Parameters

```python
# More sensitive to errors
hi_df = health_index.compute_health_index_from_inference(
    inference_results, alpha=2.0
)
```

## Troubleshooting

### No Valid Cycles
If you see "No valid cycles found", try:
- Lowering `MIN_CYCLE_DURATION` in `config.py`
- Lowering `MIN_COVERAGE` threshold
- Checking time gaps in your data

### Out of Memory
For large datasets:
- Increase `stride` in `create_windows` to reduce window count
- Process components sequentially instead of loading full dataset
- Use smaller batch sizes during training

### Low Health Index
If health index is unexpectedly low:
- Check if test data is very different from training data
- Verify outlier margins are appropriate
- Review reconstruction errors per signal
- Consider retraining with more representative data

## Requirements

```
pandas
numpy
scikit-learn
tensorflow
optuna
mlflow
joblib
tqdm
```

Install with:
```bash
pip install -r requirements.txt
```

## Contact

For questions or issues, refer to the documentation in `documentation/telemetry/`.
