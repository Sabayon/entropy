# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

from __future__ import with_statement
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
                'from': unicode(self), # from what class
            },
            'repository_server:pkginfo':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_pkginfo,
                'args': ["myargs"],
                'as_user': False,
                'desc': "returns idpackage differences against the latest available repository",
                'syntax': "<SESSION_ID> repository_server:pkginfo <content fmt True/False> <repository> <arch> <product> <branch> <idpackage>",
                'from': unicode(self), # from what class
            },
            'repository_server:treeupdates':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_treeupdates,
                'args': ["myargs"],
                'as_user': False,
                'desc': "returns repository treeupdates metadata",
                'syntax': "<SESSION_ID> repository_server:treeupdates <repository> <arch> <product> <branch>",
                'from': unicode(self), # from what class
            },
            'repository_server:get_package_sets': {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_package_sets,
                'args': ["myargs"],
                'as_user': False,
                'desc': "returns repository package sets metadata",
                'syntax': "<SESSION_ID> repository_server:get_package_sets <repository> <arch> <product> <branch>",
                'from': unicode(self), # from what class
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
        except (UnicodeEncodeError,UnicodeDecodeError,):
            return None
        foreign_idpackages = myargs[4:]
        x = (repository,arch,product,branch,)

        valid = self.HostInterface.is_repository_available(x)
        if not valid:
            return valid

        dbpath = self.get_database_path(repository, arch, product, branch)
        dbconn = self.HostInterface.open_db(dbpath, docache = False)
        mychecksum = dbconn.database_checksum(do_order = True, strict = False, strings = True)
        myids = dbconn.listAllIdpackages()
        dbconn.closeDB()
        foreign_idpackages = set(foreign_idpackages)

        removed_ids = foreign_idpackages - myids
        added_ids = myids - foreign_idpackages

        return {'removed': removed_ids, 'added': added_ids, 'checksum': mychecksum}

    def docmd_package_sets(self, myargs):

        self.trash_old_databases()

        if len(myargs) < 4:
            return None
        repository = myargs[0]
        arch = myargs[1]
        product = myargs[2]
        try:
            branch = str(myargs[3])
        except (UnicodeEncodeError,UnicodeDecodeError,):
            return None

        x = (repository,arch,product,branch,)
        valid = self.HostInterface.is_repository_available(x)
        if not valid:
            return valid

        cached = self.HostInterface.get_dcache((repository, arch, product, branch, 'docmd_package_sets'), repository)
        if cached != None:
            return cached

        dbpath = self.get_database_path(repository, arch, product, branch)
        dbconn = self.HostInterface.open_db(dbpath, docache = False)

        # get data
        data = dbconn.retrievePackageSets()

        self.HostInterface.set_dcache((repository, arch, product, branch, 'docmd_package_sets'), data, repository)
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
        except (UnicodeEncodeError,UnicodeDecodeError,):
            return None

        x = (repository,arch,product,branch,)
        valid = self.HostInterface.is_repository_available(x)
        if not valid:
            return valid

        cached = self.HostInterface.get_dcache((repository, arch, product, branch, 'docmd_treeupdates'), repository)
        if cached != None:
            return cached

        dbpath = self.get_database_path(repository, arch, product, branch)
        dbconn = self.HostInterface.open_db(dbpath, docache = False)

        # get data
        data = {}
        data['actions'] = dbconn.listAllTreeUpdatesActions()
        data['digest'] = dbconn.retrieveRepositoryUpdatesDigest(repository)

        self.HostInterface.set_dcache((repository, arch, product, branch, 'docmd_treeupdates'), data, repository)
        dbconn.closeDB()

        return data


    def docmd_pkginfo(self, myargs):

        self.trash_old_databases()

        if len(myargs) < 6:
            return None
        format_content_for_insert = myargs[0]
        if type(format_content_for_insert) is not bool:
            format_content_for_insert = False
        repository = myargs[1]
        arch = myargs[2]
        product = myargs[3]
        try:
            branch = str(myargs[4])
        except (UnicodeEncodeError,UnicodeDecodeError,):
            return None
        zidpackages = myargs[5:]
        idpackages = []
        for idpackage in zidpackages:
            if type(idpackage) is int:
                idpackages.append(idpackage)
        if not idpackages:
            return None
        idpackages = tuple(sorted(idpackages))
        x = (repository,arch,product,branch,)

        valid = self.HostInterface.is_repository_available(x)
        if not valid:
            return valid

        cached = self.HostInterface.get_dcache(
            (repository, arch, product, branch, idpackages, 'docmd_pkginfo'),
            repository
        )
        if cached != None:
            return cached

        dbpath = self.get_database_path(repository, arch, product, branch)
        dbconn = self.HostInterface.open_db(dbpath, docache = False)

        result = {}
        for idpackage in idpackages:
            try:
                mydata = dbconn.getPackageData(
                    idpackage,
                    content_insert_formatted = format_content_for_insert,
                    trigger_unicode = True
                )
            except:
                tb = self.entropyTools.getTraceback()
                print tb
                self.HostInterface.socketLog.write(tb)
                dbconn.closeDB()
                return None
            result[idpackage] = mydata.copy()

        self.HostInterface.set_dcache(
            (repository, arch, product, branch, idpackages, 'docmd_pkginfo'),
            result,
            repository
        )
        dbconn.closeDB()
        return result

    def get_database_path(self, repository, arch, product, branch):
        repoitems = (repository,arch,product,branch,)
        mydbroot = self.HostInterface.repositories[repoitems]['dbpath']
        dbpath = os.path.join(mydbroot,etpConst['etpdatabasefile'])
        return dbpath