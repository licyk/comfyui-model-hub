"""Own a lazily started Hub server without blocking ComfyUI's event loop."""

import asyncio
import logging
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .events import subscribe_changes
from .model_paths import ModelPaths

logger = logging.getLogger("ComfyUI-Model-Hub")
HUB_PREFIX = "/model-hub"


class HubService:
    def __init__(
        self,
        data_dir: Path,
        paths: Callable[[], ModelPaths],
        notify: Callable[[], None],
        public_base_url: str | None = None,
        factory: Callable[..., Any] | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.paths = paths
        self.notify = notify
        self.public_base_url = public_base_url
        self.token = secrets.token_urlsafe(32)
        self._factory = factory
        self._hub: Any = None
        self._starting: asyncio.Task[None] | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._closing = False
        self.state = "stopped"
        self.error: str | None = None

    @property
    def upstream(self) -> str:
        if self._hub is None or not self._hub.running:
            raise RuntimeError("SD Model Hub is not running")
        return self._hub.url

    def status(self) -> dict[str, Any]:
        state = self.state
        if state == "ready" and (self._hub is None or not self._hub.running):
            state = "failed"
        return {"state": state, "error": self.error if state != "ready" else None}

    async def ensure_started(self) -> None:
        if self._closing:
            raise RuntimeError("SD Model Hub is shutting down")
        if self.status()["state"] == "ready":
            return
        if self._starting is None or self._starting.done():
            self._starting = asyncio.create_task(self._start())
            # Observe errors even if the browser disconnects during startup.
            self._starting.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
        await asyncio.shield(self._starting)

    async def _start(self) -> None:
        self.state, self.error = "starting", None
        try:
            if self._unsubscribe:
                self._unsubscribe()
                self._unsubscribe = None
            paths = self.paths()
            await asyncio.to_thread(self._start_sync, paths)
            self._unsubscribe = subscribe_changes(self._hub.services, asyncio.get_running_loop(), self.notify)
            self.state = "ready"
        except Exception as exc:
            self.state, self.error = "failed", str(exc)
            logger.exception("Could not start SD Model Hub")
            raise

    def _start_sync(self, paths: ModelPaths) -> None:
        from sd_model_hub import ModelHubServer, ModelRoot
        from sd_model_hub.api.static import web_dist_dir

        if self._hub is not None:
            self._hub.stop()
            self._hub = None
        if not (web_dist_dir() / "index.html").is_file():
            raise RuntimeError("SD Model Hub's web UI is missing. Install its release wheel, or build its web UI first.")
        downloads: dict[str, Any] = {"kind_destinations": paths.destinations}
        if paths.default_download_root is not None:
            downloads["default_root"] = paths.default_download_root
        self._hub = (self._factory or ModelHubServer)(
            data_dir=self.data_dir,
            model_roots=[ModelRoot(**root) for root in paths.roots],
            lock_model_roots=True,
            host="127.0.0.1",
            port=0,
            open_browser=False,
            access_token=self.token,
            api_prefix=HUB_PREFIX,
            public_base_url=self.public_base_url,
            settings={"downloads": downloads, "server": {"allowed_origins": []}},
        )
        try:
            self._hub.start()
        except BaseException:
            self._hub.stop()
            self._hub = None
            raise

    async def close(self) -> None:
        self._closing = True
        if self._starting is not None:
            try:
                await asyncio.shield(self._starting)
            except Exception:
                pass
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        await asyncio.to_thread(self.stop_at_exit)
        self.state = "stopped"

    def stop_at_exit(self) -> None:
        """ComfyUI's direct CLI shutdown does not currently clean up its aiohttp runner."""
        hub, self._hub = self._hub, None
        if hub is not None:
            hub.stop()
