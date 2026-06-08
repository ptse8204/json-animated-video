from __future__ import annotations

from motionjson.image_classifier import is_generic_object_label, numbered_label


def test_generic_label_detection_catches_placeholder_names():
    assert is_generic_object_label("selected_object")
    assert is_generic_object_label("Candidate 2")
    assert is_generic_object_label("Moving foreground 1")
    assert not is_generic_object_label("Red ball")
    assert not is_generic_object_label("Hero Cup")


def test_numbered_label_only_suffixes_duplicates():
    used = ["Ball", "Cup", "Ball 2"]
    assert numbered_label("Ball", used) == "Ball 3"
    assert numbered_label("Plant", used) == "Plant"
