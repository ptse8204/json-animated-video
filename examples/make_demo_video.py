from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="examples/demo_red_ball.mp4")
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--frames", type=int, default=96)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=360)
    args = p.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out), fourcc, args.fps, (args.width, args.height))
    if not writer.isOpened():
        raise RuntimeError("Could not open VideoWriter")

    for i in range(args.frames):
        frame = np.full((args.height, args.width, 3), (245, 245, 245), dtype=np.uint8)
        # BGR drawing; red object
        x = int(80 + i * (args.width - 160) / max(1, args.frames - 1))
        y = int(args.height / 2 + 50 * np.sin(i / 10))
        cv2.circle(frame, (x, y), 48, (20, 20, 230), -1)
        cv2.circle(frame, (x - 14, y - 16), 10, (120, 120, 255), -1)
        cv2.putText(frame, "demo object", (25, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (60, 60, 60), 2)
        writer.write(frame)
    writer.release()
    print(out)


if __name__ == "__main__":
    main()
