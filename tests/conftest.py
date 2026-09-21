"""Exercise the released Hub behind a real aiohttp server with temporary models."""

import sys
from pathlib import Path

import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comfyui_model_hub.model_paths import collect_model_paths
from comfyui_model_hub.proxy import HubProxy
from comfyui_model_hub.service import HubService


@pytest_asyncio.fixture
async def hub(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    notifications = []
    service = HubService(
        tmp_path / "data", lambda: collect_model_paths({"loras": ([str(models)], set())}), lambda: notifications.append(True)
    )
    proxy = HubProxy(service)
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app.router.add_get("/model-hub-extension/status", proxy.status)
    app.router.add_post("/model-hub-extension/start", proxy.start)
    app.router.add_route("*", "/model-hub/{tail:.*}", proxy.handle)
    # ComfyUI also publishes every extension route under /api.
    app.router.add_route("*", "/api/model-hub/{tail:.*}", proxy.handle)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        yield service, proxy, client, models, notifications
    finally:
        await proxy.close()
        await service.close()
        await client.close()
