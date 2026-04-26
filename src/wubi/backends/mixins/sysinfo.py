from __future__ import annotations

import os
import sys
import ctypes
import locale
import logging
import platform

from ..utils import registry
from ..data  import mappings as win32_mappings
from ..utils.drive   import Drive
from ..utils.memory  import get_total_memory_mb
from ..data.mappings import lang_country2linux_locale
from ..utils.utils   import join_path, run_command
log = logging.getLogger("Backend.sysinfo")


class SysInfoMixin:

    # ── High-level fetchers ───────────────────────────────────────

    def fetch_basic_info(self) -> None:
        """Minimal info required by the task dispatcher."""
        log.debug("Fetching basic info...")
        self.info.uninstall_before_install = False
        self.info.original_exe  = self.get_original_exe()
        self.info.platform      = self.get_platform()
        self.info.os_name       = self.get_osname()
        if not self.info.language:
            self.info.language, self.info.encoding = self.get_language_encoding()
        self.info.environment_variables = os.environ
        self.info.arch = self.get_arch()
        if self.info.force_i386:
            self.info.arch = "i386"
        self.info.check_arch = False
        self.info.distro = None

        self.fetch_host_info()

        self.info.distros = self.get_distros()
        self.info.distros_dict = {
            (d.name.lower(), d.arch): d for d in self.info.distros
        }

        self.info.previous_uninstaller_path = self.get_uninstaller_path()
        self.info.previous_target_dir       = self.get_previous_target_dir()
        self.info.previous_distro_name      = self.get_previous_distro_name()
        self.info.keyboard_layout, self.info.keyboard_variant = self.get_keyboard_layout()
        if not self.info.locale:
            self.info.locale = self.get_locale(self.info.language)
        self.info.total_memory_mb = self.get_total_memory_mb()
        self.info.iso_path, self.info.iso_distro = self.find_any_iso()

    def fetch_host_info(self) -> None:
        log.debug("Fetching host info...")
        self.info.registry_key          = self.get_registry_key()
        self.info.windows_version       = self.get_windows_version()
        self.info.windows_version2      = self.get_windows_version2()
        self.info.windows_sp            = self.get_windows_sp()
        self.info.windows_build         = self.get_windows_build()
        self.info.gmt                   = self.get_gmt()
        self.info.country               = self.get_country()
        self.info.timezone              = self.get_timezone()
        self.info.host_username         = self.get_windows_username()
        self.info.user_full_name        = self.get_windows_user_full_name()
        self.info.user_directory        = self.get_windows_user_dir()
        self.info.windows_language_code = self.get_windows_language_code()
        self.info.windows_language      = self.get_windows_language()
        self.info.processor_name        = self.get_processor_name()
        self.info.bootloader            = self.get_bootloader(self.info.windows_version)
        self.info.system_drive          = self.get_system_drive()
        self.info.drives                = self.get_drives()
        self.info.drives_dict           = {d.path[:2].lower(): d for d in self.info.drives}
        self.info.efi                   = self.check_EFI()
        self.info.source_id             = self._get_source_id()
        self.info.installer_type        = self.get_installer_type()
        self.info.previous_target_dir   = self.get_previous_target_dir()
        self.info.previous_distro_name  = self.get_previous_distro_name()
        self.info.hostname              = os.environ.get('COMPUTERNAME', 'wubi-host').lower()
        self.info.username              = self.info.host_username
        self._is_already_configured     = False

        # Recompute paths from the real exe location (skip in PyInstaller bundles)
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

    # ── Individual getters ────────────────────────────────────────

    def get_original_exe(self) -> str:
        exe = self.info.original_exe or os.path.abspath(sys.argv[0])
        log.debug(f"original_exe={exe}")
        return exe

    def get_platform(self) -> str:
        p = sys.platform
        log.debug(f"platform={p}")
        return p

    def get_osname(self) -> str:
        n = os.name
        log.debug(f"osname={n}")
        return n

    def get_language_encoding(self) -> tuple[str, str]:
        language, encoding = locale.getdefaultlocale()
        language = language or "en_US"
        encoding = encoding or "utf-8"
        log.debug(f"language={language} encoding={encoding}")
        return language, encoding

    def get_arch(self) -> str:
        arch = platform.machine().lower()
        log.debug(f"arch={arch}")
        return arch

    def get_locale(self, language_country: str, fallback: str = "en_US") -> str:
        _locale = (
            lang_country2linux_locale.get(language_country)
            or lang_country2linux_locale.get(fallback)
        )
        log.debug(f"locale={_locale}")
        return _locale

    def get_total_memory_mb(self) -> int:
        mb = get_total_memory_mb()
        log.debug(f"total_memory_mb={mb}")
        return mb

    def get_windows_version(self) -> str | None:
        major, minor, _build, p, _txt = sys.getwindowsversion()
        version = None
        if p == 0:
            version = 'win32'
        elif p == 1 and major == 4:
            version = {0: '95', 10: '98', 90: 'me'}.get(minor)
        elif p == 2:
            if major == 4:
                version = 'nt'
            elif major == 5:
                version = {0: '2000', 1: 'xp', 2: '2003'}.get(minor)
            elif major >= 6:
                version = 'vista'
        log.debug(f"windows_version={version}")
        return version

    def get_windows_version2(self) -> str | None:
        v = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            r'SOFTWARE\Microsoft\Windows NT\CurrentVersion',
            'ProductName')
        log.debug(f"windows_version2={v}")
        return v

    def get_windows_sp(self) -> str | None:
        sp = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            r'SOFTWARE\Microsoft\Windows NT\CurrentVersion',
            'CSDVersion')
        log.debug(f"windows_sp={sp}")
        return sp

    def get_windows_build(self) -> str | None:
        b = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            r'SOFTWARE\Microsoft\Windows NT\CurrentVersion',
            'CurrentBuildNumber')
        log.debug(f"windows_build={b}")
        return b

    def get_processor_name(self) -> str | None:
        name = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            r'HARDWARE\DESCRIPTION\System\CentralProcessor\0',
            'ProcessorNameString')
        log.debug(f"processor_name={name}")
        return name

    def get_bootloader(self, windows_version: str | None) -> str | None:
        mapping = {
            'vista': 'vista', '2008': 'vista',
            'nt': 'xp', 'xp': 'xp', '2000': 'xp', '2003': 'xp',
            '95': '98', '98': '98',
        }
        bl = mapping.get(windows_version) if windows_version is not None else None
        log.debug(f"bootloader={bl}")
        return bl

    def get_gmt(self) -> float:
        gmt = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            r'SYSTEM\CurrentControlSet\Control\TimeZoneInformation',
            'Bias')
        if gmt:
            gmt = -gmt / 60
        if not gmt or gmt > 12 or gmt < -12:
            gmt = 0
        log.debug(f"gmt={gmt}")
        return gmt

    def get_country(self) -> int | None:
        icountry = registry.get_value(
            'HKEY_CURRENT_USER', r'Control Panel\International', 'iCountry')
        if icountry is not None:
            try:
                icountry = int(icountry)
            except (ValueError, TypeError):
                log.debug("Cannot convert country code to int: %s", icountry)
        return icountry

    def get_timezone(self) -> str:
        from ..data.mappings import country2tz, country_gmt2tz, gmt2tz
        tz = country2tz.get(self.info.country)
        tz = country_gmt2tz.get((self.info.country, self.info.gmt), tz)
        if not tz:
            tz = gmt2tz.get(self.info.gmt)
        if not tz or "partition" not in str(tz).lower():
            tz = "America/New_York"
        log.debug(f"timezone={tz}")
        return tz

    def get_windows_username(self) -> str:
        return self._decode(os.getenv('username') or '')

    def get_windows_user_full_name(self) -> str:
        return self._decode(os.getenv('fullname') or '')

    def get_windows_user_dir(self) -> str:
        homedrive = os.getenv('homedrive')
        homepath  = os.getenv('homepath')
        d = ""
        if homedrive and homepath:
            d = join_path(homedrive, homepath)
            if isinstance(d, bytes):
                d = d.decode('ascii', 'ignore')
        log.debug(f"user_directory={d}")
        return d

    def get_windows_language_code(self) -> int:
        lang = (self.info.language or "")[:2]
        code = win32_mappings.language2n.get(lang) or 1033
        log.debug(f"windows_language_code={code}")
        return code

    def get_windows_language(self) -> str:
        lang = win32_mappings.n2fulllanguage.get(
            self.info.windows_language_code, "English")
        log.debug(f"windows_language={lang}")
        return lang

    def get_keyboard_layout(self) -> tuple[str, str]:
        hkl        = ctypes.windll.user32.GetKeyboardLayout(0)
        locale_id  = hkl & 0x0000FFFF
        variant_id = hkl & 0xFFFFFFFF
        layout  = win32_mappings.keymaps.get(locale_id) or str(self.info.country).lower()
        variant = win32_mappings.hkl2variant.get(variant_id) or ""
        log.debug(f"keyboard_layout={layout} variant={variant}")
        return layout, variant

    def get_system_drive(self) -> Drive:
        drive = Drive(os.getenv('SystemDrive'))
        log.debug(f"system_drive={drive}")
        return drive

    def get_drives(self) -> list[Drive]:
        drives = []
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive = Drive(letter)
            if drive.type:
                log.debug(f"drive={drive}")
                drives.append(drive)
        return drives

    def get_registry_key(self) -> str:
        key = (r'Software\Microsoft\Windows\CurrentVersion\Uninstall\\'
               + self.info.application_name.capitalize())
        log.debug(f"registry_key={key}")
        return key

    def get_uninstaller_path(self) -> str | None:
        path = registry.get_value(
            'HKEY_LOCAL_MACHINE', self.info.registry_key, 'UninstallString')
        if path:
            if path.startswith('"'):
                path = path.split('"')[1]
            else:
                path = path.split(' --')[0].strip()
        log.debug(f"uninstaller_path={path}")
        return path

    def get_previous_target_dir(self) -> str | None:
        d = registry.get_value(
            'HKEY_LOCAL_MACHINE', self.info.registry_key, 'InstallationDir')
        log.debug(f"previous_target_dir={d}")
        return d

    def get_previous_distro_name(self) -> str | None:
        name = registry.get_value(
            'HKEY_LOCAL_MACHINE', self.info.registry_key, 'DisplayName')
        log.debug(f"previous_distro_name={name}")
        return name

    def get_startup_folder(self) -> str | None:
        folder = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders',
            'Common Startup')
        log.debug(f"startup_folder={folder}")
        return folder

    def _get_source_id(self) -> str:
        from ..backend import SOURCE_ID_MAP
        distro_obj  = getattr(self.info, 'distro', None)
        distro_name = (
            getattr(distro_obj, 'name', None)
            or getattr(self.info, 'distro_name', None)
            or 'ubuntu'
        ).lower().replace(' ', '-')

        iso_path = getattr(self.info, 'iso_path', None)
        if iso_path and os.path.isfile(iso_path):
            try:
                sources_file = self.extract_file_from_iso(
                    iso_path, 'casper/install-sources.yaml',
                    output_dir=self.info.temp_dir, overwrite=True,
                )
                if sources_file and os.path.isfile(sources_file):
                    import yaml
                    with open(sources_file, encoding='utf-8') as f:
                        sources = yaml.safe_load(f)
                    if sources:
                        for entry in sources:
                            if entry.get('default'):
                                sid = entry.get('id', '')
                                log.debug(f"source_id from ISO: {sid}")
                                return sid
            except Exception as e:
                log.debug(f"Could not read install-sources.yaml: {e}")

        sid = SOURCE_ID_MAP.get(distro_name, 'ubuntu-desktop')
        log.debug(f"source_id from map: {sid} (distro={distro_name})")
        return sid

    def get_installer_type(self) -> str:
        from ..backend import DISTRO2INSTALLER
        distro_obj  = getattr(self.info, 'distro', None)
        distro_name = (
            getattr(distro_obj, 'name', None)
            or getattr(self.info, 'distro_name', None)
            or 'ubuntu'
        ).lower().replace(' ', '-')
        installer = DISTRO2INSTALLER.get(distro_name, "calamares")
        log.debug(f"installer_type={installer}")
        return installer

    def remove_existing_binary(self) -> None:
        try:
            startup_folder = self.get_startup_folder()
            if startup_folder is None:
                return
            binary = os.path.join(startup_folder, 'wubi.exe')
        except Exception:
            return
        if os.path.exists(binary):
            try:
                import ctypes
                MOVEFILE_DELAY_UNTIL_REBOOT = 4
                ctypes.windll.kernel32.MoveFileExW(
                    binary, None, MOVEFILE_DELAY_UNTIL_REBOOT)
            except (OSError, IOError):
                log.exception("Couldn't schedule wubi.exe for removal")