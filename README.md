## ModlessChatTrans

### Real-time Chat Translator for Modless Minecraft

English|[简体中文](README_CN.md)

Tired of not understanding foreign language messages from other players in Minecraft? ModlessChatTrans can help! This lightweight tool can translate chat messages in real-time, allowing you to communicate with players from around the world without leaving the game.

### Features

- **Modless**: No need to install any mods. ModlessChatTrans extracts chat messages from the Minecraft log files for other players’ messages and reads your own chat messages from the clipboard.
- **Real-time Translation**: Translates chat messages at lightning speed, so you can communicate effortlessly even during intense PvP.
- **High-quality Translations**: Powered by an advanced LLM (Language Learning Model), ensuring accuracy and fluency, even for gaming abbreviations and slang.
- **Multiple Presentation Methods**: Supports three ways to present translation results:
  - **CustomTkinter GUI**: Uses the CustomTkinter library to create a simple GUI interface to display translation results.
  - **Text-to-Speech Output**: Uses a TTS engine to read out the translation results.
  - **HTTP Server**: Launches an HTTP server using Flask, making it easy to display translations across platforms. Any device with a browser can now serve as a translation display terminal.
- **Easy to Use:** Simply download and run the .exe file.

### Functionality

- Translates messages from other players into your language.
- Translates your own messages before sending them.
- Supports translations in multiple languages.

### How to Use

**Windows Platform**:
1. Download the [latest version](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) .exe file from the release page.
2. Run the .exe file.
3. Choose the interface language in the bottom left corner of the program.
4. Enter the necessary information as prompted (you can choose whether to have your own messages translated before sending).
5. Click "Start" and begin playing Minecraft.
6. When other players send you messages, the program will show the translated result (depending on the "Output method" you selected). To send a message, enter it into the Minecraft chat box, then press `Ctrl + A` followed by `Ctrl + C` (or `Ctrl + X`) to copy (or cut) the content to your clipboard (**Note: Do not send the message yet!**). The program will capture your message and write the translated result back to your clipboard. When the program prompts “Chat messages translated, translation results in clipboard” press `Ctrl + V` to paste the content back into the chat box. Then press `Enter` to send the message.

**Linux Platform**:
1. Download the [latest version](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) "Source code" archive from the release page.
2. Extract the downloaded archive and enter the extracted folder.
3. Run `pip install -r requirements.txt` to install the dependencies.
4. Run `python3 ./main.py` to start the program.
5. Follow steps 3 to 6 from the Windows platform instructions.

### Project Development Updates
I have been continuously working on this program; however, I encountered some challenges while transitioning from version 1.1.1 to 2.0.0 (see the README in branch `2.0.0-legacy` for details).

Due to these difficulties, development stalled. After consideration, I decided to temporarily abandon this feature and aim to implement it later when conditions allow. As a temporary alternative, I chose to use a clipboard monitoring method for translating my own messages.

The transparent proxy attempt branch has been renamed `2.0.0-legacy`, and the new `dev-2.0.0` branch is under rapid development and will be merged into the `main` branch as soon as possible, releasing version 2.0.0.

### Development

ModlessChatTrans is developed entirely in Python.

### License

This project follows the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html). For more information, please refer to the [LICENSE](LICENSE) file.

### Contribution

This project is developed by [LiJiaHua1024](https://github.com/LiJiaHua1024).

### Contact

minecraft_benli@163.com
