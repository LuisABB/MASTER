"""Logging configuration using loguru."""
import sys
from loguru import logger
from app.config import Config

# Remove default handler
logger.remove()

# Add custom handler with JSON formatting for production
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level=Config.LOG_LEVEL.upper(),  # Convert to uppercase (INFO, DEBUG, etc.)
    serialize=False,  # Set to True for JSON logs in production
    colorize=True
)

__all__ = ['logger']
