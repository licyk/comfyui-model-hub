# ComfyUI Model Hub

[中文说明](README-zh.md)

Open [SD Model Hub](https://pypi.org/project/sd-model-hub/) inside ComfyUI using the compact **Lucide Package** toolbar button (tooltip: **Model Manager**). Browse local models, discover online models, download repositories or direct links, and use the original Hub settings interface.

- Closing the window preserves its state and leaves downloads running.
- Uses ComfyUI's registered model directories, including extra paths and legacy aliases.
- The first directory option, **所有模型目录** (All model directories), opens ComfyUI's main `models` folder and its subdirectories; external paths keep their own entries.
- Refreshes ComfyUI model lists after downloads and file operations.
- Starts the Hub on demand, with no model scan during ComfyUI startup.
- Reuses the dependency installation framework from [ComfyUI-HakuImg](https://github.com/licyk/ComfyUI-HakuImg). No Node.js build is needed.

## Installation

From the ComfyUI directory, clone the extension using Git:

```bash
git clone https://github.com/licyk/comfyui-model-hub.git custom_nodes/comfyui-model-hub
```

Restart ComfyUI and refresh the browser. The prestartup script automatically installs missing/incompatible dependencies using ComfyUI's own Python interpreter.

Requires Python 3.10+, ComfyUI's V3 `ComfyExtension` and `get_system_user_directory()` APIs, and a frontend supporting `actionBarButtons`. The source baseline is ComfyUI 0.35.0 / frontend 1.55.9; older top menus are not a supported compatibility target. The Hub dependency is `sd-model-hub>=0.1.9`, with its built UI included.

## Behavior

Use the top button or **Tools → Open Model Manager**. The window opens the local library and supports maximize, close, and retry. Hub directories are read when first opened and fixed by ComfyUI; restart after changing ComfyUI path configuration.

The toolbar uses the same native ComfyUI button sizing as comfyui-browser, with a Lucide Package icon. **Open in new tab** is always available in the dialog header, including after startup failure. The new tab starts Hub independently from its own origin before opening the library.

Each registered model directory becomes a stable Hub root, deduplicated by resolved path. Default destinations follow ComfyUI's per-category path order. Auxiliary VAE and latent upscaler directories do not replace primary defaults. Unknown extension model categories remain browsable without an assumed model kind. Discovery does not create missing directories. Root locking does not restrict Hub's existing absolute download destinations or server-side imports.

One Hub and download queue are shared by the ComfyUI instance. Settings, credentials, the database and caches live under `<ComfyUI user directory>/__model_hub/`, separate from the extension and standalone Hub data.

Startup errors show the HTTP status and request path. For 404 / 405, check extension loading and proxy routes; for 401 / 403, check authentication and the public URL configuration. A 200 response without a Hub startup result may be a login page or frontend HTML. Restart ComfyUI and hard-refresh the browser after updating the extension.

## Remote access

All browser traffic uses ComfyUI's same-origin `/model-hub/` path. The private Hub binds a random loopback port and is authenticated using a backend-only token. The proxy supports streaming HTTP, WebSocket and Socket.IO polling. No additional public port is needed.

Forward the entire ComfyUI deployment path, including WebSocket upgrades. Valid browser origins accompanied by `Sec-Fetch-Site: same-origin` remain accepted after proxy TLS termination or Host rewriting. Cross-site and opaque (`Origin: null`) requests remain rejected; use **Open in new tab** if ComfyUI is embedded in a sandbox or another website.

For Civitai OAuth, or proxies that remove browser origin metadata, explicitly set the public Hub URL, including any proxy prefix:

```bash
export COMFYUI_MODEL_HUB_PUBLIC_BASE_URL=https://example.com/comfy/model-hub
```

Register `https://example.com/comfy/model-hub/api/v1/auth/civitai/callback` with the OAuth provider as required by Hub. Client-supplied forwarding headers do not choose callback URLs. Manual source tokens work without OAuth configuration.

Hub inherits access to ComfyUI; ComfyUI user IDs do not provide separate Hub authorization. Existing deployment authentication must cover both HTTP and WebSocket paths.

Set `COMFYUI_MODEL_HUB_AUTO_INSTALL=0` to manage dependencies manually. Installer logging can be configured through `COMFYUI_MODEL_HUB_LOGGER_NAME`, `COMFYUI_MODEL_HUB_LOGGER_LEVEL` (default `20`) and `COMFYUI_MODEL_HUB_LOGGER_COLOR` (`0` disables color).

## Development

```bash
python -m playwright install chromium
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m ty check --python /path/to/comfy/python
node --check js/model_hub.js
node --check js/dialog.js
node tests/test_startup.mjs
```

Type checking expects ComfyUI at `../ComfyUI`; otherwise pass `--extra-search-path /path/to/ComfyUI`. Browser tests optionally accept `PLAYWRIGHT_CHROMIUM_EXECUTABLE`.

Tests use the real released Hub, temporary model directories, and a local download source. Chromium tests use the real Hub UI inside a small host implementing the public ComfyUI extension registration contract. They do not substitute for a full ComfyUI frontend/GPU workflow check.

Licensed under [GPL-3.0-only](LICENSE). See [NOTICE](NOTICE) for the copied installation framework's attribution and modifications.
