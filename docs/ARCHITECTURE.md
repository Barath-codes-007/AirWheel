# Architecture notes (spec section 125)

- **MediaPipe over the legacy `mp.solutions.hands` API**: the mediapipe
  version pinned here only ships the newer Tasks API
  (`mediapipe.tasks.python.vision.HandLandmarker`); the old solutions API
  has been removed from recent mediapipe releases.
- **Controller backend abstraction** (`app/controller/base.py`): the
  steering engine and session never import vgamepad or `keyboard` directly,
  only the `VirtualController` interface, so a backend can be swapped or a
  new one added without touching steering logic.
- **Two-hand geometry over "left hand left of center = turn left"**: raw
  screen position is noisy and depends on where the user sits; the angle of
  the vector between the wrists is stable across seating positions once
  normalized against the calibrated hand separation.
- **EMA smoothing by default** over a one-euro/Kalman filter: simplest to
  reason about and tune (`low`/`medium`/`high` = alpha 0.8/0.5/0.25); the
  interface (`EmaSmoother`) is small enough to swap later if EMA proves too
  laggy or too jittery in practice.
- **Local-only processing**: no camera frame is ever written to disk or
  logged; only derived numbers (angles, steering values, FPS) are logged.

## Phase 9 additions

- **Gesture confirmation** (`app/vision/gestures.py::DebouncedEvent`): every
  gesture (open-palm pause, fist neutral, hands-together recenter) must be
  held for a configurable duration before it fires, so one noisy frame
  can't trigger it (spec section 92). It's edge-triggered - it fires once
  when the hold threshold is crossed, not once per frame while held.
- **Gesture neutral vs. emergency stop**: a closed-fist gesture
  (`SteeringSession.gesture_neutral()`) zeroes steering/throttle/brake
  immediately but does NOT latch the EMERGENCY_STOP state the way the F12
  hotkey does (`SteeringSession.emergency_stop()`) - normal steering can
  resume on the very next tracked frame. Conflating the two would mean a
  single false-positive fist detection could require an explicit reset to
  drive again, which is a worse failure mode than "steering blips to zero."
- **Pedals never touch steering**: `PedalEngine` (`app/steering/pedals.py`)
  has no reference to `SteeringEngine` at all - it's a separate instance per
  pedal, so a pedal bug categorically cannot corrupt steering output (spec
  section 87: "Do not interfere with steering").
- **Handbrake stays a discrete toggle**, not a gesture output directly -
  `SteeringSession.set_handbrake()` takes an explicit on/off and a button
  name from the active profile, so it can be driven by a gesture, a key, or
  the UI without the session caring which (spec section 91: "Require a
  deliberate gesture or configurable button").
