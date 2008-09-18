#!/usr/bin/python -tt
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

#    
# Authors:
#    Tim Lauridsen <tla@rasmil.dk>

import gobject
import gtk
import pango
import sys
import time
import logging
from threading import Thread,Event
import thread, random
CURRENT_CURSOR = None

def busyCursor(mainwin,insensitive=False, cur = gtk.gdk.Cursor(gtk.gdk.WATCH)):
    ''' Set busy cursor in mainwin and make it insensitive if selected '''
    mainwin.window.set_cursor(cur)
    global CURRENT_CURSOR
    CURRENT_CURSOR = cur
    if insensitive:
        mainwin.set_sensitive(False)
    doGtkEvents()

def normalCursor(mainwin):
    ''' Set Normal cursor in mainwin and make it sensitive '''
    if mainwin.window != None:
        mainwin.window.set_cursor(None)
        mainwin.set_sensitive(True)
    global CURRENT_CURSOR
    CURRENT_CURSOR = None
    doGtkEvents()

def doGtkEvents():
    while gtk.events_pending():      # process gtk events
        gtk.main_iteration()

class ProcessGtkEventsThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.__quit = False
        self.__active = Event()
        self.__active.clear()

    def run(self):
        while not self.__quit:
            while not self.__active.isSet():
                self.__active.wait()
            self.dosleep()
            if not gtk:
                continue
            while gtk.events_pending():      # process gtk events
                gtk.main_iteration()

    def dosleep(self):
        try:
            time.sleep(0.4)
        except:
            pass

    def doQuit(self):
        self.__quit = True
        self.__active.set()

    def startProcessing(self):
        self.__active.set()

    def endProcessing(self):
        self.__active.clear()

