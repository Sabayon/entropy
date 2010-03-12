# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Services Repository Management Command Interface}.

"""

import os
from entropy.services.skel import SocketCommands
from entropy.const import etpConst

class Repository(SocketCommands):

    import entropy.dump as dumpTools
    import entropy.tools as entropyTools

    def __init__(self, HostInterface):

        SocketCommands.__init__(self, HostInterface, inst_name = "repository_server")

        self.valid_commands = {
            'repository_server:dbdiff':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_dbdiff,
                'args': ["myargs"],
                'as_user': False,
                'desc': "returns idpackage differences against the latest available repository",
                'syntax': "<SESSION_ID> repository_server:dbdiff <repository> <arch> <product> <branch> [idpackages]",
                'from': str(self), # from what class
            },
            'repository_server:pkginfo_strict':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_pkginfo_strict,
                'args': ["myargs"],
                'as_user': False,
                'desc': "returns metadata of the provided idpackages excluding 'content'",
                'syntax': "<SESSION_ID> repository_server:pkginfo_strict <content fmt True/False> <repository> <arch> <product> <branch> <idpackage>",
                'from': str(self), # from what class
            },
            'repository_server:treeupdates':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_treeupdates,
                'args': ["myargs"],
                'as_user': False,
                'desc': "returns repository treeupdates metadata",
                'syntax': "<SESSION_ID> repository_server:treeupdates <repository> <arch> <product> <branch>",
                'from': str(self), # from what class
            },
            'repository_server:get_package_sets': {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_package_sets,
                'args': ["myargs"],
                'as_user': False,
                'desc': "returns repository package sets metadata",
                'syntax': "<SESSION_ID> repository_server:get_package_sets <repository> <arch> <product> <branch>",
                'from': str(self), # from what class
            },
            'repository_server:get_repository_metadata': {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_repository_metadata,
                'args': ["myargs"],
                'as_user': False,
                'desc': "returns repository metadata (package sets, treeupdates, libraries <=> idpackages map)",
                'syntax': "<SESSION_ID> repository_server:get_repository_metadata <repository> <arch> <product> <branch>",
                'from': str(self), # from what class
            }
        }

    def trash_old_databases(self):
        for db in self.HostInterface.syscache['db_trashed']:
            db.closeDB()
        self.HostInterface.syscache['db_trashed'].clear()

    def docmd_dbdiff(self, myargs):

        self.trash_old_databases()

        if len(myargs) < 5:
            return None
        repository = myargs[0]
        arch = myargs[1]
        product = myargs[2]
        try:
            branch = str(myargs[3])
        except (UnicodeEncodeError, UnicodeDecodeError,):
            return None
        foreign_idpackages = myargs[4:]
        x = (repository, arch, product, branch,)

        valid = self.HostInterface.is_repository_available(x)
        if not valid:
            return valid

        dbpath = self.get_database_path(repository, arch, product, branch)
        mtime = self.get_database_mtime(repository, arch, product, branch)

        cached = self.HostInterface.get_dcache(x + ('docmd_dbdiff', mtime,),
            repository)
        if cached is not None:
            std_checksum, secure_checksum, myids = cached
        else:
            dbconn = self.HostInterface.open_db(dbpath, docache = False)
            std_checksum = dbconn.checksum(do_order = True, strict = False,
                strings = True)
            secure_checksum = dbconn.checksum(do_order = True, strict = False,
                strings = True, include_signatures = True)
            myids = dbconn.listAllIdpackages()
            cached = std_checksum, secure_checksum, myids
            self.HostInterface.set_dcache(x + ('docmd_dbdiff', mtime,), cached,
                repository)
            dbconn.closeDB()

        foreign_idpackages = set(foreign_idpackages)

        removed_ids = foreign_idpackages - myids
        added_ids = myids - foreign_idpackages

        data = {
            'removed': removed_ids,
            'added': added_ids,
            'checksum': std_checksum,
            'secure_checksum': secure_checksum,
        }

        return data

    def docmd_repository_metadata(self, myargs):

        self.trash_old_databases()

        if len(myargs) < 4:
            return None
        repository = myargs[0]
        arch = myargs[1]
        product = myargs[2]
        try:
            branch = str(myargs[3])
        except (UnicodeEncodeError, UnicodeDecodeError,):
            return None

        x = (repository, arch, product, branch,)
        valid = self.HostInterface.is_repository_available(x)
        if not valid:
            return valid

        mtime = self.get_database_mtime(repository, arch, product, branch)
        cached = self.HostInterface.get_dcache((repository, arch, product, branch, 'docmd_repository_metadata', mtime), repository)
        if cached is not None:
            return cached

        metadata = {}
        dbpath = self.get_database_path(repository, arch, product, branch)
        dbconn = self.HostInterface.open_db(dbpath, docache = False)
        metadata['sets'] = dbconn.retrievePackageSets()
        metadata['treeupdates_actions'] = dbconn.listAllTreeUpdatesActions()
        metadata['treeupdates_digest'] = dbconn.retrieveRepositoryUpdatesDigest(repository)
        # FIXME: kept for backward compatibility (<=0.99.0.x) remove in future
        metadata['library_idpackages'] = []
        metadata['revision'] = self.get_database_revision(repository, arch,
            product, branch)

        self.HostInterface.set_dcache((repository, arch, product, branch, 'docmd_repository_metadata', mtime), metadata, repository)
        dbconn.closeDB()

        return metadata


    def docmd_package_sets(self, myargs):

        self.trash_old_databases()

        if len(myargs) < 4:
            return None
        repository = myargs[0]
        arch = myargs[1]
        product = myargs[2]
        try:
            branch = str(myargs[3])
        except (UnicodeEncodeError, UnicodeDecodeError,):
            return None

        x = (repository, arch, product, branch,)
        valid = self.HostInterface.is_repository_available(x)
        if not valid:
            return valid

        mtime = self.get_database_mtime(repository, arch, product, branch)
        cached = self.HostInterface.get_dcache((repository, arch, product, branch, 'docmd_package_sets', mtime), repository)
        if cached is not None:
            return cached

        dbpath = self.get_database_path(repository, arch, product, branch)
        dbconn = self.HostInterface.open_db(dbpath, docache = False)

        # get data
        data = dbconn.retrievePackageSets()

        self.HostInterface.set_dcache((repository, arch, product, branch, 'docmd_package_sets', mtime), data, repository)
        dbconn.closeDB()

        return data


    def docmd_treeupdates(self, myargs):

        self.trash_old_databases()

        if len(myargs) < 4:
            return None
        repository = myargs[0]
        arch = myargs[1]
        product = myargs[2]
        try:
            branch = str(myargs[3])
        except (UnicodeEncodeError, UnicodeDecodeError,):
            return None

        x = (repository, arch, product, branch,)
        valid = self.HostInterface.is_repository_available(x)
        if not valid:
            return valid

        mtime = self.get_database_mtime(repository, arch, product, branch)
        cached = self.HostInterface.get_dcache((repository, arch, product, branch, 'docmd_treeupdates', mtime), repository)
        if cached is not None:
            return cached

        dbpath = self.get_database_path(repository, arch, product, branch)
        dbconn = self.HostInterface.open_db(dbpath, docache = False)

        # get data
        data = {}
        data['actions'] = dbconn.listAllTreeUpdatesActions()
        data['digest'] = dbconn.retrieveRepositoryUpdatesDigest(repository)

        self.HostInterface.set_dcache((repository, arch, product, branch, 'docmd_treeupdates', mtime), data, repository)
        dbconn.closeDB()

        return data


    def docmd_pkginfo_strict(self, myargs):

        self.trash_old_databases()

        if len(myargs) < 6:
            return None
        format_content_for_insert = myargs[0]
        if not isinstance(format_content_for_insert, bool):
            format_content_for_insert = False
        repository = myargs[1]
        arch = myargs[2]
        product = myargs[3]
        try:
            branch = str(myargs[4])
        except (UnicodeEncodeError, UnicodeDecodeError,):
            return None
        zidpackages = myargs[5:]
        idpackages = []
        for idpackage in zidpackages:
            if isinstance(idpackage, int):
                idpackages.append(idpackage)
        if not idpackages:
            return None
        idpackages = tuple(sorted(idpackages))
        x = (repository, arch, product, branch,)

        valid = self.HostInterface.is_repository_available(x)
        if not valid:
            return valid

        mtime = self.get_database_mtime(repository, arch, product, branch)
        cached = self.HostInterface.get_dcache(
            (repository, arch, product, branch, idpackages, 'docmd_pkginfo_strict', mtime),
            repository
        )
        if cached is not None:
            return cached

        dbpath = self.get_database_path(repository, arch, product, branch)
        dbconn = self.HostInterface.open_db(dbpath, docache = False)

        result = {}
        for idpackage in idpackages:
            try:
                mydata = dbconn.getPackageData(
                    idpackage,
                    content_insert_formatted = format_content_for_insert,
                    get_content = False, get_changelog = False
                )
            except:
                tb = self.entropyTools.get_traceback()
                print(tb)
                self.HostInterface.socketLog.write(tb)
                dbconn.closeDB()
                return None
            result[idpackage] = mydata.copy()

        self.HostInterface.set_dcache(
            (repository, arch, product, branch, idpackages, 'docmd_pkginfo_strict', mtime),
            result,
            repository
        )
        dbconn.closeDB()
        return result

    def get_database_path(self, repository, arch, product, branch):
        repoitems = (repository, arch, product, branch,)
        mydbroot = self.HostInterface.repositories[repoitems]['dbpath']
        dbpath = os.path.join(mydbroot, etpConst['etpdatabasefile'])
        return dbpath

    def get_database_mtime(self, repository, arch, product, branch):
        dbpath = self.get_database_path(repository, arch, product, branch)
        try:
            mtime = os.path.getmtime(dbpath)
        except (OSError, IOError,):
            mtime = 0.0
        return mtime

    def get_database_revision(self, repository, arch, product, branch):
        repoitems = (repository, arch, product, branch,)
        mydbroot = self.HostInterface.repositories[repoitems]['dbpath']
        dbrev_path = os.path.join(mydbroot, etpConst['etpdatabaserevisionfile'])
        dbrev = -1
        if os.path.isfile(dbrev_path) and os.access(dbrev_path, os.R_OK):
            db_f = open(dbrev_path, "r")
            f_dbrev = db_f.readline().strip()
            db_f.close()
            try:
                dbrev = int(f_dbrev)
            except ValueError:
                pass
        return dbrev
