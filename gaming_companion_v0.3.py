import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

import pygame
import mss
import pyautogui

import win32gui
import win32con
import win32clipboard

import io
import time
import threading
from collections import deque


# ============================================================
# GAMING COMPANION V0.3
# ============================================================

# Game is on Monitor 2
MONITOR_NUMBER = 2

# Xbox Share / Capture button
SHARE_BUTTON = 11

# Fixed ChatGPT window title
CHATGPT_TITLE = "play_with_mia"

# Wait 5 seconds after pasting image
IMAGE_UPLOAD_WAIT = 10.0

# Preview size
PREVIEW_WIDTH = 820
PREVIEW_HEIGHT = 460

# Recent screenshot thumbnails
THUMB_WIDTH = 150
THUMB_HEIGHT = 90

MAX_CAPTURES = 5


# ============================================================
# MAIN APP
# ============================================================

class GamingCompanion:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "Gaming Companion V0.3"
        )

        self.root.geometry(
            "920x780"
        )

        self.root.minsize(
            850,
            700
        )

        self.running = True
        self.capture_busy = False

        self.current_image = None

        self.recent_captures = deque(
            maxlen=MAX_CAPTURES
        )

        self.thumbnail_photos = []

        # ====================================================
        # TITLE
        # ====================================================

        title = ttk.Label(
            root,
            text="🎮 Gaming Companion V0.3",
            font=("Segoe UI", 20, "bold")
        )

        title.pack(
            pady=(14, 4)
        )

        # ====================================================
        # MONITOR STATUS
        # ====================================================

        self.monitor_status = ttk.Label(
            root,
            text="🟡 Starting...",
            font=("Segoe UI", 11)
        )

        self.monitor_status.pack()

        # ====================================================
        # CHATGPT STATUS
        # ====================================================

        self.chatgpt_status = ttk.Label(
            root,
            text="🟡 Looking for Play_with_mia...",
            font=("Segoe UI", 10)
        )

        self.chatgpt_status.pack(
            pady=(3, 8)
        )

        # ====================================================
        # LIVE PREVIEW
        # ====================================================

        self.preview_frame = tk.Frame(
            root,
            bg="black",
            width=840,
            height=480
        )

        self.preview_frame.pack(
            padx=20,
            pady=5
        )

        self.preview_frame.pack_propagate(
            False
        )

        self.preview_label = tk.Label(
            self.preview_frame,
            bg="black"
        )

        self.preview_label.pack(
            expand=True,
            fill="both"
        )

        # ====================================================
        # INSTRUCTION
        # ====================================================

        self.instruction_label = ttk.Label(
            root,
            text="Xbox SHARE  →  Capture & Send to Mia",
            font=("Segoe UI", 12, "bold")
        )

        self.instruction_label.pack(
            pady=(10, 3)
        )

        # ====================================================
        # CONTROLLER STATUS
        # ====================================================

        self.controller_status = ttk.Label(
            root,
            text="🎮 Looking for Xbox controller...",
            font=("Segoe UI", 10)
        )

        self.controller_status.pack()

        # ====================================================
        # RECENT CAPTURES
        # ====================================================

        recent_title = ttk.Label(
            root,
            text="Recent Captures",
            font=("Segoe UI", 11, "bold")
        )

        recent_title.pack(
            pady=(12, 5)
        )

        self.thumbnail_frame = ttk.Frame(
            root
        )

        self.thumbnail_frame.pack(
            padx=15,
            pady=3
        )

        self.thumbnail_labels = []

        for i in range(MAX_CAPTURES):

            frame = tk.Frame(
                self.thumbnail_frame,
                width=155,
                height=95,
                bg="#222222"
            )

            frame.pack(
                side="left",
                padx=5
            )

            frame.pack_propagate(
                False
            )

            label = tk.Label(
                frame,
                text=str(i + 1),
                bg="#222222",
                fg="#888888"
            )

            label.pack(
                expand=True,
                fill="both"
            )

            self.thumbnail_labels.append(
                label
            )

        # ====================================================
        # MAIN STATUS
        # ====================================================

        self.status = ttk.Label(
            root,
            text="Starting Gaming Companion...",
            font=("Segoe UI", 10)
        )

        self.status.pack(
            pady=(12, 3)
        )

        quit_label = ttk.Label(
            root,
            text="ESC = Quit",
            font=("Segoe UI", 9)
        )

        quit_label.pack()

        # ====================================================
        # INITIALIZE CONTROLLER
        # ====================================================

        pygame.init()
        pygame.joystick.init()

        self.controller = None

        self.initialize_controller()

        # ====================================================
        # START CONTROLLER THREAD
        # ====================================================

        self.controller_thread = threading.Thread(
            target=self.controller_loop,
            daemon=True
        )

        self.controller_thread.start()

        # ====================================================
        # START LIVE PREVIEW
        # ====================================================

        self.update_preview()

        # ====================================================
        # START CHATGPT CHECK
        # ====================================================

        self.update_chatgpt_status()

        # ESC = Quit
        self.root.bind(
            "<Escape>",
            lambda event: self.close()
        )

    # ========================================================
    # INITIALIZE XBOX CONTROLLER
    # ========================================================

    def initialize_controller(self):

        count = (
            pygame.joystick.get_count()
        )

        if count == 0:

            self.controller_status.configure(
                text="🔴 Xbox controller not detected"
            )

            print(
                "Xbox controller not detected."
            )

            return

        self.controller = pygame.joystick.Joystick(
            0
        )

        self.controller.init()

        controller_name = (
            self.controller.get_name()
        )

        self.controller_status.configure(
            text=(
                "🟢 Controller connected — "
                + controller_name
            )
        )

        print()
        print(
            "================================"
        )

        print(
            "     Gaming Companion V0.3"
        )

        print(
            "================================"
        )

        print()
        print(
            "Controller:",
            controller_name
        )

        print(
            "Xbox Share Button:",
            SHARE_BUTTON
        )

        print(
            "Watching Monitor:",
            MONITOR_NUMBER
        )

        print(
            "ChatGPT Window:",
            CHATGPT_TITLE
        )

        print()

    # ========================================================
    # CONTROLLER LOOP
    # ========================================================

    def controller_loop(self):

        last_capture_time = 0

        while self.running:

            try:

                for event in pygame.event.get():

                    if (
                        event.type
                        == pygame.JOYBUTTONDOWN
                    ):

                        print(
                            "Controller button:",
                            event.button
                        )

                        if (
                            event.button
                            == SHARE_BUTTON
                        ):

                            now = time.time()

                            # Prevent accidental double trigger

                            if (
                                now
                                - last_capture_time
                                > 1.0
                            ):

                                last_capture_time = now

                                self.root.after(
                                    0,
                                    self.share_pressed
                                )

            except Exception as e:

                print(
                    "Controller error:",
                    e
                )

            time.sleep(
                0.01
            )

    # ========================================================
    # CAPTURE MONITOR 2
    # ========================================================

    def capture_monitor(self):

        try:

            with mss.mss() as sct:

                monitors = (
                    sct.monitors
                )

                if (
                    len(monitors)
                    <= MONITOR_NUMBER
                ):

                    print(
                        "Monitor not found:",
                        MONITOR_NUMBER
                    )

                    return None

                monitor = (
                    monitors[
                        MONITOR_NUMBER
                    ]
                )

                screenshot = (
                    sct.grab(
                        monitor
                    )
                )

                image = Image.frombytes(
                    "RGB",
                    screenshot.size,
                    screenshot.rgb
                )

                return image

        except Exception as e:

            print(
                "Monitor capture error:",
                e
            )

            return None

    # ========================================================
    # LIVE PREVIEW
    # ========================================================

    def update_preview(self):

        if not self.running:
            return

        image = (
            self.capture_monitor()
        )

        if image is not None:

            self.current_image = (
                image.copy()
            )

            preview = (
                image.copy()
            )

            preview.thumbnail(
                (
                    PREVIEW_WIDTH,
                    PREVIEW_HEIGHT
                )
            )

            photo = (
                ImageTk.PhotoImage(
                    preview
                )
            )

            self.preview_label.configure(
                image=photo
            )

            self.preview_label.image = (
                photo
            )

            self.monitor_status.configure(
                text=(
                    "🟢 Watching Monitor "
                    + str(
                        MONITOR_NUMBER
                    )
                )
            )

        else:

            self.monitor_status.configure(
                text=(
                    "🔴 Cannot read Monitor "
                    + str(
                        MONITOR_NUMBER
                    )
                )
            )

        self.root.after(
            500,
            self.update_preview
        )

    # ========================================================
    # FIND PLAY_WITH_MIA
    # ========================================================

    def find_chatgpt_window(self):

        matches = []

        def callback(
            hwnd,
            extra
        ):

            if not win32gui.IsWindowVisible(
                hwnd
            ):
                return

            title = (
                win32gui.GetWindowText(
                    hwnd
                )
            )

            if not title:
                return

            title_lower = (
                title.lower()
            )

            if (
                CHATGPT_TITLE
                in title_lower
            ):

                matches.append(
                    hwnd
                )

        win32gui.EnumWindows(
            callback,
            None
        )

        if matches:
            return matches[0]

        return None

    # ========================================================
    # CHATGPT STATUS
    # ========================================================

    def update_chatgpt_status(self):

        if not self.running:
            return

        hwnd = (
            self.find_chatgpt_window()
        )

        if hwnd:

            title = (
                win32gui.GetWindowText(
                    hwnd
                )
            )

            self.chatgpt_status.configure(
                text=(
                    "🟢 Play_with_mia connected — "
                    + title
                )
            )

        else:

            self.chatgpt_status.configure(
                text=(
                    "🔴 Play_with_mia "
                    "window not found"
                )
            )

        self.root.after(
            2000,
            self.update_chatgpt_status
        )

    # ========================================================
    # XBOX SHARE PRESSED
    # ========================================================

    def share_pressed(self):

        if self.capture_busy:
            return

        self.capture_busy = True

        print()
        print(
            "================================"
        )

        print(
            " Xbox SHARE pressed"
        )

        print(
            "================================"
        )

        self.status.configure(
            text="📸 Capturing game..."
        )

        # Fresh screenshot

        image = (
            self.capture_monitor()
        )

        if image is None:

            self.status.configure(
                text="❌ Screenshot failed"
            )

            self.capture_busy = False

            return

        # ====================================================
        # SAVE SCREENSHOT
        # ====================================================

        try:

            image.save(
                "game_screen.png"
            )

            print(
                "1. Screenshot saved."
            )

        except Exception as e:

            print(
                "Save error:",
                e
            )

        # ====================================================
        # RECENT CAPTURES
        # ====================================================

        self.recent_captures.appendleft(
            image.copy()
        )

        self.refresh_thumbnails()

        print(
            "2. Added to Recent Captures."
        )

        # ====================================================
        # COPY TO CLIPBOARD
        # ====================================================

        try:

            self.copy_image_to_clipboard(
                image
            )

            print(
                "3. Screenshot copied to clipboard."
            )

        except Exception as e:

            print(
                "Clipboard error:",
                e
            )

            self.status.configure(
                text=(
                    "⚠ Screenshot captured — "
                    "clipboard failed"
                )
            )

            self.capture_busy = False

            return

        # ====================================================
        # SEND TO CHATGPT
        # ====================================================

        self.status.configure(
            text=(
                "📋 Screenshot ready — "
                "sending to Mia..."
            )
        )

        self.root.after(
            150,
            self.send_to_chatgpt
        )

    # ========================================================
    # REFRESH THUMBNAILS
    # ========================================================

    def refresh_thumbnails(self):

        self.thumbnail_photos = []

        captures = list(
            self.recent_captures
        )

        for i in range(
            MAX_CAPTURES
        ):

            label = (
                self.thumbnail_labels[i]
            )

            if i < len(captures):

                thumb = (
                    captures[i].copy()
                )

                thumb.thumbnail(
                    (
                        THUMB_WIDTH,
                        THUMB_HEIGHT
                    )
                )

                photo = (
                    ImageTk.PhotoImage(
                        thumb
                    )
                )

                label.configure(
                    image=photo,
                    text=""
                )

                label.image = photo

                self.thumbnail_photos.append(
                    photo
                )

            else:

                label.configure(
                    image="",
                    text=str(i + 1)
                )

                label.image = None

    # ========================================================
    # WINDOWS CLIPBOARD
    # ========================================================

    def copy_image_to_clipboard(
        self,
        image
    ):

        output = io.BytesIO()

        image.convert(
            "RGB"
        ).save(
            output,
            "BMP"
        )

        # Remove BMP file header
        data = (
            output.getvalue()[14:]
        )

        output.close()

        for attempt in range(5):

            try:

                win32clipboard.OpenClipboard()

                win32clipboard.EmptyClipboard()

                win32clipboard.SetClipboardData(
                    win32con.CF_DIB,
                    data
                )

                win32clipboard.CloseClipboard()

                return

            except Exception:

                try:

                    win32clipboard.CloseClipboard()

                except Exception:
                    pass

                time.sleep(
                    0.1
                )

        raise RuntimeError(
            "Could not access Windows clipboard"
        )

    # ========================================================
    # SEND TO CHATGPT
    # ========================================================

    def send_to_chatgpt(self):

        try:

            # =================================================
            # FIND PLAY_WITH_MIA
            # =================================================

            hwnd = (
                self.find_chatgpt_window()
            )

            if hwnd is None:

                print(
                    "Play_with_mia not found."
                )

                self.status.configure(
                    text=(
                        "⚠ Play_with_mia "
                        "window not found"
                    )
                )

                return

            print(
                "4. Play_with_mia found."
            )

            print(
                "Window:",
                win32gui.GetWindowText(
                    hwnd
                )
            )

            # =================================================
            # RESTORE CHATGPT
            # =================================================

            win32gui.ShowWindow(
                hwnd,
                win32con.SW_RESTORE
            )

            time.sleep(
                0.3
            )

            # =================================================
            # BRING TO FOREGROUND
            # =================================================

            try:

                win32gui.SetForegroundWindow(
                    hwnd
                )

                print(
                    "5. ChatGPT brought to foreground."
                )

            except Exception as e:

                print(
                    "Foreground warning:",
                    e
                )

            time.sleep(
                1.0
            )

            # =================================================
            # PASTE SCREENSHOT
            # =================================================

            pyautogui.hotkey(
                "ctrl",
                "v"
            )

            print(
                "6. Ctrl+V sent."
            )

            self.status.configure(
                text=(
                    "🖼 Screenshot pasted — "
                    "waiting 5 seconds..."
                )
            )

            # =================================================
            # WAIT 5 SECONDS
            # =================================================

            print(
                "Waiting 5 seconds..."
            )

            time.sleep(
                IMAGE_UPLOAD_WAIT
            )

            # =================================================
            # PRESS ENTER
            # =================================================

            print(
                "7. Pressing ENTER..."
            )

            pyautogui.press(
                "enter"
            )

            print(
                "8. ENTER pressed."
            )

            time.sleep(
                1.0
            )

            # =================================================
            # FINISHED
            # =================================================

            self.status.configure(
                text=(
                    "✅ Screenshot sent to Mia — "
                    "keep talking 🎙"
                )
            )

            print()
            print(
                "================================"
            )

            print(
                " SCREENSHOT SEND ATTEMPT COMPLETE"
            )

            print(
                "================================"
            )

        except Exception as e:

            print(
                "Send error:",
                e
            )

            self.status.configure(
                text=(
                    "⚠ Screenshot captured — "
                    "send failed"
                )
            )

        finally:

            self.capture_busy = False

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.running = False

        try:

            pygame.quit()

        except Exception:
            pass

        self.root.destroy()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = GamingCompanion(
        root
    )

    root.protocol(
        "WM_DELETE_WINDOW",
        app.close
    )

    root.mainloop()