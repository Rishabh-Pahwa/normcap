"""Find new version on github or pypi."""

import logging
import re

from PySide6 import QtCore, QtGui, QtWidgets

from normcap import __version__
from normcap.gui.constants import INFO_UPDATE_GITHUB, INFO_UPDATE_PIP, URLS
from normcap.gui.downloader import Downloader

logger = logging.getLogger(__name__)


class Communicate(QtCore.QObject):
    """TrayMenus' communication bus."""

    check = QtCore.Signal()  # request a version check
    on_version_checked = QtCore.Signal(str)  # newest available version
    on_click_get_new_version = QtCore.Signal(str)  # url to new version


class UpdateChecker(QtWidgets.QWidget):
    """Check for a new normcap version."""

    def __init__(
        self, parent: QtCore.QObject | None = None, packaged: bool = False
    ) -> None:
        super().__init__(parent=parent)
        self.packaged = packaged

        self.com = Communicate(parent=self)
        self.com.check.connect(self._check)

        self.downloader = Downloader()
        self.downloader.com.on_download_finished.connect(self._on_download_finished)

        self.url = URLS.releases_atom if self.packaged else f"{URLS.pypi_json}"
        self.version_regex = (
            r"/releases/tag/v(\d+\.\d+\.\d+)\""  # atom
            if self.packaged
            else r"\"version\":\s*\"(\d+\.\d+\.\d+)\""  # json
        )
        self.message_box = self._create_message_box()

    @QtCore.Slot()
    def _check(self) -> None:
        """Start the update check."""
        logger.debug("Search for new version on %s", self.url)
        self.downloader.get(self.url, timeout=10)

    @QtCore.Slot(bytes, str)
    def _on_download_finished(self, data: bytes, url: str) -> None:
        """Parse the tag version from the response and emit version retrieved signal."""
        fetched_version = None
        try:
            text = data.decode("utf-8", errors="ignore")
            match = re.search(self.version_regex, text)
            if match and match[1]:
                fetched_version = match[1]
        except Exception:
            logger.exception("Parsing response of update check failed.")

        if not fetched_version:
            logger.error("Could not detect remote version. Update check won't work!")
            return

        logger.debug("Newest version: %s (installed: %s)", fetched_version, __version__)
        self.com.on_version_checked.emit(fetched_version)
        if self._is_new_version(current=__version__, other=fetched_version):
            self._show_update_message(version=fetched_version)

    def _show_update_message(self, version: str) -> None:
        """Show dialog informing about available update."""
        text = f"<b>NormCap v{version} is available.</b> (You have v{__version__})"
        self.message_box.setText(text)

        info_text = INFO_UPDATE_GITHUB if self.packaged else INFO_UPDATE_PIP
        self.message_box.setInformativeText(info_text)
        self.message_box.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

        choice = self.message_box.exec_()

        if choice == QtWidgets.QMessageBox.Ok:
            update_url = URLS.releases if self.packaged else URLS.changelog
            self.com.on_click_get_new_version.emit(update_url)

    def _create_message_box(self) -> QtWidgets.QMessageBox:
        message_box = QtWidgets.QMessageBox(parent=self.parent())
        # Necessary on wayland for main window to regain focus:
        # TODO: Test if still necessary after transformation to QWidget!
        message_box.setWindowFlags(QtCore.Qt.WindowType.Popup)

        message_box.setIconPixmap(QtGui.QIcon(":normcap").pixmap(48, 48))
        message_box.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Ok
            | QtWidgets.QMessageBox.StandardButton.Cancel
        )
        message_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Ok)
        return message_box

    @staticmethod
    def _is_new_version(current: str, other: str) -> bool:
        """Compare version strings.

        As the versions compare are within the scope of this project, a simple parsing
        logic will do. It is based on the assumption that semver is used. Pre-releases
        are discarded and will not pre considered a new version.

        NOTE: This is not very robust, so do not use elsewhere! But the standard
        solution packaging.version is not used here on purpose to avoid that dependency.
        That reduces import time and package size.
        """
        if "-" in other:
            logging.debug("Discarding pre-release version %s", other)
            return False

        current = current.split("-")[0]
        current_version = [int(c) for c in current.split(".")]
        other_version = [int(c) for c in other.split(".")]
        return other_version > current_version
