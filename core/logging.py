import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger.json import JsonFormatter

from app.core.config import get_settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
        )
    )
    handler.addFilter(ContextFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
