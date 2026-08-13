# Copyright (C) 2024-2026 LiJiaHua1024
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
"""Windows 11 风格 WebUI（Flask + Fluent UI Web Components + WebView2）。

替代旧的 PySide6 + qfluentwidgets 界面，复刻 WinUI 3 布局与全部功能。
与 web_display.py（翻译结果展示 Web UI）完全独立。
"""
from modless_chat_trans.webui.window import Api, MainWindow, ProgramInfo

__all__ = ["Api", "MainWindow", "ProgramInfo"]
