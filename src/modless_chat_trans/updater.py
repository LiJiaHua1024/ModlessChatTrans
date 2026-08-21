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

import re
import shutil
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from modless_chat_trans.file_utils import get_path, get_platform
from modless_chat_trans.logger import logger
from modless_chat_trans._version import get_edition, is_dev_build

# ──────────────────────────────
# 可选依赖：requests / packaging
# 任一导入失败则禁用自动更新功能
# ──────────────────────────────
try:
    import requests
    from packaging.version import Version, InvalidVersion
    UPDATER_AVAILABLE = True
    UPDATER_IMPORT_ERROR = None
except ImportError as _upd_exc:
    requests = None  # type: ignore[assignment]
    Version = None  # type: ignore[assignment,misc]
    InvalidVersion = Exception  # type: ignore[assignment,misc]
    UPDATER_AVAILABLE = False
    UPDATER_IMPORT_ERROR = str(_upd_exc)
    logger.warning(f"[Updater] Dependencies not available, auto-update disabled: {_upd_exc}")

# edition 后缀（变体标识）：v3.3.0-lite / v3.3.0-nano
_EDITION_SUFFIXES = ("lite", "nano")


def parse_version_with_edition(version_str):
    """
    拆分带变体后缀的版本号。

    去除 'v' 前缀与 '+build' 元数据后，识别结尾的 -lite/-nano 后缀。

    Returns:
        (base, edition) 元组，例如：
        - "v3.3.0"          -> ("3.3.0", "standard")
        - "v3.3.0-lite"     -> ("3.3.0", "lite")
        - "v3.3.0-nano+sha" -> ("3.3.0", "nano")
        - "v3.3.0-canary+sha" -> ("3.3.0-canary", "standard")
    """
    core = version_str.lstrip("v").split("+", 1)[0]
    for suffix in _EDITION_SUFFIXES:
        if core.endswith("-" + suffix) or core.endswith("_" + suffix):
            return core[: -(len(suffix) + 1)], suffix
    return core, "standard"


def _base_version_str(core):
    """
    剥离预发布/构建后缀，返回基础版本号（如 '3.3.0-canary' -> '3.3.0'）。

    优先用 packaging 的 base_version 规范化（可处理 '3.3.0.dev0' 等点分隔写法），
    非法版本（如 '3.3.0-canary'）回退到按 '-'/'+ 截断。
    """
    if UPDATER_AVAILABLE:
        try:
            return Version(core).base_version
        except InvalidVersion:
            pass
    return re.split(r"[-+]", core, maxsplit=1)[0]


class Updater:
    def __init__(self, current_version, owner, repo, include_prerelease=False):
        logger.info(f"Initializing updater: version={current_version}, repo={owner}/{repo}")
        # 当前变体：lite 只更新 lite，nano 只更新 nano，standard 只更新 standard
        self.edition = get_edition()
        logger.debug(f"Updater edition: {self.edition}")
        if UPDATER_AVAILABLE:
            # 去掉 edition 后缀，只用基础语义化版本号参与比较
            core, edition = parse_version_with_edition(current_version)
            base = _base_version_str(core)
            try:
                # 完整版本（含 dev/canary 等预发布标识）仅用于日志展示
                self.current_version = Version(core)
            except InvalidVersion:
                # 非正式版本（如 3.2.1-canary+abc12345），保留原字符串用于展示
                self.current_version = core
            # 比较只用基础版本号：剥离预发布/构建后缀后，相等版本不算更新
            try:
                self.current_base_version = Version(base)
            except InvalidVersion:
                self.current_base_version = base
        else:
            self.current_version = current_version.lstrip("v")
            self.current_base_version = self.current_version
        self.owner = owner
        self.repo = repo
        self.include_prerelease = include_prerelease
        self.api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        logger.debug(f"API URL set to: {self.api_url}")

    def check_update(self):
        if not UPDATER_AVAILABLE:
            logger.debug("[Updater] Skipping update check: dependencies not available")
            return None
        if is_dev_build():
            # 本地开发构建（v3.3.0-dev）不执行任何更新检查
            logger.info("[Updater] Skipping update check: development build")
            return None
        logger.info(f"Checking for updates (edition: {self.edition})")
        try:
            latest_release = self._get_latest_release()
            if latest_release:
                latest_version_str = latest_release.get("tag_name").lstrip("v")
                logger.debug(f"Latest version found: {latest_version_str}")
                if self._is_newer(latest_version_str):
                    logger.info(f"New version available: {latest_version_str}")
                    return latest_release
                logger.info(f"Current version {self.current_version} is up to date")
            else:
                logger.warning("No release information found")
            return None
        except Exception as e:
            logger.error(f"Error checking for updates: {str(e)}")
            return None

    def _is_newer(self, latest_version_str):
        """
        判断远端版本是否比当前版本新。

        双方均剥离预发布/构建后缀后比较基础版本号：
        相等（如 3.3.0-dev / 3.3.0-canary+sha 对 3.3.0）不算更新，
        避免同版本的开发/预发布构建被误报为有更新。
        """
        latest_core, _ = parse_version_with_edition(latest_version_str)
        try:
            latest_version = Version(_base_version_str(latest_core))
        except InvalidVersion:
            logger.error(f"Invalid version format: {latest_version_str}")
            return False
        try:
            return latest_version > self.current_base_version
        except TypeError:
            # current_base_version 解析失败时保持字符串，无法比较则视为无更新
            logger.error(f"Cannot compare versions: {latest_version} vs {self.current_base_version}")
            return False

    @staticmethod
    def download_update(latest_release, progress_callback=None, thread_count_callback=None):
        """
        下载更新文件（支持多线程下载）

        Args:
            latest_release: 最新版本信息
            progress_callback: 进度回调函数，接受参数 (downloaded, total, speed)，返回 False 表示取消
            thread_count_callback: 线程数回调函数，接受参数 (count)

        Returns:
            下载文件的路径，如果失败或取消返回 None
        """
        if not UPDATER_AVAILABLE:
            logger.debug("[Updater] Skipping download: dependencies not available")
            return None
        logger.info(f"Downloading update: {latest_release.get('tag_name')}")

        try:
            assets = latest_release.get("assets", [])
            if not assets:
                logger.warning("No assets found in the release")
                return None

            platform = get_platform()
            logger.debug(f"Detected platform: {platform}")

            if platform == 0:
                logger.debug("Looking for Windows executable (.exe)")
                exes = [asset for asset in assets if asset.get("name", "").endswith(".exe")]
                if self.edition != "standard":
                    # 只下载文件名带 edition 后缀的资产（如 ModlessChatTrans_v3.3.0-lite.exe），
                    # 找不到宁可失败也不兜底，避免把用户换成错误 edition
                    asset = next(
                        (a for a in exes if a["name"].lower().endswith(f"-{self.edition}.exe")),
                        None,
                    )
                else:
                    # standard 排除带 lite/nano 后缀的资产
                    asset = next(
                        (a for a in exes
                         if not a["name"].lower().endswith("-lite.exe")
                         and not a["name"].lower().endswith("-nano.exe")),
                        None,
                    )
            elif platform == 1:
                logger.debug("Looking for Linux archive (.tar.gz)")
                asset = next((asset for asset in assets if asset.get("name").endswith(".tar.gz")), None)
            else:
                logger.error(f"Unsupported platform: {platform}")
                return None

            if not asset:
                logger.warning(f"No suitable asset found for platform {platform}")
                return None

            download_url = asset.get("browser_download_url")
            logger.debug(f"Download URL: {download_url}")

            # 检查是否支持多线程下载
            downloader = MultiThreadDownloader(download_url, asset.get("name"), progress_callback,
                                               thread_count_callback)
            return downloader.download()

        except Exception as e:
            logger.error(f"Error downloading update: {str(e)}")
            return None

    def _get_latest_release(self):
        logger.debug("Getting latest release information")
        try:
            releases = self._get_all_releases()
            if not releases:
                logger.warning("No releases found")
                return None

            # 只考虑与当前 edition 匹配的 release（lite 更新 lite，nano 更新 nano，
            # standard 更新不带后缀的），并在其中选取基础版本号最高的一个
            best_release = None
            best_version = None
            for release in releases:
                if not release.get("tag_name"):
                    continue
                if not (self.include_prerelease or not release.get("prerelease")):
                    continue
                core, edition = parse_version_with_edition(release.get("tag_name"))
                if edition != self.edition:
                    logger.debug(f"Skipping release {release.get('tag_name')} (edition mismatch)")
                    continue
                try:
                    version = Version(_base_version_str(core))
                except InvalidVersion:
                    logger.debug(f"Skipping release {release.get('tag_name')} (invalid version)")
                    continue
                if best_version is None or version > best_version:
                    best_release, best_version = release, version

            if best_release:
                logger.debug(f"Found suitable release: {best_release.get('tag_name')}")
                return best_release

            logger.warning("No suitable release found")
            return None
        except Exception as e:
            logger.error(f"Error getting latest release: {str(e)}")
            return None

    def _get_all_releases(self):
        logger.debug("Fetching all releases from GitHub API")
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            releases = response.json()
            logger.debug(f"Fetched {len(releases)} releases")
            return releases
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error processing releases data: {str(e)}")
            return []


class MultiThreadDownloader:
    """多线程下载器"""

    def __init__(self, url, filename, progress_callback=None, thread_count_callback=None, num_threads=4,
                 chunk_size=1024 * 1024):
        self.url = url
        self.filename = filename
        self.progress_callback = progress_callback
        self.thread_count_callback = thread_count_callback
        self.num_threads = num_threads
        self.chunk_size = chunk_size
        self.cancelled = False
        self.downloaded_bytes = 0
        self.total_size = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
        self.speed_history = []
        self.actual_threads = 1  # 实际使用的线程数

    def download(self):
        """执行多线程下载"""
        try:
            # 首先检查服务器是否支持断点续传
            headers = {'Range': 'bytes=0-0'}
            test_response = requests.head(self.url, headers=headers, allow_redirects=True, timeout=30)

            # 获取文件总大小
            if 'content-range' in test_response.headers:
                # 服务器支持断点续传
                self.total_size = int(test_response.headers.get('content-range').split('/')[-1])
                logger.info(f"Server supports partial download. File size: {self.total_size} bytes")

                # 根据文件大小决定实际线程数
                min_chunk_size = 1024 * 1024  # 最小1MB per thread
                max_threads = max(1, self.total_size // min_chunk_size)
                self.actual_threads = min(self.num_threads, max_threads)

                # 通知界面实际使用的线程数
                if self.thread_count_callback:
                    self.thread_count_callback(self.actual_threads)

                return self._multi_thread_download()
            else:
                # 服务器不支持断点续传，使用单线程下载
                logger.info("Server doesn't support partial download. Using single thread.")
                self.actual_threads = 1
                if self.thread_count_callback:
                    self.thread_count_callback(1)
                return self._single_thread_download()

        except Exception as e:
            logger.error(f"Error in multi-thread download: {str(e)}")
            return None

    def _multi_thread_download(self):
        """多线程下载实现"""
        file_path = get_path(self.filename)
        final_path = get_path(self.filename, temp_path=False)

        # 计算每个线程的下载范围
        chunk_size = self.total_size // self.actual_threads
        ranges = []

        for i in range(self.actual_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < self.actual_threads - 1 else self.total_size - 1
            ranges.append((start, end, i))

        logger.debug(f"Download ranges for {self.actual_threads} threads: {ranges}")

        # 创建临时文件
        temp_files = []
        download_stats = {}  # 记录每个线程的下载状态

        # 启动进度报告线程
        progress_thread = threading.Thread(target=self._report_progress, args=(download_stats,))
        progress_thread.daemon = True
        progress_thread.start()

        try:
            with ThreadPoolExecutor(max_workers=self.actual_threads) as executor:
                futures = {}

                for start, end, part_num in ranges:
                    temp_file = f"{file_path}.part{part_num}"
                    temp_files.append(temp_file)
                    download_stats[part_num] = {'downloaded': 0, 'total': end - start + 1}

                    future = executor.submit(self._download_chunk, self.url, start, end, temp_file, part_num,
                                             download_stats)
                    futures[future] = part_num

                # 等待所有下载完成
                for future in as_completed(futures):
                    if self.cancelled:
                        executor.shutdown(wait=True, cancel_futures=True)
                        break

                    try:
                        result = future.result()
                        if not result:
                            logger.error(f"Thread {futures[future]} failed")
                            self.cancelled = True
                            executor.shutdown(wait=True, cancel_futures=True)
                            break
                    except Exception as e:
                        logger.error(f"Thread {futures[future]} error: {str(e)}")
                        self.cancelled = True
                        executor.shutdown(wait=True, cancel_futures=True)
                        break

            if self.cancelled:
                # 清理临时文件（此时线程池已 wait=True 等待全部线程退出，文件句柄已释放）
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except OSError as e:
                        logger.warning(f"Failed to remove temp file {temp_file}: {e}")
                return None

            # 合并文件
            logger.info("Merging downloaded parts...")
            with open(file_path, 'wb') as final_file:
                for i, temp_file in enumerate(temp_files):
                    with open(temp_file, 'rb') as part_file:
                        final_file.write(part_file.read())
                    os.remove(temp_file)

            # 移动到最终位置
            if os.path.exists(final_path):
                os.remove(final_path)
            shutil.move(file_path, final_path)

            logger.info(f"Multi-thread download completed: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Error in multi-thread download: {str(e)}")
            # 清理临时文件
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except OSError as e:
                    logger.warning(f"Failed to remove temp file {temp_file}: {e}")
            return None

    def _download_chunk(self, url, start, end, temp_file, part_num, download_stats):
        """下载指定范围的数据块"""
        headers = {'Range': f'bytes={start}-{end}'}

        try:
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()

            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancelled:
                        return False

                    if chunk:
                        f.write(chunk)
                        chunk_size = len(chunk)

                        with self.lock:
                            self.downloaded_bytes += chunk_size
                            download_stats[part_num]['downloaded'] += chunk_size

            return True

        except Exception as e:
            logger.error(f"Error downloading chunk {start}-{end}: {str(e)}")
            return False

    def _report_progress(self, download_stats):
        """定期报告下载进度"""
        last_downloaded = 0
        last_time = time.time()

        while not self.cancelled and self.downloaded_bytes < self.total_size:
            time.sleep(0.1)  # 每0.1秒更新一次

            current_time = time.time()
            time_diff = current_time - last_time

            if time_diff >= 0.1:
                with self.lock:
                    current_downloaded = self.downloaded_bytes

                # 计算速度
                speed = (current_downloaded - last_downloaded) / time_diff if time_diff > 0 else 0

                # 添加到速度历史
                self.speed_history.append(speed)
                if len(self.speed_history) > 20:
                    self.speed_history.pop(0)

                # 计算平均速度
                avg_speed = sum(self.speed_history) / len(self.speed_history) if self.speed_history else speed

                # 调用进度回调
                if self.progress_callback:
                    if not self.progress_callback(current_downloaded, self.total_size, avg_speed):
                        self.cancelled = True
                        break

                last_downloaded = current_downloaded
                last_time = current_time

    def _single_thread_download(self):
        """单线程下载（回退方案）"""
        file_path = get_path(self.filename)
        final_path = get_path(self.filename, temp_path=False)

        try:
            response = requests.get(self.url, stream=True, timeout=30)
            response.raise_for_status()

            self.total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_time = time.time()
            last_downloaded = 0

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        current_time = time.time()
                        time_diff = current_time - last_time

                        if time_diff >= 0.1:
                            speed = (downloaded - last_downloaded) / time_diff if time_diff > 0 else 0

                            if self.progress_callback:
                                if not self.progress_callback(downloaded, self.total_size, speed):
                                    f.close()
                                    time.sleep(0.1)
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                    return None

                            last_time = current_time
                            last_downloaded = downloaded

            # 移动到最终位置
            if os.path.exists(final_path):
                os.remove(final_path)
            shutil.move(file_path, final_path)

            logger.info(f"Single-thread download completed: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Error in single-thread download: {str(e)}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            return None