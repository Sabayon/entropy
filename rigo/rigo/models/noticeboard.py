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


class Notice(object):

    def __init__(self, repository, notice_id, metadata):
        self._repository = repository
        self._notice_id = notice_id
        self._metadata = metadata

    def __str__(self):
        """
        String representation of Notice object
        """
        return "Notice{%s, %s, %s}" % (
            self._repository, self._notice_id,
            self._metadata)

    def repository(self):
        """
        Return the Repository name from where this Notice is coming.
        """
        return self._repository

    def notice_id(self):
        """
        Return the Notice identifier (it's unique among Notice objects
        coming from the same NoticeBoard).
        """
        return self._notice_id

    def date(self):
        """
        Return Notice date (string representation, RFC822).
        """
        return self._metadata['pubDate']

    def parsed_date(self):
        """
        Parse Notice date using basing on RFC822 and return
        tuple that can be used as sort key.
        """
        return email.utils.parsedate_tz(self.date())

    def description(self):
        """
        Return Notice description string.
        """
        return self._metadata['description']

    def title(self):
        """
        Return Notice title string.
        """
        return self._metadata['title']

    def link(self):
        """
        Return Notice link string.
        """
        return self._metadata['link']

    def guid(self):
        """
        Return Notice guid (as in RSS guid) string.
        """
        return self._metadata['guid']

    def hash(self):
        """
        Return a stringy hash
        """
        m = hashlib.md5()
        m.update(self.repository() + "|")
        m.update("%s|" % (self.notice_id(),))
        m.update(self.date() + "|")
        m.update(self.description() + "|")
        m.update(self.title() + "|")
        m.update(self.link() + "|")
        m.update(self.guid())
        return m.hexdigest()

    def get_markup(self):
        """
        Return ConfigurationUpdate markup text.
        """
        msg = "<b>%s</b>\n<small><b>%s</b>, " + \
            "<i>%s</i>\n<u>%s</u></small>"
        msg = msg % (
            escape_markup(self.title()),
            escape_markup(self.repository()),
            escape_markup(self.date()),
            escape_markup(self.link()))
        return prepare_markup(msg)
