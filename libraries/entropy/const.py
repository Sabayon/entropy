'''
    # DESCRIPTION:
    # Variables container

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
# pylint ok

from __future__ import with_statement
import sys, os, stat
from entropy.i18n import _
import gzip
import bz2

# ETP_ARCH_CONST setup
ETP_ARCH_CONST = "x86"
if os.uname()[4] == "x86_64":
    ETP_ARCH_CONST = "amd64"

etpSys = {
    'archs': ["x86", "amd64"],
    'api': '3',
    'arch': ETP_ARCH_CONST,
    'rootdir': "",
    'maxthreads': 100,
    'dirstoclean': set(),
    'serverside': False,
    'killpids': set()
}

etpUi = {
    'debug': False,
    'quiet': False,
    'verbose': False,
    'ask': False,
    'pretend': False,
    'mute': False,
    'nolog': False,
    'clean': False,
}
if "--debug" in sys.argv:
    etpUi['debug'] = True

# static logging stuff
ETP_LOGLEVEL_NORMAL = 1
ETP_LOGLEVEL_VERBOSE = 2
ETP_LOGPRI_INFO = "[ INFO ]"
ETP_LOGPRI_WARNING = "[ WARNING ]"
ETP_LOGPRI_ERROR = "[ ERROR ]"

# disk caching dictionary
etpCache = {
    # used to store information about files that
    # should be merged using "equo conf merge"
    'configfiles': 'conf/scanfs',
    'dbMatch': 'match/db', # db atom match cache
    'dbSearch': 'search/db', # db search cache
    # used to store info about repository dependencies solving
    'atomMatch': 'atom_match/atom_match_',
    'install': 'resume/resume_install', # resume cache (install)
    'remove': 'resume/resume_remove', # resume cache (remove)
    'world': 'resume/resume_world', # resume cache (world)
    'world_update': 'world_update/world_cache_',
    'world_available': 'world_available/available_cache_',
    'check_package_update': 'check_update/package_update_',
    'advisories': 'security/advisories_cache_',
    'dep_tree': 'deptree/dep_tree_',
    'depends_tree': 'depends/depends_tree_',
    'filter_satisfied_deps': 'depfilter/filter_satisfied_deps_',
    'library_breakage': 'libs_break/library_breakage_',
    'repolist': 'repos/repolist',
    'repository_server': 'reposerver/item',
    'eapi3_fetch': 'eapi3/segment_',
    'ugc_votes': 'ugc/ugc_votes',
    'ugc_downloads': 'ugc/ugc_downloads',
    'ugc_docs': 'ugc/ugc_docs',
    'ugc_srv_cache': 'ugc/ugc_srv_cache'
}

etpConst = {}

def initconfig_entropy_constants(rootdir):

    """
    Main constants configurators, this is the only function that you should
    call from the outside, everytime you want. it will reset all the variables
    excluding those backed up previously.

    @param rootdir current root directory, if any, or ""
    @type rootdir str
    @return None
    """

    if rootdir and not os.path.isdir(rootdir):
        raise AttributeError("FileNotFound: not a valid chroot.")

    # save backed up settings
    if etpConst.has_key('backed_up'):
        backed_up_settings = etpConst.pop('backed_up')
    else:
        backed_up_settings = {}

    const_default_settings(rootdir)
    const_read_entropy_release()
    const_create_working_dirs()
    const_setup_entropy_pid()
    const_configure_lock_paths()

    # reflow back settings
    etpConst.update(backed_up_settings)
    etpConst['backed_up'] = backed_up_settings.copy()

    if sys.excepthook == sys.__excepthook__:
        sys.excepthook = const_handle_exception

def initConfig_entropyConstants(rootdir):
    """
    @deprecated
    Please use initconfig_entropy_constants
    """
    import warnings
    warnings.warn("deprecated please use initconfig_entropy_constants")
    return initconfig_entropy_constants(rootdir)

def const_default_settings(rootdir):

    """
    Initialization of all the Entropy base settings.

    @param rootdir current root directory, if any, or ""
    @type rootdir str
    @return None
    """

    default_etp_dir = rootdir+"/var/lib/entropy"
    default_etp_tmpdir = "/tmp"
    default_etp_repodir = "/packages/"+ETP_ARCH_CONST
    default_etp_portdir = rootdir+"/usr/portage"
    default_etp_distfilesdir = "/distfiles"
    default_etp_dbdir = "/database/"+ETP_ARCH_CONST
    default_etp_dbfile = "packages.db"
    default_etp_dbclientfile = "equo.db"
    default_etp_client_repodir = "/client"
    default_etp_triggersdir = "/triggers/"+ETP_ARCH_CONST
    default_etp_smartappsdir = "/smartapps/"+ETP_ARCH_CONST
    default_etp_smartpackagesdir = "/smartpackages/"+ETP_ARCH_CONST
    default_etp_cachesdir = "/caches/"
    default_etp_securitydir = "/glsa/"
    default_etp_setsdirname = "sets"
    default_etp_setsdir = "/%s/" % (default_etp_setsdirname,)
    default_etp_logdir = default_etp_dir+"/"+"logs"
    default_etp_confdir = rootdir+"/etc/entropy"
    default_etp_packagesdir = default_etp_confdir+"/packages"
    default_etp_ugc_confdir = default_etp_confdir+"/ugc"
    default_etp_syslogdir = rootdir+"/var/log/entropy/"
    default_etp_vardir = rootdir+"/var/tmp/entropy"
    edb_counter = rootdir+"/var/cache/edb/counter"

    cmdline = []
    cmdline_file = "/proc/cmdline"
    if os.access(cmdline_file, os.R_OK) and os.path.isfile(cmdline_file):
        with open(cmdline_file, "r") as cmdline_f:
            cmdline = cmdline_f.readline().strip().split()

    etpConst.clear()
    my_const = {
        'server_repositories': {},
        'community': {
            'mode': False,
        },
        'cmdline': cmdline,
        'backed_up': {},
        # entropy default installation directory
        'installdir': '/usr/lib/entropy',
        # etpConst['packagestmpdir'] --> temp directory
        'packagestmpdir': default_etp_dir+default_etp_tmpdir,
        # etpConst['packagesbindir'] --> repository
        # where the packages will be stored
        # by clients: to query if a package has been already downloaded
        # by servers or rsync mirrors: to store already
        #   uploaded packages to the main rsync server
        'packagesbindir': default_etp_dir+default_etp_repodir,
        # etpConst['smartappsdir'] location where smart apps files are places
        'smartappsdir': default_etp_dir+default_etp_smartappsdir,
        # etpConst['smartpackagesdir'] location where
        # smart packages files are places
        'smartpackagesdir': default_etp_dir+default_etp_smartpackagesdir,
        # etpConst['triggersdir'] location where external triggers are placed
        'triggersdir': default_etp_dir+default_etp_triggersdir,
        # directory where is stored our local portage tree
        'portagetreedir': default_etp_portdir,
        # directory where our sources are downloaded
        'distfilesdir': default_etp_portdir+default_etp_distfilesdir,
        # directory where entropy stores its configuration
        'confdir': default_etp_confdir,
        # same as above + /packages
        'confpackagesdir': default_etp_packagesdir,
        # system package sets dir
        'confsetsdir': default_etp_packagesdir+default_etp_setsdir,
        # just the dirname
        'confsetsdirname': default_etp_setsdirname,
        # entropy.conf file
        'entropyconf': default_etp_confdir+"/entropy.conf",
        # repositories.conf file
        'repositoriesconf': default_etp_confdir+"/repositories.conf",
        # server.conf file (generic server side settings)
        'serverconf': default_etp_confdir+"/server.conf",
        # client.conf file (generic entropy client side settings)
        'clientconf': default_etp_confdir+"/client.conf",
        # socket.conf file
        'socketconf': default_etp_confdir+"/socket.conf",
        # user by client interfaces
        'packagesrelativepath': "packages/"+ETP_ARCH_CONST+"/",

        'entropyworkdir': default_etp_dir, # Entropy workdir
        # Entropy unpack directory
        'entropyunpackdir': default_etp_vardir,
        # Entropy packages image directory
        'entropyimagerelativepath': "image",
        # Gentoo xpak temp directory path
        'entropyxpakrelativepath': "xpak",
        # Gentoo xpak metadata directory path
        'entropyxpakdatarelativepath': "data",
        # Gentoo xpak metadata file name
        'entropyxpakfilename': "metadata.xpak",

        'etpdatabasetimestampfile': default_etp_dbfile+".timestamp",
        'etpdatabaseconflictingtaggedfile': default_etp_dbfile + \
            ".conflicting_tagged",
        # file containing a list of packages that are strictly
        # required by the repository, thus forced
        'etpdatabasesytemmaskfile': default_etp_dbfile+".system_mask",
        'etpdatabasemaskfile': default_etp_dbfile+".mask",
        'etpdatabaseupdatefile': default_etp_dbfile+".repo_updates",
        'etpdatabaselicwhitelistfile': default_etp_dbfile+".lic_whitelist",
        # the local/remote database revision file
        'etpdatabaserevisionfile': default_etp_dbfile+".revision",
        # missing dependencies black list file
        'etpdatabasemissingdepsblfile': default_etp_dbfile + \
            ".missing_deps_blacklist",
        # compressed file that contains all the "meta"
        # files in a repository dir
        'etpdatabasemetafilesfile': default_etp_dbfile+".meta",
        # file that contains a list of the "meta"
        # files not available in the repository
        'etpdatabasemetafilesnotfound': default_etp_dbfile+".meta_notfound",
        'etpdatabasehashfile': default_etp_dbfile+".md5", # its checksum


        # the remote database lock file
        'etpdatabaselockfile': default_etp_dbfile+".lock",
        # the remote database lock file
        'etpdatabaseeapi3lockfile': default_etp_dbfile+".eapi3_lock",
        # the remote database download lock file
        'etpdatabasedownloadlockfile': default_etp_dbfile+".download.lock",
        'etpdatabasecacertfile': "ca.cert",
        'etpdatabaseservercertfile': "server.cert",
        # when this file exists, the database is not synced
        # anymore with the online one
        'etpdatabasetaintfile': default_etp_dbfile+".tainted",

        # Entropy sqlite database file default_etp_dir + \
        #    default_etp_dbdir+"/packages.db"
        'etpdatabasefile': default_etp_dbfile,
        # Entropy sqlite database file (gzipped)
        'etpdatabasefilegzip': default_etp_dbfile+".gz",
        # Entropy sqlite database file (bzipped2)
        'etpdatabasefilebzip2': default_etp_dbfile+".bz2",

        # Entropy sqlite database file (gzipped)
        'etpdatabasefilegziplight': default_etp_dbfile+"light.gz",
        'etpdatabasefilehashgziplight': default_etp_dbfile+".light.gz.md5",
        # Entropy sqlite database file (bzipped2)
        'etpdatabasefilebzip2light': default_etp_dbfile+".light.bz2",
        'etpdatabasefilehashbzip2light': default_etp_dbfile+".light.bz2.md5",

        # Entropy sqlite database dump file (bzipped2)
        'etpdatabasedumpbzip2': default_etp_dbfile+".dump.bz2",
        'etpdatabasedumphashfilebz2': default_etp_dbfile+".dump.bz2.md5",
        # Entropy sqlite database dump file (gzipped)
        'etpdatabasedumpgzip': default_etp_dbfile+".dump.gz",
        'etpdatabasedumphashfilegzip': default_etp_dbfile+".dump.gz.md5",

        # Entropy sqlite database dump file
        'etpdatabasedump': default_etp_dbfile+".dump",

        # Entropy sqlite database dump file (bzipped2) light ver
        'etpdatabasedumplightbzip2': default_etp_dbfile+".dumplight.bz2",
        # Entropy sqlite database dump file (gzipped) light ver
        'etpdatabasedumplightgzip': default_etp_dbfile+".dumplight.gz",
        # Entropy sqlite database dump file, light ver (no content)
        'etpdatabasedumplighthashfilebz2': default_etp_dbfile+".dumplight.bz2.md5",
        'etpdatabasedumplighthashfilegzip': default_etp_dbfile+".dumplight.gz.md5",
        'etpdatabasedumplight': default_etp_dbfile+".dumplight",
        # expiration based server-side packages removal

        'etpdatabaseexpbasedpkgsrm': default_etp_dbfile+".fatscope",

        # Entropy default compressed database format
        'etpdatabasefileformat': "bz2",
        # Entropy compressed databases format support
        'etpdatabasesupportedcformats': ["bz2", "gz"],
        'etpdatabasecompressclasses': {
            "bz2": (bz2.BZ2File, "unpack_bzip2", "etpdatabasefilebzip2",
                "etpdatabasedumpbzip2", "etpdatabasedumphashfilebz2",
                "etpdatabasedumplightbzip2", "etpdatabasedumplighthashfilebz2",
                "etpdatabasefilegziplight","etpdatabasefilehashgziplight",),
            "gz": (gzip.GzipFile, "unpack_gzip", "etpdatabasefilegzip",
                "etpdatabasedumpgzip", "etpdatabasedumphashfilegzip",
                "etpdatabasedumplightgzip", "etpdatabasedumplighthashfilegzip",
                "etpdatabasefilebzip2light","etpdatabasefilehashbzip2light",)
        },
        # enable/disable packages RSS feed feature
        'rss-feed': True,
        # default name of the RSS feed
        'rss-name': "packages.rss",
        'rss-light-name': "updates.rss", # light version
        # default URL to the entropy web interface
        # (overridden in reagent.conf)
        'rss-base-url': "http://packages.sabayonlinux.org/",
        # default URL to the Operating System website
        # (overridden in reagent.conf)
        'rss-website-url': "http://www.sabayonlinux.org/",
        # xml file where will be dumped ServerInterface.rssMessages dictionary
        'rss-dump-name': "rss_database_actions",
        'rss-max-entries': 10000, # maximum rss entries
        'rss-light-max-entries': 300, # max entries for the light version
        'rss-managing-editor': "lxnay@sabayonlinux.org", # updates submitter
        # repository RSS-based notice board content
        'rss-notice-board': "notice.rss",

        'packagesetprefix': "@",
        'userpackagesetsid': "__user__",
        'setsconffilename': "sets.conf",
        'cachedumpext': ".dmp",
        'packagesext': ".tbz2",
        'smartappsext': ".esa",
        # Extension of the file that contains the checksum
        # of its releated package file
        'packagesmd5fileext': ".md5",
        'packagessha512fileext': ".sha512",
        'packagessha256fileext': ".sha256",
        'packagessha1fileext': ".sha1",
        # Extension of the file that "contains" expiration mtime
        'packagesexpirationfileext': ".expired",
        # number of days after a package will be removed from mirrors
        'packagesexpirationdays': 15,
        # name of the trigger file that would be executed
        # by equo inside triggerTools
        'triggername': "trigger",
        'trigger_sh_interpreter': "/usr/sbin/entropy.sh",
        # entropy hardware hash generator executable
        'etp_hw_hash_gen': rootdir+"/usr/bin/entropy_hwgen.sh",
        # proxy configuration constants, used system wide
        'proxy': {
            'ftp': None,
            'http': None,
            'username': None,
            'password': None
        },
        # Entropy log level (default: 1 - see entropy.conf for more info)
        'entropyloglevel': 1,
        # Entropy Socket Interface log level
        'socketloglevel': 2,
        'spmloglevel': 1,
        # Log dir where ebuilds store their stuff
        'logdir': default_etp_logdir ,

        'syslogdir': default_etp_syslogdir, # Entropy system tools log directory
        'entropylogfile': default_etp_syslogdir+"entropy.log",
        'equologfile': default_etp_syslogdir+"equo.log",
        'spmlogfile': default_etp_syslogdir+"spm.log",
        'socketlogfile': default_etp_syslogdir+"socket.log",

        'etpdatabaseclientdir': default_etp_dir + default_etp_client_repodir + \
            default_etp_dbdir,
        # path to equo.db - client side database file
        'etpdatabaseclientfilepath': default_etp_dir + \
            default_etp_client_repodir + default_etp_dbdir + "/" + \
            default_etp_dbclientfile,
        # prefix of the name of self.dbname in
        # entropy.db.LocalRepository class for the repositories
        'dbnamerepoprefix': "repo_",
        # prefix of database backups
        'dbbackupprefix': 'etp_backup_',

        # Entropy database API revision
        'etpapi': etpSys['api'],
        # contains the current running architecture
        'currentarch': etpSys['arch'],
        # Entropy supported Archs
        'supportedarchs': etpSys['archs'],

         # available branches, this only exists for the server part,
         # these settings will be overridden by server.conf ones
        'branches': [],
        # default choosen branch (overridden by setting in repositories.conf)
        'branch': "4",
         # default allowed package keywords
        'keywords': set([etpSys['arch'],"~"+etpSys['arch']]),
        # allow multiple packages in single scope server-side?
        # this makes possible to have multiple versions of packages
        # and handle the removal through expiration (using creation date)
        'expiration_based_scope': False,
        'edbcounter': edb_counter,
        'libtest_blacklist': [],
        'libtest_files_blacklist': [],
        # our official repository name
        'officialserverrepositoryid': "sabayonlinux.org",
        # our official repository name
        'officialrepositoryid': "sabayonlinux.org",
        'conntestlink': "http://www.sabayonlinux.org",
        # tag to append to .tbz2 file before entropy database (must be 32bytes)
        'databasestarttag': "|ENTROPY:PROJECT:DB:MAGIC:START|",
        'pidfile': default_etp_dir+"/entropy.pid",
        'applicationlock': False,
        # option to keep a backup of config files after
        # being overwritten by equo conf update
        'filesbackup': True,
        # collision protection option, see client.conf for more info
        'collisionprotect': 1,
        # list of user specified CONFIG_PROTECT directories
        # (see Gentoo manual to understand the meaining of this parameter)
        'configprotect': [],
        # list of user specified CONFIG_PROTECT_MASK directories
        'configprotectmask': [],
        # list of user specified configuration files that
        # should be ignored and kept as they are
        'configprotectskip': [],
        # installed database CONFIG_PROTECT directories
        'dbconfigprotect': [],
        # installed database CONFIG_PROTECT_MASK directories
        'dbconfigprotectmask': [],
        # this will be used to show the number of updated
        # files at the end of the processes
        'configprotectcounter': 0,
        # default Entropy release version
        'entropyversion': "1.0",
        # default system name (overidden by entropy.conf settings)
        'systemname': "Sabayon Linux",
        # Product identificator (standard, professional...)
        'product': "standard",
        'errorstatus': default_etp_confdir+"/code",
        'systemroot': rootdir, # default system root
        'uid': os.getuid(), # current running UID
        'entropygid': None,
        'sysgroup': "entropy",
        'defaultumask': 022,
        'storeumask': 002,
        'gentle_nice': 15,
        'current_nice': 0,
        'default_nice': 0,
        'server_treeupdatescalled': set(),
        'client_treeupdatescalled': set(),
        'spm': {
            '(r)depend_id': 0,
            'pdepend_id': 1,
            'mdepend_id': 2, # actually, this is entropy-only
            'ebuild_file_extension': "ebuild",
            'preinst_phase': "preinst",
            'postinst_phase': "postinst",
            'prerm_phase': "prerm",
            'postrm_phase': "postrm",
            'setup_phase': "setup",
            'compile_phase': "compile",
            'install_phase': "install",
            'unpack_phase': "unpack",
            'ebuild_pkg_tag_var': "ENTROPY_PROJECT_TAG",
            'global_make_conf': rootdir+"/etc/make.conf",
            'global_package_keywords': rootdir+"/etc/portage/package.keywords",
            'global_package_use': rootdir+"/etc/portage/package.use",
            'global_package_mask': rootdir+"/etc/portage/package.mask",
            'global_package_unmask': rootdir+"/etc/portage/package.unmask",
            'global_make_profile': rootdir+"/etc/make.profile",
            'global_make_profile_link_name' : "profile.link",
            # source package manager executable
            'exec': rootdir+"/usr/bin/emerge",
            'env_update_cmd': rootdir+"/usr/sbin/env-update",
            'source_profile': ["source", rootdir+"/etc/profile"],
            'source_build_ext': ".ebuild",
            'ask_cmd': "--ask",
            'info_cmd': "--info",
            'remove_cmd': "-C",
            'nodeps_cmd': "--nodeps",
            'fetchonly_cmd': "--fetchonly",
            'buildonly_cmd': "--buildonly",
            'oneshot_cmd': "--oneshot",
            'pretend_cmd': "--pretend",
            'verbose_cmd': "--verbose",
            'nocolor_cmd': "--color=n",
            'backend': "portage",
            'available_backends': ["portage"],
            'cache': {},
            'xpak_entries': {
                'description': "DESCRIPTION",
                'homepage': "HOMEPAGE",
                'chost': "CHOST",
                'category': "CATEGORY",
                'cflags': "CFLAGS",
                'cxxflags': "CXXFLAGS",
                'license': "LICENSE",
                'src_uri': "SRC_URI",
                'use': "USE",
                'iuse': "IUSE",
                'slot': "SLOT",
                'provide': "PROVIDE",
                'depend': "DEPEND",
                'rdepend': "RDEPEND",
                'pdepend': "PDEPEND",
                'needed': "NEEDED",
                'inherited': "INHERITED",
                'keywords': "KEYWORDS",
                'contents': "CONTENTS",
                'counter': "COUNTER",
                'defined_phases': "DEFINED_PHASES",
            },
            'system_packages': [],
            'ignore-spm-downgrades': False,
        },

        # entropy client packages download speed limit (in kb/sec)
        'downloadspeedlimit': None,

        # data storage directory, useful to speed up
        # entropy client across multiple issued commands
        'dumpstoragedir': default_etp_dir+default_etp_cachesdir,
        # where GLSAs are stored
        'securitydir': default_etp_dir+default_etp_securitydir,
        'securityurl': "http://community.sabayonlinux.org/security"
            "/security-advisories.tar.bz2",

        'safemodeerrors': {
            'clientdb': 1,
        },
        'safemodereasons': {
            0: _("All fine"),
            1: _("Corrupted Client Repository. Please restore a backup."),
        },

        'misc_counters': {
            'forced_atoms_update_ids': {
                '__idtype__': 1,
                'kde': 1,
            },
        },

        'system_settings_plugins_ids': {
            'client_plugin': "client_plugin",
            'server_plugin': "server_plugin",
            'server_plugin_fatscope': "server_plugin_fatscope",
        },

        'clientserverrepoid': "__system__",
        'clientdbid': "client",
        'serverdbid': "etpdb:",
        'genericdbid': "generic",
        'systemreleasefile': "/etc/sabayon-release",

        # these are constants, for real settings
        # look ad SystemSettings class
        'socket_service': { # here are the constants
            'hostname': "localhost",
            'port': 1026,
            'ssl_port': 1027, # above + 1
            'timeout': 200,
            'forked_requests_timeout': 300,
            'max_command_length': 768000, # bytes
            'threads': 5,
            'session_ttl': 15,
            'default_uid': 0,
            'max_connections': 5,
            'max_connections_per_host': 15,
            'max_connections_per_host_barrier': 8,
            'disabled_cmds': set(),
            'ip_blacklist': set(),
            'ssl_key': default_etp_confdir+"/socket_server.key",
            'ssl_cert': default_etp_confdir+"/socket_server.crt",
            'ssl_ca_cert': default_etp_confdir+"/socket_server.CA.crt",
            'ssl_ca_pkey': default_etp_confdir+"/socket_server.CA.key",
            'answers': {
                'ok': chr(0)+"OK"+chr(0), # command run
                'er': chr(0)+"ER"+chr(1), # execution error
                'no': chr(0)+"NO"+chr(2), # not allowed
                'cl': chr(0)+"CL"+chr(3), # close connection
                'mcr': chr(0)+"MCR"+chr(4), # max connections reached
                'eos': chr(0), # end of size,
                'noop': chr(0)+"NOOP"+chr(0)
            },
        },

        'install_sources': {
            'unknown': 0,
            'user': 1,
            'automatic_dependency': 2,
        },

        'ugc_doctypes': {
            'comments': 1,
            'bbcode_doc': 2,
            'image': 3,
            'generic_file': 4,
            'youtube_video': 5,
        },
        'ugc_doctypes_description': {
            1: _('Comments'),
            2: _('BBcode Documents'),
            3: _('Images/Screenshots'),
            4: _('Generic Files'),
            5: _('YouTube(tm) Videos'),
        },
        'ugc_doctypes_description_singular': {
            1: _('Comment'),
            2: _('BBcode Document'),
            3: _('Image/Screenshot'),
            4: _('Generic File'),
            5: _('YouTube(tm) Video'),
        },
        'ugc_accessfile': default_etp_ugc_confdir+"/access.xml",
        'ugc_voterange': range(1, 6),

        # handler settings
        'handlers': {
            # md5sum handler,
            'md5sum': "md5sum.php?arch="+etpSys['arch']+"&package=",
            # XXX: hardcoded?
            'errorsend': "http://svn.sabayonlinux.org/entropy/standard"
                "/sabayonlinux.org/handlers/http_error_report.php",
        },

    }

    # set current nice level
    try:
        my_const['current_nice'] = os.nice(0)
    except OSError:
        pass

    etpConst.update(my_const)

def const_set_nice_level(nice_level = 0):
    """
    Change current process scheduler "nice" level.

    @param nice_level new valid nice level
    @type nice_level int
    @return current_nice new nice level
    """
    default_nice = etpConst['default_nice']
    current_nice = etpConst['current_nice']
    delta = current_nice - default_nice
    try:
        etpConst['current_nice'] = os.nice(delta*-1+nice_level)
    except OSError:
        pass
    return current_nice

def const_extract_cli_repo_params(repostring, branch = None, product = None):

    """
    Extract repository information from the provided repository string,
    usually contained in the repository settings file, repositories.conf.

    @param repostring basestring
    @type repostring valid repository string
    @return tuple composed by
        reponame => repository identifier (string),
        mydata => extracted repository information (dict)
    """

    if branch == None:
        branch = etpConst['branch']
    if product == None:
        product = etpConst['product']

    reponame = repostring.split("|")[1].strip()
    repodesc = repostring.split("|")[2].strip()
    repopackages = repostring.split("|")[3].strip()
    repodatabase = repostring.split("|")[4].strip()

    eapi3_port = int(etpConst['socket_service']['port'])
    eapi3_ssl_port = int(etpConst['socket_service']['ssl_port'])
    eapi3_formatcolon = repodatabase.rfind("#")
    if eapi3_formatcolon != -1:
        try:
            ports = repodatabase[eapi3_formatcolon+1:].split(",")
            eapi3_port = int(ports[0])
            if len(ports) > 1:
                eapi3_ssl_port = int(ports[1])
            repodatabase = repodatabase[:eapi3_formatcolon]
        except (ValueError, IndexError,):
            eapi3_port = int(etpConst['socket_service']['port'])
            eapi3_ssl_port = int(etpConst['socket_service']['ssl_port'])

    dbformat = etpConst['etpdatabasefileformat']
    dbformatcolon = repodatabase.rfind("#")
    if dbformatcolon != -1:
        if dbformat in etpConst['etpdatabasesupportedcformats']:
            try:
                dbformat = repodatabase[dbformatcolon+1:]
            except (IndexError, ValueError, TypeError,):
                pass
        repodatabase = repodatabase[:dbformatcolon]

    mydata = {}
    mydata['repoid'] = reponame
    mydata['service_port'] = eapi3_port
    mydata['ssl_service_port'] = eapi3_ssl_port
    mydata['description'] = repodesc
    mydata['packages'] = []
    mydata['plain_packages'] = []

    mydata['dbpath'] = etpConst['etpdatabaseclientdir'] + "/" + reponame + \
        "/" + product + "/" + etpConst['currentarch'] + "/" + branch

    mydata['dbcformat'] = dbformat
    if not dbformat in etpConst['etpdatabasesupportedcformats']:
        mydata['dbcformat'] = etpConst['etpdatabasesupportedcformats'][0]

    mydata['plain_database'] = repodatabase

    mydata['database'] = repodatabase + "/" + product + "/" + \
        reponame + "/database/" + etpConst['currentarch'] + \
        "/" + branch

    mydata['notice_board'] = mydata['database'] + "/" + \
        etpConst['rss-notice-board']

    mydata['local_notice_board'] = mydata['dbpath'] + "/" + \
        etpConst['rss-notice-board']

    mydata['dbrevision'] = "0"
    dbrevision_file = os.path.join(mydata['dbpath'],
        etpConst['etpdatabaserevisionfile'])
    if os.path.isfile(dbrevision_file) and os.access(dbrevision_file, os.R_OK):
        with open(dbrevision_file, "r") as dbrev_f:
            mydata['dbrevision'] = dbrev_f.readline().strip()

    # initialize CONFIG_PROTECT
    # will be filled the first time the db will be opened
    mydata['configprotect'] = None
    mydata['configprotectmask'] = None
    repopackages = [x.strip() for x in repopackages.split() if x.strip()]
    repopackages = [x for x in repopackages if (x.startswith('http://') or \
        x.startswith('ftp://') or x.startswith('file://'))]

    for repo_package in repopackages:
        try:
            repo_package = str(repo_package)
        except (UnicodeDecodeError,UnicodeEncodeError,):
            continue
        mydata['plain_packages'].append(repo_package)
        mydata['packages'].append(repo_package + "/" + product + "/" + reponame)

    return reponame, mydata

def const_read_entropy_release():
    """
    Read Entropy release file content and fill etpConst['entropyversion']

    @return None
    """
    # handle Entropy Version
    revision_file = "../libraries/revision"
    if not os.path.isfile(revision_file):
        revision_file = os.path.join(etpConst['installdir'],
            'libraries/revision')
    if os.path.isfile(revision_file) and \
        os.access(revision_file,os.R_OK):

        with open(revision_file, "r") as rev_f:
            myrev = rev_f.readline().strip()
            etpConst['entropyversion'] = myrev


def const_setup_entropy_pid(just_read = False):

    """
    Setup Entropy pid file, if possible and if UID = 0 (root).
    If the application is run with --no-pid-handling argument,
    this function will have no effect. If just_read is specified,
    this function will only try to read the current pid string in
    the Entropy pid file (etpConst['pidfile']). If any other entropy
    istance is currently owning the contained pid, etpConst['applicationlock']
    becomes True.

    @param just_read only read the current pid file, if any and if possible
    @type just_read bool

    @return None
    """

    if ("--no-pid-handling" in sys.argv) and (not just_read):
        return

    # PID creation
    pid = os.getpid()
    pid_file = etpConst['pidfile']
    if os.path.isfile(pid_file) and os.access(pid_file, os.R_OK):

        try:
            with open(pid_file,"r") as pid_f:
                found_pid = str(pid_f.readline().strip())
        except (IOError, OSError, UnicodeEncodeError, UnicodeDecodeError,):
            found_pid = "0000" # which is always invalid

        if found_pid != str(pid):
            # is found_pid still running ?
            pid_path = "%s/proc/%s" % (etpConst['systemroot'], found_pid,)
            if os.path.isdir(pid_path) and found_pid:
                etpConst['applicationlock'] = True
            elif not just_read:
                # if root, write new pid
                #if etpConst['uid'] == 0:
                if os.access(pid_file, os.W_OK):
                    try:
                        with open(pid_file,"w") as pid_f:
                            pid_f.write(str(pid))
                            pid_f.flush()
                    except IOError, err:
                        if err.errno == 30: # readonly filesystem
                            pass
                        else:
                            raise
                    try:
                        const_chmod_entropy_pid()
                    except OSError:
                        pass

    elif not just_read:

        #if etpConst['uid'] == 0:
        if os.access(os.path.dirname(pid_file), os.W_OK):

            if os.path.exists(pid_file):
                if os.path.islink(pid_file):
                    os.remove(pid_file)
                elif os.path.isdir(pid_file):
                    import shutil
                    shutil.rmtree(pid_file)

            with open(pid_file,"w") as pid_fw:
                pid_fw.write(str(pid))
                pid_fw.flush()

            try:
                const_chmod_entropy_pid()
            except OSError:
                pass

def const_secure_config_file(config_file):
    """
    Setup entropy file needing strict permissions, no world readable.

    @param config_file valid config file path
    @type config_file basestring
    @return None
    """
    try:
        mygid = const_get_entropy_gid()
    except KeyError:
        mygid = 0
    try:
        const_setup_file(config_file, mygid, 0660)
    except (OSError, IOError,):
        pass

def const_chmod_entropy_pid():
    """
    Setup entropy pid file permissions, if possible.

    @return None
    """
    try:
        mygid = const_get_entropy_gid()
    except KeyError:
        mygid = 0
    const_setup_file(etpConst['pidfile'], mygid, 0664)

def const_create_working_dirs():

    """
    Setup Entropy directory structure, as much automagically as possible.

    @return None
    """

    # handle pid file
    piddir = os.path.dirname(etpConst['pidfile'])
    if not os.path.exists(piddir) and (etpConst['uid'] == 0):
        os.makedirs(piddir)

    # create tmp dir
    #if not os.path.isdir(xpakpath_dir):
    #    os.makedirs(xpakpath_dir,0775)
    #    const_setup_file(xpakpath_dir, 

    # create user if it doesn't exist
    gid = None
    try:
        gid = const_get_entropy_gid()
    except KeyError:
        if etpConst['uid'] == 0:
            # create group
            # avoid checking cause it's not mandatory for entropy/equo itself
            const_add_entropy_group()
            try:
                gid = const_get_entropy_gid()
            except KeyError:
                pass

    # Create paths
    keys = [x for x in etpConst if isinstance(etpConst[x],basestring)]
    for key in keys:

        if not etpConst[key] or \
        etpConst[key].endswith(".conf") or \
        not os.path.isabs(etpConst[key]) or \
        etpConst[key].endswith(".cfg") or \
        etpConst[key].endswith(".tmp") or \
        etpConst[key].find(".db") != -1 or \
        etpConst[key].find(".log") != -1 or \
        os.path.isdir(etpConst[key]) or \
        not key.endswith("dir"):
            continue

        # allow users to create dirs in custom paths,
        # so don't fail here even if we don't have permissions
        try:
            key_dir = etpConst[key]
            d_paths = []
            while not os.path.isdir(key_dir):
                d_paths.append(key_dir)
                key_dir = os.path.dirname(key_dir)
            d_paths = sorted(d_paths)
            for d_path in d_paths:
                os.mkdir(d_path)
                const_setup_file(d_path, gid, 0775)
        except (OSError, IOError,):
            pass

    if gid:
        etpConst['entropygid'] = gid
        if not os.path.isdir(etpConst['entropyworkdir']):
            try:
                os.makedirs(etpConst['entropyworkdir'])
            except OSError:
                pass
        w_gid = os.stat(etpConst['entropyworkdir'])[stat.ST_GID]
        if w_gid != gid:
            const_setup_perms(etpConst['entropyworkdir'], gid)

        if not os.path.isdir(etpConst['entropyunpackdir']):
            try:
                os.makedirs(etpConst['entropyunpackdir'])
            except OSError:
                pass
        try:
            w_gid = os.stat(etpConst['entropyunpackdir'])[stat.ST_GID]
            if w_gid != gid:
                if os.path.isdir(etpConst['entropyunpackdir']):
                    const_setup_perms(etpConst['entropyunpackdir'], gid)
        except OSError:
            pass
        # always setup /var/lib/entropy/client permissions
        if not const_islive():
            # aufs/unionfs will start to leak otherwise
            const_setup_perms(etpConst['etpdatabaseclientdir'], gid)

def const_configure_lock_paths():
    """
    Setup Entropy lock file paths.

    @return None
    """
    etpConst['locks'] = {
        'using_resources': os.path.join(etpConst['etpdatabaseclientdir'],
            '.using_resources'),
    }


def const_extract_srv_repo_params(repostring, product = None):
    """
    Analyze a server repository string (usually contained in server.conf),
    extracting all the parameters.

    @param repostring repository string
    @type repostring basestring
    @return None
    """

    if product == None:
        product = etpConst['product']

    mydata = {}
    repoid = repostring.split("|")[1].strip()
    repodesc = repostring.split("|")[2].strip()
    repouris = repostring.split("|")[3].strip()
    repohandlers = repostring.split("|")[4].strip()

    service_url = None
    eapi3_port = int(etpConst['socket_service']['port'])
    eapi3_ssl_port = int(etpConst['socket_service']['ssl_port'])
    if len(repostring.split("|")) > 5:
        service_url = repostring.split("|")[5].strip()

        eapi3_formatcolon = service_url.rfind("#")
        if eapi3_formatcolon != -1:
            try:
                ports = service_url[eapi3_formatcolon+1:].split(",")
                eapi3_port = int(ports[0])
                if len(ports) > 1:
                    eapi3_ssl_port = int(ports[1])
                service_url = service_url[:eapi3_formatcolon]
            except (ValueError, IndexError,):
                eapi3_port = int(etpConst['socket_service']['port'])
                eapi3_ssl_port = int(etpConst['socket_service']['ssl_port'])

    mydata = {}
    mydata['repoid'] = repoid
    mydata['description'] = repodesc
    mydata['mirrors'] = []
    mydata['community'] = False
    mydata['service_url'] = service_url
    mydata['service_port'] = eapi3_port
    mydata['ssl_service_port'] = eapi3_ssl_port
    if repohandlers:
        repohandlers = os.path.join(repohandlers, product, repoid, "handlers")
        mydata['handler'] = repohandlers
    uris = repouris.split()
    for uri in uris:
        mydata['mirrors'].append(uri)

    return repoid, mydata

def const_setup_perms(mydir, gid):
    """
    Setup permissions and group id (GID) to a directory, recursively.

    @param mydir valid file path
    @type mydir basestring
    @param gid valid group id (GID)
    @type gid int
    @return None
    """
    if gid == None:
        return
    for currentdir, subdirs, files in os.walk(mydir):
        try:
            cur_gid = os.stat(currentdir)[stat.ST_GID]
            if cur_gid != gid:
                os.chown(currentdir, -1, gid)
            cur_mod = const_get_chmod(currentdir)
            if cur_mod != oct(0775):
                os.chmod(currentdir, 0775)
        except OSError:
            pass
        for item in files:
            item = os.path.join(currentdir, item)
            try:
                const_setup_file(item, gid, 0664)
            except OSError:
                pass

def const_setup_file(myfile, gid, chmod):
    """
    Setup file permissions and group id (GID).

    @param myfile valid file path
    @type myfile basestring
    @param gid valid group id (GID)
    @type gid int
    @param chmod permissions
    @type chmod integer representing an octal
    @return None
    """
    cur_gid = os.stat(myfile)[stat.ST_GID]
    if cur_gid != gid:
        os.chown(myfile, -1, gid)
    const_set_chmod(myfile, chmod)

# you need to convert to int
def const_get_chmod(myfile):
    """
    This function get the current permissions of the specified
    file. If you want to use the returning value with const_set_chmod
    you need to convert it back to int.

    @param myfile valid file path
    @type myfile basestring
    @return octal representing permissions
    """
    myst = os.stat(myfile)[stat.ST_MODE]
    return oct(myst & 0777)

def const_set_chmod(myfile, chmod):
    """
    This function sets specified permissions to a file.
    If they differ from the current ones.

    @param myfile valid file path
    @type myfile basestring
    @param chmod permissions
    @type chmod integer representing an octal
    @return None
    """
    cur_mod = const_get_chmod(myfile)
    if cur_mod != oct(chmod):
        os.chmod(myfile, chmod)

def const_get_entropy_gid():
    """
    This function tries to retrieve the "entropy" user group
    GID.

    @return None or KeyError exception
    """
    group_file = etpConst['systemroot']+'/etc/group'
    if not os.path.isfile(group_file):
        raise KeyError

    with open(group_file,"r") as group_f:
        for line in group_f.readlines():
            if line.startswith('%s:' % (etpConst['sysgroup'],)):
                try:
                    gid = int(line.split(":")[2])
                except ValueError:
                    raise KeyError
                return gid
    raise KeyError

def const_add_entropy_group():
    """
    This function looks for an "entropy" user group.
    If not available, it tries to create one.

    @return None
    """
    group_file = etpConst['systemroot']+'/etc/group'
    if not os.path.isfile(group_file):
        raise KeyError
    ids = set()

    with open(group_file,"r") as group_f:
        for line in group_f.readlines():
            if line and line.split(":"):
                try:
                    myid = int(line.split(":")[2])
                except ValueError:
                    pass
                ids.add(myid)
        if ids:
            # starting from 1000, get the first free
            new_id = 1000
            while 1:
                new_id += 1
                if new_id not in ids:
                    break
        else:
            new_id = 10000

    with open(group_file,"aw") as group_fw:
        group_fw.seek(0, 2)
        app_line = "entropy:x:%s:\n" % (new_id,)
        group_fw.write(app_line)
        group_fw.flush()

def const_islive():
    """
    Live environments (Operating System running off a CD/DVD)
    must feature the "cdroot" parameter in kernel /proc/cmdline

    @return bool stating if we are running Live or not
    """
    if "cdroot" in etpConst['cmdline']:
        return True
    return False

def const_kill_threads():
    """
    Entropy threads killer. Even if Python threads cannot
    be stopped or killed, TimeScheduled ones can, exporting
    the kill() method.

    @return None
    """
    import threading
    threads = threading.enumerate()
    for running_t in threads:
        if not hasattr(running_t,'kill'):
            continue
        running_t.kill()
        running_t.join()

def const_handle_exception(etype, value, t_back):
    """
    Our default Python exception handler. It kills
    all the threads generated by Entropy before
    raising exceptions. Overloads sys.excepthook

    @param etype exception type
    @param value exception value
    @param t_back traceback object?
    @return sys.__excepthook__
    """
    try:
        const_kill_threads()
    except ImportError:
        pass
    return sys.__excepthook__(etype, value, t_back)

# load config
initconfig_entropy_constants(etpSys['rootdir'])
