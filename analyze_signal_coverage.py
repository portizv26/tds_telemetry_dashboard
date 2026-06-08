"""Analyze signal coverage between registry, component mapping, and Silver data."""
import pandas as pd
import json
from pathlib import Path

# Load component mapping
with open('data/telemetry/component_signals_mapping.json', 'r') as f:
    mapping = json.load(f)

all_mapped = set()
for comp in mapping['components'].values():
    all_mapped.update(comp['signals'])

# Load Silver data to see available columns
df = pd.read_parquet('data/telemetry/silver/CDA/Telemetry_Wide_With_States/Week09Year2026.parquet')
silver_cols = set([col for col in df.columns if col not in ['Unit', 'Fecha', 'Estado', 'EstadoCarga', 'EstadoMaquina', 'GPSLat', 'GPSLon', 'GPSElevation']])

# Load baseline metadata
with open('data/telemetry/analytical_results/baselines/baseline_metadata.json', 'r') as f:
    baseline_meta = json.load(f)
in_baseline = set(baseline_meta['signals'])

print('=' * 60)
print('SIGNAL COVERAGE ANALYSIS')
print('=' * 60)
print(f'\n📋 In component mapping:  {len(all_mapped):2d} signals')
print(f'📋 In baseline:            {len(in_baseline):2d} signals')
print(f'📊 In Silver data:         {len(silver_cols):2d} signals')

print('\n' + '=' * 60)
print('❌ MISSING FROM BASELINE (in component mapping but not baseline):')
print('=' * 60)
missing = sorted(all_mapped - in_baseline)
for i, s in enumerate(missing, 1):
    exists = '✓' if s in silver_cols else '✗'
    print(f'{i:2d}. {s:20s} [{exists}] {"EXISTS in Silver" if s in silver_cols else "NOT in Silver"}')

print('\n' + '=' * 60)
print('✨ EXTRA SIGNALS (in Silver but not in component mapping):')
print('=' * 60)
extra = sorted(silver_cols - all_mapped)
for i, s in enumerate(extra, 1):
    in_bl = '✓' if s in in_baseline else '✗'
    print(f'{i:2d}. {s:20s} [{in_bl}] {"IN baseline" if s in in_baseline else "NOT in baseline"}')

print('\n' + '=' * 60)
print('SUMMARY')
print('=' * 60)
print(f'Missing from baseline: {len(missing)} signals (all exist in Silver data: {all(s in silver_cols for s in missing)})')
print(f'Extra signals available: {len(extra)} signals')
print(f'\nBaseline coverage: {len(in_baseline)}/{len(all_mapped)} ({100*len(in_baseline)/len(all_mapped):.1f}%) of component-mapped signals')
