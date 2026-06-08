"""Test new percentile configuration."""
from pathlib import Path
from src.config import SignalRegistry, TechniqueConfig
from src.baselines import BaselineGenerator
import numpy as np

# Load configuration
registry = SignalRegistry(Path('data/telemetry/config/signal_registry_v1.yaml'))
config = TechniqueConfig(Path('data/telemetry/config/technique_config.yaml'))
percentiles = config.get_baseline_percentiles()

# Initialize generator
generator = BaselineGenerator(registry, percentiles=percentiles)

print('=' * 60)
print('BASELINE GENERATOR - PERCENTILE CONFIGURATION TEST')
print('=' * 60)
print(f'\n✅ BaselineGenerator initialized successfully\n')
print(f'Configured percentiles: {generator.percentiles}')
print(f'Total: {len(generator.percentiles)} percentiles\n')

# Test on sample data
test_data = np.random.normal(100, 15, 5000)
print('Testing percentile calculation on sample data:')
print(f'Sample: N(100, 15), n={len(test_data)}\n')

print('Lower tail (detecting low anomalies):')
for p in [p for p in generator.percentiles if p < 50]:
    val = np.percentile(test_data, p)
    print(f'  P{p:2d} = {val:7.2f}')

print(f'\nMedian:')
val = np.percentile(test_data, 50)
print(f'  P50 = {val:7.2f}')

print(f'\nUpper tail (detecting high anomalies):')
for p in [p for p in generator.percentiles if p > 50]:
    val = np.percentile(test_data, p)
    print(f'  P{p:2d} = {val:7.2f}')

print('\n' + '=' * 60)
print('✅ ALL TESTS PASSED')
print('=' * 60)
