import ctypes, sys
x11=ctypes.CDLL("libX11.so.6"); xi=ctypes.CDLL("libXi.so.6")
x11.XOpenDisplay.restype=ctypes.c_void_p; x11.XOpenDisplay.argtypes=[ctypes.c_char_p]
x11.XFlush.argtypes=[ctypes.c_void_p]
xi.XIQueryVersion.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
xi.XISetFocus.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_ulong,ctypes.c_ulong]
xi.XIGetFocus.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_ulong)]
d=x11.XOpenDisplay(None)
ma,mi=ctypes.c_int(2),ctypes.c_int(0); xi.XIQueryVersion(d,ctypes.byref(ma),ctypes.byref(mi))
dev=int(sys.argv[1]); win=int(sys.argv[2])
xi.XISetFocus(d,dev,win,0); x11.XFlush(d)
w=ctypes.c_ulong(); xi.XIGetFocus(d,dev,ctypes.byref(w)); print(f"XISetFocus dev={dev} -> {win}; now XIGetFocus={w.value}")
