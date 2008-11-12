#!/usr/bin/python -tt
# -*- coding: iso-8859-1 -*-
#    It was: Yum Exteder (yumex) - A GUI for yum
#    Copyright (C) 2006 Tim Lauridsen < tim<AT>yum-extender<DOT>org > 
#    Now is: Spritz (Entropy Interface)
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
import traceback
import commands
import time

# Entropy Imports
sys.path.insert(0,"../../libraries")
sys.path.insert(1,"../../client")
sys.path.insert(2,"/usr/lib/entropy/libraries")
sys.path.insert(3,"/usr/lib/entropy/client")
from entropyConstants import *
import entropyTools
from packages import EntropyPackages
from entropyapi import EquoConnection, QueueExecutor
from entropy import ErrorReportInterface
from entropy_i18n import _

# Spritz Imports
import gtk, gobject
from etpgui.widgets import UI, Controller, SpritzConsole
from etpgui import *
from spritz_setup import SpritzConf, const, fakeoutfile, fakeinfile, cleanMarkupString
from misc import SpritzQueue
from dialogs import *
from spritz import SpritzProgress

class MyRepositoryManager(RepositoryManagerMenu):

    def __init__(self, Equo, parent):
        RepositoryManagerMenu.__init__(self, Equo, parent)

    def on_repoManagerClose_clicked(self, *args, **kwargs):
        self.QueueUpdater.kill()
        self.OutputUpdater.kill()
        self.PinboardUpdater.kill()
        self.destroy()
        raise SystemExit(1)

class ManagerApplication(Controller):
    def __init__(self):
        #ui = UI( const.GLADE_FILE , 'main', 'entropy' )
        #ui.main.hide()
        #Controller.__init__(self, ui, None, None)
        self.ui = None
        self.progressLogWrite = sys.stdout
        self.output = sys.stdout
        self.Equo = EquoConnection
        #self.progress = SpritzProgress(self.ui, self.dummy_func, self)
        self.progress = None
        self.Equo.connect_to_gui(self)
        mymenu = MyRepositoryManager(self.Equo, None)
        rc = mymenu.load()
        if not rc:
            del mymenu
            raise SystemExit(1)

    def dummy_func(self, *args, **kwargs):
        pass

if __name__ == "__main__":

    def killThreads():
        # kill threads
        threads = entropyTools.threading.enumerate()
        for thread in threads:
            if thread.getName().startswith("download::"): # equo current download speed thread
                thread.kill()

    gtkEventThread = ProcessGtkEventsThread()
    try:
        gtkEventThread.start()
        try:
            gtk.window_set_default_icon_from_file(const.PIXMAPS_PATH+"/spritz-icon.png")
        except gobject.GError:
            pass
        mainApp = ManagerApplication()
        gobject.threads_init()
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()
        killThreads()
    except SystemExit:
        print "Quit by User"
        gtkEventThread.doQuit()
        killThreads()
        raise SystemExit
    except KeyboardInterrupt:
        print "Quit by User (KeyboardInterrupt)"
        gtkEventThread.doQuit()
        killThreads()
        raise SystemExit
    except: # catch other exception and write it to the logger.

        etype = sys.exc_info()[0]
        evalue = sys.exc_info()[1]
        etb = traceback.extract_tb(sys.exc_info()[2])
        errmsg = 'Error Type: %s \n' % str(etype)
        errmsg += 'Error Value: %s \n' % str(evalue)
        for tub in etb:
            f,l,m,c = tub # file,lineno, function, codeline
            errmsg += '  File : %s , line %s, in %s\n' % (f,str(l),m)
            errmsg += '    %s \n' % c

        conntest = entropyTools.get_remote_data(etpConst['conntestlink'])
        rc, (name,mail,description) = errorMessage(
            None,
            _( "Exception caught" ),
            _( "Spritz crashed! An unexpected error occured." ),
            errmsg,
            showreport = conntest
        )
        if rc == -1:
            error = ErrorReportInterface()
            error.prepare(errmsg, name, mail, description = description)
            result = error.submit()
            if result:
                okDialog(None,_("Your report has been submitted successfully! Thanks a lot."))
            else:
                okDialog(None,_("Cannot submit your report. Not connected to Internet?"))
        gtkEventThread.doQuit()
        killThreads()
        raise SystemExit(1)

    gtkEventThread.doQuit()
    killThreads()
