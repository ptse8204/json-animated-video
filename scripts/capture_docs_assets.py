#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"
REQUIRED_SCREENSHOTS = {
    "local-ui-first-run.png": "first-run",
    "local-ui-new-project.png": "new-project",
    "local-ui-extraction-wizard.png": "extraction-wizard",
    "local-ui-provider-diagnostics.png": "provider-diagnostics",
    "local-ui-job-review.png": "job-review",
}
CAPTURE_READY_TIMEOUT_SECONDS = 8


def find_chrome() -> str | None:
    candidates = [
        os.environ.get("CHROME_BIN"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, check=True, **kwargs)


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_server(process: subprocess.Popen[str]) -> str:
    assert process.stdout is not None
    deadline = time.time() + 20
    lines: list[str] = []
    while time.time() < deadline:
        line = process.stdout.readline()
        if line:
            lines.append(line.strip())
            if "MotionJSON UI:" in line:
                return line.split("MotionJSON UI:", 1)[1].strip()
        if process.poll() is not None:
            raise RuntimeError("UI server exited before startup:\n" + "\n".join(lines))
    raise TimeoutError("Timed out waiting for MotionJSON UI startup")


def start_ui(db: Path, storage: Path) -> tuple[subprocess.Popen[str], str]:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "motionjson.cli",
            "ui",
            "--no-open",
            "--mock",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--db",
            str(db),
            "--storage-root",
            str(storage),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process, wait_for_server(process).rstrip("/")


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def seed_ui(base_url: str, video_path: Path) -> dict[str, Any]:
    project = request_json("POST", f"{base_url}/api/projects", {"name": "README Demo Project"})["project"]
    video = request_json(
        "POST",
        f"{base_url}/api/videos",
        {"projectId": project["id"], "path": str(video_path)},
    )["video"]
    job = request_json(
        "POST",
        f"{base_url}/api/jobs",
        {
            "projectId": project["id"],
            "videoId": video["id"],
            "maskProvider": "mock",
            "maxFrames": 2,
            "sampleFps": 12,
            "run": True,
        },
    )["job"]

    deadline = time.time() + 15
    while time.time() < deadline:
        job = request_json("GET", f"{base_url}/api/jobs/{job['id']}")["job"]
        if job.get("status") in {"succeeded", "failed", "canceled"}:
            break
        time.sleep(0.2)
    if job.get("status") != "succeeded":
        raise RuntimeError(f"Mock UI job did not succeed: {job}")
    return {"project": project, "video": video, "job": job}


def validate_image(path: Path, minimum_size: int = 2048, *, require_content: bool = False) -> bool:
    if not path.exists() or path.stat().st_size < minimum_size:
        return False
    try:
        with Image.open(path) as image:
            image.load()
            if require_content:
                extrema = image.convert("RGB").getextrema()
                if not any(low != high for low, high in extrema):
                    return False
        return True
    except OSError:
        return False


def stop_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)


def chrome_common_args(user_data_dir: Path) -> list[str]:
    return [
        "--headless=new",
        "--disable-background-networking",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-gpu",
        "--disable-sync",
        "--no-first-run",
        "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        "--window-size=1440,1000",
        f"--user-data-dir={user_data_dir}",
    ]


def decode_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def wait_for_capture_ready(chrome: str, url: str) -> None:
    profile_parent = Path(tempfile.mkdtemp(prefix="motionjson_chrome_probe_"))
    user_data_dir = profile_parent / "profile"
    command = [
        chrome,
        *chrome_common_args(user_data_dir),
        "--virtual-time-budget=7000",
        "--dump-dom",
        url,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=CAPTURE_READY_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = decode_output(error.stdout)
        stderr = decode_output(error.stderr)
        if 'data-capture-ready="true"' in stdout:
            return
        details = "\n".join(part[-1000:].strip() for part in [stdout, stderr] if part)
        raise RuntimeError(f"Timed out waiting for screenshot readiness for {url}\n{details}") from error
    finally:
        shutil.rmtree(profile_parent, ignore_errors=True)

    if result.returncode != 0 or 'data-capture-ready="true"' not in result.stdout:
        details = "\n".join(part for part in [result.stdout[-1000:].strip(), result.stderr[-1000:].strip()] if part)
        raise RuntimeError(f"UI did not report screenshot readiness for {url}\n{details}")


def capture_with_chrome(chrome: str, url: str, out_path: Path) -> None:
    wait_for_capture_ready(chrome, url)
    if out_path.exists():
        out_path.unlink()
    profile_parent = Path(tempfile.mkdtemp(prefix=f"motionjson_chrome_{out_path.stem}_"))
    user_data_dir = profile_parent / "profile"
    command = [
        chrome,
        *chrome_common_args(user_data_dir),
        "--virtual-time-budget=4500",
        f"--screenshot={out_path}",
        url,
    ]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        deadline = time.time() + 25
        while time.time() < deadline:
            if validate_image(out_path, require_content=True):
                break
            if process.poll() is not None:
                break
            time.sleep(0.25)
        stop_process_group(process)
        stdout, stderr = process.communicate(timeout=3)
    finally:
        shutil.rmtree(profile_parent, ignore_errors=True)

    if not validate_image(out_path, require_content=True):
        details = "\n".join(part for part in [stdout.strip(), stderr.strip()] if part)
        raise RuntimeError(f"Chrome did not write a usable screenshot: {out_path}\n{details}")


def make_red_ball_outputs(tmp: Path) -> tuple[Path, Path]:
    video = tmp / "demo_red_ball.mp4"
    out_dir = tmp / "demo_red_ball"
    run([sys.executable, "examples/make_demo_video.py", "--out", str(video)], stdout=subprocess.PIPE)
    run(
        [
            sys.executable,
            "-m",
            "motionjson.cli",
            "extract",
            str(video),
            "--out",
            str(out_dir),
            "--mask-provider",
            "threshold",
            "--lower-hsv",
            "0,80,80",
            "--upper-hsv",
            "12,255,255",
            "--sample-fps",
            "12",
            "--max-frames",
            "12",
        ],
        stdout=subprocess.PIPE,
    )
    return out_dir, video


def overlay_frame(frame_path: Path, mask_path: Path, label: str) -> Image.Image:
    frame = Image.open(frame_path).convert("RGBA")
    mask = Image.open(mask_path).convert("L").resize(frame.size)
    overlay = Image.new("RGBA", frame.size, (16, 163, 127, 0))
    overlay.putalpha(mask.point(lambda value: 105 if value else 0))
    composed = Image.alpha_composite(frame, overlay)
    bbox = mask.getbbox()
    draw = ImageDraw.Draw(composed)
    if bbox:
        draw.rectangle(bbox, outline=(16, 163, 127, 255), width=4)
        x0, y0, _x1, _y1 = bbox
        font = ImageFont.load_default()
        text_box = draw.textbbox((x0, max(0, y0 - 18)), label, font=font)
        draw.rectangle(
            (text_box[0] - 4, text_box[1] - 3, text_box[2] + 4, text_box[3] + 3),
            fill=(8, 32, 28, 220),
        )
        draw.text((text_box[0], text_box[1]), label, fill=(255, 255, 255, 255), font=font)
    return composed.convert("RGB")


def generate_red_ball_assets(out_dir: Path, asset_dir: Path) -> None:
    frame_paths = sorted((out_dir / "frames").glob("frame_*.png"))
    mask_paths = sorted((out_dir / "masks" / "object_0").glob("mask_*.png"))
    if not frame_paths or not mask_paths:
        raise RuntimeError("Expected red-ball frame and mask outputs were not generated")

    mid = min(len(frame_paths), len(mask_paths)) // 2
    preview = overlay_frame(frame_paths[mid], mask_paths[mid], "red ball")
    preview.save(asset_dir / "canvas-preview-red-ball.png", optimize=True)

    frames = [
        overlay_frame(frame, mask, "red ball").resize((320, 180), Image.Resampling.LANCZOS)
        for frame, mask in zip(frame_paths, mask_paths)
    ]
    frames[0].save(
        asset_dir / "red-ball-demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        optimize=True,
    )


def validate_assets(asset_dir: Path, *, require_screenshots: bool = True) -> None:
    expected = ["canvas-preview-red-ball.png", "red-ball-demo.gif"]
    if require_screenshots:
        expected = [*REQUIRED_SCREENSHOTS, *expected]
    missing = [name for name in expected if not (asset_dir / name).exists()]
    if missing:
        raise RuntimeError("Missing generated docs assets: " + ", ".join(missing))
    invalid = [name for name in expected if not validate_image(asset_dir / name, require_content=True)]
    if invalid:
        raise RuntimeError("Generated docs assets are not valid images: " + ", ".join(invalid))


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture real README screenshots and red-ball demo assets.")
    parser.add_argument("--out-dir", default=str(ASSET_DIR), help="Output directory for generated assets.")
    parser.add_argument("--check", action="store_true", help="Check local prerequisites without writing screenshots.")
    parser.add_argument("--skip-browser", action="store_true", help="Only generate red-ball preview assets; skip UI screenshots.")
    args = parser.parse_args()

    asset_dir = Path(args.out_dir)
    chrome = find_chrome()
    if args.check:
        print(json.dumps({"chrome": chrome, "assetDir": str(asset_dir), "canCaptureScreenshots": bool(chrome)}, indent=2))
        return 0
    if not args.skip_browser and not chrome:
        raise SystemExit("Chrome/Chromium is required for screenshot capture. Set CHROME_BIN or use --skip-browser.")

    asset_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="motionjson_docs_assets_") as tmp_raw:
        tmp = Path(tmp_raw)
        red_ball_out, red_ball_video = make_red_ball_outputs(tmp)
        generate_red_ball_assets(red_ball_out, asset_dir)

        if not args.skip_browser:
            process, base_url = start_ui(tmp / "backend.sqlite", tmp / "storage")
            try:
                capture_with_chrome(chrome, f"{base_url}/?capture=first-run", asset_dir / "local-ui-first-run.png")
                seed_ui(base_url, red_ball_video)
                for filename, capture in REQUIRED_SCREENSHOTS.items():
                    if filename == "local-ui-first-run.png":
                        continue
                    capture_with_chrome(chrome, f"{base_url}/?capture={capture}", asset_dir / filename)
            finally:
                stop_process(process)

    validate_assets(asset_dir, require_screenshots=not args.skip_browser)
    print(json.dumps({"status": "ok", "assetDir": str(asset_dir), "assets": sorted(path.name for path in asset_dir.glob("*"))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
