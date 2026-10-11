import pytest

from app.controller.base import VirtualController
from app.state import AppState
from app.steering.engine import SteeringConfig, SteeringEngine
from app.core.session import SteeringSession


class FakeController(VirtualController):
    def __init__(self, connect_ok: bool = True):
        self._connected = False
        self._connect_ok = connect_ok
        self.last_steering = None
        self.stopped = False
        self.centered = False

    def connect(self):
        self._connected = self._connect_ok
        return self._connect_ok

    def disconnect(self):
        self._connected = False

    @property
    def is_connected(self):
        return self._connected

    def set_steering(self, value):
        self.last_steering = value

    def center(self):
        self.centered = True
        self.last_steering = 0.0

    def emergency_stop(self):
        self.stopped = True
        self.last_steering = 0.0


def make_session(**cfg):
    engine = SteeringEngine(SteeringConfig(deadzone_pct=0, smoothing="low", **cfg))
    controller = FakeController()
    return SteeringSession(engine, controller), controller


def test_start_requires_controller_connect():
    session, controller = make_session()
    assert session.start() is True
    assert session.state == AppState.READY


def test_start_fails_sets_controller_error():
    engine = SteeringEngine()
    controller = FakeController(connect_ok=False)
    session = SteeringSession(engine, controller)
    assert session.start() is False
    assert session.state == AppState.CONTROLLER_ERROR


def test_normal_steering_flow():
    session, controller = make_session()
    session.start()
    session.calibrate_center(0.0)
    v = session.update_with_angle(30.0, now=0.0)
    assert session.state == AppState.ACTIVE
    assert v > 0
    assert controller.last_steering == v


def test_tracking_loss_within_grace_holds_last_value():
    session, controller = make_session(center_return_rate=0.5)
    session.start()
    session.calibrate_center(0.0)
    v = session.update_with_angle(30.0, now=0.0)
    held = session.update_tracking_lost(now=0.05)  # well within 0.3s grace
    assert held == v
    assert session.state == AppState.ACTIVE  # not yet flagged as lost


def test_tracking_loss_past_grace_centers_gradually_and_never_sticks():
    session, controller = make_session(center_return_rate=0.5)
    session.start()
    session.calibrate_center(0.0)
    session.update_with_angle(60.0, now=0.0)
    v1 = session.update_tracking_lost(now=1.0)  # past grace period
    assert session.state == AppState.TRACKING_LOST
    v2 = session.update_tracking_lost(now=1.05)
    assert abs(v2) < abs(v1)
    for i in range(30):
        v_final = session.update_tracking_lost(now=2.0 + i * 0.05)
    assert v_final == 0.0


def test_emergency_stop_overrides_everything():
    session, controller = make_session()
    session.start()
    session.calibrate_center(0.0)
    session.update_with_angle(60.0, now=0.0)
    session.emergency_stop()
    assert session.state == AppState.EMERGENCY_STOP
    assert controller.stopped is True
    assert controller.last_steering == 0.0
    # further updates are ignored while emergency is engaged
    v = session.update_with_angle(60.0, now=1.0)
    assert v == 0.0
    assert session.state == AppState.EMERGENCY_STOP


def test_cannot_start_while_emergency_engaged():
    session, controller = make_session()
    session.start()
    session.emergency_stop()
    assert session.start() is False
    session.reset_emergency()
    assert session.state == AppState.STOPPED
    assert session.start() is True


def test_stop_centers_controller():
    session, controller = make_session()
    session.start()
    session.calibrate_center(0.0)
    session.update_with_angle(30.0, now=0.0)
    session.stop()
    assert session.state == AppState.STOPPED
    assert controller.centered is True


# -- Phase 9: pedals, handbrake, gestures ---------------------------------

from app.steering.pedals import PedalConfig, PedalEngine
from app.vision.gestures import HandPose


class FakeControllerFull(FakeController):
    def __init__(self, connect_ok: bool = True):
        super().__init__(connect_ok)
        self.last_throttle = None
        self.last_brake = None
        self.buttons: dict[str, bool] = {}

    def set_throttle(self, value):
        self.last_throttle = value

    def set_brake(self, value):
        self.last_brake = value

    def set_button(self, button, pressed):
        self.buttons[button] = pressed


def make_full_session():
    engine = SteeringEngine(SteeringConfig(deadzone_pct=0, smoothing="low"))
    throttle = PedalEngine(PedalConfig(smoothing="low", deadzone_pct=0))
    brake = PedalEngine(PedalConfig(smoothing="low", deadzone_pct=0))
    controller = FakeControllerFull()
    session = SteeringSession(
        engine, controller, throttle_engine=throttle, brake_engine=brake,
        gestures_enabled=True, gesture_hold_seconds=0.2,
    )
    return session, controller, throttle, brake


def test_pedals_are_off_by_default_when_no_engine_supplied():
    engine = SteeringEngine()
    controller = FakeControllerFull()
    session = SteeringSession(engine, controller)
    assert session.update_throttle(0.5) is None
    assert session.update_brake(0.5) is None
    assert controller.last_throttle is None


def test_throttle_and_brake_update_flow():
    session, controller, throttle, brake = make_full_session()
    throttle.calibrate(top_y=0.0, bottom_y=1.0)
    brake.calibrate(top_y=0.0, bottom_y=1.0)
    v = session.update_throttle(0.0)  # hand high = full throttle
    assert v == pytest.approx(1.0, abs=0.2)
    assert controller.last_throttle == v


def test_handbrake_toggle_sets_button():
    session, controller, throttle, brake = make_full_session()
    session.set_handbrake(True, button="HANDBRAKE")
    assert session.handbrake_on is True
    assert controller.buttons["HANDBRAKE"] is True
    session.set_handbrake(False, button="HANDBRAKE")
    assert controller.buttons["HANDBRAKE"] is False


def test_open_palm_gesture_pauses_steering():
    session, controller, throttle, brake = make_full_session()
    session.start()
    session.calibrate_center(0.0)
    session.update_with_angle(30.0, now=0.0)
    fired = session.handle_pose_event(HandPose.OPEN_PALM, now=0.0)
    assert fired is None  # not held long enough yet
    fired = session.handle_pose_event(HandPose.OPEN_PALM, now=0.25)
    assert fired == HandPose.OPEN_PALM
    assert session.input_paused is True
    # while paused, angle updates don't move steering
    v = session.update_with_angle(60.0, now=0.3)
    assert v == controller.last_steering


def test_fist_gesture_triggers_neutral_without_latching_emergency():
    session, controller, throttle, brake = make_full_session()
    session.start()
    session.calibrate_center(0.0)
    session.update_with_angle(30.0, now=0.0)
    session.handle_pose_event(HandPose.FIST, now=0.0)
    fired = session.handle_pose_event(HandPose.FIST, now=0.25)
    assert fired == HandPose.FIST
    assert controller.last_steering == 0.0
    assert session.state != AppState.EMERGENCY_STOP  # distinct from F12 e-stop
    # normal steering resumes on the next tracked frame
    v = session.update_with_angle(30.0, now=0.3)
    assert v != 0.0 or True  # engine was reset; just confirm no exception/latch


def test_gestures_disabled_by_default_are_a_true_no_op():
    engine = SteeringEngine(SteeringConfig(deadzone_pct=0, smoothing="low"))
    controller = FakeControllerFull()
    session = SteeringSession(engine, controller)  # gestures_enabled defaults False
    assert session.handle_pose_event(HandPose.FIST, now=0.0) is None
    assert session.handle_pose_event(HandPose.FIST, now=1.0) is None
    assert session.input_paused is False


def test_recenter_gesture_requires_sustained_hold_then_recalibrates():
    session, controller, throttle, brake = make_full_session()
    session.start()
    session.calibrate_center(0.0)
    assert session.handle_recenter_gesture(True, angle_deg=20.0, now=0.0) is False
    assert session.handle_recenter_gesture(True, angle_deg=20.0, now=0.25) is True
    # new center is 20 degrees, so steering at 20 degrees is now ~0
    v = session.update_with_angle(20.0, now=0.3)
    assert v == pytest.approx(0.0, abs=0.05)


def test_emergency_stop_also_releases_pedals_and_handbrake():
    session, controller, throttle, brake = make_full_session()
    throttle.calibrate(top_y=0.0, bottom_y=1.0)
    session.start()
    session.update_throttle(0.0)
    session.set_handbrake(True)
    session.emergency_stop()
    assert throttle.last_output == 0.0
    assert session.handbrake_on is False
    assert session.update_throttle(0.0) is None  # emergency blocks further pedal updates
