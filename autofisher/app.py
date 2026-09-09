import ctypes
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

import numpy as np
import soundcard as sc
from scipy.io import wavfile

from autofisher import __version__, theme
from autofisher.actions import BackgroundGamepadAction, ForegroundMouseAction
from autofisher.audio import normalized_similarity, to_mono_float32
from autofisher.config import (
    enable_background_gamepad_config,
    find_terraria_config,
    find_vigem_installer,
)
from autofisher.constants import (
    ACTION_MODE_GAMEPAD,
    ACTION_MODE_MOUSE,
    CAST_DELAY_SECONDS,
    MIN_AUDIO_RMS,
    START_DELAY_SECONDS,
)
from autofisher.paths import resource_root
from autofisher.ui import create_widgets, open_settings


class FishingBot:
    def __init__(self):
        self.root = tk.Tk()
        theme.init(self.root)
        self.root.title(f"Terraria 钓鱼助手 v{__version__}")
        self.root.geometry("420x450")
        self.root.minsize(420, 450)
        self.root.resizable(False, False)
        self.root.configure(bg=theme.BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.root.iconphoto(True, theme.asset("icon"))
        except tk.TclError:
            pass

        self.is_running = False
        self.is_closing = False
        self.similarity_threshold = 0.7
        self.cooldown_time = 2.0
        self.fish_count = 0
        self.last_action_time = 0.0
        self.stop_event = threading.Event()
        self.action_lock = threading.Lock()
        self.worker_thread = None
        self.action_backend = None
        self.action_mode = ACTION_MODE_GAMEPAD
        self.ui_events = queue.SimpleQueue()
        self.status_timer = None
        self.template_audio = None
        self.template_samplerate = None

        template_path = resource_root() / "assets" / "splash_template.wav"
        self.load_template(str(template_path))
        self.create_widgets()
        self.root.after(50, self.process_ui_events)

    def load_template(self, template_path):
        try:
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"找不到音频文件: {template_path}")

            self.template_samplerate, template_data = wavfile.read(template_path)
            template_data = to_mono_float32(template_data)
            if template_data.size == 0:
                raise ValueError("音频模板为空")

            peak = float(np.max(np.abs(template_data)))
            if peak <= 0:
                raise ValueError("音频模板没有有效声音")

            self.template_audio = template_data / peak
        except Exception as exc:
            print(f"加载音频失败: {exc}")
            self.template_audio = None

    def create_widgets(self):
        create_widgets(self)

    def open_settings(self):
        open_settings(self)

    def on_threshold_changed(self, value):
        self.similarity_threshold = float(value)

    def on_cooldown_changed(self, value):
        self.cooldown_time = float(value)

    def enable_background_input(self):
        config_path = find_terraria_config()
        if config_path is None:
            messagebox.showerror("无法设置", "找不到原版 Terraria 的 config.json")
            return
        if not messagebox.askyesno(
            "启用后台输入",
            "仅用于多人模式。请先完全退出 Terraria。\n\n确认游戏已退出并修改原版配置吗？",
        ):
            return
        try:
            changed = enable_background_gamepad_config(config_path)
        except Exception as exc:
            messagebox.showerror("设置失败", str(exc))
            return

        if changed:
            self.set_status("后台输入已启用，请重启游戏", theme.LIME)
            messagebox.showinfo(
                "设置完成", "多人模式后台手柄输入已启用，现在可以启动 Terraria。"
            )
        else:
            self.set_status("后台输入已启用", theme.LIME)

    def install_vigem_driver(self):
        installer_path = find_vigem_installer()
        if installer_path is None:
            messagebox.showerror(
                "找不到安装包", "未找到 ViGEmBus 安装包，请先执行 uv sync。"
            )
            return
        if not messagebox.askyesno(
            "安装虚拟手柄驱动",
            "将打开 ViGEmBus 驱动安装程序。\n"
            "如果 Windows 提示权限确认，请选择“是”。是否继续？",
        ):
            return

        parameters = f'/i "{installer_path}"'
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "msiexec.exe", parameters, None, 1
        )
        if result <= 32:
            messagebox.showerror("启动失败", f"无法打开驱动安装程序，错误码：{result}")
            return
        self.set_status("请按提示完成驱动安装", theme.MANA)

    def get_loopback(self):
        try:
            speaker = sc.default_speaker()
            microphones = sc.all_microphones(include_loopback=True)
            speaker_name = speaker.name.casefold()

            exact_match = [mic for mic in microphones if mic.name.casefold() == speaker_name]
            if exact_match:
                return exact_match[0]

            partial_match = [
                mic
                for mic in microphones
                if speaker_name in mic.name.casefold() or mic.name.casefold() in speaker_name
            ]
            if partial_match:
                return partial_match[0]

            loopback_match = [mic for mic in microphones if "loopback" in mic.name.casefold()]
            return loopback_match[0] if loopback_match else None
        except Exception as exc:
            print(f"查找回环音频设备失败: {exc}")
            return None

    def action_if_running(self):
        # Synchronize with Stop so an action cannot begin after the user stops.
        with self.action_lock:
            if self.stop_event.is_set():
                return False
            self.action_backend.perform()
            return True

    def queue_ui_event(self, event_type, *payload):
        self.ui_events.put((event_type, payload))

    def process_ui_events(self):
        if self.is_closing:
            return

        while True:
            try:
                event_type, payload = self.ui_events.get_nowait()
            except queue.Empty:
                break

            if event_type == "similarity":
                self.update_display(payload[0])
            elif event_type == "catch":
                self.on_catch(payload[0], payload[1])
            elif event_type == "status":
                self.set_status(payload[0], payload[1])
            elif event_type == "stopped":
                self.finish_stopping(payload[0])

        self.root.after(50, self.process_ui_events)

    def fishing_thread(self):
        error_message = None
        try:
            if self.template_audio is None:
                raise RuntimeError("缺少或无法读取 assets/splash_template.wav")

            microphone = self.get_loopback()
            if microphone is None:
                raise RuntimeError("未找到系统输出的回环音频设备")

            if self.action_mode == ACTION_MODE_GAMEPAD:
                self.action_backend = BackgroundGamepadAction()
                countdown_text = "{} 秒后抛竿"
            else:
                self.action_backend = ForegroundMouseAction()
                countdown_text = "请切回游戏 · {} 秒后抛竿"

            for seconds in range(round(START_DELAY_SECONDS), 0, -1):
                self.queue_ui_event("status", countdown_text.format(seconds), theme.MANA)
                if self.stop_event.wait(1.0):
                    return
            if not self.action_if_running():
                return
            self.last_action_time = time.monotonic()

            template_size = len(self.template_audio)
            chunk_size = max(1024, template_size // 2)
            history = np.empty(0, dtype=np.float32)

            with microphone.recorder(samplerate=self.template_samplerate) as recorder:
                self.queue_ui_event("status", "等待咬钩…", theme.MANA)
                while not self.stop_event.is_set():
                    block = to_mono_float32(recorder.record(numframes=chunk_size))
                    if self.stop_event.is_set():
                        break

                    analysis_block = np.concatenate((history, block))
                    history = analysis_block[-(template_size - 1) :].copy()

                    if time.monotonic() - self.last_action_time < self.cooldown_time:
                        continue

                    rms = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
                    similarity = (
                        normalized_similarity(analysis_block, self.template_audio)
                        if rms >= MIN_AUDIO_RMS
                        else 0.0
                    )
                    self.queue_ui_event("similarity", similarity)

                    if similarity >= self.similarity_threshold and not self.stop_event.is_set():
                        if not self.action_if_running():
                            break
                        self.fish_count += 1
                        self.queue_ui_event("catch", similarity, self.fish_count)
                        if self.stop_event.wait(CAST_DELAY_SECONDS):
                            break
                        if not self.action_if_running():
                            break
                        self.last_action_time = time.monotonic()
                        history = np.empty(0, dtype=np.float32)
                        recorder.flush()
        except Exception as exc:
            error_message = str(exc)
            print(f"钓鱼线程异常: {exc}")
        finally:
            with self.action_lock:
                if self.action_backend is not None:
                    try:
                        self.action_backend.close()
                    except Exception as exc:
                        print(f"释放输入设备失败: {exc}")
                    self.action_backend = None
            self.queue_ui_event("stopped", error_message)

    def update_display(self, similarity):
        threshold = max(self.similarity_threshold, 0.01)
        progress = min(100.0, max(0.0, similarity / threshold * 100.0))
        self.match_bar.set(progress, hot=similarity >= threshold)

    def set_status(self, text, color):
        if self.status_timer is not None:
            self.root.after_cancel(self.status_timer)
            self.status_timer = None
        self.status_text.config(text=text, fill=color)

    def on_catch(self, similarity, count):
        self.set_status("上钩了！", theme.LIME)
        self.fish_slot.set_count(count)
        self.status_timer = self.root.after(800, self.restore_normal_status)

    def restore_normal_status(self):
        self.status_timer = None
        if self.is_running:
            self.set_status("等待咬钩…", theme.MANA)
        else:
            self.set_status("准备好后开始钓鱼", theme.ORANGE)

    def toggle_start(self):
        if self.is_running:
            self.is_running = False
            self.stop_event.set()
            # Wait for a click already in progress (normally under 0.1 seconds).
            with self.action_lock:
                pass
            self.start_btn.set_text("正在停止…")
            self.start_btn.set_variant("stone")
            self.start_btn.set_state("disabled")
            self.set_status("正在停止...", theme.ORANGE)
            return

        if self.worker_thread is not None and self.worker_thread.is_alive():
            return

        self.similarity_threshold = float(self.threshold_var.get())
        self.cooldown_time = float(self.cooldown_var.get())
        self.action_mode = self.action_mode_var.get()
        self.stop_event.clear()
        self.is_running = True
        self.start_btn.set_text("停止钓鱼")
        self.start_btn.set_variant("crimson")
        self.start_btn.set_state("normal")
        self.set_status("正在连接音频设备...", theme.MANA)
        self.worker_thread = threading.Thread(target=self.fishing_thread, daemon=True)
        self.worker_thread.start()

    def finish_stopping(self, error_message):
        self.is_running = False
        self.worker_thread = None
        self.start_btn.set_text("开始钓鱼")
        self.start_btn.set_variant("wood")
        self.start_btn.set_state("normal")
        if error_message:
            self.set_status("无法开始钓鱼，请查看错误提示", theme.HEALTH)
            if not self.is_closing:
                messagebox.showerror("钓鱼已停止", error_message)
        elif not self.is_closing:
            self.set_status("已停止", theme.ORANGE)

    def reset(self):
        self.fish_count = 0
        self.fish_slot.set_count(0)
        self.match_bar.set(0, hot=False)
        self.set_status("已重置", theme.LIME)
        self.status_timer = self.root.after(1200, self.restore_normal_status)

    def close(self):
        self.is_closing = True
        self.stop_event.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    FishingBot().run()
