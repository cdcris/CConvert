"""Convert images to PNG, JPG, WebP, and ICO."""
from __future__ import annotations

import multiprocessing

from cli import main
from ui import ImageConverterApp, ImageConverterTheme

__all__ = ["ImageConverterApp", "ImageConverterTheme", "main"]

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
