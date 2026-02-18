# Telemetry Analysis - Improvement Plan

**Version**: 1.0  
**Created**: February 18, 2026  
**Owner**: Telemetry Analysis Team  
**Goal**: Enhance MVP with AI recommendations and advanced detection methods

---

## 📋 Table of Contents

1. [Improvement Strategy](#improvement-strategy)
2. [Phase 1: AI Recommendations](#phase-1-ai-recommendations)
3. [Phase 2: Enhanced Detection Methods](#phase-2-enhanced-detection-methods)
4. [Phase 3: Advanced Analytics](#phase-3-advanced-analytics)
5. [Phase 4: Optimization & Scaling](#phase-4-optimization--scaling)
6. [Long-Term Roadmap](#long-term-roadmap)

---

## 🎯 Improvement Strategy

### Post-MVP Philosophy

The MVP delivers a **functional system** using percentile-based, state-conditioned analysis. This improvement plan builds on that foundation by:

1. **Adding AI-powered insights** (human-readable explanations)
2. **Incorporating temporal patterns** (rate of change, trends)
3. **Introducing multivariate analysis** (signal correlations)
4. **Optimizing performance** (faster processing, lower costs)

### Guiding Principles

- ✅ **Incremental**: Each phase independently adds value
- ✅ **Backward Compatible**: Don't break existing functionality
- ✅ **Measurable**: Each enhancement has clear success metrics
- ✅ **User-Driven**: Prioritize based on maintenance team feedback

---

## 📅 Phase 1: AI Recommendations

**Duration**: 2-3 weeks  
**Goal**: Add human-readable AI analysis to component evaluations

### Overview

Currently, the MVP outputs grades (Normal/Alerta/Anormal) and scores. Users want **contextual explanations**:
- "Why is this component flagged?"
- "What should I check during maintenance?"
- "Is this urgent or can it wait?"

AI recommendations provide narrative insights that translate technical signals into actionable maintenance advice.

---

### **Step 1.1: Design AI Prompt Template**

**Objective**: Create structured prompts that generate useful recommendations

**Prompt Components**:
1. **Component Context**: Name, current status, score
2. **Signal Evidence**: Which signals are Anormal/Alerta, their values vs. baselines
3. **Operational Context**: Recent states (Operacional, Cargado, etc.)
4. **Historical Trend**: Is this new or recurring?
5. **Ask**: Generate recommendation

**Example Prompt**:
```
You are a mining equipment maintenance expert analyzing telemetry data.

Component: Motor (Unit 247)
Status: Anormal (Score: 25)

Signal Evidence:
- EngCoolTemp: 103.5°C (Baseline P99: 98.3°C) - EXCEEDED by 5.2°C
- LtExhTemp: 502°C (Baseline P99: 485°C) - EXCEEDED by 17°C
- EngOilPres: 45.2 PSI (Baseline P50: 46.1 PSI) - Normal

Operational Context:
- Recent states: 80% Operacional-Cargado, 15% Operacional-Descargado, 5% Ralenti
- GPS Elevation: Frequently operates at 2500-3000m altitude

Historical Pattern:
- EngCoolTemp has been trending upward over last 3 weeks
- LtExhTemp spiked suddenly in last 48 hours

Task: Provide a concise maintenance recommendation (2-3 sentences) that explains:
1. What likely caused these readings
2. What maintenance action should be taken
3. Urgency level (Immediate, Within 24h, Within Week, Monitor)
```

**Deliverable**: `src/telemetry/ai_prompts.py` with template functions

---

### **Step 1.2: LLM Integration**

**Objective**: Connect to LLM API to generate recommendations

**Options**:
- **OpenAI GPT-4**: Best quality, moderate cost
- **Azure OpenAI**: Enterprise-ready, same models
- **Anthropic Claude**: Strong reasoning
- **Open-source LLMs**: Llama 3, Mixtral (self-hosted, lower cost)

**Implementation**:
```python
# ai_recommender.py

import openai  # or anthropic, etc.

def generate_ai_recommendation(component_eval, signal_details, historical_context):
    """
    Generate AI recommendation for a component
    
    Args:
        component_eval: Dict with component status, score
        signal_details: List of dicts with signal grades, values, baselines
        historical_context: Dict with trend info, operational patterns
    
    Returns:
        String with AI recommendation
    """
    
    # Build prompt
    prompt = build_recommendation_prompt(
        component_eval, signal_details, historical_context
    )
    
    # Call LLM
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a mining equipment maintenance expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower = more consistent
            max_tokens=200    # Keep recommendations concise
        )
        
        recommendation = response.choices[0].message.content.strip()
        return recommendation
    
    except Exception as e:
        logger.error(f"AI recommendation failed: {e}")
        return "AI recommendation unavailable. Please review signal details manually."
```

**Deliverable**: `src/telemetry/ai_recommender.py`

---

### **Step 1.3: Enhance classified.parquet**

**Objective**: Add `ai_recommendation` column to classified output

**Updated Schema**:
```python
# classified.parquet
columns = [
    'unit',                     # str
    'date',                     # datetime
    'component',                # str
    'component_status',         # str: Normal/Alerta/Anormal
    'signals_evaluation',       # dict: signal-level details
    'ai_recommendation'         # str: NEW - AI-generated advice
]
```

**Integration Point**:
```python
# In component_aggregator.py

def aggregate_components(signal_evaluations, component_mapping, enable_ai=True):
    """
    Roll up signals to components, optionally add AI recommendations
    """
    
    # ... existing aggregation logic ...
    
    # For each component evaluation
    for component_eval in component_evaluations:
        
        # Skip if component is Normal (no recommendation needed)
        if component_eval['component_status'] == 'Normal':
            component_eval['ai_recommendation'] = "Component operating normally."
            continue
        
        # Generate AI recommendation for Alerta/Anormal
        if enable_ai:
            recommendation = generate_ai_recommendation(
                component_eval,
                component_eval['signals_evaluation'],
                historical_context={}  # TODO: Add trend data
            )
            component_eval['ai_recommendation'] = recommendation
        else:
            component_eval['ai_recommendation'] = None
    
    return component_evaluations
```

**Deliverable**: Updated `component_aggregator.py`

---

### **Step 1.4: Enhance machine_status.parquet**

**Objective**: Add AI summary at machine level

**Optional Enhancement**:
```python
# machine_status.parquet - Add optional column
columns = [
    # ... existing columns ...
    'ai_machine_summary'  # str: High-level AI summary of machine health
]
```

**AI Prompt for Machine Summary**:
```
Summarize the overall health of Unit 247 based on component grades:
- Motor: Anormal (Score: 25) - High coolant temp, high exhaust temp
- Brakes: Alerta (Score: 10) - Elevated rear brake temps
- Powertrain: Normal (Score: 0)
- Steering: Normal (Score: 0)

Provide a 1-sentence executive summary for maintenance prioritization.
```

**Deliverable**: Updated `machine_aggregator.py` with optional AI summary

---

### **Step 1.5: Cost Optimization**

**Challenge**: LLM API calls can be expensive at scale

**Strategies**:
1. **Selective Generation**: Only call AI for Alerta/Anormal components
2. **Caching**: Cache recommendations for similar signal patterns
3. **Batch Processing**: Group multiple component evaluations per API call
4. **Fallback Templates**: Use rule-based templates when API unavailable

**Example Caching**:
```python
import hashlib
import json

def get_cached_recommendation(component_eval, signal_details, cache_db):
    """
    Check if similar evaluation exists in cache
    
    Args:
        component_eval: Component evaluation dict
        signal_details: Signal evaluation details
        cache_db: Dictionary or Redis cache
    
    Returns:
        Cached recommendation or None
    """
    
    # Create signature from evaluation
    signature_data = {
        'component': component_eval['component'],
        'status': component_eval['component_status'],
        'critical_signals': sorted([
            (sig, details['grade']) 
            for sig, details in signal_details.items()
            if details['grade'] != 'Normal'
        ])
    }
    
    signature = hashlib.md5(
        json.dumps(signature_data, sort_keys=True).encode()
    ).hexdigest()
    
    # Check cache
    return cache_db.get(signature)
```

**Deliverable**: `src/telemetry/recommendation_cache.py`

---

### **Step 1.6: Dashboard Integration**

**Objective**: Display AI recommendations in Telemetry dashboard

**Visualization Updates**:
1. **Tab 2 (Component Analysis)**: 
   - Add "AI Insights" card below component summary
   - Display recommendation with icon (💡)

2. **Tab 3 (Signal Trends)**:
   - Show component AI recommendation in sidebar
   - Link to evidence (time series charts)

**Example Layout**:
```
┌────────────────────────────────────────────────────────────┐
│ 💡 AI Recommendation - Motor (Unit 247)                   │
│                                                            │
│ "Engine coolant temperature has exceeded normal range     │
│  consistently over the past 3 weeks, with a sudden spike  │
│  in left exhaust temperature in the last 48 hours. This   │
│  pattern suggests potential cooling system degradation or │
│  thermostat malfunction.                                  │
│                                                            │
│  Recommended Action: Inspect cooling system and           │
│  thermostat. Check coolant levels and radiator condition. │
│                                                            │
│  Urgency: Within 24 hours"                                │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Deliverable**: Updated Dash tab components

---

### Phase 1 Success Metrics

- ✅ AI recommendations generated for 100% of Anormal components
- ✅ Average generation time <2 seconds per recommendation
- ✅ User survey: 80%+ find recommendations helpful
- ✅ Cost: <$0.10 per analysis run (API costs)

---

## 📅 Phase 2: Enhanced Detection Methods

**Duration**: 3-4 weeks  
**Goal**: Add temporal and multivariate analysis methods

### Overview

The MVP uses static percentile baselines. This phase adds:
1. **Rate of Change Detection** (catch sudden failures)
2. **Rolling Window Statistics** (adapt to trends)
3. **Multivariate Correlation Analysis** (detect component-level issues)

---

### **Step 2.1: Rate of Change Detection**

**Objective**: Flag rapid sensor value changes

**Method**: Calculate first derivative and compare to historical variability

**Implementation**:
```python
# rate_of_change_detector.py

def detect_rate_of_change_anomalies(current_data, historical_data, signal):
    """
    Flag signals with abnormal rate of change
    
    Args:
        current_data: DataFrame with recent readings (last 24h)
        historical_data: DataFrame for baseline (last 4 weeks)
        signal: Signal name to analyze
    
    Returns:
        List of anomaly timestamps with severity
    """
    
    # Calculate rate of change (derivative)
    current_data['delta'] = current_data[signal].diff()
    current_data['delta_per_hour'] = (
        current_data['delta'] / 
        current_data['Fecha'].diff().dt.total_seconds() * 3600
    )
    
    # Calculate baseline rate variability
    historical_data['delta'] = historical_data[signal].diff()
    historical_data['delta_per_hour'] = (
        historical_data['delta'] / 
        historical_data['Fecha'].diff().dt.total_seconds() * 3600
    )
    
    baseline_std = historical_data['delta_per_hour'].std()
    baseline_mean = historical_data['delta_per_hour'].mean()
    
    # Flag anomalies
    anomalies = []
    for idx, row in current_data.iterrows():
        rate = row['delta_per_hour']
        
        # Check if rate exceeds 3 standard deviations
        if abs(rate - baseline_mean) > 3 * baseline_std:
            anomalies.append({
                'timestamp': row['Fecha'],
                'signal': signal,
                'rate': rate,
                'baseline_mean': baseline_mean,
                'baseline_std': baseline_std,
                'severity': 'Anormal' if abs(rate - baseline_mean) > 4 * baseline_std else 'Alerta'
            })
    
    return anomalies
```

**Integration**: Add as supplementary check in `signal_evaluator.py`

**Deliverable**: `src/telemetry/rate_of_change_detector.py`

---

### **Step 2.2: Rolling Window Statistics**

**Objective**: Adapt baselines to recent trends

**Method**: Use last N days instead of fixed historical weeks

**Implementation**:
```python
# rolling_baseline_calculator.py

def calculate_rolling_baselines(current_data, signal, window_days=7):
    """
    Calculate rolling baselines using exponential moving statistics
    
    Args:
        current_data: DataFrame with time series data
        signal: Signal name
        window_days: Size of rolling window
    
    Returns:
        DataFrame with rolling mean, std, percentiles
    """
    
    # Sort by time
    data = current_data.sort_values('Fecha').copy()
    
    # Calculate rolling statistics
    window = f'{window_days}D'
    data['rolling_mean'] = data[signal].rolling(window=window, min_periods=1).mean()
    data['rolling_std'] = data[signal].rolling(window=window, min_periods=1).std()
    data['rolling_P95'] = data[signal].rolling(window=window, min_periods=1).quantile(0.95)
    data['rolling_P99'] = data[signal].rolling(window=window, min_periods=1).quantile(0.99)
    
    return data
```

**Usage**: Compare current reading against rolling baseline instead of static baseline

**Deliverable**: `src/telemetry/rolling_baseline_calculator.py`

---

### **Step 2.3: Multivariate Correlation Analysis**

**Objective**: Detect when signal relationships break down

**Method**: Monitor correlation matrices for deviations

**Example**:
- Normally, `EngCoolTemp` and `EngOilTemp` correlate (both rise together)
- If `EngCoolTemp` rises but `EngOilTemp` doesn't → Potential cooling issue

**Implementation**:
```python
# correlation_analyzer.py

def detect_correlation_anomalies(current_data, historical_data, component_signals):
    """
    Detect when signal correlations deviate from baseline
    
    Args:
        current_data: DataFrame with recent readings
        historical_data: DataFrame for baseline
        component_signals: List of signals in component (e.g., Motor signals)
    
    Returns:
        Dict with correlation anomaly details
    """
    
    # Calculate baseline correlation matrix
    baseline_corr = historical_data[component_signals].corr()
    
    # Calculate current correlation matrix
    current_corr = current_data[component_signals].corr()
    
    # Calculate difference
    corr_diff = (current_corr - baseline_corr).abs()
    
    # Flag large deviations (e.g., correlation changed by >0.3)
    anomalies = []
    for i, sig1 in enumerate(component_signals):
        for j, sig2 in enumerate(component_signals):
            if i < j:  # Upper triangle only
                if corr_diff.loc[sig1, sig2] > 0.3:
                    anomalies.append({
                        'signal1': sig1,
                        'signal2': sig2,
                        'baseline_correlation': baseline_corr.loc[sig1, sig2],
                        'current_correlation': current_corr.loc[sig1, sig2],
                        'deviation': corr_diff.loc[sig1, sig2]
                    })
    
    return anomalies
```

**Integration**: Run at component level, add findings to `component_eval['correlation_anomalies']`

**Deliverable**: `src/telemetry/correlation_analyzer.py`

---

### **Step 2.4: Combined Grading Logic**

**Objective**: Integrate multiple detection methods

**Strategy**: Use ensemble approach where any method can trigger alert

```python
# enhanced_signal_evaluator.py

def evaluate_signal_enhanced(
    signal, value, state, baselines, 
    enable_rate_of_change=True,
    enable_rolling_baseline=True
):
    """
    Enhanced signal evaluation using multiple methods
    
    Returns:
        Dict with grade, score, and detection method(s) that triggered
    """
    
    results = {
        'signal': signal,
        'value': value,
        'state': state,
        'grade': 'Normal',
        'score': 0,
        'triggered_by': []
    }
    
    # Method 1: Percentile baseline (original MVP method)
    percentile_grade, percentile_score = grade_signal_value(value, baselines)
    if percentile_grade != 'Normal':
        results['grade'] = percentile_grade
        results['score'] = max(results['score'], percentile_score)
        results['triggered_by'].append('percentile_baseline')
    
    # Method 2: Rate of change (if enabled)
    if enable_rate_of_change:
        rate_anomalies = detect_rate_of_change_anomalies(...)
        if rate_anomalies:
            rate_grade = rate_anomalies[0]['severity']
            results['grade'] = max_severity(results['grade'], rate_grade)
            results['score'] = max(results['score'], 5)
            results['triggered_by'].append('rate_of_change')
    
    # Method 3: Rolling baseline (if enabled)
    if enable_rolling_baseline:
        rolling_grade = evaluate_against_rolling_baseline(...)
        if rolling_grade != 'Normal':
            results['grade'] = max_severity(results['grade'], rolling_grade)
            results['score'] = max(results['score'], 5)
            results['triggered_by'].append('rolling_baseline')
    
    return results


def max_severity(grade1, grade2):
    """Return the more severe grade"""
    severity_order = ['Normal', 'Alerta', 'Anormal']
    return grade1 if severity_order.index(grade1) > severity_order.index(grade2) else grade2
```

**Deliverable**: `src/telemetry/enhanced_signal_evaluator.py`

---

### Phase 2 Success Metrics

- ✅ Early detection: Catch failures 12-24h earlier than static baselines
- ✅ Reduced false positives: <10% false positive rate
- ✅ Coverage: Detect 95%+ of known failure modes
- ✅ Performance: Processing time increase <30%

---

## 📅 Phase 3: Advanced Analytics

**Duration**: 4-6 weeks  
**Goal**: Introduce machine learning and predictive capabilities

### Overview

This phase adds:
1. **Isolation Forest** for multivariate anomaly detection
2. **Time Series Forecasting** to predict future failures
3. **Clustering** to identify operational profiles

---

### **Step 3.1: Isolation Forest Implementation**

**Objective**: ML-based anomaly detection

**Method**: Train Isolation Forest on "normal" historical data

**Implementation**:
```python
# ml_anomaly_detector.py

from sklearn.ensemble import IsolationForest

def train_isolation_forest(historical_data, component_signals):
    """
    Train Isolation Forest on historical normal data
    
    Args:
        historical_data: DataFrame with historical readings
        component_signals: List of signals to include as features
    
    Returns:
        Trained IsolationForest model
    """
    
    # Prepare features
    X = historical_data[component_signals].dropna()
    
    # Train model
    model = IsolationForest(
        contamination=0.05,  # Expect 5% outliers in historical data
        random_state=42,
        n_estimators=100
    )
    model.fit(X)
    
    return model


def detect_ml_anomalies(current_data, model, component_signals):
    """
    Use trained model to detect anomalies
    
    Returns:
        DataFrame with anomaly scores and predictions
    """
    
    X = current_data[component_signals].dropna()
    
    # Predict (-1 = anomaly, 1 = normal)
    predictions = model.predict(X)
    
    # Get anomaly scores (lower = more anomalous)
    scores = model.decision_function(X)
    
    current_data['ml_anomaly'] = predictions
    current_data['ml_score'] = scores
    
    return current_data
```

**Integration**: Add as optional detection method in Phase 2's ensemble

**Deliverable**: `src/telemetry/ml_anomaly_detector.py`

---

### **Step 3.2: Time Series Forecasting**

**Objective**: Predict when component will reach critical state

**Method**: Use Prophet or ARIMA to forecast sensor trajectories

**Implementation**:
```python
# forecasting.py

from prophet import Prophet

def forecast_signal_trajectory(historical_data, signal, forecast_days=7):
    """
    Forecast signal values for next N days
    
    Args:
        historical_data: DataFrame with historical readings
        signal: Signal to forecast
        forecast_days: Number of days to forecast
    
    Returns:
        DataFrame with forecasted values and confidence intervals
    """
    
    # Prepare data for Prophet
    df_prophet = historical_data[['Fecha', signal]].rename(
        columns={'Fecha': 'ds', signal: 'y'}
    )
    
    # Train model
    model = Prophet(
        changepoint_prior_scale=0.05,
        seasonality_mode='multiplicative'
    )
    model.fit(df_prophet)
    
    # Make future dataframe
    future = model.make_future_dataframe(periods=forecast_days, freq='H')
    
    # Forecast
    forecast = model.predict(future)
    
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]


def predict_time_to_failure(forecast, thresholds):
    """
    Estimate when forecasted values will exceed thresholds
    
    Args:
        forecast: DataFrame from forecast_signal_trajectory
        thresholds: Dict with 'Alerta' and 'Anormal' threshold values
    
    Returns:
        Dict with estimated time to each threshold
    """
    
    results = {}
    
    # Check when forecast exceeds Alerta threshold
    alerta_violations = forecast[forecast['yhat'] > thresholds['Alerta']]
    if not alerta_violations.empty:
        results['time_to_alerta'] = alerta_violations.iloc[0]['ds']
    else:
        results['time_to_alerta'] = None
    
    # Check when forecast exceeds Anormal threshold
    anormal_violations = forecast[forecast['yhat'] > thresholds['Anormal']]
    if not anormal_violations.empty:
        results['time_to_anormal'] = anormal_violations.iloc[0]['ds']
    else:
        results['time_to_anormal'] = None
    
    return results
```

**Use Case**: "Motor coolant temp projected to reach critical in 3 days"

**Deliverable**: `src/telemetry/forecasting.py`

---

### **Step 3.3: Operational Clustering**

**Objective**: Automatically identify different operating modes

**Method**: Use DBSCAN or K-Means to cluster operational states

**Implementation**:
```python
# operational_clustering.py

from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

def cluster_operational_modes(historical_data, feature_columns):
    """
    Cluster operational modes based on sensor patterns
    
    Args:
        historical_data: DataFrame with telemetry
        feature_columns: Signals to use for clustering
    
    Returns:
        DataFrame with cluster labels
    """
    
    # Prepare features
    X = historical_data[feature_columns].dropna()
    
    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Cluster
    clusterer = DBSCAN(eps=0.5, min_samples=50)
    clusters = clusterer.fit_predict(X_scaled)
    
    historical_data['operational_cluster'] = clusters
    
    return historical_data


def get_cluster_characteristics(clustered_data, cluster_id):
    """
    Describe characteristics of a cluster
    
    Returns:
        Dict with cluster statistics
    """
    
    cluster_data = clustered_data[
        clustered_data['operational_cluster'] == cluster_id
    ]
    
    characteristics = {
        'cluster_id': cluster_id,
        'sample_count': len(cluster_data),
        'avg_payload': cluster_data['Payload'].mean(),
        'avg_speed': cluster_data['GroundSpd'].mean(),
        'avg_elevation': cluster_data['GPSElevation'].mean(),
        'predominant_state': cluster_data['Estado'].mode()[0]
    }
    
    return characteristics
```

**Use Case**: Automatically discover operation modes beyond manual Estado labels

**Deliverable**: `src/telemetry/operational_clustering.py`

---

### Phase 3 Success Metrics

- ✅ Isolation Forest: 95%+ accuracy on validation set
- ✅ Forecasting: Predict failures 24-72h in advance with 80%+ accuracy
- ✅ Clustering: Discover 3-5 meaningful operational modes per unit type

---

## 📅 Phase 4: Optimization & Scaling

**Duration**: 2-3 weeks  
**Goal**: Improve performance and reduce costs

### Overview

As the system matures, optimize:
1. **Processing Speed**: Handle larger datasets faster
2. **Storage Efficiency**: Reduce parquet file sizes
3. **Compute Costs**: Minimize cloud/API expenses

---

### **Step 4.1: Incremental Processing**

**Objective**: Only process new data, not full recomputation

**Strategy**: Track last processed timestamp, load only new rows

**Implementation**:
```python
# incremental_processor.py

def get_last_processed_timestamp(client):
    """
    Retrieve last processed timestamp from metadata
    
    Returns:
        datetime or None
    """
    
    metadata_file = f'data/telemetry/golden/{client}/metadata.json'
    
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
            return pd.to_datetime(metadata['last_processed_timestamp'])
    
    return None


def load_new_data_only(client, last_timestamp):
    """
    Load only data newer than last_timestamp
    
    Returns:
        DataFrame with new rows
    """
    
    # Load current week
    current_week_data = load_telemetry_week(client, week, year)
    
    # Filter to new rows only
    if last_timestamp is not None:
        current_week_data = current_week_data[
            current_week_data['Fecha'] > last_timestamp
        ]
    
    return current_week_data
```

**Benefit**: Reduce processing time by 80%+

**Deliverable**: `src/telemetry/incremental_processor.py`

---

### **Step 4.2: Parquet Optimization**

**Objective**: Reduce file sizes and improve read performance

**Strategies**:
1. **Compression**: Use snappy or gzip compression
2. **Column Pruning**: Only load needed columns
3. **Partitioning**: Partition by week/year for faster queries

**Implementation**:
```python
# Optimized parquet writing
df.to_parquet(
    'data/telemetry/golden/cda/machine_status.parquet',
    compression='snappy',
    index=False,
    engine='pyarrow'
)

# Optimized parquet reading (load only needed columns)
df = pd.read_parquet(
    'data/telemetry/silver/cda/Telemetry_Wide_With_States/Week10Year2025.parquet',
    columns=['Fecha', 'Unit', 'EngCoolTemp', 'EngOilPres'],  # Subset
    engine='pyarrow'
)
```

**Benefit**: 50%+ reduction in file size, 2-3x faster reads

---

### **Step 4.3: Caching Strategy**

**Objective**: Avoid redundant computations

**Implementation**:
```python
# Use joblib for function result caching
from joblib import Memory

memory = Memory('cache/', verbose=0)

@memory.cache
def calculate_baselines(historical_data, signals, percentiles):
    """Cached baseline calculation"""
    # ... baseline logic ...
    return baselines
```

**Benefit**: Skip baseline recalculation if historical data unchanged

---

### **Step 4.4: Parallel Processing**

**Objective**: Process multiple units simultaneously

**Implementation**:
```python
# Use multiprocessing for unit-level parallelization
from multiprocessing import Pool

def process_unit(unit_data):
    """Process one unit's telemetry"""
    # ... evaluation logic ...
    return unit_results

# Parallel processing
with Pool(processes=4) as pool:
    results = pool.map(process_unit, unit_data_list)
```

**Benefit**: 3-4x speedup on multi-core machines

---

### Phase 4 Success Metrics

- ✅ Processing time: <2 minutes for full week's data
- ✅ Storage: 30%+ reduction in parquet sizes
- ✅ Cost: 50%+ reduction in compute/API costs

---

## 🗺️ Long-Term Roadmap

### Future Enhancements (6-12 months)

#### **1. Feedback Loop Integration**
- Track maintenance actions taken based on alerts
- Train models to learn which alerts lead to actual repairs
- Reduce false positives through supervised learning

#### **2. Fleet-Wide Pattern Detection**
- Identify common failure modes across units
- "Unit 247's motor issue is similar to Unit 312 last month"
- Enable proactive maintenance on similar units

#### **3. Maintenance Optimization**
- Recommend optimal maintenance timing based on alert patterns
- Balance cost of downtime vs. cost of early intervention
- Integration with maintenance scheduling systems

#### **4. Real-Time Streaming**
- Transition from batch (8-12h) to streaming analysis
- Use Apache Kafka or AWS Kinesis
- Enable real-time dashboard updates

#### **5. Computer Vision Integration**
- Analyze GPS heatmaps to identify problematic routes
- Correlate terrain features with sensor patterns
- "Brake issues always occur on this downhill section"

---

## 📊 Improvement Decision Matrix

| Enhancement | Complexity | Value | Priority |
|-------------|-----------|-------|----------|
| AI Recommendations | Medium | High | **Phase 1** |
| Rate of Change Detection | Low | Medium | **Phase 2** |
| Rolling Baselines | Medium | Medium | **Phase 2** |
| Correlation Analysis | Medium | High | **Phase 2** |
| Isolation Forest | High | Medium | Phase 3 |
| Forecasting | High | High | Phase 3 |
| Operational Clustering | Medium | Medium | Phase 3 |
| Incremental Processing | Low | High | **Phase 4** |
| Parquet Optimization | Low | Medium | **Phase 4** |
| Parallel Processing | Medium | High | **Phase 4** |

**Bold = High Priority**

---

## ✅ Success Tracking

### Key Metrics to Monitor

1. **Detection Quality**:
   - False positive rate
   - False negative rate
   - Early detection lead time

2. **User Adoption**:
   - % of alerts investigated
   - % of alerts leading to maintenance
   - User satisfaction scores

3. **Technical Performance**:
   - Processing time per run
   - Storage costs
   - API costs (for AI recommendations)

4. **Business Impact**:
   - Reduction in unplanned downtime
   - Maintenance cost savings
   - Equipment lifespan improvements

---

## 🔄 Iteration Process

After each phase:
1. **Deploy**: Roll out enhancement to production
2. **Monitor**: Track metrics for 2-4 weeks
3. **Gather Feedback**: Interview maintenance team
4. **Analyze**: Compare before/after metrics
5. **Adjust**: Tune thresholds, prompts, or methods
6. **Document**: Update this plan with learnings

---

## 📚 Documentation Updates

Each phase requires:
- ✅ Updated code documentation (docstrings)
- ✅ User guide additions (new features explained)
- ✅ Technical specifications (architecture changes)
- ✅ Testing protocols (new test cases)

---

## 🎯 Final Goal

**Vision**: A fully automated, intelligent telemetry monitoring system that:
- Detects failures before they occur
- Explains issues in human-readable terms
- Optimizes maintenance schedules
- Continuously learns and improves

**Outcome**: Mining operations run more efficiently with less downtime and lower maintenance costs.

---

**Document Status**: ✅ Ready for Phased Execution  
**Next Action**: Begin Phase 1 - AI Recommendations (after MVP complete)  
**Estimated Timeline**: 12-16 weeks for all 4 phases
