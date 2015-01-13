# -*- coding: utf-8 -*-
"""
Copyright (C) 2012 Fabio Erculiani

Authors:
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
try:
    import configparser as ConfigParser
except ImportError:
    import ConfigParser
import codecs

from gi.repository import Vte, Gdk

from entropy.const import etpConst, const_isunicode

from rigo.paths import CONF_DIR
from rigo.utils import prepare_markup

import entropy.tools
from entropy.const import etpConst

class TerminalWidget(Vte.Terminal):

    """
    Rigo Terminal Widget.
    """

    SETTINGS_FILE = os.path.join(CONF_DIR, "rigo-terminal.conf")
    S_DISPLAY_SECTION = "Display"
    S_BACKGROUND_OPTION = "background"
    S_FOREGROUND_OPTION = "foreground"
    S_DEFAULT_BACKGROUND_COLOR = "black"
    S_DEFAULT_FOREGROUND_COLOR = "white"
    S_WHITE_BACKGROUND_COLOR = "white"
    S_WHITE_FOREGROUND_COLOR = "black"

    def __init__(self):
        self._config = ConfigParser.SafeConfigParser()
        # set $TERM variable, avoid shell scripts to complain
        os.environ['TERM'] = "xterm"
        Vte.Terminal.__init__(self)

    def white(self):
        """
        Set the background color to white.
        """
        bg = TerminalWidget.S_WHITE_BACKGROUND_COLOR
        fg = TerminalWidget.S_WHITE_FOREGROUND_COLOR
        self._set_config_colors(bg, fg)

        rgba = Gdk.RGBA()
        rgba.parse(bg)
        fg_rgba = Gdk.RGBA()
        fg_rgba.parse(fg)

        self.set_color_background(rgba)
        self.set_color_foreground(fg_rgba)
        self.set_color_bold(fg_rgba)

    def black(self):
        """
        Set the background color to black.
        """
        bg = TerminalWidget.S_DEFAULT_BACKGROUND_COLOR
        fg = TerminalWidget.S_DEFAULT_FOREGROUND_COLOR
        self._set_config_colors(bg, fg)

        rgba = Gdk.RGBA()
        rgba.parse(bg)
        fg_rgba = Gdk.RGBA()
        fg_rgba.parse(fg)

        self.set_color_background(rgba)
        self.set_color_foreground(fg_rgba)
        self.set_color_bold(fg_rgba)

    def autoscroll(self, value):
        """
        Enable or disable automatic scrolling.
        """
        self.set_scroll_on_output(value)

    def _set_config_colors(self, background_color, foreground_color):
        """
        Set the given color strings to the configuration file.
        """
        if background_color is not None:
            try:
                self._config.set(
                    TerminalWidget.S_DISPLAY_SECTION,
                    TerminalWidget.S_BACKGROUND_OPTION,
                    background_color)
            except ConfigParser.NoSectionError:
                self._config.add_section(
                    TerminalWidget.S_DISPLAY_SECTION)
                self._config.set(
                    TerminalWidget.S_DISPLAY_SECTION,
                    TerminalWidget.S_BACKGROUND_OPTION,
                    background_color)

        if foreground_color is not None:
            try:
                self._config.set(
                    TerminalWidget.S_DISPLAY_SECTION,
                    TerminalWidget.S_FOREGROUND_OPTION,
                    foreground_color)
            except ConfigParser.NoSectionError:
                self._config.add_section(
                    TerminalWidget.S_DISPLAY_SECTION)
                self._config.set(
                    TerminalWidget.S_DISPLAY_SECTION,
                    TerminalWidget.S_FOREGROUND_OPTION,
                    foreground_color)

        if foreground_color or background_color:
            with codecs.open(
                TerminalWidget.SETTINGS_FILE, "w",
                encoding=etpConst['conf_encoding']) as settings_f:
                self._config.write(settings_f)

    def _configure_colors(self):

        read_files = self._config.read(TerminalWidget.SETTINGS_FILE)

        background_color = TerminalWidget.S_DEFAULT_BACKGROUND_COLOR
        foreground_color = TerminalWidget.S_DEFAULT_FOREGROUND_COLOR
        found = False
        if TerminalWidget.SETTINGS_FILE in read_files:
            found = True
            _background_color = self._config.get(
                TerminalWidget.S_DISPLAY_SECTION,
                TerminalWidget.S_BACKGROUND_OPTION)
            if _background_color:
                background_color = _background_color
            _foreground_color = self._config.get(
                TerminalWidget.S_DISPLAY_SECTION,
                TerminalWidget.S_FOREGROUND_OPTION)
            if _foreground_color:
                foreground_color = _foreground_color

        rgba = Gdk.RGBA()
        _valid = rgba.parse(background_color)
        if not _valid: # reset
            background_color = TerminalWidget.S_DEFAULT_BACKGROUND_COLOR
            rgba.parse(background_color)

        fg_rgba = Gdk.RGBA()
        _fg_valid = fg_rgba.parse(foreground_color)
        if not _fg_valid: # reset
            foreground_color = TerminalWidget.S_DEFAULT_FOREGROUND_COLOR
            fg_rgba.parse(foreground_color)

        if (not found) or (not _valid) or (not _fg_valid):
            # background
            bg, fg = None, None
            if not _valid:
                bg = background_color
            if not _fg_valid:
                fg = foreground_color
            self._set_config_colors(bg, fg)

        self.set_color_background(rgba)
        self.set_color_foreground(fg_rgba)
        self.set_color_bold(fg_rgba)

    def _configure(self):
        self.set_scrollback_lines(10000)
        self._configure_colors()

    def reset(self):
        Vte.Terminal.reset(self, True, True)
        self._configure()

    def feed_child(self, txt):
        # Workaround vte.Terminal bug not passing to .feed proper message RAW
        # size. feed() supports UTF-8 but then, string length is wrongly passed
        # by python, because it does not consider the fact that UTF-8 chars can
        # be 16bits long.
        raw_txt_len = len(txt)
        if const_isunicode(txt):
            raw_txt_len = len(txt.encode(etpConst['conf_encoding']))

        try:
            return Vte.Terminal.feed(self, txt, raw_txt_len)
        except TypeError:
            # Vte.Terminal 0.32.x
            return Vte.Terminal.feed(self, prepare_markup(txt))
