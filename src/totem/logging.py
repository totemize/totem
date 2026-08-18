"""Application logging configured for stdout-first service operation."""

import logging
from pathlib import Path
import sys
from typing import Optional, Union


_logger_instance: Optional[logging.Logger] = None


def setup_logger(
    name: str = "totem",
    level: int = logging.INFO,
    *,
    log_file: Optional[Union[str, Path]] = None,
) -> logging.Logger:
    """Configure Totem logging without writing into the source tree."""
    global _logger_instance

    configured = logging.getLogger(name)
    configured.handlers.clear()
    configured.setLevel(level)
    configured.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    configured.addHandler(console)

    if log_file is not None:
        file_path = Path(log_file).expanduser()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        configured.addHandler(file_handler)

    _logger_instance = configured
    return configured


def get_logger() -> logging.Logger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = setup_logger()
    return _logger_instance


logger = get_logger()
