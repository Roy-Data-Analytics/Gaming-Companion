# 🚨 CUT THE SHIT — READ THIS FIRST

## 🇺🇸 English

**Want to use it? Just read this.**

This small program watches your game screen.

When you press a button on your controller, it takes a screenshot and sends it to ChatGPT.

Then ChatGPT can **see what you are seeing**.

You keep playing. You keep talking.

It feels like you have a friend sitting next to you, watching the game and talking with you.

That's it.

**I will upload a video showing you how to set it up and use it.**

---

## 🇨🇳 中文

**想用这个？看这里就够了。**

这个小程序会看着你的游戏画面。

你按一下手柄上的按钮，它就会自动截图，然后把图片发给 ChatGPT。

这样 ChatGPT 就可以**看到你正在看到的东西**。

你继续玩游戏，继续和它聊天就行。

就像有一个朋友坐在你旁边，一边看你玩游戏，一边和你聊天。

就这么简单。

**我会上传一个视频，教你怎么安装和使用。**









Read this if you want to know how this idea was developed. I guess nobody wants to read it, hahaha. It’s mostly just for my own record anyway...

# 🎮 Gaming Companion

### An AI companion that can see your game and talk with you while you play.

Gaming Companion is an experimental project exploring a simple idea:

> **What if AI could sit next to you like a friend while you play a game?**

Instead of stopping the game, searching for walkthroughs, typing character names, or explaining where you are in the story, Gaming Companion allows you to show the AI what you are seeing with a single controller button.

Press the **Xbox Share button**, and the current game screen is automatically captured and sent into an ongoing ChatGPT conversation.

Then just talk.

---

## 💡 The Idea

Traditional game assistants usually work like this:

**Stop playing → Search → Read → Return to the game**

Gaming Companion tries a different approach:

**Play → Show → Talk → Keep playing**

The goal is not simply to build another walkthrough tool.

The goal is to create the feeling that an AI friend is sitting next to you, experiencing the game with you.

You might ask:

- "Who is this character?"
- "What did he just say?"
- "Why are they fighting?"
- "What does this English expression mean?"
- "What happened before this mission?"
- "Is this based on real history?"
- "Don't spoil anything — just explain what I already know."

The AI can use the current game screen together with the ongoing conversation to understand what you are talking about.

---

# 🚀 Current Version — V0.3

Gaming Companion V0.3 is a working prototype for PC gaming.

### Current workflow

```text
              🎮 Xbox Controller
                      │
                Press SHARE
                      │
                      ▼
              📸 Capture Game
                  Monitor 2
                      │
                      ▼
             🖼 Gaming Companion
               Python Application
                      │
                      ▼
              📋 Windows Clipboard
                      │
                      ▼
              🌐 ChatGPT Browser
                      │
                 Ctrl + V
                      │
               Wait for upload
                      │
                  Press Enter
                      │
                      ▼
              🤖 AI sees the game
                      │
                      ▼
              🎙 Continue talking
```

The player does not need to leave the controller.

One button gives the AI "eyes."

---

# 🧠 Design Philosophy

One of the biggest discoveries during development was that the prototype did **not** need to rebuild an entire voice assistant.

Originally, the project considered adding:

- Speech recognition
- Whisper
- Text-to-speech
- Custom voice interaction
- Additional AI APIs

But ChatGPT already provides the conversation layer.

So the architecture became much simpler:

### ChatGPT Voice

**Brain + Ears + Mouth**

### Gaming Companion

**Eyes**

Gaming Companion focuses on giving the AI visual context from the game.

---

# ✨ Current Features

### 🎮 Xbox Controller Integration

Press the Xbox **Share / Capture button** to trigger Gaming Companion.

No keyboard is required during gameplay.

### 📸 Automatic Game Capture

Gaming Companion captures the game running on the second monitor.

### 👀 Live Game Preview

The desktop application displays a live preview of the monitored game screen.

### 🖼 Recent Captures

The five most recent screenshots are displayed inside the Gaming Companion interface.

### 📋 Automatic Clipboard Transfer

Captured screenshots are automatically converted and copied to the Windows clipboard.

### 🌐 Automatic ChatGPT Detection

Gaming Companion searches for the active ChatGPT browser window used for the gaming conversation.

### 🤖 Automatic Image Submission

The screenshot is pasted into the existing ChatGPT conversation and submitted automatically after waiting for the image upload.

### 🎙 Voice Conversation

The player can continue talking naturally with ChatGPT Voice while playing.

---

# 🛠 Development History

## V0.1 — Give the AI Eyes

The first prototype used:

```text
PS5
 ↓
TV
 ↓
iPhone Camera
 ↓
Camo Studio
 ↓
Windows PC
 ↓
Gaming Companion
 ↓
Screenshot
 ↓
ChatGPT
```

An iPhone camera pointed at the television allowed the prototype to capture console gameplay.

This proved the basic idea:

> An AI companion becomes much more useful when it can see what the player is seeing.

---

## V0.2 — One-Button Visual Context

The next version automated the screenshot workflow.

A single action could:

1. Capture the game
2. Copy the image
3. Find the ChatGPT browser window
4. Paste the screenshot
5. Prepare the AI conversation

This significantly reduced the interruption to gameplay.

---

## V0.3 — Controller + PC Gaming

V0.3 moved the prototype to direct PC screen capture.

Major improvements:

- Direct monitor capture using `mss`
- Xbox controller support using `pygame`
- Share button detection
- Live game preview
- Recent screenshot history
- Automatic Windows clipboard handling
- Automatic ChatGPT window detection
- Automatic screenshot pasting
- Automatic submission
- Voice conversation continues alongside gameplay

At this stage, Gaming Companion begins to feel less like a screenshot utility and more like an actual companion.

---

# 💻 Current Environment

The prototype is currently developed and tested with:

- Windows 11
- Python 3
- Xbox Controller
- Dual-monitor PC setup
- Google Chrome
- ChatGPT
- ChatGPT Voice

Main Python libraries:

```text
pygame
mss
Pillow
PyAutoGUI
pywin32
```

---

# ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/Roy-Data-Analytics/Gaming-Companion.git
```

Enter the project folder:

```bash
cd Gaming-Companion
```

Install the required Python packages:

```bash
pip install pygame mss pillow pyautogui pywin32
```

Run Gaming Companion:

```bash
python gaming_companion_v0.3.py
```

---

# ⚠️ Prototype Limitations

V0.3 is an early experimental prototype.

The current version assumes:

- Windows
- Game running on Monitor 2
- Xbox controller
- ChatGPT open in a browser
- A specific ChatGPT conversation/window title
- Sufficient upload time before automatically submitting the screenshot

Some settings currently need to be changed directly in the Python script.

The project is not yet designed as a plug-and-play application for other users.

---

# 🗺 Roadmap

### ✅ V0.1
Camera-based game observation

### ✅ V0.2
One-button screenshot workflow

### ✅ V0.3
PC capture + Xbox controller + automatic ChatGPT visual context

### 🔨 V0.4
Planned improvements:

- Better configuration
- Automatic monitor selection
- Improved ChatGPT window detection
- More reliable image submission
- Game/session detection
- Cleaner user interface
- How to make it happen with PS5 Games 

### 🔮 Future

Possible future features include:

- Game progress memory
- Spoiler-aware responses
- Character and story tracking
- Automatic game recognition
- English-learning mode
- Historical and cultural explanations
- Session summaries
- Smarter screenshot triggering
- Optional console support
- More natural multimodal interaction

---

# 🎯 Long-Term Vision

Gaming Companion is not intended to play the game for you.

It is intended to **experience the game with you**.

The long-term goal is an AI companion that understands:

- what game you are playing,
- where you are in the story,
- which characters you have met,
- what you already know,
- what you do not want spoiled,
- and what kinds of things you enjoy discussing.

Eventually, interacting with the companion should feel less like asking a search engine a question and more like turning to a friend sitting next to you and saying:

> **"Mia, did you see that?"**

---

## 🧪 Project Status

**Experimental prototype — actively developing**

Current milestone: **V0.3**

---

## 👤 Creator

Created as a personal AI + gaming experiment by **Roy**.

This project is being built iteratively while actually playing games and testing what makes an AI gaming companion feel natural.

---

## ⭐ Why This Project Exists

Games are experiences.

Sometimes the best part isn't finding the correct answer.

It's having someone there to say:

> **"Whoa. Did you see that?"**

That's the experience Gaming Companion is trying to build.
