from __future__ import annotations
from typing import Any

class Info:

    # ── Paths ──────────────────────────────────────────────────────
    root_dir:                   str | None
    temp_dir:                   str | None
    data_dir:                   str | None
    bin_dir:                    str | None
    log_file:                   str | None
    image_dir:                  str | None
    translations_dir:           str | None
    locale_dir:                 str | None
    trusted_keys:               str | None
    install_dir:                str | None
    install_boot_dir:           str | None
    original_exe:               str | None
    target_dir:                 str | None
    disks_dir:                  str | None
    disks_boot_dir:             str | None
    custom_install:             str | None
    application_icon:           str | None
    icon:                       str | None
    kernel:                     str | None
    initrd:                     str | None

    # ── ISO / CD ───────────────────────────────────────────────────
    iso_path:                   str | None
    cd_path:                    str | None
    disk_image_path:            str | None
    iso_distro:                 Any
    cd_distro:                  Any

    # ── Distro / drives ────────────────────────────────────────────
    distro:                     Any
    distro_name:                str | None
    distros:                    list
    distros_dict:               dict
    drives:                     list
    drives_dict:                dict
    system_drive:               Any
    target_drive:               Any
    installation_size_mb:       int | None
    iso_md5_hashes:             dict

    # ── Disk sizes ─────────────────────────────────────────────────
    root_size_mb:               int | None
    swap_size_mb:               int | None
    home_size_mb:               int | None
    usr_size_mb:                int | None

    # ── Windows host info ──────────────────────────────────────────
    registry_key:               str | None
    windows_version:            str | None
    windows_version2:           str | None
    windows_sp:                 str | None
    windows_build:              str | None
    windows_language:           str | None
    windows_language_code:      int | None
    gmt:                        float
    country:                    int | None
    timezone:                   str | None
    processor_name:             str | None
    bootloader:                 str | None
    efi:                        bool
    source_id:                  str | None
    installer_type:             str | None
    hostname:                   str | None

    # ── User / session ─────────────────────────────────────────────
    username:                   str | None
    password:                   str | None
    host_username:              str | None
    user_full_name:             str | None
    user_directory:             str | None
    language:                   str | None
    locale:                     str | None
    encoding:                   str | None
    keyboard_layout:            str | None
    keyboard_variant:           str | None
    accessibility:              str
    total_memory_mb:            int

    # ── App metadata ───────────────────────────────────────────────
    application_name:           str | None
    version:                    str | None
    revision:                   str | None
    version_revision:           str | None
    full_application_name:      str | None
    full_version:               str | None
    web_proxy:                  str | None
    verbosity:                  str | None

    # ── Flags ──────────────────────────────────────────────────────
    force_exit:                 bool
    quitting:                   bool
    debug:                      bool
    test:                       bool
    no_bittorrent:              bool
    use_frontend:               str | None
    skip_md5_check:             bool
    skip_size_check:            bool
    skip_memory_check:          bool
    uninstall_before_install:   bool
    non_interactive:            bool
    force_i386:                 bool
    force_wubi:                 bool
    check_arch:                 bool

    # ── Runtime ────────────────────────────────────────────────────
    arch:                       str | None
    platform:                   str | None
    os_name:                    str | None
    environment_variables:      dict
    previous_target_dir:        str | None
    previous_uninstaller_path:  str | None
    previous_distro_name:       str | None
    run_task:                   str | None

    def __init__(
        self,
        root_dir:              str | None = None,
        application_name:      str | None = None,
        version:               str | None = None,
        revision:              str | None = None,
        version_revision:      str | None = None,
        full_application_name: str | None = None,
        full_version:          str | None = None,
    ) -> None:
        # ── Seed fields (passed at construction time) ──────────────
        self.root_dir              = root_dir
        self.application_name      = application_name
        self.version               = version
        self.revision              = revision
        self.version_revision      = version_revision
        self.full_application_name = full_application_name
        self.full_version          = full_version

        # ── Paths ──────────────────────────────────────────────────
        self.temp_dir          = None
        self.data_dir          = None
        self.bin_dir           = None
        self.image_dir         = None
        self.translations_dir  = None
        self.locale_dir        = None
        self.trusted_keys      = None
        self.application_icon  = None
        self.icon              = None
        self.log_file          = None
        self.original_exe      = None
        self.target_dir        = None
        self.install_dir       = None
        self.install_boot_dir  = None
        self.disks_dir         = None
        self.disks_boot_dir    = None
        self.custom_install    = None
        self.kernel            = None
        self.initrd            = None

        # ── ISO / CD ───────────────────────────────────────────────
        self.cd_path           = None
        self.iso_path          = None
        self.disk_image_path   = None
        self.iso_distro        = None
        self.cd_distro         = None

        # ── Distro / drives ────────────────────────────────────────
        self.distro            = None
        self.distro_name       = None
        self.distros           = []
        self.distros_dict      = {}
        self.drives            = []
        self.drives_dict       = {}
        self.system_drive      = None
        self.target_drive      = None
        self.installation_size_mb = None
        self.iso_md5_hashes    = {}

        # ── Disk sizes ─────────────────────────────────────────────
        self.root_size_mb      = None
        self.swap_size_mb      = None
        self.home_size_mb      = None
        self.usr_size_mb       = None

        # ── Windows host info ──────────────────────────────────────
        self.registry_key          = None
        self.windows_version       = None
        self.windows_version2      = None
        self.windows_sp            = None
        self.windows_build         = None
        self.windows_language      = None
        self.windows_language_code = None
        self.gmt                   = 0.0
        self.country               = None
        self.timezone              = None
        self.processor_name        = None
        self.bootloader            = None
        self.efi                   = False
        self.source_id             = None
        self.installer_type        = None
        self.hostname              = None

        # ── User / session ─────────────────────────────────────────
        self.username          = None
        self.password          = None
        self.host_username     = None
        self.user_full_name    = None
        self.user_directory    = None
        self.language          = None
        self.locale            = None
        self.encoding          = None
        self.keyboard_layout   = None
        self.keyboard_variant  = None
        self.accessibility     = ""
        self.total_memory_mb   = 0

        # ── Flags ──────────────────────────────────────────────────
        self.force_exit              = False
        self.quitting                = False
        self.debug                   = False
        self.test                    = False
        self.no_bittorrent           = False
        self.use_frontend            = None
        self.skip_md5_check          = False
        self.skip_size_check         = False
        self.skip_memory_check       = False
        self.uninstall_before_install = False
        self.non_interactive         = False
        self.force_i386              = False
        self.force_wubi              = False
        self.check_arch              = False

        # ── Runtime ────────────────────────────────────────────────
        self.arch                       = None
        self.platform                   = None
        self.os_name                    = None
        self.environment_variables      = {}
        self.previous_target_dir        = None
        self.previous_uninstaller_path  = None
        self.previous_distro_name       = None
        self.run_task                   = None
        self.verbosity                  = None
        self.web_proxy                  = None

    # ── Helpers ────────────────────────────────────────────────────

    def update(self, mapping: dict) -> None:
        for key, value in mapping.items():
            setattr(self, key, value)

    def __str__(self) -> str:
        return f"Info({self.__dict__})"