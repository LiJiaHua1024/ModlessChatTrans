## ModlessChatTrans

  ### 无模组 Minecraft 实时聊天翻译器

[English](README.md)|简体中文

厌倦了在 Minecraft 中看不懂其他玩家的外语消息？ ModlessChatTrans 可以帮到你！这款轻量级工具可以实时翻译聊天消息，让你无需离开游戏就能与来自世界各地的玩家交流。

  ### 特点

  - **无模组**：无需安装任何模组，ModlessChatTrans 通过读取 Minecraft 日志文件获取其他玩家发送的聊天消息，读取剪切板获取自己的聊天消息
  - **实时翻译**：以极快的速度翻译聊天消息，让你在激烈的 PvP 中也能轻松沟通
  - **高质量翻译**：使用先进的 LLM 进行翻译，确保准确性和流畅度，即使是游戏缩写和俚语也能准确翻译
  - **多种呈现方式**：支持三种其他玩家消息的翻译呈现方式：
    - **CustomTkinter GUI 界面**：使用 CustomTkinter 库创建一个简单的 GUI 界面显示翻译结果
    - **语音合成播报**：使用语音合成引擎将翻译结果播报出来
    - **HTTP Server**：使用 Flask 模块启动一个 HTTP 服务器，简化跨平台翻译结果的展示。大多数带有浏览器的电子设备现在都可以用作翻译内容的显示终端
  - **简单易用**：只需下载并运行 .exe 文件即可

  ### 功能

  - 将其他玩家发送的消息翻译成你的语言
  - 自己的消息经翻译后再发送
  - 支持多种语言翻译

  ### 使用方法

  **Windows 平台**:
  1. 从发布页面下载 [最新版](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) .exe 文件
  2. 运行 .exe 文件
  3. 在程序的左下角选择界面语言 
  4. 按照要求填入信息（可选择是否将自己的消息翻译后发送）
  5. 点击 “启动” ，启动 Minecraft 开始游玩
  6. 当其他玩家向您发送消息时，程序会展示翻译结果（展示方式取决于您对 “翻译结果呈现方式” 的选择）；当您想要发送消息时，请在 Minecraft 聊天框处把内容输入完毕后，依次按下 `Ctrl + A`、`Ctrl + C`（或 `Ctrl + X` ）将内容复制（或剪切）到剪切板（**注意：这个时候请不要发送！**），程序会获取到您的消息，并将翻译结果写入剪切板中。当程序提示“聊天消息已翻译，翻译结果已复制到剪贴板”，按下 `Ctrl + V`将剪切板的内容释放到聊天框。此时再按下 `Enter` 键发送消息

  **Linux 平台**
  1. 从发布页面下载[最新版](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) “Source code” 归档文件
  2. 提取下载的归档文件，进入提取后的文件夹
  3. 运行 `pip install -r requirements.txt` 安装依赖
  4. 运行 `python3 ./main.py` 启动程序
  5. 剩下的操作与 Windows 平台 的第3 - 6步相同

  ### 项目开发状态更新

  我一直在努力开发此程序，然而，在 1.1.1->2.0.0 版本中，我遇到了一些困难（详见分支`2.0.0-legacy`的README说明）
  
  由于这些原因，项目一直没有进展，经过考虑，我决定暂时放弃这个功能，在日后条件允许时再去实现。退而求其次，我选择通过监视剪切板的方式暂时作为翻译自己消息的解决方案

  对透明代理的尝试分支已重命名为`2.0.0-legacy`，新的`dev-2.0.0`分支正在快速开发，将尽快合并到`main`分支并推出2.0.0版本

  ### 开发

  ModlessChatTrans 使用纯 Python 编写。

  ### 许可证

  本项目遵循 [GNU 通用公共许可证 第3版](https://www.gnu.org/licenses/gpl-3.0.zh-cn.html)。更多信息请参阅 [LICENSE](LICENSE) 文件。 

  ### 贡献

  本项目由[LiJiaHua1024](https://github.com/LiJiaHua1024)开发

  ### 联系方式

  minecraft_benli@163.com

  
