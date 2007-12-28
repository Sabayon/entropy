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

import yum
import gobject
import gtk
import pango
import sys
import time
import logging

from yum.packages import YumInstalledPackage

#
# Classes
#
            

class TextViewLogHandler(logging.Handler):
    ''' Python logging handler for writing in a TextViewConsole'''
    def __init__(self,console,doGTK=False):
        logging.Handler.__init__(self)
        self.console = console
        self.doGTK = doGTK
        
        #TextViewConsole.__init__(self,textview)
        
    def emit(self,record):   
        while gtk.events_pending():      # process gtk events
           gtk.main_iteration()    
        msg = self.format(record)
        if self.console:
            if self.doGTK:
                doGtkEvents()
            if record.levelno < 40:
                self.console.write_line("%s\n" % msg)
            else:
                self.console.write_line("%s\n" % msg,self.console.style_err)  
        #print msg
        
        
    
#
# Functions
#    
def doLoggerSetup(console,logroot,logfmt='%(message)s',loglvl=logging.DEBUG):
    logger = logging.getLogger(logroot)
    logger.setLevel(loglvl)
    formatter = logging.Formatter(logfmt, "%H:%M:%S")
    handler = TextViewLogHandler(console)
    handler.setFormatter(formatter)
    handler.propagate = False
    logger.addHandler(handler)
    
def busyCursor(mainwin,insensitive=False):
    ''' Set busy cursor in mainwin and make it insensitive if selected '''
    mainwin.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
    if insensitive:
        mainwin.set_sensitive(False)
    doGtkEvents()

def normalCursor(mainwin):
    ''' Set Normal cursor in mainwin and make it sensitive '''
    if mainwin.window != None:
        mainwin.window.set_cursor(None)
        mainwin.set_sensitive(True)        
    doGtkEvents()
    
def doGtkEvents():
    while gtk.events_pending():      # process gtk events
        gtk.main_iteration()

# from output.py (yum)
def format_number(number, SI=0, space=' '):
    """Turn numbers into human-readable metric-like numbers"""
    symbols = ['',  # (none)
                'k', # kilo
                'M', # mega
                'G', # giga
                'T', # tera
                'P', # peta
                'E', # exa
                'Z', # zetta
                'Y'] # yotta

    if SI: step = 1000.0
    else: step = 1024.0

    thresh = 999
    depth = 0

    # we want numbers between 
    while number > thresh:
        depth  = depth + 1
        number = number / step

    # just in case someone needs more than 1000 yottabytes!
    diff = depth - len(symbols) + 1
    if diff > 0:
        depth = depth - diff
        number = number * thresh**depth

    if type(number) == type(1) or type(number) == type(1L):
        format = '%i%s%s'
    elif number < 9.95:
        # must use 9.95 for proper sizing.  For example, 9.99 will be
        # rounded to 10.0 with the .1f format string (which is too long)
        format = '%.1f%s%s'
    else:
        format = '%.0f%s%s'

    return(format % (number, space, symbols[depth]))
    
    