# Virtual controller driver (ViGEmBus)

The analog controller backend (`app/controller/gamepad_backend.py`) uses
the `vgamepad` Python package (https://github.com/yannbouteiller/vgamepad),
confirmed via its README as of this writing:

- **Driver**: ViGEmBus (Virtual Gamepad Emulation Bus driver)
- **Install**: `pip install vgamepad` — this automatically launches the
  ViGEmBus installer; accept the license, click Install, wait, click Finish.
- **Windows versions**: vgamepad's Windows support is listed as "Stable" by
  the project; Linux support is listed as "Experimental". AirWheel targets
  Windows 10/11 (spec section 2) and has not been tested on Linux.
- **Security**: ViGEmBus is a kernel-mode driver that lets user-mode
  software present a virtual Xbox 360 / DS4 controller to Windows. Only
  install it from the official installer bundled with `vgamepad`'s pip
  package — do not download drivers from unrelated sites (spec section 101).
- **Uninstall**: Windows Settings → Apps → "ViGEmBus Driver" → Uninstall.

This backend has NOT been exercised on real Windows hardware in this
project yet (this dev environment is Linux, no driver). Treat it as
EXPERIMENTAL until you've run `python -m app.main`, connected a profile
using the `virtual_gamepad` backend, and confirmed a game or the Windows
"Set up USB game controllers" panel sees the device.

## Handbrake / buttons

`app/controller/gamepad_backend.py::set_button()` looks up the button name
against `vgamepad`'s `vg.XUSB_BUTTON` enum (e.g. `XUSB_GAMEPAD_A`). Pick
whichever button your game doesn't already use for something else, and set
it in the profile.
