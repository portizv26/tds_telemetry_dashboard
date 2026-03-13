"""
I/O Module

Handles data loading and saving operations.
"""

import json
from pathlib import Path
from typing import Dict, Any
import pandas as pd

from .config import (
    COMPONENT_MAPPING_PATH,
    get_silver_data_path,
    get_processed_data_path,
    get_golden_inference_path,
    get_golden_health_index_path,
)


def load_component_mapping() -> Dict[str, Any]:
    """Load component to signals mapping from JSON."""
    with open(COMPONENT_MAPPING_PATH, 'r') as f:
        return json.load(f)


def load_telemetry_data(client: str) -> pd.DataFrame:
    """
    Load telemetry data from silver layer.
    
    Args:
        client: Client name (e.g., 'cda')
    
    Returns:
        DataFrame with telemetry data
    """
    path = get_silver_data_path(client)
    df = pd.read_parquet(path)
    
    # Sort and deduplicate
    df.sort_values(['Unit', 'Fecha'], inplace=True)
    df.drop_duplicates(subset=['Unit', 'Fecha'], keep='first', inplace=True)
    
    # Drop unnecessary columns if they exist
    drop_cols = ['Payload', 'EngOilFltr', 'AirFltr']
    existing_drop_cols = [col for col in drop_cols if col in df.columns]
    if existing_drop_cols:
        df.drop(columns=existing_drop_cols, inplace=True)
    
    print(f"Loaded {len(df)/1e6:.3f}M rows for client '{client}'")
    
    return df


def save_processed_data(df: pd.DataFrame, client: str):
    """Save processed data to silver layer."""
    path = get_processed_data_path(client)
    df.to_parquet(path, index=False)
    print(f"Saved processed data to: {path}")


def save_inference_data(df: pd.DataFrame, client: str):
    """Save inference/reconstruction data to golden layer."""
    path = get_golden_inference_path(client)
    df.to_parquet(path, index=False)
    print(f"Saved inference data to: {path}")


def save_health_index_data(df: pd.DataFrame, client: str):
    """Save health index data to golden layer."""
    path = get_golden_health_index_path(client)
    df.to_parquet(path, index=False)
    print(f"Saved health index data to: {path}")


def save_dict_as_json(data: Dict[str, Any], path: Path):
    """Save dictionary as JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Saved JSON to: {path}")


def load_dict_from_json(path: Path) -> Dict[str, Any]:
    """Load dictionary from JSON file."""
    with open(path, 'r') as f:
        return json.load(f)
