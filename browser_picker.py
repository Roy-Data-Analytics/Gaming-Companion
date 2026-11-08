"""English desktop picker for ChatGPT tabs reported by the browser bridge."""
import tkinter as tk
from tkinter import ttk, messagebox


def open_browser_picker(parent, bridge, on_selected=None):
    existing = getattr(parent, "_chatgpt_picker", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        return
    dialog = tk.Toplevel(parent)
    parent._chatgpt_picker = dialog
    dialog.title("Select ChatGPT Window")
    dialog.geometry("900x420")
    dialog.minsize(640, 320)
    dialog.transient(parent)
    body = ttk.Frame(dialog, padding=16)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="Choose the ChatGPT conversation for this game.",
              font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(body, text="All open ChatGPT tabs are listed, including tabs in other browser windows.",
              wraplength=820).pack(anchor="w", pady=(0, 10))
    frame = ttk.Frame(body)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=("window", "title", "url"), show="headings", selectmode="browse")
    for key, text, width in (("window", "Window", 140), ("title", "Conversation", 260), ("url", "URL", 400)):
        tree.heading(key, text=text)
        tree.column(key, width=width, minwidth=80)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    hint = tk.StringVar(value="Waiting for the browser extension...")
    ttk.Label(body, textvariable=hint, wraplength=820).pack(anchor="w", pady=10)
    buttons = ttk.Frame(body)
    buttons.pack(fill="x")
    entries = {}

    def refresh(schedule=False):
        if not dialog.winfo_exists():
            return
        selected = tree.selection()
        tabs = bridge.available_tabs()
        entries.clear()
        clients = {}
        for tab in tabs:
            clients.setdefault(tab["browserId"], len(clients) + 1)
            key = f"{tab['browserId']}:{tab['id']}"
            entries[key] = tab
            values = (f"Browser {clients[tab['browserId']]} / Window {tab['windowId']}", tab["title"], tab["url"])
            if tree.exists(key):
                tree.item(key, values=values)
            else:
                tree.insert("", "end", iid=key, values=values)
        for key in tree.get_children():
            if key not in entries:
                tree.delete(key)
        if selected and selected[0] in entries:
            tree.selection_set(selected[0])
        hint.set(bridge.discovery_status())
        if schedule:
            dialog.after(1000, lambda: refresh(True))

    def connect(event=None):
        selected = tree.selection()
        if not selected or selected[0] not in entries:
            messagebox.showinfo("Select ChatGPT Window", "Select a conversation from the list first.", parent=dialog)
            return
        tab = entries[selected[0]]
        try:
            title = bridge.select_target(tab["browserId"], tab["id"])
        except ValueError as error:
            messagebox.showerror("Unable to Connect", str(error), parent=dialog)
            return
        if on_selected:
            on_selected(title)
        dialog.destroy()

    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(buttons, text="Connect", command=connect).pack(side="right", padx=(8, 0))
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
    tree.bind("<Double-1>", connect)
    refresh(True)
