"""Type stubs for apscheduler.schedulers.asyncio."""

from typing import Any, Callable

class AsyncIOScheduler:
    """Async IO scheduler for APScheduler."""

    def __init__(self, **options: Any) -> None: ...
    def add_job(
        self,
        func: Callable[..., Any],
        trigger: str | None = None,
        *,
        minutes: int | None = None,
        hours: int | None = None,
        id: str | None = None,
        replace_existing: bool = False,
        coalesce: bool = True,
        max_instances: int = 1,
        **trigger_args: Any,
    ) -> Job: ...
    def start(self) -> None: ...
    def shutdown(self, wait: bool = True) -> None: ...

class Job:
    """Scheduled job."""

    ...
