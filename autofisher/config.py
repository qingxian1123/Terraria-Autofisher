import ctypes
import json
import os
import shutil
from ctypes import wintypes
from pathlib import Path


TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)


class ProcessEntry32W(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("usage", wintypes.DWORD),
        ("process_id", wintypes.DWORD),
        ("default_heap_id", ctypes.c_size_t),
        ("module_id", wintypes.DWORD),
        ("threads", wintypes.DWORD),
        ("parent_process_id", wintypes.DWORD),
        ("base_priority", wintypes.LONG),
        ("flags", wintypes.DWORD),
        ("exe_file", wintypes.WCHAR * 260),
    ]


KERNEL32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
KERNEL32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
KERNEL32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
KERNEL32.Process32FirstW.restype = wintypes.BOOL
KERNEL32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
KERNEL32.Process32NextW.restype = wintypes.BOOL
KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL32.CloseHandle.restype = wintypes.BOOL


def find_process_id(executable_name):
    """Find a process by executable name without requiring extra packages."""
    snapshot = KERNEL32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return None
    try:
        entry = ProcessEntry32W()
        entry.size = ctypes.sizeof(entry)
        if not KERNEL32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return None
        expected = executable_name.casefold()
        while True:
            if entry.exe_file.casefold() == expected:
                return int(entry.process_id)
            if not KERNEL32.Process32NextW(snapshot, ctypes.byref(entry)):
                return None
    finally:
        KERNEL32.CloseHandle(snapshot)


def find_terraria_config():
    """Return the first standard vanilla Terraria config path that exists."""
    user_profile = Path(os.environ.get("USERPROFILE", Path.home()))
    candidates = [
        user_profile / "Documents" / "My Games" / "Terraria" / "config.json",
        user_profile / "OneDrive" / "Documents" / "My Games" / "Terraria" / "config.json",
    ]
    return next((path for path in candidates if path.is_file()), None)


def background_gamepad_config_state(config_path=None):
    """Return True/False for Terraria's setting, or None when it cannot be read."""
    path = Path(config_path) if config_path else find_terraria_config()
    if path is None:
        return None
    try:
        with path.open("r", encoding="utf-8-sig") as config_file:
            config = json.load(config_file)
        return config.get("AllowUnfocusedInputOnGamepad") is True
    except (OSError, ValueError, TypeError):
        return None


def enable_background_gamepad_config(config_path):
    """Enable vanilla background gamepad input and keep one recovery backup."""
    path = Path(config_path)
    with path.open("r", encoding="utf-8-sig") as config_file:
        config = json.load(config_file)
    setting = "AllowUnfocusedInputOnGamepad"
    if config.get(setting) is True:
        return False
    if setting not in config:
        raise ValueError(f"配置中缺少 {setting}")

    backup_path = path.with_name(f"{path.name}.autofisher.bak")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)

    config["AllowUnfocusedInputOnGamepad"] = True
    temporary_path = path.with_name(f"{path.name}.autofisher.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as config_file:
            json.dump(config, config_file, ensure_ascii=False, indent=2)
            config_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return True


def find_vigem_installer():
    """Locate the ViGEmBus installer bundled with the vgamepad package."""
    try:
        import vgamepad
    except ImportError:
        return None

    architecture = "x64" if ctypes.sizeof(ctypes.c_void_p) == 8 else "x86"
    installer = (
        Path(vgamepad.__file__).resolve().parent
        / "win"
        / "vigem"
        / "install"
        / architecture
        / f"ViGEmBusSetup_{architecture}.msi"
    )
    return installer if installer.is_file() else None
