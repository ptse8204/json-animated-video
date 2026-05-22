#!/usr/bin/env python3
"""Apply the MotionJSON Apache-2.0 and Colab notebook update.

Run this script from the root of https://github.com/ptse8204/json-animated-video
after extracting the update bundle, or pass --repo /path/to/json-animated-video.
It is idempotent and avoids overwriting unrelated generated outputs.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"wrote {dst}")


def ensure_contains(path: Path, needle: str, insert_after: str, insertion: str) -> None:
    if not path.exists():
        print(f"skip missing {path}")
        return
    text = read(path)
    if needle in text:
        return
    if insert_after not in text:
        print(f"skip {path}: anchor not found for {needle!r}")
        return
    text = text.replace(insert_after, insert_after + insertion, 1)
    write(path, text)
    print(f"updated {path}")


def update_json_license(path: Path, anchor: str) -> None:
    if not path.exists():
        print(f"skip missing {path}")
        return
    text = read(path)
    if '"license"' in text:
        return
    if anchor in text:
        text = text.replace(anchor, anchor + '  "license": "Apache-2.0",\n', 1)
        write(path, text)
        print(f"updated {path}")
        return
    data = json.loads(text)
    data.setdefault("license", "Apache-2.0")
    write(path, json.dumps(data, indent=2) + "\n")
    print(f"updated {path}")


def replace_section(text: str, start_heading: str, next_heading: str, replacement_body: str) -> tuple[str, bool]:
    pattern = re.compile(rf"({re.escape(start_heading)}\n)(.*?)(?=\n{re.escape(next_heading)}\n)", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return text, False
    replacement = start_heading + "\n\n" + replacement_body.strip() + "\n"
    return pattern.sub(replacement, text, count=1), True


def update_readme(repo: Path) -> None:
    path = repo / "README.md"
    if not path.exists():
        print("skip missing README.md")
        return
    text = read(path)
    original = text

    old_badge = (
        "[![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)]"
        "(https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_red_ball_cli_demo.ipynb)\n"
    )
    new_badges = (
        "[![Open UI demo in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)]"
        "(https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_ui_local_demo.ipynb)\n"
        "[![Open CLI demo in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)]"
        "(https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_red_ball_cli_demo.ipynb)\n"
    )
    if old_badge in text and "colab_ui_local_demo.ipynb" not in text:
        text = text.replace(old_badge, new_badges, 1)

    colab_body = """
Colab is useful for short interactive demos and artifact inspection. It is not
the right place to host a long-running public MotionJSON web service, but the
checked-in notebooks cover the main onboarding paths:

- [Colab local UI demo](notebooks/colab_ui_local_demo.ipynb): launches the
  MotionJSON local UI inside a Colab runtime through the notebook port proxy.
- [Colab red-ball CLI demo](notebooks/colab_red_ball_cli_demo.ipynb): compact
  CPU/no-model extraction and validation path.
- [Colab export and browser preview demo](notebooks/colab_red_ball_export_preview.ipynb):
  creates a website ZIP and previews the browser runtime against generated
  MotionJSON assets.
- [Colab provider diagnostics](notebooks/colab_provider_diagnostics.ipynb):
  reports provider readiness and runs a no-model smoke extraction.

Keep shared notebooks free of private videos, provider credentials, SAM
checkpoints, hosted API keys, or other secrets.
"""
    text, replaced_colab = replace_section(
        text,
        "### Google Colab CLI demo",
        "### Hugging Face Space demo plan",
        colab_body,
    )
    if not replaced_colab and "## Colab notebooks" not in text:
        text += "\n\n## Colab notebooks\n\n" + colab_body.strip() + "\n"

    license_section = """## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
"""
    if "## License" in text:
        text = re.sub(r"## License\n\n.*\Z", license_section, text, count=1, flags=re.DOTALL)
    else:
        text += "\n\n" + license_section

    if text != original:
        write(path, text)
        print("updated README.md")


def update_free_instances(repo: Path) -> None:
    path = repo / "docs" / "run_free_instances.md"
    if not path.exists():
        print("skip missing docs/run_free_instances.md")
        return
    text = read(path)
    original = text
    body = """
Colab is suitable for short interactive demos and inspecting generated files.
It is not the right place to host a public long-running MotionJSON web service.
Use the checked-in notebooks when you want ready Colab surfaces:

- [Colab local UI demo](../notebooks/colab_ui_local_demo.ipynb): launches
  `python3 -m motionjson.cli ui --no-open --mock` in the notebook runtime and
  displays `/ui/` through Colab's port proxy.
- [Colab red-ball CLI demo](../notebooks/colab_red_ball_cli_demo.ipynb): runs
  the compact threshold extraction, validation, and ZIP download path.
- [Colab export and browser preview demo](../notebooks/colab_red_ball_export_preview.ipynb):
  runs extraction, validates output, exports a website ZIP, and previews
  `examples/plain_js_embed.html` against generated MotionJSON assets.
- [Colab provider diagnostics](../notebooks/colab_provider_diagnostics.ipynb):
  reports provider readiness and runs a no-model smoke extraction.

The UI notebook is intended for active, short, notebook-driven demos. Keep it in
mock/no-model mode first, avoid secrets in shared notebooks, and prefer
Codespaces or a local machine for sustained UI sessions.

Notebook cells can still use the manual CLI path:

```bash
!git clone https://github.com/ptse8204/json-animated-video.git
%cd json-animated-video
!python3 -m pip install -U pip
!python3 -m pip install -e ".[ui]"
!python3 -m motionjson.cli backend diagnostics --json
!python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4
!python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo_red_ball \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 12
!python3 -m motionjson.cli validate out/demo_red_ball
```

Use Colab file browsing or zip downloads to inspect generated outputs. Avoid
putting provider credentials in notebooks unless you understand Colab's sharing
and runtime behavior.
Google's Colab FAQ says resources are not guaranteed or unlimited, and it lists
file hosting, media serving, unrelated web services, and bypassing the notebook
UI to interact primarily through a web UI among restricted activities.
"""
    text, replaced = replace_section(text, "## Google Colab CLI demo", "## Hugging Face Space plan", body)
    if not replaced and "## Google Colab notebooks" not in text:
        text += "\n\n## Google Colab notebooks\n\n" + body.strip() + "\n"
    if text != original:
        write(path, text)
        print("updated docs/run_free_instances.md")


def update_pyproject(repo: Path) -> None:
    path = repo / "pyproject.toml"
    if not path.exists():
        print("skip missing pyproject.toml")
        return
    text = read(path)
    original = text
    if "license =" not in text:
        text = text.replace('readme = "README.md"\n', 'readme = "README.md"\nlicense = { file = "LICENSE" }\n', 1)
    if "License :: OSI Approved :: Apache Software License" not in text:
        text = text.replace(
            'dependencies = ["numpy", "opencv-python", "Pillow", "tqdm", "jsonschema>=4.22", "attrs>=23.1"]\n',
            'dependencies = ["numpy", "opencv-python", "Pillow", "tqdm", "jsonschema>=4.22", "attrs>=23.1"]\n'
            'classifiers = [\n'
            '  "License :: OSI Approved :: Apache Software License",\n'
            '  "Programming Language :: Python :: 3",\n'
            ']\n',
            1,
        )
    if text != original:
        write(path, text)
        print("updated pyproject.toml")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".", help="Path to the json-animated-video repo root")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    bundle = Path(__file__).resolve().parent
    if not (repo / "pyproject.toml").exists() or not (repo / "package.json").exists():
        raise SystemExit(f"{repo} does not look like the MotionJSON repository root")

    copy_file(bundle / "LICENSE", repo / "LICENSE")
    for src in (bundle / "notebooks").iterdir():
        if src.is_file():
            copy_file(src, repo / "notebooks" / src.name)
    copy_file(
        bundle / "docs" / "roadmap" / "phase-license-colab-notebooks-report.md",
        repo / "docs" / "roadmap" / "phase-license-colab-notebooks-report.md",
    )

    update_json_license(repo / "package.json", '  "private": true,\n')
    update_json_license(repo / "packages" / "motionjson-runtime" / "package.json", '  "sideEffects": false,\n')
    update_json_license(repo / "packages" / "motionjson-sdk" / "package.json", '  "sideEffects": false,\n')
    update_pyproject(repo)
    update_readme(repo)
    update_free_instances(repo)

    print("\nRecommended validation:")
    print("python3 -m json.tool notebooks/colab_ui_local_demo.ipynb >/dev/null")
    print("python3 -m json.tool notebooks/colab_red_ball_export_preview.ipynb >/dev/null")
    print("python3 -m json.tool notebooks/colab_provider_diagnostics.ipynb >/dev/null")
    print('python3 -m pip install -e ".[ui]"')
    print("python3 -m motionjson.cli backend diagnostics --json")
    print("python3 -m motionjson.cli ui --help")
    print("npm test && npm run build && npm run lint && npm run ui:layout && npm run embed:smoke")


if __name__ == "__main__":
    main()
