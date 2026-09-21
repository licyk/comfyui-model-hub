import asyncio
import hashlib

import pytest
import socketio
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer

from comfyui_model_hub.model_paths import collect_model_paths


async def start(client):
    response = await client.post("/model-hub-extension/start")
    assert response.status == 200, await response.text()
    assert (await response.json())["state"] == "ready"


async def test_start_is_singleton_and_private_port_requires_token(hub):
    service, _, client, _, _ = hub
    assert (await (await client.get("/model-hub-extension/status")).json())["state"] == "stopped"
    await asyncio.gather(*(start(client) for _ in range(4)))
    url = service.upstream
    await start(client)
    assert service.upstream == url
    async with ClientSession() as direct:
        response = await direct.get(url + "/api/v1/library/roots")
        assert response.status == 401
    response = await client.get("/model-hub/api/v1/library/roots")
    assert response.status == 200
    roots = await response.json()
    assert len(roots) == 1
    response = await client.post("/model-hub/api/v1/library/roots", json={"path": "/tmp", "layout": "custom"})
    assert response.status == 409
    await service.close()
    assert service.status()["state"] == "stopped"


async def test_ui_assets_alias_routes_and_default_destination(hub):
    _, _, client, models, _ = hub
    await start(client)
    response = await client.get("/model-hub/")
    html = await response.text()
    assert response.status == 200 and 'id="app"' in html
    import re

    asset = re.search(r'src="(\./assets/[^\"]+\.js)"', html).group(1)
    response = await client.get("/model-hub/" + asset.removeprefix("./"))
    assert response.status == 200
    assert "javascript" in response.headers["Content-Type"]
    response = await client.get("/api/model-hub/api/v1/library/destination?kind=lora")
    destination = await response.json()
    assert destination["rel_dir"] == ""
    assert models.exists()


async def test_complete_directory_browsing_preserves_download_defaults(hub):
    service, _, client, models, _ = hub
    checkpoints = models / "checkpoints"
    checkpoints.mkdir()
    external = models.parent / "external-loras"
    external.mkdir()
    service.paths = lambda: collect_model_paths(
        {"checkpoints": ([str(checkpoints)], set()), "loras": ([str(external)], set())}, models
    )
    await start(client)
    roots = await (await client.get("/model-hub/api/v1/library/roots")).json()
    complete = roots[0]
    assert complete["name"] == "所有模型目录"
    assert complete["path"] == str(models)
    response = await client.get(f"/model-hub/api/v1/library/roots/{complete['id']}/entries")
    assert response.status == 200, await response.text()
    assert "checkpoints" in await response.text()
    by_id = {root["id"]: root for root in roots}
    for query, expected in [("", checkpoints), ("?kind=checkpoint", checkpoints), ("?kind=lora", external)]:
        response = await client.get("/model-hub/api/v1/library/destination" + query)
        assert response.status == 200, await response.text()
        destination = await response.json()
        assert by_id[destination["root_id"]]["path"] == str(expected)
        assert destination["rel_dir"] == ""


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Origin": "http://["},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ],
)
async def test_cross_origin_start_cannot_launch_service(hub, headers):
    service, _, client, _, _ = hub
    response = await client.post("/model-hub-extension/start", headers=headers)
    assert response.status == 403
    assert response.content_type == "application/json"
    assert (await response.json())["error"]
    assert service.state == "stopped"


async def test_streamed_upload_unicode_and_change_notification(hub):
    _, _, client, models, notifications = hub
    await start(client)
    roots = await (await client.get("/model-hub/api/v1/library/roots")).json()
    root_id = roots[0]["id"]
    content = b"test model" * 10000

    async def body():
        for index in range(0, len(content), 1024):
            yield content[index : index + 1024]

    response = await client.put(
        "/model-hub/api/v1/library/upload",
        params={"root_id": root_id, "name": "模型 #1.bin"},
        data=body(),
        headers={"Origin": str(client.make_url("/")).rstrip("/")},
    )
    assert response.status == 201, await response.text()
    assert (models / "模型 #1.bin").read_bytes() == content
    await asyncio.sleep(0.6)
    assert notifications


@pytest.mark.parametrize("transport", ["websocket", "polling"])
async def test_socketio_events_through_both_transports(hub, transport):
    service, _, client, _, _ = hub
    await start(client)
    socket = socketio.AsyncClient()
    arrived = asyncio.Event()
    socket.on("library_changed", lambda _event: arrived.set())
    try:
        await socket.connect(str(client.make_url("/")), socketio_path="model-hub/ws/socket.io", transports=[transport])
        root = service._hub.services.library.list_roots()[0]
        service._hub.services.library.notify_changed(root.id, "")
        await asyncio.wait_for(arrived.wait(), 5)
    finally:
        await socket.disconnect()


async def test_real_download_finishes_without_a_ui(hub):
    _, _, client, models, notifications = hub
    await start(client)
    payload = b"download fixture\n" * 32768
    app = web.Application()

    async def fixture_file(_):
        return web.Response(body=payload)

    app.router.add_get("/fixture.bin", fixture_file)
    async with TestServer(app) as source:
        response = await client.post(
            "/model-hub/api/v1/downloads",
            json={
                "url": str(source.make_url("/fixture.bin")),
                "expected_sha256": hashlib.sha256(payload).hexdigest(),
            },
        )
        assert response.status == 201, await response.text()
        job = await response.json()
        for _ in range(100):
            job = await (await client.get(f"/model-hub/api/v1/downloads/{job['id']}")).json()
            if job["state"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.1)
        assert job["state"] == "completed", job
        assert (models / "fixture.bin").read_bytes() == payload
        await asyncio.sleep(0.6)
        assert notifications
