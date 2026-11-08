# ============================================================
# Gaming Companion - Stable Core 540p
#
# PURPOSE:
#   1. Preview selected monitor
#   2. F8 / Xbox Share -> screenshot
#   3. Resize screenshot to 960 x 540
#   4. Send one screenshot task to the paired browser extension
#   5. Confirm the matching upload transfer and commit responses
#   6. Press Enter in the exact editor (no Send-button detection)
#   7. Release the task immediately after Enter (no chat-history inspection)
#
# Windows / Python 3.13
# ============================================================

import os
import threading
import time
import tkinter as tk
from tkinter import ttk

import mss
import pygame
import win32api
import win32con

from PIL import Image, ImageTk
from companion_bridge import BrowserBridge
from browser_picker import open_browser_picker


# ============================================================
# CONFIG
# ============================================================

# Physical monitor index
# 1 = first monitor
# 2 = second monitor
MONITOR_INDEX = 2


# Screenshot resolution sent to ChatGPT
SEND_WIDTH = 960
SEND_HEIGHT = 540


# Keyboard screenshot button
HOTKEY_VK = win32con.VK_F8


# Xbox Share button ID
# Change this if your controller reports a different button number
XBOX_SHARE_BUTTON = 11


# Preview refresh
PREVIEW_INTERVAL_MS = 200


# Trigger debounce
HOTKEY_DEBOUNCE = 0.50




# Save last screenshot for debugging
SAVE_DEBUG_SCREENSHOT = True

DEBUG_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "debug"
)

DEBUG_FILE = os.path.join(
    DEBUG_FOLDER,
    "last_capture.jpg"
)


PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))
browser_bridge = BrowserBridge(PROJECT_FOLDER)
browser_bridge.start()


# ============================================================
# GLOBAL STATE
# ============================================================

state_lock = threading.Lock()

is_busy = False
running = True

last_f8_state = False
last_trigger_time = 0.0

controller = None


# ============================================================
# TKINTER
# ============================================================

root = tk.Tk()

root.title(
    "Gaming Companion - Stable Core 540p"
)

root.geometry(
    "820x740"
)

root.minsize(
    600,
    500
)


status_var = tk.StringVar(
    value="READY"
)

chatgpt_var = tk.StringVar(
    value="Checking..."
)

controller_var = tk.StringVar(
    value="Checking..."
)

monitor_var = tk.StringVar(
    value=f"Monitor {MONITOR_INDEX}"
)

resolution_var = tk.StringVar(
    value=f"{SEND_WIDTH} x {SEND_HEIGHT}"
)


# ============================================================
# UI
# ============================================================

main_frame = ttk.Frame(
    root,
    padding=12
)

main_frame.pack(
    fill="both",
    expand=True
)


title_label = ttk.Label(
    main_frame,
    text="Gaming Companion — Stable Core",
    font=(
        "Segoe UI",
        18,
        "bold"
    )
)

title_label.pack(
    pady=(0, 10)
)

connection_bar = ttk.Frame(main_frame)
connection_bar.pack(fill="x", pady=(0, 8))
ttk.Button(
    connection_bar,
    text="Select ChatGPT Window",
    command=lambda: open_browser_picker(
        root, browser_bridge,
        on_selected=lambda title: status_var.set(f"Connecting to: {title}"),
    ),
).pack(side="left")
ttk.Label(connection_bar, text="Choose a conversation for each game.").pack(side="left", padx=12)


preview_label = ttk.Label(
    main_frame,
    anchor="center"
)

preview_label.pack(
    fill="both",
    expand=True,
    pady=5
)


info_frame = ttk.Frame(
    main_frame
)

info_frame.pack(
    fill="x",
    pady=10
)
info_frame.columnconfigure(1, weight=1)


ttk.Label(
    info_frame,
    text="Monitor:",
    font=(
        "Segoe UI",
        10,
        "bold"
    )
).grid(
    row=0,
    column=0,
    sticky="w",
    padx=5,
    pady=3
)


ttk.Label(
    info_frame,
    textvariable=monitor_var
).grid(
    row=0,
    column=1,
    sticky="w",
    padx=5
)


ttk.Label(
    info_frame,
    text="Send Resolution:",
    font=(
        "Segoe UI",
        10,
        "bold"
    )
).grid(
    row=1,
    column=0,
    sticky="w",
    padx=5,
    pady=3
)


ttk.Label(
    info_frame,
    textvariable=resolution_var
).grid(
    row=1,
    column=1,
    sticky="w",
    padx=5
)


ttk.Label(
    info_frame,
    text="ChatGPT:",
    font=(
        "Segoe UI",
        10,
        "bold"
    )
).grid(
    row=2,
    column=0,
    sticky="w",
    padx=5,
    pady=3
)


ttk.Label(
    info_frame,
    textvariable=chatgpt_var,
    wraplength=580,
).grid(
    row=2,
    column=1,
    sticky="w",
    padx=5
)


ttk.Label(
    info_frame,
    text="Controller:",
    font=(
        "Segoe UI",
        10,
        "bold"
    )
).grid(
    row=3,
    column=0,
    sticky="w",
    padx=5,
    pady=3
)


ttk.Label(
    info_frame,
    textvariable=controller_var
).grid(
    row=3,
    column=1,
    sticky="w",
    padx=5
)


ttk.Label(
    info_frame,
    text="Status:",
    font=(
        "Segoe UI",
        10,
        "bold"
    )
).grid(
    row=4,
    column=0,
    sticky="w",
    padx=5,
    pady=3
)


status_label = ttk.Label(
    info_frame,
    textvariable=status_var,
    wraplength=580,
    font=(
        "Segoe UI",
        11,
        "bold"
    )
)

status_label.grid(
    row=4,
    column=1,
    sticky="w",
    padx=5
)


instruction_label = ttk.Label(
    main_frame,
    text=(
        "F8 / Xbox Share = Screenshot & Send\n"
        "Use Select ChatGPT Window to choose your game conversation"
    ),
    justify="center",
    font=(
        "Segoe UI",
        11
    )
)

instruction_label.pack(
    pady=(5, 10)
)


# ============================================================
# SAFE UI UPDATE
# ============================================================

def ui_set(variable, text):

    try:

        root.after(
            0,
            lambda: variable.set(text)
        )

    except Exception:

        pass


# ============================================================
# CAPTURE GAME MONITOR
# ============================================================

def capture_game_monitor():

    with mss.mss() as sct:

        monitors = sct.monitors


        if MONITOR_INDEX >= len(monitors):

            raise RuntimeError(
                f"Monitor {MONITOR_INDEX} does not exist. "
                f"Available physical monitors: "
                f"{len(monitors) - 1}"
            )


        monitor = monitors[
            MONITOR_INDEX
        ]


        raw = sct.grab(
            monitor
        )


        image = Image.frombytes(
            "RGB",
            raw.size,
            raw.rgb
        )


        # -----------------------------------------
        # Resize before sending to ChatGPT
        # -----------------------------------------

        image = image.resize(
            (
                SEND_WIDTH,
                SEND_HEIGHT
            ),
            Image.Resampling.LANCZOS
        )


        return image


# ============================================================
# DEBUG SAVE
# ============================================================

def save_debug_image(image):

    if not SAVE_DEBUG_SCREENSHOT:

        return


    try:

        os.makedirs(
            DEBUG_FOLDER,
            exist_ok=True
        )


        image.save(
            DEBUG_FILE,
            "JPEG",
            quality=90
        )


        print(
            "Debug screenshot saved:",
            DEBUG_FILE
        )


    except Exception as e:

        print(
            "Debug save error:",
            e
        )


# ============================================================
# BROWSER EXTENSION SCREENSHOT PIPELINE
# ============================================================

def screenshot_and_send():
    global is_busy
    with state_lock:
        if is_busy:
            print("Ignored trigger: a screenshot task is already active.")
            return
        is_busy = True
    try:
        if not browser_bridge.connected:
            raise RuntimeError("Connect the Gaming Companion browser extension first")
        ui_set(status_var, "CAPTURING")
        image = capture_game_monitor()
        save_debug_image(image)
        print("Screenshot captured:", image.size)
        def progress(state, detail):
            ui_set(status_var, f"{state}: {detail}" if state == "UPLOADING" else state)
        job_id = browser_bridge.submit(image, callback=progress)
        ui_set(status_var, "UPLOAD COMPLETE — BACKGROUND SEND TRIGGERED")
        print("Image uploaded; background Send triggered:", job_id)
    except Exception as exc:
        print("PIPELINE ERROR:", str(exc))
        ui_set(status_var, f"Error: {exc}")
    finally:
        with state_lock:
            is_busy = False


# ============================================================
# TRIGGER
# ============================================================


def trigger_send():

    global last_trigger_time


    now = time.time()


    if (
        now
        - last_trigger_time
        < HOTKEY_DEBOUNCE
    ):

        return


    last_trigger_time = now


    threading.Thread(
        target=screenshot_and_send,
        daemon=True
    ).start()


# ============================================================
# KEYBOARD LOOP
# ============================================================

def keyboard_loop():

    global last_f8_state


    while running:

        try:

            pressed = bool(
                win32api.GetAsyncKeyState(
                    HOTKEY_VK
                )
                & 0x8000
            )


            if (
                pressed
                and not last_f8_state
            ):

                print(
                    "F8 pressed."
                )

                trigger_send()


            last_f8_state = pressed


        except Exception as e:

            print(
                "Keyboard error:",
                e
            )


        time.sleep(
            0.03
        )


# ============================================================
# CONTROLLER
# ============================================================

def initialize_controller():

    global controller


    try:

        pygame.init()

        pygame.joystick.init()


        count = (
            pygame.joystick.get_count()
        )


        if count == 0:

            controller = None

            ui_set(
                controller_var,
                "NOT CONNECTED"
            )


            print(
                "No controller detected."
            )


            return


        controller = (
            pygame.joystick.Joystick(
                0
            )
        )


        controller.init()


        name = (
            controller.get_name()
        )


        ui_set(
            controller_var,
            f"CONNECTED — {name}"
        )


        print(
            "Controller connected:",
            name
        )


        print(
            "Buttons:",
            controller.get_numbuttons()
        )


    except Exception as e:

        controller = None


        ui_set(
            controller_var,
            "ERROR"
        )


        print(
            "Controller init error:",
            e
        )


def controller_loop():

    global controller


    initialize_controller()


    previous_buttons = {}


    while running:

        try:

            pygame.event.pump()


            if controller is None:

                if (
                    pygame.joystick.get_count()
                    > 0
                ):

                    initialize_controller()


                time.sleep(
                    1
                )

                continue


            button_count = (
                controller.get_numbuttons()
            )


            for button_id in range(
                button_count
            ):

                current = (
                    controller.get_button(
                        button_id
                    )
                )


                previous = (
                    previous_buttons.get(
                        button_id,
                        0
                    )
                )


                if (
                    current
                    and not previous
                ):

                    print(
                        "Controller button pressed:",
                        button_id
                    )


                    if (
                        button_id
                        == XBOX_SHARE_BUTTON
                    ):

                        print(
                            "Xbox Share trigger."
                        )

                        trigger_send()


                previous_buttons[
                    button_id
                ] = current


        except Exception as e:

            print(
                "Controller error:",
                e
            )


            controller = None


            ui_set(
                controller_var,
                "DISCONNECTED"
            )


            time.sleep(
                1
            )


        time.sleep(
            0.02
        )


# ============================================================
# CHATGPT STATUS LOOP
# ============================================================

def chatgpt_status_loop():
    while running:
        status = (f"Connected: {browser_bridge.tab_title}" if browser_bridge.connected
                  else "Waiting for selected ChatGPT window")
        ui_set(chatgpt_var, status)
        time.sleep(1)


# ============================================================
# LIVE PREVIEW
# ============================================================

def update_preview():

    if not running:

        return


    try:

        with mss.mss() as sct:

            monitors = (
                sct.monitors
            )


            if (
                MONITOR_INDEX
                < len(monitors)
            ):

                monitor = monitors[
                    MONITOR_INDEX
                ]


                raw = sct.grab(
                    monitor
                )


                img = Image.frombytes(
                    "RGB",
                    raw.size,
                    raw.rgb
                )


                preview_width = 700


                ratio = (
                    preview_width
                    / img.width
                )


                preview_height = int(
                    img.height
                    * ratio
                )


                if preview_height > 390:

                    preview_height = 390


                    ratio = (
                        preview_height
                        / img.height
                    )


                    preview_width = int(
                        img.width
                        * ratio
                    )


                img = img.resize(
                    (
                        preview_width,
                        preview_height
                    ),
                    Image.Resampling.LANCZOS
                )


                tk_img = (
                    ImageTk.PhotoImage(
                        img
                    )
                )


                preview_label.configure(
                    image=tk_img
                )


                preview_label.image = (
                    tk_img
                )


    except Exception as e:

        print(
            "Preview error:",
            e
        )


    root.after(
        PREVIEW_INTERVAL_MS,
        update_preview
    )


# ============================================================
# MANUAL TEST BUTTON
# ============================================================

def manual_test():

    trigger_send()


test_button = ttk.Button(
    main_frame,
    text="TEST SCREENSHOT & SEND",
    command=manual_test
)

test_button.pack(
    pady=5
)


# ============================================================
# CLOSE
# ============================================================

def on_close():

    global running


    running = False
    browser_bridge.close()


    try:

        pygame.quit()

    except Exception:

        pass


    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    on_close
)


# ============================================================
# THREADS
# ============================================================

threading.Thread(
    target=keyboard_loop,
    daemon=True
).start()


threading.Thread(
    target=controller_loop,
    daemon=True
).start()


threading.Thread(
    target=chatgpt_status_loop,
    daemon=True
).start()


root.after(
    200,
    update_preview
)


# ============================================================
# START
# ============================================================

print()
print(
    "=========================================="
)

print(
    "Gaming Companion - Stable Core 540p"
)

print(
    "=========================================="
)

print(
    "ChatGPT connection:",
    "Select the ChatGPT window in the desktop app; the extension runs in the background"
)

print(
    "Monitor:",
    MONITOR_INDEX
)

print(
    "Send Resolution:",
    f"{SEND_WIDTH} x {SEND_HEIGHT}"
)

print(
    "Keyboard:",
    "F8"
)

print(
    "Xbox Share button ID:",
    XBOX_SHARE_BUTTON
)

print(
    "Debug screenshot:",
    DEBUG_FILE
)

print(
    "=========================================="
)

print()


root.mainloop()
