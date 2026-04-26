from __future__ import annotations

import os
import logging
import shutil

from gettext import gettext as _

from ..utils.utils import join_path, unix_path, read_file, write_file, copy_file, replace_line_in_file, md5_password, hash_password

log = logging.getLogger("Backend.preseed")


class PreseedMixin:

    def create_preseed(self, associated_task=None) -> None:
        installer = getattr(self.info.distro, 'installer', None)
        if not isinstance(installer, str):
            installer = 'subiquity'
        installer = installer.strip().lower() or 'subiquity'
        if installer == 'subiquity':
            self._create_autoinstall()
        # Calamares does not use a preseed file

    def _create_autoinstall(self) -> None:
        source   = join_path(self.info.data_dir, 'autoinstall.yaml')
        template = read_file(source)
        if isinstance(template, (bytes, bytearray, memoryview)):
            template = bytes(template).decode('utf-8', errors='ignore')
        if not template:
            raise Exception(f"Could not read autoinstall template: {source}")

        username = self.info.username or self.info.host_username or ""
        hostname = (
            self.info.hostname
            or self.info.distro.name.lower().replace(' ', '-')
        )
        autoinstall_base = self.info.custom_install or self.info.install_dir
        if not autoinstall_base:
            raise Exception("Could not determine target directory for autoinstall")

        dic = dict(
            locale                  = self.info.locale,
            keyboard_layout         = self.info.keyboard_layout,
            keyboard_variant        = self.info.keyboard_variant,
            timezone                = self.info.timezone,
            realname                = self.info.user_full_name or username,
            hostname                = hostname,
            username                = username,
            hashed_password         = hash_password(self.info.password),
            source_id               = self._get_source_id(),
            custom_installation_dir = unix_path(autoinstall_base),
        )
        content = template
        for k, v in dic.items():
            content = content.replace(f'$({k})', v if v is not None else '')

        autoinstall_dir = join_path(autoinstall_base, 'autoinstall')
        os.makedirs(autoinstall_dir, exist_ok=True)
        write_file(join_path(autoinstall_dir, 'autoinstall.yaml'), content)

    def create_preseed_diskimage(self, associated_task=None) -> None:
        source   = join_path(self.info.data_dir, 'preseed.disk')
        template = read_file(source)
        if template is None:
            raise Exception(f"Could not read preseed template: {source}")
        if isinstance(template, (bytes, bytearray, memoryview)):
            template = bytes(template).decode('utf-8', errors='ignore')
        dic = dict(
            timezone         = self.info.timezone,
            password         = md5_password(self.info.password),
            keyboard_variant = self.info.keyboard_variant,
            keyboard_layout  = self.info.keyboard_layout,
            locale           = self.info.locale,
            user_full_name   = self.info.user_full_name,
            username         = self.info.username,
        )
        for k, v in dic.items():
            template = template.replace(f'$({k})', v if v is not None else '')
        write_file(join_path(self.info.install_dir, 'preseed.cfg'), template)
        copy_file(
            join_path(self.info.data_dir, 'wubildr-disk.cfg'),
            join_path(self.info.install_dir, 'wubildr-disk.cfg'),
        )

    def create_preseed_cdboot(self, associated_task=None) -> None:
        source = join_path(self.info.data_dir, 'preseed.cdboot')
        target = self.info.custom_install or self.info.install_dir
        if not target:
            raise Exception("Could not determine target directory for preseed.cdboot")
        copy_file(source, join_path(target, 'preseed.cfg'))

    def modify_grub_configuration(self, associated_task=None) -> None:
        installer     = getattr(self.info.distro, 'installer', 'subiquity')
        template_file = join_path(self.info.data_dir, f'grub.install.{installer}.cfg')
        template      = read_file(template_file)
        if template is None:
            raise Exception(f"Could not read grub template: {template_file}")
        if isinstance(template, (bytes, bytearray, memoryview)):
            template = bytes(template).decode('utf-8', errors='ignore')

        isopath = unix_path(self.info.iso_path) if self.info.iso_path else ""
        custom  = unix_path(self.info.custom_install) if self.info.custom_install else ""

        dic = dict(
            custom_installation_dir           = custom,
            iso_path                          = isopath,
            keyboard_variant                  = self.info.keyboard_variant,
            keyboard_layout                   = self.info.keyboard_layout,
            locale                            = self.info.locale,
            accessibility                     = self.info.accessibility,
            kernel                            = unix_path(self.info.kernel),
            initrd                            = unix_path(self.info.initrd),
            rootflags                         = "rootflags=sync",
            title1                            = "Completing the Ubuntu installation.",
            title2                            = "For more installation boot options, press `ESC' now...",
            normal_mode_title                 = "Normal mode",
            pae_mode_title                    = "PAE mode",
            safe_graphic_mode_title           = "Safe graphic mode",
            intel_graphics_workarounds_title  = "Intel graphics workarounds",
            nvidia_graphics_workarounds_title = "Nvidia graphics workarounds",
            acpi_workarounds_title            = "ACPI workarounds",
            verbose_mode_title                = "Verbose mode",
            demo_mode_title                   = "Demo mode",
        )
        content = template
        for k, v in dic.items():
            content = content.replace(f'$({k})', v if v is not None else '')
        write_file(
            join_path(self.info.install_boot_dir, 'grub', 'grub.cfg'),
            content,
        )