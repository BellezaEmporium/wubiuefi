#!/usr/bin/env python
#
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

# once compiled and packaged by pypack,
# all dependencies will be in ./lib,
# so let's add ./lib to the path
import sys
import os
import platform

def get_base_path():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS')
    # En dev, remonter d'un niveau au-dessus de src/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

root_dir = get_base_path()
lib_dir = os.path.join(root_dir, 'lib')
sys.path.insert(0, lib_dir)


from wubi.application import Wubi

if platform.architecture()[0] != '64bit':
    print("We're sorry, but Wubi requires a 64-bit version of Windows to run, " \
    "due to Ubuntu not releasing 32-bit versions of their ISOs since 18.04. " \
    "Please use an earlier version of Wubi if you have a 32-bit Windows.")
    sys.exit(1)

try:
    from version import application_name, version, revision
except:
    application_name = "wubi"
    version = "0.0"
    revision = "0"

application = Wubi(application_name, version, revision, root_dir)
application.run()
