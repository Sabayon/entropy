# -*- coding: utf-8 -*-
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
import shutil
import threading

import gtk
import gtk.glade
import gobject
from entropy.const import const_debug_write, const_drop_privileges, \
    const_regain_privileges, etpConst
from entropy.misc import ParallelTask
from entropy.core import Singleton
from sulfur.setup import const

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

def resize_image(max_width, image_path, new_image_path):
    shutil.copy2(image_path, new_image_path)
    img = gtk.Image()
    img.set_from_file(new_image_path)
    img_buf = img.get_pixbuf()
    w, h = img_buf.get_width(), img_buf.get_height()
    if w > max_width:
        # resize pix
        new_w = max_width
        new_h = new_w*h/w
        img_buf = img_buf.scale_simple(int(new_w),
            int(new_h), gtk.gdk.INTERP_BILINEAR)
        try:
            img_buf.save(new_image_path, "png")
        except gobject.GError:
            # libpng issue? try jpeg
            img_buf.save(new_image_path, "jpeg")
        del img_buf
    del img

def resize_image_height(max_height, image_path, new_image_path):
    shutil.copy2(image_path, new_image_path)
    img = gtk.Image()
    img.set_from_file(new_image_path)
    img_buf = img.get_pixbuf()
    w, h = img_buf.get_width(), img_buf.get_height()
    if h > max_height:
        # resize pix
        new_h = max_height
        new_w = new_h*w/h
        img_buf = img_buf.scale_simple(int(new_w),
            int(new_h), gtk.gdk.INTERP_BILINEAR)
        try:
            img_buf.save(new_image_path, "png")
        except gobject.GError:
            # libpng issue? try jpeg
            img_buf.save(new_image_path, "jpeg")
        del img_buf
    del img

def load_url(url):
    xdg_open = '/usr/bin/xdg-open'
    if os.access(xdg_open, os.X_OK):
        pid = os.fork()
        if pid == 0:
            # child
            os.execv(xdg_open, [xdg_open, url])
            os._exit(0)

def get_entropy_webservice(entropy_client, repository_id, tx_cb = None):
    """
    Get Entropy Web Services service object (ClientWebService).

    @param entropy_client: Entropy Client interface
    @type entropy_client: entropy.client.interfaces.Client
    @param repository_id: repository identifier
    @type repository_id: string
    @return: the ClientWebService instance
    @rtype: entropy.client.services.interfaces.ClientWebService
    @raise WebService.UnsupportedService: if service is unsupported by
        repository
    """
    factory = entropy_client.WebServices()
    webserv = factory.new(repository_id)
    if tx_cb is not None:
        webserv._set_transfer_callback(tx_cb)
    return webserv

class Privileges(Singleton):

    def init_singleton(self):
        self.__drop_privs = True
        self.__drop_privs_lock = threading.RLock()
        self.__with_stmt = 0

    def __enter__(self):
        """
        Hold the lock.
        """
        self.__drop_privs_lock.acquire()
        if self.__with_stmt < 1:
            self.regain()
        self.__with_stmt += 1

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Drop the lock.
        """
        if self.__with_stmt == 1:
            self.drop()
        self.__with_stmt -= 1
        self.__drop_privs_lock.release()

    def drop(self):
        """
        Drop process privileges. Setting unpriv_gid to etpConst['entropygid']
        makes Entropy UGC/Data cache handling working.
        """
        if self.__drop_privs:
            with self.__drop_privs_lock:
                const_drop_privileges(unpriv_gid = etpConst['entropygid'])
                const.setup()

    def regain(self):
        """
        Regain previously dropped process privileges.
        """
        if self.__drop_privs:
            with self.__drop_privs_lock:
                const_regain_privileges()
                const.setup()
