#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
编译 i18n 目录下的 .po 文件为 .mo 文件，并将其放置到 src/locales 目录的相应结构中。

此脚本设计为放置在项目根目录下的 'tools/' 子目录中。
它会自动计算项目根目录，并查找 'i18n/' 和 'src/locales/' 文件夹。

用法：
1. 将此脚本放置在项目的 'tools/' 目录下。
   项目结构预期为：
   <project_root>/
   ├── tools/
   │   └── compile_translations.py
   ├── i18n/
   │   ├── en_US.po
   │   └── ...
   └── src/
       ├── locales/
       │   ├── en_US/
       │   │   └── LC_MESSAGES/
       │   └── ...
       └── ...
2. 确保已安装 gettext 工具 (包含 msgfmt 命令)。
   - Ubuntu/Debian: sudo apt-get update && sudo apt-get install gettext
   - macOS (using Homebrew): brew install gettext && brew link --force gettext
   - Windows: 可从 https://mlocati.github.io/articles/gettext-iconv-windows.html 下载并添加到PATH
3. 从项目根目录运行此脚本： python tools/compile_translations.py
"""

import os
import subprocess
import sys
from pathlib import Path
import shutil # 用于 shutil.which

# --- 配置 ---
# 获取脚本文件所在的目录
SCRIPT_DIR = Path(__file__).parent.resolve()
# 脚本在 tools/ 目录下，那么项目根目录是脚本目录的上一级
PROJECT_ROOT = SCRIPT_DIR.parent
# 基于项目根目录定义源和目标路径
SOURCE_DIR = PROJECT_ROOT / "i18n"
TARGET_BASE_DIR = PROJECT_ROOT / "src" / "locales"  # 修改为新的目标路径

OUTPUT_FILENAME = "translations.mo" # 所有 .mo 文件都使用这个名称
TEMPLATE_FILENAME = "translations.pot"
# -------------

def find_msgfmt():
    """尝试查找 msgfmt 命令。"""
    # 优先检查 PATH
    msgfmt_path = shutil.which("msgfmt")
    if msgfmt_path:
        return msgfmt_path

    # 如果 PATH 中没有，尝试在常见位置查找 (特别是 macOS Homebrew)
    if sys.platform == "darwin":
        common_paths = [
            "/usr/local/opt/gettext/bin/msgfmt",
            "/opt/homebrew/opt/gettext/bin/msgfmt",
        ]
        for path in common_paths:
            if Path(path).is_file():
                print(f"信息: 在非标准路径找到 msgfmt: {path}")
                return path

    # 在 Windows 的常见路径检查（示例，可能需要根据实际安装调整）
    if sys.platform == "win32":
        possible_paths = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "gettext" / "bin" / "msgfmt.exe",
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "gettext" / "bin" / "msgfmt.exe",
            # 可以添加其他可能的 gettext 安装路径
        ]
        for path in possible_paths:
             if path.is_file():
                 print(f"信息: 在非标准路径找到 msgfmt: {path}")
                 return str(path) # subprocess 需要字符串

    # 如果都找不到
    print("错误: 未能自动定位 'msgfmt' 命令。", file=sys.stderr)
    print("请确保 gettext 工具已安装并且 'msgfmt' 在系统的 PATH 环境变量中，", file=sys.stderr)
    print("或者在此脚本的 find_msgfmt 函数中添加其绝对路径。", file=sys.stderr)
    return None

def compile_po_to_mo(po_file: Path, mo_file: Path, msgfmt_cmd: str):
    """使用 msgfmt 编译 .po 文件为 .mo 文件。"""
    target_dir = mo_file.parent
    # 确保目标目录存在
    target_dir.mkdir(parents=True, exist_ok=True)

    # msgfmt 命令需要字符串路径
    command = [
        msgfmt_cmd,
        "-o", str(mo_file),
        str(po_file)
    ]

    print(f"  执行: {' '.join(command)}")
    try:
        # 使用 utf-8 编码捕获输出，以防文件名或消息包含非 ASCII 字符
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        # print(f"    输出:\n{result.stdout}") # 如果需要看 msgfmt 的输出
        if result.stderr:
             print(f"    警告/信息:\n{result.stderr.strip()}", file=sys.stderr)
        return True
    except FileNotFoundError:
        # 这通常在 find_msgfmt 成功但实际执行时 msgfmt 又找不到了的情况下发生（不太可能）
        print(f"错误: 命令 '{msgfmt_cmd}' 未找到或无法执行。", file=sys.stderr)
        print("请重新检查 gettext 安装和 PATH 配置。", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"错误: 编译 {po_file.name} 失败。", file=sys.stderr)
        print(f"  命令: {' '.join(e.cmd)}", file=sys.stderr)
        print(f"  返回码: {e.returncode}", file=sys.stderr)
        print(f"  错误输出:\n{e.stderr.strip()}", file=sys.stderr) # .strip() 移除多余换行
        return False
    except Exception as e:
        print(f"错误: 编译 {po_file.name} 时发生意外错误: {e}", file=sys.stderr)
        return False

def main():
    """主函数，执行编译流程。"""
    msgfmt_executable = find_msgfmt()
    if not msgfmt_executable:
         sys.exit(1) # find_msgfmt 内部已打印错误信息

    print(f"\n使用 msgfmt: {msgfmt_executable}")
    print(f"源 (.po) 目录: {SOURCE_DIR}")
    print(f"目标 (.mo) 基础目录: {TARGET_BASE_DIR}")

    if not SOURCE_DIR.is_dir():
        print(f"\n错误: 源目录 '{SOURCE_DIR}' 不存在或不是一个目录。", file=sys.stderr)
        print("请确保 'i18n' 文件夹在项目根目录下。", file=sys.stderr)
        sys.exit(1)

    if not TARGET_BASE_DIR.exists():
        print(f"\n信息: 目标基础目录 '{TARGET_BASE_DIR}' 不存在，将根据需要创建子目录。")
        # 不需要在这里创建 TARGET_BASE_DIR 本身，compile_po_to_mo 会创建子目录
    elif not TARGET_BASE_DIR.is_dir():
         print(f"\n错误: 目标路径 '{TARGET_BASE_DIR}' 已存在但不是一个目录。", file=sys.stderr)
         sys.exit(1)

    po_files_found = 0
    compiled_count = 0
    error_count = 0

    print(f"\n开始在 '{SOURCE_DIR.name}' 中查找 .po 文件...")

    # 使用 sorted() 确保处理顺序一致（可选）
    po_files = sorted(SOURCE_DIR.glob("*.po"))

    if not po_files:
         print(f"在 '{SOURCE_DIR}' 中没有找到任何 .po 文件。")
         sys.exit(0) # 没有文件不是错误，正常退出

    for po_file in po_files:
        if po_file.name == TEMPLATE_FILENAME:
            print(f"\n跳过模板文件: {po_file.name}")
            continue

        po_files_found += 1
        print(f"\n处理文件: {po_file.name}")

        # 从 .po 文件名获取 locale 代码 (例如 'de_DE' 从 'de_DE.po')
        locale_code = po_file.stem

        # 构建目标 .mo 文件的完整路径
        target_mo_dir = TARGET_BASE_DIR / locale_code / "LC_MESSAGES"
        target_mo_file = target_mo_dir / OUTPUT_FILENAME

        print(f"  目标 .mo 文件: {target_mo_file}")

        if compile_po_to_mo(po_file, target_mo_file, msgfmt_executable):
            compiled_count += 1
            print(f"  成功编译并放置到: {target_mo_file}")
        else:
            error_count += 1
            # 编译失败信息已在 compile_po_to_mo 中打印

    print("\n--- 编译摘要 ---")
    if po_files_found == 0:
        print(f"在 '{SOURCE_DIR.name}' 中没有找到需要编译的 .po 文件 (已排除 '{TEMPLATE_FILENAME}')。")
    else:
        print(f"扫描了 {len(po_files)} 个文件，处理了 {po_files_found} 个 .po 文件 (已排除模板)。")
        print(f"成功编译: {compiled_count}")
        print(f"编译失败: {error_count}")
        if error_count > 0:
            print("\n编译过程中出现错误，请检查上面的日志。")
            sys.exit(1) # 如果有错误则以非零状态退出

    print("\n翻译文件编译完成。")

if __name__ == "__main__":
    # 打印计算出的路径，方便调试
    print("-" * 30)
    print("脚本执行环境信息:")
    print(f"  脚本位置 (SCRIPT_DIR): {SCRIPT_DIR}")
    print(f"  项目根目录 (PROJECT_ROOT): {PROJECT_ROOT}")
    print("-" * 30)

    # 执行主逻辑
    main()

    input("\n按 Enter 键退出...") # 等待用户输入，防止脚本窗口立即关闭