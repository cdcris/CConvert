# Repository Guidelines

## Project Structure & Module Organization

This repository is a small Python image converter with a desktop interface and command-line mode. The `app.py` file is the launcher. `ui.py` contains the Tkinter window, while `ui_theme.py` owns shared styling. `image_processing.py` handles image discovery and conversion; `conversion_runner.py` coordinates background jobs; and `cli.py` implements command-line arguments and batch processing. `requirements.txt` lists the runtime dependency. Converted files are written to `converted_images/` by default. There is no separate test or asset source directory currently.

## Build, Test, and Development Commands

Install the only declared dependency with `python -m pip install -r requirements.txt`.

- `python app.py` — launch the desktop interface.
- `python app.py --help` — list command-line options.
- `python app.py ./images --output ./converted --formats png webp` — convert a file or directory from the command line.
- `python -m py_compile app.py cli.py conversion_runner.py image_processing.py ui.py ui_theme.py` — check Python syntax.

There is no build step or configured automated test suite at this time.

## Coding Style & Naming Conventions

Use four spaces for indentation and follow standard Python conventions: `snake_case` for functions, variables, and modules; `PascalCase` for classes; and uppercase names for module constants. Keep UI code in `ui.py` and conversion or batch behavior in the non-UI modules. Prefer standard-library and existing Pillow functionality over adding dependencies. No formatter or linter is configured.

## Testing Guidelines

No test framework or coverage requirement is configured. For changes, run the syntax-check command above and manually exercise the affected path. For conversion changes, try representative formats and verify output files; for UI changes, launch `python app.py` and check the relevant interaction. If adding tests, place them in a new `tests/` directory and use descriptive `test_*.py` filenames.

## Commit & Pull Request Guidelines

Git history is not available in this workspace, so no existing commit convention could be confirmed. Use short, imperative commit subjects. In pull requests, summarize behavior changes, list validation performed, link related issues when applicable, and include screenshots for visible UI changes.

## Configuration & Generated Files

Install dependencies from `requirements.txt`; do not commit generated conversions, Python bytecode, or local environment files. Keep output paths and worker settings configurable through the existing CLI or UI rather than hard-coding machine-specific paths.
