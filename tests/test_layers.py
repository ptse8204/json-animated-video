import numpy as np

from motionjson.layers import build_raster_motion_layer, crop_rgba_layer


def test_crop_rgba_layer_uses_bbox_padding_and_anchor():
    rgb = np.zeros((20, 30, 3), dtype=np.uint8)
    rgb[8:12, 10:15] = [255, 0, 0]
    mask = np.zeros((20, 30), dtype=np.uint8)
    mask[8:12, 10:15] = 255

    crop = crop_rgba_layer(rgb, mask, [10, 8, 5, 4], centroid=[12.5, 10], padding=2)

    assert crop.bbox == [8, 6, 9, 8]
    assert crop.rgba.shape == (8, 9, 4)
    assert crop.anchor == [4.5, 4.0]
    assert crop.rgba[:, :, 3].max() == 255


def test_build_raster_motion_layer_exports_editable_frames():
    frames = [
        {
            "out_index": 0,
            "t": 0.0,
            "visible": True,
            "centroid": [12.5, 10],
            "render": {
                "asset": "objects/object_0/layers/frame_00000.png",
                "x": 8,
                "y": 6,
                "width": 9,
                "height": 8,
                "anchor": [4.5, 4.0],
            },
        }
    ]

    layer = build_raster_motion_layer(object_id="object_0", fps=12, frames=frames)

    assert layer["asset_type"] == "cropped_rgba_png_sequence"
    assert layer["frames"][0]["asset"] == "objects/object_0/layers/frame_00000.png"
    assert "scale" in layer["controls"]["editable"]
