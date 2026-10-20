"""Command-line interface for image conversion."""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Iterable

from image_processing import OUTPUT_FORMATS, find_images, process_image_job
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert an image or folder to PNG, JPG, WEBP, and/or ICO."
    )
    parser.add_argument("source", nargs="?", help="Image file or directory to scan recursively.")
    parser.add_argument(
        "-o", "--output", default="converted_images",
        help="Output directory (default: converted_images).",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=[name.lower() for name in OUTPUT_FORMATS],
        default=[name.lower() for name in OUTPUT_FORMATS],
        help="Output formats to create (default: png jpg webp ico).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(4, max(1, (os.cpu_count() or 2) - 1)),
        help="Parallel worker processes (default: up to 4).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing outputs instead of skipping them.",
    )
    parser.add_argument("--gui", action="store_true", help="Open the desktop interface.")
    return parser.parse_args()


def run_cli(
    source_text: str,
    output_text: str,
    formats: Iterable[str] = OUTPUT_FORMATS,
    workers: int = 4,
    skip_existing: bool = True,
) -> int:
    source = Path(source_text).expanduser().resolve()
    output_dir = Path(output_text).expanduser().resolve()
    if not source.exists():
        print(f"Error: source does not exist: {source}", file=sys.stderr)
        return 2

    images = list(find_images(source, output_dir))
    if not images:
        print(f"No supported images found in: {source}")
        return 0

    workers = max(1, min(workers, os.cpu_count() or 1))
    selected_formats = tuple(item.upper() for item in formats)
    completed = 0
    skipped = 0
    failed = 0
    iterator = iter(images)
    pending = {}

    try:
        executor = ProcessPoolExecutor(max_workers=workers)
    except OSError as error:
        print(
            f"Process workers unavailable; using threads instead: {error}",
            file=sys.stderr,
        )
        executor = ThreadPoolExecutor(max_workers=workers)

    with executor:
        def submit_jobs() -> None:
            while len(pending) < workers * 2:
                try:
                    image_path = next(iterator)
                except StopIteration:
                    return
                future = executor.submit(
                    process_image_job,
                    str(image_path),
                    str(source),
                    str(output_dir),
                    selected_formats,
                    skip_existing,
                )
                pending[future] = image_path

        submit_jobs()
        processed = 0
        while pending:
            done, _not_done = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in done:
                image_path = pending.pop(future)
                processed += 1
                try:
                    status, _image_text, detail = future.result()
                except Exception as error:
                    status, detail = "failed", str(error)
                if status == "completed":
                    completed += 1
                    print(f"[{processed:,}/{len(images):,}] Created: {detail}")
                elif status == "skipped":
                    skipped += 1
                    print(f"[{processed:,}/{len(images):,}] Existing: {detail}")
                else:
                    failed += 1
                    print(f"Skipped {image_path}: {detail}", file=sys.stderr)
            submit_jobs()

    print(
        f"\nFinished: {completed:,} converted, {skipped:,} existing, "
        f"{failed:,} failed."
    )
    return 1 if failed else 0


def main() -> int:
    args = parse_args()
    if args.gui or args.source is None:
        from ui import ImageConverterApp

        app = ImageConverterApp()
        app.mainloop()
        return 0
    return run_cli(
        args.source,
        args.output,
        args.formats,
        workers=args.workers,
        skip_existing=not args.overwrite,
    )



