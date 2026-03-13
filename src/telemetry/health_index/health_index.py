"""
Health-index computation module.

Single responsibility: convert reconstruction errors into a 0-1
health index score.
"""

import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


def compute_health_index(
    inferences_df: pd.DataFrame,
    error_quantile: float = 0.95,
    error_col: str = "reconstruction_error",
    coverage_col: str = "coverage",
) -> pd.DataFrame:
    """
    Compute a per-window health index.

    ``health_index = (1 − normalised_error) × coverage``

    The error is normalised against the *error_quantile* ceiling
    so that 1.0 ≈ perfectly healthy and 0.0 ≈ highly anomalous.
    """
    df = inferences_df.copy()
    ceiling = df[error_col].quantile(error_quantile)
    df["error_norm"] = (df[error_col] / ceiling).clip(upper=1.0)
    df["health_index"] = (1.0 - df["error_norm"]) * df[coverage_col]
    df["health_index"] = df["health_index"].clip(0.0, 1.0)
    logger.info(
        f"Health index — mean={df['health_index'].mean():.4f}  "
        f"median={df['health_index'].median():.4f}"
    )
    return df
