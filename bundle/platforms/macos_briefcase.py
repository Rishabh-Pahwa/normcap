"""Run adjustments while packaging with briefcase during CI/CD."""

import platform
import shutil
from pathlib import Path

from platforms.utils import BuilderBase


class MacBriefcase(BuilderBase):
    """Create prebuilt package for macOS using Briefcase."""

    binary_suffix = ""

    def run_framework(self) -> None:
        self.run(cmd="briefcase create", cwd=self.PROJECT_PATH)
        self.bundle_tesseract()
        self.run(cmd="briefcase build", cwd=self.PROJECT_PATH)
        # TODO: Re-enable if we have a solution for unfocusing on macOS
        # patch_info_plist_for_proper_fullscreen()
        self.run(cmd="briefcase package macos app --no-sign", cwd=self.PROJECT_PATH)

    @staticmethod
    def _get_path_to_tesseract() -> Path:
        if which := shutil.which("tesseract"):
            return Path(which).resolve()
        return Path("/usr/local/bin/tesseract")

    def bundle_tesseract(self) -> None:
        bin_path = (
            self.PROJECT_PATH
            / "build"
            / "normcap"
            / "macos"
            / "app"
            / "NormCap.app"
            / "Contents"
            / "Resources"
            / "app_packages"
            / "bin"
        )
        bin_path.mkdir(exist_ok=True)

        tesseract_source = self._get_path_to_tesseract()
        tesseract_target = bin_path / "tesseract"
        install_path = "@executable_path/"
        self.run(
            cmd=(
                "dylibbundler "
                f"--fix-file {tesseract_source.resolve()} "
                f"--dest-dir {bin_path.resolve()} "
                f"--install-path {install_path} "
                "--bundle-deps "
                "--overwrite-files"
            ),
            cwd=self.BUILD_PATH,
        )
        shutil.copy(tesseract_source, tesseract_target)

    def patch_info_plist_for_proper_fullscreen(self) -> None:
        """Set attribute to keep dock and menubar hidden in fullscreen.

        See details:
        https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/LaunchServicesKeys.html#//apple_ref/doc/uid/20001431-113616
        """
        file_path = Path("macOS/app/NormCap/NormCap.app/Contents") / "Info.plist"
        patch = """
    <key>LSUIPresentationMode</key>
    <integer>3</integer>
"""
        insert_after = "<string>normcap</string>"
        self.patch_file(
            file_path=file_path,
            insert_after=insert_after,
            patch=patch,
            comment_prefix="",
        )

    def install_system_deps(self) -> None:
        self.run(cmd="brew install tesseract")
        self.run(cmd="brew install dylibbundler")

    def rename_package_file(self) -> None:
        source = list(Path(self.PROJECT_PATH / "dist").glob("*.dmg"))[0]
        arch = "arm64" if platform.machine().startswith("arm64") else "x86_64"
        target = (
            self.BUILD_PATH
            / f"NormCap-{self.get_version()}-{arch}-macOS{self.binary_suffix}.dmg"
        )
        target.unlink(missing_ok=True)
        shutil.move(source, target)

    def create(self) -> None:
        self.download_tessdata()
        self.install_system_deps()
        self.run_framework()
        self.rename_package_file()
