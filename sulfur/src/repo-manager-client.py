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

# Base Python Imports
import sys, os, pty, random
import logging
import commands
import time

# Entropy Imports
sys.path.insert(0,"../../libraries")
sys.path.insert(1,"../../client")
sys.path.insert(2,"./sulfur")
sys.path.insert(3,"/usr/lib/entropy/libraries")
sys.path.insert(4,"/usr/lib/entropy/client")
sys.path.insert(5,"/usr/lib/entropy/sulfur")
from entropy.const import *
import entropy.tools as entropyTools
from sulfur.packages import EntropyPackages
from sulfur.entropyapi import Equo, QueueExecutor
from entropy.qa import ErrorReportInterface
from entropy.i18n import _

# Sulfur Imports
import gtk, gobject
from sulfur.etpgui import *
from sulfur.setup import const
from sulfur.dialogs import *

class MyRepositoryManager(RepositoryManagerMenu):

    def __init__(self, Equo, parent):
        RepositoryManagerMenu.__init__(self, Equo, parent)

    def on_repoManagerClose_clicked(self, *args, **kwargs):
        self.QueueUpdater.kill()
        self.OutputUpdater.kill()
        self.PinboardUpdater.kill()
        self.destroy()
        raise SystemExit(1)

class ManagerApplication:

    def __init__(self):
        self.Equo = Equo()
        self.ui = None
        self.progressLogWrite = sys.stdout
        self.output = sys.stdout
        self.progress = None
        self.Equo.connect_to_gui(self)

    def init(self):
        mymenu = MyRepositoryManager(self.Equo, None)
        rc = mymenu.load()
        if not rc:
            del mymenu
            raise SystemExit(1)

    def destroy(self):
        self.Equo.destroy()

    def dummy_func(self, *args, **kwargs):
        pass

if __name__ == "__main__":

    try:
        try:
            gtk.window_set_default_icon_from_file(const.PIXMAPS_PATH+"/sulfur-icon.png")
        except gobject.GError:
            pass
        mainApp = ManagerApplication()
        mainApp.init()
        gobject.threads_init()
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()
        Equo.destroy()
    except SystemExit:
        print "Quit by User"
        mainApp.destroy()
        raise SystemExit(0)
    except KeyboardInterrupt:
        print "Quit by User (KeyboardInterrupt)"
        mainApp.destroy()
        raise SystemExit(0)
    except: # catch other exception and write it to the logger.
        my = ExceptionDialog()
        my.show()

    raise SystemExit(0)
