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

import requests
import shutil
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from packaging.version import Version, InvalidVersion
from modless_chat_trans.file_utils import get_path, get_platform
from modless_chat_trans.logger import logger


class Updater:
    def __init__(self, current_version, owner, repo, include_prerelease=False):
        logger.info(f"Initializing updater: version={current_version}, repo={owner}/{repo}")
        self.current_version = Version(current_version.lstrip("v"))
        self.owner = owner
        self.repo = repo
        self.include_prerelease = include_prerelease
        self.api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        logger.debug(f"API URL set to: {self.api_url}")

    def check_update(self):
        logger.info("Checking for updates")
        try:
            latest_release = self._get_latest_release()
            if latest_release:
                latest_version_str = latest_release.get("tag_name").lstrip("v")
                logger.debug(f"Latest version found: {latest_version_str}")
                try:
                    latest_version = Version(latest_version_str)
                    if latest_version > self.current_version:
                        logger.info(f"New version available: {latest_version_str}")
                        return latest_release
                    else:
                        logger.info(f"Current version {self.current_version} is up to date")
                except InvalidVersion:
                    logger.error(f"Invalid version format: {latest_version_str}")
            else:
                logger.warning("No release information found")
            return None
        except Exception as e:
            logger.error(f"Error checking for updates: {str(e)}")
            return None

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
                asset = next((asset for asset in assets if asset.get("name").endswith(".exe")), None)
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

            for release in releases:
                if release.get("tag_name") and (self.include_prerelease or not release.get("prerelease")):
                    logger.debug(f"Found suitable release: {release.get('tag_name')}")
                    return release

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
            test_response = requests.head(self.url, headers=headers, allow_redirects=True)

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
                        executor.shutdown(wait=False)
                        break

                    try:
                        result = future.result()
                        if not result:
                            logger.error(f"Thread {futures[future]} failed")
                            self.cancelled = True
                            executor.shutdown(wait=False)
                            break
                    except Exception as e:
                        logger.error(f"Thread {futures[future]} error: {str(e)}")
                        self.cancelled = True
                        executor.shutdown(wait=False)
                        break

            if self.cancelled:
                # 清理临时文件
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except:
                        pass
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
                except:
                    pass
            return None

    def _download_chunk(self, url, start, end, temp_file, part_num, download_stats):
        """下载指定范围的数据块"""
        headers = {'Range': f'bytes={start}-{end}'}

        try:
            response = requests.get(url, headers=headers, stream=True)
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
            response = requests.get(self.url, stream=True)
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