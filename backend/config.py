"""Paths and resource limits; configuration never depends on the working directory."""
from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    legacy_dir: Path | None = None
    checkpoint: Path | None = None
    max_upload_bytes: int = 12 * 1024 * 1024
    max_pixels: int = 12_000_000
    max_comparisons: int = 20

    @classmethod
    def from_env(cls):
        def optional_path(name):
            value = os.environ.get(name, "").strip()
            return Path(value).expanduser().resolve() if value else None

        return cls(
            data_dir=optional_path("HM_DATA_DIR") or ROOT / "var",
            legacy_dir=optional_path("HM_SUPERGLUE_DIR"),
            checkpoint=optional_path("HM_SUPERGLUE_WEIGHTS"),
        )
