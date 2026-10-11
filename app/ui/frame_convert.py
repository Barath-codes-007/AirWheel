"""BGR numpy frame -> QPixmap, for the live camera preview."""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage, QPixmap


def bgr_to_pixmap(frame_bgr: np.ndarray) -> QPixmap:
    h, w, ch = frame_bgr.shape
    # QImage has no native BGR888; swap to RGB first (cheap, numpy view when possible).
    rgb = frame_bgr[:, :, ::-1].copy()
    image = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(image)
