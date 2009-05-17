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

# Authors:
#    Tim Lauridsen <tla@rasmil.dk>

import sys, os, threading
import gtk.glade,gtk.gdk
import pango
import etpgui
import gobject
from sulfur_setup import const, SulfurConf
import vte

def hex2float(myhex):
     ret = []
     for i in range(4):
             ic = int(myhex[i])
             ret.append( ic / 255.0 )
     return ret

class TransparentWindow(gtk.Window):
    __gsignals__ = {
            'expose-event':   'override',
            'screen-changed': 'override',
    }

    def __init__(self):
        import cairo
        self.cairo = cairo
        gtk.Window.__init__(self)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.connect('button-press-event', self.on_button_press)
        self.do_screen_changed()

    def on_button_press(self, widget, event):
        self.begin_move_drag(
                        event.button,
                        int(event.x_root),
                        int(event.y_root),
                        event.time)

    def render_rect(self, cr, x, y, w, h, o):
        # Crea un rettangolo con i bordi arrotondati
        x0 = x
        y0 = y
        rect_width = w
        rect_height = h
        radius = 10 + o

        x1 = x0 + rect_width
        y1 = y0 + rect_height
        cr.move_to(x0, y0 + radius)
        cr.curve_to(x0, y0, x0, y0, x0 + radius, y0)
        cr.line_to(x1 - radius, y0)
        cr.curve_to(x1, y0, x1, y0, x1, y0 + radius)
        cr.line_to(x1 , y1)
        cr.line_to (x0 , y1)
        cr.close_path()

    def do_expose_event(self, event):
        cr = self.window.cairo_create()

        if self.supports_alpha:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.0)
        else:
                cr.set_source_rgb(1.0, 1.0, 1.0)

        cr.set_operator(self.cairo.OPERATOR_SOURCE)
        cr.paint()


        (width, height) = self.get_size()
        cr.move_to(0, 0)
        cr.set_line_width(1.0)

        cr.set_operator(self.cairo.OPERATOR_OVER)

        pat = self.cairo.LinearGradient(0.0, 0.0, 0.0, height)

        ex_list = [0xA1, 0xA8, 0xBB, 0xEC]
        col = hex2float(ex_list)
        pat.add_color_stop_rgba(0.0, col[0], col[1], col[2], col[3])

        ex_list = [0x14, 0x1E, 0x3C, 0xF3]
        col = hex2float(ex_list)
        pat.add_color_stop_rgba(1.0, col[0], col[1], col[2], col[3])

        self.render_rect(cr, 0, 0, width, height, 10)
        cr.set_source(pat)
        cr.fill()

        ex_list = [0xFF, 0xFF, 0xFF, 0x4e]
        col = hex2float(ex_list)
        cr.set_source_rgba(col[0], col[1], col[2], col[3])
        self.render_rect(cr, 1.5, 1.5, width - 3 , height - 3, 10)
        cr.stroke()

        # border
        ex_list = [0x00, 0x15, 0x1F, 0xe0]
        col = hex2float(ex_list)
        cr.set_source_rgba(col[0], col[1], col[2], col[3])
        self.render_rect(cr, 0.5, 0.5, width - 1 , height - 1, 10)
        cr.stroke()

        ex_list = [0xFF, 0xFF, 0xFF, 0xFF]
        col = hex2float(ex_list)
        cr.set_source_rgba(col[0], col[1], col[2], col[3])
        self.render_rect(cr, 0, 0, width , height, 10)
        cr.stroke()

        pat = self.cairo.LinearGradient(0.0, 0.0, 0.0, height)
        cr.set_source(pat)
        ex_list = [0xFF, 0xFF, 0xFF, 0xbb]
        col = hex2float(ex_list)
        pat.add_color_stop_rgba(0.0, col[0], col[1], col[2], col[3])

        ex_list = [0x00, 0x00, 0x10, 0xaa]
        col = hex2float(ex_list)
        pat.add_color_stop_rgba(0.2, col[0], col[1], col[2], col[3])
        self.render_rect(cr, 0, 0, width, 20, 10)
        cr.fill()

        children = self.get_children()
        for c in children:  self.propagate_expose(c, event)

    def do_screen_changed(self, old_screen=None):
        screen = self.get_screen()
        if self.is_composited():
            colormap = screen.get_rgba_colormap()
            self.supports_alpha = True
        else:
            # no alpha support
            colormap = screen.get_rgb_colormap()
            self.supports_alpha = False
        self.set_colormap(colormap)

class CellRendererStars(gtk.GenericCellRenderer):
    __gproperties__ = {
            "custom": (gobject.TYPE_OBJECT, "Custom",
            "Custom", gobject.PARAM_READWRITE),
    }

    def __init__(self):
        self.__gobject_init__()
        self.value = -1
        self.value_voted = 0

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def on_render(self, window, widget, background_area, cell_area, expose_area, flags):

        (x_offset, y_offset, width, height) = self.on_get_size(widget, cell_area)
        if isinstance(window,gtk.gdk.Window):
            widget.style.paint_box(window,
                                gtk.STATE_NORMAL,
                                gtk.SHADOW_IN,
                                None, widget, "trough",
                                cell_area.x+x_offset,
                                cell_area.y+y_offset,
                                width, height)
        if ((self.value > -1) and (self.value < 6)) or (self.value_voted > 0):

            xt = widget.style.xthickness
            empty = gtk.Image()
            empty.set_from_file(const.empty_background)
            empty_buf = empty.get_pixbuf()

            if self.value_voted:
                star = gtk.Image()
                star.set_from_file(const.star_selected_pixmap)
            else:
                star = gtk.Image()
                star.set_from_file(const.star_normal_pixmap)

            star_empty = gtk.Image()
            star_empty.set_from_file(const.star_empty_pixmap)

            star_buf = star.get_pixbuf()
            star_empty_buf = star_empty.get_pixbuf()

            w, h = star_buf.get_width(),star_buf.get_height()
            myval = self.value
            if self.value_voted:
                myval = self.value_voted
            empty_buf = empty_buf.scale_simple(w*5,h+12,gtk.gdk.INTERP_BILINEAR)
            myvals = [0,w,w*2,w*3,w*4]
            cnt = 0
            while myval:
                star_buf.copy_area(0, 0, w, h, empty_buf, myvals[cnt], 6)
                myval -= 1
                cnt += 1
            myval = 5 - cnt
            while myval:
                star_empty_buf.copy_area(0, 0, w, h, empty_buf, myvals[cnt], 6)
                myval -= 1
                cnt += 1

            if empty_buf: window.draw_pixbuf(None, empty_buf, 0, 0, cell_area.x+x_offset+xt, cell_area.y+y_offset+xt, -1, -1)


    def on_get_size(self, widget, cell_area):
        xpad = self.get_property("xpad")
        ypad = self.get_property("ypad")
        if cell_area:
            width = cell_area.width
            height = cell_area.height
            x_offset = xpad
            y_offset = ypad
        else:
            width = self.get_property("width")
            height = self.get_property("height")
            if width == -1: width = 100
            if height == -1: height = 30
            width += xpad*2
            height += ypad*2
            x_offset = 0
            y_offset = 0
        return x_offset, y_offset, width, height


gobject.type_register(CellRendererStars)


class SulfurConsole(vte.Terminal):

    def __init__(self):
        vte.Terminal.__init__(self)
        self.reset()

    def _dosettings(self):
        imgpath = os.path.join(const.PIXMAPS_PATH,'sabayon-console-background.png')
        if os.path.isfile(imgpath):
            self.set_background_image_file(imgpath)
        self.set_background_saturation(0.4)
        self.set_opacity(65535)
        myfc = gtk.gdk.color_parse(SulfurConf.color_console_font)
        self.set_color_foreground(myfc)

    def reset (self):
        vte.Terminal.reset(self, True, True)
        self._dosettings()


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
                                 (`name`, `self.filename`))

        # Cache the widget to speed up future lookups.  If multiple
        # widgets in a hierarchy have the same name, the lookup
        # behavior is non-deterministic just as for libglade.
        setattr(self, name, result)
        return result

class Controller:
    """Base class for all controllers of glade-derived UIs."""
    def __init__(self, ui, addrepo_ui, wait_ui):
        """Initialize a new instance.
        `ui' is the user interface to be controlled."""
        self.ui = ui
        self.addrepo_ui = addrepo_ui
        self.wait_ui = wait_ui
        self.ui.signal_autoconnect(self._getAllMethods())

        if addrepo_ui != None:
            self.addrepo_ui.signal_autoconnect(self._getAllMethods())
            self.addrepo_ui.addRepoWin.set_transient_for(self.ui.main)

        if wait_ui != None:
            self.wait_ui.signal_autoconnect(self._getAllMethods())
            self.wait_ui.waitWindow.set_transient_for(self.ui.main)

    def _getAllMethods(self):
        """Get a dictionary of all methods in self's class hierarchy."""
        result = {}

        # Find all callable instance/class attributes.  This will miss
        # attributes which are "interpreted" via __getattr__.  By
        # convention such attributes should be listed in
        # self.__methods__.
        allAttrNames = self.__dict__.keys() + self._getAllClassAttributes()
        for name in allAttrNames:
            value = getattr(self, name)
            if callable(value):
                result[name] = value
        return result

    def _getAllClassAttributes(self):
        """Get a list of all attribute names in self's class hierarchy."""
        nameSet = {}
        for currClass in self._getAllClasses():
            nameSet.update(currClass.__dict__)
        result = nameSet.keys()
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

class _IdleObject(gobject.GObject):
    """
    Override gobject.GObject to always emit signals in the main thread
    by emmitting on an idle handler
    """
    def __init__(self):
        gobject.GObject.__init__(self)

    def emit(self, *args):
        gobject.idle_add(gobject.GObject.emit,self,*args)

class _FooThread(threading.Thread, _IdleObject):
    """
    Cancellable thread which uses gobject signals to return information
    to the GUI.
    """
    __gsignals__ =  { 
        "completed": (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, []),
    }

    def __init__(self, function, *args, **kwargs):
        threading.Thread.__init__(self)
        _IdleObject.__init__(self)
        self.func = function
        self.args = args
        self.kwargs = kwargs

    def cancel(self):
        """
        Threads in python are not cancellable, so we implement our own
        cancellation logic
        """
        self.cancelled = True

    def run(self):
        rc = self.func(*self.args,**self.kwargs)
        self.emit("completed")


