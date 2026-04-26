from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Info:

    # ── Paths ──────────────────────────────────────────────────────
    root_dir:                   str | None = None
    temp_dir:                   str | None = None
    data_dir:                   str | None = None
    bin_dir:                    str | None = None
    image_dir:                  str | None = None
    translations_dir:           str | None = None
    log_file:                   str | None = None
    install_dir:                str | None = None
    install_boot_dir:           str | None = None
    original_exe:               str | None = None
    target_dir:                 str | None = None
    disks_dir:                  str | None = None
    disks_boot_dir:             str | None = None
    disk_image_path:            str | None = None
    iso_path:                   str | None = None
    cd_path:                    str | None = None
    custom_install:             str | None = None
    trusted_keys:               str | None = None
    application_icon:           str | None = None

    # ── App identity ───────────────────────────────────────────────
    application_name:           str | None = None
    version:                    str | None = None
    revision:                   str | None = None
    version_revision:           str | None = None
    full_application_name:      str | None = None
    full_version:               str | None = None

    # ── Runtime flags ──────────────────────────────────────────────
    force_exit:                 bool = False
    quitting:                   bool = False
    debug:                      bool = False
    test:                       bool = False
    efi:                        bool = False
    force_i386:                 bool = False
    force_wubi:                 bool = False
    check_arch:                 bool = False
    no_bittorrent:              bool = False
    skip_md5_check:             bool = False
    skip_size_check:            bool = False
    skip_memory_check:          bool = False
    uninstall_before_install:   bool = False
    non_interactive:            bool = False

    # ── Task / flow ────────────────────────────────────────────────
    run_task:                   str | None = None
    use_frontend:               str | None = None
    verbosity:                  str | None = None
    web_proxy:                  str | None = None

    # ── Distros ────────────────────────────────────────────────────
    distro:                     Any | None = None   # Distro object
    distro_name:                str | None = None
    iso_distro:                 Any | None = None
    cd_distro:                  Any | None = None
    previous_distro_name:       str | None = None
    previous_target_dir:        str | None = None
    previous_uninstaller_path:  str | None = None
    distros:                    list = field(default_factory=list)
    distros_dict:               dict = field(default_factory=dict)
    iso_md5_hashes:             dict = field(default_factory=dict)

    # ── Drives ─────────────────────────────────────────────────────
    target_drive:               Any | None = None   # Drive object
    system_drive:               str | None = None
    installation_size_mb:       int | None = None
    drives:                     list = field(default_factory=list)
    drives_dict:                dict = field(default_factory=dict)

    # ── Partition sizes ────────────────────────────────────────────
    root_size_mb:               int | None = None
    swap_size_mb:               int | None = None
    home_size_mb:               int | None = None
    usr_size_mb:                int | None = None

    # ── System info ────────────────────────────────────────────────
    platform:                   str | None = None
    os_name:                    str | None = None
    arch:                       str | None = None
    encoding:                   str | None = None
    total_memory_mb:            int = 0
    environment_variables:      dict = field(default_factory=dict)

    # ── Locale / language ──────────────────────────────────────────
    language:                   str | None = None
    windows_language:           str | None = None
    locale:                     str | None = None
    country:                    str | None = None
    timezone:                   str | None = None

    # ── User ───────────────────────────────────────────────────────
    username:                   str | None = None
    password:                   str | None = None
    host_username:              str | None = None
    user_full_name:             str | None = None
    user_directory:             str | None = None
    accessibility:              str = ""

    # ── Keyboard ───────────────────────────────────────────────────
    keyboard_layout:            str | None = None
    keyboard_variant:           str | None = None

    # ── Boot ───────────────────────────────────────────────────────
    kernel:                     str | None = None
    initrd:                     str | None = None

    # ── Windows host info (populated by fetch_host_info) ──────────────
    registry_key:           str | None = None
    windows_version:        str | None = None
    windows_version2:       str | None = None
    windows_sp:             str | None = None
    windows_build:          str | None = None
    windows_language_code:  int | None = None
    gmt:                    float = 0.0
    processor_name:         str | None = None
    bootloader:             str | None = None
    hostname:               str | None = None
    locale_dir:             str | None = None
    source_id:              str | None = None
    installer_type:         str | None = None

    # ── Runtime-assigned paths ─────────────────────────────────────────
    icon:                   str | None = None
    custom_install:         str | None = None
    dimage_path:            str | None = None

    # ── Helpers ────────────────────────────────────────────────────
    def update(self, mapping: dict) -> None:
        for key, value in mapping.items():
            setattr(self, key, value)

    def __str__(self) -> str:
        return f"Info({self.__dict__})"