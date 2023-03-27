from __future__ import annotations

import enum


class Mode(enum.Enum):
    DISABLED = "disabled"
    REMOTE = "remote"
    LOCAL = "local"
    RAW = "raw"
