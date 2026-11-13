#!/usr/bin/env python3
"""
seat2-cp — назначает ClientPointer (XInput2) окнам игр по их Steam-аккаунту.

Клик и курсор в игре идут по тому указателю, который назначен окну как
ClientPointer. Два окна Foxhole на одном экране должны смотреть на разные
указатели, иначе fullscreen/грабы и курсор путаются.

Правило простое: у процесса игры читается HOME.
  * HOME = .../steam-alt  -> окно получает "second pointer" (второе место);
  * иначе                 -> "Virtual core pointer" (основное место).

Запуск: seat2-cp [--interval 2] [-v]
"""
import ctypes
import os
import re
import subprocess
import sys
import time

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv
INTERVAL = 2.0
for i, a in enumerate(sys.argv):
    if a == "--interval" and i + 1 < len(sys.argv):
        INTERVAL = float(sys.argv[i + 1])

x11 = ctypes.CDLL("libX11.so.6")
xi = ctypes.CDLL("libXi.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                           ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                           ctypes.POINTER(ctypes.c_uint)]
x11.XFree.argtypes = [ctypes.c_void_p]
x11.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
x11.XInternAtom.restype = ctypes.c_ulong
x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
x11.XGetWindowProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long,
                                   ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                   ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
                                   ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
xi.XIQueryVersion.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
xi.XISetClientPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int]
xi.XIGetClientPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_int)]
x11.XFlush.argtypes = [ctypes.c_void_p]

ALT_HOME = os.environ.get("FOXHOLE_ALT_HOME", os.path.expanduser("~/steam-alt"))
APP_HINT = os.environ.get("FOXHOLE_WINDOW_HINT", "War")
SECOND_HOME = os.path.realpath(ALT_HOME)


def log(msg):
    if VERBOSE:
        print(f"seat2-cp: {msg}", flush=True)


def master_id(name):
    try:
        out = subprocess.run(["xinput", "list", "--id-only", name],
                             capture_output=True, text=True, timeout=5).stdout
        ids = [i for i in out.split() if i.isdigit()]
        return int(ids[0]) if ids else None
    except Exception:
        return None


# Xlib по умолчанию завершает процесс на любой X-ошибке (BadWindow при закрытии окна
# игры — обычное дело). Ставим заглушку, чтобы демон переживал такие моменты.
ERRHANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)


def _ignore_x_error(display, event):
    return 0


_X_ERR_HANDLER = ERRHANDLER(_ignore_x_error)
x11.XSetErrorHandler.argtypes = [ERRHANDLER]
x11.XSetErrorHandler(_X_ERR_HANDLER)

dpy = x11.XOpenDisplay(None)
if not dpy:
    log("нет X display")
    raise SystemExit(1)
root = x11.XDefaultRootWindow(dpy)
ma, mi = ctypes.c_int(2), ctypes.c_int(0)
xi.XIQueryVersion(dpy, ctypes.byref(ma), ctypes.byref(mi))
NET_WM_PID = x11.XInternAtom(dpy, b"_NET_WM_PID", 0)

second_ptr = master_id("second pointer")
core_ptr = master_id("Virtual core pointer")
if not second_ptr or not core_ptr:
    log("нет мастер-указателей (нужен Xorg и поднятый second pointer)")
    raise SystemExit(1)
log(f"старт: second={second_ptr} core={core_ptr} interval={INTERVAL:g}s alt_home={SECOND_HOME}")

assigned = {}


def window_name(win):
    name = ctypes.c_char_p()
    if x11.XFetchName(dpy, win, ctypes.byref(name)) and name.value:
        s = name.value.decode("utf-8", "replace")
        x11.XFree(name)
        return s
    return ""


def window_pid(win):
    t = ctypes.c_ulong(); f = ctypes.c_int(); cnt = ctypes.c_ulong()
    rem = ctypes.c_ulong(); data = ctypes.POINTER(ctypes.c_ubyte)()
    x11.XGetWindowProperty(dpy, win, NET_WM_PID, 0, 1, 0, 0, ctypes.byref(t),
                           ctypes.byref(f), ctypes.byref(cnt), ctypes.byref(rem), ctypes.byref(data))
    pid = None
    if data:
        if cnt.value and f.value == 32:
            pid = ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[0]
        x11.XFree(data)
    return pid


def home_of(pid):
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            for item in f.read().split(b"\0"):
                if item.startswith(b"HOME="):
                    return os.path.realpath(item[5:].decode())
    except OSError:
        return None
    return None


def walk(win, depth=0):
    """Все окна дерева (в глубину)."""
    yield win
    if depth > 12:
        return
    r = ctypes.c_ulong(); p = ctypes.c_ulong()
    kids = ctypes.POINTER(ctypes.c_ulong)(); n = ctypes.c_uint()
    if not x11.XQueryTree(dpy, win, ctypes.byref(r), ctypes.byref(p), ctypes.byref(kids), ctypes.byref(n)):
        return
    children = [kids[i] for i in range(n.value)] if kids else []
    if kids:
        x11.XFree(kids)
    for c in children:
        yield from walk(c, depth + 1)


def set_cp(win, dev, label):
    cur = ctypes.c_int(0)
    if xi.XIGetClientPointer(dpy, win, ctypes.byref(cur)) and cur.value == dev:
        return
    xi.XISetClientPointer(dpy, win, dev)
    x11.XFlush(dpy)
    assigned[win] = dev
    print(f"CP {win} -> {label}", flush=True)


while True:
    try:
        for win in walk(root):
            name = window_name(win)
            if not name or APP_HINT not in name:
                continue
            pid = window_pid(win)
            if not pid:
                continue
            home = home_of(pid)
            if not home:
                continue
            target = second_ptr if home == SECOND_HOME else core_ptr
            label = "second pointer" if target == second_ptr else "Virtual core pointer"
            set_cp(win, target, label)
        time.sleep(INTERVAL)
    except Exception as e:  # демон не должен падать
        log(f"ошибка: {e!r}")
        time.sleep(1.0)
