import ctypes, time
x11=ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.restype=ctypes.c_void_p; x11.XOpenDisplay.argtypes=[ctypes.c_char_p]
x11.XSelectInput.argtypes=[ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]
x11.XNextEvent.argtypes=[ctypes.c_void_p, ctypes.c_void_p]
x11.XPending.argtypes=[ctypes.c_void_p]
class XFocus(ctypes.Structure):
    _fields_=[("type",ctypes.c_int),("pad",ctypes.c_int),("serial",ctypes.c_ulong),("send_event",ctypes.c_int),
              ("pad2",ctypes.c_int),("display",ctypes.c_void_p),("window",ctypes.c_ulong),("mode",ctypes.c_int),("detail",ctypes.c_int)]
d=x11.XOpenDisplay(None)
wins={224395265:"twink-frame", 42120170:"twink-client", 287309825:"main-frame"}
for w in wins:
    x11.XSelectInput(d, w, 1<<21)  # FocusChangeMask
buf=ctypes.create_string_buffer(192)
end=time.time()+1800
while time.time()<end:
    while x11.XPending(d):
        x11.XNextEvent(d, buf)
        e=ctypes.cast(buf, ctypes.POINTER(XFocus)).contents
        if e.type in (9,10):
            print(f"{time.strftime('%H:%M:%S')} {'FocusIn' if e.type==9 else 'FocusOut'} win={e.window} ({wins.get(e.window,'?')}) send={e.send_event} mode={e.mode} detail={e.detail}", flush=True)
    time.sleep(0.01)
