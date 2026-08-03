"""Cancellation-safe helpers for blocking work owned by an async lane."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar


T = TypeVar("T")


async def to_thread_drained(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run ``fn`` off-loop and drain it before propagating cancellation.

    ``asyncio.to_thread`` cannot stop its worker.  Cancelling a task that awaits it
    normally abandons the still-running thread, which is unsafe when that thread
    owns a SQLite transaction or a broker session.  Shield the worker, then wait
    for it to finish before allowing lane shutdown to continue.
    """
    worker = asyncio.create_task(asyncio.to_thread(fn, *args, **kwargs))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        try:
            await worker
        except Exception:
            # Cancellation owns the control flow.  The lane's normal error path
            # handles worker failures when no cancellation is in progress.
            pass
        raise
