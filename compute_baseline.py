"""
Baseline Computation Script

Computes baseline percentiles (P1, P2, P5, P10, P90, P95, P98, P99) 
using all available historical telemetry data.

Usage:
    python compute_baseline.py --client cda
    python compute_baseline.py --client cda --lookback-days 180
    python compute_baseline.py --client cda --baseline-date 20260513
    python compute_baseline.py --client cda --data-folder data
    python compute_baseline.py --client cda --data-folder dataDev
"""

import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd

from src.telemetry.baseline import compute_baseline_percentiles, save_baseline
from src.telemetry.data_loader import get_signal_columns
from src.utils.logger import logger


def load_all_telemetry_data(client: str, base_dir: Path, max_lookback_days: int = None) -> pd.DataFrame:
    """
    Load all available telemetry data for baseline computation.
    
    Parameters
    ----------
    client : str
        Client identifier (e.g., 'cda', 'emin', 'enex')
    base_dir : Path
        Base data directory
    max_lookback_days : int, optional
        Maximum number of days to look back. If None, loads all available data.
    
    Returns
    -------
    pd.DataFrame
        Combined telemetry data from all available weeks
    """
    silver_dir = base_dir / 'telemetry' / 'silver' / client / 'Telemetry_Wide_With_States'
    
    if not silver_dir.exists():
        raise FileNotFoundError(f"Silver layer directory not found: {silver_dir}")
    
    # Find all parquet files
    parquet_files = sorted(silver_dir.glob('Week*.parquet'))
    
    if not parquet_files:
        raise FileNotFoundError(f"No telemetry files found in {silver_dir}")
    
    logger.info(f"Found {len(parquet_files)} telemetry files")
    logger.info(f"Loading all data from: {silver_dir}")
    
    # Load and combine all data
    dfs = []
    for file in parquet_files:
        try:
            logger.info(f"  Loading {file.name}...")
            df_chunk = pd.read_parquet(file)
            
            # Ensure Fecha is datetime
            if 'Fecha' in df_chunk.columns:
                if not pd.api.types.is_datetime64_any_dtype(df_chunk['Fecha']):
                    df_chunk['Fecha'] = pd.to_datetime(df_chunk['Fecha'])
            
            # Apply time filter if specified
            if max_lookback_days is not None:
                cutoff_date = datetime.now() - pd.Timedelta(days=max_lookback_days)
                df_chunk = df_chunk[df_chunk['Fecha'] >= cutoff_date]
            
            if not df_chunk.empty:
                dfs.append(df_chunk)
                logger.info(f"    Loaded {len(df_chunk):,} rows")
        
        except Exception as e:
            logger.warning(f"  Could not load {file.name}: {e}")
            continue
    
    if not dfs:
        raise ValueError("No data could be loaded from any file")
    
    # Combine all data
    logger.info("Combining all data...")
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Sort by date for determinism
    combined_df = combined_df.sort_values(['Unit', 'Fecha']).reset_index(drop=True)
    
    logger.info(f"Total data loaded:")
    logger.info(f"  Rows: {len(combined_df):,}")
    logger.info(f"  Units: {combined_df['Unit'].nunique()}")
    logger.info(f"  Date range: {combined_df['Fecha'].min()} to {combined_df['Fecha'].max()}")
    logger.info(f"  Days of data: {(combined_df['Fecha'].max() - combined_df['Fecha'].min()).days}")
    
    return combined_df


def main():
    parser = argparse.ArgumentParser(
        description='Compute baseline percentiles from all available telemetry data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compute baseline for CDA using all available data
  python compute_baseline.py --client cda
  
  # Use only last 180 days of data
  python compute_baseline.py --client cda --lookback-days 180
  
  # Specify custom baseline date identifier
  python compute_baseline.py --client cda --baseline-date 20260513
  
  # Use dataDev folder instead of data
  python compute_baseline.py --client cda --data-folder dataDev
        """
    )
    
    parser.add_argument(
        '--client',
        type=str,
        required=True,
        help='Client identifier (e.g., cda, emin, enex)'
    )
    
    parser.add_argument(
        '--lookback-days',
        type=int,
        default=None,
        help='Maximum number of days to look back (default: use all available data)'
    )
    
    parser.add_argument(
        '--baseline-date',
        type=str,
        default=None,
        help='Baseline version identifier in YYYYMMDD format (default: today\'s date)'
    )
    
    parser.add_argument(
        '--data-folder',
        type=str,
        default='data',
        choices=['data', 'dataDev'],
        help='Data folder to use (default: data)'
    )
    
    parser.add_argument(
        '--min-samples',
        type=int,
        default=100,
        help='Minimum samples required per baseline (default: 100)'
    )
    
    args = parser.parse_args()
    
    # Set up paths
    base_dir = Path(__file__).parent / args.data_folder
    
    # Set baseline date
    if args.baseline_date is None:
        baseline_date = datetime.now().strftime('%Y%m%d')
    else:
        # Validate format
        try:
            datetime.strptime(args.baseline_date, '%Y%m%d')
            baseline_date = args.baseline_date
        except ValueError:
            logger.error(f"Invalid baseline date format: {args.baseline_date}. Use YYYYMMDD format.")
            return 1
    
    logger.info("=" * 80)
    logger.info("BASELINE COMPUTATION")
    logger.info("=" * 80)
    logger.info(f"Client: {args.client}")
    logger.info(f"Data folder: {args.data_folder}")
    logger.info(f"Baseline date: {baseline_date}")
    logger.info(f"Lookback days: {'ALL' if args.lookback_days is None else args.lookback_days}")
    logger.info(f"Min samples: {args.min_samples}")
    logger.info(f"Percentiles: P1, P2, P5, P10, P90, P95, P98, P99")
    logger.info("=" * 80)
    
    try:
        # Step 1: Load all telemetry data
        logger.info("\n[STEP 1] Loading telemetry data...")
        telemetry_df = load_all_telemetry_data(args.client, base_dir, args.lookback_days)
        
        # Step 2: Identify signal columns
        logger.info("\n[STEP 2] Identifying signal columns...")
        signal_cols = get_signal_columns(telemetry_df)
        logger.info(f"Found {len(signal_cols)} signal columns")
        logger.info(f"Signals: {', '.join(signal_cols[:10])}{'...' if len(signal_cols) > 10 else ''}")
        
        # Step 3: Compute baseline percentiles
        logger.info("\n[STEP 3] Computing baseline percentiles...")
        logger.info("This may take several minutes depending on data volume...")
        
        # Use all available percentiles from baseline module
        from src.telemetry.baseline import PERCENTILES, MIN_SAMPLES_FOR_BASELINE
        
        # Override min samples if specified
        if args.min_samples != MIN_SAMPLES_FOR_BASELINE:
            import src.telemetry.baseline as baseline_module
            original_min_samples = baseline_module.MIN_SAMPLES_FOR_BASELINE
            baseline_module.MIN_SAMPLES_FOR_BASELINE = args.min_samples
            logger.info(f"Using custom minimum samples: {args.min_samples} (default: {original_min_samples})")
        
        baseline_df = compute_baseline_percentiles(
            training_df=telemetry_df,
            signal_cols=signal_cols,
            percentiles=PERCENTILES,
            baseline_date=baseline_date
        )
        
        # Step 4: Save baseline
        logger.info("\n[STEP 4] Saving baseline...")
        output_file = save_baseline(
            baseline_df=baseline_df,
            client=args.client,
            base_dir=base_dir / 'telemetry'
        )
        
        logger.info("\n" + "=" * 80)
        logger.info("BASELINE COMPUTATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Output file: {output_file}")
        logger.info(f"Total baseline records: {len(baseline_df):,}")
        logger.info(f"Units covered: {baseline_df['Unit'].nunique()}")
        logger.info(f"Signals covered: {baseline_df['Signal'].nunique()}")
        
        # Show sample of percentile columns
        percentile_cols = [col for col in baseline_df.columns if col.startswith('P')]
        logger.info(f"Percentile columns: {', '.join(percentile_cols)}")
        
        # Show distribution of state-specific vs aggregate baselines
        state_specific = (baseline_df['EstadoMaquina'] != 'All').sum()
        aggregate = (baseline_df['EstadoMaquina'] == 'All').sum()
        logger.info(f"State-specific baselines: {state_specific:,}")
        logger.info(f"Aggregate baselines: {aggregate:,}")
        
        # Show sample records
        logger.info("\nSample baseline records:")
        sample_cols = ['Unit', 'Signal', 'EstadoMaquina'] + percentile_cols + ['sample_count']
        logger.info(f"\n{baseline_df[sample_cols].head(10).to_string()}")
        
        logger.info("\n" + "=" * 80)
        logger.info("Next steps:")
        logger.info(f"1. Review the baseline file: {output_file}")
        logger.info(f"2. Use this baseline in your evaluation pipeline")
        logger.info(f"3. The baseline version identifier is: {baseline_date}")
        logger.info("=" * 80)
        
        return 0
    
    except Exception as e:
        logger.error(f"\nERROR: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
