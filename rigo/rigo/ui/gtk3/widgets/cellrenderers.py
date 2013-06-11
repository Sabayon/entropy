# -*- coding: utf-8 -*-
"""
Copyright (C) 2011 Canonical
Copyright (C) 2012 Fabio Erculiani

Authors:
  Michael Vogt
  Matthew McGowan
  Fabio Erculiani

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; version 3.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""
from gi.repository import GLib, Gtk, Gdk, GObject, Pango

from threading import Lock, Timer

from rigo.em import Ems
from rigo.utils import escape_markup
from rigo.enums import Icons

from .stars import StarRenderer, StarSize


class CellButtonIDs:
    INFO = 0
    ACTION = 1


# custom cell renderer to support dynamic grow
class CellRendererAppView(Gtk.CellRendererText):

    # x, y offsets for the overlay icon
    OVERLAY_XO = OVERLAY_YO = 2

    # size of the install overlay icon
    OVERLAY_SIZE = 16

    # ratings
    MAX_STARS = 5

    @property
    def STAR_SIZE(self):
        return Ems.EM

    __gproperties__ = {
        'application' : (GObject.TYPE_PYOBJECT, 'document',
                         'an Entropy Package Match',
                         GObject.PARAM_READWRITE),

        'isactive'    : (bool,'isactive', 'is cell active/selected', False,
                         GObject.PARAM_READWRITE),
                     }

    def __init__(self, icons, layout, show_ratings,
                 overlay_icon_name, scrolling_cb=None):
        super(CellRendererAppView, self).__init__()

        self._is_scrolling = scrolling_cb
        if scrolling_cb is None:
            def _is_scrolling(): return False
            self._is_scrolling = _is_scrolling
        else:
            self._is_scrolling = scrolling_cb

        # geometry-state values
        self.pixbuf_width = 0
        self.apptitle_width = 0
        self.apptitle_height = 0
        self.normal_height = 0
        self.selected_height = 0
        self.show_ratings = show_ratings

        # button packing
        self.button_spacing = 0
        self._buttons = {Gtk.PackType.START: [],
                         Gtk.PackType.END:   []}
        self._all_buttons = {}

        # cache a layout
        self._layout = layout
        # star painter, paints stars
        self._stars = StarRenderer()
        self._stars.size = StarSize.SMALL

        # icon/overlay jazz
        try:
            self._installed = icons.load_icon(overlay_icon_name,
                                              self.OVERLAY_SIZE, 0)
        except GObject.GError:
            # icon not present in theme, probably because running uninstalled
            self._installed = icons.load_icon('emblem-system',
                                              self.OVERLAY_SIZE, 0)

    def _layout_get_pixel_width(self, layout):
        return layout.get_size()[0] / Pango.SCALE

    def _layout_get_pixel_height(self, layout):
        return layout.get_size()[1] / Pango.SCALE

    def _render_icon(self, cr, app, cell_area, xpad, ypad, is_rtl):

        # calc offsets so icon is nicely centered
        icon = self.model.get_icon(app, cached=self._is_scrolling())
        xo = (self.pixbuf_width - icon.get_width())/2

        if not is_rtl:
            x = cell_area.x + xo + xpad
        else:
            x = cell_area.x + cell_area.width + xo - self.pixbuf_width - xpad
        y = cell_area.y + ypad

        # draw appicon pixbuf
        Gdk.cairo_set_source_pixbuf(cr, icon, x, y)
        cr.paint()

        # draw overlay if application is installed
        if app.is_installed():
            if not is_rtl:
                x += (self.pixbuf_width - self.OVERLAY_SIZE + self.OVERLAY_XO)
            else:
                x -= self.OVERLAY_XO
            y += (self.pixbuf_width - self.OVERLAY_SIZE + self.OVERLAY_YO)
            Gdk.cairo_set_source_pixbuf(cr, self._installed, x, y)
            cr.paint()
        return

    def _render_summary(self, context, cr, app,
                        cell_area, layout, xpad, ypad,
                        star_width, is_rtl):

        layout.set_markup(app.get_markup(), -1)

        # work out max allowable layout width
        layout.set_width(-1)
        lw = self._layout_get_pixel_width(layout)
        max_layout_width = (cell_area.width - self.pixbuf_width -
                            3*xpad - star_width)

        max_layout_width = cell_area.width - self.pixbuf_width - 3*xpad

        if self.show_ratings:
            max_layout_width -= star_width+6*xpad

        if self.props.isactive:
            if app.get_transaction_progress() > 0:
                action_btn = self.get_button_by_name(CellButtonIDs.ACTION)
                max_layout_width -= (xpad + action_btn.width)

        if lw >= max_layout_width:
            layout.set_width((max_layout_width)*Pango.SCALE)
            layout.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            lw = max_layout_width

        # HACK{lxnay}: apparently, using Layout directly screws its internal
        # structure and overwrites random areas of the heap causing
        # random fuck ups.
        # But fortunately, this code just positions the stars in the canvas
        self.apptitle_width = cell_area.width - self.pixbuf_width - \
            10 * xpad - star_width
        self.apptitle_height = self.STAR_SIZE
        # WHACKY CODE:
        #apptitle_extents = layout.get_line_readonly(0).get_pixel_extents()[1]
        #self.apptitle_width = apptitle_extents.width
        #self.apptitle_height = apptitle_extents.height

        if not is_rtl:
            x = cell_area.x+2*xpad+self.pixbuf_width
        else:
            x = cell_area.x+cell_area.width-lw-self.pixbuf_width-2*xpad

        y = cell_area.y + ypad

        Gtk.render_layout(context, cr, x, y, layout)
        return

    def _render_rating(self, context, cr, app,
                       cell_area, layout, xpad, ypad,
                       star_width, star_height, is_rtl):

        def _still_visible():
            return self.model.visible(app.get_details().pkg)
        stats = app.get_review_stats(
            _still_visible_cb=_still_visible,
            cached=self._is_scrolling())

        if not stats:
            return
        sr = self._stars

        if not is_rtl:
            x = (cell_area.x + 7 * xpad + self.pixbuf_width +
                 self.apptitle_width)
        else:
            x = (cell_area.x + cell_area.width
                 - 7*xpad
                 - self.pixbuf_width
                 - self.apptitle_width
                 - star_width)

        star_size = self.STAR_SIZE
        y = cell_area.y + ypad + (self.apptitle_height - star_size)/2

        sr.rating = stats.ratings_average
        sr.render_star(context, cr, x, y)

        # and nr-reviews in parenthesis to the right of the title
        nreviews_int = stats.downloads_total
        nreviews = stats.downloads_total_markup
        size = app.get_details().humansize
        if nreviews_int < 0:
            s = "..."
        else:
            s = nreviews

        layout.set_markup("<small>%s\n%s</small>" % (s, size), -1)

        y += ypad + self.STAR_SIZE

        context.save()
        context.add_class("cellrenderer-avgrating-label")
        Gtk.render_layout(context, cr, x, y, layout)
        context.restore()
        return

    def _render_progress(self, context, cr, progress, cell_area, ypad, is_rtl):
        percent = progress * 0.01
        # per the spec, the progressbar should be the width of the action button
        action_btn = self.get_button_by_name(CellButtonIDs.ACTION)

        x, _, w, h = action_btn.allocation
        # shift the bar under the rating info
        y = cell_area.y + ypad + self.apptitle_height + self.STAR_SIZE
        y += ypad

        context.save()
        context.add_class("trough")

        Gtk.render_background(context, cr, x, y, w, h)
        Gtk.render_frame(context, cr, x, y, w, h)

        context.restore ()

        bar_size = w * percent

        context.save ()
        context.add_class ("progressbar")

        if (bar_size > 0):
            if is_rtl:
                x += (w - bar_size)
            Gtk.render_activity(context, cr, x, y, bar_size, h)

        context.restore ()
        return

    def _render_buttons(self,
            context, cr, cell_area, layout, xpad, ypad,
            is_rtl, is_available):

        # layout buttons and paint
        y = cell_area.y + cell_area.height - ypad
        spacing = self.button_spacing

        if not is_rtl:
            start = Gtk.PackType.START
            end = Gtk.PackType.END
            xs = cell_area.x + 2*xpad + self.pixbuf_width
            xb = cell_area.x + cell_area.width - xpad
        else:
            start = Gtk.PackType.END
            end = Gtk.PackType.START
            xs = cell_area.x + xpad
            xb = cell_area.x + cell_area.width - 2*xpad - self.pixbuf_width

        for btn in self._buttons[start]:
            btn.set_position(xs, y-btn.height)
            btn.render(context, cr, layout)
            xs += btn.width + spacing

        for btn in self._buttons[end]:
            xb -= btn.width
            btn.set_position(xb, y-btn.height)
            btn.render(context, cr, layout)

            xb -= spacing
        return

    def set_pixbuf_width(self, w):
        self.pixbuf_width = w
        return

    def set_button_spacing(self, spacing):
        self.button_spacing = spacing
        return

    def get_button_by_name(self, name):
        if name in self._all_buttons:
            return self._all_buttons[name]
        return None

    def get_buttons(self):
        btns = ()
        for k, v in self._buttons.items():
            btns += tuple(v)
        return btns

    def button_pack(self, btn, pack_type=Gtk.PackType.START):
        self._buttons[pack_type].append(btn)
        self._all_buttons[btn.name] = btn
        return

    def button_pack_start(self, btn):
        self.button_pack(btn, Gtk.PackType.START)
        return

    def button_pack_end(self, btn):
        self.button_pack(btn, Gtk.PackType.END)
        return

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_preferred_height_for_width(self, treeview, width):

        if not self.get_properties("isactive")[0]:
            return self.normal_height, self.normal_height

        return self.selected_height, self.selected_height

    def do_render(self, cr, widget, bg_area, cell_area, flags):
        pkg_match = self.props.application
        if not pkg_match:
            return

        self.model = widget.model
        app = self.model.get_application(pkg_match)

        context = widget.get_style_context()
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        star_width, star_height = self._stars.get_visible_size(context)
        is_rtl = widget.get_direction() == Gtk.TextDirection.RTL

        layout = self._layout
        context.save()

        self._render_icon(cr, app,
                          cell_area,
                          xpad, ypad,
                          is_rtl)

        self._render_summary(context, cr, app,
                             cell_area,
                             layout,
                             xpad, ypad,
                             star_width,
                             is_rtl)

        # only show ratings if we have one
        if self.show_ratings:
            self._render_rating(context, cr, app,
                                cell_area,
                                layout,
                                xpad, ypad,
                                star_width,
                                star_height,
                                is_rtl)

        # below is the stuff that is only done for the active cell
        if not self.props.isactive:
            return

        progress = app.get_transaction_progress()
        #~ print progress
        if progress > 0:
            self._render_progress(context, cr, progress,
                                  cell_area,
                                  ypad,
                                  is_rtl)

        is_available = app.is_available()
        self._render_buttons(context, cr,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl,
                             is_available)

        context.restore()
        return


class ConfigUpdateCellButtonIDs:

    EDIT = 0
    DIFF = 2
    MERGE = 3
    DISCARD = 4


class CellRendererConfigUpdateView(Gtk.CellRendererText):

    _ICON = None
    _ICON_MUTEX = Lock()

    __gproperties__ = {
        'confupdate' : (GObject.TYPE_PYOBJECT, 'document',
                         'a ConfigUpdate object',
                         GObject.PARAM_READWRITE),

        'isactive'    : (bool,'isactive', 'is cell active/selected', False,
                         GObject.PARAM_READWRITE),
                     }

    def __init__(self, icons, icon_size, layout):
        super(CellRendererConfigUpdateView, self).__init__()

        # Icons
        self._icons = icons
        self._icon_size = icon_size

        # geometry-state values
        self.pixbuf_width = 0
        self.title_width = 0
        self.title_height = 0
        self.normal_height = 0
        self.selected_height = 0

        # button packing
        self.button_spacing = 0
        self._buttons = {Gtk.PackType.START: [],
                         Gtk.PackType.END:   []}
        self._all_buttons = {}

        # cache a layout
        self._layout = layout

    @property
    def _icon(self):
        if CellRendererConfigUpdateView._ICON is not None:
            return CellRendererConfigUpdateView._ICON
        with CellRendererConfigUpdateView._ICON_MUTEX:
            if CellRendererConfigUpdateView._ICON is not None:
                return CellRendererConfigUpdateView._ICON
            _icon = self._icons.load_icon(
                Icons.CONFIGURATION_FILE,
                self._icon_size, 0)
            CellRendererConfigUpdateView._ICON = _icon
            return _icon

    def _layout_get_pixel_width(self, layout):
        return layout.get_size()[0] / Pango.SCALE

    def _layout_get_pixel_height(self, layout):
        return layout.get_size()[1] / Pango.SCALE

    def _render_icon(self, cr, cu, cell_area, xpad, ypad, is_rtl):

        icon = self._icon
        xo = (self.pixbuf_width - icon.get_width())/2

        if not is_rtl:
            x = cell_area.x + xo + xpad
        else:
            x = cell_area.x + cell_area.width + xo - \
                self.pixbuf_width - xpad
        y = cell_area.y + ypad

        Gdk.cairo_set_source_pixbuf(cr, icon, x, y)
        cr.paint()

    def _render_summary(self, context, cr, cu,
                        cell_area, layout, xpad, ypad,
                        is_rtl):

        layout.set_markup(cu.get_markup(), -1)

        # work out max allowable layout width
        layout.set_width(-1)
        lw = self._layout_get_pixel_width(layout)
        max_layout_width = (cell_area.width - self.pixbuf_width -
                            3 * xpad)
        max_layout_width = cell_area.width - self.pixbuf_width - 3 * xpad

        if lw >= max_layout_width:
            layout.set_width((max_layout_width)*Pango.SCALE)
            layout.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            lw = max_layout_width

        self.title_width = cell_area.width - self.pixbuf_width - \
            10 * xpad
        self.title_height = Ems.EM

        if not is_rtl:
            x = cell_area.x+2*xpad+self.pixbuf_width
        else:
            x = cell_area.x+cell_area.width-lw-self.pixbuf_width-2*xpad

        y = cell_area.y + ypad

        Gtk.render_layout(context, cr, x, y, layout)

    def _render_buttons(
        self, context, cr, cell_area, layout, xpad, ypad, is_rtl):

        # layout buttons and paint
        y = cell_area.y + cell_area.height - ypad
        spacing = self.button_spacing

        if not is_rtl:
            start = Gtk.PackType.START
            end = Gtk.PackType.END
            xs = cell_area.x + 2*xpad + self.pixbuf_width
            xb = cell_area.x + cell_area.width - xpad
        else:
            start = Gtk.PackType.END
            end = Gtk.PackType.START
            xs = cell_area.x + xpad
            xb = cell_area.x + cell_area.width - 2*xpad - \
                self.pixbuf_width

        for btn in self._buttons[start]:
            btn.set_position(xs, y-btn.height)
            btn.render(context, cr, layout)
            xs += btn.width + spacing

        for btn in self._buttons[end]:
            xb -= btn.width
            btn.set_position(xb, y-btn.height)
            btn.render(context, cr, layout)

            xb -= spacing

    def set_pixbuf_width(self, w):
        self.pixbuf_width = w

    def set_button_spacing(self, spacing):
        self.button_spacing = spacing

    def get_button_by_name(self, name):
        if name in self._all_buttons:
            return self._all_buttons[name]

    def get_buttons(self):
        btns = ()
        for k, v in self._buttons.items():
            btns += tuple(v)
        return btns

    def button_pack(self, btn, pack_type=Gtk.PackType.START):
        self._buttons[pack_type].append(btn)
        self._all_buttons[btn.name] = btn

    def button_pack_start(self, btn):
        self.button_pack(btn, Gtk.PackType.START)

    def button_pack_end(self, btn):
        self.button_pack(btn, Gtk.PackType.END)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_preferred_height_for_width(self, treeview, width):
        if not self.get_properties("isactive")[0]:
            return self.normal_height, self.normal_height
        return self.selected_height, self.selected_height

    def do_render(self, cr, widget, bg_area, cell_area, flags):
        cu = self.props.confupdate
        if not cu:
            return

        self.model = widget.model
        context = widget.get_style_context()
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        is_rtl = widget.get_direction() == Gtk.TextDirection.RTL

        layout = self._layout
        context.save()

        self._render_icon(cr, cu,
                          cell_area,
                          xpad, ypad,
                          is_rtl)

        self._render_summary(context, cr, cu,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        # below is the stuff that is only done for the active cell
        if not self.props.isactive:
            return

        self._render_buttons(context, cr,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        context.restore()

class NoticeCellButtonIDs:

    SHOW = 0

class CellRendererNoticeView(Gtk.CellRendererText):

    _ICON = None
    _ICON_MUTEX = Lock()

    __gproperties__ = {
        'notice' : (GObject.TYPE_PYOBJECT, 'document',
                    'a Notice object',
                    GObject.PARAM_READWRITE),

        'isactive'    : (bool,'isactive', 'is cell active/selected', False,
                         GObject.PARAM_READWRITE),
                     }

    def __init__(self, icons, icon_size, layout):
        super(CellRendererNoticeView, self).__init__()

        # Icons
        self._icons = icons
        self._icon_size = icon_size

        # geometry-state values
        self.pixbuf_width = 0
        self.title_width = 0
        self.title_height = 0
        self.normal_height = 0
        self.selected_height = 0

        # button packing
        self.button_spacing = 0
        self._buttons = {Gtk.PackType.START: [],
                         Gtk.PackType.END:   []}
        self._all_buttons = {}

        # cache a layout
        self._layout = layout

    @property
    def _icon(self):
        if CellRendererNoticeView._ICON is not None:
            return CellRendererNoticeView._ICON
        with CellRendererNoticeView._ICON_MUTEX:
            if CellRendererNoticeView._ICON is not None:
                return CellRendererNoticeView._ICON
            _icon = self._icons.load_icon(
                Icons.CONFIGURATION_FILE,
                self._icon_size, 0)
            CellRendererNoticeView._ICON = _icon
            return _icon

    def _layout_get_pixel_width(self, layout):
        return layout.get_size()[0] / Pango.SCALE

    def _layout_get_pixel_height(self, layout):
        return layout.get_size()[1] / Pango.SCALE

    def _render_icon(self, cr, cu, cell_area, xpad, ypad, is_rtl):

        icon = self._icon
        xo = (self.pixbuf_width - icon.get_width())/2

        if not is_rtl:
            x = cell_area.x + xo + xpad
        else:
            x = cell_area.x + cell_area.width + xo - \
                self.pixbuf_width - xpad
        y = cell_area.y + ypad

        Gdk.cairo_set_source_pixbuf(cr, icon, x, y)
        cr.paint()

    def _render_summary(self, context, cr, cu,
                        cell_area, layout, xpad, ypad,
                        is_rtl):

        markup = cu.get_markup()

        layout.set_markup(markup, -1)

        # work out max allowable layout width
        layout.set_width(-1)
        lw = self._layout_get_pixel_width(layout)
        max_layout_width = (cell_area.width - self.pixbuf_width -
                            3 * xpad)
        max_layout_width = cell_area.width - self.pixbuf_width - 3 * xpad

        if lw >= max_layout_width:
            layout.set_width((max_layout_width)*Pango.SCALE)
            layout.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            lw = max_layout_width

        self.title_width = cell_area.width - self.pixbuf_width - \
            10 * xpad
        self.title_height = Ems.EM

        if not is_rtl:
            x = cell_area.x+2*xpad+self.pixbuf_width
        else:
            x = cell_area.x+cell_area.width-lw-self.pixbuf_width-2*xpad

        y = cell_area.y + ypad

        Gtk.render_layout(context, cr, x, y, layout)

    def _render_buttons(
        self, context, cr, cell_area, layout, xpad, ypad, is_rtl):

        # layout buttons and paint
        y = cell_area.y + cell_area.height - ypad
        spacing = self.button_spacing

        if not is_rtl:
            start = Gtk.PackType.START
            end = Gtk.PackType.END
            xs = cell_area.x + 2*xpad + self.pixbuf_width
            xb = cell_area.x + cell_area.width - xpad
        else:
            start = Gtk.PackType.END
            end = Gtk.PackType.START
            xs = cell_area.x + xpad
            xb = cell_area.x + cell_area.width - 2*xpad - \
                self.pixbuf_width

        for btn in self._buttons[start]:
            btn.set_position(xs, y-btn.height)
            btn.render(context, cr, layout)
            xs += btn.width + spacing

        for btn in self._buttons[end]:
            xb -= btn.width
            btn.set_position(xb, y-btn.height)
            btn.render(context, cr, layout)

            xb -= spacing

    def set_pixbuf_width(self, w):
        self.pixbuf_width = w

    def set_button_spacing(self, spacing):
        self.button_spacing = spacing

    def get_button_by_name(self, name):
        if name in self._all_buttons:
            return self._all_buttons[name]

    def get_buttons(self):
        btns = ()
        for k, v in self._buttons.items():
            btns += tuple(v)
        return btns

    def button_pack(self, btn, pack_type=Gtk.PackType.START):
        self._buttons[pack_type].append(btn)
        self._all_buttons[btn.name] = btn

    def button_pack_start(self, btn):
        self.button_pack(btn, Gtk.PackType.START)

    def button_pack_end(self, btn):
        self.button_pack(btn, Gtk.PackType.END)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_preferred_height_for_width(self, treeview, width):
        if not self.get_properties("isactive")[0]:
            return self.normal_height, self.normal_height
        return self.selected_height, self.selected_height

    def do_render(self, cr, widget, bg_area, cell_area, flags):
        notice = self.props.notice
        if not notice:
            return

        widget._calc_row_heights(self)

        self.model = widget.model
        context = widget.get_style_context()
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        is_rtl = widget.get_direction() == Gtk.TextDirection.RTL

        layout = self._layout
        context.save()

        self._render_icon(cr, notice,
                          cell_area,
                          xpad, ypad,
                          is_rtl)

        self._render_summary(context, cr, notice,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        # below is the stuff that is only done for the active cell
        if not self.props.isactive:
            return

        self._render_buttons(context, cr,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        context.restore()


class RepositoryCellButtonIDs:

    TOGGLE = 0
    RENAME = 1


class CellRendererRepositoryView(Gtk.CellRendererText):

    _ICON = None
    _ICON_MUTEX = Lock()

    __gproperties__ = {
        'repository' : (GObject.TYPE_PYOBJECT, 'document',
                    'a Repository object',
                    GObject.PARAM_READWRITE),

        'isactive'    : (bool, 'isactive', 'is cell active/selected', False,
                         GObject.PARAM_READWRITE),
                     }

    def __init__(self, icons, icon_size, layout):
        super(CellRendererRepositoryView, self).__init__()

        # Icons
        self._icons = icons
        self._icon_size = icon_size

        # geometry-state values
        self.pixbuf_width = 0
        self.title_width = 0
        self.title_height = 0
        self.normal_height = 0
        self.selected_height = 0

        # button packing
        self.button_spacing = 0
        self._buttons = {Gtk.PackType.START: [],
                         Gtk.PackType.END:   []}
        self._all_buttons = {}

        # cache a layout
        self._layout = layout

    @property
    def _icon(self):
        if CellRendererRepositoryView._ICON is not None:
            return CellRendererRepositoryView._ICON
        with CellRendererRepositoryView._ICON_MUTEX:
            if CellRendererRepositoryView._ICON is not None:
                return CellRendererRepositoryView._ICON
            _icon = self._icons.load_icon(
                Icons.REPOSITORY,
                self._icon_size, 0)
            CellRendererRepositoryView._ICON = _icon
            return _icon

    def _layout_get_pixel_width(self, layout):
        return layout.get_size()[0] / Pango.SCALE

    def _layout_get_pixel_height(self, layout):
        return layout.get_size()[1] / Pango.SCALE

    def _render_icon(self, cr, repo, cell_area, xpad, ypad, is_rtl):

        icon = self._icon
        xo = (self.pixbuf_width - icon.get_width())/2

        if not is_rtl:
            x = cell_area.x + xo + xpad
        else:
            x = cell_area.x + cell_area.width + xo - \
                self.pixbuf_width - xpad
        y = cell_area.y + ypad

        Gdk.cairo_set_source_pixbuf(cr, icon, x, y)
        cr.paint()

    def _render_summary(self, context, cr, repo,
                        cell_area, layout, xpad, ypad,
                        is_rtl):

        markup = repo.get_markup()

        layout.set_markup(markup, -1)

        # work out max allowable layout width
        layout.set_width(-1)
        lw = self._layout_get_pixel_width(layout)
        max_layout_width = (cell_area.width - self.pixbuf_width -
                            3 * xpad)
        max_layout_width = cell_area.width - self.pixbuf_width - 3 * xpad

        if lw >= max_layout_width:
            layout.set_width((max_layout_width)*Pango.SCALE)
            layout.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            lw = max_layout_width

        self.title_width = cell_area.width - self.pixbuf_width - \
            10 * xpad
        self.title_height = Ems.EM

        if not is_rtl:
            x = cell_area.x+2*xpad+self.pixbuf_width
        else:
            x = cell_area.x+cell_area.width-lw-self.pixbuf_width-2*xpad

        y = cell_area.y + ypad

        Gtk.render_layout(context, cr, x, y, layout)

    def _render_buttons(
        self, context, cr, cell_area, layout, xpad, ypad, is_rtl):

        # layout buttons and paint
        y = cell_area.y + cell_area.height - ypad
        spacing = self.button_spacing

        if not is_rtl:
            start = Gtk.PackType.START
            end = Gtk.PackType.END
            xs = cell_area.x + 2*xpad + self.pixbuf_width
            xb = cell_area.x + cell_area.width - xpad
        else:
            start = Gtk.PackType.END
            end = Gtk.PackType.START
            xs = cell_area.x + xpad
            xb = cell_area.x + cell_area.width - 2*xpad - \
                self.pixbuf_width

        for btn in self._buttons[start]:
            btn.set_position(xs, y-btn.height)
            btn.render(context, cr, layout)
            xs += btn.width + spacing

        for btn in self._buttons[end]:
            xb -= btn.width
            btn.set_position(xb, y-btn.height)
            btn.render(context, cr, layout)

            xb -= spacing

    def set_pixbuf_width(self, w):
        self.pixbuf_width = w

    def set_button_spacing(self, spacing):
        self.button_spacing = spacing

    def get_button_by_name(self, name):
        if name in self._all_buttons:
            return self._all_buttons[name]

    def get_buttons(self):
        btns = ()
        for k, v in self._buttons.items():
            btns += tuple(v)
        return btns

    def button_pack(self, btn, pack_type=Gtk.PackType.START):
        self._buttons[pack_type].append(btn)
        self._all_buttons[btn.name] = btn

    def button_pack_start(self, btn):
        self.button_pack(btn, Gtk.PackType.START)

    def button_pack_end(self, btn):
        self.button_pack(btn, Gtk.PackType.END)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_preferred_height_for_width(self, treeview, width):
        if not self.get_properties("isactive")[0]:
            return self.normal_height, self.normal_height
        return self.selected_height, self.selected_height

    def do_render(self, cr, widget, bg_area, cell_area, flags):
        repository = self.props.repository
        if not repository:
            return

        widget._calc_row_heights(self)

        self.model = widget.model
        context = widget.get_style_context()
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        is_rtl = widget.get_direction() == Gtk.TextDirection.RTL

        layout = self._layout
        context.save()

        self._render_icon(cr, repository,
                          cell_area,
                          xpad, ypad,
                          is_rtl)

        self._render_summary(context, cr, repository,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        # below is the stuff that is only done for the active cell
        if not self.props.isactive:
            return

        self._render_buttons(context, cr,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        context.restore()


class PreferenceCellButtonIDs:

    RUN = 0


class CellRendererPreferenceView(Gtk.CellRendererText):

    __gproperties__ = {
        'preference' : (GObject.TYPE_PYOBJECT, 'document',
                        'a Preference object',
                        GObject.PARAM_READWRITE),

        'isactive'    : (bool,'isactive', 'is cell active/selected', False,
                         GObject.PARAM_READWRITE),
                     }

    def __init__(self, icons, icon_size, layout):
        super(CellRendererPreferenceView, self).__init__()

        # Icons
        self._icons = icons
        self._icon_size = icon_size

        # geometry-state values
        self.pixbuf_width = 0
        self.title_width = 0
        self.title_height = 0
        self.normal_height = 0
        self.selected_height = 0

        # button packing
        self.button_spacing = 0
        self._buttons = {Gtk.PackType.START: [],
                         Gtk.PackType.END:   []}
        self._all_buttons = {}

        # cache a layout
        self._layout = layout

    def _icon(self, pref):
        try:
            _icon = self._icons.load_icon(
                pref.icon(),
                self._icon_size, 0)
        except GObject.GError:
            _icon = self._icons.load_icon(
                Icons.CONFIGURATION_FILE,
                self._icon_size, 0)
        return _icon

    def _layout_get_pixel_width(self, layout):
        return layout.get_size()[0] / Pango.SCALE

    def _layout_get_pixel_height(self, layout):
        return layout.get_size()[1] / Pango.SCALE

    def _render_icon(self, cr, cu, cell_area, xpad, ypad, is_rtl):

        icon = self._icon(cu)
        xo = (self.pixbuf_width - icon.get_width())/2

        if not is_rtl:
            x = cell_area.x + xo + xpad
        else:
            x = cell_area.x + cell_area.width + xo - \
                self.pixbuf_width - xpad
        y = cell_area.y + ypad

        Gdk.cairo_set_source_pixbuf(cr, icon, x, y)
        cr.paint()

    def _render_summary(self, context, cr, cu,
                        cell_area, layout, xpad, ypad,
                        is_rtl):

        markup = cu.get_markup()
        layout.set_markup(markup, -1)

        # work out max allowable layout width
        layout.set_width(-1)
        lw = self._layout_get_pixel_width(layout)
        max_layout_width = (cell_area.width - self.pixbuf_width -
                            3 * xpad)
        max_layout_width = cell_area.width - self.pixbuf_width - 3 * xpad

        if lw >= max_layout_width:
            layout.set_width((max_layout_width)*Pango.SCALE)
            layout.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            lw = max_layout_width

        self.title_width = cell_area.width - self.pixbuf_width - \
            10 * xpad
        self.title_height = Ems.EM

        if not is_rtl:
            x = cell_area.x+2*xpad+self.pixbuf_width
        else:
            x = cell_area.x+cell_area.width-lw-self.pixbuf_width-2*xpad

        y = cell_area.y + ypad

        Gtk.render_layout(context, cr, x, y, layout)

    def _render_buttons(
        self, context, cr, cell_area, layout, xpad, ypad, is_rtl):

        # layout buttons and paint
        y = cell_area.y + cell_area.height - ypad
        spacing = self.button_spacing

        if not is_rtl:
            start = Gtk.PackType.START
            end = Gtk.PackType.END
            xs = cell_area.x + 2*xpad + self.pixbuf_width
            xb = cell_area.x + cell_area.width - xpad
        else:
            start = Gtk.PackType.END
            end = Gtk.PackType.START
            xs = cell_area.x + xpad
            xb = cell_area.x + cell_area.width - 2*xpad - \
                self.pixbuf_width

        for btn in self._buttons[start]:
            btn.set_position(xs, y-btn.height)
            btn.render(context, cr, layout)
            xs += btn.width + spacing

        for btn in self._buttons[end]:
            xb -= btn.width
            btn.set_position(xb, y-btn.height)
            btn.render(context, cr, layout)

            xb -= spacing

    def set_pixbuf_width(self, w):
        self.pixbuf_width = w

    def set_button_spacing(self, spacing):
        self.button_spacing = spacing

    def get_button_by_name(self, name):
        if name in self._all_buttons:
            return self._all_buttons[name]

    def get_buttons(self):
        btns = ()
        for k, v in self._buttons.items():
            btns += tuple(v)
        return btns

    def button_pack(self, btn, pack_type=Gtk.PackType.START):
        self._buttons[pack_type].append(btn)
        self._all_buttons[btn.name] = btn

    def button_pack_start(self, btn):
        self.button_pack(btn, Gtk.PackType.START)

    def button_pack_end(self, btn):
        self.button_pack(btn, Gtk.PackType.END)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_preferred_height_for_width(self, treeview, width):
        if not self.get_properties("isactive")[0]:
            return self.normal_height, self.normal_height
        return self.selected_height, self.selected_height

    def do_render(self, cr, widget, bg_area, cell_area, flags):
        pref = self.props.preference
        if not pref:
            return

        widget._calc_row_heights(self)

        self.model = widget.model
        context = widget.get_style_context()
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        is_rtl = widget.get_direction() == Gtk.TextDirection.RTL

        layout = self._layout
        context.save()

        self._render_icon(cr, pref,
                          cell_area,
                          xpad, ypad,
                          is_rtl)

        self._render_summary(context, cr, pref,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        # below is the stuff that is only done for the active cell
        if not self.props.isactive:
            return

        self._render_buttons(context, cr,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        context.restore()


class GroupCellButtonIDs:

    VIEW = 0


class CellRendererGroupView(Gtk.CellRendererText):

    __gproperties__ = {
        'group' : (GObject.TYPE_PYOBJECT, 'document',
                   'a Group object',
                   GObject.PARAM_READWRITE),

        'isactive'    : (bool,'isactive', 'is cell active/selected', False,
                         GObject.PARAM_READWRITE),
        }

    def __init__(self, icons, icon_size, layout):
        super(CellRendererGroupView, self).__init__()

        # Icons
        self._icons = icons
        self._icon_size = icon_size

        # geometry-state values
        self.pixbuf_width = 0
        self.title_width = 0
        self.title_height = 0
        self.normal_height = 0
        self.selected_height = 0

        # button packing
        self.button_spacing = 0
        self._buttons = {Gtk.PackType.START: [],
                         Gtk.PackType.END:   []}
        self._all_buttons = {}

        # cache a layout
        self._layout = layout

    def _icon(self, group):
        try:
            _icon = self._icons.load_icon(
                group.icon(),
                self._icon_size, 0)
        except GObject.GError:
            _icon = self._icons.load_icon(
                Icons.GROUPS,
                self._icon_size, 0)
        return _icon

    def _layout_get_pixel_width(self, layout):
        return layout.get_size()[0] / Pango.SCALE

    def _layout_get_pixel_height(self, layout):
        return layout.get_size()[1] / Pango.SCALE

    def _render_icon(self, cr, group, cell_area, xpad, ypad, is_rtl):

        icon = self._icon(group)
        xo = (self.pixbuf_width - icon.get_width())/2

        if not is_rtl:
            x = cell_area.x + xo + xpad
        else:
            x = cell_area.x + cell_area.width + xo - \
                self.pixbuf_width - xpad
        y = cell_area.y + ypad

        Gdk.cairo_set_source_pixbuf(cr, icon, x, y)
        cr.paint()

    def _render_summary(self, context, cr, group,
                        cell_area, layout, xpad, ypad,
                        is_rtl):

        markup = group.get_markup()
        layout.set_markup(markup, -1)

        # work out max allowable layout width
        layout.set_width(-1)
        lw = self._layout_get_pixel_width(layout)
        max_layout_width = (cell_area.width - self.pixbuf_width -
                            3 * xpad)
        max_layout_width = cell_area.width - self.pixbuf_width - 3 * xpad

        if lw >= max_layout_width:
            layout.set_width((max_layout_width)*Pango.SCALE)
            layout.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            lw = max_layout_width

        self.title_width = cell_area.width - self.pixbuf_width - \
            10 * xpad
        self.title_height = Ems.EM

        if not is_rtl:
            x = cell_area.x+2*xpad+self.pixbuf_width
        else:
            x = cell_area.x+cell_area.width-lw-self.pixbuf_width-2*xpad

        y = cell_area.y + ypad

        Gtk.render_layout(context, cr, x, y, layout)

    def _render_buttons(
        self, context, cr, cell_area, layout, xpad, ypad, is_rtl):

        # layout buttons and paint
        y = cell_area.y + cell_area.height - ypad
        spacing = self.button_spacing

        if not is_rtl:
            start = Gtk.PackType.START
            end = Gtk.PackType.END
            xs = cell_area.x + 2*xpad + self.pixbuf_width
            xb = cell_area.x + cell_area.width - xpad
        else:
            start = Gtk.PackType.END
            end = Gtk.PackType.START
            xs = cell_area.x + xpad
            xb = cell_area.x + cell_area.width - 2*xpad - \
                self.pixbuf_width

        for btn in self._buttons[start]:
            btn.set_position(xs, y-btn.height)
            btn.render(context, cr, layout)
            xs += btn.width + spacing

        for btn in self._buttons[end]:
            xb -= btn.width
            btn.set_position(xb, y-btn.height)
            btn.render(context, cr, layout)

            xb -= spacing

    def set_pixbuf_width(self, w):
        self.pixbuf_width = w

    def set_button_spacing(self, spacing):
        self.button_spacing = spacing

    def get_button_by_name(self, name):
        if name in self._all_buttons:
            return self._all_buttons[name]

    def get_buttons(self):
        btns = ()
        for k, v in self._buttons.items():
            btns += tuple(v)
        return btns

    def button_pack(self, btn, pack_type=Gtk.PackType.START):
        self._buttons[pack_type].append(btn)
        self._all_buttons[btn.name] = btn

    def button_pack_start(self, btn):
        self.button_pack(btn, Gtk.PackType.START)

    def button_pack_end(self, btn):
        self.button_pack(btn, Gtk.PackType.END)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_preferred_height_for_width(self, treeview, width):
        if not self.get_properties("isactive")[0]:
            return self.normal_height, self.normal_height
        return self.selected_height, self.selected_height

    def do_render(self, cr, widget, bg_area, cell_area, flags):
        pref = self.props.group
        if not pref:
            return

        widget._calc_row_heights(self)

        self.model = widget.model
        context = widget.get_style_context()
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        is_rtl = widget.get_direction() == Gtk.TextDirection.RTL

        layout = self._layout
        context.save()

        self._render_icon(cr, pref,
                          cell_area,
                          xpad, ypad,
                          is_rtl)

        self._render_summary(context, cr, pref,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        # below is the stuff that is only done for the active cell
        if not self.props.isactive:
            return

        self._render_buttons(context, cr,
                             cell_area,
                             layout,
                             xpad, ypad,
                             is_rtl)

        context.restore()


class CellButtonRenderer(object):

    def __init__(self, widget, name, use_max_variant_width=True):
        # use_max_variant_width is currently ignored. assumed to be True

        self.name = name
        self.markup_variants = {}
        self.current_variant = None

        self.xpad = 12
        self.ypad = 4
        self.allocation = [0, 0, 1, 1]
        self.state = Gtk.StateFlags.NORMAL
        self.has_focus = False
        self.visible = True

        self.widget = widget

    def _layout_reset(self, layout):
        layout.set_width(-1)
        layout.set_ellipsize(Pango.EllipsizeMode.NONE)

    @property
    def x(self):
        return self.allocation[0]

    @property
    def y(self):
        return self.allocation[1]

    @property
    def width(self):
        return self.allocation[2]

    @property
    def height(self):
        return self.allocation[3]

    def configure_geometry(self, layout):
        self._layout_reset(layout)
        max_size = (0,0)

        for k, variant in self.markup_variants.items():
            safe_markup = escape_markup(variant)
            layout.set_markup(safe_markup, -1)
            size = layout.get_size()
            max_size = max(max_size, size)

        w, h = max_size
        w /= Pango.SCALE
        h /= Pango.SCALE

        w = w+2*self.xpad
        h = h+2*self.ypad
        self.set_size(w, h)

    def point_in(self, px, py):
        x, y, w, h = self.allocation
        return (px >= x and px <= x + w and
                py >= y and py <= y + h)

    def get_size(self):
        return self.allocation[2:]

    def set_position(self, x, y):
        self.allocation[:2] = int(x), int(y)

    def set_size(self, w, h):
        self.allocation[2:] = int(w), int(h)

    def set_state(self, state):
        if not isinstance(state, Gtk.StateFlags):
            msg = "state should be of type Gtk.StateFlags, got %s" % type(state)
            raise TypeError(msg)

        elif state == self.state: return

        self.state = state
        self.widget.queue_draw_area(*self.allocation)

    def set_sensitive(self, is_sensitive):
        if is_sensitive:
            state = Gtk.StateFlags.PRELIGHT
        else:
            state = Gtk.StateFlags.INSENSITIVE
        self.set_state(state)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def set_markup(self, markup):
        self.markup_variant = (markup,)

    def set_markup_variants(self, markup_variants):
        if not isinstance(markup_variants, dict):
            msg = type(markup_variants)
            raise TypeError("Expects a dict object, got %s" % msg)

        elif not markup_variants:
            return

        self.markup_variants = markup_variants
        self.current_variant = list(markup_variants.keys())[0]

    def set_variant(self, current_var):
        self.current_variant = current_var

    def is_sensitive(self):
        return self.state == Gtk.StateFlags.INSENSITIVE

    def render(self, context, cr, layout):
        if not self.visible:
            return

        x, y, width, height = self.allocation

        context.save()
        context.add_class("cellrenderer-button")

        if self.has_focus:
            context.set_state(self.state | Gtk.StateFlags.FOCUSED)
        else:
            context.set_state(self.state)

        # render background and focal frame if has-focus
        context.save()
        context.add_class(Gtk.STYLE_CLASS_BUTTON)
        Gtk.render_background(context, cr, x, y, width, height)
        context.restore()

        if self.has_focus:
            Gtk.render_focus(context, cr, x+3, y+3, width-6, height-6)

        # position and render layout markup
        context.save()
        context.add_class(Gtk.STYLE_CLASS_BUTTON)
        layout.set_markup(self.markup_variants[self.current_variant], -1)
        layout_width = layout.get_pixel_extents()[1].width
        x = x + (width - layout_width)/2
        y += self.ypad
        Gtk.render_layout(context, cr, x, y, layout)
        context.restore()

        context.restore()
