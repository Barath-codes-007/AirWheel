# Manual Test Matrix

Never change NOT TESTED to PASS without actually testing on real hardware.

## Core (Phases 1-8)

| Test | Expected Result | Status |
|---|---|---|
| Camera detection | Camera appears | NOT TESTED (no camera in dev sandbox; enumeration confirmed not to crash with zero cameras) |
| Two hands | Both detected | NOT TESTED |
| Calibration | Center established | NOT TESTED (math unit-tested, not run against a real camera) |
| Left steering | Negative axis | NOT TESTED |
| Right steering | Positive axis | NOT TESTED |
| Center | Near zero | NOT TESTED |
| Tracking loss | Safe center | Unit-tested at the SteeringSession level (fake controller); NOT TESTED with a real camera |
| Camera disconnect | Output stops | NOT TESTED |
| Emergency stop | Immediate stop | Unit-tested at the SteeringSession level; NOT TESTED with real hotkey/hardware |
| Keyboard mode | Keys controlled | NOT TESTED (needs Windows + 'keyboard' package + admin) |
| Virtual controller | Axis moves | NOT TESTED (needs Windows + ViGEmBus) |
| GUI renders | Dashboard appears and is usable | NOT TESTED (PySide6 not installed / no display in dev sandbox) |
| **START button actually starts camera+tracking+output** | **Previously broken — button did nothing.** Now wired via `app/core/app_controller.py`. NOT TESTED on real hardware yet — please confirm. |

## Phase 9 - throttle/brake/gestures/overlay

| Test | Expected Result | Status |
|---|---|---|
| Throttle from hand height | Higher hand = more throttle | Unit-tested (PedalEngine math); NOT TESTED with a real hand/camera |
| Brake from hand height | Same as throttle, separate engine | Unit-tested; NOT TESTED with real hand/camera |
| Pedal tracking loss | Releases toward 0, never stuck | Unit-tested (`on_tracking_lost_tick`) |
| Handbrake toggle | Sets/clears the mapped button | Unit-tested at the session level (fake controller); NOT TESTED with a real game |
| Open-palm pause | Steering holds, resumes cleanly | Unit-tested (gesture classify + debounce + session pause); NOT TESTED with a real camera/hand |
| Closed-fist neutral | Zeros output, doesn't latch e-stop | Unit-tested; NOT TESTED with a real camera/hand |
| Hands-together recenter | Recalibrates center | Unit-tested; NOT TESTED with a real camera/hand (and OFF by default) |
| Overlay renders in Game Mode | Small always-on-top HUD | NOT TESTED (PySide6 not installed / no display) |
| Pedal bars in main UI | Show only when a pedal is enabled | NOT TESTED (PySide6 not installed / no display) |
