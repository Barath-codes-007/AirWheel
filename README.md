# AirWheel

*Turn Your Hands Into a Steering Wheel.*

Camera-based virtual steering controller for Windows: webcam hand tracking → analog steering axis, with optional throttle/brake/handbrake/gestures.

## What's implemented and unit-tested (93 passing tests)

Run via a minimal pytest-compatible shim in this Linux dev sandbox (no
network to `pip install pytest` here) — install real `pytest` on your
machine and rerun `pytest` to confirm independently.

**Core (Phases 1-6, 8):**
- **Steering engine** (`app/steering/engine.py`) — angle wrapping, deadzone,
  sensitivity, response curves, EMA smoothing, clamping, tracking-loss
  return-to-center, emergency stop.
- **Hand geometry** (`app/vision/geometry.py`) — two-hand angle from
  landmark points, one-hand experimental mode, separation normalization.
- **Calibration** (`app/steering/calibration.py`) — center/reference
  computation and a 0-100 quality score with actionable notes.
- **Session/failsafe state machine** (`app/core/session.py`) — wires
  steering + a controller together behind the states in spec section 60:
  Emergency Stop > Stop > Tracking Loss > Normal Steering.
- **Profiles** (`app/profiles/manager.py`) — validated save/load/import/
  export; rejects malformed or malicious profile JSON without executing it.
- **Settings** (`app/config/settings.py`) — JSON load/save, corrupt-file and
  wrong-type resilience.
- **Camera helpers** (`app/camera/capture.py`) — BGR→RGB, mirroring, and
  threaded capture/FPS measurement; `list_cameras()` confirmed not to crash
  with zero cameras present.

**Phase 9 (throttle, brake, handbrake, gestures, overlay):**
- **Pedals** (`app/steering/pedals.py`) — hand-height → 0-1 throttle/brake,
  completely decoupled from the steering engine so a pedal bug can't
  corrupt steering. OFF by default (`PedalSettings.throttle_mode = "off"`).
- **Handbrake** — discrete on/off toggle mapped to a profile-configurable
  controller button (`SteeringSession.set_handbrake()`).
- **Gestures** (`app/vision/gestures.py`) — open-palm/fist classification
  from landmark geometry, plus a debounce layer (`DebouncedEvent`) that
  requires a pose to be held before it fires, so one noisy frame can't
  trigger anything. Open palm pauses steering; closed fist zeros
  steering/throttle/brake without latching the F12 emergency-stop state;
  hands brought together optionally recenters. All gestures are **disabled
  by default** (`GestureSettings.enabled = False`).
- **Overlay** (`app/overlay/overlay_window.py`) — configurable
  opacity/position/size and per-row show/hide, driven by `OverlaySettings`.
- **Pedal bar UI** (`app/ui/pedal_widget.py`) — steering/throttle/brake bars,
  wired into the main window but only shown when a profile actually enables
  a pedal.

## What's implemented but NOT run/tested on real hardware

No camera, no Windows, and no display are available in this dev
environment. These are real implementations against documented APIs, but
unverified end-to-end:

- **Hand tracking** (`app/vision/hand_tracking.py`) — MediaPipe Tasks API
  (`HandLandmarker`); requires a downloaded model, see `models/README.md`.
- **Keyboard backend** (`app/controller/keyboard_backend.py`) — needs the
  Windows-only `keyboard` package and usually admin rights.
- **Virtual gamepad backend** (`app/controller/gamepad_backend.py`) — needs
  `vgamepad` + the ViGEmBus driver on Windows, see `docs/DRIVER_SETUP.md`.
- **GUI** (`app/ui/`, `app/overlay/`) — PySide6 dashboard, calibration
  wizard, pedal bars, transparent overlay. `python -m app.main` falls back
  to a headless status printout when PySide6 is missing rather than
  crashing — that fallback path IS confirmed working.

Every one of these fails with a clear error (never a silent no-op or fake
success) if its dependency is missing — see spec section 58.

## Setup (Windows)

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -r requirements.txt
python scripts\download_model.py
pytest
python -m app.main
```

## Troubleshooting: "keyboard mode does nothing in my game"

By far the most common cause: **simulated key presses go to whichever window
has OS focus, not to AirWheel.** The `keyboard` package injects input at
the OS level (`SendInput`), which Windows then routes to the currently
focused window — exactly like a real keyboard. If AirWheel (or anything
else) is the focused window, your game/browser tab never sees the
LEFT/RIGHT presses.

Fix: after clicking START, click into the game/browser window so it has
focus, and don't click back on AirWheel while playing. AirWheel shows a
reminder dialog on START when keyboard mode is active.

Other things to check, in order:
1. **Running as Administrator** — the `keyboard` package needs elevated
   privileges to hook global keys on Windows; without it, presses can fail
   silently. Right-click your terminal/shortcut → "Run as administrator".
2. **Correct keys for the game** — AirWheel defaults to arrow-key LEFT/
   RIGHT (`OutputSettings.keyboard_left_key` / `keyboard_right_key` in
   settings.json). Most racing games/websites use arrows or WASD; check the
   game's own control scheme if it's unusual.
3. **Steering threshold not being crossed** — keyboard mode is digital: a
   key only fires once steering passes ±30% (default `threshold` in
   `KeyboardController`). Watch the Steering % in the telemetry panel while
   turning your hands; if it never crosses ~30%, recalibrate or increase
   sensitivity in the active profile.
4. **The site itself filters synthetic input** — rare, but some
   anti-automation browser games ignore `SendInput`-based key events on
   purpose. If a keyboard-testing site like keyboard-test.io also doesn't
   register AirWheel's key presses, that's this case, and no keyboard
   automation library can get around it from outside the browser.

## Privacy

Everything runs locally. No cloud, no camera upload, no camera recording. Logs never contain frames or landmarks.

## Limitations

Camera-based steering is not a replacement for a force-feedback racing wheel: no physical rotation, resistance, force feedback or mechanical precision. Poor lighting, occlusion, low FPS and hands leaving the frame all degrade tracking; the steering/pedal engines mitigate this with calibration, smoothing, deadzone, and safe return-to-center — but none of that has been validated against a real camera yet. Gesture detection here is a simple extended-finger-count heuristic, not a trained classifier — expect it to need tuning (the `extend_ratio` threshold in `app/vision/gestures.py`) against your actual hands and lighting.

## Docs

- `docs/ARCHITECTURE.md` — key design decisions, including Phase 9
- `docs/DRIVER_SETUP.md` — ViGEmBus driver + handbrake button mapping
- `docs/TEST_MATRIX.md` — manual test status (mostly NOT TESTED — see above)

## Status

Phases 1-6, 8, 9 have real, unit-tested implementations. Phase 7 (UI) is
written but unverified end-to-end. Phase 10 (real-hardware testing) is next
— and needs an actual Windows machine with a webcam, which this environment
doesn't have.
