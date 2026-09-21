"""ComfyUI entry point; model management is provided without workflow nodes."""


async def comfy_entrypoint():
    from .comfyui_model_hub.extension import ModelHubExtension

    return ModelHubExtension()


WEB_DIRECTORY = "./js"
__all__ = ["WEB_DIRECTORY", "comfy_entrypoint"]
