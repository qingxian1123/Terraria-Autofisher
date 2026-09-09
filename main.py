from autofisher.app import FishingBot, main
from autofisher.actions import BackgroundGamepadAction, ForegroundMouseAction
from autofisher.audio import normalized_similarity, to_mono_float32
from autofisher.config import (
    background_gamepad_config_state,
    enable_background_gamepad_config,
    find_process_id,
    find_terraria_config,
    find_vigem_installer,
)
from autofisher.constants import PATCH_PROTOCOL_VERSION

__all__ = [
    "BackgroundGamepadAction",
    "FishingBot",
    "ForegroundMouseAction",
    "PATCH_PROTOCOL_VERSION",
    "background_gamepad_config_state",
    "enable_background_gamepad_config",
    "find_process_id",
    "find_terraria_config",
    "find_vigem_installer",
    "main",
    "normalized_similarity",
    "to_mono_float32",
]


if __name__ == "__main__":
    main()
