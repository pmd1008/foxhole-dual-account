#!/usr/bin/env python3
"""
seat2-focuspin — держит XI-фокус второй клавиатуры на ОКНЕ WINE (WM_STATE),
а не на фрейме KWin.

Почему так: под KWin окно игры — потомок фрейма. Старый seat2-focusd ставил фокус
на «верхнее окно с parent == root», т.е. на фрейм: клавиши уходили туда, Wine не
находил для фрейма hwnd и игнорировал ввод. Здесь цель ищется по WM_STATE.

Что делает:
  * при нажатии кнопки на втором указателе ставит XISetFocus(second keyboard, client);
  * если XI-фокус уехал на фрейм/root — возвращает его на запомненный client;
  * НИКОГДА не трогает core-фокус (это делает KWin/focusd-политика) и не делаег grabs.

Запуск: python3 seat2-focuspin.py [--verbose]
"""
import ctypes, os, re, subprocess, sys, time

VERBOSE = "--verbose" in sys.argv
LOG = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp",
                   f"seat2-focuspin-{os.getuid()}.log")

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
x11.XInternAtom.restype = ctypes.c_ulong
x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
x11.XGetWindowProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long,
                                   ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                   ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
                                   ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
xi.XIQueryVersion.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
xi.XIQueryPointer.restype = ctypes.c_int
xi.XIGetFocus.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ulong)]
xi.XISetFocus.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong]
x11.XFlush.argtypes = [ctypes.c_void_p]


class XIButtonState(ctypes.Structure):
    _fields_ = [("mask_len", ctypes.c_int), ("mask", ctypes.POINTER(ctypes.c_ubyte))]


class XIModifierState(ctypes.Structure):
    _fields_ = [("base", ctypes.c_int), ("latched", ctypes.c_int),
                ("locked", ctypes.c_int), ("effective", ctypes.c_int)]


class XIGroupState(ctypes.Structure):
    _fields_ = [("base", ctypes.c_int), ("latched", ctypes.c_int),
                ("locked", ctypes.c_int), ("effective", ctypes.c_int)]


class XFocusChangeEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("pad", ctypes.c_int), ("serial", ctypes.c_ulong),
                ("send_event", ctypes.c_int), ("pad2", ctypes.c_int), ("display", ctypes.c_void_p),
                ("window", ctypes.c_ulong), ("mode", ctypes.c_int), ("detail", ctypes.c_int)]


xi.XIQueryPointer.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(XIButtonState), ctypes.POINTER(XIModifierState), ctypes.POINTER(XIGroupState)]


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        print(line, file=sys.stderr, flush=True)
    if VERBOSE:
        print(line, flush=True)


def dev_rows():
    out = subprocess.run(["xinput", "list", "--short"], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        m = re.search(r"id=(\d+)\s*\[([^\]]+)\]\s*$", line)
        if not m:
            continue
        name = re.sub(r"^[^\w]+", "", line[:m.start()])
        name = re.sub(r"\s+", " ", name).strip()
        rows.append((int(m.group(1)), m.group(2), name))
    return rows


def master_id(name, cls):
    for i, c, n in dev_rows():
        if n == name and cls in c:
            return i
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
    sys.exit(1)
root = x11.XDefaultRootWindow(dpy)
ma, mi = ctypes.c_int(2), ctypes.c_int(0)
xi.XIQueryVersion(dpy, ctypes.byref(ma), ctypes.byref(mi))
WM_STATE = x11.XInternAtom(dpy, b"WM_STATE", 0)

kbd = master_id("second keyboard", "master keyboard")
ptr = master_id("second pointer", "master pointer")
if not kbd or not ptr:
    log("нет мастер-пары second (нужен Xorg); выходим")
    sys.exit(1)
log(f"старт: pointer={ptr} keyboard={kbd}")


def has_wm_state(win):
    t = ctypes.c_ulong(); f = ctypes.c_int(); cnt = ctypes.c_ulong()
    rem = ctypes.c_ulong(); data = ctypes.POINTER(ctypes.c_ubyte)()
    x11.XGetWindowProperty(dpy, win, WM_STATE, 0, 2, 0, 0, ctypes.byref(t),
                           ctypes.byref(f), ctypes.byref(cnt), ctypes.byref(rem), ctypes.byref(data))
    if data:
        x11.XFree(data)
    return t.value == WM_STATE


def parent_of(win):
    r = ctypes.c_ulong(); p = ctypes.c_ulong()
    kids = ctypes.POINTER(ctypes.c_ulong)(); n = ctypes.c_uint()
    if not x11.XQueryTree(dpy, win, ctypes.byref(r), ctypes.byref(p), ctypes.byref(kids), ctypes.byref(n)):
        return 0
    if kids:
        x11.XFree(kids)
    return p.value


def client_window(win):
    """Ближайший вверх по дереву, у которого есть WM_STATE (окно Wine), иначе None."""
    cur = win
    for _ in range(32):
        if not cur or cur == root:
            return None
        if has_wm_state(cur):
            return cur
        cur = parent_of(cur)
    return None


def pointer_state(dev):
    r = ctypes.c_ulong(); c = ctypes.c_ulong()
    rx, ry, wx, wy = (ctypes.c_double() for _ in range(4))
    bs, ms, gs = XIButtonState(), XIModifierState(), XIGroupState()
    ok = xi.XIQueryPointer(dpy, dev, root, ctypes.byref(r), ctypes.byref(c),
                           ctypes.byref(rx), ctypes.byref(ry), ctypes.byref(wx), ctypes.byref(wy),
                           ctypes.byref(bs), ctypes.byref(ms), ctypes.byref(gs))
    pressed = bool(bs.mask and bs.mask_len > 0 and any(bs.mask[i] for i in range(bs.mask_len)))
    if bs.mask:
        x11.XFree(bs.mask)
    return (ok, c.value, pressed)


def xi_focus(dev):
    w = ctypes.c_ulong()
    xi.XIGetFocus(dpy, dev, ctypes.byref(w))
    return w.value


def send_focus_in(win):
    ev = XFocusChangeEvent()
    ev.type = 9  # FocusIn
    ev.send_event = 1
    ev.display = dpy
    ev.window = win
    ev.mode = 0  # NotifyNormal
    ev.detail = 3  # NotifyNonlinear
    x11.XSendEvent(dpy, win, 1, 1 << 21, ctypes.byref(ev))
    x11.XFlush(dpy)


def pin(win, why):
    if xi_focus(kbd) != win:
        xi.XISetFocus(dpy, kbd, win, 0)
        x11.XFlush(dpy)
        log(f"{why}: XISetFocus({kbd}) -> {win} (было {xi_focus(kbd)})")
    send_focus_in(win)


prev = False
pinned = None
while True:
    try:
        ok, child, pressed = pointer_state(ptr)
        if pressed and not prev:
            win = client_window(child)
            if win:
                pinned = win
                pin(win, "клик")
            else:
                pinned = None  # клик мимо окна игры — не навязываем фокус
        prev = pressed
        # Держим фокус на последнем выбранном окне твинка и чиним увод на фрейм.
        cur = xi_focus(kbd)
        if not cur or cur == 0:
            # фокуса нет (перезапуск игры / KWin сбросил) — берём окно под курсором
            _ok, child, _pressed = pointer_state(ptr)
            win = client_window(child)
            if win:
                pinned = win
                pin(win, "фокуса не было")
        elif pinned and cur != pinned:
            cur_client = client_window(cur) if cur else None
            if cur_client == pinned:
                pin(pinned, "фокус на фрейме")
            else:
                pin(pinned, "фокус увели")
        elif cur and cur != 0:
            win = client_window(cur)
            if win and win != cur:
                pin(win, "фокус на фрейме")
        time.sleep(0.05)
    except Exception as e:  # daemon must survive
        log(f"ошибка: {e!r}")
        time.sleep(0.5)
