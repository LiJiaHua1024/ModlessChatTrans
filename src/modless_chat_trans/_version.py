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
    from modless_chat_trans._build_info import BUILD_CHANNEL, BRANCH, COMMIT_SHA, EDITION
    IS_CI_BUILD = True
except ImportError:
    try:
        # 兼容旧版 CI 生成的 _build_info.py（无 EDITION 字段）
        from modless_chat_trans._build_info import BUILD_CHANNEL, BRANCH, COMMIT_SHA
        EDITION = "standard"
        IS_CI_BUILD = True
    except ImportError:
        BUILD_CHANNEL = "dev"
        BRANCH = "local"
        COMMIT_SHA = "unknown"
        EDITION = "standard"
        IS_CI_BUILD = False


def is_dev_build() -> bool:
    """
    是否为本地开发构建（非 CI 产物，版本形如 v3.3.0-dev）。

    开发构建不执行任何更新检查（自动或手动）。
    """
    return not IS_CI_BUILD


def get_edition() -> str:
    """
    返回当前构建的变体（edition）。

    - standard: 标准版（main 分支 / 无后缀 tag）
    - lite:     精简版（lite 分支 / v x.x.x-lite tag）
    - nano:     极简版（nano 分支 / v x.x.x-nano tag）
    """
    return EDITION if EDITION in ("lite", "nano") else "standard"


def get_version_string() -> str:
    """
    生成完整版本字符串。

    - 本地开发:              "v3.2.1-dev"
    - CI stable (tag 触发):  "v3.2.1" / "v3.2.1-lite" / "v3.2.1-nano"
    - CI canary:             "v3.2.1-canary+abc12345"
    - CI canary-exp:         "v3.2.1-canary-exp+abc12345"
    - CI lite/nano 分支:     "v3.2.1-lite+abc12345" / "v3.2.1-nano+abc12345"
    """
    edition = get_edition()
    edition_suffix = f"-{edition}" if edition != "standard" else ""

    if not IS_CI_BUILD:
        return f"v{BASE_VERSION}-dev"

    if BUILD_CHANNEL == "stable":
        return f"v{BASE_VERSION}{edition_suffix}"

    if edition != "standard":
        return f"v{BASE_VERSION}-{edition}+{COMMIT_SHA}"

    return f"v{BASE_VERSION}-{BUILD_CHANNEL}+{COMMIT_SHA}"


def get_short_version() -> str:
    """用于文件名的简短版本（不含 'v' 前缀）。"""
    return get_version_string().lstrip("v")
