"""Ties tracking + steering + controller output together behind the failsafe
state machine (spec sections 21, 59-61, 72). Framework-agnostic: the camera
and hand-tracker are injected, so this is fully unit-testable with fakes -
no real camera or MediaPipe needed.

Priority (spec section 61), highest first:
    Emergency Stop > Application Stop > Tracking Failure > Normal Steering
"""
from __future__ import annotations

import logging
import time

from app.controller.base import VirtualController
from app.state import AppState
from app.steering.engine import SteeringEngine
from app.steering.pedals import PedalEngine
from app.vision.gestures import DebouncedEvent, HandPose

log = logging.getLogger("airwheel.session")


class SteeringSession:
    def __init__(
        self,
        steering_engine: SteeringEngine,
        controller: VirtualController,
        tracking_loss_grace_s: float = 0.3,
        throttle_engine: PedalEngine | None = None,
        brake_engine: PedalEngine | None = None,
        gestures_enabled: bool = False,
        gesture_hold_seconds: float = 0.4,
    ):
        self.engine = steering_engine
        self.controller = controller
        self.tracking_loss_grace_s = tracking_loss_grace_s

        # Phase 9: throttle/brake are optional and OFF unless engines are
        # supplied (spec sections 18, 19, 87, 88 - never enabled by default).
        self.throttle_engine = throttle_engine
        self.brake_engine = brake_engine
        self.handbrake_on = False

        # Phase 9: gestures are optional and OFF by default (spec sections
        # 20, 29). When enabled, poses must be held for gesture_hold_seconds
        # before they fire (spec section 92).
        self.gestures_enabled = gestures_enabled
        self._pose_debouncer = DebouncedEvent(hold_seconds=gesture_hold_seconds)
        self._recenter_debouncer = DebouncedEvent(hold_seconds=gesture_hold_seconds)
        self.input_paused = False

        self.state = AppState.IDLE
        self._last_seen_ts: float | None = None
        self._emergency = False

    # -- lifecycle -----------------------------------------------------
    def start(self) -> bool:
        if self._emergency:
            log.warning("Cannot start while in EMERGENCY_STOP; call reset_emergency() first")
            return False
        if not self.controller.is_connected and not self.controller.connect():
            self.state = AppState.CONTROLLER_ERROR
            return False
        self.state = AppState.READY
        return True

    def stop(self) -> None:
        self.controller.center()
        if self.throttle_engine is not None:
            self.throttle_engine.release()
        if self.brake_engine is not None:
            self.brake_engine.release()
        self.handbrake_on = False
        self.input_paused = False
        self.state = AppState.STOPPED

    def emergency_stop(self) -> None:
        """Highest priority: always wins, from any state."""
        self._emergency = True
        self.engine.emergency_stop()
        if self.throttle_engine is not None:
            self.throttle_engine.release()
        if self.brake_engine is not None:
            self.brake_engine.release()
        self.handbrake_on = False
        self.controller.emergency_stop()
        self.state = AppState.EMERGENCY_STOP
        log.warning("EMERGENCY STOP engaged")

    def reset_emergency(self) -> None:
        self._emergency = False
        self.state = AppState.STOPPED

    # -- per-frame update ------------------------------------------------
    def update_with_angle(self, angle_deg: float, now: float | None = None) -> float:
        """Call once per frame when both hands are tracked with sufficient
        confidence. Returns the steering value actually sent to the controller."""
        if self._emergency:
            return 0.0
        now = now if now is not None else time.monotonic()
        self._last_seen_ts = now
        if self.state in (AppState.TRACKING_LOST, AppState.READY, AppState.STOPPED):
            self.state = AppState.ACTIVE
        if self.input_paused:
            # Open-palm pause (spec section 20): hold center, don't advance
            # the smoother with fresh angle data, so resuming isn't a jolt.
            value = self.engine.last_output
            self.controller.set_steering(value)
            return value
        value = self.engine.update(angle_deg)
        self.controller.set_steering(value)
        return value

    def update_tracking_lost(self, now: float | None = None) -> float:
        """Call once per frame when hands are missing/low-confidence
        (spec section 72: grace period before treating it as a real loss)."""
        if self._emergency:
            return 0.0
        now = now if now is not None else time.monotonic()
        if self._last_seen_ts is not None and (now - self._last_seen_ts) < self.tracking_loss_grace_s:
            # still within grace period - hold last output, don't panic yet
            self.controller.set_steering(self.engine.last_output)
            return self.engine.last_output
        self.state = AppState.TRACKING_LOST
        value = self.engine.on_tracking_lost_tick()
        self.controller.set_steering(value)
        if self.throttle_engine is not None:
            self.throttle_engine.on_tracking_lost_tick()
            self.controller.set_throttle(self.throttle_engine.last_output)
        if self.brake_engine is not None:
            self.brake_engine.on_tracking_lost_tick()
            self.controller.set_brake(self.brake_engine.last_output)
        return value

    def calibrate_center(self, angle_deg: float) -> None:
        self.engine.calibrate_center(angle_deg)
        self.state = AppState.READY

    # -- Phase 9: pedals (spec sections 18, 19, 87, 88, 89) ---------------
    def update_throttle(self, hand_y: float) -> float | None:
        """No-op (returns None) unless a throttle_engine was supplied - the
        session never invents throttle behavior on its own."""
        if self.throttle_engine is None or self._emergency or self.input_paused:
            return None
        value = self.throttle_engine.update(hand_y)
        self.controller.set_throttle(value)
        return value

    def update_brake(self, hand_y: float) -> float | None:
        if self.brake_engine is None or self._emergency or self.input_paused:
            return None
        value = self.brake_engine.update(hand_y)
        self.controller.set_brake(value)
        return value

    def set_handbrake(self, on: bool, button: str = "XUSB_GAMEPAD_A") -> None:
        """Deliberate, discrete toggle - not driven by the gesture debouncer
        directly, so callers can also bind it to a key (spec section 91).
        `button` is whatever the active profile maps the handbrake to."""
        if self._emergency:
            return
        self.handbrake_on = on
        self.controller.set_button(button, on)

    # -- Phase 9: gestures (spec sections 20, 29, 73, 92) ------------------
    def pause_input(self) -> None:
        """Open-palm gesture: hold current center without disabling output
        entirely (spec section 20 - 'Pause/disable input')."""
        self.input_paused = True
        self.controller.set_steering(0.0)
        if self.throttle_engine is not None:
            self.controller.set_throttle(0.0)
        if self.brake_engine is not None:
            self.controller.set_brake(0.0)

    def resume_input(self) -> None:
        self.input_paused = False

    def gesture_neutral(self) -> None:
        """Closed-fist gesture: immediately zero everything (spec section
        20 - 'Emergency neutral'). Distinct from emergency_stop(): this does
        NOT latch - the session can keep steering normally on the next
        tracked frame, unlike the dedicated F12 emergency stop."""
        self.engine.emergency_stop()
        if self.throttle_engine is not None:
            self.throttle_engine.release()
            self.controller.set_throttle(0.0)
        if self.brake_engine is not None:
            self.brake_engine.release()
            self.controller.set_brake(0.0)
        self.controller.set_steering(0.0)

    def handle_pose_event(self, pose: HandPose | None, now: float | None = None) -> HandPose | None:
        """Feed the latest classified hand pose (or None if no clear pose).
        Returns the pose if it just fired (after being held long enough),
        else None. No-op entirely if gestures_enabled is False."""
        if not self.gestures_enabled:
            return None
        now = now if now is not None else time.monotonic()
        confirmed = self._pose_debouncer.update(pose, now)
        if confirmed == HandPose.OPEN_PALM:
            self.pause_input()
        elif confirmed == HandPose.FIST:
            self.gesture_neutral()
        elif confirmed is None and pose != HandPose.OPEN_PALM:
            # any non-open-palm pose sustained means the user isn't holding
            # the pause gesture anymore; resume as soon as we see the hands
            # doing something else and confirm it (handled by caller loop -
            # left simple/explicit here rather than magic auto-resume).
            pass
        return confirmed

    def handle_recenter_gesture(self, hands_close: bool, angle_deg: float, now: float | None = None) -> bool:
        """Optional: both hands brought together re-centers the wheel (spec
        section 29). Returns True the instant recentering fires."""
        if not self.gestures_enabled:
            return False
        now = now if now is not None else time.monotonic()
        confirmed = self._recenter_debouncer.update(hands_close, now)
        if confirmed is True:
            self.calibrate_center(angle_deg)
            return True
        return False
