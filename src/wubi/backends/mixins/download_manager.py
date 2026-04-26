from __future__ import annotations

import os
import shutil
import logging

from gettext import gettext as _

from .downloader import download as http_download
from . import btdownloader
from .utils import join_path, copy_file

log = logging.getLogger("Backend.download_manager")


class DownloadMixin:

    # ── ISO ───────────────────────────────────────────────────────

    def get_iso(self, associated_task=None) -> bool:
        if (self.get_prespecified_iso(associated_task)
                or self.use_cd(associated_task)
                or self.use_iso(associated_task)
                or self.download_iso(associated_task)):
            if associated_task:
                return associated_task.finish()
            return True
        raise Exception("Could not retrieve the required installation files")

    def get_prespecified_iso(self, associated_task) -> bool:
        if self.info.iso_path and os.path.exists(self.info.iso_path):
            log.debug(f"Trying pre-specified ISO {self.info.iso_path}")
            is_valid = (
                associated_task.add_subtask(
                    self.info.distro.is_valid_iso,
                    description=_(f"Validating {self.info.iso_path}"))
                if associated_task else self.info.distro.is_valid_iso
            )
            if is_valid(self.info.iso_path, self.info.check_arch):
                self.info.cd_path = None
            return self.copy_iso(self.info.iso_path, associated_task)
        return False

    def download_iso(self, associated_task=None) -> bool:
        log.debug("No ISO found locally — downloading")
        file_url = self.info.distro.iso_url
        save_as  = os.path.join(self.info.install_dir, os.path.basename(file_url))

        if associated_task:
            dl       = associated_task.add_subtask(http_download, is_required=True)
            iso_path = dl(file_url, save_as, web_proxy=self.info.web_proxy)
        else:
            iso_path = http_download(file_url, save_as, web_proxy=self.info.web_proxy)

        if not iso_path:
            raise Exception("Download failed")

        if associated_task:
            verify = associated_task.add_subtask(
                self.check_iso, description=_("Verifying ISO"))
            ok = verify(iso_path)
        else:
            ok = self.check_iso(iso_path)

        if not ok:
            os.unlink(iso_path)
            raise Exception("ISO verification failed")

        self.info.iso_path = iso_path
        return True

    def copy_iso(self, iso_path: str, associated_task) -> bool:
        if not iso_path:
            return False
        dest      = join_path(self.info.install_dir, iso_path.split('/')[-1])
        check_iso = (
            associated_task.add_subtask(self.check_iso, description=_("Checking installation files"))
            if associated_task else self.check_iso
        )
        if not check_iso(iso_path):
            return False
        if os.path.dirname(iso_path) == dest:
            mover = (
                associated_task.add_subtask(shutil.move, description=_("Copying installation files"))
                if associated_task else shutil.move
            )
            log.debug(f"Moving {iso_path} > {dest}")
            mover(iso_path, dest)
        else:
            copier = (
                associated_task.add_subtask(copy_file, description=_("Copying installation files"))
                if associated_task else copy_file
            )
            log.debug(f"Copying {iso_path} > {dest}")
            copier(iso_path, dest)
        self.info.cd_path  = None
        self.info.iso_path = dest
        return True

    def use_cd(self, associated_task) -> bool:
        if not self.iso_path:
            return False
        extract_iso = (
            associated_task.add_subtask(
                copy_file,
                description=_(f"Extracting files from {self.iso_path}"))
            if associated_task else copy_file
        )
        self.info.iso_path = join_path(
            self.info.install_dir, self.iso_path.split('/')[-1])
        try:
            extract_iso(self.info.iso_path, self.info.iso_path)
        except Exception as err:
            log.error(err)
            self.info.cd_path = self.info.iso_path = None
            return False
        self.info.cd_path = self.iso_path
        check_iso = (
            associated_task.add_subtask(self.check_iso, description=_("Checking installation files"))
            if associated_task else self.check_iso
        )
        if not check_iso(self.info.iso_path):
            subversion = self.info.cd_distro.get_info(self.info.cd_path)[2]
            if subversion.lower() in ("alpha", "beta", "release candidate"):
                log.error(f"CD check failed, ignoring because CD is {subversion}")
            else:
                self.info.cd_path = self.info.iso_path = None
                return False
        return True

    def use_iso(self, associated_task) -> bool:
        if self.iso_path:
            log.debug(f"Trying to use ISO {self.iso_path}")
            return self.copy_iso(self.iso_path, associated_task)
        return False

    # ── Disk image ────────────────────────────────────────────────

    def get_diskimage(self, associated_task=None) -> None:
        if self.get_prespecified_diskimage(associated_task):
            if associated_task:
                return associated_task.finish()
            return

        dimage  = self.info.distro.diskimage
        dimage2 = self.info.distro.diskimage2

        if dimage and dimage.endswith('.torrent') and not self._has_aria2c():
            log.info("Torrent requested but aria2c unavailable — trying direct download")
            if dimage2 and self.download_diskimage(dimage2, associated_task):
                if associated_task:
                    return associated_task.finish()
                return

        if self.download_diskimage(dimage, associated_task):
            if associated_task:
                return associated_task.finish()
            return

        if dimage2 and self.download_diskimage(dimage2, associated_task):
            if associated_task:
                return associated_task.finish()
            return

        raise Exception("Could not retrieve the required disk image files")

    def get_prespecified_diskimage(self, associated_task) -> bool:
        if self.info.disk_image_path and os.path.exists(self.info.disk_image_path):
            self.dimage_path = self.info.disk_image_path
            log.debug(f"Trying pre-specified disk image {self.info.disk_image_path}")
            is_valid = (
                associated_task.add_subtask(
                    self.info.distro.is_valid_dimage,
                    description=_(f"Validating {self.info.disk_image_path}"))
                if associated_task else self.info.distro.is_valid_dimage
            )
            if is_valid(self.info.disk_image_path, self.info.check_arch):
                self.info.cd_path = None
                return True
        return False

    def download_diskimage(self, diskimage: str, associated_task=None) -> bool:
        proxy   = self.info.web_proxy
        save_as = join_path(self.info.disks_dir, diskimage.split('/')[-1])
        if os.path.isfile(save_as):
            os.unlink(save_as)
        try:
            use_torrent = diskimage.endswith('.torrent') and self._has_aria2c()
            if use_torrent:
                dl = (
                    associated_task.add_subtask(btdownloader.download, is_required=False)
                    if associated_task else btdownloader.download
                )
                self.dimage_path = dl(
                    diskimage, save_as,
                    root_dir=self.info.root_dir, web_proxy=proxy,
                )
            else:
                dl = (
                    associated_task.add_subtask(http_download, is_required=False)
                    if associated_task else http_download
                )
                self.dimage_path = dl(diskimage, save_as, web_proxy=proxy)
            return self.dimage_path is not None
        except Exception:
            log.exception(f"Cannot download disk image {diskimage}")
            return False

    def copy_diskimage(self, dimage_path: str, associated_task) -> bool:
        if not dimage_path:
            return False
        dimage_name = self.info.distro.diskimage.split('/')[-1]
        dest = os.path.join(self.info.disks_dir, dimage_name)
        copy_dimage = (
            associated_task.add_subtask(copy_file, description=_("Copying installation files"))
            if associated_task else copy_file
        )
        log.debug(f"Copying {dimage_path} > {dest}")
        copy_dimage(dimage_path, dest)
        return True