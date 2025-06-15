# Copyright (C) 2024-2025 LiJiaHua1024
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import tkinter as tk
import customtkinter as ctk
import webbrowser
import datetime
from dataclasses import dataclass
from collections import deque
from typing import Tuple
from tkinter import messagebox
from tktooltip import ToolTip
from modless_chat_trans.file_utils import read_config, save_config, get_path, get_platform
from modless_chat_trans.i18n import _, supported_languages, lang_window_size_map
from modless_chat_trans.translator import services, service_supported_languages, LLM_PROVIDERS
from modless_chat_trans.logger import logger

try:
    from CTkScrollableDropdown import CTkScrollableDropdown  # 提供滚动和高度限制的下拉菜单

    logger.info("CTkScrollableDropdown imported successfully")
except ImportError:
    CTkScrollableDropdown = None
    logger.info("CTkScrollableDropdown not found, using default dropdown")

if (platform := get_platform()) == 0:
    import hPyT

updater = None

# 各 LLM 提供商默认 API URL 映射（若用户未自定义则自动填充）
DEFAULT_LLM_API_URLS = {
    "OpenAI": "https://api.openai.com/v1/chat/completions",
    "Claude": "https://api.anthropic.com/v1/messages",
    "Gemini": "https://generativelanguage.googleapis.com/v1beta",
    "DeepSeek": "https://api.deepseek.com/chat/completions"
}


@dataclass
class ProgramInfo:
    version: str
    author: str
    email: str
    github: str
    license: Tuple[str, str]


def destroy_widgets(*widgets):
    """
    销毁一组控件对象并返回一个包含相同长度的None值的元组
    :param widgets: 需要被销毁的控件对象
    :return: 一个长度与输入控件数量相同的None值元组
    """
    length = len(widgets)
    destroyed_widgets = (None,) * length
    for i in range(length):
        widgets[i].destroy()
    return destroyed_widgets


def normalize_port_number(http_port_entry):
    """
    规范化端口号，确保端口号在0到65535之间。
    如果端口号为浮点数，将其四舍五入到最近的整数
    如果端口号>65535，将其设置为65535；如果端口号<1，将其设置为1

    :param http_port_entry: 端口号输入框
    """

    http_port = http_port_entry.get()
    try:
        http_port = float(http_port)
        http_port = int(round(http_port))
    except ValueError:
        http_port = 5000
        logger.warning("Invalid port number, set to default 5000")

    if http_port > 65535:
        http_port = 65535
        logger.warning("Port number too large, set to 65535")
    elif http_port < 1:
        http_port = 1
        logger.warning("Port number too small, set to 1")

    http_port_entry.delete(0, ctk.END)
    http_port_entry.insert(0, str(http_port))


def normalize_max_messages(max_messages_entry):
    """
    规范化最大消息数，确保其为正整数。
    如果输入为浮点数，将其四舍五入到最近的整数
    如果输入小于10，将其设置为10
    如果输入无法转换为数字，则设置一个默认值（100）

    :param max_messages_entry: 最大消息数输入框
    """

    max_messages_str = max_messages_entry.get()
    try:
        max_messages = float(max_messages_str)
        max_messages = int(max_messages + 0.5)
    except ValueError:
        max_messages = 100
        logger.warning("Invalid max messages, set to default 100")

    if max_messages < 10:
        max_messages = 10
        logger.warning("Max messages too small, set to 10")

    max_messages_entry.delete(0, ctk.END)
    max_messages_entry.insert(0, str(max_messages))


# noinspection PyUnresolvedReferences
def check_and_update(manual_check=False):
    logger.info("Checking for updates")
    if new_release := updater.check_update():
        logger.info(f"New release found: {new_release.get('tag_name')}")
        if messagebox.askyesno(_("Update available"),
                               f"{_('A new version of ModlessChatTrans is available:')} "
                               f"{new_release.get('tag_name')}\n"
                               f"{_('Do you want to download it now?')}"):
            if file_path := updater.download_update(new_release):
                messagebox.showinfo(_("Update downloaded"),
                                    f"{_('Update downloaded')}: {file_path}")
            else:
                messagebox.showerror(_("Update download failed"),
                                     _("Failed to download the update. "
                                       "Please check your internet connection and try again."))
    elif manual_check:
        logger.info("No update available")
        messagebox.showinfo(_("No update available"), _("No update available."))

    save_config(last_check_time=datetime.datetime.now().isoformat())


class MainInterfaceManager:
    def __init__(self, info: ProgramInfo, updater_object):
        self.info = info
        self.config = read_config()
        logger.info("Configuration loaded")

        self.main_window = None
        self.start_button = None
        self.http_port_entry = None
        self.http_port_label = None
        self.max_messages_entry = None
        self.max_messages_label = None

        self.llm_widgets = None
        self.traditional_widgets = None
        self.widgets = None
        self.service_var = None

        self.self_src_lang_var = None
        self.self_tgt_lang_var = None

        self.minecraft_log_folder_entry = None
        self.output_method_var = None
        self.self_translation_var = None
        self.always_on_top_var = None

        global updater
        updater = updater_object

    def create_main_window(self, **functions):
        """
        创建程序主窗口

        :param functions: 函数字典
        """

        # 创建主窗口
        self.main_window = ctk.CTk()
        self.main_window.title(f"Modless Chat Trans {self.info.version}")
        logger.info("Main window created")

        self.main_window.geometry(lang_window_size_map[read_config().interface_lang])

        self.main_window.resizable(False, False)

        self.main_window.rowconfigure(10, weight=1)
        self.main_window.columnconfigure(9, weight=1)

        self.main_window.protocol("WM_DELETE_WINDOW", self.on_closing)

        language_menu = tk.Menu(self.main_window, tearoff=0)

        language_menu.add_command(label="* Changes take effect after reboot")
        for lang, lang_code in supported_languages:
            language_menu.add_command(
                label=lang,
                command=lambda lc=lang_code: save_config(interface_lang=lc)
            )

        def show_language_menu(event):
            nonlocal language_menu
            try:
                language_menu.tk_popup(event.x_root, event.y_root)
            finally:
                language_menu.grab_release()

        self.create_config_widgets(self.main_window)

        self.start_button = ctk.CTkButton(
            self.main_window,
            text=_("Start"),
            font=("default", 60),
            command=lambda: self.prepare_translation_config(
                functions["start_translation"]
            )
        )
        self.start_button.grid(row=10, column=0, columnspan=2, padx=20, pady=10)

        choose_language_photo = tk.PhotoImage(file=get_path("choose_language.png"))
        choose_language_button = ctk.CTkButton(self.main_window, image=choose_language_photo, text="",
                                               width=50, height=50, fg_color="transparent", hover_color="white")
        choose_language_button.bind("<Button-1>", show_language_menu)
        choose_language_button.grid(row=11, column=0, padx=(0, 150))

        self.always_on_top_var = ctk.BooleanVar(value=self.config.always_on_top)
        always_on_top_button = ctk.CTkSwitch(self.main_window, text=_("Always on top"), font=("Arial", 15),
                                             variable=self.always_on_top_var, onvalue=True, offvalue=False)
        always_on_top_button.grid(row=11, column=1, padx=(0, 200), pady=15)

        more_settings_button = ctk.CTkButton(self.main_window, text="\u2699\uFE0F", font=("default", 36),
                                             width=50, height=60, fg_color="transparent", text_color="black",
                                             hover_color="white", command=functions["more_settings"])
        more_settings_button.grid(row=10, column=0, pady=10, sticky="w")

        about_button = ctk.CTkButton(self.main_window, text=_("About"), width=50, height=25,
                                     command=self.show_about_window)
        about_button.grid(row=11, column=2, padx=0, pady=15)

        # --------------- Check for updates ---------------
        ucf = self.config.update_check_frequency
        lct = self.config.last_check_time
        now = datetime.datetime.now()
        lct_date = datetime.datetime.fromisoformat(lct)

        if (
                (ucf == "Daily" and now.date() > lct_date.date()) or
                (ucf == "Weekly" and (now - lct_date).days >= 7) or
                (ucf == "Monthly" and (now - lct_date).days >= 30)
        ):
            check_and_update()
        # -------------------------------------------------

        self.main_window.mainloop()

    def show_about_window(self):
        """
        显示关于窗口
        """

        # 创建关于窗口
        about_window = ctk.CTkToplevel(self.main_window)
        about_window.title(_("About"))
        about_window.geometry("350x200")
        # noinspection PyTypeChecker
        about_window.after(50, about_window.grab_set)
        about_window.resizable(False, False)
        if platform == 0:
            hPyT.maximize_minimize_button.hide(about_window)
            hPyT.window_frame.center_relative(self.main_window, about_window)

        # 添加关于窗口的内容
        ctk.CTkLabel(about_window, text="Modless Chat Trans", font=("Arial", 20, "bold")).pack()
        ctk.CTkLabel(about_window, text=f"{_('Version')}: {self.info.version}").pack()
        ctk.CTkLabel(about_window, text=f"{_('Author')}: {self.info.author}").pack()
        ctk.CTkLabel(about_window, text=f"{_('Email')}: {self.info.email}").pack()
        github_url_label = ctk.CTkLabel(about_window, text=f"GitHub: {self.info.github}", cursor="hand2")
        github_url_label.bind("<Button-1>", lambda event: webbrowser.open_new(self.info.github))
        github_url_label.pack()
        license_label = ctk.CTkLabel(about_window, text=f"{_('License')}: {self.info.license[0]}", cursor="hand2")
        license_label.bind("<Button-1>", lambda event: webbrowser.open_new(self.info.license[1]))
        license_label.pack()

    def prepare_translation_config(self, start_translation):
        """
        准备翻译配置并启动翻译流程

        :param start_translation: 启动翻译流程的函数
        """

        self.start_button.configure(state="disabled")

        minecraft_log_folder = self.minecraft_log_folder_entry.get()

        output_method_map = {_("Graphical"): "Graphical", _("Speech"): "Speech", _("Httpserver"): "Httpserver"}
        output_method = output_method_map[self.output_method_var.get()]
        if output_method == "Httpserver" and hasattr(self.http_port_entry, "get"):
            http_port = int(self.http_port_entry.get())
            save_config(http_port=http_port)
            webbrowser.open_new(f"http://localhost:{http_port}")
        elif output_method == "Graphical":
            max_messages = int(self.max_messages_entry.get())
            save_config(max_messages=max_messages)

        self_translation_enabled = self.self_translation_var.get()

        always_on_top = self.always_on_top_var.get()

        trans_service = self.service_var.get()

        if trans_service in LLM_PROVIDERS:
            op_src_lang = self.widgets[0]["source_language_entry"].get()
            op_tgt_lang = self.widgets[0]["target_language_entry"].get()
            api_url = self.widgets[0]["api_url_entry"].get()
            api_key = self.widgets[0]["api_key_entry"].get()
            model = self.widgets[0]["model_entry"].get()

            save_config(op_src_lang=op_src_lang, op_tgt_lang=op_tgt_lang, api_url=api_url, api_key=api_key, model=model)

            if (
                    self_translation_enabled
                    and hasattr(self.widgets[0]["self_source_language_entry"], "get")
                    and hasattr(self.widgets[0]["self_target_language_entry"], "get")
            ):
                self_src_lang = self.widgets[0]["self_source_language_entry"].get()
                self_tgt_lang = self.widgets[0]["self_target_language_entry"].get()
                save_config(self_src_lang=self_src_lang, self_tgt_lang=self_tgt_lang)

        elif trans_service in services and trans_service not in LLM_PROVIDERS:
            op_src_lang = self.widgets[1]["source_language_menu"].get()
            op_tgt_lang = self.widgets[1]["target_language_menu"].get()
            save_config(op_src_lang=op_src_lang, op_tgt_lang=op_tgt_lang)

            if (
                    self_translation_enabled
                    and hasattr(self.widgets[1]["self_source_language_menu"], "get")
                    and hasattr(self.widgets[1]["self_target_language_menu"], "get")
            ):
                self_src_lang = self.widgets[1]["self_source_language_menu"].get()
                self_tgt_lang = self.widgets[1]["self_target_language_menu"].get()
                save_config(self_src_lang=self_src_lang, self_tgt_lang=self_tgt_lang)

            if self.widgets[1]["use_api_key_var"].get():
                traditional_api_key = self.widgets[1]["api_key_entry"].get()
            else:
                traditional_api_key = ""
            save_config(traditional_api_key=traditional_api_key)

        save_config(minecraft_log_folder=minecraft_log_folder, output_method=output_method, trans_service=trans_service,
                    self_trans_enabled=self_translation_enabled, always_on_top=always_on_top)

        logger.info(f"Starting translation with config: minecraft_log_folder={minecraft_log_folder}, "
                    f"output_method={output_method}, trans_service={trans_service}, "
                    f"self_translation_enabled={self_translation_enabled}, always_on_top={always_on_top}")

        start_translation()

    # noinspection PyUnresolvedReferences,PyTypedDict
    def update_service_widgets(self, service):
        """根据选择的翻译服务更新控件"""

        logger.info(f"Updating widgets for service: {service}")

        for i in range(len(self.widgets)):
            widgets = self.widgets[i]
            keys_to_destroy = [key for key in widgets if hasattr(widgets[key], "destroy")]
            widgets_to_destroy = [widgets[key] for key in keys_to_destroy]
            destroyed_dict = dict(zip(keys_to_destroy, destroy_widgets(*widgets_to_destroy)))
            self.widgets[i].update(destroyed_dict)

        if service in LLM_PROVIDERS:
            self.llm_widgets["source_language_entry"] = ctk.CTkEntry(self.main_window, width=400)
            self.llm_widgets["source_language_entry"].insert(0, self.config.op_src_lang)
            self.llm_widgets["source_language_entry"].grid(row=2, column=1, padx=20, pady=10, sticky="w")

            self.llm_widgets["target_language_entry"] = ctk.CTkEntry(self.main_window, width=400)
            self.llm_widgets["target_language_entry"].insert(0, self.config.op_tgt_lang)
            self.llm_widgets["target_language_entry"].grid(row=3, column=1, padx=20, pady=10, sticky="w")

            self.llm_widgets["api_url_label"] = ctk.CTkLabel(self.main_window, text=_("API URL:"))
            self.llm_widgets["api_url_label"].grid(row=4, column=0, padx=20, pady=10, sticky="w")
            self.llm_widgets["api_url_entry"] = ctk.CTkEntry(self.main_window, width=400)
            # 根据当前提供商填充默认 URL（若尚未保存自定义）
            preset_url = (
                self.config.api_url
                if self.config.trans_service == service and self.config.api_url
                else DEFAULT_LLM_API_URLS.get(service, "")
            )
            self.llm_widgets["api_url_entry"].insert(0, preset_url)
            self.llm_widgets["api_url_entry"].grid(row=4, column=1, padx=20, pady=10, sticky="w")

            self.llm_widgets["api_key_label"] = ctk.CTkLabel(self.main_window, text=_("API Key:"))
            self.llm_widgets["api_key_label"].grid(row=5, column=0, padx=20, pady=10, sticky="w")
            self.llm_widgets["api_key_entry"] = ctk.CTkEntry(self.main_window, width=400)
            self.llm_widgets["api_key_entry"].insert(0, self.config.api_key)
            self.llm_widgets["api_key_entry"].grid(row=5, column=1, padx=20, pady=10, sticky="w")

            self.llm_widgets["model_label"] = ctk.CTkLabel(self.main_window, text=_("Model:"))
            self.llm_widgets["model_label"].grid(row=6, column=0, padx=20, pady=10, sticky="w")
            self.llm_widgets["model_entry"] = ctk.CTkEntry(self.main_window, width=400)
            self.llm_widgets["model_entry"].insert(0, self.config.model)
            self.llm_widgets["model_entry"].grid(row=6, column=1, padx=20, pady=10, sticky="w")

        elif service in services and service not in LLM_PROVIDERS:
            self.main_window.title(f"Modless Chat Trans {self.info.version} - {_('Loading supported languages')}...")

            src_lang_var = ctk.StringVar(
                value=self.config.op_src_lang if self.config.op_src_lang in service_supported_languages[service]
                else service_supported_languages[service][0]
            )
            tgt_lang_var = ctk.StringVar(
                value=self.config.op_tgt_lang
                if self.config.op_tgt_lang in [l for l in service_supported_languages[service] if l != 'auto']
                else [l for l in service_supported_languages[service] if l != 'auto'][0]
            )

            self.traditional_widgets["source_language_menu"] = ctk.CTkOptionMenu(
                self.main_window, values=service_supported_languages[service], variable=src_lang_var)
            self.traditional_widgets["source_language_menu"].grid(row=2, column=1, padx=20, pady=10, sticky="w")

            if CTkScrollableDropdown is not None:
                try:
                    CTkScrollableDropdown(self.traditional_widgets["source_language_menu"],
                                          values=service_supported_languages[service])
                except Exception as e:
                    logger.debug(f"Failed to attach scrollable dropdown (src): {e}")

            self.traditional_widgets["target_language_menu"] = ctk.CTkOptionMenu(
                self.main_window,
                values=[l for l in service_supported_languages[service] if l != 'auto'],
                variable=tgt_lang_var
            )
            self.traditional_widgets["target_language_menu"].grid(row=3, column=1, padx=20, pady=10, sticky="w")

            if CTkScrollableDropdown is not None:
                try:
                    CTkScrollableDropdown(self.traditional_widgets["target_language_menu"],
                                          values=[l for l in service_supported_languages[service] if l != 'auto'])
                except Exception as e:
                    logger.debug(f"Failed to attach scrollable dropdown (tgt): {e}")

            self.traditional_widgets["use_api_key_var"] = ctk.BooleanVar(value=bool(self.config.traditional_api_key))
            self.traditional_widgets["use_api_key_checkbox"] = ctk.CTkCheckBox(
                self.main_window,
                text=_("I have an API Key"),
                variable=self.traditional_widgets["use_api_key_var"],
                command=self.on_use_api_key_toggle
            )
            self.traditional_widgets["use_api_key_checkbox"].grid(row=4, column=1, padx=20, pady=10, sticky="w")

            self.on_use_api_key_toggle()

            self.main_window.title(f"Modless Chat Trans {self.info.version}")

        self.on_self_translation_toggle()

    def create_service_widgets(self):
        """
        根据选定的翻译服务创建/删除配置控件
        """

        # global tgt_lang_var, src_lang_var

        self.llm_widgets = {
            "source_language_entry": None,
            "target_language_entry": None,
            "api_url_label": None,
            "api_url_entry": None,
            "api_key_label": None,
            "api_key_entry": None,
            "model_label": None,
            "model_entry": None,
            "self_source_language_entry": None,
            "self_target_language_entry": None,
            "self_source_language_label": None,
            "self_target_language_label": None
        }

        self.traditional_widgets = {
            "source_language_menu": None,
            "target_language_menu": None,
            "self_source_language_menu": None,
            "self_target_language_menu": None,
            "self_source_language_label": None,
            "self_target_language_label": None,
            "use_api_key_var": None,
            "use_api_key_checkbox": None,
            "api_key_entry": None,
            "api_key_label": None
        }

        self.widgets = [self.llm_widgets, self.traditional_widgets]
        default_service = self.config.trans_service if self.config.trans_service in services else LLM_PROVIDERS[0]
        self.service_var = ctk.StringVar(value=default_service)
        service_option_menu = ctk.CTkOptionMenu(self.main_window,
                                                values=services,
                                                variable=self.service_var,
                                                command=self.update_service_widgets)
        service_option_menu.grid(row=7, column=0, padx=20, pady=10, sticky="w")

        self.update_service_widgets(self.service_var.get())  # 初始化控件

    def on_use_api_key_toggle(self):
        """
        切换是否使用 API Key 的复选框时的回调函数
        """
        if self.traditional_widgets["use_api_key_var"].get():
            logger.info("API key enabled")
            if not self.traditional_widgets.get("api_key_entry"):
                self.traditional_widgets["api_key_label"] = ctk.CTkLabel(self.main_window, text=_("API Key:"))
                self.traditional_widgets["api_key_label"].grid(row=5, column=0, padx=20, pady=10, sticky="w")
                self.traditional_widgets["api_key_entry"] = ctk.CTkEntry(self.main_window, width=400)
                self.traditional_widgets["api_key_entry"].grid(row=5, column=1, padx=20, pady=10, sticky="w")
                self.traditional_widgets["api_key_entry"].insert(0, self.config.traditional_api_key)

        else:
            logger.info("API key disabled")
            if self.traditional_widgets.get("api_key_entry"):
                (self.traditional_widgets["api_key_label"],
                 self.traditional_widgets["api_key_entry"]) = destroy_widgets(
                    self.traditional_widgets["api_key_label"],
                    self.traditional_widgets["api_key_entry"]
                )

    def on_output_method_change(self, choice):
        """
        输出方式选择改变时的回调函数

        :param choice: 选择的输出方式
        """

        logger.info(f"Output method changed to: {choice}")

        if self.http_port_entry:
            self.http_port_label, self.http_port_entry = destroy_widgets(self.http_port_label,
                                                                         self.http_port_entry)
        if self.max_messages_entry:
            self.max_messages_label, self.max_messages_entry = destroy_widgets(self.max_messages_label,
                                                                               self.max_messages_entry)

        if choice == _("Httpserver"):
            self.http_port_label = ctk.CTkLabel(self.main_window, text=_("HTTP Port:"))
            self.http_port_label.grid(row=1, column=1, padx=(200, 0), pady=10, sticky="w")
            self.http_port_entry = ctk.CTkEntry(self.main_window, width=100)
            self.http_port_entry.grid(row=1, column=1, padx=(270, 0), pady=10, sticky="w")
            self.http_port_entry.insert(0, self.config.http_port)
            self.http_port_entry.bind("<FocusOut>", lambda event: normalize_port_number(self.http_port_entry))
        elif choice == _("Graphical"):
            self.max_messages_label = ctk.CTkLabel(self.main_window, text=_("Max Messages:"))
            self.max_messages_label.grid(row=1, column=1, padx=(190, 0), pady=10, sticky="w")
            self.max_messages_entry = ctk.CTkEntry(self.main_window, width=100)
            self.max_messages_entry.grid(row=1, column=1, padx=(320, 0), pady=10, sticky="w")
            self.max_messages_entry.insert(0, self.config.max_messages)
            self.max_messages_entry.bind("<FocusOut>", lambda event: normalize_max_messages(self.max_messages_entry))

    def on_self_translation_toggle(self):
        """
        自翻译开关切换时的回调函数
        """

        if self.self_translation_var.get():
            logger.info("Self translation enabled")
        else:
            logger.info("Self translation disabled")

        service = self.service_var.get()

        if self.self_translation_var.get():

            if service in LLM_PROVIDERS:
                if not self.widgets[0]["self_source_language_entry"]:
                    self.widgets[0]["self_source_language_label"] = ctk.CTkLabel(self.main_window,
                                                                                 text=_("Self Source Language:"))
                    self.widgets[0]["self_source_language_label"].grid(row=8, column=0, padx=20, pady=10, sticky="w")
                    self.widgets[0]["self_source_language_entry"] = ctk.CTkEntry(self.main_window, width=400)
                    self.widgets[0]["self_source_language_entry"].grid(row=8, column=1, padx=20, pady=10, sticky="w")
                    self.widgets[0]["self_source_language_entry"].insert(0, self.config.self_src_lang)
                if not self.widgets[0]["self_target_language_entry"]:
                    self.widgets[0]["self_target_language_label"] = ctk.CTkLabel(self.main_window,
                                                                                 text=_("Self Target Language:"))
                    self.widgets[0]["self_target_language_label"].grid(row=9, column=0, padx=20, pady=10, sticky="w")
                    self.widgets[0]["self_target_language_entry"] = ctk.CTkEntry(self.main_window, width=400)
                    self.widgets[0]["self_target_language_entry"].grid(row=9, column=1, padx=20, pady=10, sticky="w")
                    self.widgets[0]["self_target_language_entry"].insert(0, self.config.self_tgt_lang)
            elif service in services and service not in LLM_PROVIDERS:
                if not self.widgets[1]["self_source_language_menu"]:
                    self.widgets[1]["self_source_language_label"] = ctk.CTkLabel(self.main_window,
                                                                                 text=_("Self Source Language:"))
                    self.widgets[1]["self_source_language_label"].grid(row=8, column=0, padx=20, pady=10, sticky="w")
                    self.self_src_lang_var = ctk.StringVar(
                        value=self.config.self_src_lang if self.config.self_src_lang in service_supported_languages[
                            service]
                        else service_supported_languages[service][0]
                    )
                    self.widgets[1]["self_source_language_menu"] = ctk.CTkOptionMenu(
                        self.main_window, values=service_supported_languages[service], variable=self.self_src_lang_var)
                    self.widgets[1]["self_source_language_menu"].grid(row=8, column=1, padx=20, pady=10, sticky="w")
                    if CTkScrollableDropdown is not None:
                        try:
                            CTkScrollableDropdown(self.widgets[1]["self_source_language_menu"],
                                                  values=service_supported_languages[service])
                        except Exception as e:
                            logger.debug(f"Failed to attach scrollable dropdown (self src): {e}")
                if not self.widgets[1]["self_target_language_menu"]:
                    self.widgets[1]["self_target_language_label"] = ctk.CTkLabel(self.main_window,
                                                                                 text=_("Self Target Language:"))
                    self.widgets[1]["self_target_language_label"].grid(row=9, column=0, padx=20, pady=10, sticky="w")
                    self.self_tgt_lang_var = ctk.StringVar(
                        value=self.config.self_tgt_lang
                        if self.config.self_tgt_lang in [l for l in service_supported_languages[service] if l != 'auto']
                        else [l for l in service_supported_languages[service] if l != 'auto'][0]
                    )
                    self.widgets[1]["self_target_language_menu"] = ctk.CTkOptionMenu(
                        self.main_window,
                        values=[l for l in service_supported_languages[service] if l != 'auto'],
                        variable=self.self_tgt_lang_var
                    )
                    self.widgets[1]["self_target_language_menu"].grid(row=9, column=1, padx=20, pady=10, sticky="w")
                    if CTkScrollableDropdown is not None:
                        try:
                            CTkScrollableDropdown(self.widgets[1]["self_target_language_menu"],
                                                  values=[l for l in service_supported_languages[service] if
                                                          l != 'auto'])
                        except Exception as e:
                            logger.debug(f"Failed to attach scrollable dropdown (self tgt): {e}")
        else:
            if service in LLM_PROVIDERS:
                if self.widgets[0]["self_source_language_entry"]:
                    (self.widgets[0]["self_source_language_label"],
                     self.widgets[0]["self_source_language_entry"]) = destroy_widgets(
                        self.widgets[0]["self_source_language_label"],
                        self.widgets[0]["self_source_language_entry"]
                    )
                if self.widgets[0]["self_target_language_entry"]:
                    (self.widgets[0]["self_target_language_label"],
                     self.widgets[0]["self_target_language_entry"]) = destroy_widgets(
                        self.widgets[0]["self_target_language_label"],
                        self.widgets[0]["self_target_language_entry"]
                    )
            elif service in services and service not in LLM_PROVIDERS:
                if self.widgets[1]["self_source_language_menu"]:
                    (self.widgets[1]["self_source_language_label"],
                     self.widgets[1]["self_source_language_menu"]) = destroy_widgets(
                        self.widgets[1]["self_source_language_label"],
                        self.widgets[1]["self_source_language_menu"]
                    )
                if self.widgets[1]["self_target_language_menu"]:
                    (self.widgets[1]["self_target_language_label"],
                     self.widgets[1]["self_target_language_menu"]) = destroy_widgets(
                        self.widgets[1]["self_target_language_label"],
                        self.widgets[1]["self_target_language_menu"]
                    )

        self.main_window.update()

    def create_config_widgets(self, main_window):
        """
        创建配置控件

        :param main_window: 配置窗口对象
        """

        if self.config.output_method not in {"Graphical", "Speech", "Httpserver"}:
            self.config.output_method = "Graphical"

        # Minecraft Log Folder
        minecraft_log_folder_label = ctk.CTkLabel(main_window, text=_("Minecraft Log Folder:"))
        minecraft_log_folder_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        self.minecraft_log_folder_entry = ctk.CTkEntry(main_window, width=400)
        self.minecraft_log_folder_entry.insert(0, self.config.minecraft_log_folder)
        self.minecraft_log_folder_entry.grid(row=0, column=1, padx=20, pady=10, sticky="w")

        # Output Method
        self.on_output_method_change(_(self.config.output_method))
        output_method_label = ctk.CTkLabel(main_window, text=_("Output Method:"))
        output_method_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        self.output_method_var = ctk.StringVar(value=_(self.config.output_method))
        output_method_optionmenu = ctk.CTkOptionMenu(main_window,
                                                     values=[_("Graphical"), _("Speech"), _("Httpserver")],
                                                     variable=self.output_method_var,
                                                     command=self.on_output_method_change)
        output_method_optionmenu.grid(row=1, column=1, padx=20, pady=10, sticky="w")

        # Source Language
        source_language_label = ctk.CTkLabel(main_window, text=_("Source Language(Auto if blank):"))
        source_language_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")

        # Target Language
        target_language_label = ctk.CTkLabel(main_window, text=_("Target Language:"))
        target_language_label.grid(row=3, column=0, padx=20, pady=10, sticky="w")

        # Self Translation Toggle
        self.self_translation_var = ctk.BooleanVar(value=self.config.self_trans_enabled)
        self_translation_toggle = ctk.CTkCheckBox(main_window, text=_("Translate Player's Own Message"),
                                                  variable=self.self_translation_var,
                                                  command=self.on_self_translation_toggle)
        self_translation_toggle.grid(row=7, column=1, padx=20, pady=10, sticky="w")

        self.create_service_widgets()

        # self.on_self_translation_toggle()

    def on_closing(self):
        self.main_window.title(f"Modless Chat Trans {self.info.version} - Exiting...")
        from modless_chat_trans.translator import flush_pending_tokens
        flush_pending_tokens()
        logger.info(f"Cumulative tokens consumed")
        from modless_chat_trans.file_utils import cache
        cache.close()
        logger.info("Cache saved")
        self.main_window.destroy()
        logger.info("Application closed")


class MoreSettingsManager:
    def __init__(self, main_window, config):
        self.main_window = main_window
        self.config = config
        self.more_settings_window = None
        self.variables = {}

    def create_more_settings_window(self):
        self.more_settings_window = ctk.CTkToplevel(self.main_window)
        self.more_settings_window.title(_("More Settings"))
        self.more_settings_window.geometry(
            "460x420" if self.config.interface_lang in {"fr_FR", "es_ES", "ru_RU", "pt_BR"} else "400x420"
        )
        # noinspection PyTypeChecker
        self.more_settings_window.after(50, self.more_settings_window.grab_set)
        self.more_settings_window.resizable(False, False)
        logger.info("More settings window created")

        # 在打开窗口时刷新配置，确保显示最新的累计 token 数
        self.config = read_config()

        if platform == 0:
            hPyT.maximize_minimize_button.hide(self.more_settings_window)

        self.create_additional_widgets()

    def open_glossary_window(self):
        logger.info("Opening Glossary window")
        self.config = read_config()
        glossary_manager = GlossaryManager(self.more_settings_window, self.config)
        glossary_manager.create_glossary_window()

    def create_additional_widgets(self):
        # 定义所有控件的配置
        widgets_config = [
            {
                'type': 'label_optionmenu',
                'label': _("Automatic Update Frequency"),
                'var_name': 'update_check_frequency',
                'var_type': 'string',
                'default': _(
                    self.config.update_check_frequency
                    if self.config.update_check_frequency in {
                        "On Startup", "Daily", "Weekly", "Monthly", "Never"
                    }
                    else "Daily"
                ),
                'options': [_("On Startup"), _("Daily"), _("Weekly"), _("Monthly"), _("Never")],
                'row': 0
            },
            {
                'type': 'checkbox',
                'text': _("Include Pre-release"),
                'var_name': 'include_prerelease',
                'var_type': 'boolean',
                'default': self.config.include_prerelease,
                'row': 1,
                'column': 0
            },
            {
                'type': 'button',
                'text': _("Check for Updates"),
                'command': lambda: check_and_update(manual_check=True),
                'row': 1,
                'column': 1
            },
            {
                'type': 'checkbox',
                'text': _("Enable Translation Quality Optimization"),
                'var_name': 'enable_optimization',
                'var_type': 'boolean',
                'default': self.config.enable_optimization,
                'tooltip': (
                        _("Enabling this will improve translation quality, "
                          "but will increase latency and consume more tokens")
                        + f"\n{_('Cumulative tokens consumed')}: {self.config.total_tokens}"
                ),
                'row': 2,
                'columnspan': 2
            },
            {
                'type': 'checkbox',
                'text': _("Enable High Version Fix"),
                'var_name': 'use_high_version_fix',
                'var_type': 'boolean',
                'default': self.config.use_high_version_fix,
                'tooltip': _(
                    "Enabling this will temporarily fix the issue of logs "
                    "not being captured in high versions of Minecraft\n"
                    "If it doesn't work, restart this program"
                ),
                'row': 3,
                'columnspan': 2
            },
            {
                'type': 'checkbox',
                'text': _("Translate System Messages"),
                'var_name': 'trans_sys_message',
                'var_type': 'boolean',
                'default': self.config.trans_sys_message,
                'tooltip': _(
                    "Enable this will translate system messages "
                    "(messages without names)"
                ),
                'row': 4,
                'columnspan': 2
            },
            {
                'type': 'checkbox',
                'text': _("Replace Garbled Characters"),
                'var_name': 'replace_garbled_character',
                'var_type': 'boolean',
                'default': self.config.replace_garbled_character,
                'tooltip': _(
                    "Replace all garbled characters with "
                    "Minecraft formatting codes"
                ),
                'row': 5,
                'columnspan': 2
            },
            {
                'type': 'label_entry',
                'label': _("Log Encoding"),
                'var_name': 'encoding',
                'var_type': 'string',
                'default': self.config.encoding,
                'tooltip': _(
                    "Manually specify the log encoding\n"
                    "If there are garbled characters, try changing this value\n"
                    "Leave it blank for automatic detection"
                ),
                'row': 6
            },
            {
                'type': 'button',
                'text': _("Glossary"),
                'command': self.open_glossary_window,
                'row': 7,
                'columnspan': 2,
                'sticky': 'ew'
            },
            {
                'type': 'button',
                'text': _("Save Settings"),
                'command': self.save_more_settings,
                'row': 8,
                'columnspan': 2,
                'pady': 20,
                'sticky': ''
            }
        ]

        # 创建所有控件
        for config in widgets_config:
            self._create_widget(config)

    def _create_widget(self, config):
        """根据配置创建单个控件"""
        widget_type = config['type']
        row = config['row']
        column = config.get('column', 0)
        columnspan = config.get('columnspan', 1)
        padx = config.get('padx', 20)
        pady = config.get('pady', 10)
        sticky = config.get('sticky', 'w')

        # 创建变量
        if 'var_name' in config:
            var_type = config['var_type']
            if var_type == 'string':
                self.variables[config['var_name']] = ctk.StringVar(value=config['default'])
            elif var_type == 'boolean':
                self.variables[config['var_name']] = ctk.BooleanVar(value=config['default'])

        # 创建控件
        if widget_type == 'label_optionmenu':
            # 创建标签
            ctk.CTkLabel(
                self.more_settings_window,
                text=config['label']
            ).grid(row=row, column=0, padx=padx, pady=pady, sticky=sticky)

            # 创建选项菜单
            ctk.CTkOptionMenu(
                self.more_settings_window,
                values=config['options'],
                variable=self.variables[config['var_name']]
            ).grid(row=row, column=1, padx=padx, pady=pady, sticky=sticky)

        elif widget_type == 'checkbox':
            checkbox = ctk.CTkCheckBox(
                self.more_settings_window,
                text=config['text'],
                variable=self.variables[config['var_name']]
            )
            checkbox.grid(row=row, column=column, columnspan=columnspan,
                          padx=padx, pady=pady, sticky=sticky)

            # 添加工具提示（如果有）
            if 'tooltip' in config:
                ToolTip(checkbox, config['tooltip'], delay=0.3)

        elif widget_type == 'button':
            ctk.CTkButton(
                self.more_settings_window,
                text=config['text'],
                command=config['command']
            ).grid(row=row, column=column, columnspan=columnspan,
                   padx=padx, pady=pady, sticky=sticky)

        elif widget_type == 'label_entry':
            # 创建标签
            label = ctk.CTkLabel(
                self.more_settings_window,
                text=config['label']
            )
            label.grid(row=row, column=0, padx=padx, pady=pady, sticky=sticky)

            # 添加工具提示（如果有）
            if 'tooltip' in config:
                ToolTip(label, config['tooltip'], delay=0.3)

            # 创建输入框
            ctk.CTkEntry(
                self.more_settings_window,
                textvariable=self.variables[config['var_name']]
            ).grid(row=row, column=1, padx=padx, pady=pady, sticky=sticky)

    def save_more_settings(self):
        update_check_frequency_map = {
            _("On Startup"): "On Startup",
            _("Daily"): "Daily",
            _("Weekly"): "Weekly",
            _("Monthly"): "Monthly",
            _("Never"): "Never"
        }

        config_keys = [
            "include_prerelease",
            "enable_optimization",
            "use_high_version_fix",
            "trans_sys_message",
            "encoding",
            "replace_garbled_character"
        ]

        # 批量获取配置值
        config_values = {key: self.variables[key].get() for key in config_keys}

        config_values["update_check_frequency"] = update_check_frequency_map[
            self.variables["update_check_frequency"].get()
        ]

        logger.info("Saving more settings")
        save_config(**config_values)
        self.more_settings_window.destroy()


class ChatInterfaceManager:
    def __init__(self, main_window, max_messages=150, always_on_top=False):
        self.main_window = main_window
        self.chat_window = None
        self.chat_frame = None
        self.canvas = None
        self.scrollbar = None
        self.messages = deque(maxlen=max_messages)
        self.displayed_messages = []
        self.always_on_top = always_on_top

    def start(self):
        self.chat_window = ctk.CTkToplevel(self.main_window)
        self.chat_window.title(_("Translated Message"))
        self.chat_window.geometry("700x400")
        logger.info("Chat window created")

        self.chat_window.attributes("-topmost", self.always_on_top)

        self.canvas = ctk.CTkCanvas(self.chat_window, bg="#EAF6FF", highlightthickness=0)
        self.scrollbar = ctk.CTkScrollbar(self.chat_window, command=self.canvas.yview)
        self.chat_frame = ctk.CTkFrame(self.canvas, fg_color="#EAF6FF")

        self.canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.chat_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.chat_window.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)

    def display(self, name, message):
        """
        显示消息，使用聊天气泡样式，并添加逐字展开的动画效果
        :param name: 发送者名称
        :param message: 消息内容
        """
        logger.debug(f"Displaying message from {name}: {message}")
        self.messages.append((name, message))
        self._append_message(name, message)

        # 自动滚动到最新消息
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _append_message(self, name, message):
        """
        追加单条消息到显示区域，并添加逐字展开动画
        """
        message_frame = ctk.CTkFrame(
            self.chat_frame,
            fg_color="#FFFFFF",
            corner_radius=10,
            border_width=1,
            border_color="#D0E8FF",
        )
        message_frame.pack(fill="x", pady=5, padx=10, anchor="w")

        # 当显示的message_frame数量大于等于消息的最大限制数量时，移除最旧的message_frame
        if len(self.displayed_messages) >= self.messages.maxlen:
            oldest_message_frame = self.displayed_messages.pop(0)
            oldest_message_frame.destroy()

        self.displayed_messages.append(message_frame)

        # 显示昵称
        if name:
            name_label = ctk.CTkLabel(
                message_frame,
                text=name,
                font=("SimSun", 12, "bold"),
                text_color="#007ACC",
            )
            name_label.pack(anchor="w", padx=10, pady=(5, 0))

        message_label = ctk.CTkLabel(
            message_frame,
            text="",  # 初始内容为空
            font=("SimSun", 14),
            text_color="#333333",
            wraplength=500,  # 自动换行
            justify="left",
        )
        message_label.pack(anchor="w", padx=10, pady=(0, 5))

        # 开始逐字展开动画
        try:
            self._animate_text(message_label, message)
        except Exception as e:
            logger.error(f"Error in animation: {str(e)}")
            message_label.configure(text=message)

    def _animate_text(self, label, full_text, index=0, delay=5, step=5):
        """
        动画效果：按 step 个字符为单位逐步展开消息内容
        :param label: 消息标签
        :param full_text: 完整的消息内容
        :param index: 当前显示到的字符索引
        :param delay: 每帧的延迟时间（毫秒）
        :param step: 每次更新的字符数量
        """
        if index < len(full_text):
            new_index = min(index + step, len(full_text))
            label.configure(text=full_text[:new_index])
            label.after(delay, self._animate_text, label, full_text, new_index, delay, step)

    def _on_mouse_wheel(self, event):
        """
        鼠标滚轮事件处理函数，用于滚动聊天窗口。
        """
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")


class GlossaryManager:
    def __init__(self, main_window, config):
        self.main_window = main_window
        self.config = config
        self.glossary_window = None
        # 输入控件
        self.src_entry = None
        self.tgt_entry = None
        self.add_button = None
        # 列表显示控件
        self.glossary_frame = None  # 将使用 CTkScrollableFrame
        self.term_buttons = {}  # 存储按钮以便更新状态 {src: button_widget}
        # 删除和保存控件
        self.delete_button = None
        self.save_button = None
        # 状态变量
        self.selected_term_src = None  # 当前选中的源术语
        self.glossary_rules = {}
        if hasattr(config, 'glossary') and isinstance(config.glossary, dict):
            self.glossary_rules = config.glossary.copy()
            logger.info(f"Loaded glossary rules: {len(self.glossary_rules)}")
        else:
            logger.warning("Glossary in config is not a dictionary or missing. Initializing as empty.")

    def create_glossary_window(self):
        """创建术语表窗口"""
        self.glossary_window = ctk.CTkToplevel(self.main_window)
        self.glossary_window.title(_("Glossary"))
        self.glossary_window.geometry("550x450")
        # noinspection PyTypeChecker
        self.glossary_window.after(50, self.glossary_window.grab_set)
        self.glossary_window.resizable(False, False)
        logger.info("Glossary window created")

        if platform == 0:
            hPyT.maximize_minimize_button.hide(self.glossary_window)
            hPyT.window_frame.center_relative(self.main_window, self.glossary_window)

        self._create_widgets()
        self._update_glossary_display()  # 初始加载并显示术语列表

    def _create_widgets(self):
        """在术语表窗口中创建控件"""
        # --- 输入区域 ---
        input_frame = ctk.CTkFrame(self.glossary_window)
        input_frame.pack(pady=10, padx=10, fill="x")

        ctk.CTkLabel(input_frame, text=_("Source Term:")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.src_entry = ctk.CTkEntry(input_frame, width=180)
        self.src_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(input_frame, text=_("Target Term:")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.tgt_entry = ctk.CTkEntry(input_frame, width=180)
        self.tgt_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.add_button = ctk.CTkButton(input_frame, text=_("Add/Update Term"), command=self._add_update_term)
        self.add_button.grid(row=0, column=2, rowspan=2, padx=10, pady=5)

        input_frame.columnconfigure(1, weight=1)

        # --- 术语列表显示区域 ---
        self.glossary_frame = ctk.CTkScrollableFrame(self.glossary_window, label_text=_("Glossary Rules"))
        self.glossary_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # --- 操作按钮区域 ---
        button_frame = ctk.CTkFrame(self.glossary_window)
        button_frame.pack(pady=10, padx=10, fill="x")

        self.delete_button = ctk.CTkButton(button_frame, text=_("Delete Selected"), command=self._delete_selected_term,
                                           state="disabled")
        self.delete_button.pack(side="left", padx=10)

        self.save_button = ctk.CTkButton(button_frame, text=_("Save Glossary and Close"), command=self._save_glossary)
        self.save_button.pack(side="right", padx=10)

    def _update_glossary_display(self):
        """清空并重新填充术语列表显示区域"""
        # 清空旧按钮
        for widget in self.glossary_frame.winfo_children():
            widget.destroy()
        self.term_buttons.clear()
        self.selected_term_src = None
        self.delete_button.configure(state="disabled")

        if not self.glossary_rules:
            ctk.CTkLabel(self.glossary_frame, text=_("<No glossary rules defined>")).pack(pady=5)
            return

        # 按源术语排序显示
        sorted_sources = sorted(self.glossary_rules.keys())

        for src in sorted_sources:
            tgt = self.glossary_rules[src]
            display_text = f"\"{src}\" → \"{tgt}\""

            # 为每个条目创建一个按钮
            term_button = ctk.CTkButton(
                self.glossary_frame,
                text=display_text,
                anchor="w",  # 文本左对齐
                fg_color="transparent",  # 默认透明背景
                text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"],  # 使用标签的文本颜色
                hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"],  # 悬停颜色
                command=lambda s=src: self._on_term_select(s)  # 使用 lambda 传递当前 src
            )
            term_button.pack(fill="x", pady=2, padx=5)
            self.term_buttons[src] = term_button

    def _on_term_select(self, clicked_src):
        """当用户点击列表中的术语按钮时调用"""
        logger.debug(f"Term button clicked: {clicked_src}")

        # --- 检查是否点击了当前已选项，如果是则取消选择 ---
        if clicked_src == self.selected_term_src:

            # 恢复按钮视觉效果为未选中
            if clicked_src in self.term_buttons:
                try:
                    self.term_buttons[clicked_src].configure(
                        fg_color="transparent",
                        text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"]
                    )
                except tk.TclError as e:
                    logger.warning(f"TclError resetting style for deselected button '{clicked_src}': {e}")
                except KeyError:
                    logger.warning(f"KeyError: Button for '{clicked_src}' not found during deselect.")

            # 更新状态变量
            self.selected_term_src = None

            # 更新UI状态
            self.delete_button.configure(state="disabled")
            self.src_entry.delete(0, ctk.END)
            self.tgt_entry.delete(0, ctk.END)

            return  # 取消选择操作完成，提前退出

        # --- 如果未点击已选项，则执行原有的选择逻辑 ---

        # --- 更新视觉效果 ---
        # 取消之前选中项的高亮
        if self.selected_term_src and self.selected_term_src in self.term_buttons:
            try:
                # 恢复按钮的默认外观
                self.term_buttons[self.selected_term_src].configure(
                    fg_color="transparent",
                    text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"]
                )
            except tk.TclError:
                logger.warning(f"Could not reset style for button: {self.selected_term_src}")

        # 高亮新选中项
        self.selected_term_src = clicked_src
        if self.selected_term_src in self.term_buttons:
            try:
                # 设置选中时的外观
                self.term_buttons[self.selected_term_src].configure(
                    fg_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"],  # 使用悬停色作为选中色
                    text_color=ctk.ThemeManager.theme["CTkButton"]["text_color"]  # 使用按钮的文本颜色
                )
            except tk.TclError:
                logger.warning(f"Could not set style for selected button: {self.selected_term_src}")

        # --- 启用删除按钮 ---
        self.delete_button.configure(state="normal")

        # --- 填充输入框以便编辑 ---
        if clicked_src in self.glossary_rules:
            try:
                tgt_term = self.glossary_rules[clicked_src]
                # 先清空当前输入框内容
                self.src_entry.delete(0, ctk.END)
                self.tgt_entry.delete(0, ctk.END)
                # 插入选中的术语
                self.src_entry.insert(0, clicked_src)
                self.tgt_entry.insert(0, tgt_term)
                logger.debug(f"Populated input fields with: '{clicked_src}' -> '{tgt_term}'")
            except Exception as e:
                logger.error(f"Error populating input fields for '{clicked_src}': {e}")
                self.src_entry.delete(0, ctk.END)
                self.tgt_entry.delete(0, ctk.END)
        else:
            # 理论上不应该发生，因为 selected_src 来自 glossary_rules 的键
            logger.warning(
                f"Selected source term '{clicked_src}' not found in glossary_rules dict when trying to populate fields.")
            # 清空输入框
            self.src_entry.delete(0, ctk.END)
            self.tgt_entry.delete(0, ctk.END)

    def _add_update_term(self):
        """添加或更新一个术语对。优先处理选中的规则进行修改。"""
        current_src = self.src_entry.get().strip()
        current_tgt = self.tgt_entry.get().strip()

        if not current_src:
            messagebox.showwarning(_("Input Error"), _("Source term cannot be empty."), parent=self.glossary_window)
            return

        original_selected_src = self.selected_term_src  # 获取当前选中的源术语（可能是 None）

        if original_selected_src is not None:
            # --- 处理选中的规则 ---
            logger.debug(
                f"Processing with selected rule: Original='{original_selected_src}', Current Input='{current_src}'")

            if original_selected_src == current_src:
                # Case 1: 源术语未变，仅更新目标术语
                if self.glossary_rules.get(original_selected_src) != current_tgt:
                    self.glossary_rules[original_selected_src] = current_tgt
                    logger.info(f"Glossary rule target updated: '{original_selected_src}' -> '{current_tgt}'")
                else:
                    logger.info(f"Glossary rule target unchanged for '{original_selected_src}'.")
                    # 可选：给用户提示"无更改"
            else:
                # Case 2: 源术语被修改，需要"重命名"规则键
                # 检查新源术语是否与 其他 现有规则冲突 (除了原本选中的那个)
                if current_src in self.glossary_rules and current_src != original_selected_src:
                    if not messagebox.askyesno(_("Confirm Overwrite"),
                                               _("The new source term '{0}' already exists. Overwrite it?").format(
                                                   current_src),
                                               parent=self.glossary_window):
                        logger.info("Rule modification cancelled by user due to potential overwrite.")
                        return  # 用户取消操作

                # 先删除旧规则
                del self.glossary_rules[original_selected_src]
                logger.debug(f"Removed old rule key: '{original_selected_src}'")
                # 添加新规则（使用新源作为键）
                self.glossary_rules[current_src] = current_tgt
                logger.info(
                    f"Glossary rule modified (source changed): '{current_src}' -> '{current_tgt}' (Original was '{original_selected_src}')")

            # 操作完成后，清除选中状态和输入框
            self.selected_term_src = None  # 重置选中状态
            self.src_entry.delete(0, ctk.END)
            self.tgt_entry.delete(0, ctk.END)
            self._update_glossary_display()  # 刷新列表

        else:
            # --- 没有选中规则，执行旧逻辑：添加或更新 ---
            action = "updated (no selection)" if current_src in self.glossary_rules else "added"
            # 检查是否有实际更改，避免不必要的日志和刷新
            if self.glossary_rules.get(current_src) != current_tgt:
                self.glossary_rules[current_src] = current_tgt
                logger.info(f"Glossary rule {action}: '{current_src}' -> '{current_tgt}'")
                # 清空输入框
                self.src_entry.delete(0, ctk.END)
                self.tgt_entry.delete(0, ctk.END)

                # 刷新列表显示
                self._update_glossary_display()

    def _delete_selected_term(self):
        """删除当前选中的术语"""
        if self.selected_term_src is None:
            logger.warning("Delete button clicked but no term selected.")
            return

        if self.selected_term_src in self.glossary_rules:
            del self.glossary_rules[self.selected_term_src]
            logger.info(f"Glossary rule deleted: {self.selected_term_src}")
            # 刷新列表显示 (这会自动取消选择并禁用删除按钮)
            self._update_glossary_display()
        else:
            logger.error(f"Selected term '{self.selected_term_src}' not found in rules for deletion.")
            self._update_glossary_display()

    def _save_glossary(self):
        try:
            save_config(glossary=self.glossary_rules)
            logger.info(f"Glossary dictionary saved successfully with {len(self.glossary_rules)} rules.")
            self.glossary_window.destroy()
        except Exception as e:
            logger.error(f"Failed to save glossary: {e}")
