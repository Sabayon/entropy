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

import os
import sys

import gtk
import gtk.glade
import gobject
from entropy.const import const_debug_write
from entropy.misc import ParallelTask

FORK_PIDS = []

CURRENT_CURSOR = None

STATUS_BAR_CONTEXT_IDS = {
    'UGC': 1001,
}

class UI(gtk.glade.XML):
    """Base class for UIs loaded from glade."""

    def __init__(self, filename, rootname,domain=None):
        """Initialize a new instance.
        `filename' is the name of the .glade file containing the UI hierarchy.
        `rootname' is the name of the topmost widget to be loaded.
        `gladeDir' is the name of the directory, relative to the Python
        path, in which to search for `filename'."""
        if domain:
            gtk.glade.XML.__init__(self, filename, rootname, domain)
        else:
            gtk.glade.XML.__init__(self, filename, rootname)
        self.filename = filename
        self.root = self.get_widget(rootname)

    def __getattr__(self, name):
        """Look up an as-yet undefined attribute, assuming it's a widget."""
        result = self.get_widget(name)
        if result is None:
            raise AttributeError("Can't find widget %s in %s.\n" %
                                 (repr(name), repr(self.filename)))

        # Cache the widget to speed up future lookups.  If multiple
        # widgets in a hierarchy have the same name, the lookup
        # behavior is non-deterministic just as for libglade.
        setattr(self, name, result)
        return result

class Controller:

    """Base class for all controllers of glade-derived UIs."""
    def __init__(self, ui):
        """Initialize a new instance.
        `ui' is the user interface to be controlled."""
        self.ui = ui
        self.ui.signal_autoconnect(self._getAllMethods())

    def _getAllMethods(self):
        """Get a dictionary of all methods in self's class hierarchy."""
        result = {}

        # Find all callable instance/class attributes.  This will miss
        # attributes which are "interpreted" via __getattr__.  By
        # convention such attributes should be listed in
        # self.__methods__.
        allAttrNames = list(self.__dict__.keys()) + self._getAllClassAttributes()
        for name in allAttrNames:
            value = getattr(self, name)
            if hasattr(value, '__call__'):
                result[name] = value
        return result

    def _getAllClassAttributes(self):
        """Get a list of all attribute names in self's class hierarchy."""
        nameSet = {}
        for currClass in self._getAllClasses():
            nameSet.update(currClass.__dict__)
        result = list(nameSet.keys())
        return result

    def _getAllClasses(self):
        """Get all classes in self's heritage."""
        result = [self.__class__]
        i = 0
        while i < len(result):
            currClass = result[i]
            result.extend(list(currClass.__bases__))
            i = i + 1
        return result

def busy_cursor(mainwin, insensitive=False, cur = gtk.gdk.Cursor(gtk.gdk.WATCH)):
    ''' Set busy cursor in mainwin and make it insensitive if selected '''
    mainwin.window.set_cursor(cur)
    global CURRENT_CURSOR
    CURRENT_CURSOR = cur
    if insensitive:
        mainwin.set_sensitive(False)

def normal_cursor(mainwin):
    ''' Set Normal cursor in mainwin and make it sensitive '''
    if mainwin.window != None:
        mainwin.window.set_cursor(None)
        mainwin.set_sensitive(True)
    global CURRENT_CURSOR
    CURRENT_CURSOR = None

def fork_function(child_function, parent_function):
    # Uber suber optimized stuffffz

    def do_wait(pid):
        os.waitpid(pid, 0)
        FORK_PIDS.remove(pid)
        gobject.idle_add(parent_function)

    pid = os.fork()
    if pid != 0:
        const_debug_write(__name__, "_fork_function: enter %s" % (
            child_function,))
        FORK_PIDS.append(pid)
        if parent_function is not None:
            task = ParallelTask(do_wait, pid)
            task.start()
        const_debug_write(__name__, "_fork_function: leave %s" % (
            child_function,))
    else:
        sys.excepthook = sys.__excepthook__
        child_function()
        os._exit(0)