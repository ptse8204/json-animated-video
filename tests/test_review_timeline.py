from __future__ import annotations

from motionjson.review_timeline import REVIEW_TIMELINE_FORMAT, review_timeline_payload


def test_review_timeline_builds_candidate_track_markers_and_scene_change_suggestions():
    payload = review_timeline_payload(
        candidates=[
            {
                "candidateId": "cand_001",
                "label": "hero object",
                "source": "auto_object_proposals",
                "frameIndex": 0,
                "confidence": 0.83,
                "reviewStatus": "pending",
            },
            {
                "candidateId": "cand_002",
                "label": "background",
                "frameIndex": 4,
                "rejectionReason": "background_like",
            },
        ],
        tracks=[
            {
                "objectId": "cand_001",
                "label": "hero object",
                "source": "mock",
                "exportStatus": "review_pending",
                "frames": [
                    {"frame": 1, "visible": True, "bbox": [4, 4, 12, 12]},
                    {"frame": 3, "visible": True, "bbox": [6, 4, 12, 12]},
                ],
            }
        ],
        source={"frameCount": 6, "fps": 12},
        candidate_summary={
            "config": {
                "qualityPreset": "clean",
                "keyframePolicy": "scene_changes",
            }
        },
    )

    assert payload["format"] == REVIEW_TIMELINE_FORMAT
    assert payload["frameCount"] == 6
    assert payload["markerCountsByKind"] == {
        "candidate": 2,
        "track_end": 1,
        "track_lost": 1,
        "track_start": 1,
    }
    assert [marker["kind"] for marker in payload["markers"]] == [
        "candidate",
        "track_start",
        "track_lost",
        "track_end",
        "candidate",
    ]
    assert payload["markers"][1]["objectId"] == "cand_001"
    assert payload["markers"][2]["frameIndex"] == 2
    assert payload["markers"][-1]["status"] == "rejected"
    assert [item["frameIndex"] for item in payload["suggestedKeyframes"]] == [0, 1, 2, 3, 4]
    assert all(item["reason"] == "scene_change_policy_review_marker" for item in payload["suggestedKeyframes"])


def test_review_timeline_prefers_configured_keyframes_when_present():
    payload = review_timeline_payload(
        candidates=[{"candidateId": "cand_001", "frameIndex": 1}],
        tracks=[],
        source={"frameCount": 10},
        candidate_summary={"config": {"keyframes": [0, 5, 9], "keyframePolicy": "scene_changes"}},
    )

    assert [item["frameIndex"] for item in payload["suggestedKeyframes"]] == [0, 5, 9]
    assert {item["reason"] for item in payload["suggestedKeyframes"]} == {"configured_keyframe"}
