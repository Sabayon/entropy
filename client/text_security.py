#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo security tools

    Copyright (C) 2007-2008 Fabio Erculiani

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

from entropy import EquoInterface
Equo = EquoInterface()

def security(options):

    rc = 0
    if len(options) < 1:
        return -10

    if options[0] == "update":
        rc = Equo.Security.fetch_advisories()
    #elif options[0] == "XXXX":
    #    XXXXX
    else:
        rc = -10

    return rc




