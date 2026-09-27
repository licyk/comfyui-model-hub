import pytest

from comfyui_model_hub.runtime.config import combined_view


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, True), ("", True), ("1", True), ("On", True), ("0", False), ("false", False), ("maybe", True)]
)
def test_combined_view_environment(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("COMFYUI_MODEL_HUB_COMBINED_VIEW", raising=False)
    else:
        monkeypatch.setenv("COMFYUI_MODEL_HUB_COMBINED_VIEW", raw)
    assert combined_view() is expected
