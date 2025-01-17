# Copyright (C) 2024 LiJiaHua1024
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
import hPyT
import webbrowser
from dataclasses import dataclass
from collections import deque
from modless_chat_trans.file_utils import read_config, save_config, get_path
from modless_chat_trans.i18n import _, supported_languages, lang_window_size_map
from modless_chat_trans.translator import service_supported_languages


@dataclass
class ProgramInfo:
    version: str
    author: str
    email: str
    github: str
    license: tuple[str, str]


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


class InterfaceManager:
    def __init__(self, info: ProgramInfo):
        self.info = info
        self.config = read_config()

        self.main_window = None
        self.start_button = None
        self.http_port_entry = None
        self.http_port_label = None
        self.max_messages_entry = None
        self.max_messages_label = None

        self.llm_widgets = None
        self.traditional_widgets = None
        self.services = None
        self.service_var = None

        self.self_src_lang_var = None
        self.self_tgt_lang_var = None

        self.minecraft_log_folder_entry = None
        self.output_method_var = None
        self.self_translation_var = None

    def create_main_window(self, start_translation):
        """
        创建程序主窗口

        :param start_translation: 启动翻译流程的函数
        """

        # 创建主窗口
        self.main_window = ctk.CTk()
        self.main_window.title(f"Modless Chat Trans {self.info.version}")

        self.main_window.geometry(lang_window_size_map[read_config().interface_lang])

        self.main_window.resizable(False, False)

        self.main_window.rowconfigure(10, weight=1)
        self.main_window.columnconfigure(9, weight=1)

        language_menu = tk.Menu(self.main_window, tearoff=0)

        language_menu.add_command(label="* Changes take effect after reboot")
        for lang, lang_code in supported_languages:
            language_menu.add_command(
                label=lang,
                command=lambda lang_code=lang_code: save_config(interface_lang=lang_code)
            )

        def show_language_menu(event):
            nonlocal language_menu
            try:
                language_menu.tk_popup(event.x_root, event.y_root)
            finally:
                language_menu.grab_release()

        self.create_config_widgets(self.main_window)

        self.start_button = ctk.CTkButton(self.main_window, text=_("Start"), font=("default", 60),
                                          command=lambda: self.prepare_translation_config(start_translation))
        self.start_button.grid(row=10, column=0, columnspan=2, padx=20, pady=10)

        choose_language_photo = tk.PhotoImage(file=get_path("choose_language.png"))
        choose_language_button = ctk.CTkButton(self.main_window, image=choose_language_photo, text="",
                                               width=50, height=50, fg_color="transparent", hover_color="white")
        choose_language_button.bind("<Button-1>", show_language_menu)
        choose_language_button.grid(row=11, column=0, padx=(0, 150))

        about_button = ctk.CTkButton(self.main_window, text=_("About"), width=50, height=25,
                                     command=self.show_about_window)
        about_button.grid(row=11, column=2, padx=0, pady=15)

        hPyT.maximize_minimize_button.hide(self.main_window)

        self.main_window.mainloop()

    def show_about_window(self):
        """
        显示关于窗口
        """

        # 创建关于窗口
        about_window = ctk.CTkToplevel(self.main_window)
        about_window.title(_("About"))
        about_window.geometry("350x200")
        about_window.grab_set()
        about_window.resizable(False, False)
        hPyT.maximize_minimize_button.hide(about_window)

        # 添加关于窗口的内容
        ctk.CTkLabel(about_window, text="Modless Chat Trans", font=("Arial", 20, "bold")).pack()
        ctk.CTkLabel(about_window, text=f"{_("Version")}: {self.info.version}").pack()
        ctk.CTkLabel(about_window, text=f"{_("Author")}: {self.info.author}").pack()
        ctk.CTkLabel(about_window, text=f"{_("Email")}: {self.info.email}").pack()
        github_url_label = ctk.CTkLabel(about_window, text=f"GitHub: {self.info.github}", cursor="hand2")
        github_url_label.bind("<Button-1>", lambda event: webbrowser.open_new(self.info.github))
        github_url_label.pack()
        license_label = ctk.CTkLabel(about_window, text=f"{_("License")}: {self.info.license[0]}", cursor="hand2")
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

        trans_service = self.service_var.get()

        if trans_service == "LLM":
            op_src_lang = self.services[0]["source_language_entry"].get()
            op_tgt_lang = self.services[0]["target_language_entry"].get()
            api_url = self.services[0]["api_url_entry"].get()
            api_key = self.services[0]["api_key_entry"].get()
            model = self.services[0]["model_entry"].get()

            save_config(op_src_lang=op_src_lang, op_tgt_lang=op_tgt_lang, api_url=api_url, api_key=api_key, model=model)

            if (
                    self_translation_enabled
                    and hasattr(self.services[0]["self_source_language_entry"], "get")
                    and hasattr(self.services[0]["self_target_language_entry"], "get")
            ):
                self_src_lang = self.services[0]["self_source_language_entry"].get()
                self_tgt_lang = self.services[0]["self_target_language_entry"].get()
                save_config(self_src_lang=self_src_lang, self_tgt_lang=self_tgt_lang)

        elif trans_service in ["Bing", "DeepL"]:
            op_src_lang = self.services[1]["source_language_menu"].get()
            op_tgt_lang = self.services[1]["target_language_menu"].get()
            save_config(op_src_lang=op_src_lang, op_tgt_lang=op_tgt_lang)

            if (
                    self_translation_enabled
                    and hasattr(self.services[1]["self_source_language_menu"], "get")
                    and hasattr(self.services[1]["self_target_language_menu"], "get")
            ):
                self_src_lang = self.services[1]["self_source_language_menu"].get()
                self_tgt_lang = self.services[1]["self_target_language_menu"].get()
                save_config(self_src_lang=self_src_lang, self_tgt_lang=self_tgt_lang)

        save_config(minecraft_log_folder=minecraft_log_folder, output_method=output_method, trans_service=trans_service,
                    self_trans_enabled=self_translation_enabled)

        start_translation()

    # noinspection PyUnresolvedReferences,PyTypedDict
    def update_service_widgets(self, choice):
        """根据选择的翻译服务更新控件"""

        for i in range(len(self.services)):
            widgets = self.services[i]
            keys_to_destroy = [key for key in widgets if hasattr(widgets[key], "destroy")]
            widgets_to_destroy = [widgets[key] for key in keys_to_destroy]
            destroyed_dict = dict(zip(keys_to_destroy, destroy_widgets(*widgets_to_destroy)))
            self.services[i].update(destroyed_dict)

        if choice == "LLM":
            self.llm_widgets["source_language_entry"] = ctk.CTkEntry(self.main_window, width=400)
            self.llm_widgets["source_language_entry"].insert(0, self.config.op_src_lang)
            self.llm_widgets["source_language_entry"].grid(row=2, column=1, padx=20, pady=10, sticky="w")

            self.llm_widgets["target_language_entry"] = ctk.CTkEntry(self.main_window, width=400)
            self.llm_widgets["target_language_entry"].insert(0, self.config.op_tgt_lang)
            self.llm_widgets["target_language_entry"].grid(row=3, column=1, padx=20, pady=10, sticky="w")

            self.llm_widgets["api_url_label"] = ctk.CTkLabel(self.main_window, text=_("API URL:"))
            self.llm_widgets["api_url_label"].grid(row=4, column=0, padx=20, pady=10, sticky="w")
            self.llm_widgets["api_url_entry"] = ctk.CTkEntry(self.main_window, width=400)
            self.llm_widgets["api_url_entry"].insert(0, self.config.api_url)
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

        elif choice in {"DeepL", "Bing"}:
            src_lang_var = ctk.StringVar(
                value=self.config.op_src_lang if self.config.op_src_lang in service_supported_languages[choice]
                else service_supported_languages[choice][0]
            )
            tgt_lang_var = ctk.StringVar(
                value=self.config.op_tgt_lang if self.config.op_tgt_lang in service_supported_languages[choice]
                else service_supported_languages[choice][0]
            )

            self.traditional_widgets["source_language_menu"] = ctk.CTkOptionMenu(
                self.main_window, values=service_supported_languages[choice], variable=src_lang_var)
            self.traditional_widgets["source_language_menu"].grid(row=2, column=1, padx=20, pady=10, sticky="w")

            self.traditional_widgets["target_language_menu"] = ctk.CTkOptionMenu(
                self.main_window,
                values=[l for l in service_supported_languages[choice] if l != 'auto'],
                variable=tgt_lang_var
            )
            self.traditional_widgets["target_language_menu"].grid(row=3, column=1, padx=20, pady=10, sticky="w")

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
            "self_target_language_label": None
        }

        self.services = [self.llm_widgets, self.traditional_widgets]
        self.service_var = ctk.StringVar(
            value=service if (service := self.config.trans_service) in {"LLM", "DeepL", "Bing"} else "LLM")
        service_option_menu = ctk.CTkOptionMenu(self.main_window,
                                                values=["LLM", "DeepL", "Bing"],
                                                variable=self.service_var,
                                                command=self.update_service_widgets)
        service_option_menu.grid(row=7, column=0, padx=20, pady=10, sticky="w")

        self.update_service_widgets(self.service_var.get())  # 初始化控件

    def on_output_method_change(self, choice):
        """
        输出方式选择改变时的回调函数

        :param choice: 选择的输出方式
        """

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
            self.max_messages_label = ctk.CTkLabel(self.main_window, text="Max Messages:")
            self.max_messages_label.grid(row=1, column=1, padx=(170, 0), pady=10, sticky="w")
            self.max_messages_entry = ctk.CTkEntry(self.main_window, width=100)
            self.max_messages_entry.grid(row=1, column=1, padx=(270, 0), pady=10, sticky="w")
            self.max_messages_entry.insert(0, self.config.max_messages)
            self.max_messages_entry.bind("<FocusOut>", lambda event: normalize_max_messages(self.max_messages_entry))

    def on_self_translation_toggle(self):
        """
        自翻译开关切换时的回调函数
        """

        service = self.service_var.get()

        if self.self_translation_var.get():

            if service == "LLM":
                if not self.services[0]["self_source_language_entry"]:
                    self.services[0]["self_source_language_label"] = ctk.CTkLabel(self.main_window,
                                                                                  text=_("Self Source Language:"))
                    self.services[0]["self_source_language_label"].grid(row=8, column=0, padx=20, pady=10, sticky="w")
                    self.services[0]["self_source_language_entry"] = ctk.CTkEntry(self.main_window, width=400)
                    self.services[0]["self_source_language_entry"].grid(row=8, column=1, padx=20, pady=10, sticky="w")
                    self.services[0]["self_source_language_entry"].insert(0, self.config.self_src_lang)
                if not self.services[0]["self_target_language_entry"]:
                    self.services[0]["self_target_language_label"] = ctk.CTkLabel(self.main_window,
                                                                                  text=_("Self Target Language:"))
                    self.services[0]["self_target_language_label"].grid(row=9, column=0, padx=20, pady=10, sticky="w")
                    self.services[0]["self_target_language_entry"] = ctk.CTkEntry(self.main_window, width=400)
                    self.services[0]["self_target_language_entry"].grid(row=9, column=1, padx=20, pady=10, sticky="w")
                    self.services[0]["self_target_language_entry"].insert(0, self.config.self_tgt_lang)
            elif service in {"DeepL", "Bing"}:
                if not self.services[1]["self_source_language_menu"]:
                    self.services[1]["self_source_language_label"] = ctk.CTkLabel(self.main_window,
                                                                                  text=_("Self Source Language:"))
                    self.services[1]["self_source_language_label"].grid(row=8, column=0, padx=20, pady=10, sticky="w")
                    self.self_src_lang_var = ctk.StringVar(
                        value=self.config.self_src_lang if self.config.self_src_lang in service_supported_languages[
                            service]
                        else service_supported_languages[service][0]
                    )
                    self.services[1]["self_source_language_menu"] = ctk.CTkOptionMenu(
                        self.main_window, values=service_supported_languages[service], variable=self.self_src_lang_var)
                    self.services[1]["self_source_language_menu"].grid(row=8, column=1, padx=20, pady=10, sticky="w")
                if not self.services[1]["self_target_language_menu"]:
                    self.services[1]["self_target_language_label"] = ctk.CTkLabel(self.main_window,
                                                                                  text=_("Self Target Language:"))
                    self.services[1]["self_target_language_label"].grid(row=9, column=0, padx=20, pady=10, sticky="w")
                    self.self_tgt_lang_var = ctk.StringVar(
                        value=self.config.self_tgt_lang if self.config.self_tgt_lang in service_supported_languages[
                            service]
                        else service_supported_languages[service][0]
                    )
                    self.services[1]["self_target_language_menu"] = ctk.CTkOptionMenu(
                        self.main_window,
                        values=[l for l in service_supported_languages[service] if l != 'auto'],
                        variable=self.self_tgt_lang_var
                    )
                    self.services[1]["self_target_language_menu"].grid(row=9, column=1, padx=20, pady=10, sticky="w")
        else:
            if service == "LLM":
                if self.services[0]["self_source_language_entry"]:
                    (self.services[0]["self_source_language_label"],
                     self.services[0]["self_source_language_entry"]) = destroy_widgets(
                        self.services[0]["self_source_language_label"],
                        self.services[0]["self_source_language_entry"]
                    )
                if self.services[0]["self_target_language_entry"]:
                    (self.services[0]["self_target_language_label"],
                     self.services[0]["self_target_language_entry"]) = destroy_widgets(
                        self.services[0]["self_target_language_label"],
                        self.services[0]["self_target_language_entry"]
                    )
            elif service in {"DeepL", "Bing"}:
                if self.services[1]["self_source_language_menu"]:
                    (self.services[1]["self_source_language_label"],
                     self.services[1]["self_source_language_menu"]) = destroy_widgets(
                        self.services[1]["self_source_language_label"],
                        self.services[1]["self_source_language_menu"]
                    )
                if self.services[1]["self_target_language_menu"]:
                    (self.services[1]["self_target_language_label"],
                     self.services[1]["self_target_language_menu"]) = destroy_widgets(
                        self.services[1]["self_target_language_label"],
                        self.services[1]["self_target_language_menu"]
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


class ChatInterfaceManager:
    def __init__(self, main_window, max_messages=150):
        self.main_window = main_window
        self.chat_window = None
        self.chat_frame = None
        self.canvas = None
        self.scrollbar = None
        self.messages = deque(maxlen=max_messages)
        self.displayed_messages = []

    def start(self):
        self.chat_window = ctk.CTkToplevel(self.main_window)
        self.chat_window.title(_("Translated Message"))
        self.chat_window.geometry("700x400")

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
        self._animate_text(message_label, message)

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

    if http_port > 65535:
        http_port = 65535
    elif http_port < 1:
        http_port = 1

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

    if max_messages < 10:
        max_messages = 10

    max_messages_entry.delete(0, ctk.END)
    max_messages_entry.insert(0, str(max_messages))
