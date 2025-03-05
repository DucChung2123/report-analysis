import logging
import sys
import os
from pathlib import Path
from typing import Optional

try:
    from src.core.config import config

    log_level = config.get("logging.log_level", logging.INFO)
    log_file = config.get("logging.log_file", None)
except ImportError:
    log_level = logging.INFO
    log_file = None


def setup_logger(
    name: str, level: int | None = None, log_file: str | None = None
) -> logging.Logger:
    """
    Setup logger for the application

    Args:
        name (str): name of the logger
        level (Optional[int]): log level
        log_file (Optional[str]): path to log file

    Returns:
        logging.Logger: logger object
    """
    log_level_to_use = level if level is not None else log_level

    logger = logging.getLogger(name)
    logger.setLevel(log_level_to_use)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    console_handler.setLevel(logging.WARNING)
    log_file_to_use = log_file
    if log_file_to_use:
        log_dir = Path(log_file_to_use).parent
        os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(log_file_to_use, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


logger = setup_logger("finance_analyzer", log_level, log_file)

# if __name__ == "__main__":
#     logger.debug("Debug message")
#     logger.info("Info message")
#     logger.warning("Warning message")
