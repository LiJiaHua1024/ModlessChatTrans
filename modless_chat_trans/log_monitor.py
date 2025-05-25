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
import threading
import chardet
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from modless_chat_trans.file_utils import find_latest_log
from modless_chat_trans.logger import logger


class LogMonitorHandler(FileSystemEventHandler):
    """
    监控日志文件的变化
    """

    def __init__(self, directory, callback, use_high_version_fix, encoding=None):
        super().__init__()
        logger.debug(f"Initializing LogMonitorHandler for directory: {directory}, "
                     f"high_version_fix: {use_high_version_fix}, encoding: {encoding}")
        self.directory = directory
        self.callback = callback
        self.use_high_version_fix = use_high_version_fix
        self.encoding = encoding
        self.current_file = os.path.join(directory, "latest.log") if use_high_version_fix else find_latest_log(directory)
        self.file_pointer = None
        self.line_number = 0
        while not self.current_file:
            logger.info(f"No initial log file found in {directory}. Waiting and retrying in 5 seconds...")
            time.sleep(5)
            self.current_file = find_latest_log(directory)

        logger.info(f"Monitoring initial log file: {self.current_file}")

    def open_file(self, file_path):
        """
        打开指定文件并移动到末尾
        """
        if self.file_pointer:
            try:
                self.file_pointer.close()
                logger.debug(f"Closed previous file pointer for: {self.file_pointer.name}")
            except Exception as e:
                logger.warning(f"Error closing previous file pointer: {str(e)}")

        self.file_pointer = None
        self.line_number = 0

        try:
            chunk_size = 65536  # 64KB
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.line_number += chunk.count(b'\n')

            encoding = self.encoding or "utf-8"
            self.file_pointer = open(file_path, 'r', encoding=encoding)
            self.file_pointer.seek(0, os.SEEK_END)
        except (PermissionError, FileNotFoundError) as e:
            logger.warning(f"Error opening file {file_path}: {str(e)}. Will attempt retry shortly if needed.")
            time.sleep(5)
            if not self.use_high_version_fix:
                logger.info(f"Attempting to find a potentially newer log file in {self.directory} due to error.")
                latest_log = find_latest_log(self.directory)
                if latest_log and latest_log != self.current_file:
                    logger.info(f"Found newer log file: {latest_log}. Switching.")
                    self.current_file = latest_log
                elif latest_log:
                    logger.info(f"No new log found, retrying same file.")
                else:
                    logger.error(f"Could not find any log file in {self.directory} after error.")
                    while not self.current_file:
                        logger.info(f"No log file found in {self.directory}. Waiting and retrying in 5 seconds...")
                        time.sleep(5)
                        self.current_file = find_latest_log(self.directory)
            else:
                logger.info(f"Continuing to monitor {self.current_file} despite error, hoping it becomes available.")
            self.open_file(self.current_file)
        except Exception as e:
            logger.exception(f"An unexpected error occurred while opening or seeking file {file_path}: {str(e)}")

    def activate_file(self):
        """
        激活 log 文件，解决高版本 Minecraft 优化导致的问题
        """
        logger.info(f"Activating high version fix for file: {self.current_file}")

        def _read():
            logger.debug(f"Background file activation thread started for {self.current_file}")
            while True:
                try:
                    with open(self.current_file, 'rb'):
                        pass
                    time.sleep(0.2)
                except (PermissionError, FileNotFoundError):
                    logger.warning(f"Activation fix: File {self.current_file} not accessible. Retrying in 2 seconds.")
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Activation fix: Unexpected error for {self.current_file}: {str(e)}. Retrying in 2 seconds.")
                    time.sleep(2)

        threading.Thread(target=_read, daemon=True).start()
        logger.debug("Background file activation thread initiated.")

    @staticmethod
    def _detect_file_encoding(file_path):
        """
        检测文件的编码
        """
        logger.debug(f"Detecting encoding for file: {file_path}")
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(1024)
                result = chardet.detect(raw_data)
                encoding = result.get("encoding", "utf-8") or "utf-8"  # Ensure encoding is not None
                confidence = result.get("confidence", 0.0) or 0.0

                if confidence < 0.8 and confidence != 1.0:  # chardet sometimes returns 1.0 for utf-8 even on small reads
                    logger.debug(f"Low confidence ({confidence:.2f}) for encoding '{encoding}'. Reading more data.")
                    f.seek(0)
                    raw_data = f.read(8192)
                    result = chardet.detect(raw_data)
                    encoding = result.get("encoding", "utf-8") or "utf-8"
                    confidence = result.get("confidence", 0.0) or 0.0
                    logger.debug(f"Re-evaluated encoding: '{encoding}' with confidence {confidence:.2f}")

                if encoding.upper() in {"GB2312", "GBK"}:
                    logger.info(f"Detected encoding {encoding} for {file_path}, "
                                f"promoting to GB18030 for broader compatibility.")
                    encoding = "GB18030"

        except FileNotFoundError:
            logger.error(f"File not found during encoding detection: {file_path}")
            return "utf-8"
        except Exception as e:
            logger.error(f"Error during encoding detection for {file_path}: {str(e)}")
            return "utf-8"

        logger.debug(f"Final detected encoding for {file_path}: {encoding} (Confidence: {confidence:.2f})")
        return encoding

    def _read_new_lines(self):
        """
        读取当前文件的新内容
        """
        logger.debug(f"Starting to read new content from file {self.current_file}")
        if self.file_pointer:
            while True:
                try:
                    logger.debug(f"Attempting to read new lines from file, current line number: {self.line_number}")
                    for line in self.file_pointer:
                        self.line_number += 1
                        # 使用线程调用回调函数，避免阻塞
                        threading.Thread(target=self.callback, daemon=True, args=(line,),
                                         kwargs={"data_type": "log"}).start()
                    logger.debug("Finished reading the file")
                    break
                except UnicodeDecodeError:
                    if self.encoding:
                        logger.error(f"Failed to parse the file using user specified encoding {self.encoding}, "
                                     f"skipping current line")
                        self.line_number += 1
                        continue

                    logger.warning(f"Encoding parsing error occurred for file {self.current_file}, "
                                   f"attempting to re-detect encoding")
                    encoding = self._detect_file_encoding(self.current_file)
                    logger.info(f"Detected file encoding as: {encoding}")
                    self.file_pointer.close()
                    self.file_pointer = open(self.current_file, 'r', encoding=encoding)
                    try:
                        logger.debug(f"Skipping {self.line_number} lines that have already been read")
                        for i in range(self.line_number):
                            self.file_pointer.readline()
                        logger.debug("Starting to read new lines")
                        for line in self.file_pointer:
                            self.line_number += 1
                            threading.Thread(target=self.callback, daemon=True, args=(line,),
                                             kwargs={"data_type": "log"}).start()
                        logger.debug("Finished reading the file")
                        break
                    except UnicodeDecodeError:
                        logger.error(f"Failed to parse the file using detected encoding {encoding}, "
                                     f"skipping current line")
                        self.line_number += 1
        else:
            logger.warning("File pointer is empty, unable to read the file")
        logger.debug("Finished executing _read_new_lines method")

    def on_modified(self, event):
        if event.src_path == self.current_file:
            logger.debug(f"File modified: {event.src_path}. Checking for new lines.")
            self._read_new_lines()

    def on_created(self, event):
        logger.debug(f"Detected file creation event for: {event.src_path}")

        if self.use_high_version_fix:
            return

        if event.src_path.endswith('.log'):
            logger.info(f"New log file detected: {event.src_path}")
            # 切换到新文件
            logger.debug(f"Switching current file from {self.current_file} to {event.src_path}")
            self.current_file = event.src_path
            logger.debug(f"Opening new log file: {self.current_file}")
            self.open_file(self.current_file)
        else:
            logger.debug(f"Ignoring non-log file creation: {event.src_path}")


def monitor_log_file(directory, callback, use_high_version_fix, encoding):
    """
    启动日志文件监控

    :param directory: 要监控的日志文件目录
    :param callback: 检测到新内容的回调函数
    :param use_high_version_fix: 是否使用高版本 Minecraft 修复
    :param encoding: 用户指定的文件编码，如果为空则自动检测
    """
    logger.info(f"Starting log file monitoring in directory: {directory}")

    event_handler = LogMonitorHandler(directory, callback, use_high_version_fix, encoding)
    if event_handler.current_file:
        event_handler.open_file(event_handler.current_file)
    else:
        logger.error(f"Could not determine initial log file in {directory}. Monitoring might not start correctly.")

    if use_high_version_fix and event_handler.current_file:
        logger.debug("High version fix is enabled, activating file keep-alive.")
        event_handler.activate_file()

    observer = Observer()
    observer.schedule(event_handler, directory, recursive=False)
    logger.info(f"Observer scheduled for directory: {directory}. Starting observer thread.")
    observer.start()

    try:
        observer.join()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Stopping observer...")
        observer.stop()
    except Exception as e:
        logger.error(f"An unexpected error occurred in the monitoring loop: {str(e)}")
        observer.stop()
        logger.error("Observer stopped due to unexpected error.")

    observer.join()
    logger.info("Log file monitoring stopped.")

    if event_handler.file_pointer:
        try:
            event_handler.file_pointer.close()
            logger.debug(f"Closed final log file pointer for {event_handler.current_file}")
        except Exception as e:
            logger.warning(f"Error closing final log file pointer: {e}")
