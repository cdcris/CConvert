"""Image discovery and conversion operations."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps, UnidentifiedImageError

SUPPORTED_EXTENSIONS = {
    ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"
}
OUTPUT_FORMATS = ("PNG", "JPG", "WEBP", "ICO")
ICO_SIZES = (16, 32, 48, 64, 128, 256)
IMAGES_PER_PAGE = 50
COLORS = {
    "bg": "#0a0a0f",
    "sidebar": "#13131a",
    "card": "#1a1a24",
    "border": "#2e2e3e",
    "text": "#f5f5f7",
    "muted": "#9797a8",
    "primary": "#14b8a6",
    "primary_hover": "#2dd4bf",
    "success": "#4ade80",
    "warning": "#fb923c",
    "input": "#22222e",
}


def is_inside(path: Path, directory: Path) -> bool:
    """Return True when path is inside directory (or is directory itself)."""
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def find_images(source: Path, output_dir: Path) -> Iterable[Path]:
    """Yield supported images, excluding files in the output directory."""
    if source.is_file():
        if source.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield source
        return

    for path in sorted(source.rglob("*")):
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
            and not is_inside(path.resolve(), output_dir)
        ):
            yield path


def square_image(image: Image.Image, size: int) -> Image.Image:
    """Fit an image inside a transparent square without stretching it."""
    image = ImageOps.exif_transpose(image).convert("RGBA")
    fitted = ImageOps.contain(image, (size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    position = ((size - fitted.width) // 2, (size - fitted.height) // 2)
    canvas.alpha_composite(fitted, position)
    return canvas


def format_file_size(size: int) -> str:
    """Return a compact, human-readable file size."""
    value = float(size)
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024


def output_folder(image_path: Path, source: Path, output_dir: Path) -> Path:
    """Build a collision-resistant destination while preserving subfolders."""
    extension = image_path.suffix.lower().lstrip(".")
    source_key = hashlib.sha1(
        str(source.resolve()).casefold().encode("utf-8")
    ).hexdigest()[:8]
    if source.is_dir():
        relative_parent = image_path.parent.relative_to(source)
        source_folder = f"{source.name}_{source_key}"
        return (
            output_dir / source_folder / relative_parent /
            f"{image_path.stem}_{extension}"
        )
    return output_dir / f"{image_path.stem}_{extension}_{source_key}"


def output_targets(
    image_path: Path,
    source: Path,
    output_dir: Path,
    formats: Iterable[str],
) -> dict[str, Path]:
    destination = output_folder(image_path, source, output_dir)
    suffixes = {"PNG": ".png", "JPG": ".jpg", "WEBP": ".webp", "ICO": ".ico"}
    return {
        name: destination / f"{image_path.stem}{suffixes[name]}"
        for name in (item.upper() for item in formats)
        if name in suffixes
    }


def save_atomic(image: Image.Image, target: Path, image_format: str, **options) -> None:
    """Save beside the target and atomically replace it when encoding succeeds."""
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        image.save(temporary, format=image_format, **options)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def generate_for_image(
    image_path: Path,
    source: Path,
    output_dir: Path,
    formats: Iterable[str] = OUTPUT_FORMATS,
    skip_existing: bool = False,
) -> Path:
    """Convert one image to each requested output format."""
    destination = output_folder(image_path, source, output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    selected = {item.upper() for item in formats}
    targets = output_targets(image_path, source, output_dir, selected)

    with Image.open(image_path) as image:
        converted = ImageOps.exif_transpose(image).convert("RGBA")

        if "PNG" in targets and not (skip_existing and targets["PNG"].exists()):
            save_atomic(converted, targets["PNG"], "PNG", optimize=True)
        if "JPG" in targets and not (skip_existing and targets["JPG"].exists()):
            background = Image.new("RGB", converted.size, "white")
            background.paste(converted, mask=converted.getchannel("A"))
            save_atomic(background, targets["JPG"], "JPEG", quality=95, optimize=True)
        if "WEBP" in targets and not (skip_existing and targets["WEBP"].exists()):
            save_atomic(converted, targets["WEBP"], "WEBP", quality=95, method=6)
        if "ICO" in targets and not (skip_existing and targets["ICO"].exists()):
            ico_base = square_image(converted, max(ICO_SIZES))
            save_atomic(
                ico_base,
                targets["ICO"],
                "ICO",
                sizes=[(n, n) for n in ICO_SIZES],
            )

    return destination


def process_image_job(
    image_text: str,
    source_text: str,
    output_text: str,
    formats: tuple[str, ...],
    skip_existing: bool,
) -> tuple[str, str, str]:
    """Picklable worker entry point used by the process pool."""
    image_path = Path(image_text)
    source = Path(source_text)
    output_dir = Path(output_text)
    targets = output_targets(image_path, source, output_dir, formats)
    if skip_existing and targets and all(path.exists() for path in targets.values()):
        return "skipped", image_text, str(output_folder(image_path, source, output_dir))
    try:
        destination = generate_for_image(
            image_path, source, output_dir, formats, skip_existing=skip_existing
        )
        return "completed", image_text, str(destination)
    except (OSError, UnidentifiedImageError, ValueError) as error:
        return "failed", image_text, str(error)


