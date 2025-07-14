# ModlessChatTrans

## Real-Time Minecraft Chat Translator Without Mods

---

English | [简体中文](README_CN.md)

Tired of not understanding foreign language messages from other players in Minecraft? **No Mods Required!**
ModlessChatTrans can help! This lightweight tool allows you to communicate with players from around the world without
leaving the game.

**ModlessChatTrans** is a tool that provides real-time chat translation for Minecraft players **without requiring any
mods**.

### Features

- **No Mods Required**: No need to install any mods. ModlessChatTrans reads other players' chat messages from Minecraft
  log files and your own messages from the clipboard
- **Real-time Translation**: Translates chat messages at lightning speed, so you can communicate effortlessly even
  during intense PvP
- **High-quality Translations**: Supports multiple large language models for translation, including OpenAI, Anthropic
  Claude, Google Gemini, DeepSeek, etc., ensuring accuracy and fluency, even for gaming abbreviations and slang
- **Multiple Translation Services**: Supports various translation services: LLM translation, DeepL Translate, Bing
  Translate, Google Translate, Yandex Translate, Alibaba Translate, Caiyun Translate, Youdao Translate, Sogou Translate,
  Iflyrec Translate
- **Multiple Presentation Methods**: Supports three ways to display other players' translated messages: CustomTkinter
  GUI interface, Text-to-Speech output, Web interface
- **Glossary**: Define custom translation rules for specific terms or patterns, supporting variable parsing and regex
  constraints
    - [English User Guide](./docs/glossary_guide_en.md)
- **Multi-language Interface**: Supports 9 interface languages, including Simplified Chinese, English, Japanese, French,
  German, Spanish, Korean, Russian, Brazilian Portuguese, Traditional Chinese
- **Smart Cache**: Built-in translation cache mechanism to reduce redundant translations and improve response speed
- **Minecraft Formatting Code Rendering**: Full support for Minecraft chat formatting in web interface, including
  colors, styles, etc
- **Multi-theme Web Interface**: Provides 6 beautiful themes, including Default, Material, Fluent, Skeuomorphic,
  Cyberpunk, Retro Terminal, etc
- **Easy to Use**: Download and run the .exe file, configurations are automatically saved and loaded

### Functionality

- **Quick Translation of Other Players' Messages**: Captures and translates chat messages in real-time
- **Translate and Send Your Own Messages**: Automatically translates your messages to the target language before sending
    - **Capture Messages via Clipboard**: The program automatically captures your messages and translates them to the
      target language before sending
    - **Send Messages via Web Interface**: Effectively avoids the problem of input methods not displaying when the game
      is in fullscreen

### How to Use

We provide two ways to use the tool: a ready-to-use `.exe` file for regular Windows users, and running from source code
for Linux and advanced users.

---

#### Method 1: Direct Run (for Windows Users)

This is the simplest method, recommended for all Windows users.

1. Go to the project's [**Releases page**](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) and
   download the latest `.exe` file
2. Run the downloaded `.exe` file directly, the program will start
3. Choose the interface language in the bottom left corner of the program
4. Fill in the required information:

- **Minecraft Log Folder**: Location of Minecraft game logs (usually the logs folder)
- **Translation Result Presentation Method**: How to display translation results
    - **GUI Interface**: Creates a simple GUI interface to display translation results (Max Messages: maximum number
      of messages shown in the message window)
    - **Voice**: Uses text-to-speech to announce translation results
    - **Web Interface**: Launches a beautiful web page that can receive/send messages. Most electronic devices with
      browsers can now serve as translation display terminals (HTTP Port: port number for the HTTP server)
- **Source Language (Auto-detect if blank)**: Source language of other players' messages (leave blank for
  auto-detection)
- **Target Language**: Target language for translations
- **Translation Service Selection**: Choose the translation service to use
    - **LLM Translation**: Supports OpenAI, Anthropic Claude, Google Gemini, DeepSeek, etc
    - **Traditional Translation Services**: Supports DeepL, Bing, Google, Yandex, Alibaba, Caiyun, Youdao, Sogou,
      Iflyrec, etc
- **LLM Options**:
    - **API URL**: LLM API address (OpenAI-compatible API format)
    - **API Key**: LLM API key
    - **Model**: LLM model name (For model names,
      see: [OpenAI](https://platform.openai.com/docs/models) | [Gemini](https://ai.google/get-started/our-models) | [SiliconFlow](https://cloud.siliconflow.cn/models) | [Deepseek](https://api-docs.deepseek.com/zh-cn/quick_start/pricing) | [Anthropic](https://docs.anthropic.com/en/docs/about-claude/models/all-models))
- **Traditional Translation Service Options**:
    - **I have an API key**: Whether to use your own API key
        - **API Key**: API key
- **Translate Own Messages**: Whether to translate your own messages (only for messages captured from clipboard)
    - **Source Language for Your Messages**: Source language of your own messages
    - **Target Language for Your Messages**: Target language for your own messages
- **Always on top**: Whether to keep the GUI window always on top
- **More Settings**: Hover over options for more information
    - **Enable Translation Quality Optimization**: Improve translation quality by enabling explicit chain of thought,
      but will increase latency and consume more tokens
    - **Enable High Version Fix**: If chat messages cannot be captured, try enabling this
    - **Translate System Messages**: When disabled, will not translate chat messages without names
    - **Replace Garbled Characters**: Replace all garbled characters with Minecraft formatting codes
    - **Log Encoding**: Manually specify log encoding. If you encounter garbled text or cannot capture messages, try
      changing this to `utf-8`/`gbk`. Leave blank for auto-detection
    - **Glossary**: Configure custom translation rules, supporting variable parsing and regex constraints
        - [English User Guide](./docs/glossary_guide_en.md)

5. Click "Start" and launch Minecraft to begin playing
6. **Receiving Messages**: When other players send messages, the program will display translations according to your
   chosen display method
   **Sending Messages**:
    1. Capture content:  
       a. After typing in the Minecraft chat box, press `Ctrl + A` to select all, then `Ctrl + C` to copy (or `Ctrl + X`
       to cut)  
       b. [**Recommended**] If you selected "Web Interface" as the display method, you can also enter content in the web
       interface and
       click the "Send" button to send messages
    2. The program will translate your message and copy it to the clipboard, then press `Ctrl + V` to paste the
       translated content back to the chat box, and press `Enter` to send

---

#### Method 2: Run from Source Code (for Linux / Advanced Users)

This method is suitable for all Linux users, as well as Windows advanced users who want to experience the latest
features or modify the code themselves.

**Step 1: Install Prerequisites**

Please ensure your system has `uv` installed.

- **uv Installation**: `uv` is an extremely fast Python package manager. Please run the following command in your
  terminal:
    - **Linux / macOS**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
    - **Windows**: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

**Step 2: Get Source Code**

We provide two ways to get the source code:

- **Stable version, recommended for regular users**:
    1. Go to the project's [**Releases page**](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest)
    2. Download the source code archive named `Source code (zip)` or `Source code (tar.gz)`
    3. Extract the file to your preferred location

- **Development version, for developers**:  
  If you want to get the latest, possibly unstable development code, please use `git` to clone this project.
  This method requires you to have [Git](https://git-scm.com/downloads) installed.
  ```bash
  git clone https://github.com/LiJiaHua1024/ModlessChatTrans.git
  ```

**Step 3: Create Environment and Install Dependencies**

1. Open terminal and enter the project folder you extracted or cloned
   ```bash
   cd ModlessChatTrans
   ```
2. Use `uv` to create virtual environment and install all dependencies
   ```bash
   # 1. Create virtual environment
   uv venv
   
   # 2. Activate environment
   # Windows users please execute:
   .\.venv\Scripts\activate
   # Linux users please execute:
   source .venv/bin/activate
   
   # 3. Install project dependencies
   uv sync
   ```

**Step 4: Run the Program**

After environment configuration is complete, run the following command in the terminal to start the program:

```bash
modless-chat-trans
```

**Step 5: Configure and Use**

After the program starts, please refer to steps 3 to 6 in **Method 1** for configuration and usage.

### License

This project follows the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html). For more
information, please refer to the [LICENSE](LICENSE) file.

### Acknowledgements

This project utilizes [CTkScrollableDropdown](https://github.com/Akascape/CTkScrollableDropdown)
by [Akascape](https://github.com/Akascape) for some of its UI features, which is licensed under the MIT License.

### Contribution

This project is developed by [LiJiaHua1024](https://github.com/LiJiaHua1024)

### Contact

For any questions or suggestions, please contact: minecraft_benli@163.com