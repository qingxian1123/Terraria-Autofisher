"""Pixel-style Tk widgets that mimic classic Terraria inventory chrome."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

from autofisher import theme


class PixelPanel(tk.Frame):
    def __init__(self, master, title: str = "", *, grass: bool = False, **kwargs):
        super().__init__(master, bg=theme.BG, highlightthickness=0, bd=0, **kwargs)
        self._title = title
        self._grass = grass
        self._pad_x = 14 if grass else 8
        self._pad_bottom = 14 if grass else 8
        self._pad_top = 46 if grass else 24 if title else 8
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=theme.BG)
        self._canvas.pack(fill="both", expand=True)
        self.body = tk.Frame(self._canvas, bg=theme.WOOD, highlightthickness=0, bd=0)
        self._window = self._canvas.create_window(
            self._pad_x, self._pad_top, window=self.body, anchor="nw"
        )
        self.body.bind("<Configure>", self._fit_to_body)
        self._canvas.bind("<Configure>", self._stretch_body)

    def _fit_to_body(self, _event=None) -> None:
        height = max(self.body.winfo_reqheight() + self._pad_top + self._pad_bottom, 36)
        if abs(int(self._canvas.cget("height")) - height) > 1:
            self._canvas.configure(height=height)
        self._redraw()

    def _stretch_body(self, event) -> None:
        width = max(event.width - self._pad_x * 2, 20)
        current = int(float(self._canvas.itemcget(self._window, "width") or 0))
        if abs(current - width) > 1:
            self._canvas.itemconfigure(self._window, width=width)
        self._redraw()

    def _redraw(self) -> None:
        width = max(self._canvas.winfo_width(), 8)
        height = max(self._canvas.winfo_height(), 8)
        self._canvas.delete("chrome")
        before = set(self._canvas.find_all())
        if self._grass:
            theme.draw_grass_frame(self._canvas, width, height)
        else:
            theme.draw_bevel(self._canvas, 0, 0, width, height, fill=theme.WOOD)
        if self._title:
            theme.draw_outlined_text(
                self._canvas,
                20 if self._grass else 14,
                29 if self._grass else 13,
                self._title,
                font_spec=theme.font("panel"),
                fill=theme.TEXT_GOLD,
                anchor="w",
            )
        for item in self._canvas.find_all():
            if item not in before:
                self._canvas.addtag_withtag("chrome", item)
        self._canvas.tag_lower("chrome")


class PixelButton(tk.Canvas):
    def __init__(
        self,
        master,
        text: str,
        command=None,
        variant: str = "wood",
        padx: int = 16,
        pady: int = 3,
        font_name: str = "button",
    ):
        super().__init__(master, highlightthickness=0, bd=0, bg=theme.BG, cursor="hand2")
        self._text = text
        self._command = command
        self._variant = variant
        self._padx = padx
        self._pady = pady
        self._font_name = font_name
        self._state = "normal"
        self._hover = False
        self._pressed = False
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Map>", lambda _e: self._redraw())
        self._resize()

    def set_text(self, text: str) -> None:
        self._text = text
        self._resize()
        self._redraw()

    def set_state(self, state: str) -> None:
        self._state = state
        self.configure(cursor="" if state == "disabled" else "hand2")
        if state == "disabled":
            self._hover = False
            self._pressed = False
        self._redraw()

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._redraw()

    def _resize(self) -> None:
        spec = tkfont.Font(self, font=theme.font(self._font_name))
        width = spec.measure(self._text) + self._padx * 2 + 8
        height = spec.metrics("linespace") + self._pady * 2 + 8
        self.configure(width=max(width, 88), height=max(height, 36))

    def _on_enter(self, _event) -> None:
        if self._state != "disabled":
            self._hover = True
            self._redraw()

    def _on_leave(self, _event) -> None:
        self._hover = False
        self._pressed = False
        self._redraw()

    def _on_press(self, _event) -> None:
        if self._state != "disabled":
            self._pressed = True
            self._redraw()

    def _on_release(self, event) -> None:
        if self._state == "disabled":
            return
        was_pressed = self._pressed
        self._pressed = False
        self._redraw()
        if was_pressed and 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            if self._command:
                self._command()

    def _redraw(self, _event=None) -> None:
        width = max(self.winfo_width(), 8)
        height = max(self.winfo_height(), 8)
        palette = theme.VARIANTS[self._variant]
        if self._state == "disabled":
            fill = theme.STONE
            text_fill = theme.TEXT_DIM
            inset = True
        elif self._pressed:
            fill = palette["press"]
            text_fill = palette["text"]
            inset = True
        elif self._hover:
            fill = palette["hover"]
            text_fill = palette["text"]
            inset = False
        else:
            fill = palette["fill"]
            text_fill = palette["text"]
            inset = False
        self.delete("all")
        theme.draw_bevel(self, 0, 0, width, height, inset=inset, fill=fill)
        tx, ty = width // 2, height // 2
        if self._pressed and self._state != "disabled":
            tx += 1
            ty += 1
        theme.draw_outlined_text(
            self,
            tx,
            ty,
            self._text,
            font_spec=theme.font(self._font_name),
            fill=text_fill,
        )


class PixelScale(tk.Canvas):
    def __init__(
        self,
        master,
        *,
        from_: float,
        to: float,
        resolution: float,
        variable: tk.Variable,
        command=None,
        value_format=None,
        length: int = 360,
    ):
        super().__init__(
            master,
            height=36,
            width=length,
            highlightthickness=0,
            bd=0,
            bg=theme.WOOD,
            cursor="hand2",
        )
        self._from = from_
        self._to = to
        self._resolution = resolution
        self._variable = variable
        self._command = command
        self._value_format = value_format or (lambda value: f"{value:.2f}")
        self._dragging = False
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda _e: self._redraw())
        self._trace = variable.trace_add("write", lambda *_args: self._redraw())

    def _track_box(self) -> tuple[int, int, int, int]:
        width = max(self.winfo_width(), 80)
        return 6, 10, width - 64, 26

    def _value_from_x(self, x: int) -> float:
        x1, _, x2, _ = self._track_box()
        ratio = (x - x1) / max(x2 - x1, 1)
        ratio = min(1.0, max(0.0, ratio))
        raw = self._from + ratio * (self._to - self._from)
        steps = round((raw - self._from) / self._resolution)
        value = self._from + steps * self._resolution
        return min(self._to, max(self._from, value))

    def _set_from_event(self, event) -> None:
        value = self._value_from_x(event.x)
        self._variable.set(value)
        if self._command:
            self._command(str(value))

    def _on_click(self, event) -> None:
        self._dragging = True
        self._set_from_event(event)

    def _on_drag(self, event) -> None:
        if self._dragging:
            self._set_from_event(event)

    def _on_release(self, _event) -> None:
        self._dragging = False

    def _redraw(self, _event=None) -> None:
        width = max(self.winfo_width(), 80)
        height = max(self.winfo_height(), 28)
        self.delete("all")
        self.configure(bg=theme.WOOD)
        theme.hrect(self, 0, 0, width, height, theme.WOOD)
        x1, y1, x2, y2 = self._track_box()
        theme.draw_bevel(self, x1, y1, x2, y2, inset=True, fill=theme.WOOD_DEEP)
        value = float(self._variable.get())
        ratio = (value - self._from) / max(self._to - self._from, 0.0001)
        fill_x = x1 + 3 + int((x2 - x1 - 6) * min(1.0, max(0.0, ratio)))
        if fill_x > x1 + 4:
            theme.hrect(self, x1 + 3, y1 + 3, fill_x, y2 - 3, theme.GOLD_MID)
        knob_x = fill_x
        knob_y = (y1 + y2) // 2
        theme.draw_bevel(
            self,
            knob_x - 7,
            knob_y - 11,
            knob_x + 7,
            knob_y + 11,
            fill=theme.WOOD_HOVER,
        )
        theme.draw_outlined_text(
            self,
            width - 8,
            height // 2,
            self._value_format(value),
            font_spec=theme.font("small"),
            fill=theme.TEXT_MOUSE,
            anchor="e",
        )


class PixelBar(tk.Canvas):
    def __init__(self, master, length: int = 360):
        super().__init__(
            master,
            height=22,
            width=length,
            highlightthickness=0,
            bd=0,
            bg=theme.WOOD,
        )
        self._value = 0.0
        self._hot = False
        self.bind("<Configure>", lambda _e: self._redraw())

    def __setitem__(self, key, value) -> None:
        if key == "value":
            self.set(float(value), hot=self._hot)
            return
        raise KeyError(key)

    def set(self, value: float, hot: bool = False) -> None:
        self._value = min(100.0, max(0.0, float(value)))
        self._hot = hot
        self._redraw()

    def _redraw(self, _event=None) -> None:
        width = max(self.winfo_width(), 40)
        height = max(self.winfo_height(), 16)
        self.delete("all")
        theme.hrect(self, 0, 0, width, height, theme.WOOD)
        theme.draw_bevel(self, 0, 0, width, height, inset=True, fill=theme.WOOD_DEEP)
        inner_x1, inner_y1, inner_x2, inner_y2 = 4, 4, width - 4, height - 4
        fill_width = int((inner_x2 - inner_x1) * (self._value / 100.0))
        if fill_width <= 0:
            return
        fill = theme.LIME if self._hot else theme.MANA if self._value >= 55 else theme.GOLD_MID
        chunk = 4
        x = inner_x1
        end = inner_x1 + fill_width
        while x < end:
            next_x = min(x + chunk - 1, end)
            theme.hrect(self, x, inner_y1, next_x, inner_y2, fill)
            x += chunk


class PixelLabel(tk.Canvas):
    def __init__(
        self,
        master,
        text: str,
        *,
        font_name: str = "body",
        fill: str = theme.TEXT,
        anchor: str = "w",
        height: int = 22,
        background: str = theme.WOOD,
    ):
        super().__init__(
            master,
            height=height,
            highlightthickness=0,
            bd=0,
            bg=background,
        )
        self._background = background
        self._text = text
        self._font_name = font_name
        self._fill = fill
        self._anchor = anchor
        self.bind("<Configure>", lambda _e: self._redraw())

    def config(self, **kwargs):
        if "text" in kwargs:
            self._text = kwargs.pop("text")
        if "fg" in kwargs:
            self._fill = kwargs.pop("fg")
        if "fill" in kwargs:
            self._fill = kwargs.pop("fill")
        if kwargs:
            super().configure(**kwargs)
        self._redraw()

    configure = config

    def _wrap(self, max_width: int) -> list[str]:
        spec = tkfont.Font(self, font=theme.font(self._font_name))
        lines: list[str] = []
        current = ""
        for char in self._text:
            if spec.measure(current + char) <= max(max_width - 8, 12):
                current += char
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines or [""]

    def _redraw(self, _event=None) -> None:
        width = max(self.winfo_width(), 8)
        height = max(self.winfo_height(), 8)
        self.delete("all")
        theme.hrect(self, 0, 0, width, height, self._background)
        lines = self._wrap(width)
        spec = tkfont.Font(self, font=theme.font(self._font_name))
        line_height = spec.metrics("linespace") + 2
        total = line_height * len(lines)
        y = max((height - total) // 2 + line_height // 2, line_height // 2)
        x = 2 if self._anchor == "w" else width // 2
        for line in lines:
            theme.draw_outlined_text(
                self,
                x,
                y,
                line,
                font_spec=theme.font(self._font_name),
                fill=self._fill,
                anchor=self._anchor,
            )
            y += line_height


class PixelRadio(tk.Frame):
    def __init__(self, master, text: str, value: str, variable: tk.StringVar, label_width: int = 360):
        super().__init__(master, bg=theme.WOOD, highlightthickness=0, bd=0)
        self._text = text
        self._value = value
        self._variable = variable
        self._box = tk.Canvas(self, width=22, height=22, highlightthickness=0, bd=0, bg=theme.WOOD)
        self._box.pack(side="left", padx=(2, 8), pady=2)
        self._label = tk.Canvas(
            self, height=22, width=label_width, highlightthickness=0, bd=0, bg=theme.WOOD
        )
        self._label.pack(side="left", fill="x", expand=True)
        for widget in (self, self._box, self._label):
            widget.bind("<Button-1>", self._select)
            widget.configure(cursor="hand2")
        self._label.bind("<Configure>", lambda _e: self._redraw())
        self._box.bind("<Configure>", lambda _e: self._redraw())
        self._trace = variable.trace_add("write", lambda *_args: self._redraw())
        self._redraw()

    def _select(self, _event=None) -> None:
        self._variable.set(self._value)

    def _redraw(self, _event=None) -> None:
        selected = self._variable.get() == self._value
        self._box.delete("all")
        fill = theme.GOLD_MID if selected else theme.WOOD_DEEP
        theme.draw_bevel(self._box, 0, 0, 22, 22, inset=not selected, fill=fill, selected=selected)
        if selected:
            theme.hrect(self._box, 7, 7, 15, 15, theme.TEXT_GOLD)
        self._label.delete("all")
        width = max(self._label.winfo_width(), 40)
        self._label.configure(width=width)
        theme.hrect(self._label, 0, 0, width, 22, theme.WOOD)
        theme.draw_outlined_text(
            self._label,
            0,
            11,
            self._text,
            font_spec=theme.font("body"),
            fill=theme.TEXT_MOUSE if selected else theme.TEXT,
            anchor="w",
        )


class PixelSlot(tk.Canvas):
    """Square equipment slot; only the catch slot displays a live count."""
    def __init__(self, master, sprite: str, *, count=None):
        super().__init__(master, width=80, height=80, bg=theme.WOOD,
                         highlightthickness=0, bd=0)
        self._sprite = sprite
        self._count = count
        self.bind("<Configure>", self._redraw)

    def set_count(self, count):
        self._count = count
        self._redraw()

    def _redraw(self, _event=None):
        self.delete("all")
        theme.draw_bevel(self, 0, 0, 80, 80, fill=theme.SLOT_DARK, selected=self._sprite == "rod")
        theme.hrect(self, 4, 4, 76, 76, theme.SLOT_HI)
        theme.hrect(self, 6, 6, 76, 76, theme.SLOT_DARK)
        theme.hrect(self, 6, 6, 74, 74, theme.SLOT)
        self.create_image(40, 39, image=theme.asset(self._sprite))
        if self._count is not None:
            count = str(self._count) if self._count < 10000 else "9999+"
            theme.draw_outlined_text(self, 72, 68, count, font_spec=theme.font("small"),
                                     fill=theme.TEXT_WHITE, anchor="e")
