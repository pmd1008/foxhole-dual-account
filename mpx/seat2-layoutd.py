#!/usr/bin/env python3
"""
seat2-layoutd — переключение раскладки на второй клавиатуре.

KWin ловит Alt+Shift только с основной клавиатуры, поэтому у второго места язык не
менялся. Демон слушает клавиатуры через evdev и для НЕосновных клавиатур переключает
XKB-группу их master-устройства (XkbLockGroup). Основную не трогает — там KWin.

Запуск: seat2-layoutd [-v]
"""
import ctypes
import os
import re
import selectors
import subprocess
import sys
import time

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv
LOG = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp",
                   f"seat2-layoutd-{os.getuid()}.log")
GROUPS = int(os.environ.get("SEAT2_LAYOUT_GROUPS", "2"))

from evdev import ecodes, InputDevice, list_devices  # noqa: E402

QDBUS = next((p for p in ("/usr/bin/qdbus-qt6", "/usr/bin/qdbus6", "/usr/bin/qdbus")
              if os.path.exists(p)), "qdbus")

ALT = {ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT}
SHIFT = {ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT}


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass
    if VERBOSE:
        print(line, flush=True)


x11 = ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]


class XkbStateRec(ctypes.Structure):
    _fields_ = [("group", ctypes.c_ubyte), ("locked_group", ctypes.c_ubyte),
                ("base_group", ctypes.c_short), ("latched_group", ctypes.c_short),
                ("mods", ctypes.c_ubyte), ("base_mods", ctypes.c_ubyte),
                ("latched_mods", ctypes.c_ubyte), ("locked_mods", ctypes.c_ubyte),
                ("compat_state", ctypes.c_ubyte), ("grab_mods", ctypes.c_ubyte),
                ("compat_grab_mods", ctypes.c_ubyte), ("lookup_mods", ctypes.c_ubyte),
                ("compat_lookup_mods", ctypes.c_ubyte), ("ptr_buttons", ctypes.c_ushort)]


x11.XkbGetState.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(XkbStateRec)]
x11.XkbLockGroup.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]

dpy = x11.XOpenDisplay(None)
if not dpy:
    print("seat2-layoutd: нет X display", file=sys.stderr)
    raise SystemExit(1)


def xinput(*args):
    try:
        return subprocess.run(["xinput", *args], capture_output=True, text=True,
                              timeout=5).stdout
    except Exception:
        return ""


def master_map():
    """имя slave-устройства (нижний регистр) -> id мастера."""
    out = xinput("list")
    mapping = {}
    for line in out.splitlines():
        if "[slave" not in line:
            continue
        parent = re.search(r"\((\d+)\)", line)
        mid = re.search(r"id=(\d+)", line)
        if not (parent and mid):
            continue
        name = re.sub(r"\s+id=\d+.*$", "", line)
        name = re.sub(r"^[^0-9A-Za-z]+", "", name)
        name = re.sub(r"\s+", " ", name).strip().lower()
        mapping[name] = int(parent.group(1))
    return mapping


core_ids = set()
for name in ("Virtual core keyboard",):
    ids = [i for i in xinput("list", "--id-only", name).split() if i.isdigit()]
    if ids:
        core_ids.add(int(ids[0]))
log(f"старт: core keyboard ids={sorted(core_ids)} groups={GROUPS}")


def current_group(dev):
    st = XkbStateRec()
    x11.XkbGetState(dpy, dev, ctypes.byref(st))
    return st.group


def toggle(dev):
    """Глобальное переключение раскладки KDE (обновляет и индикатор, и приложения)."""
    r = subprocess.run([QDBUS, "org.kde.keyboard", "/Layouts",
                        "org.kde.KeyboardLayouts.switchToNextLayout"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        log(f"switchToNextLayout (dev {dev})")
    else:
        log(f"qdbus failed: {r.stderr.strip()[:80]}")


sel = selectors.DefaultSelector()
known = set()
last_map = 0.0
seat_map = {}
held = set()
last_toggle = 0.0


def refresh_devices():
    for path in list_devices():
        if path in known:
            continue
        try:
            dev = InputDevice(path)
            codes = set(dev.capabilities(verbose=False).get(ecodes.EV_KEY, []))
            if codes & (ALT | SHIFT):
                sel.register(dev, selectors.EVENT_READ)
                known.add(path)
                log(f"слушаю {dev.name}")
        except Exception:
            pass


refresh_devices()
while True:
    now = time.time()
    if now - last_map > 2.0:
        seat_map = master_map()
        last_map = now
    for key, _ in sel.select(timeout=1.0):
        dev = key.fileobj
        try:
            for ev in dev.read():
                if ev.type != ecodes.EV_KEY:
                    continue
                if ev.value == 1:
                    held.add(ev.code)
                    if held & ALT and held & SHIFT and ev.code in (ALT | SHIFT):
                        if time.time() - last_toggle < 0.4:
                            continue
                        last_toggle = time.time()
                        devname = re.sub(r"\s+", " ", dev.name or "").strip().lower()
                        master = seat_map.get(devname)
                        if master is None or master in core_ids:
                            continue  # основную клавиатуру обрабатывает KWin
                        toggle(master)
                elif ev.value == 0:
                    held.discard(ev.code)
        except OSError:
            try:
                sel.unregister(dev)
            except Exception:
                pass
            known.discard(dev.path)
