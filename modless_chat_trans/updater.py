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
from packaging.version import Version, InvalidVersion


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
                    return latest_release.get("tag_name")
            except InvalidVersion:
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
