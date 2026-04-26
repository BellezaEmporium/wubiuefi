from __future__ import annotations

import os
import sys
import shutil
import logging
import gettext
import locale
import configparser
import functools
import subprocess

from gettext import gettext as _
from os.path import abspath, isdir

from .utils import registry
from .utils.drive import Drive
from .utils.tasklist import ThreadedTaskList, Task
from .utils.eject import eject_cd
from .utils import join_path, run_command

from .data.mappings import lang_country2linux_locale
from .distro import Distro
from .mixins import (SysInfoMixin, IsoMixin, DownloadMixin,
                     PreseedMixin, BootloaderMixin, DiskMixin)

from wubi import errors

log = logging.getLogger("Backend")

# ── Distro / installer lookup tables ─────────────────────────────────────────

SOURCE_ID_MAP = {
    "ubuntu":               "ubuntu-desktop",
    "ubuntu-desktop":       "ubuntu-desktop",
    "ubuntu-server":        "ubuntu-server",
    "kubuntu":              "kubuntu-desktop",
    "kubuntu-desktop":      "kubuntu-desktop",
    "xubuntu":              "xubuntu-desktop",
    "xubuntu-desktop":      "xubuntu-desktop",
    "lubuntu":              "lubuntu-desktop",
    "lubuntu-desktop":      "lubuntu-desktop",
    "ubuntu-mate":          "ubuntu-mate-desktop",
    "ubuntu-mate-desktop":  "ubuntu-mate-desktop",
    "ubuntu-budgie":        "ubuntu-budgie-desktop",
    "budgie-desktop":       "ubuntu-budgie-desktop",
    "ubuntu-studio":        "ubuntustudio-desktop",
    "ubuntustudio-desktop": "ubuntustudio-desktop",
    "ubuntukylin":          "ubuntukylin-desktop",
    "ubuntukylin-desktop":  "ubuntukylin-desktop",
}

DISTRO2INSTALLER = {
    "ubuntu-desktop":       "subiquity",
    "kubuntu-desktop":      "calamares",
    "xubuntu-desktop":      "calamares",
    "lubuntu-desktop":      "calamares",
    "ubuntukylin-desktop":  "calamares",
    "ubuntu-mate-desktop":  "calamares",
    "budgie-desktop":       "calamares",
    "ubuntustudio-desktop": "calamares",
}


class Backend(SysInfoMixin, IsoMixin, DownloadMixin,
              PreseedMixin, BootloaderMixin, DiskMixin):

    def __init__(self, application) -> None:
        self.application = application
        self.info        = application.info
        self.cache: dict = {}
        self._is_already_configured = False

        self.info.temp_dir         = join_path(self.info.root_dir, 'temp')
        self.info.data_dir         = join_path(self.info.root_dir, 'data')
        self.info.bin_dir          = join_path(self.info.root_dir, 'bin')
        self.info.image_dir        = join_path(self.info.data_dir, 'images')
        self.info.translations_dir = join_path(self.info.root_dir, 'translations')
        self.info.trusted_keys     = join_path(self.info.data_dir, 'trustedkeys.gpg')
        self.info.application_icon = join_path(
            self.info.image_dir,
            self.info.application_name.capitalize() + '.ico',
        )
        self.info.icon          = self.info.application_icon
        self.info.iso_md5_hashes = {}

        if self.info.locale:
            locale.setlocale(locale.LC_ALL, self.info.locale)
            log.debug(f"user defined locale={self.info.locale}")
        gettext.install(
            self.info.application_name,
            localedir=self.info.translations_dir,
            names=['ngettext'],
        )

    # ── Internal helpers shared across mixins ─────────────────────

    def _decode(self, value) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (bytes, memoryview)):
            try:
                return bytes(value).decode('utf-8', 'ignore')
            except Exception:
                return bytes(value).decode('ascii', 'ignore')
        return str(value)

    def _has_aria2c(self) -> bool:
        candidates = [
            join_path(self.info.root_dir, 'blobs', 'aria2c.exe'),
            join_path(self.info.bin_dir,  'aria2c.exe'),
        ]
        return any(os.path.isfile(p) for p in candidates) or bool(
            shutil.which('aria2c') or shutil.which('aria2c.exe')
        )

    def _find_bcdedit(self) -> str:
        path = shutil.which('bcdedit.exe')
        if path and os.path.isfile(path):
            return path
        system_root = os.environ.get('SystemRoot', r'C:\Windows')
        for sub in ('System32', 'sysnative'):
            candidate = join_path(system_root, sub, 'bcdedit.exe')
            if os.path.isfile(candidate):
                return candidate
        raise FileNotFoundError("bcdedit.exe not found")

    def contains_partition(self, value) -> bool:
        return "partition" in self._decode(value).lower()

    # ── Distros ───────────────────────────────────────────────────

    def get_distros(self) -> list:
        isolist_path = join_path(self.info.data_dir, 'isolist.ini')
        log.debug(f"isolist_path={isolist_path} exists={os.path.isfile(isolist_path)}")
        return self.parse_isolist(isolist_path)

    def parse_isolist(self, isolist_path: str) -> list:
        log.debug(f"Parsing isolist={isolist_path}")
        isolist = configparser.ConfigParser()
        isolist.read(isolist_path)
        distros = []
        for section in isolist.sections():
            log.debug(f"  Adding distro {section}")
            kargs = dict(isolist.items(section))
            kargs.setdefault('md5sums', '')
            kargs.setdefault('iso_url', '')
            kargs.setdefault('releases_url', '')
            distros.append(Distro(backend=self, **kargs))

        def compfunc(x, y):
            if x.ordering == y.ordering: return 0
            return 1 if x.ordering > y.ordering else -1

        distros.sort(key=functools.cmp_to_key(compfunc))
        return distros

    # ── Task lists ────────────────────────────────────────────────

    def get_installation_tasklist(self) -> ThreadedTaskList:
        self.cache_iso_path()
        tasks = [
            Task(self.select_target_dir,         description=_("Selecting the target directory")),
            Task(self.create_dir_structure,      description=_("Creating the installation directories")),
            Task(self.uncompress_target_dir,     description=_("Uncompressing files in the target directory")),
            Task(self.create_uninstaller,        description=_("Creating the uninstaller")),
            Task(self.copy_installation_files,   description=_("Copying installation files")),
            Task(self.get_iso,                   description=_("Retrieving installation files")),
            Task(self.extract_kernel,            description=_("Extracting the kernel")),
            Task(self.choose_disk_sizes,         description=_("Choosing disk sizes")),
            Task(self.create_preseed,            description=_("Creating a preseed file")),
            Task(self.modify_bootloader,         description=_("Adding a new bootloader entry")),
            Task(self.modify_grub_configuration, description=_("Setting up installation boot menu")),
            Task(self.create_virtual_disks,      description=_("Creating the virtual disks")),
            Task(self.uncompress_files,          description=_("Uncompressing files")),
        ]
        description = _("Installing %(distro)s-%(version)s") % dict(
            distro=self.info.distro.name, version=self.info.version)
        return ThreadedTaskList(description=description, tasks=tasks)

    def get_uninstallation_tasklist(self) -> ThreadedTaskList:
        tasks = [
            Task(self.undo_bootloader,    description=_("Remove bootloader entry")),
            Task(self.remove_target_dir,  description=_("Remove target dir")),
            Task(self.remove_registry_key,description=_("Remove registry key")),
        ]
        return ThreadedTaskList(
            description=_(f"Uninstalling {self.info.previous_distro_name}"),
            tasks=tasks,
        )

    def get_cdboot_tasklist(self) -> ThreadedTaskList:
        tasks = [
            Task(self.select_target_dir,    description=_("Selecting the target directory")),
            Task(self.create_dir_structure, description=_("Creating the installation directories")),
            Task(self.uncompress_target_dir,description=_("Uncompressing files")),
            Task(self.create_uninstaller,   description=_("Creating the uninstaller")),
            Task(self.create_preseed_cdboot,description=_("Creating a preseed file")),
            Task(self.modify_bootloader,    description=_("Adding a new bootloader entry")),
        ]
        return ThreadedTaskList(description=_("Configuring CD boot helper"), tasks=tasks)

    # ── Misc ──────────────────────────────────────────────────────

    def show_info(self) -> None:
        log.debug("Showing info")
        os.startfile(self.info.cd_distro.website)

    def reboot(self, associated_task=None) -> None:
        run_command(['shutdown', '-r', '-t', '00'])

    def eject_cd(self, associated_task=None) -> None:
        eject_cd(self.info.cd_path)

    def fetch_installer_info(self) -> None:
        pass

    def run_previous_uninstaller(self) -> bool:
        if (not self.info.previous_uninstaller_path
                or not os.path.isfile(self.info.previous_uninstaller_path)):
            return False
        uninstaller = self.info.previous_uninstaller_path

        if "--uninstall" in sys.argv:
            log.info("Uninstaller invoked via --uninstall — not re-launching")
            return False
        try:
            orig = os.path.realpath(self.info.original_exe).lower()
            prev = os.path.realpath(uninstaller).lower()
            if orig == prev:
                log.info("This is the running uninstaller (path match)")
                return False
        except Exception as e:
            log.debug(f"Error resolving paths: {e}")

        command = [uninstaller, "--uninstall"]
        if self.info.non_interactive:
            command.append("--noninteractive")
        log.info(f"Launching previous uninstaller {uninstaller}")
        try:
            process = subprocess.Popen(command, shell=False)
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            log.error("Previous uninstaller timed out — killing it")
            process.kill()
        if self.application:
            self.application.quit()
        return True