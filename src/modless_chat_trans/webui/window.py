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
"""WebView2 宿主窗口：Flask 服务 + pywebview（edgechromium = WebView2）。"""
import threading
import webbrowser
from dataclasses import dataclass
from typing import Tuple

from modless_chat_trans.logger import logger
from modless_chat_trans.webui.server import GuiState, create_app


@dataclass
class ProgramInfo:
    version: str
    author: str
    email: str
    github: str
    license: Tuple[str, str]


class Api:
    """暴露给页面的原生能力（window.pywebview.api.*）"""

    def __init__(self, state: GuiState):
        self.state = state

    def select_folder(self):
        """打开原生文件夹选择对话框，返回所选路径或 None"""
        try:
            import webview
            window = None
            if getattr(webview, "active_window", None):
                try:
                    window = webview.active_window()
                except Exception:
                    window = None
            if window is None:
                windows = getattr(webview, "windows", None) or []
                window = windows[0] if windows else None
            if window is None:
                return None
            try:
                dialog_type = webview.FileDialog.FOLDER
            except AttributeError:
                dialog_type = webview.FOLDER_DIALOG  # type: ignore[attr-defined]
            dirs = window.create_file_dialog(dialog_type)
            if dirs and len(dirs) > 0:
                return dirs[0]
            return None
        except Exception as e:
            logger.error(f"Folder dialog failed: {e}")
            return None

    def open_external(self, url: str):
        """在系统默认浏览器中打开链接"""
        try:
            if url and url.startswith(("http://", "https://")):
                webbrowser.open(url)
        except Exception as e:
            logger.warning(f"Failed to open external url: {e}")


class MainWindow:
    """替代旧 Qt MainWindow：WebView2 窗口 + 内置 Flask GUI 服务。

    对外接口保持兼容：main.py 只需要构造实例并调用 run()。
    """

    def __init__(self, info: ProgramInfo, updater_object, config, start_callback):
        self.info = info
        self.updater = updater_object
        self.config = config
        self.start_callback = start_callback

        self.state = GuiState(info, updater_object, config, start_callback)
        self._app = create_app(self.state)
        self._server = None
        self._server_thread = None
        self._url = None

        self._start_server()

    # ── HTTP 服务 ───────────────────────────────────────────────────

    def _start_server(self):
        import logging
        from werkzeug.serving import make_server

        # GUI 服务仅供本地 WebView2 使用，访问日志无价值，静默到 ERROR 级
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

        self._server = make_server("127.0.0.1", 0, self._app, threaded=True)
        port = self._server.server_port
        self._url = f"http://127.0.0.1:{port}"
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="webui-gui-server",
        )
        self._server_thread.start()
        logger.info(f"GUI web server started at {self._url}")

    @property
    def url(self) -> str:
        return self._url

    # ── 对外兼容接口 ────────────────────────────────────────────────

    def check_for_updates(self, silent=False):
        """供 main.py 的定时更新检查调用"""
        from modless_chat_trans.webui.server import _check_update_task

        self.state.updater.include_prerelease = self.config.settings.include_prerelease
        threading.Thread(
            target=_check_update_task,
            args=(self.state, silent),
            daemon=True,
            name="webui-update-check-scheduled",
        ).start()

    def run(self):
        """阻塞式启动 WebView2 窗口（须在主线程调用）"""
        import webview

        title = f"Modless Chat Trans {self.info.version}"
        api = Api(self.state)

        debug = bool(getattr(self.config.settings, "debug", False))

        webview.create_window(
            title,
            url=self._url,
            width=900,
            height=700,
            min_size=(720, 520),
            js_api=api,
        )
        logger.info("WebView2 window starting")
        webview.start(debug=debug, gui="edgechromium")

    def destroy(self):
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
