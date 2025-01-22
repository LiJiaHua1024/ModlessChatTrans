# ModlessChatTrans

## 无需模组的 Minecraft 实时聊天翻译器

---

[English](README.md) | 简体中文

厌倦了在 Minecraft 中看不懂其他玩家的外语消息？ **无需安装任何 Mod！** ModlessChatTrans
可以帮到你！这款轻量级工具可以让你无需离开游戏就能与来自世界各地的玩家交流。

**ModlessChatTrans** 是一款 **无需安装任何 Mod** 即可为 Minecraft 玩家提供实时聊天翻译的工具。

### 特点

- **无需 Mod**：无需安装任何Mod，ModlessChatTrans 通过读取 Minecraft 日志文件获取其他玩家发送的聊天消息，读取剪切板获取自己的聊天消息
- **实时翻译**：以极快的速度翻译聊天消息，让你在激烈的 PvP 中也能轻松沟通
- **高质量翻译**：使用先进的 LLMs 进行翻译，确保准确性和流畅度，即使是游戏缩写和俚语也能准确翻译
- **多种翻译服务支持**：支持多种翻译服务，例如 OpenAI、DeepL、Bing翻译 等
- **多种呈现方式**：支持三种其他玩家消息的翻译呈现方式：CustomTkinter GUI 界面、语音合成播报、HTTP Server
- **简单易用**：只需下载并运行 .exe 文件即可

### 功能

- **快速翻译其他玩家的消息**：实时捕捉并翻译他人发送的聊天信息
- **翻译并发送自己的消息**：在发送消息前自动将其翻译为目标语言

### 使用方法

#### **Windows 平台**:

1. 从发布页面下载 [最新版](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) .exe 文件
2. 运行 .exe 文件
3. 在程序的左下角选择界面语言
4. 按照要求填入信息：

- **Minecraft 日志文件夹**：Minecraft 游戏日志存放的位置（通常为 logs 文件夹）
- **翻译结果呈现方式**：显示翻译结果的方式
  - **图形界面**：创建一个简单的 GUI 界面显示翻译结果（最大消息数：在消息窗口中显示消息的最大数量）
  - **语音**：使用语音合成引擎将翻译结果播报出来
  - **HTTP服务器**：启动一个 HTTP 服务器，简化跨平台翻译结果的展示。大多数带有浏览器的电子设备现在都可以用作翻译内容的显示终端（HTTP端口：HTTP服务器的端口号）
- **源语言（留空自动）**：其他玩家消息的源语言（留空自动）
- **目标语言**：翻译结果的目标语言
- **LLM/DeepL/Bing**：选择使用的翻译服务
- **LLM相关选项**：
    - **API 地址**：LLM API 地址（OpenAI 兼容的 API 格式）
    - **API 密钥**：LLM API 密钥
    - **模型代号**：LLM 代号（OpenAI的模型代号详见[此处](https://platform.openai.com/docs/models)）
- **翻译玩家自己的消息**：是否翻译玩家自己的消息
  - **玩家消息源语言**：玩家自己的消息的源语言
  - **玩家消息目标语言**：玩家自己的消息的目标语言
- **始终置顶**：是否始终置顶 图形界面 窗口

5. 点击 “启动” ，启动 Minecraft 开始游玩
6. **接收消息**：当其他玩家发送消息时，程序会根据选择的呈现方式展示翻译结果
   **发送消息**：
   - 在 Minecraft 聊天框输入内容后，按下 `Ctrl + A` 全选，再按 `Ctrl + C` 复制内容（或 `Ctrl + X` 剪切）
   - 程序将翻译您的消息并复制到剪贴板，随后按下 `Ctrl + V` 将翻译后的内容粘贴回聊天框，再按 `Enter` 发送

#### **Linux 平台**

1. 从发布页面下载[最新版](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) “Source code” 归档文件
2. 解压下载的归档文件，进入解压后的文件夹
3. 运行 `pip3 install -r requirements.txt` 安装依赖
4. 运行 `python3 ./main.py` 启动程序
5. 按照 Windows 平台第3至第6步的操作执行

### 开发

ModlessChatTrans 使用纯 Python 编写。

### 许可证

本项目遵循 [GNU 通用公共许可证 第3版](https://www.gnu.org/licenses/gpl-3.0.zh-cn.html)。更多信息请参阅 [LICENSE](LICENSE)
文件。

### 贡献

本项目由[LiJiaHua1024](https://github.com/LiJiaHua1024)开发

### 联系方式

如有任何问题或建议，请联系：minecraft_benli@163.com
