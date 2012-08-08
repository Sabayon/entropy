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

from rigo.utils import prepare_markup, escape_markup

class Group(object):

    GROUP_ICONS_MAP = {
        'accessibility': "access",
        'development': "applications-development",
        'games': "applications-games",
        'gnome': "gnome",
        'kde': "kde",
        'lxde': "lxde",
        'multimedia': "applications-multimedia",
        'networking': "applications-internet",
        'office': "applications-office",
        'science': "applications-science",
        'security': "system-config-securitylevel",
        'system': "preferences-system",
        'x11': "desktop-effects",
        'xfce': "xfce",
        '__fallback__': "applications-other",
    }

    def __init__(self, avc, identifier, name, description, categories):
        self._avc = avc
        self._id = identifier
        self._name = name
        self._description = description
        self._categories = categories

    def __str__(self):
        """
        String representation of Group object
        """
        return "Group{%s, %s, %s}" % (
            self._id, self._name,
            "; ".join(self._categories))

    def identifier(self):
        """
        Return the Group identifier
        """
        return self._id

    def icon(self):
        """
        Return the Group icon.
        """
        icon = self.GROUP_ICONS_MAP.get(
            self._id)
        if icon is None:
            icon = self.GROUP_ICON_MAP.get(
                "__fallback__")
        return icon

    def name(self):
        """
        Return the Group mnemonic name.
        """
        return self._name

    def description(self):
        """
        Return the Group description.
        """
        return self._description

    def categories(self):
        """
        Return the Group categories.
        """
        return self._categories

    def get_markup(self):
        """
        Return ConfigurationUpdate markup text.
        """
        categories = self.categories()
        max_cat = 4
        max_cat_str = ""
        if len(categories) > max_cat:
            max_cat_str = " ..."
        cat_str = ", ".join(
            ["<b>%s</b>" % x for x in categories[:max_cat]])
        msg = "<b>%s</b>\n<small><i>%s</i>\n%s%s</small>"
        msg = msg % (
            escape_markup(self.name()),
            escape_markup(self.description()),
            prepare_markup(cat_str),
            prepare_markup(max_cat_str))
        return prepare_markup(msg)

    def run(self):
        """
        Show the Group Content.
        """
        if self._avc is not None:
            txt = "%s %s" % (
                self._avc.SHOW_CATEGORY_KEY,
                " ".join(self.categories()))
            self._avc.search(txt)
