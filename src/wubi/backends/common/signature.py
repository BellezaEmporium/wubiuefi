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

'''
Check signature using openpgp and pgpy
'''

import os
from .utils import read_file
import pgpy

def verify_gpg_signature(detached_file, signature_file, key_file):
    signature_data = read_file(signature_file, binary=True)
    if signature_data is None:
        return False
    
    key_data = read_file(key_file, binary=True)
    if key_data is None:
        return False
    
    message = read_file(detached_file, binary=True)
    if message is None:
        return False
    
    try:
        key = pgpy.PGPKey()
        key.parse(key_data)
        
        signature = pgpy.PGPSignature()
        signature.parse(signature_data)
        
        return key.verify(message, signature)
    except Exception:
        return False