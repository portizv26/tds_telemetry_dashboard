"""
Historical Data Analysis Script
Processes all available Silver layer data to generate comprehensive analysis.

This script:
1. Discovers all available weeks in Silver layer
2. Profiles data quality for each week
3. Generates comprehensive baselines from all historical data
4. Creates summary reports and visualizations
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple
import pandas as pd
import json
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import SignalRegistry, TechniqueConfig
from src.data import DataLoader, DataProfiler
from src.baselines import BaselineGenerator
from src.utils.logger import setup_logger
from src.utils.date_utils import parse_week_year
from src.utils.file_utils import ensure_dir


def discover_available_weeks(silver_dir: Path, client: str) -> List[Tuple[int, int]]:
    """
    Discover all available week files in Silver layer.
    
    Parameters
    ----------
    silver_dir : Path
        Silver data directory
    client : str
        Client identifier
        
    Returns
    -------
    List[Tuple[int, int]]
        List of (week, year) tuples sorted chronologically
    """
    client_dir = silver_dir / client / "Telemetry_Wide_With_States"
    
    if not client_dir.exists():
        raise FileNotFoundError(f"Client directory not found: {client_dir}")
    
    week_files = list(client_dir.glob("Week*.parquet"))
    
    weeks = []
    for file_path in week_files:
        try:
            week, year = parse_week_year(file_path.name)
            weeks.append((week, year))
        except ValueError as e:
            logging.warning(f"Skipping invalid filename {file_path.name}: {e}")
    
    # Sort chronologically
    weeks.sort(key=lambda x: (x[1], x[0]))  # Sort by year, then week
    
    return weeks


def profile_all_weeks(
    silver_dir: Path,
    client: str,
    signal_registry: SignalRegistry,
    output_dir: Path,
    weeks: List[Tuple[int, int]]
) -> List[Dict[str, Any]]:
    """
    Profile data quality for all available weeks.
    
    Parameters
    ----------
    silver_dir : Path
        Silver data directory
    client : str
        Client identifier
    signal_registry : SignalRegistry
        Signal registry
    output_dir : Path
        Output directory for reports
    weeks : List[Tuple[int, int]]
        List of (week, year) tuples
        
    Returns
    -------
    List[Dict[str, Any]]
        List of profiling results for each week
    """
    logger = logging.getLogger(__name__)
    
    data_loader = DataLoader(silver_dir)
    profiler = DataProfiler(signal_registry)
    
    all_profiles = []
    
    for i, (week, year) in enumerate(weeks, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"Profiling Week {week}/{year} ({i}/{len(weeks)})")
        logger.info(f"{'='*80}")
        
        try:
            # Load data
            df = data_loader.load_evaluation_week(client, week, year)
            
            # Profile data
            profile = profiler.profile_week(
                df=df,
                client=client,
                week=week,
                year=year,
                output_dir=output_dir
            )
            
            all_profiles.append(profile)
            
            logger.info(f"✓ Week {week}/{year} profiled: {profile['data_quality']['average_coverage_pct']:.1f}% coverage")
            
        except Exception as e:
            logger.error(f"✗ Failed to profile Week {week}/{year}: {e}")
            all_profiles.append({
                'client': client,
                'week': week,
                'year': year,
                'error': str(e),
                'total_rows': 0,
                'data_quality': {'average_coverage_pct': 0.0}
            })
    
    return all_profiles


def generate_comprehensive_baselines(
    silver_dir: Path,
    client: str,
    signal_registry: SignalRegistry,
    technique_config: TechniqueConfig,
    output_dir: Path,
    lookback_days: int = 90
) -> Path:
    """
    Generate baselines from all available historical data.
    
    Parameters
    ----------
    silver_dir : Path
        Silver data directory
    client : str
        Client identifier
    signal_registry : SignalRegistry
        Signal registry
    technique_config : TechniqueConfig
        Technique configuration
    output_dir : Path
        Output directory
    lookback_days : int
        Maximum lookback days (uses most recent N days)
        
    Returns
    -------
    Path
        Path to baseline file
    """
    logger = logging.getLogger(__name__)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Generating Baselines from Historical Data")
    logger.info(f"{'='*80}")
    logger.info(f"Lookback: {lookback_days} days")
    
    # Load historical data
    data_loader = DataLoader(silver_dir)
    df = data_loader.load_historical_for_baseline(
        client=client,
        lookback_days=lookback_days
    )
    
    logger.info(f"Loaded {len(df):,} rows for baseline generation")
    
    # Generate baselines
    generator = BaselineGenerator(
        signal_registry=signal_registry,
        min_samples_required=technique_config.get_baseline_min_samples(),
        percentiles=technique_config.get_baseline_percentiles()
    )
    
    baseline_version = datetime.now().strftime("%Y%m%d")
    
    baselines_df = generator.generate_baselines(
        df=df,
        client=client,
        baseline_version=baseline_version,
        output_dir=output_dir
    )
    
    baseline_file = output_dir / f"baseline_{baseline_version}.parquet"
    
    logger.info(f"✓ Generated {len(baselines_df)} baseline records")
    logger.info(f"✓ Saved to: {baseline_file}")
    
    return baseline_file


def generate_summary_report(
    profiles: List[Dict[str, Any]],
    baseline_file: Path,
    output_dir: Path,
    client: str
) -> Path:
    """
    Generate comprehensive summary report.
    
    Parameters
    ----------
    profiles : List[Dict[str, Any]]
        List of week profiles
    baseline_file : Path
        Path to baseline file
    output_dir : Path
        Output directory
    client : str
        Client identifier
        
    Returns
    -------
    Path
        Path to summary report
    """
    logger = logging.getLogger(__name__)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Generating Summary Report")
    logger.info(f"{'='*80}")
    
    # Calculate summary statistics
    total_weeks = len(profiles)
    successful_weeks = sum(1 for p in profiles if 'error' not in p)
    failed_weeks = total_weeks - successful_weeks
    
    # Coverage statistics
    coverages = [p['data_quality']['average_coverage_pct'] for p in profiles if 'error' not in p]
    avg_coverage = sum(coverages) / len(coverages) if coverages else 0.0
    min_coverage = min(coverages) if coverages else 0.0
    max_coverage = max(coverages) if coverages else 0.0
    
    # Total rows processed
    total_rows = sum(p.get('total_rows', 0) for p in profiles)
    
    # Load baseline statistics
    baseline_stats = {}
    if baseline_file.exists():
        baseline_df = pd.read_parquet(baseline_file)
        baseline_stats = {
            'total_records': len(baseline_df),
            'signals': baseline_df['signal_name'].nunique(),
            'states': baseline_df['operational_state'].nunique(),
            'fallback_distribution': baseline_df['fallback_level'].value_counts().to_dict()
        }
    
    # Create summary
    summary = {
        'analysis_date': datetime.now().isoformat(),
        'client': client,
        'coverage': {
            'total_weeks_analyzed': total_weeks,
            'successful_weeks': successful_weeks,
            'failed_weeks': failed_weeks,
            'average_coverage_pct': round(avg_coverage, 2),
            'min_coverage_pct': round(min_coverage, 2),
            'max_coverage_pct': round(max_coverage, 2),
            'total_rows_processed': total_rows
        },
        'baselines': baseline_stats,
        'week_details': []
    }
    
    # Add week details
    for profile in profiles:
        if 'error' in profile:
            summary['week_details'].append({
                'week': profile['week'],
                'year': profile['year'],
                'status': 'failed',
                'error': profile['error']
            })
        else:
            summary['week_details'].append({
                'week': profile['week'],
                'year': profile['year'],
                'status': 'success',
                'coverage_pct': profile['data_quality']['average_coverage_pct'],
                'total_rows': profile['total_rows'],
                'quality_score': profile['data_quality']['quality_score']
            })
    
    # Save JSON summary
    summary_file = output_dir / f"historical_analysis_summary_{client}.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"✓ Summary saved to: {summary_file}")
    
    # Generate HTML report
    html_file = generate_html_summary(summary, output_dir, client)
    logger.info(f"✓ HTML report saved to: {html_file}")
    
    return summary_file


def generate_html_summary(summary: Dict[str, Any], output_dir: Path, client: str) -> Path:
    """Generate HTML summary report."""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Historical Analysis Summary - {client}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #666; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 30px; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric-card {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; border-left: 4px solid #4CAF50; }}
        .metric-label {{ font-size: 14px; color: #666; text-transform: uppercase; }}
        .metric-value {{ font-size: 32px; font-weight: bold; color: #333; margin: 10px 0; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; font-weight: bold; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .success {{ color: green; font-weight: bold; }}
        .failed {{ color: red; font-weight: bold; }}
        .excellent {{ color: #2e7d32; }}
        .good {{ color: #66bb6a; }}
        .warning {{ color: #ffa726; }}
        .poor {{ color: #e53935; }}
        .timestamp {{ color: #999; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Historical Data Analysis Summary</h1>
        <p class="timestamp">Analysis Date: {summary['analysis_date']}</p>
        <p class="timestamp">Client: <strong>{summary['client']}</strong></p>
        
        <h2>Coverage Statistics</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Total Weeks</div>
                <div class="metric-value">{summary['coverage']['total_weeks_analyzed']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Successful</div>
                <div class="metric-value success">{summary['coverage']['successful_weeks']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Failed</div>
                <div class="metric-value {'failed' if summary['coverage']['failed_weeks'] > 0 else 'success'}">{summary['coverage']['failed_weeks']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Coverage</div>
                <div class="metric-value">{summary['coverage']['average_coverage_pct']:.1f}%</div>
            </div>
        </div>
        
        <h2>Data Volume</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Total Rows</div>
                <div class="metric-value">{summary['coverage']['total_rows_processed']:,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Min Coverage</div>
                <div class="metric-value">{summary['coverage']['min_coverage_pct']:.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Max Coverage</div>
                <div class="metric-value">{summary['coverage']['max_coverage_pct']:.1f}%</div>
            </div>
        </div>
"""
    
    # Baseline statistics
    if summary['baselines']:
        html_content += f"""
        <h2>Baseline Statistics</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Total Baseline Records</div>
                <div class="metric-value">{summary['baselines']['total_records']:,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Signals Covered</div>
                <div class="metric-value">{summary['baselines']['signals']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Operational States</div>
                <div class="metric-value">{summary['baselines']['states']}</div>
            </div>
        </div>
        
        <h3>Baseline Fallback Distribution</h3>
        <table>
            <tr>
                <th>Level</th>
                <th>Count</th>
                <th>Percentage</th>
            </tr>
"""
        
        total = sum(summary['baselines']['fallback_distribution'].values())
        for level, count in summary['baselines']['fallback_distribution'].items():
            pct = (count / total * 100) if total > 0 else 0
            html_content += f"""
            <tr>
                <td>{level}</td>
                <td>{count:,}</td>
                <td>{pct:.1f}%</td>
            </tr>
"""
        
        html_content += """
        </table>
"""
    
    # Week details
    html_content += """
        <h2>Week-by-Week Details</h2>
        <table>
            <tr>
                <th>Week</th>
                <th>Year</th>
                <th>Status</th>
                <th>Coverage %</th>
                <th>Total Rows</th>
                <th>Quality Score</th>
            </tr>
"""
    
    for week_detail in summary['week_details']:
        status = week_detail['status']
        status_class = 'success' if status == 'success' else 'failed'
        
        if status == 'success':
            coverage = week_detail['coverage_pct']
            coverage_class = 'excellent' if coverage >= 90 else 'good' if coverage >= 80 else 'warning' if coverage >= 60 else 'poor'
            
            html_content += f"""
            <tr>
                <td>{week_detail['week']}</td>
                <td>{week_detail['year']}</td>
                <td class="{status_class}">✓ Success</td>
                <td class="{coverage_class}">{coverage:.1f}%</td>
                <td>{week_detail['total_rows']:,}</td>
                <td>{week_detail['quality_score']}</td>
            </tr>
"""
        else:
            html_content += f"""
            <tr>
                <td>{week_detail['week']}</td>
                <td>{week_detail['year']}</td>
                <td class="{status_class}">✗ Failed</td>
                <td colspan="3">{week_detail['error']}</td>
            </tr>
"""
    
    html_content += """
        </table>
    </div>
</body>
</html>
"""
    
    html_file = output_dir / f"historical_analysis_summary_{client}.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return html_file


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Historical Data Analysis - Process all available Silver data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all available data for client CDA
  python run_historical_analysis.py --client CDA
  
  # Skip profiling, only generate baselines
  python run_historical_analysis.py --client CDA --skip-profiling
  
  # Use 180 days for baseline generation
  python run_historical_analysis.py --client CDA --lookback-days 180
        """
    )
    
    parser.add_argument(
        '--client',
        type=str,
        required=True,
        help='Client identifier (e.g., CDA, EMIN)'
    )
    parser.add_argument(
        '--skip-profiling',
        action='store_true',
        help='Skip weekly profiling, only generate baselines'
    )
    parser.add_argument(
        '--skip-baselines',
        action='store_true',
        help='Skip baseline generation, only profile data'
    )
    parser.add_argument(
        '--lookback-days',
        type=int,
        default=90,
        help='Days of history for baseline generation (default: 90)'
    )
    parser.add_argument(
        '--silver-dir',
        type=Path,
        default=Path('data/telemetry/silver'),
        help='Silver data directory'
    )
    parser.add_argument(
        '--config-dir',
        type=Path,
        default=Path('data/telemetry/config'),
        help='Config directory'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('outputs/historical_analysis'),
        help='Output directory for reports'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = getattr(logging, args.log_level)
    logger = setup_logger(
        name='historical_analysis',
        log_dir=Path('logs'),
        level=log_level
    )
    
    logger.info("="*80)
    logger.info("HISTORICAL DATA ANALYSIS")
    logger.info("="*80)
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client: {args.client}")
    logger.info(f"Silver dir: {args.silver_dir}")
    logger.info("")
    
    try:
        # Ensure output directory exists
        ensure_dir(args.output_dir)
        
        # Load configurations
        logger.info("Loading configurations...")
        signal_registry = SignalRegistry(args.config_dir / "signal_registry_v1.yaml")
        technique_config = TechniqueConfig(args.config_dir / "technique_config.yaml")
        logger.info(f"✓ Loaded {len(signal_registry.get_all_signal_names())} signals")
        logger.info(f"✓ Loaded {len(technique_config.get_all_technique_names())} techniques")
        
        # Discover available weeks
        logger.info("\nDiscovering available weeks...")
        weeks = discover_available_weeks(args.silver_dir, args.client)
        logger.info(f"✓ Found {len(weeks)} weeks of data")
        
        if not weeks:
            logger.error("No data found! Check Silver directory path.")
            return 1
        
        logger.info(f"  First week: Week {weeks[0][0]}/{weeks[0][1]}")
        logger.info(f"  Last week: Week {weeks[-1][0]}/{weeks[-1][1]}")
        
        # Profile all weeks
        profiles = []
        if not args.skip_profiling:
            logger.info("\n" + "="*80)
            logger.info("STEP 1: PROFILING ALL WEEKS")
            logger.info("="*80)
            
            profiles = profile_all_weeks(
                silver_dir=args.silver_dir,
                client=args.client,
                signal_registry=signal_registry,
                output_dir=args.output_dir,
                weeks=weeks
            )
            
            successful = sum(1 for p in profiles if 'error' not in p)
            logger.info(f"\n✓ Profiling complete: {successful}/{len(weeks)} weeks successful")
        
        # Generate baselines
        baseline_file = None
        if not args.skip_baselines:
            logger.info("\n" + "="*80)
            logger.info("STEP 2: GENERATING COMPREHENSIVE BASELINES")
            logger.info("="*80)
            
            baseline_dir = Path('data/telemetry/analytical_results/baselines')
            ensure_dir(baseline_dir)
            
            baseline_file = generate_comprehensive_baselines(
                silver_dir=args.silver_dir,
                client=args.client,
                signal_registry=signal_registry,
                technique_config=technique_config,
                output_dir=baseline_dir,
                lookback_days=args.lookback_days
            )
        
        # Generate summary report
        if profiles or baseline_file:
            logger.info("\n" + "="*80)
            logger.info("STEP 3: GENERATING SUMMARY REPORT")
            logger.info("="*80)
            
            summary_file = generate_summary_report(
                profiles=profiles,
                baseline_file=baseline_file if baseline_file else Path(),
                output_dir=args.output_dir,
                client=args.client
            )
        
        # Final summary
        logger.info("\n" + "="*80)
        logger.info("HISTORICAL ANALYSIS COMPLETE")
        logger.info("="*80)
        logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"\nOutputs saved to: {args.output_dir}")
        logger.info(f"  - Week profiles: {len(profiles)} files")
        logger.info(f"  - Summary report: historical_analysis_summary_{args.client}.html")
        logger.info(f"  - Summary JSON: historical_analysis_summary_{args.client}.json")
        if baseline_file:
            logger.info(f"  - Baselines: {baseline_file}")
        logger.info("\n✅ Historical analysis successful!")
        
        return 0
    
    except Exception as e:
        logger.error(f"\n❌ Historical analysis failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
