"""Check missing signals in Silver data."""
import pandas as pd
from pathlib import Path

silver = Path('dataDep/telemetry/silver/CDA/Telemetry_Wide_With_States')
df = pd.read_parquet(list(silver.glob('Week*.parquet'))[0])

missing = ['CompInPres1', 'CompInPres2', 'EngOilFltr', 'GearSelect', 
           'LckupSlip', 'TrboInPres', 'TrboOutPres', 'TrnGear', 'TrnSlip']

print('=' * 70)
print('MISSING SIGNALS STATUS')
print('=' * 70)
for sig in missing:
    status = '✓ IN' if sig in df.columns else '❌ NOT IN'
    print(f'  {status:8s} Silver data: {sig}')

print('\n' + '=' * 70)
print('CURRENT BASELINE LOCATION')
print('=' * 70)
baseline_path = Path('dataDep/telemetry/analytical_results/baselines/baseline_20260528.parquet')
print(f'Location: {baseline_path}')
print(f'Exists: {baseline_path.exists()}')
print(f'Size: {baseline_path.stat().st_size / 1024:.1f} KB' if baseline_path.exists() else 'N/A')
