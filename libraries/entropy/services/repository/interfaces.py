# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Services Repository Management Interface}.

"""

import os
import shutil
from entropy.services.interfaces import SocketHost
from entropy.output import TextInterface, blue, brown, darkred, darkgreen
from entropy.const import etpConst
from entropy.misc import TimeScheduled
from entropy.cache import EntropyCacher
from entropy.i18n import _
from entropy.db.exceptions import ProgrammingError

import entropy.dump
import entropy.tools

class Server(SocketHost):

    CACHE_ID = 'reposerver/item'

    class ServiceInterface(TextInterface):
        def __init__(self, *args, **kwargs):
            pass

    def __init__(self, repositories, do_ssl = False, stdout_logging = True, **kwargs):

        # instantiate critical constants
        etpConst['socket_service']['max_connections'] = 5000

        from entropy.services.repository.commands import Repository
        self.RepositoryCommands = Repository
        from entropy.client.interfaces import Client
        self.Entropy = Client(noclientdb = 2)
        self.__cacher = EntropyCacher()
        self.do_ssl = do_ssl
        self.LockScanner = None
        self.syscache = {
            'db': {},
            'db_trashed': set(),
            'dbs_not_available': set(),
        }

        # setup System Settings
        from entropy.core.settings.base import SystemSettings
        self.SystemSettings = SystemSettings()
        self.SystemSettings['socket_service']['max_connections'] = 5000

        etpConst['socketloglevel'] = 1
        if 'external_cmd_classes' not in kwargs:
            kwargs['external_cmd_classes'] = []
        kwargs['external_cmd_classes'].insert(0, self.RepositoryCommands)
        SocketHost.__init__(
            self,
            self.ServiceInterface,
            noclientdb = 2,
            sock_output = self.Entropy,
            ssl = do_ssl,
            **kwargs
        )
        self.stdout_logging = stdout_logging
        self.repositories = repositories.copy()
        self.expand_repositories()
        # start timed lock file scanning
        self.start_repository_lock_scanner()

    def killall(self):
        SocketHost.killall(self)
        if self.LockScanner != None:
            self.LockScanner.kill()

    def start_repository_lock_scanner(self):
        self.LockScanner = TimeScheduled(5, self.lock_scan)
        self.LockScanner.start()

    def set_repository_db_availability(self, repo_tuple):
        self.repositories[repo_tuple]['enabled'] = False
        mydbpath = os.path.join(self.repositories[repo_tuple]['dbpath'], etpConst['etpdatabasefile'])
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
        for repository, arch, product, branch in self.repositories:

            x = (repository, arch, product, branch,)
            self.set_repository_db_availability(x)

            saved_rev = self.repositories[x]['live_db_rev']
            saved_rev_mtime = self.repositories[x]['live_db_rev_mtime']
            dbrev_path = os.path.join(self.repositories[x]['dbpath'],
                etpConst['etpdatabaserevisionfile'])
            db_path = os.path.join(self.repositories[x]['dbpath'],
                etpConst['etpdatabasefile'])

            cur_rev = None
            cur_mtime = None
            if os.path.isfile(dbrev_path):
                cur_mtime = os.path.getmtime(dbrev_path)
                cur_f = open(dbrev_path, "r")
                cur_rev = cur_f.readline().strip()
                cur_f.close()

            if (cur_rev == saved_rev) and (cur_mtime == saved_rev_mtime):
                continue

            self.repositories[x]['locked'] = True
            # trash old databases
            self.close_db(db_path)
            do_clear.add(repository)
            mytxt = blue("%s.") % (
                _("repository changed. Updating metadata"),)
            self.output(
                "[%s] %s" % (
                        brown(str(x)),
                        mytxt,
                ),
                importance = 1,
                level = "info"
            )

            # now unpack and unlock
            cmethod = self.repositories[x]['cmethod']
            cmethod_data = etpConst['etpdatabasecompressclasses'].get(
                cmethod)
            unpack_method = cmethod_data[1]
            compressed_dbfile = etpConst[cmethod_data[2]]
            compressed_dbpath = os.path.join(self.repositories[x]['dbpath'],
                compressed_dbfile)

            if not (os.access(compressed_dbpath, os.R_OK | os.W_OK) and \
                os.path.isfile(compressed_dbpath)):
                mytxt = darkred("%s: %s !!") % (
                    _("cannot unlock database, compressed file not found"),
                    compressed_dbpath,
                )
                self.output(
                    "[%s] %s" % (
                            brown(str(x)),
                            mytxt,
                    ),
                    importance = 1,
                    level = "warning"
                )
                self.syscache['dbs_not_available'].add(x)
                do_clear.add(repository)
                continue

            # make sure this db is closed
            self.close_db(db_path)

            mytxt = blue("%s: %s") % (
                _("unpacking compressed database"),
                compressed_dbpath,
            )
            self.output(
                "[%s] %s" % (
                        brown(str(x)),
                        mytxt,
                ),
                importance = 1,
                level = "info"
            )

            # now unpack compressed db in place
            unpack_func = getattr(entropy.tools, unpack_method)
            generated_outpath = unpack_func(compressed_dbpath)
            if db_path != generated_outpath:
                try:
                    os.rename(generated_outpath, db_path)
                except OSError:
                    shutil.move(generated_outpath, db_path)

            mytxt = blue("%s. %s:") % (
                _("unlocking and indexing database"),
                _("hash"),
            )
            self.output(
                "[%s] %s" % (
                        brown(str(x)),
                        mytxt,
                ),
                importance = 1,
                level = "info"
            )
            # woohoo, got unlocked eventually
            mydb = self.open_db(db_path, docache = False)
            mydb.createAllIndexes()
            db_ck = mydb.checksum(do_order = True, strict = False,
                strings = True)
            self.output(
                darkgreen(str(db_ck)),
                importance = 1,
                level = "info"
            )
            mydb.closeDB()
            self.__cacher.discard()
            EntropyCacher.clear_cache_item(
                Server.CACHE_ID+"/"+repository+"/")

            self.repositories[x]['live_db_rev'] = cur_rev
            self.repositories[x]['live_db_rev_mtime'] = cur_mtime
            self.repositories[x]['locked'] = False

        self.__cacher.discard()
        for repo in do_clear:
            EntropyCacher.clear_cache_item(Server.CACHE_ID+"/"+repo+"/")

    def get_dcache(self, item, repo = '_norepo_'):
        return entropy.dump.loadobj(Server.CACHE_ID+"/"+repo+"/"+str(hash(item)))

    def set_dcache(self, item, data, repo = '_norepo_'):
        entropy.dump.dumpobj(Server.CACHE_ID+"/"+repo+"/"+str(hash(item)), data)

    def close_db(self, dbpath):
        try:
            dbc = self.syscache['db'].pop(dbpath)
            dbc.closeDB()
        except KeyError:
            pass
        except ProgrammingError:
            # they've been opened by the Commands Processor
            self.syscache['db_trashed'].add(dbc)

    def open_db(self, dbpath, docache = True):
        if docache:
            cached = self.syscache['db'].get(dbpath)
            if cached != None:
                return cached
        dbc = self.Entropy.open_generic_repository(
            dbpath,
            xcache = False,
            readOnly = True,
            skipChecks = True
        )
        if docache:
            self.syscache['db'][dbpath] = dbc
        return dbc

    def expand_repositories(self):

        for repository, arch, product, branch in self.repositories:
            x = (repository, arch, product, branch,)
            self.repositories[x]['locked'] = True # loading locked
            self.set_repository_db_availability(x)
            mydbpath = self.repositories[x]['dbpath']
            myrevfile = os.path.join(mydbpath, etpConst['etpdatabaserevisionfile'])
            myrev = '0'
            if os.path.isfile(myrevfile):
                while True:
                    try:
                        f = open(myrevfile)
                        myrev = f.readline().strip()
                        f.close()
                    except IOError: # should never happen but who knows
                        continue
                    break
            self.repositories[x]['dbrevision'] = myrev
            self.repositories[x]['live_db_rev'] = None
            self.repositories[x]['live_db_rev_mtime'] = None
            if 'cmethod' not in self.repositories[x]:
                raise AttributeError("cmethod not specified for: %s" % (x,))
            if self.repositories[x]['cmethod'] not in etpConst['etpdatabasesupportedcformats']:
                raise AttributeError("wrong cmethod for: %s" % (x,))
