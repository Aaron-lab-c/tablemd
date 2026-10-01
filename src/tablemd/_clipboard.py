"""Tiny dependency-free clipboard access for the CLI (macOS / Windows / Linux / WSL)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import List, Optional, Sequence

from ._table import TablemdError

__all__ = ["read_clipboard", "write_clipboard"]

_HINT = (
    "no clipboard tool found. Install one of: xclip, xsel (X11) or wl-clipboard "
    "(Wayland); on macOS/Windows the built-in tools are used automatically."
)


# --------------------------------------------------------------------------- #
# Subprocess-based backends (macOS, Linux, WSL)
# --------------------------------------------------------------------------- #

def _run(cmd: Sequence[str], data: Optional[str] = None) -> str:
    # When *copying*, xclip/wl-copy fork a daemon that keeps the clipboard
    # alive and inherits our pipes; capturing its stdout would block forever.
    capture = subprocess.PIPE if data is None else subprocess.DEVNULL
    try:
        proc = subprocess.run(
            list(cmd),
            input=data.encode("utf-8") if data is not None else None,
            stdout=capture,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TablemdError(f"clipboard command failed: {' '.join(cmd)} ({exc})") from exc
    return proc.stdout.decode("utf-8", errors="replace") if data is None else ""


def _is_wsl() -> bool:
    try:
        with open("/proc/version", "r", encoding="utf-8") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def _paste_commands() -> List[List[str]]:
    if sys.platform == "darwin":
        return [["pbpaste"]]
    cmds: List[List[str]] = []
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        cmds.append(["wl-paste", "--no-newline"])
    if shutil.which("xclip"):
        cmds.append(["xclip", "-selection", "clipboard", "-o"])
    if shutil.which("xsel"):
        cmds.append(["xsel", "--clipboard", "--output"])
    if _is_wsl() and shutil.which("powershell.exe"):
        cmds.append(["powershell.exe", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw"])
    return cmds


def _copy_commands() -> List[List[str]]:
    if sys.platform == "darwin":
        return [["pbcopy"]]
    cmds: List[List[str]] = []
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        cmds.append(["wl-copy"])
    if shutil.which("xclip"):
        cmds.append(["xclip", "-selection", "clipboard"])
    if shutil.which("xsel"):
        cmds.append(["xsel", "--clipboard", "--input"])
    if _is_wsl() and shutil.which("clip.exe"):
        cmds.append(["clip.exe"])
    return cmds


# --------------------------------------------------------------------------- #
# Native Windows backend (ctypes, Unicode-safe)
# --------------------------------------------------------------------------- #

_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002


def _win_api():  # pragma: no cover - Windows only
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    return ctypes, user32, kernel32


def _win_read() -> str:  # pragma: no cover - Windows only
    ctypes, user32, kernel32 = _win_api()
    if not user32.OpenClipboard(None):
        raise TablemdError("could not open the Windows clipboard")
    try:
        handle = user32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _win_write(text: str) -> None:  # pragma: no cover - Windows only
    ctypes, user32, kernel32 = _win_api()
    data = text.encode("utf-16-le") + b"\x00\x00"
    handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(data))
    if not handle:
        raise TablemdError("GlobalAlloc failed")
    ptr = kernel32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not user32.OpenClipboard(None):
        raise TablemdError("could not open the Windows clipboard")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(_CF_UNICODETEXT, handle):
            raise TablemdError("SetClipboardData failed")
    finally:
        user32.CloseClipboard()


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def read_clipboard() -> str:
    """Return the clipboard's text content."""
    if sys.platform.startswith("win"):
        return _win_read().replace("\r\n", "\n")
    cmds = _paste_commands()
    if not cmds:
        raise TablemdError(_HINT)
    last: Optional[TablemdError] = None
    for cmd in cmds:
        try:
            text = _run(cmd)
        except TablemdError as exc:
            last = exc
            continue
        if cmd[0] == "powershell.exe":
            text = text.replace("\r\n", "\n")
        return text
    assert last is not None
    raise last


def write_clipboard(text: str) -> None:
    """Replace the clipboard content with *text*."""
    if sys.platform.startswith("win"):
        _win_write(text.replace("\n", "\r\n"))
        return
    cmds = _copy_commands()
    if not cmds:
        raise TablemdError(_HINT)
    last: Optional[TablemdError] = None
    for cmd in cmds:
        try:
            _run(cmd, data=text)
            return
        except TablemdError as exc:
            last = exc
    assert last is not None
    raise last
