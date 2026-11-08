# SteamGamingCompanion

A Windows companion for Steam games. Press F8 or the Xbox controller’s Share button to capture a 960 × 540 screenshot and send it to a ChatGPT conversation you select.

## Setup

1. Install Python 3.13 with Tkinter and add Python to PATH. Run `setup_dependencies.bat`.
2. Close any other Gaming Companion instance, then run `Start_SteamGamingCompanion.bat`. The desktop app generates the local browser pairing on first launch.
3. Open `chrome://extensions` or `edge://extensions`, enable **Developer mode**, then choose **Load unpacked** and select this project’s `browser_extension` folder. Keep one copy of the extension enabled per browser profile. If you loaded it before starting the desktop app, reload the extension once.
4. Open your ChatGPT conversation in that browser profile. In the desktop app, click **Select ChatGPT Window**, choose the conversation, and click **Connect**.
5. With the selected ChatGPT draft empty, press F8 or Xbox Share in-game to capture and send one screenshot.

The desktop bridge listens on `127.0.0.1:8765`. Pairing credentials, the selected conversation, and diagnostic files are generated locally and ignored by Git.

## Tests

Run these commands from the project folder. The JavaScript tests require Node.js.

```powershell
python -m unittest discover -s tests -p "test_*.py"
node --test tests/*.test.mjs
```

For browser troubleshooting, see [Desktop Connection](docs/Browser_Bridge_Setup.md).
