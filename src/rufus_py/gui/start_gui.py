import subprocess
import json
import sys
import urllib.parse
from pathlib import Path

from rufus_py.drives.find_usb import find_usb

def launch_gui_with_usb_data() -> None:
    usb_devices = find_usb()
    print("Detected USB devices:", usb_devices)

    usb_json = json.dumps(usb_devices)
    encoded_data = urllib.parse.quote(usb_json)

    try:
        gui_path = Path(__file__).resolve().with_name("gui.py")
        subprocess.run([sys.executable, str(gui_path), encoded_data], check=True)
    except FileNotFoundError as e:
        print(f"Failed to launch GUI: executable or script not found: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"GUI exited with an error (return code {e.returncode}): {e}")
        sys.exit(e.returncode or e)
    except Exception as e:
        print(f"Unexpected error while launching GUI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    launch_gui_with_usb_data()

"""
import sys as _s
import json as _j
import subprocess as _sp
import urllib.parse as _u
from pathlib import Path as _P

try:
    from rufus_py.drives.find_usb import find_usb as _f
except Exception as _e:
    _s.stderr.write(f"[init] import failure: {_e}\n")
    _s.exit(1)


def _encode_payload(_d):
    return _u.quote(_j.dumps(_d))


def _resolve_gui():
    _base = _P(__file__).resolve()
    return _base.parent / "gui.py"


def _execute(_target, _payload):
    if not _target.exists():
        raise FileNotFoundError(str(_target))

    _cmd = [_s.executable, str(_target), _payload]
    return _sp.run(_cmd, check=True)


def _orchestrate():
    try:
        _devices = _f()
    except Exception as _e:
        _s.stderr.write(f"[usb] detection failure: {_e}\n")
        _s.exit(1)

    _blob = _encode_payload(_devices)
    _gui = _resolve_gui()

    try:
        _execute(_gui, _blob)
    except _sp.CalledProcessError as _e:
        _s.stderr.write(f"[gui] exited: {_e.returncode}\n")
        _s.exit(_e.returncode)
    except Exception as _e:
        _s.stderr.write(f"[fatal] {_e}\n")
        _s.exit(1)


if __name__ == "__main__":
    _orchestrate() """ '''test this before commit - larvene'''
