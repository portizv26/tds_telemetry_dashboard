"""
Telemetry Analysis Pipeline - Main Module

This module implements the telemetry analysis pipeline for mining equipment,
transforming raw sensor data into actionable health assessments.

Version: 1.0.0
"""

__version__ = "1.0.0"

from . import data_loader
from . import data_cleaner
from . import baseline
from . import scoring
from . import aggregation
from . import output_writer

__all__ = [
    'data_loader',
    'data_cleaner',
    'baseline',
    'scoring',
    'aggregation',
    'output_writer',
]
