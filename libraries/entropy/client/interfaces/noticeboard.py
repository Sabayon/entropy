# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Notice Board functions Interface}.

"""
from __future__ import with_statement
import os
from entropy.misc import RSS
from entropy.dump import loadobj as dump_loadobj, dumpobj as dump_dumpobj
from entropy.exceptions import RepositoryError

class NoticeBoardMixin:

    """
    Main interface for handling Repository Notice Board user data,
    such as notice board items status, metadata retrieval, etc.
    """

    def get_noticeboard(self, repoid):
        """
        Return noticeboard RSS metadata (dict form) for given repository
        identifier.
        This method is fault tolerant, except for invalid repoid given,
        if repository notice board file is broken or not found an empty dict
        is returned.

        @param repoid: repository identifier
        @type repoid: string
        @return: repository metadata
        @rtype: dict
        @raise KeyError: if given repository identifier is not available
        """
        repo_data = self.SystemSettings['repositories']['available'][repoid]
        nb_path = repo_data['local_notice_board']

        if not os.access(nb_path, os.R_OK) and os.path.isfile(nb_path):
            return {} # not found

        # load RSS metadata and return if valid
        myrss = RSS(nb_path, '', '')
        data, data_len = myrss.get_entries()

        if data is None:
            return {}
        return data

    def get_noticeboard_userdata(self, repoid):
        """
        Return noticeboard user metadata dict for given repository identifier.
        This dictionary contains misc noticeboard information for given
        repository, like (at the moment) items read status.

        @param repoid: repository identifier
        @type repoid: string
        @return: repository user metadata
        @rtype: dict
        @raise KeyError: if given repository identifier is not available
        """
        repo_data = self.SystemSettings['repositories']['available'][repoid]
        nb_path = repo_data['local_notice_board_userdata']

        if not os.access(nb_path, os.R_OK) and os.path.isfile(nb_path):
            return {} # not found

        # load metadata
        data = dump_loadobj(nb_path, complete_path = True) or {}
        return data

    def store_noticeboard_userdata(self, repoid, metadata):
        """
        Store given noticeboard metadata for given repository to disk.

        @param repoid: repository identifier
        @type repoid: string
        @param metadata: repository user metadata to store
        @type metadata: dict
        @raise KeyError: if given repository identifier is not available
        @raise RepositoryError: if given repository directory is not available
        """
        repo_data = self.SystemSettings['repositories']['available'][repoid]
        nb_path = repo_data['local_notice_board_userdata']

        # check availability
        nb_dir = os.path.dirname(nb_path)
        if not (os.path.isdir(nb_dir) and os.access(nb_dir, os.W_OK)):
            raise RepositoryError(
                "repository directory not available for %s" % (repoid,))

        return dump_dumpobj(nb_path, metadata, complete_path = True)

    def set_noticeboard_item_read_status(self, repoid, item_id, read_status):
        """
        Set given noticeboard item read status.
        This method also handles repository user metadata on-disk storage,
        this is a "one-shot" function, no need to call anything else.

        @param repoid: repository identifier
        @type repoid: string
        @param item_id: repository noticeboard item identifier
        @type item_id: int
        @param read_status: read status (True if read, False if not)
        @type read_status: bool
        @raise KeyError: if given repository identifier is not valid
        """
        data = self.get_noticeboard_userdata(repoid)
        obj = data.setdefault('read_items', set())
        if read_status:
            obj.add(item_id)
        else:
            obj.discard(item_id)

        return self.store_noticeboard_userdata(repoid, data)

    def get_noticeboard_item_read_status(self, repoid):
        """
        Return noticeboard items read status for given repository identifier.

        @param repoid: repository identifier
        @type repoid: string
        @return: item identifiers marked as "read"
        @rtype: set
        """
        data = self.get_noticeboard_userdata(repoid)
        return data.get('read_items', set())

    def _get_noticeboard_hash(self, repoid):
        """
        Return noticeboard hash data.

        @param repoid: repository identifier
        @type repoid: string
        """
        nb_data = self.get_noticeboard(repoid)

        mystr = ''
        for key in ("description", "pubDate", "title", "link", "id",):
            if key not in nb_data:
                continue
            elem = nb_data[key]
            if not isinstance(elem, basestring):
                continue
            mystr += elem

        return self.entropyTools.md5string(mystr)

    def mark_noticeboard_items_as_read(self, repoid):
        """
        Mark noticeboard items for given repository as "read". "read" status
        will be automatically tainted when noticeboard changes.

        @param repoid: repository identifier
        @type repoid: string
        """
        data = self.get_noticeboard_userdata(repoid)
        data['as_read'] = self._get_noticeboard_hash(repoid)

        return self.store_noticeboard_userdata(repoid, data)

    def unmark_noticeboard_items_as_read(self, repoid):
        """
        Unmark noticeboard items for given repository as "read". "read" status
        will be automatically tainted when noticeboard changes.

        @param repoid: repository identifier
        @type repoid: string
        """
        data = self.get_noticeboard_userdata(repoid)
        data['as_read'] = "0000"

        return self.store_noticeboard_userdata(repoid, data)

    def is_noticeboard_marked_as_read(self, repoid):
        """
        Return whether noticeboard for given repository has been marked as
        "read" by user.

        @param repoid: repository identifier
        @type repoid: string
        """
        data = self.get_noticeboard_userdata(repoid)
        if not data.has_key('as_read'):
            return False
        nb_hash = self._get_noticeboard_hash(repoid)
        return nb_hash == data['as_read']

    def are_noticeboards_marked_as_read(self):
        """
        Return whether all available repository noticeboards are marked as
        read.

        @return: read status
        @rtype: bool
        """
        for repoid in self.validRepositories:
            if not self.is_noticeboard_marked_as_read(repoid):
                return False
        return True
