"""Reserve a new report without following an existing final-path symlink."""
import os
from pathlib import Path


def reserve_new_report(path):
    path = Path(path)
    if os.name != 'nt':
        return path.open('x')
    # Windows CRT exclusive open may follow a dangling symlink and create its
    # target. CREATE_NEW + OPEN_REPARSE_POINT rejects the existing link itself.
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    handle = create(str(path.absolute()), 0x40000000, 1, None, 1, 0x00200000 | 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY | os.O_NOINHERIT)
    except BaseException:
        close(handle)
        raise
    try:
        return os.fdopen(fd, 'w', encoding='utf-8')
    except BaseException:
        os.close(fd)
        raise
