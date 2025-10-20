"""Type stubs for asyncpg."""

from typing import Any, AsyncContextManager

class Pool:
    """AsyncPG connection pool."""

    def acquire(
        self, *, timeout: float | None = None
    ) -> AsyncContextManager[Connection]: ...
    async def close(self) -> None: ...
    def get_size(self) -> int: ...
    def get_idle_size(self) -> int: ...

class Connection:
    """AsyncPG database connection."""

    async def execute(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> str: ...
    async def fetch(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> list[Record]: ...
    async def fetchrow(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> Record | None: ...
    async def fetchval(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> Any: ...
    def transaction(self) -> AsyncContextManager[Transaction]: ...

class Transaction:
    """Database transaction context."""

    ...

class Record:
    """Query result record."""

    def __getitem__(self, key: str | int) -> Any: ...
    def get(self, key: str, default: Any = None) -> Any: ...

async def create_pool(
    dsn: str | None = None,
    *,
    min_size: int = 10,
    max_size: int = 10,
    max_queries: int = 50000,
    max_inactive_connection_lifetime: float = 300.0,
    timeout: float = 60.0,
    **connect_kwargs: Any,
) -> Pool: ...
