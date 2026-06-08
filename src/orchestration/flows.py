"""
Prefect flows for pipeline orchestration.
Implements execution scheduling and task coordination.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime
import logging

# Check if Prefect is installed (optional dependency for Phase 1)
try:
    from prefect import flow, task
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    # Define dummy decorators if Prefect not available
    def flow(func):
        return func
    def task(func):
        return func

from src.config import SignalRegistry, TechniqueConfig
from src.data import DataLoader, DataProfiler
from src.baselines import BaselineGenerator
from src.utils.logger import setup_logger

logger = logging.getLogger(__name__)


@task
def load_historical_data_task(
    silver_dir: Path,
    client: str,
    lookback_days: int
) -> 'pd.DataFrame':
    """
    Task: Load historical data for baseline generation.
    
    Parameters
    ----------
    silver_dir : Path
        Silver data directory
    client : str
        Client identifier
    lookback_days : int
        Days to look back
        
    Returns
    -------
    pd.DataFrame
        Historical telemetry data
    """
    logger.info(f"Loading {lookback_days} days of historical data for {client}")
    
    data_loader = DataLoader(silver_dir)
    df = data_loader.load_historical_for_baseline(
        client=client,
        lookback_days=lookback_days
    )
    
    logger.info(f"Loaded {len(df):,} rows")
    
    return df


@task
def generate_baselines_task(
    df: 'pd.DataFrame',
    client: str,
    signal_registry: SignalRegistry,
    technique_config: TechniqueConfig,
    output_dir: Path
) -> Path:
    """
    Task: Generate baselines from historical data.
    
    Parameters
    ----------
    df : pd.DataFrame
        Historical telemetry data
    client : str
        Client identifier
    signal_registry : SignalRegistry
        Signal registry
    technique_config : TechniqueConfig
        Technique configuration
    output_dir : Path
        Output directory for baselines
        
    Returns
    -------
    Path
        Path to generated baseline file
    """
    logger.info(f"Generating baselines for {client}")
    
    generator = BaselineGenerator(
        signal_registry=signal_registry,
        min_samples_required=technique_config.get_baseline_min_samples(),
        percentiles=technique_config.get_baseline_percentiles()
    )
    
    baseline_version = datetime.now().strftime("%Y%m%d")
    
    generator.generate_baselines(
        df=df,
        client=client,
        baseline_version=baseline_version,
        output_dir=output_dir
    )
    
    baseline_file = output_dir / f"baseline_{baseline_version}.parquet"
    
    logger.info(f"Baselines generated: {baseline_file}")
    
    return baseline_file


@task
def profile_data_task(
    df: 'pd.DataFrame',
    client: str,
    week: int,
    year: int,
    signal_registry: SignalRegistry,
    output_dir: Path
) -> Dict:
    """
    Task: Profile data quality.
    
    Parameters
    ----------
    df : pd.DataFrame
        Telemetry data
    client : str
        Client identifier
    week : int
        Week number
    year : int
        Year
    signal_registry : SignalRegistry
        Signal registry
    output_dir : Path
        Output directory for reports
        
    Returns
    -------
    Dict
        Profiling metrics
    """
    logger.info(f"Profiling {client} Week {week} Year {year}")
    
    profiler = DataProfiler(signal_registry=signal_registry)
    
    profile = profiler.profile_week(
        df=df,
        client=client,
        week=week,
        year=year,
        output_dir=output_dir
    )
    
    logger.info(
        f"Profiling complete: "
        f"{profile['data_quality']['average_coverage_pct']:.1f}% coverage"
    )
    
    return profile


@flow(name="Generate Baselines")
def generate_baselines_flow(
    client: str,
    lookback_days: int = 90,
    silver_dir: Optional[Path] = None,
    config_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> Path:
    """
    Flow: Generate baselines from historical data.
    
    Parameters
    ----------
    client : str
        Client identifier
    lookback_days : int
        Days of historical data to use
    silver_dir : Optional[Path]
        Silver data directory. If None, uses default
    config_dir : Optional[Path]
        Config directory. If None, uses default
    output_dir : Optional[Path]
        Output directory. If None, uses default
        
    Returns
    -------
    Path
        Path to generated baseline file
    """
    # Setup logger
    logger = setup_logger("baseline_generation")
    
    logger.info(f"Starting baseline generation flow for {client}")
    
    # Set default paths
    if silver_dir is None:
        silver_dir = Path("dataDep/telemetry/silver")
    if config_dir is None:
        config_dir = Path("dataDep/telemetry/config")
    if output_dir is None:
        output_dir = Path("dataDep/telemetry/analytical_results/baselines")
    
    # Load configurations
    logger.info("Loading configurations...")
    signal_registry = SignalRegistry(config_dir / "signal_registry_v1.yaml")
    technique_config = TechniqueConfig(config_dir / "technique_config.yaml")
    
    # Execute tasks
    df = load_historical_data_task(silver_dir, client, lookback_days)
    
    baseline_file = generate_baselines_task(
        df=df,
        client=client,
        signal_registry=signal_registry,
        technique_config=technique_config,
        output_dir=output_dir
    )
    
    logger.info(f"Baseline generation flow complete: {baseline_file}")
    
    return baseline_file


@flow(name="Profile Data Quality")
def profile_data_flow(
    client: str,
    week: int,
    year: int,
    silver_dir: Optional[Path] = None,
    config_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> Dict:
    """
    Flow: Profile data quality for a week.
    
    Parameters
    ----------
    client : str
        Client identifier
    week : int
        Week number
    year : int
        Year
    silver_dir : Optional[Path]
        Silver data directory
    config_dir : Optional[Path]
        Config directory
    output_dir : Optional[Path]
        Output directory for reports
        
    Returns
    -------
    Dict
        Profiling metrics
    """
    # Setup logger
    logger = setup_logger("data_profiling")
    
    logger.info(f"Starting data profiling flow for {client} Week {week} Year {year}")
    
    # Set default paths
    if silver_dir is None:
        silver_dir = Path("dataDep/telemetry/silver")
    if config_dir is None:
        config_dir = Path("dataDep/telemetry/config")
    if output_dir is None:
        output_dir = Path("outputs/profiling")
    
    # Load configurations
    logger.info("Loading configurations...")
    signal_registry = SignalRegistry(config_dir / "signal_registry_v1.yaml")
    
    # Load data
    logger.info("Loading telemetry data...")
    data_loader = DataLoader(silver_dir)
    df = data_loader.load_evaluation_week(client, week, year)
    
    # Profile data
    profile = profile_data_task(
        df=df,
        client=client,
        week=week,
        year=year,
        signal_registry=signal_registry,
        output_dir=output_dir
    )
    
    logger.info(f"Data profiling flow complete")
    
    return profile


# Add type hints for imports
from typing import Dict
import pandas as pd
