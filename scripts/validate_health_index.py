"""
Validation Script for Health Index Module

Quick validation that all modules can be imported and key functions exist.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def validate_imports():
    """Validate all modules can be imported."""
    print("Validating imports...")
    
    try:
        from health_index import (
            config,
            io,
            preprocessing,
            cycles,
            labeling,
            scaling,
            windowing,
            modeling,
            optimization,
            training,
            inference,
            health_index,
            artifacts,
            pipeline,
        )
        print("✓ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def validate_key_functions():
    """Validate key functions exist in each module."""
    print("\nValidating key functions...")
    
    checks = [
        ("config", "get_model_dir"),
        ("io", "load_telemetry_data"),
        ("preprocessing", "clean_outliers"),
        ("cycles", "detect_cycles"),
        ("labeling", "create_labels"),
        ("scaling", "fit_scalers_per_unit"),
        ("windowing", "create_windows"),
        ("modeling", "build_lstm_autoencoder"),
        ("optimization", "optimize_hyperparameters"),
        ("training", "train_model"),
        ("inference", "predict_over_horizon"),
        ("health_index", "compute_health_index_from_inference"),
        ("artifacts", "save_all_artifacts"),
        ("pipeline", "run_component_pipeline"),
    ]
    
    all_passed = True
    
    for module_name, function_name in checks:
        try:
            module = __import__(f"health_index.{module_name}", fromlist=[function_name])
            if hasattr(module, function_name):
                print(f"✓ {module_name}.{function_name}")
            else:
                print(f"✗ {module_name}.{function_name} not found")
                all_passed = False
        except Exception as e:
            print(f"✗ Error checking {module_name}.{function_name}: {e}")
            all_passed = False
    
    return all_passed


def validate_config():
    """Validate configuration values."""
    print("\nValidating configuration...")
    
    try:
        from health_index import config
        
        # Check key paths exist as attributes
        required_attrs = [
            'PROJECT_ROOT',
            'DATA_DIR',
            'MODELS_DIR',
            'UNIT_COL',
            'TIME_COL',
            'OUTLIER_MARGINS',
            'DEFAULT_HYPERPARAMS',
        ]
        
        all_passed = True
        for attr in required_attrs:
            if hasattr(config, attr):
                print(f"✓ config.{attr}")
            else:
                print(f"✗ config.{attr} missing")
                all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        return False


def validate_dependencies():
    """Validate required dependencies are installed."""
    print("\nValidating dependencies...")
    
    required = [
        'pandas',
        'numpy',
        'sklearn',
        'tensorflow',
        'optuna',
        'mlflow',
        'joblib',
        'tqdm',
    ]
    
    all_passed = True
    
    for package in required:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} not installed")
            all_passed = False
    
    return all_passed


def main():
    """Run all validation checks."""
    print("=" * 80)
    print("HEALTH INDEX MODULE VALIDATION")
    print("=" * 80)
    
    results = []
    
    results.append(("Imports", validate_imports()))
    results.append(("Functions", validate_key_functions()))
    results.append(("Configuration", validate_config()))
    results.append(("Dependencies", validate_dependencies()))
    
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    for check_name, passed in results:
        status = "PASSED" if passed else "FAILED"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {check_name}: {status}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ALL VALIDATIONS PASSED")
        print("=" * 80)
        return 0
    else:
        print("✗ SOME VALIDATIONS FAILED")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
