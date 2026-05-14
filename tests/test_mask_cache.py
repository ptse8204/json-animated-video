import json

import numpy as np

from motionjson.providers.mask_cache import MaskCache, normalize_binary_mask


def test_normalize_binary_mask_handles_logits_and_uint8():
    logits = np.array([[-0.2, 0.7], [0.0, 2.0]], dtype=np.float32)
    normalized = normalize_binary_mask(logits)

    assert normalized.dtype == np.uint8
    assert normalized.tolist() == [[0, 255], [0, 255]]

    uint8 = normalize_binary_mask(np.array([[0, 128], [127, 255]], dtype=np.uint8))
    assert uint8.tolist() == [[0, 255], [0, 255]]


def test_mask_cache_writes_binary_png_and_manifest(tmp_path):
    cache = MaskCache(tmp_path / "cache")
    key = cache.key_for(
        provider="sam2-local",
        config={"checkpoint": "ckpt.pt", "model_config": "sam2.yaml"},
        source="video.mp4",
        prompt={"point": (5, 6), "box": None},
        frame_index=3,
        object_id="object_0",
        metadata={"width": 4, "height": 3},
    )

    path = cache.set(key, np.array([[0.2, 0.8], [0.6, 0.1]], dtype=np.float32), frame_index=3, metadata={"provider": "sam2-local"})
    loaded = cache.get(key, frame_index=3)
    manifest = json.loads((tmp_path / "cache" / "manifest.json").read_text(encoding="utf-8"))
    entry_manifest = json.loads((tmp_path / "cache" / key / "manifest.json").read_text(encoding="utf-8"))

    assert path.exists()
    assert path.name == "mask_000003.png"
    assert loaded.tolist() == [[0, 255], [255, 0]]
    assert manifest["schema"] == "motionjson.mask_cache.v0.1"
    assert manifest["entries"][key]["metadata"]["provider"] == "sam2-local"
    assert manifest["entries"][key]["masks"]["3"] == f"{key}/mask_000003.png"
    assert entry_manifest["schema"] == "motionjson.mask_cache_entry.v0.1"


def test_mask_cache_key_changes_with_prompt_metadata(tmp_path):
    cache = MaskCache(tmp_path / "cache")
    common = {
        "provider": "sam2-local",
        "config": {"device": "cpu"},
        "source": "video.mp4",
        "frame_index": 1,
        "object_id": "object_0",
        "metadata": {"width": 10, "height": 10},
    }

    point_key = cache.key_for(prompt={"point": (1, 2), "box": None}, **common)
    box_key = cache.key_for(prompt={"point": None, "box": (1, 2, 3, 4)}, **common)

    assert point_key != box_key
