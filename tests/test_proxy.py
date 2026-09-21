import gzip

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer, make_mocked_request

from comfyui_model_hub.proxy import check_origin


@pytest.mark.parametrize("origin", ["https://example.com", "http://example.com", "http://127.0.0.1:8188"])
def test_tls_proxy_requires_the_configured_public_origin(origin):
    request = make_mocked_request("POST", "/model-hub/api/v1/library/delete", headers={"Host": "127.0.0.1:8188", "Origin": origin})
    if origin == "http://example.com":
        with pytest.raises(web.HTTPForbidden):
            check_origin(request, "https://example.com/comfy/model-hub")
    else:
        check_origin(request, "https://example.com/comfy/model-hub")


def test_cross_site_oauth_callback_is_the_only_exception():
    request = make_mocked_request("GET", "/model-hub/api/v1/auth/civitai/callback", headers={"Sec-Fetch-Site": "cross-site"})
    check_origin(request)
    request = make_mocked_request("POST", "/model-hub/api/v1/auth/civitai/callback", headers={"Sec-Fetch-Site": "cross-site"})
    with pytest.raises(web.HTTPForbidden):
        check_origin(request)


@pytest.mark.parametrize(
    "host, origin",
    [
        ("example.com", "https://example.com"),
        ("127.0.0.1:8188", "https://comfy.example.com"),
        ("localhost:8188", "https://comfy.example.com:9443"),
    ],
)
@pytest.mark.parametrize("method", ["POST", "GET"])
def test_browser_same_origin_survives_tls_and_host_rewriting(host, origin, method):
    request = make_mocked_request(
        method,
        "/model-hub/api/v1/library/roots",
        headers={
            "Host": host,
            "Origin": origin,
            "Sec-Fetch-Site": "same-origin",
            **({"Upgrade": "websocket"} if method == "GET" else {}),
        },
    )
    check_origin(request)


@pytest.mark.parametrize(
    "origin, fetch_site",
    [
        ("https://evil.example", "cross-site"),
        ("https://other.example", "same-site"),
        ("null", "same-origin"),
        ("http://[", "same-origin"),
    ],
)
def test_cross_site_or_opaque_origins_remain_rejected(origin, fetch_site):
    request = make_mocked_request(
        "POST",
        "/model-hub-extension/start",
        headers={
            "Host": "localhost:8188",
            "Origin": origin,
            "Sec-Fetch-Site": fetch_site,
            "X-Forwarded-Host": "evil.example",
            "X-Forwarded-Proto": "https",
        },
    )
    with pytest.raises(web.HTTPForbidden):
        check_origin(request)


async def test_streaming_headers_cookie_and_redirect_handling(hub):
    service, _, client, _, _ = hub
    await service.ensure_started()
    real_hub = service._hub
    captured = []

    async def upstream(request):
        captured.append(dict(request.headers))
        if request.match_info["tail"] == "redirect":
            raise web.HTTPTemporaryRedirect(location=f"http://{request.host}/model-hub/destination")
        headers = {"Content-Encoding": "gzip", "Content-Type": "text/plain", "Cache-Control": "public, max-age=60"}
        response = web.Response(body=gzip.compress(b"body compressed once"), headers=headers)
        response.set_cookie("sd_model_hub_oauth", "transaction", path="/model-hub/api/v1/auth/civitai", httponly=True, samesite="Lax")
        response.set_cookie("second", "preserved")
        return response

    app = web.Application()
    app.router.add_route("*", "/model-hub/{tail:.*}", upstream)
    async with TestServer(app) as target:

        class Endpoint:
            running = True
            url = str(target.make_url("/model-hub"))

        service._hub = Endpoint()
        try:
            response = await client.get(
                "/model-hub/compressed",
                headers={
                    "Authorization": "Bearer external-token",
                    "X-Forwarded-Host": "evil.example",
                    "Cookie": "comfy_session=private; sd_model_hub_oauth=binding",
                },
            )
            assert await response.text() == "body compressed once"
            assert response.headers["Cache-Control"] == "public, max-age=60"
            assert len(response.headers.getall("Set-Cookie")) == 2
            assert captured[0]["Authorization"] == "Bearer " + service.token
            assert "X-Forwarded-Host" not in captured[0]
            assert captured[0]["Cookie"] == "sd_model_hub_oauth=binding"
            response = await client.get("/api/model-hub/redirect", allow_redirects=False)
            assert response.status == 307
            assert response.headers["Location"] == "/api/model-hub/destination"
        finally:
            service._hub = real_hub


@pytest.mark.parametrize("chunked", [False, True])
async def test_oversized_upload_is_rejected_without_saving(hub, chunked):
    service, _, client, models, _ = hub
    await service.ensure_started()
    root = service._hub.services.library.list_roots()[0]

    async def body():
        for _ in range(48):
            yield b"x" * (64 * 1024)

    response = await client.put(
        "/model-hub/api/v1/library/upload",
        params={"root_id": root.id, "name": "large.bin"},
        data=body() if chunked else b"x" * (3 * 1024 * 1024),
    )
    assert response.status == 413
    assert not (models / "large.bin").exists()
