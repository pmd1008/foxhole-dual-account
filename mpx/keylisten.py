import ctypes, time, select
x11=ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.restype=ctypes.c_void_p; x11.XOpenDisplay.argtypes=[ctypes.c_char_p]
x11.XSelectInput.argtypes=[ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]
x11.XNextEvent.argtypes=[ctypes.c_void_p, ctypes.c_void_p]
x11.XPending.argtypes=[ctypes.c_void_p]
x11.XConnectionNumber.restype=ctypes.c_int; x11.XConnectionNumber.argtypes=[ctypes.c_void_p]
x11.XFlush.argtypes=[ctypes.c_void_p]
class XKey(ctypes.Structure):
    _fields_=[("type",ctypes.c_int),("pad",ctypes.c_int),("serial",ctypes.c_ulong),("send_event",ctypes.c_int),("pad2",ctypes.c_int),
              ("display",ctypes.c_void_p),("window",ctypes.c_ulong),("root",ctypes.c_ulong),("subwindow",ctypes.c_ulong),
              ("time",ctypes.c_ulong),("x",ctypes.c_int),("y",ctypes.c_int),("x_root",ctypes.c_int),("y_root",ctypes.c_int),
              ("state",ctypes.c_uint),("keycode",ctypes.c_uint),("same_screen",ctypes.c_int)]
d=x11.XOpenDisplay(None)
wins={224395265:"wine", 0xd40003d:"wine-child", 42120170:"frame"}
for w in wins: x11.XSelectInput(d,w,1|2)  # KeyPressMask|KeyReleaseMask
x11.XFlush(d); fd=x11.XConnectionNumber(d)
buf=ctypes.create_string_buffer(192); t0=time.time()
while time.time()-t0<120:
    r,_,_=select.select([fd],[],[],0.2)
    while x11.XPending(d):
        x11.XNextEvent(d,buf); e=ctypes.cast(buf,ctypes.POINTER(XKey)).contents
        if e.type in (2,3):
            print(f"{time.strftime('%H:%M:%S')} {'KeyPress' if e.type==2 else 'KeyRelease'} win={e.window} ({wins.get(e.window,'?')}) keycode={e.keycode} send={e.send_event}",flush=True)
