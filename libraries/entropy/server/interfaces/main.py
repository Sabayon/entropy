# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server Main Interfaces}.

"""

from __future__ import with_statement
import os
import shutil
from entropy.core import Singleton
from entropy.exceptions import OnlineMirrorError, PermissionDenied, \
    SystemDatabaseError
from entropy.const import etpConst, etpSys, const_setup_perms, \
    const_create_working_dirs, const_extract_srv_repo_params, etpUi
from entropy.output import TextInterface, purple, red, darkgreen, \
    bold, brown, blue, darkred
from entropy.server.interfaces.mirrors import Server as MirrorsServer
from entropy.i18n import _
from entropy.core import SystemSettings, SystemSettingsPlugin
from entropy.transceivers import FtpInterface
from entropy.db import EntropyRepository
from entropy.spm import get_spm

class ServerSystemSettingsPlugin(SystemSettingsPlugin):

    def server_parser(self, sys_set):

        """
        Parses Entropy server system configuration file.

        @return dict data
        """

        data = {
            'repositories': etpConst['server_repositories'].copy(),
            'default_repository_id': etpConst['officialserverrepositoryid'],
            'packages_expiration_days': etpConst['packagesexpirationdays'],
            'database_file_format': etpConst['etpdatabasefileformat'],
            'disabled_eapis': set(),
            'exp_based_scope': etpConst['expiration_based_scope'],
            'rss': {
                'enabled': etpConst['rss-feed'],
                'name': etpConst['rss-name'],
                'base_url': etpConst['rss-base-url'],
                'website_url': etpConst['rss-website-url'],
                'editor': etpConst['rss-managing-editor'],
                'max_entries': etpConst['rss-max-entries'],
                'light_max_entries': etpConst['rss-light-max-entries'],
            },
        }

        fake_instance = self._helper.fake_default_repo

        if not os.access(etpConst['serverconf'], os.R_OK):
            return data

        with open(etpConst['serverconf'],"r") as server_f:
            serverconf = [x.strip() for x in server_f.readlines() if x.strip()]

        for line in serverconf:

            split_line = line.split("|")
            split_line_len = len(split_line)

            if (line.find("officialserverrepositoryid|") != -1) and \
                (not line.startswith("#")) and (split_line_len == 2):

                if not fake_instance:
                    data['default_repository_id'] = split_line[1].strip()

            elif line.startswith("expiration-days|") and (split_line_len == 2):

                mydays = split_line[1].strip()
                try:
                    mydays = int(mydays)
                    data['packages_expiration_days'] = mydays
                except ValueError:
                    continue

            elif line.startswith("expiration-based-scope|") and \
                (split_line_len == 2):

                exp_opt = split_line[1].strip().lower()
                if exp_opt in ("enable", "enabled", "true", "1", "yes"):
                    data['exp_based_scope'] = True
                else:
                    data['exp_based_scope'] = False

            elif line.startswith("disabled-eapis|") and (split_line_len == 2):

                mydis = split_line[1].strip().split(",")
                try:
                    mydis = [int(x) for x in mydis]
                    mydis = set([x for x in mydis if x in (1, 2, 3,)])
                except ValueError:
                    continue
                if (len(mydis) < 3) and mydis:
                    data['disabled_eapis'] = mydis


            elif line.startswith("repository|") and (split_line_len in [5, 6]) \
                and (not fake_instance):

                repoid, repodata = const_extract_srv_repo_params(line,
                    product = sys_set['repositories']['product'])
                if repoid in data['repositories']:
                    # just update mirrors
                    data['repositories'][repoid]['mirrors'].extend(
                        repodata['mirrors'])
                else:
                    data['repositories'][repoid] = repodata.copy()

            elif line.startswith("database-format|") and (split_line_len == 2):

                fmt = split_line[1]
                if fmt in etpConst['etpdatabasesupportedcformats']:
                    data['database_file_format'] = fmt

            elif line.startswith("rss-feed|") and (split_line_len == 2):

                feed = split_line[1]
                if feed in ("enable", "enabled", "true", "1"):
                    data['rss']['enabled'] = True
                elif feed in ("disable", "disabled", "false", "0", "no",):
                    data['rss']['enabled'] = False

            elif line.startswith("rss-name|") and (split_line_len == 2):

                feedname = line.split("rss-name|")[1].strip()
                data['rss']['name'] = feedname

            elif line.startswith("rss-base-url|") and (split_line_len == 2):

                data['rss']['base_url'] = line.split("rss-base-url|")[1].strip()
                if not data['rss']['base_url'][-1] == "/":
                    data['rss']['base_url'] += "/"

            elif line.startswith("rss-website-url|") and (split_line_len == 2):

                data['rss']['website_url'] = split_line[1].strip()

            elif line.startswith("managing-editor|") and (split_line_len == 2):

                data['rss']['editor'] = split_line[1].strip()

            elif line.startswith("max-rss-entries|") and (split_line_len == 2):

                try:
                    entries = int(split_line[1].strip())
                    data['rss']['max_entries'] = entries
                except (ValueError, IndexError,):
                    continue

            elif line.startswith("max-rss-light-entries|") and \
                (split_line_len == 2):

                try:
                    entries = int(split_line[1].strip())
                    data['rss']['light_max_entries'] = entries
                except (ValueError, IndexError,):
                    continue

        # add system database if community repository mode is enabled
        if self._helper.community_repo:
            data['repositories'][etpConst['clientserverrepoid']] = {}
            mydata = {}
            mydata['description'] = "Community Repositories System Database"
            mydata['mirrors'] = []
            mydata['community'] = False
            data['repositories'][etpConst['clientserverrepoid']].update(mydata)

        # expand paths
        for repoid in data['repositories']:
            data['repositories'][repoid]['packages_dir'] = \
                os.path.join(   etpConst['entropyworkdir'],
                                "server",
                                repoid,
                                "packages",
                                etpSys['arch']
                            )
            data['repositories'][repoid]['store_dir'] = \
                os.path.join(   etpConst['entropyworkdir'],
                                "server",
                                repoid,
                                "store",
                                etpSys['arch']
                            )
            data['repositories'][repoid]['upload_dir'] = \
                os.path.join(   etpConst['entropyworkdir'],
                                "server",
                                repoid,
                                "upload",
                                etpSys['arch']
                            )
            data['repositories'][repoid]['database_dir'] = \
                os.path.join(   etpConst['entropyworkdir'],
                                "server",
                                repoid,
                                "database",
                                etpSys['arch']
                            )
            data['repositories'][repoid]['packages_relative_path'] = \
                os.path.join(   sys_set['repositories']['product'],
                                repoid,
                                "packages",
                                etpSys['arch']
                            )+"/"
            data['repositories'][repoid]['database_relative_path'] = \
                os.path.join(   sys_set['repositories']['product'],
                                repoid,
                                "database",
                                etpSys['arch']
                            )+"/"

        # Support for shell variables
        shell_repoid = os.getenv('ETP_REPO')
        if shell_repoid:
            data['default_repository_id'] = shell_repoid

        expiration_days = os.getenv('ETP_EXPIRATION_DAYS')
        if expiration_days:
            try:
                expiration_days = int(expiration_days)
                data['packages_expiration_days'] = expiration_days
            except ValueError:
                pass

        return data

class ServerFatscopeSystemSettingsPlugin(SystemSettingsPlugin):

    import entropy.tools as entropyTools

    def repos_parser(self, sys_set):

        data = {}
        srv_plug_id = etpConst['system_settings_plugins_ids']['server_plugin']
        # if support is not enabled, don't waste time scanning files
        srv_parser_data = sys_set[srv_plug_id]['server']
        if not srv_parser_data['exp_based_scope']:
            return data

        # get expiration-based packages removal data from config files
        for repoid in srv_parser_data['repositories']:

            # filter out system repository if community repository
            # mode is enabled
            if repoid == etpConst['clientserverrepoid']:
                continue

            idpackages = set()
            exp_fp = self._helper.get_local_exp_based_pkgs_rm_whitelist_file(
                repo = repoid)
            dbconn = self._helper.open_server_repository(
                just_reading = True, repo = repoid)

            if os.access(exp_fp, os.R_OK | os.F_OK):
                pkgs = self.entropyTools.generic_file_content_parser(exp_fp)
                if '*' in pkgs: # wildcard support
                    idpackages.add(-1)
                else:
                    for pkg in pkgs:
                        idpackage, rc_match = dbconn.atomMatch(pkg)
                        if rc_match:
                            continue
                        idpackages.add(idpackage)

            data[repoid] = idpackages

        return data


class Server(Singleton, TextInterface):

    def init_singleton(self, default_repository = None, save_repository = False,
            community_repo = False, fake_default_repo = False,
            fake_default_repo_id = '::fake::',
            fake_default_repo_desc = 'this is a fake repository'):

        self.__instance_destroyed = False
        if etpConst['uid'] != 0:
            mytxt = _("Entropy Server interface must be run as root")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

        # settings
        self.SystemSettings = SystemSettings()
        self.community_repo = community_repo
        from entropy.db import dbapi2
        self.dbapi2 = dbapi2 # export for third parties
        etpSys['serverside'] = True
        self._memory_db_instances = {}
        self.fake_default_repo = fake_default_repo
        self.indexing = False
        self.xcache = False
        self.MirrorsService = None
        self.__server_dbcache = {}
        self.repository_treeupdate_digests = {}
        self.__settings_to_backup = []
        self.__do_save_repository = save_repository
        self.__sync_lock_cache = set()
        self.rssMessages = {
            'added': {},
            'removed': {},
            'commitmessage': "",
            'light': {},
        }

        if fake_default_repo:
            default_repository = fake_default_repo_id
            etpConst['officialserverrepositoryid'] = fake_default_repo_id
            self.init_generic_memory_server_repository(fake_default_repo_id,
                fake_default_repo_desc)

        # create our SystemSettings plugin
        self.sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        self.sys_settings_plugin = ServerSystemSettingsPlugin(
            self.sys_settings_plugin_id, self)
        self.SystemSettings.add_plugin(self.sys_settings_plugin)

        # Fatscope support SystemSettings plugin
        self.sys_settings_fatscope_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin_fatscope']
        self.sys_settings_fatscope_plugin = ServerFatscopeSystemSettingsPlugin(
            self.sys_settings_fatscope_plugin_id, self)
        self.SystemSettings.add_plugin(self.sys_settings_fatscope_plugin)

        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        self.default_repository = default_repository
        if self.default_repository == None:
            self.default_repository = srv_set['default_repository_id']

        if self.default_repository in srv_set['repositories']:
            self.ensure_paths(self.default_repository)

        # NOW DISABLED, deprecated!
        # self.migrate_repository_databases_to_new_branched_path()

        if self.default_repository not in srv_set['repositories']:
            raise PermissionDenied("PermissionDenied: %s %s" % (
                        self.default_repository,
                        _("repository not configured"),
                    )
            )
        if etpConst['clientserverrepoid'] == self.default_repository:
            raise PermissionDenied("PermissionDenied: %s %s" % (
                    etpConst['clientserverrepoid'],
                    _("protected repository id, can't use this, sorry dude..."),
                )
            )

        self.switch_default_repository(self.default_repository)

    def destroy(self):
        self.__instance_destroyed = True
        if hasattr(self,'ClientService'):
            self.ClientService.destroy()
        if hasattr(self,'sys_settings_server_plugin'):
            try:
                self.SystemSettings.remove_plugin(self.sys_settings_plugin_id)
            except KeyError:
                pass
        if hasattr(self,'sys_settings_fatscope_plugin'):
            try:
                self.SystemSettings.remove_plugin(
                    self.sys_settings_fatscope_plugin)
            except KeyError:
                pass
        self.close_server_databases()

    def is_destroyed(self):
        return self.__instance_destroyed

    def __del__(self):
        self.destroy()

    def ensure_paths(self, repo):
        upload_dir = os.path.join(self.get_local_upload_directory(repo),
            self.SystemSettings['repositories']['branch'])
        db_dir = self.get_local_database_dir(repo)
        for mydir in [upload_dir, db_dir]:
            if (not os.path.isdir(mydir)) and (not os.path.lexists(mydir)):
                os.makedirs(mydir)
                const_setup_perms(mydir, etpConst['entropygid'])


    def migrate_repository_databases_to_new_branched_path(self):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        migrated_filename = '.branch_migrated'
        for repoid in srv_set['repositories'].keys():

            if repoid == etpConst['clientserverrepoid']: continue
            mydir = srv_set['repositories'][repoid]['database_dir']
            if not os.path.isdir(mydir): # empty ?
                continue

            migrated_filepath = os.path.join(mydir, migrated_filename)
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

            repo_files = [os.path.join(mydir, x) for x in os.listdir(mydir) if \
                (os.path.isfile(os.path.join(mydir, x)) and \
                os.access(os.path.join(mydir, x), os.W_OK))
            ]
            os.makedirs(my_branched_dir)
            const_setup_perms(my_branched_dir, etpConst['entropygid'])

            for repo_file in repo_files:
                repo_filename = os.path.basename(repo_file)
                shutil.move(repo_file,
                    os.path.join(my_branched_dir, repo_filename))

            f_migrated = open(migrated_filepath,"w")
            f_migrated.write("done\n")
            f_migrated.flush()
            f_migrated.close()

    def setup_services(self):
        self.setup_entropy_settings()
        cs_name = 'ClientService'
        if hasattr(self, cs_name):
            obj = getattr(self, cs_name)
            obj.destroy()
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
        self.validRepositories = self.ClientService.validRepositories
        self.entropyTools = self.ClientService.entropyTools
        self.dumpTools = self.ClientService.dumpTools
        self.QA = self.ClientService.QA
        self.backup_entropy_settings()

        self.MirrorsService = MirrorsServer(self)

    def Spm(self):
        """
        Get Source Package Manager interface instance.

        @return: Source Package Manager interface instance
        @rtype: entropy.spm.SpmPlugin based instance
        """
        return get_spm(self)

    def setup_entropy_settings(self, repo = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        backup_list = [
            'etpdatabaseclientfilepath',
            'clientdbid',
            {'server': srv_set.copy()},
        ]
        for setting in backup_list:
            if setting not in self.__settings_to_backup:
                self.__settings_to_backup.append(setting)
        # setup client database
        if not self.community_repo:
            etpConst['etpdatabaseclientfilepath'] = \
                self.get_local_database_file(repo)
            etpConst['clientdbid'] = etpConst['serverdbid']
        const_create_working_dirs()

    def close_server_databases(self):
        if hasattr(self,'serverDbCache'):
            for item in self.__server_dbcache:
                try:
                    self.__server_dbcache[item].closeDB()
                except self.dbapi2.ProgrammingError: # already closed?
                    pass
            self.__server_dbcache.clear()

    def close_server_database(self, dbinstance):
        found = None
        for item in self.__server_dbcache:
            if dbinstance == self.__server_dbcache[item]:
                found = item
                break
        if found:
            instance = self.__server_dbcache.pop(found)
            instance.closeDB()

    def get_available_repositories(self):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        return srv_set['repositories'].copy()

    def switch_default_repository(self, repoid, save = None,
        handle_uninitialized = True):

        # avoid setting __default__ as default server repo
        if repoid == etpConst['clientserverrepoid']:
            return
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']

        if save == None:
            save = self.__do_save_repository
        if repoid not in srv_set['repositories']:
            raise PermissionDenied("PermissionDenied: %s %s" % (
                        repoid,
                        _("repository not configured"),
                    )
            )
        self.close_server_databases()
        srv_set['default_repository_id'] = repoid
        self.default_repository = repoid
        self.setup_services()
        if save:
            self.save_default_repository(repoid)

        self.setup_community_repositories_settings()
        self.show_interface_status()
        if handle_uninitialized and etpUi['warn']:
            self.handle_uninitialized_repository(repoid)

    def setup_community_repositories_settings(self):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if self.community_repo:
            for repoid in srv_set['repositories']:
                srv_set['repositories'][repoid]['community'] = True


    def handle_uninitialized_repository(self, repoid):

        if not self.is_repository_initialized(repoid):
            mytxt = blue("%s.") % (
                _("Your default repository is not initialized"),)
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
            answer = self.askQuestion(
                _("Do you want to initialize your default repository ?"))
            if answer == "No":
                mytxt = red("%s.") % (
                    _("Continuing with an uninitialized repository"),)
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
                    shutil.move(dbfile, dbfile+".backup")
                self.initialize_server_database(empty = True,
                    repo = repoid, warnings = False)


    def show_interface_status(self):
        type_txt = _("server-side repository")
        if self.community_repo:
            type_txt = _("community repository")
        # ..on repository: <repository_name>
        mytxt = _("Entropy Server Interface Instance on repository")
        self.updateProgress(
            blue("%s: %s, %s: %s (%s: %s)" % (
                    mytxt,
                    red(self.default_repository),
                    _("current branch"),
                    darkgreen(self.SystemSettings['repositories']['branch']),
                    purple(_("type")),
                    bold(type_txt),
                )
            ),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        repos = srv_set['repositories'].keys()
        mytxt = blue("%s:") % (_("Currently configured repositories"),)
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
            f_srv = open(etpConst['serverconf'],"r")
            content = f_srv.readlines()
            f_srv.close()
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
            f_srv_t = open(etpConst['serverconf']+".save_default_repo_tmp","w")
            for line in new_content:
                f_srv_t.write(line+"\n")
            f_srv_t.flush()
            f_srv_t.close()
            os.rename(etpConst['serverconf']+".save_default_repo_tmp",
                etpConst['serverconf'])
        else:
            f_srv = open(etpConst['serverconf'],"w")
            f_srv.write("officialserverrepositoryid|%s\n" % (repoid,))
            f_srv.flush()
            f_srv.close()

    def toggle_repository(self, repoid, enable = True):

        # avoid setting __default__ as default server repo
        if repoid == etpConst['clientserverrepoid']:
            return False

        if not os.path.isfile(etpConst['serverconf']):
            return None
        f_srv = open(etpConst['serverconf'])
        tmpfile = etpConst['serverconf']+".switch"
        mycontent = [x.strip() for x in f_srv.readlines()]
        f_srv.close()
        f_tmp = open(tmpfile,"w")
        st = "repository|%s" % (repoid,)
        status = False
        for line in mycontent:
            if enable:
                if (line.find(st) != -1) and line.startswith("#") and \
                    (len(line.split("|")) == 5):
                    line = line[1:]
                    status = True
            else:
                if (line.find(st) != -1) and not line.startswith("#") and \
                    (len(line.split("|")) == 5):
                    line = "#"+line
                    status = True
            f_tmp.write(line+"\n")
        f_tmp.flush()
        f_tmp.close()
        shutil.move(tmpfile, etpConst['serverconf'])
        if status:
            self.close_server_databases()
            self.SystemSettings.clear()
            self.setup_services()
            self.show_interface_status()
        return status

    def backup_entropy_settings(self):
        for setting in self.__settings_to_backup:
            if isinstance(setting, basestring):
                self.ClientService.backup_constant(setting)
            elif isinstance(setting, dict):
                self.SystemSettings.set_persistent_setting(setting)

    def is_repository_initialized(self, repo):

        def do_validate(dbc):
            try:
                dbc.validateDatabase()
                return True
            except SystemDatabaseError:
                return False

        dbc = self.open_server_repository(just_reading = True, repo = repo)
        valid = do_validate(dbc)
        self.close_server_database(dbc)
        if not valid: # check online?
            dbc = self.open_server_repository(read_only = False,
                no_upload = True, repo = repo, is_new = True)
            valid = do_validate(dbc)
            self.close_server_database(dbc)

        return valid

    def do_server_repository_sync_lock(self, repo, no_upload):

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
                given_up = self.MirrorsService.mirror_lock_check(uri,
                    repo = repo)
                if given_up:
                    crippled_uri = \
                        self.entropyTools.extract_ftp_host_from_uri(uri)
                    mytxt = "%s:" % (_("Mirrors status table"),)
                    self.updateProgress(
                        darkgreen(mytxt),
                        importance = 1,
                        type = "info",
                        header = brown(" * ")
                    )
                    dbstatus = self.MirrorsService.get_mirrors_lock(repo = repo)
                    for db_uri, db_st1, db_st2 in dbstatus:
                        db_st1_info = darkgreen(_("Unlocked"))
                        if db_st1:
                            db_st1_info = red(_("Locked"))
                        db_st2_info = darkgreen(_("Unlocked"))
                        if db_st2:
                            db_st2_info = red(_("Locked"))

                        crippled_uri = \
                            self.entropyTools.extract_ftp_host_from_uri(db_uri)
                        self.updateProgress(
                            "%s: [%s: %s] [%s: %s]" % (
                                bold(crippled_uri),
                                brown(_("database")),
                                db_st1_info,
                                brown(_("download")),
                                db_st2_info,
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


    def init_generic_memory_server_repository(self, repoid, description,
        mirrors = None, community_repo = False, service_url = None):

        if mirrors is None:
            mirrors = []
        dbc = self.open_memory_database(dbname = etpConst['serverdbid']+repoid)
        self._memory_db_instances[repoid] = dbc

        eapi3_port = int(etpConst['socket_service']['port'])
        eapi3_ssl_port = int(etpConst['socket_service']['ssl_port'])
        # add to settings
        repodata = {
            'repoid': repoid,
            'description': description,
            'mirrors': mirrors,
            'community': community_repo,
            'service_port': eapi3_port,
            'ssl_service_port': eapi3_ssl_port,
            'service_url': service_url,
            'handler': '', # not supported
            'in_memory': True,
        }

        etpConst['server_repositories'][repoid] = repodata
        self.SystemSettings.clear()

        return dbc

    def open_memory_database(self, dbname = None):
        if dbname == None:
            dbname = etpConst['genericdbid']
        dbc = EntropyRepository(
            readOnly = False,
            dbFile = ':memory:',
            clientDatabase = True,
            dbname = dbname,
            xcache = False,
            indexing = False,
            OutputInterface = self,
            skipChecks = True
        )
        dbc.initializeDatabase()
        return dbc

    def open_server_repository(
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
            is_new = False,
            do_treeupdates = True
        ):

        if repo == None:
            repo = self.default_repository

        if repo == etpConst['clientserverrepoid'] and self.community_repo:
            return self.ClientService.clientDbconn

        # in-memory server repos
        if repo in self._memory_db_instances:
            return self._memory_db_instances.get(repo)

        if just_reading:
            read_only = True
            no_upload = True

        local_dbfile = self.get_local_database_file(repo, use_branch)
        if do_cache:
            cached = self.__server_dbcache.get(
                (repo, etpConst['systemroot'], local_dbfile, read_only,
                    no_upload, just_reading, use_branch, lock_remote,)
            )
            if cached != None:
                return cached

        local_dbfile_dir = os.path.dirname(local_dbfile)
        if not os.path.isdir(local_dbfile_dir):
            os.makedirs(local_dbfile_dir)

        if (not read_only) and (lock_remote) and \
            (repo not in self.__sync_lock_cache):
            self.do_server_repository_sync_lock(repo, no_upload)
            self.__sync_lock_cache.add(repo)

        local_dbfile_exists = os.path.lexists(local_dbfile)
        conn = EntropyRepository(
            readOnly = read_only,
            dbFile = local_dbfile,
            noUpload = no_upload,
            OutputInterface = self,
            dbname = etpConst['serverdbid']+repo,
            useBranch = use_branch,
            lockRemote = lock_remote
        )
        if not local_dbfile_exists:
            # better than having a completely broken db
            conn.readOnly = False
            conn.initializeDatabase()
            conn.commitChanges()

        valid = True
        try:
            conn.validateDatabase()
        except SystemDatabaseError:
            valid = False

        # verify if we need to update the database to sync
        # with portage updates, we just ignore being readonly in the case
        if (repo not in etpConst['server_treeupdatescalled']) and \
            (not just_reading):
            # sometimes, when filling a new server db
            # we need to avoid tree updates
            if valid:
                if do_treeupdates:
                    self.repository_packages_spm_sync(conn,
                        branch = use_branch, repo = repo)
            elif warnings and not is_new:
                mytxt = _("Entropy database is corrupted!")
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
            self.__server_dbcache[
                (repo, etpConst['systemroot'], local_dbfile, read_only,
                no_upload, just_reading, use_branch, lock_remote,)] = conn

        # auto-update package sets
        if (not read_only) and (not is_new):
            cur_sets = conn.retrievePackageSets()
            sys_sets = self.get_configured_package_sets(repo)
            if cur_sets != sys_sets:
                self.update_database_package_sets(repo, dbconn = conn)
            conn.commitChanges()

        return conn

    def repository_packages_spm_sync(self, repo_db, branch = None, repo = None):
        """
        Service method used to sync package names with Source Package Manager.
        Source Package Manager can change package names, categories or slot
        and Entropy repositories must be kept in sync.

        In other words, it checks for /usr/portage/profiles/updates changes.
        """

        if branch == None:
            branch = self.SystemSettings['repositories']['branch']
        if repo == None:
            repo = self.default_repository

        etpConst['server_treeupdatescalled'].add(repo)

        repo_updates_file = self.get_local_database_treeupdates_file(repo)
        doRescan = False

        stored_digest = repo_db.retrieveRepositoryUpdatesDigest(repo)
        if stored_digest == -1:
            doRescan = True

        # check portage files for changes if doRescan is still false
        portage_dirs_digest = "0"
        if not doRescan:

            if self.repository_treeupdate_digests.has_key(repo):
                portage_dirs_digest = self.repository_treeupdate_digests.get(
                    repo)
            else:

                spm = self.Spm()
                # grab portdir
                updates_dir = etpConst['systemroot'] + \
                    spm.get_spm_setting("PORTDIR") + "/profiles/updates"
                if os.path.isdir(updates_dir):
                    # get checksum
                    mdigest = self.entropyTools.md5obj_directory(updates_dir)
                    # also checksum etpConst['etpdatabaseupdatefile']
                    if os.path.isfile(repo_updates_file):
                        f = open(repo_updates_file)
                        block = f.read(1024)
                        while block:
                            mdigest.update(block)
                            block = f.read(1024)
                        f.close()
                    portage_dirs_digest = mdigest.hexdigest()
                    self.repository_treeupdate_digests[repo] = \
                        portage_dirs_digest

        if doRescan or (str(stored_digest) != str(portage_dirs_digest)):

            # force parameters
            repo_db.readOnly = False
            repo_db.noUpload = True

            # reset database tables
            repo_db.clearTreeupdatesEntries(repo)

            updates_dir = etpConst['systemroot'] + \
                self.Spm().get_spm_setting("PORTDIR") + "/profiles/updates"
            update_files = self.entropyTools.sort_update_files(
                os.listdir(updates_dir))
            update_files = [os.path.join(updates_dir, x) for x in update_files]
            # now load actions from files
            update_actions = []
            for update_file in update_files:
                f = open(update_file, "r")
                mycontent = f.readlines()
                f.close()
                lines = [x.strip() for x in mycontent if x.strip()]
                update_actions.extend(lines)

            # add entropy packages.db.repo_updates content
            if os.path.isfile(repo_updates_file):
                f = open(repo_updates_file, "r")
                mycontent = f.readlines()
                f.close()
                lines = [x.strip() for x in mycontent if x.strip() and \
                    not x.strip().startswith("#")]
                update_actions.extend(lines)
            # now filter the required actions
            update_actions = repo_db.filterTreeUpdatesActions(update_actions)
            if update_actions:

                mytxt = "%s: %s. %s %s" % (
                    bold(_("ATTENTION")),
                    red(_("forcing package updates")),
                    red(_("Syncing with")),
                    blue(updates_dir),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = brown(" * ")
                )
                # lock database
                if repo_db.lockRemote:
                    self.do_server_repository_sync_lock(
                        repo, repo_db.noUpload)
                # now run queue
                try:
                    quickpkg_list = repo_db.runTreeUpdatesActions(
                        update_actions)
                except:
                    # destroy digest
                    repo_db.setRepositoryUpdatesDigest(repo, "-1")
                    raise

                if quickpkg_list:
                    # quickpkg package and packages owning it as a dependency
                    try:
                        self._run_packages_spm_sync_quickpkg(
                            quickpkg_list, repo_db, repo)
                    except:
                        self.entropyTools.print_traceback()
                        mytxt = "%s: %s: %s, %s." % (
                            bold(_("WARNING")),
                            red(_("Cannot complete quickpkg for atoms")),
                            blue(str(sorted(quickpkg_list))),
                            _("do it manually"),
                        )
                        self.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "warning",
                            header = darkred(" * ")
                        )
                    repo_db.commitChanges()

                # store new actions
                repo_db.addRepositoryUpdatesActions(
                    repo, update_actions, branch)

            # store new digest into database
            repo_db.setRepositoryUpdatesDigest(
                repo, portage_dirs_digest)
            repo_db.commitChanges()

    def _run_packages_spm_sync_quickpkg(self, atoms, repo_db, repo):
        """
        Executes packages regeneration for given atoms.
        """
        package_paths = set()
        runatoms = set()
        for myatom in atoms:
            mymatch = repo_db.atomMatch(myatom)
            if mymatch[0] == -1:
                continue
            myatom = repo_db.retrieveAtom(mymatch[0])
            myatom = self.entropyTools.remove_tag(myatom)
            runatoms.add(myatom)

        for myatom in runatoms:

            self.updateProgress(
                red("%s: " % (_("repackaging"),) )+blue(myatom),
                importance = 1,
                type = "warning",
                header = blue("  # ")
            )
            mydest = self.get_local_store_directory(repo = repo)
            try:
                mypath = self.quickpkg(myatom, mydest)
            except:
                # remove broken bin before raising
                mypath = os.path.join(mydest,
                    os.path.basename(myatom) + etpConst['packagesext'])
                if os.path.isfile(mypath):
                    os.remove(mypath)
                self.entropyTools.print_traceback()
                mytxt = "%s: %s: %s, %s." % (
                    bold(_("WARNING")),
                    red(_("Cannot complete quickpkg for atom")),
                    blue(myatom),
                    _("do it manually"),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = darkred(" * ")
                )
                continue
            package_paths.add(mypath)
        packages_data = [(x, False,) for x in package_paths]
        idpackages = self.add_packages_to_repository(
            packages_data, repo = repo)

        if not idpackages:

            mytxt = "%s: %s. %s." % (
                bold(_("ATTENTION")),
                red(_("package files rebuild did not run properly")),
                red(_("Please update packages manually")),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred(" * ")
            )

    def deps_tester(self, default_repo = None):

        sys_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        server_repos = sys_set['repositories'].keys()
        installed_packages = set()
        # if a default repository is passed, we will just test against it
        if default_repo:
            server_repos = [default_repo]

        for repo in server_repos:
            dbconn = self.open_server_repository(read_only = True,
                no_upload = True, repo = repo, do_treeupdates = False)
            installed_packages |= set([(x, repo) for x in \
                dbconn.listAllIdpackages()])


        deps_not_satisfied = set()
        length = str((len(installed_packages)))
        count = 0
        mytxt = _("Checking")

        for idpackage, repo in installed_packages:
            count += 1
            dbconn = self.open_server_repository(read_only = True,
                no_upload = True, repo = repo, do_treeupdates = False)

            if (count%150 == 0) or (count == length) or (count == 1):
                atom = dbconn.retrieveAtom(idpackage)
                self.updateProgress(
                    darkgreen(mytxt)+" "+bold(atom),
                    importance = 0,
                    type = "info",
                    back = True,
                    count = (count, length),
                    header = darkred(" @@  ")
                )

            xdeps = dbconn.retrieveDependencies(idpackage)
            for xdep in xdeps:
                xid, xuseless = self.atom_match(xdep)
                if xid == -1:
                    deps_not_satisfied.add(xdep)

        return deps_not_satisfied

    def dependencies_test(self, repo = None):

        mytxt = "%s %s" % (blue(_("Running dependencies test")), red("..."))
        self.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        server_repos = srv_set['repositories'].keys()
        deps_not_matched = self.deps_tester(repo)

        if deps_not_matched:

            crying_atoms = {}
            for atom in deps_not_matched:
                for repo in server_repos:
                    dbconn = self.open_server_repository(just_reading = True,
                        repo = repo, do_treeupdates = False)
                    riddep = dbconn.searchDependency(atom)
                    if riddep == -1:
                        continue
                    ridpackages = dbconn.searchIdpackageFromIddependency(riddep)
                    for i in ridpackages:
                        iatom = dbconn.retrieveAtom(i)
                        if not crying_atoms.has_key(atom):
                            crying_atoms[atom] = set()
                        crying_atoms[atom].add((iatom, repo))

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
                    for my_dep, myrepo in crying_atoms[atom]:
                        self.updateProgress(
                            "[%s:%s] %s" % (
                                blue(_("by repo")),
                                darkred(myrepo),
                                darkgreen(my_dep),
                            ),
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

    def test_shared_objects(self, get_files = False, repo = None):

        # load db
        dbconn = self.open_server_repository(read_only = True,
            no_upload = True, repo = repo)
        QA = self.QA()
        packages_matched, brokenexecs, status = QA.test_shared_objects(dbconn,
            broken_symbols = True)
        if status != 0:
            return 1, None

        if get_files:
            return 0, brokenexecs

        if (not brokenexecs) and (not packages_matched):
            mytxt = "%s." % (_("System is healthy"),)
            self.updateProgress(
                blue(mytxt),
                importance = 2,
                type = "info",
                header = red(" @@ ")
            )
            return 0, None

        mytxt = "%s..." % (_("Matching libraries with Spm, please wait"),)
        self.updateProgress(
            blue(mytxt),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        packages = self.Spm().query_belongs_multiple(brokenexecs)

        if packages:
            mytxt = "%s:" % (_("These are the matched packages"),)
            self.updateProgress(
                red(mytxt),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
            for my_atom, my_elf_id in packages:
                package_slot = my_atom, my_elf_id
                self.updateProgress(
                    "%s [elf:%s]" % (
                        purple(my_atom),
                        darkgreen(str(my_elf_id)),
                    ),
                    importance = 0,
                    type = "info",
                    header = red("     # ")
                )
                for filename in sorted(list(packages[package_slot])):
                    self.updateProgress(
                        darkgreen(filename),
                        importance = 0,
                        type = "info",
                        header = brown("       => ")
                    )
            # print string
            pkgstring = ' '.join(["%s:%s" % (
                self.entropyTools.dep_getkey(x[0]), x[1],) for x \
                    in sorted(packages)])
            mytxt = "%s: %s" % (darkgreen(_("Packages string")), pkgstring,)
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

        return 0, packages

    def orphaned_spm_packages_test(self):

        mytxt = "%s %s" % (
            blue(_("Running orphaned SPM packages test")), red("..."),)
        self.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        installed_packages, length = self.Spm().get_installed_packages()
        not_found = {}
        count = 0
        for installed_package in installed_packages:
            count += 1
            self.updateProgress(
                "%s: %s" % (
                    darkgreen(_("Scanning package")),
                    brown(installed_package),),
                importance = 0,
                type = "info",
                back = True,
                count = (count, length),
                header = darkred(" @@ ")
            )
            key, slot = (self.entropyTools.dep_getkey(installed_package),
                self.Spm().get_installed_package_slot(installed_package),)
            pkg_atom = "%s:%s" % (key, slot,)
            tree_atom = self.Spm().get_best_atom(pkg_atom)
            if not tree_atom:
                not_found[installed_package] = pkg_atom
                self.updateProgress(
                    "%s: %s" % (
                        blue(pkg_atom),
                        darkred(_("not found anymore")),
                    ),
                    importance = 0,
                    type = "warning",
                    count = (count, length),
                    header = darkred(" @@ ")
                )

        if not_found:
            not_found_list = ' '.join([not_found[x] for x in sorted(not_found)])
            self.updateProgress(
                "%s: %s" % (
                        blue(_("Packages string")),
                        not_found_list,
                    ),
                importance = 0,
                type = "warning",
                count = (count, length),
                header = darkred(" @@ ")
            )

        return not_found

    def depends_table_initialize(self, repo = None):
        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo)
        dbconn.regenerateReverseDependenciesMetadata()
        dbconn.taintDatabase()
        dbconn.commitChanges()

    def library_paths_table_initialize(self, repo = None):
        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo)
        dbconn.regenerateLibrarypathsidpackageTable()
        dbconn.taintDatabase()
        dbconn.commitChanges()

    def create_empty_database(self, dbpath = None, repo = None):
        if dbpath == None:
            dbpath = self.get_local_database_file(repo)

        dbdir = os.path.dirname(dbpath)
        if not os.path.isdir(dbdir):
            os.makedirs(dbdir)

        mytxt = red("%s ...") % (_("Initializing an empty database"),)
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
        mytxt = "%s %s %s." % (
            red(_("Entropy database file")),
            bold(dbpath),
            red(_("successfully initialized")),
        )
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
            if " " in package_tag:
                raise ValueError
        except (UnicodeDecodeError, UnicodeEncodeError, ValueError,):
            self.updateProgress(
                "%s: %s" % (
                    blue(_("Invalid tag specified")),
                    package_tag,
                ),
                importance = 1, type = "error", header = darkred(" !! ")
            )
            return 1, package_tag

        if repo == None:
            repo = self.default_repository

        # sanity check
        invalid_atoms = []
        dbconn = self.open_server_repository(read_only = True,
            no_upload = True, repo = repo)
        for idpackage in idpackages:
            ver_tag = dbconn.retrieveVersionTag(idpackage)
            if ver_tag:
                invalid_atoms.append(dbconn.retrieveAtom(idpackage))

        if invalid_atoms:
            self.updateProgress(
                "%s: %s" % (
                    blue(_("Packages already tagged, action aborted")),
                    ', '.join([darkred(unicode(x)) for x in invalid_atoms]),
                ),
                importance = 1, type = "error", header = darkred(" !! ")
            )
            return 2, invalid_atoms

        matches = [(x, repo) for x in idpackages]
        status = 0
        data = self.move_packages(
            matches, to_repo = repo, from_repo = repo, ask = ask,
            do_copy = True, new_tag = package_tag
        )
        return status, data

    def flushback_packages(self, from_branches, repo = None, ask = True):
        """
        When creating a new branch, for space reasons, packages are not
        moved to a new location. This works fine until old branch is removed.
        To avoid inconsistences, before deciding to do that, all the packages
        in the old branch should be flushed back to the the currently configured
        branch.

        @param from_branches -- list of branches to move packages from
        @type from_branches -- list
        @param repo -- repository to work on
        @type repo -- str
        @param ask -- user interactivity
        @type ask -- bool

        @return status
        """

        status = True
        if repo == None:
            repo = self.default_repository
        branch = self.SystemSettings['repositories']['branch']

        if branch in from_branches:
            from_branches = [x for x in from_branches if x != branch]

        self.updateProgress(
            "[%s=>%s|%s] %s" % (
                darkgreen(', '.join(from_branches)),
                darkred(branch),
                brown(repo),
                blue(_("flushing back selected packages from branches")),
            ),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        dbconn = self.open_server_repository(read_only = True,
            no_upload = True, repo = repo)

        idpackage_map = dict(((x, [],) for x in from_branches))
        idpackages = dbconn.listAllIdpackages(order_by = 'atom')
        for idpackage in idpackages:
            download_url = dbconn.retrieveDownloadURL(idpackage)
            url_br = self.ClientService.get_branch_from_download_relative_uri(
                download_url)
            if url_br in from_branches:
                idpackage_map[url_br].append(idpackage)

        mapped_branches = [x for x in idpackage_map if idpackage_map[x]]
        if not mapped_branches:
            self.updateProgress(
                "[%s=>%s|%s] %s !" % (
                    darkgreen(', '.join(from_branches)),
                    darkred(branch),
                    brown(repo),
                    blue(_("nothing to do")),
                ),
                importance = 0,
                type = "warning",
                header = blue(" @@ ")
            )
            return status


        all_fine = True
        tmp_down_dir = self.entropyTools.get_random_temp_file()
        os.makedirs(tmp_down_dir)

        download_queue = {}
        local_up_dir = self.get_local_upload_directory(repo)
        local_basedir = os.path.join(local_up_dir, branch)
        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo)

        def generate_queue(branch, repo, from_branch, down_q, idpackage_map):

            self.updateProgress(
                "[%s=>%s|%s] %s" % (
                    darkgreen(from_branch),
                    darkred(branch),
                    brown(repo),
                    brown(_("these are the packages that will be flushed")),
                ),
                importance = 1,
                type = "info",
                header = brown(" @@ ")
            )


            for idpackage in idpackage_map[from_branch]:
                atom = dbconn.retrieveAtom(idpackage)
                self.updateProgress(
                    "[%s=>%s|%s] %s" % (
                        darkgreen(from_branch),
                        darkred(branch),
                        brown(repo),
                        purple(atom),
                    ),
                    importance = 0,
                    type = "info",
                    header = blue("  # ")
                )
                pkg_fp = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
                pkg_fp = os.path.join(tmp_down_dir, pkg_fp)
                down_q.append((pkg_fp, idpackage,))


        for from_branch in sorted(mapped_branches):

            download_queue[from_branch] = []
            all_fine = False
            generate_queue(branch, repo, from_branch,
                download_queue[from_branch], idpackage_map)

            if ask:
                rc_question = self.askQuestion(
                    _("Would you like to continue ?"))
                if rc_question == "No":
                    continue

            remote_relative_path = self.get_remote_packages_relative_path(repo)

            for uri in self.get_remote_mirrors(repo):

                crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
                ftp_basedir = os.path.join(remote_relative_path, from_branch)

                downloader_queue = [x[0] for x in download_queue[from_branch]]
                downloader = self.MirrorsService.FtpServerHandler(
                    FtpInterface,
                    self,
                    [uri],
                    downloader_queue,
                    critical_files = downloader_queue,
                    use_handlers = True,
                    ftp_basedir = ftp_basedir,
                    local_basedir = tmp_down_dir,
                    download = True,
                    repo = repo
                )

                errors, m_fine_uris, m_broken_uris = downloader.go()

                if not errors:
                    for downloaded_path, idpackage in \
                        download_queue[from_branch]:

                        self.updateProgress(
                            "[%s=>%s|%s|%s] %s: %s" % (
                                darkgreen(from_branch),
                                darkred(branch),
                                brown(repo),
                                dbconn.retrieveAtom(idpackage),
                                blue(_("checking package hash")),
                                darkgreen(os.path.basename(downloaded_path)),
                            ),
                            importance = 0,
                            type = "info",
                            header = brown("   "),
                            back = True
                        )

                        md5hash = self.entropyTools.md5sum(downloaded_path)
                        db_md5hash = dbconn.retrieveDigest(idpackage)
                        if md5hash != db_md5hash:
                            errors = True
                            self.updateProgress(
                                "[%s=>%s|%s|%s] %s: %s" % (
                                    darkgreen(from_branch),
                                    darkred(branch),
                                    brown(repo),
                                    dbconn.retrieveAtom(idpackage),
                                    blue(_("hash does not match for")),
                                    darkgreen(os.path.basename(downloaded_path)),
                                ),
                                importance = 0,
                                type = "error",
                                header = brown("   ")
                            )
                            continue



                if errors:
                    reason = _("wrong md5")
                    if m_broken_uris:
                        my_broken_uris = [
                        (self.entropyTools.extract_ftp_host_from_uri(x), y,) \
                            for x, y in m_broken_uris]
                        reason = my_broken_uris[0][1]

                    self.updateProgress(
                        "[%s=>%s|%s] %s, %s: %s" % (
                            darkgreen(from_branch),
                            darkred(branch),
                            brown(repo),
                            blue(_("download errors")),
                            blue(_("reason")),
                            reason,
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    # continuing if possible
                    continue

                all_fine = True

                self.updateProgress(
                    "[%s=>%s|%s] %s: %s" % (
                        darkgreen(from_branch),
                        darkred(branch),
                        brown(repo),
                        blue(_("download completed successfully")),
                        darkgreen(crippled_uri),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )

        if not all_fine:
            self.updateProgress(
                "[%s=>%s|%s] %s" % (
                    darkgreen(', '.join(from_branches)),
                    darkred(branch),
                    brown(repo),
                    blue(_("error downloading packages from mirrors")),
                ),
                importance = 2,
                type = "error",
                header = darkred(" !!! ")
            )
            return False

        for from_branch in sorted(mapped_branches):

            self.updateProgress(
                "[%s=>%s|%s] %s: %s" % (
                    darkgreen(from_branch),
                    darkred(branch),
                    brown(repo),
                    blue(_("working on branch")),
                    darkgreen(from_branch),
                ),
                importance = 1,
                type = "info",
                header = brown(" @@ ")
            )

            down_queue = download_queue[from_branch]
            for package_path, idpackage in down_queue:

                self.updateProgress(
                    "[%s=>%s|%s] %s: %s" % (
                        darkgreen(from_branch),
                        darkred(branch),
                        brown(repo),
                        blue(_("updating package")),
                        darkgreen(os.path.basename(package_path)),
                    ),
                    importance = 1,
                    type = "info",
                    header = brown("   "),
                    back = True
                )

                # move files to upload
                package_name = os.path.basename(package_path)
                new_package_path = os.path.join(local_basedir, package_name)
                try:
                    os.rename(package_path, new_package_path)
                except OSError:
                    shutil.move(package_path, new_package_path)

                # create md5 checksum
                self.entropyTools.create_md5_file(new_package_path)

                # update database
                download_url = dbconn.retrieveDownloadURL(idpackage)
                download_url = \
                    self.ClientService.swap_branch_in_download_relative_uri(
                        branch, download_url)
                dbconn.setDownloadURL(idpackage, download_url)
                dbconn.switchBranch(idpackage, branch)
                dbconn.commitChanges()

                self.updateProgress(
                    "[%s=>%s|%s] %s: %s" % (
                        darkgreen(from_branch),
                        darkred(branch),
                        brown(repo),
                        blue(_("package flushed")),
                        darkgreen(os.path.basename(package_path)),
                    ),
                    importance = 1,
                    type = "info",
                    header = brown("   ")
                )

        try:
            os.rmdir(tmp_down_dir)
        except OSError:
            pass

        return True

    def move_packages(self, matches, to_repo, from_repo = None, ask = True,
        do_copy = False, new_tag = None, pull_deps = False):

        if from_repo == None:
            from_repo = self.default_repository
        switched = set()

        my_matches = list(matches)

        # avoid setting __default__ as default server repo
        if etpConst['clientserverrepoid'] in (to_repo, from_repo):
            self.updateProgress(
                "%s: %s" % (
                    blue(_("Cannot touch system database")),
                    red(etpConst['clientserverrepoid']),
                ),
                importance = 2, type = "warning", header = darkred(" @@ ")
            )
            return switched

        if not my_matches and from_repo:
            dbconn = self.open_server_repository(read_only = True,
                no_upload = True, repo = from_repo)
            my_matches = set( \
                [(x, from_repo) for x in \
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
                red(_("all old packages with conflicting scope will be " \
                    "removed from destination repo unless injected")),
            ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        new_tag_string = ''
        if new_tag != None:
            new_tag_string = "[%s: %s]" % (darkgreen(_("new tag")),
                brown(new_tag),)

        my_qa = self.QA()
        branch = self.SystemSettings['repositories']['branch']
        pull_deps_matches = []
        for idpackage, repo in my_matches:
            dbconn = self.open_server_repository(read_only = True,
                no_upload = True, repo = repo)
            self.updateProgress(
                "[%s=>%s|%s] %s " % (
                        darkgreen(repo),
                        darkred(to_repo),
                        brown(branch),
                        blue(dbconn.retrieveAtom(idpackage)),
                ) + new_tag_string,
                importance = 0,
                type = "info",
                header = brown("    # ")
            )
            # do we want to pull in also package dependencies?
            if pull_deps:
                dep_idpackages = my_qa.get_deep_dependency_list(dbconn,
                    idpackage)
                for dep_idpackage in dep_idpackages:

                    my_dep_match = (dep_idpackage, repo,)
                    if my_dep_match in pull_deps_matches:
                        continue
                    if my_dep_match in my_matches:
                        continue

                    pull_deps_matches.append(my_dep_match)
                    self.updateProgress(
                        "[%s|%s] %s" % (
                            brown(branch),
                            blue(_("dependency")),
                            purple(dbconn.retrieveAtom(dep_idpackage)),
                        ),
                        importance = 0,
                        type = "info",
                        header = purple("    >> ")
                    )

        if pull_deps:
            # put deps first!
            my_matches = pull_deps_matches + [x for x in my_matches if x not \
                in pull_deps_matches]

        if ask:
            rc_question = self.askQuestion(_("Would you like to continue ?"))
            if rc_question == "No":
                return switched

        for idpackage, repo in my_matches:
            dbconn = self.open_server_repository(read_only = False,
                no_upload = True, repo = repo)
            match_branch = dbconn.retrieveBranch(idpackage)
            match_atom = dbconn.retrieveAtom(idpackage)
            package_filename = os.path.basename(
                dbconn.retrieveDownloadURL(idpackage))
            self.updateProgress(
                "[%s=>%s|%s] %s: %s" % (
                        darkgreen(repo),
                        darkred(to_repo),
                        brown(branch),
                        blue(_("switching")),
                        darkgreen(match_atom),
                ),
                importance = 0,
                type = "info",
                header = red(" @@ "),
                back = True
            )
            # move binary file
            from_file = os.path.join(self.get_local_packages_directory(repo),
                match_branch, package_filename)
            if not os.path.isfile(from_file):
                from_file = os.path.join(self.get_local_upload_directory(repo),
                    match_branch, package_filename)
            if not os.path.isfile(from_file):
                self.updateProgress(
                    "[%s=>%s|%s] %s: %s -> %s" % (
                        darkgreen(repo),
                        darkred(to_repo),
                        brown(branch),
                        bold(_("cannot switch, package not found, skipping")),
                        darkgreen(match_atom),
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
                tagged_package_filename = \
                    self.entropyTools.create_package_filename(
                        match_category, match_name, match_version, new_tag)
                to_file = os.path.join(self.get_local_upload_directory(to_repo),
                    match_branch, tagged_package_filename)
            else:
                to_file = os.path.join(self.get_local_upload_directory(to_repo),
                    match_branch, package_filename)
            if not os.path.isdir(os.path.dirname(to_file)):
                os.makedirs(os.path.dirname(to_file))

            copy_data = [
                (from_file, to_file,),
                (from_file + etpConst['packagesmd5fileext'],
                    to_file + etpConst['packagesmd5fileext'],),
                (from_file + etpConst['packagesexpirationfileext'],
                    to_file + etpConst['packagesexpirationfileext'],)
            ]

            for from_item, to_item in copy_data:
                self.updateProgress(
                        "[%s=>%s|%s] %s: %s" % (
                            darkgreen(repo),
                            darkred(to_repo),
                            brown(branch),
                            blue(_("moving file")),
                            darkgreen(os.path.basename(from_item)),
                        ),
                        importance = 0,
                        type = "info",
                        header = red(" @@ "),
                        back = True
                )
                if os.path.isfile(from_item):
                    shutil.copy2(from_item, to_item)

            self.updateProgress(
                "[%s=>%s|%s] %s: %s" % (
                    darkgreen(repo),
                    darkred(to_repo),
                    brown(branch),
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

            todbconn = self.open_server_repository(read_only = False,
                no_upload = True, repo = to_repo)

            self.updateProgress(
                "[%s=>%s|%s] %s: %s" % (
                    darkgreen(repo),
                    darkred(to_repo),
                    brown(branch),
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
                        brown(branch),
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
                    brown(branch),
                    blue(_("successfully handled atom")),
                    darkgreen(match_atom),
                ),
                importance = 0,
                type = "info",
                header = blue(" @@ ")
            )
            switched.add((idpackage, repo,))

        # just run this to make dev aware
        self.dependencies_test(to_repo)

        return switched


    def package_injector(self, package_file, inject = False, repo = None):

        if repo == None:
            repo = self.default_repository

        upload_dir = os.path.join(self.get_local_upload_directory(repo),
            self.SystemSettings['repositories']['branch'])
        if not os.path.isdir(upload_dir):
            os.makedirs(upload_dir)

        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo)
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
        mydata = self.Spm().extract_pkg_metadata(package_file,
            inject = inject)
        idpackage, revision, mydata = dbconn.handlePackage(mydata)

        # set trashed counters
        trashing_counters = set()
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        myserver_repos = srv_set['repositories'].keys()
        for myrepo in myserver_repos:
            mydbconn = self.open_server_repository(read_only = True,
                no_upload = True, repo = myrepo)
            mylist = mydbconn.retrieve_packages_to_remove(
                    mydata['name'],
                    mydata['category'],
                    mydata['slot'],
                    mydata['injected']
            )
            for myitem in mylist:
                trashing_counters.add(mydbconn.retrieveSpmUid(myitem))

        for mycounter in trashing_counters:
            dbconn.setTrashedUid(mycounter)

        # add package info to our current server repository
        dbconn.dropInstalledPackageFromStore(idpackage)
        dbconn.storeInstalledPackage(idpackage, repo)
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

        download_url = self._setup_repository_package_filename(idpackage,
            repo = repo)
        downloadfile = os.path.basename(download_url)
        destination_path = os.path.join(upload_dir, downloadfile)
        try:
            os.rename(package_file, destination_path)
        except OSError:
            shutil.move(package_file, destination_path)

        dbconn.commitChanges()
        return idpackage, destination_path

    # this function changes the final repository package filename
    def _setup_repository_package_filename(self, idpackage, repo = None):

        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo)

        downloadurl = dbconn.retrieveDownloadURL(idpackage)
        packagerev = dbconn.retrieveRevision(idpackage)
        downloaddir = os.path.dirname(downloadurl)
        downloadfile = os.path.basename(downloadurl)
        # add revision
        downloadfile = downloadfile[:-5]+"~%s%s" % (packagerev,
            etpConst['packagesext'],)
        downloadurl = os.path.join(downloaddir, downloadfile)

        # update url
        dbconn.setDownloadURL(idpackage, downloadurl)

        return downloadurl

    def add_packages_to_repository(self, packages_data, ask = True,
        repo = None):

        if repo == None:
            repo = self.default_repository

        mycount = 0
        maxcount = len(packages_data)
        idpackages_added = set()
        to_be_injected = set()
        my_qa = self.QA()
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
                count = (mycount, maxcount,)
            )

            try:
                # add to database
                idpackage, destination_path = self.package_injector(
                    package_filepath,
                    inject = inject,
                    repo = repo
                )
                idpackages_added.add(idpackage)
                to_be_injected.add((idpackage, destination_path))
            except Exception, err:
                self.entropyTools.print_traceback()
                self.updateProgress(
                    "[repo:%s] %s: %s" % (
                        darkgreen(repo),
                        darkred(_("Exception caught, closing tasks")),
                        darkgreen(unicode(err)),
                    ),
                    importance = 1,
                    type = "error",
                    header = bold(" !!! "),
                    count = (mycount, maxcount,)
                )
                # reinit depends table
                self.depends_table_initialize(repo)
                # reinit librarypathsidpackage table
                self.library_paths_table_initialize(repo)
                if idpackages_added:
                    dbconn = self.open_server_repository(read_only = False,
                        no_upload = True, repo = repo)
                    missing_deps_taint = my_qa.test_missing_dependencies(
                        idpackages_added,
                        dbconn,
                        ask = ask,
                        repo = repo,
                        self_check = True,
                        black_list = \
                            self.get_missing_dependencies_blacklist(
                                repo = repo),
                        black_list_adder = \
                            self.add_missing_dependencies_blacklist_items
                    )
                    my_qa.test_depends_linking(idpackages_added, dbconn,
                        repo = repo)
                if to_be_injected:
                    self.inject_database_into_packages(to_be_injected,
                        repo = repo)
                # reinit depends table
                if missing_deps_taint:
                    self.depends_table_initialize(repo)
                self.close_server_databases()
                raise

        # reinit depends table
        self.depends_table_initialize(repo)
        # reinit librarypathsidpackage table
        self.library_paths_table_initialize(repo)

        if idpackages_added:
            dbconn = self.open_server_repository(read_only = False,
                no_upload = True, repo = repo)
            missing_deps_taint = my_qa.test_missing_dependencies(
                idpackages_added,
                dbconn,
                ask = ask,
                repo = repo,
                self_check = True,
                black_list = \
                    self.get_missing_dependencies_blacklist(repo = repo),
                black_list_adder = \
                    self.add_missing_dependencies_blacklist_items
            )
            my_qa.test_depends_linking(idpackages_added, dbconn, repo = repo)

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

        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo)
        for idpackage, package_path in injection_data:
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
            dbpath = self.ClientService.inject_entropy_database_into_package(
                package_path, data, treeupdates_actions)
            digest = self.entropyTools.md5sum(package_path)
            # update digest
            dbconn.setDigest(idpackage, digest)
            # update signatures
            signatures = data['signatures'].copy()
            for hash_key in sorted(signatures):
                hash_func = getattr(self.entropyTools, hash_key)
                signatures[hash_key] = hash_func(package_path)
            dbconn.setSignatures(idpackage, signatures['sha1'],
                signatures['sha256'], signatures['sha512'])
            self.entropyTools.create_md5_file(package_path)
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
            for key in scandata:
                self.updateProgress(
                    "%s" % (brown(etpConst['systemroot'] + \
                        scandata[key]['destination'])),
                    importance = 1,
                    type = "info",
                    header = "\t"
                )
            return True
        return False

    def quickpkg(self, atom, storedir):
        return self.Spm().quickpkg(atom, storedir)


    def remove_packages(self, idpackages, repo = None):

        if repo == None:
            repo = self.default_repository

        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo)
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
        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo)
        dbconn.taintDatabase()
        self.close_server_database(dbconn)

    def get_remote_mirrors(self, repo = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if repo == None:
            repo = self.default_repository
        return srv_set['repositories'][repo]['mirrors'][:]

    def get_remote_packages_relative_path(self, repo = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if repo == None:
            repo = self.default_repository
        return srv_set['repositories'][repo]['packages_relative_path']

    def get_remote_database_relative_path(self, repo = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if repo == None:
            repo = self.default_repository
        return srv_set['repositories'][repo]['database_relative_path']

    def get_local_database_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasefile'])

    def get_local_store_directory(self, repo = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if repo == None:
            repo = self.default_repository
        return srv_set['repositories'][repo]['store_dir']

    def get_local_upload_directory(self, repo = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if repo == None:
            repo = self.default_repository
        return srv_set['repositories'][repo]['upload_dir']

    def get_local_packages_directory(self, repo = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if repo == None:
            repo = self.default_repository
        return srv_set['repositories'][repo]['packages_dir']

    def get_local_database_taint_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasetaintfile'])

    def get_local_database_revision_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabaserevisionfile'])

    def get_local_database_timestamp_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasetimestampfile'])

    def get_local_database_ca_cert_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasecacertfile'])

    def get_local_database_server_cert_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabaseservercertfile'])

    def get_local_database_mask_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasemaskfile'])

    def get_local_database_system_mask_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasesytemmaskfile'])

    def get_local_database_confl_tagged_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabaseconflictingtaggedfile'])

    def get_local_database_licensewhitelist_file(self, repo = None,
        branch = None):

        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabaselicwhitelistfile'])

    def get_local_database_rss_file(self, repo = None, branch = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            srv_set['rss']['name'])

    def get_local_database_rsslight_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['rss-light-name'])

    def get_local_database_notice_board_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['rss-notice-board'])

    def get_local_database_treeupdates_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabaseupdatefile'])

    def get_local_database_compressed_metafiles_file(self, repo = None,
        branch = None):

        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasemetafilesfile'])

    def get_local_database_metafiles_not_found_file(self, repo = None,
        branch = None):

        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasemetafilesnotfound'])

    def get_local_exp_based_pkgs_rm_whitelist_file(self, repo = None,
        branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabaseexpbasedpkgsrm'])

    def get_local_pkglist_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasepkglist'])

    def get_local_database_sets_dir(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['confsetsdirname'])

    def get_local_post_branch_mig_script(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etp_post_branch_hop_script'])

    def get_local_post_branch_upg_script(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etp_post_branch_upgrade_script'])

    def get_local_critical_updates_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasecriticalfile'])

    def get_local_database_keywords_file(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        return os.path.join(self.get_local_database_dir(repo, branch),
            etpConst['etpdatabasekeywordsfile'])

    def get_local_database_dir(self, repo = None, branch = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if repo == None:
            repo = self.default_repository
        if branch == None:
            branch = self.SystemSettings['repositories']['branch']
        return os.path.join(srv_set['repositories'][repo]['database_dir'],
            branch)

    def get_missing_dependencies_blacklist_file(self, repo = None,
        branch = None):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if repo == None:
            repo = self.default_repository
        if branch == None:
            branch = self.SystemSettings['repositories']['branch']
        return os.path.join(srv_set['repositories'][repo]['database_dir'],
            branch, etpConst['etpdatabasemissingdepsblfile'])

    def get_missing_dependencies_blacklist(self, repo = None, branch = None):
        if repo == None:
            repo = self.default_repository
        if branch == None:
            branch = self.SystemSettings['repositories']['branch']
        wl_file = self.get_missing_dependencies_blacklist_file(repo, branch)
        wl_data = []
        if os.path.isfile(wl_file) and os.access(wl_file, os.R_OK):
            f_wl = open(wl_file,"r")
            wl_data = [x.strip() for x in f_wl.readlines() if x.strip() and \
                not x.strip().startswith("#")]
            f_wl.close()
        return set(wl_data)

    def add_missing_dependencies_blacklist_items(self, items, repo = None,
        branch = None):

        if repo == None:
            repo = self.default_repository
        if branch == None:
            branch = self.SystemSettings['repositories']['branch']
        wl_file = self.get_missing_dependencies_blacklist_file(repo, branch)
        wl_dir = os.path.dirname(wl_file)
        if not (os.path.isdir(wl_dir) and os.access(wl_dir, os.W_OK)):
            return
        if os.path.isfile(wl_file) and not os.access(wl_file, os.W_OK):
            return
        f_wl = open(wl_file,"a+")
        f_wl.write('\n'.join(items)+'\n')
        f_wl.flush()
        f_wl.close()

    def get_local_database_revision(self, repo = None):

        if repo == None:
            repo = self.default_repository

        dbrev_file = self.get_local_database_revision_file(repo)
        if os.path.isfile(dbrev_file):
            f_rev = open(dbrev_file)
            rev = f_rev.readline().strip()
            f_rev.close()
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

    def get_current_timestamp(self):
        from datetime import datetime
        import time
        return "%s" % (datetime.fromtimestamp(time.time()),)

    def create_repository_pkglist(self, repo = None, branch = None):
        pkglist_file = self.get_local_pkglist_file(repo = repo, branch = branch)

        tmp_pkglist_file = pkglist_file + ".tmp"
        dbconn = self.open_server_repository(repo = repo, just_reading = True,
            do_treeupdates = False)
        pkglist = dbconn.listAllDownloads(do_sort = True, full_path = True)

        with open(tmp_pkglist_file, "w") as pkg_f:
            for pkg in pkglist:
                pkg_f.write(pkg + "\n")
            pkg_f.flush()

        os.rename(tmp_pkglist_file, pkglist_file)

    def package_set_list(self, *args, **kwargs):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        repos = srv_set['repositories'].keys()
        kwargs['server_repos'] = repos
        kwargs['serverInstance'] = self
        return self.ClientService.package_set_list(*args, **kwargs)

    def package_set_search(self, *args, **kwargs):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        repos = srv_set['repositories'].keys()
        kwargs['server_repos'] = repos
        kwargs['serverInstance'] = self
        return self.ClientService.package_set_search(*args, **kwargs)

    def package_set_match(self, *args, **kwargs):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        repos = srv_set['repositories'].keys()
        kwargs['server_repos'] = repos
        kwargs['serverInstance'] = self
        return self.ClientService.package_set_match(*args, **kwargs)

    def atom_match(self, *args, **kwargs):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        repos = srv_set['repositories'].keys()
        kwargs['server_repos'] = repos
        kwargs['serverInstance'] = self
        return self.ClientService.atom_match(*args, **kwargs)

    def scan_package_changes(self):

        installed_packages = self.Spm().get_installed_packages_counter()
        installed_counters = set()
        to_be_added = set()
        to_be_removed = set()
        to_be_injected = set()
        my_settings = self.SystemSettings[self.sys_settings_plugin_id]['server']
        exp_based_scope = my_settings['exp_based_scope']

        server_repos = my_settings['repositories'].keys()

        # packages to be added
        for spm_atom, spm_counter in installed_packages:
            found = False
            for server_repo in server_repos:
                installed_counters.add(spm_counter)
                server_dbconn = self.open_server_repository(read_only = True,
                    no_upload = True, repo = server_repo)
                counter = server_dbconn.isSpmUidAvailable(spm_counter)
                if counter:
                    found = True
                    break
            if not found:
                to_be_added.add((spm_atom, spm_counter,))

        # packages to be removed from the database
        database_counters = {}
        for server_repo in server_repos:
            server_dbconn = self.open_server_repository(read_only = True,
                no_upload = True, repo = server_repo)
            database_counters[server_repo] = server_dbconn.listAllSpmUids()

        ordered_counters = set()
        for server_repo in database_counters:
            for data in database_counters[server_repo]:
                ordered_counters.add((data, server_repo))
        database_counters = ordered_counters

        for (counter, idpackage,), xrepo in database_counters:

            if counter < 0:
                continue # skip packages without valid counter

            if counter in installed_counters:
                continue

            dbconn = self.open_server_repository(read_only = True,
                no_upload = True, repo = xrepo)

            dorm = True
            # check if the package is in to_be_added
            if to_be_added:

                dorm = False
                atom = dbconn.retrieveAtom(idpackage)
                atomkey = self.entropyTools.dep_getkey(atom)
                atomtag = self.entropyTools.dep_gettag(atom)
                atomslot = dbconn.retrieveSlot(idpackage)

                add = True
                for spm_atom, spm_counter in to_be_added:
                    addslot = self.Spm().get_installed_package_slot(
                        spm_atom)
                    addkey = self.entropyTools.dep_getkey(spm_atom)
                    # workaround for ebuilds not having slot
                    if addslot == None:
                        addslot = '0'
                    # atomtag != None is for handling tagged pkgs correctly
                    if (atomkey == addkey) and \
                        ((str(atomslot) == str(addslot)) or (atomtag != None)):
                        # do not add to to_be_removed
                        add = False
                        break

                if not add:
                    continue
                dorm = True

            # checking if we are allowed to remove stuff on this repo
            # it xrepo is not the default one, we MUST skip this to
            # avoid touching what developer doesn't expect
            if dorm and (xrepo == self.default_repository):
                trashed = self.is_counter_trashed(counter)
                if trashed:
                    # search into portage then
                    try:
                        key, slot = dbconn.retrieveKeySlot(idpackage)
                        trashed = self.Spm().get_installed_atom(
                            key+":"+slot)
                    except TypeError: # referred to retrieveKeySlot
                        trashed = True
                if not trashed:

                    dbtag = dbconn.retrieveVersionTag(idpackage)
                    if dbtag:
                        is_injected = dbconn.isInjected(idpackage)
                        if not is_injected:
                            to_be_injected.add((idpackage, xrepo))

                    elif exp_based_scope:

                        # check if support for this is set
                        plg_id = self.sys_settings_fatscope_plugin_id
                        exp_data = self.SystemSettings[plg_id]['repos'].get(
                            xrepo, set())

                        # only some packages are set, check if our is
                        # in the list
                        if (idpackage not in exp_data) and (-1 not in exp_data):
                            to_be_removed.add((idpackage, xrepo))
                            continue

                        idpackage_expired = self.is_match_expired((idpackage,
                            xrepo,))

                        if idpackage_expired:
                            # expired !!!
                            # add this and its depends (reverse deps)
                            to_be_removed.add((idpackage, xrepo))
                            for my_id in dbconn.retrieveReverseDependencies(
                                idpackage):
                                to_be_removed.add((my_id, xrepo))

                    else:
                        to_be_removed.add((idpackage, xrepo))

        return to_be_added, to_be_removed, to_be_injected

    def is_match_expired(self, match):

        idpackage, repoid = match
        dbconn = self.open_server_repository(repo = repoid, just_reading = True)
        # 3600 * 24 = 86400
        my_settings = self.SystemSettings[self.sys_settings_plugin_id]['server']
        pkg_exp_secs = my_settings['packages_expiration_days'] * 86400
        cur_unix_time = self.entropyTools.get_current_unix_time()
        # if packages removal is triggered by expiration
        # we will have to check if our package is really
        # expired and remove its reverse deps too
        mydate = dbconn.retrieveCreationDate(idpackage)
        # cross fingers hoping that time is set correctly
        mydelta = cur_unix_time - float(mydate)
        if mydelta > pkg_exp_secs:
            return True
        return False

    def is_counter_trashed(self, counter):
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        server_repos = srv_set['repositories'].keys()
        for repo in server_repos:
            dbconn = self.open_server_repository(read_only = True,
                no_upload = True, repo = repo)
            if dbconn.isSpmUidTrashed(counter):
                return True
        return False

    def transform_package_into_injected(self, idpackage, repo = None):
        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo)
        counter = dbconn.getNewNegativeSpmUid()
        dbconn.setSpmUid(idpackage, counter)
        dbconn.setInjected(idpackage)

    def initialize_server_database(self, empty = True, repo = None,
        warnings = True):

        if repo == None:
            repo = self.default_repository

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

            dbconn = self.open_server_repository(read_only = True,
                no_upload = True, repo = repo, warnings = warnings)

            try:
                dbconn.validateDatabase()
                idpackages = dbconn.listAllIdpackages()
            except SystemDatabaseError:
                pass

            try:
                treeupdates_actions = dbconn.listAllTreeUpdatesActions()
            except dbconn.dbapi2.Error:
                pass

            # save list of injected packages
            try:
                injected_packages = dbconn.listAllInjectedPackages(
                    just_files = True)
                injected_packages = set([os.path.basename(x) for x \
                    in injected_packages])
            except dbconn.dbapi2.Error:
                pass

            for idpackage in idpackages:
                url = dbconn.retrieveDownloadURL(idpackage)
                package = os.path.basename(url)
                branch = dbconn.retrieveBranch(idpackage)
                revision = dbconn.retrieveRevision(idpackage)
                revisions_match[package] = (branch, revision,)

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

            rc_question = self.askQuestion(_("Do you want to continue ?"))
            if rc_question == "No":
                return
            try:
                os.remove(self.get_local_database_file(repo))
            except OSError:
                pass


        # initialize
        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo, is_new = True)
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
                f_rev = open(revisions_file,"w")
                f_rev.write(str(revisions_match))
                f_rev.flush()
                f_rev.close()

            # dump treeupdates - as a backup
            treeupdates_file = "/entropy-treeupdates-dump.txt"
            if treeupdates_actions:
                self.updateProgress(
                    "%s: %s" % (
                        # do not translate treeupdates
                        red(_("Dumping current 'treeupdates' actions to file")),
                        bold(treeupdates_file),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                f_tree = open(treeupdates_file,"w")
                f_tree.write(str(treeupdates_actions))
                f_tree.flush()
                f_tree.close()

            rc_question = self.askQuestion(
                _("Would you like to sync packages first (important!) ?"))
            if rc_question == "Yes":
                self.MirrorsService.sync_packages(repo = repo)

            # fill tree updates actions
            if treeupdates_actions:
                dbconn.bumpTreeUpdatesActions(treeupdates_actions)

            # now fill the database
            pkg_branch_dir = os.path.join(
                self.get_local_packages_directory(repo),
                self.SystemSettings['repositories']['branch'])
            pkglist = os.listdir(pkg_branch_dir)
            # filter .md5 and .expired packages
            pkg_ext_len = len(etpConst['packagesext'])
            pkglist = [x for x in pkglist if (x[(pkg_ext_len*-1):] == \
                etpConst['packagesext']) and not \
                os.path.isfile(os.path.join(pkg_branch_dir,
                    x + etpConst['packagesexpirationfileext']))]

            if pkglist:
                self.updateProgress(
                    "%s '%s' %s %s" % (
                        red(_("Reinitializing Entropy database for branch")),
                        bold(self.SystemSettings['repositories']['branch']),
                        red(_("using Packages in the repository")),
                        red("..."),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )

            counter = 0
            maxcount = len(pkglist)
            branch = self.SystemSettings['repositories']['branch']
            for pkg in pkglist:
                counter += 1

                self.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                        darkgreen(repo),
                        brown(branch),
                        blue(_("analyzing")),
                        bold(pkg),
                    ),
                    importance = 1,
                    type = "info",
                    header = " ",
                    back = True,
                    count = (counter, maxcount,)
                )

                doinject = False
                if pkg in injected_packages:
                    doinject = True

                pkg_path = os.path.join(self.get_local_packages_directory(repo),
                    branch, pkg)
                mydata = self.Spm().extract_pkg_metadata(pkg_path,
                    inject = doinject)

                # get previous revision
                revision_avail = revisions_match.get(pkg)
                add_revision = 0
                if (revision_avail != None):
                    if branch == revision_avail[0]:
                        add_revision = revision_avail[1]

                idpackage, revision, mydata_upd = dbconn.addPackage(mydata,
                    revision = add_revision)
                idpackages_added.add(idpackage)

                self.updateProgress(
                    "[repo:%s] [%s:%s/%s] %s: %s, %s: %s" % (
                            repo,
                            brown(branch),
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
            self.library_paths_table_initialize(repo)

            my_qa = self.QA()

            if idpackages_added:
                dbconn = self.open_server_repository(read_only = False,
                    no_upload = True, repo = repo)
                my_qa.test_missing_dependencies(
                    idpackages_added, dbconn, ask = True,
                    repo = repo, self_check = True,
                    black_list = \
                        self.get_missing_dependencies_blacklist(repo = repo),
                    black_list_adder = \
                        self.add_missing_dependencies_blacklist_items
                )

        dbconn.commitChanges()
        self.close_server_databases()

        return 0

    def match_packages(self, packages, repo = None):

        dbconn = self.open_server_repository(read_only = True,
            no_upload = True, repo = repo)
        if ("world" in packages) or not packages:
            return dbconn.listAllIdpackages(), True
        else:
            idpackages = set()
            for package in packages:
                matches = dbconn.atomMatch(package, multiMatch = True)
                if matches[1] == 0:
                    idpackages |= matches[0]
                else:
                    mytxt = "%s: %s: %s" % (
                        red(_("Attention")),
                        blue(_("cannot match")),
                        bold(package),
                    )
                    self.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "warning",
                        header = darkred(" !!! ")
                    )
            return idpackages, False

    def get_remote_package_checksum(self, repo, filename, branch):

        import urllib2
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if not srv_set['repositories'][repo].has_key('handler'):
            return None
        url = srv_set['repositories'][repo]['handler']

        # does the package has "#" (== tag) ? hackish thing that works
        filename = filename.replace("#","%23")
        # "+"
        filename = filename.replace("+","%2b")
        request = os.path.join(url, etpConst['handlers']['md5sum'])
        request += filename+"&branch="+branch

        proxy_settings = self.SystemSettings['system']['proxy']
        try:
            mydict = {}
            if proxy_settings['ftp']:
                mydict['ftp'] = proxy_settings['ftp']
            if proxy_settings['http']:
                mydict['http'] = proxy_settings['http']
            if mydict:
                mydict['username'] = proxy_settings['username']
                mydict['password'] = proxy_settings['password']
                self.entropyTools.add_proxy_opener(urllib2, mydict)
            else:
                # unset
                urllib2._opener = None
            item = urllib2.urlopen(request)
            result = item.readline().strip()
            item.close()
            del item
            return result
        except (urllib2.URLError, urllib2.HTTPError,): # no HTTP support?
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
        dbconn = self.open_server_repository(read_only = True, no_upload = True,
            repo = repo)
        branch = self.SystemSettings['repositories']['branch']

        if world:
            self.updateProgress(
                blue(
                    _("All the packages in repository will be checked.")),
                importance = 1,
                type = "info",
                header = "    "
            )
        else:
            mytxt = red("%s:") % (
                _("This is the list of the packages that would be checked"),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = "    "
            )
            for idpackage in idpackages:
                pkgatom = dbconn.retrieveAtom(idpackage)
                down_url = dbconn.retrieveDownloadURL(idpackage)
                pkgfile = os.path.basename(down_url)
                self.updateProgress(
                    red(pkgatom) + " -> " + bold(os.path.join(branch, pkgfile)),
                    importance = 1,
                    type = "info",
                    header = darkgreen("   - ")
                )

        if ask:
            rc_question = self.askQuestion(
                _("Would you like to continue ?"))
            if rc_question == "No":
                return set(), set(), {}

        match = set()
        not_match = set()
        broken_packages = {}

        for uri in self.get_remote_mirrors(repo):

            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
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
                orig_branch = self.get_branch_from_download_relative_uri(
                    pkgfile)

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
                    count = (currentcounter, totalcounter,)
                )

                checksum_ok = False
                ck_remote = self.get_remote_package_checksum(repo,
                    os.path.basename(pkgfile), orig_branch)
                if ck_remote == None:
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
                        count = (currentcounter, totalcounter,)
                    )
                elif len(ck_remote) == 32:
                    pkghash = dbconn.retrieveDigest(idpackage)
                    if ck_remote == pkghash:
                        checksum_ok = True
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
                        count = (currentcounter, totalcounter,)
                    )

                if checksum_ok:
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
                        count = (currentcounter, totalcounter,)
                    )
                    if not broken_packages.has_key(crippled_uri):
                        broken_packages[crippled_uri] = []
                    broken_packages[crippled_uri].append(pkgfile)

            if broken_packages:
                mytxt = blue("%s:") % (
                    _("This is the list of broken packages"),)
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = red(" * ")
                )
                for mirror in broken_packages.keys():
                    mytxt = "%s: %s" % (
                        brown(_("Mirror")),
                        bold(mirror),
                    )
                    self.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "info",
                        header = red("   <> ")
                    )
                    for broken_package in broken_packages[mirror]:
                        self.updateProgress(
                            blue(broken_package),
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
                    brown(str(len(match) + len(not_match))),
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
        dbconn = self.open_server_repository(read_only = True,
            no_upload = True, repo = repo)

        if world:
            self.updateProgress(
                blue(_("All the packages in repository will be checked.")),
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

            bindir_path = os.path.join(self.get_local_packages_directory(repo),
                pkg_rel_path)
            uploaddir_path = os.path.join(self.get_local_upload_directory(repo),
                pkg_rel_path)

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
                to_download.add((idpackage, pkg_path,))

        if ask:
            rc_question = self.askQuestion(_("Would you like to continue ?"))
            if rc_question == "No":
                return set(), set(), set(), set()


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
                    mytxt = blue("%s ...") % (
                        _("Searching missing/broken files on another mirror"),)
                    self.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "info",
                        header = "   "
                    )
                    to_download = not_downloaded.copy()
                    not_downloaded = set()

                for idpackage, pkg_path in to_download:
                    rc_down = self.MirrorsService.download_package(uri,
                        pkg_path, repo = repo)
                    if rc_down:
                        downloaded_fine.add(idpackage)
                        available.add(idpackage)
                    else:
                        not_downloaded.add(pkg_path)

                if not not_downloaded:
                    self.updateProgress(
                        red(_("Binary packages downloaded successfully.")),
                        importance = 1,
                        type = "info",
                        header = "   "
                    )
                    break

            if not_downloaded:
                mytxt = blue("%s:") % (
                    _("These are the packages that cannot be found online"),)
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

        my_qa = self.QA()

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
                        blue(_("checking status of")),
                        darkgreen(pkgfile),
                ),
                importance = 1,
                type = "info",
                header = "   ",
                back = True,
                count = (currentcounter, totalcounter,)
            )

            storedmd5 = dbconn.retrieveDigest(idpackage)
            pkgpath = os.path.join(self.get_local_packages_directory(repo),
                orig_branch, pkgfile)
            result = self.entropyTools.compare_md5(pkgpath, storedmd5)
            qa_fine = my_qa.entropy_package_checks(pkgpath)
            if result and qa_fine:
                fine.add(idpackage)
            else:
                failed.add(idpackage)
                self.updateProgress(
                    "[branch:%s] %s %s %s: %s" % (
                            brown(orig_branch),
                            blue(_("package")),
                            darkgreen(pkg_path),
                            blue(_("is corrupted, stored checksum")),
                            brown(storedmd5),
                    ),
                    importance = 1,
                    type = "info",
                    header = "   ",
                    count = (currentcounter, totalcounter,)
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
                down_p = dbconn.retrieveDownloadURL(idpackage)
                self.updateProgress(
                        blue("[atom:%s] %s" % (atom, down_p,)),
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
            brown("%s => %s" % (
                    len(fine) + len(failed),
                    _("checked packages"),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            darkgreen("%s => %s" % (
                    len(fine),
                    _("healthy packages"),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            darkred("%s => %s" % (
                    len(failed),
                    _("broken packages"),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            blue("%s => %s" % (
                    len(downloaded_fine),
                    _("downloaded packages"),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            bold("%s => %s" % (
                    len(downloaded_errors),
                    _("failed downloads"),
                )
            ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )

        self.close_server_database(dbconn)
        return fine, failed, downloaded_fine, downloaded_errors


    def switch_packages_branch(self, from_branch, to_branch, repo = None):

        if repo == None:
            repo = self.default_repository

        if to_branch != self.SystemSettings['repositories']['branch']:
            mytxt = "%s: %s %s" % (
                blue(_("Please setup your branch to")),
                bold(to_branch),
                blue(_("and retry")),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = darkred(" !! ")
            )
            return None

        mytxt = red("%s ...") % (_("Copying database (if not exists)"),)
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = darkgreen(" @@ ")
        )
        branch_dbdir = self.get_local_database_dir(repo)
        old_branch_dbdir = self.get_local_database_dir(repo, from_branch)

        # close all our databases
        self.close_server_databases()

        # if database file did not exist got created as an empty file
        # we can just rm -rf it
        branch_dbfile = self.get_local_database_file(repo)
        if os.path.isfile(branch_dbfile):
            if self.entropyTools.get_file_size(branch_dbfile) == 0:
                shutil.rmtree(branch_dbdir, True)

        if os.path.isdir(branch_dbdir):

            while 1:
                rnd_num = self.entropyTools.get_random_number()
                backup_dbdir = branch_dbdir + str(rnd_num)
                if not os.path.isdir(backup_dbdir):
                    break
            os.rename(branch_dbdir, backup_dbdir)

        if os.path.isdir(old_branch_dbdir):
            shutil.copytree(old_branch_dbdir, branch_dbdir)

        mytxt = red("%s ...") % (_("Switching packages"),)
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = darkgreen(" @@ ")
        )

        dbconn = self.open_server_repository(read_only = False,
            no_upload = True, repo = repo, lock_remote = False)
        try:
            dbconn.validateDatabase()
        except SystemDatabaseError:
            self.handle_uninitialized_repository(repo)
            dbconn = self.open_server_repository(read_only = False,
                no_upload = True, repo = repo, lock_remote = False)

        idpackages = dbconn.listAllIdpackages()
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
                    count = (count, maxcount,)
                )
                ignored.add(idpackage)
                continue

            self.updateProgress(
                "[%s=>%s] %s" % (
                    brown(cur_branch),
                    bold(to_branch),
                    darkgreen(atom),
                ),
                importance = 0,
                type = "info",
                header = darkgreen(" @@ "),
                back = True,
                count = (count, maxcount,)
            )
            dbconn.switchBranch(idpackage, to_branch)
            dbconn.commitChanges()
            switched.add(idpackage)

        dbconn.commitChanges()

        # now migrate counters
        dbconn.moveSpmUidsToBranch(to_branch, from_branch = from_branch)

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

    def get_entropy_sets(self, repo = None, branch = None):

        if branch == None:
            branch = self.SystemSettings['repositories']['branch']
        if repo == None:
            repo = self.default_repository

        sets_dir = self.get_local_database_sets_dir(repo, branch)
        if not (os.path.isdir(sets_dir) and os.access(sets_dir, os.R_OK)):
            return {}

        mydata = {}
        items = os.listdir(sets_dir)
        for item in items:

            try:
                item_clean = str(item)
            except (UnicodeEncodeError, UnicodeDecodeError,):
                continue
            item_path = os.path.join(sets_dir, item)
            if not (os.path.isfile(item_path) and \
                os.access(item_path, os.R_OK)):
                continue
            item_elements = self.entropyTools.extract_packages_from_set_file(
                item_path)
            if item_elements:
                mydata[item_clean] = item_elements.copy()

        return mydata

    def get_configured_package_sets(self, repo = None, branch = None,
        validate = True):

        if branch == None:
            branch = self.SystemSettings['repositories']['branch']
        if repo == None:
            repo = self.default_repository

        # portage sets
        sets_data = self.Spm().get_sets_expanded(builtin_sets = False)
        sets_data.update(self.get_entropy_sets(repo, branch))

        if validate:
            invalid_sets = set()
            # validate
            for setname in sets_data:
                good = True
                for atom in sets_data[setname]:
                    dbconn = self.open_server_repository(just_reading = True,
                        repo = repo)
                    match = dbconn.atomMatch(atom)
                    if match[0] == -1:
                        good = False
                        break
                if not good:
                    invalid_sets.add(setname)
            for invalid_set in invalid_sets:
                del sets_data[invalid_set]

        return sets_data

    def update_database_package_sets(self, repo = None, dbconn = None):

        if repo == None:
            repo = self.default_repository
        package_sets = self.get_configured_package_sets(repo)
        if dbconn == None:
            dbconn = self.open_server_repository(
                read_only = False, no_upload = True, repo = repo,
                do_treeupdates = False)
        dbconn.clearPackageSets()
        if package_sets:
            dbconn.insertPackageSets(package_sets)
        dbconn.commitChanges()
