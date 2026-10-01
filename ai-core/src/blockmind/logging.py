from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """One JSON object per line for inspectable autonomous execution."""

    def format(self, record: logging.LogRecord) -> str:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "source": record.name,
            "message": record.getMessage(),
        }
        for key in ("category", "operation_id", "component_id", "position", "blocks", "progress",
                    "mode", "minecraft", "adapter", "protocol", "reason", "strategy", "capabilities", "target"):
            if hasattr(record, key):
                event[key] = getattr(record, key)
        return json.dumps(event, separators=(",", ":"), default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
