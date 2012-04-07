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
from rigo.utils import escape_markup, prepare_markup

class ConfigUpdate(object):

    def __init__(self, source, metadata, rigo_service):
        self._source = source
        self._metadata = metadata
        self._service = rigo_service

    def source(self):
        """
        Return source file path (pointer to proposed
        configuration file).
        """
        return self._source

    def destination(self):
        """
        Return destination file path (pointer to file
        to be replaced).
        """
        return self._metadata['destination']

    def root(self):
        """
        Return current ROOT prefix (usually "").
        """
        return self._metadata['root']

    def package_ids(self):
        """
        Return the list of package identifiers owning the
        destination file.
        """
        return self._metadata['package_ids']

    def get_markup(self):
        """
        Return ConfigurationUpdate markup text.
        """
        return escape_markup(
            self.source() + " -> " + self.destination())
