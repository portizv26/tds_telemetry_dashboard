"""
File system utilities for telemetry health evaluation framework.
Handles directory management, partitioned storage, and Parquet I/O.
"""

from pathlib import Path
from typing import Union, Dict, Any, Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime


def ensure_dir(path: Path) -> Path:
    """
    Create directory if it doesn't exist.
    
    Parameters
    ----------
    path : Path
        Directory path to create
        
    Returns
    -------
    Path
        Created directory path
        
    Examples
    --------
    >>> output_dir = ensure_dir(Path("data/outputs"))
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_partition_path(
    base_dir: Path,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    week: Optional[int] = None,
    client: Optional[str] = None,
) -> Path:
    """
    Generate partitioned directory path.
    
    Parameters
    ----------
    base_dir : Path
        Base directory
    year : Optional[int]
        Year for partitioning
    month : Optional[int]
        Month for partitioning (1-12)
    day : Optional[int]
        Day for partitioning (1-31)
    week : Optional[int]
        ISO week for partitioning (1-53)
    client : Optional[str]
        Client identifier for partitioning
        
    Returns
    -------
    Path
        Partitioned directory path
        
    Examples
    --------
    >>> path = get_partition_path(
    ...     Path("data/results"),
    ...     year=2026, 
    ...     month=5, 
    ...     day=25,
    ...     client="CDA"
    ... )
    >>> str(path)
    'data/results/year=2026/month=5/day=25/client=CDA'
    """
    path = base_dir
    
    if year is not None:
        path = path / f"year={year}"
    if month is not None:
        path = path / f"month={month}"
    if day is not None:
        path = path / f"day={day}"
    if week is not None:
        path = path / f"week={week}"
    if client is not None:
        path = path / f"client={client}"
    
    return path


def save_to_parquet(
    df: pd.DataFrame,
    file_path: Path,
    compression: str = "snappy",
    partition_cols: Optional[list] = None,
) -> None:
    """
    Save DataFrame to Parquet with compression.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to save
    file_path : Path
        Output file path
    compression : str
        Compression codec ("snappy", "gzip", "zstd")
    partition_cols : Optional[list]
        Columns to partition by
        
    Examples
    --------
    >>> df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    >>> save_to_parquet(df, Path("output.parquet"))
    """
    # Ensure directory exists
    ensure_dir(file_path.parent)
    
    # Convert to PyArrow Table for better control
    table = pa.Table.from_pandas(df)
    
    if partition_cols:
        # Partitioned write
        pq.write_to_dataset(
            table,
            root_path=str(file_path.parent),
            partition_cols=partition_cols,
            compression=compression,
            existing_data_behavior='overwrite_or_ignore'
        )
    else:
        # Single file write
        pq.write_table(
            table,
            str(file_path),
            compression=compression
        )


def load_from_parquet(
    file_path: Path,
    columns: Optional[list] = None,
    filters: Optional[list] = None,
) -> pd.DataFrame:
    """
    Load DataFrame from Parquet file or directory.
    
    Parameters
    ----------
    file_path : Path
        Input file or directory path
    columns : Optional[list]
        Specific columns to load
    filters : Optional[list]
        Row filters in PyArrow format
        
    Returns
    -------
    pd.DataFrame
        Loaded DataFrame
        
    Examples
    --------
    >>> df = load_from_parquet(Path("input.parquet"))
    >>> df = load_from_parquet(
    ...     Path("data/results"),
    ...     columns=["unit_id", "risk_score"],
    ...     filters=[("client", "=", "CDA")]
    ... )
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Parquet file/directory not found: {file_path}")
    
    # Load from file or directory
    if file_path.is_dir():
        # Partitioned dataset
        dataset = pq.ParquetDataset(str(file_path), filters=filters)
        table = dataset.read(columns=columns)
    else:
        # Single file
        table = pq.read_table(str(file_path), columns=columns, filters=filters)
    
    return table.to_pandas()


def get_latest_baseline(baselines_dir: Path) -> Optional[Path]:
    """
    Find the most recent baseline file.
    
    Parameters
    ----------
    baselines_dir : Path
        Baselines directory
        
    Returns
    -------
    Optional[Path]
        Path to latest baseline file, or None if no baselines found
        
    Examples
    --------
    >>> latest = get_latest_baseline(Path("data/baselines"))
    >>> print(latest)
    PosixPath('data/baselines/baseline_20260525.parquet')
    """
    if not baselines_dir.exists():
        return None
    
    baseline_files = list(baselines_dir.glob("baseline_*.parquet"))
    
    if not baseline_files:
        return None
    
    # Sort by filename (YYYYMMDD format sorts correctly)
    baseline_files.sort(reverse=True)
    
    return baseline_files[0]


def list_parquet_files(
    directory: Path,
    pattern: str = "*.parquet",
    recursive: bool = True
) -> list:
    """
    List all Parquet files in directory.
    
    Parameters
    ----------
    directory : Path
        Directory to search
    pattern : str
        File pattern to match
    recursive : bool
        Search recursively
        
    Returns
    -------
    list
        List of Parquet file paths
        
    Examples
    --------
    >>> files = list_parquet_files(Path("data/results"))
    """
    if not directory.exists():
        return []
    
    if recursive:
        return list(directory.rglob(pattern))
    else:
        return list(directory.glob(pattern))


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in megabytes.
    
    Parameters
    ----------
    file_path : Path
        File path
        
    Returns
    -------
    float
        File size in MB
        
    Examples
    --------
    >>> size = get_file_size_mb(Path("data.parquet"))
    >>> print(f"{size:.2f} MB")
    """
    if not file_path.exists():
        return 0.0
    
    return file_path.stat().st_size / (1024 * 1024)
