## ModlessChatTrans

  ### 无模组 Minecraft 实时聊天翻译器

[English](README.md)|简体中文

厌倦了在 Minecraft 中看不懂其他玩家的外语消息？ ModlessChatTrans 可以帮到你！这款轻量级工具可以实时翻译聊天消息，让你无需离开游戏就能与来自世界各地的玩家交流。

  ### 特点

  - **无模组**：无需安装任何模组，ModlessChatTrans 通过读取 Minecraft 日志文件获取聊天消息，安全便捷
  - **实时翻译**：以极快的速度翻译聊天消息，让你在激烈的 PvP 中也能轻松沟通
  - **高质量翻译**：使用先进的 LLM 模型进行翻译，确保准确性和流畅度，即使是游戏缩写和俚语也能准确翻译
  - **多种呈现方式**：支持三种翻译结果呈现方式：
    - **直接打印**：将翻译结果直接打印到控制台。
    - **Tkinter GUI 界面**：使用 Tkinter 库创建一个简单的 GUI 界面显示翻译结果。
    - **语音合成播报**：使用语音合成引擎将翻译结果播报出来。
    - **HTTP Server**：使用 Flask 模块启动一个 HTTP 服务器，简化跨平台翻译结果的展示。大多数带有浏览器的电子设备现在都可以用作翻译内容的显示终端。
  - **简单易用**：只需下载并运行 .exe 文件即可

  ### 功能

  - 将其他玩家发送的消息翻译成你的语言
  - 支持多种语言翻译

  ### 未来计划

  - 支持自己的消息翻译后发送
  - 支持更多翻译结果的呈现方式
  - 支持更多翻译服务

  ### 使用方法

  1. 从发布页面下载最新版 .exe 文件
  2. 运行 .exe 文件
  3. 输入 Minecraft 日志文件目录、翻译结果呈现方式、API地址、API 密钥、翻译使用的模型
  4. 启动 Minecraft 并加入游戏

  ### 项目开发状态更新

  非常感谢大家一直以来对本项目的支持和关注。自1.1.1版本发布以来，我一直在努力开发下一个重大版本更新(2.0.0)。这个版本将带来许多激动人心的新功能和改进，拥有全新的图形化用户界面，支持保存配置文件。

  在2024年7月2日，我已实现除 “透明代理” 外的所有功能。

  然而，开发过程中遇到了一些技术挑战，特别是在实现网络相关功能方面。这些挑战需要更多时间来解决和测试。计划中的透明代理功能，允许我们直接从网络数据包中获取和修改聊天消息，而无需依赖监视日志文件，或许还可以解决低版本可能出现的消息乱码问题。此外，还可以通过修改网络数据包实现一种全新的近乎完美的翻译结果呈现方式——在Minecraft原版消息页面显示。但是这个功能实现起来需要深入理解Minecraft的网络协议。

  由于个人原因和技术难题，项目目前处于缓慢更新状态。我正在努力学习相关知识以克服这些障碍，但进展比预期要慢。

  在此，我诚挚地邀请有网络编程经验，特别是熟悉Minecraft网络协议的开发者加入这个项目。如果你对实现透明代理功能有兴趣或者有相关经验，请不要犹豫，在Issues中联系我或直接提交Pull Request。你的贡献将极大地推动项目的发展。顺带说一下，[wiki.vg](https://wiki.vg) 是一个了解Minecraft网络协议的好地方。

  我会继续努力，尽快为大家带来这个重大更新。如果你有兴趣参与开发，请在dev-2.0.0分支上进行工作。

  ### 开发

  ModlessChatTrans 使用纯 Python 编写。

  ### 许可证

  本项目遵循 [GNU 通用公共许可证 第3版](https://www.gnu.org/licenses/gpl-3.0.zh-cn.html)。更多信息请参阅 [LICENSE](LICENSE) 文件。 

  ### 贡献

  本项目由[LiJiaHua1024](https://github.com/LiJiaHua1024)开发

  ### 联系方式

  minecraft_benli@163.com

  
