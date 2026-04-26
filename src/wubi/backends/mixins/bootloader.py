from __future__ import annotations

import os
import re
import shutil
import string
import logging
import subprocess
from pathlib import Path

from . import registry
from .utils import join_path, write_file, run_command

log = logging.getLogger("Backend.bootloader")


class BootloaderMixin:

    # ── Detection ─────────────────────────────────────────────────

    def check_EFI(self) -> bool:
        if self.info.bootloader != 'vista':
            return False
        try:
            bcdedit = self._find_bcdedit()
            result  = run_command([bcdedit, '/enum'])
        except Exception as err:
            log.warning(f"EFI detection skipped: {err}")
            return False
        result = self._decode(result).lower()
        efi = "bootmgfw.efi" in result or "winload.efi" in result
        log.debug(f"EFI boot={efi}")
        return efi

    def check_secure_boot(self) -> bool:
        val = registry.get_value(
            'HKEY_LOCAL_MACHINE',
            r'SYSTEM\CurrentControlSet\Control\SecureBoot\State',
            'UEFISecureBootEnabled')
        enabled = bool(val)
        if enabled:
            build = int(self.info.windows_build or 0)
            if build >= 22000:
                log.warning(
                    "Secure Boot is active — the BCD GRUB entry will not be "
                    "signed. The user must disable Secure Boot manually."
                )
        return enabled

    # ── Install ───────────────────────────────────────────────────

    def modify_bootloader(self, associated_task) -> None:
        for drive in self.info.drives:
            if drive.type in ('removable', 'hd'):
                def make_bcd_task(d):
                    def _task(associated_task=None):
                        self.modify_bcd(d, associated_task)
                    _task.__name__ = f"modify_bcd_{d.path}"
                    return _task
                associated_task.add_subtask(make_bcd_task(drive))

    def modify_bcd(self, drive, associated_task=None) -> None:
        if getattr(self, '_is_already_configured', False):
            log.info(f"BCD already configured — skipping duplicate call ({drive.path})")
            return

        bcdedit = self._find_bcdedit()
        if registry.get_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'VistaBootDrive'):
            log.debug("BCD already modified (registry check).")
            self._is_already_configured = True
            return

        if self.info.efi:
            log.debug("Configuring UEFI bootloader…")
            self.modify_EFI_folder(associated_task, bcdedit)
            try:
                run_command(['powercfg', '/h', 'off'])
            except Exception as err:
                log.error(err)
        else:
            log.error(
                "Legacy BIOS boot is not supported — Ubuntu dropped it in recent releases."
            )

        self._is_already_configured = True

    def modify_EFI_folder(self, associated_task, bcdedit) -> str:
        esp_drive, need_unmount = self._get_or_mount_esp()
        log.debug(f"EFI partition at {esp_drive}")
        try:
            target_name = self.info.target_dir[3:].replace(' ', '_').replace('__', '_') \
                or self.info.application_name.replace(' ', '_')

            dest_root = join_path(esp_drive, 'EFI', target_name)
            os.makedirs(dest_root, exist_ok=True)

            src_efi = join_path(self.info.root_dir, 'winboot', 'EFI')
            if os.path.exists(src_efi):
                shutil.copytree(src_efi, dest_root, dirs_exist_ok=True)

            wubildr_cfg_src = join_path(self.info.root_dir, 'winboot', 'wubildr.cfg')
            if os.path.isfile(wubildr_cfg_src):
                shutil.copyfile(wubildr_cfg_src, join_path(dest_root, 'wubildr.cfg'))

            efi_prefix = ('/' + dest_root[3:].replace('\\', '/') + '/').replace('//', '/')
            write_file(
                join_path(dest_root, 'grub.cfg'),
                f'search --no-floppy --file --set=root {efi_prefix}wubildr.cfg\n'
                f'configfile {efi_prefix}wubildr.cfg\n',
            )

            efi_binary = 'grubia32.efi' if self.get_efi_arch(associated_task, esp_drive) == 'ia32' \
                else 'shimx64.efi'
            efi_relative_path = f"\\EFI\\{target_name}\\{efi_binary}"

            guid = self._find_existing_bcd_guid(bcdedit, efi_relative_path)
            if guid:
                log.info(f"Existing BCD entry found ({guid}). Updating…")
            else:
                res = subprocess.run(
                    [bcdedit, '/create', '/d', self.info.distro.name, '/application', 'bootapp'],
                    capture_output=True, text=True, check=True,
                )
                match = re.search(r'\{([a-fA-F0-9-]+)\}', res.stdout)
                if not match:
                    raise RuntimeError("Could not retrieve GUID from bcdedit output.")
                guid = f"{{{match.group(1)}}}"

            for cmd in [
                [bcdedit, '/set',         guid, 'device', f'partition={esp_drive}'],
                [bcdedit, '/set',         guid, 'path', efi_relative_path],
                [bcdedit, '/set',         guid, 'locale', self.info.locale],
                [bcdedit, '/set',         guid, 'inherit', '{bootloadersettings}'],
                [bcdedit, '/displayorder', guid, '/addlast'],
                [bcdedit, '/set', '{fwbootmgr}', 'displayorder', guid, '/addlast'],
                [bcdedit, '/timeout',     '10'],
                [bcdedit, '/bootsequence', guid],
            ]:
                subprocess.run(cmd, check=False, capture_output=True)

            registry.set_value(
                'HKEY_LOCAL_MACHINE', self.info.registry_key, 'VistaBootDrive', guid)
            return efi_relative_path

        finally:
            if need_unmount:
                log.debug(f"Unmounting ESP from {esp_drive}")
                res = subprocess.run(['mountvol', esp_drive, '/D'], capture_output=True, text=True)
                if res.returncode != 0:
                    err = (res.stderr or res.stdout or '').strip().lower()
                    if 'not found' not in err and 'introuvable' not in err:
                        log.debug(f"Unmount failed for {esp_drive}: {res.stderr or res.stdout}")

    # ── Uninstall ─────────────────────────────────────────────────

    def undo_bootloader(self, associated_task) -> None:
        self.undo_bcd(associated_task)
        for drive in self.info.drives:
            if drive.type not in ('removable', 'hd'):
                continue
            for fname in ['wubildr', 'wubildr.exe']:
                f = join_path(drive.path, fname)
                if os.path.isfile(f):
                    os.unlink(f)
        if self.info.efi:
            self.undo_EFI_folder(associated_task)
            try:
                run_command(['powercfg', '/h', 'on'])
            except Exception as err:
                log.error(err)

    def undo_bcd(self, associated_task=None) -> None:
        try:
            bcdedit = self._find_bcdedit()
        except FileNotFoundError:
            log.error("bcdedit not found — BCD entry not removed")
            return
        bcd_id = registry.get_value(
            'HKEY_LOCAL_MACHINE', self.info.registry_key, 'VistaBootDrive')
        if not bcd_id:
            log.debug("BCD ID not found — nothing to remove")
            return
        log.debug(f"Removing BCD entry {bcd_id}")
        try:
            if self.info.efi:
                subprocess.run(
                    [bcdedit, '/set', '{fwbootmgr}', 'displayorder', bcd_id, '/remove'],
                    capture_output=True,
                )
            run_command([bcdedit, '/delete', bcd_id, '/f'])
            registry.set_value('HKEY_LOCAL_MACHINE', self.info.registry_key, 'VistaBootDrive', "")
        except Exception as err:
            log.error(err)

    def undo_EFI_folder(self, associated_task=None) -> None:
        if not self.info.previous_target_dir:
            log.debug("No previous target directory — skipping EFI folder removal.")
            return
        esp_drive, need_unmount = self._get_or_mount_esp()
        try:
            target_name = self.info.previous_target_dir[3:].replace(' ', '_').replace('__', '_')
            dest = join_path(esp_drive, 'EFI', target_name)
            if os.path.exists(dest):
                log.debug(f"Removing EFI folder {dest}")
                shutil.rmtree(dest, ignore_errors=True)
        except Exception as err:
            log.error(err)
        finally:
            if need_unmount:
                subprocess.run(['mountvol', esp_drive, '/D'], capture_output=True)

    # ── Helpers ───────────────────────────────────────────────────

    def get_efi_arch(self, associated_task, efidrive) -> str:
        mapping = {
            "amd64": "x64", "x86_64": "x64",
            "x86": "ia32", "i386": "ia32", "i686": "ia32",
            "arm64": "arm64", "aarch64": "arm64",
        }
        arch = mapping.get(self.info.arch.lower(), "x64")
        log.debug(f"efi_arch={arch} (from arch={self.info.arch})")
        return arch

    def _get_available_drive_letter(self) -> str:
        if os.name != 'nt':
            return "/mnt/esp"
        bitmask = __import__('ctypes').windll.kernel32.GetLogicalDrives()
        for letter in reversed(string.ascii_uppercase):
            if not (bitmask & (1 << (ord(letter) - ord('A')))):
                return f"{letter}:"
        raise RuntimeError("No available drive letter.")

    def _get_or_mount_esp(self) -> tuple[str, bool]:
        for letter in reversed(string.ascii_uppercase):
            drive = f"{letter}:"
            if Path(f"{drive}\\EFI\\Microsoft").is_dir() or Path(f"{drive}\\EFI\\Boot").is_dir():
                try:
                    test = Path(f"{drive}\\EFI\\.wubi_test")
                    test.touch(); test.unlink()
                    return drive, False
                except OSError:
                    pass
        drive = self._get_available_drive_letter()
        mount = subprocess.run(['mountvol', drive, '/S'], capture_output=True, text=True)
        if Path(f"{drive}\\EFI").is_dir():
            return drive, True
        # diskpart fallback
        lv = subprocess.run(['diskpart'], input="list volume\n",
                            capture_output=True, text=True)
        vol_num = None
        for line in lv.stdout.splitlines():
            low = line.lower()
            if 'fat32' in low and any(k in low for k in ('system', 'syst', 'efi')):
                m = re.search(r'volume\s+(\d+)', line, re.IGNORECASE)
                if m:
                    vol_num = m.group(1)
                    break
        if vol_num is None:
            raise RuntimeError(
                f"Cannot locate ESP. mountvol output: {(mount.stderr or mount.stdout or '').strip()}")
        assign = subprocess.run(
            ['diskpart'],
            input=f"select volume {vol_num}\nassign letter={drive[0]}\n",
            capture_output=True, text=True,
        )
        if assign.returncode != 0:
            raise RuntimeError(
                f"diskpart failed to assign {drive}: {(assign.stderr or assign.stdout or '').strip()}")
        if not Path(f"{drive}\\EFI").is_dir():
            raise RuntimeError(f"ESP not available at {drive}\\")
        return drive, True

    def _find_existing_bcd_guid(self, bcdedit: str, search_path: str) -> str | None:
        try:
            result = subprocess.run([bcdedit, '/v'], capture_output=True, text=True, errors='ignore')
            current_guid = None
            for line in result.stdout.splitlines():
                line = line.strip().lower()
                if line.startswith(('identificateur', 'identifier')):
                    current_guid = line.split()[-1]
                if line.startswith('path') and search_path.lower() in line:
                    return current_guid
        except Exception:
            pass
        return None