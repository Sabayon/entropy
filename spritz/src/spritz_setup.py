#!/usr/bin/python -tt
# -*- coding: iso-8859-1 -*-
#    Yum Exteder (yumex) - A GUI for yum
#    Copyright (C) 2006 Tim Lauridsen < tim<AT>yum-extender<DOT>org > 
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

import os, sys
from entropyConstants import *
from entropy_i18n import _

class const:
    ''' This Class contains all the Constants in Yumex'''
    __spritz_version__   = etpConst['entropyversion']
    # Paths
    MAIN_PATH = os.path.abspath( os.path.dirname( sys.argv[0] ) )
    GLADE_FILE = MAIN_PATH+'/spritz.glade'
    if not os.path.isfile(GLADE_FILE):
        MAIN_PATH = '/usr/lib/entropy/spritz'
        GLADE_FILE = MAIN_PATH+'/spritz.glade'
    if MAIN_PATH == '/usr/lib/entropy/spritz':
        PIXMAPS_PATH = '/usr/share/pixmaps/spritz'
    else:
        PIXMAPS_PATH = MAIN_PATH+'/../gfx'
    if MAIN_PATH == '/usr/lib/entropy/spritz':
        ICONS_PATH = '/usr/share/pixmaps/spritz'
    else:
        ICONS_PATH = MAIN_PATH+'/pixmaps'

    # package categories
    PACKAGE_CATEGORIES = [
        "None",
        "Groups",
        "RPM Groups",
        "Age"]

    DAY_IN_SECONDS = 86400
    # Page -> Notebook page numbers
    PAGE_REPOS = 0
    PAGE_PKG = 1
    PAGE_OUTPUT = 2
    PAGE_GROUP = 3
    PAGE_QUEUE = 4
    PAGE_FILESCONF = 5
    PAGE_GLSA = 6
    PAGES = {
       'packages'  : PAGE_PKG,
       'repos'     : PAGE_REPOS,
       'output'    : PAGE_OUTPUT,
       'queue'     : PAGE_QUEUE,
       'group'     : PAGE_GROUP,
       'filesconf' : PAGE_FILESCONF,
       'glsa'      : PAGE_GLSA
    }

    PACKAGE_PROGRESS_STEPS = ( 0.1, # Depsolve
                               0.5, # Download
                               0.1, # Transaction Test
                               0.3 ) # Running Transaction

    SETUP_PROGRESS_STEPS = ( 0.1, # Yum Config
                             0.2, # Repo Setup
                             0.1, # Sacksetup  
                             0.2, # Updates 
                             0.1, # Group 
                             0.3) # get package Lists

    CREDITS = (
           (('Spritz Package Manager - %s' % __spritz_version__),
           ('Copyright 2008','Fabio Erculiani')),

           (_("Programming:"),
           ("Fabio Erculiani",)),

           (_("Yum Extender Programmers:"),
           ("Tim Lauridsen", "David Zamirski")),

           (_("Translation:"),
           ("Tim Lauridsen (Danish)",
            "MATSUURA Takanori (Japanese)",
            "Rodrigo Padula de Oliveira (Brazilian)",
            "Eric Tanguy (French)",
            "Soohyung Cho (Korean)",
            "Danilo (Italian)",
            "Serta . YILDIZ (Turkish)",
            "Dawid Zamirski, Patryk Zawadzki (Polish)",
            "Piotr Drag (Polish)",
            "Tero Hietanen (Finnish)",
            "Dieter Komendera (German)",
            "Maxim Dziumanenko (Ukrainian)",
            "Novotny Lukas (Czech)",
            "Szll Tams (Hungarian)",
            "Leonid Kanter, Nikita (Russian)",   
            "Diego Alonso (Spanish)",   
            "A Singh Alam (Punjabi)",    
            "Hao Song (Chinese(Simplified))")),


           (_("Dedicated to:"),
                ("Sergio Erculiani",)
           )

          )

class SpritzConf:
    """ Yum Extender Config Setting"""
    autorefresh = True
    recentdays = 14
    debug = False
    plugins = True
    usecache = False
    proxy = ""
    font_console = 'Monospace 8'
    font_pkgdesc = 'Monospace 8'
    color_console_background = '#FFFFFF'
    color_console_font = '#000000'
    color_pkgdesc = '#68228B'
    color_normal = 'black'
    color_install = 'darkgreen'
    color_update = 'darkgreen'
    color_obsolete = 'red'
    filelist = True
    changelog = False
    disable_repo_page = False
    branding_title = 'Spritz Package Manager'
    dummy_empty = 0
    dummy_category = 1

def cleanMarkupSting(msg):
    import gobject
    msg = str(msg) # make sure it is a string
    msg = gobject.markup_escape_text(msg)
    #msg = msg.replace('@',' AT ')
    #msg = msg.replace('<','[')
    #msg = msg.replace('>',']')
    return msg

from htmlentitydefs import codepoint2name
def unicode2htmlentities(u):
   htmlentities = list()
   for c in u:
      if ord(c) < 128:
         htmlentities.append(c)
      else:
         htmlentities.append('&%s;' % codepoint2name[ord(c)])
   return ''.join(htmlentities)

class fakeoutfile:
    """
    A general purpose fake output file object.
    """

    def __init__(self, fn):
        self.fn = fn
        self.text_written = []

    def close(self):
        pass

    def flush(self):
        self.close()

    def fileno(self):
        return self.fn

    def isatty(self):
        return False

    def read(self, a):
        return ''

    def readline(self):
        return ''

    def readlines(self):
        return []

    def write(self, s):
        os.write(self.fn,s)
        self.text_written.append(s)
        # cut at 1024 entries
        if len(self.text_written) > 1024:
            self.text_written = self.text_written[-1024:]

    def write_line(self, s):
        self.write(s)

    def writelines(self, l):
        for s in l:
            self.write(s)

    def seek(self, a):
        raise IOError, (29, 'Illegal seek')

    def tell(self):
        raise IOError, (29, 'Illegal seek')

    def truncate(self):
        self.tell()

class fakeinfile:
    """
    A general purpose fake input file object.
    """
    def __init__(self, fn):
        self.fn = fn

    def close(self):
        pass

    flush = close

    def fileno(self):
        return self.fn

    def isatty(self):
        return False

    def read(self, a):
        return self.readline(count = a)

    def readline(self, count = 2048):
        return os.read(self.fn,count)

    def readlines(self): return []

    def write(self, s):
        return None

    def writelines(self, l):
        return None

    def seek(self, a):
        raise IOError, (29, 'Illegal seek')

    def tell(self):
        raise IOError, (29, 'Illegal seek')

    truncate = tell