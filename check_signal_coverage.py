"""Check signal coverage between Silver data and signal registry."""
import pandas as pd
import yaml
from pathlib import Path

# Load signal registry
with open('dataDep/telemetry/config/signal_registry_v1.yaml', 'r') as f:
    registry = yaml.safe_load(f)

registry_signals = {s['name'] for s in registry['signals']}

# Load Silver data
silver_dir = Path('dataDep/telemetry/silver/CDA/Telemetry_Wide_With_States')
files = list(silver_dir.glob('Week*.parquet'))
df = pd.read_parquet(files[0])

# Get telemetry signals (exclude metadata columns)
exclude_cols = ['timestamp', 'Fecha', 'unit_id', 'Unit', 'operational_state', 
                'EstadoMaquina', 'equipment_model', 'ModeloEquipo', 'Estado', 
                'EstadoCarga', 'GPSLat', 'GPSLon', 'GPSElevation', 'GroundSpd', 'Payload']
silver_signals = {c for c in df.columns if c not in exclude_cols}

print('=' * 70)
print('SIGNAL COVERAGE ANALYSIS')
print('=' * 70)
print(f'Signals in Silver data: {len(silver_signals)}')
print(f'Signals in registry: {len(registry_signals)}')

print('\n' + '=' * 70)
print('SIGNALS IN SILVER DATA BUT NOT IN REGISTRY')
print('=' * 70)
missing_in_registry = silver_signals - registry_signals
if missing_in_registry:
    for sig in sorted(missing_in_registry):
        print(f'  ❌ {sig}')
else:
    print('  ✓ All Silver signals are in registry')

print('\n' + '=' * 70)
print('SIGNALS IN REGISTRY BUT NOT IN SILVER DATA')
print('=' * 70)
missing_in_silver = registry_signals - silver_signals
if missing_in_silver:
    for sig in sorted(missing_in_silver):
        print(f'  ⚠️  {sig}')
else:
    print('  ✓ All registry signals are in Silver data')

# Now check data availability for each signal
print('\n' + '=' * 70)
print('DATA AVAILABILITY PER SIGNAL (Sample count from one week)')
print('=' * 70)

for sig in sorted(silver_signals):
    if sig in df.columns:
        non_null = df[sig].notna().sum()
        total = len(df)
        pct = (non_null / total) * 100 if total > 0 else 0
        status = '✓' if non_null > 1000 else '⚠️'
        print(f'  {status} {sig:20s}: {non_null:7,} / {total:7,} ({pct:5.1f}%)')
