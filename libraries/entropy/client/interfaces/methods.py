# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Miscellaneous functions Interface}.

"""
import os
import bz2
import stat
import fcntl
import errno
import sys
import shutil
import time
import subprocess
import tempfile
from datetime import datetime

from entropy.i18n import _
from entropy.const import etpConst, const_debug_write, etpSys, \
    const_setup_file, initconfig_entropy_constants, const_pid_exists, \
    const_set_nice_level, const_setup_perms, const_setup_entropy_pid, \
    const_isstring, const_convert_to_unicode
from entropy.exceptions import RepositoryError, InvalidPackageSet,\
    SystemDatabaseError
from entropy.db import EntropyRepository
from entropy.cache import EntropyCacher
from entropy.client.interfaces.db import ClientEntropyRepositoryPlugin
from entropy.client.mirrors import StatusInterface
from entropy.output import purple, bold, red, blue, darkgreen, darkred, brown

from entropy.db.exceptions import IntegrityError, OperationalError, \
    DatabaseError

import entropy.tools

class RepositoryMixin:

    def _validate_repositories(self, quiet = False):

        StatusInterface().clear()
        self._repo_error_messages_cache.clear()

        # clear live masking validation cache, if exists
        cl_id = self.sys_settings_client_plugin_id
        client_metadata = self._settings.get(cl_id, {})
        if "masking_validation" in client_metadata:
            client_metadata['masking_validation']['cache'].clear()

        # valid repositories
        del self._enabled_repos[:]
        for repoid in self._settings['repositories']['order']:
            # open database
            try:

                dbc = self.open_repository(repoid)
                dbc.listConfigProtectEntries()
                dbc.validateDatabase()
                self._enabled_repos.append(repoid)

            except RepositoryError:

                if quiet:
                    continue

                t = _("Repository") + " " + const_convert_to_unicode(repoid) \
                    + " " + _("is not available") + ". " + _("Cannot validate")
                t2 = _("Please update your repositories now in order to remove this message!")
                self.output(
                    darkred(t),
                    importance = 1,
                    level = "warning"
                )
                self.output(
                    purple(t2),
                    header = bold("!!! "),
                    importance = 1,
                    level = "warning"
                )
                continue # repo not available
            except (OperationalError, DatabaseError, SystemDatabaseError,):

                if quiet:
                    continue

                t = _("Repository") + " " + repoid + " " + \
                    _("is corrupted") + ". " + _("Cannot validate")
                self.output(
                                    darkred(t),
                                    importance = 1,
                                    level = "warning"
                                   )
                continue

        # to avoid having zillions of open files when loading a lot of EquoInterfaces
        self.close_repositories(mask_clear = False)

    def __get_repository_cache_key(self, repoid):
        return (repoid, etpConst['systemroot'],)

    def _init_generic_temp_repository(self, repoid, description,
        package_mirrors = None, temp_file = None):
        if package_mirrors is None:
            package_mirrors = []

        dbc = self.open_temp_repository(dbname = repoid, temp_file = temp_file)
        repo_key = self.__get_repository_cache_key(repoid)
        self._memory_db_instances[repo_key] = dbc

        # add to self._settings['repositories']['available']
        repodata = {
            'repoid': repoid,
            '__temporary__': True,
            'description': description,
            'packages': package_mirrors,
            'dbpath': dbc.dbFile,
        }
        self.add_repository(repodata)
        return dbc

    def close_repositories(self, mask_clear = True):
        for item in sorted(self._repodb_cache.keys()):
            # in-memory repositories cannot be closed
            # otherwise everything will be lost, to
            # effectively close these repos you
            # must call remove_repository method
            if item in self._memory_db_instances:
                continue
            try:
                self._repodb_cache.pop(item).closeDB()
            except OperationalError as err: # wtf!
                sys.stderr.write("!!! Cannot close Entropy repos: %s\n" % (
                    err,))
        self._repodb_cache.clear()

        # disable hooks during SystemSettings cleanup
        # otherwise it makes entropy.client.interfaces.repository crazy
        old_value = self._can_run_sys_set_hooks
        self._can_run_sys_set_hooks = False
        if mask_clear:
            self._settings.clear()
        self._can_run_sys_set_hooks = old_value

    def open_repository(self, repoid):

        # support for installed pkgs repository, got by issuing
        # repoid = etpConst['clientdbid']
        if repoid == etpConst['clientdbid']:
            return self._installed_repository

        key = self.__get_repository_cache_key(repoid)
        if key not in self._repodb_cache:
            dbconn = self._load_repository_database(repoid,
                xcache = self.xcache, indexing = self.indexing)
            try:
                dbconn.checkDatabaseApi()
            except (OperationalError, TypeError,):
                pass

            self._repodb_cache[key] = dbconn
            return dbconn

        return self._repodb_cache.get(key)

    def _load_repository_database(self, repoid, xcache = True, indexing = True):

        if const_isstring(repoid):
            if repoid.endswith(etpConst['packagesext']):
                xcache = False

        repo_data = self._settings['repositories']['available']
        if repoid not in repo_data:
            t = "%s: %s" % (_("bad repository id specified"), repoid,)
            if repoid not in self._repo_error_messages_cache:
                self.output(
                    darkred(t),
                    importance = 2,
                    level = "warning"
                )
                self._repo_error_messages_cache.add(repoid)
            raise RepositoryError("RepositoryError: %s" % (t,))

        if repo_data[repoid].get('__temporary__'):
            repo_key = self.__get_repository_cache_key(repoid)
            conn = self._memory_db_instances.get(repo_key)
        else:
            dbfile = os.path.join(repo_data[repoid]['dbpath'],
                etpConst['etpdatabasefile'])
            if not os.path.isfile(dbfile):
                t = _("Repository %s hasn't been downloaded yet.") % (repoid,)
                if repoid not in self._repo_error_messages_cache:
                    self.output(
                        darkred(t),
                        importance = 2,
                        level = "warning"
                    )
                    self._repo_error_messages_cache.add(repoid)
                raise RepositoryError("RepositoryError: %s" % (t,))

            conn = EntropyRepository(
                readOnly = True,
                dbFile = dbfile,
                dbname = etpConst['dbnamerepoprefix']+repoid,
                xcache = xcache,
                indexing = indexing
            )
            self._add_plugin_to_client_repository(conn, repoid)

        if (repoid not in self._treeupdates_repos) and \
            (entropy.tools.is_root()) and \
            (not repoid.endswith(etpConst['packagesext'])):
                # only as root due to Portage
                try:
                    updated = self.repository_packages_spm_sync(repoid, conn)
                except (OperationalError, DatabaseError,):
                    updated = False
                if updated:
                    self._cacher.discard()
                    EntropyCacher.clear_cache_item(
                        EntropyCacher.CACHE_IDS['world_update'])
                    EntropyCacher.clear_cache_item(
                        EntropyCacher.CACHE_IDS['critical_update'])
        return conn

    def get_repository_revision(self, reponame):

        db_data = self._settings['repositories']['available'][reponame]
        fname = os.path.join(db_data['dbpath'],
            etpConst['etpdatabaserevisionfile'])
        revision = -1

        if os.path.isfile(fname) and os.access(fname, os.R_OK):
            with open(fname, "r") as f:
                try:
                    revision = int(f.readline().strip())
                except (OSError, IOError, ValueError,):
                    pass

        return revision

    def add_repository(self, repodata):

        product = self._settings['repositories']['product']
        branch = self._settings['repositories']['branch']
        avail_data = self._settings['repositories']['available']
        repoid = repodata['repoid']

        avail_data[repoid] = {}
        avail_data[repoid]['description'] = repodata['description']

        if repoid.endswith(etpConst['packagesext']) or \
            repodata.get('__temporary__'):
            # dynamic repository

            # no need # avail_data[repoid]['plain_packages'] = \
            # repodata['plain_packages'][:]
            avail_data[repoid]['packages'] = repodata['packages'][:]
            smart_package = repodata.get('smartpackage')
            if smart_package != None:
                avail_data[repoid]['smartpackage'] = smart_package

            avail_data[repoid]['dbpath'] = repodata.get('dbpath')
            avail_data[repoid]['pkgpath'] = repodata.get('pkgpath')
            avail_data[repoid]['__temporary__'] = repodata.get('__temporary__')
            # put at top priority, shift others
            self._settings['repositories']['order'].insert(0, repoid)

        else:

            self.__save_repository_settings(repodata)
            self._settings._clear_repository_cache(repoid = repoid)
            self.close_repositories()
            self.clear_cache()
            self._settings.clear()

        self._validate_repositories()

    def remove_repository(self, repoid, disable = False):

        done = False
        if repoid in self._settings['repositories']['available']:
            del self._settings['repositories']['available'][repoid]
            done = True

        if repoid in self._settings['repositories']['excluded']:
            del self._settings['repositories']['excluded'][repoid]
            done = True

        # also early remove from validRepositories to avoid
        # issues when reloading SystemSettings which is bound to Entropy Client
        # SystemSettings plugin, which triggers calculate_world_updates, which
        # triggers _all_repositories_checksum, which triggers open_repository,
        # which triggers _load_repository_database, which triggers an unwanted
        # output message => "bad repository id specified"
        if repoid in self._enabled_repos:
            self._enabled_repos.remove(repoid)

        # ensure that all dbs are closed
        self.close_repositories()

        if done:

            if repoid in self._settings['repositories']['order']:
                self._settings['repositories']['order'].remove(repoid)

            self._settings._clear_repository_cache(repoid = repoid)
            # save new self._settings['repositories']['available'] to file
            repodata = {}
            repodata['repoid'] = repoid
            if disable:
                self.__save_repository_settings(repodata, disable = True)
            else:
                self.__save_repository_settings(repodata, remove = True)
            self._settings.clear()

        repo_mem_key = self.__get_repository_cache_key(repoid)
        mem_inst = self._memory_db_instances.pop(repo_mem_key, None)
        if isinstance(mem_inst, EntropyRepository):
            mem_inst.closeDB()

        # reset db cache
        self.close_repositories()
        self._validate_repositories()

    def __save_repository_settings(self, repodata, remove = False,
        disable = False, enable = False):

        if repodata['repoid'].endswith(etpConst['packagesext']):
            return

        content = []
        if os.path.isfile(etpConst['repositoriesconf']):
            f = open(etpConst['repositoriesconf'])
            content = [x.strip() for x in f.readlines()]
            f.close()

        if not disable and not enable:
            content = [x for x in content if not \
                x.startswith("repository|"+repodata['repoid'])]
            if remove:
                # also remove possible disable repo
                content = [x for x in content if not (x.startswith("#") and \
                    not x.startswith("##") and \
                        (x.find("repository|"+repodata['repoid']) != -1))]
        if not remove:

            repolines = [x for x in content if x.startswith("repository|") or \
                (x.startswith("#") and not x.startswith("##") and \
                    (x.find("repository|") != -1))]
            # exclude lines from repolines
            content = [x for x in content if x not in repolines]
            # filter sane repolines lines
            repolines = [x for x in repolines if (len(x.split("|")) == 5)]
            repolines_data = {}
            repocount = 0
            for x in repolines:
                repolines_data[repocount] = {}
                repolines_data[repocount]['repoid'] = x.split("|")[1]
                repolines_data[repocount]['line'] = x
                if disable and x.split("|")[1] == repodata['repoid']:
                    if not x.startswith("#"):
                        x = "#"+x
                    repolines_data[repocount]['line'] = x
                elif enable and x.split("|")[1] == repodata['repoid'] \
                    and x.startswith("#"):
                    repolines_data[repocount]['line'] = x[1:]
                repocount += 1

            if not disable and not enable: # so it's a add

                line = "repository|%s|%s|%s|%s#%s#%s,%s" % (
                    repodata['repoid'],
                    repodata['description'],
                    ' '.join(repodata['plain_packages']),
                    repodata['plain_database'],
                    repodata['dbcformat'],
                    repodata['service_port'],
                    repodata['ssl_service_port'],
                )

                # seek in repolines_data for a disabled entry and remove
                to_remove = set()
                for cc in repolines_data:
                    cc_line = repolines_data[cc]['line']
                    if cc_line.startswith("#") and \
                        (cc_line.find("repository|"+repodata['repoid']) != -1):
                        # then remove
                        to_remove.add(cc)
                for x in to_remove:
                    del repolines_data[x]

                repolines_data[repocount] = {}
                repolines_data[repocount]['repoid'] = repodata['repoid']
                repolines_data[repocount]['line'] = line

            # inject new repodata
            keys = sorted(repolines_data.keys())
            for cc in keys:
                #repoid = repolines_data[cc]['repoid']
                # write the first
                line = repolines_data[cc]['line']
                content.append(line)

        try:
            repo_conf = etpConst['repositoriesconf']
            tmp_repo_conf = repo_conf + ".cfg_save_set"
            with open(tmp_repo_conf, "w") as tmp_f:
                for line in content:
                    tmp_f.write(line + "\n")
                tmp_f.flush()
            os.rename(tmp_repo_conf, repo_conf)
        except (OSError, IOError,): # permission denied?
            return False
        return True


    def __write_ordered_repositories_entries(self, ordered_repository_list):
        content = []
        if os.path.isfile(etpConst['repositoriesconf']):
            f = open(etpConst['repositoriesconf'])
            content = [x.strip() for x in f.readlines()]
            f.close()

        repolines = [x for x in content if x.startswith("repository|") and \
            (len(x.split("|")) == 5)]
        content = [x for x in content if x not in repolines]
        for repoid in ordered_repository_list:
            # get repoid from repolines
            for x in repolines:
                repoidline = x.split("|")[1]
                if repoid == repoidline:
                    content.append(x)

        repo_conf = etpConst['repositoriesconf']
        tmp_repo_conf = repo_conf + ".cfg_save"
        with open(tmp_repo_conf, "w") as tmp_f:
            for line in content:
                tmp_f.write(line + "\n")
            tmp_f.flush()
        os.rename(tmp_repo_conf, repo_conf)

    def shift_repository(self, repoid, toidx):
        # update self._settings['repositories']['order']
        self._settings['repositories']['order'].remove(repoid)
        self._settings['repositories']['order'].insert(toidx, repoid)
        self.__write_ordered_repositories_entries(
            self._settings['repositories']['order'])
        self._settings.clear()
        self.close_repositories()
        self._settings._clear_repository_cache(repoid = repoid)
        self._validate_repositories()

    def enable_repository(self, repoid):
        self._settings._clear_repository_cache(repoid = repoid)
        # save new self._settings['repositories']['available'] to file
        repodata = {}
        repodata['repoid'] = repoid
        self.__save_repository_settings(repodata, enable = True)
        self._settings.clear()
        self.close_repositories()
        self._validate_repositories()

    def disable_repository(self, repoid):
        # update self._settings['repositories']['available']
        done = False
        try:
            del self._settings['repositories']['available'][repoid]
            done = True
        except:
            pass

        if done:
            try:
                self._settings['repositories']['order'].remove(repoid)
            except (IndexError,):
                pass
            # it's not vital to reset
            # self._settings['repositories']['order'] counters

            self._settings._clear_repository_cache(repoid = repoid)
            # save new self._settings['repositories']['available'] to file
            repodata = {}
            repodata['repoid'] = repoid
            self.__save_repository_settings(repodata, disable = True)
            self._settings.clear()

        self.close_repositories()
        self._validate_repositories()

    # every tbz2 file that would be installed must pass from here
    def add_package_to_repositories(self, pkg_file):

        atoms_contained = []
        basefile = os.path.basename(pkg_file)
        db_dir = tempfile.mkdtemp()
        dbfile = os.path.join(db_dir, etpConst['etpdatabasefile'])
        dump_rc = entropy.tools.dump_entropy_metadata(pkg_file, dbfile)
        if not dump_rc:
            return -1, atoms_contained
        # add dbfile
        repodata = {}
        repodata['repoid'] = basefile
        repodata['description'] = "Dynamic database from " + basefile
        repodata['packages'] = []
        repodata['dbpath'] = os.path.dirname(dbfile)
        repodata['pkgpath'] = os.path.realpath(pkg_file) # extra info added
        repodata['smartpackage'] = False # extra info added

        mydbconn = self.open_generic_repository(dbfile)
        # read all idpackages
        try:
            # all branches admitted from external files
            myidpackages = mydbconn.listAllIdpackages()
        except (AttributeError, DatabaseError, IntegrityError,
            OperationalError,):
            return -2, atoms_contained

        if len(myidpackages) > 1:
            repodata[basefile]['smartpackage'] = True
        for myidpackage in myidpackages:
            compiled_arch = mydbconn.retrieveDownloadURL(myidpackage)
            if compiled_arch.find("/"+etpConst['currentarch']+"/") == -1:
                return -3, atoms_contained
            atoms_contained.append((int(myidpackage), basefile))

        self.add_repository(repodata)
        self._validate_repositories()
        if basefile not in self._enabled_repos:
            self.remove_repository(basefile)
            return -4, atoms_contained
        mydbconn.closeDB()
        del mydbconn
        return 0, atoms_contained

    def _add_plugin_to_client_repository(self, entropy_client_repository,
        repo_id):
        etp_db_meta = {
            'output_interface': self,
            'repo_name': repo_id,
        }
        repo_plugin = ClientEntropyRepositoryPlugin(self,
            metadata = etp_db_meta)
        entropy_client_repository.add_plugin(repo_plugin)

    def repositories(self):
        """
        Return a list of enabled (and valid) repository identifiers, excluding
        installed packages repository. You can use the identifiers in this list
        to open EntropyRepository instances using Client.open_repository()
        NOTE: this method directly returns a reference to the internal
        enabled repository list object.
        NOTE: the returned list is built based on SystemSettings repository
        metadata but might differ because extra checks are done at runtime.
        So, if you want to iterate over valid repositories, use this method.

        @return: enabled and valid repository identifiers
        @rtype list
        """
        return self._enabled_repos

    def installed_repository(self):
        """
        Return Entropy Client installed packages repository.

        @return: Entropy Client installed packages repository
        @rtype: entropy.db.EntropyRepository
        """
        return self._installed_repository

    def _open_installed_repository(self):

        def load_db_from_ram():
            self.safe_mode = etpConst['safemodeerrors']['clientdb']
            mytxt = "%s, %s" % (_("System database not found or corrupted"),
                _("running in safe mode using temporary, empty repository"),)
            self.output(
                darkred(mytxt),
                importance = 1,
                level = "warning",
                header = bold(" !!! "),
            )
            m_conn = self.open_temp_repository(dbname = etpConst['clientdbid'])
            self._add_plugin_to_client_repository(m_conn,
                etpConst['clientdbid'])
            return m_conn

        db_dir = os.path.dirname(etpConst['etpdatabaseclientfilepath'])
        if not os.path.isdir(db_dir):
            os.makedirs(db_dir)

        db_path = etpConst['etpdatabaseclientfilepath']
        if (not self.noclientdb) and (not os.path.isfile(db_path)):
            conn = load_db_from_ram()
            entropy.tools.print_traceback(f = self.clientLog)
        else:
            try:
                conn = EntropyRepository(readOnly = False, dbFile = db_path,
                    dbname = etpConst['clientdbid'],
                    xcache = self.xcache, indexing = self.indexing
                )
                self._add_plugin_to_client_repository(conn,
                    etpConst['clientdbid'])
                # TODO: remove this in future, drop useless data from clientdb
            except (DatabaseError,):
                entropy.tools.print_traceback(f = self.clientLog)
                conn = load_db_from_ram()
            else:
                # validate database
                if not self.noclientdb:
                    try:
                        conn.validateDatabase()
                    except SystemDatabaseError:
                        try:
                            conn.closeDB()
                        except:
                            pass
                        entropy.tools.print_traceback(f = self.clientLog)
                        conn = load_db_from_ram()

        self._installed_repository = conn
        return conn

    def reopen_installed_repository(self):
        self._installed_repository.closeDB()
        self._open_installed_repository()
        # make sure settings are in sync
        self._settings.clear()

    def open_generic_repository(self, dbfile, dbname = None, xcache = None,
            readOnly = False, indexing_override = None, skipChecks = False):
        if xcache is None:
            xcache = self.xcache
        if indexing_override != None:
            indexing = indexing_override
        else:
            indexing = self.indexing
        if dbname is None:
            dbname = etpConst['genericdbid']
        conn = EntropyRepository(
            readOnly = readOnly,
            dbFile = dbfile,
            dbname = dbname,
            xcache = xcache,
            indexing = indexing,
            skipChecks = skipChecks
        )
        self._add_plugin_to_client_repository(conn, dbname)
        return conn

    def open_temp_repository(self, dbname = None, temp_file = None):
        if dbname is None:
            dbname = etpConst['genericdbid']
        if temp_file is None:
            temp_file = entropy.tools.get_random_temp_file()

        dbc = EntropyRepository(
            readOnly = False,
            dbFile = temp_file,
            dbname = dbname,
            xcache = False,
            indexing = False,
            skipChecks = True,
            temporary = True
        )
        self._add_plugin_to_client_repository(dbc, dbname)
        dbc.initializeDatabase()
        return dbc

    def backup_repository(self, dbpath, backup_dir = None, silent = False,
        compress_level = 9):

        if compress_level not in list(range(1, 10)):
            compress_level = 9

        backup_dir = os.path.dirname(dbpath)
        if not backup_dir: backup_dir = os.path.dirname(dbpath)
        dbname = os.path.basename(dbpath)
        bytes_required = 1024000*300
        if not (os.access(backup_dir, os.W_OK) and \
                os.path.isdir(backup_dir) and os.path.isfile(dbpath) and \
                os.access(dbpath, os.R_OK) and \
                entropy.tools.check_required_space(backup_dir, bytes_required)):
            if not silent:
                mytxt = "%s: %s, %s" % (
                    darkred(_("Cannot backup selected database")),
                    blue(dbpath),
                    darkred(_("permission denied")),
                )
                self.output(
                    mytxt,
                    importance = 1,
                    level = "error",
                    header = red(" @@ ")
                )
            return False, mytxt

        def get_ts():
            ts = datetime.fromtimestamp(time.time())
            return "%s%s%s_%sh%sm%ss" % (ts.year, ts.month, ts.day, ts.hour,
                ts.minute, ts.second)

        comp_dbname = "%s%s.%s.bz2" % (etpConst['dbbackupprefix'], dbname, get_ts(),)
        comp_dbpath = os.path.join(backup_dir, comp_dbname)
        if not silent:
            mytxt = "%s: %s ..." % (
                darkgreen(_("Backing up database to")),
                blue(os.path.basename(comp_dbpath)),
            )
            self.output(
                mytxt,
                importance = 1,
                level = "info",
                header = blue(" @@ "),
                back = True
            )
        try:
            entropy.tools.compress_file(dbpath, comp_dbpath, bz2.BZ2File,
                compress_level)
        except:
            if not silent:
                entropy.tools.print_traceback()
            return False, _("Unable to compress")

        if not silent:
            mytxt = "%s: %s" % (
                darkgreen(_("Database backed up successfully")),
                blue(os.path.basename(comp_dbpath)),
            )
            self.output(
                mytxt,
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
        return True, _("All fine")

    def restore_repository(self, backup_path, db_destination, silent = False):

        bytes_required = 1024000*200
        db_dir = os.path.dirname(db_destination)
        if not (os.access(db_dir, os.W_OK) and os.path.isdir(db_dir) and \
            os.path.isfile(backup_path) and os.access(backup_path, os.R_OK) and \
            entropy.tools.check_required_space(db_dir, bytes_required)):

                if not silent:
                    mytxt = "%s: %s, %s" % (
                        darkred(_("Cannot restore selected backup")),
                        blue(os.path.basename(backup_path)),
                        darkred(_("permission denied")),
                    )
                    self.output(
                        mytxt,
                        importance = 1,
                        level = "error",
                        header = red(" @@ ")
                    )
                return False, mytxt

        if not silent:
            mytxt = "%s: %s => %s ..." % (
                darkgreen(_("Restoring backed up database")),
                blue(os.path.basename(backup_path)),
                blue(db_destination),
            )
            self.output(
                mytxt,
                importance = 1,
                level = "info",
                header = blue(" @@ "),
                back = True
            )

        try:
            entropy.tools.uncompress_file(backup_path, db_destination,
                bz2.BZ2File)
        except:
            if not silent:
                entropy.tools.print_traceback()
            return False, _("Unable to unpack")

        if not silent:
            mytxt = "%s: %s" % (
                darkgreen(_("Database restored successfully")),
                blue(os.path.basename(backup_path)),
            )
            self.output(
                mytxt,
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
        self.clear_cache()
        return True, _("All fine")

    def installed_repository_backups(self, client_dbdir = None):
        if not client_dbdir:
            client_dbdir = os.path.dirname(etpConst['etpdatabaseclientfilepath'])
        return [os.path.join(client_dbdir, x) for x in os.listdir(client_dbdir) \
                    if x.startswith(etpConst['dbbackupprefix']) and \
                    os.access(os.path.join(client_dbdir, x), os.R_OK)
        ]

    def _run_repositories_post_branch_switch_hooks(self, old_branch, new_branch):
        """
        This method is called whenever branch is successfully switched by user.
        Branch is switched when user wants to upgrade the OS to a new
        major release.
        Any repository can be shipped with a sh script which if available,
        handles system configuration to ease the migration.

        @param old_branch: previously set branch
        @type old_branch: string
        @param new_branch: newly set branch
        @type new_branch: string
        @return: tuple composed by (1) list of repositories whose script has
        been run and (2) bool describing if scripts exited with error
        @rtype: tuple(set, bool)
        """

        const_debug_write(__name__,
            "run_repositories_post_branch_switch_hooks: called")

        client_dbconn = self._installed_repository
        hooks_ran = set()
        if client_dbconn is None:
            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: clientdb not avail")
            return hooks_ran, True

        errors = False
        repo_data = self._settings['repositories']['available']
        repo_data_excl = self._settings['repositories']['available']
        all_repos = sorted(set(list(repo_data.keys()) + list(repo_data_excl.keys())))

        for repoid in all_repos:

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: %s" % (
                    repoid,)
            )

            mydata = repo_data.get(repoid)
            if mydata is None:
                mydata = repo_data_excl.get(repoid)

            if mydata is None:
                const_debug_write(__name__,
                    "run_repositories_post_branch_switch_hooks: skipping %s" % (
                        repoid,)
                )
                continue

            branch_mig_script = mydata['post_branch_hop_script']
            branch_mig_md5sum = '0'
            if os.access(branch_mig_script, os.R_OK) and \
                os.path.isfile(branch_mig_script):
                branch_mig_md5sum = entropy.tools.md5sum(branch_mig_script)

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: script md5: %s" % (
                    branch_mig_md5sum,)
            )

            # check if it is needed to run post branch migration script
            status_md5sums = client_dbconn.isBranchMigrationAvailable(
                repoid, old_branch, new_branch)
            if status_md5sums:
                if branch_mig_md5sum == status_md5sums[0]: # its stored md5
                    const_debug_write(__name__,
                        "run_repositories_post_branch_switch_hooks: skip %s" % (
                            branch_mig_script,)
                    )
                    continue # skipping, already ran the same script

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: preparing run: %s" % (
                    branch_mig_script,)
                )

            if branch_mig_md5sum != '0':
                args = ["/bin/sh", branch_mig_script, repoid, 
                    etpConst['systemroot'] + "/", old_branch, new_branch]
                const_debug_write(__name__,
                    "run_repositories_post_branch_switch_hooks: run: %s" % (
                        args,)
                )
                proc = subprocess.Popen(args, stdin = sys.stdin,
                    stdout = sys.stdout, stderr = sys.stderr)
                # it is possible to ignore errors because
                # if it's a critical thing, upstream dev just have to fix
                # the script and will be automagically re-run
                br_rc = proc.wait()
                const_debug_write(__name__,
                    "run_repositories_post_branch_switch_hooks: rc: %s" % (
                        br_rc,)
                )
                if br_rc != 0:
                    errors = True

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: done")

            # update metadata inside database
            # overriding post branch upgrade md5sum is INTENDED
            # here but NOT on the other function
            # this will cause the post-branch upgrade migration
            # script to be re-run also.
            client_dbconn.insertBranchMigration(repoid, old_branch, new_branch,
                branch_mig_md5sum, '0')

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: db data: %s" % (
                    (repoid, old_branch, new_branch, branch_mig_md5sum, '0',),)
            )

            hooks_ran.add(repoid)

        return hooks_ran, errors

    def _run_repository_post_branch_upgrade_hooks(self, pretend = False):
        """
        This method is called whenever branch is successfully switched by user
        and all the updates have been installed (also look at:
        run_repositories_post_branch_switch_hooks()).
        Any repository can be shipped with a sh script which if available,
        handles system configuration to ease the migration.

        @param pretend: do not run hooks but just return list of repos whose
            scripts should be run
        @type pretend: bool
        @return: tuple of length 2 composed by list of repositories whose
            scripts have been run and errors boolean)
        @rtype: tuple
        """

        const_debug_write(__name__,
            "run_repository_post_branch_upgrade_hooks: called"
        )

        client_dbconn = self._installed_repository
        hooks_ran = set()
        if client_dbconn is None:
            return hooks_ran, True

        repo_data = self._settings['repositories']['available']
        branch = self._settings['repositories']['branch']
        errors = False

        for repoid in self._enabled_repos:

            const_debug_write(__name__,
                "run_repository_post_branch_upgrade_hooks: repoid: %s" % (
                    (repoid,),
                )
            )

            mydata = repo_data.get(repoid)
            if mydata is None:
                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: repo data N/A")
                continue

            # check if branch upgrade script exists
            branch_upg_script = mydata['post_branch_upgrade_script']
            branch_upg_md5sum = '0'
            if os.access(branch_upg_script, os.R_OK) and \
                os.path.isfile(branch_upg_script):
                branch_upg_md5sum = entropy.tools.md5sum(branch_upg_script)

            if branch_upg_md5sum == '0':
                # script not found, skip completely
                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        repoid, "branch upgrade script not avail",)
                )
                continue

            const_debug_write(__name__,
                "run_repository_post_branch_upgrade_hooks: script md5: %s" % (
                    branch_upg_md5sum,)
            )

            upgrade_data = client_dbconn.retrieveBranchMigration(branch)
            if upgrade_data.get(repoid) is None:
                # no data stored for this repository, skipping
                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        repoid, "branch upgrade data not avail",)
                )
                continue
            repo_upgrade_data = upgrade_data[repoid]

            const_debug_write(__name__,
                "run_repository_post_branch_upgrade_hooks: upgrade data: %s" % (
                    repo_upgrade_data,)
            )

            for from_branch in sorted(repo_upgrade_data):

                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: upgrade: %s" % (
                        from_branch,)
                )

                # yeah, this is run for every branch even if script
                # which md5 is checked against is the same
                # this makes the code very flexible
                post_mig_md5, post_upg_md5 = repo_upgrade_data[from_branch]
                if branch_upg_md5sum == post_upg_md5:
                    # md5 is equal, this means that it's been already run
                    const_debug_write(__name__,
                        "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                            "already run for from_branch", from_branch,)
                    )
                    continue

                hooks_ran.add(repoid)

                if pretend:
                    const_debug_write(__name__,
                        "run_repository_post_branch_upgrade_hooks: %s: %s => %s" % (
                            "pretend enabled, not actually running",
                            repoid, from_branch,
                        )
                    )
                    continue

                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        "running upgrade script from_branch:", from_branch,)
                )

                args = ["/bin/sh", branch_upg_script, repoid,
                    etpConst['systemroot'] + "/", from_branch, branch]
                proc = subprocess.Popen(args, stdin = sys.stdin,
                    stdout = sys.stdout, stderr = sys.stderr)
                mig_rc = proc.wait()

                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        "upgrade script exit status", mig_rc,)
                )

                if mig_rc != 0:
                    errors = True

                # save branch_upg_md5sum in db
                client_dbconn.setBranchMigrationPostUpgradeMd5sum(repoid,
                    from_branch, branch, branch_upg_md5sum)

                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        "saved upgrade data",
                        (repoid, from_branch, branch, branch_upg_md5sum,),
                    )
                )

        return hooks_ran, errors


class MiscMixin:

    # resources lock file object container
    RESOURCES_LOCK_F_REF = None
    RESOURCES_LOCK_F_COUNT = 0

    def _reload_constants(self):
        initconfig_entropy_constants(etpSys['rootdir'])
        self._settings.clear()

    def setup_file_permissions(self, file_path):
        const_setup_file(file_path, etpConst['entropygid'], 0o664)

    def lock_resources(self):
        acquired = self._create_pid_file_lock()
        if acquired:
            MiscMixin.RESOURCES_LOCK_F_COUNT += 1
        return acquired

    def unlock_resources(self):

        # decrement lock counter
        if MiscMixin.RESOURCES_LOCK_F_COUNT > 0:
            MiscMixin.RESOURCES_LOCK_F_COUNT -= 1

        # if lock counter > 0, still locked
        # waiting for other upper-level calls
        if MiscMixin.RESOURCES_LOCK_F_COUNT > 0:
            return

        f_obj = MiscMixin.RESOURCES_LOCK_F_REF
        if f_obj is not None:
            fcntl.flock(f_obj.fileno(), fcntl.LOCK_UN)

            if f_obj is not None:
                f_obj.close()
            MiscMixin.RESOURCES_LOCK_F_REF = None

        lock_file = etpConst['locks']['using_resources']
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def resources_locked(self):
        """
        Determine whether Entropy resources are locked (in use).

        @return: True, if resources are locked
        @rtype: bool
        """
        return self._check_pid_file_lock(etpConst['locks']['using_resources'])

    def _check_pid_file_lock(self, pidfile):
        if not os.path.isfile(pidfile):
            return False # not locked

        f = open(pidfile, "r")
        s_pid = f.readline().strip()
        f.close()
        try:
            s_pid = int(s_pid)
        except ValueError:
            return False # not locked
        # is it our pid?

        mypid = os.getpid()
        if (s_pid != mypid) and const_pid_exists(s_pid):
            # is it running
            return True # locked
        return False

    def _create_pid_file_lock(self):

        if MiscMixin.RESOURCES_LOCK_F_REF is not None:
            # already locked, reentrant lock
            return True

        pidfile = etpConst['locks']['using_resources']
        lockdir = os.path.dirname(pidfile)
        if not os.path.isdir(lockdir):
            os.makedirs(lockdir, 0o775)
        const_setup_perms(lockdir, etpConst['entropygid'])
        mypid = os.getpid()

        pid_f = open(pidfile, "w")
        try:
            fcntl.flock(pid_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as err:
            if err.errno not in (errno.EACCES, errno.EAGAIN,):
                # ouch, wtf?
                raise
            pid_f.close()
            return False # lock already acquired

        pid_f.write(str(mypid))
        pid_f.flush()
        MiscMixin.RESOURCES_LOCK_F_REF = pid_f
        return True

    def another_entropy_running(self):
        # check if another instance is running
        acquired, locked = const_setup_entropy_pid(just_read = True)
        return locked

    def wait_resources(self, sleep_seconds = 1.0, max_lock_count = 300):

        lock_count = 0

        # check lock file
        while True:
            locked = self.resources_locked()
            if not locked:
                if lock_count > 0:
                    self.output(
                        blue(_("Resources unlocked, let's go!")),
                        importance = 1,
                        level = "info",
                        header = darkred(" @@ ")
                    )
                    # wait for other process to exit
                    # 5 seconds should be enough
                    time.sleep(5)
                break
            if lock_count >= max_lock_count:
                mycalc = max_lock_count*sleep_seconds/60
                self.output(
                    blue(_("Resources still locked after %s minutes, giving up!")) % (
                        mycalc,),
                    importance = 1,
                    level = "warning",
                    header = darkred(" @@ ")
                )
                return True # gave up
            lock_count += 1
            self.output(
                blue(_("Resources locked, sleeping %s seconds, check #%s/%s")) % (
                        sleep_seconds,
                        lock_count,
                        max_lock_count,
                ),
                importance = 1,
                level = "warning",
                header = darkred(" @@ "),
                back = True
            )
            time.sleep(sleep_seconds)
        return False # yay!

    def _backup_constant(self, constant_name):
        if constant_name in etpConst:
            myinst = etpConst[constant_name]
            if type(etpConst[constant_name]) in (list, tuple):
                myinst = etpConst[constant_name][:]
            elif type(etpConst[constant_name]) in (dict, set):
                myinst = etpConst[constant_name].copy()
            else:
                myinst = etpConst[constant_name]
            etpConst['backed_up'].update({constant_name: myinst})
        else:
            t = _("Nothing to backup in etpConst with %s key") % (constant_name,)
            raise AttributeError(t)

    def switch_chroot(self, chroot = ""):

        self.clear_cache()
        self.close_repositories()
        if chroot.endswith("/"):
            chroot = chroot[:-1]
        etpSys['rootdir'] = chroot
        self._reload_constants()
        self._validate_repositories()
        self.reopen_installed_repository()
        # keep them closed, since SystemSettings.clear() is called
        # above on reopen_installed_repository()
        self.close_repositories()
        if chroot:
            try:
                self._installed_repository.resetTreeupdatesDigests()
            except:
                pass

    def _is_installed_idpackage_in_system_mask(self, idpackage):
        client_plugin_id = etpConst['system_settings_plugins_ids']['client_plugin']
        cl_set = self._settings[client_plugin_id]
        mask_installed = cl_set['system_mask']['repos_installed']
        if idpackage in mask_installed:
            return True
        return False

    def is_entropy_package_free(self, pkg_id, repo_id):
        """
        Return whether given Entropy package match tuple points to a free
        (as in freedom) package.
        """
        cl_id = self.sys_settings_client_plugin_id
        repo_sys_data = self._settings[cl_id]['repositories']

        dbconn = self.open_repository(repo_id)

        wl = repo_sys_data['license_whitelist'].get(repo_id)
        if not wl: # no whitelist available
            return True

        keys = dbconn.retrieveLicensedataKeys(pkg_id)
        keys = [x for x in keys if x not in wl]
        if keys:
            return False
        return True

    def get_licenses_to_accept(self, install_queue):

        cl_id = self.sys_settings_client_plugin_id
        repo_sys_data = self._settings[cl_id]['repositories']
        lic_accepted = self._settings['license_accept']

        licenses = {}
        for pkg_id, repo_id in install_queue:
            dbconn = self.open_repository(repo_id)
            wl = repo_sys_data['license_whitelist'].get(repo_id)
            if not wl:
                continue
            try:
                keys = dbconn.retrieveLicensedataKeys(pkg_id)
            except OperationalError:
                # it has to be fault-tolerant, cope with missing tables
                continue
            keys = [x for x in keys if x not in lic_accepted]
            for key in keys:
                if key in wl:
                    continue
                found = self._installed_repository.isLicenseAccepted(key)
                if found:
                    continue
                obj = licenses.setdefault(key, set())
                obj.add((pkg_id, repo_id))

        return licenses

    def set_branch(self, branch):
        """
        Set new Entropy branch. This is NOT thread-safe.
        Please note that if you call this method all your
        repository instance references will become invalid.
        This is caused by close_repositories and SystemSettings
        clear methods.
        Once you changed branch, the repository databases won't be
        available until you fetch them (through Repositories class)

        @param branch -- new branch
        @type branch basestring
        @return None
        """
        cacher_started = self._cacher.is_started()
        self._cacher.discard()
        if cacher_started:
            self._cacher.stop()
        self.clear_cache()
        self.close_repositories()
        # etpConst should be readonly but we override the rule here
        # this is also useful when no config file or parameter into it exists
        etpConst['branch'] = branch
        entropy.tools.write_parameter_to_file(etpConst['repositoriesconf'],
            "branch", branch)
        # there are no valid repos atm
        del self._enabled_repos[:]
        self._settings.clear()

        # reset treeupdatesactions
        self.reopen_installed_repository()
        self._installed_repository.resetTreeupdatesDigests()
        self._validate_repositories(quiet = True)
        self.close_repositories()
        if cacher_started:
            self._cacher.start()

    def get_meant_packages(self, search_term, from_installed = False,
        valid_repos = None):

        if valid_repos is None:
            valid_repos = []

        pkg_data = []
        atom_srch = False
        if "/" in search_term:
            atom_srch = True

        if from_installed:
            if hasattr(self, '_installed_repository'):
                if self._installed_repository is not None:
                    valid_repos.append(self._installed_repository)

        elif not valid_repos:
            valid_repos.extend(self._enabled_repos[:])

        for repo in valid_repos:
            if const_isstring(repo):
                dbconn = self.open_repository(repo)
            elif isinstance(repo, EntropyRepository):
                dbconn = repo
            else:
                continue
            pkg_data.extend([(x, repo,) for x in \
                dbconn.searchSimilarPackages(search_term, atom = atom_srch)])

        return pkg_data

    def get_package_groups(self):
        """
        Return Entropy Package Groups metadata. The returned dictionary
        contains information to make Entropy Client users to group packages
        into "macro" categories.

        @return: Entropy Package Groups metadata
        @rtype: dict
        """
        from entropy.spm.plugins.factory import get_default_class
        spm = get_default_class()
        groups = spm.get_package_groups().copy()

        # expand metadata
        categories = self._get_package_categories()
        for data in list(groups.values()):

            exp_cats = set()
            for g_cat in data['categories']:
                exp_cats.update([x for x in categories if x.startswith(g_cat)])
            data['categories'] = sorted(exp_cats)

        return groups

    def _get_package_categories(self):
        categories = set()
        for repo in self._enabled_repos:
            dbconn = self.open_repository(repo)
            catsdata = dbconn.listAllCategories()
            categories.update(set([x[1] for x in catsdata]))
        return sorted(categories)

    def _inject_entropy_database_into_package(self, package_filename, data,
        treeupdates_actions = None):
        tmp_fd, tmp_path = tempfile.mkstemp()
        os.close(tmp_fd)
        dbconn = self.open_generic_repository(tmp_path)
        dbconn.initializeDatabase()
        dbconn.addPackage(data, revision = data['revision'])
        if treeupdates_actions != None:
            dbconn.bumpTreeUpdatesActions(treeupdates_actions)
        dbconn.commitChanges()
        dbconn.closeDB()
        entropy.tools.aggregate_entropy_metadata(package_filename, tmp_path)
        os.remove(tmp_path)

    def quickpkg(self, pkgdata, dirpath, edb = True, fake = False,
        compression = "bz2", shiftpath = ""):

        import tarfile

        if compression not in ("bz2", "", "gz"):
            compression = "bz2"

        version = pkgdata['version']
        version += "%s%s" % (etpConst['entropyrevisionprefix'],
            pkgdata['revision'],)
        pkgname = entropy.tools.create_package_filename(pkgdata['category'],
            pkgdata['name'], version, pkgdata['versiontag'])
        pkg_path = os.path.join(dirpath, pkgname)
        if os.path.isfile(pkg_path):
            os.remove(pkg_path)

        tar = tarfile.open(pkg_path, "w:"+compression)

        if not fake:

            contents = sorted([x for x in pkgdata['content']])

            # collect files
            for path in contents:
                # convert back to filesystem str
                encoded_path = path
                path = path.encode('raw_unicode_escape')
                path = shiftpath+path
                try:
                    exist = os.lstat(path)
                except OSError:
                    continue # skip file
                arcname = path[len(shiftpath):] # remove shiftpath
                if arcname.startswith("/"):
                    arcname = arcname[1:] # remove trailing /
                ftype = pkgdata['content'][encoded_path]
                if str(ftype) == '0':
                    # force match below, '0' means databases without ftype
                    ftype = 'dir'
                if 'dir' == ftype and \
                    not stat.S_ISDIR(exist.st_mode) and \
                    os.path.isdir(path):
                    # workaround for directory symlink issues
                    path = os.path.realpath(path)

                tarinfo = tar.gettarinfo(path, arcname)

                if stat.S_ISREG(exist.st_mode):
                    tarinfo.mode = stat.S_IMODE(exist.st_mode)
                    tarinfo.type = tarfile.REGTYPE
                    f = open(path)
                    try:
                        tar.addfile(tarinfo, f)
                    finally:
                        f.close()
                else:
                    tar.addfile(tarinfo)

        tar.close()

        # append SPM metadata
        Spm = self.Spm()
        Spm.append_metadata_to_package(pkgname, pkg_path)
        if edb:
            self._inject_entropy_database_into_package(pkg_path, pkgdata)

        if os.path.isfile(pkg_path):
            return pkg_path
        return None


class MatchMixin:

    def get_package_action(self, package_match):
        """
        upgrade: int(2)
        install: int(1)
        reinstall: int(0)
        downgrade: int(-1)
        """
        dbconn = self.open_repository(package_match[1])
        pkgkey, pkgslot = dbconn.retrieveKeySlot(package_match[0])
        results = self._installed_repository.searchKeySlot(pkgkey, pkgslot)
        if not results:
            return 1

        installed_idpackage = results[0][0]
        pkgver, pkgtag, pkgrev = dbconn.getVersioningData(package_match[0])
        installed_ver, installed_tag, installed_rev = \
            self._installed_repository.getVersioningData(installed_idpackage)
        pkgcmp = entropy.tools.entropy_compare_versions(
            (pkgver, pkgtag, pkgrev),
            (installed_ver, installed_tag, installed_rev))
        if pkgcmp == 0:
            # check digest, if it differs, we should mark pkg as update
            # we don't want users to think that they are "reinstalling" stuff
            # because it will just confuse them
            inst_digest = self._installed_repository.retrieveDigest(installed_idpackage)
            repo_digest = dbconn.retrieveDigest(package_match[0])
            if inst_digest != repo_digest:
                return 2
            return 0
        elif pkgcmp > 0:
            return 2
        return -1

    def is_package_masked(self, package_match, live_check = True):
        m_id, m_repo = package_match
        dbconn = self.open_repository(m_repo)
        idpackage, idreason = dbconn.idpackageValidator(m_id, live = live_check)
        if idpackage != -1:
            return False
        return True

    def is_package_masked_by_user(self, package_match, live_check = True):

        m_id, m_repo = package_match
        if m_repo not in self._enabled_repos:
            return False
        dbconn = self.open_repository(m_repo)
        idpackage, idreason = dbconn.idpackageValidator(m_id, live = live_check)
        if idpackage != -1:
            return False

        myr = self._settings['pkg_masking_reference']
        user_masks = [myr['user_package_mask'], myr['user_license_mask'],
            myr['user_live_mask']]
        if idreason in user_masks:
            return True
        return False

    def is_package_unmasked_by_user(self, package_match, live_check = True):

        m_id, m_repo = package_match
        if m_repo not in self._enabled_repos:
            return False
        dbconn = self.open_repository(m_repo)
        idpackage, idreason = dbconn.idpackageValidator(m_id, live = live_check)
        if idpackage == -1:
            return False

        myr = self._settings['pkg_masking_reference']
        user_masks = [
            myr['user_package_unmask'], myr['user_live_unmask'],
            myr['user_package_keywords'], myr['user_repo_package_keywords_all'],
            myr['user_repo_package_keywords']
        ]
        if idreason in user_masks:
            return True
        return False

    def mask_package(self, package_match, method = 'atom', dry_run = False):
        if self.is_package_masked(package_match, live_check = False):
            return True
        methods = {
            'atom': self._mask_package_by_atom,
            'keyslot': self._mask_package_by_keyslot,
        }
        rc = self._mask_unmask_package(package_match, method, methods,
            dry_run = dry_run)
        if dry_run: # inject if done "live"
            lpm = self._settings['live_packagemasking']
            lpm['unmask_matches'].discard(package_match)
            lpm['mask_matches'].add(package_match)
        return rc

    def unmask_package(self, package_match, method = 'atom', dry_run = False):
        if not self.is_package_masked(package_match, live_check = False):
            return True
        methods = {
            'atom': self._unmask_package_by_atom,
            'keyslot': self._unmask_package_by_keyslot,
        }
        rc = self._mask_unmask_package(package_match, method, methods,
            dry_run = dry_run)
        if dry_run: # inject if done "live"
            lpm = self._settings['live_packagemasking']
            lpm['unmask_matches'].add(package_match)
            lpm['mask_matches'].discard(package_match)
        return rc

    def _mask_unmask_package(self, package_match, method, methods_reference,
        dry_run = False):

        f = methods_reference.get(method)
        if not hasattr(f, '__call__'):
            raise AttributeError('%s: %s' % (
                _("not a valid method"), method,) )

        self._cacher.discard()
        self._settings._clear_repository_cache(package_match[1])
        done = f(package_match, dry_run)
        if done and not dry_run:
            self._settings.clear()

        cl_id = self.sys_settings_client_plugin_id
        self._settings[cl_id]['masking_validation']['cache'].clear()
        return done

    def _unmask_package_by_atom(self, package_match, dry_run = False):
        m_id, m_repo = package_match
        dbconn = self.open_repository(m_repo)
        atom = dbconn.retrieveAtom(m_id)
        return self.unmask_package_generic(package_match, atom, dry_run = dry_run)

    def _unmask_package_by_keyslot(self, package_match, dry_run = False):
        m_id, m_repo = package_match
        dbconn = self.open_repository(m_repo)
        key, slot = dbconn.retrieveKeySlot(m_id)
        keyslot = "%s%s%s" % (key, etpConst['entropyslotprefix'], slot,)
        return self.unmask_package_generic(package_match, keyslot,
            dry_run = dry_run)

    def _mask_package_by_atom(self, package_match, dry_run = False):
        m_id, m_repo = package_match
        dbconn = self.open_repository(m_repo)
        atom = dbconn.retrieveAtom(m_id)
        return self.mask_package_generic(package_match, atom, dry_run = dry_run)

    def _mask_package_by_keyslot(self, package_match, dry_run = False):
        m_id, m_repo = package_match
        dbconn = self.open_repository(m_repo)
        key, slot = dbconn.retrieveKeySlot(m_id)
        keyslot = "%s%s%s" % (key, etpConst['entropyslotprefix'], slot)
        return self.mask_package_generic(package_match, keyslot,
            dry_run = dry_run)

    def unmask_package_generic(self, package_match, keyword, dry_run = False):
        self._clear_package_mask(package_match, dry_run)
        m_file = self._settings.get_setting_files_data()['unmask']
        return self._mask_unmask_package_generic(keyword, m_file,
            dry_run = dry_run)

    def mask_package_generic(self, package_match, keyword, dry_run = False):
        self._clear_package_mask(package_match, dry_run)
        m_file = self._settings.get_setting_files_data()['mask']
        return self._mask_unmask_package_generic(keyword, m_file,
            dry_run = dry_run)

    def _mask_unmask_package_generic(self, keyword, m_file, dry_run = False):
        exist = False
        if not os.path.isfile(m_file):
            if not os.access(os.path.dirname(m_file), os.W_OK):
                return False # cannot write
        elif not os.access(m_file, os.W_OK):
            return False
        elif not dry_run:
            exist = True

        if dry_run:
            return True

        content = []
        if exist:
            f = open(m_file, "r")
            content = [x.strip() for x in f.readlines()]
            f.close()
        content.append(keyword)
        m_file_tmp = m_file+".tmp"
        f = open(m_file_tmp, "w")
        for line in content:
            f.write(line+"\n")
        f.flush()
        f.close()
        try:
            os.rename(m_file_tmp, m_file)
        except OSError:
            shutil.copy2(m_file_tmp, m_file)
            os.remove(m_file_tmp)
        return True

    def _clear_package_mask(self, package_match, dry_run = False):
        setting_data = self._settings.get_setting_files_data()
        masking_list = [setting_data['mask'], setting_data['unmask']]
        return self._clear_match_generic(package_match,
            masking_list = masking_list, dry_run = dry_run)

    def _clear_match_generic(self, match, masking_list = None, dry_run = False):

        if dry_run:
            return

        if masking_list is None:
            masking_list = []

        self._settings['live_packagemasking']['unmask_matches'].discard(
            match)
        self._settings['live_packagemasking']['mask_matches'].discard(
            match)

        new_mask_list = [x for x in masking_list if os.path.isfile(x) \
            and os.access(x, os.W_OK)]

        for mask_file in new_mask_list:

            tmp_fd, tmp_path = tempfile.mkstemp()
            os.close(tmp_fd)

            with open(mask_file, "r") as mask_f:
                with open(tmp_path, "w") as tmp_f:
                    for line in mask_f.readlines():
                        strip_line = line.strip()

                        if not (strip_line.startswith("#") or not strip_line):
                            mymatch = self.atom_match(strip_line,
                                mask_filter = False)
                            if mymatch == match:
                                continue

                        tmp_f.write(line)

            try:
                os.rename(tmp_path, mask_file)
            except OSError:
                shutil.copy2(tmp_path, mask_file)
                os.remove(tmp_path)

    def search_installed_mimetype(self, mimetype):
        """
        Given a mimetype, return list of installed package identifiers
        belonging to packages that can handle it.

        @param mimetype: mimetype string
        @type mimetype: string
        @return: list of installed package identifiers
        @rtype: list
        """
        return self._installed_repository.searchProvidedMime(mimetype)

    def search_available_mimetype(self, mimetype):
        """
        Given a mimetype, return list of available package matches
        belonging to packages that can handle it.

        @param mimetype: mimetype string
        @type mimetype: string
        @return: list of available package matches
        @rtype: list
        """
        packages = []
        for repo in self._enabled_repos:
            repo_db = self.open_repository(repo)
            packages += [(x, repo) for x in \
                repo_db.searchProvidedMime(mimetype)]
        return packages
