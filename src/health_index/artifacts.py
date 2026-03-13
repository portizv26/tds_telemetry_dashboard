"""
Artifacts Module

Handles persistence of all training artifacts and metadata.
"""

import json
from pathlib import Path
from typing import Dict, Any, List
import joblib
import pandas as pd

from .config import get_model_dir


def save_all_artifacts(
    model_dir: Path,
    scalers: Dict,
    encoder: Any,
    feature_cols: List[str],
    hyperparams: Dict[str, Any],
    optimization_results: Dict[str, Any] = None,
    training_history: Dict[str, Any] = None,
    metadata: Dict[str, Any] = None,
):
    """
    Save all training artifacts to model directory.
    
    Args:
        model_dir: Directory to save artifacts
        scalers: Per-unit scalers
        encoder: Categorical encoder
        feature_cols: List of feature columns used
        hyperparams: Final hyperparameters used
        optimization_results: Optuna optimization results
        training_history: Training history
        metadata: Additional metadata
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # Save scalers
    joblib.dump(scalers, model_dir / "scalers.pkl")
    print(f"Saved scalers to: {model_dir / 'scalers.pkl'}")
    
    # Save encoder
    if encoder is not None:
        joblib.dump(encoder, model_dir / "encoder.pkl")
        print(f"Saved encoder to: {model_dir / 'encoder.pkl'}")
    
    # Save feature list
    with open(model_dir / "feature_cols.json", 'w') as f:
        json.dump(feature_cols, f, indent=2)
    print(f"Saved feature columns to: {model_dir / 'feature_cols.json'}")
    
    # Save hyperparameters
    with open(model_dir / "hyperparams.json", 'w') as f:
        json.dump(hyperparams, f, indent=2, default=str)
    print(f"Saved hyperparameters to: {model_dir / 'hyperparams.json'}")
    
    # Save optimization results if available
    if optimization_results is not None:
        with open(model_dir / "optimization_results.json", 'w') as f:
            json.dump(optimization_results, f, indent=2, default=str)
        print(f"Saved optimization results to: {model_dir / 'optimization_results.json'}")
    
    # Save training history
    if training_history is not None:
        with open(model_dir / "training_history.json", 'w') as f:
            json.dump(training_history, f, indent=2, default=str)
        print(f"Saved training history to: {model_dir / 'training_history.json'}")
    
    # Save metadata
    if metadata is None:
        metadata = {}
    
    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"Saved metadata to: {metadata_path}")


def load_artifacts(model_dir: Path) -> Dict[str, Any]:
    """
    Load all artifacts from model directory.
    
    Args:
        model_dir: Directory containing artifacts
    
    Returns:
        Dictionary with all loaded artifacts
    """
    artifacts = {}
    
    # Load scalers
    scalers_path = model_dir / "scalers.pkl"
    if scalers_path.exists():
        artifacts['scalers'] = joblib.load(scalers_path)
    
    # Load encoder
    encoder_path = model_dir / "encoder.pkl"
    if encoder_path.exists():
        artifacts['encoder'] = joblib.load(encoder_path)
    else:
        artifacts['encoder'] = None
    
    # Load feature columns
    feature_cols_path = model_dir / "feature_cols.json"
    if feature_cols_path.exists():
        with open(feature_cols_path, 'r') as f:
            artifacts['feature_cols'] = json.load(f)
    
    # Load hyperparameters
    hyperparams_path = model_dir / "hyperparams.json"
    if hyperparams_path.exists():
        with open(hyperparams_path, 'r') as f:
            artifacts['hyperparams'] = json.load(f)
    
    # Load optimization results
    opt_path = model_dir / "optimization_results.json"
    if opt_path.exists():
        with open(opt_path, 'r') as f:
            artifacts['optimization_results'] = json.load(f)
    
    # Load training history
    history_path = model_dir / "training_history.json"
    if history_path.exists():
        with open(history_path, 'r') as f:
            artifacts['training_history'] = json.load(f)
    
    # Load metadata
    metadata_path = model_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            artifacts['metadata'] = json.load(f)
    
    print(f"Loaded artifacts from: {model_dir}")
    
    return artifacts


def create_artifact_summary(model_dir: Path) -> pd.DataFrame:
    """
    Create a summary of artifacts in a model directory.
    
    Args:
        model_dir: Directory containing artifacts
    
    Returns:
        DataFrame with artifact summary
    """
    summary = []
    
    artifact_files = [
        "model.keras",
        "scalers.pkl",
        "encoder.pkl",
        "feature_cols.json",
        "hyperparams.json",
        "optimization_results.json",
        "training_history.json",
        "metadata.json",
    ]
    
    for filename in artifact_files:
        filepath = model_dir / filename
        exists = filepath.exists()
        size = filepath.stat().st_size if exists else 0
        
        summary.append({
            'artifact': filename,
            'exists': exists,
            'size_bytes': size,
            'size_mb': size / (1024 * 1024) if exists else 0,
        })
    
    return pd.DataFrame(summary)
