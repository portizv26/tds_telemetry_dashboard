# Health Index Module

A modular Python package for telemetry-based equipment health monitoring using LSTM autoencoders.

## Package Structure

```
src/health_index/
├── __init__.py              # Package initialization
├── config.py                # Configuration and constants
├── io.py                    # Data I/O operations
├── preprocessing.py         # Outlier cleaning
├── cycles.py                # Cycle detection and interpolation
├── labeling.py              # Percentile-based anomaly labeling
├── scaling.py               # Per-unit feature scaling
├── windowing.py             # Sequence window creation
├── modeling.py              # LSTM autoencoder architecture
├── optimization.py          # Optuna hyperparameter optimization
├── training.py              # Model training with MLflow
├── inference.py             # Single and multi-window inference
├── health_index.py          # Health index computation
├── artifacts.py             # Artifact persistence
└── pipeline.py              # End-to-end pipeline orchestration
```

## Module Descriptions

### config.py
Central configuration for all pipeline parameters:
- File paths and directories
- Preprocessing parameters (outlier margins, cycle thresholds)
- Model hyperparameters
- Optuna search space
- MLflow settings
- Health index parameters

### io.py
Handles all data loading and saving:
- `load_telemetry_data()`: Load raw telemetry from parquet
- `load_component_mapping()`: Load component-signal mapping from JSON
- `save_processed_data()`: Save preprocessed data to silver layer
- `save_inference_data()`: Save predictions to golden layer
- `save_health_index_data()`: Save health indices to golden layer
- `save/load_dict_as_json()`: Generic JSON operations

### preprocessing.py
Data cleaning utilities:
- `clean_outliers()`: Replace out-of-range values with NaN
- `drop_rows_with_missing_signals()`: Remove rows with excessive missing data
- `fill_categorical_missing()`: Impute categorical NaNs

### cycles.py
Cycle-based temporal processing:
- `detect_cycles()`: Identify operating cycles based on time gaps
- `is_valid_cycle()`: Validate cycle duration and coverage
- `interpolate_cycle()`: Time-based interpolation within a cycle
- `process_cycles()`: Complete cycle processing pipeline

**Why cycles?** Telemetry data often has gaps. Cycles ensure we only interpolate within continuous operating periods, preserving temporal integrity.

### labeling.py
Anomaly labeling for training:
- `compute_percentile_thresholds()`: Calculate P5-P95 thresholds per signal
- `flag_out_of_range()`: Flag values outside normal range
- `label_cycles_by_anomaly_ratio()`: Label cycles as Normal/Anomalous
- `create_labels()`: Complete labeling pipeline

**Purpose:** Labels help with model evaluation and can be used for supervised/semi-supervised approaches.

### scaling.py
Feature scaling and encoding:
- `fit_scalers_per_unit()`: Fit RobustScaler for each equipment unit
- `apply_scalers_per_unit()`: Apply per-unit scaling
- `fit_categorical_encoder()`: Fit OneHotEncoder for categorical features
- `apply_categorical_encoder()`: Apply categorical encoding
- `save/load_scalers()`: Persist scalers to disk
- `save/load_encoder()`: Persist encoder to disk

**Key insight:** Each equipment unit has unique baseline behavior. Per-unit scaling is critical for accurate anomaly detection.

### windowing.py
Sequence window creation for LSTM:
- `create_windows()`: Create sliding windows with metadata
- `create_single_window_inference()`: Extract latest window per unit

**Important:** Windows maintain temporal continuity within cycles. Invalid windows (with NaN) are automatically filtered out.

### modeling.py
Neural network architecture:
- `build_lstm_autoencoder()`: Construct LSTM encoder-decoder model
- `get_model_summary()`: Get model architecture as string
- `count_parameters()`: Count trainable parameters

**Architecture:** The autoencoder learns to reconstruct normal operating patterns. High reconstruction error indicates anomalous behavior.

### optimization.py
Hyperparameter tuning with Optuna:
- `OptunaObjective`: Objective function for Optuna trials
- `optimize_hyperparameters()`: Run Optuna study with TPE sampler
- `save/load_optimization_results()`: Persist optimization results as JSON

**Why Optuna?** Efficient Bayesian optimization finds better hyperparameters than grid/random search.

### training.py
Model training with experiment tracking:
- `setup_mlflow()`: Configure MLflow tracking
- `train_model()`: Train with early stopping and MLflow logging
- `save/load_model()`: Persist Keras models

**MLflow integration:** Automatically logs hyperparameters, metrics, and training curves for reproducibility.

### inference.py
Prediction generation:
- `predict_single_window()`: Generate reconstructions for one batch
- `compute_reconstruction_error()`: Calculate MSE/MAE/RMSE
- `predict_over_horizon()`: **Multi-window inference for long time periods**
- `predict_latest_window_per_unit()`: Real-time inference per unit

**Key function:** `predict_over_horizon()` is the core of long-horizon inference. It slides a window over weeks of test data, generating dense predictions.

### health_index.py
Health index computation and analysis:
- `compute_health_index()`: Convert reconstruction error to 0-100 health score
- `aggregate_health_index_per_unit()`: Summarize per equipment unit
- `categorize_health_status()`: Map scores to Excellent/Good/Fair/Poor/Critical
- `compute_health_index_from_inference()`: Complete HI pipeline
- `compute_trend()`: Analyze health trends over time

**Formula:** HI = 100 * exp(-alpha * normalized_error), where higher HI = healthier equipment.

### artifacts.py
Artifact management:
- `save_all_artifacts()`: Save all training artifacts to disk
- `load_artifacts()`: Load artifacts for inference
- `create_artifact_summary()`: Generate artifact inventory

**Artifacts include:** Trained model, scalers, encoder, feature list, hyperparameters, optimization results, training history, metadata.

### pipeline.py
End-to-end orchestration:
- `run_component_pipeline()`: Execute full pipeline for one component
- `run_all_components_pipeline()`: Process all components sequentially

**Workflow:** Load → Split → Preprocess → Cycles → Label → Scale → Optimize → Train → Infer → Health Index → Save

## Design Principles

### 1. Single Responsibility
Each module handles one aspect of the pipeline. Functions are small and focused.

### 2. Modularity
Modules can be used independently or composed into custom workflows.

### 3. Configurability
All constants are centralized in `config.py`. No hard-coded magic numbers.

### 4. Robustness
Handles missing data, invalid cycles, and edge cases gracefully.

### 5. Scalability
Designed to process multiple units, components, and long time horizons efficiently.

### 6. Reproducibility
MLflow tracking and artifact persistence ensure experiments can be reproduced.

## Key Concepts

### Per-Unit Scaling
Each equipment unit has unique operating characteristics. We fit a separate scaler for each unit to normalize signals relative to that unit's baseline.

### Cycle-Based Processing
Operating cycles are detected and validated before interpolation. This ensures we only fill gaps within continuous operating periods, not across shutdowns or maintenance.

### Multi-Window Inference
The model is trained on fixed-size windows (e.g., 60 minutes). For inference on weeks of data, we slide the window with a stride, generating overlapping predictions. This provides dense temporal coverage.

### Health Index
Reconstruction error is normalized and converted to an intuitive 0-100 scale, where 100 = perfect health. This makes results interpretable for non-technical stakeholders.

## Usage Examples

See `scripts/health_index_examples.py` for detailed usage examples.

Quick start:
```python
from health_index import io, pipeline

# Load component mapping
mapping = io.load_component_mapping()

# Run pipeline for Motor
result = pipeline.run_component_pipeline(
    client='cda',
    component='Motor',
    signal_cols=mapping['components']['Motor']['signals'],
    run_optimization=True,
)
```

## Testing

To test the pipeline on a small subset:
```python
# Load only recent data for quick testing
df = io.load_telemetry_data('cda')
df_recent = df[df['Fecha'] >= '2025-01-01']

result = pipeline.run_component_pipeline(
    client='cda',
    component='Motor',
    signal_cols=signal_cols,
    df=df_recent,  # Pass pre-filtered data
    run_optimization=False,  # Skip optimization for speed
    use_mlflow=False,  # Disable tracking for testing
    test_weeks=1,  # Smaller test set
)
```

## Performance Considerations

### Memory
- Large datasets may require chunking or reducing stride in windowing
- Consider processing components sequentially rather than loading all data at once

### Computation
- Optuna optimization is the most expensive step (20+ trials)
- Training typically takes 5-15 minutes per component
- Inference is faster (~1-2 minutes per component)

### Storage
- Models are typically 1-5 MB each
- Scalers and artifacts are < 1 MB
- Inference results depend on test set size (6 weeks ≈ 10-50 MB)

## Extending the Package

### Adding New Preprocessing Steps
Edit `preprocessing.py` and add new functions. Call them in `pipeline.py`.

### Custom Model Architectures
Edit `modeling.py` to define new architectures. Ensure input/output shapes match the autoencoder pattern.

### Different Optimization Strategies
Modify `optimization.py` to use different samplers or search spaces.

### Alternative Health Metrics
Edit `health_index.py` to implement new health score formulas.

## Dependencies

- pandas, numpy: Data manipulation
- scikit-learn: Scaling and preprocessing
- tensorflow: Deep learning
- optuna: Hyperparameter optimization
- mlflow: Experiment tracking
- joblib: Artifact serialization
- tqdm: Progress bars

## Future Improvements

Potential enhancements:
- Distributed training for multiple components in parallel
- Online learning for continuous model updates
- Uncertainty quantification for predictions
- Automated alert generation based on health thresholds
- Time series forecasting for predictive maintenance
- Multi-modal fusion (telemetry + images + maintenance logs)

## Contributing

When contributing:
1. Keep functions focused and single-purpose
2. Add docstrings with Args/Returns
3. Update `config.py` for new parameters
4. Test with small data subsets first
5. Document breaking changes

## License

Internal use only.
