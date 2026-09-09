import ctypes
import os
import shutil
import subprocess
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from autofisher.config import background_gamepad_config_state, find_process_id
from autofisher.constants import (
    GAMEPAD_PRESS_SECONDS,
    GAMEPAD_REFRESH_SECONDS,
    PATCH_PROTOCOL_VERSION,
    PATCH_PULSE_MARGIN_SECONDS,
    PIPE_CONNECT_TIMEOUT_SECONDS,
)
from autofisher.paths import resource_root


INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

USER32 = ctypes.WinDLL("user32", use_last_error=True)


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouse_data", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("extra_info", wintypes.WPARAM),
    ]


class InputUnion(ctypes.Union):
    _fields_ = [("mouse", MouseInput)]


class Input(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", wintypes.DWORD), ("value", InputUnion)]


USER32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
USER32.SendInput.restype = wintypes.UINT


class ForegroundMouseAction:
    @staticmethod
    def _send(flags):
        event = Input()
        event.type = INPUT_MOUSE
        event.mouse = MouseInput(0, 0, 0, flags, 0, 0)
        ctypes.set_last_error(0)
        if USER32.SendInput(1, ctypes.byref(event), ctypes.sizeof(Input)) != 1:
            error_code = ctypes.get_last_error()
            if error_code == 5:
                raise RuntimeError("鼠标输入被拒绝；请让工具与 Terraria 使用相同权限运行")
            raise RuntimeError(f"鼠标输入失败，Windows 错误码: {error_code}")

    def perform(self):
        button_is_down = False
        try:
            self._send(MOUSEEVENTF_LEFTDOWN)
            button_is_down = True
            time.sleep(0.05)
        finally:
            if button_is_down:
                self._send(MOUSEEVENTF_LEFTUP)

    def close(self):
        pass


class BackgroundGamepadAction:
    def __init__(self):
        config_state = background_gamepad_config_state()
        if config_state is False:
            raise RuntimeError(
                "原版后台运行尚未开启：请退出 Terraria，打开“设置 → 启用后台输入”，再启动游戏"
            )
        if config_state is None:
            raise RuntimeError("找不到或无法读取原版 Terraria 的 config.json")

        try:
            import vgamepad as vg

            self.gamepad = vg.VX360Gamepad()
        except Exception as exc:
            raise RuntimeError(
                "无法创建虚拟 Xbox 手柄，请确认 vgamepad 和 ViGEmBus 已安装"
            ) from exc

        self.pipe_name = None
        self.injector_copy_dir = None
        self.patch_status_path = None
        try:
            self._attach_runtime_patch()
        except Exception:
            self._cleanup_injector_copy()
            self.gamepad.reset()
            self.gamepad.update()
            raise

    def _attach_runtime_patch(self):
        terraria_pid = find_process_id("Terraria.exe")
        if terraria_pid is None:
            raise RuntimeError("未找到 Terraria.exe，请先进入游戏")

        injector_source_dir = resource_root() / "injector" / "runtime-v2"
        injector_source = injector_source_dir / "TerrariaAutoFisher.Injector.exe"
        if not injector_source.is_file():
            raise RuntimeError("找不到后台补丁注入器，请先构建 injector 项目")

        self.pipe_name = f"TerrariaAutoFisher_Control_{terraria_pid}"
        try:
            existing_response = self._pipe_command("PING", timeout=0.35)
        except RuntimeError:
            existing_response = None
        if existing_response is not None:
            self._validate_ready_response(existing_response)
            return

        staging_root = Path(tempfile.gettempdir()) / "TerrariaAutoFisher"
        staging_root.mkdir(parents=True, exist_ok=True)
        for stale_dir in staging_root.iterdir():
            if stale_dir.is_dir():
                shutil.rmtree(stale_dir, ignore_errors=True)
        self.injector_copy_dir = Path(
            tempfile.mkdtemp(prefix=f"{terraria_pid}_", dir=staging_root)
        )
        shutil.copytree(
            injector_source_dir, self.injector_copy_dir, dirs_exist_ok=True
        )
        injector = self.injector_copy_dir / injector_source.name
        self.patch_status_path = self.injector_copy_dir / "startup.status"
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            [
                str(injector),
                "attach",
                str(terraria_pid),
                self.pipe_name,
                str(os.getpid()),
                str(self.patch_status_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=creation_flags,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            message = " | ".join(detail.splitlines()) if detail else (
                f"错误码 {result.returncode}"
            )
            startup_status = self._read_startup_status()
            if startup_status:
                message += f" | 游戏内状态：{startup_status}"
            raise RuntimeError(
                f"注入后台补丁失败：{message}。请让工具与 Terraria 使用相同权限运行"
            )
        try:
            response = self._pipe_command("PING")
        except RuntimeError as exception:
            startup_status = self._read_startup_status()
            if startup_status:
                raise RuntimeError(
                    f"游戏内补丁启动失败：{startup_status}"
                ) from exception
            raise
        finally:
            if self.patch_status_path:
                self.patch_status_path.unlink(missing_ok=True)
        self._validate_ready_response(response)

    @staticmethod
    def _validate_ready_response(response):
        if response.startswith("ERROR "):
            raise RuntimeError(f"游戏内补丁初始化失败：{response[6:]}")
        expected = f"READY {PATCH_PROTOCOL_VERSION}"
        if response != expected:
            if response.startswith("READY"):
                raise RuntimeError(
                    "Terraria 内运行的是其他版本的后台补丁；"
                    "请完整退出并重新启动 Terraria"
                )
            raise RuntimeError(f"后台补丁通信验证失败：{response or '无响应'}")

    def _pipe_command(self, command, timeout=PIPE_CONNECT_TIMEOUT_SECONDS):
        if not self.pipe_name:
            raise RuntimeError("后台补丁尚未连接")
        pipe_path = rf"\\.\pipe\{self.pipe_name}"
        deadline = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < deadline:
            try:
                with open(pipe_path, "r+b", buffering=0) as pipe:
                    pipe.write(f"{command}\n".encode("ascii"))
                    return pipe.readline().decode("ascii", errors="replace").strip()
            except OSError as exc:
                last_error = exc
                time.sleep(0.05)
        raise RuntimeError(f"无法连接游戏内后台补丁：{last_error}")

    def perform(self):
        pulse_milliseconds = round(
            (GAMEPAD_PRESS_SECONDS + PATCH_PULSE_MARGIN_SECONDS) * 1000
        )
        if self._pipe_command(f"PULSE {pulse_milliseconds}") != "PULSED":
            raise RuntimeError("游戏内补丁拒绝了钓鱼脉冲")
        self.gamepad.right_trigger(value=255)
        self.gamepad.update()
        try:
            # Vanilla throttles its update loop while unfocused. Keep the trigger
            # alive across several background ticks so GamePad.GetState cannot
            # miss a short pulse, and refresh the report for older XInput paths.
            deadline = time.monotonic() + GAMEPAD_PRESS_SECONDS
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(GAMEPAD_REFRESH_SECONDS, remaining))
                self.gamepad.update()
        finally:
            self.gamepad.right_trigger(value=0)
            self.gamepad.update()

    def close(self):
        if self.pipe_name:
            try:
                response = self._pipe_command("DISABLE", timeout=1.5)
                if response != "DISABLED":
                    print(f"停用游戏内补丁脉冲失败: {response}")
            except Exception as exc:
                print(f"停用游戏内补丁脉冲失败: {exc}")
            self.pipe_name = None
        self.gamepad.reset()
        self.gamepad.update()
        self._cleanup_injector_copy()

    def _read_startup_status(self):
        if not self.patch_status_path or not self.patch_status_path.is_file():
            return ""
        try:
            return " | ".join(
                self.patch_status_path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
            )
        except OSError:
            return ""

    def _cleanup_injector_copy(self):
        if self.injector_copy_dir:
            shutil.rmtree(self.injector_copy_dir, ignore_errors=True)
            self.injector_copy_dir = None
            self.patch_status_path = None
