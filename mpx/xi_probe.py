import ctypes, sys
x11 = ctypes.CDLL("libX11.so.6"); xi = ctypes.CDLL("libXi.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
xi.XIQueryVersion.argtypes=[ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
xi.XIGetClientPointer.argtypes=[ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_int)]
xi.XIGetFocus.argtypes=[ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ulong)]
d = x11.XOpenDisplay(None)
if not d: print("нет X"); sys.exit(1)
ma, mi = ctypes.c_int(2), ctypes.c_int(0)
xi.XIQueryVersion(d, ctypes.byref(ma), ctypes.byref(mi))
print("XI", ma.value, mi.value)
for win,name in ((226492417,"alt/Тайлер"),(289406977,"main/Мерзавец")):
    dev = ctypes.c_int(0)
    xi.XIGetClientPointer(d, ctypes.c_ulong(win), ctypes.byref(dev))
    print(f"ClientPointer окна {win} ({name}) = {dev.value}")
for kbd,name in ((3,"core kbd"),(22,"second kbd")):
    fw = ctypes.c_ulong(0)
    xi.XIGetFocus(d, kbd, ctypes.byref(fw))
    print(f"XI focus {name} ({kbd}) = {fw.value}")
