"""
Confidence calibration utility.

This module defines a `ConfidenceCalibrator` class which maintains
historical records of predicted confidence values versus actual
outcomes and fits a piecewise linear calibration function.  The
calibration function maps a raw confidence value (0–100) to a
calibrated value such that, over time, a prediction of X% maps to an
empirical hit-rate of approximately X%.

The calibrator persists its state to JSON and updates its model
whenever a new data point is recorded via the `update` method.
Calibration is performed using isotonic regression-like monotonic
interpolation between sorted pairs of `(predicted, success_rate)`.
"""

from __future__ import annotations

import json
import logging
from bisect import bisect_left
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


class ConfidenceCalibrator:
    """Calibrate raw confidence scores based on historical performance."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.history: List[Tuple[float, bool]] = []
        self.calibration: List[Tuple[float, float]] = []
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text())
                self.history = [(float(p), bool(s)) for p, s in data.get('history', [])]
                self.calibration = [(float(p), float(sr)) for p, sr in data.get('calibration', [])]
        except Exception:
            logger.debug("ConfidenceCalibrator failed to load", exc_info=True)

    def _save(self) -> None:
        try:
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'history': self.history, 'calibration': self.calibration}, indent=2))
            tmp.replace(self.path)
        except Exception:
            logger.debug("ConfidenceCalibrator failed to save", exc_info=True)

    def update(self, predicted: float, success: bool) -> None:
        try:
            self.history.append((float(predicted), bool(success)))
            max_records = 1000
            if len(self.history) > max_records:
                self.history = self.history[-max_records:]
            self._fit_calibration()
            self._save()
        except Exception:
            logger.debug("ConfidenceCalibrator update failed", exc_info=True)

    def _fit_calibration(self) -> None:
        if not self.history:
            return
        bins = {i: [] for i in range(0, 101, 10)}
        for pred, succ in self.history:
            key = min(100, int(pred // 10 * 10))
            bins[key].append(succ)
        calib: List[Tuple[float, float]] = []
        last_rate = 0.0
        for i in range(0, 101, 10):
            vals = bins[i]
            if vals:
                rate = sum(vals) / len(vals)
                last_rate = rate
            calib.append((float(i), float(last_rate)))
        self.calibration = calib

    def calibrate(self, predicted: float) -> float:
        if not self.calibration:
            return float(predicted)
        predicted = float(predicted)
        points = self.calibration
        xs = [p[0] for p in points]
        idx = bisect_left(xs, predicted)
        if idx <= 0:
            return points[0][1] * 100.0
        if idx >= len(points):
            return points[-1][1] * 100.0
        x0, y0 = points[idx - 1]
        x1, y1 = points[idx]
        if x1 == x0:
            return y0 * 100.0
        frac = (predicted - x0) / (x1 - x0)
        calibrated = y0 + frac * (y1 - y0)
        return calibrated * 100.0