"""Tkinter theme and shared visual styling."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from image_processing import COLORS
class ImageConverterTheme:
    """AdminLTE-inspired styling adapted from template.py."""

    def __init__(self, root: tk.Misc):
        self.c = COLORS
        root.configure(bg=self.c["bg"])
        root.option_add("*Font", ("Segoe UI", 10))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background=self.c["bg"])
        style.configure("Card.TFrame", background=self.c["card"])
        style.configure("Sidebar.TFrame", background=self.c["sidebar"])
        style.configure("TLabel", background=self.c["bg"], foreground=self.c["text"])
        style.configure("Card.TLabel", background=self.c["card"], foreground=self.c["text"])
        style.configure("Muted.TLabel", background=self.c["card"], foreground=self.c["muted"])
        style.configure(
            "Primary.TButton", background=self.c["primary"], foreground="white",
            borderwidth=0, padding=(18, 10), font=("Segoe UI", 10, "bold")
        )
        style.map("Primary.TButton", background=[("active", self.c["primary_hover"])])
        style.configure(
            "Light.TButton", background=self.c["input"], foreground=self.c["text"],
            borderwidth=0, padding=(13, 8)
        )
        style.map("Light.TButton", background=[("active", self.c["border"])])
        style.configure(
            "Files.Treeview", background=self.c["input"], fieldbackground=self.c["input"],
            foreground=self.c["text"], borderwidth=0, rowheight=38
        )
        style.configure(
            "Files.Treeview.Heading", background=self.c["card"], foreground=self.c["muted"],
            borderwidth=0, padding=(8, 8), font=("Segoe UI", 9, "bold")
        )
        style.map("Files.Treeview", background=[("selected", self.c["primary"])])
        style.configure(
            "TProgressbar", troughcolor=self.c["input"], background=self.c["success"],
            borderwidth=0, thickness=10
        )


