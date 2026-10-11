"""Calibration wizard dialog (spec sections 6, 37, 77, 78). Same caveat as
main_window.py: written against the documented PySide6 API, not run here.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel, QProgressBar, QPushButton, QVBoxLayout, QWizard, QWizardPage,
)

from app.steering.calibration import CalibrationResult


class _CenterPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Step 1: Center your hands")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Hold your hands as if gripping a steering wheel, centered.\n"
            "If only one hand is detected: show both hands.\n"
            "If hands are too close: move them farther apart."
        ))


class _HoldStillPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Step 2: Hold still")
        layout = QVBoxLayout(self)
        self.progress = QProgressBar()
        layout.addWidget(QLabel("Hold the pose steady while we measure..."))
        layout.addWidget(self.progress)

    def set_progress(self, pct: int) -> None:
        self.progress.setValue(pct)


class _ResultPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Step 3: Test steering")
        layout = QVBoxLayout(self)
        self.quality_label = QLabel("Calibration quality: --")
        self.notes_label = QLabel("")
        self.notes_label.setWordWrap(True)
        layout.addWidget(self.quality_label)
        layout.addWidget(self.notes_label)
        layout.addWidget(QLabel("Turn left. Turn right. Return to center."))
        self.left_ok = QLabel("○ Left detected")
        self.center_ok = QLabel("○ Center detected")
        self.right_ok = QLabel("○ Right detected")
        for w in (self.left_ok, self.center_ok, self.right_ok):
            layout.addWidget(w)

    def show_result(self, result: CalibrationResult) -> None:
        self.quality_label.setText(f"Calibration quality: {result.quality_score}%")
        self.notes_label.setText(" ".join(result.quality_notes) or "Looks good.")

    def mark_detected(self, which: str) -> None:
        label = {"left": self.left_ok, "center": self.center_ok, "right": self.right_ok}.get(which)
        if label:
            label.setText(label.text().replace("○", "✓"))


class CalibrationWizard(QWizard):
    recalibrate_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AirWheel Calibration")
        self.center_page = _CenterPage()
        self.hold_page = _HoldStillPage()
        self.result_page = _ResultPage()
        self.addPage(self.center_page)
        self.addPage(self.hold_page)
        self.addPage(self.result_page)
