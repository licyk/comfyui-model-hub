from comfyui_model_hub.model_paths import collect_model_paths
from comfyui_model_hub.runtime.config import REQUIREMENTS_PATH
from comfyui_model_hub.runtime.package_analyzer import validate_requirements


def test_priority_aliases_auxiliary_and_unknown_categories(tmp_path):
    external = tmp_path / "external"
    paths = collect_model_paths(
        {
            "vae_approx": ([str(tmp_path / "approx")], set()),
            "latent_upscale_models": ([str(tmp_path / "latent")], set()),
            "vae": ([str(external), str(tmp_path / "vae")], set()),
            "upscale_models": ([str(tmp_path / "upscalers")], set()),
            "text_encoders": ([str(tmp_path / "text"), str(tmp_path / "clip")], set()),
            "clip": ([str(tmp_path / "clip")], set()),
            "custom_nodes": ([str(tmp_path)], set()),
            "configs": ([str(tmp_path / "configs")], set()),
            "custom_detector": ([str(tmp_path / "detector")], set()),
        }
    )
    by_id = {root["id"]: root for root in paths.roots}
    assert by_id[paths.destinations["vae"]["root_id"]]["path"] == str(external)
    assert by_id[paths.destinations["upscaler"]["root_id"]]["path"] == str(tmp_path / "upscalers")
    assert sum(root["path"] == str(tmp_path / "clip") for root in paths.roots) == 1
    assert all(root["layout"] == "custom" for root in paths.roots)
    assert "custom_nodes" not in paths.categories
    assert "custom_detector" in paths.categories
    assert not external.exists()  # Discovery must not create folders.


def test_stable_ids_shared_paths_and_symlinks(tmp_path):
    directory = tmp_path / "shared"
    directory.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(directory, target_is_directory=True)
    first = collect_model_paths({"loras": ([str(directory)], set())})
    second = collect_model_paths({"vae": ([str(alias)], set()), "loras": ([str(directory)], set())})
    assert len(second.roots) == 1
    assert second.roots[0]["id"] == first.roots[0]["id"]
    assert second.roots[0]["kind"] is None
    assert second.destinations["vae"]["root_id"] == second.destinations["lora"]["root_id"]


def test_requirements_use_extension_root():
    assert REQUIREMENTS_PATH.is_file()
    assert REQUIREMENTS_PATH.parent.name == "comfyui-model-hub"
    assert validate_requirements(REQUIREMENTS_PATH)


def test_complete_directory_leads_without_changing_download_destinations(tmp_path):
    models = tmp_path / "models"
    registry = {
        "classifiers": ([str(models / "classifiers")], set()),
        "checkpoints": ([str(models / "checkpoints")], set()),
        "loras": ([str(tmp_path / "external-loras")], set()),
    }
    original = collect_model_paths(registry)
    paths = collect_model_paths(registry, models)
    assert paths.roots[0]["path"] == str(models)
    assert paths.roots[0]["name"] == "所有模型目录"
    assert paths.roots[0]["layout"] == "comfyui"
    assert paths.roots[0]["kind"] is None
    assert paths.roots[1:] == original.roots
    assert paths.destinations == original.destinations
    assert paths.default_download_root == original.roots[0]["id"]
    assert not models.exists()


def test_complete_directory_deduplicates_registered_alias(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(models, target_is_directory=True)
    paths = collect_model_paths({"checkpoints": ([str(alias)], set())}, models)
    assert len(paths.roots) == 1
    assert paths.roots[0]["name"] == "所有模型目录"
    assert paths.roots[0]["kind"] is None
    assert paths.destinations["checkpoint"]["root_id"] == paths.roots[0]["id"]
