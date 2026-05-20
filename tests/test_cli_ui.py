from __future__ import annotations

from pathlib import Path

import pytest

from motionjson.cli import main


def test_ui_command_help_documents_local_launcher(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["ui", "--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "Launch the local MotionJSON UI" in output
    assert "--db" in output
    assert "--storage-root" in output
    assert "--mock" in output
    assert "--no-open" in output


def test_extract_help_documents_discovery_modes_and_flags(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["extract", "--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    for expected in [
        "--discovery-provider",
        "auto_object_proposals",
        "sam_auto_masks",
        "text_detector",
        "class_detector",
        "motion_foreground",
        "external_masks",
        "--discovery-text",
        "--discovery-class",
        "--discovery-class-preset",
        "--discovery-config",
    ]:
        assert expected in output


def test_ui_command_launches_server_with_local_defaults(tmp_path, monkeypatch, capsys):
    calls = []

    def fake_serve_ui(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("motionjson.ui.server.serve_ui", fake_serve_ui)

    main(
        [
            "ui",
            "--db",
            str(tmp_path / "backend.sqlite"),
            "--storage-root",
            str(tmp_path / "storage"),
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--no-open",
            "--mock",
        ]
    )

    output = capsys.readouterr().out

    assert "http://127.0.0.1:0/" not in output
    assert "Mock mode: on" in output
    assert calls == [
        {
            "db_path": Path(tmp_path / "backend.sqlite"),
            "storage_root": Path(tmp_path / "storage"),
            "host": "127.0.0.1",
            "port": 0,
            "open_browser": False,
            "mock_mode": True,
        }
    ]
