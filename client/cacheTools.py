#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo on-disk caching tools

    Copyright (C) 2007 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

from equoTools import EquoInterface
def cache(options):
    rc = 0
    if len(options) < 1:
	return -10

    Equo = EquoInterface(noclientdb = True, xcache = False)
    if options[0] == "clean":
	Equo.purge_cache()
    elif options[0] == "generate":
	Equo.generate_cache()
    else:
        rc = -10

    return rc




