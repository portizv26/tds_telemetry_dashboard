"""
Main Training and Inference Script

Coordinates the execution of the full health index pipeline:
1. Loads telemetry data
2. Splits into train/test (last 6 weeks = test)
3. Trains models for all components
4. Generates inferences for the full test set
5. Computes health indices
6. Saves all artifacts and results

Usage:
    python scripts/train_and_infer_health_index.py --client cda --run-optimization
    python scripts/train_and_infer_health_index.py --client cda --component Motor
    python scripts/train_and_infer_health_index.py --client cda --no-optimization --no-mlflow
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from health_index import io, pipeline


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train health index models and generate inferences"
    )
    
    parser.add_argument(
        "--client",
        type=str,
        default="cda",
        help="Client name (default: cda)"
    )
    
    parser.add_argument(
        "--component",
        type=str,
        default=None,
        help="Specific component to process (if None, processes all components)"
    )
    
    parser.add_argument(
        "--run-optimization",
        action="store_true",
        default=False,
        help="Run Optuna hyperparameter optimization (default: False)"
    )
    
    parser.add_argument(
        "--no-optimization",
        action="store_true",
        default=False,
        help="Skip hyperparameter optimization and use defaults"
    )
    
    parser.add_argument(
        "--use-mlflow",
        action="store_true",
        default=True,
        help="Use MLflow for experiment tracking (default: True)"
    )
    
    parser.add_argument(
        "--no-mlflow",
        action="store_true",
        default=False,
        help="Disable MLflow tracking"
    )
    
    parser.add_argument(
        "--test-weeks",
        type=int,
        default=6,
        help="Number of weeks to use for testing (default: 6)"
    )
    
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()
    
    # Handle optimization flags
    run_optimization = args.run_optimization and not args.no_optimization
    
    # Handle MLflow flags
    use_mlflow = args.use_mlflow and not args.no_mlflow
    
    print("\n" + "=" * 80)
    print("HEALTH INDEX TRAINING AND INFERENCE PIPELINE")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Client: {args.client}")
    print(f"  Component: {args.component if args.component else 'ALL'}")
    print(f"  Run Optimization: {run_optimization}")
    print(f"  Use MLflow: {use_mlflow}")
    print(f"  Test Weeks: {args.test_weeks}")
    print("")
    
    # Load component mapping
    print("Loading component mapping...")
    component_mapping = io.load_component_mapping()
    
    if args.component:
        # Single component execution
        print(f"\nProcessing single component: {args.component}")
        
        components = component_mapping.get('components', {})
        
        if args.component not in components:
            print(f"ERROR: Component '{args.component}' not found in mapping")
            print(f"Available components: {list(components.keys())}")
            return 1
        
        component_info = components[args.component]
        signal_cols = component_info.get('signals', [])
        
        result = pipeline.run_component_pipeline(
            client=args.client,
            component=args.component,
            signal_cols=signal_cols,
            df=None,  # Will load from disk
            run_optimization=run_optimization,
            use_mlflow=use_mlflow,
            test_weeks=args.test_weeks,
        )
        
        print(f"\nResult: {result}")
        
        if result.get('status') == 'success':
            print("\n✓ Pipeline completed successfully!")
            return 0
        else:
            print(f"\n✗ Pipeline failed: {result.get('reason', 'unknown error')}")
            return 1
    
    else:
        # All components execution
        print("\nProcessing all components...")
        
        results = pipeline.run_all_components_pipeline(
            client=args.client,
            component_mapping=component_mapping,
            run_optimization=run_optimization,
            use_mlflow=use_mlflow,
        )
        
        # Check results
        success_count = sum(1 for r in results if r.get('status') == 'success')
        total_count = len(results)
        
        print(f"\n\n{'=' * 80}")
        print(f"PIPELINE SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total components: {total_count}")
        print(f"Successful: {success_count}")
        print(f"Failed: {total_count - success_count}")
        
        if success_count == total_count:
            print("\n✓ All components completed successfully!")
            return 0
        else:
            print("\n⚠ Some components failed. Check logs for details.")
            return 1


if __name__ == "__main__":
    sys.exit(main())
