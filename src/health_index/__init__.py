"""
Health Index Module

Production-ready Health Index computation pipeline using LSTM autoencoders.
"""

from .config import WindowingConfig, LSTMAEModelConfig, HealthIndexConfig
from .preprocessing import LSTMAutoencoderPreprocessor
from .model import LSTMAutoencoderService
from .health_index import HealthIndexService
from .orchestration import ComponentPipeline, FullPipeline

__version__ = "1.0.0"

__all__ = [
    "WindowingConfig",
    "LSTMAEModelConfig",
    "HealthIndexConfig",
    "LSTMAutoencoderPreprocessor",
    "LSTMAutoencoderService",
    "HealthIndexService",
    "ComponentPipeline",
    "FullPipeline",
]
