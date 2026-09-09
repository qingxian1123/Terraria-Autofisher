"""Classic Terraria inventory colors, pixel fonts, and tiny sprites."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

from autofisher.paths import resource_root

# Night dirt behind the inventory, sampled from classic UI chrome.
BG = "#1A120C"
BG_RAISED = "#22180F"

# Wood fill used by Inventory_Back-style panels.
WOOD = "#634229"
WOOD_DARK = "#3C2818"
WOOD_DEEP = "#2A1A10"
WOOD_HOVER = "#7A5330"
WOOD_PRESS = "#4A301C"
WOOD_GRAIN = "#54361E"

# Gold 3D bevel around inventory slots and menu plaques.
GOLD_HI = "#F0D878"
GOLD_MID = "#C8A048"
GOLD_LO = "#6B4A18"
GOLD_DEEP = "#3C2810"
OUTLINE = "#302015"
TOOLTIP = "#19243B"
WOOD_HI = "#AD8150"
GRASS = "#55A630"
GRASS_HI = "#A3D950"
GRASS_DARK = "#285525"
DIRT = "#795039"
DIRT_HI = "#AC7950"
SLOT = "#304E80"
SLOT_HI = "#7891C2"
SLOT_DARK = "#1B2B52"

# In-game mouse text and rarity colors.
TEXT = "#FFF8DC"
TEXT_DIM = "#C8B890"
TEXT_GOLD = "#FFE46A"
TEXT_MOUSE = "#FFFFA0"
TEXT_WHITE = "#F8F8F0"

JUNGLE = "#2E6B1E"
JUNGLE_HI = "#3C8C28"
JUNGLE_LO = "#1E4A14"
CRIMSON = "#8C2020"
CRIMSON_HI = "#B42828"
CRIMSON_LO = "#5A1414"
STONE = "#4A4438"
STONE_HI = "#5A5448"
STONE_LO = "#2A2620"

MANA = "#4B9BFF"
WATER = "#48C8E0"
LIME = "#78F078"
ORANGE = "#F0A028"
HEALTH = "#E84B4B"

VARIANTS = {
    "wood": {
        "fill": WOOD,
        "hover": WOOD_HOVER,
        "press": WOOD_PRESS,
        "text": TEXT_WHITE,
    },
    "jungle": {
        "fill": JUNGLE,
        "hover": JUNGLE_HI,
        "press": JUNGLE_LO,
        "text": TEXT_WHITE,
    },
    "crimson": {
        "fill": CRIMSON,
        "hover": CRIMSON_HI,
        "press": CRIMSON_LO,
        "text": TEXT_WHITE,
    },
    "stone": {
        "fill": STONE,
        "hover": STONE_HI,
        "press": STONE_LO,
        "text": TEXT_DIM,
    },
}

_fonts: dict[str, tuple] = {}
_assets: dict[str, tk.PhotoImage] = {}
_family = "TkDefaultFont"


def _choose_family(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for name in ("SimSun", "NSimSun", "宋体", "新宋体"):
        if name in available:
            return name
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑"):
        if name in available:
            return name
    return "TkDefaultFont"


def _font(size: int) -> tuple:
    return (_family, -size, "bold")


def init(root: tk.Misc) -> None:
    """Resolve pixel-friendly fonts and cache sprites. Call after Tk()."""
    global _family
    _family = _choose_family(root)
    _fonts.update(
        {
            "title": _font(20),
            "subtitle": _font(14),
            "panel": _font(14),
            "body": _font(14),
            "button": _font(15),
            "button_lg": _font(16),
            "small": _font(12),
            "count": _font(16),
        }
    )
    for key, filename in (("rod", "Golden_Fishing_Rod.png"),
                          ("bait", "Master_Bait.png"),
                          ("tackle", "Angler_Tackle_Bag.png")):
        source = tk.PhotoImage(master=root, file=str(resource_root() / "assets" / "ui" / filename))
        scale = max(1, min(68 // source.width(), 68 // source.height()))
        _assets[key] = source.zoom(scale)
    _assets["icon"] = _assets["rod"]


def font(name: str) -> tuple:
    return _fonts[name]


def asset(name: str) -> tk.PhotoImage:
    return _assets[name]


def hrect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, color: str) -> None:
    canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")


def draw_bevel(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    inset: bool = False,
    fill: str = WOOD,
    selected: bool = False,
) -> None:
    """Hard square bevel, lit from the upper left; gold marks selection."""
    light = GOLD_HI if selected else STONE_HI if fill == STONE else WOOD_HI
    dark = GOLD_LO if selected else STONE_LO if fill == STONE else WOOD_DEEP
    hi, lo = (dark, light) if inset else (light, dark)
    mid_hi, mid_lo = (WOOD_DARK, WOOD_HOVER) if inset else (WOOD_HOVER, WOOD_DARK)
    hrect(canvas, x1, y1, x2, y2, fill)
    hrect(canvas, x1, y1, x2, y1 + 1, OUTLINE)
    hrect(canvas, x1, y2 - 1, x2, y2, OUTLINE)
    hrect(canvas, x1, y1, x1 + 1, y2, OUTLINE)
    hrect(canvas, x2 - 1, y1, x2, y2, OUTLINE)
    hrect(canvas, x1 + 1, y1 + 1, x2 - 1, y1 + 2, hi)
    hrect(canvas, x1 + 1, y1 + 1, x1 + 2, y2 - 1, hi)
    hrect(canvas, x1 + 2, y1 + 2, x2 - 2, y1 + 3, mid_hi)
    hrect(canvas, x1 + 2, y1 + 2, x1 + 3, y2 - 2, mid_hi)
    hrect(canvas, x1 + 1, y2 - 2, x2 - 1, y2 - 1, lo)
    hrect(canvas, x2 - 2, y1 + 1, x2 - 1, y2 - 1, lo)
    hrect(canvas, x1 + 2, y2 - 3, x2 - 2, y2 - 2, mid_lo)
    hrect(canvas, x2 - 3, y1 + 2, x2 - 2, y2 - 2, mid_lo)


def draw_outlined_text(
    canvas: tk.Canvas,
    x: int,
    y: int,
    text: str,
    *,
    font_spec: tuple,
    fill: str = TEXT_GOLD,
    outline: str = OUTLINE,
    anchor: str = "center",
) -> int:
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            canvas.create_text(
                x + dx,
                y + dy,
                text=text,
                font=font_spec,
                fill=outline,
                anchor=anchor,
            )
    return canvas.create_text(
        x, y, text=text, font=font_spec, fill=fill, anchor=anchor
    )


def draw_grass_frame(canvas: tk.Canvas, width: int, height: int) -> None:
    """Draw deterministic terrain pixels around an opaque wooden interior."""
    draw_bevel(canvas, 2, 10, width - 2, height, fill=DIRT)
    hrect(canvas, 12, 30, width - 12, height - 12, WOOD)
    hrect(canvas, 12, 16, width - 12, 42, GRASS_DARK)
    for y in range(30, height - 12, 18):
        for x in (4, width - 10):
            hrect(canvas, x, y, x + 4, y + 6, DIRT_HI)
            hrect(canvas, x + 2, y + 8, x + 6, y + 12, WOOD_DEEP)
    for x in range(18, width - 16, 26):
        hrect(canvas, x, height - 9, x + 8, height - 5, DIRT_HI)
        if x % 3 == 0:
            hrect(canvas, x, height - 10, x + 6, height - 6, STONE_HI)
    hrect(canvas, 2, 10, width - 2, 18, GRASS_DARK)
    hrect(canvas, 4, 8, width - 4, 14, GRASS)
    hrect(canvas, 6, 6, width - 6, 10, GRASS_HI)
    for index, x in enumerate(range(8, width - 10, 12)):
        tip = 2 if index % 3 == 0 else 4
        hrect(canvas, x, tip, x + 2, 8, GRASS_DARK)
        hrect(canvas, x + 2, tip, x + 4, 10, GRASS_HI)
        hrect(canvas, x + 4, 4, x + 6, 10, GRASS)
        hrect(canvas, x + 4, 14, x + 8, 18 + (index % 3) * 2, GRASS_DARK)
    for x, length in ((4, 40), (width - 8, 54)):
        hrect(canvas, x, 14, x + 2, length, GRASS_DARK)
        for y in range(20, length, 10):
            hrect(canvas, x - 2, y, x + 4, y + 4, GRASS)
