"""Type stubs for slowapi."""

from typing import Any

from fastapi import Request, Response

def _rate_limit_exceeded_handler(request: Request, exc: Any) -> Response: ...

class Limiter:
    def __init__(self, **kwargs: Any) -> None: ...
    def limit(self, limit_value: str) -> Any: ...
