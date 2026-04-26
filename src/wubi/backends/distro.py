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
#

import os
from pathlib import Path
from .utils import read_file
import logging
import re
from typing import Union

log = logging.getLogger('Distro')
# Ubuntu: "Ubuntu 24.04 LTS "Noble Numbat" - Release amd64 (20240425)"
_ubuntu_re = re.compile(
    r'(?P<name>[\w\s-]+?) '
    r'(?P<version>\d[\w.]+)'
    r'(?: LTS)?(?: (?:["(])?(?P<codename>[\w\s-]+)(?:[")]))? - '
    r'(?P<subversion>[\D]+)? '
    r'(?P<arch>i386|amd64)(?:[\D]+)?(?P<build>[\d:.-]+)?'
)

# Debian: "Debian GNU/Linux 12.9.0 "Bookworm" - Official amd64 DVD Binary-1"
_debian_re = re.compile(
    r'Debian GNU/Linux '
    r'(?P<version>\d[\d.]+)'
    r'(?:\s+"(?P<codename>[^"]+)")? - '
    r'(?P<subversion>[^a-z]+)?'
    r'(?P<arch>i386|amd64|arm64)'
)

# Mint: "Linux Mint 21.3 "Virginia" - Release amd64"
_mint_re = re.compile(
    r'Linux Mint '
    r'(?P<version>\d[\d.]+)'
    r'(?:\s+"(?P<codename>[^"]+)")? - '
    r'(?P<subversion>[\w\s]+) '
    r'(?P<arch>i386|amd64|arm64)'
)

class Distro(object):

    cache = {}

    def __init__(
        self, name, version, kernel, initrd,
        info_file, arch, packages, size, files_to_check,
        backend, ordering, website, support, min_disk_space_mb,
        min_memory_mb, installation_dir,
        md5sums=None,
        iso_url=None,
        releases_url=None,
        diskimage=None, diskimage2=None,
        min_iso_size: Union[str, int] = 0, max_iso_size: Union[str, int] = 0,
        **kwargs):
        self.name = name
        self.version = version
        self.arch = arch
        self.kernel = str(Path(kernel))
        self.initrd = str(Path(initrd))
        self.info_file = str(Path(info_file))
        self.size = size and int(size) or 0
        self.min_iso_size = min_iso_size and int(min_iso_size) or 0
        self.max_iso_size = max_iso_size and int(max_iso_size) or 0
        self.min_disk_space_mb = int(min_disk_space_mb)
        self.min_memory_mb = int(min_memory_mb)
        self.packages = packages
        self.backend = backend
        self.ordering = ordering
        self.website = website
        self.support = support
        self.installation_dir = installation_dir
        self.diskimage = diskimage
        self.diskimage2 = diskimage2
        self.iso_url = iso_url
        self.releases_url = releases_url
        self.installer = kwargs.pop('installer', 'subiquity')
        self.md5sums = os.path.normpath(md5sums) if md5sums else None
        if isinstance(files_to_check, str):
            files_to_check = [
                os.path.normpath(f.strip().lower())
                for f in files_to_check.split(',')]
        self.files_to_check = files_to_check
        if kwargs:
            log.debug("Distro %s: unknown isolist fields ignored: %s" % (name, list(kwargs.keys())))

    def is_valid_cd(self, cd_path, check_arch):
        cd_path = str(Path(cd_path).resolve())
        log.debug('  checking whether %s is a valid %s CD' % (cd_path, self.name))
        if not Path(cd_path).is_dir():
            log.debug('    dir does not exist')
            return False
        required_files = self.get_required_files()
        for file in required_files:
            file = str(Path(cd_path) / file)
            if not Path(file).is_file():
                log.debug('    does not contain %s' % file)
                return False
        info = self.get_info(cd_path)
        if self.check_info(info, check_arch):
            log.info('Found a valid CD for %s: %s' % (self.name, cd_path))
            return True
        else:
            return False

    def is_valid_dimage(self, dimage_path, check_arch):
        '''
        Validate a disk image

        TBD: Add more checks
        '''
        dimage_path = str(Path(dimage_path).resolve())
        log.debug('  checking %s diskimage %s' % (self.name, dimage_path))
        if not Path(dimage_path).is_file():
            log.debug('    file does not exist')
            return False
        return True

    def is_valid_iso(self, iso_path, check_arch):
        iso_path = str(Path(iso_path).resolve())
        log.debug('  checking %s ISO %s' % (self.name, iso_path))
        if not Path(iso_path).is_file():
            log.debug('    file does not exist')
            return False
        files = self.backend.get_iso_file_names(iso_path)
        if not files:
            log.debug('    does not contain any file')
            return False
        files = [f.strip().lower() for f in files]
        required_files = self.get_required_files()
        for file in required_files:
            if file.strip().lower() not in files:
                log.debug('    does not contain %s' % file)
                return False
        info = self.get_info(iso_path)
        if self.check_info(info, check_arch):
            log.info('Found a valid iso for %s: %s' % (self.name, iso_path))
            return True
        else:
            return False

    def get_info(self, cd_or_iso_path):
        if (cd_or_iso_path, self.info_file) in Distro.cache:
            return Distro.cache[(cd_or_iso_path, self.info_file)]
        else:
            Distro.cache[(cd_or_iso_path, self.info_file)] = None
            if Path(cd_or_iso_path).is_file():
                info_file = self.backend.extract_file_from_iso(
                    cd_or_iso_path,
                    self.info_file,
                    output_dir=self.backend.info.temp_dir,
                    overwrite=True)
            elif Path(cd_or_iso_path).is_dir():
                info_file = str(Path(cd_or_iso_path) / self.info_file)
            else:
                return
            if not info_file or not Path(info_file).is_file():
                return
            try:
                info = read_file(info_file)
                info = self.parse_isoinfo(info)
            except Exception as err:
                log.error(err)
                return
            Distro.cache[(cd_or_iso_path, self.info_file)] = info
            return info

    def get_required_files(self):
        required_files = self.files_to_check[:]
        required_files += [
            self.kernel,
            self.initrd,
            self.info_file]
        if self.md5sums:
            required_files.append(self.md5sums)
        return required_files

    def check_info(self, info, check_arch):
        if not info:
            log.debug('could not get info %s' % info)
            return False
        name, version, subversion, arch = info # used in backend as well
        if self.name and name != self.name and self.version:
            log.debug('wrong name: %s != %s' % (name, self.name))
            return False
        if self.version and not (version == self.version or version.startswith(self.version + '.')):
            log.debug('wrong version: %s != %s' % (version, self.version))
            return False
        if check_arch and self.arch and arch != self.arch:
            log.debug('wrong arch: %s != %s' % (arch, self.arch))
            return False
        return True

    def parse_isoinfo(self, info):
        '''
        Parses the file within the ISO
        that contains metadata on the iso
        e.g. .disk/info in Ubuntu
        '''
        log.debug(f"  parsing info from str={info!r}")
        if not info:
            return None

        for pattern, distro_name in [
            (_ubuntu_re, self.name),
            (_debian_re, "Debian"),
            (_mint_re,   "Linux Mint"),
        ]:
            m = pattern.match(info)
            if m:
                groups = m.groupdict()
                name     = distro_name
                version  = groups.get("version", "")
                subver   = groups.get("subversion", "")
                arch     = groups.get("arch", self.arch)
                log.debug(f"  parsed info={groups}")
                return name, version, subver, arch

        # Fallback — unknown format, trust the distro config entirely
        log.debug("  parse_isoinfo: no pattern matched, using config values")
        return self.name, self.version, "", self.arch