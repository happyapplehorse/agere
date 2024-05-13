import logging


class NullHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        pass


def get_null_logger(name: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name or __name__)
    logger.addHandler(NullHandler())
    logger.propagate = False
    return logger
