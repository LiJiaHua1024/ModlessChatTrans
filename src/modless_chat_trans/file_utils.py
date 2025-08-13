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

import os
import glob
import json
import shelve
import importlib
from dataclasses import dataclass
from modless_chat_trans.logger import logger

base_path = os.path.dirname(os.path.dirname(__file__))
cache = shelve.open("MCT_cache")


def get_path(path: str, temp_path=True) -> str:
    if temp_path:
        return os.path.join(base_path, path)
    else:
        return os.path.join(os.getcwd(), path)


def is_file_exists(file_path: str) -> bool:
    return os.path.exists(file_path)


def get_platform() -> int:
    return {"nt": 0, "posix": 1}.get(os.name, 2)


class LazyImporter:
    def __init__(self, module_name, attr_name=None):
        self.module_name = module_name
        self.attr_name = attr_name
        self._module = None

    def _ensure_module_loaded(self):
        if self._module is None:
            logger.debug(f"Lazily importing '{self.module_name}' library now...")
            try:
                module = importlib.import_module(self.module_name)
                if self.attr_name:
                    self._module = getattr(module, self.attr_name)
                else:
                    self._module = module
            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to import '{self.module_name}' library: {e}")
                raise
            logger.info(f"'{self.module_name}' library imported successfully.")

    def __getattr__(self, name):
        self._ensure_module_loaded()
        return getattr(self._module, name)

    def __call__(self, *args, **kwargs):
        self._ensure_module_loaded()
        return self._module(*args, **kwargs)


def find_latest_log(directory: str) -> str:
    """
    获取目录中最新的日志文件

    :param directory: 目录
    :return: 最新的日志文件
    """

    log_files = glob.glob(os.path.join(directory, '*.log'))

    # 根据修改时间排序日志文件，最新的文件在最前
    if log_files:
        latest_log_file = max(log_files, key=os.path.getmtime)
        return latest_log_file

    # 如果没有找到任何日志文件，返回空
    return ""
