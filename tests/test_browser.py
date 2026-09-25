"""Real Chromium + released Hub UI, with a small Comfy extension API harness.

The harness exercises the extension's public registration contract; it is not a full
ComfyUI frontend or a GPU workflow test.
"""

import os
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestServer
from playwright.async_api import async_playwright, expect

from comfyui_model_hub.model_paths import collect_model_paths
from comfyui_model_hub.proxy import HubProxy
from comfyui_model_hub.service import HubService

API_JS = """
export const api = new EventTarget();
api.fileURL = path => '/comfy' + path;
api.apiURL = path => '/comfy/api' + path;
api.fetchApi = (path, options) => fetch('/comfy/api' + path, options);
window.hubTestApi = api;
"""
APP_JS = """
window.hubTestRefreshes = 0;
const settings = document.createElement('div');
document.body.append(settings);
export const app = {
    menu: {settingsGroup: {element: settings}},
    extensionManager: {
        setting: {get: () => 'en'},
        command: {execute: async () => {window.hubTestRefreshes++;}},
    },
    async registerExtension(extension) {
        window.hubExtension = extension;
        await extension.setup?.();
        for (const action of extension.actionBarButtons || []) {
            const button = document.createElement('button');
            button.textContent = action.label || '';
            button.setAttribute('aria-label', action.tooltip);
            button.onclick = action.onClick;
            document.body.append(button);
        }
    },
};
"""
BUTTON_JS = """
export class ComfyButton {
    constructor({action, tooltip, content, classList}) {
        this.element = document.createElement('button');
        this.element.append(content);
        this.element.title = tooltip;
        this.element.className = classList;
        this.element.onclick = action;
    }
}
"""
GROUP_JS = """
export class ComfyButtonGroup {
    constructor(...buttons) {
        this.element = document.createElement('div');
        this.element.append(...buttons);
    }
}
"""


async def test_button_iframe_close_reopen_retry_and_refresh(tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    loras = model_dir / "loras"
    loras.mkdir()
    service = HubService(
        tmp_path / "data", lambda: collect_model_paths({"loras": ([str(loras)], set())}, model_dir), lambda: None
    )
    proxy = HubProxy(service)
    app = web.Application()

    async def page(_):
        return web.Response(
            text='<html><body><script type="module" src="/comfy/extensions/model-hub/model_hub.js"></script></body></html>',
            content_type="text/html",
        )

    async def api_js(_):
        return web.Response(text=API_JS, content_type="text/javascript")

    async def app_js(_):
        return web.Response(text=APP_JS, content_type="text/javascript")

    async def button_js(_):
        return web.Response(text=BUTTON_JS, content_type="text/javascript")

    async def group_js(_):
        return web.Response(text=GROUP_JS, content_type="text/javascript")

    app.router.add_get("/comfy/", page)
    app.router.add_get("/comfy/scripts/api.js", api_js)
    app.router.add_get("/comfy/scripts/app.js", app_js)
    app.router.add_get("/comfy/scripts/ui/components/button.js", button_js)
    app.router.add_get("/comfy/scripts/ui/components/buttonGroup.js", group_js)
    app.router.add_static("/comfy/extensions/model-hub/", Path(__file__).resolve().parents[1] / "js")
    app.router.add_post("/comfy/api/model-hub-extension/start", proxy.start)
    app.router.add_post("/comfy/model-hub-extension/start", proxy.start)
    app.router.add_get("/comfy/model-hub-extension/open", proxy.open_page)
    app.router.add_get("/comfy/model-hub-extension/open.js", proxy.open_script)
    app.router.add_route("*", "/comfy/model-hub/{tail:.*}", proxy.handle)
    async with TestServer(app) as server, async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            executable_path=os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE"),
            args=["--no-sandbox"],
        )
        try:
            tab = await browser.new_page()
            errors = []
            tab.on("pageerror", lambda error: errors.append(str(error)))
            await tab.goto(str(server.make_url("/comfy/")))
            button = tab.get_by_role("button", name="Model Manager", exact=True)
            await expect(button).to_have_text("")
            await expect(button.locator("i")).to_have_class("icon-[lucide--package] comfy-model-hub-icon")

            async def html_error(route):
                await route.fulfill(status=404, content_type="text/html", body="<html><body>Not found</body></html>")

            await tab.route("**/comfy/api/model-hub-extension/start", html_error)
            await button.click()
            await expect(tab.get_by_role("status")).to_contain_text("HTTP 404")
            await expect(tab.get_by_role("status")).to_contain_text("/comfy/api/model-hub-extension/start")
            await expect(tab.get_by_role("status")).to_contain_text("Restart ComfyUI")
            await expect(tab.locator("iframe")).to_be_hidden()
            await tab.unroute("**/comfy/api/model-hub-extension/start", html_error)

            async def forbidden_start(route):
                await route.fulfill(status=403, json={"state": "failed", "error": "Cross-origin model manager request refused"})

            await tab.route("**/comfy/api/model-hub-extension/start", forbidden_start)
            await tab.get_by_role("button", name="Retry", exact=True).click()
            await expect(tab.get_by_role("status")).to_contain_text("HTTP 403")
            # The parent cannot start Hub, but the link must still bootstrap a fresh tab.
            assert service.state == "stopped"
            async with tab.expect_popup() as popup_info:
                await tab.get_by_role("link", name="Open in new tab").click()
            popup = await popup_info.value
            await expect(popup.locator("p.root-path")).to_have_text(str(model_dir), timeout=30000)
            assert "/comfy/model-hub/#/library" in popup.url
            assert await popup.evaluate("window.opener === null")
            await popup.close()
            await tab.unroute("**/comfy/api/model-hub-extension/start", forbidden_start)

            # A deployment that refuses framing must be named instead of the generic failure.
            async def deny_framing(route):
                if route.request.resource_type != "document":
                    await route.continue_()
                    return
                await route.fulfill(
                    status=200,
                    content_type="text/html",
                    headers={"X-Frame-Options": "deny"},
                    body='<html><body><div id="app"></div></body></html>',
                )

            await tab.route("**/comfy/model-hub/**", deny_framing)
            await tab.get_by_role("button", name="Retry", exact=True).click()
            await expect(tab.get_by_role("status")).to_contain_text("X-Frame-Options")
            await expect(tab.locator("iframe")).to_be_hidden()
            await tab.unroute("**/comfy/model-hub/**", deny_framing)

            # A proxy adding only X-Frame-Options is overridden by the Hub's frame-ancestors policy.
            async def proxy_denies_framing(route):
                if route.request.resource_type != "document":
                    await route.continue_()
                    return
                response = await route.fetch()
                await route.fulfill(response=response, headers={**response.headers, "x-frame-options": "deny"})

            await tab.route("**/comfy/model-hub/**", proxy_denies_framing)
            await tab.get_by_role("button", name="Close", exact=True).click()
            await button.click()
            frame = tab.frame_locator("iframe")
            await expect(frame.get_by_role("navigation", name="Main", exact=True)).to_be_visible(timeout=30000)
            await expect(frame.locator("p.root-path")).to_have_text(str(model_dir))
            await tab.unroute("**/comfy/model-hub/**", proxy_denies_framing)
            await expect(frame.locator(".root-select md-select-option").first).to_have_text("所有模型目录")
            if os.getenv("MODEL_HUB_SCREENSHOT"):
                await tab.screenshot(path=os.environ["MODEL_HUB_SCREENSHOT"])
            assert service.state == "ready"
            hub_src = await tab.locator("iframe").get_attribute("src")
            assert "/comfy/model-hub/" in hub_src and hub_src.endswith("#/library")
            assert await tab.locator("iframe").count() == 1
            await frame.locator("body").evaluate("el => el.dataset.sessionMarker = 'kept'")
            await tab.get_by_role("button", name="Maximize", exact=True).click()
            await expect(tab.get_by_role("button", name="Restore", exact=True)).to_be_visible()
            await tab.get_by_role("button", name="Close", exact=True).click()
            await expect(button).to_be_focused()
            await button.click()
            assert await frame.locator("body").get_attribute("data-session-marker") == "kept"
            await tab.evaluate("for (let i=0;i<5;i++) window.hubTestApi.dispatchEvent(new CustomEvent('comfyui-model-hub.models-changed'))")
            await tab.wait_for_function("window.hubTestRefreshes === 1")
            await tab.get_by_role("button", name="Close", exact=True).click()
            # A failed restart remains recoverable through the visible Retry action.
            await service.close()
            service._closing = False
            original = service._factory

            def failure(**_):
                raise RuntimeError("Test restart failure")

            service._factory = failure
            await button.click()
            await expect(tab.get_by_role("button", name="Retry", exact=True)).to_be_visible()
            service._factory = original
            await tab.get_by_role("button", name="Retry", exact=True).click()
            await expect(frame.get_by_role("navigation", name="Main", exact=True)).to_be_visible(timeout=30000)
            await expect(frame.locator("p.root-path")).to_have_text(str(model_dir))
            assert errors == []
        finally:
            await browser.close()
            await proxy.close()
            await service.close()
