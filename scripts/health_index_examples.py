"""
Example: Using the Health Index Module Programmatically

This example demonstrates how to use the health_index package for:
1. Training a model for a single component
2. Running inference on test data
3. Computing health indices
4. Loading trained models for new predictions
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from health_index import io, pipeline, config


def example_single_component():
    """Example 1: Train and infer for a single component."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Single Component Pipeline")
    print("=" * 80)
    
    # Load component mapping
    component_mapping = io.load_component_mapping()
    
    # Get Motor component signals
    motor_info = component_mapping['components']['Motor']
    signal_cols = motor_info['signals']
    
    print(f"\nMotor signals: {signal_cols}")
    
    # Run pipeline
    result = pipeline.run_component_pipeline(
        client='cda',
        component='Motor',
        signal_cols=signal_cols,
        run_optimization=False,  # Set to True for hyperparameter optimization
        use_mlflow=True,
        test_weeks=6,
    )
    
    print(f"\nResult:")
    print(f"  Status: {result['status']}")
    print(f"  Model: {result.get('model_path')}")
    print(f"  Mean Health Index: {result.get('health_index_mean', 0):.2f}")


def example_all_components():
    """Example 2: Train and infer for all components."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: All Components Pipeline")
    print("=" * 80)
    
    # Load component mapping
    component_mapping = io.load_component_mapping()
    
    # Run pipeline for all components
    results = pipeline.run_all_components_pipeline(
        client='cda',
        component_mapping=component_mapping,
        run_optimization=False,  # Set to True for hyperparameter optimization
        use_mlflow=True,
    )
    
    print("\nResults Summary:")
    for result in results:
        status = result.get('status', 'unknown')
        component = result.get('component', 'unknown')
        hi_mean = result.get('health_index_mean', 0)
        print(f"  {component}: {status} (HI: {hi_mean:.2f})")


def example_load_and_infer():
    """Example 3: Load a trained model and run inference on new data."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Load Trained Model and Infer")
    print("=" * 80)
    
    from health_index import training, artifacts, scaling, inference, health_index
    
    # Specify component
    client = 'cda'
    component = 'Motor'
    
    # Load trained model
    model_dir = config.get_model_dir(client, component)
    model_path = config.get_model_path(client, component)
    
    print(f"\nLoading model from: {model_path}")
    model = training.load_model(model_path)
    
    # Load artifacts (scalers, encoder, feature list, etc.)
    print(f"Loading artifacts from: {model_dir}")
    arts = artifacts.load_artifacts(model_dir)
    
    print(f"\nLoaded artifacts:")
    print(f"  Features: {len(arts['feature_cols'])}")
    print(f"  Window size: {arts['hyperparams']['window_size']}")
    print(f"  Scalers: {len(arts['scalers'])} units")
    
    # Load new test data
    print(f"\nLoading test data...")
    df_test = io.load_telemetry_data(client)
    
    # You would typically filter to the new time period here
    # df_test = df_test[df_test['Fecha'] >= new_start_date]
    
    # Apply same preprocessing pipeline
    from health_index import preprocessing, cycles
    
    print("Preprocessing...")
    df_test = preprocessing.clean_outliers(df_test)
    df_test = preprocessing.fill_categorical_missing(df_test, config.CAT_COLS)
    df_test = cycles.detect_cycles(df_test)
    
    # Get numeric columns for this component
    component_mapping = io.load_component_mapping()
    signal_cols = component_mapping['components'][component]['signals']
    num_cols = [col for col in signal_cols if col in df_test.columns]
    
    df_test = cycles.process_cycles(df_test, num_cols)
    
    # Apply saved scalers and encoder
    print("Applying transformations...")
    df_test_scaled = scaling.apply_scalers_per_unit(
        df_test, num_cols, arts['scalers']
    )
    df_test_scaled = scaling.apply_categorical_encoder(
        df_test_scaled, arts['encoder'], config.CAT_COLS
    )
    
    # Run inference
    print("Running inference...")
    inference_results = inference.predict_over_horizon(
        df_test_scaled,
        model,
        arts['feature_cols'],
        arts['hyperparams']['window_size'],
        stride=1,
    )
    
    # Compute health index
    print("Computing health index...")
    hi_df = health_index.compute_health_index_from_inference(inference_results)
    
    # Display summary
    print(f"\nInference completed:")
    print(f"  Windows processed: {len(hi_df)}")
    print(f"  Mean health index: {hi_df['health_index'].mean():.2f}")
    print(f"  Units analyzed: {hi_df['Unit'].nunique()}")
    
    # Show per-unit summary
    unit_summary = health_index.aggregate_health_index_per_unit(hi_df)
    print(f"\nPer-unit summary:")
    print(unit_summary[['Unit', 'health_index', 'reconstruction_error_mean']])


def example_custom_pipeline():
    """Example 4: Build a custom pipeline with individual modules."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Custom Pipeline with Individual Modules")
    print("=" * 80)
    
    from health_index import (
        preprocessing, cycles, labeling, scaling, 
        windowing, modeling, training
    )
    
    client = 'cda'
    
    # 1. Load and prepare data
    print("\n[1] Loading data...")
    df = io.load_telemetry_data(client)
    
    # 2. Preprocess
    print("[2] Preprocessing...")
    df = preprocessing.clean_outliers(df)
    df = preprocessing.fill_categorical_missing(df, config.CAT_COLS)
    
    # 3. Detect and process cycles
    print("[3] Processing cycles...")
    df = cycles.detect_cycles(df)
    
    # Get signals for Motor component
    component_mapping = io.load_component_mapping()
    signal_cols = component_mapping['components']['Motor']['signals']
    num_cols = [col for col in signal_cols if col in df.columns]
    
    df = cycles.process_cycles(df, num_cols)
    
    # 4. Create labels
    print("[4] Creating labels...")
    df = labeling.create_labels(df, num_cols)
    
    # 5. Scale features
    print("[5] Scaling features...")
    scalers = scaling.fit_scalers_per_unit(df, num_cols)
    encoder = scaling.fit_categorical_encoder(df, config.CAT_COLS)
    
    df_scaled = scaling.apply_scalers_per_unit(df, num_cols, scalers)
    df_scaled = scaling.apply_categorical_encoder(df_scaled, encoder, config.CAT_COLS)
    
    # Feature columns
    feature_cols = [col for col in df_scaled.columns 
                   if col not in [config.UNIT_COL, config.TIME_COL, 'cycle_id', 
                                 'Label', 'created_by_reindex', 'imputed_any']]
    
    # 6. Create windows
    print("[6] Creating windows...")
    window_size = 60  # 1 hour
    X, meta = windowing.create_windows(df_scaled, feature_cols, window_size, stride=1)
    
    print(f"  Created {len(X):,} windows of shape {X.shape}")
    
    # 7. Split for training/validation
    val_split = int(len(X) * 0.8)
    X_train = X[:val_split]
    X_val = X[val_split:]
    
    # 8. Build and train model
    print("[7] Building and training model...")
    model = modeling.build_lstm_autoencoder(
        window_size=window_size,
        n_features=len(feature_cols),
        lstm_units_1=16,
        lstm_units_2=8,
        dropout_rate=0.2,
        learning_rate=0.001,
    )
    
    hyperparams = {
        'window_size': window_size,
        'lstm_units_1': 16,
        'lstm_units_2': 8,
        'dropout_rate': 0.2,
        'learning_rate': 0.001,
        'batch_size': 32,
        'epochs': 10,  # Use more epochs in production
        'early_stopping_patience': 3,
    }
    
    model, history = training.train_model(
        X_train, X_val, hyperparams, len(feature_cols),
        component='Motor', client=client,
        use_mlflow=False,  # Disable for this example
    )
    
    print(f"\nTraining completed!")
    print(f"  Final train loss: {history['loss'][-1]:.6f}")
    print(f"  Final val loss: {history['val_loss'][-1]:.6f}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Health Index Module Examples")
    parser.add_argument(
        "--example",
        type=int,
        choices=[1, 2, 3, 4],
        default=1,
        help="Which example to run (1-4)"
    )
    
    args = parser.parse_args()
    
    if args.example == 1:
        example_single_component()
    elif args.example == 2:
        example_all_components()
    elif args.example == 3:
        example_load_and_infer()
    elif args.example == 4:
        example_custom_pipeline()
