import sys

from loguru import logger

# Remove default handlers and add stdout with a concise format suitable for console
logger.remove()
logger.add(
    sys.stdout,
    level="DEBUG",
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
)

__all__ = ["logger"]
