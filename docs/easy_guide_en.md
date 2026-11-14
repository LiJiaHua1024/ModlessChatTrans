# Modless Chat Trans - Easy Guide

Welcome to Modless Chat Trans! Feeling overwhelmed by all the settings? Don't worry—this guide is written to get
beginners up and running quickly.

In this guide, we use an advanced AI model like DeepSeek for translation. That means translations sound natural and
casual—great for in-game chat, slang, and memes!

Once configured with this guide, Modless Chat Trans will work like this:  
✅ **Understand other players:** Chat messages in other languages appear translated into English in the web interface.  
✅ **Let others understand you:** Type in English, and the tool translates it into your target server language and copies
it to your clipboard—just paste and send in Minecraft!

> **First launch in Chinese?** By default, the app UI opens in Simplified Chinese (`简体中文`). To switch it to English:
> click the **gear icon** (`设置`) at the very bottom of the left sidebar, pick **English** from the dropdown, click
> **保存** (Save) right next to it, and restart the program.

### 1. Set Your Game Log Path & Languages

1. Click the first menu on the left: **Message Capture**.
2. Check **Minecraft log location:**
    - If you use the **official Minecraft Launcher**, the default path already works—no change needed!
    - If you use a **third-party launcher** (Prism Launcher, MultiMC, Modrinth App, HMCL, PCL2, BakaXL, etc.): find the
      `logs` folder of your active Minecraft instance (if version isolation is enabled, it is typically inside
      `versions/<your-version>/logs`), copy its folder path, and paste it into **Minecraft log location:**.
3. Adjust your translation languages (defaults are set up for Chinese players, so English users should flip them):
    - Still in **Message Capture**: leave **Source language:** empty to auto-detect any language (or specify one such
      as `Simplified Chinese` or `Japanese`), and set **Target language:** to `English`.
    - Click the fourth menu on the left (**Send Message**): set **Source language:** to `English`, and **Target
      language:** to the language spoken on your server (e.g., `Simplified Chinese`, `Japanese`, `Spanish`).

### 2. Set Up an AI Translation Service

Using DeepSeek as an example (the same flow applies to OpenAI, Google Gemini, OpenRouter, etc.): register at
[DeepSeek Platform](https://platform.deepseek.com/api_keys), create an API key, and copy it.

- Click the second menu on the left (**Translation Service**) and stay on the default **Primary Model** tab.
- **Select service:** choose `DeepSeek`.
- **API Key:** paste your API key.
- **Model ID:** clear the pre-filled default text and type `deepseek-chat`.

**That's it—core setup is done!**

### 3. Start and Chat!

1. **Launch Minecraft first and wait until the game window appears** (especially important for older versions like 1.8.9).
2. Click **Start** at the bottom of the main left navigation (power button icon), then click **Save configuration and
   start**.
3. The web translation viewer opens automatically 1 second after starting! Drag it to your **secondary screen**, or open
   one of the **Web Access Links** displayed inside the Modless Chat Trans **Start** page on your phone/tablet browser
   (try the links from top to bottom until one connects).
4. Ready to reply in chat?
    - **[Recommended]** Type what you want to say in English into the input box at the bottom of the web page and click
      Send.
    - Shortly after, the web page will show `"Message translation completed. The result has been copied to the
      clipboard."`
    - Switch back to Minecraft, press `T` to open chat, press `Ctrl + V` to paste, and press Enter!

Now you can both follow international chat and talk smoothly with players on any server!

That's the end of the guide—have fun chatting! Want to try TTS voice read-aloud, Rage Mode, custom glossaries, or
blacklists next? Head back to the [README](../README_EN.md) for the full menu guide.
