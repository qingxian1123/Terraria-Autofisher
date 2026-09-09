import unittest

from autofisher import theme


class UiThemeTests(unittest.TestCase):
    def test_classic_palette_is_wood_and_gold(self):
        self.assertEqual(theme.BG, "#1A120C")
        self.assertEqual(theme.WOOD, "#634229")
        self.assertEqual(theme.GOLD_HI, "#F0D878")
        self.assertNotIn("2b1f35", theme.BG.lower())

    def test_widgets_construct_without_mainloop(self):
        import tkinter as tk

        from autofisher.widgets import (
            PixelBar,
            PixelButton,
            PixelLabel,
            PixelPanel,
            PixelRadio,
            PixelScale,
        )

        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")

        try:
            root.withdraw()
            theme.init(root)
            panel = PixelPanel(root, title="实时状态")
            panel.pack()
            variable = tk.DoubleVar(value=0.7)
            PixelScale(
                panel.body,
                from_=0.5,
                to=0.95,
                resolution=0.01,
                variable=variable,
            ).pack()
            mode = tk.StringVar(value="gamepad")
            PixelRadio(panel.body, text="后台", value="gamepad", variable=mode).pack()
            bar = PixelBar(panel.body)
            bar.set(80, hot=True)
            PixelLabel(panel.body, text="匹配度: 80%").pack()
            button = PixelButton(root, text="开始钓鱼", variant="jungle")
            button.pack()
            button.set_variant("crimson")
            button.set_text("停止钓鱼")
            root.update_idletasks()
            self.assertGreater(button.winfo_reqwidth(), 40)
            self.assertEqual(theme.asset("rod").width(), 48)
            self.assertEqual(theme.asset("bait").width(), 48)
            self.assertEqual(theme.asset("tackle").height(), 68)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
