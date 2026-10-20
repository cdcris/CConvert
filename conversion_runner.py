"""Background conversion orchestration shared by the desktop interface."""
from __future__ import annotations

import queue
import threading
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, wait
from pathlib import Path

from image_processing import process_image_job


def run_generation(
    jobs: list[tuple[Path, Path]],
    output: Path,
    formats: tuple[str, ...],
    workers: int,
    skip_existing: bool,
    work_queue: queue.Queue,
    cancel_event: threading.Event,
) -> None:
    completed = skipped = processed = 0
    failures: list[tuple[Path, str]] = []
    total = len(jobs)
    pending = {}
    job_iterator = iter(jobs)
    try:
        executor = ProcessPoolExecutor(max_workers=workers)
    except OSError as error:
        executor = ThreadPoolExecutor(max_workers=workers)
        work_queue.put(("notice", f"Process workers unavailable; using threads ({error})."))

    def submit_jobs() -> None:
        while len(pending) < workers * 2:
            try:
                image_path, source = next(job_iterator)
            except StopIteration:
                return
            future = executor.submit(process_image_job, str(image_path), str(source), str(output), formats, skip_existing)
            pending[future] = image_path

    def record_result(future, image_path: Path) -> None:
        nonlocal completed, skipped, processed
        try:
            status, _image_text, detail = future.result()
            if status == "completed":
                completed += 1
            elif status == "skipped":
                skipped += 1
            else:
                failures.append((image_path, detail))
        except Exception as error:
            failures.append((image_path, str(error)))
        processed += 1
        work_queue.put(("progress", processed, total, image_path.name, completed, skipped))

    was_cancelled = False
    try:
        submit_jobs()
        while pending:
            if cancel_event.is_set():
                was_cancelled = True
                for future in pending:
                    future.cancel()
                break
            done, _not_done = wait(tuple(pending), timeout=0.2, return_when=FIRST_COMPLETED)
            for future in done:
                record_result(future, pending.pop(future))
            submit_jobs()
    except Exception as error:
        was_cancelled = True
        failures.append((Path("worker-pool"), str(error)))
        for future in pending:
            future.cancel()
    finally:
        executor.shutdown(wait=True, cancel_futures=was_cancelled)

    if was_cancelled:
        for future, image_path in list(pending.items()):
            if future.done() and not future.cancelled():
                record_result(future, image_path)
    cancelled = total - processed
    work_queue.put(("done", completed, skipped, failures, output, cancelled))
