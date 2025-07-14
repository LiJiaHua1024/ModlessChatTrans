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
    def download_update(latest_release):
        logger.info(f"Downloading update: {latest_release.get('tag_name')}")
        try:
            assets = latest_release.get("assets", [])
            if assets:
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

                if asset:
                    download_url = asset.get("browser_download_url")
                    logger.debug(f"Download URL: {download_url}")
                    try:
                        response = requests.get(download_url, stream=True)
                        response.raise_for_status()
                        file_path = get_path(asset.get("name"))
                        final_path = get_path(asset.get("name"), temp_path=False)

                        logger.debug(f"Saving to temporary path: {file_path}")
                        with open(file_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)

                        logger.debug(f"Moving to final path: {final_path}")
                        shutil.move(file_path, final_path)
                        logger.info(f"Update downloaded successfully to {final_path}")
                        return final_path
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Request error: {str(e)}")
                        return None
                else:
                    logger.warning(f"No suitable asset found for platform {platform}")
                    return None
            else:
                logger.warning("No assets found in the release")
                return None
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
