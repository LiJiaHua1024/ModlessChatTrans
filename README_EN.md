# ModlessChatTrans

## AI-Based Minecraft Real-Time Chat Translator

---

English | [简体中文](README.md)

## Features

- **AI High-Quality Translation**: Utilizes advanced large language models (LLM) for translation, significantly
  outperforming traditional translation engines in casual chat scenarios
    - **Prompt Optimized for Minecraft**: Extensively optimized prompt engineering ensures the LLM deeply understands
      Minecraft's chat style, terminology, and cultural context for accurate translation
    - **Custom Glossary**: Perfectly solves translation issues with game slang or server-specific terms. Users can
      define terms and their translations, which the tool automatically incorporates into LLM requests to ensure key
      information is conveyed accurately
    - ⏳**Contextual Translation** (Coming Soon): Coming soon! Will allow the model to reference previous chat messages
      for context, greatly improving translation accuracy and coherence in complex dialogues, abbreviations, and
      references
- **Simple and Easy to Use**: Automatically retrieves chat messages by directly reading Minecraft log files, eliminating
  the instability and operational complexity of traditional OCR methods. Provides a lightweight web interface for clear
  translation results and convenient message sending, offering a smooth and natural experience with integration second
  only to native game mods
- **Modern Interface**: Adopts Fluent Design style for an aesthetically pleasing interface. Carefully organized with
  clear functional modules and intuitive navigation and operation logic, delivering an intuitive, user-friendly, and
  visually enjoyable experience
- **No Mods Required**: As one of the few solutions in the community that runs without mods, this tool avoids mod
  compatibility issues and eliminates tedious version adaptation work. Whether using vanilla clients, mod-restricted
  environments, or seeking minimal deployment, you can enjoy an excellent translation experience
- **Minecraft Formatting Code Rendering**: The web interface fully supports Minecraft text formatting, presenting visual
  effects consistent with the game client
- **Multiple Translation Services Supported**: Supports 23 large language model (LLM) providers and 9 traditional
  translation service providers. For traditional services, you can use integrated free online translation or your own
  API Key
- **Intelligent Translation Caching**: All translation results are reliably stored. The tool prioritizes matching
  historical caches, significantly improving response speed for repeated messages while reducing calls to translation
  services, effectively saving your API quota
- **Multi-Theme Web Interface**: Offers 6 themes, including default, Material, Fluent, Skeuomorphic, Cyberpunk, and
  Retro Terminal styles
- **Multi-Language Interface**: Supports ten common languages, primarily translated using GPT-5 for precise and natural
  interface text, making it easy for global players to get started

## Usage

We provide two ways to start the program: one is a simple direct run method for regular Windows users, and the other is
running from source code for Linux users or advanced users who want to customize. The following details how to download,
start, configure, and use the program.

### Download and Start the Program

#### Method 1: Direct Run (For Windows Users)

This is the simplest method, recommended for all Windows users.

1. Go to the project's [**Releases page**](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest) and
   download the latest `.exe` file
2. Directly run the downloaded `.exe` file to start the program
3. After the program starts, configure according to the prompts on the interface (see the "Program Interface
   Configuration" section below for details)

#### Method 2: Run from Source Code (For Linux / Advanced Users)

This method is suitable for all Linux users, as well as Windows advanced users who want to experience the latest
features or modify the code themselves.

**Step 1: Install Prerequisites**

Ensure your system has `uv` installed.

- **uv Installation**: `uv` is a high-speed Python package manager. Run the following command in the terminal to
  install:
    - **Linux / macOS**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
    - **Windows**: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

**Step 2: Obtain the Source Code**

We provide two ways to obtain the source code:

- **Stable Version, Recommended for Regular Users**:
    1. Go to the project's [**Releases page**](https://github.com/LiJiaHua1024/ModlessChatTrans/releases/latest)
    2. Download the source code archive named `Source code (zip)` or `Source code (tar.gz)`
    3. Extract the file to your preferred location

- **Development Version, For Developers**:  
  If you want the latest, potentially unstable development code, use `git` to clone the project.  
  This requires [Git](https://git-scm.com/downloads) to be pre-installed.
  ```bash
  git clone https://github.com/LiJiaHua1024/ModlessChatTrans.git
  ```

**Step 3: Create Environment and Install Dependencies**

1. Open the terminal and navigate to the extracted or cloned project folder
   ```bash
   cd ModlessChatTrans
   ```
2. Use `uv` to create a virtual environment and install all dependencies
   ```bash
   # 1. Create virtual environment
   uv venv
   
   # 2. Activate environment
   # For Windows users:
   .\.venv\Scripts\activate
   # For Linux users:
   source .venv/bin/activate
   
   # 3. Install project dependencies
   uv sync
   ```

**Step 4: Run the Program**

After configuring the environment, run the following command in the terminal to start the program:

```bash
modless-chat-trans
```

**Step 5: Configure and Use**

After the program starts, configure in the GUI interface, including filling in the Minecraft log path, selecting
translation languages, etc. Follow the prompts on the program interface step by step.  
If you encounter issues during configuration, refer to the "Program Interface Configuration" section in this README,
which has detailed menu explanations.

### Program Interface Configuration

The program's interface has a left-side menu divided into 6 main menus at the top and 2 auxiliary menus at the bottom,
totaling 8 menus. The bottom menus include "About" and "App Settings", where "App Settings" covers interface language
and update settings, explained later. First, the top 6 menus are introduced.

*For configuration items that are hard to understand, there are explanation buttons in the program; click to view
details.*

#### Message Capture

This menu configures how to read Minecraft chat messages from log files.

- **Minecraft Log Location**: Enter the path to the Minecraft log folder. If unsure, search online to find it
- **Source Language**: Specify the language of received messages. If unsure, leave blank to enable auto-detection
- **Target Language**: Specify the language to translate received messages into
- **Log Encoding**: Select the encoding format for reading Minecraft logs. Default "auto" usually works; if issues
  arise, try switching to "GBK" or others
- **Monitoring Mode**: Offers "Efficient Mode" and "Compatible Mode". "Efficient Mode" reduces resource usage and
  slightly improves game smoothness; "Compatible Mode" suits higher Minecraft versions to adapt to their log
  optimization mechanisms
- **Filter Server Messages**: When enabled, filters out server/system messages without player names (e.g., server
  announcements)
- **Replace Garbled Characters**: When enabled, the program assumes garbled characters are Minecraft formatting code
  separators and replaces them to restore readability

#### Translation Service

This menu configures the translation service.

First, select the translation service type: AI Translation (recommended) or Traditional Translation Service.

- **AI Translation**:
    - **Select Service**: Choose the AI model provider
    - **API Key**: Enter the API key
    - **API Endpoint**: If needing a custom API endpoint (e.g., for relays or mirrors), enter the endpoint address (
      excluding "/chat/completion" path)
    - **Model ID**: Specify the AI model to use
    - **Deep Translation Mode**: Enabling this uses CoT to improve translation quality but increases token consumption
      and latency
- **Traditional Translation**:
    - **Select Service**: Choose the translation service provider
    - **API Key**: Enter the key if available; selecting "Do not use" will use web-based online services

At the bottom of the page, there is an option for "Set a separate translation service for sending messages", explained
after the "Send Message" menu.

#### Translation Result Display

This menu configures how translation results are displayed.

- **Web Port**: Set the port number for the web interface on the local machine. For most users, no need to change the
  default

#### Send Message

This menu configures translation for sent messages.

- **Monitor Clipboard**: Enable this checkbox to monitor clipboard changes and translate the changed content as a
  message to send
- **Source Language**: Specify the language of user-input messages (i.e., sender language)
- **Target Language**: Specify the language to translate user messages into

Note: Unlike the source and target languages in the "Message Capture" menu, these settings are for user-sent messages,
while the former are for received messages. Configure separately based on actual needs.

Regarding "Set a separate translation service for sending messages" in "Translation Service": If enabled, you can
configure a separate translation service for message sending, distinct from the received message service. After
enabling, switch between "Player Message Translation Service" and "Message Sending Translation Service" tabs at the top
of the "Translation Service" interface to configure respectively.

#### Glossary

This menu works better with AI translation services for customizing the glossary.

- Enter the original term and target term, then click add. Click added terms to edit  
  For most users, this function is sufficient. For detailed tutorials, see [Glossary Guide](./docs/glossary_guide_en.md)

#### Start

This menu saves configurations and starts the program, also displaying the web interface access link after starting.

- **Start**:
    - **Start Directly**: Starts the program based on current configurations without saving to config file
    - **Save Configuration and Start**: Saves configurations first, then starts the program
- **Save Configuration**: Saves current configurations to the config file

#### About

This menu displays program information, including version, author, email, related links, and license.

#### Settings

This menu is for overall program settings.

- **Language Settings**: Select the program's interface display language (not message translation language). Restart the
  program after changing for it to take effect
- **Update Settings**:
    - **Auto-Check**: Set the frequency for automatic update checks
    - **Pre-Releases**: Choose whether to include pre-release versions
    - **Manual Check**: Check for updates immediately
    - **Current Version**: Displays the current program version number

### Usage After Starting

After starting the program via any method in the "Start" menu, the "Start" page will display a "Web Access Links" card.
At the same time, this link will automatically open the web interface 1 second after starting.

- **View Translation Results**: Open the provided web link (recommended to access via phone/tablet or computer secondary
  screen). If unfamiliar with network configuration, try the links from top to bottom until successful. The web page
  will display translated chat messages
- **Send Messages**:
    - **Web Input Method (Recommended)**: Enter content in the web message input box and click send. After translation,
      the web will show an Info-level prompt indicating the result has been copied to the clipboard. Then, in the
      Minecraft chat (T by default), press Ctrl+V to paste the translated result. This avoids IME “stuck input” issues
    - **Clipboard Monitoring Method**: Requires enabling "Monitor Clipboard" in "Send Message". After entering the
      message, press Ctrl+A to select all and Ctrl+C (or Ctrl+X) to copy/cut to clipboard; the program will capture and
      translate it. Similarly, after the web shows an Info-level prompt, use the same operation to paste in Minecraft

### Notes

If using low-version Minecraft (e.g., 1.8.9, common for PVP), it is recommended to start Minecraft first and wait for
the game window to appear before clicking the start button in the program. Otherwise, Minecraft logs may not generate,
preventing translation of received messages.

## License

This project follows the [GNU General Public License Version 3](https://www.gnu.org/licenses/gpl-3.0.en.html). For more
information, see the [LICENSE](LICENSE) file.

## Contributions

This project is developed by [LiJiaHua1024](https://github.com/LiJiaHua1024).

## Contact

For any questions or suggestions, please contact: minecraft_benli@163.com.