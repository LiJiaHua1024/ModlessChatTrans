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
- **High-quality Translations**: Uses advanced LLMs for translation, ensuring accuracy and fluency, even for gaming
  abbreviations and slang
- **Multiple Translation Services**: Supports various translation services: LLM translation, DeepL Translate, Bing
  Translate, Google Translate, Yandex Translate, Alibaba Translate, Caiyun Translate, Youdao Translate, Sogou Translate,
  Iflyrec Translate
- **Multiple Presentation Methods**: Supports three ways to display other players' translated messages: CustomTkinter
  GUI interface, Text-to-Speech output, Web interface
- **Easy to Use**: Simply download and run the .exe file

### Functionality

- **Quick Translation of Other Players' Messages**: Captures and translates chat messages in real-time
- **Translate and Send Your Own Messages**: Automatically translates your messages to the target language before sending
    - **Capture Messages via Clipboard**: The program automatically captures your messages and translates them to the
      target language before sending
    - **Send Messages via Web Interface**: Effectively avoids the problem of input methods not displaying when the game
      is in fullscreen

### How to Use

#### **Windows Platform**:

1. Download the [latest version](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) .exe file
2. Run the .exe file
3. Choose the interface language in the bottom left corner of the program
4. Fill in the required information:

- **Minecraft Log Folder**: Location of Minecraft game logs (usually the logs folder)
- **Output Method**: How to display translation results
    - **Window Interface**: Creates a simple GUI interface to display translation results (Max Messages: maximum number
      of messages shown in the message window)
    - **Voice**: Uses text-to-speech to announce translation results
    - **Web Interface**: Launches a beautiful web page that can receive/send messages. Most electronic devices with
      browsers can now serve as translation display terminals (HTTP Port: port number for the HTTP server)
- **Source Language (Auto-detect if blank)**: Source language of other players' messages (leave blank for
  auto-detection)
- **Target Language**: Target language for translations
- **LLM/DeepL/Bing/Google/Yandex/Alibaba/Caiyun/Youdao/Sogou/Iflyrec**: Choose the translation service to use
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

5. Click "Start" and launch Minecraft to begin playing
6. **Receiving Messages**: When other players send messages, the program will display translations according to your
   chosen display method
   **Sending Messages**:
    1. Capture content:  
       a. After typing in the Minecraft chat box, press `Ctrl + A` to select all, then `Ctrl + C` to copy (or `Ctrl + X`
       to cut)  
       b. If you selected "Web Interface" as the display method, you can also enter content in the web interface and
       click the "Send" button to send messages
    2. The program will translate your message and copy it to the clipboard, then press `Ctrl + V` to paste the
       translated content back to the chat box, and press `Enter` to send

#### **Linux Platform**

1. Download the [latest version](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) "Source code" archive
2. Extract the downloaded archive and enter the extracted folder
3. Run `pip3 install -r requirements.txt` to install dependencies
4. Run `python3 ./main.py` to start the program
5. Follow steps 3 to 6 from the Windows platform instructions

### Development

ModlessChatTrans is developed entirely in Python.

### License

This project follows the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html). For more
information, please refer to the [LICENSE](LICENSE) file.

### Contribution

This project is developed by [LiJiaHua1024](https://github.com/LiJiaHua1024)

### Contact

For any questions or suggestions, please contact: minecraft_benli@163.com