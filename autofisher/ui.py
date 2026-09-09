"""Window composition, separate from fishing and device lifecycle."""

import tkinter as tk

from autofisher import theme
from autofisher.constants import ACTION_MODE_GAMEPAD, ACTION_MODE_MOUSE
from autofisher.widgets import (
    PixelBar, PixelButton, PixelLabel, PixelPanel, PixelRadio, PixelScale, PixelSlot,
)


def create_widgets(bot):
    panel = PixelPanel(bot.root, title="TERRARIA · 钓鱼助手", grass=True)
    panel.pack(fill="both", expand=True, padx=10, pady=10)
    body = panel.body

    inventory = tk.Frame(body, bg=theme.WOOD)
    inventory.pack(fill="x", padx=6, pady=(8, 6))
    for column, (sprite, label) in enumerate((("bait", "大师鱼饵"), ("rod", "金钓竿"), ("tackle", "收竿次数"))):
        inventory.columnconfigure(column, weight=1, uniform="slot")
        slot = PixelSlot(inventory, sprite, count=0 if sprite == "tackle" else None)
        slot.grid(row=0, column=column)
        PixelLabel(inventory, text=label, font_name="small", anchor="center").grid(
            row=1, column=column, sticky="ew", pady=(3, 0))
        if sprite == "tackle":
            bot.fish_slot = slot

    bot.status_text = PixelLabel(
        body, text="准备好后开始钓鱼", fill=theme.TEXT_MOUSE,
        height=32, background=theme.TOOLTIP)
    bot.status_text.pack(fill="x", padx=6, pady=(0, 6))
    meter = tk.Frame(body, bg=theme.WOOD)
    meter.pack(fill="x", padx=6, pady=(0, 6))
    signal_label = PixelLabel(meter, text="咬钩信号", font_name="small")
    signal_label.configure(width=76)
    signal_label.pack(side="left")
    bot.match_bar = PixelBar(meter)
    bot.match_bar.configure(width=130)
    bot.match_bar.pack(side="right", fill="x", expand=True)

    bot.threshold_var = tk.DoubleVar(value=bot.similarity_threshold)
    bot.cooldown_var = tk.DoubleVar(value=bot.cooldown_time)
    settings = tk.Frame(body, bg=theme.WOOD)
    settings.pack(fill="x", padx=6)
    settings.columnconfigure(1, weight=1)
    for row, (label, variable, lower, upper, step, callback, formatter) in enumerate((
        ("识别阈值", bot.threshold_var, 0.5, 0.95, 0.01, bot.on_threshold_changed, lambda v: f"{v:.0%}"),
        ("抛竿间隔", bot.cooldown_var, 1.0, 5.0, 0.1, bot.on_cooldown_changed, lambda v: f"{v:.1f}s"),
    )):
        caption = PixelLabel(settings, text=label)
        caption.configure(width=76)
        caption.grid(row=row, column=0, sticky="ew")
        PixelScale(settings, from_=lower, to=upper, resolution=step, variable=variable,
                   command=callback, value_format=formatter, length=250).grid(
                       row=row, column=1, sticky="ew")

    bot.action_mode_var = tk.StringVar(value=ACTION_MODE_GAMEPAD)
    modes = tk.Frame(body, bg=theme.WOOD)
    modes.pack(fill="x", padx=6, pady=(6, 2))
    for label, value in (("多人后台", ACTION_MODE_GAMEPAD), ("前台鼠标", ACTION_MODE_MOUSE)):
        radio = PixelRadio(modes, text=label, value=value, variable=bot.action_mode_var, label_width=115)
        radio.pack(side="left", fill="x", expand=True)
    PixelLabel(body, text="开启游戏音效 · 后台钓鱼需进入多人模式", font_name="small",
               fill=theme.TEXT_DIM).pack(fill="x", padx=6, pady=(2, 6))

    controls = tk.Frame(body, bg=theme.WOOD)
    controls.pack(fill="x", padx=6, pady=(4, 4))
    controls.columnconfigure(0, weight=2)
    controls.columnconfigure((1, 2), weight=1)
    bot.start_btn = PixelButton(controls, text="开始钓鱼", command=bot.toggle_start,
                                 pady=5, font_name="button_lg")
    bot.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
    PixelButton(controls, text="清零", command=bot.reset, pady=5).grid(
        row=0, column=1, sticky="ew", padx=(0, 6))
    PixelButton(controls, text="设置", command=bot.open_settings, pady=5).grid(
        row=0, column=2, sticky="ew")

def open_settings(bot):
    existing = getattr(bot, "settings_window", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        existing.focus_set()
        return
    window = bot.settings_window = tk.Toplevel(bot.root)
    window.title("钓鱼助手 · 设置")
    window.geometry("360x260")
    window.resizable(False, False)
    window.configure(bg=theme.BG)
    window.transient(bot.root)
    window.bind("<Escape>", lambda _event: window.destroy())
    panel = PixelPanel(window, title="设置", grass=True)
    panel.pack(fill="both", expand=True, padx=10, pady=10)
    PixelLabel(panel.body, text="首次使用多人后台时完成以下设置", font_name="small",
               fill=theme.TEXT_DIM).pack(fill="x", padx=6, pady=(4, 8))
    PixelButton(panel.body, text="启用后台输入", command=bot.enable_background_input).pack(
        fill="x", padx=6, pady=4)
    PixelButton(panel.body, text="安装 / 修复手柄驱动", command=bot.install_vigem_driver).pack(
        fill="x", padx=6, pady=4)
    PixelButton(panel.body, text="返回", command=window.destroy, variant="stone").pack(
        fill="x", padx=6, pady=(10, 4))

