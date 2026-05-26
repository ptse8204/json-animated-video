from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVIDER_NOTEBOOK = ROOT / "notebooks" / "colab_ui_provider_connect_demo.ipynb"
PUBLIC_TUNNEL_MARKERS = ("ngrok", "localtunnel", "lt --port", "cloudflared", "trycloudflare", "serveo")
SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9._~-]{12,}|hf_[A-Za-z0-9]{12,}|Bearer\s+[A-Za-z0-9._~+/=-]{12,})")


def _load_notebook(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _joined_source(path: Path = PROVIDER_NOTEBOOK) -> str:
    notebook = _load_notebook(path)
    return "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])


def _cell_with(path: Path, needle: str) -> str:
    notebook = _load_notebook(path)
    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if needle in source:
            return source
    raise AssertionError(f"Could not find notebook cell containing {needle!r}")


def test_checked_in_colab_notebooks_are_valid_json_and_have_empty_outputs() -> None:
    notebooks = sorted((ROOT / "notebooks").glob("*.ipynb"))

    assert notebooks
    for path in notebooks:
        notebook = _load_notebook(path)
        assert notebook["nbformat"] == 4
        for cell in notebook["cells"]:
            assert cell.get("outputs", []) == []
            assert cell.get("execution_count") is None
            assert not SECRET_VALUE_RE.search(json.dumps(cell.get("outputs", [])))


def test_provider_connect_notebook_has_no_public_tunnel_or_saved_secret_values() -> None:
    source = _joined_source()
    lowered = source.lower()

    for marker in PUBLIC_TUNNEL_MARKERS:
        assert marker not in lowered
    assert not SECRET_VALUE_RE.search(source)
    assert "print(token)" not in source
    assert "print(os.environ[\"HF_TOKEN\"])" not in source
    assert "secret_json" not in source


def test_provider_connect_notebook_opens_ui_before_advanced_model_debug_cells() -> None:
    notebook = _load_notebook(PROVIDER_NOTEBOOK)
    cell_sources = ["".join(cell.get("source", [])) for cell in notebook["cells"]]
    joined = "\n".join(cell_sources)

    assert "# MotionJSON Local UI setup" in cell_sources[0]
    assert "Run the first launch cells, then stay in the UI" in cell_sources[0]
    assert "Do model configuration in the UI" in cell_sources[0]
    assert "sam3TrackerModel=facebook/sam3" in cell_sources[0]
    assert "Do not paste a single `sam3.pt` checkpoint into the scene-sweep tracker model field" in cell_sources[0]
    assert '"-e", ".[ui]"' in joined
    assert "hosted-segmentation,hosted-sam3,hosted-sam-vendors" not in joined
    assert "## Advanced fallback only" in joined
    launch_index = next(index for index, source in enumerate(cell_sources) if "output.serve_kernel_port_as_iframe" in source)
    advanced_index = next(index for index, source in enumerate(cell_sources) if "## Advanced fallback only" in source)
    sam2_debug_index = next(index for index, source in enumerate(cell_sources) if "RUN_LOCAL_SAM2_SETUP = False" in source)
    sam3_debug_index = next(index for index, source in enumerate(cell_sources) if "RUN_LOCAL_SAM3_SETUP = False" in source)

    assert launch_index < advanced_index < sam2_debug_index < sam3_debug_index


def test_provider_connect_sam2_source_repo_checkpoint_and_config_are_distinct() -> None:
    source = _joined_source()
    package_cell = _cell_with(PROVIDER_NOTEBOOK, "RUN_LOCAL_SAM2_SETUP = False")

    assert "SAM2_SOURCE_DIR = Path(\"/content/sam2\")" in source
    assert "SAM2_CHECKPOINT_FILENAME = \"sam2.1_hiera_large.pt\"" in source
    assert "SAM2_CONFIG_FILENAME = \"sam2.1_hiera_l.yaml\"" in source
    assert "/content/sam2 is the official SAM2 source/package directory, not the checkpoint path" in source
    assert "SAM2_LOCAL_CHECKPOINT must be a local .pt checkpoint file path" in source
    assert "SAM2_LOCAL_CONFIG must be the matching local YAML config path" in source
    assert "https://github.com/facebookresearch/sam2.git" in package_cell
    assert "pip\", \"install\", \"-e\", str(SAM2_SOURCE_DIR)" in package_cell
    assert "This installs SAM2 code only. It does not download checkpoint .pt files." in package_cell
    assert "download_ckpts.sh" not in package_cell


def test_provider_connect_sam2_checkpoint_download_is_opt_in_and_validated() -> None:
    resolver_cell = _cell_with(PROVIDER_NOTEBOOK, "MANUAL_SAM2_CHECKPOINT_PATH = \"\"")

    assert "RUN_DOWNLOAD_SAM2_CHECKPOINTS = False" in resolver_cell
    assert "MANUAL_SAM2_CHECKPOINT_PATH" in resolver_cell
    assert "MANUAL_SAM2_CONFIG_PATH" in resolver_cell
    assert "find_sam2_checkpoint_candidates(sam2_search_roots)" in resolver_cell
    assert "find_sam2_config_candidates([SAM2_SOURCE_DIR, Path.cwd()])" in resolver_cell
    assert "elif RUN_DOWNLOAD_SAM2_CHECKPOINTS:" in resolver_cell
    assert resolver_cell.index("elif RUN_DOWNLOAD_SAM2_CHECKPOINTS:") < resolver_cell.index("download_ckpts.sh")
    assert "set_and_validate_sam2_local_checkpoint(candidates[0])" in resolver_cell
    assert "set_and_validate_sam2_local_config(config_candidates[0])" in resolver_cell
    assert "Copy these values into Model setup -> SAM2 fallback" in _joined_source()


def test_provider_connect_sam2_readiness_validates_paths_before_diagnostics() -> None:
    readiness_cell = _cell_with(PROVIDER_NOTEBOOK, "current_checkpoint_value = os.environ.get(\"SAM2_LOCAL_CHECKPOINT\", \"\").strip()")

    assert "find_spec(\"sam2\")" in readiness_cell
    assert "torch.cuda.is_available()" in readiness_cell
    assert "set_and_validate_sam2_local_checkpoint(current_checkpoint_value)" in readiness_cell
    assert "set_and_validate_sam2_local_config(current_config_value)" in readiness_cell
    assert "print_sam2_path_help(resolved_checkpoint_for_ui, resolved_config_for_ui)" in readiness_cell
    assert "backend\", \"diagnostics\", \"--text\"" in readiness_cell
    assert readiness_cell.index("set_and_validate_sam2_local_checkpoint(current_checkpoint_value)") < readiness_cell.index("backend\", \"diagnostics\", \"--text\"")


def test_provider_connect_sam3_source_repo_and_checkpoint_path_are_distinct() -> None:
    source = _joined_source()
    package_cell = _cell_with(PROVIDER_NOTEBOOK, "RUN_LOCAL_SAM3_SETUP = False")

    assert "SAM3_SOURCE_DIR = Path(\"/content/sam3\")" in source
    assert "SAM3_HF_REPO_ID = \"facebook/sam3\"" in source
    assert "SAM3_CHECKPOINT_FILENAME = \"sam3.pt\"" in source
    assert "/content/sam3 is the official SAM3 source/package directory, not the checkpoint path" in source
    assert "facebook/sam3 is the Hugging Face repo id, not a local model path" in source
    assert "SAM3_LOCAL_MODEL must be a local checkpoint file path ending in sam3.pt" in source
    assert "SAM3 Scene Sweep uses sam3TrackerModel=facebook/sam3 or a local Hugging Face model directory" in source
    assert "SAM3_LOCAL_MODEL path (leave blank to skip)" not in source
    assert "https://github.com/facebookresearch/sam3.git" in package_cell
    assert "pip\", \"install\", \"-e\", str(SAM3_SOURCE_DIR)" in package_cell
    assert "This installs SAM3 code only. It does not download facebook/sam3 sam3.pt." in package_cell
    assert "Use of the local `facebook/sam3` model is allowed only after Meta has approved your access" in source


def test_provider_connect_sam3_checkpoint_download_is_opt_in_and_validated() -> None:
    resolver_cell = _cell_with(PROVIDER_NOTEBOOK, "MANUAL_SAM3_CHECKPOINT_PATH = \"\"")

    assert "RUN_DOWNLOAD_SAM3_CHECKPOINT = False" in resolver_cell
    assert "RUN_USE_GOOGLE_DRIVE_SAM3_CHECKPOINT = False" in resolver_cell
    assert "GOOGLE_DRIVE_SAM3_CHECKPOINT_PATH" in resolver_cell
    assert "MANUAL_SAM3_CHECKPOINT_PATH" in resolver_cell
    assert "find_sam3_checkpoint_candidates(search_roots)" in resolver_cell
    assert "drive.mount(\"/content/drive\")" in resolver_cell
    assert "elif RUN_DOWNLOAD_SAM3_CHECKPOINT:" in resolver_cell
    assert resolver_cell.index("elif RUN_DOWNLOAD_SAM3_CHECKPOINT:") < resolver_cell.index("hf_hub_download")
    assert "hf_hub_download(repo_id=SAM3_HF_REPO_ID, filename=SAM3_CHECKPOINT_FILENAME, token=token)" in resolver_cell
    assert "set_and_validate_sam3_local_model(downloaded_path)" in resolver_cell
    assert "Checkpoint size:" in resolver_cell
    assert "No Hugging Face token is needed for a manual local path" in resolver_cell
    assert "No Hugging Face token is required for this path" in resolver_cell
    assert "To avoid Hugging Face tokens, use MANUAL_SAM3_CHECKPOINT_PATH or RUN_USE_GOOGLE_DRIVE_SAM3_CHECKPOINT" in resolver_cell
    assert "Or skip local SAM3 and use Roboflow SAM3 or Fal SAM3 image in Model setup." in resolver_cell
    assert "The Hugging Face token is passed directly and is not printed." in resolver_cell
    assert "Only continue if Meta has approved your access to facebook/sam3" in resolver_cell
    assert "print(token)" not in resolver_cell
    assert "Use these values only in Model setup -> Advanced SAM3 official package / concept-exemplar config" in _joined_source()
    assert "sam3ModelPath:" in _joined_source()
    assert "Copy these values into Model setup -> SAM3 Scene Sweep" not in _joined_source()


def test_provider_connect_sam3_readiness_validates_model_before_diagnostics() -> None:
    readiness_cell = _cell_with(PROVIDER_NOTEBOOK, "current_model_value = os.environ.get(\"SAM3_LOCAL_MODEL\", \"\").strip()")

    assert "find_spec(\"sam3\")" in readiness_cell
    assert "torch.cuda.is_available()" in readiness_cell
    assert "current_model_value = os.environ.get(\"SAM3_LOCAL_MODEL\", \"\").strip()" in readiness_cell
    assert "set_and_validate_sam3_local_model(current_model_value)" in readiness_cell
    assert "print_sam3_path_help(resolved_for_ui)" in readiness_cell
    assert "backend\", \"diagnostics\", \"--text\"" in readiness_cell
    assert readiness_cell.index("set_and_validate_sam3_local_model(current_model_value)") < readiness_cell.index("backend\", \"diagnostics\", \"--text\"")


def test_provider_connect_notebook_preserves_hosted_sam3_path() -> None:
    source = _joined_source()

    assert "Roboflow SAM3" in source
    assert "Fal SAM3 image" in source
    assert "If you prefer hosted SAM3, configure it from Model setup." in source
    assert "Hosted SAM3 users can skip local readiness failures" in source
    assert "do not require local SAM3 package or checkpoint cells" in source
