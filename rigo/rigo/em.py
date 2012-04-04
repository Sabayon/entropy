# -*- coding: utf-8 -*-
"""
Copyright (C) 2009 Canonical
Copyright (C) 2012 Fabio Erculiani

Authors:
  Somebody at Canonical?
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
from gi.repository import Pango
from gi.repository import Gtk

def get_em(size=""):
    # calc the height of a character, use as 1em
    if size:
        m = '<%s>M</%s>' % (size, size)
    else:
        m = 'M'
    l = Gtk.Label()
    l.set_markup(m)
    w, h = l.get_layout().get_size()
    return h / Pango.SCALE

def get_small_em():
    return get_em("small")

def get_big_em():
    return get_em("big")

class _Ems:

    _EM = None
    _BIG_EM = None
    _SMALL_EM = None

    @property
    def EM(self):
        if (Ems._EM is None) or (Ems._EM == 0):
            Ems._EM = get_em()
        return Ems._EM

    @property
    def BIG_EM(self):
        if (Ems._BIG_EM is None) or (Ems._BIG_EM == 0):
            Ems._BIG_EM = get_big_em()
        return Ems._BIG_EM

    @property
    def SMALL_EM(self):
        if (Ems._SMALL_EM is None) or (Ems._SMALL_EM == 0):
            Ems._SMALL_EM = get_small_em()
        return Ems._SMALL_EM

Ems = _Ems()

def em(multiplier=1, min=1):
    _em = Ems.EM
    if _em == 0:
        return 0
    return max(int(min), int(round(_em * multiplier, 0)))

def small_em(multiplier=1, min=1):
    _em = Ems.SMALL_EM
    if _em == 0:
        return 0
    return max(int(min), int(round(_em * multiplier, 0)))

def big_em(multiplier=1, min=1):
    _em = Ems.BIG_EM
    if _em == 0:
        return 0
    return max(int(min), int(round(_em * multiplier, 0)))

# common values
class _StockEms:

    _XXLARGE = None
    @property
    def XXLARGE(self):
        if StockEms._XXLARGE is None or StockEms._XXLARGE == 0:
            StockEms._XXLARGE = em(1.66, 7)
        return StockEms._XXLARGE

    _XLARGE = None
    @property
    def XLARGE(self):
        if StockEms._XLARGE is None or StockEms._XLARGE == 0:
            StockEms._XLARGE = em(1.33, 5)
        return StockEms._XLARGE

    _LARGE = None
    @property
    def LARGE(self):
        if StockEms._LARGE is None or StockEms._LARGE == 0:
            StockEms._LARGE = em(min=3)
        return StockEms._LARGE

    _MEDIUM = None
    @property
    def MEDIUM(self):
        if StockEms._MEDIUM is None or StockEms._MEDIUM == 0:
            StockEms._MEDIUM = em(0.666, 2)
        return StockEms._MEDIUM

    _SMALL = None
    @property
    def SMALL(self):
        if StockEms._SMALL is None or StockEms._SMALL == 0:
            StockEms._SMALL = em(0.333, 1)
        return StockEms._SMALL

StockEms = _StockEms()
