"""
Phase 1 Implementation Test Script
Tests core Phase 1 components without executing full pipeline.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import SignalRegistry, TechniqueConfig
from src.models import Signal, EvaluationWindow
from src.utils import date_utils, file_utils
from src.utils.logger import setup_logger
import logging


def test_signal_registry():
    """Test signal registry loading and queries."""
    print("\n" + "="*80)
    print("TEST 1: Signal Registry")
    print("="*80)
    
    config_path = Path("dataDep/telemetry/config/signal_registry_v1.yaml")
    
    try:
        registry = SignalRegistry(config_path)
        print(f"✓ Loaded registry: {registry}")
        print(f"  - Signals: {len(registry.get_all_signal_names())}")
        print(f"  - Systems: {len(registry.get_all_systems())}")
        
        # Test signal lookup
        signal = registry.get_signal("EngCoolTemp")
        if signal:
            print(f"\n✓ Sample signal: {signal.name}")
            print(f"  - System: {signal.system}")
            print(f"  - Criticality: {signal.criticality}")
            print(f"  - Risk direction: {signal.risk_direction}")
        
        # Test system grouping
        engine_signals = registry.get_signals_by_system("Engine")
        print(f"\n✓ Engine system: {len(engine_signals)} signals")
        for sig in engine_signals[:3]:
            print(f"  - {sig.name}")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def test_technique_config():
    """Test technique configuration loading."""
    print("\n" + "="*80)
    print("TEST 2: Technique Configuration")
    print("="*80)
    
    config_path = Path("dataDep/telemetry/config/technique_config.yaml")
    
    try:
        config = TechniqueConfig(config_path)
        print(f"✓ Loaded config: {config}")
        print(f"  - Techniques: {len(config.get_all_technique_names())}")
        
        # Test technique lookup
        threshold_config = config.get_technique_config("threshold_deviation")
        if threshold_config:
            print(f"\n✓ Threshold Deviation config:")
            print(f"  - Cadence: {threshold_config['cadence']}")
            print(f"  - Lookback: {threshold_config['lookback_window']}")
            print(f"  - Enabled: {threshold_config['enabled']}")
        
        # Test baseline config
        print(f"\n✓ Baseline configuration:")
        print(f"  - Lookback days: {config.get_baseline_lookback_days()}")
        print(f"  - Min samples: {config.get_baseline_min_samples()}")
        print(f"  - Percentiles: {config.get_baseline_percentiles()}")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def test_date_utilities():
    """Test date utility functions."""
    print("\n" + "="*80)
    print("TEST 3: Date Utilities")
    print("="*80)
    
    try:
        from datetime import datetime
        
        # Test week parsing
        week, year = date_utils.parse_week_year("Week21Year2026.parquet")
        print(f"✓ Parsed filename: Week {week}, Year {year}")
        
        # Test week date range
        start, end = date_utils.get_week_date_range(2026, 21)
        print(f"✓ Week 21/2026: {start.date()} to {end.date()}")
        
        # Test lookback calculation
        eval_date = datetime(2026, 5, 25, 23, 59, 59)
        start, end = date_utils.calculate_lookback_period(eval_date, "24h")
        print(f"✓ Lookback 24h from {eval_date.date()}: starts {start.date()}")
        
        # Test baseline version
        version = date_utils.get_current_baseline_version()
        print(f"✓ Current baseline version: {version}")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def test_file_utilities():
    """Test file utility functions."""
    print("\n" + "="*80)
    print("TEST 4: File Utilities")
    print("="*80)
    
    try:
        # Test directory creation
        test_dir = Path("test_output")
        file_utils.ensure_dir(test_dir)
        print(f"✓ Created directory: {test_dir}")
        
        # Test partition path generation
        partition_path = file_utils.get_partition_path(
            Path("data/results"),
            year=2026,
            month=5,
            day=25,
            client="CDA"
        )
        print(f"✓ Partition path: {partition_path}")
        
        # Check if baseline directory exists
        baseline_dir = Path("dataDep/telemetry/analytical_results/baselines")
        if baseline_dir.exists():
            baselines = list(baseline_dir.glob("baseline_*.parquet"))
            print(f"✓ Found {len(baselines)} baseline files")
        else:
            print(f"  (Baseline directory not yet created)")
        
        # Cleanup
        if test_dir.exists():
            test_dir.rmdir()
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def test_data_models():
    """Test data model instantiation."""
    print("\n" + "="*80)
    print("TEST 5: Data Models")
    print("="*80)
    
    try:
        from datetime import datetime
        from src.models import TechniqueResult, SystemHealth, UnitHealth, Event
        
        # Test TechniqueResult
        result = TechniqueResult(
            technique_name="threshold_deviation",
            unit_id="CDA_001",
            client="CDA",
            equipment_model="CAT 789D",
            signal_name="EngCoolTemp",
            system="Engine",
            risk_score=65.0,
            confidence_score=85.0,
            status="Alerta"
        )
        print(f"✓ Created TechniqueResult: {result.result_id[:8]}...")
        print(f"  - Status: {result.status}, Risk: {result.risk_score}")
        
        # Test to_dict conversion
        result_dict = result.to_dict()
        print(f"✓ Converted to dict: {len(result_dict)} fields")
        
        # Test SystemHealth
        system_health = SystemHealth(
            unit_id="CDA_001",
            client="CDA",
            system="Engine",
            system_score=68.5,
            system_confidence=82.0,
            system_status="Alerta"
        )
        print(f"✓ Created SystemHealth: {system_health.system}")
        
        # Test UnitHealth
        unit_health = UnitHealth(
            unit_id="CDA_001",
            client="CDA",
            unit_score=55.0,
            overall_status="Alerta",
            priority_score=120.5
        )
        print(f"✓ Created UnitHealth: {unit_health.unit_id}")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_evaluation_window():
    """Test evaluation window system."""
    print("\n" + "="*80)
    print("TEST 6: Evaluation Window System")
    print("="*80)
    
    try:
        from datetime import datetime
        from src.utils.evaluation_window import EvaluationWindow, EvaluationWindowGenerator
        
        # Test daily window
        eval_date = datetime(2026, 5, 25, 23, 59, 59)
        window = EvaluationWindowGenerator.generate_daily_window(eval_date)
        print(f"✓ Daily window: {window.start.date()} to {window.end.date()}")
        print(f"  - Duration: {window.duration_hours():.1f} hours")
        
        # Test weekly window
        window = EvaluationWindowGenerator.generate_weekly_window(2026, 21)
        print(f"✓ Weekly window: {window.start.date()} to {window.end.date()}")
        
        # Test trend windows
        windows = EvaluationWindowGenerator.generate_trend_windows(eval_date, [4, 8, 12])
        print(f"✓ Generated {len(windows)} trend windows:")
        for w in windows:
            print(f"  - {w.lookback_window}: {w.duration_days():.1f} days")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("PHASE 1 IMPLEMENTATION TESTS")
    print("Testing core components without executing full pipeline")
    print("="*80)
    
    # Setup logger
    logger = setup_logger("phase1_tests", log_to_file=False)
    
    tests = [
        ("Signal Registry", test_signal_registry),
        ("Technique Config", test_technique_config),
        ("Date Utilities", test_date_utilities),
        ("File Utilities", test_file_utilities),
        ("Data Models", test_data_models),
        ("Evaluation Window", test_evaluation_window),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n✗ TEST FAILED: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name}")
    
    print(f"\n{passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All Phase 1 component tests passed!")
        print("Ready to execute: python run_pipeline.py --generate-baselines --client CDA")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
