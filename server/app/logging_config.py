"""
Structured JSON logging for Railway/Render log viewers.

Outputs one JSON object per log line so that log aggregators can
parse, filter, and sort fields like timestamp, level, request path,
response time, etc.
"""

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Standard fields:
        timestamp, level, logger, message

    Optional extras (passed via `extra={}` on logger calls):
        method, path, status_code, duration_ms, model, error_type, ...
    """

    # Fields that are part of the LogRecord and should NOT appear as "extra"
    _BUILTIN = frozenset({
        "name", "msg", "args", "created", "relativeCreated",
        "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "filename", "module", "pathname", "thread", "threadName",
        "process", "processName", "levelname", "levelno", "message",
        "msecs", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Exception info
        if record.exc_info and record.exc_info[0] is not None:
            log_obj["error_type"] = record.exc_info[0].__name__
            log_obj["error_detail"] = self.formatException(record.exc_info)

        # Merge any extra fields passed by the caller
        for key, value in record.__dict__.items():
            if key not in self._BUILTIN and key not in log_obj:
                log_obj[key] = value

        return json.dumps(log_obj, ensure_ascii=False, default=str)


def setup_logging(debug: bool = False) -> None:
    """
    Configure the root logger with JSON output.

    Call once at app startup (before any other logging).
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Clear any existing handlers to avoid duplicate output
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("groq").setLevel(logging.WARNING)
