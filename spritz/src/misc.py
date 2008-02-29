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

import logging
import gtk
import gobject
import time
from i18n import _
import packages
from entropyConstants import *


class const:
    ''' This Class contains all the Constants in Yumex'''
    __spritz_version__   = etpConst['entropyversion']
    # Paths
    MAIN_PATH = os.path.abspath( os.path.dirname( sys.argv[0] ) );
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
    PAGES = {
       'packages'  : PAGE_PKG,
       'repos'     : PAGE_REPOS,
       'output'    : PAGE_OUTPUT,
       'queue'     : PAGE_QUEUE,
       'group'     : PAGE_GROUP,
       'filesconf' : PAGE_FILESCONF
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

class SpritzQueue:
    def __init__(self):
        self.logger = logging.getLogger('yumex.YumexQueue')
        self.packages = {}
        self.groups = {}
        self.before = []
        self.keyslotFilter = set()
        self._keyslotFilter = set()
        self.clear()
        self.Entropy = None
        self.etpbase = None
        self.pkgView = None
        self.queueView = None
        import dialogs
        self.dialogs = dialogs


    def connect_objects(self, EquoConnection, etpbase, pkgView, ui):
        self.Entropy = EquoConnection
        self.etpbase = etpbase
        self.pkgView = pkgView
        self.ui = ui

    def clear( self ):
        self.packages.clear()
        self.packages['i'] = []
        self.packages['u'] = []
        self.packages['r'] = []
        self.packages['rr'] = []
        self.groups.clear()
        self.groups['i'] = []
        self.groups['r'] = []
        del self.before[:]
        self.keyslotFilter.clear()

    def get( self, action = None ):
        if action == None:
            return self.packages
        else:
            return self.packages[action]

    def total(self):
        size = 0
        for key in self.packages:
            size += len(self.packages[key])
        return size

    def keySlotFiltering(self, queue):

        blocked = []
        for pkg in queue:
            match = pkg.matched_atom
            if type(match[1]) is int: # installed package
                dbconn = self.Entropy.clientDbconn
            else:
                dbconn = self.Entropy.openRepositoryDatabase(match[1])
            keyslot = dbconn.retrieveKeySlot(match[0])
            if keyslot in self.keyslotFilter:
                blocked.append(pkg)
            else:
                self._keyslotFilter.add(keyslot)

        return blocked

    def showKeySlotErrorMessage(self, blocked):

        confirmDialog = self.dialogs.ConfirmationDialog( self.ui.main,
                    list(blocked),
                    top_text = _("Attention"),
                    sub_text = _("There are packages that can't be installed at the same time, thus are blocking your request:"),
                    bottom_text = "",
                    cancel = False
        )
        confirmDialog.run()
        confirmDialog.destroy()


    def add(self, pkgs):

        if type(pkgs) is not list:
            pkgs = [pkgs]

        action = [pkgs[0].queued]

        if action[0] in ("u","i","rr"): # update/install

            self._keyslotFilter.clear()
            blocked = self.keySlotFiltering(pkgs)
            if blocked:
                self.showKeySlotErrorMessage(blocked)
                return 1,0

            action = ["u","i","rr"]
            tmpqueue = [x for x in pkgs if x not in self.packages['u']+self.packages['i']+self.packages['rr']]
            xlist = [x.matched_atom for x in self.packages['u']+self.packages['i']+self.packages['rr']+tmpqueue]
            xlist = list(set(xlist))
            status = self.elaborateInstall(xlist,action,False)
            if status == 0:
                self.keyslotFilter |= self._keyslotFilter
            return status,0

        else: # remove

            mypkgs = []
            for pkg in pkgs:
                status = self.checkSystemPackage(pkg)
                if status:
                    mypkgs.append(pkg)
            pkgs = mypkgs

            if not pkgs:
                return -2,1

            tmpqueue = [x for x in pkgs if x not in self.packages['r']]
            xlist = [x.matched_atom[0] for x in self.packages['r']+tmpqueue]
            status = self.elaborateRemoval(xlist,False)
            return status,1

    def elaborateInstall(self, xlist, actions, deep_deps):
        (runQueue, removalQueue, status) = self.Entropy.retrieveInstallQueue(xlist,False,deep_deps)
        if status == -2: # dependencies not found
            confirmDialog = self.dialogs.ConfirmationDialog( self.ui.main,
                        runQueue,
                        top_text = _("Attention"),
                        sub_text = _("Some dependencies couldn't be found. It can either be because they are masked or because they aren't in any active repository."),
                        bottom_text = "",
                        cancel = False,
                        simpleList = True 
            )
            confirmDialog.run()
            confirmDialog.destroy()
            return -10
        elif status == 0:
            # runQueue
            remove_todo = []
            install_todo = []
            if runQueue:
                #print "runQueue",runQueue
                for dep_pkg in self.etpbase.getRawPackages('updates') + \
                    self.etpbase.getRawPackages('available') + \
                    self.etpbase.getRawPackages('reinstallable'):
                        for matched_atom in runQueue:
                            if (dep_pkg.matched_atom == matched_atom) and \
                                (dep_pkg not in self.packages[actions[0]]+self.packages[actions[1]]+self.packages[actions[2]]) and \
                                (dep_pkg not in install_todo):
                                    install_todo.append(dep_pkg)

            # removalQueue
            if removalQueue:
                for rem_pkg in self.etpbase.getRawPackages('installed'):
                    for matched_atom in removalQueue:
                        if rem_pkg.matched_atom == (matched_atom,0) and (rem_pkg not in remove_todo):
                            remove_todo.append(rem_pkg)

            if install_todo or remove_todo:
                ok = True

                items_before = [x for x in install_todo+remove_todo if x not in self.before]

                if len(items_before) > 1:
                    ok = False
                    size = 0
                    for x in install_todo:
                        size += x.disksize
                    for x in remove_todo:
                        size -= x.disksize
                    if size > 0:
                        bottom_text = _("Needed disk space")
                    else:
                        size = abs(size)
                        bottom_text = _("Freed disk space")
                    size = self.Entropy.entropyTools.bytesIntoHuman(size)
                    confirmDialog = self.dialogs.ConfirmationDialog( self.ui.main,
                                                                    install_todo+remove_todo,
                                                                    top_text = _("These are the packages that would be installed/updated"),
                                                                    bottom_text = bottom_text,
                                                                    bottom_data = size
                                                                  )
                    result = confirmDialog.run()
                    if result == -5: # ok
                        ok = True
                    confirmDialog.destroy()

                if ok:
                    for rem_pkg in remove_todo:
                        rem_pkg.queued = rem_pkg.action
                        if rem_pkg not in self.packages['r']:
                            self.packages['r'].append(rem_pkg)
                    for dep_pkg in install_todo:
                        dep_pkg.queued = dep_pkg.action
                        if dep_pkg not in self.packages[dep_pkg.action]:
                            self.packages[dep_pkg.action].append(dep_pkg)
                else:
                    return -10

        return status

    def elaborateRemoval(self, list, nodeps):
        if nodeps:
            return 0
        removalQueue = self.Entropy.retrieveRemovalQueue(list)
        if removalQueue:
            todo = []
            for rem_pkg in self.etpbase.getRawPackages('installed'):
                for matched_atom in removalQueue:
                    if rem_pkg.matched_atom == (matched_atom,0):
                        if rem_pkg not in self.packages[rem_pkg.action] and (rem_pkg not in todo):
                            todo.append(rem_pkg)
            if todo:
                ok = True
                items_before = [x for x in todo if x not in self.before]
                if len(items_before) > 1:
                    ok = False
                    size = 0
                    for x in todo:
                        size += x.disksize
                    if size > 0:
                        bottom_text = _("Freed space")
                    else:
                        size = abs(size)
                        bottom_text = _("Needed space")
                    size = self.Entropy.entropyTools.bytesIntoHuman(size)
                    confirmDialog = self.dialogs.ConfirmationDialog( self.ui.main,
                                                                    todo,
                                                                    top_text = _("These are the packages that would be removed"),
                                                                    bottom_text = bottom_text,
                                                                    bottom_data = size
                                                                  )
                    result = confirmDialog.run()
                    if result == -5: # ok
                        ok = True
                    confirmDialog.destroy()

                if ok:
                    for rem_pkg in todo:
                        rem_pkg.queued = rem_pkg.action
                        if rem_pkg not in self.packages[rem_pkg.action]:
                            self.packages[rem_pkg.action].append(rem_pkg)
                else:
                    return -10

        return 0


    def checkSystemPackage(self, pkg):
        # check if it's a system package
        valid = self.Entropy.validatePackageRemoval(pkg.matched_atom[0])
        if not valid:
            pkg.queued = None
        return valid

    def remove(self, pkgs):

        one = False
        if type(pkgs) is not list:
            one = True
            pkgs = [pkgs]

        action = [pkgs[0].action]
        if action[0] in ("u","i","rr"): # update/install

            action = ["u","i","rr"]

            xlist = [x.matched_atom for x in self.packages['u']+self.packages['i']+self.packages['rr'] if x not in pkgs]
            self.before = self.packages['u'][:]+self.packages['i'][:]+self.packages['rr'][:]
            for pkg in self.before:
                pkg.queued = None
            del self.packages['u'][:]
            del self.packages['i'][:]
            del self.packages['rr'][:]

            if xlist:

                status = self.elaborateInstall(xlist,action,False)

                del self.before[:]
                return status,0

            del self.before[:]
            return 0,0

        else:

            xlist = [x.matched_atom[0] for x in self.packages[action[0]] if x not in pkgs]
            self.before = self.packages[action[0]][:]
            # clean, will be refilled
            for pkg in self.before:
                pkg.queued = None
            del self.packages[action[0]][:]

            if xlist:

                status = self.elaborateRemoval(xlist,False)
                if status == -10:
                    del self.packages[action[0]][:]
                    self.packages[action[0]] = self.before[:]

                del self.before[:]
                return status,1

            del self.before[:]
            return 0,1

    def addGroup( self, grp, action):
        list = self.groups[action]
        if not grp in list:
            list.append( grp )
        self.groups[action] = list

    def removeGroup( self, grp, action):
        list = self.groups[action]
        if grp in list:
            list.remove( grp )
        self.groups[action] = list

    def hasGroup(self,grp):
        for action in ['i','r']:
            if grp in self.groups[action]:
                return action
        return None

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
    color_install = 'darkgreen'
    color_update = 'red'
    color_normal = 'black'
    color_obsolete = 'blue'
    filelist = True
    changelog = False
    disable_repo_page = False
    branding_title = 'Spritz Package Manager'

def cleanMarkupSting(msg):
    msg = str(msg) # make sure it is a string
    msg = gobject.markup_escape_text(msg)
    #msg = msg.replace('@',' AT ')
    #msg = msg.replace('<','[')
    #msg = msg.replace('>',']')
    return msg

class fakeoutfile:
    """
    A fake output file object.  It sends output to a GTK TextView widget,
    and if asked for a file number, returns one set on instance creation
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
        #sys.stdout.write(s+"\n")

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
    A fake input file object.  It receives input from a GTK TextView widget,
    and if asked for a file number, returns one set on instance creation
    """

    def __init__(self, fn):
        self.fn = fn
    def close(self): pass
    flush = close
    def fileno(self):    return self.fn
    def isatty(self):    return False
    def read(self, a):   return self.readline()
    def readline(self): ## just a fake
        return os.read(self.fn,2048)
    def readlines(self): return []
    def write(self, s):  return None
    def writelines(self, l): return None
    def seek(self, a):   raise IOError, (29, 'Illegal seek')
    def tell(self):      raise IOError, (29, 'Illegal seek')
    truncate = tell

from htmlentitydefs import codepoint2name
def unicode2htmlentities(u):
   htmlentities = list()
   for c in u:
      if ord(c) < 128:
         htmlentities.append(c)
      else:
         htmlentities.append('&%s;' % codepoint2name[ord(c)])
   return ''.join(htmlentities)