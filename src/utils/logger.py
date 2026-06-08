"""
Logging utilities for telemetry health evaluation framework.
Follows programming_rules.md Section 7 (Logging Standards)
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str,
    log_dir: Optional[Path] = None,
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
) -> logging.Logger:
    """
    Set up structured logger with file and console handlers.
    
    Parameters
    ----------
    name : str
        Logger name
    log_dir : Optional[Path]
        Directory for log files. If None, uses ./logs
    level : int
        Logging level (e.g., logging.INFO, logging.DEBUG)
    log_to_file : bool
        Enable file logging
    log_to_console : bool
        Enable console logging
        
    Returns
    -------
    logging.Logger
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_to_file:
        if log_dir is None:
            log_dir = Path.cwd() / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log file with date
        log_file = log_dir / f"telemetry_pipeline_{datetime.now().strftime('%Y%m%d')}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get logger by name.
    
    Parameters
    ----------
    name : str
        Logger name
        
    Returns
    -------
    logging.Logger
        Logger instance
    """
    return logging.getLogger(name)
