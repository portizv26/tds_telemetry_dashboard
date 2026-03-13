"""
Pipeline Module

Orchestrates the complete health index modeling workflow.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta

from . import config
from . import io
from . import preprocessing
from . import cycles
from . import labeling
from . import scaling
from . import windowing
from . import modeling
from . import optimization
from . import training
from . import inference
from . import health_index as hi
from . import artifacts


def run_component_pipeline(
    client: str,
    component: str,
    signal_cols: List[str],
    df: pd.DataFrame = None,
    run_optimization: bool = True,
    use_mlflow: bool = True,
    test_weeks: int = config.WEEKS_TO_TEST,
) -> Dict[str, Any]:
    """
    Execute complete pipeline for a single component.
    
    Args:
        client: Client name (e.g., 'cda')
        component: Component name (e.g., 'Motor')
        signal_cols: List of signal column names for this component
        df: Pre-loaded DataFrame (if None, will load from disk)
        run_optimization: Whether to run Optuna hyperparameter optimization
        use_mlflow: Whether to use MLflow tracking
        test_weeks: Number of weeks to reserve for testing
    
    Returns:
        Dictionary with component, status, and results
    """
    print("=" * 80)
    print(f"PIPELINE: {client} - {component}")
    print("=" * 80)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = config.get_model_dir(client, component)
    
    # ========================================
    # 1. LOAD DATA
    # ========================================
    if df is None:
        print("\n[1/12] Loading data...")
        df = io.load_telemetry_data(client)
    else:
        print("\n[1/12] Using provided data...")
    
    # ========================================
    # 2. TRAIN/TEST SPLIT
    # ========================================
    print(f"\n[2/12] Splitting train/test (last {test_weeks} weeks = test)...")
    
    max_date = df[config.TIME_COL].max()
    test_start_date = max_date - timedelta(weeks=test_weeks)
    
    df_train = df[df[config.TIME_COL] < test_start_date].copy()
    df_test = df[df[config.TIME_COL] >= test_start_date].copy()
    
    print(f"  Train: {len(df_train):,} rows ({df_train[config.TIME_COL].min()} to {df_train[config.TIME_COL].max()})")
    print(f"  Test: {len(df_test):,} rows ({df_test[config.TIME_COL].min()} to {df_test[config.TIME_COL].max()})")
    
    # ========================================
    # 3. PREPROCESSING
    # ========================================
    print("\n[3/12] Cleaning outliers...")
    df_train = preprocessing.clean_outliers(df_train)
    df_test = preprocessing.clean_outliers(df_test)
    
    df_train = preprocessing.fill_categorical_missing(df_train, config.CAT_COLS)
    df_test = preprocessing.fill_categorical_missing(df_test, config.CAT_COLS)
    
    # ========================================
    # 4. CYCLE DETECTION
    # ========================================
    print("\n[4/12] Detecting cycles...")
    df_train = cycles.detect_cycles(df_train)
    df_test = cycles.detect_cycles(df_test)
    
    # ========================================
    # 5. CYCLE INTERPOLATION
    # ========================================
    print("\n[5/12] Processing and interpolating cycles...")
    
    # Filter to component signals
    all_num_cols = [col for col in signal_cols if col in df_train.columns]
    
    df_train = cycles.process_cycles(df_train, all_num_cols)
    df_test = cycles.process_cycles(df_test, all_num_cols)
    
    if len(df_train) == 0:
        return {
            "component": component,
            "status": "failed",
            "reason": "No valid training cycles"
        }
    
    # ========================================
    # 6. LABELING (Train only)
    # ========================================
    print("\n[6/12] Creating labels...")
    df_train = labeling.create_labels(df_train, all_num_cols)
    
    # ========================================
    # 7. FEATURE PREPARATION
    # ========================================
    print("\n[7/12] Preparing features...")
    
    # Ensure we have the columns we need
    feature_num_cols = [col for col in all_num_cols if col in df_train.columns]
    
    # Fit scalers on training data (per unit)
    print("  Fitting per-unit scalers...")
    unit_scalers = scaling.fit_scalers_per_unit(df_train, feature_num_cols)
    
    # Fit categorical encoder
    print("  Fitting categorical encoder...")
    cat_encoder = scaling.fit_categorical_encoder(df_train, config.CAT_COLS)
    
    # Apply scaling
    df_train_scaled = scaling.apply_scalers_per_unit(df_train, feature_num_cols, unit_scalers)
    df_test_scaled = scaling.apply_scalers_per_unit(df_test, feature_num_cols, unit_scalers)
    
    # Apply encoding
    df_train_scaled = scaling.apply_categorical_encoder(df_train_scaled, cat_encoder, config.CAT_COLS)
    df_test_scaled = scaling.apply_categorical_encoder(df_test_scaled, cat_encoder, config.CAT_COLS)
    
    # Feature columns after encoding
    feature_cols = [col for col in df_train_scaled.columns 
                   if col not in [config.UNIT_COL, config.TIME_COL, 'cycle_id', 'Label', 
                                 'created_by_reindex', 'imputed_any']]
    
    n_features = len(feature_cols)
    print(f"  Total features: {n_features}")
    
    # ========================================
    # 8. HYPERPARAMETER OPTIMIZATION
    # ========================================
    if run_optimization:
        print("\n[8/12] Running hyperparameter optimization...")
        
        # Create temporary windows for optimization
        # Use a default window size for creating training data
        temp_window_size = config.DEFAULT_HYPERPARAMS['window_size']
        
        X_train_temp, _ = windowing.create_windows(
            df_train_scaled, feature_cols, temp_window_size, stride=5
        )
        
        # Split for validation
        val_split = int(len(X_train_temp) * (1 - config.VALIDATION_SPLIT))
        X_train_opt = X_train_temp[:val_split]
        X_val_opt = X_train_temp[val_split:]
        
        # Run Optuna
        opt_results = optimization.optimize_hyperparameters(
            X_train_opt, X_val_opt, n_features
        )
        
        # Use best hyperparameters
        best_params = opt_results['best_params']
        
        # Save optimization results
        optimization.save_optimization_results(opt_results, model_dir / "optimization_results.json")
    else:
        print("\n[8/12] Skipping optimization, using default hyperparameters...")
        best_params = config.DEFAULT_HYPERPARAMS.copy()
        opt_results = None
    
    # ========================================
    # 9. CREATE TRAINING WINDOWS
# ========================================
    print("\n[9/12] Creating training windows...")
    
    window_size = best_params['window_size']
    
    X_train, meta_train = windowing.create_windows(
        df_train_scaled, feature_cols, window_size, stride=1
    )
    
    # Split for validation
    val_split = int(len(X_train) * (1 - config.VALIDATION_SPLIT))
    X_train_final = X_train[:val_split]
    X_val_final = X_train[val_split:]
    
    print(f"  Train windows: {len(X_train_final):,}")
    print(f"  Val windows: {len(X_val_final):,}")
    
    # ========================================
    # 10. TRAIN MODEL
    # ========================================
    print("\n[10/12] Training model...")
    
    experiment_name = config.get_experiment_name(component, window_size, timestamp)
    
    model, train_history = training.train_model(
        X_train_final,
        X_val_final,
        best_params,
        n_features,
        component,
        client,
        experiment_name,
        use_mlflow,
    )
    
    # Save model
    model_path = config.get_model_path(client, component)
    training.save_model(model, model_path)
    
    # ========================================
    # 11. INFERENCE ON TEST SET
    # ========================================
    print("\n[11/12] Running inference on test set...")
    
    inference_results = inference.predict_over_horizon(
        df_test_scaled,
        model,
        feature_cols,
        window_size,
        stride=1,  # Dense predictions for full coverage
    )
    
    if len(inference_results) == 0:
        return {
            "component": component,
            "status": "failed",
            "reason": "No valid inference results"
        }
    
    # Save inference results
    io.save_inference_data(inference_results, client)
    
    # ========================================
    # 12. COMPUTE HEALTH INDEX
    # ========================================
    print("\n[12/12] Computing health index...")
    
    health_index_df = hi.compute_health_index_from_inference(inference_results)
    
    # Save health index
    io.save_health_index_data(health_index_df, client)
    
    # Aggregate per unit
    unit_summary = hi.aggregate_health_index_per_unit(health_index_df)
    print("\nUnit Summary:")
    print(unit_summary)
    
    # ========================================
    # SAVE ALL ARTIFACTS
    # ========================================
    print("\nSaving artifacts...")
    
    metadata = {
        "component": component,
        "client": client,
        "timestamp": timestamp,
        "n_features": n_features,
        "window_size": window_size,
        "n_train_windows": len(X_train_final),
        "n_test_inference_windows": len(inference_results),
        "train_date_range": [str(df_train[config.TIME_COL].min()), str(df_train[config.TIME_COL].max())],
        "test_date_range": [str(df_test[config.TIME_COL].min()), str(df_test[config.TIME_COL].max())],
    }
    
    artifacts.save_all_artifacts(
        model_dir,
        unit_scalers,
        cat_encoder,
        feature_cols,
        best_params,
        opt_results,
        train_history,
        metadata,
    )
    
    print("\n" + "=" * 80)
    print(f"PIPELINE COMPLETED: {component}")
    print("=" * 80)
    
    return {
        "component": component,
        "status": "success",
        "model_path": str(model_path),
        "health_index_mean": float(health_index_df['health_index'].mean()),
        "n_inference_windows": len(inference_results),
    }


def run_all_components_pipeline(
    client: str,
    component_mapping: Dict[str, Any],
    run_optimization: bool = True,
    use_mlflow: bool = True,
) -> List[Dict[str, Any]]:
    """
    Execute pipeline for all components.
    
    Args:
        client: Client name
        component_mapping: Component to signals mapping from JSON
        run_optimization: Whether to run optimization for each component
        use_mlflow: Whether to use MLflow tracking
    
    Returns:
        List of results dictionaries, one per component
    """
    print("\n" + "=" * 80)
    print(f"RUNNING PIPELINE FOR ALL COMPONENTS: {client}")
    print("=" * 80)
    
    # Load data once
    df = io.load_telemetry_data(client)
    
    results = []
    
    components = component_mapping.get('components', {})
    
    for component_name, component_info in components.items():
        signal_cols = component_info.get('signals', [])
        
        print(f"\n\nProcessing component: {component_name}")
        print(f"Signals: {signal_cols}")
        
        try:
            result = run_component_pipeline(
                client=client,
                component=component_name,
                signal_cols=signal_cols,
                df=df,
                run_optimization=run_optimization,
                use_mlflow=use_mlflow,
            )
            results.append(result)
        except Exception as e:
            print(f"\nERROR processing {component_name}: {e}")
            import traceback
            traceback.print_exc()
            
            results.append({
                "component": component_name,
                "status": "error",
                "error": str(e),
            })
    
    print("\n" + "=" * 80)
    print("ALL COMPONENTS COMPLETED")
    print("=" * 80)
    
    # Summary
    print("\nSummary:")
    for result in results:
        status = result.get('status', 'unknown')
        component = result.get('component', 'unknown')
        print(f"  {component}: {status}")
    
    return results
