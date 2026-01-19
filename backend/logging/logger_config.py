import logging
import sys
from datetime import datetime
from pathlib import Path
import json
from typing import Dict, Any

class CustomFormatter(logging.Formatter):
    """Custom formatter to add color and structure to logs"""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info']:
                log_entry[key] = value
                
        return json.dumps(log_entry)


def setup_logger(
    name: str = __name__,
    log_file: str = None,
    level: int = logging.INFO,
    use_json: bool = False,
    include_console: bool = True
) -> logging.Logger:
    """
    Function to setup a logger with both file and console handlers
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent adding handlers multiple times
    if logger.handlers:
        return logger
    
    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = CustomFormatter()
    
    # Console handler
    if include_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        # Create directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        
        if use_json:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_app_logger(name: str = "app") -> logging.Logger:
    """Get application logger with standard configuration"""
    return setup_logger(
        name=name,
        log_file="logs/app.log",
        level=logging.INFO,
        include_console=True
    )


def get_error_logger(name: str = "error") -> logging.Logger:
    """Get error logger with detailed configuration"""
    return setup_logger(
        name=name,
        log_file="logs/error.log",
        level=logging.ERROR,
        include_console=True
    )


def get_audit_logger(name: str = "audit") -> logging.Logger:
    """Get audit logger for tracking important events"""
    return setup_logger(
        name=name,
        log_file="logs/audit.log",
        level=logging.INFO,
        use_json=True
    )


# Global loggers
app_logger = get_app_logger()
error_logger = get_error_logger()
audit_logger = get_audit_logger()