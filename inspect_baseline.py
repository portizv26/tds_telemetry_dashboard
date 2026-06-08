"""Detailed baseline inspection script."""
import pandas as pd
import json
from pathlib import Path

# Load baseline
baseline_file = 'dataDep/telemetry/analytical_results/baselines/baseline_20260528.parquet'
df = pd.read_parquet(baseline_file)

print('=' * 80)
print('COMPREHENSIVE BASELINE INSPECTION')
print('=' * 80)
print(f'Baseline file: {baseline_file}')
print(f'File size: {Path(baseline_file).stat().st_size / 1024:.1f} KB')
print()

# Summary stats
print('=' * 80)
print('OVERALL STATISTICS')
print('=' * 80)
print(f'Total baseline records: {len(df):,}')
print(f'Unique signals: {df["signal_name"].nunique()}')
print(f'Unique units: {df["unit_id"].nunique()}')
print(f'Unique operational states: {df["operational_state"].nunique()}')
print(f'Unique clients: {df["client"].nunique()}')
print()

# Sample baseline for each signal
print('=' * 80)
print('SAMPLE BASELINES (One per signal)')
print('=' * 80)
for signal in sorted(df['signal_name'].unique()):
    sample = df[df['signal_name'] == signal].iloc[0]
    print(f'\n📊 {signal} (Unit: {sample["unit_id"]}, State: {sample["operational_state"]})')
    print(f'   P5: {sample["p5"]:.2f}  |  P50: {sample["p50"]:.2f}  |  P95: {sample["p95"]:.2f}')
    print(f'   Mean: {sample["mean"]:.2f} ± {sample["std"]:.2f}')
    print(f'   Samples: {sample["sample_count"]:,}  |  Quality: {sample["quality_score"]:.1f}  |  Level: {sample["fallback_level"]}')

# Quality distribution
print('\n' + '=' * 80)
print('BASELINE QUALITY DISTRIBUTION')
print('=' * 80)
quality_dist = df['quality_score'].value_counts().sort_index(ascending=False)
for quality, count in quality_dist.items():
    pct = (count / len(df)) * 100
    if quality == 1.0:
        label = "Excellent (5000+ samples)"
    elif quality == 0.8:
        label = "Good (2000-5000 samples)"
    elif quality == 0.6:
        label = "Fair (1000-2000 samples)"
    else:
        label = "Adequate (<1000 samples)"
    print(f'  {quality:.1f} ({label:25s}): {count:4d} baselines ({pct:5.1f}%)')

# Sample count stats
print('\n' + '=' * 80)
print('SAMPLE COUNT STATISTICS')
print('=' * 80)
print(f'Min samples: {df["sample_count"].min():,}')
print(f'Max samples: {df["sample_count"].max():,}')
print(f'Mean samples: {df["sample_count"].mean():,.0f}')
print(f'Median samples: {df["sample_count"].median():,.0f}')

# Units coverage
print('\n' + '=' * 80)
print('UNIT COVERAGE')
print('=' * 80)
units = [u for u in df['unit_id'].unique() if u is not None]
for unit in sorted(units):
    unit_df = df[df['unit_id'] == unit]
    signals = unit_df['signal_name'].nunique()
    states = unit_df['operational_state'].nunique()
    records = len(unit_df)
    fallback_unit = len(unit_df[unit_df['fallback_level'] == 'unit'])
    pct = (fallback_unit / records) * 100 if records > 0 else 0
    print(f'  {unit:10s}: {records:3d} baselines ({signals:2d} signals, {states} states, {pct:5.1f}% unit-level)')

# System breakdown (from signal registry)
print('\n' + '=' * 80)
print('SYSTEM BREAKDOWN')
print('=' * 80)

# Map signals to systems based on your signal registry
system_map = {
    'Engine': ['EngCoolTemp', 'EngOilPres', 'EngOilFltr', 'EngSpd', 'TCOutTemp', 
               'RAftrclrTemp', 'LtExhTemp', 'RtExhTemp', 'RtLtExhTemp', 'AirFltr', 'CnkcasePres'],
    'Transmission': ['TrnLubeTemp'],
    'Drive': ['DiffTemp', 'DiffLubePres'],
    'Brakes': ['LtFBrkTemp', 'RtFBrkTemp', 'LtRBrkTemp', 'RtRBrkTemp'],
    'Steering': ['StrgOilTemp']
}

for system, signals in system_map.items():
    system_df = df[df['signal_name'].isin(signals)]
    if len(system_df) > 0:
        avg_quality = system_df['quality_score'].mean()
        print(f'  {system:15s}: {len(system_df):3d} baselines ({len([s for s in signals if s in df["signal_name"].unique()])} signals, avg quality: {avg_quality:.2f})')

# Export sample to CSV for inspection
sample_csv = 'outputs/baseline_sample.csv'
Path('outputs').mkdir(exist_ok=True)
df.head(20).to_csv(sample_csv, index=False)
print(f'\n✓ Sample exported to: {sample_csv}')

print('\n' + '=' * 80)
print('VALIDATION CHECKS')
print('=' * 80)
checks = []

# Check 1: All percentiles present
if all(col in df.columns for col in ['p1', 'p2', 'p5', 'p10', 'p50', 'p90', 'p95', 'p98', 'p99']):
    checks.append('✅ All percentiles (P1, P2, P5, P10, P50, P90, P95, P98, P99) present')
else:
    checks.append('❌ Missing percentile columns')

# Check 2: No null values in critical columns
critical_cols = ['signal_name', 'unit_id', 'operational_state', 'p5', 'p95', 'mean', 'std']
if df[critical_cols].notna().all().all():
    checks.append('✅ No null values in critical columns')
else:
    checks.append('⚠️  Some null values detected')

# Check 3: Reasonable sample counts
if df['sample_count'].min() >= 1000:
    checks.append('✅ All baselines meet minimum sample requirement (1000+)')
else:
    checks.append('⚠️  Some baselines below 1000 samples')

# Check 4: Unit-level coverage
unit_level_pct = (len(df[df['fallback_level'] == 'unit']) / len(df)) * 100
if unit_level_pct >= 70:
    checks.append(f'✅ High unit-level coverage ({unit_level_pct:.1f}%)')
elif unit_level_pct >= 50:
    checks.append(f'⚠️  Moderate unit-level coverage ({unit_level_pct:.1f}%)')
else:
    checks.append(f'❌ Low unit-level coverage ({unit_level_pct:.1f}%)')

# Check 5: Signal coverage
if df['signal_name'].nunique() >= 15:
    checks.append(f'✅ Good signal coverage ({df["signal_name"].nunique()} signals)')
else:
    checks.append(f'⚠️  Limited signal coverage ({df["signal_name"].nunique()} signals)')

for check in checks:
    print(f'  {check}')

print('\n' + '=' * 80)
print('BASELINE READY FOR PHASE 2!')
print('=' * 80)
print('You can now use these baselines for:')
print('  • Threshold Deviation Detection (using P5, P95)')
print('  • Event Detection (using P1, P99)')
print('  • Trend Analysis (using mean, std)')
print('  • Anomaly Scoring (using MAD)')
print('=' * 80)
