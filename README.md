## ModlessChatTrans

### Real-time Chat Translator for Modless Minecraft

English|[简体中文](README_CN.md)

Tired of not understanding foreign language messages from other players in Minecraft? ModlessChatTrans can help! This lightweight tool can translate chat messages in real-time, allowing you to communicate with players from around the world without leaving the game.

### Features

- **Modless**: No need to install any mods. ModlessChatTrans works by reading Minecraft log files to capture chat messages, making it safe and convenient.
- **Real-time Translation**: Translates chat messages at lightning speed, so you can communicate effortlessly even during intense PvP.
- **High-quality Translations**: Utilizes advanced LLM models to ensure accuracy and fluency, accurately translating even gaming abbreviations and slang.
- **Multiple Presentation Methods**: Supports three ways to present translation results:
  - **Direct Print**: Prints the translation results directly to the console.
  - **Tkinter GUI Interface**: Uses the Tkinter library to create a simple GUI interface to display translation results.
  - **Speech Synthesis Broadcast**: Uses a speech synthesis engine to broadcast the translation results.
  - **HTTP Server**: Utilizes the Flask module to launch an HTTP server, enabling easier cross-platform result presentation. Most electronic devices with a browser can now serve as display terminals for the translation content.
- **Easy to Use:** Simply download and run the .exe file.

### Functionality

- Translates messages from other players into your language.
- Supports translations in multiple languages.

### Future Plans

- Support translating your own messages before sending.
- Support more ways to present translation results.
- Support more translation services.

### Usage

1. Download the latest .exe file from the release page.
2. Run the .exe file.
3. Enter the Minecraft log file directory, translation result presentation method, API address, API key, and translation model to use.
4. Launch Minecraft and join a game.

### Development Status Update

Thank you all for your continuous support and attention to this project. Since the release of version 1.1.1, I have been diligently working on the next major update (2.0.0). This version will bring many exciting new features and improvements, including a brand new graphical user interface and support for saving configuration files.

As of July 2, 2024, I have implemented all features except for the "transparent proxy".

However, during development, I encountered some technical challenges, particularly in implementing network-related features. These challenges require more time to resolve and test. The planned transparent proxy feature will allow us to capture and modify chat messages directly from network packets without relying on log file monitoring. It might also resolve message garbling issues in lower versions. Furthermore, by modifying network packets, we can achieve a near-perfect translation presentation method—displaying translated messages directly on the original Minecraft message screen. However, implementing this feature requires an in-depth understanding of Minecraft's network protocol.

Due to personal reasons and these technical challenges, the project is currently progressing slowly. I am striving to learn the necessary knowledge to overcome these obstacles, but the progress is slower than expected.

Here, I sincerely invite developers with network programming experience, especially those familiar with Minecraft's network protocol, to join this project. If you are interested in implementing the transparent proxy feature or have relevant experience, please do not hesitate to contact me through Issues or directly submit a Pull Request. Your contribution will significantly advance the project. By the way, [wiki.vg](https://wiki.vg) is a great place to learn about Minecraft's network protocol.

I will continue to work hard to bring this major update to everyone as soon as possible. If you are interested in contributing to the development, please work on the dev-2.0.0 branch.

### Development

ModlessChatTrans is written in pure Python. 

### License

This project follows the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html). For more information, please refer to the [LICENSE](LICENSE) file.

### Contribution

This project is developed by [LiJiaHua1024](https://github.com/LiJiaHua1024).

### Contact

minecraft_benli@163.com
