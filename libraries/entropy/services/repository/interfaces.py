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
from entropy.services.interfaces import SocketHost
from entropy.output import TextInterface, blue, brown
from entropy.const import etpConst, etpCache
from entropy.misc import TimeScheduled
from entropy.i18n import _

class Server(SocketHost):

    class ServiceInterface(TextInterface):
        def __init__(self, *args, **kwargs):
            pass

    import entropy.tools as entropyTools
    import entropy.dump as dumpTools
    def __init__(self, repositories, do_ssl = False, stdout_logging = True, **kwargs):

        # instantiate critical constants
        etpConst['socket_service']['max_connections'] = 5000

        from entropy.services.repository.commands import Repository
        self.RepositoryCommands = Repository
        from entropy.db import dbapi2
        self.dbapi2 = dbapi2
        from entropy.client.interfaces import Client
        self.Entropy = Client(noclientdb = 2)
        self.do_ssl = do_ssl
        self.LockScanner = None
        self.syscache = {
            'db': {},
            'db_trashed': set(),
            'dbs_not_available': set(),
        }

        # setup System Settings
        from entropy.core import SystemSettings
        self.SystemSettings = SystemSettings()
        self.SystemSettings['socket_service']['max_connections'] = 5000

        etpConst['socketloglevel'] = 1
        if not kwargs.has_key('external_cmd_classes'):
            kwargs['external_cmd_classes'] = []
        kwargs['external_cmd_classes'].insert(0,self.RepositoryCommands)
        SocketHost.__init__(
            self,
            self.ServiceInterface,
            noclientdb = 2,
            sock_output = self.Entropy,
            ssl = do_ssl,
            **kwargs
        )
        self.stdout_logging = stdout_logging
        self.repositories = repositories
        self.expand_repositories()
        # start timed lock file scanning
        self.start_repository_lock_scanner()

    def killall(self):
        SocketHost.killall(self)
        if self.LockScanner != None:
            self.LockScanner.kill()

    def start_repository_lock_scanner(self):
        self.LockScanner = TimeScheduled(0.5, self.lock_scan)
        self.LockScanner.start()

    def set_repository_db_availability(self, repo_tuple):
        self.repositories[repo_tuple]['enabled'] = False
        mydbpath = os.path.join(self.repositories[repo_tuple]['dbpath'],etpConst['etpdatabasefile'])
        if os.path.isfile(mydbpath) and os.access(mydbpath, os.W_OK):
            self.syscache['dbs_not_available'].discard(repo_tuple)
            self.repositories[repo_tuple]['enabled'] = True

    def is_repository_available(self, repo_tuple):

        if repo_tuple not in self.repositories:
            return None
        # is repository being updated
        if self.repositories[repo_tuple]['locked']:
            return False
        # repository database does not exist
        if not self.repositories[repo_tuple]['enabled']:
            return False

        return True

    def lock_scan(self):
        do_clear = set()
        for repository,arch,product,branch in self.repositories:
            x = (repository,arch,product,branch,)
            self.set_repository_db_availability(x)
            if not self.repositories[x]['enabled']:
                if x in self.syscache['dbs_not_available']:
                    continue
                self.syscache['dbs_not_available'].add(x)
                mytxt = blue("%s.") % (_("database does not exist. Locking services for it"),)
                self.updateProgress(
                    "[%s] %s" % (
                            brown(str(x)),
                            mytxt,
                    ),
                    importance = 1,
                    type = "info"
                )
                do_clear.add(repository)
                continue
            if os.path.isfile(self.repositories[x]['download_lock']) and \
                not self.repositories[x]['locked']:
                    self.repositories[x]['locked'] = True
                    mydbpath = os.path.join(self.repositories[x]['dbpath'],etpConst['etpdatabasefile'])
                    self.close_db(mydbpath)
                    self.eapi3_lock_repo(*x)
                    do_clear.add(repository)
                    mytxt = blue("%s.") % (_("database got locked. Locking services for it"),)
                    self.updateProgress(
                        "[%s] %s" % (
                                brown(str(x)),
                                mytxt,
                        ),
                        importance = 1,
                        type = "info"
                    )
            elif not os.path.isfile(self.repositories[x]['download_lock']) and \
                self.repositories[x]['locked']:
                mydbpath = os.path.join(self.repositories[x]['dbpath'],etpConst['etpdatabasefile'])
                self.close_db(mydbpath)
                mytxt = blue("%s. %s:") % (
                    _("unlocking and indexing database"),
                    _("hash"),
                )
                self.updateProgress(
                    "[%s] %s" % (
                            brown(str(x)),
                            mytxt,
                    ),
                    importance = 1,
                    type = "info"
                )
                # woohoo, got unlocked eventually
                mydb = self.open_db(mydbpath, docache = False)
                mydb.createAllIndexes()
                self.updateProgress(
                    str(mydb.database_checksum(do_order = True, strict = False, strings = True)),
                    importance = 1,
                    type = "info"
                )
                mydb.closeDB()
                self.Entropy.clear_dump_cache(etpCache['repository_server']+"/"+repository+"/")
                self.repositories[x]['locked'] = False
                self.eapi3_unlock_repo(*x)

        for repo in do_clear:
            self.Entropy.clear_dump_cache(etpCache['repository_server']+"/"+repo+"/")

    def eapi3_lock_repo(self, repository, arch, product, branch):
        lock_file = os.path.join(self.repositories[(repository, arch, product, branch,)]['dbpath'],etpConst['etpdatabaseeapi3lockfile'])
        if not os.path.lexists(lock_file):
            f = open(lock_file,"w")
            f.write("this repository is EAPI3 locked")
            f.flush()
            f.close()

    def eapi3_unlock_repo(self, repository, arch, product, branch):
        lock_file = os.path.join(self.repositories[(repository, arch, product, branch,)]['dbpath'],etpConst['etpdatabaseeapi3lockfile'])
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def get_dcache(self, item, repo = '_norepo_'):
        return self.dumpTools.loadobj(etpCache['repository_server']+"/"+repo+"/"+str(hash(item)))

    def set_dcache(self, item, data, repo = '_norepo_'):
        self.dumpTools.dumpobj(etpCache['repository_server']+"/"+repo+"/"+str(hash(item)),data)

    def close_db(self, dbpath):
        try:
            dbc = self.syscache['db'].pop(dbpath)
            dbc.closeDB()
        except KeyError:
            pass
        except self.dbapi2.ProgrammingError:
            # they've been opened by the Commands Processor
            self.syscache['db_trashed'].add(dbc)

    def open_db(self, dbpath, docache = True):
        if docache:
            cached = self.syscache['db'].get(dbpath)
            if cached != None:
                return cached
        dbc = self.Entropy.open_generic_database(
            dbpath,
            xcache = False,
            readOnly = True,
            skipChecks = True
        )
        if docache:
            self.syscache['db'][dbpath] = dbc
        return dbc

    def expand_repositories(self):

        for repository,arch,product, branch in self.repositories:
            x = (repository,arch,product,branch,)
            self.repositories[x]['locked'] = True # loading locked
            self.set_repository_db_availability(x)
            mydbpath = self.repositories[x]['dbpath']
            myrevfile = os.path.join(mydbpath,etpConst['etpdatabaserevisionfile'])
            myrev = '0'
            if os.path.isfile(myrevfile):
                while 1:
                    try:
                        f = open(myrevfile)
                        myrev = f.readline().strip()
                        f.close()
                    except IOError: # should never happen but who knows
                        continue
                    break
            self.repositories[x]['dbrevision'] = myrev
            self.repositories[x]['download_lock'] = os.path.join(
                mydbpath,
                etpConst['etpdatabasedownloadlockfile']
            )
