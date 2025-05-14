"""
Logging configuration for the application.

This module provides a centralized logging configuration that can be used throughout
the application to ensure consistent logging behavior.
"""

import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from typing import Optional, Union, Dict, Any

# Default log format
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

class LogManager:
    """Manager for configuring and accessing loggers throughout the application."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure a single LogManager instance."""
        if cls._instance is None:
            cls._instance = super(LogManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the log manager if not already initialized."""
        if not getattr(self, "_initialized", False):
            self.root_logger = logging.getLogger("smart_pdf_parser")
            self.loggers: Dict[str, logging.Logger] = {}
            self.log_level = logging.INFO
            self.log_format = DEFAULT_LOG_FORMAT
            self.log_file: Optional[str] = None
            self.max_file_size = 10 * 1024 * 1024  # 10 MB
            self.backup_count = 3
            self._initialized = True
    
    def configure(self, 
                  level: Union[int, str] = logging.INFO, 
                  log_format: str = DEFAULT_LOG_FORMAT,
                  log_file: Optional[str] = None,
                  max_file_size: int = 10 * 1024 * 1024,
                  backup_count: int = 3) -> None:
        """
        Configure the logging system.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_format: Format string for log messages
            log_file: Path to log file (if None, logs to console only)
            max_file_size: Maximum size in bytes before rotating log files
            backup_count: Number of backup log files to keep
        """
        # Convert string level to int if needed
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        
        self.log_level = level
        self.log_format = log_format
        self.log_file = log_file
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        # Configure root logger
        self.root_logger.setLevel(self.log_level)
        
        # Remove existing handlers
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)
        
        # Create formatter
        formatter = logging.Formatter(self.log_format)
        
        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.root_logger.addHandler(console_handler)
        
        # Add file handler if log file is specified
        if self.log_file:
            # Ensure log directory exists
            log_dir = os.path.dirname(self.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count
            )
            file_handler.setFormatter(formatter)
            self.root_logger.addHandler(file_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger with the specified name.
        
        Args:
            name: Logger name, typically the module name using __name__
            
        Returns:
            Logger instance
        """
        logger_name = f"smart_pdf_parser.{name}"
        
        if logger_name not in self.loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(self.log_level)
            self.loggers[logger_name] = logger
            
        return self.loggers[logger_name]


# Singleton instance
log_manager = LogManager()

def configure_logging(**kwargs: Any) -> None:
    """
    Configure the logging system.
    
    Args:
        **kwargs: Arguments to pass to LogManager.configure()
    """
    log_manager.configure(**kwargs)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the specified module.
    
    Args:
        name: Module name, typically __name__
        
    Returns:
        Logger instance
    """
    return log_manager.get_logger(name)