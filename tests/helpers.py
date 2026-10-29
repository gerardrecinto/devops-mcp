import json
from typing import Any


def load(raw: str) -> Any:
    """json.loads that unwraps the demo-mode envelope."""
    body = json.loads(raw)
    if isinstance(body, dict) and body.get("demo") is True:
        return body["data"]
    return body
