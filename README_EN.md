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
    - **Contextual Translation**: Supports referencing previous chat messages for context (both incoming and outgoing
      messages), greatly improving translation accuracy and coherence in multi-turn dialogues, abbreviations, and
      pronoun references
    - **Fallback Model & Multi-Strategy Failover**: Supports configuring a fallback LLM with four failover/racing
      strategies (Direct Switch, Switch After Retries Exhausted, Race on First Failure, Always Race), and supports
      OpenRouter extended model routing syntax to ensure high availability and low latency
- **Simple and Easy to Use**: Automatically retrieves chat messages by directly reading Minecraft log files, eliminating
  the instability and operational complexity of traditional OCR methods. Provides a lightweight web interface for clear
  translation results and convenient message sending, offering a smooth and natural experience with integration second
  only to native game mods
- **Modern Interface**: Adopts Fluent Design style for an aesthetically pleasing interface. Carefully organized with
  clear functional modules and intuitive navigation and operation logic, delivering an intuitive, user-friendly, and
  visually enjoyable experience. Also offers a lightweight WebView2-based `-nano` edition for even lower resource usage
- **No Mods Required**: As one of the few solutions in the community that runs without mods, this tool avoids mod
  compatibility issues and eliminates tedious version adaptation work. Whether using vanilla clients, mod-restricted
  environments, or seeking minimal deployment, you can enjoy an excellent translation experience
- **Minecraft Formatting Code Rendering**: The web interface fully supports Minecraft text formatting, presenting visual
  effects consistent with the game client
- **Multiple Translation Services Supported**: Supports 23 large language model (LLM) providers and 9 traditional
  translation service providers. For traditional services, you can use integrated free online translation or your own
  API Key
- **Smart Message Classification & Blacklist**: Beyond zero-latency built-in rules, supports Jev semantic classification
  or Hybrid mode to accurately distinguish player chat from server/system announcements (handling custom server ranks
  and titles); paired with user and content blacklists (supporting keywords and regex) to effortlessly filter spam and
  distractions
- **TTS Read-Aloud & Pre-TTS**: Integrates Edge TTS synthesis and local audio playback to automatically read incoming
  translations sequentially without overlap, with support for interrupt-and-read via long-press on the web UI and muting
  specific users in the config file; built-in Pre-TTS pre-synthesizes frequently cached translations into local audio for
  near-instant playback
- **Intelligent Translation Caching**: All translation results are reliably stored locally using an LFU (Least Frequently
  Used) eviction policy. The tool prioritizes matching historical caches, significantly improving response speed for
  repeated messages while saving your API quota, and supports one-click pruning of unused cache entries in Settings
- **Multi-Theme & Rich Interactive Web Interface**: Offers 6 themes (Default, Material, Fluent, Skeuomorphic, Cyberpunk,
  and Retro Terminal) plus a one-click Rage Mode; the web UI supports message-type filtering, smart merging and folding
  of duplicate/similar messages, long-press bubbles to toggle original/translated text or copy/read aloud, token/latency
  metadata tags, and automatic SSE reconnection with recovery
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
   download the latest `.exe` file (typically three editions are provided; see "Edition Differences" below for a
   detailed comparison):
    - `ModlessChatTrans_v*.exe`: Standard edition (flagship release with full compatibility and dependencies)
    - `ModlessChatTrans_v*-lite.exe`: Lite edition (built-in lightweight engines with full desktop GUI)
    - `ModlessChatTrans_v*-nano.exe`: Nano edition (built-in lightweight engines + WebView2 UI for minimal footprint)
2. Directly run the downloaded `.exe` file to start the program
3. After the program starts, configure according to the prompts on the interface (see the "Program Interface
   Configuration" section below for details)

#### Edition Differences

Since v3.3.0, ModlessChatTrans offers three Windows editions tailored to different needs: **Standard**, **Lite**, and
**Nano**. All three editions share the core AI and traditional translation pipelines, custom glossary, contextual
translation, fallback models, blacklist, TTS read-aloud, and multi-theme web interface, with each edition checking its
own matching release channel for auto-updates. They differ primarily in underlying translation backends, desktop settings
UI technology, and binary size:

- **Standard Edition (`ModlessChatTrans_v*.exe`)**: The flagship edition, recommended for most users
    - **Desktop UI**: Native Fluent Design desktop interface built on PySide6, including all 11 configuration menus
    - **Translation Engines**: Uses proven third-party libraries (`litellm` and `translators`) for the broadest service
      compatibility and stability, supporting all 23 LLM providers (including Google Vertex AI) and the full suite of
      traditional translation services
    - **Size & Positioning**: ~127 MB (as of v3.3.5); ideal if you want maximum compatibility and reliability
- **Lite Edition (`ModlessChatTrans_v*-lite.exe`)**: Substantially reduces binary size while preserving the native GUI
  and full functionality
    - **Desktop UI**: Retains the full PySide6 Fluent Design desktop settings interface and all 11 configuration menus,
      matching the Standard Edition experience
    - **Translation Engines**: Replaces heavyweight third-party dependencies with lightweight in-house implementations:
        - **Built-in Lightweight LLM Gateway (replaces `litellm`)**: Direct HTTP integration supporting OpenAI, Azure
          OpenAI, Anthropic Claude, Google Gemini, Google Vertex AI, DeepSeek, OpenRouter, Mistral, Moonshot, and all
          other declared LLM providers, along with deep translation mode, reasoning effort control, and JSON structured
          output (only GitHub Copilot no longer triggers interactive keyless device login)
        - **Built-in Free Translation Engine (replaces `translators`)**: Directly supports Bing, Google, Yandex,
          Alibaba, Caiyun, Youdao, DeepL Free, Sogou, Iflyrec, and other free online translators; paid traditional APIs
          remain identical to Standard
    - **Size & Positioning**: ~41 MB (dramatically smaller than Standard); ideal if you want a smaller download without
      giving up the full native GUI or any features
- **Nano Edition (`ModlessChatTrans_v*-nano.exe`)**: Ultra-compact edition built for minimal size, fast startup, and
  low memory usage
    - **Desktop UI**: Completely removes the heavy Qt/PySide6 runtime and uses the system built-in **Microsoft Edge
      WebView2** runtime for a lightweight settings interface (out of the box on Windows 11). Covers all essential
      pages—Message Capture, Translation Service (including Fallback Model), Display & TTS/Pre-TTS, Send Message,
      Contextual Translation, Glossary, Blacklist, Start, About, and Settings—while omitting the standalone "Message
      Classification" settings page from the GUI (still configurable in the TOML file; defaults to built-in rules)
    - **Translation Engines**: Also powered by the built-in lightweight LLM gateway and free translation engine, with
      Google Vertex AI service-account authentication removed (standard Google Gemini API via API Key remains fully
      supported)
    - **Size & Positioning**: ~22 MB; ideal for Windows 11 users or anyone seeking the smallest possible footprint and
      lowest resource consumption

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

The program's interface has a left-side menu divided into 9 main menus at the top and 2 auxiliary menus at the bottom,
totaling 11 menus. The bottom menus include "About" and "Settings", where "Settings" covers interface language, cache
management, and update settings, explained later. First, the top 9 menus are introduced.

> **Beginner Guide**: If you find the configuration options below overwhelming and want to get started quickly,
> we have prepared an [**Easy Guide**](./docs/easy_guide_en.md) to help you finish the core setup in three minutes and
> start using the tool.

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
  Tabs at the top of the page let you switch between **Primary Model** and **Fallback Model** to configure each
  independently:
    - **Select Service**: Choose the AI model provider
    - **API Key**: Enter the API key
    - **API Endpoint**: If needing a custom API endpoint (e.g., for relays or mirrors), enter the endpoint address (
      excluding "/chat/completion" path)
    - **Model ID**: Specify the AI model to use. When using OpenRouter, extended suffix syntax is supported (e.g.,
      `:free`, `:nitro`, `:floor`, `:latency`, or explicit provider ordering `model:provider1,provider2`)
    - **Max Output Tokens**: Limit the maximum output tokens per model response (range `1`–`100000`, default `4096`)
    - **Deep Translation Mode**: Enabling this uses CoT to improve translation quality but increases token consumption
      and latency
    - **Fallback Model Strategy** (effective when a fallback model is configured): Four failover and racing strategies:
        - **Direct Switch**: Immediately falls back to the fallback model on the primary model's first failure
        - **Switch After Retries Exhausted**: Falls back only after the primary model fails all automatic retries
        - **Race on First Failure**: After the primary model fails once, concurrently queries both primary and fallback
          models and returns whichever succeeds first
        - **Always Race**: Concurrently calls both primary and fallback models on every request and returns the fastest
          successful response (lowest latency, doubles request usage)
- **Traditional Translation**:
    - **Select Service**: Choose the translation service provider
    - **API Key**: Enter the key if available; selecting "Do not use" will use web-based online services
    - Alibaba, Youdao, and Sogou use the `id:secret` format; Iflyrec (iFLYTEK Machine Translation) uses `AppID:APIKey:APISecret` and requires an explicit source language for paid requests
    - Yandex also requires a Folder ID; enter an Azure region for regional resources and leave it empty for global resources

At the bottom of the page, there is an option for "Set a separate translation service for sending messages", explained
after the "Send Message" menu.

#### Translation Result Display

This menu configures how translation results are displayed and read aloud.

- **TTS Read-Aloud Settings**: Uses Edge TTS to automatically read incoming translations aloud with web UI controls:
    - **Enable Read-Aloud**: Reads incoming translated messages sequentially without overlap
    - **Voice**: Choose a specific Edge TTS voice or keep "Auto" to select an appropriate voice based on the translated
      content
    - **Speech Rate**: Adjust reading speed across 5 levels (`-50%` to `+50%`)
    - **Read Player Name**: When enabled, reads the speaker's player name before the message
    - **Test Read-Aloud**: Click to immediately preview the current voice and speed settings
    - **Pre-TTS Hot Word Pre-Synthesis**: Analyzes frequently hit entries in the translation cache and pre-synthesizes
      local audio to reduce playback latency (supports Start, Stop, and Clear Audio; unavailable when "Read Player Name"
      is enabled)
- **Web Settings**:
    - **Web Port**: Set the port number for the web interface on the local machine. For most users, no need to change the
      default (`56552`)

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

#### Contextual Translation

This menu configures contextual translation so the model can reference earlier chat messages for better accuracy and
coherence in multi-turn conversations (incoming and outgoing messages each maintain separate context history).

- **Context Splitting Strategy**:
    - **Disabled**: Translates each message independently without prior history
    - **Fixed Length**: Always keeps a fixed number of recent messages as context
    - **Time-Based**: Clears older context when the time gap between message batches exceeds the threshold, preventing
      unrelated past chat from interfering with the current conversation
- **Max History Messages**: Maximum number of prior messages included as context (`0` means unlimited)
- **Time Span Threshold (seconds)**: Only applies to the "Time-Based" strategy to determine when to start a new context
  window

#### Glossary

This menu works better with AI translation services for customizing the glossary.

- Enter the original term and target term, then click add. Click added terms to edit  
  For most users, this function is sufficient. For detailed tutorials, see [Glossary Guide](./docs/glossary_guide_en.md)

#### Blacklist

This menu filters out messages from specific players or matching specific content before translation and display. It
applies only to received player and system messages and does not affect messages you send.

- **User Blacklist**: Supports batch entry (one player name per line). Matches are case-insensitive exact comparisons
  against sanitized player names (formatting codes, server ranks such as `[MVP+]`, and channel prefixes are
  automatically stripped)
- **Message Content Blacklist**: Supports adding blocked keywords (case-insensitive substring match) or regular
  expressions (`/pattern/` syntax or regex toggle); matching messages are skipped

#### Message Classification

This menu configures how the tool distinguishes "player chat messages" from "server/system announcements", which is
especially useful on servers with custom rank titles or non-standard chat formatting.

- **Classification Mode**:
    - **Built-in Rules**: Purely local rule matching with zero latency and zero extra API cost
    - **Jev Model**: Uses a semantic classification model to identify message types with local result caching;
      automatically falls back to built-in rules on timeout or failure, and pauses via a circuit breaker on consecutive
      failures
    - **Hybrid Mode**: Performs a permissive local pre-screen first and only sends ambiguous or hard-to-classify lines
      to Jev for confirmation, maintaining high accuracy while reducing API calls
- **Jev Service Configuration** (available when using `Jev Model` or `Hybrid Mode`):
    - **API Format**: Supports `Jev Standard Format` (TypeSafe official, OpenRouter, or other OpenAI-compatible
      endpoints) and `Cloudflare AI`
    - **API Key**, **Model**, **Endpoint**: Configure authentication and request target for the classification service
    - **Account ID**: Required only when using Cloudflare AI
    - **Request Timeout**: Timeout in milliseconds for each classification call; falls back to built-in rules if exceeded

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
- **Cache Management**:
    - **Prune Unused Cache**: One-click cleanup that removes translation cache entries that have never been reused,
      keeping frequently accessed translations intact
- **Update Settings**:
    - **Auto-Check**: Set the frequency for automatic update checks
    - **Pre-Releases**: Choose whether to include pre-release versions
    - **Manual Check**: Check for updates immediately (fetches update packages matching your current Standard, `lite`,
      or `nano` edition)
    - **Current Version**: Displays the current program version and edition

### Usage After Starting

After starting the program via any method in the "Start" menu, the "Start" page will display a "Web Access Links" card.
At the same time, this link will automatically open the web interface 1 second after starting.

- **View Translation Results**: Open the provided web link (recommended to access via phone/tablet or computer secondary
  screen). If unfamiliar with network configuration, try the links from top to bottom until successful. The web page
  will display translated chat messages:
    - **Top Filters**: Filter displayed messages by type (User, System, Error, Info)
    - **Smart Merging & Folding**: Consecutive identical messages merge automatically with a counter badge (`xN`), and
      consecutive similar system or player messages fold into an expandable group (`+N`)
    - **Long-Press Context Menu**: Long-press any message bubble to quickly toggle between original and translated text,
      copy text, or interrupt playback to read that message aloud via TTS
    - **Floating Action Button (FAB)**: Expand the bottom-right button to toggle Dark Mode, clear messages, toggle
      **Rage Mode**, or switch among the 6 web themes in real time
- **Send Messages**:
    - **Web Input Method (Recommended)**: Enter content in the web message input box and click send. After translation,
      the web will show an Info-level prompt indicating the result has been copied to the clipboard. Then, in the
      Minecraft chat (T by default), press Ctrl+V to paste the translated result. This avoids IME “stuck input” issues.
      If **Rage Mode** is enabled from the FAB menu, the web page switches to the Rage theme and sent messages are
      translated in an aggressive Minecraft PVPer trash-talk style (gracefully falling back to normal translation when
      using traditional services)
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
