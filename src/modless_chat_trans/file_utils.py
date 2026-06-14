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
import importlib
import threading
from dataclasses import dataclass
from diskcache import Cache
from modless_chat_trans.logger import logger

base_path = os.path.dirname(os.path.dirname(__file__))
cache = Cache("mct-cache", eviction_policy="least-frequently-used")


def get_path(path: str, temp_path=True) -> str:
    if temp_path:
        return os.path.join(base_path, path)
    else:
        return os.path.join(os.getcwd(), path)


def is_file_exists(file_path: str) -> bool:
    return os.path.exists(file_path)


def get_platform() -> int:
    return {"nt": 0, "posix": 1}.get(os.name, 2)


def prune_stale_cache(*, dry_run: bool = False) -> tuple[int, int]:
    """
    清理缓存中从未被读取过的条目（access_count == 0）。

    Args:
        dry_run: 为 True 时只统计不删除，返回 (stale_count, total)。

    Returns:
        (stale_count, total): dry_run 模式返回待清理数和总数；
                              实际删除后返回已清理数和清理前总数。
    """
    rows = cache._sql('SELECT key FROM Cache WHERE access_count = 0')
    stale_keys = [row[0] for row in rows]

    if dry_run or not stale_keys:
        total = len(cache)
        if not stale_keys:
            logger.debug(f"Cache prune: no stale entries found (total={total})")
        return len(stale_keys), total

    total_before = len(cache)
    deleted = 0
    for key in stale_keys:
        try:
            del cache[key]
            deleted += 1
        except KeyError:
            pass

    logger.info(f"Cache pruned: deleted {deleted} stale entries (access_count=0), "
                f"{len(cache)} remaining (was {total_before})")
    return deleted, total_before


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
