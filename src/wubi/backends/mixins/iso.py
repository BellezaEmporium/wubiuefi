from __future__ import annotations

import os
import glob
import logging
import tempfile

from os.path import abspath, isfile
from gettext import gettext as _

from .iso_verifier import verify_iso
from .utils import join_path, find_line_in_file, get_file_hash

log = logging.getLogger("Backend.iso")


class IsoMixin:

    # ── Search ────────────────────────────────────────────────────

    def find_iso(self, associated_task=None) -> str | None:
        log.debug("Searching for local ISO")
        for path in self.get_iso_search_paths():
            for iso in glob.glob(join_path(path, '*.iso')):
                if self.info.distro.is_valid_iso(iso, self.info.check_arch):
                    return iso
        return None

    def find_any_iso(self) -> tuple[str | None, object | None]:
        if self.info.iso_path and os.path.exists(self.info.iso_path):
            log.debug(f"Checking pre-specified ISO {self.info.iso_path}")
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

    def cache_iso_path(self) -> None:
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

    # ── Validation ────────────────────────────────────────────────

    def check_cd(self, cd_path: str, associated_task=None) -> bool:
        if associated_task:
            associated_task.description = _(f"Checking CD {cd_path}")
        if not self.info.distro.is_valid_cd(cd_path, check_arch=False):
            return False
        self.set_distro_from_arch(cd_path)
        if self.info.skip_md5_check:
            return True
        md5sums_file = join_path(cd_path, self.info.distro.md5sums)
        for rel_path in self.info.distro.get_required_files():
            if rel_path == self.info.distro.md5sums:
                continue
            check_file = (
                associated_task.add_subtask(self.check_file)
                if associated_task else self.check_file
            )
            if not check_file(join_path(cd_path, rel_path), rel_path, md5sums_file):
                return False
        return True

    def check_iso(self, iso_path: str, associated_task=None) -> bool:
        log.debug(f"Checking {iso_path}")
        if not self.info.distro.is_valid_iso(iso_path, check_arch=False):
            return False
        self.set_distro_from_arch(iso_path)
        if self.info.skip_md5_check:
            return True
        base_url = getattr(self.info.distro, 'releases_url', None) \
            or f"https://releases.ubuntu.com/{self.info.distro.version}"
        return verify_iso(
            base_url=base_url,
            iso_path=iso_path,
            install_dir=self.info.install_dir,
            proxy=self.info.web_proxy,
            skip_gpg=self.info.skip_md5_check,
            associated_task=associated_task,
        )

    def check_file(
        self, file_path: str, relpath: str, md5sums: str,
        associated_task=None,
    ) -> bool:
        log.debug(f"  checking {file_path}")
        if associated_task:
            associated_task.description = _(f"Checking {file_path}")
        relpath     = relpath.replace("\\", "/")
        md5line     = find_line_in_file(md5sums, f"./{relpath}", endswith=True)
        if not md5line:
            raise Exception(f"Cannot find md5 in {md5sums} for {relpath}")
        reference   = md5line.split()[0]
        hash_len    = len(reference) * 4
        if hash_len == 160:
            hash_name = 'sha1'
        elif hash_len in (224, 256, 384, 512):
            hash_name = f'sha{hash_len}'
        else:
            hash_name = 'md5'
        computed    = get_file_hash(file_path, hash_name, associated_task)
        match       = computed == reference
        log.debug(f"  {file_path} {hash_name}: {'OK' if match else 'MISMATCH'}")
        return match

    def set_distro_from_arch(self, cd_or_iso_path: str) -> None:
        if self.info.check_arch:
            return
        arch = self.info.distro.get_info(cd_or_iso_path)[3]
        if self.info.distro.arch == arch:
            return
        name = self.info.distro.name
        log.debug(f"Switching to {name} {arch} (was {name} {self.info.distro.arch})")
        self.info.distro = self.info.distros_dict.get((name.lower(), arch))

    # ── ISO file listing / extraction ─────────────────────────────

    def get_iso_file_names(self, iso_path: str) -> list[str]:
        iso_path = abspath(iso_path)
        if iso_path in self.cache:
            return self.cache[iso_path] or []
        self.cache[iso_path] = None
        try:
            import pycdlib
            iso = pycdlib.pycdlib.PyCdlib()
            iso.open(iso_path)
            try:
                if iso.has_rock_ridge():
                    walk_kwargs = {'rr_path': '/'}
                    mode = 'rock_ridge'
                elif iso.has_joliet():
                    walk_kwargs = {'joliet_path': '/'}
                    mode = 'joliet'
                else:
                    walk_kwargs = {'iso_path': '/'}
                    mode = 'iso9660'
                log.debug(f"get_iso_file_names using {mode}")
                names = []
                for dirname, _dirs, filelist in iso.walk(**walk_kwargs):
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

    def extract_file_from_iso(
        self, iso_path: str, file_path: str,
        output_dir: str | None = None, overwrite: bool = False,
    ) -> str | None:
        log.debug(f"  extracting {file_path} from {iso_path}")
        if not iso_path or not os.path.exists(iso_path):
            raise Exception(f"Invalid path: {iso_path}")
        if not output_dir:
            output_dir = tempfile.gettempdir()
        output_file = join_path(output_dir, os.path.basename(file_path))
        if os.path.exists(output_file):
            if overwrite:
                os.unlink(output_file)
            else:
                raise Exception(f"Cannot overwrite {output_file}")
        try:
            import pycdlib
            iso = pycdlib.pycdlib.PyCdlib()
            iso.open(iso_path)
            use_rr     = iso.has_rock_ridge()
            use_joliet = iso.has_joliet()
            try:
                iso_file_path = '/' + file_path.replace('\\', '/').lstrip('/')
                os.makedirs(output_dir, exist_ok=True)
                for candidate in [iso_file_path, iso_file_path.upper(), iso_file_path.lower()]:
                    try:
                        with open(output_file, 'wb') as f:
                            if use_rr:
                                iso.get_file_from_iso_fp(f, rr_path=candidate)
                            elif use_joliet:
                                iso.get_file_from_iso_fp(f, joliet_path=candidate)
                            else:
                                iso.get_file_from_iso_fp(f, iso_path=candidate)
                        return output_file if isfile(output_file) else None
                    except Exception:
                        pass
            finally:
                iso.close()
        except Exception as err:
            log.exception(err)
        return None

    # ── Search paths ──────────────────────────────────────────────

    def get_iso_search_paths(self) -> list[str]:
        paths  = [os.path.dirname(self.info.original_exe)]
        paths += [drive.path for drive in self.info.drives]
        paths += [os.environ.get('Desktop')]
        return [abspath(p) for p in paths if p and os.path.isdir(p)]

    def get_cd_search_paths(self) -> list[str]:
        return [drive.path for drive in self.info.drives]

    def select_mirrors(self, urls: list) -> list:
        for url in urls:
            url.score = url.preference + (50 if self.info.country == url.location else 0)
        return sorted(urls, key=lambda u: -u.score)