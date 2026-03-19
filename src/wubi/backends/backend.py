# Copyright (c) 2008 Agostino Russo
#
# Written by Agostino Russo <agostino.russo@gmail.com>
#
# This file is part of Wubi the Win32 Ubuntu Installer.
#
# Wubi is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2.1 of
# the License, or (at your option) any later version.
#
# Wubi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import locale
import logging
import gettext
import glob
import shutil
import configparser
import functools
import subprocess
import ctypes
import platform
import re
import tempfile
import threading
import py7zr

from os.path import abspath, isfile, isdir
from gettext import gettext as _

from .drive import Drive
from .virtualdisk import create_virtual_disk
from .eject import eject_cd
from . import registry
from .memory import get_total_memory_mb
from . import mappings as win32_mappings
from .downloader import download as http_download
from . import btdownloader
from .iso_verifier import verify_iso
from .tasklist import ThreadedTaskList, Task
from .distro import Distro
from .mappings import lang_country2linux_locale
from .utils import (
    join_path, md5_password, hash_password, copy_file, read_file,
    write_file, get_file_hash, find_line_in_file, unix_path,
    rm_tree, spawn_command, run_command, run_nonblocking_command,
    replace_line_in_file, remove_line_in_file,
)
from wubi import errors

log = logging.getLogger("Backend")

# Source ID map — valid IDs are defined in casper/install-sources.yaml on each ISO
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


class Backend(object):
    """
    Windows backend implementation. Provides methods for fetching system information,
    managing downloads, verifying ISOs, and performing installation tasks.
    """

    # ── Initialisation ───────────────────────────────────────────────────────

    def __init__(self, application):
        self.application = application
        self.info = application.info
        self.cache = {}

        # Base paths derived from root_dir
        self.info.temp_dir         = join_path(self.info.root_dir, 'temp')
        self.info.data_dir         = join_path(self.info.root_dir, 'data')
        self.info.bin_dir          = join_path(self.info.root_dir, 'bin')
        self.info.image_dir        = join_path(self.info.data_dir, 'images')
        self.info.translations_dir = join_path(self.info.root_dir, 'translations')
        self.info.trusted_keys     = join_path(self.info.data_dir, 'trustedkeys.gpg')
        self.info.application_icon = join_path(
            self.info.image_dir,
            self.info.application_name.capitalize() + ".ico"
        )
        self.info.icon         = self.info.application_icon
        self.info.iso_md5_hashes = {}

        # Locale setup
        if self.info.locale:
            locale.setlocale(locale.LC_ALL, self.info.locale)
            log.debug('user defined locale=%s' % self.info.locale)
        gettext.install(
            self.info.application_name,
            localedir=self.info.translations_dir,
            names=['ngettext'],
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _decode(self, output):
        if isinstance(output, (bytes, bytearray, memoryview)):
            return bytes(output).decode('utf-8', errors='replace')
        return output or ""

    def _has_aria2c(self):
        """Verifies if aria2c is available."""
        candidates = [
            join_path(self.info.root_dir, 'blobs', 'aria2c.exe'),
            join_path(self.info.bin_dir, 'aria2c.exe'),
        ]
        return any(os.path.isfile(p) for p in candidates) or bool(
            shutil.which('aria2c') or shutil.which('aria2c.exe')
        )

    def _find_bcdedit(self):
        """Locates bcdedit.exe.
        On 64-bit Windows, 32-bit applications are redirected to
        SysWOW64 — so we need to check sysnative as well.
        """
        path_candidate = shutil.which('bcdedit.exe')
        if path_candidate and os.path.isfile(path_candidate):
            return path_candidate
        candidates = [
            join_path(os.environ.get('SystemRoot', r'C:\Windows'), 'System32',  'bcdedit.exe'),
            join_path(os.environ.get('SystemRoot', r'C:\Windows'), 'sysnative', 'bcdedit.exe'),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        raise FileNotFoundError("bcdedit.exe not found")

    def contains_partition(self, value):
        if isinstance(value, str):
            text = value
        elif isinstance(value, memoryview):
            text = value.tobytes().decode('utf-8', errors='ignore')
        else:
            text = bytes(value).decode('utf-8', errors='ignore')
        return 'partition=' in text

    # ── System information ─────────────────────────────────────────────────

    def fetch_basic_info(self):
        """Basic information required by the select_task() dispatcher."""
        log.debug("Fetching basic info...")
        self.info.uninstall_before_install = False
        self.info.original_exe = self.get_original_exe()
        self.info.platform     = self.get_platform()
        self.info.osname       = self.get_osname()
        if not self.info.language:
            self.info.language, self.info.encoding = self.get_language_encoding()
        self.info.environment_variables = os.environ
        self.info.arch = self.get_arch()
        if self.info.force_i386:
            self.info.arch = "i386"
        self.info.check_arch = False
        self.info.distro      = None

        # fetch_host_info recalculates root_dir and data_dir — call it before get_distros
        self.fetch_host_info()

        self.info.distros = self.get_distros()
        distros = [((d.name.lower(), d.arch), d) for d in self.info.distros]
        self.info.distros_dict = dict(distros)

        self.info.previous_uninstaller_path = self.get_uninstaller_path()
        self.info.previous_target_dir       = self.get_previous_target_dir()
        self.info.previous_distro_name      = self.get_previous_distro_name()
        self.info.keyboard_layout, self.info.keyboard_variant = self.get_keyboard_layout()
        if not self.info.locale:
            self.info.locale = self.get_locale(self.info.language)
        self.info.total_memory_mb = self.get_total_memory_mb()
        self.info.iso_path, self.info.iso_distro = self.find_any_iso()

    def fetch_host_info(self):
        log.debug("Fetching host info...")
        self.info.registry_key       = self.get_registry_key()
        self.info.windows_version    = self.get_windows_version()
        self.info.windows_version2   = self.get_windows_version2()
        self.info.windows_sp         = self.get_windows_sp()
        self.info.windows_build      = self.get_windows_build()
        self.info.gmt                = self.get_gmt()
        self.info.country            = self.get_country()
        self.info.timezone           = self.get_timezone()
        self.info.host_username      = self.get_windows_username()
        self.info.user_full_name     = self.get_windows_user_full_name()
        self.info.user_directory     = self.get_windows_user_dir()
        self.info.windows_language_code = self.get_windows_language_code()
        self.info.windows_language   = self.get_windows_language()
        self.info.processor_name     = self.get_processor_name()
        self.info.bootloader         = self.get_bootloader(self.info.windows_version)
        self.info.system_drive       = self.get_system_drive()
        self.info.drives             = self.get_drives()
        drives = [(d.path[:2].lower(), d) for d in self.info.drives]
        self.info.drives_dict        = dict(drives)
        self.info.efi                = self.check_EFI()
        self.info.source_id          = self._get_source_id()
        self.info.installer_type     = self.get_installer_type()
        self.info.previous_target_dir  = self.get_previous_target_dir()
        self.info.previous_distro_name = self.get_previous_distro_name()
        self.info.hostname = os.environ.get('COMPUTERNAME', 'wubi-host').lower()
        self.info.username = self.info.host_username

        # Redefine root_dir from the actual exe, then derive data_dir etc.
        # Skip in PyInstaller mode — get_base_path() has already set everything up.
        if not hasattr(sys, '_MEIPASS'):
            root_dir = os.path.abspath(
                os.path.join(os.path.dirname(self.info.original_exe), '..')
            )
            self.info.root_dir         = root_dir
            self.info.data_dir         = join_path(root_dir, 'data')
            self.info.bin_dir          = join_path(root_dir, 'bin')
            self.info.image_dir        = join_path(self.info.data_dir, 'images')
            self.info.translations_dir = join_path(root_dir, 'translations')
            self.info.locale_dir       = join_path(root_dir, 'translations')

    def get_original_exe(self):
        if self.info.original_exe:
            original_exe = self.info.original_exe
        else:
            original_exe = abspath(sys.argv[0])
        log.debug("original_exe=%s" % original_exe)
        return original_exe

    def get_platform(self):
        p = sys.platform
        log.debug("platform=%s" % p)
        return p

    def get_osname(self):
        n = os.name
        log.debug("osname=%s" % n)
        return n

    def get_language_encoding(self):
        language, encoding = locale.getdefaultlocale()
        log.debug("language=%s encoding=%s" % (language, encoding))
        return language, encoding

    def get_arch(self):
        arch = platform.machine()
        log.debug("arch=%s" % arch.lower())
        return arch.lower()

    def get_locale(self, language_country, fallback="en_US"):
        _locale = lang_country2linux_locale.get(language_country)
        if not _locale:
            _locale = lang_country2linux_locale.get(fallback)
        log.debug("locale=%s" % _locale)
        return _locale

    def get_total_memory_mb(self):
        mb = get_total_memory_mb()
        log.debug("total_memory_mb=%s" % mb)
        return mb

    def get_windows_version(self):
        full_version = sys.getwindowsversion()
        major, minor, build, p, txt = full_version
        version = None
        if p == 0:
            version = 'win32'
        elif p == 1:
            if major == 4:
                version = {0: '95', 10: '98', 90: 'me'}.get(minor)
        elif p == 2:
            if major == 4:
                version = 'nt'
            elif major == 5:
                version = {0: '2000', 1: 'xp', 2: '2003'}.get(minor)
            elif major >= 6:
                version = 'vista'
        log.debug("windows version=%s" % version)
        return version

    def get_windows_version2(self):
        v = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion',
            'ProductName')
        log.debug("windows_version2=%s" % v)
        return v

    def get_windows_sp(self):
        sp = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion',
            'CSDVersion')
        log.debug("windows_sp=%s" % sp)
        return sp

    def get_windows_build(self):
        b = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion',
            'CurrentBuildNumber')
        log.debug("windows_build=%s" % b)
        return b

    def get_processor_name(self):
        name = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            'HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0',
            'ProcessorNameString')
        log.debug("processor_name=%s" % name)
        return name

    def get_bootloader(self, windows_version):
        mapping = {
            'vista': 'vista', '2008': 'vista',
            'nt': 'xp', 'xp': 'xp', '2000': 'xp', '2003': 'xp',
            '95': '98', '98': '98',
        }
        bootloader = mapping.get(windows_version)
        log.debug("bootloader=%s" % bootloader)
        return bootloader

    def get_gmt(self):
        gmt = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            'SYSTEM\\CurrentControlSet\\Control\\TimeZoneInformation',
            'Bias')
        if gmt:
            gmt = -gmt / 60
        if not gmt or gmt > 12 or gmt < -12:
            gmt = 0
        log.debug("gmt=%s" % gmt)
        return gmt

    def get_country(self):
        from .mappings import name2country, gmt2country
        icountry = registry.get_value(
            'HKEY_CURRENT_USER', 'Control Panel\\International', 'iCountry')
        country = None
        if icountry is not None:
            try:
                icountry = int(icountry)
            except Exception:
                pass
            country = win32_mappings.icountry2country.get(icountry)
            if not country:
                scountry = registry.get_value(
                    'HKEY_CURRENT_USER', 'Control Panel\\International', 'sCountry')
                country = name2country.get(scountry) if scountry else None
            if not country:
                country = gmt2country.get(self.info.gmt)
        country = country or "US"
        log.debug("country=%s" % country)
        return country

    def get_timezone(self):
        from .mappings import country2tz, country_gmt2tz, gmt2tz
        timezone = country2tz.get(self.info.country)
        timezone = country_gmt2tz.get((self.info.country, self.info.gmt), timezone)
        if not timezone:
            timezone = gmt2tz.get(self.info.gmt)
        if not timezone:
            timezone = "America/New_York"
        log.debug("timezone=%s" % timezone)
        return timezone

    def get_windows_username(self):
        username = os.getenv('username') or ''
        if isinstance(username, bytes):
            username = username.decode('ascii', 'ignore')
        log.debug("windows_username=%s" % username)
        return username

    def get_windows_user_full_name(self):
        name = os.getenv('username') or ''
        if isinstance(name, bytes):
            name = name.decode('ascii', 'ignore')
        log.debug("user_full_name=%s" % name)
        return name

    def get_windows_user_dir(self):
        homedrive = os.getenv('homedrive')
        homepath  = os.getenv('homepath')
        user_directory = ""
        if homedrive and homepath:
            user_directory = join_path(homedrive, homepath)
            if isinstance(user_directory, bytes):
                user_directory = user_directory.decode('ascii', 'ignore')
        log.debug("user_directory=%s" % user_directory)
        return user_directory

    def get_windows_language_code(self):
        lang = (self.info.language or "")[:2]
        code = win32_mappings.language2n.get(lang) or 1033  # fallback English
        log.debug("windows_language_code=%s" % code)
        return code

    def get_windows_language(self):
        lang = win32_mappings.n2fulllanguage.get(self.info.windows_language_code, "English")
        log.debug("windows_language=%s" % lang)
        return lang

    def get_keyboard_layout(self):
        win_keyboard_id = ctypes.windll.user32.GetKeyboardLayout(0)
        locale_id  = win_keyboard_id & 0x0000FFFF
        variant_id = win_keyboard_id & 0xFFFFFFFF
        layout  = win32_mappings.keymaps.get(locale_id) or self.info.country.lower()
        variant = win32_mappings.hkl2variant.get(variant_id) or ""
        log.debug("keyboard_layout=%s variant=%s" % (layout, variant))
        return layout, variant

    def get_system_drive(self):
        drive = Drive(os.getenv('SystemDrive'))
        log.debug("system_drive=%s" % drive)
        return drive

    def get_drives(self):
        drives = []
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive = Drive(letter)
            if drive.type:
                log.debug("drive=%s" % str(drive))
                drives.append(drive)
        return drives

    def get_registry_key(self):
        key = ('Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\'
               + self.info.application_name.capitalize())
        log.debug("registry_key=%s" % key)
        return key

    def get_uninstaller_path(self):
        path = registry.get_value(
            'HKEY_LOCAL_MACHINE', self.info.registry_key, 'UninstallString')
        log.debug("uninstaller_path=%s" % path)
        return path

    def get_previous_target_dir(self):
        d = registry.get_value(
            'HKEY_LOCAL_MACHINE', self.info.registry_key, 'InstallationDir')
        log.debug("previous_target_dir=%s" % d)
        return d

    def get_previous_distro_name(self):
        name = registry.get_value(
            'HKEY_LOCAL_MACHINE', self.info.registry_key, 'DisplayName')
        log.debug("previous_distro_name=%s" % name)
        return name

    def get_startup_folder(self):
        folder = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            'SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
            '\\Explorer\\Shell Folders',
            'Common Startup')
        log.debug("startup_folder=%s" % folder)
        return folder

    def _get_source_id(self):
        """
        Returns the Subiquity source ID corresponding to the selected distro.
        First tries to read casper/install-sources.yaml from the ISO,
        then uses SOURCE_ID_MAP as a fallback.
        """
        distro_obj  = getattr(self.info, 'distro', None)
        distro_name = (
            getattr(distro_obj, 'name', None)
            or getattr(self.info, 'distro_name', None)
            or 'ubuntu'
        ).lower().replace(' ', '-')

        # Try reading from the ISO if available
        iso_path = getattr(self.info, 'iso_path', None)
        if iso_path and os.path.isfile(iso_path):
            try:
                sources_file = self.extract_file_from_iso(
                    iso_path,
                    'casper/install-sources.yaml',
                    output_dir=self.info.temp_dir,
                    overwrite=True,
                )
                if sources_file and os.path.isfile(sources_file):
                    import yaml
                    with open(sources_file, 'r', encoding='utf-8') as f:
                        sources = yaml.safe_load(f)
                    if sources:
                        for entry in sources:
                            if entry.get('default'):
                                source_id = entry.get('id', '')
                                log.debug("source_id from ISO: %s" % source_id)
                                return source_id
            except Exception as e:
                log.debug("Could not read install-sources.yaml: %s" % e)

        # Fallback to static map
        source_id = SOURCE_ID_MAP.get(distro_name, 'ubuntu-desktop')
        log.debug("source_id from map: %s (distro=%s)" % (source_id, distro_name))
        return source_id

    def get_installer_type(self):
        distro_obj  = getattr(self.info, 'distro', None)
        distro_name = (
            getattr(distro_obj, 'name', None)
            or getattr(self.info, 'distro_name', None)
            or 'ubuntu'
        ).lower().replace(' ', '-')
        installer = DISTRO2INSTALLER.get(distro_name, "calamares")
        log.debug("installer_type=%s" % installer)
        return installer

    def check_secure_boot(self):
        val = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            r'SYSTEM\CurrentControlSet\Control\SecureBoot\State',
            'UEFISecureBootEnabled')
        enabled = bool(val)
        if enabled:
            build = int(self.info.windows_build or 0)
            if build >= 22000:
                log.warning(
                    "Secure Boot is reported to be running — the BCD entry "
                    "for GRUB will not be signed. The user will have to "
                    "disable Secure Boot manually."
                )
        return enabled

    def check_EFI(self):
        if self.info.bootloader != 'vista':
            return False
        try:
            bcdedit = self._find_bcdedit()
            result  = run_command([bcdedit, '/enum'])
        except Exception as err:
            log.warning("EFI detection skipped: %s" % err)
            return False
        result = self._decode(result).lower()
        efi = "bootmgfw.efi" in result or "winload.efi" in result
        log.debug("EFI boot=%s" % efi)
        return efi

    # ── Task lists ────────────────────────────────────────────────────────────

    def get_installation_tasklist(self):
        log.debug("get_installation_tasklist distro=%s" % self.info.distro)
        log.debug("get_installation_tasklist target_drive=%s" % self.info.target_drive)
        self.cache_iso_path()
        log.debug("get_installation_tasklist iso_path=%s" % self.iso_path)
        dimage = self.info.distro.diskimage
        if dimage and not self.iso_path and not self.info.target_drive.is_fat():
            tasks = [
                Task(self.select_target_dir,        description=_("Selecting the target directory")),
                Task(self.create_dir_structure,      description=_("Creating the directories")),
                Task(self.create_uninstaller,        description=_("Creating the uninstaller")),
                Task(self.create_preseed_diskimage,  description=_("Creating a preseed file")),
                Task(self.get_diskimage,             description=_("Retrieving installation files")),
                Task(self.extract_diskimage,         description=_("Extracting")),
                Task(self.choose_disk_sizes,         description=_("Choosing disk sizes")),
                Task(self.expand_diskimage,          description=_("Expanding")),
                Task(self.create_swap_diskimage,     description=_("Creating virtual memory")),
                Task(self.modify_bootloader,         description=_("Adding a new bootloader entry")),
                Task(self.diskimage_bootloader,      description=_("Installing the bootloader")),
            ]
        else:
            tasks = [
                Task(self.select_target_dir,          description=_("Selecting the target directory")),
                Task(self.create_dir_structure,       description=_("Creating the installation directories")),
                Task(self.uncompress_target_dir,      description=_("Uncompressing files")),
                Task(self.create_uninstaller,         description=_("Creating the uninstaller")),
                Task(self.copy_installation_files,    description=_("Copying installation files")),
                Task(self.get_iso,                    description=_("Retrieving installation files")),
                Task(self.extract_kernel,             description=_("Extracting the kernel")),
                Task(self.choose_disk_sizes,          description=_("Choosing disk sizes")),
                Task(self.create_preseed,             description=_("Creating a preseed file")),
                Task(self.modify_bootloader,          description=_("Adding a new bootloader entry")),
                Task(self.modify_grub_configuration,  description=_("Setting up installation boot menu")),
                Task(self.create_virtual_disks,       description=_("Creating the virtual disks")),
                Task(self.uncompress_files,           description=_("Uncompressing files")),
            ]
        description = _("Installing %(distro)s-%(version)s") % dict(
            distro=self.info.distro.name, version=self.info.version)
        return ThreadedTaskList(description=description, tasks=tasks)

    def get_uninstallation_tasklist(self):
        tasks = [
            Task(self.undo_bootloader,    _("Remove bootloader entry")),
            Task(self.remove_target_dir,  _("Remove target dir")),
            Task(self.remove_registry_key,_("Remove registry key")),
        ]
        return ThreadedTaskList(
            description=_("Uninstalling %s") % self.info.previous_distro_name,
            tasks=tasks,
        )

    def get_cdboot_tasklist(self):
        tasks = [
            Task(self.select_target_dir,        description=_("Selecting the target directory")),
            Task(self.create_dir_structure,      description=_("Creating the installation directories")),
            Task(self.uncompress_target_dir,     description=_("Uncompressing files")),
            Task(self.create_uninstaller,        description=_("Creating the uninstaller")),
            Task(self.create_preseed_cdboot,     description=_("Creating a preseed file")),
            Task(self.modify_bootloader,         description=_("Adding a new bootloader entry")),
        ]
        return ThreadedTaskList(
            description=_("Configuring CD boot helper"),
            tasks=tasks,
        )

    # ── Directory structure ──────────────────────────────────────────────

    def select_target_dir(self, associated_task=None):
        target_dir = join_path(
            self.info.target_drive.path, self.info.distro.installation_dir)
        target_dir = target_dir.replace(' ', '_').replace('__', '_')
        if os.path.exists(target_dir):
            raise Exception(
                "Cannot install into %s.\n"
                "There is another file or directory with this name.\n"
                "Please remove it before continuing." % target_dir
            )
        self.info.target_dir = target_dir
        log.info("Installing into %s" % target_dir)
        self.info.icon = join_path(
            self.info.target_dir, self.info.distro.name + '.ico')

    def create_dir_structure(self, associated_task=None):
        self.info.disks_dir       = join_path(self.info.target_dir, "disks")
        self.info.install_dir     = join_path(self.info.target_dir, "install")
        self.info.install_boot_dir = join_path(self.info.install_dir, "boot")
        self.info.disks_boot_dir  = join_path(self.info.disks_dir, "boot")
        dirs = [
            self.info.target_dir,
            self.info.disks_dir,
            self.info.install_dir,
            self.info.install_boot_dir,
            self.info.disks_boot_dir,
            join_path(self.info.disks_boot_dir, "grub"),
            join_path(self.info.install_boot_dir, "grub"),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    def create_diskimage_dirs(self, associated_task=None):
        self.info.disks_dir      = join_path(self.info.target_dir, "disks")
        self.info.disks_boot_dir = join_path(self.info.disks_dir, "boot")
        dirs = [
            self.info.target_dir,
            self.info.disks_dir,
            self.info.disks_boot_dir,
            join_path(self.info.disks_boot_dir, "grub"),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    # ── Distributions ───────────────────────────────────────────────────────────────

    def get_distros(self):
        isolist_path = join_path(self.info.data_dir, 'isolist.ini')
        log.debug("isolist_path=%s exists=%s" % (
            isolist_path, os.path.isfile(isolist_path)))
        return self.parse_isolist(isolist_path)

    def parse_isolist(self, isolist_path):
        log.debug("Parsing isolist=%s" % isolist_path)
        isolist = configparser.ConfigParser()
        isolist.read(isolist_path)
        distros = []
        for distro in isolist.sections():
            log.debug("  Adding distro %s" % distro)
            kargs = dict(isolist.items(distro))
            kargs.setdefault('md5sums', '')
            kargs.setdefault('iso_url', '')
            kargs.setdefault('releases_url', '')
            distros.append(Distro(backend=self, **kargs))

        def compfunc(x, y):
            if x.ordering == y.ordering: return 0
            return 1 if x.ordering > y.ordering else -1

        distros.sort(key=functools.cmp_to_key(compfunc))
        return distros

    def show_info(self):
        log.debug("Showing info")
        os.startfile(self.info.cd_distro.website)

    # ── ISO / CD ──────────────────────────────────────────────────────────────

    def find_iso(self, associated_task=None):
        log.debug("Searching for local ISO")
        for path in self.get_iso_search_paths():
            for iso in glob.glob(join_path(path, '*.iso')):
                if self.info.distro.is_valid_iso(iso, self.info.check_arch):
                    return iso

    def find_any_iso(self):
        if self.info.iso_path and os.path.exists(self.info.iso_path):
            log.debug("Checking pre-specified ISO %s" % self.info.iso_path)
            for distro in self.info.distros:
                if distro.is_valid_iso(self.info.iso_path, self.info.check_arch):
                    return self.info.iso_path, distro
        log.debug("Searching for local ISOs")
        for path in self.get_iso_search_paths():
            for iso in glob.glob(join_path(path, '*.iso')):
                for distro in self.info.distros:
                    if distro.is_valid_iso(iso, self.info.check_arch):
                        return iso, distro
        return None, None

    def cache_iso_path(self):
        self.iso_path = None
        if self.info.distro is None:
            return
        if (self.info.iso_distro
                and self.info.distro == self.info.iso_distro
                and self.info.iso_path
                and os.path.isfile(self.info.iso_path)):
            self.iso_path = self.info.iso_path
        else:
            self.iso_path = self.find_iso()

    def check_cd(self, cd_path, associated_task=None):
        if associated_task:
            associated_task.description = _("Checking CD %s") % cd_path
        if not self.info.distro.is_valid_cd(cd_path, check_arch=False):
            return False
        self.set_distro_from_arch(cd_path)
        if self.info.skip_md5_check:
            return True
        md5sums_file = join_path(cd_path, self.info.distro.md5sums)
        for rel_path in self.info.distro.get_required_files():
            if rel_path == self.info.distro.md5sums:
                continue
            check_file = (associated_task.add_subtask(self.check_file)
                          if associated_task else self.check_file)
            if not check_file(join_path(cd_path, rel_path), rel_path, md5sums_file):
                return False
        return True

    def check_iso(self, iso_path, associated_task=None):
        log.debug("Checking %s" % iso_path)
        if not self.info.distro.is_valid_iso(iso_path, check_arch=False):
            return False
        self.set_distro_from_arch(iso_path)
        if self.info.skip_md5_check:
            return True
        base_url = getattr(self.info.distro, 'releases_url', None)
        if not base_url:
            base_url = "https://releases.ubuntu.com/%s" % self.info.distro.version
        return verify_iso(
            base_url=base_url,
            iso_path=iso_path,
            install_dir=self.info.install_dir,
            proxy=self.info.web_proxy,
            skip_gpg=self.info.skip_md5_check,
            associated_task=associated_task,
        )

    def check_file(self, file_path, relpath, md5sums, associated_task=None):
        log.debug("  checking %s" % file_path)
        if associated_task:
            associated_task.description = _("Checking %s") % file_path
        relpath  = relpath.replace("\\", "/")
        md5line  = find_line_in_file(md5sums, "./%s" % relpath, endswith=True)
        if not md5line:
            raise Exception("Cannot find md5 in %s for %s" % (md5sums, relpath))
        reference_hash = md5line.split()[0]
        hash_len = len(reference_hash) * 4
        if hash_len == 160:
            hash_name = 'sha1'
        elif hash_len in (224, 256, 384, 512):
            hash_name = 'sha' + str(hash_len)
        else:
            hash_name = 'md5'
        hash_file = get_file_hash(file_path, hash_name, associated_task)
        log.debug("  %s %s = %s %s %s" % (
            file_path, hash_name, hash_file,
            "==" if hash_file == reference_hash else "!=",
            reference_hash,
        ))
        return hash_file == reference_hash

    def set_distro_from_arch(self, cd_or_iso_path):
        if self.info.check_arch:
            return
        arch = self.info.distro.get_info(cd_or_iso_path)[3]
        if self.info.distro.arch == arch:
            return
        name = self.info.distro.name
        log.debug("Using distro %s %s instead of %s %s" % (
            name, arch, name, self.info.distro.arch))
        distro = self.info.distros_dict.get((name.lower(), arch))
        self.info.distro = distro

    def select_mirrors(self, urls):
        urls = list(urls)
        for url in urls:
            url.score = url.preference + (50 if self.info.country == url.location else 0)
        urls.sort(key=lambda u: -u.score)
        return urls

    def get_iso_search_paths(self):
        paths  = [os.path.dirname(self.info.original_exe)]
        paths += [drive.path for drive in self.info.drives]
        paths += [os.environ.get('Desktop')]
        return [abspath(p) for p in paths if p and os.path.isdir(p)]

    def get_cd_search_paths(self):
        return [drive.path for drive in self.info.drives]

    def get_usb_search_paths(self):
        return [drive.path for drive in self.info.drives]

    def get_iso_file_names(self, iso_path):
        iso_path = abspath(iso_path)
        if iso_path in self.cache:
            return self.cache[iso_path] or []
        self.cache[iso_path] = None
        try:
            import pycdlib
            iso = pycdlib.pycdlib.PyCdlib()
            iso.open(iso_path)

            use_joliet = iso.has_joliet()
            use_rr = iso.has_rock_ridge()
            try:
                names = []
                if use_joliet:
                    for dirname, dirlist, filelist in iso.walk(joliet_path='/'):
                        for filename in filelist:
                            clean = filename.split(';')[0].rstrip('.')
                            path  = (dirname.rstrip('/') + '/' + clean).lstrip('/')
                            names.append(os.path.normpath(path) if path else clean)
                if use_rr:
                    for dirname, dirlist, filelist in iso.walk(rr_path='/'):
                        for filename in filelist:
                            clean = filename.split(';')[0].rstrip('.')
                            path  = (dirname.rstrip('/') + '/' + clean).lstrip('/')
                            names.append(os.path.normpath(path) if path else clean)
                names.sort()
                self.cache[iso_path] = names
                return names
            finally:
                iso.close()
        except Exception as err:
            log.exception(err)
            return []

    def extract_file_from_iso(self, iso_path, file_path,
                            output_dir=None, overwrite=False):
        log.debug("  extracting %s from %s" % (file_path, iso_path))
        if not iso_path or not os.path.exists(iso_path):
            raise Exception("Invalid path %s" % iso_path)
        if not output_dir:
            output_dir = tempfile.gettempdir()
        output_file = join_path(output_dir, os.path.basename(file_path))
        if os.path.exists(output_file):
            if overwrite:
                os.unlink(output_file)
            else:
                raise Exception("Cannot overwrite %s" % output_file)
        try:
            import pycdlib
            iso = pycdlib.pycdlib.PyCdlib()
            iso.open(iso_path)
            use_joliet = iso.has_joliet()
            use_rr = iso.has_rock_ridge()
            try:
                iso_file_path = '/' + file_path.replace('\\', '/').lstrip('/')
                os.makedirs(output_dir, exist_ok=True)
                tried = []
                for candidate in [iso_file_path, iso_file_path.upper(), iso_file_path.lower()]:
                    try:
                        with open(output_file, 'wb') as f:
                            if use_joliet:
                                iso.get_file_from_iso_fp(f, joliet_path=iso_file_path)
                            if use_rr:
                                iso.get_file_from_iso_fp(f, rr_path=iso_file_path)
                            else:
                                iso.get_file_from_iso_fp(f, iso_path=iso_file_path.upper())
                            iso_file_path = candidate
                            return output_file if isfile(output_file) else None
                    except Exception as e:
                        tried.append((candidate, str(e)))
                
            finally:
                iso.close()
        except Exception as err:
            log.exception(err)
            return None

    # ── Downloads ───────────────────────────────────────────────────────

    def download_iso(self, associated_task=None):
        log.debug("No ISO found locally, downloading")
        file_url  = self.info.distro.iso_url
        iso_name  = os.path.basename(file_url)
        save_as   = os.path.join(self.info.install_dir, iso_name)

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
            if not verify(iso_path):
                os.unlink(iso_path)
                raise Exception("ISO verification failed")
        else:
            if not self.check_iso(iso_path):
                os.unlink(iso_path)
                raise Exception("ISO verification failed")

        self.info.iso_path = iso_path
        return True

    def download_diskimage(self, diskimage, associated_task=None):
        proxy   = self.info.web_proxy
        save_as = join_path(self.info.disks_dir, diskimage.split('/')[-1])
        if os.path.isfile(save_as):
            os.unlink(save_as)
        try:
            use_torrent = diskimage.endswith('.torrent') and self._has_aria2c()
            if use_torrent:
                dl = (associated_task.add_subtask(btdownloader.download, is_required=False)
                      if associated_task else btdownloader.download)
                self.dimage_path = dl(
                    diskimage, save_as,
                    root_dir=self.info.root_dir, web_proxy=proxy,
                )
            else:
                dl = (associated_task.add_subtask(http_download, is_required=False)
                      if associated_task else http_download)
                self.dimage_path = dl(diskimage, save_as, web_proxy=proxy)
            return self.dimage_path is not None
        except Exception:
            log.exception("Cannot download disk image %s" % diskimage)
            return False

    def get_prespecified_diskimage(self, associated_task):
        if self.info.dimage_path and os.path.exists(self.info.dimage_path):
            self.dimage_path = self.info.dimage_path
            log.debug("Trying pre-specified disk image %s" % self.info.dimage_path)
            is_valid = (associated_task.add_subtask(
                self.info.distro.is_valid_dimage,
                description=_("Validating %s") % self.info.dimage_path)
                if associated_task else self.info.distro.is_valid_dimage)
            if is_valid(self.info.dimage_path, self.info.check_arch):
                self.info.cd_path = None
                return True

    def get_prespecified_iso(self, associated_task):
        if self.info.iso_path and os.path.exists(self.info.iso_path):
            log.debug("Trying pre-specified ISO %s" % self.info.iso_path)
            is_valid = (associated_task.add_subtask(
                self.info.distro.is_valid_iso,
                description=_("Validating %s") % self.info.iso_path)
                if associated_task else self.info.distro.is_valid_iso)
            if is_valid(self.info.iso_path, self.info.check_arch):
                self.info.cd_path = None
            return self.copy_iso(self.info.iso_path, associated_task)

    def get_diskimage(self, associated_task=None):
        if self.get_prespecified_diskimage(associated_task):
            if associated_task:
                return associated_task.finish()

        dimage  = self.info.distro.diskimage
        dimage2 = self.info.distro.diskimage2

        # Torrent requested but aria2c unavailable — try diskimage2 directly
        if dimage and dimage.endswith('.torrent') and not self._has_aria2c():
            log.info("Torrent demandé mais aria2c absent — essai diskimage2")
            if dimage2 and self.download_diskimage(dimage2, associated_task):
                if associated_task:
                    return associated_task.finish()

        if self.download_diskimage(dimage, associated_task):
            if associated_task:
                return associated_task.finish()

        if dimage2 and self.download_diskimage(dimage2, associated_task):
            if associated_task:
                return associated_task.finish()

        raise Exception("Could not retrieve the required disk image files")

    def get_iso(self, associated_task=None):
        if (self.get_prespecified_iso(associated_task)
                or self.use_cd(associated_task)
                or self.use_iso(associated_task)
                or self.download_iso(associated_task)):
            if associated_task:
                return associated_task.finish()
        raise Exception("Could not retrieve the required installation files")

    def copy_diskimage(self, dimage_path, associated_task):
        if not dimage_path:
            return
        dimage_name = self.info.distro.diskimage.split('/')[-1]
        dest = os.path.join(self.info.disks_dir, dimage_name)
        copy_dimage = (associated_task.add_subtask(
            copy_file, description=_("Copying installation files"))
            if associated_task else copy_file)
        log.debug("Copying %s > %s" % (dimage_path, dest))
        copy_dimage(dimage_path, dest)
        return True

    def copy_iso(self, iso_path, associated_task):
        if not iso_path:
            return
        dest      = join_path(self.info.install_dir, iso_path.split('/')[-1])
        check_iso = (associated_task.add_subtask(
            self.check_iso, description=_("Checking installation files"))
            if associated_task else self.check_iso)
        if check_iso(iso_path):
            if os.path.dirname(iso_path) == dest:
                mover = (associated_task.add_subtask(
                    shutil.move, description=_("Copying installation files"))
                    if associated_task else shutil.move)
                log.debug("Moving %s > %s" % (iso_path, dest))
                mover(iso_path, dest)
            else:
                copier = (associated_task.add_subtask(
                    copy_file, description=_("Copying installation files"))
                    if associated_task else copy_file)
                log.debug("Copying %s > %s" % (iso_path, dest))
                copier(iso_path, dest)
            self.info.cd_path  = None
            self.info.iso_path = dest
            return True

    def use_cd(self, associated_task):
        if self.iso_path:
            extract_iso = (associated_task.add_subtask(
                copy_file,
                description=_("Extracting files from %s") % self.iso_path)
                if associated_task else copy_file)
            self.info.iso_path = join_path(
                self.info.install_dir, self.iso_path.split('/')[-1])
            try:
                extract_iso(self.info.iso_path, self.info.iso_path)
            except Exception as err:
                log.error(err)
                self.info.cd_path  = None
                self.info.iso_path = None
                return False
            self.info.cd_path = self.iso_path
            check_iso = (associated_task.add_subtask(
                self.check_iso, description=_("Checking installation files"))
                if associated_task else self.check_iso)
            if not check_iso(self.info.iso_path):
                subversion = self.info.cd_distro.get_info(self.info.cd_path)[2]
                if subversion.lower() in ("alpha", "beta", "release candidate"):
                    log.error("CD check failed, but ignoring because CD is %s" % subversion)
                else:
                    self.info.cd_path  = None
                    self.info.iso_path = None
                    return False
            return True

    def use_iso(self, associated_task):
        if self.iso_path:
            log.debug("Trying to use ISO %s" % self.iso_path)
            return self.copy_iso(self.iso_path, associated_task)

    # ── Kernel ────────────────────────────────────────────────────────────────

    def extract_kernel(self, associated_task=None):
        bootdir = self.info.install_boot_dir
        if self.info.iso_path:
            log.debug("Extracting files from ISO %s" % self.info.iso_path)
            if self.info.distro.md5sums:
                self.extract_file_from_iso(
                    self.info.iso_path, self.info.distro.md5sums, output_dir=bootdir)
            self.extract_file_from_iso(
                self.info.iso_path, self.info.distro.kernel, output_dir=bootdir)
            self.extract_file_from_iso(
                self.info.iso_path, self.info.distro.initrd, output_dir=bootdir)
        else:
            raise Exception("Could not retrieve the required installation files")

        self.info.kernel = join_path(bootdir, os.path.basename(self.info.distro.kernel))
        self.info.initrd = join_path(bootdir, os.path.basename(self.info.distro.initrd))
        if self.info.distro.md5sums:
            md5sums          = join_path(bootdir, os.path.basename(self.info.distro.md5sums))
            for file_path, rel_path in [
                (self.info.kernel, self.info.distro.kernel),
                (self.info.initrd, self.info.distro.initrd),
            ]:
                if not self.check_file(file_path, rel_path, md5sums):
                    raise Exception("File %s is corrupted" % file_path)
        else:
            log.debug("No md5sums provided for this distro, skipping integrity check")

    # ── Preseed / Autoinstall ─────────────────────────────────────────────────

    def create_preseed(self, associated_task=None):
        installer = getattr(self.info.distro, 'installer', 'subiquity')
        if installer == 'subiquity':
            self._create_autoinstall()
        else:
            pass  # Calamares does not use a preseed file

    def _create_autoinstall(self):
        source   = join_path(self.info.data_dir, 'autoinstall.yaml')
        template = read_file(source)
        if isinstance(template, (bytes, bytearray, memoryview)):
            template = bytes(template).decode('utf-8', errors='ignore')
        if not template:
            raise Exception("Could not read autoinstall template: %s" % source)
        hashed_password = hash_password(self.info.password)
        dic = dict(
            locale           = self.info.locale,
            keyboard_layout  = self.info.keyboard_layout,
            keyboard_variant = self.info.keyboard_variant,
            timezone         = self.info.timezone,
            realname         = self.info.user_full_name,
            hostname         = self.info.distro.name.lower().replace(' ', '-'),
            username         = self.info.username,
            hashed_password  = hashed_password,
            source_id        = 'ubuntu-desktop',
        )
        content = template
        for k, v in dic.items():
            content = content.replace('$(%s)' % k, v if v is not None else '')
        autoinstall_dir = join_path(self.info.custominstall, 'autoinstall')
        os.makedirs(autoinstall_dir, exist_ok=True)
        write_file(join_path(autoinstall_dir, 'autoinstall.yaml'), content)

    def create_subiquity_autoinstall(self):
        """
        Generates an autoinstall.yaml file for Subiquity-based installers based on the
        user's configuration. The file is placed in the "autoinstall" subdirectory of the installation directory.
        """
        import yaml
        base = self.info.custom_install or self.info.install_dir
        autoinstall_dir = join_path(base, "autoinstall")
        os.makedirs(autoinstall_dir, exist_ok=True)

        ptable = "gpt" if getattr(self.info, 'efi', False) else "msdos"

        config = {
            "autoinstall": {
                "version": 1,
                "locale": self.info.locale or "en_US.UTF-8",
                "keyboard": {
                    "layout":  self.info.keyboard_layout  or "us",
                    "variant": self.info.keyboard_variant or "",
                },
                "timezone": self.info.timezone or "Etc/UTC",
                "identity": {
                    "realname": self.info.user_full_name or self.info.host_username,
                    "hostname": self.info.hostname or "ubuntu",
                    "username": self.info.host_username or self.info.username,
                    "password": hash_password(self.info.password),
                },
                "ssh": {"install-server": False},
                "source": {
                    "id":             self._get_source_id(),
                    "search_drivers": True,
                },
                "storage": {
                    "layout": {
                        "name":   "direct",
                        "ptable": ptable,
                    }
                },
                "apt": {
                    "geoip": True,
                    "mirror-selection": {
                        "primary": [
                            "country-mirror",
                            {
                                "uri":   "http://archive.ubuntu.com/ubuntu",
                                "arches": ["amd64"],
                            },
                        ]
                    },
                },
                "updates":  "security",
                "shutdown": "reboot",
            }
        }

        write_file(
            join_path(autoinstall_dir, "autoinstall.yaml"),
            yaml.dump(config, default_flow_style=False, allow_unicode=True),
        )
        # Empty meta-data required by cloud-init
        write_file(join_path(autoinstall_dir, "meta-data"), "")

    def create_calamares_autoinstall(self):
        log.debug("Distro uses Calamares installer, no autoinstall file will be created.")

    def create_preseed_diskimage(self, associated_task=None):
        source   = join_path(self.info.data_dir, 'preseed.disk')
        template = read_file(source)
        if template is None:
            raise Exception("Could not read preseed template: %s" % source)
        if isinstance(template, (bytes, bytearray, memoryview)):
            template = bytes(template).decode('utf-8', errors='ignore')
        password = md5_password(self.info.password)
        dic = dict(
            timezone         = self.info.timezone,
            password         = password,
            keyboard_variant = self.info.keyboard_variant,
            keyboard_layout  = self.info.keyboard_layout,
            locale           = self.info.locale,
            user_full_name   = self.info.user_full_name,
            username         = self.info.username,
        )
        for k, v in dic.items():
            template = template.replace("$(%s)" % k, v if v is not None else "")
        write_file(join_path(self.info.install_dir, "preseed.cfg"), template)
        copy_file(
            join_path(self.info.data_dir, "wubildr-disk.cfg"),
            join_path(self.info.install_dir, "wubildr-disk.cfg"),
        )

    def create_preseed_cdboot(self, associated_task=None):
        source = join_path(self.info.data_dir, 'preseed.cdboot')
        custom_install_dir = self.info.custominstall or self.info.install_dir
        if not custom_install_dir:
            raise Exception("Could not determine target directory for preseed.cdboot")
        copy_file(source, join_path(custom_install_dir, "preseed.cfg"))

    def modify_grub_configuration(self, associated_task=None):
        installer     = getattr(self.info.distro, 'installer', 'subiquity')
        template_file = join_path(
            self.info.data_dir, 'grub.install.%s.cfg' % installer)
        template = read_file(template_file)
        if template is None:
            raise Exception("Could not read grub template: %s" % template_file)
        if isinstance(template, (bytes, bytearray, memoryview)):
            template = bytes(template).decode('utf-8', errors='ignore')
        isopath   = unix_path(self.info.iso_path) if self.info.iso_path else ""
        dic = dict(
            custom_installation_dir        = unix_path(self.info.custominstall) if self.info.custominstall else "",
            iso_path                       = isopath,
            keyboard_variant               = self.info.keyboard_variant,
            keyboard_layout                = self.info.keyboard_layout,
            locale                         = self.info.locale,
            accessibility                  = self.info.accessibility,
            kernel                         = unix_path(self.info.kernel),
            initrd                         = unix_path(self.info.initrd),
            rootflags                      = "rootflags=sync",
            title1                         = "Completing the Ubuntu installation.",
            title2                         = "For more installation boot options, press `ESC' now...",
            normal_mode_title              = "Normal mode",
            pae_mode_title                 = "PAE mode",
            safe_graphic_mode_title        = "Safe graphic mode",
            intel_graphics_workarounds_title = "Intel graphics workarounds",
            nvidia_graphics_workarounds_title = "Nvidia graphics workarounds",
            acpi_workarounds_title         = "ACPI workarounds",
            verbose_mode_title             = "Verbose mode",
            demo_mode_title                = "Demo mode",
        )
        content = template
        for k, v in dic.items():
            content = content.replace("$(%s)" % k, v if v is not None else "")
        write_file(
            join_path(self.info.install_boot_dir, "grub", "grub.cfg"),
            content,
        )

    # ── Windows installation ──────────────────────────────────────────────────

    def create_uninstaller(self, associated_task=None):
        uninstaller_name = ('uninstall-%s.exe' % self.info.application_name
                            ).replace(' ', '_').replace('__', '_')
        uninstaller_path = join_path(self.info.target_dir, uninstaller_name)
        if os.path.splitext(self.info.original_exe)[-1] == '.exe':
            log.debug("Copying uninstaller %s -> %s" % (
                self.info.original_exe, uninstaller_path))
            shutil.copyfile(self.info.original_exe, uninstaller_path)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'UninstallString',   uninstaller_path)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'InstallationDir',   self.info.target_dir)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'DisplayName',       self.info.distro.name)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'DisplayIcon',       self.info.icon)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'DisplayVersion',    self.info.version_revision)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'Publisher',         self.info.distro.name)
        if self.info.distro.website:
            registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'URLInfoAbout', self.info.distro.website)
        if self.info.distro.support:
            registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'HelpLink',     self.info.distro.support)

    def copy_installation_files(self, associated_task=None):
        self.info.custom_install = join_path(self.info.install_dir, 'custom-installation')
        src  = join_path(self.info.data_dir, 'custom-installation')
        dest = self.info.custom_install
        log.debug("Copying %s -> %s" % (src, dest))
        shutil.copytree(src, dest)

        if self.info.installer_type == "subiquity":
            self.create_subiquity_autoinstall()
        else:
            self.create_calamares_autoinstall()

        src = join_path(self.info.root_dir, 'winboot')
        if isdir(src):
            dest = join_path(self.info.target_dir, 'winboot')
            log.debug("Copying %s -> %s" % (src, dest))
            shutil.copytree(src, dest)

        dest = join_path(self.info.custom_install, 'hooks', 'failure-command.sh')
        msg  = _("The installation failed. Logs have been saved in: %s."
                 "\n\nNote that in verbose mode, the logs may include the password."
                 "\n\nThe system will now reboot.")
        msg  = msg % join_path(self.info.install_dir, 'installation-logs.zip')
        msg  = 'msg="%s"' % msg
        msg  = str(msg.encode('utf8'))
        replace_line_in_file(dest, 'msg=', msg)

        src  = join_path(self.info.image_dir, self.info.distro.name + '.ico')
        dest = self.info.icon
        log.debug("Copying %s -> %s" % (src, dest))
        shutil.copyfile(src, dest)

    def uncompress_target_dir(self, associated_task=None):
        if self.info.target_drive.is_fat():
            return
        try:
            run_command(['compact', self.info.target_dir, '/U', '/A', '/F'])
            run_command(['compact', join_path(self.info.target_dir, '*.*'), '/U', '/A', '/F'])
        except Exception as err:
            log.error(err)

    def uncompress_files(self, associated_task=None):
        if self.info.target_drive.is_fat():
            return
        for cmd in [
            ['compact', join_path(self.info.install_boot_dir), '/U', '/A', '/F'],
            ['compact', join_path(self.info.install_boot_dir, '*.*'), '/U', '/A', '/F'],
        ]:
            try:
                run_command(cmd)
            except Exception as err:
                log.error(err)

    def create_virtual_disks(self, associated_task=None):
        for disk in ("root", "home", "usr", "swap"):
            path    = join_path(self.info.disks_dir, disk + ".disk")
            size_mb = int(getattr(self.info, disk + "_size_mb"))
            if size_mb:
                create_virtual_disk(path, size_mb)

    def choose_disk_sizes(self, associated_task=None):
        total_size_mb = self.info.installation_size_mb
        home_size_mb  = 0
        usr_size_mb   = 0
        swap_size_mb  = 256
        root_size_mb  = total_size_mb - swap_size_mb
        if self.info.target_drive.is_fat():
            if root_size_mb > 8500:
                home_size_mb = root_size_mb - 8000
                usr_size_mb  = 4000
                root_size_mb = 4000
            elif root_size_mb > 5500:
                usr_size_mb  = 4000
                root_size_mb -= 4000
            elif root_size_mb > 4000:
                usr_size_mb  = root_size_mb - 1500
                root_size_mb = 1500
            if home_size_mb > 4000:
                home_size_mb = 4000
        self.info.home_size_mb = home_size_mb
        self.info.usr_size_mb  = usr_size_mb
        self.info.swap_size_mb = swap_size_mb
        self.info.root_size_mb = root_size_mb
        log.debug("total=%s root=%s swap=%s home=%s usr=%s" % (
            total_size_mb, root_size_mb, swap_size_mb, home_size_mb, usr_size_mb))

    def remove_existing_binary(self):
        try:
            startup_folder = self.get_startup_folder()
            if startup_folder is None:
                return
            binary = os.path.join(startup_folder, 'wubi.exe')
        except Exception:
            return
        if os.path.exists(binary):
            try:
                MOVEFILE_DELAY_UNTIL_REBOOT = 4
                ctypes.windll.kernel32.MoveFileExW(
                    binary, None, MOVEFILE_DELAY_UNTIL_REBOOT)
            except (OSError, IOError):
                log.exception("Couldn't remove Wubi from startup")

    # ── Virtual disks / disk image ─────────────────────────────────────────

    def extract_diskimage(self, associated_task=None):
        xz = self.dimage_path
        assert isinstance(xz, str), "dimage_path must be a string path"
        
        target_dir = self.info.disks_dir
        os.makedirs(target_dir, exist_ok=True)
        
        try:
            with py7zr.SevenZipFile(xz, mode='r') as archive:
                archive.extractall(path=target_dir)
            log.debug("Successfully extracted diskimage from %s to %s" % (xz, target_dir))
        except Exception as e:
            log.error("Diskimage extraction failed: %s" % e)
            raise Exception("Failed to extract diskimage: %s" % e)
        
        # Clean up the compressed file if it wasn't pre-specified
        if not self.info.dimage_path:
            try:
                os.remove(xz)
                log.debug("Removed temporary diskimage file: %s" % xz)
            except Exception as e:
                log.warning("Could not remove diskimage file: %s" % e)

    def expand_diskimage(self, associated_task=None):
        root     = join_path(self.info.disks_dir, 'root.disk')
        resize2fs = join_path(self.info.bin_dir, 'resize2fs.exe')
        if not associated_task:
            run_command([resize2fs, '-f', root, '%dM' % self.info.root_size_mb])
            return
        resize_cmd = [resize2fs, '-p', '-f', root, '%dM' % self.info.root_size_mb]
        associated_task.size = 100
        associated_task.set_progress(0)
        proc = spawn_command(resize_cmd)
        assert proc.stdout is not None and proc.stderr is not None
        threading.Thread(target=proc.stdout.read, daemon=True).start()
        buf       = ''
        cancelled = False
        stderr = proc.stderr
        for raw in iter(lambda: stderr.read(1), b''):
            ch = raw.decode('utf-8', 'replace')
            if ch in ('\r', '\n'):
                m = re.search(r'(\d+(?:\.\d+)?)\s*%', buf)
                if m:
                    pct = min(float(m.group(1)), 99.0)
                    if associated_task.set_progress(pct):
                        cancelled = True
                        proc.terminate()
                        break
                buf = ''
            else:
                buf += ch
        proc.wait()
        if cancelled:
            return
        if proc.returncode != 0:
            raise Exception("resize2fs failed with code: %d" % proc.returncode)
        associated_task.set_progress(100)

    def create_swap_diskimage(self, associated_task=None):
        path      = join_path(self.info.disks_dir, 'swap.disk')
        swap_size = '%d' % (self.info.swap_size_mb * 1024 * 1024)
        run_command(['fsutil', 'file', 'createnew', path, swap_size])

    def diskimage_bootloader(self, associated_task=None):
        src  = join_path(self.info.root_dir, 'winboot')
        dest = join_path(self.info.target_dir, 'winboot')
        if isdir(src):
            log.debug("Copying %s -> %s" % (src, dest))
            shutil.copytree(src, dest)
        src = join_path(self.info.disks_dir, 'wubildr')
        shutil.copyfile(src, join_path(dest, 'wubildr'))
        for drive in self.info.drives:
            if drive.type not in ('removable', 'hd'):
                continue
            try:
                shutil.copyfile(src, join_path(drive.path, 'wubildr'))
            except Exception:
                pass
        os.unlink(src)

    # ── Boot loader ────────────────────────────────────────────────────────────

    def modify_bootloader(self, associated_task):
        if self.info.bootloader == "vista":
            for drive in self.info.drives:
                if drive.type in ('removable', 'hd'):
                    def make_bcd_task(d):
                        def _task(associated_task=None):
                            self.modify_bcd(d, associated_task)
                        _task.__name__ = "modify_bcd_%s" % d.path
                        return _task
                    associated_task.add_subtask(make_bcd_task(drive))
        elif self.info.bootloader == "xp":
            for drive in self.info.drives:
                if drive.type in ('removable', 'hd'):
                    def make_bootini_task(d):
                        def _task(associated_task=None):
                            self.modify_bootini(d, associated_task)
                        return _task
                    associated_task.add_subtask(make_bootini_task(drive))
        elif self.info.bootloader == "98":
            for drive in self.info.drives:
                def make_configsys_task(d):
                    def _task(associated_task=None):
                        self.modify_configsys(d, associated_task)
                    return _task
                associated_task.add_subtask(make_configsys_task(drive))

    def undo_bootloader(self, associated_task):
        winboot_files = ['wubildr', 'wubildr.mbr', 'wubildr.exe']
        self.undo_bcd(associated_task)
        for drive in self.info.drives:
            if drive.type not in ('removable', 'hd'):
                continue
            self.undo_bootini(drive, associated_task)
            self.undo_configsys(drive, associated_task)
            for f in winboot_files:
                f = join_path(drive.path, f)
                if os.path.isfile(f):
                    os.unlink(f)
        if self.info.efi:
            log.debug("Undo EFI boot")
            self.undo_EFI_folder(associated_task)
            try:
                run_command(['powercfg', '/h', 'on'])
            except Exception as err:
                log.error(err)

    def modify_bcd(self, drive, associated_task=None):
        bcdedit = self._find_bcdedit()
        boot_drive_out = run_command([bcdedit, '/enum', '{bootmgr}'])
        boot_drive = self._decode(boot_drive_out)
        if self.contains_partition(boot_drive):
            idx = boot_drive.find('partition=')
            if idx != -1:
                boot_drive = boot_drive[idx + len('partition='):]
        log.debug("modify_bcd %s" % drive)
        system_drive = (os.getenv('SystemDrive') or '').upper()
        if (drive is self.info.system_drive
                or drive.path == "C:"
                or (system_drive and drive.path == system_drive)
                or drive.path == self.info.target_drive.path):
            for fname in ('wubildr', 'wubildr.mbr'):
                shutil.copyfile(
                    join_path(self.info.root_dir, 'winboot', fname),
                    join_path(drive.path, fname),
                )
        if registry.get_value(
                'HKEY_LOCAL_MACHINE', self.info.registry_key, 'VistaBootDrive'):
            log.debug("BCD has already been modified")
            return
        if self.info.efi:
            log.debug("EFI boot")
            efi_path = self.modify_EFI_folder(associated_task, bcdedit)
            try:
                run_command(['powercfg', '/h', 'off'])
            except Exception as err:
                log.error(err)
            id_out  = run_command([bcdedit, '/copy', '{bootmgr}', '/d', self.info.distro.name])
            id_text = self._decode(id_out)
            match   = re.search(r'\{[^\}]+\}', id_text)
            if not match:
                raise Exception("Could not extract BCD entry ID: %s" % id_text)
            bcd_id = match.group(0)
            run_command([bcdedit, '/set', bcd_id, 'path', efi_path])
            for cmd in [
                [bcdedit, '/set', '{fwbootmgr}', 'displayorder', bcd_id, '/addlast'],
                [bcdedit, '/set', '{fwbootmgr}', 'timeout', '10'],
                [bcdedit, '/set', '{fwbootmgr}', 'bootsequence', bcd_id],
            ]:
                try:
                    run_command(cmd)
                except Exception as err:
                    log.error(err)
            registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key,
                                'VistaBootDrive', bcd_id)
            return

        id_out  = run_command([bcdedit, '/create', '/d', self.info.distro.name,
                               '/application', 'bootsector'])
        id_text = self._decode(id_out)
        match   = re.search(r'\{[^\}]+\}', id_text)
        if not match:
            raise Exception("Could not extract BCD entry ID: %s" % id_text)
        bcd_id   = match.group(0)
        mbr_path = os.path.normpath(
            join_path(self.info.target_dir, 'winboot', 'wubildr.mbr'))[2:]
        run_command([bcdedit, '/set', bcd_id, 'device',
                     'partition=%s' % self.info.target_drive.path])
        run_command([bcdedit, '/set', bcd_id, 'path', mbr_path])
        run_command([bcdedit, '/displayorder', bcd_id, '/addlast'])
        run_command([bcdedit, '/timeout', '10'])
        run_command([bcdedit, '/bootsequence', bcd_id])
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key,
                            'VistaBootDrive', bcd_id)

    def undo_bcd(self, associated_task=None):
        try:
            bcdedit = self._find_bcdedit()
        except FileNotFoundError:
            log.error("Cannot find bcdedit — BCD entry not removed")
            return
        bcd_id = registry.get_value(
            'HKEY_LOCAL_MACHINE', self.info.registry_key, 'VistaBootDrive')
        if not bcd_id:
            log.debug("Could not find bcd id")
            return
        log.debug("Removing bcd entry %s" % bcd_id)
        try:
            run_command([bcdedit, '/delete', bcd_id, '/f'])
            registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key,
                                'VistaBootDrive', "")
        except Exception as err:
            log.error(err)

    def modify_EFI_folder(self, associated_task, bcdedit):
        boot_drive_out = run_command([bcdedit, '/enum', '{bootmgr}'])
        boot_drive     = self._decode(boot_drive_out)
        if 'partition=' in boot_drive:
            boot_drive = boot_drive.split('partition=', 1)[1]
        boot_drive = boot_drive.strip().splitlines()[0].split()[0] if boot_drive.strip() else ''
        log.debug("EFI boot partition %s" % boot_drive)

        mounted_temporarily = False
        if len(boot_drive) >= 2 and boot_drive[1] == ':':
            efi_drive = boot_drive[:2]
        else:
            free_letter = next(
                (c for c in 'HIJKLMNOPQRSTUVWXYZ' if not Drive(c).type), None)
            if not free_letter:
                raise Exception("No free drive letter available for EFI mount")
            efi_drive           = free_letter + ':'
            mounted_temporarily = True
            log.debug("Temporary EFI drive %s" % efi_drive)

        if mounted_temporarily:
            run_command(['mountvol', efi_drive, '/s'])
        try:
            src         = join_path(self.info.root_dir, 'winboot', 'EFI')
            target_name = self.info.target_dir[3:].replace(' ', '_').replace('__', '_')
            dest_root   = join_path(efi_drive, 'EFI', target_name)
            os.makedirs(dest_root, exist_ok=True)
            dest = join_path(dest_root, 'wubildr')
            if os.path.exists(dest):
                shutil.rmtree(dest)
            log.debug("Copying EFI folder %s -> %s" % (src, dest))
            shutil.copytree(src, dest)
            grub_cfg   = join_path(dest, 'grub.cfg')
            efi_prefix = ('/' + dest[3:].replace('\\', '/') + '/').replace('//', '/')
            write_file(grub_cfg,
                       'set prefix="%s"\nconfigfile "${prefix}wubildr.cfg"\n' % efi_prefix)
            if self.get_efi_arch(associated_task, efi_drive) == "ia32":
                efi_path = os.path.normpath(join_path(dest, 'grubia32.efi'))[2:]
            else:
                efi_path = os.path.normpath(join_path(dest, 'shimx64.efi'))[2:]
            return efi_path
        finally:
            if mounted_temporarily:
                run_command(['mountvol', efi_drive, '/d'])

    def get_efi_arch(self, associated_task, efidrive):
        mapping = {
            "amd64": "x64", "x86_64": "x64",
            "x86": "ia32", "i386": "ia32", "i686": "ia32",
            "arm64": "arm64", "aarch64": "arm64",
        }
        efi_arch = mapping.get(self.info.arch.lower(), "x64")
        log.debug("efi_arch=%s (from arch=%s)" % (efi_arch, self.info.arch))
        return efi_arch

    def undo_EFI_folder(self, associated_task=None):
        free_letter = next(
            (c for c in 'HIJKLMNOPQRSTUVWXYZ' if not Drive(c).type), None)
        if not free_letter:
            log.error("No free drive letter available for EFI mount")
            return
        efi_drive = free_letter + ':'
        log.debug("Temporary EFI drive %s" % efi_drive)
        try:
            run_command(['mountvol', efi_drive, '/s'])
            target_name = self.info.previous_target_dir[3:].replace(' ', '_').replace('__', '_')
            dest = join_path(efi_drive, 'EFI', target_name, 'wubildr')
            if os.path.exists(dest):
                log.debug("Removing EFI folder %s" % dest)
                shutil.rmtree(dest)
            run_command(['mountvol', efi_drive, '/d'])
        except Exception as err:
            log.error(err)

    def modify_bootini(self, drive, associated_task=None):
        log.debug("modify_bootini %s" % drive.path)
        bootini = join_path(drive.path, 'boot.ini')
        if not os.path.isfile(bootini):
            log.debug("Could not find boot.ini %s" % bootini)
            return
        for fname in ('wubildr', 'wubildr.mbr'):
            shutil.copyfile(
                join_path(self.info.root_dir, 'winboot', fname),
                join_path(drive.path, fname),
            )
        run_command(['attrib', '-R', '-S', '-H', bootini])
        boot_line = 'C:\\wubildr.mbr = "%s"' % self.info.distro.name
        old_line  = boot_line[:boot_line.index("=")].strip().lower()
        content   = read_file(bootini) or ''
        if isinstance(content, (bytes, bytearray, memoryview)):
            content = bytes(content).decode('utf-8', errors='ignore')
        if content and content[-1] != '\n':
            content += '\n'
        lines      = content.split('\n')
        is_section = False
        for i, line in enumerate(lines):
            if line.strip().lower() == "[operating systems]":
                is_section = True
            elif line.strip().startswith("["):
                is_section = False
            if is_section and line.strip().lower().startswith(old_line):
                lines[i] = boot_line
                break
            if is_section and not line.strip():
                lines.insert(i, boot_line)
                break
        write_file(bootini, '\n'.join(lines))
        run_command(['attrib', '+R', '+S', '+H', bootini])

    def undo_bootini(self, drive, associated_task=None):
        log.debug("undo_bootini %s" % drive.path)
        bootini = join_path(drive.path, 'boot.ini')
        if not os.path.isfile(bootini):
            return
        run_command(['attrib', '-R', '-S', '-H', bootini])
        remove_line_in_file(bootini, 'c:\\wubildr.mbr', ignore_case=True)
        run_command(['attrib', '+R', '+S', '+H', bootini])

    def modify_configsys(self, drive, associated_task=None):
        log.debug("modify_configsys %s" % drive.path)
        configsys = join_path(drive.path, 'config.sys')
        if not os.path.isfile(configsys):
            return
        shutil.copyfile(
            join_path(self.info.root_dir, 'winboot', 'wubildr.exe'),
            join_path(drive.path, 'wubildr.exe'),
        )
        run_command(['attrib', '-R', '-S', '-H', configsys])
        config = read_file(configsys) or ''
        if isinstance(config, (bytes, bytearray, memoryview)):
            config = bytes(config).decode('utf-8', errors='ignore')
        if 'REM WUBI MENU START\n' in config:
            log.debug("Configsys has already been modified")
            return
        config += (
            '\nREM WUBI MENU START\n'
            '[menu]\n'
            'menucolor=15,0\n'
            'menuitem=windows,Windows\n'
            'menuitem=wubildr,%s\n'
            'menudefault=windows,10\n'
            '[wubildr]\n'
            'device=wubildr.exe\n'
            '[windows]\n'
            'REM WUBI MENU END\n'
        ) % self.info.distro.name
        write_file(configsys, config)
        run_command(['attrib', '+R', '+S', '+H', configsys])

    def undo_configsys(self, drive, associated_task=None):
        log.debug("undo_configsys %s" % drive.path)
        configsys = join_path(drive.path, 'config.sys')
        if not os.path.isfile(configsys):
            return
        run_command(['attrib', '-R', '-S', '-H', configsys])
        config = read_file(configsys) or ''
        if isinstance(config, (bytes, bytearray, memoryview)):
            config = bytes(config).decode('utf-8', errors='ignore')
        s = config.find('REM WUBI MENU START\n')
        e = config.find('REM WUBI MENU END\n')
        if s >= 0 and e >= 0:
            e += len('REM WUBI MENU END')
            config = config[:s] + config[e:]
        write_file(configsys, config)
        run_command(['attrib', '+R', '+S', '+H', configsys])

    # ── Uninstallation ───────────────────────────────────────────────────────

    def remove_target_dir(self, associated_task=None):
        if not os.path.isdir(self.info.previous_target_dir):
            log.debug("Cannot find %s" % self.info.previous_target_dir)
            return
        log.debug("Deleting %s" % self.info.previous_target_dir)
        try:
            rm_tree(self.info.previous_target_dir)
        except OSError as e:
            if e.errno == 22:
                log.exception("Unable to remove target directory.")
                cmd = spawn_command(['chkdsk', '/F'])
                cmd.communicate(input=('Y%s' % os.linesep).encode())
                raise errors.WubiCorruptionError

    def remove_registry_key(self, associated_task=None):
        registry.delete_key('HKEY_LOCAL_MACHINE', self.info.registry_key)

    def run_previous_uninstaller(self):
        if (not self.info.previous_uninstaller_path
                or not os.path.isfile(self.info.previous_uninstaller_path)):
            return
        uninstaller = self.info.previous_uninstaller_path
        command     = [uninstaller, "--uninstall"]
        if self.info.non_interactive:
            command.append("--noninteractive")
        if get_file_hash(self.info.original_exe) == get_file_hash(
                self.info.previous_uninstaller_path):
            log.info("This is the uninstaller running")
        else:
            log.info("Launching previous uninstaller %s" % uninstaller)
            process = subprocess.Popen(command)
            process.wait()
            self.application.quit()
            return True

    # ── Miscellaneous ──────────────────────────────────────────────────────────────────

    def reboot(self, associated_task=None):
        run_command(['shutdown', '-r', '-t', '00'])

    def eject_cd(self, associated_task=None):
        eject_cd(self.info.cd_path)

    def fetch_installer_info(self):
        pass