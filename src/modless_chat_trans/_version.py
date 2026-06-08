# Copyright (C) 2024-2025 LiJiaHua1024
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
版本信息模块。

BASE_VERSION 始终从 pyproject.toml 获取（通过 importlib.metadata），
CI 构建元数据（分支名、commit hash 等）从 _build_info.py 获取。
_build_info.py 由 CI 自动生成、不提交到 Git。
"""

from importlib.metadata import version, PackageNotFoundError

try:
    BASE_VERSION = version("ModlessChatTrans")
except PackageNotFoundError:
    BASE_VERSION = "0.0.0"

# 尝试导入 CI 构建信息（仅在 CI 构建时存在）
try:
    from modless_chat_trans._build_info import BUILD_CHANNEL, BRANCH, COMMIT_SHA
    IS_CI_BUILD = True
except ImportError:
    BUILD_CHANNEL = "dev"
    BRANCH = "local"
    COMMIT_SHA = "unknown"
    IS_CI_BUILD = False


def get_version_string() -> str:
    """
    生成完整版本字符串。

    - 本地开发:              "v3.2.1-dev"
    - CI stable (tag 触发):  "v3.2.1"
    - CI canary:             "v3.2.1-canary+abc12345"
    - CI canary-exp:         "v3.2.1-canary-exp+abc12345"
    """
    if not IS_CI_BUILD:
        return f"v{BASE_VERSION}-dev"

    if BUILD_CHANNEL == "stable":
        return f"v{BASE_VERSION}"

    return f"v{BASE_VERSION}-{BUILD_CHANNEL}+{COMMIT_SHA}"


def get_short_version() -> str:
    """用于文件名的简短版本（不含 'v' 前缀）。"""
    return get_version_string().lstrip("v")
