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

from gi.repository import Vte

from entropy.const import etpConst, const_isunicode

from rigo.utils import prepare_markup

class TerminalWidget(Vte.Terminal):

    """
    Rigo Terminal Widget.
    """

    def __init__(self):
        # set $TERM variable, avoid shell scripts to complain
        os.environ['TERM'] = "xterm"
        Vte.Terminal.__init__(self)

    def _configure(self):
        self.set_emulation("xterm")
        self.set_background_saturation(0.0)
        self.set_opacity(65535)
        self.set_font_from_string("Monospace 9")
        self.set_scrollback_lines(10000)
        self.set_scroll_on_output(True)

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
