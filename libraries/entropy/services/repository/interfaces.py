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
from entropy.core.settings.base import SystemSettings
from entropy.output import TextInterface, blue, brown, darkred, teal
from entropy.const import etpConst
from entropy.misc import TimeScheduled
from entropy.cache import EntropyCacher
from entropy.services.interfaces import SocketHost
from entropy.services.repository.commands import Repository
from entropy.client.interfaces import Client

import entropy.dump
import entropy.tools

class Server(SocketHost):

    CACHE_ID = 'reposerver/item'

    class ServiceInterface(TextInterface):
        def __init__(self, *args, **kwargs):
            pass

    def __init__(self, repositories, repository_lock_scanner = True,
        do_ssl = False, stdout_logging = True, **kwargs):

        # instantiate critical constants
        etpConst['socket_service']['max_connections'] = 5000

        self.__repository_commands_class = Repository
        self._entropy = Client(noclientdb = 2)
        self.__cacher = EntropyCacher()
        self.__lock_scanner = None
        self.__dbcache = {}

        # setup System Settings
        self._settings = SystemSettings()
        self._settings['socket_service']['max_connections'] = 5000

        etpConst['socketloglevel'] = 1
        if 'external_cmd_classes' not in kwargs:
            kwargs['external_cmd_classes'] = []
        if repository_lock_scanner:
            kwargs['external_cmd_classes'].insert(0,
                self.__repository_commands_class)
        SocketHost.__init__(
            self,
            Server.ServiceInterface,
            noclientdb = 2,
            sock_output = self._entropy,
            ssl = do_ssl,
            **kwargs
        )
        self.stdout_logging = stdout_logging
        self.repositories = repositories.copy()
        self._expand_repositories()
        if repository_lock_scanner:
            # start timed lock file scanning
            self._start_repository_lock_scanner()

    def killall(self):
        SocketHost.killall(self)
        if self.__lock_scanner != None:
            self.__lock_scanner.kill()

    def is_repository_active(self, repo_tuple):

        if repo_tuple not in self.repositories:
            return None
        if self.repositories[repo_tuple]['fatal_error']:
            return False
        # is repository being updated
        if self.repositories[repo_tuple]['locked']:
            return False
        # repository database does not exist
        if not self.repositories[repo_tuple]['enabled']:
            return False

        return True

    def get_dcache(self, item, repo = '_norepo_'):
        return entropy.dump.loadobj(Server.CACHE_ID+"/"+repo+"/"+str(hash(item)))

    def set_dcache(self, item, data, repo = '_norepo_'):
        entropy.dump.dumpobj(Server.CACHE_ID+"/"+repo+"/"+str(hash(item)), data)

    def close_db(self, dbpath):
        try:
            dbc = self.__dbcache.pop(dbpath)
            dbc.close()
        except KeyError:
            pass

    def open_db(self, dbpath, docache = True):
        if docache:
            cached = self.__dbcache.get(dbpath)
            if cached != None:
                return cached
        dbc = self._entropy.open_generic_repository(
            dbpath,
            xcache = False,
            read_only = True,
            skip_checks = True
        )
        if docache:
            self.__dbcache[dbpath] = dbc
        return dbc

    def _start_repository_lock_scanner(self):
        self.__lock_scanner = TimeScheduled(3, self.__lock_scan)
        self.__lock_scanner.start()

    def _is_repository_available(self, repo_tuple):

        if self.repositories[repo_tuple]['fatal_error']:
            return False

        xxx, yyy, compressed_dbpath = self.__get_unpack_metadata(repo_tuple)
        if not os.path.exists(compressed_dbpath):
            return False
        return True

    def __get_unpack_metadata(self, repo_tuple):

        cmethod = self.repositories[repo_tuple]['cmethod']
        cmethod_data = etpConst['etpdatabasecompressclasses'].get(
            cmethod)
        unpack_method = cmethod_data[1]
        compressed_dbfile = etpConst[cmethod_data[2]]
        compressed_dbpath = os.path.join(
            self.repositories[repo_tuple]['dbpath'], compressed_dbfile)
        return cmethod, unpack_method, compressed_dbpath

    def __unpack_repository(self, db_path, repo_tuple):

        cmethod, unpack_method, compressed_dbpath = self.__get_unpack_metadata(
            repo_tuple)
        try:
            unpack_func = getattr(entropy.tools, unpack_method, None)
        except (IOError, OSError):
            return False

        if unpack_func is None:
            return False
        generated_outpath = unpack_func(compressed_dbpath)
        if db_path != generated_outpath:
            try:
                os.rename(generated_outpath, db_path)
            except OSError:
                shutil.move(generated_outpath, db_path)
        return True

    def __drop_cache_now(self, repo):
        return EntropyCacher.clear_cache_item(Server.CACHE_ID+"/"+repo+"/")

    def __lock_scan(self):

        do_clear = set()
        for repository, arch, product, branch in self.repositories:

            repo_tuple = (repository, arch, product, branch,)
            lock_file = os.path.join(self.repositories[repo_tuple]['dbpath'],
                etpConst['etpdatabasedownloadlockfile'])
            db_path = os.path.join(self.repositories[repo_tuple]['dbpath'],
                etpConst['etpdatabasefile'])

            available = self._is_repository_available(repo_tuple)
            if not available:
                if self.repositories[repo_tuple]['enabled']:
                    self.repositories[repo_tuple]['enabled'] = False
                    self.close_db(db_path)
                    do_clear.add(repository)
                continue

            if os.path.lexists(lock_file):

                # locked !
                if not self.repositories[repo_tuple]['locked']:
                    self.repositories[repo_tuple]['locked'] = True
                    # trash old databases
                    self.close_db(db_path)
                    do_clear.add(repository)

                    mytxt = blue("%s.") % (
                        "repository is now locked, it's being uploaded",)
                    self.output(
                        "[%s] %s" % (
                            brown(str(repo_tuple)),
                            mytxt,
                        ),
                        importance = 1,
                        level = "info"
                    )
                continue

            elif self.repositories[repo_tuple]['locked']:

                # lock_file does not exists, but locked is enable.
                # this means that repo got locked while this app was running.
                # unpack the repository db and then unlock repository
                mytxt = blue("%s.") % (
                    "new repository revision available. Updating metadata",)
                self.output(
                    "[%s] %s" % (
                        brown(str(repo_tuple)),
                        mytxt,
                    ),
                    importance = 1,
                    level = "info"
                )
                # make sure it is all closed, again
                self.close_db(db_path)
                do_clear.add(repository)
                status = self.__unpack_repository(db_path, repo_tuple)
                if status:
                    mytxt = blue("%s. %s:") % (
                        "unlocking and indexing database",
                        "hash",
                    )
                    self.output(
                        "[%s] %s" % (
                                brown(str(repo_tuple)),
                                mytxt,
                        ),
                        importance = 1,
                        level = "info"
                    )
                    # update revision
                    self.repositories[repo_tuple]['dbrevision'] = \
                        self.__read_revision(repo_tuple)
                    # woohoo, got unlocked eventually
                    dbc = self.open_db(db_path, docache = False)
                    dbc.createAllIndexes()
                    db_ck = dbc.checksum(do_order = True, strict = False,
                        strings = True)
                    self.output(
                        teal(str(db_ck)),
                        importance = 1,
                        level = "info"
                    )
                    dbc.close()
                    self.__cacher.discard()
                    self.__drop_cache_now(repository)
                    self.repositories[repo_tuple]['locked'] = False

                else:
                    mytxt = darkred("%s.") % (
                        "error during repository unpack, disabling repository",)
                    self.output( # scrive 2 volte stessa roba (self.output())
                        "[%s] %s" % (
                            brown(str(repo_tuple)),
                            mytxt,
                        ),
                        importance = 1,
                        level = "info"
                    )
                    self.repositories[repo_tuple]['fatal_error'] = True
                    self.repositories[repo_tuple]['enabled'] = False
                    continue


            # at this point, repository is enabled, always
            self.repositories[repo_tuple]['enabled'] = True

        self.__cacher.discard()
        for repo in do_clear:
            self.__drop_cache_now(repo)

    def __read_revision(self, repo_tuple):
        db_dir = self.repositories[repo_tuple]['dbpath']
        rev_file = os.path.join(db_dir, etpConst['etpdatabaserevisionfile'])
        myrev = '0'
        if os.path.isfile(rev_file) and os.access(rev_file, os.R_OK):
            with open(rev_file, "r") as f:
                try:
                    myrev = str(int(f.readline().strip()))
                except ValueError:
                    myrev = '-1'
        return myrev

    def _expand_repositories(self):

        for repository, arch, product, branch in self.repositories:
            x = (repository, arch, product, branch,)

            if 'cmethod' not in self.repositories[x]:
                raise AttributeError("cmethod not specified for: %s" % (x,))
            if self.repositories[x]['cmethod'] not in \
                etpConst['etpdatabasesupportedcformats']:
                raise AttributeError("wrong cmethod for: %s" % (x,))

            # repository is locked by default, its db needs to be unpacked
            self.repositories[x]['locked'] = True
            # repository can become faulty (inability of unpacking data, etc)
            # and run into unrecoverable errors
            self.repositories[x]['fatal_error'] = False

            db_path = os.path.join(self.repositories[x]['dbpath'],
                etpConst['etpdatabasefile'])
            if os.path.isfile(db_path) and os.access(db_path, os.R_OK):
                self.repositories[x]['enabled'] = True
            else:
                self.repositories[x]['enabled'] = False

            self.repositories[x]['dbrevision'] = self.__read_revision(x)
