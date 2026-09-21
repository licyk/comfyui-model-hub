"""Transfer Hub worker events to ComfyUI's event loop."""

import asyncio
from collections.abc import Callable
from typing import Any

EVENT_NAME = "comfyui-model-hub.models-changed"


def subscribe_changes(services: Any, loop: asyncio.AbstractEventLoop, notify: Callable[[], None]) -> Callable[[], None]:
    """Debounce completed downloads and file operations; never touch ComfyUI from Hub threads."""
    timer: asyncio.TimerHandle | None = None
    active = True

    def flush() -> None:
        nonlocal timer
        timer = None
        if active:
            notify()

    def schedule() -> None:
        nonlocal timer
        if active and timer is None:
            timer = loop.call_later(0.4, flush)

    def handler(event: Any) -> None:
        if active and event.__event_name__ in {"download_completed", "library_changed"}:
            try:
                loop.call_soon_threadsafe(schedule)
            except RuntimeError:
                pass  # The application event loop has already closed.

    unsubscribe = services.events.subscribe(handler)

    def close() -> None:
        nonlocal active
        active = False
        unsubscribe()
        if timer is not None:
            timer.cancel()

    return close
