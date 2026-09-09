import sys
from pathlib import Path


def resource_root() -> Path:
    """Return the directory that contains assets/ and injector/."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parent.parent
