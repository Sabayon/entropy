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
from rigo.utils import prepare_markup


class Preference(object):

    def __init__(self, priority, title, description, icon_name, callback):
        self._priority = priority
        self._title = title
        self._description = description
        self._icon_name = icon_name
        self._callback = callback

    def __str__(self):
        """
        String representation of Notice object
        """
        return "Preference{%s, %s, %s}" % (
            self._markup, self._icon_name,
            self._callback)

    def priority(self):
        """
        Return the preference priority that is used
        to sort the elements in the list.
        """
        return self._priority

    def run(self):
        """
        Execute the callback.
        """
        return self._callback()

    def icon(self):
        """
        Return the icon name bound to this Preference.
        """
        return self._icon_name

    def get_markup(self):
        """
        Return Preference markup text.
        """
        msg = "<b>%s</b>\n\n<small>%s</small>"
        msg = msg % (self._title, self._description)
        return prepare_markup(msg)
