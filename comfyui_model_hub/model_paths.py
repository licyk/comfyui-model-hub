"""Translate ComfyUI's registered directories into stable Hub roots."""

import hashlib
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KINDS = {
    "checkpoints": "checkpoint",
    "loras": "lora",
    "vae": "vae",
    "vae_approx": "vae",
    "text_encoders": "text_encoder",
    "clip": "text_encoder",
    "diffusion_models": "diffusion_model",
    "unet": "diffusion_model",
    "controlnet": "controlnet",
    "t2i_adapter": "controlnet",
    "upscale_models": "upscaler",
    "latent_upscale_models": "upscaler",
    "embeddings": "embedding",
    "hypernetworks": "hypernetwork",
    "clip_vision": "clip_vision",
    "style_models": "style_model",
    "diffusers": "diffusers",
    "gligen": "gligen",
    "photomaker": "photomaker",
    "model_patches": "model_patch",
    "audio_encoders": "audio_encoder",
}
NON_MODEL_CATEGORIES = {"custom_nodes", "configs", "datasets"}
PRIMARY_CATEGORIES = (
    "checkpoints",
    "loras",
    "vae",
    "text_encoders",
    "diffusion_models",
    "controlnet",
    "upscale_models",
    "embeddings",
    "hypernetworks",
    "clip_vision",
    "style_models",
    "diffusers",
)


@dataclass
class ModelPaths:
    roots: list[dict[str, Any]]
    destinations: dict[str, dict[str, str]]
    categories: set[str]
    default_download_root: str | None = None


def collect_model_paths(registry: Mapping[str, tuple[Sequence[str], Any]], models_dir: str | Path | None = None) -> ModelPaths:
    """Preserve per-category priority; auxiliary folders never take primary defaults.

    ComfyUI registers folders it never creates (such as "classifiers"), so only existing
    directories become roots; discovery never creates them.
    """
    by_path: dict[str, dict[str, Any]] = {}
    destinations: dict[str, dict[str, str]] = {}
    categories: set[str] = set()
    ordered = [key for key in PRIMARY_CATEGORIES if key in registry]
    ordered.extend(key for key in registry if key not in ordered and key not in NON_MODEL_CATEGORIES)
    for category in ordered:
        kind = KINDS.get(category)
        for index, directory in enumerate(registry[category][0]):
            path = str(Path(directory).expanduser().resolve())
            if not os.path.isdir(path):
                continue
            identity = os.path.normcase(path)
            root = by_path.get(identity)
            if root is None:
                root = {
                    "path": path,
                    "layout": "custom",
                    "kind": kind,
                    "name": category if index == 0 else f"{category} ({index + 1})",
                    "id": "comfy-" + hashlib.sha256(identity.encode()).hexdigest()[:16],
                }
                by_path[identity] = root
            elif root["kind"] != kind:
                # A shared directory is ambiguous; file detection remains authoritative.
                root["kind"] = None
            categories.add(category)
            if kind and kind not in destinations:
                destinations[kind] = {"root_id": str(root["id"]), "rel_dir": ""}
    roots = list(by_path.values())
    default_download_root = None
    models_path = None if models_dir is None else str(Path(models_dir).expanduser().resolve())
    if models_path is not None and os.path.isdir(models_path):
        # Keep the old first-root download fallback while showing the complete directory first.
        default_download_root = str(roots[0]["id"]) if roots else None
        identity = os.path.normcase(models_path)
        complete: dict[str, Any] | None = by_path.get(identity)
        if complete is None:
            complete = {"id": "comfy-" + hashlib.sha256(identity.encode()).hexdigest()[:16], "path": models_path}
        else:
            roots.remove(complete)
        complete.update(name="所有模型目录", layout="comfyui", kind=None)
        roots.insert(0, complete)
    return ModelPaths(roots, destinations, categories, default_download_root)
