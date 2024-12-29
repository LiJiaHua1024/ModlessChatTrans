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

import os
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from modless_chat_trans.file_utils import find_latest_log


class LogMonitorHandler(FileSystemEventHandler):
    """
    监控日志文件的变化
    """

    def __init__(self, directory, callback):
        super().__init__()
        self.directory = directory
        self.callback = callback
        self.current_file = find_latest_log(directory)
        self.file_pointer = None

    def open_file(self, file_path):
        """
        打开指定文件并移动到末尾
        """
        if self.file_pointer:
            self.file_pointer.close()
        self.file_pointer = open(file_path, 'r', encoding='utf-8')
        self.file_pointer.seek(0, os.SEEK_END)

    def _read_new_lines(self):
        """
        读取当前文件的新内容
        """
        if self.file_pointer:
            for line in self.file_pointer:
                # 使用线程调用回调函数，避免阻塞
                threading.Thread(target=self.callback, daemon=True, args=(line,), kwargs={"data_type": "log"}).start()

    def on_modified(self, event):
        if event.src_path == self.current_file:
            self._read_new_lines()

    def on_created(self, event):
        if event.src_path.endswith('.log'):
            # 切换到新文件
            self.current_file = event.src_path
            self.open_file(self.current_file)


def monitor_log_file(directory, callback):
    """
    启动日志文件监控

    :param directory: 要监控的日志文件目录
    :param callback: 检测到新内容的回调函数
    """
    event_handler = LogMonitorHandler(directory, callback)
    event_handler.open_file(event_handler.current_file)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=False)
    observer.start()

    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
