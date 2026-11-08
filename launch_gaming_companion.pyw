"""Desktop entry point: keep the console hidden and preserve diagnostic output."""
import os
from pathlib import Path
import runpy
import sys
import traceback

folder = Path(__file__).resolve().parent
os.chdir(folder)
log_folder = folder / "debug"
log_folder.mkdir(exist_ok=True)
with (log_folder / "desktop_launch.log").open("a", encoding="utf-8", buffering=1) as log:
    sys.stdout = log
    sys.stderr = log
    try:
        runpy.run_path(str(folder / "ScreenShot_StableCore.py"), run_name="__main__")
    except Exception:
        traceback.print_exc()
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Gaming Companion",
            "Gaming Companion could not start. If it is already open, use the existing window.\n\n"
            "Details were saved to debug/desktop_launch.log.",
            parent=root,
        )
        root.destroy()
