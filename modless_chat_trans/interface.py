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
from modless_chat_trans.file_utils import read_config, save_config
from modless_chat_trans.i18n import _, supported_languages, lang_window_size_map


@dataclass
class ProgramInfo:
    version: str
    author: str
    email: str
    github: str
    license: tuple[str, str]


def create_main_window(info, start_translation):
    """
    创建程序主窗口

    :param info: ProgramInfo类的实例，包含程序信息
    :param start_translation: 启动翻译流程的函数
    """

    global start_button
    # 创建主窗口
    main_window = ctk.CTk()
    main_window.title(f"Modless Chat Trans {info.version}")

    main_window.geometry(lang_window_size_map[read_config().interface_lang])

    main_window.resizable(False, False)

    main_window.rowconfigure(10, weight=1)
    main_window.columnconfigure(9, weight=1)

    language_menu = tk.Menu(main_window, tearoff=0)

    language_menu.add_command(label="* Changes take effect after reboot")
    for lang, lang_code in supported_languages:
        language_menu.add_command(label=lang, command=lambda lang_code=lang_code: save_config(interface_lang=lang_code))

    def show_language_menu(event):
        nonlocal language_menu
        try:
            language_menu.tk_popup(event.x_root, event.y_root)
        finally:
            language_menu.grab_release()

    create_config_widgets(main_window)

    start_button = ctk.CTkButton(main_window, text=_("Start"), font=("default", 60),
                                 command=lambda: prepare_translation_config(start_translation))
    start_button.grid(row=10, column=0, columnspan=2, padx=20, pady=10)

    choose_language_photo = tk.PhotoImage(file="choose_language.png")
    choose_language_button = ctk.CTkButton(main_window, image=choose_language_photo, text="",
                                           width=50, height=50, fg_color="transparent", hover_color="white")
    choose_language_button.bind("<Button-1>", show_language_menu)
    choose_language_button.grid(row=11, column=0, padx=(0, 150))

    about_button = ctk.CTkButton(main_window, text=_("About"), width=50, height=25,
                                 command=lambda: show_about_window(main_window, info))
    about_button.grid(row=11, column=2, padx=0, pady=15)

    hPyT.maximize_minimize_button.hide(main_window)

    main_window.mainloop()


def show_about_window(main_window, info):
    """
    显示关于窗口

    :param main_window: 主窗口对象
    :param info: ProgramInfo类的实例，包含程序信息
    """

    # 创建关于窗口
    about_window = ctk.CTkToplevel(main_window)
    about_window.title(_("About"))
    about_window.geometry("350x200")
    about_window.grab_set()
    about_window.resizable(False, False)
    hPyT.maximize_minimize_button.hide(about_window)

    # 添加关于窗口的内容
    ctk.CTkLabel(about_window, text="Modless Chat Trans", font=("Arial", 20, "bold")).pack()
    ctk.CTkLabel(about_window, text=f"{_("Version")}: {info.version}").pack()
    ctk.CTkLabel(about_window, text=f"{_("Author")}: {info.author}").pack()
    ctk.CTkLabel(about_window, text=f"{_("Email")}: {info.email}").pack()
    github_url_label = ctk.CTkLabel(about_window, text=f"GitHub: {info.github}", cursor="hand2")
    github_url_label.bind("<Button-1>", lambda event: webbrowser.open_new(info.github))
    github_url_label.pack()
    license_label = ctk.CTkLabel(about_window, text=f"{_("License")}: {info.license[0]}", cursor="hand2")
    license_label.bind("<Button-1>", lambda event: webbrowser.open_new(info.license[1]))
    license_label.pack()


def prepare_translation_config(start_translation):
    """
    准备翻译配置并启动翻译流程

    :param start_translation: 启动翻译流程的函数
    """

    global start_button
    start_button.configure(state="disabled")

    minecraft_log_folder = minecraft_log_folder_entry.get()
    op_src_lang = source_language_entry.get()
    op_tgt_lang = target_language_entry.get()
    api_url = api_url_entry.get()
    api_key = api_key_entry.get()
    model = model_entry.get()

    output_method_map = {_("Graphical"): "Graphical", _("Speech"): "Speech", _("Httpserver"): "Httpserver"}
    output_method = output_method_map[output_method_var.get()]

    # 获取自翻译选项
    self_translation_enabled = self_translation_var.get()
    self_src_lang = self_src_lang_entry.get() if self_translation_enabled else ""
    self_tgt_lang = self_tgt_lang_entry.get() if self_translation_enabled else ""

    save_config(minecraft_log_folder=minecraft_log_folder, output_method=output_method, op_src_lang=op_src_lang,
                op_tgt_lang=op_tgt_lang, self_trans_enabled=self_translation_enabled, self_src_lang=self_src_lang,
                self_tgt_lang=self_tgt_lang, api_url=api_url, api_key=api_key, model=model)

    if output_method == "Httpserver":
        http_port = int(http_port_entry.get())
        save_config(http_port=http_port)
        webbrowser.open_new(f"http://localhost:{http_port}")

    start_translation()


def create_config_widgets(main_window):
    """
    创建配置控件

    :param main_window: 配置窗口对象
    """

    global minecraft_log_folder_entry, output_method_var, source_language_entry, target_language_entry, api_url_entry, \
        api_key_entry, model_entry, http_port_entry, http_port_label, self_translation_var, \
        self_src_lang_entry, self_tgt_lang_entry, self_src_lang_label, self_tgt_lang_label

    http_port_entry = None
    http_port_label = None
    self_src_lang_entry = None
    self_tgt_lang_entry = None
    self_src_lang_label = None
    self_tgt_lang_label = None

    def on_output_method_change(choice):
        """
        输出方式选择改变时的回调函数

        :param choice: 选择的输出方式
        """

        global http_port_entry, http_port_label
        if choice == _("Httpserver"):
            if not http_port_entry:
                http_port_label = ctk.CTkLabel(main_window, text=_("HTTP Port:"))
                http_port_label.grid(row=1, column=1, padx=(200, 0), pady=10, sticky="w")
                http_port_entry = ctk.CTkEntry(main_window, width=100)
                http_port_entry.grid(row=1, column=1, padx=(270, 0), pady=10, sticky="w")
                http_port_entry.insert(0, config.http_port)
                http_port_entry.bind("<FocusOut>", lambda event: normalize_port_number(http_port_entry))
        else:
            if http_port_entry:
                http_port_label.grid_remove()
                http_port_entry.grid_remove()
                http_port_label = None
                http_port_entry = None

    def on_self_translation_toggle():
        """
        自翻译开关切换时的回调函数
        """

        global self_src_lang_entry, self_tgt_lang_entry, self_src_lang_label, self_tgt_lang_label
        if self_translation_var.get():
            if not self_src_lang_entry:
                self_src_lang_label = ctk.CTkLabel(main_window, text=_("Self Source Language:"))
                self_src_lang_label.grid(row=8, column=0, padx=20, pady=10, sticky="w")
                self_src_lang_entry = ctk.CTkEntry(main_window, width=400)
                self_src_lang_entry.grid(row=8, column=1, padx=20, pady=10, sticky="w")
                self_src_lang_entry.insert(0, config.self_src_lang)

            if not self_tgt_lang_entry:
                self_tgt_lang_label = ctk.CTkLabel(main_window, text=_("Self Target Language:"))
                self_tgt_lang_label.grid(row=9, column=0, padx=20, pady=10, sticky="w")
                self_tgt_lang_entry = ctk.CTkEntry(main_window, width=400)
                self_tgt_lang_entry.grid(row=9, column=1, padx=20, pady=10, sticky="w")
                self_tgt_lang_entry.insert(0, config.self_tgt_lang)
        else:
            if self_src_lang_entry:
                self_src_lang_label.grid_remove()
                self_src_lang_entry.grid_remove()
                self_src_lang_label = None
                self_src_lang_entry = None

            if self_tgt_lang_entry:
                self_tgt_lang_label.grid_remove()
                self_tgt_lang_entry.grid_remove()
                self_tgt_lang_label = None
                self_tgt_lang_entry = None

    # 读取配置文件
    config = read_config()

    if config.output_method not in {"Graphical", "Speech", "Httpserver"}:
        config.output_method = "Graphical"

    # Minecraft Log Folder
    minecraft_log_folder_label = ctk.CTkLabel(main_window, text=_("Minecraft Log Folder:"))
    minecraft_log_folder_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")
    minecraft_log_folder_entry = ctk.CTkEntry(main_window, width=400)
    minecraft_log_folder_entry.insert(0, config.minecraft_log_folder)
    minecraft_log_folder_entry.grid(row=0, column=1, padx=20, pady=10, sticky="w")

    # Output Method
    on_output_method_change(config.output_method)
    output_method_label = ctk.CTkLabel(main_window, text=_("Output Method:"))
    output_method_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")
    output_method_var = ctk.StringVar(value=_(config.output_method))
    output_method_optionmenu = ctk.CTkOptionMenu(main_window,
                                                 values=[_("Graphical"), _("Speech"), _("Httpserver")],
                                                 variable=output_method_var, command=on_output_method_change)
    output_method_optionmenu.grid(row=1, column=1, padx=20, pady=10, sticky="w")

    # Source Language
    source_language_label = ctk.CTkLabel(main_window, text=_("Source Language(Auto if blank):"))
    source_language_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")
    source_language_entry = ctk.CTkEntry(main_window, width=400)
    source_language_entry.insert(0, config.op_src_lang)
    source_language_entry.grid(row=2, column=1, padx=20, pady=10, sticky="w")

    # Target Language
    target_language_label = ctk.CTkLabel(main_window, text=_("Target Language:"))
    target_language_label.grid(row=3, column=0, padx=20, pady=10, sticky="w")
    target_language_entry = ctk.CTkEntry(main_window, width=400)
    target_language_entry.insert(0, config.op_tgt_lang)
    target_language_entry.grid(row=3, column=1, padx=20, pady=10, sticky="w")

    # API URL
    api_url_label = ctk.CTkLabel(main_window, text=_("API URL:"))
    api_url_label.grid(row=4, column=0, padx=20, pady=10, sticky="w")
    api_url_entry = ctk.CTkEntry(main_window, width=400)
    api_url_entry.insert(0, config.api_url)
    api_url_entry.grid(row=4, column=1, padx=20, pady=10, sticky="w")

    # API Key
    api_key_label = ctk.CTkLabel(main_window, text=_("API Key:"))
    api_key_label.grid(row=5, column=0, padx=20, pady=10, sticky="w")
    api_key_entry = ctk.CTkEntry(main_window, width=400)
    api_key_entry.insert(0, config.api_key)
    api_key_entry.grid(row=5, column=1, padx=20, pady=10, sticky="w")

    # Model
    model_label = ctk.CTkLabel(main_window, text=_("Model:"))
    model_label.grid(row=6, column=0, padx=20, pady=10, sticky="w")
    model_entry = ctk.CTkEntry(main_window, width=400)
    model_entry.insert(0, config.model)
    model_entry.grid(row=6, column=1, padx=20, pady=10, sticky="w")

    # Self Translation Toggle
    self_translation_var = ctk.BooleanVar(value=config.self_src_lang != "" and config.self_tgt_lang != "")
    self_translation_toggle = ctk.CTkCheckBox(main_window, text=_("Translate Player's Own Message"),
                                              variable=self_translation_var,
                                              command=on_self_translation_toggle)
    self_translation_toggle.grid(row=7, column=1, padx=20, pady=10, sticky="w")

    on_self_translation_toggle()


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
