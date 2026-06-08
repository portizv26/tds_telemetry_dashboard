# Phase 8: AutoEncoder Anomaly Detection — Implementation Guide

**Duration**: Weeks 10-11 (4-5 working days)  
**Objective**: Implement deep learning-based multivariate anomaly detection for complex failure patterns  
**Status**: Not Started  
**Last Updated**: May 28, 2026  
**Prerequisites**: Phase 7 completed (change-point detection validated); All explainable techniques deployed

---

## 📋 Table of Contents

1. [Phase Overview](#phase-overview)
2. [Timeline](#timeline)
3. [Inputs](#inputs)
4. [Outputs](#outputs)
5. [Task Checklist](#task-checklist)
6. [Deliverables](#deliverables)
7. [Success Criteria](#success-criteria)
8. [Local Execution Guide](#local-execution-guide)
9. [Implementation Notes](#implementation-notes)

---

## 🎯 Phase Overview

### Purpose

Implement **AutoEncoder-based anomaly detection** to capture complex multivariate patterns that explainable techniques miss:

- **Multivariate Detection**: Analyze multiple signals simultaneously (e.g., Engine system: 5 signals together)
- **Complex Patterns**: Detect non-linear relationships and interactions between signals
- **Learned Baselines**: Model learns "normal" behavior from healthy units
- **Partial Explainability**: Use SHAP or reconstruction error decomposition to identify contributing signals

### Why This Phase Matters

**Single-signal techniques have limitations**:
- Phase 2-7 techniques analyze signals mostly independently
- Some failures have **multivariate signatures**:
  - Engine overheating may involve correlated changes in 4-5 signals simultaneously
  - Brake system failure shows specific pattern across all 4 brake temperatures
  - Transmission stress combines temperature, pressure, and speed patterns

**AutoEncoder captures these complex interactions**:
- Learns normal correlation structure between signals
- Detects when signals behave normally individually but abnormally together
- Provides multivariate anomaly score (reconstruction error)

### Why This Is Phase 8 (Last Mandatory Phase)

**Rationale**:
1. ⚠️ **Lowest Explainability**: Black-box model, harder to debug
2. ⚠️ **Highest Complexity**: Requires ML training, hyperparameter tuning
3. ⚠️ **Longest Implementation**: 4-5 days vs. 2-3 days for other techniques
4. ⚠️ **Requires All Other Techniques First**: Validates ML is needed (if Phase 2-7 catch 90%+ failures, AutoEncoder may not add value)
5. ✅ **Highest Potential**: Can detect complex patterns explainable techniques miss

### Key Principle

**ML as last resort.** Only deploy AutoEncoder if validation shows it adds incremental value. Prioritize explainability; use SHAP to partially explain anomalies.

---

## 📅 Timeline

### Day 47: Model Architecture & Data Preparation

**Morning** (4 hours): **AutoEncoder Architecture Design**

**Tasks**:
1. Select target system for pilot: **Engine System**
   - Rationale: Most critical, richest signal set (5-6 signals)
   - Signals: `EngCoolTemp`, `EngOilPres`, `EngOilTemp`, `EngSpd`, `EngIntakePres`, `TCOutTemp`
2. Design AutoEncoder architecture:
   - **Input Layer**: 6 signals (normalized)
   - **Encoder**: [6 → 4 → 2] (compress to 2D latent space)
   - **Decoder**: [2 → 4 → 6] (reconstruct input)
   - **Activation**: ReLU (hidden layers), Linear (output layer)
   - **Loss Function**: Mean Squared Error (MSE)
3. Define training approach:
   - Train on "healthy" units only (no known failures in training period)
   - Use 6-hour windows (rolling windows from daily data)
   - Train/validation split: 80/20

**AutoEncoder Architecture**:
```
Input (6 signals, normalized)
    ↓
Dense(6 → 4) + ReLU + Dropout(0.2)
    ↓
Dense(4 → 2) + ReLU  [Latent Space]
    ↓
Dense(2 → 4) + ReLU + Dropout(0.2)
    ↓
Dense(4 → 6) + Linear  [Reconstruction]

Loss: MSE(input, reconstruction)
```

**Output**: Architecture design document

---

**Afternoon** (4 hours): **Data Preparation for Training**

**Tasks**:
1. Identify healthy training units:
   - Exclude units with known failures in past 90 days
   - Exclude units with high Phase 2-7 risk scores
   - Aim for ≥10 units for training
2. Load 6-hour windows from Silver data:
   - Operational state = "Operacional" only
   - Require ≥80% coverage (no long gaps)
   - Normalize signals (z-score normalization per signal)
3. Create training dataset:
   - Extract ~10,000 healthy 6-hour windows
   - Split 80% train, 20% validation
   - Store as numpy arrays or Parquet
4. Calculate normalization parameters (mean, std per signal):
   - Save for inference time

**Code Structure**:
```python
class AutoEncoderDataPrep:
    def prepare_training_data(self, units, start_date, end_date):
        """Extract healthy 6-hour windows for training."""
        windows = []
        
        for unit_id in units:
            # Load Silver data
            unit_data = self.load_silver_data(unit_id, start_date, end_date)
            
            # Filter operational state
            unit_data = unit_data[unit_data['operational_state'] == 'Operacional']
            
            # Create 6-hour rolling windows
            for window_start in self.generate_window_starts(unit_data, window_hours=6):
                window = self.extract_window(unit_data, window_start, hours=6)
                
                # Check coverage
                if self.calculate_coverage(window) < 0.8:
                    continue
                
                # Extract signal values (6 signals × N minutes)
                signal_values = window[self.engine_signals].values.T  # Shape: (6, 360)
                
                # Aggregate to single vector (mean per signal)
                window_vector = signal_values.mean(axis=1)  # Shape: (6,)
                
                windows.append(window_vector)
        
        # Normalize
        X = np.array(windows)
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0)
        X_normalized = (X - self.mean) / self.std
        
        return X_normalized
```

**Output**: 
- `data/ml_models/autoencoder/training_data/engine_training.npy`
- `data/ml_models/autoencoder/normalization_params.json`

---

### Day 48: Model Training & Validation

**Morning** (4 hours): **Model Training**

**Tasks**:
1. Implement AutoEncoder model (TensorFlow/Keras or PyTorch)
2. Choose framework:
   - **Recommendation**: TensorFlow/Keras (simpler API, good for local training)
   - Alternative: PyTorch (more flexible, harder learning curve)
3. Train model on healthy data:
   - Optimizer: Adam (learning_rate=0.001)
   - Epochs: 50-100 (early stopping on validation loss)
   - Batch size: 32
4. Monitor training:
   - Train loss decreasing
   - Validation loss stable (no overfitting)
   - Reconstruction error on healthy units <0.1 (normalized MSE)

**Training Code (Keras)**:
```python
import tensorflow as tf
from tensorflow import keras

class EngineAutoEncoder:
    def build_model(self, input_dim=6, latent_dim=2):
        """Build AutoEncoder model."""
        # Encoder
        encoder_input = keras.Input(shape=(input_dim,))
        x = keras.layers.Dense(4, activation='relu')(encoder_input)
        x = keras.layers.Dropout(0.2)(x)
        latent = keras.layers.Dense(latent_dim, activation='relu', name='latent')(x)
        
        # Decoder
        x = keras.layers.Dense(4, activation='relu')(latent)
        x = keras.layers.Dropout(0.2)(x)
        decoder_output = keras.layers.Dense(input_dim, activation='linear')(x)
        
        # Full model
        autoencoder = keras.Model(encoder_input, decoder_output, name='autoencoder')
        autoencoder.compile(optimizer='adam', loss='mse')
        
        return autoencoder
    
    def train(self, X_train, X_val, epochs=50):
        """Train AutoEncoder."""
        early_stop = keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=5,
            restore_best_weights=True
        )
        
        history = self.model.fit(
            X_train, X_train,  # Reconstruct input
            validation_data=(X_val, X_val),
            epochs=epochs,
            batch_size=32,
            callbacks=[early_stop],
            verbose=1
        )
        
        return history
```

**Output**: 
- `data/ml_models/autoencoder/engine_autoencoder.h5` (trained model)
- Training history plot

---

**Afternoon** (4 hours): **Threshold Calibration**

**Tasks**:
1. Calculate reconstruction error on healthy validation set:
   - For each window: `error = MSE(input, reconstruction)`
   - Distribution: Most healthy units have error <0.1
2. Define anomaly threshold:
   - **Method 1**: Percentile-based (e.g., P95 of healthy validation errors)
   - **Method 2**: Statistical (mean + 3*std)
   - **Recommended**: P95 = 0.08 (example)
3. Test on known abnormal units (from Phase 4):
   - Units with failures should have error >threshold
4. Validate on edge cases:
   - Units at boundary (error ~ threshold)
   - Units in different operational profiles
5. Calculate ROC curve (if labeled data available):
   - Plot True Positive Rate vs. False Positive Rate
   - Select threshold that balances detection vs. FP

**Threshold Calibration**:
```python
def calibrate_threshold(model, X_healthy_val, percentile=95):
    """Calculate anomaly threshold from healthy validation set."""
    # Reconstruct
    X_reconstructed = model.predict(X_healthy_val)
    
    # Calculate reconstruction errors
    errors = np.mean((X_healthy_val - X_reconstructed) ** 2, axis=1)
    
    # Threshold at P95
    threshold = np.percentile(errors, percentile)
    
    print(f"Healthy validation errors:")
    print(f"  Mean: {errors.mean():.4f}")
    print(f"  Std: {errors.std():.4f}")
    print(f"  P50: {np.percentile(errors, 50):.4f}")
    print(f"  P95: {threshold:.4f}")
    
    return threshold
```

**Output**: Anomaly threshold (e.g., 0.080)

---

### Day 49: Inference & Risk Scoring

**Morning** (4 hours): **Inference Pipeline**

**Tasks**:
1. Implement `AutoEncoderAnomaly` technique class
2. Load trained model and normalization parameters
3. For each unit + 6-hour window:
   - Extract 6 signals
   - Normalize using training mean/std
   - Run inference (get reconstruction)
   - Calculate reconstruction error (MSE)
4. Compare error to threshold:
   - Error < threshold → Normal
   - Error > threshold → Anomaly

**Inference Code**:
```python
class AutoEncoderAnomaly(BaseTechnique):
    def __init__(self, model_path, normalization_params, threshold):
        self.model = keras.models.load_model(model_path)
        self.mean = normalization_params['mean']
        self.std = normalization_params['std']
        self.threshold = threshold
    
    def detect_anomaly(self, window_data):
        """Run inference on 6-hour window."""
        # Extract signals
        signal_vector = window_data[self.engine_signals].mean(axis=0).values
        
        # Normalize
        signal_vector_norm = (signal_vector - self.mean) / self.std
        
        # Reshape for model input
        X = signal_vector_norm.reshape(1, -1)
        
        # Reconstruct
        X_reconstructed = self.model.predict(X, verbose=0)
        
        # Calculate error
        reconstruction_error = np.mean((X - X_reconstructed) ** 2)
        
        # Classify
        is_anomaly = reconstruction_error > self.threshold
        
        return {
            'reconstruction_error': reconstruction_error,
            'is_anomaly': is_anomaly,
            'threshold': self.threshold
        }
```

**Output**: `src/techniques/autoencoder_anomaly.py` (partial)

---

**Afternoon** (4 hours): **Risk Score Normalization**

**Tasks**:
1. Convert reconstruction error to risk score (0-100):
   - Error = threshold → score = 70 (Anormal starts here)
   - Error = 2×threshold → score = 90
   - Error = 3×threshold → score = 100
2. Calculate confidence score:
   - High if: Window coverage >90%, operational state stable
   - Medium if: Window coverage 80-90%
   - Low if: Window coverage <80% or state transitions
3. Build evidence dictionary:
   - Reconstruction error value
   - Threshold
   - Signal-level reconstruction errors (which signal contributes most?)

**Risk Score Formula**:
```python
def calculate_risk_score(self, reconstruction_error, threshold):
    """Convert reconstruction error to risk score."""
    if reconstruction_error <= threshold:
        # Normal: linear scaling 0-70
        risk_score = (reconstruction_error / threshold) * 70
    else:
        # Abnormal: linear scaling 70-100
        excess_error = reconstruction_error - threshold
        risk_score = 70 + min(30, (excess_error / threshold) * 30)
    
    return min(100, risk_score)
```

**Signal-Level Contribution**:
```python
def decompose_reconstruction_error(self, X_input, X_reconstructed):
    """Identify which signals contribute most to error."""
    signal_errors = (X_input - X_reconstructed) ** 2
    
    contributions = []
    for i, signal_name in enumerate(self.engine_signals):
        contributions.append({
            'signal': signal_name,
            'squared_error': signal_errors[0, i],
            'pct_contribution': (signal_errors[0, i] / signal_errors.sum()) * 100
        })
    
    # Sort by contribution
    contributions.sort(key=lambda x: x['pct_contribution'], reverse=True)
    
    return contributions[:3]  # Top 3 contributors
```

**Output**: `src/techniques/autoencoder_anomaly.py` (complete)

---

### Day 50: SHAP Explainability & Testing

**Morning** (4 hours): **SHAP Integration (Optional)**

**Tasks**:
1. Install SHAP library:
   ```bash
   pip install shap
   ```
2. Apply SHAP to AutoEncoder:
   - SHAP explains: "Which input signals most influenced the reconstruction error?"
   - Use DeepExplainer (for neural networks)
3. Generate SHAP values for anomalous windows
4. Visualize signal importance (SHAP waterfall plot)

**SHAP Code**:
```python
import shap

class AutoEncoderWithSHAP(AutoEncoderAnomaly):
    def explain_anomaly(self, window_data, background_data):
        """Generate SHAP explanation for anomalous window."""
        # Prepare data
        X_window = self.preprocess(window_data)
        X_background = self.preprocess(background_data)  # Sample of healthy data
        
        # Create SHAP explainer
        explainer = shap.DeepExplainer(self.model, X_background)
        
        # Calculate SHAP values
        shap_values = explainer.shap_values(X_window)
        
        # Identify most influential signals
        signal_importance = []
        for i, signal_name in enumerate(self.engine_signals):
            signal_importance.append({
                'signal': signal_name,
                'shap_value': abs(shap_values[0, i]),
                'direction': 'high' if shap_values[0, i] > 0 else 'low'
            })
        
        signal_importance.sort(key=lambda x: x['shap_value'], reverse=True)
        
        return signal_importance[:3]  # Top 3
```

**Output**: SHAP-based explanations for anomalies

---

**Afternoon** (4 hours): **Testing & Validation**

**Tasks**:
1. Test on known Engine failures from Phase 4:
   - Load failure events
   - Extract 6-hour windows before failure
   - Run AutoEncoder inference
   - Check: Did AutoEncoder detect anomaly?
2. Calculate detection metrics:
   - Detection rate for Engine failures
   - Mean advance warning (hours before failure)
   - False positive rate (sample healthy units)
3. Compare against Phase 2-7 techniques:
   - Which failures detected ONLY by AutoEncoder?
   - Incremental value quantification
4. Test on full fleet (sample 20-30 units)

**Test Script**:
```bash
# Test on known failures
python scripts/test_autoencoder_on_failures.py \
  --known-events data/validation/known_events.csv \
  --system Engine \
  --output data/validation/autoencoder_validation.csv

# Test on full fleet (sampling)
python scripts/test_autoencoder_fleet.py \
  --sample-size 30 \
  --client CDA \
  --output reports/autoencoder_fleet_test.csv
```

**Output**: 
- `data/validation/autoencoder_validation.csv`
- Validation report

---

### Day 51: Integration & Deployment

**Morning** (4 hours): **Model Serving Setup**

**Tasks**:
1. Package trained model for deployment:
   - Model file (`.h5` or `.pt`)
   - Normalization parameters (JSON)
   - Threshold config (JSON)
   - Signal list (YAML)
2. Create model registry:
   - Track model versions
   - Track training date, data used
   - Track performance metrics
3. Implement model loader:
   - Load model on startup (not per-execution)
   - Cache in memory for fast inference

**Model Registry**:
```json
{
  "model_id": "engine_autoencoder_v1",
  "system": "Engine",
  "version": "1.0.0",
  "training_date": "2026-05-24",
  "training_units": 12,
  "training_windows": 10420,
  "threshold_p95": 0.080,
  "validation_metrics": {
    "mean_healthy_error": 0.042,
    "p95_healthy_error": 0.080,
    "detection_rate": 0.67,
    "false_positive_rate": 0.22
  },
  "signals": [
    "EngCoolTemp",
    "EngOilPres",
    "EngOilTemp",
    "EngSpd",
    "EngIntakePres",
    "TCOutTemp"
  ]
}
```

**Output**: 
- `data/ml_models/autoencoder/model_registry.json`
- Model packaging complete

---

**Afternoon** (4 hours): **Runner Script & Integration**

**Tasks**:
1. Create runner script: `run_autoencoder_detection.py`
2. Execution strategy:
   - Run every 6 hours (4x per day)
   - Process 6-hour rolling windows
   - Store anomalies only (skip Normal results to save space)
3. Test on full fleet (all clients)
4. Store results to `technique_results/autoencoder/`
5. Verify integration with Phase 3 aggregation:
   - AutoEncoder results feed into system health
   - High reconstruction errors increase Engine health score

**Execution**:
```bash
# Run AutoEncoder detection (every 6 hours)
python src/runners/run_autoencoder_detection.py \
  --date 2026-05-28 \
  --time 06:00 \
  --system Engine \
  --client CDA \
  --output data/telemetry/analytical_results/technique_results/autoencoder/

# Summary report
python scripts/summarize_autoencoder_anomalies.py \
  --date 2026-05-28 \
  --output reports/autoencoder_anomalies_20260528.csv
```

**Output**: 
- `src/runners/run_autoencoder_detection.py`
- AutoEncoder results in `technique_results/autoencoder/`

---

## 📥 Inputs

### Data Inputs

| Input | Location | Format | Created By | Notes |
|-------|----------|--------|------------|-------|
| Silver telemetry | `data/telemetry/silver/{client}/` | Parquet | Upstream | 6-hour windows, operational state filter |
| Signal registry | `config/signal_registry_v1.yaml` | YAML | Phase 1 | Engine system signals |
| Known failure events | `data/validation/known_events.csv` | CSV | Phase 4 | For validation (Engine failures only) |
| Healthy unit list | Manual or Phase 3 output | CSV | Analyst | Units with low risk scores |

### Configuration Inputs

| Parameter | Source | Default | Notes |
|-----------|--------|---------|-------|
| Window size | Configuration | 6 hours | Evaluation window |
| Latent dimension | Architecture | 2 | Compressed representation size |
| Anomaly threshold | Calibration | P95 healthy errors | Adjust based on validation |
| Operational state filter | Configuration | "Operacional" only | Exclude idle/off |

---

## 📤 Outputs

### Code Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| AutoEncoderDataPrep | `src/ml/autoencoder_data_prep.py` | Training data preparation |
| EngineAutoEncoder | `src/ml/engine_autoencoder.py` | Model architecture and training |
| AutoEncoderAnomaly | `src/techniques/autoencoder_anomaly.py` | Inference and risk scoring |
| AutoEncoderWithSHAP | `src/ml/autoencoder_shap.py` | SHAP explainability (optional) |
| Runner script | `src/runners/run_autoencoder_detection.py` | Local execution |
| Test suite | `tests/test_autoencoder.py` | Unit tests |

### Data Artifacts

| Artifact | Location | Format | Cadence | Purpose |
|----------|----------|--------|---------|---------|
| Trained model | `data/ml_models/autoencoder/engine_autoencoder.h5` | HDF5 (Keras) | One-time | Model weights |
| Normalization params | `data/ml_models/autoencoder/normalization_params.json` | JSON | One-time | Mean/std per signal |
| Model registry | `data/ml_models/autoencoder/model_registry.json` | JSON | One-time | Model metadata |
| AutoEncoder results | `technique_results/autoencoder/year=*/month=*/day=*/hour=*/` | Parquet | Every 6h | Anomaly detections |
| Validation report | `data/validation/autoencoder_validation.csv` | CSV | One-time | Performance metrics |

### Documentation Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| AutoEncoder methodology | `documentation/telemetry/autoencoder_methodology.md` | Model architecture, training process |
| SHAP explainability guide | `documentation/telemetry/autoencoder_shap_guide.md` | How to interpret SHAP values |
| Model retraining guide | `documentation/telemetry/autoencoder_retraining.md` | When and how to retrain |

---

## ✅ Task Checklist

### Day 47: Architecture & Data Prep

**Morning: Architecture Design**
- [ ] Select pilot system (Engine)
- [ ] Select Engine signals (6 signals)
- [ ] Design AutoEncoder architecture (6→4→2→4→6)
- [ ] Define activation functions (ReLU, Linear)
- [ ] Define loss function (MSE)
- [ ] Document training approach (healthy units, 6h windows)
- [ ] Create architecture diagram

**Afternoon: Data Preparation**
- [ ] Identify healthy training units (≥10 units)
- [ ] Load Silver data for training period
- [ ] Filter operational state ("Operacional")
- [ ] Extract 6-hour rolling windows
- [ ] Check coverage per window (≥80%)
- [ ] Aggregate to signal vectors (mean per signal per window)
- [ ] Calculate normalization parameters (mean, std)
- [ ] Normalize training data
- [ ] Split train/validation (80/20)
- [ ] Save training data and normalization params

### Day 48: Training & Threshold Calibration

**Morning: Model Training**
- [ ] Install TensorFlow/Keras (`pip install tensorflow`)
- [ ] Implement AutoEncoder model (build_model())
- [ ] Compile model (optimizer=Adam, loss=MSE)
- [ ] Train on healthy data (50-100 epochs)
- [ ] Add early stopping (patience=5)
- [ ] Monitor training/validation loss
- [ ] Save trained model (engine_autoencoder.h5)
- [ ] Plot training history

**Afternoon: Threshold Calibration**
- [ ] Run inference on healthy validation set
- [ ] Calculate reconstruction errors
- [ ] Analyze error distribution (mean, std, P95)
- [ ] Select anomaly threshold (P95 or mean+3std)
- [ ] Test on known abnormal units
- [ ] Validate threshold (ROC curve if possible)
- [ ] Document threshold selection rationale
- [ ] Save threshold to config

### Day 49: Inference & Risk Scoring

**Morning: Inference Pipeline**
- [ ] Implement AutoEncoderAnomaly class
- [ ] Load trained model and normalization params
- [ ] Implement detect_anomaly() method
- [ ] Extract 6-hour windows from Silver data
- [ ] Normalize input
- [ ] Run inference (reconstruction)
- [ ] Calculate reconstruction error
- [ ] Compare to threshold (classify)
- [ ] Test on sample units

**Afternoon: Risk Scoring**
- [ ] Implement risk score normalization formula
- [ ] Map reconstruction error to 0-100 scale
- [ ] Calculate confidence score (coverage, state stability)
- [ ] Decompose reconstruction error (signal-level contributions)
- [ ] Build evidence dictionary (error, threshold, top contributors)
- [ ] Add natural language explanation
- [ ] Validate TechniqueResult output schema
- [ ] Test risk scoring on edge cases

### Day 50: SHAP & Testing

**Morning: SHAP Integration (Optional)**
- [ ] Install SHAP library (`pip install shap`)
- [ ] Implement AutoEncoderWithSHAP class
- [ ] Create DeepExplainer with background data
- [ ] Generate SHAP values for anomalous windows
- [ ] Identify most influential signals (top 3)
- [ ] Test SHAP on sample anomalies
- [ ] Document SHAP interpretation

**Afternoon: Testing & Validation**
- [ ] Load Phase 4 known Engine failures
- [ ] Test AutoEncoder on failure events
- [ ] Calculate detection rate
- [ ] Calculate mean advance warning (hours)
- [ ] Test on healthy units (false positive rate)
- [ ] Compare against Phase 2-7 techniques
- [ ] Identify incremental detections (AutoEncoder only)
- [ ] Test on fleet sample (20-30 units)
- [ ] Generate validation report

### Day 51: Integration & Deployment

**Morning: Model Serving Setup**
- [ ] Package trained model (model, normalization, threshold, signals)
- [ ] Create model_registry.json (version, metrics, metadata)
- [ ] Implement model loader (load once, cache in memory)
- [ ] Track model versions
- [ ] Document model serving approach

**Afternoon: Runner Script & Integration**
- [ ] Create run_autoencoder_detection.py runner
- [ ] Implement 6-hour rolling window execution
- [ ] Add operational state filter
- [ ] Store anomalies only (skip Normal to save space)
- [ ] Test on full fleet (all clients)
- [ ] Store results to technique_results/autoencoder/
- [ ] Verify integration with Phase 3 aggregation
- [ ] Update aggregation to consume AutoEncoder results
- [ ] Test end-to-end (AutoEncoder → system health)
- [ ] Create anomaly summary script
- [ ] Document execution commands

---

## 📦 Deliverables

### Critical Deliverables (Must-Have)

1. **Trained AutoEncoder Model**
   - Engine AutoEncoder trained on healthy data
   - Stored in `data/ml_models/autoencoder/engine_autoencoder.h5`
   - Model registry with metadata and metrics

2. **Inference Pipeline**
   - `AutoEncoderAnomaly` technique class complete
   - Risk scoring and confidence calculation working
   - Signal-level contribution decomposition implemented

3. **Validation Report**
   - AutoEncoder tested on Phase 4 known failures
   - Detection rate and advance warning calculated
   - Incremental value vs. Phase 2-7 quantified

4. **Runner Script**
   - `run_autoencoder_detection.py` working
   - Executes every 6 hours (manually for POC)
   - Results stored correctly

### Important Deliverables (Should-Have)

5. **Threshold Calibration Report**
   - Anomaly threshold selection documented
   - Validation on healthy and abnormal units

6. **Integration with Aggregation**
   - AutoEncoder results feed into Phase 3 system health
   - Engine health scores reflect AutoEncoder anomalies

### Nice-to-Have Deliverables

7. **SHAP Explainability**
   - SHAP values calculated for anomalies
   - Signal importance visualization

8. **Model Retraining Guide**
   - When to retrain (e.g., quarterly)
   - How to include new units in training
   - Performance degradation monitoring

---

## 🏆 Success Criteria

### Functional Success

- [ ] AutoEncoder trains successfully on healthy data
- [ ] Training converges (validation loss stable)
- [ ] Inference runs in <1 second per window
- [ ] Results stored in correct Parquet partitions

### Detection Performance

- [ ] AutoEncoder detects ≥1 Engine failure missed by Phase 2-7 (or N/A if all already detected)
- [ ] Mean advance warning ≥6 hours (before failure)
- [ ] False positive rate ≤30% (acceptable for ML technique)
- [ ] Healthy validation error distribution is narrow (std <0.02)

### Explainability

- [ ] Signal-level reconstruction error decomposition available
- [ ] Top 3 contributing signals identified per anomaly
- [ ] SHAP values provide partial explainability (optional)

### Model Quality

- [ ] Training/validation loss ratio <1.2 (no overfitting)
- [ ] Reconstruction error on healthy units <0.1 (normalized MSE)
- [ ] Model generalizes to new units (not in training set)

### Integration

- [ ] AutoEncoder results feed into Phase 3 aggregation
- [ ] System health scores updated correctly
- [ ] Can run manually via command line

---

## 💻 Local Execution Guide

### Setup Requirements

**Python Environment**:
```bash
# Core dependencies
pip install pandas numpy scipy tensorflow

# Optional (for SHAP)
pip install shap matplotlib

# Verify TensorFlow installation
python -c "import tensorflow as tf; print(tf.__version__)"
```

**Hardware Requirements**:
- **Training**: 8GB RAM minimum, 16GB recommended
- **Inference**: 4GB RAM sufficient
- **GPU**: Optional (CPU training is acceptable for small dataset)

**Data Prerequisites**:
- Silver telemetry for ≥10 healthy units (past 90 days)
- Phase 4 known failure events for validation
- List of units to exclude from training (units with known issues)

### Model Training (One-Time Setup)

**Step 1: Prepare Training Data**:

```bash
cd c:\Users\patri\Coddi\Proyectos\telemetry_dashboard

# Prepare training data from healthy units
python src/ml/prepare_autoencoder_training_data.py \
  --system Engine \
  --start-date 2025-11-01 \
  --end-date 2026-02-28 \
  --min-units 10 \
  --output data/ml_models/autoencoder/training_data/
```

**Step 2: Train Model**:

```bash
# Train AutoEncoder
python src/ml/train_autoencoder.py \
  --training-data data/ml_models/autoencoder/training_data/engine_training.npy \
  --epochs 50 \
  --latent-dim 2 \
  --output data/ml_models/autoencoder/
```

**Step 3: Calibrate Threshold**:

```bash
# Calibrate anomaly threshold
python src/ml/calibrate_autoencoder_threshold.py \
  --model data/ml_models/autoencoder/engine_autoencoder.h5 \
  --validation-data data/ml_models/autoencoder/training_data/engine_validation.npy \
  --percentile 95 \
  --output data/ml_models/autoencoder/threshold_config.json
```

### Running AutoEncoder Detection

**Daily Execution** (run every 6 hours):

```bash
# Run for specific 6-hour window
python src/runners/run_autoencoder_detection.py \
  --date 2026-05-28 \
  --hour 06 \
  --system Engine \
  --client CDA \
  --output data/telemetry/analytical_results/technique_results/autoencoder/

# Run for all 6-hour windows in a day
for hour in 00 06 12 18; do
  python src/runners/run_autoencoder_detection.py \
    --date 2026-05-28 \
    --hour $hour \
    --system Engine \
    --client CDA \
    --output data/telemetry/analytical_results/technique_results/autoencoder/
done
```

**Generate Anomaly Report**:

```bash
# Summarize anomalies detected
python scripts/summarize_autoencoder_anomalies.py \
  --date 2026-05-28 \
  --system Engine \
  --client CDA \
  --output reports/autoencoder_anomalies_20260528.csv

# View high-risk anomalies only
python scripts/high_risk_autoencoder_anomalies.py \
  --date 2026-05-28 \
  --risk-threshold 80 \
  --output reports/high_risk_autoencoder_20260528.csv
```

**Validation Against Known Failures**:

```bash
# Test on known Engine failures
python scripts/test_autoencoder_on_failures.py \
  --known-events data/validation/known_events.csv \
  --system Engine \
  --output data/validation/autoencoder_validation.csv
```

### Expected Output Files

After training:
```
data/ml_models/autoencoder/
  engine_autoencoder.h5
  normalization_params.json
  threshold_config.json
  model_registry.json
```

After detection:
```
technique_results/autoencoder/
  year=2026/
    month=05/
      day=28/
        hour=06/
          client=CDA/
            part-0.parquet
```

Each AutoEncoder result contains:
- `unit_id`
- `timestamp`
- `system`: "Engine"
- `technique_name`: "autoencoder"
- `reconstruction_error`
- `threshold`
- `risk_score`
- `confidence_score`
- `status`
- `evidence`: {"top_contributors": [...], "shap_values": [...]}

### Troubleshooting

**Issue**: Model doesn't converge (loss not decreasing)
- Check training data quality (sufficient coverage?)
- Try more epochs (50 → 100)
- Adjust learning rate (0.001 → 0.0005)
- Check for NaN values in training data

**Issue**: High false positive rate (>40%)
- Increase anomaly threshold (P95 → P97 → P99)
- Retrain with more healthy units (expand training set)
- Check if "healthy" units actually had subtle issues

**Issue**: Low detection rate (<50%)
- Decrease anomaly threshold (P95 → P90)
- Check if failures show multivariate patterns (AutoEncoder's strength)
- Verify normalization is applied correctly at inference
- Consider expanding signal set (6 → 8 signals)

**Issue**: Model overfits (train loss << validation loss)
- Increase Dropout rate (0.2 → 0.3)
- Reduce model complexity (4 nodes → 3 nodes in hidden layers)
- Add more training data
- Apply L2 regularization

**Issue**: SHAP takes too long (>10 seconds per window)
- Reduce background data size (100 samples → 50)
- Skip SHAP for POC (use signal-level decomposition only)
- Run SHAP offline for investigation only (not in production pipeline)

---

## 📝 Implementation Notes

### Day 47 Notes

**Date**: ___________  
**Developer**: ___________

**Work Completed**:
- 
- 

**Decisions Made**:
- 

**Blockers/Issues**:
- 

**Next Steps**:
- 

---

### Day 48 Notes

**Date**: ___________  
**Developer**: ___________

**Work Completed**:
- 
- 

**Decisions Made**:
- 

**Blockers/Issues**:
- 

**Next Steps**:
- 

---

### Day 49 Notes

**Date**: ___________  
**Developer**: ___________

**Work Completed**:
- 
- 

**Decisions Made**:
- 

**Blockers/Issues**:
- 

**Next Steps**:
- 

---

### Day 50 Notes

**Date**: ___________  
**Developer**: ___________

**Work Completed**:
- 
- 

**Decisions Made**:
- 

**Blockers/Issues**:
- 

**Next Steps**:
- 

---

### Day 51 Notes

**Date**: ___________  
**Developer**: ___________

**Work Completed**:
- 
- 

**Decisions Made**:
- 

**Blockers/Issues**:
- 

**Next Steps**:
- 

---

## 🔄 Phase Retrospective

**Completion Date**: ___________

### What Went Well
- 
- 

### What Didn't Go Well
- 
- 

### Lessons Learned
- 
- 

### Recommendations for Production Deployment
- 
- 

---

## 📊 Validation Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Model convergence | Yes (validation loss stable) | ___ | ⏳ |
| Healthy validation error | <0.1 (normalized MSE) | ___ | ⏳ |
| Overfitting ratio (train/val loss) | <1.2 | ___ | ⏳ |
| Detection rate (Engine failures) | ≥50% | ___ | ⏳ |
| Incremental detections (vs. Phase 2-7) | ≥1 | ___ | ⏳ |
| Mean advance warning | ≥6 hours | ___ | ⏳ |
| False positive rate | ≤30% | ___ | ⏳ |
| Inference time per window | <1 second | ___ | ⏳ |

**Overall Phase 8 Status**: ⏳ Not Started

---

**Implementation Complete**: After Phase 8, all mandatory analytical techniques are deployed. Proceed to Phase 3 aggregation updates and final validation.
