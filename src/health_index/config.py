"""
Configuration Module

Contains all configuration constants, paths, and hyperparameters.
"""

from pathlib import Path
from typing import Dict, Any
import pandas as pd

# ========================
# PROJECT PATHS
# ========================
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
LOGS_DIR = PROJECT_ROOT / "logs"

# Telemetry paths
TELEMETRY_SILVER_DIR = DATA_DIR / "telemetry" / "silver"
TELEMETRY_GOLDEN_DIR = DATA_DIR / "telemetry" / "golden"
COMPONENT_MAPPING_PATH = DATA_DIR / "telemetry" / "component_signals_mapping.json"

# ========================
# DATA COLUMNS
# ========================
UNIT_COL = "Unit"
TIME_COL = "Fecha"
CAT_COLS = ["EstadoMaquina", "EstadoCarga"]

# ========================
# PREPROCESSING PARAMETERS
# ========================
# Cycle detection
FREQ = "1min"
GAP_THRESHOLD = pd.Timedelta("10min")
MIN_CYCLE_DURATION = pd.Timedelta("4h")
MIN_COVERAGE = 0.75
INTERP_LIMIT = 10

# Outlier margins
OUTLIER_MARGINS = {
    # General
    'GPSLat': (-30.4, -30.1),
    'GPSLon': (-71.3, -70.9),
    'GPSElevation': (400, 2000),
    'GroundSpd': (0, 80),
    'EngSpd': (0, 2500),
    # Engine
    "EngCoolTemp": (30, 120),
    "RAftrclrTemp": (10, 100),
    "EngOilPres": (150, 700),
    "EngOilFltr": (1, 50),
    "CnkcasePres": (-1.5, 1.5),
    "RtLtExhTemp": (-10, 10),
    "RtExhTemp": (150, 750),
    "LtExhTemp": (150, 750),
    # Transmission
    "DiffLubePres": (0, 800),
    "DiffTemp": (0, 150),
    "TrnLubeTemp": (-5, 120),
    "TCOutTemp": (30, 180),
    # Brakes
    "RtRBrkTemp": (20, 200),
    "RtFBrkTemp": (20, 200),
    "LtRBrkTemp": (20, 200),
    "LtFBrkTemp": (20, 200),
    # Direction
    'StrgOilTemp': (-10, 150),
}

# Labeling
LABELING_PERCENTILES = (0.05, 0.95)
ANOMALY_THRESHOLD_RATIO = 1.2

# ========================
# MODEL PARAMETERS
# ========================
# Default hyperparameters (can be overridden by Optuna)
DEFAULT_HYPERPARAMS = {
    "window_size": 60,  # 1 hour at 1-minute frequency
    "lstm_units_1": 16,
    "lstm_units_2": 8,
    "dropout_rate": 0.2,
    "learning_rate": 0.001,
    "batch_size": 32,
    "epochs": 50,
    "early_stopping_patience": 5,
}

# ========================
# TRAINING PARAMETERS
# ========================
WEEKS_TO_TEST = 8
VALIDATION_SPLIT = 0.2

# ========================
# OPTUNA PARAMETERS
# ========================
OPTUNA_N_TRIALS = 2
OPTUNA_TIMEOUT = None  # seconds, None for no timeout
OPTUNA_SAMPLER = "TPE"  # Tree-structured Parzen Estimator

# Hyperparameter search space
# Note: window_size is NOT optimized - it's fixed in DEFAULT_HYPERPARAMS
OPTUNA_SEARCH_SPACE = {
    "lstm_units_1": (8, 32),
    "lstm_units_2": (4, 16),
    "dropout_rate": (0.1, 0.5),
    "learning_rate": (1e-4, 1e-2),
    "batch_size": [16, 32, 64],
}

# ========================
# MLFLOW PARAMETERS
# ========================
MLFLOW_TRACKING_URI = str(LOGS_DIR / "mlflow")
MLFLOW_ARTIFACT_LOCATION = str(LOGS_DIR / "mlflow_artifacts")

# ========================
# HEALTH INDEX PARAMETERS
# ========================
HEALTH_INDEX_ALPHA = 1.0
HEALTH_INDEX_AGG_METHOD = "mean"  # "mean" or "median"
HEALTH_INDEX_EPS = 1e-8

# ========================
# HELPER FUNCTIONS
# ========================
def get_silver_data_path(client: str) -> Path:
    """Get path to silver telemetry data."""
    return TELEMETRY_SILVER_DIR / client / "Telemetry_Wide_With_States"

def get_golden_inference_path(client: str) -> Path:
    """Get path to store golden inference data."""
    path = TELEMETRY_GOLDEN_DIR / client / "inferences.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def get_golden_health_index_path(client: str) -> Path:
    """Get path to store golden health index data."""
    path = TELEMETRY_GOLDEN_DIR / client / "health_index.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def get_processed_data_path(client: str) -> Path:
    """Get path to store processed data."""
    path = TELEMETRY_SILVER_DIR / client / "processed_data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def get_model_dir(client: str, component: str) -> Path:
    """Get directory for model artifacts."""
    path = MODELS_DIR / client / component
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_model_path(client: str, component: str) -> Path:
    """Get path to model file."""
    return get_model_dir(client, component) / "model.keras"

def get_experiment_name(component: str, window_size: int, timestamp: str) -> str:
    """Generate MLflow experiment name."""
    return f"{component}_{window_size}_{timestamp}"

def get_numeric_columns(component_mapping: Dict[str, Any]) -> list:
    """Extract all numeric columns from outlier margins."""
    return [col for col in OUTLIER_MARGINS.keys()]
