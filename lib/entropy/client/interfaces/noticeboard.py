# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Notice Board functions Interface}.

"""
import os
from entropy.const import const_isstring, const_file_readable, \
    const_dir_writable
from entropy.misc import RSS
from entropy.dump import loadobj as dump_loadobj, dumpobj as dump_dumpobj
from entropy.exceptions import RepositoryError

import entropy.tools

class NoticeBoardMixin:

    """
    Main interface for handling Repository Notice Board user data,
    such as notice board items status, metadata retrieval, etc.
    """

    def get_noticeboard(self, repository_id):
        """
        Return noticeboard RSS metadata (dict form) for given repository
        identifier.
        This method is fault tolerant, except for invalid repository_id given,
        if repository notice board file is broken or not found an empty dict
        is returned.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: repository metadata
        @rtype: dict
        @raise KeyError: if given repository identifier is not available
        """
        repo_data = self._settings['repositories']['available'][repository_id]
        nb_path = repo_data['local_notice_board']

        if not const_file_readable(nb_path):
            return {} # not found

        # load RSS metadata and return if valid
        myrss = RSS(nb_path, '', '')
        data, data_len = myrss.get_entries()

        if data is None:
            return {}
        return data

    def get_noticeboard_userdata(self, repository_id):
        """
        Return noticeboard user metadata dict for given repository identifier.
        This dictionary contains misc noticeboard information for given
        repository, like (at the moment) items read status.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: repository user metadata
        @rtype: dict
        @raise KeyError: if given repository identifier is not available
        """
        repo_data = self._settings['repositories']['available'][repository_id]
        nb_path = repo_data['local_notice_board_userdata']

        if not const_file_readable(nb_path):
            return {} # not found

        # load metadata
        data = dump_loadobj(nb_path, complete_path = True) or {}
        return data

    def store_noticeboard_userdata(self, repository_id, metadata):
        """
        Store given noticeboard metadata for given repository to disk.

        @param repository_id: repository identifier
        @type repository_id: string
        @param metadata: repository user metadata to store
        @type metadata: dict
        @raise KeyError: if given repository identifier is not available
        @raise RepositoryError: if given repository directory is not available
        """
        repo_data = self._settings['repositories']['available'][repository_id]
        nb_path = repo_data['local_notice_board_userdata']

        # check availability
        nb_dir = os.path.dirname(nb_path)
        if not const_dir_writable(nb_dir):
            raise RepositoryError(
                "repository directory not available for %s" % (repository_id,))

        return dump_dumpobj(nb_path, metadata, complete_path = True)

    def set_noticeboard_item_read_status(self, repository_id, item_id,
        read_status):
        """
        Set given noticeboard item read status.
        This method also handles repository user metadata on-disk storage,
        this is a "one-shot" function, no need to call anything else.

        @param repository_id: repository identifier
        @type repository_id: string
        @param item_id: repository noticeboard item identifier
        @type item_id: int
        @param read_status: read status (True if read, False if not)
        @type read_status: bool
        @raise KeyError: if given repository identifier is not valid
        """
        data = self.get_noticeboard_userdata(repository_id)
        obj = data.setdefault('read_items', set())
        if read_status:
            obj.add(item_id)
        else:
            obj.discard(item_id)

        return self.store_noticeboard_userdata(repository_id, data)

    def get_noticeboard_item_read_status(self, repository_id):
        """
        Return noticeboard items read status for given repository identifier.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: item identifiers marked as "read"
        @rtype: set
        """
        data = self.get_noticeboard_userdata(repository_id)
        return data.get('read_items', set())

    def _get_noticeboard_hash(self, repository_id):
        """
        Return noticeboard hash data.

        @param repository_id: repository identifier
        @type repository_id: string
        """
        nb_data = self.get_noticeboard(repository_id)

        mystr = ''
        for key in ("description", "pubDate", "title", "link", "id",):
            if key not in nb_data:
                continue
            elem = nb_data[key]
            if not const_isstring(elem):
                continue
            mystr += elem

        return entropy.tools.md5string(mystr)

    def mark_noticeboard_items_as_read(self, repository_id):
        """
        Mark noticeboard items for given repository as "read". "read" status
        will be automatically tainted when noticeboard changes.

        @param repository_id: repository identifier
        @type repository_id: string
        """
        data = self.get_noticeboard_userdata(repository_id)
        data['as_read'] = self._get_noticeboard_hash(repository_id)

        return self.store_noticeboard_userdata(repository_id, data)

    def unmark_noticeboard_items_as_read(self, repository_id):
        """
        Unmark noticeboard items for given repository as "read". "read" status
        will be automatically tainted when noticeboard changes.

        @param repository_id: repository identifier
        @type repository_id: string
        """
        data = self.get_noticeboard_userdata(repository_id)
        data['as_read'] = "0000"

        return self.store_noticeboard_userdata(repository_id, data)

    def is_noticeboard_marked_as_read(self, repository_id):
        """
        Return whether noticeboard for given repository has been marked as
        "read" by user.

        @param repository_id: repository identifier
        @type repository_id: string
        """
        data = self.get_noticeboard_userdata(repository_id)
        if 'as_read' not in data:
            return False
        nb_hash = self._get_noticeboard_hash(repository_id)
        return nb_hash == data['as_read']

    def are_noticeboards_marked_as_read(self):
        """
        Return whether all available repository noticeboards are marked as
        read.

        @return: read status
        @rtype: bool
        """
        for repository_id in self._enabled_repos:
            if not self.is_noticeboard_marked_as_read(repository_id):
                return False
        return True
