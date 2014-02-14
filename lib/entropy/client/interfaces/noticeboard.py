# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Notice Board functions Interface}.

"""
import hashlib
import os


from entropy.core.settings.base import SystemSettings
from entropy.const import const_file_readable, const_dir_writable, \
    const_convert_to_rawstring

from entropy.misc import RSS
from entropy.dump import loadobj as dump_loadobj, dumpobj as dump_dumpobj
from entropy.exceptions import RepositoryError


class NoticeBoard(object):

    """
    Main interface for handling Repository Notice Board user data,
    such as notice board items status, metadata retrieval, etc.
    """

    def __init__(self, repository_id):
        """
        Object constructor.

        @param repository_id: the repository identifier
        @type repository_id: string
        """
        self._repository_id = repository_id
        self._settings = SystemSettings()

    def _get_hash(self):
        """
        Return the noticeboard data and metadata hash string.
        """
        nb_data = self.data()

        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring("--"))

        for key in ("description", "pubDate", "title", "link", "id",):
            if key not in nb_data:
                continue
            elem = nb_data[key]

            elem_str = "{%s=%s}" % (key, elem)
            sha.update(const_convert_to_rawstring(elem_str))

        return sha.hexdigest()

    def data(self):
        """
        Return the noticeboard RSS metadata.

        This method is fault tolerant, except for invalid repository_id given,
        if repository notice board file is broken or not found an empty dict
        is returned.

        @return: repository metadata
        @rtype: dict
        @raise KeyError: if given repository identifier is not available
        """
        avail_data = self._settings['repositories']['available']
        nb_path = avail_data[self._repository_id]['local_notice_board']

        if not const_file_readable(nb_path):
            return {} # not found

        myrss = RSS(nb_path, '', '')
        data, data_len = myrss.get_entries()

        if data is None:
            return {}
        return data

    def _userdata(self):
        """
        Return the noticeboard user metadata.

        This dictionary contains misc noticeboard information for given
        repository, like (at the moment) items read status.

        @return: repository user metadata
        @rtype: dict
        @raise KeyError: if given repository identifier is not available
        """
        avail_data = self._settings['repositories']['available']
        nb_path = avail_data[self._repository_id]['local_notice_board']

        if not const_file_readable(nb_path):
            return {} # not found

        return dump_loadobj(nb_path, complete_path = True) or {}

    def _save_userdata(self, metadata):
        """
        Save the given noticeboard metadata to disk.

        @param metadata: repository user metadata to store
        @type metadata: dict
        @raise KeyError: if given repository identifier is not available
        @raise RepositoryError: if given repository directory is not available
        """
        avail_data = self._settings['repositories']['available']
        nb_path = avail_data[self._repository_id]['local_notice_board']

        nb_dir = os.path.dirname(nb_path)
        if not const_dir_writable(nb_dir):
            raise RepositoryError(
                "repository directory not available for %s" % (
                    self._repository_id,))

        return dump_dumpobj(nb_path, metadata, complete_path = True)

    def mark_read(self, item_id, read_status):
        """
        Set the given noticeboard item read status.

        This method also handles repository user metadata on-disk storage,
        this is a "one-shot" function, no need to call anything else.

        @param item_id: repository noticeboard item identifier
        @type item_id: int
        @param read_status: read status (True if read, False if not)
        @type read_status: bool
        @raise KeyError: if given repository identifier is not valid
        """
        data = self._userdata()
        obj = data.setdefault('read_items', set())
        if read_status:
            obj.add(item_id)
        else:
            obj.discard(item_id)

        return self._save_userdata(data)

    def items_read(self):
        """
        Return noticeboard items read status.

        @return: item identifiers marked as "read"
        @rtype: set
        """
        data = self._userdata()
        return data.get('read_items', set())

    def mark_all_read(self, status):
        """
        Mark all the noticeboard items as read or unread.

        The read status will be automatically tainted when
        noticeboard items are updated.

        @param status: True, if items must be marked as read, False
            otherwise
        @type status: bool
        """
        data = self._userdata()
        if status:
            data['as_read'] = self._get_hash()
        else:
            data['as_read'] = "0"

        return self._save_userdata(data)

    def is_all_read(self):
        """
        Return whether the noticeboard has been marked as read.
        """
        data = self._userdata()
        if 'as_read' not in data:
            return False

        return self._get_hash() == data['as_read']

    @classmethod
    def are_read(cls, repository_ids):
        """
        Return whether all the noticeboards of the repositories are marked as
        read.

        @param repository_ids: list of repository identifiers
        @type repository_ids: list
        @return: True if they are all marked as read, False otherwise
        @rtype: bool
        """
        for repository_id in repository_ids:
            nb = NoticeBoard(repository_id)
            if not nb.is_all_read():
                return False

        return True
