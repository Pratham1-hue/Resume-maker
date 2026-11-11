import logging
import sys
from typing import Any


def get_logger(name: str = __name__) -> logging.Logger:
    """Get a configured logger instance."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# Setup default application logger
setup_logging = get_logger