# -*- coding: utf-8 -*-
"""
Copyright (C) 2012 Fabio Erculiani

Authors:
  Fabio Erculiani

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; version 3.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""
import os
import tempfile

ICON_PATH = os.getenv("RIGO_ICON_PATH", "/usr/share/rigo/icons")
DATA_DIR = os.getenv("RIGO_DATA_DIR", "/usr/share/rigo")

_home_dir = os.getenv("HOME")
if _home_dir is None:
    _home_dir = tempfile.mkdtemp(
        prefix="EntropyHomeDirectory",
        dir="/var/tmp")
CONF_DIR = os.path.join(_home_dir, ".entropy")
