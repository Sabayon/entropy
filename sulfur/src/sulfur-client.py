#!/usr/bin/python -O
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

import sys
import gtk
import gobject
sys.path.insert(0,"../../libraries")
sys.path.insert(1,"../../client")
sys.path.insert(2,"./")
sys.path.insert(3,"/usr/lib/entropy/libraries")
sys.path.insert(4,"/usr/lib/entropy/client")
sys.path.insert(5,"/usr/lib/entropy/sulfur")
import entropy.tools
from sulfur import SulfurApplication
from sulfur.dialogs import ExceptionDialog
from sulfur.setup import const

try:
    try:
        gtk.window_set_default_icon_from_file(
            const.PIXMAPS_PATH+"/sulfur-icon.png")
    except gobject.GError:
        pass
    mainApp = SulfurApplication()
    mainApp.init()
    gobject.threads_init()
    gtk.gdk.threads_enter()
    gtk.main()
    gtk.gdk.threads_leave()
    entropy.tools.kill_threads()
    mainApp.quit()
except SystemExit:
    print "Quit by User (SystemExit)"
    try:
        mainApp.quit()
    except NameError:
        pass
except KeyboardInterrupt:
    print "Quit by User (KeyboardInterrupt)"
    try:
        mainApp.quit()
    except NameError:
        pass
except: # catch other exception and write it to the logger.
    my = ExceptionDialog()
    my.show()
    entropy.tools.kill_threads()
    try:
        mainApp.quit(sysexit = False)
    except NameError:
        pass

raise SystemExit(0)