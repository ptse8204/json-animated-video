from __future__ import annotations

import json

from motionjson.candidate_review import candidate_review_payload


def test_candidate_review_payload_shapes_candidates_and_summary() -> None:
    payload = candidate_review_payload(
        {
            "format": "motionjson.candidates.v0.1",
            "provider": "mock",
            "config": {"qualityPreset": "clean", "requireReview": True},
            "video": {"width": 200, "height": 100, "sampledFrameCount": 10},
            "candidates": [
                {
                    "id": "cand_001",
                    "label": "red ball",
                    "source": "auto_object_proposals",
                    "frameIndex": 0,
                    "box": {"x": 10, "y": 5, "w": 40, "h": 20},
                    "score": 0.83,
                    "metadata": {
                        "providerName": "mock",
                        "stabilityScore": 0.88,
                        "motionScore": 0.64,
                        "maskFiles": 7,
                    },
                },
                {
                    "id": "cand_002",
                    "label": "floor fragment",
                    "source": "auto_object_proposals",
                    "frameIndex": 0,
                    "box": [0, 0, 200, 90],
                    "score": 0.4,
                    "metadata": {
                        "rejectionReason": "background_like",
                        "warnings": ["file:///Users/example/private.png", "api_key=sk-1234567890"],
                        "storageKey": "projects/private/candidates.json",
                    },
                },
                {
                    "id": "cand_003",
                    "label": "manually rejected",
                    "source": "auto_object_proposals",
                    "frameIndex": 0,
                    "reviewStatus": "rejected",
                    "score": 0.5,
                },
            ],
        }
    )

    candidates = payload["candidates"]
    assert candidates[0]["candidateId"] == "cand_001"
    assert candidates[0]["objectId"] is None
    assert candidates[0]["areaRatio"] == 0.04
    assert candidates[0]["stabilityScore"] == 0.88
    assert candidates[0]["motionScore"] == 0.64
    assert candidates[0]["confidence"] == 0.83
    assert candidates[0]["frameCoverageEstimate"] == 0.7
    assert candidates[0]["defaultSelected"] is True
    assert candidates[0]["reviewStatus"] == "pending"
    assert candidates[1]["rejectionReason"] == "background_like"
    assert candidates[1]["defaultSelected"] is False
    assert candidates[1]["reviewStatus"] == "rejected"
    assert candidates[2]["rejectionReason"] is None
    assert candidates[2]["defaultSelected"] is False
    assert candidates[2]["reviewStatus"] == "rejected"

    summary = payload["candidateSummary"]
    assert summary["candidateCount"] == 3
    assert summary["acceptedCandidateCount"] == 1
    assert summary["rejectedCandidateCount"] == 2
    assert summary["defaultSelectedCount"] == 1
    assert summary["rejectionReasons"] == {"background_like": 1, "review_rejected": 1}
    assert summary["qualityPreset"] == "clean"
    assert summary["providerName"] == "mock"
    assert summary["requiresReview"] is True

    public_json = json.dumps(payload)
    assert "storageKey" not in public_json
    assert "projects/private" not in public_json
    assert "file://" not in public_json
    assert "1234567890" not in public_json
