#!/bin/sh
#    Entropy Bash-based trigger interpreter
#
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

# Pre-declared public functions

pkg_setup() {
    return 0
}

pkg_preinst() {
    return 0
}

pkg_postinst() {
    return 0
}

pkg_prerm() {
    return 0
}

pkg_postrm() {
    return 0
}

# that's it, for now
. $1
sandbox $2
