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

import requests
import shutil
from packaging.version import Version, InvalidVersion
from modless_chat_trans.file_utils import get_path, get_platform


class Updater:
    def __init__(self, current_version, owner, repo, include_prerelease=False):
        self.current_version = Version(current_version.lstrip("v"))
        self.owner = owner
        self.repo = repo
        self.include_prerelease = include_prerelease
        self.api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"

    def check_update(self):
        latest_release = self._get_latest_release()
        if latest_release:
            latest_version_str = latest_release.get("tag_name").lstrip("v")
            try:
                latest_version = Version(latest_version_str)
                if latest_version > self.current_version:
                    return latest_release
            except InvalidVersion:
                return None

    @staticmethod
    def download_update(latest_release):
        assets = latest_release.get("assets", [])
        if assets:
            if get_platform() == 0:
                asset = next((asset for asset in assets if asset.get("name").endswith(".exe")), None)
            elif get_platform() == 1:
                asset = next((asset for asset in assets if asset.get("name").endswith(".tar.gz")), None)
            else:
                return None

            if asset:
                download_url = asset.get("browser_download_url")
                try:
                    response = requests.get(download_url, stream=True)
                    file_path = get_path(asset.get("name"))
                    final_path = get_path(asset.get("name"), temp_path=False)

                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    shutil.move(file_path, final_path)

                    return final_path
                except requests.exceptions.RequestException:
                    return None
            else:
                return None
        else:
            return None

    def _get_latest_release(self):
        releases = self._get_all_releases()
        if not releases:
            return None
        for release in releases:
            if release.get("tag_name") and (self.include_prerelease or not release.get("prerelease")):
                return release
        return None

    def _get_all_releases(self):
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return []
