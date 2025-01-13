import os
import functools
import logging
from logging.handlers import RotatingFileHandler


class LoggerTemplate:
    def __init__(self,
                 logger_name: str,
                 log_level: int,
                 log_handlers: list,
                 log_formatter: logging.Formatter
                 ):
        self.logger_name = logger_name
        self.log_level = log_level
        self.log_handlers = log_handlers
        self.log_formatter = log_formatter

    def create_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.logger_name)
        logger.setLevel(self.log_level)

        for handler in self.log_handlers:
            handler.setFormatter(self.log_formatter)
            logger.addHandler(handler)

        return logger


class CustomRotatingFileHandler(RotatingFileHandler):
    def rotation_filename(self, default_name):
        base_name = default_name.split(".")[0]
        count = default_name.split(".")[-1]
        return f"{base_name}_{count}.log"


def create_rotating_file_logger(logger_name: str,
                                log_file_path: str,
                                size_mb: int = 1,
                                bak_count: int = 2
                                ) -> logging.Logger:
    # Define the log format
    log_formatter = logging.Formatter(
        "[%(levelname)s] %(asctime)s | %(name)s | Line %(lineno)d | %(message)s"
    )

    file_path = str(LOG_DIR_PATH / log_file_path)

    # Set up the rotating file handler
    rotating_handler = CustomRotatingFileHandler(
        file_path,
        maxBytes=size_mb * 1024 * 1024,
        backupCount=bak_count
    )

    # Create a logger using the template
    logger_template = LoggerTemplate(
        logger_name=logger_name,
        log_level=logging.DEBUG,
        log_handler=rotating_handler,
        log_formatter=log_formatter
    )

    return logger_template.create_logger()


def create_console_logger(logger_name: str) -> logging.Logger:
    # Define the log format
    log_formatter = logging.Formatter(
        "[%(levelname)s] %(asctime)s | %(name)s | Line %(lineno)d | %(message)s"
    )

    console_handler = logging.StreamHandler()

    # Create a logger using the template
    logger_template = LoggerTemplate(
        logger_name=logger_name,
        log_level=logging.DEBUG,
        log_handlers=[console_handler],
        log_formatter=log_formatter
    )

    return logger_template.create_logger()


def result_logging_decorator(name: str):
    """
    Result logging decorator.

    Usage:
        Decorate any callable with return values
        Step 1: Create Environment Variable `MARSH_USE_LOGGER` with value `true` in terminal.
            - On Linux/MacOS: `export MARSH_USE_LOGGER=true`
            - On Windows (PowerShell): `$env:MARSH_USE_LOGGER="true"`
        Step 2: Decorate any callable with return values.
            `@result_logging_decorator(__name__)`
    """

    use_logger = True if os.getenv("MARSH_USE_LOGGER") == "true" else False
    logger = create_console_logger(name)

    def outer(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if use_logger:
                    logger.info(f"{func.__name__} result: {result}")
                return result
            except Exception as err:
                if use_logger:
                    logger.error(str(err))

        return wrapper

    return outer
