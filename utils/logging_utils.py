import sys
import os
from config.settings import BASE_DIR

LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

try:
    from loguru import logger

    # Configure loguru
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level}")
    logger.add(os.path.join(LOG_DIR, "app.log"), rotation="10 MB", retention="10 days", level="INFO")

    def get_logger(name):
        return logger.bind(name=name)

except Exception:
    # Fallback to standard library logging when loguru is unavailable
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        stream=sys.stdout,
    )

    class _StdLoggerWrapper:
        def __init__(self, name):
            self._logger = logging.getLogger(name)

        def bind(self, **kwargs):
            # Keep API parity with loguru's bind
            return self

        def debug(self, *args, **kwargs):
            return self._logger.debug(*args, **kwargs)

        def info(self, *args, **kwargs):
            return self._logger.info(*args, **kwargs)

        def warning(self, *args, **kwargs):
            return self._logger.warning(*args, **kwargs)

        def error(self, *args, **kwargs):
            return self._logger.error(*args, **kwargs)

        def exception(self, *args, **kwargs):
            return self._logger.exception(*args, **kwargs)

    def get_logger(name):
        return _StdLoggerWrapper(name)
