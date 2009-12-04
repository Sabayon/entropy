# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server Main Interfaces}.

    I{ServerRepositoryStatus} is a singleton containing the status of
    server-side repositories. It is used to determine if repository has
    been modified (tainted) or has been revision bumped already.
    Revision bumps are automatic and happen on the very first data "commit".
    Every repository features a revision number which is stored into the
    "packages.db.revision" file. Only server-side (or community) repositories
    are subject to this automation (revision file update on commit).

"""
from entropy.core import Singleton

class ServerRepositoryStatus(Singleton):

    """
    Server-side Repositories status information container.
    """

    def init_singleton(self):
        """ Singleton "constructor" """
        self.__data = {}
        self.__updates_log = {}

    def __create_if_necessary(self, db):
        if db not in self.__data:
            self.__data[db] = {}
            self.__data[db]['tainted'] = False
            self.__data[db]['bumped'] = False
            self.__data[db]['unlock_msg'] = False

    def set_unlock_msg(self, db):
        """
        Set bit which determines if the unlock warning has been already
        printed to user.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['unlock_msg'] = True

    def unset_unlock_msg(self, db):
        """
        Unset bit which determines if the unlock warning has been already
        printed to user.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['unlock_msg'] = False

    def set_tainted(self, db):
        """
        Set bit which determines if the repository which db points to has been
        modified.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['tainted'] = True

    def unset_tainted(self, db):
        """
        Unset bit which determines if the repository which db points to has been
        modified.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['tainted'] = False

    def set_bumped(self, db):
        """
        Set bit which determines if the repository which db points to has been
        revision bumped.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['bumped'] = True

    def unset_bumped(self, db):
        """
        Unset bit which determines if the repository which db points to has been
        revision bumped.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['bumped'] = False

    def is_tainted(self, db):
        """
        Return whether repository which db points to has been modified.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        return self.__data[db]['tainted']

    def is_bumped(self, db):
        """
        Return whether repository which db points to has been revision bumped.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        return self.__data[db]['bumped']

    def is_unlock_msg(self, db):
        """
        Return whether repository which db points to has outputed the unlock
        warning message.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        return self.__data[db]['unlock_msg']

    def get_updates_log(self, db):
        """
        Return dict() object containing metadata related to package
        updates occured in a server-side repository.
        """
        if db not in self.__updates_log:
            self.__updates_log[db] = {}
        return self.__updates_log[db]
