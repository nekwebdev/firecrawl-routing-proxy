from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger("route_decision")


def hash_query(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def log_route_decision(payload: dict[str, Any], *, enabled: bool = True) -> None:
    if enabled:
        logger.info(json.dumps(payload, sort_keys=True))
