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
import hashlib
import email.utils

from rigo.utils import prepare_markup, escape_markup

from entropy.i18n import _


class Repository(object):

    def __init__(self, repository, description, enabled):
        self._repository = repository
        self._description = description
        self._enabled = enabled

    def __str__(self):
        """
        String representation of Repository object
        """
        return "Repository{%s, %s, %s}" % (
            self._repository, self._description, self._enabled)

    def repository(self):
        """
        Return the Repository.
        """
        return self._repository

    def description(self):
        """
        Return the Repository description.
        """
        return self._description

    def enabled(self):
        """
        Return the Repository status.
        """
        return self._enabled

    def get_markup(self):
        """
        Return Repository markup text.
        """
        msg = "<b>%s</b>\n<small><i>%s</i>\n<b>%s</b></small>"
        if self.enabled():
            enabled_msg = _("Enabled")
        else:
            enabled_msg = _("Disabled")
        msg = msg % (
            escape_markup(self.repository()),
            escape_markup(self.description()),
            escape_markup(enabled_msg))
        return prepare_markup(msg)
