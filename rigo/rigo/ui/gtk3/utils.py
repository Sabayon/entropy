# -*- coding: utf-8 -*-
"""
Copyright (C) 2009 Canonical
Copyright (C) 2012 Fabio Erculiani

Authors:
  Michael Vogt
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
import os
import logging
import shutil

from gi.repository import Gtk, GdkPixbuf, GObject

from entropy.const import const_mkstemp

from rigo.paths import ICON_PATH

LOG = logging.getLogger(__name__)


def point_in(rect, px, py):
    return (rect.x <= px <= rect.x + rect.width and
            rect.y <= py <= rect.y + rect.height)

def init_sc_css_provider(toplevel, settings, screen, datadir):
    context = toplevel.get_style_context()
    theme_name = settings.get_property("gtk-theme-name").lower()

    if hasattr(toplevel, '_css_provider'):
        # check old provider, see if we can skip setting or remove old
        # style provider
        if toplevel._css_provider._theme_name == theme_name:
            return
        else: # clean up old css provider if exixts
            context.remove_provider_for_screen(screen, toplevel._css_provider)

    # munge css path for theme-name
    css_path = os.path.join(datadir,
                            "ui/gtk3/css/rigo.%s.css" % \
                            theme_name)

    # if no css for theme-name try fallback css
    if not os.path.exists(css_path):
        css_path = os.path.join(datadir, "ui/gtk3/css/rigo.css")

    if not os.path.exists(css_path):
        # check fallback exists as well... if not return None but warn
        # its not the end of the world if there is no fallback, just some
        # styling will be derived from the plain ol' Gtk theme
        msg = "Could not set rigo " + \
            "CSS provider. File '%s' does not exist!"
        LOG.warn(msg % css_path)
        return None

    # things seem ok, now set the css provider for Rigo
    msg = "Rigo style provider for %s Gtk theme: %s"
    LOG.info(msg % (theme_name, css_path))

    provider = Gtk.CssProvider()
    provider._theme_name = theme_name
    toplevel._css_provider = provider

    provider.load_from_path(css_path)
    context.add_provider_for_screen(screen, provider, 800)
    return css_path

def get_sc_icon_theme(datadir):
    # additional icons come from app-install-data
    icons = Gtk.IconTheme.get_default()
    icons.append_search_path(ICON_PATH)
    icons.append_search_path(os.path.join(datadir, "icons"))
    icons.append_search_path(os.path.join(datadir, "emblems"))
    # HACK: make it more friendly for local installs (for mpt)
    icons.append_search_path(datadir+"/icons/32x32/status")

    return icons

def resize_image(max_width, image_path, final_image_path):
    dirname = os.path.dirname(final_image_path)
    tmp_fd, new_image_path = const_mkstemp(
        dir=dirname, prefix="resize_image")
    os.close(tmp_fd)

    shutil.copy2(image_path, new_image_path)
    img = Gtk.Image()
    img.set_from_file(new_image_path)
    img_buf = img.get_pixbuf()
    w, h = img_buf.get_width(), img_buf.get_height()
    if w > max_width:
        # resize pix
        new_w = max_width
        new_h = new_w * h / w
        img_buf = img_buf.scale_simple(int(new_w),
            int(new_h), GdkPixbuf.InterpType.BILINEAR)
        try:
            img_buf.save(new_image_path, "png")
        except GObject.GError:
            # libpng issue? try jpeg
            img_buf.save(new_image_path, "jpeg")
        del img_buf
    del img
    os.rename(new_image_path, final_image_path)

def resize_image_height(max_height, image_path, final_image_path):
    dirname = os.path.dirname(final_image_path)
    tmp_fd, new_image_path = const_mkstemp(
        dir=dirname, prefix="resize_image")
    os.close(tmp_fd)

    shutil.copy2(image_path, new_image_path)
    img = Gtk.Image()
    img.set_from_file(new_image_path)
    img_buf = img.get_pixbuf()
    w, h = img_buf.get_width(), img_buf.get_height()
    if h > max_height:
        # resize pix
        new_h = max_height
        new_w = new_h*w/h
        img_buf = img_buf.scale_simple(int(new_w),
            int(new_h), GdkPixbuf.InterpType.BILINEAR)
        try:
            img_buf.save(new_image_path, "png")
        except GObject.GError:
            # libpng issue? try jpeg
            img_buf.save(new_image_path, "jpeg")
        del img_buf
    del img
    os.rename(new_image_path, final_image_path)
