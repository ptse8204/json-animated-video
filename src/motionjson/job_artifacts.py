from __future__ import annotations

import json
import mimetypes
import os
import shutil
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .capabilities import build_capability_report


JOB_ARTIFACT_FORMAT = "motionjson.local_job_artifacts.v0.1"
JOB_EVENT_FORMAT = "motionjson.local_job_event.v0.1"

TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}

JobEventCallback = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]


class JobCanceled(RuntimeError):
    """Raised when a cooperative job cancellation marker is observed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def worker_heartbeat_interval_seconds() -> float:
    raw = os.environ.get("MOTIONJSON_WORKER_HEARTBEAT_INTERVAL_SECONDS", "").strip()
    if not raw:
        return 15.0
    try:
        value = float(raw)
    except ValueError:
        return 15.0
    if value <= 0:
        return 0.0
    return max(1.0, value)


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


GENERATED_EXTRACTION_FILES = {
    "scene_graph.json",
    "object_motion.json",
    "web_asset_manifest.json",
    "rights_manifest.json",
    "resource_profile.json",
    "candidates.json",
    "tracks.json",
    "fallback_diagnostics.json",
    "partial_review.json",
    "silhouette_lottie.json",
    "benchmark_report.json",
}

GENERATED_EXTRACTION_DIRS = {"frames", "masks", "objects", "preview", "exports", "discovery"}


def _object_id_for_rel_path(rel_path: str) -> str | None:
    parts = Path(rel_path.replace("\\", "/")).parts
    if len(parts) >= 2 and parts[0] in {"objects", "masks"}:
        return parts[1]
    return None


def artifact_kind_for_rel_path(rel_path: str) -> str:
    name = Path(rel_path).name
    if rel_path == "run_config.json":
        return "run_config"
    if rel_path == "job.json":
        return "job_state"
    if rel_path == "events.jsonl":
        return "job_events"
    if rel_path == "logs.txt":
        return "job_logs"
    if rel_path == "metrics.json":
        return "job_metrics"
    if rel_path == "artifacts.json":
        return "artifact_manifest"
    if name == "failure.json":
        return "failure_diagnostics"
    if rel_path == "provider_diagnostics.json":
        return "provider_diagnostics"
    if rel_path == "candidates.json":
        return "candidate_summary"
    if rel_path == "tracks.json":
        return "track_summary"
    if rel_path == "review/selected_candidates.json":
        return "selected_candidate_tracking"
    if rel_path == "fallback_diagnostics.json":
        return "fallback_diagnostics"
    if rel_path == "partial_review.json":
        return "partial_review"
    if rel_path == "scene_graph.json":
        return "scene_graph"
    if rel_path == "rights_manifest.json":
        return "rights_manifest"
    if rel_path == "resource_profile.json":
        return "resource_profile"
    if rel_path == "silhouette_lottie.json":
        return "lottie_silhouette"
    if name == "object_manifest.json":
        return "object_manifest"
    if name == "object_motion.json":
        return "object_motion"
    if name == "web_asset_manifest.json":
        return "web_manifest"
    if rel_path.startswith("frames/"):
        return "debug_frame"
    if rel_path.startswith("discovery/"):
        return "discovery_artifact"
    if rel_path.startswith("masks/"):
        return "mask"
    if "/cutouts/" in rel_path:
        return "cutout"
    if rel_path.startswith("preview/"):
        return "preview"
    return "extraction_file"


def _reason_code(exc: BaseException) -> str:
    if isinstance(exc, JobCanceled):
        return "user_canceled"
    if isinstance(exc, FileNotFoundError):
        return "missing_input_or_artifact"
    if isinstance(exc, PermissionError):
        return "output_unwritable"
    if isinstance(exc, ValueError):
        return "invalid_run_config"
    if isinstance(exc, RuntimeError):
        return "provider_unavailable"
    return "extraction_failed"


@dataclass
class LocalJobRun:
    run_dir: Path | str
    run_config: Mapping[str, Any]
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    event_callback: JobEventCallback | None = None
    heartbeat_callback: JobEventCallback | None = None
    heartbeat_interval_seconds: float | None = None
    cancel_check: CancelCheck | None = None
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    status: str = "queued"
    result: dict[str, Any] = field(default_factory=dict)
    failure: dict[str, Any] | None = None
    _last_overall_ratio: float = field(default=0.0, init=False, repr=False)
    _last_stage_ratios: dict[tuple[str, str], float] = field(default_factory=dict, init=False, repr=False)
    _event_write_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _heartbeat_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _heartbeat_stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _heartbeat_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _heartbeat_state: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _heartbeat_started_at_monotonic: float = field(default=0.0, init=False, repr=False)
    _worker_thread_ident: int | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.run_dir = Path(self.run_dir)
        self.cancel_marker = self.run_dir / "cancel.requested"
        self.run_config_path = self.run_dir / "run_config.json"
        self.provider_diagnostics_path = self.run_dir / "provider_diagnostics.json"
        self.state_path = self.run_dir / "job.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.logs_path = self.run_dir / "logs.txt"
        self.metrics_path = self.run_dir / "metrics.json"
        self.artifacts_path = self.run_dir / "artifacts.json"
        self.failure_path = self.run_dir / "failure.json"

    def initialize(
        self,
        *,
        video_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        sam2_checkpoint: str | Path | None = None,
        sam2_model_config: str | Path | None = None,
    ) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._clear_previous_generated_outputs()
        for stale in (
            self.run_config_path,
            self.provider_diagnostics_path,
            self.state_path,
            self.events_path,
            self.logs_path,
            self.metrics_path,
            self.artifacts_path,
            self.failure_path,
            self.cancel_marker,
        ):
            if stale.exists():
                stale.unlink()
        _write_json(self.run_config_path, dict(self.run_config))
        diagnostics = build_capability_report(
            output_dir=output_dir or self.run_dir,
            video_path=video_path,
            sam2_checkpoint=sam2_checkpoint,
            sam2_model_config=sam2_model_config,
        )
        _write_json(
            self.provider_diagnostics_path,
            {
                "format": f"{JOB_ARTIFACT_FORMAT}.provider_diagnostics_snapshot",
                "jobId": self.job_id,
                "diagnostics": diagnostics,
            },
        )
        self.log("job queued")
        self._write_state()
        self.emit("queued", "queued", "job queued", event_type="job", progress={"overallRatio": 0.0})

    def _clear_previous_generated_outputs(self) -> None:
        for filename in GENERATED_EXTRACTION_FILES:
            path = self.run_dir / filename
            if path.exists() and path.is_file():
                path.unlink()
        for directory in GENERATED_EXTRACTION_DIRS:
            path = self.run_dir / directory
            if path.exists() and path.is_dir():
                shutil.rmtree(path)

    def start(self) -> None:
        self.started_at = utc_now()
        self.status = "running"
        self._worker_thread_ident = threading.get_ident()
        self.log("job started")
        self._write_state()
        self.emit("running", "running", "job started", event_type="job", progress={"overallRatio": 0.0})
        self.start_heartbeat()

    def emit(
        self,
        stage: str,
        status: str,
        message: str,
        *,
        event_type: str = "progress",
        progress: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        progress_payload = dict(progress or {})
        metadata_payload = dict(metadata or {})
        if "ratio" in progress_payload and "overallRatio" not in progress_payload:
            progress_payload["overallRatio"] = progress_payload.pop("ratio")
        overall = progress_payload.get("overallRatio")
        if isinstance(overall, (int, float)):
            monotonic = max(self._last_overall_ratio, min(float(overall), 1.0))
            self._last_overall_ratio = monotonic
            progress_payload["overallRatio"] = round(monotonic, 4)
            progress_payload["ratio"] = round(monotonic, 4)
        stage_ratio = progress_payload.get("stageRatio")
        if isinstance(stage_ratio, (int, float)):
            object_id = str(metadata_payload.get("objectId") or "")
            stage_key = (stage, object_id)
            monotonic_stage = max(self._last_stage_ratios.get(stage_key, 0.0), min(float(stage_ratio), 1.0))
            self._last_stage_ratios[stage_key] = monotonic_stage
            progress_payload["stageRatio"] = round(monotonic_stage, 4)
        event = {
            "format": JOB_EVENT_FORMAT,
            "id": uuid.uuid4().hex,
            "jobId": self.job_id,
            "timestamp": utc_now(),
            "type": event_type,
            "stage": stage,
            "status": status,
            "message": message,
            "progress": progress_payload,
            "metadata": metadata_payload,
        }
        if event_type != "worker_heartbeat":
            self._update_heartbeat_state(stage=stage, status=status, message=message, metadata=metadata_payload)
        self._append_event(event)
        self._dispatch_event(event, self.event_callback)
        return event

    def start_heartbeat(self) -> None:
        interval = self.heartbeat_interval_seconds
        if interval is None:
            interval = worker_heartbeat_interval_seconds()
        if interval <= 0:
            return
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_started_at_monotonic = time.monotonic()
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"motionjson-heartbeat-{self.job_id[:8]}",
            args=(float(interval),),
            daemon=True,
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def _heartbeat_loop(self, interval: float) -> None:
        while not self._heartbeat_stop.wait(interval):
            try:
                self._emit_heartbeat(interval)
            except Exception as exc:
                try:
                    self.log(f"worker heartbeat failed: {type(exc).__name__}: {exc}")
                except Exception:
                    pass

    def _emit_heartbeat(self, interval: float) -> dict[str, Any]:
        with self._heartbeat_lock:
            state = dict(self._heartbeat_state)
        stage = str(state.get("stage") or "running")
        status = str(state.get("status") or self.status or "running")
        metadata = dict(state.get("metadata") or {})
        metadata.update(
            {
                "heartbeatIntervalSeconds": interval,
                "elapsedSeconds": round(max(0.0, time.monotonic() - self._heartbeat_started_at_monotonic), 3),
                "pid": os.getpid(),
                "workerThreadIdent": self._worker_thread_ident,
                "heartbeatThreadName": threading.current_thread().name,
                "activeStage": stage,
                "activeStatus": status,
                "activeMessage": state.get("message") or "",
            }
        )
        event = {
            "format": JOB_EVENT_FORMAT,
            "id": uuid.uuid4().hex,
            "jobId": self.job_id,
            "timestamp": utc_now(),
            "type": "worker_heartbeat",
            "stage": stage,
            "status": status,
            "message": f"worker heartbeat during {stage}",
            "progress": {},
            "metadata": metadata,
        }
        self._append_event(event)
        self._dispatch_event(event, self.heartbeat_callback or self.event_callback)
        return event

    def _update_heartbeat_state(self, *, stage: str, status: str, message: str, metadata: Mapping[str, Any]) -> None:
        with self._heartbeat_lock:
            self._heartbeat_state = {
                "stage": stage,
                "status": status,
                "message": message,
                "metadata": dict(metadata),
                "updatedAt": utc_now(),
            }

    def _append_event(self, event: Mapping[str, Any]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self._event_write_lock:
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(dict(event), sort_keys=True) + "\n")

    def _dispatch_event(self, event: dict[str, Any], callback: JobEventCallback | None) -> None:
        if callback is not None:
            callback(event)

    def log(self, message: str) -> None:
        _append_text(self.logs_path, f"[{utc_now()}] {message}\n")

    def check_cancel(self, stage: str) -> None:
        if self.cancel_marker.exists() or (self.cancel_check is not None and self.cancel_check()):
            raise JobCanceled(f"job canceled during {stage}")

    def succeed(
        self,
        *,
        scene: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        progress_ratio: float = 1.0,
    ) -> None:
        self.status = "succeeded"
        self.finished_at = utc_now()
        self.stop_heartbeat()
        self.result = result or {}
        self.log("job succeeded")
        self.write_metrics(scene=scene)
        artifacts = self.write_artifact_manifest()
        self.result.setdefault("artifactCount", len(artifacts))
        self.result.setdefault("artifactBytes", sum(int(artifact["byteSize"]) for artifact in artifacts))
        self.emit(
            "succeeded",
            "succeeded",
            "job completed",
            event_type="job",
            progress={"overallRatio": progress_ratio},
            metadata=self.result,
        )
        self._write_state()

    def fail(self, exc: BaseException, *, reason_code: str | None = None, user_message: str | None = None) -> None:
        self.status = "failed"
        self.finished_at = utc_now()
        self.stop_heartbeat()
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        message = user_message or str(exc) or type(exc).__name__
        self.log(f"job failed: {message}")
        _append_text(self.logs_path, "\nTraceback:\n" + tb)
        self.failure = {
            "format": f"{JOB_ARTIFACT_FORMAT}.failure",
            "jobId": self.job_id,
            "status": "failed",
            "reasonCode": reason_code or _reason_code(exc),
            "message": message,
            "exceptionType": type(exc).__name__,
            "tracebackRef": "logs.txt",
            "createdAt": self.finished_at,
        }
        _write_json(self.failure_path, self.failure)
        self.write_metrics(scene=None)
        artifacts = self.write_artifact_manifest()
        self.result = {"artifactCount": len(artifacts), "artifactBytes": sum(int(artifact["byteSize"]) for artifact in artifacts)}
        self.emit("failed", "failed", message, event_type="job", metadata=self.failure)
        self._write_state()

    def cancel(self, message: str = "job canceled") -> None:
        self.status = "canceled"
        self.finished_at = utc_now()
        self.stop_heartbeat()
        self.log(message)
        self.failure = {
            "format": f"{JOB_ARTIFACT_FORMAT}.cancellation",
            "jobId": self.job_id,
            "status": "canceled",
            "reasonCode": "user_canceled",
            "message": message,
            "createdAt": self.finished_at,
        }
        _write_json(self.failure_path, self.failure)
        self.write_metrics(scene=None)
        artifacts = self.write_artifact_manifest()
        self.result = {"artifactCount": len(artifacts), "artifactBytes": sum(int(artifact["byteSize"]) for artifact in artifacts)}
        self.emit("canceled", "canceled", message, event_type="job", progress={"overallRatio": 1.0}, metadata=self.failure)
        self._write_state()

    def write_metrics(self, *, scene: dict[str, Any] | None) -> dict[str, Any]:
        artifacts = self.scan_artifacts(exclude={"metrics.json", "artifacts.json"})
        metrics = {
            "format": f"{JOB_ARTIFACT_FORMAT}.metrics",
            "jobId": self.job_id,
            "status": self.status,
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "artifactCount": len(artifacts),
            "artifactBytes": sum(int(artifact["byteSize"]) for artifact in artifacts),
            "latencyMetrics": scene.get("latencyMetrics", {}) if isinstance(scene, dict) else {},
            "providerPerformance": scene.get("providerPerformance", {}) if isinstance(scene, dict) else {},
            "costDashboard": scene.get("costDashboard", {}) if isinstance(scene, dict) else {},
        }
        _write_json(self.metrics_path, metrics)
        return metrics

    def scan_artifacts(self, *, exclude: set[str] | None = None) -> list[dict[str, Any]]:
        excluded = exclude or set()
        records: list[dict[str, Any]] = []
        if not self.run_dir.exists():
            return records
        for path in sorted(self.run_dir.rglob("*")):
            if not path.is_file():
                continue
            rel_path = str(path.relative_to(self.run_dir)).replace("\\", "/")
            if rel_path in excluded:
                continue
            records.append(
                {
                    "path": rel_path,
                    "kind": artifact_kind_for_rel_path(rel_path),
                    "byteSize": path.stat().st_size,
                    "contentType": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "objectId": _object_id_for_rel_path(rel_path),
                }
            )
        return records

    def write_artifact_manifest(self) -> list[dict[str, Any]]:
        artifacts = self.scan_artifacts(exclude={"artifacts.json"})
        manifest = {
            "format": f"{JOB_ARTIFACT_FORMAT}.manifest",
            "jobId": self.job_id,
            "status": self.status,
            "runDir": str(self.run_dir),
            "artifacts": artifacts,
        }
        _write_json(self.artifacts_path, manifest)
        return artifacts

    def _write_state(self) -> None:
        _write_json(
            self.state_path,
            {
                "format": f"{JOB_ARTIFACT_FORMAT}.state",
                "id": self.job_id,
                "status": self.status,
                "createdAt": self.created_at,
                "startedAt": self.started_at,
                "finishedAt": self.finished_at,
                "runDir": str(self.run_dir),
                "result": self.result,
                "failure": self.failure,
                "cancelMarker": "cancel.requested",
            },
        )
