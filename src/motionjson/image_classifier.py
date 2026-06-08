from __future__ import annotations

from dataclasses import dataclass
import re
import threading
from typing import Any, Iterable, Sequence

import numpy as np
from PIL import Image


MOBILENETV3_SMALL_MODEL_ID = "timm/tf_mobilenetv3_small_100.in1k"

GENERIC_LABEL_RE = re.compile(
    r"^(?:"
    r"candidate(?:\s+\d+)?|"
    r"selected[_\s-]?object|"
    r"object(?:[_\s-]?\d+)?|"
    r"manual[_\s-]?\d+|"
    r"mock object(?:\s+\d+)?|"
    r"moving foreground(?:\s+\d+)?|"
    r"visible segment(?:\s+\d+)?|"
    r"sam2 proposal(?:\s+\d+)?|"
    r"rejected sam2 proposal(?:\s+\d+)?|"
    r"sam3 .*|"
    r"external[_\s-]?\d+|"
    r"motion[_\s-]?\d+|"
    r"trace[_\s-]?.*|"
    r"discover.*"
    r")$",
    re.IGNORECASE,
)

GENERIC_LABEL_TOKENS = {
    "candidate",
    "object",
    "selected",
    "foreground",
    "segment",
    "proposal",
    "moving",
    "manual",
    "trace",
    "discover",
}

FRIENDLY_IMAGENET_LABELS = {
    "soccer ball": "Ball",
    "tennis ball": "Ball",
    "golf ball": "Ball",
    "baseball": "Ball",
    "ping-pong ball": "Ball",
    "coffee mug": "Cup",
    "cup": "Cup",
    "water bottle": "Bottle",
    "pop bottle": "Bottle",
    "beer bottle": "Bottle",
    "wine bottle": "Bottle",
    "cellular telephone": "Phone",
    "mobile phone": "Phone",
    "iPod": "Phone",
    "laptop": "Laptop",
    "notebook": "Laptop",
    "monitor": "Screen",
    "television": "Screen",
    "desktop computer": "Computer",
    "computer keyboard": "Keyboard",
    "mouse": "Mouse",
    "book jacket": "Book",
    "comic book": "Book",
    "bookshop": "Book",
    "potted plant": "Plant",
    "vase": "Vase",
    "chair": "Chair",
    "folding chair": "Chair",
    "table lamp": "Lamp",
    "desk": "Table",
    "dining table": "Table",
    "sports car": "Car",
    "convertible": "Car",
    "pickup": "Truck",
    "minivan": "Van",
    "bus": "Bus",
    "mountain bike": "Bike",
    "bicycle-built-for-two": "Bike",
    "motor scooter": "Scooter",
    "motorcycle": "Motorcycle",
    "dog": "Dog",
    "Labrador retriever": "Dog",
    "golden retriever": "Dog",
    "tabby": "Cat",
    "tiger cat": "Cat",
    "Egyptian cat": "Cat",
    "birdhouse": "Bird",
    "macaw": "Bird",
    "toucan": "Bird",
    "banana": "Banana",
    "orange": "Orange",
    "lemon": "Lemon",
    "strawberry": "Strawberry",
    "pineapple": "Pineapple",
    "broccoli": "Broccoli",
    "cauliflower": "Cauliflower",
}


@dataclass(frozen=True)
class LabelPrediction:
    label: str
    raw_label: str
    confidence: float
    model_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "rawLabel": self.raw_label,
            "confidence": round(float(self.confidence), 4),
            "modelId": self.model_id,
        }


class _ClassifierBackend:
    def __init__(self, *, model: Any, transform: Any, labels: Sequence[str]):
        self.model = model
        self.transform = transform
        self.labels = list(labels)


_backend_lock = threading.Lock()
_backend: _ClassifierBackend | None | bool = False


def is_generic_object_label(label: str | None) -> bool:
    text = str(label or "").strip()
    if not text:
        return True
    if GENERIC_LABEL_RE.match(text):
        return True
    lowered = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return bool(lowered) and any(token in GENERIC_LABEL_TOKENS for token in lowered.split())


def classify_image_label(image: Image.Image | np.ndarray | None, *, min_confidence: float = 0.28) -> LabelPrediction | None:
    if image is None:
        return None
    backend = _load_backend()
    if backend is None:
        return None
    pil_image = _to_rgb_image(image)
    if pil_image is None:
        return None
    try:
        import torch  # type: ignore
    except ImportError:
        return None
    tensor = backend.transform(pil_image).unsqueeze(0)
    with torch.inference_mode():
        logits = backend.model(tensor)
        if not hasattr(logits, "softmax"):
            return None
        probabilities = logits.softmax(dim=-1)[0]
        confidence, index = probabilities.max(dim=-1)
    confidence_value = float(confidence.item())
    if confidence_value < min_confidence:
        return None
    raw_label = _label_name(backend.labels, int(index.item()))
    friendly = _friendly_label(raw_label)
    if not friendly:
        return None
    return LabelPrediction(
        label=friendly,
        raw_label=raw_label,
        confidence=confidence_value,
        model_id=MOBILENETV3_SMALL_MODEL_ID,
    )


def numbered_label(label: str, used_labels: Iterable[str]) -> str:
    base = str(label or "").strip() or "Object"
    existing = {str(item or "").strip().lower() for item in used_labels if str(item or "").strip()}
    if base.lower() not in existing:
        return base
    index = 2
    while True:
        candidate = f"{base} {index}"
        if candidate.lower() not in existing:
            return candidate
        index += 1


def _friendly_label(raw_label: str) -> str | None:
    text = str(raw_label or "").strip()
    if not text:
        return None
    first = text.split(",", 1)[0].strip()
    if first in FRIENDLY_IMAGENET_LABELS:
        return FRIENDLY_IMAGENET_LABELS[first]
    normalized = re.sub(r"[_-]+", " ", first).strip().lower()
    if normalized in FRIENDLY_IMAGENET_LABELS:
        return FRIENDLY_IMAGENET_LABELS[normalized]
    return None


def _label_name(labels: Sequence[str], index: int) -> str:
    if 0 <= index < len(labels):
        return str(labels[index])
    return ""


def _to_rgb_image(image: Image.Image | np.ndarray) -> Image.Image | None:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    array = np.asarray(image)
    if array.ndim == 2:
        array = np.repeat(array[:, :, None], 3, axis=2)
    if array.ndim != 3:
        return None
    if array.shape[2] == 4:
        rgba = array.astype(np.uint8, copy=False)
        alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
        rgb = rgba[:, :, :3].astype(np.float32)
        background = np.full_like(rgb, 255.0)
        composed = (rgb * alpha) + (background * (1.0 - alpha))
        return Image.fromarray(np.clip(composed, 0, 255).astype(np.uint8), mode="RGB")
    if array.shape[2] >= 3:
        return Image.fromarray(array[:, :, :3].astype(np.uint8, copy=False), mode="RGB")
    return None


def _load_backend() -> _ClassifierBackend | None:
    global _backend
    if _backend is None:
        return None
    if _backend is not False:
        return _backend
    with _backend_lock:
        if _backend is None:
            return None
        if _backend is not False:
            return _backend
        try:
            import timm  # type: ignore
            import torch  # type: ignore
        except ImportError:
            _backend = None
            return None
        try:
            model = timm.create_model(f"hf_hub:{MOBILENETV3_SMALL_MODEL_ID}", pretrained=True)
            model.eval()
            labels = (
                model.pretrained_cfg.get("label_names")
                or model.pretrained_cfg.get("labels")
                or []
            )
            if not isinstance(labels, Sequence) or isinstance(labels, (str, bytes, bytearray)):
                labels = []
            data_config = timm.data.resolve_model_data_config(model)
            transform = timm.data.create_transform(**data_config, is_training=False)
            backend = _ClassifierBackend(model=model.to(torch.device("cpu")), transform=transform, labels=[str(item) for item in labels])
        except Exception:
            _backend = None
            return None
        _backend = backend
        return backend
