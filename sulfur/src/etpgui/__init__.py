#!/usr/bin/python2 -O
# -*- coding: iso-8859-1 -*-
#    Sulfur (Entropy Interface)
#    Copyright: (C) 2007-2009 Fabio Erculiani < lxnay<AT>sabayonlinux<DOT>org >
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

import gtk
CURRENT_CURSOR = None

def busyCursor(mainwin, insensitive=False, cur = gtk.gdk.Cursor(gtk.gdk.WATCH)):
    ''' Set busy cursor in mainwin and make it insensitive if selected '''
    mainwin.window.set_cursor(cur)
    global CURRENT_CURSOR
    CURRENT_CURSOR = cur
    if insensitive:
        mainwin.set_sensitive(False)

def normalCursor(mainwin):
    ''' Set Normal cursor in mainwin and make it sensitive '''
    if mainwin.window != None:
        mainwin.window.set_cursor(None)
        mainwin.set_sensitive(True)
    global CURRENT_CURSOR
    CURRENT_CURSOR = None

