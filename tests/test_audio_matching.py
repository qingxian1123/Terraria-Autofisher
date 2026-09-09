import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from autofisher.actions import BackgroundGamepadAction
from autofisher.audio import normalized_similarity, to_mono_float32
from autofisher.config import (
    background_gamepad_config_state,
    enable_background_gamepad_config,
    find_vigem_installer,
)


class AudioMatchingTests(unittest.TestCase):
    def test_finds_scaled_template_inside_larger_block(self):
        rng = np.random.default_rng(42)
        template = rng.normal(size=512).astype(np.float32)
        recording = rng.normal(scale=0.01, size=2048).astype(np.float32)
        recording[731:1243] = template * 0.25 + 0.1

        self.assertGreater(normalized_similarity(recording, template), 0.99)

    def test_silence_does_not_match(self):
        template = np.linspace(-1.0, 1.0, 128, dtype=np.float32)
        silence = np.zeros(512, dtype=np.float32)

        self.assertEqual(normalized_similarity(silence, template), 0.0)

    def test_short_recording_does_not_match(self):
        self.assertEqual(
            normalized_similarity(np.ones(10, dtype=np.float32), np.ones(20, dtype=np.float32)),
            0.0,
        )

    def test_stereo_conversion(self):
        stereo = np.array([[1.0, -1.0], [0.5, 0.5]], dtype=np.float32)

        np.testing.assert_allclose(to_mono_float32(stereo), [0.0, 0.5])

    def test_reads_enabled_background_gamepad_setting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps({"AllowUnfocusedInputOnGamepad": True}),
                encoding="utf-8",
            )
            self.assertTrue(background_gamepad_config_state(config_path))

    def test_missing_background_gamepad_setting_is_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text("{}", encoding="utf-8")
            self.assertFalse(background_gamepad_config_state(config_path))

    def test_enables_background_gamepad_setting_with_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            original = '{"AllowUnfocusedInputOnGamepad": false, "PlayWhenUnfocused": false}'
            config_path.write_text(original, encoding="utf-8")

            self.assertTrue(enable_background_gamepad_config(config_path))
            self.assertTrue(background_gamepad_config_state(config_path))
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertFalse(updated["PlayWhenUnfocused"])
            self.assertEqual(
                config_path.with_name("config.json.autofisher.bak").read_text(encoding="utf-8"),
                original,
            )

    def test_finds_bundled_vigem_installer(self):
        installer = find_vigem_installer()
        self.assertIsNotNone(installer)
        self.assertTrue(installer.is_file())
        self.assertEqual(installer.suffix.lower(), ".msi")

    def test_background_gamepad_holds_and_refreshes_trigger(self):
        class FakeGamepad:
            def __init__(self):
                self.trigger_values = []
                self.update_count = 0

            def right_trigger(self, value):
                self.trigger_values.append(value)

            def update(self):
                self.update_count += 1

        clock = [0.0]

        def advance(seconds):
            clock[0] += seconds

        action = object.__new__(BackgroundGamepadAction)
        action.gamepad = FakeGamepad()
        commands = []

        def pipe_command(command):
            commands.append(command)
            return "PULSED"

        action._pipe_command = pipe_command
        with mock.patch("autofisher.actions.time.monotonic", side_effect=lambda: clock[0]), mock.patch(
            "autofisher.actions.time.sleep", side_effect=advance
        ):
            action.perform()

        self.assertTrue(commands[0].startswith("PULSE "))
        self.assertEqual(action.gamepad.trigger_values, [255, 0])
        self.assertGreater(action.gamepad.update_count, 2)

    def test_background_patch_accepts_matching_protocol(self):
        BackgroundGamepadAction._validate_ready_response("READY 1.0.2")

    def test_background_patch_rejects_stale_protocol(self):
        with self.assertRaisesRegex(RuntimeError, "其他版本"):
            BackgroundGamepadAction._validate_ready_response("READY 1.0.1")

if __name__ == "__main__":
    unittest.main()
