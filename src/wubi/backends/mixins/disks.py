from __future__ import annotations

import os
import re
import logging
import threading

import py7zr

from .virtualdisk import create_virtual_disk
from .utils import join_path, run_command, spawn_command, copy_file, rm_tree
from wubi import errors

log = logging.getLogger("Backend.disks")


class DiskMixin:

    # ── Directory structure ───────────────────────────────────────

    def select_target_dir(self, associated_task=None) -> None:
        target_dir = join_path(
            self.info.target_drive.path,
            self.info.distro.installation_dir,
        ).replace(' ', '_').replace('__', '_')
        if os.path.exists(target_dir):
            raise Exception(
                f"Cannot install into {target_dir}.\n"
                f"A file or directory with that name already exists.\n"
                f"Please remove it before continuing."
            )
        self.info.target_dir = target_dir
        log.info(f"Installing into {target_dir}")
        self.info.icon = join_path(
            self.info.target_dir, self.info.distro.name + '.ico')

    def create_dir_structure(self, associated_task=None) -> None:
        self.info.disks_dir        = join_path(self.info.target_dir, "disks")
        self.info.install_dir      = join_path(self.info.target_dir, "install")
        self.info.install_boot_dir = join_path(self.info.install_dir, "boot")
        self.info.disks_boot_dir   = join_path(self.info.disks_dir, "boot")
        for d in [
            self.info.target_dir,
            self.info.disks_dir,
            self.info.install_dir,
            self.info.install_boot_dir,
            self.info.disks_boot_dir,
            join_path(self.info.disks_boot_dir, "grub"),
            join_path(self.info.install_boot_dir, "grub"),
        ]:
            os.makedirs(d, exist_ok=True)

    def create_diskimage_dirs(self, associated_task=None) -> None:
        self.info.disks_dir      = join_path(self.info.target_dir, "disks")
        self.info.disks_boot_dir = join_path(self.info.disks_dir, "boot")
        for d in [
            self.info.target_dir,
            self.info.disks_dir,
            self.info.disks_boot_dir,
            join_path(self.info.disks_boot_dir, "grub"),
        ]:
            os.makedirs(d, exist_ok=True)

    # ── Kernel ────────────────────────────────────────────────────

    def extract_kernel(self, associated_task=None) -> None:
        bootdir = self.info.install_boot_dir
        if not self.info.iso_path:
            raise Exception("Could not retrieve the required installation files")

        log.debug(f"Extracting files from ISO {self.info.iso_path}")
        if self.info.distro.md5sums:
            self.extract_file_from_iso(
                self.info.iso_path, self.info.distro.md5sums, output_dir=bootdir)
        self.extract_file_from_iso(
            self.info.iso_path, self.info.distro.kernel, output_dir=bootdir)
        self.extract_file_from_iso(
            self.info.iso_path, self.info.distro.initrd, output_dir=bootdir)

        self.info.kernel = join_path(bootdir, os.path.basename(self.info.distro.kernel))
        self.info.initrd = join_path(bootdir, os.path.basename(self.info.distro.initrd))

        if self.info.distro.md5sums:
            md5sums = join_path(bootdir, os.path.basename(self.info.distro.md5sums))
            for file_path, rel_path in [
                (self.info.kernel, self.info.distro.kernel),
                (self.info.initrd, self.info.distro.initrd),
            ]:
                if not self.check_file(file_path, rel_path, md5sums):
                    raise Exception(f"File {file_path} is corrupted")
        else:
            log.debug("No md5sums for this distro — skipping integrity check")

    # ── Windows-side installation files ──────────────────────────

    def create_uninstaller(self, associated_task=None) -> None:
        import shutil
        from . import registry
        name = f'uninstall-{self.info.application_name}.exe'.replace(' ', '_').replace('__', '_')
        path = join_path(self.info.target_dir, name)
        if os.path.splitext(self.info.original_exe)[-1] == '.exe':
            log.debug(f"Copying uninstaller {self.info.original_exe} -> {path}")
            shutil.copyfile(self.info.original_exe, path)
        uninstall_string = f'"{path}" --uninstall'
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'UninstallString',  uninstall_string)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'InstallationDir',  self.info.target_dir)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'DisplayName',      self.info.distro.name)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'DisplayIcon',      self.info.icon)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'DisplayVersion',   self.info.version_revision)
        registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'Publisher',        self.info.distro.name)
        if self.info.distro.website:
            registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'URLInfoAbout', self.info.distro.website)
        if self.info.distro.support:
            registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'HelpLink',     self.info.distro.support)

    def copy_installation_files(self, associated_task=None) -> None:
        import shutil
        from gettext import gettext as _
        from .utils import replace_line_in_file
        from os.path import isdir

        self.info.custom_install = join_path(self.info.install_dir, 'custom-installation')
        src  = join_path(self.info.data_dir, 'custom-installation')
        log.debug(f"Copying {src} -> {self.info.custom_install}")
        shutil.copytree(src, self.info.custom_install)

        src = join_path(self.info.root_dir, 'winboot')
        if isdir(src):
            dest = join_path(self.info.target_dir, 'winboot')
            log.debug(f"Copying {src} -> {dest}")
            shutil.copytree(src, dest)

        failure_hook = join_path(self.info.custom_install, 'hooks', 'failure-command.sh')
        msg = _(
            f"The installation failed. Logs have been saved in: "
            f"{join_path(self.info.install_dir, 'installation-logs.zip')}.\n\n"
            f"Note that in verbose mode, the logs may include the password.\n\n"
            f"The system will now reboot."
        )
        replace_line_in_file(failure_hook, 'msg=', f'msg="{str(msg.encode(\"utf8\"))}"')

        src  = join_path(self.info.image_dir, self.info.distro.name + '.ico')
        dest = self.info.icon
        log.debug(f"Copying {src} -> {dest}")
        shutil.copyfile(src, dest)

    def uncompress_target_dir(self, associated_task=None) -> None:
        if self.info.target_drive.is_fat():
            return
        for cmd in [
            ['compact', self.info.target_dir,                         '/U', '/A', '/F'],
            ['compact', join_path(self.info.target_dir, '*.*'),       '/U', '/A', '/F'],
        ]:
            try:
                run_command(cmd)
            except Exception as err:
                log.error(err)

    def uncompress_files(self, associated_task=None) -> None:
        if self.info.target_drive.is_fat():
            return
        for cmd in [
            ['compact', self.info.install_boot_dir,                   '/U', '/A', '/F'],
            ['compact', join_path(self.info.install_boot_dir, '*.*'), '/U', '/A', '/F'],
        ]:
            try:
                run_command(cmd)
            except Exception as err:
                log.error(err)

    # ── Virtual disks ─────────────────────────────────────────────

    def choose_disk_sizes(self, associated_task=None) -> None:
        total    = self.info.installation_size_mb
        swap     = 256
        root     = total - swap
        home = usr = 0
        if self.info.target_drive.is_fat():
            if root > 8500:
                home = root - 8000
                usr  = 4000
                root = 4000
            elif root > 5500:
                usr  = 4000
                root -= 4000
            elif root > 4000:
                usr  = root - 1500
                root = 1500
            if home > 4000:
                home = 4000
        self.info.root_size_mb = root
        self.info.swap_size_mb = swap
        self.info.home_size_mb = home
        self.info.usr_size_mb  = usr
        log.debug(
            "disk sizes — total=%s root=%s swap=%s home=%s usr=%s",
            total, root, swap, home, usr,
        )

    def create_virtual_disks(self, associated_task=None) -> None:
        for disk in ("root", "home", "usr", "swap"):
            path    = join_path(self.info.disks_dir, disk + ".disk")
            size_mb = int(getattr(self.info, disk + "_size_mb") or 0)
            if size_mb:
                create_virtual_disk(path, size_mb)

    def extract_diskimage(self, associated_task=None) -> None:
        xz = self.dimage_path
        assert isinstance(xz, str), "dimage_path must be a string path"
        target_dir = self.info.disks_dir
        os.makedirs(target_dir, exist_ok=True)
        try:
            with py7zr.SevenZipFile(xz, mode='r') as archive:
                archive.extractall(path=target_dir)
            log.debug(f"Extracted diskimage from {xz} to {target_dir}")
        except Exception as e:
            log.error(f"Diskimage extraction failed: {e}")
            raise Exception(f"Failed to extract diskimage: {e}")
        if not self.info.disk_image_path:
            try:
                os.remove(xz)
                log.debug(f"Removed temporary diskimage file: {xz}")
            except Exception as e:
                log.warning(f"Could not remove diskimage file: {e}")

    def expand_diskimage(self, associated_task=None) -> None:
        root      = join_path(self.info.disks_dir, 'root.disk')
        resize2fs = join_path(self.info.bin_dir, 'resize2fs.exe')
        size_arg  = f'{self.info.root_size_mb}M'
        if not associated_task:
            run_command([resize2fs, '-f', root, size_arg])
            return
        associated_task.size = 100
        associated_task.set_progress(0)
        proc = spawn_command([resize2fs, '-p', '-f', root, size_arg])
        assert proc.stdout is not None and proc.stderr is not None
        threading.Thread(target=proc.stdout.read, daemon=True).start()
        buf = ''
        cancelled = False
        for raw in iter(lambda: proc.stderr.read(1), b''):
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
            raise Exception(f"resize2fs failed with code: {proc.returncode}")
        associated_task.set_progress(100)

    def create_swap_diskimage(self, associated_task=None) -> None:
        path = join_path(self.info.disks_dir, 'swap.disk')
        size = str(self.info.swap_size_mb * 1024 * 1024)
        run_command(['fsutil', 'file', 'createnew', path, size])

    # ── Uninstallation ────────────────────────────────────────────

    def remove_target_dir(self, associated_task=None) -> None:
        prev = self.info.previous_target_dir
        if not prev or not os.path.isdir(prev):
            log.debug(f"Unable to find {prev}")
            return
        log.debug(f"Removing {prev}")
        try:
            rm_tree(prev)
        except OSError as e:
            if e.errno == 22:
                log.exception("Unable to remove target directory.")
                cmd = spawn_command(['chkdsk', '/F'])
                cmd.communicate(input=('Y' + os.linesep).encode())
                raise errors.WubiCorruptionError

    def remove_registry_key(self, associated_task=None) -> None:
        from . import registry
        registry.delete_key('HKEY_LOCAL_MACHINE', self.info.registry_key)