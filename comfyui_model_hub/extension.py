"""Register the service with ComfyUI's V3 extension lifecycle."""

import atexit
from pathlib import Path
from urllib.parse import urlsplit

from comfy_api.latest import ComfyExtension

from .events import EVENT_NAME
from .model_paths import collect_model_paths
from .proxy import HubProxy
from .runtime.config import public_base_url
from .service import HubService


class ModelHubExtension(ComfyExtension):
    async def get_node_list(self) -> list:
        return []

    async def on_load(self) -> None:
        import folder_paths
        from comfy.cli_args import args
        from server import PromptServer

        server = getattr(PromptServer, "instance")
        if getattr(server, "_model_hub_extension", None) is not None:
            return

        def notify() -> None:
            paths = collect_model_paths(folder_paths.folder_names_and_paths)
            for category in paths.categories:
                folder_paths.filename_list_cache.pop(category, None)
            folder_paths.cache_helper.clear()
            server.send_sync(EVENT_NAME, {})

        service = HubService(
            Path(folder_paths.get_system_user_directory("model_hub")),
            lambda: collect_model_paths(folder_paths.folder_names_and_paths, folder_paths.models_dir),
            notify,
            public_base_url(),
        )
        loopback = {"127.0.0.1", "localhost", "::1"}
        listeners = set(args.listen.split(","))
        hosts = loopback.copy() if listeners <= loopback else None
        if hosts is not None and service.public_base_url:
            hostname = urlsplit(service.public_base_url).hostname
            if hostname:
                hosts.add(hostname)
        proxy = HubProxy(service, hosts)
        server.routes.get("/model-hub-extension/open")(proxy.open_page)
        server.routes.get("/model-hub-extension/open.js")(proxy.open_script)
        server.routes.get("/model-hub-extension/status")(proxy.status)
        server.routes.post("/model-hub-extension/start")(proxy.start)
        server.routes.get("/model-hub")(proxy.handle)
        server.routes.route("*", "/model-hub/{tail:.*}")(proxy.handle)

        async def shutdown(_app) -> None:
            await proxy.close()
            await service.close()
            atexit.unregister(service.stop_at_exit)

        server.app.on_shutdown.append(shutdown)
        atexit.register(service.stop_at_exit)
        server._model_hub_extension = (service, proxy)
