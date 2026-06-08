"""Quick script to check baseline statistics."""
import pandas as pd
import json

# Load baseline
df = pd.read_parquet('dataDep/telemetry/analytical_results/baselines/baseline_20260528.parquet')

print('=' * 60)
print('NEW BASELINE STATISTICS')
print('=' * 60)
print(f'Total baseline records: {len(df):,}')
print(f'Unique signals: {df["signal_name"].nunique()}')
print(f'Unique units: {df["unit_id"].nunique()}')
print(f'Unique states: {df["operational_state"].nunique()}')

print('\n' + '=' * 60)
print('SIGNALS WITH BASELINES')
print('=' * 60)
for sig in sorted(df['signal_name'].unique()):
    count = len(df[df['signal_name'] == sig])
    states = df[df['signal_name'] == sig]['operational_state'].nunique()
    units = df[df['signal_name'] == sig]['unit_id'].nunique()
    print(f'  {sig:20s}: {count:3d} baselines ({units} units, {states} states)')

print('\n' + '=' * 60)
print('FALLBACK LEVEL DISTRIBUTION')
print('=' * 60)
fallback_counts = df['fallback_level'].value_counts()
for level, count in fallback_counts.items():
    pct = (count / len(df)) * 100
    print(f'  {level:10s}: {count:4d} baselines ({pct:5.1f}%)')

print('\n' + '=' * 60)
print('OPERATIONAL STATES')
print('=' * 60)
for state in sorted(df['operational_state'].unique()):
    count = len(df[df['operational_state'] == state])
    print(f'  {state:20s}: {count:3d} baselines')

# Load metadata
with open('dataDep/telemetry/analytical_results/baselines/baseline_metadata.json', 'r') as f:
    metadata = json.load(f)

print('\n' + '=' * 60)
print('BASELINE METADATA')
print('=' * 60)
print(f"Version: {metadata['baseline_version']}")
print(f"Generated: {metadata['generation_timestamp']}")
print(f"Training window: {metadata['training_window_start']} to {metadata['training_window_end']}")
print(f"Min samples required: {metadata['min_samples_required']:,}")
print(f"Percentiles: {metadata['percentiles_calculated']}")
