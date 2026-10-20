"""Tkinter presentation layer for the image converter."""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Iterable

from PIL import Image, ImageTk, UnidentifiedImageError

from image_processing import (
    COLORS, IMAGES_PER_PAGE, OUTPUT_FORMATS, SUPPORTED_EXTENSIONS,
    find_images, format_file_size, square_image,
)
from conversion_runner import run_generation
from ui_theme import ImageConverterTheme
class ImageConverterApp(tk.Tk):
    """A guided image conversion interface for non-technical users."""

    def __init__(self):
        super().__init__()
        self.title("Image Converter")
        self.geometry("1080x720")
        self.minsize(860, 620)
        self.theme = ImageConverterTheme(self)
        self.c = COLORS
        self.images: list[Path] = []
        self.image_sources: dict[Path, Path] = {}
        self.output_dir = tk.StringVar(
            value=str(Path.cwd() / "converted_images")
        )
        self.status = tk.StringVar(value="Ready — add images to begin.")
        self.summary = tk.StringVar(value="No images selected")
        self.page_summary = tk.StringVar(value="Page 1 of 1")
        self.current_page = 0
        self.format_vars = {
            name: tk.BooleanVar(value=True) for name in OUTPUT_FORMATS
        }
        default_workers = min(4, max(1, (os.cpu_count() or 2) - 1))
        self.worker_count = tk.IntVar(value=default_workers)
        self.skip_existing = tk.BooleanVar(value=True)
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.file_thumbnails: dict[str, ImageTk.PhotoImage] = {}
        self.thumbnail_labels: dict[str, tk.Label] = {}
        self.work_queue: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.is_working = False
        self._build_ui()
        self.after(100, self._read_worker_messages)

    def _build_ui(self):
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)
        self._build_sidebar(shell)

        main = ttk.Frame(shell)
        main.pack(side="left", fill="both", expand=True)
        self._build_topbar(main)

        content = ttk.Frame(main, padding=(26, 22))
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        self._build_source_card(content)
        self._build_file_card(content)
        self._build_output_card(content)

        footer = tk.Label(
            main, textvariable=self.status, anchor="w", bg=self.c["sidebar"],
            fg=self.c["muted"], padx=22, pady=8
        )
        footer.pack(fill="x", side="bottom")

    def _build_sidebar(self, parent):
        side = ttk.Frame(parent, style="Sidebar.TFrame", width=225)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(
            side, text="IMAGE CONVERTER", bg=self.c["sidebar"], fg="white",
            anchor="w", padx=20, pady=22, font=("Segoe UI", 13, "bold")
        ).pack(fill="x")
        tk.Label(
            side, text="THREE EASY STEPS", bg=self.c["sidebar"], fg=self.c["muted"],
            anchor="w", padx=20, pady=10, font=("Segoe UI", 8, "bold")
        ).pack(fill="x", pady=(8, 0))
        steps = [
            ("1", "Add your images", "Browse for files or a folder"),
            ("2", "Choose formats", "PNG, JPG, WEBP, or ICO"),
            ("3", "Convert images", "One click does the rest"),
        ]
        for number, title, detail in steps:
            row = tk.Frame(side, bg=self.c["sidebar"])
            row.pack(fill="x", padx=18, pady=10)
            tk.Label(
                row, text=number, bg=self.c["primary"], fg="white", width=2,
                font=("Segoe UI", 9, "bold"), padx=2, pady=4
            ).pack(side="left", anchor="n")
            text = tk.Frame(row, bg=self.c["sidebar"])
            text.pack(side="left", padx=10)
            tk.Label(text, text=title, bg=self.c["sidebar"], fg=self.c["text"], anchor="w").pack(fill="x")
            tk.Label(text, text=detail, bg=self.c["sidebar"], fg=self.c["muted"], anchor="w", font=("Segoe UI", 8)).pack(fill="x")
        tk.Label(
            side, text="Convert every selected image\nto one or more formats.",
            bg=self.c["sidebar"], fg=self.c["muted"], justify="left", anchor="w",
            padx=20, pady=20, font=("Segoe UI", 9)
        ).pack(side="bottom", fill="x")

    def _build_topbar(self, parent):
        top = tk.Frame(parent, bg=self.c["sidebar"], height=66)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(
            top, text="Convert images to the formats you need", bg=self.c["sidebar"],
            fg=self.c["text"], font=("Segoe UI", 15, "bold"), padx=26
        ).pack(side="left", pady=18)
        tk.Label(
            top, text="No design skills needed", bg=self.c["input"], fg=self.c["muted"],
            padx=12, pady=5, font=("Segoe UI", 8, "bold")
        ).pack(side="right", padx=22)

    def _card(self, parent, padding=(18, 16)):
        return ttk.Frame(parent, style="Card.TFrame", padding=padding)

    def _build_source_card(self, parent):
        card = self._card(parent)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        card.columnconfigure(1, weight=1)

        self.preview = tk.Label(
            card, text="IMAGE", bg=self.c["input"], fg=self.c["muted"],
            width=12, height=5, font=("Segoe UI", 9, "bold")
        )
        self.preview.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 18))

        source_panel = tk.Frame(
            card, bg=self.c["card"], highlightbackground=self.c["border"],
            highlightcolor=self.c["border"], highlightthickness=1
        )
        source_panel.grid(row=0, column=1, sticky="ew")
        source_panel.columnconfigure(0, weight=1)
        tk.Label(
            source_panel, text="Choose your images", bg=self.c["card"],
            fg=self.c["text"], font=("Segoe UI", 13, "bold"), pady=11
        ).grid(row=0, column=0)
        tk.Label(
            source_panel, text="PNG, JPG, WebP, ICO, GIF, BMP or TIFF", bg=self.c["card"], fg=self.c["muted"],
            font=("Segoe UI", 9), pady=2
        ).grid(row=1, column=0)
        buttons = tk.Frame(source_panel, bg=self.c["card"])
        buttons.grid(row=2, column=0, pady=(8, 13))
        ttk.Button(buttons, text="Browse images", style="Primary.TButton", command=self.browse_images).pack(side="left")
        ttk.Button(buttons, text="Choose folder", style="Light.TButton", command=self.browse_folder).pack(side="left", padx=8)

    def _build_file_card(self, parent):
        card = self._card(parent, (18, 14))
        card.grid(row=1, column=0, sticky="nsew", pady=(0, 14))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)
        header = ttk.Frame(card, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(header, textvariable=self.summary, style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(header, text="Remove selected", style="Light.TButton", command=self.remove_selected).pack(side="right")
        ttk.Button(header, text="Clear all", style="Light.TButton", command=self.clear_images).pack(side="right", padx=7)

        table_box = ttk.Frame(card, style="Card.TFrame")
        table_box.grid(row=1, column=0, sticky="nsew")
        self.file_list = ttk.Treeview(
            table_box, columns=("number", "name", "size", "view"), show="headings", style="Files.Treeview",
            selectmode="extended"
        )
        self.file_list.heading("number", text="NO.", anchor="center")
        self.file_list.heading("name", text="FILENAME", anchor="w")
        self.file_list.heading("size", text="FILE SIZE", anchor="e")
        self.file_list.heading("view", text="IMAGE VIEW", anchor="center")
        self.file_list.column("number", width=65, minwidth=55, anchor="center", stretch=False)
        self.file_list.column("name", width=390, minwidth=180, anchor="w")
        self.file_list.column("size", width=120, minwidth=90, anchor="e", stretch=False)
        self.file_list.column("view", width=130, minwidth=110, anchor="center", stretch=False)
        self.file_list.tag_configure("empty", foreground=self.c["muted"])
        scroll = ttk.Scrollbar(table_box, orient="vertical", command=self._scroll_file_list)
        self.file_list.configure(yscrollcommand=scroll.set)
        self.file_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.file_list.bind("<<TreeviewSelect>>", self._show_selected_preview)
        self.file_list.bind("<Configure>", self._schedule_thumbnail_positions, add="+")
        self.file_list.bind("<MouseWheel>", self._schedule_thumbnail_positions, add="+")
        self.file_list.bind("<KeyRelease>", self._schedule_thumbnail_positions, add="+")

        pagination = ttk.Frame(card, style="Card.TFrame")
        pagination.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        pagination.columnconfigure(1, weight=1)
        self.previous_page_button = ttk.Button(
            pagination, text="Previous", style="Light.TButton",
            command=lambda: self._change_page(-1), state="disabled",
        )
        self.previous_page_button.grid(row=0, column=0)
        page_status = ttk.Frame(pagination, style="Card.TFrame")
        page_status.grid(row=0, column=1)
        self.page_loading = ttk.Progressbar(
            page_status, mode="indeterminate", length=72,
        )
        self.page_loading.pack(side="left", padx=(0, 8))
        self.page_loading.pack_forget()
        self.page_status_label = ttk.Label(
            page_status, textvariable=self.page_summary, style="Muted.TLabel",
            anchor="center",
        )
        self.page_status_label.pack(side="left")
        self.next_page_button = ttk.Button(
            pagination, text="Next", style="Light.TButton",
            command=lambda: self._change_page(1), state="disabled",
        )
        self.next_page_button.grid(row=0, column=2)

    def _build_output_card(self, parent):
        card = self._card(parent, (18, 14))
        card.grid(row=2, column=0, sticky="ew")
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text="Results are saved automatically", style="Card.TLabel", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        path_row = tk.Frame(card, bg=self.c["card"])
        path_row.grid(row=1, column=0, sticky="ew", pady=(7, 12))
        path_row.columnconfigure(0, weight=1)
        tk.Label(
            path_row, textvariable=self.output_dir, bg=self.c["input"], fg=self.c["muted"],
            anchor="w", padx=12, pady=9, font=("Segoe UI", 10)
        ).grid(row=0, column=0, sticky="ew")

        format_row = tk.Frame(card, bg=self.c["card"])
        format_row.grid(row=2, column=0, sticky="w", pady=(0, 12))
        tk.Label(
            format_row, text="OUTPUT FORMATS", bg=self.c["card"], fg=self.c["muted"],
            font=("Segoe UI", 8, "bold")
        ).pack(side="left", padx=(0, 12))
        for name in OUTPUT_FORMATS:
            tk.Checkbutton(
                format_row, text=name, variable=self.format_vars[name],
                command=self._format_selection_changed,
                bg=self.c["card"], fg=self.c["text"], activebackground=self.c["card"],
                activeforeground=self.c["text"], selectcolor=self.c["input"],
                highlightthickness=0, padx=7,
            ).pack(side="left")

        options_row = tk.Frame(card, bg=self.c["card"])
        options_row.grid(row=3, column=0, sticky="w", pady=(0, 12))
        tk.Checkbutton(
            options_row, text="Skip existing files", variable=self.skip_existing,
            bg=self.c["card"], fg=self.c["text"], activebackground=self.c["card"],
            activeforeground=self.c["text"], selectcolor=self.c["input"],
            highlightthickness=0,
        ).pack(side="left", padx=(0, 18))
        tk.Label(
            options_row, text="WORKERS", bg=self.c["card"], fg=self.c["muted"],
            font=("Segoe UI", 8, "bold")
        ).pack(side="left", padx=(0, 7))
        tk.Spinbox(
            options_row, from_=1, to=max(1, os.cpu_count() or 1),
            textvariable=self.worker_count, width=4,
            bg=self.c["input"], fg=self.c["text"], buttonbackground=self.c["border"],
            insertbackground=self.c["text"], relief="flat",
        ).pack(side="left")

        action_row = ttk.Frame(card, style="Card.TFrame")
        action_row.grid(row=4, column=0, sticky="ew")
        action_row.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(action_row, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 14))
        self.generate_button = ttk.Button(
            action_row, text="Convert images", style="Primary.TButton",
            command=self.start_generation, state="disabled"
        )
        self.generate_button.grid(row=0, column=1)
        self.cancel_button = ttk.Button(
            action_row, text="Cancel", style="Light.TButton",
            command=self.cancel_generation, state="disabled"
        )
        self.cancel_button.grid(row=0, column=2, padx=(8, 0))
        self.open_button = ttk.Button(
            action_row, text="Open results", style="Light.TButton", command=self.open_results,
            state="disabled"
        )
        self.open_button.grid(row=0, column=3, padx=(8, 0))

    def browse_images(self):
        paths = filedialog.askopenfilenames(
            title="Choose your images",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.ico *.gif *.bmp *.tif *.tiff"), ("All files", "*.*")],
        )
        if paths:
            self.add_paths(Path(path) for path in paths)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Choose a folder containing images")
        if folder:
            self.add_paths([Path(folder)])

    def add_paths(self, paths: Iterable[Path]):
        output = Path(self.output_dir.get()).expanduser().resolve()
        found: list[tuple[Path, Path]] = []
        unsupported = 0
        for raw_path in paths:
            path = raw_path.expanduser().resolve()
            if path.is_dir():
                found.extend((image, path) for image in find_images(path, output))
            elif path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                found.append((path, path))
            else:
                unsupported += 1

        existing = set(self.images)
        new_images = [path for path, _source in found if path not in existing]
        for path, source in found:
            if path not in existing:
                self.image_sources[path] = source
        self.images.extend(new_images)
        self.images.sort(key=lambda path: (path.name.lower(), str(path.parent).lower()))
        self.current_page = 0
        self._refresh_file_list()
        if new_images:
            self.status.set(f"Added {len(new_images)} image{'s' if len(new_images) != 1 else ''}. Ready to convert.")
        elif unsupported:
            self.status.set("That item is not a supported image. Try PNG, JPG, WebP, ICO, GIF, BMP or TIFF.")
        else:
            self.status.set("No new supported images were found.")

    def _refresh_file_list(self):
        for label in self.thumbnail_labels.values():
            label.destroy()
        self.file_thumbnails.clear()
        self.thumbnail_labels.clear()
        self.file_list.delete(*self.file_list.get_children())
        count = len(self.images)
        page_count = max(1, (count + IMAGES_PER_PAGE - 1) // IMAGES_PER_PAGE)
        self.current_page = min(self.current_page, page_count - 1)
        page_start = self.current_page * IMAGES_PER_PAGE
        page_end = min(page_start + IMAGES_PER_PAGE, count)
        displayed = self.images[page_start:page_end]
        for index, path in enumerate(displayed, start=page_start):
            try:
                size = format_file_size(path.stat().st_size)
            except OSError:
                size = "Unavailable"
            self.file_list.insert(
                "", "end", iid=str(index),
                values=(index + 1, path.name, size, ""),
            )
            try:
                with Image.open(path) as image:
                    thumbnail = square_image(image, 30)
                photo = ImageTk.PhotoImage(thumbnail)
                self.file_thumbnails[str(index)] = photo
                label = tk.Label(
                    self.file_list, image=photo, bg=self.c["input"],
                    borderwidth=0, cursor="hand2",
                )
                label.bind(
                    "<Button-1>",
                    lambda _event, item=str(index): self._select_thumbnail(item),
                )
                self.thumbnail_labels[str(index)] = label
            except (OSError, UnidentifiedImageError):
                pass
        if not count:
            self.file_list.insert(
                "", "end", iid="empty",
                values=("", "No images selected", "", ""),
                tags=("empty",),
            )
        summary = f"{count:,} image{'s' if count != 1 else ''} ready" if count else "No images selected"
        self.summary.set(summary)
        if count:
            self.page_summary.set(
                f"Showing {page_start + 1:,}\u2013{page_end:,} of {count:,}  \u2022  "
                f"Page {self.current_page + 1} of {page_count}"
            )
        else:
            self.page_summary.set("Page 1 of 1")
        self.previous_page_button.configure(
            state="normal" if self.current_page > 0 else "disabled"
        )
        self.next_page_button.configure(
            state="normal" if self.current_page < page_count - 1 else "disabled"
        )
        self._update_generate_button()
        if count:
            first_item = str(page_start)
            self.file_list.selection_set(first_item)
            self._show_preview(self.images[page_start])
            self.after_idle(self._position_file_thumbnails)
        else:
            self.preview.configure(image="", text="IMAGE", width=12, height=5)
            self.preview_photo = None

    def _change_page(self, offset: int):
        page_count = max(
            1, (len(self.images) + IMAGES_PER_PAGE - 1) // IMAGES_PER_PAGE
        )
        next_page = min(max(self.current_page + offset, 0), page_count - 1)
        if next_page == self.current_page:
            return
        self.current_page = next_page
        self.previous_page_button.configure(state="disabled")
        self.next_page_button.configure(state="disabled")
        self.page_summary.set("Loading page…")
        self.page_loading.pack(side="left", padx=(0, 8), before=self.page_status_label)
        self.page_loading.start(12)
        # Let Tk paint the loading state before decoding thumbnails for the page.
        self.after(30, self._finish_page_change)

    def _finish_page_change(self):
        try:
            self._refresh_file_list()
        finally:
            self.page_loading.stop()
            self.page_loading.pack_forget()

    def _scroll_file_list(self, *args):
        self.file_list.yview(*args)
        self.after_idle(self._position_file_thumbnails)

    def _schedule_thumbnail_positions(self, _event=None):
        self.after_idle(self._position_file_thumbnails)

    def _position_file_thumbnails(self):
        selected = set(self.file_list.selection())
        for item, label in self.thumbnail_labels.items():
            bounds = self.file_list.bbox(item, "view")
            if not bounds:
                label.place_forget()
                continue
            x, y, width, height = bounds
            label.configure(bg=self.c["primary"] if item in selected else self.c["input"])
            label.place(x=x, y=y, width=width, height=height)

    def _select_thumbnail(self, item: str):
        self.file_list.selection_set(item)
        self.file_list.focus(item)
        self._show_selected_preview()

    def remove_selected(self):
        selected = {
            int(item) for item in self.file_list.selection()
            if item.isdigit()
        }
        if not selected:
            self.status.set("Select an image in the list first.")
            return
        self.images = [path for index, path in enumerate(self.images) if index not in selected]
        self.image_sources = {
            path: source for path, source in self.image_sources.items()
            if path in self.images
        }
        self._refresh_file_list()
        self.status.set("Selected images removed.")

    def clear_images(self):
        self.images.clear()
        self.image_sources.clear()
        self.current_page = 0
        self._refresh_file_list()
        self.status.set("List cleared. Add another image when you are ready.")

    def _show_selected_preview(self, _event=None):
        selected = [item for item in self.file_list.selection() if item.isdigit()]
        if selected:
            self._show_preview(self.images[int(selected[0])])
        self._position_file_thumbnails()

    def _show_preview(self, path: Path):
        try:
            with Image.open(path) as image:
                preview = square_image(image, 92)
            self.preview_photo = ImageTk.PhotoImage(preview)
            self.preview.configure(image=self.preview_photo, text="", width=92, height=92)
        except (OSError, UnidentifiedImageError):
            self.preview.configure(image="", text="NO PREVIEW", width=12, height=5)
            self.preview_photo = None

    def _selected_formats(self) -> tuple[str, ...]:
        return tuple(
            name for name in OUTPUT_FORMATS if self.format_vars[name].get()
        )

    def _format_selection_changed(self):
        self._update_generate_button()
        formats = self._selected_formats()
        if formats:
            self.status.set(f"Output formats: {', '.join(formats)}")
        else:
            self.status.set("Select at least one output format.")

    def _update_generate_button(self):
        enabled = self.images and self._selected_formats() and not self.is_working
        self.generate_button.configure(state="normal" if enabled else "disabled")

    def start_generation(self):
        if self.is_working:
            return
        if not self.images:
            messagebox.showinfo("Add an image first", "Click Browse images and choose one or more images.")
            return
        formats = self._selected_formats()
        if not formats:
            messagebox.showinfo(
                "Choose an output format",
                "Select at least one format: PNG, JPG, WEBP, or ICO.",
            )
            return
        try:
            workers = max(1, min(int(self.worker_count.get()), os.cpu_count() or 1))
        except (TypeError, ValueError, tk.TclError):
            workers = min(4, max(1, (os.cpu_count() or 2) - 1))
            self.worker_count.set(workers)
        output = Path(self.output_dir.get()).resolve()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror(
                "Could not create the results folder",
                f"The app could not create converted_images in the current folder.\n\n{error}",
            )
            return

        self.is_working = True
        self.cancel_event.clear()
        self.progress["value"] = 0
        self.generate_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.open_button.configure(state="disabled")
        self.status.set(f"Starting {workers} worker{'s' if workers != 1 else ''}…")
        jobs = [(path, self.image_sources.get(path, path)) for path in self.images]
        threading.Thread(
            target=run_generation,
            args=(jobs, output, formats, workers, self.skip_existing.get(), self.work_queue, self.cancel_event),
            daemon=True,
        ).start()

    def cancel_generation(self):
        if not self.is_working:
            return
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.status.set("Cancelling after active conversions finish…")

    def _read_worker_messages(self):
        try:
            while True:
                message = self.work_queue.get_nowait()
                if message[0] == "progress":
                    _, current, total, name, completed, skipped = message
                    self.progress["value"] = current / total * 100
                    self.status.set(
                        f"Processed {current:,} of {total:,}: {name} "
                        f"({completed:,} converted, {skipped:,} skipped)"
                    )
                elif message[0] == "done":
                    _, completed, skipped, failures, output, cancelled = message
                    self._generation_finished(
                        completed, skipped, failures, output, cancelled
                    )
                elif message[0] == "notice":
                    self.status.set(message[1])
        except queue.Empty:
            pass
        self.after(100, self._read_worker_messages)

    def _generation_finished(
        self,
        completed: int,
        skipped: int,
        failures: list[tuple[Path, str]],
        output: Path,
        cancelled: int,
    ):
        self.is_working = False
        self.cancel_button.configure(state="disabled")
        self._update_generate_button()
        self.open_button.configure(state="normal" if completed or skipped else "disabled")
        if cancelled:
            messagebox.showinfo(
                "Conversion cancelled",
                f"Converted: {completed:,}\nSkipped: {skipped:,}\n"
                f"Failed: {len(failures):,}\nCancelled: {cancelled:,}",
            )
            self.status.set(
                f"Cancelled — {completed:,} converted, {skipped:,} skipped, "
                f"{cancelled:,} not processed."
            )
        elif failures:
            details = "\n".join(f"• {path.name}: {error}" for path, error in failures[:5])
            more = f"\n…and {len(failures) - 5} more." if len(failures) > 5 else ""
            messagebox.showwarning(
                "Finished with a few problems",
                f"Converted: {completed:,}\nSkipped: {skipped:,}\n\n"
                f"Could not process:\n{details}{more}",
            )
            self.status.set(
                f"Finished: {completed:,} converted, {skipped:,} skipped, "
                f"{len(failures):,} failed."
            )
        else:
            messagebox.showinfo(
                "Your images are ready",
                f"Converted: {completed:,}\nSkipped: {skipped:,}\n\nSaved in:\n{output}",
            )
            self.status.set(
                f"Done — {completed:,} converted, {skipped:,} skipped."
            )

    def open_results(self):
        output = Path(self.output_dir.get()).expanduser().resolve()
        if not output.exists():
            messagebox.showinfo("No results yet", "Convert your images first.")
            return
        try:
            os.startfile(output)  # Windows Explorer
        except OSError as error:
            messagebox.showerror("Could not open the folder", str(error))




