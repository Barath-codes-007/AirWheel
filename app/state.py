"""Application/failsafe states (spec section 60)."""
from enum import Enum


class AppState(str, Enum):
    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    CALIBRATING = "CALIBRATING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    TRACKING_LOST = "TRACKING_LOST"
    CAMERA_ERROR = "CAMERA_ERROR"
    CONTROLLER_ERROR = "CONTROLLER_ERROR"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    STOPPED = "STOPPED"
