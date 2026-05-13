from motionjson.exporters.lottie import build_silhouette_lottie


def test_lottie_basic():
    frames = [
        {"out_index": 0, "visible": True, "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        {"out_index": 1, "visible": True, "polygon": [[1, 0], [11, 0], [11, 10], [1, 10]]},
    ]
    data = build_silhouette_lottie(100, 100, 12, frames)
    assert data["w"] == 100
    assert data["layers"][0]["ty"] == 4
    assert data["layers"][0]["shapes"][0]["it"][0]["ty"] == "sh"
