# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
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
from entropy.const import etpConst
from entropy.core import Singleton
from entropy.db import EntropyRepository

import entropy.dep
import entropy.tools

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


class ServerPackagesRepository(EntropyRepository):
    """
    This class represents the installed packages repository and is a direct
    subclass of EntropyRepository.
    """

    @staticmethod
    def revision(repository_id):
        """
        Reimplemented from EntropyRepository
        """
        from entropy.server.interfaces import Server
        srv = Server()
        return srv.get_local_repository_revision(repo = repository_id)

    @staticmethod
    def remote_revision(repository_id):
        """
        Reimplemented from EntropyRepository
        """
        from entropy.server.interfaces import Server
        srv = Server()
        return srv.get_remote_repository_revision(repo = repository_id)

    @staticmethod
    def update(entropy_client, repository_id, force, gpg):
        """
        Reimplemented from EntropyRepository
        """
        return ServerPackagesRepositoryUpdater(entropy_client, repository_id,
            force, gpg).update()

    def maskFilter(self, package_id, live = True):
        """
        Reimplemented from EntropyRepository.
        Server-side repositories do not feature any masked package. So, it's
        safe to always consider package_id valid.
        """
        return package_id, 0

    def handlePackage(self, pkg_data, forcedRevision = -1,
        formattedContent = False):
        """
        Reimplemented from EntropyRepository.
        """

        # build atom string, server side
        pkgatom = entropy.dep.create_package_atom_string(
            pkg_data['category'], pkg_data['name'], pkg_data['version'],
            pkg_data['versiontag'])

        current_rev = forcedRevision

        manual_deps = set()
        # Remove entries in the same scope.
        for package_id in self.getPackageIds(pkgatom):

            if forcedRevision == -1:
                myrev = self.retrieveRevision(package_id)
                if myrev > current_rev:
                    current_rev = myrev

            #
            manual_deps |= self.retrieveManualDependencies(package_id)
            # injected packages wouldn't be removed by addPackage
            self.removePackage(package_id, do_cleanup = False,
                do_commit = False)

        if forcedRevision == -1:
            current_rev += 1

        # manual dependencies handling
        removelist = self.getPackagesToRemove(
            pkg_data['name'], pkg_data['category'],
            pkg_data['slot'], pkg_data['injected']
        )

        for r_package_id in removelist:
            manual_deps |= self.retrieveManualDependencies(r_package_id)
            self.removePackage(r_package_id, do_cleanup = False,
                do_commit = False)

        # inject old manual dependencies back to package metadata
        for manual_dep in manual_deps:
            if manual_dep in pkg_data['dependencies']:
                continue
            pkg_data['dependencies'][manual_dep] = \
                etpConst['dependency_type_ids']['mdepend_id']

        # add the new one
        return self.addPackage(pkg_data, revision = current_rev,
            formatted_content = formattedContent)


class ServerPackagesRepositoryUpdater(object):

    """
    This class handles the repository update across all the configured mirrors.
    It is used by entropy.server.interfaces.mirrors module and called from
    inside ServerPackagesRepository class.
    """

    def __init__(self, entropy_server, repository_id, force, gpg):
        """
        ServerPackagesRepositoryUpdater constructor, called by
        ServerPackagesRepository.
        """
        self._entropy = entropy_server
        self._repository_id = repository_id
        self._force = force
        self._gpg = gpg

    def update(self):
        """
        Executes the repository update by calling
        Server.Mirrors.sync_repositories().
        TODO: move logic here.
        """
        rc, x, y = self._entropy.Mirrors.sync_repositories(
            repo = self._repository_id)
        return rc
