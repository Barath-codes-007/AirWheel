"""Download the MediaPipe Hand Landmarker model used by app/vision/hand_tracking.py.

If this URL is out of date, get the current one from the official docs
(see models/README.md) and save it manually as models/hand_landmarker.task.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
DEST = Path(__file__).resolve().parents[1] / "models" / "hand_landmarker.task"


def main() -> int:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {URL}")
    try:
        urllib.request.urlretrieve(URL, DEST)
    except Exception as exc:  # noqa: BLE001 - report and exit non-zero
        print(f"Download failed: {exc}")
        print("Get the current model URL from the docs linked in models/README.md")
        return 1
    print(f"Saved to {DEST} ({DEST.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
