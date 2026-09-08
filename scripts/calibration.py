"""Shared authored dimension/camera candidates. Uncertainty lives with the data."""

import json
from pathlib import Path

CALIBRATION_PATH = Path(__file__).resolve().parents[1] / "config/calibration.json"
CALIBRATION = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
