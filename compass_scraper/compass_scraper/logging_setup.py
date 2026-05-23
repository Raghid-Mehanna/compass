"""
JSON structured logging for Compass.

Imported from settings.py at scrapy startup so the JSON handler is in place
before any spider, pipeline, or third-party library emits a log line.

In settings.py we also set LOG_ENABLED = False, which tells Scrapy not to
install its own plain-text handler on the root logger — otherwise our JSON
handler would compete with Scrapy's and the output would be a mix.
"""

import logging
import sys

from pythonjsonlogger import jsonlogger


def configure_json_logging(level: str = "INFO") -> None:
    """Install a single JSON handler on the root logger and remove others."""
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
        },
    )

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
