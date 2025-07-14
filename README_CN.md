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
- **高质量翻译**：支持选择多种大语言模型进行翻译，包括 OpenAI、Anthropic Claude、Google Gemini、DeepSeek
  等，确保准确性和流畅度，即使是游戏缩写和俚语也能准确翻译
- **多种翻译服务支持**：支持多种翻译服务：大语言模型翻译、DeepL翻译、Bing翻译、Google翻译、Yandex翻译、阿里翻译、彩云小译、有道翻译、搜狗翻译、讯飞翻译
- **多种呈现方式**：支持三种其他玩家消息的翻译呈现方式：CustomTkinter GUI 界面、语音合成播报、网页界面
- **术语表**：为特定术语或模式定义自定义翻译规则，支持变量解析和正则约束
    - [中文用户指南](./docs/glossary_guide_zh.md)
- **多语言界面**：支持9种界面语言，包括简体中文、英语、日语、法语、德语、西班牙语、韩语、俄语、巴西葡萄牙语、繁体中文
- **智能缓存**：内置翻译缓存机制，减少重复翻译，提高响应速度
- **Minecraft 格式化代码渲染**：网页完整支持 Minecraft 聊天格式，包括颜色、样式等
- **多主题网页界面**：提供6种精美主题，包括默认、Material、Fluent、拟物、赛博朋克、复古终端等风格
- **简单易用**：只需下载并运行 .exe 文件即可，配置会自动保存和加载

### 功能

- **快速翻译其他玩家的消息**：实时捕捉并翻译他人发送的聊天信息
- **翻译并发送自己的消息**：在发送消息前自动将其翻译为目标语言
    - **通过剪切板捕获消息**：程序会自动捕获您的消息，并在发送前将其翻译为目标语言
    - **通过网页界面发送消息**：有效避免了游戏在全屏时输入法无法显示的问题

### 使用方法

我们提供两种使用方式：为普通 Windows 用户准备的开箱即用的 `.exe` 文件，以及为 Linux 和高级用户准备的从源代码运行。

---

#### 方式一：直接运行 (适用于 Windows 用户)

这是最简单的方式，推荐所有 Windows 用户使用。

1. 前往项目的 [**Releases 页面**](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest)，下载最新的 `.exe` 文件
2. 直接运行下载的 `.exe` 文件，程序将启动
3. 在程序的左下角选择界面语言
4. 按照要求填入信息：

- **Minecraft 日志文件夹**：Minecraft 游戏日志存放的位置（通常为 logs 文件夹）
- **翻译结果呈现方式**：显示翻译结果的方式
    - **图形界面**：创建一个简单的 GUI 界面显示翻译结果（最大消息数：在消息窗口中显示消息的最大数量）
    - **语音**：使用语音合成引擎将翻译结果播报出来
    - **网页**：启动一个美观的网页，可以接收/发送消息。大多数带有浏览器的电子设备现在都可以用作翻译内容的显示终端（HTTP端口：HTTP服务器的端口号）
- **源语言（留空自动）**：其他玩家消息的源语言（留空自动）
- **目标语言**：翻译结果的目标语言
- **翻译服务选择**：选择使用的翻译服务
    - **大语言模型翻译**：支持 OpenAI、Anthropic Claude、Google Gemini、DeepSeek 等
    - **传统翻译服务**：支持 DeepL、Bing、Google、Yandex、阿里、彩云小译、有道、搜狗、讯飞等
- **LLM相关选项**：
    - **API 地址**：LLM API 地址（OpenAI 兼容的 API 格式）
    - **API 密钥**：LLM API 密钥
    - **模型代号**：LLM
      代号（模型代号详见此处：[OpenAI](https://platform.openai.com/docs/models) | [Gemini](https://ai.google/get-started/our-models) |
      [硅基流动](https://cloud.siliconflow.cn/models) | [Deepseek](https://api-docs.deepseek.com/zh-cn/quick_start/pricing) |
      [Anthropic](https://docs.anthropic.com/en/docs/about-claude/models/all-models)
- **传统翻译服务相关选项**：
    - **我有API密钥**：是否使用自己的 API 密钥
        - **API 密钥**：API 密钥
- **翻译玩家自己的消息**：是否翻译玩家自己的消息（仅针对剪切板捕获的消息）
    - **玩家消息源语言**：玩家自己的消息的源语言
    - **玩家消息目标语言**：玩家自己的消息的目标语言
- **始终置顶**：是否始终置顶 图形界面 窗口
- **更多设置**：鼠标悬停在选项上查看更多信息
    - **启用翻译质量优化**：通过启用显式思维链，提高翻译质量，但会增加延迟并消耗更多令牌
    - **启用高版本修复**：如果捕获不到聊天消息，可尝试启用
    - **翻译系统消息**：关闭后，不会翻译没有名称的聊天消息
    - **替换乱码字符**：将所有乱码字符替换为Minecraft格式化代码
    - **日志编码**：手动指定日志编码。如果出现乱码或无法捕获消息，可尝试更改此值为`utf-8`/`gbk`。留空则自动检测
    - **术语表**：配置自定义翻译规则，支持变量解析和正则约束
        - [中文用户指南](./docs/glossary_guide_zh.md)


5. 点击 "启动" ，启动 Minecraft 开始游玩
6. **接收消息**：当其他玩家发送消息时，程序会根据选择的呈现方式展示翻译结果
   **发送消息**：
    1. 捕获内容：  
       a. 在 Minecraft 聊天框输入内容后，按下 `Ctrl + A` 全选，再按 `Ctrl + C` 复制内容（或 `Ctrl + X` 剪切）  
       b. 【**推荐**】如果您选择了 "网页" 作为呈现方式，您也可以在网页中输入内容并点击 "发送" 按钮发送消息
    2. 程序将翻译您的消息并复制到剪贴板，随后按下 `Ctrl + V` 将翻译后的内容粘贴回聊天框，再按 `Enter` 发送

---

#### 方式二：从源代码运行 (适用于 Linux / 高级用户)

此方法适用于所有 Linux 用户，以及希望体验最新功能或自行修改代码的 Windows 高级用户。

**第一步：安装先决条件**

请确保您的系统已安装`uv`。

- **uv 安装**: `uv` 是一个极速的 Python 包管理器。请在终端运行以下命令安装：
    - **Linux / macOS**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
    - **Windows**: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

**第二步：获取源代码**

我们提供两种获取源码的方式：

- **稳定版，推荐给普通用户**:
    1. 前往项目的 [**Releases 页面**](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest)
    2. 下载名为 `Source code (zip)` 或 `Source code (tar.gz)` 的源码压缩包
    3. 将文件解压到您喜欢的位置

- **开发版，适用于开发者**:  
  如果您希望获取最新的、可能尚不稳定的开发中代码，请使用 `git` 克隆本项目。
  此方式需要您预先安装 [Git](https://git-scm.com/downloads)。
  ```bash
  git clone https://github.com/LiJiaHua1024/ModlessChatTrans.git
  ```

**第三步：创建环境并安装依赖**

1. 打开终端，进入您解压或克隆的项目文件夹
   ```bash
   cd ModlessChatTrans
   ```
2. 使用 `uv` 创建虚拟环境并安装所有依赖
   ```bash
   # 1.创建虚拟环境
   uv venv
   
   # 2.激活环境
   # Windows用户请执行：
   .\.venv\Scripts\activate
   # Linux用户请执行：
   source .venv/bin/activate
   
   # 3.安装项目依赖
   uv sync
   ```

**第四步：运行程序**

环境配置完成后，直接在终端中运行以下命令即可启动程序：

```bash
modless-chat-trans
```

**第五步：配置并使用**

程序启动后，请参照 **方式一** 中的第3至第6步进行配置和使用。

### 许可证

本项目遵循 [GNU 通用公共许可证 第3版](https://www.gnu.org/licenses/gpl-3.0.zh-cn.html)。更多信息请参阅 [LICENSE](LICENSE)
文件。

### 致谢

本项目的部分 UI 功能使用了由 [Akascape](https://github.com/Akascape)
开发的 [CTkScrollableDropdown](https://github.com/Akascape/CTkScrollableDropdown) 项目，该项目基于 MIT 许可证授权。

### 贡献

本项目由[LiJiaHua1024](https://github.com/LiJiaHua1024)开发。

### 联系方式

如有任何问题或建议，请联系：minecraft_benli@163.com。