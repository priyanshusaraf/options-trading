import sys
from loguru import logger
from .config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    logger.add(
        settings.data_dir / "logs" / "app.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        compression="gz",
    )


__all__ = ["logger", "configure_logging"]
