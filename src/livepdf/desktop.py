"""Start a program on a separate, invisible Windows desktop, so a "headful" browser never shows up on the
user's screen or takes the keyboard focus.

    python -m livepdf.desktop <exe> [args...]     prints the new process id, then waits until it exits

The launcher keeps the desktop open while the program runs (a desktop disappears when its last handle closes).
Windows only.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes

DESKTOP_NAME = 'livepdf'
GENERIC_ALL = 0x10000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('lpReserved', wintypes.LPWSTR), ('lpDesktop', wintypes.LPWSTR),
                ('lpTitle', wintypes.LPWSTR), ('dwX', wintypes.DWORD), ('dwY', wintypes.DWORD),
                ('dwXSize', wintypes.DWORD), ('dwYSize', wintypes.DWORD), ('dwXCountChars', wintypes.DWORD),
                ('dwYCountChars', wintypes.DWORD), ('dwFillAttribute', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('wShowWindow', wintypes.WORD), ('cbReserved2', wintypes.WORD), ('lpReserved2', ctypes.c_void_p),
                ('hStdInput', wintypes.HANDLE), ('hStdOutput', wintypes.HANDLE), ('hStdError', wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [('hProcess', wintypes.HANDLE), ('hThread', wintypes.HANDLE), ('dwProcessId', wintypes.DWORD),
                ('dwThreadId', wintypes.DWORD)]


def launch_hidden(argv: list[str], desktop: str = DESKTOP_NAME, wait: bool = False) -> int:
    """Start ``argv`` on the invisible desktop ``desktop`` (created if needed). Returns the process id; with
    ``wait`` prints it first and returns only when the program has exited."""
    user32, kernel32 = ctypes.WinDLL('user32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True)
    user32.CreateDesktopW.restype = wintypes.HANDLE
    h = user32.CreateDesktopW(desktop, None, None, 0, GENERIC_ALL, None)
    if not h:
        raise OSError(ctypes.get_last_error(), 'CreateDesktopW failed')
    si = STARTUPINFOW(cb=ctypes.sizeof(STARTUPINFOW), lpDesktop=desktop)
    pi = PROCESS_INFORMATION()
    cmd = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
    if not kernel32.CreateProcessW(None, cmd, None, None, False, CREATE_NEW_PROCESS_GROUP, None, None,
                                   ctypes.byref(si), ctypes.byref(pi)):
        raise OSError(ctypes.get_last_error(), 'CreateProcessW failed')
    kernel32.CloseHandle(pi.hThread)
    if wait:
        print(pi.dwProcessId, flush=True)
        kernel32.WaitForSingleObject(pi.hProcess, 0xFFFFFFFF)
    kernel32.CloseHandle(pi.hProcess)
    return pi.dwProcessId


if __name__ == '__main__':
    launch_hidden(sys.argv[1:], wait=True)
