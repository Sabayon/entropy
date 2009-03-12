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
import shutil
import time
from entropy.core import Singleton
from entropy.exceptions import *
from entropy.output import TextInterface, purple, green, red, darkgreen, bold, brown, blue, darkred, darkblue
from entropy.const import etpConst, etpSys, const_setup_perms, const_createWorkingDirectories, const_readServerSettings


class Server(Singleton,TextInterface):

    def init_singleton(self, default_repository = None, save_repository = False, community_repo = False):

        self.__instance_destroyed = False
        if etpConst['uid'] != 0:
            mytxt = _("Entropy Server interface must be run as root")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

        from entropy.misc import LogFile
        self.serverLog = LogFile(
            level = etpConst['entropyloglevel'],
            filename = etpConst['entropylogfile'],
            header = "[server]"
        )

        self.default_repository = default_repository
        if self.default_repository == None:
            self.default_repository = etpConst['officialserverrepositoryid']

        if self.default_repository in etpConst['server_repositories']:
            self.ensure_paths(self.default_repository)
        self.migrate_repository_databases_to_new_branched_path()
        self.community_repo = community_repo
        from entropy.db import dbapi2, LocalRepository
        self.LocalRepository = LocalRepository
        self.dbapi2 = dbapi2 # export for third parties

        # settings
        etpSys['serverside'] = True
        self.indexing = False
        self.xcache = False
        self.MirrorsService = None
        from entropy.transceivers import FtpInterface
        self.FtpInterface = FtpInterface
        from entropy.misc import rssFeed
        self.rssFeed = rssFeed
        self.serverDbCache = {}
        self.repository_treeupdate_digests = {}
        self.package_match_validator_cache = {}
        self.settings_to_backup = []
        self.do_save_repository = save_repository
        self.rssMessages = {
            'added': {},
            'removed': {},
            'commitmessage': "",
            'light': {},
        }


        if self.default_repository not in etpConst['server_repositories']:
            raise PermissionDenied("PermissionDenied: %s %s" % (
                        self.default_repository,
                        _("repository not configured"),
                    )
            )
        if etpConst['clientserverrepoid'] in etpConst['server_repositories']:
            raise PermissionDenied("PermissionDenied: %s %s" % (
                        etpConst['clientserverrepoid'],
                        _("protected repository id, can't use this, sorry dude..."),
                    )
            )

        if self.community_repo:
            self.add_client_database_to_repositories()
        self.switch_default_repository(self.default_repository)

    def destroy(self):
        self.__instance_destroyed = True
        if hasattr(self,'serverLog'):
            self.serverLog.close()
        if hasattr(self,'ClientService'):
            self.ClientService.destroy()
        self.close_server_databases()

    def is_destroyed(self):
        return self.__instance_destroyed

    def __del__(self):
        self.destroy()

    def ensure_paths(self, repo):
        upload_dir = os.path.join(self.get_local_upload_directory(repo),etpConst['branch'])
        db_dir = self.get_local_database_dir(repo)
        for mydir in [upload_dir,db_dir]:
            if (not os.path.isdir(mydir)) and (not os.path.lexists(mydir)):
                os.makedirs(mydir)
                const_setup_perms(mydir,etpConst['entropygid'])


    # FIXME: this will be removed in future, creation date: 2008-10-08
    def migrate_repository_databases_to_new_branched_path(self):
        migrated_filename = '.branch_migrated'
        for repoid in etpConst['server_repositories'].keys():

            if repoid == etpConst['clientserverrepoid']: continue
            mydir = etpConst['server_repositories'][repoid]['database_dir']
            if not os.path.isdir(mydir): # empty ?
                continue

            migrated_filepath = os.path.join(mydir,migrated_filename)
            if os.path.isfile(migrated_filepath):
                continue

            my_branched_dir = self.get_local_database_dir(repoid)
            if os.path.isdir(my_branched_dir): # wtf? do not touch
                continue

            self.updateProgress(
                "[%s:%s] %s: %s, %s: %s" % (
                        brown("repo"),
                        purple(repoid),
                        _("migrating database path from"),
                        brown(mydir),
                        _('to'),
                        brown(my_branched_dir),
                ),
                importance = 1,
                type = "info",
                header = bold(" @@ ")
            )

            repo_files = [os.path.join(mydir,x) for x in os.listdir(mydir) if \
                (os.path.isfile(os.path.join(mydir,x)) and \
                os.access(os.path.join(mydir,x),os.W_OK))
            ]
            os.makedirs(my_branched_dir)
            const_setup_perms(my_branched_dir,etpConst['entropygid'])

            for repo_file in repo_files:
                repo_filename = os.path.basename(repo_file)
                shutil.move(repo_file,os.path.join(my_branched_dir,repo_filename))

            f = open(migrated_filepath,"w")
            f.write("done\n")
            f.flush()
            f.close()

    def add_client_database_to_repositories(self):
        etpConst['server_repositories'][etpConst['clientserverrepoid']] = {}
        mydata = {}
        mydata['description'] = "Community Repositories System Database"
        mydata['mirrors'] = []
        mydata['community'] = False
        etpConst['server_repositories'][etpConst['clientserverrepoid']].update(mydata)

    def setup_services(self):
        self.setup_entropy_settings()
        if hasattr(self,'ClientService'):
            self.ClientService.destroy()
        from entropy.client.interfaces import Client
        self.ClientService = Client(
            indexing = self.indexing,
            xcache = self.xcache,
            repo_validation = False,
            noclientdb = 1
        )
        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()
        self.ClientService.updateProgress = self.updateProgress
        self.SystemSettings = self.ClientService.SystemSettings
        self.validRepositories = self.ClientService.validRepositories
        self.entropyTools = self.ClientService.entropyTools
        self.dumpTools = self.ClientService.dumpTools
        self.QA = self.ClientService.QA
        self.backup_entropy_settings()
        self.SpmService = self.ClientService.Spm()
        self.MirrorsService = MirrorsServer(self)

    def setup_entropy_settings(self, repo = None):
        backup_list = [
            'etpdatabaseclientfilepath',
            'clientdbid',
            'officialserverrepositoryid'
        ]
        for setting in backup_list:
            if setting not in self.settings_to_backup:
                self.settings_to_backup.append(setting)
        # setup client database
        if not self.community_repo:
            etpConst['etpdatabaseclientfilepath'] = self.get_local_database_file(repo)
            etpConst['clientdbid'] = etpConst['serverdbid']
        const_createWorkingDirectories()

    def close_server_databases(self):
        if hasattr(self,'serverDbCache'):
            for item in self.serverDbCache:
                try:
                    self.serverDbCache[item].closeDB()
                except self.dbapi2.ProgrammingError: # already closed?
                    pass
        self.serverDbCache.clear()

    def close_server_database(self, dbinstance):
        found = None
        for item in self.serverDbCache:
            if dbinstance == self.serverDbCache[item]:
                found = item
                break
        if found:
            instance = self.serverDbCache.pop(found)
            instance.closeDB()

    def get_available_repositories(self):
        return etpConst['server_repositories'].copy()

    def switch_default_repository(self, repoid, save = None, handle_uninitialized = True):

        # avoid setting __default__ as default server repo
        if repoid == etpConst['clientserverrepoid']:
            return

        if save == None:
            save = self.do_save_repository
        if repoid not in etpConst['server_repositories']:
            raise PermissionDenied("PermissionDenied: %s %s" % (
                        repoid,
                        _("repository not configured"),
                    )
            )
        self.close_server_databases()
        etpConst['officialserverrepositoryid'] = repoid
        self.default_repository = repoid
        self.setup_services()
        if save:
            self.save_default_repository(repoid)

        self.setup_community_repositories_settings()
        self.show_interface_status()
        if handle_uninitialized:
            self.handle_uninitialized_repository(repoid)

    def setup_community_repositories_settings(self):
        if self.community_repo:
            for repoid in etpConst['server_repositories']:
                etpConst['server_repositories'][repoid]['community'] = True


    def handle_uninitialized_repository(self, repoid):
        if not self.is_repository_initialized(repoid):
            mytxt = blue("%s.") % (_("Your default repository is not initialized"),)
            self.updateProgress(
                "[%s:%s] %s" % (
                        brown("repo"),
                        purple(repoid),
                        mytxt,
                ),
                importance = 1,
                type = "warning",
                header = darkred(" !!! ")
            )
            answer = self.askQuestion(_("Do you want to initialize your default repository ?"))
            if answer == "No":
                mytxt = red("%s.") % (_("You have taken the risk to continue with an uninitialized repository"),)
                self.updateProgress(
                    "[%s:%s] %s" % (
                            brown("repo"),
                            purple(repoid),
                            mytxt,
                    ),
                    importance = 1,
                    type = "warning",
                    header = darkred(" !!! ")
                )
            else:
                # move empty database for security sake
                dbfile = self.get_local_database_file(repoid)
                if os.path.isfile(dbfile):
                    shutil.move(dbfile,dbfile+".backup")
                self.initialize_server_database(empty = True, repo = repoid, warnings = False)


    def show_interface_status(self):
        type_txt = _("server-side repository")
        if self.community_repo:
            type_txt = _("community repository")
        mytxt = _("Entropy Server Interface Instance on repository") # ..on repository: <repository_name>
        self.updateProgress(
            blue("%s: %s, %s: %s (%s: %s)" % (
                    mytxt,
                    red(self.default_repository),
                    _("current branch"),
                    darkgreen(etpConst['branch']),
                    purple(_("type")),
                    bold(type_txt),
                )
            ),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        repos = etpConst['server_repositories'].keys()
        mytxt = blue("%s:") % (_("Currently configured repositories"),) # ...: <list>
        self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red(" @@ ")
        )
        for repo in repos:
            self.updateProgress(
                darkgreen(repo),
                importance = 0,
                type = "info",
                header = brown("   # ")
            )


    def save_default_repository(self, repoid):

        # avoid setting __default__ as default server repo
        if repoid == etpConst['clientserverrepoid']:
            return

        if os.path.isfile(etpConst['serverconf']):
            f = open(etpConst['serverconf'],"r")
            content = f.readlines()
            f.close()
            content = [x.strip() for x in content]
            found = False
            new_content = []
            for line in content:
                if line.strip().startswith("officialserverrepositoryid|"):
                    line = "officialserverrepositoryid|%s" % (repoid,)
                    found = True
                new_content.append(line)
            if not found:
                new_content.append("officialserverrepositoryid|%s" % (repoid,))
            f = open(etpConst['serverconf']+".save_default_repo_tmp","w")
            for line in new_content:
                f.write(line+"\n")
            f.flush()
            f.close()
            shutil.move(etpConst['serverconf']+".save_default_repo_tmp",etpConst['serverconf'])
        else:
            f = open(etpConst['serverconf'],"w")
            f.write("officialserverrepositoryid|%s\n" % (repoid,))
            f.flush()
            f.close()

    def toggle_repository(self, repoid, enable = True):

        # avoid setting __default__ as default server repo
        if repoid == etpConst['clientserverrepoid']:
            return False

        if not os.path.isfile(etpConst['serverconf']):
            return None
        f = open(etpConst['serverconf'])
        tmpfile = etpConst['serverconf']+".switch"
        mycontent = [x.strip() for x in f.readlines()]
        f.close()
        f = open(tmpfile,"w")
        st = "repository|%s" % (repoid,)
        status = False
        for line in mycontent:
            if enable:
                if (line.find(st) != -1) and line.startswith("#") and (len(line.split("|")) == 5):
                    line = line[1:]
                    status = True
            else:
                if (line.find(st) != -1) and not line.startswith("#") and (len(line.split("|")) == 5):
                    line = "#"+line
                    status = True
            f.write(line+"\n")
        f.flush()
        f.close()
        shutil.move(tmpfile,etpConst['serverconf'])
        if status:
            self.close_server_databases()
            const_readServerSettings()
            self.setup_services()
            self.show_interface_status()
        return status

    def backup_entropy_settings(self):
        for setting in self.settings_to_backup:
            self.ClientService.backup_setting(setting)

    def is_repository_initialized(self, repo):

        def do_validate(dbc):
            try:
                dbc.validateDatabase()
                return True
            except SystemDatabaseError:
                return False

        dbc = self.openServerDatabase(just_reading = True, repo = repo)
        valid = do_validate(dbc)
        self.close_server_database(dbc)
        if not valid: # check online?
            dbc = self.openServerDatabase(read_only = False, no_upload = True, repo = repo, is_new = True)
            valid = do_validate(dbc)
            self.close_server_database(dbc)

        return valid

    def doServerDatabaseSyncLock(self, repo, no_upload):

        if repo == None:
            repo = self.default_repository

        # check if the database is locked locally
        lock_file = self.MirrorsService.get_database_lockfile(repo)
        if os.path.isfile(lock_file):
            self.updateProgress(
                red(_("Entropy database is already locked by you :-)")),
                importance = 1,
                type = "info",
                header = red(" * ")
            )
        else:
            # check if the database is locked REMOTELY
            mytxt = "%s ..." % (_("Locking and Syncing Entropy database"),)
            self.updateProgress(
                red(mytxt),
                importance = 1,
                type = "info",
                header = red(" * "),
                back = True
            )
            for uri in self.get_remote_mirrors(repo):
                given_up = self.MirrorsService.mirror_lock_check(uri, repo = repo)
                if given_up:
                    crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
                    mytxt = "%s:" % (_("Mirrors status table"),)
                    self.updateProgress(
                        darkgreen(mytxt),
                        importance = 1,
                        type = "info",
                        header = brown(" * ")
                    )
                    dbstatus = self.MirrorsService.get_mirrors_lock(repo = repo)
                    for db in dbstatus:
                        db[1] = green(_("Unlocked"))
                        if (db[1]):
                            db[1] = red(_("Locked"))
                        db[2] = green(_("Unlocked"))
                        if (db[2]):
                            db[2] = red(_("Locked"))

                        crippled_uri = self.entropyTools.extractFTPHostFromUri(db[0])
                        self.updateProgress(
                            "%s: [%s: %s] [%s: %s]" % (
                                bold(crippled_uri),
                                brown(_("database")),
                                db[1],
                                brown(_("download")),
                                db[2],
                            ),
                            importance = 1,
                            type = "info",
                            header = "\t"
                        )

                    raise OnlineMirrorError("OnlineMirrorError: %s %s" % (
                            _("cannot lock mirror"),
                            crippled_uri,
                        )
                    )

            # if we arrive here, it is because all the mirrors are unlocked
            self.MirrorsService.lock_mirrors(True, repo = repo)
            self.MirrorsService.sync_databases(no_upload, repo = repo)

    def openServerDatabase(
            self,
            read_only = True,
            no_upload = True,
            just_reading = False,
            repo = None,
            indexing = True,
            warnings = True,
            do_cache = True,
            use_branch = None,
            lock_remote = True,
            is_new = False
        ):

        if repo == None:
            repo = self.default_repository

        if repo == etpConst['clientserverrepoid'] and self.community_repo:
            return self.ClientService.clientDbconn

        if just_reading:
            read_only = True
            no_upload = True

        t_ident = 1 # thread.get_ident() disabled for now
        local_dbfile = self.get_local_database_file(repo, use_branch)
        if do_cache:
            cached = self.serverDbCache.get(
                            (   etpConst['systemroot'],
                                local_dbfile,
                                read_only,
                                no_upload,
                                just_reading,
                                repo,
                                t_ident,
                                use_branch,
                                lock_remote,
                            )
            )
            if cached != None:
                return cached

        if not os.path.isdir(os.path.dirname(local_dbfile)):
            os.makedirs(os.path.dirname(local_dbfile))

        if (not read_only) and (lock_remote):
            self.doServerDatabaseSyncLock(repo, no_upload)

        conn = self.LocalRepository(
            readOnly = read_only,
            dbFile = local_dbfile,
            noUpload = no_upload,
            OutputInterface = self,
            ServiceInterface = self,
            dbname = etpConst['serverdbid']+repo,
            useBranch = use_branch,
            lockRemote = lock_remote
        )

        valid = True
        try:
            conn.validateDatabase()
        except SystemDatabaseError:
            valid = False

        # verify if we need to update the database to sync
        # with portage updates, we just ignore being readonly in the case
        if (repo not in etpConst['server_treeupdatescalled']) and (not just_reading):
            # sometimes, when filling a new server db, we need to avoid tree updates
            if valid:
                conn.serverUpdatePackagesData()
            elif warnings and not is_new:
                mytxt = _( "Entropy database is probably corrupted! I won't stop you here btw...")
                self.updateProgress(
                    darkred(mytxt),
                    importance = 1,
                    type = "warning",
                    header = bold(" !!! ")
                )

        if not read_only and valid and indexing:

            self.updateProgress(
                "[repo:%s|%s] %s" % (
                            blue(repo),
                            red(_("database")),
                            blue(_("indexing database")),
                    ),
                importance = 1,
                type = "info",
                header = brown(" @@ "),
                back = True
            )
            conn.createAllIndexes()

        if do_cache:
            # !!! also cache just_reading otherwise there will be
            # real issues if the connection is opened several times
            self.serverDbCache[(
                etpConst['systemroot'],
                local_dbfile,
                read_only,
                no_upload,
                just_reading,
                repo,
                t_ident,
                use_branch,
                lock_remote
            )] = conn

        # auto-update package sets
        if (not read_only) and (not is_new):
            cur_sets = conn.retrievePackageSets()
            sys_sets = self.get_configured_package_sets(repo)
            if cur_sets != sys_sets:
                self.update_database_package_sets(repo, dbconn = conn)
            conn.commitChanges()

        return conn

    def deps_tester(self):

        server_repos = etpConst['server_repositories'].keys()
        installed_packages = set()
        for repo in server_repos:
            dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo)
            installed_packages |= set([(x,repo) for x in dbconn.listAllIdpackages()])


        deps_not_satisfied = set()
        length = str((len(installed_packages)))
        count = 0
        mytxt = _("Checking")
        for pkgdata in installed_packages:
            count += 1
            idpackage = pkgdata[0]
            repo = pkgdata[1]
            dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo)
            atom = dbconn.retrieveAtom(idpackage)
            if atom == None:
                continue
            self.updateProgress(
                darkgreen(mytxt)+" "+bold(atom),
                importance = 0,
                type = "info",
                back = True,
                count = (count,length),
                header = darkred(" @@  ")
            )

            xdeps = dbconn.retrieveDependencies(idpackage)
            for xdep in xdeps:
                xmatch = self.atom_match(xdep)
                if xmatch[0] == -1:
                    deps_not_satisfied.add(xdep)

        return deps_not_satisfied

    def dependencies_test(self):

        mytxt = "%s %s" % (blue(_("Running dependencies test")),red("..."))
        self.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        server_repos = etpConst['server_repositories'].keys()
        deps_not_matched = self.deps_tester()

        if deps_not_matched:

            crying_atoms = {}
            for atom in deps_not_matched:
                for repo in server_repos:
                    dbconn = self.openServerDatabase(just_reading = True, repo = repo)
                    riddep = dbconn.searchDependency(atom)
                    if riddep == -1:
                        continue
                    if riddep != -1:
                        ridpackages = dbconn.searchIdpackageFromIddependency(riddep)
                        for i in ridpackages:
                            iatom = dbconn.retrieveAtom(i)
                            if not crying_atoms.has_key(atom):
                                crying_atoms[atom] = set()
                            crying_atoms[atom].add((iatom,repo))

            mytxt = blue("%s:") % (_("These are the dependencies not found"),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
            mytxt = "%s:" % (_("Needed by"),)
            for atom in deps_not_matched:
                self.updateProgress(
                    red(atom),
                    importance = 1,
                    type = "info",
                    header = blue("   # ")
                )
                if crying_atoms.has_key(atom):
                    self.updateProgress(
                        red(mytxt),
                        importance = 0,
                        type = "info",
                        header = blue("      # ")
                    )
                    for x , myrepo in crying_atoms[atom]:
                        self.updateProgress(
                            "[%s:%s] %s" % (blue(_("by repo")),darkred(myrepo),darkgreen(x),),
                            importance = 0,
                            type = "info",
                            header = blue("      # ")
                        )
        else:

            mytxt = blue(_("Every dependency is satisfied. It's all fine."))
            self.updateProgress(
                mytxt,
                importance = 2,
                type = "info",
                header = red(" @@ ")
            )

        return deps_not_matched

    def libraries_test(self, get_files = False, repo = None):

        # load db
        dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo)
        packagesMatched, brokenexecs, status = self.ClientService.libraries_test(dbconn = dbconn, broken_symbols = False)
        if status != 0:
            return 1,None

        if get_files:
            return 0,brokenexecs

        if (not brokenexecs) and (not packagesMatched):
            mytxt = "%s." % (_("System is healthy"),)
            self.updateProgress(
                blue(mytxt),
                importance = 2,
                type = "info",
                header = red(" @@ ")
            )
            return 0,None

        mytxt = "%s..." % (_("Matching libraries with Spm, please wait"),)
        self.updateProgress(
            blue(mytxt),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        packages = self.SpmService.query_belongs_multiple(brokenexecs)

        if packages:
            mytxt = "%s:" % (_("These are the matched packages"),)
            self.updateProgress(
                red(mytxt),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
            for package_slot in packages:
                self.updateProgress(
                    blue(unicode(package_slot)),
                    importance = 0,
                    type = "info",
                    header = red("     # ")
                )
                for filename in sorted(list(packages[package_slot])):
                    self.updateProgress(
                        blue(filename),
                        importance = 0,
                        type = "info",
                        header = brown("       => ")
                    )
            # print string
            pkgstring = ' '.join(["%s:%s" % (self.entropyTools.dep_getkey(x[0]),x[1],) for x in sorted(packages.keys())])
            mytxt = "%s: %s" % (darkgreen(_("Packages string")),pkgstring,)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
        else:
            self.updateProgress(
                red(_("No matched packages")),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )

        return 0,packages

    def orphaned_spm_packages_test(self):

        mytxt = "%s %s" % (blue(_("Running orphaned SPM packages test")),red("..."),)
        self.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        installed_packages, length = self.SpmService.get_installed_packages()
        not_found = {}
        count = 0
        for installed_package in installed_packages:
            count += 1
            self.updateProgress(
                "%s: %s" % (darkgreen(_("Scanning package")),brown(installed_package),),
                importance = 0,
                type = "info",
                back = True,
                count = (count,length),
                header = darkred(" @@ ")
            )
            key, slot = self.entropyTools.dep_getkey(installed_package),self.SpmService.get_installed_package_slot(installed_package)
            pkg_atom = "%s:%s" % (key,slot,)
            tree_atom = self.SpmService.get_best_atom(pkg_atom)
            if not tree_atom:
                not_found[installed_package] = pkg_atom
                self.updateProgress(
                    "%s: %s" % (blue(pkg_atom),darkred(_("not found anymore")),),
                    importance = 0,
                    type = "warning",
                    count = (count,length),
                    header = darkred(" @@ ")
                )

        if not_found:
            not_found_list = ' '.join([not_found[x] for x in sorted(not_found.keys())])
            self.updateProgress(
                "%s: %s" % (blue(_("Packages string")),not_found_list,),
                importance = 0,
                type = "warning",
                count = (count,length),
                header = darkred(" @@ ")
            )

        return not_found

    def depends_table_initialize(self, repo = None):
        dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
        dbconn.regenerateDependsTable()
        dbconn.taintDatabase()
        dbconn.commitChanges()

    def create_empty_database(self, dbpath = None, repo = None):
        if dbpath == None:
            dbpath = self.get_local_database_file(repo)

        dbdir = os.path.dirname(dbpath)
        if not os.path.isdir(dbdir):
            os.makedirs(dbdir)

        mytxt = red("%s ...") % (_("Initializing an empty database file with Entropy structure"),)
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = darkgreen(" * "),
            back = True
        )
        dbconn = self.ClientService.open_generic_database(dbpath)
        dbconn.initializeDatabase()
        dbconn.commitChanges()
        dbconn.closeDB()
        mytxt = "%s %s %s." % (red(_("Entropy database file")),bold(dbpath),red(_("successfully initialized")),)
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )

    def tag_packages(self, package_tag, idpackages, repo = None, ask = True):

        # check package_tag "no spaces"

        try:
            package_tag = str(package_tag)
            if " " in package_tag: raise ValueError
        except (UnicodeDecodeError,UnicodeEncodeError,ValueError,):
            self.updateProgress(
                "%s: %s" % (
                    blue(_("Invalid tag specified")),
                    package_tag,
                ),
                importance = 1, type = "error", header = darkred(" !! ")
            )
            return 1, package_tag

        if repo == None: repo = self.default_repository

        # sanity check
        invalid_atoms = []
        dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo)
        for idpackage in idpackages:
            ver_tag = dbconn.retrieveVersionTag(idpackage)
            if ver_tag:
                invalid_atoms.append(dbconn.retrieveAtom(idpackage))

        if invalid_atoms:
            self.updateProgress(
                "%s: %s" % (
                    blue(_("These are the packages already tagged, cannot re-tag, action aborted")),
                    ', '.join([darkred(unicode(x)) for x in invalid_atoms]),
                ),
                importance = 1, type = "error", header = darkred(" !! ")
            )
            return 2, invalid_atoms

        matches = [(x,repo) for x in idpackages]
        status = 0
        data = self.move_packages(
            matches, to_repo = repo, from_repo = repo, ask = ask,
            do_copy = True, new_tag = package_tag
        )
        return status, data


    def move_packages(self, matches, to_repo, from_repo = None, ask = True, do_copy = False, new_tag = None):

        if from_repo == None: from_repo = self.default_repository
        switched = set()

        # avoid setting __default__ as default server repo
        if etpConst['clientserverrepoid'] in (to_repo,from_repo):
            self.updateProgress(
                "%s: %s" % (
                        blue(_("You cannot switch packages from/to your system database")),
                        red(etpConst['clientserverrepoid']),
                ),
                importance = 2, type = "warning", header = darkred(" @@ ")
            )
            return switched

        if not matches and from_repo:
            dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = from_repo)
            matches = set( \
                [(x,from_repo) for x in \
                    dbconn.listAllIdpackages()]
            )

        mytxt = _("Preparing to move selected packages to")
        if do_copy:
            mytxt = _("Preparing to copy selected packages to")
        self.updateProgress(
            "%s %s:" % (
                    blue(mytxt),
                    red(to_repo),
            ),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        self.updateProgress(
            "%s: %s" % (
                    bold(_("Note")),
                    red(_("all the old packages with conflicting scope will be removed from the destination repo unless injected")),
            ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        new_tag_string = ''
        if new_tag != None: new_tag_string = "[%s: %s]" % (darkgreen(_("new tag")),brown(new_tag),)
        for match in matches:
            repo = match[1]
            dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo)
            self.updateProgress(
                "[%s=>%s|%s] %s " % (
                        darkgreen(repo),
                        darkred(to_repo),
                        brown(etpConst['branch']),
                        blue(dbconn.retrieveAtom(match[0])),
                ) + new_tag_string,
                importance = 0,
                type = "info",
                header = brown("    # ")
            )


        if ask:
            rc = self.askQuestion(_("Would you like to continue ?"))
            if rc == "No":
                return switched

        for idpackage, repo in matches:
            dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
            match_branch = dbconn.retrieveBranch(idpackage)
            match_atom = dbconn.retrieveAtom(idpackage)
            package_filename = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
            self.updateProgress(
                "[%s=>%s|%s] %s: %s" % (
                        darkgreen(repo),
                        darkred(to_repo),
                        brown(etpConst['branch']),
                        blue(_("switching")),
                        darkgreen(match_atom),
                ),
                importance = 0,
                type = "info",
                header = red(" @@ "),
                back = True
            )
            # move binary file
            from_file = os.path.join(self.get_local_packages_directory(repo),match_branch,package_filename)
            if not os.path.isfile(from_file):
                from_file = os.path.join(self.get_local_upload_directory(repo),match_branch,package_filename)
            if not os.path.isfile(from_file):
                self.updateProgress(
                    "[%s=>%s|%s] %s: %s -> %s" % (
                            darkgreen(repo),
                            darkred(to_repo),
                            brown(etpConst['branch']),
                            bold(_("cannot switch, package not found, skipping")),
                            darkgreen(),
                            red(from_file),
                    ),
                    importance = 1,
                    type = "warning",
                    header = darkred(" !!! ")
                )
                continue

            if new_tag != None:
                match_category = dbconn.retrieveCategory(idpackage)
                match_name = dbconn.retrieveName(idpackage)
                match_version = dbconn.retrieveVersion(idpackage)
                tagged_package_filename = self.entropyTools.create_package_filename(match_category, match_name, match_version, new_tag)
                to_file = os.path.join(self.get_local_upload_directory(to_repo),match_branch,tagged_package_filename)
            else:
                to_file = os.path.join(self.get_local_upload_directory(to_repo),match_branch,package_filename)
            if not os.path.isdir(os.path.dirname(to_file)):
                os.makedirs(os.path.dirname(to_file))

            copy_data = [
                            (from_file,to_file,),
                            (from_file+etpConst['packageshashfileext'],to_file+etpConst['packageshashfileext'],),
                            (from_file+etpConst['packagesexpirationfileext'],to_file+etpConst['packagesexpirationfileext'],)
                        ]

            for from_item,to_item in copy_data:
                self.updateProgress(
                        "[%s=>%s|%s] %s: %s" % (
                                darkgreen(repo),
                                darkred(to_repo),
                                brown(etpConst['branch']),
                                blue(_("moving file")),
                                darkgreen(os.path.basename(from_item)),
                        ),
                        importance = 0,
                        type = "info",
                        header = red(" @@ "),
                        back = True
                )
                if os.path.isfile(from_item):
                    shutil.copy2(from_item,to_item)

            self.updateProgress(
                "[%s=>%s|%s] %s: %s" % (
                        darkgreen(repo),
                        darkred(to_repo),
                        brown(etpConst['branch']),
                        blue(_("loading data from source database")),
                        darkgreen(repo),
                ),
                importance = 0,
                type = "info",
                header = red(" @@ "),
                back = True
            )
            # install package into destination db
            data = dbconn.getPackageData(idpackage)
            if new_tag != None:
                data['versiontag'] = new_tag

            todbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = to_repo)

            self.updateProgress(
                "[%s=>%s|%s] %s: %s" % (
                        darkgreen(repo),
                        darkred(to_repo),
                        brown(etpConst['branch']),
                        blue(_("injecting data to destination database")),
                        darkgreen(to_repo),
                ),
                importance = 0,
                type = "info",
                header = red(" @@ "),
                back = True
            )
            new_idpackage, new_revision, new_data = todbconn.handlePackage(data)
            del data
            todbconn.commitChanges()

            if not do_copy:
                self.updateProgress(
                    "[%s=>%s|%s] %s: %s" % (
                            darkgreen(repo),
                            darkred(to_repo),
                            brown(etpConst['branch']),
                            blue(_("removing entry from source database")),
                            darkgreen(repo),
                    ),
                    importance = 0,
                    type = "info",
                    header = red(" @@ "),
                    back = True
                )

                # remove package from old db
                dbconn.removePackage(idpackage)
                dbconn.commitChanges()

            self.updateProgress(
                "[%s=>%s|%s] %s: %s" % (
                        darkgreen(repo),
                        darkred(to_repo),
                        brown(etpConst['branch']),
                        blue(_("successfully handled atom")),
                        darkgreen(match_atom),
                ),
                importance = 0,
                type = "info",
                header = blue(" @@ ")
            )
            switched.add(match)

        return switched


    def package_injector(self, package_file, inject = False, repo = None):

        if repo == None:
            repo = self.default_repository

        upload_dir = os.path.join(self.get_local_upload_directory(repo),etpConst['branch'])
        if not os.path.isdir(upload_dir):
            os.makedirs(upload_dir)

        dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
        self.updateProgress(
            red("[repo: %s] %s: %s" % (
                        darkgreen(repo),
                        _("adding package"),
                        bold(os.path.basename(package_file)),
                    )
            ),
            importance = 1,
            type = "info",
            header = brown(" * "),
            back = True
        )
        mydata = self.ClientService.extract_pkg_metadata(package_file, etpBranch = etpConst['branch'], inject = inject)
        idpackage, revision, mydata = dbconn.handlePackage(mydata)

        # set trashed counters
        trashing_counters = set()
        myserver_repos = etpConst['server_repositories'].keys()
        for myrepo in myserver_repos:
            mydbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = myrepo)
            mylist = mydbconn.retrieve_packages_to_remove(
                    mydata['name'],
                    mydata['category'],
                    mydata['slot'],
                    mydata['injected']
            )
            for myitem in mylist:
                trashing_counters.add(mydbconn.retrieveCounter(myitem))

        for mycounter in trashing_counters:
            dbconn.setTrashedCounter(mycounter)

        # add package info to our current server repository
        dbconn.removePackageFromInstalledTable(idpackage)
        dbconn.addPackageToInstalledTable(idpackage,repo)
        atom = dbconn.retrieveAtom(idpackage)

        self.updateProgress(
            "[repo:%s] %s: %s %s: %s" % (
                        darkgreen(repo),
                        blue(_("added package")),
                        darkgreen(atom),
                        blue(_("rev")), # as in revision
                        bold(str(revision)),
                ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        manual_deps = sorted(dbconn.retrieveManualDependencies(idpackage))
        if manual_deps:
            self.updateProgress(
                "[repo:%s] %s: %s" % (
                            darkgreen(repo),
                            blue(_("manual dependencies for")),
                            darkgreen(atom),
                    ),
                importance = 1,
                type = "warning",
                header = darkgreen("   ## ")
            )
            for m_dep in manual_deps:
                self.updateProgress(
                    brown(m_dep),
                    importance = 1,
                    type = "warning",
                    header = darkred("    # ")
                )

        download_url = self._setup_repository_package_filename(idpackage, repo = repo)
        downloadfile = os.path.basename(download_url)
        destination_path = os.path.join(upload_dir,downloadfile)
        shutil.move(package_file,destination_path)

        dbconn.commitChanges()
        return idpackage,destination_path

    # this function changes the final repository package filename
    def _setup_repository_package_filename(self, idpackage, repo = None):

        dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)

        downloadurl = dbconn.retrieveDownloadURL(idpackage)
        packagerev = dbconn.retrieveRevision(idpackage)
        downloaddir = os.path.dirname(downloadurl)
        downloadfile = os.path.basename(downloadurl)
        # add revision
        downloadfile = downloadfile[:-5]+"~%s%s" % (packagerev,etpConst['packagesext'],)
        downloadurl = os.path.join(downloaddir,downloadfile)

        # update url
        dbconn.setDownloadURL(idpackage,downloadurl)

        return downloadurl

    def add_packages_to_repository(self, packages_data, ask = True, repo = None):

        if repo == None:
            repo = self.default_repository

        mycount = 0
        maxcount = len(packages_data)
        idpackages_added = set()
        to_be_injected = set()
        myQA = self.QA()
        missing_deps_taint = False
        for package_filepath, inject in packages_data:

            mycount += 1
            self.updateProgress(
                "[repo:%s] %s: %s" % (
                            darkgreen(repo),
                            blue(_("adding package")),
                            darkgreen(os.path.basename(package_filepath)),
                        ),
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                count = (mycount,maxcount,)
            )

            try:
                # add to database
                idpackage, destination_path = self.package_injector(
                    package_filepath,
                    inject = inject,
                    repo = repo
                )
                idpackages_added.add(idpackage)
                to_be_injected.add((idpackage,destination_path))
            except Exception, e:
                self.entropyTools.printTraceback()
                self.updateProgress(
                    "[repo:%s] %s: %s" % (
                                darkgreen(repo),
                                darkred(_("Exception caught, running injection and RDEPEND check before raising")),
                                darkgreen(unicode(e)),
                            ),
                    importance = 1,
                    type = "error",
                    header = bold(" !!! "),
                    count = (mycount,maxcount,)
                )
                # reinit depends table
                self.depends_table_initialize(repo)
                if idpackages_added:
                    dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
                    missing_deps_taint = myQA.scan_missing_dependencies(
                        idpackages_added,
                        dbconn,
                        ask = ask,
                        repo = repo,
                        self_check = True,
                        black_list = self.get_missing_dependencies_blacklist(repo = repo),
                        black_list_adder = self.add_missing_dependencies_blacklist_items
                    )
                    myQA.test_depends_linking(idpackages_added, dbconn, repo = repo)
                if to_be_injected:
                    self.inject_database_into_packages(to_be_injected, repo = repo)
                # reinit depends table
                if missing_deps_taint:
                    self.depends_table_initialize(repo)
                self.close_server_databases()
                raise

        # reinit depends table
        self.depends_table_initialize(repo)

        if idpackages_added:
            dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
            missing_deps_taint = myQA.scan_missing_dependencies(
                idpackages_added,
                dbconn,
                ask = ask,
                repo = repo,
                self_check = True,
                black_list = self.get_missing_dependencies_blacklist(repo = repo),
                black_list_adder = self.add_missing_dependencies_blacklist_items
            )
            myQA.test_depends_linking(idpackages_added, dbconn, repo = repo)

        # reinit depends table
        if missing_deps_taint:
            self.depends_table_initialize(repo)

        # inject database into packages
        self.inject_database_into_packages(to_be_injected, repo = repo)

        return idpackages_added


    def inject_database_into_packages(self, injection_data, repo = None):

        if repo == None:
            repo = self.default_repository

        # now inject metadata into tbz2 packages
        self.updateProgress(
            "[repo:%s] %s:" % (
                        darkgreen(repo),
                        blue(_("Injecting entropy metadata into built packages")),
                    ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
        for idpackage,package_path in injection_data:
            self.updateProgress(
                "[repo:%s|%s] %s: %s" % (
                            darkgreen(repo),
                            brown(str(idpackage)),
                            blue(_("injecting entropy metadata")),
                            darkgreen(os.path.basename(package_path)),
                        ),
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True
            )
            data = dbconn.getPackageData(idpackage)
            treeupdates_actions = dbconn.listAllTreeUpdatesActions()
            dbpath = self.ClientService.inject_entropy_database_into_package(package_path, data, treeupdates_actions)
            digest = self.entropyTools.md5sum(package_path)
            # update digest
            dbconn.setDigest(idpackage,digest)
            self.entropyTools.createHashFile(package_path)
            # remove garbage
            os.remove(dbpath)
            self.updateProgress(
                "[repo:%s|%s] %s: %s" % (
                            darkgreen(repo),
                            brown(str(idpackage)),
                            blue(_("injection complete")),
                            darkgreen(os.path.basename(package_path)),
                        ),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
            dbconn.commitChanges()

    def check_config_file_updates(self):
        self.updateProgress(
            "[%s] %s" % (
                red(_("config files")), # something short please
                blue(_("checking system")),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ "),
            back = True
        )
        # scanning for config files not updated
        scandata = self.ClientService.FileUpdates.scanfs(dcache = False)
        if scandata:
            self.updateProgress(
                "[%s] %s" % (
                    red(_("config files")), # something short please
                    blue(_("there are configuration files not updated yet")),
                ),
                importance = 1,
                type = "error",
                header = darkred(" @@ ")
            )
            for x in scandata:
                self.updateProgress(
                    "%s" % ( brown(etpConst['systemroot']+scandata[x]['destination']) ),
                    importance = 1,
                    type = "info",
                    header = "\t"
                )
            return True
        return False

    def quickpkg(self, atom, storedir):
        return self.SpmService.quickpkg(atom,storedir)


    def remove_packages(self, idpackages, repo = None):

        if repo == None:
            repo = self.default_repository

        dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
        for idpackage in idpackages:
            atom = dbconn.retrieveAtom(idpackage)
            self.updateProgress(
                "[repo:%s] %s: %s" % (
                        darkgreen(repo),
                        blue(_("removing package")),
                        darkgreen(atom),
                ),
                importance = 1,
                type = "info",
                header = brown(" @@ ")
            )
            dbconn.removePackage(idpackage)
        self.close_server_database(dbconn)
        self.updateProgress(
            "[repo:%s] %s" % (
                        darkgreen(repo),
                        blue(_("removal complete")),
                ),
            importance = 1,
            type = "info",
            header = brown(" @@ ")
        )


    def bump_database(self, repo = None):
        dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
        dbconn.taintDatabase()
        self.close_server_database(dbconn)

    def get_remote_mirrors(self, repo = None):
        if repo == None:
            repo = self.default_repository
        return etpConst['server_repositories'][repo]['mirrors'][:]

    def get_remote_packages_relative_path(self, repo = None):
        if repo == None:
            repo = self.default_repository
        return etpConst['server_repositories'][repo]['packages_relative_path']

    def get_remote_database_relative_path(self, repo = None):
        if repo == None:
            repo = self.default_repository
        return etpConst['server_repositories'][repo]['database_relative_path']

    def get_local_database_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabasefile'])

    def get_local_store_directory(self, repo = None):
        if repo == None:
            repo = self.default_repository
        return etpConst['server_repositories'][repo]['store_dir']

    def get_local_upload_directory(self, repo = None):
        if repo == None:
            repo = self.default_repository
        return etpConst['server_repositories'][repo]['upload_dir']

    def get_local_packages_directory(self, repo = None):
        if repo == None:
            repo = self.default_repository
        return etpConst['server_repositories'][repo]['packages_dir']

    def get_local_database_taint_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabasetaintfile'])

    def get_local_database_revision_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabaserevisionfile'])

    def get_local_database_ca_cert_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabasecacertfile'])

    def get_local_database_server_cert_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabaseservercertfile'])

    def get_local_database_mask_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabasemaskfile'])

    def get_local_database_system_mask_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabasesytemmaskfile'])

    def get_local_database_confl_tagged_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabaseconflictingtaggedfile'])

    def get_local_database_licensewhitelist_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabaselicwhitelistfile'])

    def get_local_database_rss_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['rss-name'])

    def get_local_database_rsslight_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['rss-light-name'])

    def get_local_database_notice_board_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['rss-notice-board'])

    def get_local_database_treeupdates_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabaseupdatefile'])

    def get_local_database_compressed_metafiles_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabasemetafilesfile'])

    def get_local_database_metafiles_not_found_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['etpdatabasemetafilesnotfound'])

    def get_local_database_sets_dir(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),etpConst['confsetsdirname'])

    def get_local_database_dir(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        if branch == None:
            branch = etpConst['branch']
        return os.path.join(etpConst['server_repositories'][repo]['database_dir'],branch)

    def get_missing_dependencies_blacklist_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        if branch == None:
            branch = etpConst['branch']
        return os.path.join(etpConst['server_repositories'][repo]['database_dir'],branch,etpConst['etpdatabasemissingdepsblfile'])

    def get_missing_dependencies_blacklist(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        if branch == None:
            branch = etpConst['branch']
        wl_file = self.get_missing_dependencies_blacklist_file(repo, branch)
        wl_data = []
        if os.path.isfile(wl_file) and os.access(wl_file,os.R_OK):
            f = open(wl_file,"r")
            wl_data = [x.strip() for x in f.readlines() if x.strip() and not x.strip().startswith("#")]
            f.close()
        return set(wl_data)

    def add_missing_dependencies_blacklist_items(self, items, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        if branch == None:
            branch = etpConst['branch']
        wl_file = self.get_missing_dependencies_blacklist_file(repo, branch)
        wl_dir = os.path.dirname(wl_file)
        if not (os.path.isdir(wl_dir) and os.access(wl_dir,os.W_OK)):
            return
        if os.path.isfile(wl_file) and not os.access(wl_file,os.W_OK):
            return
        f = open(wl_file,"a+")
        f.write('\n'.join(items)+'\n')
        f.flush()
        f.close()

    def get_local_database_revision(self, repo = None):

        if repo == None:
            repo = self.default_repository

        dbrev_file = self.get_local_database_revision_file(repo)
        if os.path.isfile(dbrev_file):
            f = open(dbrev_file)
            rev = f.readline().strip()
            f.close()
            try:
                rev = int(rev)
            except ValueError:
                self.updateProgress(
                    "[repo:%s] %s: %s - %s" % (
                            darkgreen(repo),
                            blue(_("invalid database revision")),
                            bold(rev),
                            blue(_("defaulting to 0")),
                        ),
                    importance = 2,
                    type = "error",
                    header = darkred(" !!! ")
                )
                rev = 0
            return rev
        else:
            return 0

    def get_remote_database_revision(self, repo = None):

        if repo == None:
            repo = self.default_repository

        remote_status =  self.MirrorsService.get_remote_databases_status(repo)
        if not [x for x in remote_status if x[1]]:
            remote_revision = 0
        else:
            remote_revision = max([x[1] for x in remote_status])

        return remote_revision

    def get_branch_from_download_relative_uri(self, mypath):
        return self.ClientService.get_branch_from_download_relative_uri(mypath)

    def package_set_list(self, *args, **kwargs):
        repos = etpConst['server_repositories'].keys()
        kwargs['server_repos'] = repos
        kwargs['serverInstance'] = self
        return self.ClientService.package_set_list(*args,**kwargs)

    def package_set_search(self, *args, **kwargs):
        repos = etpConst['server_repositories'].keys()
        kwargs['server_repos'] = repos
        kwargs['serverInstance'] = self
        return self.ClientService.package_set_search(*args,**kwargs)

    def package_set_match(self, *args, **kwargs):
        repos = etpConst['server_repositories'].keys()
        kwargs['server_repos'] = repos
        kwargs['serverInstance'] = self
        return self.ClientService.package_set_match(*args,**kwargs)

    def atom_match(self, *args, **kwargs):
        repos = etpConst['server_repositories'].keys()
        kwargs['server_repos'] = repos
        kwargs['serverInstance'] = self
        return self.ClientService.atom_match(*args,**kwargs)

    def scan_package_changes(self):

        installed_packages = self.SpmService.get_installed_packages_counter()
        installed_counters = set()
        toBeAdded = set()
        toBeRemoved = set()
        toBeInjected = set()

        server_repos = etpConst['server_repositories'].keys()

        # packages to be added
        for spm_atom,spm_counter in installed_packages:
            found = False
            for server_repo in server_repos:
                installed_counters.add(spm_counter)
                server_dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = server_repo)
                counter = server_dbconn.isCounterAvailable(spm_counter, branch = etpConst['branch'])
                if counter:
                    found = True
                    break
            if not found:
                toBeAdded.add((spm_atom,spm_counter,))

        # packages to be removed from the database
        database_counters = {}
        for server_repo in server_repos:
            server_dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = server_repo)
            database_counters[server_repo] = server_dbconn.listAllCounters(branch = etpConst['branch'])

        ordered_counters = set()
        for server_repo in database_counters:
            for data in database_counters[server_repo]:
                ordered_counters.add((data,server_repo))
        database_counters = ordered_counters

        for (counter,idpackage,),xrepo in database_counters:

            if counter < 0:
                continue # skip packages without valid counter

            if counter in installed_counters:
                continue

            dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = xrepo)

            dorm = True
            # check if the package is in toBeAdded
            if toBeAdded:

                dorm = False
                atom = dbconn.retrieveAtom(idpackage)
                atomkey = self.entropyTools.dep_getkey(atom)
                atomtag = self.entropyTools.dep_gettag(atom)
                atomslot = dbconn.retrieveSlot(idpackage)

                add = True
                for spm_atom, spm_counter in toBeAdded:
                    addslot = self.SpmService.get_installed_package_slot(spm_atom)
                    addkey = self.entropyTools.dep_getkey(spm_atom)
                    # workaround for ebuilds not having slot
                    if addslot == None:
                        addslot = '0'                                              # handle tagged packages correctly
                    if (atomkey == addkey) and ((str(atomslot) == str(addslot)) or (atomtag != None)):
                        # do not add to toBeRemoved
                        add = False
                        break

                if not add:
                    continue
                dorm = True

            if dorm:
                trashed = self.is_counter_trashed(counter)
                if trashed:
                    # search into portage then
                    try:
                        key, slot = dbconn.retrieveKeySlot(idpackage)
                        trashed = self.SpmService.get_installed_atom(key+":"+slot)
                    except TypeError: # referred to retrieveKeySlot
                        trashed = True
                if not trashed:
                    dbtag = dbconn.retrieveVersionTag(idpackage)
                    if dbtag != '':
                        is_injected = dbconn.isInjected(idpackage)
                        if not is_injected:
                            toBeInjected.add((idpackage,xrepo))
                    else:
                        toBeRemoved.add((idpackage,xrepo))

        return toBeAdded, toBeRemoved, toBeInjected

    def is_counter_trashed(self, counter):
        server_repos = etpConst['server_repositories'].keys()
        for repo in server_repos:
            dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo)
            if dbconn.isCounterTrashed(counter):
                return True
        return False

    def transform_package_into_injected(self, idpackage, repo = None):
        dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
        counter = dbconn.getNewNegativeCounter()
        dbconn.setCounter(idpackage,counter)
        dbconn.setInjected(idpackage)

    def initialize_server_database(self, empty = True, repo = None, warnings = True):

        if repo == None: repo = self.default_repository

        self.close_server_databases()
        revisions_match = {}
        treeupdates_actions = []
        injected_packages = set()
        idpackages = set()
        idpackages_added = set()

        mytxt = red("%s ...") % (_("Initializing Entropy database"),)
        self.updateProgress(
            mytxt, importance = 1,
            type = "info", header = darkgreen(" * "),
            back = True
        )

        if os.path.isfile(self.get_local_database_file(repo)):

            dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo, warnings = warnings)

            if dbconn.doesTableExist("baseinfo") and dbconn.doesTableExist("extrainfo"):
                idpackages = dbconn.listAllIdpackages()

            if dbconn.doesTableExist("treeupdatesactions"):
                treeupdates_actions = dbconn.listAllTreeUpdatesActions()

            # save list of injected packages
            if dbconn.doesTableExist("injected") and dbconn.doesTableExist("extrainfo"):
                injected_packages = dbconn.listAllInjectedPackages(justFiles = True)
                injected_packages = set([os.path.basename(x) for x in injected_packages])

            for idpackage in idpackages:
                package = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
                branch = dbconn.retrieveBranch(idpackage)
                revision = dbconn.retrieveRevision(idpackage)
                revisions_match[package] = (branch,revision,)

            self.close_server_database(dbconn)

            mytxt = "%s: %s: %s" % (
                bold(_("WARNING")),
                red(_("database already exists")),
                self.get_local_database_file(repo),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred(" !!! ")
            )

            rc = self.askQuestion(_("Do you want to continue ?"))
            if rc == "No": return
            try:
                os.remove(self.get_local_database_file(repo))
            except OSError:
                pass


        # initialize
        dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo, is_new = True)
        dbconn.initializeDatabase()

        if not empty:

            revisions_file = "/entropy-revisions-dump.txt"
            # dump revisions - as a backup
            if revisions_match:
                self.updateProgress(
                    "%s: %s" % (
                        red(_("Dumping current revisions to file")),
                        darkgreen(revisions_file),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                f = open(revisions_file,"w")
                f.write(str(revisions_match))
                f.flush()
                f.close()

            # dump treeupdates - as a backup
            treeupdates_file = "/entropy-treeupdates-dump.txt"
            if treeupdates_actions:
                self.updateProgress(
                    "%s: %s" % (
                        red(_("Dumping current 'treeupdates' actions to file")), # do not translate treeupdates
                        bold(treeupdates_file),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                f = open(treeupdates_file,"w")
                f.write(str(treeupdates_actions))
                f.flush()
                f.close()

            rc = self.askQuestion(_("Would you like to sync packages first (important if you don't have them synced) ?"))
            if rc == "Yes":
                self.MirrorsService.sync_packages(repo = repo)

            # fill tree updates actions
            if treeupdates_actions:
                dbconn.bumpTreeUpdatesActions(treeupdates_actions)

            # now fill the database
            pkg_branch_dir = os.path.join(self.get_local_packages_directory(repo),etpConst['branch'])
            pkglist = os.listdir(pkg_branch_dir)
            # filter .md5 and .expired packages
            pkglist = [x for x in pkglist if x[-5:] == etpConst['packagesext'] and not \
                os.path.isfile(os.path.join(pkg_branch_dir,x+etpConst['packagesexpirationfileext']))]

            if pkglist:
                self.updateProgress(
                    "%s '%s' %s %s" % (
                        red(_("Reinitializing Entropy database for branch")),
                        bold(etpConst['branch']),
                        red(_("using Packages in the repository")),
                        red("..."),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )

            counter = 0
            maxcount = len(pkglist)
            for pkg in pkglist:
                counter += 1

                self.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                            darkgreen(repo),
                            brown(etpConst['branch']),
                            blue(_("analyzing")),
                            bold(pkg),
                        ),
                    importance = 1,
                    type = "info",
                    header = " ",
                    back = True,
                    count = (counter,maxcount,)
                )

                doinject = False
                if pkg in injected_packages:
                    doinject = True

                pkg_path = os.path.join(self.get_local_packages_directory(repo),etpConst['branch'],pkg)
                mydata = self.ClientService.extract_pkg_metadata(pkg_path, etpConst['branch'], inject = doinject)

                # get previous revision
                revision_avail = revisions_match.get(pkg)
                addRevision = 0
                if (revision_avail != None):
                    if etpConst['branch'] == revision_avail[0]:
                        addRevision = revision_avail[1]

                idpackage, revision, mydata_upd = dbconn.addPackage(mydata, revision = addRevision)
                idpackages_added.add(idpackage)

                self.updateProgress(
                    "[repo:%s] [%s:%s/%s] %s: %s, %s: %s" % (
                                repo,
                                brown(etpConst['branch']),
                                darkgreen(str(counter)),
                                blue(str(maxcount)),
                                red(_("added package")),
                                darkgreen(pkg),
                                red(_("revision")),
                                brown(str(revision)),
                        ),
                    importance = 1,
                    type = "info",
                    header = " ",
                    back = True
                )

            self.depends_table_initialize(repo)

            myQA = self.QA()

            if idpackages_added:
                dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
                myQA.scan_missing_dependencies(
                    idpackages_added, dbconn, ask = True,
                    repo = repo, self_check = True,
                    black_list = self.get_missing_dependencies_blacklist(repo = repo),
                    black_list_adder = self.add_missing_dependencies_blacklist_items
                )

        dbconn.commitChanges()
        self.close_server_databases()

        return 0

    def match_packages(self, packages, repo = None):

        dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo)
        if ("world" in packages) or not packages:
            return dbconn.listAllIdpackages(),True
        else:
            idpackages = set()
            for package in packages:
                matches = dbconn.atomMatch(package, multiMatch = True)
                if matches[1] == 0:
                    idpackages |= matches[0]
                else:
                    mytxt = "%s: %s: %s" % (red(_("Attention")),blue(_("cannot match")),bold(package),)
                    self.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "warning",
                        header = darkred(" !!! ")
                    )
            return idpackages,False

    def get_remote_package_checksum(self, repo, filename, branch):

        import urllib2
        if not etpConst['server_repositories'][repo].has_key('handler'):
            return None
        url = etpConst['server_repositories'][repo]['handler']

        # does the package has "#" (== tag) ? hackish thing that works
        filename = filename.replace("#","%23")
        # "+"
        filename = filename.replace("+","%2b")
        request = os.path.join(url,etpConst['handlers']['md5sum'])
        request += filename+"&branch="+branch

        # now pray the server
        try:
            mydict = {}
            if etpConst['proxy']['ftp']:
                mydict['ftp'] = etpConst['proxy']['ftp']
            if etpConst['proxy']['http']:
                mydict['http'] = etpConst['proxy']['http']
            if mydict:
                mydict['username'] = etpConst['proxy']['username']
                mydict['password'] = etpConst['proxy']['password']
                self.entropyTools.add_proxy_opener(urllib2, mydict)
            else:
                # unset
                urllib2._opener = None
            item = urllib2.urlopen(request)
            result = item.readline().strip()
            item.close()
            del item
            return result
        except: # no HTTP support?
            return None

    def verify_remote_packages(self, packages, ask = True, repo = None):

        if repo == None:
            repo = self.default_repository

        self.updateProgress(
            "[%s] %s:" % (
                red("remote"),
                blue(_("Integrity verification of the selected packages")),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )

        idpackages, world = self.match_packages(packages)
        dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo)

        if world:
            self.updateProgress(
                blue(_("All the packages in the Entropy Packages repository will be checked.")),
                importance = 1,
                type = "info",
                header = "    "
            )
        else:
            mytxt = red("%s:") % (_("This is the list of the packages that would be checked"),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = "    "
            )
            for idpackage in idpackages:
                pkgatom = dbconn.retrieveAtom(idpackage)
                pkgfile = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
                self.updateProgress(
                    red(pkgatom)+" -> "+bold(os.path.join(etpConst['branch'],pkgfile)),
                    importance = 1,
                    type = "info",
                    header = darkgreen("   - ")
                )

        if ask:
            rc = self.askQuestion(_("Would you like to continue ?"))
            if rc == "No":
                return set(),set(),{}

        match = set()
        not_match = set()
        broken_packages = {}

        for uri in self.get_remote_mirrors(repo):

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
            self.updateProgress(
                "[repo:%s] %s: %s" % (
                        darkgreen(repo),
                        blue(_("Working on mirror")),
                        brown(crippled_uri),
                    ),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )


            totalcounter = len(idpackages)
            currentcounter = 0
            for idpackage in idpackages:

                currentcounter += 1
                pkgfile = dbconn.retrieveDownloadURL(idpackage)
                orig_branch = self.get_branch_from_download_relative_uri(pkgfile)

                self.updateProgress(
                    "[%s] %s: %s" % (
                            brown(crippled_uri),
                            blue(_("checking hash")),
                            darkgreen(pkgfile),
                    ),
                    importance = 1,
                    type = "info",
                    header = blue(" @@ "),
                    back = True,
                    count = (currentcounter,totalcounter,)
                )

                ckOk = False
                ck = self.get_remote_package_checksum(repo, os.path.basename(pkgfile), orig_branch)
                if ck == None:
                    self.updateProgress(
                        "[%s] %s: %s %s" % (
                            brown(crippled_uri),
                            blue(_("digest verification of")),
                            bold(pkgfile),
                            blue(_("not supported")),
                        ),
                        importance = 1,
                        type = "info",
                        header = blue(" @@ "),
                        count = (currentcounter,totalcounter,)
                    )
                elif len(ck) == 32:
                    pkghash = dbconn.retrieveDigest(idpackage)
                    if ck == pkghash: ckOk = True
                else:
                    self.updateProgress(
                        "[%s] %s: %s %s" % (
                            brown(crippled_uri),
                            blue(_("digest verification of")),
                            bold(pkgfile),
                            blue(_("failed for unknown reasons")),
                        ),
                        importance = 1,
                        type = "info",
                        header = blue(" @@ "),
                        count = (currentcounter,totalcounter,)
                    )

                if ckOk:
                    match.add(idpackage)
                else:
                    not_match.add(idpackage)
                    self.updateProgress(
                        "[%s] %s: %s %s" % (
                            brown(crippled_uri),
                            blue(_("package")),
                            bold(pkgfile),
                            red(_("NOT healthy")),
                        ),
                        importance = 1,
                        type = "warning",
                        header = darkred(" !!! "),
                        count = (currentcounter,totalcounter,)
                    )
                    if not broken_packages.has_key(crippled_uri):
                        broken_packages[crippled_uri] = []
                    broken_packages[crippled_uri].append(pkgfile)

            if broken_packages:
                mytxt = blue("%s:") % (_("This is the list of broken packages"),)
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = red(" * ")
                )
                for mirror in broken_packages.keys():
                    mytxt = "%s: %s" % (brown(_("Mirror")),bold(mirror),)
                    self.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "info",
                        header = red("   <> ")
                    )
                    for bp in broken_packages[mirror]:
                        self.updateProgress(
                            blue(bp),
                            importance = 1,
                            type = "info",
                            header = red("      - ")
                        )

            self.updateProgress(
                "%s:" % (
                    blue(_("Statistics")),
                ),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
            self.updateProgress(
                "[%s] %s:\t%s" % (
                    red(crippled_uri),
                    brown(_("Number of checked packages")),
                    brown(str(len(match)+len(not_match))),
                ),
                importance = 1,
                type = "info",
               header = brown("   # ")
            )
            self.updateProgress(
                "[%s] %s:\t%s" % (
                    red(crippled_uri),
                    darkgreen(_("Number of healthy packages")),
                    darkgreen(str(len(match))),
                ),
                importance = 1,
                type = "info",
               header = brown("   # ")
            )
            self.updateProgress(
                "[%s] %s:\t%s" % (
                    red(crippled_uri),
                    darkred(_("Number of broken packages")),
                    darkred(str(len(not_match))),
                ),
                importance = 1,
                type = "info",
                header = brown("   # ")
            )

        return match, not_match, broken_packages


    def verify_local_packages(self, packages, ask = True, repo = None):

        if repo == None:
            repo = self.default_repository

        self.updateProgress(
            "[%s] %s:" % (
                red(_("local")),
                blue(_("Integrity verification of the selected packages")),
            ),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )

        idpackages, world = self.match_packages(packages)
        dbconn = self.openServerDatabase(read_only = True, no_upload = True, repo = repo)

        if world:
            self.updateProgress(
                blue(_("All the packages in the Entropy Packages repository will be checked.")),
                importance = 1,
                type = "info",
                header = "    "
            )

        to_download = set()
        available = set()
        for idpackage in idpackages:

            pkgatom = dbconn.retrieveAtom(idpackage)
            pkg_path = dbconn.retrieveDownloadURL(idpackage)
            pkg_rel_path = '/'.join(pkg_path.split("/")[2:])

            bindir_path = os.path.join(self.get_local_packages_directory(repo),pkg_rel_path)
            uploaddir_path = os.path.join(self.get_local_upload_directory(repo),pkg_rel_path)

            if os.path.isfile(bindir_path):
                if not world:
                    self.updateProgress(
                        "[%s] %s :: %s" % (
                                darkgreen(_("available")),
                                blue(pkgatom),
                                darkgreen(pkg_rel_path),
                        ),
                        importance = 0,
                        type = "info",
                        header = darkgreen("   # ")
                    )
                available.add(idpackage)
            elif os.path.isfile(uploaddir_path):
                if not world:
                    self.updateProgress(
                        "[%s] %s :: %s" % (
                                darkred(_("upload/ignored")),
                                blue(pkgatom),
                                darkgreen(pkg_rel_path),
                        ),
                        importance = 0,
                        type = "info",
                        header = darkgreen("   # ")
                    )
            else:
                self.updateProgress(
                    "[%s] %s :: %s" % (
                            brown(_("download")),
                            blue(pkgatom),
                            darkgreen(pkg_rel_path),
                    ),
                    importance = 0,
                    type = "info",
                    header = darkgreen("   # ")
                )
                to_download.add((idpackage,pkg_path,))

        if ask:
            rc = self.askQuestion(_("Would you like to continue ?"))
            if rc == "No":
                return set(),set(),set(),set()


        fine = set()
        failed = set()
        downloaded_fine = set()
        downloaded_errors = set()

        if to_download:

            not_downloaded = set()
            mytxt = blue("%s ...") % (_("Starting to download missing files"),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = "   "
            )
            for uri in self.get_remote_mirrors(repo):

                if not_downloaded:
                    mytxt = blue("%s ...") % (_("Trying to search missing or broken files on another mirror"),)
                    self.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "info",
                        header = "   "
                    )
                    to_download = not_downloaded.copy()
                    not_downloaded = set()

                for idpackage, pkg_path in to_download: # idpackage, pkgfile, branch
                    rc = self.MirrorsService.download_package(uri, pkg_path, repo = repo)
                    if rc:
                        downloaded_fine.add(idpackage)
                        available.add(idpackage)
                    else:
                        not_downloaded.add(pkg_path)

                if not not_downloaded:
                    self.updateProgress(
                        red(_("All the binary packages have been downloaded successfully.")),
                        importance = 1,
                        type = "info",
                        header = "   "
                    )
                    break

            if not_downloaded:
                mytxt = blue("%s:") % (_("These are the packages that cannot be found online"),)
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = "   "
                )
                for pkg_path in not_downloaded:
                    downloaded_errors.add(pkg_path)
                    self.updateProgress(
                            brown(pkg_path),
                            importance = 1,
                            type = "warning",
                            header = red("    * ")
                    )
                downloaded_errors |= not_downloaded
                mytxt = "%s." % (_("They won't be checked"),)
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = "   "
                )

        totalcounter = str(len(available))
        currentcounter = 0
        for idpackage in available:
            currentcounter += 1
            pkg_path = dbconn.retrieveDownloadURL(idpackage)
            orig_branch = self.get_branch_from_download_relative_uri(pkg_path)
            pkgfile = os.path.basename(pkg_path)

            self.updateProgress(
                "[branch:%s] %s %s" % (
                        brown(orig_branch),
                        blue(_("checking hash of")),
                        darkgreen(pkgfile),
                ),
                importance = 1,
                type = "info",
                header = "   ",
                back = True,
                count = (currentcounter,totalcounter,)
            )

            storedmd5 = dbconn.retrieveDigest(idpackage)
            pkgpath = os.path.join(self.get_local_packages_directory(repo),orig_branch,pkgfile)
            result = self.entropyTools.compareMd5(pkgpath,storedmd5)
            if result:
                fine.add(idpackage)
            else:
                failed.add(idpackage)
                self.updateProgress(
                    "[branch:%s] %s %s %s: %s" % (
                            brown(orig_branch),
                            blue(_("package")),
                            darkgreen(pkg_path),
                            blue(_("is corrupted, stored checksum")), # package -blah- is corrupted...
                            brown(storedmd5),
                    ),
                    importance = 1,
                    type = "info",
                    header = "   ",
                    count = (currentcounter,totalcounter,)
                )

        if failed:
            mytxt = blue("%s:") % (_("This is the list of broken packages"),)
            self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header =  darkred("  # ")
            )
            for idpackage in failed:
                atom = dbconn.retrieveAtom(idpackage)
                dp = dbconn.retrieveDownloadURL(idpackage)
                self.updateProgress(
                        blue("[atom:%s] %s" % (atom,dp,)),
                        importance = 0,
                        type = "warning",
                        header =  brown("    # ")
                )

        # print stats
        self.updateProgress(
            red("Statistics:"),
            importance = 1,
            type = "info",
            header = blue(" * ")
        )
        self.updateProgress(
            brown("%s:\t\t%s" % (
                    _("Number of checked packages"),
                    len(fine)+len(failed),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            darkgreen("%s:\t\t%s" % (
                    _("Number of healthy packages"),
                    len(fine),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            darkred("%s:\t\t%s" % (
                    _("Number of broken packages"),
                    len(failed),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            blue("%s:\t\t%s" % (
                    _("Number of downloaded packages"),
                    len(downloaded_fine),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            bold("%s:\t\t%s" % (
                    _("Number of failed downloads"),
                    len(downloaded_errors),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )

        self.close_server_database(dbconn)
        return fine, failed, downloaded_fine, downloaded_errors


    def switch_packages_branch(self, idpackages, from_branch, to_branch, repo = None):

        if repo == None:
            repo = self.default_repository

        if to_branch != etpConst['branch']:
            mytxt = "%s: %s %s" % (blue(_("Please setup your branch to")),bold(to_branch),blue(_("and retry")),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = darkred(" !! ")
            )
            return None

        mytxt = red("%s ...") % (_("Moving database (if not exists)"),)
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = darkgreen(" @@ ")
        )
        branch_dbdir = self.get_local_database_dir(repo)
        old_branch_dbdir = self.get_local_database_dir(repo, from_branch)
        if (not os.path.isdir(branch_dbdir)) and os.path.isdir(old_branch_dbdir):
            shutil.copytree(old_branch_dbdir,branch_dbdir)

        mytxt = red("%s ...") % (_("Switching packages"),)
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = darkgreen(" @@ ")
        )
        dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo, lock_remote = False)

        already_switched = set()
        not_found = set()
        switched = set()
        ignored = set()
        no_checksum = set()

        maxcount = len(idpackages)
        count = 0
        for idpackage in idpackages:
            count += 1

            cur_branch = dbconn.retrieveBranch(idpackage)
            atom = dbconn.retrieveAtom(idpackage)
            if cur_branch == to_branch:
                already_switched.add(idpackage)
                self.updateProgress(
                    red("%s %s, %s %s" % (
                            _("Ignoring"),
                            bold(atom),
                            _("already in branch"),
                            cur_branch,
                        )
                    ),
                    importance = 0,
                    type = "info",
                    header = darkgreen(" @@ "),
                    count = (count,maxcount,)
                )
                ignored.add(idpackage)
                continue

            mytxt = blue("%s ...") % (_("configuring package information"),)
            self.updateProgress(
                "[%s=>%s] %s, %s" % (
                    brown(cur_branch),
                    bold(to_branch),
                    darkgreen(atom),
                    mytxt,
                ),
                importance = 0,
                type = "info",
                header = darkgreen(" @@ "),
                back = True,
                count = (count,maxcount,)
            )
            switch_status = dbconn.switchBranch(idpackage,to_branch)
            if not switch_status:
                # remove idpackage
                dbconn.removePackage(idpackage)
            dbconn.commitChanges()
            switched.add(idpackage)

        dbconn.commitChanges()

        # now migrate counters
        dbconn.moveCountersToBranch(to_branch)

        self.close_server_database(dbconn)
        mytxt = blue("%s.") % (_("migration loop completed"),)
        self.updateProgress(
            "[%s=>%s] %s" % (
                    brown(from_branch),
                    bold(to_branch),
                    mytxt,
            ),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )

        return switched, already_switched, ignored, not_found, no_checksum

    def get_entropy_sets(self, repo = None, branch = etpConst['branch']):

        if repo == None: repo = self.default_repository

        sets_dir = self.get_local_database_sets_dir(repo, branch)
        if not (os.path.isdir(sets_dir) and os.access(sets_dir,os.R_OK)):
            return {}

        mydata = {}
        items = os.listdir(sets_dir)
        for item in items:

            try:
                item_clean = str(item)
            except (UnicodeEncodeError,UnicodeDecodeError,):
                continue
            item_path = os.path.join(sets_dir,item)
            if not (os.path.isfile(item_path) and os.access(item_path,os.R_OK)):
                continue
            item_elements = self.entropyTools.extract_packages_from_set_file(item_path)
            if item_elements:
                mydata[item_clean] = item_elements.copy()

        return mydata

    def get_configured_package_sets(self, repo = None, branch = etpConst['branch'], validate = True):

        if repo == None: repo = self.default_repository

        # portage sets
        sets_data = self.SpmService.get_sets_expanded(builtin_sets = False)
        sets_data.update(self.get_entropy_sets(repo, branch))

        if validate:
            invalid_sets = set()
            # validate
            for setname in sets_data:
                good = True
                for atom in sets_data[setname]:
                    dbconn = self.openServerDatabase(just_reading = True, repo = repo)
                    match = dbconn.atomMatch(atom)
                    if match[0] == -1:
                        good = False
                        break
                if not good: invalid_sets.add(setname)
            for invalid_set in invalid_sets:
                del sets_data[invalid_set]

        return sets_data

    def update_database_package_sets(self, repo = None, dbconn = None):

        if repo == None: repo = self.default_repository
        package_sets = self.get_configured_package_sets(repo)
        if dbconn == None: dbconn = self.openServerDatabase(read_only = False, no_upload = True, repo = repo)
        dbconn.clearPackageSets()
        if package_sets: dbconn.insertPackageSets(package_sets)
        dbconn.commitChanges()

class MirrorsServer:

    import socket
    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    def __init__(self,  ServerInstance, repo = None):

        if not isinstance(ServerInstance,Server):
            mytxt = _("A valid Server interface based instance is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.Entropy = ServerInstance
        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()
        self.FtpInterface = self.Entropy.FtpInterface
        self.rssFeed = self.Entropy.rssFeed

        mytxt = blue("%s:") % (_("Entropy Server Mirrors Interface loaded"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        mytxt = _("mirror")
        for mirror in self.Entropy.get_remote_mirrors(repo):
            mirror = self.entropyTools.hideFTPpassword(mirror)
            self.Entropy.updateProgress(
                blue("%s: %s") % (mytxt,darkgreen(mirror),),
                importance = 0,
                type = "info",
                header = brown("   # ")
            )


    def lock_mirrors(self, lock = True, mirrors = [], repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        if not mirrors:
            mirrors = self.Entropy.get_remote_mirrors(repo)

        issues = False
        for uri in mirrors:

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)

            lock_text = _("unlocking")
            if lock: lock_text = _("locking")
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    bold(lock_text),
                    blue("%s...") % (_("mirror"),),
                ),
                importance = 1,
                type = "info",
                header = brown(" * "),
                back = True
            )

            try:
                ftp = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.printTraceback()
                return True # issues
            my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
            ftp.set_cwd(my_path, dodir = True)

            if lock and ftp.is_file_available(etpConst['etpdatabaselockfile']):
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            blue(_("mirror already locked")),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                ftp.close()
                continue
            elif not lock and not ftp.is_file_available(etpConst['etpdatabaselockfile']):
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            blue(_("mirror already unlocked")),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                ftp.close()
                continue

            if lock:
                rc = self.do_mirror_lock(uri, ftp, repo = repo)
            else:
                rc = self.do_mirror_unlock(uri, ftp, repo = repo)
            ftp.close()
            if not rc: issues = True

        if not issues:
            database_taint_file = self.Entropy.get_local_database_taint_file(repo)
            if os.path.isfile(database_taint_file):
                os.remove(database_taint_file)

        return issues

    # this functions makes entropy clients to not download anything from the chosen
    # mirrors. it is used to avoid clients to download databases while we're uploading
    # a new one.
    def lock_mirrors_for_download(self, lock = True, mirrors = [], repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        if not mirrors:
            mirrors = self.Entropy.get_remote_mirrors(repo)

        issues = False
        for uri in mirrors:

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)

            lock_text = _("unlocking")
            if lock: lock_text = _("locking")
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s %s..." % (
                            blue(repo),
                            red(crippled_uri),
                            bold(lock_text),
                            blue(_("mirror for download")),
                    ),
                importance = 1,
                type = "info",
                header = red(" @@ "),
                back = True
            )

            try:
                ftp = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.printTraceback()
                return True # issues
            my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
            ftp.set_cwd(my_path, dodir = True)

            if lock and ftp.is_file_available(etpConst['etpdatabasedownloadlockfile']):
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("mirror already locked for download")),
                        ),
                    importance = 1,
                    type = "info",
                    header = red(" @@ ")
                )
                ftp.close()
                continue
            elif not lock and not ftp.is_file_available(etpConst['etpdatabasedownloadlockfile']):
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("mirror already unlocked for download")),
                        ),
                    importance = 1,
                    type = "info",
                    header = red(" @@ ")
                )
                ftp.close()
                continue

            if lock:
                rc = self.do_mirror_lock(uri, ftp, dblock = False, repo = repo)
            else:
                rc = self.do_mirror_unlock(uri, ftp, dblock = False, repo = repo)
            ftp.close()
            if not rc: issues = True

        return issues

    def do_mirror_lock(self, uri, ftp_connection = None, dblock = True, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
        if not ftp_connection:
            try:
                ftp_connection = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.printTraceback()
                return False # issues
            ftp_connection.set_cwd(my_path, dodir = True)
        else:
            mycwd = ftp_connection.get_cwd()
            if mycwd != my_path:
                ftp_connection.set_basedir()
                ftp_connection.set_cwd(my_path, dodir = True)

        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
        lock_string = ''
        if dblock:
            self.create_local_database_lockfile(repo)
            lock_file = self.get_database_lockfile(repo)
        else:
            lock_string = _('for download') # locking/unlocking mirror1 for download
            self.create_local_database_download_lockfile(repo)
            lock_file = self.get_database_download_lockfile(repo)

        rc = ftp_connection.upload_file(lock_file, ascii = True)
        if rc:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("mirror successfully locked")),
                            blue(lock_string),
                    ),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
        else:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s: %s - %s %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue("lock error"),
                            rc,
                            blue(_("mirror not locked")),
                            blue(lock_string),
                    ),
                importance = 1,
                type = "error",
                header = darkred(" * ")
            )
            self.remove_local_database_lockfile(repo)

        return rc


    def do_mirror_unlock(self, uri, ftp_connection, dblock = True, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
        if not ftp_connection:
            try:
                ftp_connection = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.printTraceback()
                return False # issues
            ftp_connection.set_cwd(my_path)
        else:
            mycwd = ftp_connection.get_cwd()
            if mycwd != my_path:
                ftp_connection.set_basedir()
                ftp_connection.set_cwd(my_path)

        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)

        if dblock:
            dbfile = etpConst['etpdatabaselockfile']
        else:
            dbfile = etpConst['etpdatabasedownloadlockfile']
        rc = ftp_connection.delete_file(dbfile)
        if rc:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("mirror successfully unlocked")),
                    ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
            if dblock:
                self.remove_local_database_lockfile(repo)
            else:
                self.remove_local_database_download_lockfile(repo)
        else:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s: %s - %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("unlock error")),
                            rc,
                            blue(_("mirror not unlocked")),
                    ),
                importance = 1,
                type = "error",
                header = darkred(" * ")
            )

        return rc

    def get_database_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        return os.path.join(self.Entropy.get_local_database_dir(repo),etpConst['etpdatabaselockfile'])

    def get_database_download_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        return os.path.join(self.Entropy.get_local_database_dir(repo),etpConst['etpdatabasedownloadlockfile'])

    def create_local_database_download_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_download_lockfile(repo)
        f = open(lock_file,"w")
        f.write("download locked")
        f.flush()
        f.close()

    def create_local_database_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_lockfile(repo)
        f = open(lock_file,"w")
        f.write("database locked")
        f.flush()
        f.close()

    def remove_local_database_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_lockfile(repo)
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def remove_local_database_download_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_download_lockfile(repo)
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def download_package(self, uri, pkg_relative_path, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)

        tries = 0
        while tries < 5:
            tries += 1

            pkg_to_join_path = '/'.join(pkg_relative_path.split('/')[2:])
            pkg_to_join_dirpath = os.path.dirname(pkg_to_join_path)
            pkgfile = os.path.basename(pkg_relative_path)

            self.Entropy.updateProgress(
                "[repo:%s|%s|#%s] %s: %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    brown(tries),
                    blue(_("connecting to download package")), # connecting to download package xyz
                    darkgreen(pkg_to_join_path),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )

            try:
                ftp = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.printTraceback()
                return False # issues
            dirpath = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),pkg_to_join_dirpath)
            ftp.set_cwd(dirpath, dodir = True)

            self.Entropy.updateProgress(
                "[repo:%s|%s|#%s] %s: %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    brown(tries),
                    blue(_("downloading package")),
                    darkgreen(pkg_to_join_path),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )

            download_path = os.path.join(self.Entropy.get_local_packages_directory(repo),pkg_to_join_dirpath)
            if (not os.path.isdir(download_path)) and (not os.access(download_path,os.R_OK)):
                os.makedirs(download_path)
            rc = ftp.download_file(pkgfile,download_path)
            if not rc:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(tries),
                        blue(_("package")),
                        darkgreen(pkg_to_join_path),
                        blue(_("does not exist")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                ftp.close()
                return rc

            dbconn = self.Entropy.openServerDatabase(read_only = True, no_upload = True, repo = repo)
            idpackage = dbconn.getIDPackageFromDownload(pkg_relative_path)
            if idpackage == -1:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(tries),
                        blue(_("package")),
                        darkgreen(pkgfile),
                        blue(_("is not listed in the current repository database!!")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                ftp.close()
                return False

            storedmd5 = dbconn.retrieveDigest(idpackage)
            self.Entropy.updateProgress(
                "[repo:%s|%s|#%s] %s: %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    brown(tries),
                    blue(_("verifying checksum of package")),
                    darkgreen(pkgfile),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )

            pkg_path = os.path.join(download_path,pkgfile)
            md5check = self.entropyTools.compareMd5(pkg_path,storedmd5)
            if md5check:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(tries),
                        blue(_("package")),
                        darkgreen(pkgfile),
                        blue(_("downloaded successfully")),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                return True
            else:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(tries),
                        blue(_("package")),
                        darkgreen(pkgfile),
                        blue(_("checksum does not match. re-downloading...")),
                    ),
                    importance = 1,
                    type = "warning",
                    header = darkred(" * ")
                )
                if os.path.isfile(pkg_path):
                    os.remove(pkg_path)

            continue

        # if we get here it means the files hasn't been downloaded properly
        self.Entropy.updateProgress(
            "[repo:%s|%s|#%s] %s: %s %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                brown(tries),
                blue(_("package")),
                darkgreen(pkgfile),
                blue(_("seems broken. Consider to re-package it. Giving up!")),
            ),
            importance = 1,
            type = "error",
            header = darkred(" !!! ")
        )
        return False


    def get_remote_databases_status(self, repo = None, mirrors = []):

        if repo == None:
            repo = self.Entropy.default_repository

        if not mirrors:
            mirrors = self.Entropy.get_remote_mirrors(repo)

        data = []
        for uri in mirrors:

            # let it raise an exception if connection is impossible
            ftp = self.FtpInterface(uri, self.Entropy)
            try:
                my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
                ftp.set_cwd(my_path, dodir = True)
            except ftp.ftplib.error_perm:
                crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s !" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            blue(_("mirror doesn't have a valid directory structure")),
                    ),
                    importance = 1,
                    type = "warning",
                    header = darkred(" !!! ")
                )
                ftp.close()
                continue
            cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
            if cmethod == None:
                raise InvalidDataType("InvalidDataType: %s." % (
                        _("Wrong database compression method passed"),
                    )
                )
            compressedfile = etpConst[cmethod[2]]

            revision = 0
            rc1 = ftp.is_file_available(compressedfile)
            revfilename = os.path.basename(self.Entropy.get_local_database_revision_file(repo))
            rc2 = ftp.is_file_available(revfilename)
            if rc1 and rc2:
                revision_localtmppath = os.path.join(etpConst['packagestmpdir'],revfilename)
                dlcount = 5
                while dlcount:
                    dled = ftp.download_file(revfilename,etpConst['packagestmpdir'],True)
                    if dled: break
                    dlcount -= 1

                crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
                try:
                    f = open(revision_localtmppath,"r")
                    revision = int(f.readline().strip())
                except IOError:
                    if dlcount == 0:
                        self.Entropy.updateProgress(
                            "[repo:%s|%s] %s: %s" % (
                                    brown(repo),
                                    darkgreen(crippled_uri),
                                    blue(_("unable to download remote mirror repository revision file, defaulting to 0")),
                                    bold(revision),
                            ),
                            importance = 1,
                            type = "error",
                            header = darkred(" !!! ")
                        )
                    else:
                        self.Entropy.updateProgress(
                            "[repo:%s|%s] %s: %s" % (
                                    brown(repo),
                                    darkgreen(crippled_uri),
                                    blue(_("mirror doesn't have a valid database revision file")),
                                    bold(revision),
                            ),
                            importance = 1,
                            type = "error",
                            header = darkred(" !!! ")
                        )
                    revision = 0
                except ValueError:
                    self.Entropy.updateProgress(
                        "[repo:%s|%s] %s: %s" % (
                                brown(repo),
                                darkgreen(crippled_uri),
                                blue(_("mirror doesn't have a valid database revision file")),
                                bold(revision),
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    revision = 0
                f.close()
                if os.path.isfile(revision_localtmppath):
                    os.remove(revision_localtmppath)

            info = [uri,revision]
            data.append(info)
            ftp.close()

        return data

    def is_local_database_locked(self, repo = None):
        x = repo
        if x == None:
            x = self.Entropy.default_repository
        lock_file = self.get_database_lockfile(x)
        return os.path.isfile(lock_file)

    def get_mirrors_lock(self, repo = None):

        dbstatus = []
        for uri in self.Entropy.get_remote_mirrors(repo):
            data = [uri,False,False]
            ftp = self.FtpInterface(uri, self.Entropy)
            try:
                my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
                ftp.set_cwd(my_path)
            except ftp.ftplib.error_perm:
                ftp.close()
                continue
            if ftp.is_file_available(etpConst['etpdatabaselockfile']):
                # upload locked
                data[1] = True
            if ftp.is_file_available(etpConst['etpdatabasedownloadlockfile']):
                # download locked
                data[2] = True
            ftp.close()
            dbstatus.append(data)
        return dbstatus

    def download_notice_board(self, repo = None):

        if repo == None: repo = self.Entropy.default_repository
        mirrors = self.Entropy.get_remote_mirrors(repo)
        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        mytmpdir = self.entropyTools.getRandomTempFile()
        os.makedirs(mytmpdir)

        self.Entropy.updateProgress(
            "[repo:%s] %s %s" % (
                    brown(repo),
                    blue(_("downloading notice board from mirrors to")),
                    red(rss_path),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )

        downloaded = False
        for uri in mirrors:
            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
            downloader = self.FileTransceiver(
                self.FtpInterface, self.Entropy, [uri],
                [rss_path], download = True,
                local_basedir = mytmpdir, critical_files = [rss_path], repo = repo
            )
            errors, m_fine_uris, m_broken_uris = downloader.go()
            if not errors:
                self.Entropy.updateProgress(
                    "[repo:%s] %s: %s" % (
                            brown(repo),
                            blue(_("notice board downloaded successfully from")),
                            red(crippled_uri),
                    ),
                    importance = 1,
                    type = "info",
                    header = blue(" @@ ")
                )
                downloaded = True
                break

        if downloaded:
            shutil.move(os.path.join(mytmpdir,os.path.basename(rss_path)),rss_path)

        return downloaded

    def upload_notice_board(self, repo = None):

        if repo == None: repo = self.Entropy.default_repository
        mirrors = self.Entropy.get_remote_mirrors(repo)
        rss_path = self.Entropy.get_local_database_notice_board_file(repo)

        self.Entropy.updateProgress(
            "[repo:%s] %s %s" % (
                    brown(repo),
                    blue(_("uploading notice board from")),
                    red(rss_path),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )

        uploader = self.FileTransceiver(
            self.FtpInterface,
            self.Entropy,
            mirrors,
            [rss_path],
            critical_files = [rss_path],
            repo = repo
        )
        errors, m_fine_uris, m_broken_uris = uploader.go()
        if errors:
            m_broken_uris = sorted(list(m_broken_uris))
            m_broken_uris = [self.entropyTools.extractFTPHostFromUri(x) for x in m_broken_uris]
            self.Entropy.updateProgress(
                "[repo:%s] %s %s" % (
                        brown(repo),
                        blue(_("notice board upload failed on")),
                        red(', '.join(m_broken_uris)),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            return False
        self.Entropy.updateProgress(
            "[repo:%s] %s" % (
                    brown(repo),
                    blue(_("notice board upload success")),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )
        return True


    def update_notice_board(self, title, notice_text, link = None, repo = None):

        rss_title = "%s Notice Board" % (etpConst['systemname'],)
        rss_description = "Inform about important distribution activities."
        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        if not link: link = etpConst['rss-website-url']

        self.download_notice_board(repo)
        Rss = self.rssFeed(rss_path, rss_title, rss_description, maxentries = 20)
        Rss.addItem(title, link, description = notice_text)
        Rss.writeChanges()
        status = self.upload_notice_board(repo)
        return status

    def read_notice_board(self, do_download = True, repo = None):

        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        if do_download: self.download_notice_board(repo)
        if not (os.path.isfile(rss_path) and os.access(rss_path,os.R_OK)):
            return None
        Rss = self.rssFeed(rss_path, '', '')
        return Rss.getEntries()

    def remove_from_notice_board(self, identifier, repo = None):

        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        rss_title = "%s Notice Board" % (etpConst['systemname'],)
        rss_description = "Inform about important distribution activities."
        if not (os.path.isfile(rss_path) and os.access(rss_path,os.R_OK)):
            return 0
        Rss = self.rssFeed(rss_path, rss_title, rss_description)
        data = Rss.removeEntry(identifier)
        Rss.writeChanges()
        return data

    def update_rss_feed(self, repo = None):

        #db_dir = self.Entropy.get_local_database_dir(repo)
        rss_path = self.Entropy.get_local_database_rss_file(repo)
        rss_light_path = self.Entropy.get_local_database_rsslight_file(repo)
        rss_dump_name = etpConst['rss-dump-name']
        db_revision_path = self.Entropy.get_local_database_revision_file(repo)

        rss_title = "%s Online Repository Status" % (etpConst['systemname'],)
        rss_description = "Keep you updated on what's going on in the %s Repository." % (etpConst['systemname'],)
        Rss = self.rssFeed(rss_path, rss_title, rss_description, maxentries = etpConst['rss-max-entries'])
        # load dump
        db_actions = self.Cacher.pop(rss_dump_name)
        if db_actions:
            try:
                f = open(db_revision_path)
                revision = f.readline().strip()
                f.close()
            except (IOError, OSError):
                revision = "N/A"
            commitmessage = ''
            if self.Entropy.rssMessages['commitmessage']:
                commitmessage = ' :: '+self.Entropy.rssMessages['commitmessage']
            title = ": "+etpConst['systemname']+" "+etpConst['product'][0].upper()+etpConst['product'][1:]+" "+etpConst['branch']+" :: Revision: "+revision+commitmessage
            link = etpConst['rss-base-url']
            # create description
            added_items = db_actions.get("added")
            if added_items:
                for atom in added_items:
                    mylink = link+"?search="+atom.split("~")[0]+"&arch="+etpConst['currentarch']+"&product="+etpConst['product']
                    description = atom+": "+added_items[atom]['description']
                    Rss.addItem(title = "Added/Updated"+title, link = mylink, description = description)
            removed_items = db_actions.get("removed")
            if removed_items:
                for atom in removed_items:
                    description = atom+": "+removed_items[atom]['description']
                    Rss.addItem(title = "Removed"+title, link = link, description = description)
            light_items = db_actions.get('light')
            if light_items:
                rssLight = self.rssFeed(rss_light_path, rss_title, rss_description, maxentries = etpConst['rss-light-max-entries'])
                for atom in light_items:
                    mylink = link+"?search="+atom.split("~")[0]+"&arch="+etpConst['currentarch']+"&product="+etpConst['product']
                    description = light_items[atom]['description']
                    rssLight.addItem(title = "["+revision+"] "+atom, link = mylink, description = description)
                rssLight.writeChanges()

        Rss.writeChanges()
        self.Entropy.rssMessages.clear()
        self.dumpTools.removeobj(rss_dump_name)


    # f_out is a file instance
    def dump_database_to_file(self, db_path, destination_path, opener, repo = None):
        f_out = opener(destination_path, "wb")
        dbconn = self.Entropy.openServerDatabase(db_path, just_reading = True, repo = repo)
        dbconn.doDatabaseExport(f_out)
        self.Entropy.close_server_database(dbconn)
        f_out.close()

    def create_file_checksum(self, file_path, checksum_path):
        mydigest = self.entropyTools.md5sum(file_path)
        f = open(checksum_path,"w")
        mystring = "%s  %s\n" % (mydigest,os.path.basename(file_path),)
        f.write(mystring)
        f.flush()
        f.close()

    def compress_file(self, file_path, destination_path, opener):
        f_out = opener(destination_path, "wb")
        f_in = open(file_path,"rb")
        data = f_in.read(8192)
        while data:
            f_out.write(data)
            data = f_in.read(8192)
        f_in.close()
        try:
            f_out.flush()
        except:
            pass
        f_out.close()

    def get_files_to_sync(self, cmethod, download = False, repo = None):

        critical = []
        extra_text_files = []
        data = {}
        data['database_revision_file'] = self.Entropy.get_local_database_revision_file(repo)
        extra_text_files.append(data['database_revision_file'])
        critical.append(data['database_revision_file'])

        database_package_mask_file = self.Entropy.get_local_database_mask_file(repo)
        extra_text_files.append(database_package_mask_file)
        if os.path.isfile(database_package_mask_file) or download:
            data['database_package_mask_file'] = database_package_mask_file
            if not download:
                critical.append(data['database_package_mask_file'])

        database_package_system_mask_file = self.Entropy.get_local_database_system_mask_file(repo)
        extra_text_files.append(database_package_system_mask_file)
        if os.path.isfile(database_package_system_mask_file) or download:
            data['database_package_system_mask_file'] = database_package_system_mask_file
            if not download:
                critical.append(data['database_package_system_mask_file'])

        database_package_confl_tagged_file = self.Entropy.get_local_database_confl_tagged_file(repo)
        extra_text_files.append(database_package_confl_tagged_file)
        if os.path.isfile(database_package_confl_tagged_file) or download:
            data['database_package_confl_tagged_file'] = database_package_confl_tagged_file
            if not download:
                critical.append(data['database_package_confl_tagged_file'])

        database_license_whitelist_file = self.Entropy.get_local_database_licensewhitelist_file(repo)
        extra_text_files.append(database_license_whitelist_file)
        if os.path.isfile(database_license_whitelist_file) or download:
            data['database_license_whitelist_file'] = database_license_whitelist_file
            if not download:
                critical.append(data['database_license_whitelist_file'])

        database_rss_file = self.Entropy.get_local_database_rss_file(repo)
        if os.path.isfile(database_rss_file) or download:
            data['database_rss_file'] = database_rss_file
            if not download:
                critical.append(data['database_rss_file'])
        database_rss_light_file = self.Entropy.get_local_database_rsslight_file(repo)
        extra_text_files.append(database_rss_light_file)
        if os.path.isfile(database_rss_light_file) or download:
            data['database_rss_light_file'] = database_rss_light_file
            if not download:
                critical.append(data['database_rss_light_file'])

        # EAPI 2,3
        if not download: # we don't need to get the dump
            data['metafiles_path'] = self.Entropy.get_local_database_compressed_metafiles_file(repo)
            critical.append(data['metafiles_path'])
            data['dump_path'] = os.path.join(self.Entropy.get_local_database_dir(repo),etpConst[cmethod[3]])
            critical.append(data['dump_path'])
            data['dump_path_digest'] = os.path.join(self.Entropy.get_local_database_dir(repo),etpConst[cmethod[4]])
            critical.append(data['dump_path_digest'])
            data['database_path'] = self.Entropy.get_local_database_file(repo)
            critical.append(data['database_path'])

        # EAPI 1
        data['compressed_database_path'] = os.path.join(self.Entropy.get_local_database_dir(repo),etpConst[cmethod[2]])
        critical.append(data['compressed_database_path'])
        data['compressed_database_path_digest'] = os.path.join(
            self.Entropy.get_local_database_dir(repo),etpConst['etpdatabasehashfile']
        )
        critical.append(data['compressed_database_path_digest'])

        # SSL cert file, just for reference
        ssl_ca_cert = self.Entropy.get_local_database_ca_cert_file()
        extra_text_files.append(ssl_ca_cert)
        if os.path.isfile(ssl_ca_cert):
            data['ssl_ca_cert_file'] = ssl_ca_cert
            if not download:
                critical.append(ssl_ca_cert)
        ssl_server_cert = self.Entropy.get_local_database_server_cert_file()
        extra_text_files.append(ssl_server_cert)
        if os.path.isfile(ssl_server_cert):
            data['ssl_server_cert_file'] = ssl_server_cert
            if not download:
                critical.append(ssl_server_cert)

        # Some information regarding how packages are built
        spm_files = [
            (etpConst['spm']['global_make_conf'],"global_make_conf"),
            (etpConst['spm']['global_package_keywords'],"global_package_keywords"),
            (etpConst['spm']['global_package_use'],"global_package_use"),
            (etpConst['spm']['global_package_mask'],"global_package_mask"),
            (etpConst['spm']['global_package_unmask'],"global_package_unmask"),
        ]
        for myfile,myname in spm_files:
            if os.path.isfile(myfile) and os.access(myfile,os.R_OK):
                data[myname] = myfile
            extra_text_files.append(myfile)

        make_profile = etpConst['spm']['global_make_profile']
        mytmpdir = os.path.dirname(self.Entropy.entropyTools.getRandomTempFile())
        mytmpfile = os.path.join(mytmpdir,etpConst['spm']['global_make_profile_link_name'])
        extra_text_files.append(mytmpfile)
        if os.path.islink(make_profile):
            mylink = os.readlink(make_profile)
            f = open(mytmpfile,"w")
            f.write(mylink)
            f.flush()
            f.close()
            data['global_make_profile'] = mytmpfile

        return data, critical, extra_text_files

    class FileTransceiver:

        import entropy.tools as entropyTools
        def __init__(   self,
                        ftp_interface,
                        entropy_interface,
                        uris,
                        files_to_upload,
                        download = False,
                        remove = False,
                        ftp_basedir = None,
                        local_basedir = None,
                        critical_files = [],
                        use_handlers = False,
                        handlers_data = {},
                        repo = None
            ):

            self.FtpInterface = ftp_interface
            self.Entropy = entropy_interface
            if not isinstance(uris,list):
                raise InvalidDataType("InvalidDataType: %s" % (_("uris must be a list instance"),))
            if not isinstance(files_to_upload,(list,dict)):
                raise InvalidDataType("InvalidDataType: %s" % (
                        _("files_to_upload must be a list or dict instance"),
                    )
                )
            self.uris = uris
            if isinstance(files_to_upload,list):
                self.myfiles = files_to_upload[:]
            else:
                self.myfiles = sorted([x for x in files_to_upload])
            self.download = download
            self.remove = remove
            self.repo = repo
            if self.repo == None:
                self.repo = self.Entropy.default_repository
            self.use_handlers = use_handlers
            if self.remove:
                self.download = False
                self.use_handlers = False
            if not ftp_basedir:
                # default to database directory
                my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
                self.ftp_basedir = unicode(my_path)
            else:
                self.ftp_basedir = unicode(ftp_basedir)
            if not local_basedir:
                # default to database directory
                self.local_basedir = os.path.dirname(self.Entropy.get_local_database_file(self.repo))
            else:
                self.local_basedir = unicode(local_basedir)
            self.critical_files = critical_files
            self.handlers_data = handlers_data.copy()

        def handler_verify_upload(self, local_filepath, uri, ftp_connection, counter, maxcount, action, tries):

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)

            self.Entropy.updateProgress(
                "[%s|#%s|(%s/%s)] %s: %s" % (
                    blue(crippled_uri),
                    darkgreen(str(tries)),
                    blue(str(counter)),
                    bold(str(maxcount)),
                    darkgreen(_("verifying upload (if supported)")),
                    blue(os.path.basename(local_filepath)),
                ),
                importance = 0,
                type = "info",
                header = red(" @@ "),
                back = True
            )

            checksum = self.Entropy.get_remote_package_checksum(
                self.repo,
                os.path.basename(local_filepath),
                self.handlers_data['branch']
            )
            if checksum == None:
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        darkred(_("not supported")),
                    ),
                    importance = 0,
                    type = "info",
                    header = red(" @@ ")
                )
                return True
            elif checksum == False:
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        bold(_("file not found")),
                    ),
                    importance = 0,
                    type = "warning",
                    header = brown(" @@ ")
                )
                return False
            elif len(checksum) == 32:
                # valid? checking
                ckres = self.entropyTools.compareMd5(local_filepath,checksum)
                if ckres:
                    self.Entropy.updateProgress(
                        "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                            blue(crippled_uri),
                            darkgreen(str(tries)),
                            blue(str(counter)),
                            bold(str(maxcount)),
                            blue(_("digest verification")),
                            os.path.basename(local_filepath),
                            darkgreen(_("so far, so good!")),
                        ),
                        importance = 0,
                        type = "info",
                        header = red(" @@ ")
                    )
                    return True
                else:
                    self.Entropy.updateProgress(
                        "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                            blue(crippled_uri),
                            darkgreen(str(tries)),
                            blue(str(counter)),
                            bold(str(maxcount)),
                            blue(_("digest verification")),
                            os.path.basename(local_filepath),
                            darkred(_("invalid checksum")),
                        ),
                        importance = 0,
                        type = "warning",
                        header = brown(" @@ ")
                    )
                    return False
            else:
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        darkred(_("unknown data returned")),
                    ),
                    importance = 0,
                    type = "warning",
                    header = brown(" @@ ")
                )
                return True

        def go(self):

            broken_uris = set()
            fine_uris = set()
            errors = False
            action = 'upload'
            if self.download:
                action = 'download'
            elif self.remove:
                action = 'remove'

            for uri in self.uris:

                crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
                self.Entropy.updateProgress(
                    "[%s|%s] %s..." % (
                        blue(crippled_uri),
                        brown(action),
                        blue(_("connecting to mirror")),
                    ),
                    importance = 0,
                    type = "info",
                    header = blue(" @@ ")
                )
                try:
                    ftp = self.FtpInterface(uri, self.Entropy)
                except ConnectionError:
                    self.entropyTools.printTraceback()
                    return True,fine_uris,broken_uris # issues
                my_path = os.path.join(self.Entropy.get_remote_database_relative_path(self.repo),etpConst['branch'])
                self.Entropy.updateProgress(
                    "[%s|%s] %s %s..." % (
                        blue(crippled_uri),
                        brown(action),
                        blue(_("changing directory to")),
                        darkgreen(my_path),
                    ),
                    importance = 0,
                    type = "info",
                    header = blue(" @@ ")
                )

                ftp.set_cwd(self.ftp_basedir, dodir = True)
                maxcount = len(self.myfiles)
                counter = 0

                for mypath in self.myfiles:

                    ftp.set_basedir()
                    ftp.set_cwd(self.ftp_basedir, dodir = True)

                    mycwd = None
                    if isinstance(mypath,tuple):
                        if len(mypath) < 2: continue
                        mycwd = mypath[0]
                        mypath = mypath[1]
                        ftp.set_cwd(mycwd, dodir = True)

                    syncer = ftp.upload_file
                    myargs = [mypath]
                    if self.download:
                        syncer = ftp.download_file
                        myargs = [os.path.basename(mypath),self.local_basedir]
                    elif self.remove:
                        syncer = ftp.delete_file

                    counter += 1
                    tries = 0
                    done = False
                    lastrc = None
                    while tries < 5:
                        tries += 1
                        self.Entropy.updateProgress(
                            "[%s|#%s|(%s/%s)] %s: %s" % (
                                blue(crippled_uri),
                                darkgreen(str(tries)),
                                blue(str(counter)),
                                bold(str(maxcount)),
                                blue(action+"ing"),
                                red(os.path.basename(mypath)),
                            ),
                            importance = 0,
                            type = "info",
                            header = red(" @@ ")
                        )
                        rc = syncer(*myargs)
                        if rc and self.use_handlers and not self.download:
                            rc = self.handler_verify_upload(mypath, uri, ftp, counter, maxcount, action, tries)
                        if rc:
                            self.Entropy.updateProgress(
                                "[%s|#%s|(%s/%s)] %s %s: %s" % (
                                            blue(crippled_uri),
                                            darkgreen(str(tries)),
                                            blue(str(counter)),
                                            bold(str(maxcount)),
                                            blue(action),
                                            _("successful"),
                                            red(os.path.basename(mypath)),
                                ),
                                importance = 0,
                                type = "info",
                                header = darkgreen(" @@ ")
                            )
                            done = True
                            break
                        else:
                            self.Entropy.updateProgress(
                                "[%s|#%s|(%s/%s)] %s %s: %s" % (
                                            blue(crippled_uri),
                                            darkgreen(str(tries)),
                                            blue(str(counter)),
                                            bold(str(maxcount)),
                                            blue(action),
                                            brown(_("failed, retrying")),
                                            red(os.path.basename(mypath)),
                                    ),
                                importance = 0,
                                type = "warning",
                                header = brown(" @@ ")
                            )
                            lastrc = rc
                            continue

                    if not done:

                        self.Entropy.updateProgress(
                            "[%s|(%s/%s)] %s %s: %s - %s: %s" % (
                                    blue(crippled_uri),
                                    blue(str(counter)),
                                    bold(str(maxcount)),
                                    blue(action),
                                    darkred("failed, giving up"),
                                    red(os.path.basename(mypath)),
                                    _("error"),
                                    lastrc,
                            ),
                            importance = 1,
                            type = "error",
                            header = darkred(" !!! ")
                        )

                        if mypath not in self.critical_files:
                            self.Entropy.updateProgress(
                                "[%s|(%s/%s)] %s: %s, %s..." % (
                                    blue(crippled_uri),
                                    blue(str(counter)),
                                    bold(str(maxcount)),
                                    blue(_("not critical")),
                                    os.path.basename(mypath),
                                    blue(_("continuing")),
                                ),
                                importance = 1,
                                type = "warning",
                                header = brown(" @@ ")
                            )
                            continue

                        ftp.close()
                        errors = True
                        broken_uris.add((uri,lastrc))
                        # next mirror
                        break

                # close connection
                ftp.close()
                fine_uris.add(uri)

            return errors,fine_uris,broken_uris

    def _show_package_sets_messages(self, repo):
        self.Entropy.updateProgress(
            "[repo:%s] %s:" % (
                brown(repo),
                blue(_("configured package sets")),
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )
        sets_data = self.Entropy.package_set_list(matchRepo = repo)
        if not sets_data:
            self.Entropy.updateProgress(
                "%s" % (_("None configured"),),
                importance = 0,
                type = "info",
                header = brown("    # ")
            )
            return
        for s_repo, s_name, s_sets in sets_data:
            self.Entropy.updateProgress(
                blue("%s" % (s_name,)),
                importance = 0,
                type = "info",
                header = brown("    # ")
            )

    def _show_eapi3_upload_messages(self, crippled_uri, database_path, repo):
        self.Entropy.updateProgress(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("3"),
                blue(_("preparing uncompressed database for the upload")),
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("database path"),blue(database_path),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _show_eapi2_upload_messages(self, crippled_uri, database_path, upload_data, cmethod, repo):

        if repo == None:
            repo = self.Entropy.default_repository

        self.Entropy.updateProgress(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("2"),
                blue(_("creating compressed database dump + checksum")),
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("database path"),blue(database_path),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("dump"),blue(upload_data['dump_path']),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("dump checksum"),blue(upload_data['dump_path_digest']),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("opener"),blue(cmethod[0]),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _show_eapi1_upload_messages(self, crippled_uri, database_path, upload_data, cmethod, repo):

        self.Entropy.updateProgress(
            "[repo:%s|%s|%s:%s] %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        red("EAPI"),
                        bold("1"),
                        blue(_("compressing database + checksum")),
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * "),
            back = True
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("database path"),blue(database_path),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("compressed database path"),blue(upload_data['compressed_database_path']),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("compressed checksum"),blue(upload_data['compressed_database_path_digest']),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("opener"),blue(cmethod[0]),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _create_metafiles_file(self, compressed_dest_path, file_list, repo):
        found_file_list = [x for x in file_list if os.path.isfile(x) and \
            os.access(x,os.F_OK) and os.access(x,os.R_OK)]
        not_found_file_list = ["%s\n" % (os.path.basename(x),) for x in file_list if x not in found_file_list]
        metafile_not_found_file = self.Entropy.get_local_database_metafiles_not_found_file(repo)
        f = open(metafile_not_found_file,"w")
        f.writelines(not_found_file_list)
        f.flush()
        f.close()
        found_file_list.append(metafile_not_found_file)
        if os.path.isfile(compressed_dest_path):
            os.remove(compressed_dest_path)
        self.entropyTools.compress_files(compressed_dest_path, found_file_list)

    def create_mirror_directories(self, ftp_connection, path_to_create):
        bdir = ""
        for mydir in path_to_create.split("/"):
            bdir += "/"+mydir
            if not ftp_connection.is_file_available(bdir):
                try:
                    ftp_connection.mkdir(bdir)
                except Exception, e:
                    error = unicode(e)
                    if (error.find("550") == -1) and (error.find("File exist") == -1):
                        mytxt = "%s %s, %s: %s" % (
                            _("cannot create mirror directory"),
                            bdir,
                            _("error"),
                            e,
                        )
                        raise OnlineMirrorError("OnlineMirrorError:  %s" % (mytxt,))

    def mirror_lock_check(self, uri, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        gave_up = False
        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
        try:
            ftp = self.FtpInterface(uri, self.Entropy)
        except ConnectionError:
            self.entropyTools.printTraceback()
            return True # gave up
        my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
        ftp.set_cwd(my_path, dodir = True)

        lock_file = self.get_database_lockfile(repo)
        if not os.path.isfile(lock_file) and ftp.is_file_available(os.path.basename(lock_file)):
            self.Entropy.updateProgress(
                red("[repo:%s|%s|%s] %s, %s" % (
                    repo,
                    crippled_uri,
                    _("locking"),
                    _("mirror already locked"),
                    _("waiting up to 2 minutes before giving up"),
                )
                ),
                importance = 1,
                type = "warning",
                header = brown(" * "),
                back = True
            )
            unlocked = False
            count = 0
            while count < 120:
                count += 1
                time.sleep(1)
                if not ftp.is_file_available(os.path.basename(lock_file)):
                    self.Entropy.updateProgress(
                        red("[repo:%s|%s|%s] %s !" % (
                                repo,
                                crippled_uri,
                                _("locking"),
                                _("mirror unlocked"),
                            )
                        ),
                        importance = 1,
                        type = "info",
                        header = darkgreen(" * ")
                    )
                    unlocked = True
                    break
            if not unlocked:
                gave_up = True

        ftp.close()
        return gave_up

    def shrink_database_and_close(self, repo = None):
        dbconn = self.Entropy.openServerDatabase(read_only = False, no_upload = True, repo = repo, indexing = False)
        dbconn.dropAllIndexes()
        dbconn.vacuum()
        dbconn.vacuum()
        dbconn.commitChanges()
        self.Entropy.close_server_database(dbconn)

    def sync_database_treeupdates(self, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository
        dbconn = self.Entropy.openServerDatabase(read_only = False, no_upload = True, repo = repo)
        # grab treeupdates from other databases and inject
        server_repos = etpConst['server_repositories'].keys()
        all_actions = set()
        for myrepo in server_repos:

            # avoid __default__
            if myrepo == etpConst['clientserverrepoid']:
                continue

            mydbc = self.Entropy.openServerDatabase(just_reading = True, repo = myrepo)
            actions = mydbc.listAllTreeUpdatesActions(no_ids_repos = True)
            for data in actions:
                all_actions.add(data)
            if not actions:
                continue
        backed_up_entries = dbconn.listAllTreeUpdatesActions()
        try:
            # clear first
            dbconn.removeTreeUpdatesActions(repo)
            dbconn.insertTreeUpdatesActions(all_actions,repo)
        except Exception, e:
            self.entropyTools.printTraceback()
            mytxt = "%s, %s: %s. %s" % (
                _("Troubles with treeupdates"),
                _("error"),
                e,
                _("Bumping old data back"),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning"
            )
            # restore previous data
            dbconn.bumpTreeUpdatesActions(backed_up_entries)

        dbconn.commitChanges()
        self.Entropy.close_server_database(dbconn)

    def upload_database(self, uris, lock_check = False, pretend = False, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        # doing some tests
        import gzip
        myt = type(gzip)
        del myt
        import bz2
        myt = type(bz2)
        del myt

        if etpConst['rss-feed']:
            self.update_rss_feed(repo = repo)

        upload_errors = False
        broken_uris = set()
        fine_uris = set()

        for uri in uris:

            cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
            if cmethod == None:
                raise InvalidDataType("InvalidDataType: %s." % (
                        _("wrong database compression method passed"),
                    )
                )

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
            database_path = self.Entropy.get_local_database_file(repo)
            upload_data, critical, text_files = self.get_files_to_sync(cmethod, repo = repo)

            if lock_check:
                given_up = self.mirror_lock_check(uri, repo = repo)
                if given_up:
                    upload_errors = True
                    broken_uris.add(uri)
                    continue

            self.lock_mirrors_for_download(True, [uri], repo = repo)

            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s" % (
                    blue(repo),
                    red(crippled_uri),
                    darkgreen(_("upload")),
                    darkgreen(_("preparing to upload database to mirror")),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )

            # Package Sets info
            self._show_package_sets_messages(repo)

            self.sync_database_treeupdates(repo)
            self.Entropy.update_database_package_sets(repo)
            self.Entropy.close_server_databases()

            # backup current database to avoid re-indexing
            old_dbpath = self.Entropy.get_local_database_file(repo)
            backup_dbpath = old_dbpath+".up_backup"
            copy_back = False
            if not pretend:
                try:
                    if os.path.isfile(backup_dbpath):
                        os.remove(backup_dbpath)
                    shutil.copy2(old_dbpath,backup_dbpath)
                    copy_back = True
                except:
                    pass

            self.shrink_database_and_close(repo)

            # EAPI 3
            self._create_metafiles_file(upload_data['metafiles_path'], text_files, repo)
            self._show_eapi3_upload_messages(crippled_uri, database_path, repo)

            # EAPI 2
            self._show_eapi2_upload_messages(crippled_uri, database_path, upload_data, cmethod, repo)
            # create compressed dump + checksum
            self.dump_database_to_file(database_path, upload_data['dump_path'], eval(cmethod[0]), repo = repo)
            self.create_file_checksum(upload_data['dump_path'], upload_data['dump_path_digest'])

            # EAPI 1
            self._show_eapi1_upload_messages(crippled_uri, database_path, upload_data, cmethod, repo)
            # compress the database
            self.compress_file(database_path, upload_data['compressed_database_path'], eval(cmethod[0]))
            self.create_file_checksum(database_path, upload_data['compressed_database_path_digest'])

            if not pretend:
                # upload
                uploader = self.FileTransceiver(
                    self.FtpInterface,
                    self.Entropy,
                    [uri],
                    [upload_data[x] for x in upload_data],
                    critical_files = critical,
                    repo = repo
                )
                errors, m_fine_uris, m_broken_uris = uploader.go()
                if errors:
                    #my_fine_uris = sorted([self.entropyTools.extractFTPHostFromUri(x) for x in m_fine_uris])
                    my_broken_uris = sorted([(self.entropyTools.extractFTPHostFromUri(x[0]),x[1]) for x in m_broken_uris])
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|%s] %s" % (
                            repo,
                            crippled_uri,
                            _("errors"),
                            _("failed to upload to mirror, not unlocking and continuing"),
                        ),
                        importance = 0,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    # get reason
                    reason = my_broken_uris[0][1]
                    self.Entropy.updateProgress(
                        blue("%s: %s" % (_("reason"),reason,)),
                        importance = 0,
                        type = "error",
                        header = blue("    # ")
                    )
                    upload_errors = True
                    broken_uris |= m_broken_uris
                    continue

                # copy db back
                if copy_back and os.path.isfile(backup_dbpath):
                    self.Entropy.close_server_databases()
                    further_backup_dbpath = old_dbpath+".security_backup"
                    if os.path.isfile(further_backup_dbpath):
                        os.remove(further_backup_dbpath)
                    shutil.copy2(old_dbpath,further_backup_dbpath)
                    shutil.move(backup_dbpath,old_dbpath)

            # unlock
            self.lock_mirrors_for_download(False,[uri], repo = repo)
            fine_uris |= m_fine_uris

        if not fine_uris:
            upload_errors = True
        return upload_errors, broken_uris, fine_uris


    def download_database(self, uris, lock_check = False, pretend = False, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        # doing some tests
        import gzip
        myt = type(gzip)
        del myt
        import bz2
        myt = type(bz2)
        del myt

        download_errors = False
        broken_uris = set()
        fine_uris = set()

        for uri in uris:

            cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
            if cmethod == None:
                raise InvalidDataType("InvalidDataType: %s." % (
                        _("wrong database compression method passed"),
                    )
                )

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
            database_path = self.Entropy.get_local_database_file(repo)
            database_dir_path = os.path.dirname(self.Entropy.get_local_database_file(repo))
            download_data, critical, text_files = self.get_files_to_sync(cmethod, download = True, repo = repo)
            mytmpdir = self.entropyTools.getRandomTempFile()
            os.makedirs(mytmpdir)

            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    red(_("download")),
                    blue(_("preparing to download database from mirror")),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
            files_to_sync = sorted(download_data.keys())
            for myfile in files_to_sync:
                self.Entropy.updateProgress(
                    "%s: %s" % (blue(_("download path")),brown(unicode(download_data[myfile])),),
                    importance = 0,
                    type = "info",
                    header = brown("    # ")
                )

            if lock_check:
                given_up = self.mirror_lock_check(uri, repo = repo)
                if given_up:
                    download_errors = True
                    broken_uris.add(uri)
                    continue

            # avoid having others messing while we're downloading
            self.lock_mirrors(True,[uri], repo = repo)

            if not pretend:
                # download
                downloader = self.FileTransceiver(
                    self.FtpInterface, self.Entropy, [uri],
                    [download_data[x] for x in download_data], download = True,
                    local_basedir = mytmpdir, critical_files = critical, repo = repo
                )
                errors, m_fine_uris, m_broken_uris = downloader.go()
                if errors:
                    #my_fine_uris = sorted([self.entropyTools.extractFTPHostFromUri(x) for x in m_fine_uris])
                    my_broken_uris = sorted([(self.entropyTools.extractFTPHostFromUri(x[0]),x[1]) for x in m_broken_uris])
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|%s] %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            red(_("errors")),
                            blue(_("failed to download from mirror")),
                        ),
                        importance = 0,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    # get reason
                    reason = my_broken_uris[0][1]
                    self.Entropy.updateProgress(
                        blue("%s: %s" % (_("reason"),reason,)),
                        importance = 0,
                        type = "error",
                        header = blue("    # ")
                    )
                    download_errors = True
                    broken_uris |= m_broken_uris
                    self.lock_mirrors(False,[uri], repo = repo)
                    continue

                # all fine then, we need to move data from mytmpdir to database_dir_path

                # EAPI 1
                # unpack database
                compressed_db_filename = os.path.basename(download_data['compressed_database_path'])
                uncompressed_db_filename = os.path.basename(database_path)
                compressed_file = os.path.join(mytmpdir,compressed_db_filename)
                uncompressed_file = os.path.join(mytmpdir,uncompressed_db_filename)
                self.entropyTools.uncompress_file(compressed_file, uncompressed_file, eval(cmethod[0]))
                # now move
                for myfile in os.listdir(mytmpdir):
                    fromfile = os.path.join(mytmpdir,myfile)
                    tofile = os.path.join(database_dir_path,myfile)
                    shutil.move(fromfile,tofile)
                    self.Entropy.ClientService.setup_default_file_perms(tofile)

            if os.path.isdir(mytmpdir):
                shutil.rmtree(mytmpdir)
            if os.path.isdir(mytmpdir):
                os.rmdir(mytmpdir)


            fine_uris.add(uri)
            self.lock_mirrors(False,[uri], repo = repo)

        return download_errors, fine_uris, broken_uris

    def calculate_database_sync_queues(self, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        remote_status =  self.get_remote_databases_status(repo)
        local_revision = self.Entropy.get_local_database_revision(repo)
        upload_queue = []
        download_latest = ()

        # all mirrors are empty ? I rule
        if not [x for x in remote_status if x[1]]:
            upload_queue = remote_status[:]
        else:
            highest_remote_revision = max([x[1] for x in remote_status])

            if local_revision < highest_remote_revision:
                for x in remote_status:
                    if x[1] == highest_remote_revision:
                        download_latest = x
                        break

            if download_latest:
                upload_queue = [x for x in remote_status if (x[1] < highest_remote_revision)]
            else:
                upload_queue = [x for x in remote_status if (x[1] < local_revision)]

        return download_latest, upload_queue

    def sync_databases(self, no_upload = False, unlock_mirrors = False, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        while 1:

            db_locked = False
            if self.is_local_database_locked(repo):
                db_locked = True

            lock_data = self.get_mirrors_lock(repo)
            mirrors_locked = [x for x in lock_data if x[1]]

            if not mirrors_locked and db_locked:
                # mirrors not locked remotely but only locally
                mylock_file = self.get_database_lockfile(repo)
                if os.path.isfile(mylock_file) and os.access(mylock_file,os.W_OK):
                    os.remove(mylock_file)
                    continue

            break

        if mirrors_locked and not db_locked:
            mytxt = "%s, %s %s" % (
                _("At the moment, mirrors are locked, someone is working on their databases"),
                _("try again later"),
                "...",
            )
            raise OnlineMirrorError("OnlineMirrorError: %s" % (mytxt,))

        download_latest, upload_queue = self.calculate_database_sync_queues(repo)

        if not download_latest and not upload_queue:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s" % (
                    brown(repo),
                    red(_("sync")), # something short please
                    blue(_("database already in sync")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            return 0, set(), set()

        if download_latest:
            download_uri = download_latest[0]
            download_errors, fine_uris, broken_uris = self.download_database([download_uri], repo = repo)
            if download_errors:
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        red(_("sync")),
                        blue(_("database sync failed")),
                        red(_("download issues")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                return 1,fine_uris,broken_uris
            # XXX: reload revision settings?

        if upload_queue and not no_upload:

            deps_not_found = self.Entropy.dependencies_test()
            if deps_not_found and not self.Entropy.community_repo:
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        red(_("sync")),
                        blue(_("database sync forbidden")),
                        red(_("dependencies_test() reported errors")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                return 3,set(),set()

            problems = self.Entropy.check_config_file_updates()
            if problems:
                return 4,set(),set()

            self.Entropy.updateProgress(
                "[repo:%s|%s] %s" % (
                    brown(repo),
                    red(_("config files")), # something short please
                    blue(_("no configuration files to commit. All fine.")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True
            )
            #             for x in scandata:
            #    

            uris = [x[0] for x in upload_queue]
            errors, fine_uris, broken_uris = self.upload_database(uris, repo = repo)
            if errors:
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        red(_("sync")),
                        blue(_("database sync failed")),
                        red(_("upload issues")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                return 2,fine_uris,broken_uris


        self.Entropy.updateProgress(
            "[repo:%s|%s] %s" % (
                brown(repo),
                red(_("sync")),
                blue(_("database sync completed successfully")),
            ),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )

        if unlock_mirrors:
            self.lock_mirrors(False, repo = repo)
        return 0, set(), set()


    def calculate_local_upload_files(self, branch, repo = None):
        upload_files = 0
        upload_packages = set()
        upload_dir = os.path.join(self.Entropy.get_local_upload_directory(repo),branch)

        for package in os.listdir(upload_dir):
            if package.endswith(etpConst['packagesext']) or package.endswith(etpConst['packageshashfileext']):
                upload_packages.add(package)
                if package.endswith(etpConst['packagesext']):
                    upload_files += 1

        return upload_files, upload_packages

    def calculate_local_package_files(self, branch, repo = None):
        local_files = 0
        local_packages = set()
        packages_dir = os.path.join(self.Entropy.get_local_packages_directory(repo),branch)

        if not os.path.isdir(packages_dir):
            os.makedirs(packages_dir)

        for package in os.listdir(packages_dir):
            if package.endswith(etpConst['packagesext']) or package.endswith(etpConst['packageshashfileext']):
                local_packages.add(package)
                if package.endswith(etpConst['packagesext']):
                    local_files += 1

        return local_files, local_packages


    def _show_local_sync_stats(self, upload_files, local_files):
        self.Entropy.updateProgress(
            "%s:" % ( blue(_("Local statistics")),),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )
        self.Entropy.updateProgress(
            red("%s:\t\t%s %s" % (
                    blue(_("upload directory")),
                    bold(str(upload_files)),
                    red(_("files ready")),
                )
            ),
            importance = 0,
            type = "info",
            header = red(" @@ ")
        )
        self.Entropy.updateProgress(
            red("%s:\t\t%s %s" % (
                    blue(_("packages directory")),
                    bold(str(local_files)),
                    red(_("files ready")),
                )
            ),
            importance = 0,
            type = "info",
            header = red(" @@ ")
        )

    def _show_sync_queues(self, upload, download, removal, copy, metainfo, branch):

        # show stats
        for itemdata in upload:
            package = darkgreen(os.path.basename(itemdata[0]))
            size = blue(self.entropyTools.bytesIntoHuman(itemdata[1]))
            self.Entropy.updateProgress(
                "[branch:%s|%s] %s [%s]" % (
                    brown(branch),
                    blue(_("upload")),
                    darkgreen(package),
                    size,
                ),
                importance = 0,
                type = "info",
                header = red("    # ")
            )
        for itemdata in download:
            package = darkred(os.path.basename(itemdata[0]))
            size = blue(self.entropyTools.bytesIntoHuman(itemdata[1]))
            self.Entropy.updateProgress(
                "[branch:%s|%s] %s [%s]" % (
                    brown(branch),
                    darkred(_("download")),
                    blue(package),
                    size,
                ),
                importance = 0,
                type = "info",
                header = red("    # ")
            )
        for itemdata in copy:
            package = darkblue(os.path.basename(itemdata[0]))
            size = blue(self.entropyTools.bytesIntoHuman(itemdata[1]))
            self.Entropy.updateProgress(
                "[branch:%s|%s] %s [%s]" % (
                    brown(branch),
                    darkgreen(_("copy")),
                    brown(package),
                    size,
                ),
                importance = 0,
                type = "info",
                header = red("    # ")
            )
        for itemdata in removal:
            package = brown(os.path.basename(itemdata[0]))
            size = blue(self.entropyTools.bytesIntoHuman(itemdata[1]))
            self.Entropy.updateProgress(
                "[branch:%s|%s] %s [%s]" % (
                    brown(branch),
                    red(_("remove")),
                    red(package),
                    size,
                ),
                importance = 0,
                type = "info",
                header = red("    # ")
            )

        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                blue(_("Packages to be removed")),
                darkred(str(len(removal))),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )
        self.Entropy.updateProgress(
            "%s:\t\t%s" % (
                darkgreen(_("Packages to be moved locally")),
                darkgreen(str(len(copy))),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )
        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                bold(_("Packages to be uploaded")),
                bold(str(len(upload))),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )

        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                darkred(_("Total removal size")),
                darkred(self.entropyTools.bytesIntoHuman(metainfo['removal'])),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )

        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                blue(_("Total upload size")),
                blue(self.entropyTools.bytesIntoHuman(metainfo['upload'])),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )
        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                brown(_("Total download size")),
                brown(self.entropyTools.bytesIntoHuman(metainfo['download'])),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )


    def calculate_remote_package_files(self, uri, branch, ftp_connection = None, repo = None):

        remote_files = 0
        close_conn = False
        remote_packages_data = {}

        my_path = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),branch)
        if ftp_connection == None:
            close_conn = True
            # let it raise an exception if things go bad
            ftp_connection = self.FtpInterface(uri, self.Entropy)
        ftp_connection.set_cwd(my_path, dodir = True)

        remote_packages = ftp_connection.list_dir()
        remote_packages_info = ftp_connection.get_raw_list()
        if close_conn:
            ftp_connection.close()

        for tbz2 in remote_packages:
            if tbz2.endswith(etpConst['packagesext']):
                remote_files += 1

        for remote_package in remote_packages_info:
            remote_packages_data[remote_package.split()[8]] = int(remote_package.split()[4])

        return remote_files, remote_packages, remote_packages_data

    def calculate_packages_to_sync(self, uri, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
        upload_files, upload_packages = self.calculate_local_upload_files(branch, repo)
        local_files, local_packages = self.calculate_local_package_files(branch, repo)
        self._show_local_sync_stats(upload_files, local_files)

        self.Entropy.updateProgress(
            "%s: %s" % (blue(_("Remote statistics for")),red(crippled_uri),),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )
        remote_files, remote_packages, remote_packages_data = self.calculate_remote_package_files(
            uri,
            branch,
            repo = repo
        )
        self.Entropy.updateProgress(
            "%s:\t\t\t%s %s" % (
                blue(_("remote packages")),
                bold(str(remote_files)),
                red(_("files stored")),
            ),
            importance = 0,
            type = "info",
            header = red(" @@ ")
        )

        mytxt = blue("%s ...") % (_("Calculating queues"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        uploadQueue, downloadQueue, removalQueue, fineQueue = self.calculate_sync_queues(
                upload_packages,
                local_packages,
                remote_packages,
                remote_packages_data,
                branch,
                repo
        )
        return uploadQueue, downloadQueue, removalQueue, fineQueue, remote_packages_data

    def calculate_sync_queues(
            self,
            upload_packages,
            local_packages,
            remote_packages,
            remote_packages_data,
            branch,
            repo = None
        ):

        uploadQueue = set()
        downloadQueue = set()
        removalQueue = set()
        fineQueue = set()

        for local_package in upload_packages:
            if local_package in remote_packages:
                local_filepath = os.path.join(self.Entropy.get_local_upload_directory(repo),branch,local_package)
                local_size = self.entropyTools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(local_package)
                if remote_size == None:
                    remote_size = 0
                if (local_size != remote_size):
                    # size does not match, adding to the upload queue
                    uploadQueue.add(local_package)
                else:
                    fineQueue.add(local_package) # just move from upload to packages
            else:
                # always force upload of packages in uploaddir
                uploadQueue.add(local_package)

        # if a package is in the packages directory but not online, we have to upload it
        # we have local_packages and remotePackages
        for local_package in local_packages:
            if local_package in remote_packages:
                local_filepath = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,local_package)
                local_size = self.entropyTools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(local_package)
                if remote_size == None:
                    remote_size = 0
                if (local_size != remote_size) and (local_size != 0):
                    # size does not match, adding to the upload queue
                    if local_package not in fineQueue:
                        uploadQueue.add(local_package)
            else:
                # this means that the local package does not exist
                # so, we need to download it
                uploadQueue.add(local_package)

        # Fill downloadQueue and removalQueue
        for remote_package in remote_packages:
            if remote_package in local_packages:
                local_filepath = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,remote_package)
                local_size = self.entropyTools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(remote_package)
                if remote_size == None:
                    remote_size = 0
                if (local_size != remote_size) and (local_size != 0):
                    # size does not match, remove first
                    if remote_package not in uploadQueue: # do it only if the package has not been added to the uploadQueue
                        removalQueue.add(remote_package) # remotePackage == localPackage # just remove something that differs from the content of the mirror
                        # then add to the download queue
                        downloadQueue.add(remote_package)
            else:
                # this means that the local package does not exist
                # so, we need to download it
                if not remote_package.endswith(".tmp"): # ignore .tmp files
                    downloadQueue.add(remote_package)

        # Collect packages that don't exist anymore in the database
        # so we can filter them out from the download queue
        dbconn = self.Entropy.openServerDatabase(just_reading = True, repo = repo)
        db_files = dbconn.listBranchPackagesTbz2(branch, do_sort = False, full_path = True)
        db_files = set([os.path.basename(x) for x in db_files if (self.Entropy.get_branch_from_download_relative_uri(x) == branch)])

        exclude = set()
        for myfile in downloadQueue:
            if myfile.endswith(etpConst['packagesext']):
                if myfile not in db_files:
                    exclude.add(myfile)
        downloadQueue -= exclude

        exclude = set()
        for myfile in uploadQueue:
            if myfile.endswith(etpConst['packagesext']):
                if myfile not in db_files:
                    exclude.add(myfile)
        uploadQueue -= exclude

        exclude = set()
        for myfile in downloadQueue:
            if myfile in uploadQueue:
                exclude.add(myfile)
        downloadQueue -= exclude

        return uploadQueue, downloadQueue, removalQueue, fineQueue


    def expand_queues(self, uploadQueue, downloadQueue, removalQueue, remote_packages_data, branch, repo):

        metainfo = {
            'removal': 0,
            'download': 0,
            'upload': 0,
        }
        removal = []
        download = []
        do_copy = []
        upload = []

        for item in removalQueue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,item)
            size = self.entropyTools.get_file_size(local_filepath)
            metainfo['removal'] += size
            removal.append((local_filepath,size))

        for item in downloadQueue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(self.Entropy.get_local_upload_directory(repo),branch,item)
            if not os.path.isfile(local_filepath):
                size = remote_packages_data.get(item)
                if size == None:
                    size = 0
                size = int(size)
                metainfo['removal'] += size
                download.append((local_filepath,size))
            else:
                size = self.entropyTools.get_file_size(local_filepath)
                do_copy.append((local_filepath,size))

        for item in uploadQueue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(self.Entropy.get_local_upload_directory(repo),branch,item)
            local_filepath_pkgs = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,item)
            if os.path.isfile(local_filepath):
                size = self.entropyTools.get_file_size(local_filepath)
                upload.append((local_filepath,size))
            else:
                size = self.entropyTools.get_file_size(local_filepath_pkgs)
                upload.append((local_filepath_pkgs,size))
            metainfo['upload'] += size


        return upload, download, removal, do_copy, metainfo


    def _sync_run_removal_queue(self, removal_queue, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        for itemdata in removal_queue:

            remove_filename = itemdata[0]
            remove_filepath = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,remove_filename)
            remove_filepath_hash = remove_filepath+etpConst['packageshashfileext']
            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s: %s [%s]" % (
                        brown(repo),
                        red("sync"),
                        brown(branch),
                        blue(_("removing package+hash")),
                        darkgreen(remove_filename),
                        blue(self.entropyTools.bytesIntoHuman(itemdata[1])),
                ),
                importance = 0,
                type = "info",
                header = darkred(" * ")
            )

            if os.path.isfile(remove_filepath):
                os.remove(remove_filepath)
            if os.path.isfile(remove_filepath_hash):
                os.remove(remove_filepath_hash)

        self.Entropy.updateProgress(
            "[repo:%s|%s|%s] %s" % (
                    brown(repo),
                    red(_("sync")),
                    brown(branch),
                    blue(_("removal complete")),
            ),
            importance = 0,
            type = "info",
            header = darkred(" * ")
        )


    def _sync_run_copy_queue(self, copy_queue, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        for itemdata in copy_queue:

            from_file = itemdata[0]
            from_file_hash = from_file+etpConst['packageshashfileext']
            to_file = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,os.path.basename(from_file))
            to_file_hash = to_file+etpConst['packageshashfileext']
            expiration_file = to_file+etpConst['packagesexpirationfileext']
            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s: %s" % (
                        brown(repo),
                        red("sync"),
                        brown(branch),
                        blue(_("copying file+hash to repository")),
                        darkgreen(from_file),
                ),
                importance = 0,
                type = "info",
                header = darkred(" * ")
            )

            if not os.path.isdir(os.path.dirname(to_file)):
                os.makedirs(os.path.dirname(to_file))

            shutil.copy2(from_file,to_file)
            if not os.path.isfile(from_file_hash):
                self.create_file_checksum(from_file, from_file_hash)
            shutil.copy2(from_file_hash,to_file_hash)

            # clear expiration file
            if os.path.isfile(expiration_file):
                os.remove(expiration_file)


    def _sync_run_upload_queue(self, uri, upload_queue, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
        myqueue = []
        for itemdata in upload_queue:
            x = itemdata[0]
            hash_file = x+etpConst['packageshashfileext']
            if not os.path.isfile(hash_file):
                self.entropyTools.createHashFile(x)
            myqueue.append(hash_file)
            myqueue.append(x)

        ftp_basedir = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),branch)
        uploader = self.FileTransceiver(    self.FtpInterface,
                                            self.Entropy,
                                            [uri],
                                            myqueue,
                                            critical_files = myqueue,
                                            use_handlers = True,
                                            ftp_basedir = ftp_basedir,
                                            handlers_data = {'branch': branch },
                                            repo = repo
                                        )
        errors, m_fine_uris, m_broken_uris = uploader.go()
        if errors:
            my_broken_uris = [(self.entropyTools.extractFTPHostFromUri(x[0]),x[1]) for x in m_broken_uris]
            reason = my_broken_uris[0][1]
            self.Entropy.updateProgress(
                "[branch:%s] %s: %s, %s: %s" % (
                            brown(branch),
                            blue(_("upload errors")),
                            red(crippled_uri),
                            blue(_("reason")),
                            darkgreen(unicode(reason)),
                ),
                importance = 1,
                type = "error",
                header = darkred(" !!! ")
            )
            return errors, m_fine_uris, m_broken_uris

        self.Entropy.updateProgress(
            "[branch:%s] %s: %s" % (
                        brown(branch),
                        blue(_("upload completed successfully")),
                        red(crippled_uri),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )
        return errors, m_fine_uris, m_broken_uris


    def _sync_run_download_queue(self, uri, download_queue, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
        myqueue = []
        for itemdata in download_queue:
            x = itemdata[0]
            hash_file = x+etpConst['packageshashfileext']
            myqueue.append(x)
            myqueue.append(hash_file)

        ftp_basedir = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),branch)
        local_basedir = os.path.join(self.Entropy.get_local_packages_directory(repo),branch)
        downloader = self.FileTransceiver(
            self.FtpInterface,
            self.Entropy,
            [uri],
            myqueue,
            critical_files = myqueue,
            use_handlers = True,
            ftp_basedir = ftp_basedir,
            local_basedir = local_basedir,
            handlers_data = {'branch': branch },
            download = True,
            repo = repo
        )
        errors, m_fine_uris, m_broken_uris = downloader.go()
        if errors:
            my_broken_uris = [(self.entropyTools.extractFTPHostFromUri(x[0]),x[1]) for x in m_broken_uris]
            reason = my_broken_uris[0][1]
            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s: %s, %s: %s" % (
                    brown(repo),
                    red(_("sync")),
                    brown(branch),
                    blue(_("download errors")),
                    darkgreen(crippled_uri),
                    blue(_("reason")),
                    reason,
                ),
                importance = 1,
                type = "error",
                header = darkred(" !!! ")
            )
            return errors, m_fine_uris, m_broken_uris

        self.Entropy.updateProgress(
            "[repo:%s|%s|%s] %s: %s" % (
                brown(repo),
                red(_("sync")),
                brown(branch),
                blue(_("download completed successfully")),
                darkgreen(crippled_uri),
            ),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )
        return errors, m_fine_uris, m_broken_uris


    def sync_packages(self, ask = True, pretend = False, packages_check = False, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        self.Entropy.updateProgress(
            "[repo:%s|%s] %s" % (
                repo,
                red(_("sync")),
                darkgreen(_("starting packages sync")),
            ),
            importance = 1,
            type = "info",
            header = red(" @@ "),
            back = True
        )

        successfull_mirrors = set()
        broken_mirrors = set()
        check_data = ()
        mirrors_tainted = False
        mirror_errors = False
        mirrors_errors = False

        for uri in self.Entropy.get_remote_mirrors(repo):

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
            mirror_errors = False

            self.Entropy.updateProgress(
                "[repo:%s|%s|branch:%s] %s: %s" % (
                    repo,
                    red(_("sync")),
                    brown(etpConst['branch']),
                    blue(_("packages sync")),
                    bold(crippled_uri),
                ),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )

            try:
                uploadQueue, downloadQueue, removalQueue, fineQueue, remote_packages_data = self.calculate_packages_to_sync(uri, etpConst['branch'], repo)
                del fineQueue
            except self.socket.error, e:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s, %s %s" % (
                        repo,
                        red(_("sync")),
                        etpConst['branch'],
                        darkred(_("socket error")),
                        e,
                        darkred(_("on")),
                        crippled_uri,
                    ),
                    importance = 1,
                    type = "error",
                    header = darkgreen(" * ")
                )
                continue

            if (not uploadQueue) and (not downloadQueue) and (not removalQueue):
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s" % (
                        repo,
                        red(_("sync")),
                        etpConst['branch'],
                        darkgreen(_("nothing to do on")),
                        crippled_uri,
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                successfull_mirrors.add(uri)
                continue

            self.Entropy.updateProgress(
                "%s:" % (blue(_("Expanding queues")),),
                importance = 1,
                type = "info",
                header = red(" ** ")
            )

            upload, download, removal, copy, metainfo = self.expand_queues(
                        uploadQueue,
                        downloadQueue,
                        removalQueue,
                        remote_packages_data,
                        etpConst['branch'],
                        repo
            )
            del uploadQueue, downloadQueue, removalQueue, remote_packages_data
            self._show_sync_queues(upload, download, removal, copy, metainfo, etpConst['branch'])

            if not len(upload)+len(download)+len(removal)+len(copy):

                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s %s" % (
                        self.Entropy.default_repository,
                        red(_("sync")),
                        etpConst['branch'],
                        blue(_("nothing to sync for")),
                        crippled_uri,
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" @@ ")
                )

                successfull_mirrors.add(uri)
                continue

            if pretend:
                successfull_mirrors.add(uri)
                continue

            if ask:
                rc = self.Entropy.askQuestion(_("Would you like to run the steps above ?"))
                if rc == "No":
                    continue

            try:

                if removal:
                    self._sync_run_removal_queue(removal, etpConst['branch'], repo)
                if copy:
                    self._sync_run_copy_queue(copy, etpConst['branch'], repo)
                if upload or download:
                    mirrors_tainted = True
                if upload:
                    d_errors, m_fine_uris, m_broken_uris = self._sync_run_upload_queue(uri, upload, etpConst['branch'], repo)
                    if d_errors: mirror_errors = True
                if download:
                    d_errors, m_fine_uris, m_broken_uris = self._sync_run_download_queue(uri, download, etpConst['branch'], repo)
                    if d_errors: mirror_errors = True
                if not mirror_errors:
                    successfull_mirrors.add(uri)
                else:
                    mirrors_errors = True

            except KeyboardInterrupt:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s" % (
                        repo,
                        red(_("sync")),
                        etpConst['branch'],
                        darkgreen(_("keyboard interrupt !")),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                continue

            except Exception, e:

                self.entropyTools.printTraceback()
                mirrors_errors = True
                broken_mirrors.add(uri)
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s, %s: %s" % (
                        repo,
                        red(_("sync")),
                        etpConst['branch'],
                        darkred(_("exception caught")),
                        Exception,
                        _("error"),
                        e,
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )

                exc_txt = self.Entropy.entropyTools.printException(returndata = True)
                for line in exc_txt:
                    self.Entropy.updateProgress(
                        unicode(line),
                        importance = 1,
                        type = "error",
                        header = darkred(":  ")
                    )

                if len(successfull_mirrors) > 0:
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|branch:%s] %s" % (
                            repo,
                            red(_("sync")),
                            etpConst['branch'],
                            darkred(_("at least one mirror has been sync'd properly, hooray!")),
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                continue

        # if at least one server has been synced successfully, move files
        if (len(successfull_mirrors) > 0) and not pretend:
            self.remove_expiration_files(etpConst['branch'], repo)

        if packages_check:
            check_data = self.Entropy.verify_local_packages([], ask = ask, repo = repo)

        return mirrors_tainted, mirrors_errors, successfull_mirrors, broken_mirrors, check_data

    def remove_expiration_files(self, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        branch_dir = os.path.join(self.Entropy.get_local_upload_directory(repo),branch)
        branchcontent = os.listdir(branch_dir)
        for xfile in branchcontent:
            source = os.path.join(self.Entropy.get_local_upload_directory(repo),branch,xfile)
            destdir = os.path.join(self.Entropy.get_local_packages_directory(repo),branch)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)
            dest = os.path.join(destdir,xfile)
            shutil.move(source,dest)
            # clear expiration file
            dest_expiration = dest+etpConst['packagesexpirationfileext']
            if os.path.isfile(dest_expiration):
                os.remove(dest_expiration)


    def is_package_expired(self, package_file, branch, repo = None):
        pkg_path = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,package_file)
        pkg_path += etpConst['packagesexpirationfileext']
        if not os.path.isfile(pkg_path):
            return False
        mtime = self.entropyTools.getFileUnixMtime(pkg_path)
        delta = int(etpConst['packagesexpirationdays'])*24*3600
        currmtime = time.time()
        file_delta = currmtime - mtime
        if file_delta > delta:
            return True
        return False

    def create_expiration_file(self, package_file, branch, repo = None, gentle = False):
        pkg_path = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,package_file)
        pkg_path += etpConst['packagesexpirationfileext']
        if gentle and os.path.isfile(pkg_path):
            return
        f = open(pkg_path,"w")
        f.flush()
        f.close()


    def collect_expiring_packages(self, branch, repo = None):
        dbconn = self.Entropy.openServerDatabase(just_reading = True, repo = repo)
        database_bins = dbconn.listBranchPackagesTbz2(branch, do_sort = False, full_path = True)
        bins_dir = os.path.join(self.Entropy.get_local_packages_directory(repo),branch)
        repo_bins = set()
        if os.path.isdir(bins_dir):
            repo_bins = os.listdir(bins_dir)
            repo_bins = set([os.path.join('packages',etpSys['arch'],branch,x) for x in repo_bins if x.endswith(etpConst['packagesext'])])
        repo_bins -= database_bins
        return set([os.path.basename(x) for x in repo_bins])


    def tidy_mirrors(self, ask = True, pretend = False, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        self.Entropy.updateProgress(
            "[repo:%s|%s|branch:%s] %s" % (
                brown(repo),
                red(_("tidy")),
                blue(etpConst['branch']),
                blue(_("collecting expired packages")),
            ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        branch_data = {}
        errors = False

        branch_data['errors'] = False

        if etpConst['branch'] != etpConst['branches'][-1]:
            self.Entropy.updateProgress(
                "[branch:%s] %s" % (
                    brown(etpConst['branch']),
                    blue(_("not the latest branch, skipping tidy for consistence. This branch entered the maintenance mode.")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            branch_data['errors'] = True
            return True, branch_data

        self.Entropy.updateProgress(
            "[branch:%s] %s" % (
                brown(etpConst['branch']),
                blue(_("collecting expired packages in the selected branches")),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )

        # collect removed packages
        expiring_packages = self.collect_expiring_packages(etpConst['branch'], repo)

        removal = []
        for package in expiring_packages:
            expired = self.is_package_expired(package, etpConst['branch'], repo)
            if expired:
                removal.append(package)
            else:
                self.create_expiration_file(package, etpConst['branch'], repo, gentle = True)

        # fill returning data
        branch_data['removal'] = removal[:]

        if not removal:
            self.Entropy.updateProgress(
                "[branch:%s] %s" % (
                        brown(etpConst['branch']),
                        blue(_("nothing to remove on this branch")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            return errors, branch_data
        else:
            self.Entropy.updateProgress(
                "[branch:%s] %s:" % (
                    brown(etpConst['branch']),
                    blue(_("these are the expired packages")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            for package in removal:
                self.Entropy.updateProgress(
                    "[branch:%s] %s: %s" % (
                                brown(etpConst['branch']),
                                blue(_("remove")),
                                darkgreen(package),
                        ),
                    importance = 1,
                    type = "info",
                    header = brown("    # ")
                )

        if pretend:
            return errors,branch_data

        if ask:
            rc = self.Entropy.askQuestion(_("Would you like to continue ?"))
            if rc == "No":
                return errors, branch_data

        myqueue = []
        for package in removal:
            myqueue.append(package+etpConst['packageshashfileext'])
            myqueue.append(package)
        ftp_basedir = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),etpConst['branch'])
        for uri in self.Entropy.get_remote_mirrors(repo):

            self.Entropy.updateProgress(
                "[branch:%s] %s..." % (
                    brown(etpConst['branch']),
                    blue(_("removing packages remotely")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
            destroyer = self.FileTransceiver(
                self.FtpInterface,
                self.Entropy,
                [uri],
                myqueue,
                critical_files = [],
                ftp_basedir = ftp_basedir,
                remove = True,
                repo = repo
            )
            errors, m_fine_uris, m_broken_uris = destroyer.go()
            if errors:
                my_broken_uris = [(self.entropyTools.extractFTPHostFromUri(x[0]),x[1]) for x in m_broken_uris]
                reason = my_broken_uris[0][1]
                self.Entropy.updateProgress(
                    "[branch:%s] %s: %s, %s: %s" % (
                        brown(etpConst['branch']),
                        blue(_("remove errors")),
                        red(crippled_uri),
                        blue(_("reason")),
                        reason,
                    ),
                    importance = 1,
                    type = "warning",
                    header = brown(" !!! ")
                )
                branch_data['errors'] = True
                errors = True

            self.Entropy.updateProgress(
                "[branch:%s] %s..." % (
                        brown(etpConst['branch']),
                        blue(_("removing packages locally")),
                    ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )

            branch_data['removed'] = set()
            for package in removal:
                package_path = os.path.join(self.Entropy.get_local_packages_directory(repo),etpConst['branch'],package)
                package_path_hash = package_path+etpConst['packageshashfileext']
                package_path_expired = package_path+etpConst['packagesexpirationfileext']
                for myfile in [package_path_hash,package_path,package_path_expired]:
                    if os.path.isfile(myfile):
                        self.Entropy.updateProgress(
                            "[branch:%s] %s: %s" % (
                                        brown(etpConst['branch']),
                                        blue(_("removing")),
                                        darkgreen(myfile),
                                ),
                            importance = 1,
                            type = "info",
                            header = brown(" @@ ")
                        )
                        os.remove(myfile)
                        branch_data['removed'].add(myfile)


        return errors, branch_data
