# ComfyUI Model Hub

在 ComfyUI 顶部点击 **Lucide Package** 包裹图标（提示文字“模型管理器”），直接打开 [SD Model Hub](https://pypi.org/project/sd-model-hub/) 的模型库、在线浏览、Hub 仓库、链接下载和设置界面。

- 界面在 ComfyUI 内打开，支持最大化、关闭和重试；关闭窗口不停止下载。
- 自动接入 ComfyUI 已注册的模型目录，包括 `extra_model_paths.yaml`、自定义模型路径、旧 `clip` / `unet` 目录和其他扩展注册的模型目录。
- 目录列表首项“所有模型目录”可浏览 ComfyUI 主 `models` 文件夹及其子目录；主目录之外的模型路径保留独立入口。
- 下载完成及模型文件操作后自动刷新 ComfyUI 模型列表。
- 首次打开时启动服务，日常启动 ComfyUI 不扫描模型库。
- Python 安装和目录结构参考 [ComfyUI-HakuImg](https://github.com/licyk/ComfyUI-HakuImg)，无需 Node.js 或前端构建。

## 安装

在 ComfyUI 目录下使用 Git 克隆本扩展：

```bash
git clone https://github.com/licyk/comfyui-model-hub.git custom_nodes/comfyui-model-hub
```

重启 ComfyUI，刷新浏览器。扩展的 `prestartup_script.py` 会检查依赖，使用 **ComfyUI 当前运行的 Python** 安装缺失或版本不兼容的依赖。

## 使用与目录

顶部按钮或 Tools 菜单中的 **Open Model Manager** 打开窗口，默认进入本地模型库。窗口内可切换 Hub 原有的其他页面。顶部按钮与 comfyui-browser 使用相同的 ComfyUI 原生按钮尺寸，图标为 Lucide Package。

窗口标题栏提供 **在新标签页打开**。即使内嵌窗口启动失败，也可以使用此链接：新标签页会在自己的来源下独立启动 Hub，再进入模型库，无需先在原窗口启动成功。

每个实际模型目录显示为一个根目录，目录 ID 按路径稳定生成，符号链接指向相同目录时去重。每类默认下载目录遵循 ComfyUI 注册路径顺序；普通 VAE / 放大模型目录优先于 `vae_approx` / `latent_upscale_models`。未知的扩展模型类别也可以浏览，但不会猜测其模型类型。

目录列表由 ComfyUI 管理并在首次打开时读取，在 Hub 中不可新增或删除根目录。修改 ComfyUI 路径配置后重启生效。不存在的目录不会在发现阶段自动创建，实际写入由 Hub 处理。根目录锁定不限制 Hub 原有的绝对路径下载和服务器文件导入功能。

整个 ComfyUI 实例共享一个 Hub 和下载队列。配置、凭据、数据库及缓存位于：

```text
<ComfyUI user 目录>/__model_hub/
```

这会遵循 ComfyUI 的自定义 user 目录设置，不会写入扩展目录或占用独立 SD Model Hub 的默认数据目录。依赖自动安装失败时可查看启动日志排查原因；Hub 启动失败时窗口会显示原因并允许重试。

打开失败时，窗口会显示启动请求的 HTTP 状态码和路径。404 / 405 表示需要检查扩展后端是否加载及代理路由；401 / 403 表示需要检查访问权限或外部地址配置；200 但没有 Hub 启动结果通常表示返回了登录页或前端 HTML。更新扩展后需重启 ComfyUI，并强制刷新浏览器，避免继续加载旧的 JavaScript。

## 远程访问与反向代理

浏览器只访问 ComfyUI 同源的 `/model-hub/` 路径。Hub 在后台线程监听 `127.0.0.1` 随机端口，使用仅后端持有的随机访问令牌；不需要开放额外端口。扩展转发 HTTP、流式上传、Socket.IO WebSocket 和 polling。

现有反向代理需要把 ComfyUI 部署路径下的请求和 WebSocket 升级一起转发。若 ComfyUI 在 `https://example.com/comfy/`，配置：

```bash
export COMFYUI_MODEL_HUB_PUBLIC_BASE_URL=https://example.com/comfy/model-hub
```

浏览器提供有效 Origin 且 `Sec-Fetch-Site: same-origin` 时，即使代理终止 TLS 或改写 Host，扩展仍识别为同源请求；跨站请求和 `Origin: null` 仍会拒绝。ComfyUI 被嵌入其他站点或沙箱页面导致来源不可用时，可使用“在新标签页打开”。

窗口通过同源 iframe 嵌入 `/model-hub/`。扩展转发的 Hub 响应带有 `Content-Security-Policy: frame-ancestors 'self'`，浏览器会因此忽略反向代理或 CDN 添加的 `X-Frame-Options: DENY`。若代理自身的 `Content-Security-Policy` 设置了限制性的 `frame-ancestors`，或代理删除、替换了后端的 CSP 响应头，即使父页面同源也会被浏览器拒绝嵌入，窗口会提示嵌入被拒绝。请为 ComfyUI 所在站点允许 `frame-ancestors 'self'`，或改用“在新标签页打开”——顶层跳转不受该限制。

上述环境变量是浏览器实际访问的完整 Hub 地址。启用 Civitai OAuth，或代理删除浏览器来源元数据时应显式设置它；扩展不会信任客户端传入的 `X-Forwarded-*` 来决定 OAuth 回调地址。OAuth 回调还必须按 Hub 的要求登记到提供方：

```text
https://example.com/comfy/model-hub/api/v1/auth/civitai/callback
```

普通来源 API token 仍可以在 Hub 设置界面配置，无需 OAuth。访问 Hub 的权限与访问 ComfyUI 的权限一致；ComfyUI 多用户 ID 本身不是独立的 Hub 权限隔离机制。

| 环境变量 | 默认值 | 用途 |
|---|---|---|
| `COMFYUI_MODEL_HUB_AUTO_INSTALL` | `1` | 设置为 `0` 禁用启动前自动安装 |
| `COMFYUI_MODEL_HUB_PUBLIC_BASE_URL` | 未设置 | 固定外部 Hub 地址，支持 TLS 终止及 OAuth |
| `COMFYUI_MODEL_HUB_LOGGER_NAME` | `ComfyUI-Model-Hub` | 安装框架日志名称 |
| `COMFYUI_MODEL_HUB_LOGGER_LEVEL` | `20` | 安装框架日志级别 |
| `COMFYUI_MODEL_HUB_LOGGER_COLOR` | `1` | 设置为 `0` 关闭安装框架彩色日志 |

## 开发与验证

Python 依赖安装框架保留 HakuImg 的包分析器，修正根目录定位及包内循环导入，预启动结束只卸载本项目的临时模块。

开发环境准备好 pytest、pytest-asyncio、playwright、ruff 和 ty 后，可运行以下验证：

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

ty 默认从相邻的 `../ComfyUI` 解析宿主接口；不同目录布局请用 `--extra-search-path /path/to/ComfyUI`。浏览器测试可通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 使用已有 Chromium。

集成测试运行真实 sd-model-hub 发行包、aiohttp 代理及本地下载源，模型和数据放在临时目录。浏览器测试使用真实 Chromium 和 Hub 页面，以及模拟 ComfyUI 扩展注册接口的小型宿主，不代表完整 ComfyUI 前端或 GPU 工作流验证。

本项目采用 [GPL-3.0-only](LICENSE) 协议。
