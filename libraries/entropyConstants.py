#!/usr/bin/python
'''
    # DESCRIPTION:
    # Variables container

    Copyright (C) 2007-2008 Fabio Erculiani

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


import random
import sys
import os
import stat
import exceptionTools
from entropy_i18n import _


# Specifications of the content of packages metadata
'''
data = {
    'name': u"", # the Package Name
    'version': u"", # the Package version
    'description': u"", # the Package description
    'category': u"", # the gentoo category
    'chost': u"", # the CHOST used to compile it
    'cflags': u"", # CFLAGS used
    'cxxflags': u"", # CXXFLAGS used
    'homepage': u"", # home page of the package
    'useflags': u"", # USE flags used
    'license': u"", # License adpoted
    'keywords': u"", # supported ARCHs (by the SRC)
    'branch': u"", # package branch location
    'download': u"", # link to download the binary package
    'digest': u"", # md5 hash of the .tbz2 package
    'sources': u"", # link to the sources
    'slot': u"", # this is filled if the package is slotted
    'content': u"", # content of the package (files)
    'mirrorlinks': u"", # =mirror://openoffice|link1|link2|link3
    'dependencies': u"", # dependencies
    'conflicts': u"", # blockers
    'etpapi': u"", # Entropy API revision
    'datecreation': u"", # mtime of the .tbz2 file
    'size': u"", # the package size
    'versiontag': u"", # particular version tag
    'provide': u"", # like, cups provides dep virtual/lpr
    'systempackage': u"", # if this is a system package, this will be != ""
    'config_protect': u"", # list of directories that contain files that should not be overwritten
    'config_protect_mask': u"", # list of directories that contain files that should be overwritten
    'disksize': u"", # size on the hard disk in bytes (integer)
    'counter': u"", # aka. COUNTER file
    'messages': u"", # elog content from portage
    'eclasses': u"", # eclasses used by the ebuild
    'needed': set, # runtime libraries needed by the package
    'trigger': bool, # this will become a bool, containing info about external trigger presence
    'injected': bool, # if the package has been injected manually, this will be true
    'licensedata': dict # dictionary that contains license text
}
'''

# Entropy SQL initialization Schema and data structure
etpSQLInitDestroyAll = """
DROP TABLE IF EXISTS baseinfo;
DROP TABLE IF EXISTS extrainfo;
DROP TABLE IF EXISTS content;
DROP TABLE IF EXISTS contentreference;
DROP TABLE IF EXISTS contenttypes;
DROP TABLE IF EXISTS dependencies;
DROP TABLE IF EXISTS dependenciesreference;
DROP TABLE IF EXISTS provide;
DROP TABLE IF EXISTS conflicts;
DROP TABLE IF EXISTS neededlibs;
DROP TABLE IF EXISTS libraries;
DROP TABLE IF EXISTS mirrorlinks;
DROP TABLE IF EXISTS sources;
DROP TABLE IF EXISTS sourcesreference;
DROP TABLE IF EXISTS useflags;
DROP TABLE IF EXISTS useflagsreference;
DROP TABLE IF EXISTS keywords;
DROP TABLE IF EXISTS binkeywords;
DROP TABLE IF EXISTS keywordsreference;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS licenses;
DROP TABLE IF EXISTS flags;
DROP TABLE IF EXISTS systempackages;
DROP TABLE IF EXISTS configprotect;
DROP TABLE IF EXISTS configprotectmask;
DROP TABLE IF EXISTS configprotectreference;
DROP TABLE IF EXISTS installedtable;
DROP TABLE IF EXISTS dependstable;
DROP TABLE IF EXISTS sizes;
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS counters;
DROP TABLE IF EXISTS eclasses;
DROP TABLE IF EXISTS eclassesreference;
DROP TABLE IF EXISTS needed;
DROP TABLE IF EXISTS neededreference;
DROP TABLE IF EXISTS triggers;
DROP TABLE IF EXISTS countersdata;
DROP TABLE IF EXISTS injected;
DROP TABLE IF EXISTS treeupdates;
DROP TABLE IF EXISTS treeupdatesactions;
DROP TABLE IF EXISTS library_breakages;
DROP TABLE IF EXISTS licensedata;
DROP TABLE IF EXISTS licenses_accepted;
DROP TABLE IF EXISTS trashedcounters;
DROP TABLE IF EXISTS entropy_misc_counters;
DROP TABLE IF EXISTS categoriesdescription;
DROP TABLE IF EXISTS packagesets;
"""

etpSQLInit = """

CREATE TABLE baseinfo (
    idpackage INTEGER PRIMARY KEY AUTOINCREMENT,
    atom VARCHAR,
    idcategory INTEGER,
    name VARCHAR,
    version VARCHAR,
    versiontag VARCHAR,
    revision INTEGER,
    branch VARCHAR,
    slot VARCHAR,
    idlicense INTEGER,
    etpapi INTEGER,
    trigger INTEGER
);

CREATE TABLE extrainfo (
    idpackage INTEGER PRIMARY KEY,
    description VARCHAR,
    homepage VARCHAR,
    download VARCHAR,
    size VARCHAR,
    idflags INTEGER,
    digest VARCHAR,
    datecreation VARCHAR
);

CREATE TABLE content (
    idpackage INTEGER,
    file VARCHAR,
    type VARCHAR
);

CREATE TABLE provide (
    idpackage INTEGER,
    atom VARCHAR
);

CREATE TABLE dependencies (
    idpackage INTEGER,
    iddependency INTEGER,
    type INTEGER
);

CREATE TABLE dependenciesreference (
    iddependency INTEGER PRIMARY KEY AUTOINCREMENT,
    dependency VARCHAR
);

CREATE TABLE conflicts (
    idpackage INTEGER,
    conflict VARCHAR
);

CREATE TABLE mirrorlinks (
    mirrorname VARCHAR,
    mirrorlink VARCHAR
);

CREATE TABLE sources (
    idpackage INTEGER,
    idsource INTEGER
);

CREATE TABLE sourcesreference (
    idsource INTEGER PRIMARY KEY AUTOINCREMENT,
    source VARCHAR
);

CREATE TABLE useflags (
    idpackage INTEGER,
    idflag INTEGER
);

CREATE TABLE useflagsreference (
    idflag INTEGER PRIMARY KEY AUTOINCREMENT,
    flagname VARCHAR
);

CREATE TABLE keywords (
    idpackage INTEGER,
    idkeyword INTEGER
);

CREATE TABLE keywordsreference (
    idkeyword INTEGER PRIMARY KEY AUTOINCREMENT,
    keywordname VARCHAR
);

CREATE TABLE categories (
    idcategory INTEGER PRIMARY KEY AUTOINCREMENT,
    category VARCHAR
);

CREATE TABLE licenses (
    idlicense INTEGER PRIMARY KEY AUTOINCREMENT,
    license VARCHAR
);

CREATE TABLE flags (
    idflags INTEGER PRIMARY KEY AUTOINCREMENT,
    chost VARCHAR,
    cflags VARCHAR,
    cxxflags VARCHAR
);

CREATE TABLE configprotect (
    idpackage INTEGER PRIMARY KEY,
    idprotect INTEGER
);

CREATE TABLE configprotectmask (
    idpackage INTEGER PRIMARY KEY,
    idprotect INTEGER
);

CREATE TABLE configprotectreference (
    idprotect INTEGER PRIMARY KEY AUTOINCREMENT,
    protect VARCHAR
);

CREATE TABLE systempackages (
    idpackage INTEGER PRIMARY KEY
);

CREATE TABLE injected (
    idpackage INTEGER PRIMARY KEY
);

CREATE TABLE installedtable (
    idpackage INTEGER PRIMARY KEY,
    repositoryname VARCHAR
);

CREATE TABLE sizes (
    idpackage INTEGER PRIMARY KEY,
    size INTEGER
);

CREATE TABLE messages (
    idpackage INTEGER,
    message VARCHAR
);

CREATE TABLE counters (
    counter INTEGER,
    idpackage INTEGER,
    branch VARCHAR,
    PRIMARY KEY(idpackage,branch)
);

CREATE TABLE trashedcounters (
    counter INTEGER
);

CREATE TABLE eclasses (
    idpackage INTEGER,
    idclass INTEGER
);

CREATE TABLE eclassesreference (
    idclass INTEGER PRIMARY KEY AUTOINCREMENT,
    classname VARCHAR
);

CREATE TABLE needed (
    idpackage INTEGER,
    idneeded INTEGER,
    elfclass INTEGER
);

CREATE TABLE neededreference (
    idneeded INTEGER PRIMARY KEY AUTOINCREMENT,
    library VARCHAR
);

CREATE TABLE treeupdates (
    repository VARCHAR PRIMARY KEY,
    digest VARCHAR
);

CREATE TABLE treeupdatesactions (
    idupdate INTEGER PRIMARY KEY AUTOINCREMENT,
    repository VARCHAR,
    command VARCHAR,
    branch VARCHAR,
    date VARCHAR
);

CREATE TABLE licensedata (
    licensename VARCHAR UNIQUE,
    text BLOB,
    compressed INTEGER
);

CREATE TABLE licenses_accepted (
    licensename VARCHAR UNIQUE
);

CREATE TABLE triggers (
    idpackage INTEGER PRIMARY KEY,
    data BLOB
);

CREATE TABLE entropy_misc_counters (
    idtype INTEGER PRIMARY KEY,
    counter INTEGER
);

CREATE TABLE categoriesdescription (
    category VARCHAR,
    locale VARCHAR,
    description VARCHAR
);

CREATE TABLE packagesets (
    setname VARCHAR,
    dependency VARCHAR
);

"""

# ETP_ARCH_CONST setup
if os.uname()[4] == "x86_64":
    ETP_ARCH_CONST = "amd64"
else:
    ETP_ARCH_CONST = "x86"

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
    'postinstall_triggers_disable': set(),
    'postremove_triggers_disable': set(),
    'preinstall_triggers_disable': set(),
    'preremove_triggers_disable': set()
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
    'configfiles': 'conf/scanfs', # used to store information about files that should be merged using "equo conf merge"
    'dbMatch': 'match/db', # db atom match cache
    'dbSearch': 'search/db', # db search cache
    'atomMatch': 'atom_match/atom_match_', # used to store info about repository dependencies solving
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

# ahahaha
etpExitMessages = {
    0: _("You should run equo --help"),
    1: _("You didn't run equo --help, did you?"),
    2: _("Did you even read equo --help??"),
    3: _("I give up. Run that equo --help !!!!!!!"),
    4: _("OH MY GOD. RUN equo --heeeeeeeeeeeeeelp"),
    5: _("Illiteracy is a huge problem in this world"),
    6: _("Ok i give up, you are hopeless"),
    7: _("Go to hell."),
}

# information about what has been done on the database,
# those dicts will be dumped to a file and used by activator to update and upload .rss
etpRSSMessages = {
    'added': {}, # packages that has been added
    'removed': {}, # packages that has been removed
    'commitmessage': "", # commit message from the guy who is going to submit a repository update
    'light': {} # this stuff will be pushed to the light rss
}

# CACHING dictionaries
idpackageValidatorCache = {}
maskingReasonsStorage = {}
linkerPaths = []
# repository atoms updates digest cache
repositoryUpdatesDigestCache_disk = {}
fetch_repository_if_not_available_cache = {}
repo_error_messages_cache = set()

### Application disk cache
def const_resetCache():
    idpackageValidatorCache.clear()
    del linkerPaths[:]
    repositoryUpdatesDigestCache_disk.clear()
    fetch_repository_if_not_available_cache.clear()
    repo_error_messages_cache.clear()
    maskingReasonsStorage.clear()

# Client packages/database repositories
etpRepositories = {}
etpRepositoriesExcluded = {}
etpRepositoriesOrder = []

# remote section
etpRemoteFailures = {}  # dict of excluded mirrors due to failures, 
                        # it contains mirror name and failure count | > 5 == ignore mirror

# your bible
etpConst = {}
# database status dict
etpDbStatus = {}

# ===============================================================================================
# BEGINNING OF THE DYNAMIC SECTION
# ===============================================================================================

def initConfig_entropyConstants(rootdir):

    if rootdir and not os.path.isdir(rootdir):
        raise exceptionTools.FileNotFound("FileNotFound: not a valid chroot.")

    # save backed up settings
    if etpConst.has_key('backed_up'):
        backed_up_settings = etpConst.pop('backed_up')
    else:
        backed_up_settings = {}

    const_resetCache()
    const_defaultSettings(rootdir)
    const_readEntropyRelease()
    const_createWorkingDirectories()
    const_setupEntropyPid()
    const_readEntropySettings()
    const_readRepositoriesSettings()
    const_readSocketSettings()
    const_configureLockPaths()
    initConfig_clientConstants()
    # server stuff
    const_readReagentSettings()
    const_readServerSettings()
    const_readActivatorSettings()

    # reflow back settings
    etpConst.update(backed_up_settings)
    etpConst['backed_up'] = backed_up_settings.copy()
    const_setupWithEnvironment()

def initConfig_clientConstants():
    const_readEquoSettings()

def const_defaultSettings(rootdir):

    ETP_DIR = rootdir+"/var/lib/entropy"
    ETP_TMPDIR = "/tmp"
    ETP_RANDOM = str(random.random())[2:7]
    ETP_TMPFILE = "/.random-"+ETP_RANDOM+".tmp"
    ETP_REPODIR = "/packages/"+ETP_ARCH_CONST
    ETP_PORTDIR = rootdir+"/usr/portage"
    ETP_DISTFILESDIR = "/distfiles"
    ETP_DBDIR = "/database/"+ETP_ARCH_CONST
    ETP_DBFILE = "packages.db"
    ETP_DBCLIENTFILE = "equo.db"
    ETP_CLIENT_REPO_DIR = "/client"
    ETP_TRIGGERSDIR = "/triggers/"+ETP_ARCH_CONST
    ETP_SMARTAPPSDIR = "/smartapps/"+ETP_ARCH_CONST
    ETP_SMARTPACKAGESDIR = "/smartpackages/"+ETP_ARCH_CONST
    ETP_CACHESDIR = "/caches/"
    ETP_SECURITYDIR = "/glsa/"
    ETP_SETSDIRNAME = "sets"
    ETP_SETSDIR = "/%s/" % (ETP_SETSDIRNAME,)
    ETP_LOG_DIR = ETP_DIR+"/"+"logs"
    ETP_CONF_DIR = rootdir+"/etc/entropy"
    ETP_CONF_PACKAGES_DIR = ETP_CONF_DIR+"/packages"
    ETP_UGC_CONF_DIR = ETP_CONF_DIR+"/ugc"
    ETP_SYSLOG_DIR = rootdir+"/var/log/entropy/"
    ETP_VAR_DIR = rootdir+"/var/tmp/entropy"
    edbCOUNTER = rootdir+"/var/cache/edb/counter"

    etpConst.clear()
    myConst = {
        'server_repositories': {},
        'community': {
            'mode': False,
        },
        'backed_up': {},
        'sql_destroy': etpSQLInitDestroyAll,
        'sql_init': etpSQLInit,
        'installdir': '/usr/lib/entropy', # entropy default installation directory
        'packagestmpdir': ETP_DIR+ETP_TMPDIR, # etpConst['packagestmpdir'] --> temp directory
        'packagestmpfile': ETP_DIR+ETP_TMPDIR+ETP_TMPFILE, # etpConst['packagestmpfile'] --> general purpose tmp file
        'packagesbindir': ETP_DIR+ETP_REPODIR, # etpConst['packagesbindir'] --> repository where the packages will be stored
                            # by the clients: to query if a package has been already downloaded
                            # by the servers or rsync mirrors: to store already uploaded packages to the main rsync server
        'smartappsdir': ETP_DIR+ETP_SMARTAPPSDIR, # etpConst['smartappsdir'] location where smart apps files are places
        'smartpackagesdir': ETP_DIR+ETP_SMARTPACKAGESDIR, # etpConst['smartpackagesdir'] location where smart packages files are places
        'triggersdir': ETP_DIR+ETP_TRIGGERSDIR, # etpConst['triggersdir'] location where external triggers are placed
        'portagetreedir': ETP_PORTDIR, # directory where is stored our local portage tree
        'distfilesdir': ETP_PORTDIR+ETP_DISTFILESDIR, # directory where our sources are downloaded
        'confdir': ETP_CONF_DIR, # directory where entropy stores its configuration
        'confpackagesdir': ETP_CONF_PACKAGES_DIR, # same as above + /packages
        'confsetsdir': ETP_CONF_PACKAGES_DIR+ETP_SETSDIR, # system package sets dir
        'confsetsdirname': ETP_SETSDIRNAME, # just the dirname
        'entropyconf': ETP_CONF_DIR+"/entropy.conf", # entropy.conf file
        'repositoriesconf': ETP_CONF_DIR+"/repositories.conf", # repositories.conf file
        'activatorconf': ETP_CONF_DIR+"/activator.conf", # activator.conf file
        'serverconf': ETP_CONF_DIR+"/server.conf", # server.conf file (generic server side settings)
        'reagentconf': ETP_CONF_DIR+"/reagent.conf", # reagent.conf file
        'equoconf': ETP_CONF_DIR+"/equo.conf", # equo.conf file
        'socketconf': ETP_CONF_DIR+"/socket.conf", # socket.conf file
        'packagesrelativepath': "packages/"+ETP_ARCH_CONST+"/", # user by client interfaces

        'entropyworkdir': ETP_DIR, # Entropy workdir
        'entropyunpackdir': ETP_VAR_DIR, # Entropy unpack directory
        'entropyimagerelativepath': "image", # Entropy packages image directory
        'entropyxpakrelativepath': "xpak", # Gentoo xpak temp directory path
        'entropyxpakdatarelativepath': "data", # Gentoo xpak metadata directory path
        'entropyxpakfilename': "metadata.xpak", # Gentoo xpak metadata file name

        'etpdatabasesytemmaskfile': ETP_DBFILE+".system_mask", # file containing a list of packages that are strictly required by the repository, thus forced 
        'etpdatabasemaskfile': ETP_DBFILE+".mask",
        'etpdatabaseupdatefile': ETP_DBFILE+".repo_updates",
        'etpdatabaselicwhitelistfile': ETP_DBFILE+".lic_whitelist",
        'etpdatabaserevisionfile': ETP_DBFILE+".revision", # the local/remote database revision file
        'etpdatabasemissingdepsblfile': ETP_DBFILE+".missing_deps_blacklist", # missing dependencies black list file
        'etpdatabasehashfile': ETP_DBFILE+".md5", # its checksum
        'etpdatabasedumphashfilebz2': ETP_DBFILE+".dump.bz2.md5",
        'etpdatabasedumphashfilegzip': ETP_DBFILE+".dump.gz.md5",
        'etpdatabaselockfile': ETP_DBFILE+".lock", # the remote database lock file
        'etpdatabaseeapi3lockfile': ETP_DBFILE+".eapi3_lock", # the remote database lock file
        'etpdatabasedownloadlockfile': ETP_DBFILE+".download.lock", # the remote database download lock file
        'etpdatabasecacertfile': "ca.cert",
        'etpdatabaseservercertfile': "server.cert",
        'etpdatabasetaintfile': ETP_DBFILE+".tainted", # when this file exists, the database is not synced anymore with the online one
        'etpdatabasefile': ETP_DBFILE, # Entropy sqlite database file ETP_DIR+ETP_DBDIR+"/packages.db"
        'etpdatabasefilegzip': ETP_DBFILE+".gz", # Entropy sqlite database file (gzipped)
        'etpdatabasefilebzip2': ETP_DBFILE+".bz2", # Entropy sqlite database file (bzipped2)
        'etpdatabasedumpbzip2': ETP_DBFILE+".dump.bz2", # Entropy sqlite database dump file (bzipped2)
        'etpdatabasedumpgzip': ETP_DBFILE+".dump.gz", # Entropy sqlite database dump file (gzipped)
        'etpdatabasedump': ETP_DBFILE+".dump", # Entropy sqlite database dump file
        'etpdatabasefileformat': "bz2", # Entropy default compressed database format
        'etpdatabasesupportedcformats': ["bz2","gz"], # Entropy compressed databases format support
        'etpdatabasecompressclasses': {
            "bz2": ("bz2.BZ2File","unpackBzip2","etpdatabasefilebzip2","etpdatabasedumpbzip2","etpdatabasedumphashfilebz2"),
            "gz": ("gzip.GzipFile","unpackGzip","etpdatabasefilegzip","etpdatabasedumpgzip","etpdatabasedumphashfilegzip")
        },
        'rss-feed': True, # enable/disable packages RSS feed feature
        'rss-name': "packages.rss", # default name of the RSS feed
        'rss-light-name': "updates.rss", # light version
        'rss-base-url': "http://packages.sabayonlinux.org/", # default URL to the entropy web interface (overridden in reagent.conf)
        'rss-website-url': "http://www.sabayonlinux.org/", # default URL to the Operating System website (overridden in reagent.conf)
        'rss-dump-name': "rss_database_actions", # xml file where will be dumped etpRSSMessages dictionary
        'rss-max-entries': 10000, # maximum rss entries
        'rss-light-max-entries': 300, # max entries for the light version
        'rss-managing-editor': "lxnay@sabayonlinux.org", # updates submitter
        'rss-notice-board': "notice.rss", # repository RSS-based notice board content

        'packagesetprefix': "@",
        'userpackagesetsid': "__user__",
        'packagesext': ".tbz2",
        'packageshashfileext': ".md5", # Extension of the file that contains the checksum of its releated package file
        'packagesexpirationfileext': ".expired", # Extension of the file that "contains" expiration mtime
        'packagesexpirationdays': 15, # number of days after a package will be removed from mirrors
        'triggername': "trigger", # name of the trigger file that would be executed by equo inside triggerTools
        'proxy': {
            'ftp': None,
            'http': None,
            'username': None,
            'password': None
        }, # proxy configuration information, used system wide

        'entropyloglevel': 1, # # Entropy log level (default: 1 - see entropy.conf for more info)
        'socketloglevel': 2, # # Entropy Socket Interface log level
        'electronloglevel': 2, # # Entropy Socket Interface log level
        'equologlevel': 1, # # Equo log level (default: 1 - see equo.conf for more info)
        'spmloglevel': 1,
        'logdir': ETP_LOG_DIR , # Log dir where ebuilds store their stuff

        'syslogdir': ETP_SYSLOG_DIR, # Entropy system tools log directory
        'entropylogfile': ETP_SYSLOG_DIR+"entropy.log",
        'equologfile': ETP_SYSLOG_DIR+"equo.log",
        'spmlogfile': ETP_SYSLOG_DIR+"spm.log",
        'socketlogfile': ETP_SYSLOG_DIR+"socket.log",

        'etpdatabaseclientdir': ETP_DIR+ETP_CLIENT_REPO_DIR+ETP_DBDIR,
        'etpdatabaseclientfilepath': ETP_DIR+ETP_CLIENT_REPO_DIR+ETP_DBDIR+"/"+ETP_DBCLIENTFILE, # path to equo.db - client side database file
        'dbnamerepoprefix': "repo_", # prefix of the name of self.dbname in EntropyDatabaseInterface class for the repositories
        'dbbackupprefix': 'etp_backup_', # prefix of database backups

        'etpapi': etpSys['api'], # Entropy database API revision
        'currentarch': etpSys['arch'], # contains the current running architecture
        'supportedarchs': etpSys['archs'], # Entropy supported Archs

        'branches': [], # available branches, this only exists for the server part, these settings will be overridden by server.conf ones
        'branch': "4", # default choosen branch (overridden by setting in repositories.conf)
        'keywords': set([etpSys['arch'],"~"+etpSys['arch']]), # default allowed package keywords
        'gentoo-compat': True, # Gentoo compatibility (/var/db/pkg + Portage availability)
        'edbcounter': edbCOUNTER,
        'filesystemdirs': ['/bin','/emul','/etc','/lib','/lib32','/lib64','/opt','/sbin','/usr','/var'], # directory of the filesystem
        'filesystemdirsmask': [
                                    '/var/cache','/var/db','/var/empty','/var/log','/var/mail','/var/tmp','/var/www', '/usr/portage', '/usr/src', '/etc/skel', '/etc/ssh', '/etc/ssl', '/var/run', '/var/spool/cron', '/var/lib/init.d', '/lib/modules', '/etc/env.d', '/etc/gconf', '/etc/runlevels', '/lib/splash/cache', '/usr/share/mime', '/etc/portage', '/var/spool', '/var/lib', '/usr/lib/locale','/lib64/splash/cache'
        ],
        'libtest_blacklist': [],
        'libtest_files_blacklist': [],
        'officialserverrepositoryid': "sabayonlinux.org", # our official repository name
        'officialrepositoryid': "sabayonlinux.org", # our official repository name
        'conntestlink': "http://www.google.com",
        'databasestarttag': "|ENTROPY:PROJECT:DB:MAGIC:START|", # tag to append to .tbz2 file before entropy database (must be 32bytes)
        'pidfile': ETP_DIR+"/entropy.pid",
        'applicationlock': False,
        'filesbackup': True, # option to keep a backup of config files after being overwritten by equo conf update
        'collisionprotect': 1, # collision protection option, read equo.conf for more info
        'configprotect': [], # list of user specified CONFIG_PROTECT directories (see Gentoo manual to understand the meaining of this parameter)
        'configprotectmask': [], # list of user specified CONFIG_PROTECT_MASK directories
        'configprotectskip': [], # list of user specified configuration files that should be ignored and kept as they are
        'dbconfigprotect': [], # installed database CONFIG_PROTECT directories
        'dbconfigprotectmask': [], # installed database CONFIG_PROTECT_MASK directories
        'configprotectcounter': 0, # this will be used to show the number of updated files at the end of the processes
        'entropyversion': "1.0", # default Entropy release version
        'systemname': "Sabayon Linux", # default system name (overidden by entropy.conf settings)
        'product': "standard", # Product identificator (standard, professional...)
        'errorstatus': ETP_CONF_DIR+"/code",
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
            'global_make_conf': rootdir+"/etc/make.conf",
            'global_package_keywords': rootdir+"/etc/portage/package.keywords",
            'global_package_use': rootdir+"/etc/portage/package.use",
            'global_package_mask': rootdir+"/etc/portage/package.mask",
            'global_package_unmask': rootdir+"/etc/portage/package.unmask",
            'global_make_profile': rootdir+"/etc/make.profile",
            'global_make_profile_link_name' : "profile.link",
            'exec': rootdir+"/usr/bin/emerge", # source package manager executable
            'env_update_cmd': rootdir+"/usr/sbin/env-update",
            'source_profile': ["source",rootdir+"/etc/profile"],
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
                'counter': "COUNTER"
            },
            'system_packages': [],
            'ignore-spm-downgrades': False,
        },

        'downloadspeedlimit': None, # equo packages download speed limit (in kb/sec)

        'dumpstoragedir': ETP_DIR+ETP_CACHESDIR, # data storage directory, useful to speed up equo across multiple issued commands
        'securitydir': ETP_DIR+ETP_SECURITYDIR, # where GLSAs are stored
        'securityurl': "http://community.sabayonlinux.org/security/security-advisories.tar.bz2",

        # packages keywords/mask/unmask live settings
        'packagemaskingreasons': {
            0: _('reason not available'),
            1: _('user package.mask'),
            2: _('system keywords'),
            3: _('user package.unmask'),
            4: _('user repo package.keywords (all packages)'),
            5: _('user repo package.keywords'),
            6: _('user package.keywords'),
            7: _('completely masked'),
            8: _('repository general packages.db.mask'),
            9: _('repository in branch packages.db.mask'), # FIXME: this has been removed
            10: _('user license.mask'),
            11: _('user live unmask'),
            12: _('user live mask'),
        },
        'safemodeerrors': {
            'clientdb': 1,
        },
        'safemodereasons': {
            0: _("All fine"),
            1: _("Corrupted Entropy installed packages database. Please restore a backup."),
        },

        'misc_counters': {
            'forced_atoms_update_ids': {
                '__idtype__': 1,
                'kde': 1,
            },
        },

        # packages whose need their other installs (different tag), to be removed
        'conflicting_tagged_packages': {
            'x11-drivers/nvidia-drivers': ['x11-drivers/nvidia-drivers'],
            'x11-drivers/ati-drivers': ['x11-drivers/ati-drivers'],
        },

        'clientserverrepoid': "__system__",
        'clientdbid': "client",
        'serverdbid': "etpdb:",
        'genericdbid': "generic",
        'systemreleasefile': "/etc/sabayon-release",

        'socket_service': {
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
            'ssl_key': ETP_CONF_DIR+"/socket_server.key",
            'ssl_cert': ETP_CONF_DIR+"/socket_server.crt",
            'ssl_ca_cert': ETP_CONF_DIR+"/socket_server.CA.crt",
            'ssl_ca_pkey': ETP_CONF_DIR+"/socket_server.CA.key",
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
        'ugc_accessfile': ETP_UGC_CONF_DIR+"/access.xml",
        'ugc_voterange': range(1,6),

        # handler settings
        'handlers': {
            'md5sum': "md5sum.php?arch="+etpSys['arch']+"&package=", # md5sum handler,
            # XXX: hardcoded?
            'errorsend': "http://svn.sabayonlinux.org/entropy/standard/sabayonlinux.org/handlers/http_error_report.php",
        },

    }

    # set current nice level
    try:
        myConst['current_nice'] = os.nice(0)
    except OSError:
        pass

    etpConst.update(myConst)

def const_setNiceLevel(low = 0):
    default_nice = etpConst['default_nice']
    current_nice = etpConst['current_nice']
    delta = current_nice - default_nice
    try:
        etpConst['current_nice'] = os.nice(delta*-1+low)
    except OSError:
        pass
    return current_nice

def const_extractClientRepositoryParameters(repostring):

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
            except:
                pass
        repodatabase = repodatabase[:dbformatcolon]

    mydata = {}
    mydata['repoid'] = reponame
    mydata['service_port'] = eapi3_port
    mydata['ssl_service_port'] = eapi3_ssl_port
    mydata['description'] = repodesc
    mydata['packages'] = []
    mydata['plain_packages'] = []
    mydata['dbpath'] = etpConst['etpdatabaseclientdir']+"/"+reponame+"/"+etpConst['product']+"/"+etpConst['currentarch']+"/"+etpConst['branch']
    mydata['dbcformat'] = dbformat
    if not dbformat in etpConst['etpdatabasesupportedcformats']:
        mydata['dbcformat'] = etpConst['etpdatabasesupportedcformats'][0]
    mydata['plain_database'] = repodatabase
    mydata['database'] = repodatabase+"/"+etpConst['product']+"/"+reponame+"/database/"+etpConst['currentarch']+"/"+etpConst['branch']
    mydata['notice_board'] = mydata['database']+"/"+etpConst['rss-notice-board']
    mydata['local_notice_board'] = mydata['dbpath']+"/"+etpConst['rss-notice-board']
    mydata['dbrevision'] = "0"
    dbrevision_file = os.path.join(mydata['dbpath'],etpConst['etpdatabaserevisionfile'])
    if os.path.isfile(dbrevision_file) and os.access(dbrevision_file,os.R_OK):
        f = open(dbrevision_file,"r")
        mydata['dbrevision'] = f.readline().strip()
        f.close()
    # initialize CONFIG_PROTECT - will be filled the first time the db will be opened
    mydata['configprotect'] = None
    mydata['configprotectmask'] = None
    repopackages = [x.strip() for x in repopackages.split() if x.strip()]
    repopackages = [x for x in repopackages if (x.startswith('http://') or x.startswith('ftp://') or x.startswith('file://'))]
    for x in repopackages:
        mydata['plain_packages'].append(x)
        mydata['packages'].append(x+"/"+etpConst['product']+"/"+reponame)

    return reponame, mydata


def const_readRepositoriesSettings():

    etpRepositories.clear()
    etpRepositoriesExcluded.clear()
    del etpRepositoriesOrder[:]
    if os.path.isfile(etpConst['repositoriesconf']):
        f = open(etpConst['repositoriesconf'],"r")
        repositoriesconf = f.readlines()
        f.close()

        # setup product and branch first
        for line in repositoriesconf:
            if (line.strip().find("product|") != -1) and (not line.strip().startswith("#")) and (len(line.strip().split("|")) == 2):
                etpConst['product'] = line.strip().split("|")[1]
            elif (line.find("branch|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                branch = line.split("|")[1].strip()
                etpConst['branch'] = branch
                if not os.path.isdir(etpConst['packagesbindir']+"/"+branch):
                    if etpConst['uid'] == 0:
                        # check if we have a broken symlink
                        os.makedirs(etpConst['packagesbindir']+"/"+branch)

        for line in repositoriesconf:

            line = line.strip()
            # populate etpRepositories
            if (line.find("repository|") != -1) and (len(line.split("|")) == 5):

                excluded = False
                myRepodata = etpRepositories
                if line.startswith("##"):
                    continue
                elif line.startswith("#"):
                    excluded = True
                    myRepodata = etpRepositoriesExcluded
                    line = line[1:]

                reponame, repodata = const_extractClientRepositoryParameters(line)
                if myRepodata.has_key(reponame):
                    myRepodata[reponame]['plain_packages'].extend(repodata['plain_packages'])
                    myRepodata[reponame]['packages'].extend(repodata['packages'])
                    if (not myRepodata[reponame]['plain_database']) and repodata['plain_database']:
                        myRepodata[reponame]['plain_database'] = repodata['plain_database']
                        myRepodata[reponame]['database'] = repodata['database']
                        myRepodata[reponame]['dbrevision'] = repodata['dbrevision']
                        myRepodata[reponame]['dbcformat'] = repodata['dbcformat']
                else:
                    myRepodata[reponame] = repodata.copy()
                    if not excluded:
                        etpRepositoriesOrder.append(reponame)

            elif (line.find("officialrepositoryid|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                officialreponame = line.split("|")[1]
                etpConst['officialrepositoryid'] = officialreponame

            elif (line.find("conntestlink|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                conntestlink = line.split("|")[1]
                etpConst['conntestlink'] = conntestlink

            elif (line.find("downloadspeedlimit|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                try:
                    myval = int(line.split("|")[1])
                    if myval > 0:
                        etpConst['downloadspeedlimit'] = myval
                    else:
                        etpConst['downloadspeedlimit'] = None
                except (ValueError,IndexError,):
                    etpConst['downloadspeedlimit'] = None

            elif (line.find("securityurl|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                try:
                    url = line.split("|")[1]
                    etpConst['securityurl'] = url
                except:
                    pass

def const_readSocketSettings():
    if os.path.isfile(etpConst['socketconf']):
        f = open(etpConst['socketconf'],"r")
        socketconf = f.readlines()
        f.close()
        for line in socketconf:
            if line.startswith("listen|") and (len(line.split("|")) > 1):
                x = line.split("|")[1].strip()
                if x:
                    etpConst['socket_service']['hostname'] = x
            elif line.startswith("listen-port|") and (len(line.split("|")) > 1):
                x = line.split("|")[1].strip()
                try:
                    x = int(x)
                    etpConst['socket_service']['port'] = x
                except ValueError:
                    pass
            elif line.startswith("listen-timeout|") and (len(line.split("|")) > 1):
                x = line.split("|")[1].strip()
                try:
                    x = int(x)
                    etpConst['socket_service']['timeout'] = x
                except ValueError:
                    pass
            elif line.startswith("listen-threads|") and (len(line.split("|")) > 1):
                x = line.split("|")[1].strip()
                try:
                    x = int(x)
                    etpConst['socket_service']['threads'] = x
                except ValueError:
                    pass
            elif line.startswith("session-ttl|") and (len(line.split("|")) > 1):
                x = line.split("|")[1].strip()
                try:
                    x = int(x)
                    etpConst['socket_service']['session_ttl'] = x
                except ValueError:
                    pass
            elif line.startswith("max-connections|") and (len(line.split("|")) > 1):
                x = line.split("|")[1].strip()
                try:
                    x = int(x)
                    etpConst['socket_service']['max_connections'] = x
                except ValueError:
                    pass
            elif line.startswith("ssl-port|") and (len(line.split("|")) > 1):
                x = line.split("|")[1].strip()
                try:
                    x = int(x)
                    etpConst['socket_service']['ssl_port'] = x
                except ValueError:
                    pass
            elif line.startswith("disabled-commands|") and (len(line.split("|")) > 1):
                x = line.split("|")[1].strip().split()
                for y in x:
                    etpConst['socket_service']['disabled_cmds'].add(y)
            elif line.startswith("ip-blacklist|") and (len(line.split("|")) > 1):
                x = line.split("|")[1].strip().split()
                for y in x:
                    etpConst['socket_service']['ip_blacklist'].add(y)

def const_readEntropySettings():
    # entropy section
    if os.path.isfile(etpConst['entropyconf']):

        const_secure_config_file(etpConst['entropyconf'])

        f = open(etpConst['entropyconf'],"r")
        entropyconf = f.readlines()
        f.close()
        for line in entropyconf:
            if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
                loglevel = line.split("loglevel|")[1]
                try:
                    loglevel = int(loglevel)
                except ValueError:
                    pass
                if (loglevel > -1) and (loglevel < 3):
                    etpConst['entropyloglevel'] = loglevel

            elif line.startswith("ftp-proxy|") and (len(line.split("|")) == 2):
                ftpproxy = line.split("|")[1].strip().split()
                if ftpproxy:
                    etpConst['proxy']['ftp'] = ftpproxy[-1]
            elif line.startswith("http-proxy|") and (len(line.split("|")) == 2):
                httpproxy = line.split("|")[1].strip().split()
                if httpproxy:
                    etpConst['proxy']['http'] = httpproxy[-1]
            elif line.startswith("proxy-username|") and (len(line.split("|")) == 2):
                httpproxy = line.split("|")[1].strip().split()
                if httpproxy:
                    etpConst['proxy']['username'] = httpproxy[-1]
            elif line.startswith("proxy-password|") and (len(line.split("|")) == 2):
                httpproxy = line.split("|")[1].strip().split()
                if httpproxy:
                    etpConst['proxy']['password'] = httpproxy[-1]
            elif line.startswith("system-name|") and (len(line.split("|")) == 2):
                etpConst['systemname'] = line.split("|")[1].strip()
            elif line.startswith("nice-level|") and (len(line.split("|")) == 2):
                mylevel = line.split("|")[1].strip()
                try:
                    mylevel = int(mylevel)
                    if (mylevel >= -19) and (mylevel <= 19):
                        const_setNiceLevel(mylevel)
                except (ValueError,):
                    pass

def const_readEntropyRelease():
    # handle Entropy Version
    ETP_REVISION_FILE = "../libraries/revision"
    if not os.path.isfile(ETP_REVISION_FILE):
        ETP_REVISION_FILE = os.path.join(etpConst['installdir'],'libraries/revision')
    if os.path.isfile(ETP_REVISION_FILE):
        f = open(ETP_REVISION_FILE,"r")
        myrev = f.readline().strip()
        etpConst['entropyversion'] = myrev

def const_readEquoSettings():
    # equo section
    if (os.path.isfile(etpConst['equoconf'])):
        f = open(etpConst['equoconf'],"r")
        equoconf = f.readlines()
        f.close()
        for line in equoconf:
            if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
                loglevel = line.split("loglevel|")[1]
                try:
                    loglevel = int(loglevel)
                except:
                    pass
                if (loglevel > -1) and (loglevel < 3):
                    etpConst['equologlevel'] = loglevel

            elif line.startswith("filesbackup|") and (len(line.split("|")) == 2):
                compatopt = line.split("|")[1].strip()
                if compatopt.lower() in ("disable","disabled","false","0","no"):
                    etpConst['filesbackup'] = False

            elif line.startswith("ignore-spm-downgrades|") and (len(line.split("|")) == 2):
                compatopt = line.split("|")[1].strip()
                if compatopt.lower() in ("enable","enabled","true","1","yes"):
                    etpConst['spm']['ignore-spm-downgrades'] = True

            elif line.startswith("collisionprotect|") and (len(line.split("|")) == 2):
                collopt = line.split("|")[1].strip()
                if collopt.lower() in ("0","1","2",):
                    etpConst['collisionprotect'] = int(collopt)

            elif line.startswith("configprotect|") and (len(line.split("|")) == 2):
                configprotect = line.split("|")[1].strip()
                for x in configprotect.split():
                    etpConst['configprotect'].append(unicode(x,'raw_unicode_escape'))

            elif line.startswith("configprotectmask|") and (len(line.split("|")) == 2):
                configprotect = line.split("|")[1].strip()
                for x in configprotect.split():
                    etpConst['configprotectmask'].append(unicode(x,'raw_unicode_escape'))

            elif line.startswith("configprotectskip|") and (len(line.split("|")) == 2):
                configprotect = line.split("|")[1].strip()
                for x in configprotect.split():
                    etpConst['configprotectskip'].append(etpConst['systemroot']+x)

def const_setupEntropyPid(just_read = False):

    if ("--no-pid-handling" in sys.argv) and (not just_read):
        return

    # PID creation
    pid = os.getpid()
    if os.path.isfile(etpConst['pidfile']):

        f = open(etpConst['pidfile'],"r")
        foundPid = str(f.readline().strip())
        f.close()
        if foundPid != str(pid):
            # is foundPid still running ?
            if os.path.isdir("%s/proc/%s" % (etpConst['systemroot'],foundPid,)):
                etpConst['applicationlock'] = True
            elif not just_read:
                # if root, write new pid
                #if etpConst['uid'] == 0:
                if os.access(etpConst['pidfile'],os.W_OK):
                    try:
                        f = open(etpConst['pidfile'],"w")
                        f.write(str(pid))
                        f.flush()
                        f.close()
                    except IOError, e:
                        if e.errno == 30: # readonly filesystem
                            pass
                        else:
                            raise
                    try:
                        const_chmod_entropy_pid()
                    except OSError:
                        pass

    elif not just_read:
        #if etpConst['uid'] == 0:
        if os.access(os.path.dirname(etpConst['pidfile']),os.W_OK):

            if os.path.exists(etpConst['pidfile']):
                if os.path.islink(etpConst['pidfile']):
                    os.remove(etpConst['pidfile'])
                elif os.path.isdir(etpConst['pidfile']):
                    import shutil
                    shutil.rmtree(etpConst['pidfile'])

            f = open(etpConst['pidfile'],"w")
            f.write(str(pid))
            f.flush()
            f.close()

            try:
                const_chmod_entropy_pid()
            except OSError:
                pass

def const_secure_config_file(config_file):
    try:
        mygid = const_get_entropy_gid()
    except KeyError:
        mygid = 0
    try:
        const_setup_file(config_file, mygid, 0660)
    except (OSError, IOError,):
        pass

def const_chmod_entropy_pid():
    try:
        mygid = const_get_entropy_gid()
    except KeyError:
        mygid = 0
    const_setup_file(etpConst['pidfile'], mygid, 0664)

def const_createWorkingDirectories():

    # handle pid file
    piddir = os.path.dirname(etpConst['pidfile'])
    if not os.path.exists(piddir) and (etpConst['uid'] == 0):
        os.makedirs(piddir)

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
    for x in etpConst:
        if (type(etpConst[x]) is basestring):

            if not etpConst[x] or \
                etpConst[x].endswith(".conf") or \
                not os.path.isabs(etpConst[x]) or \
                etpConst[x].endswith(".cfg") or \
                etpConst[x].endswith(".tmp") or \
                etpConst[x].find(".db") != -1 or \
                etpConst[x].find(".log") != -1 or \
                os.path.isdir(etpConst[x]) or \
                not x.endswith("dir"):
                    continue

            # allow users to create dirs in custom paths,
            # so don't fail here even if we don't have permissions
            try:
                os.makedirs(etpConst[x])
            except OSError:
                pass

    if gid:
        etpConst['entropygid'] = gid
        '''
        change permissions of:
            /var/lib/entropy
            /var/tmp/entropy
        '''
        if not os.path.isdir(etpConst['entropyworkdir']):
            try:
                os.makedirs(etpConst['entropyworkdir'])
            except OSError:
                pass
        w_gid = os.stat(etpConst['entropyworkdir'])[stat.ST_GID]
        if w_gid != gid:
            const_setup_perms(etpConst['entropyworkdir'],gid)

        if not os.path.isdir(etpConst['entropyunpackdir']):
            try:
                os.makedirs(etpConst['entropyunpackdir'])
            except OSError:
                pass
        try:
            w_gid = os.stat(etpConst['entropyunpackdir'])[stat.ST_GID]
            if w_gid != gid:
                if os.path.isdir(etpConst['entropyunpackdir']):
                    const_setup_perms(etpConst['entropyunpackdir'],gid)
        except OSError:
            pass
        # always setup /var/lib/entropy/client permissions
        if not const_islive():
            # aufs/unionfs will start to leak otherwise
            const_setup_perms(etpConst['etpdatabaseclientdir'],gid)

def const_configureLockPaths():
    etpConst['locks'] = {
        'using_resources': os.path.join(etpConst['etpdatabaseclientdir'],'.using_resources'),
    }


def const_readActivatorSettings():

    if os.path.isfile(etpConst['activatorconf']):

        f = open(etpConst['activatorconf'],"r")
        actconffile = f.readlines()
        f.close()
        for line in actconffile:
            line = line.strip()
            if line.startswith("database-format|") and (len(line.split("database-format|")) == 2):
                format = line.split("database-format|")[1]
                if format in etpConst['etpdatabasesupportedcformats']:
                    etpConst['etpdatabasefileformat'] = format

def const_readReagentSettings():

    if (os.path.isfile(etpConst['reagentconf'])):
        f = open(etpConst['reagentconf'],"r")
        reagentconf = f.readlines()
        f.close()
        for line in reagentconf:

            if line.startswith("rss-feed|") and (len(line.split("rss-feed|")) == 2):
                feed = line.split("rss-feed|")[1]
                if feed in ("enable","enabled","true","1"):
                    etpConst['rss-feed'] = True
                elif feed in ("disable","disabled","false","0","no",):
                    etpConst['rss-feed'] = False
            elif line.startswith("rss-name|") and (len(line.split("rss-name|")) == 2):
                feedname = line.split("rss-name|")[1].strip()
                etpConst['rss-name'] = feedname
            elif line.startswith("rss-base-url|") and (len(line.split("rss-base-url|")) == 2):
                etpConst['rss-base-url'] = line.split("rss-base-url|")[1].strip()
                if not etpConst['rss-base-url'][-1] == "/":
                    etpConst['rss-base-url'] += "/"
            elif line.startswith("rss-website-url|") and (len(line.split("rss-website-url|")) == 2):
                etpConst['rss-website-url'] = line.split("rss-website-url|")[1].strip()
            elif line.startswith("managing-editor|") and (len(line.split("managing-editor|")) == 2):
                etpConst['rss-managing-editor'] = line.split("managing-editor|")[1].strip()
            elif line.startswith("max-rss-entries|") and (len(line.split("max-rss-entries|")) == 2):
                try:
                    entries = int(line.split("max-rss-entries|")[1].strip())
                    etpConst['rss-max-entries'] = entries
                except ValueError:
                    pass
            elif line.startswith("max-rss-light-entries|") and (len(line.split("max-rss-light-entries|")) == 2):
                try:
                    entries = int(line.split("max-rss-light-entries|")[1].strip())
                    etpConst['rss-light-max-entries'] = entries
                except ValueError:
                    pass

def const_readServerSettings():

    if not os.access(etpConst['serverconf'],os.R_OK):
        return

    etpConst['server_repositories'].clear()

    f = open(etpConst['serverconf'],"r")
    serverconf = f.readlines()
    f.close()

    for line in serverconf:

        if line.startswith("branches|") and (len(line.split("branches|")) == 2):
            branches = line.split("branches|")[1]
            etpConst['branches'] = []
            for branch in branches.split():
                etpConst['branches'].append(branch)
            if etpConst['branch'] not in etpConst['branches']:
                etpConst['branches'].append(etpConst['branch'])
            etpConst['branches'] = sorted(etpConst['branches'])

        elif (line.find("officialserverrepositoryid|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
            etpConst['officialserverrepositoryid'] = line.split("|")[1].strip()

        elif (line.find("expiration-days|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
            mydays = line.split("|")[1].strip()
            try:
                mydays = int(mydays)
                etpConst['packagesexpirationdays'] = mydays
            except ValueError:
                pass

        elif line.startswith("repository|") and (len(line.split("|")) in [5,6]):

            repoid, repodata = const_extractServerRepositoryParameters(line)
            if repoid in etpConst['server_repositories']:
                # just update mirrors
                etpConst['server_repositories'][repoid]['mirrors'].extend(repodata['mirrors'])
            else:
                etpConst['server_repositories'][repoid] = repodata.copy()

    const_configureServerRepoPaths()

def const_extractServerRepositoryParameters(repostring):

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
        repohandlers = os.path.join(repohandlers,etpConst['product'],repoid,"handlers")
        mydata['handler'] = repohandlers
    uris = repouris.split()
    for uri in uris:
        mydata['mirrors'].append(uri)

    return repoid, mydata

def const_configureServerRepoPaths():

    #'packagesserverstoredir': ETP_DIR+"/server/"+ETP_DBREPODIR+"/"+ETP_STOREDIR,
    #'packagesserveruploaddir': ETP_DIR+"/server/"+ETP_DBREPODIR+"/"+ETP_UPLOADDIR,
    #'packagesserverbindir': ETP_DIR+"/server/"+ETP_DBREPODIR+"/"+ETP_REPODIR,
    #'etpdatabasedir': ETP_DIR+"/server/"+ETP_DBREPODIR+"/"+ETP_DBDIR,
    #'etpdatabasefilepath': ETP_DIR+"/server/"+ETP_DBREPODIR+"/"+ETP_DBDIR+"/"+ETP_DBFILE,
    # etpConst['server_repositories']

    for repoid in etpConst['server_repositories']:
        etpConst['server_repositories'][repoid]['packages_dir'] = \
            os.path.join(   etpConst['entropyworkdir'],
                            "server",
                            repoid,
                            "packages",
                            etpSys['arch']
                        )
        etpConst['server_repositories'][repoid]['store_dir'] = \
            os.path.join(   etpConst['entropyworkdir'],
                            "server",
                            repoid,
                            "store",
                            etpSys['arch']
                        )
        etpConst['server_repositories'][repoid]['upload_dir'] = \
            os.path.join(   etpConst['entropyworkdir'],
                            "server",
                            repoid,
                            "upload",
                            etpSys['arch']
                        )
        etpConst['server_repositories'][repoid]['database_dir'] = \
            os.path.join(   etpConst['entropyworkdir'],
                            "server",
                            repoid,
                            "database",
                            etpSys['arch']
                        )
        etpConst['server_repositories'][repoid]['packages_relative_path'] = \
            os.path.join(   etpConst['product'],
                            repoid,
                            "packages",
                            etpSys['arch']
                        )+"/"
        etpConst['server_repositories'][repoid]['database_relative_path'] = \
            os.path.join(   etpConst['product'],
                            repoid,
                            "database",
                            etpSys['arch']
                        )+"/"


def const_setupWithEnvironment():

    shell_repoid = os.getenv('ETP_REPO')
    if shell_repoid:
        etpConst['officialserverrepositoryid'] = shell_repoid

    expiration_days = os.getenv('ETP_EXPIRATION_DAYS')
    if expiration_days:
        try:
            expiration_days = int(expiration_days)
            etpConst['packagesexpirationdays'] = expiration_days
        except ValueError:
            pass


def const_setup_perms(mydir, gid):
    if gid == None:
        return
    for currentdir,subdirs,files in os.walk(mydir):
        try:
            cur_gid = os.stat(currentdir)[stat.ST_GID]
            if cur_gid != gid:
                os.chown(currentdir,-1,gid)
            cur_mod = const_get_chmod(currentdir)
            if cur_mod != oct(0775):
                os.chmod(currentdir,0775)
        except OSError:
            pass
        for item in files:
            item = os.path.join(currentdir,item)
            try:
                const_setup_file(item, gid, 0664)
            except OSError:
                pass

def const_setup_file(myfile, gid, chmod):
    cur_gid = os.stat(myfile)[stat.ST_GID]
    if cur_gid != gid:
        os.chown(myfile,-1,gid)
    cur_mod = const_get_chmod(myfile)
    if cur_mod != oct(chmod):
        os.chmod(myfile,chmod)

# you need to convert to int
def const_get_chmod(item):
    st = os.stat(item)[stat.ST_MODE]
    return oct(st & 0777)

def const_get_entropy_gid():
    group_file = os.path.join(etpConst['systemroot'],'/etc/group')
    if not os.path.isfile(group_file):
        raise KeyError
    f = open(group_file,"r")
    for line in f.readlines():
        if line.startswith('%s:' % (etpConst['sysgroup'],)):
            try:
                gid = int(line.split(":")[2])
            except ValueError:
                raise KeyError
            return gid
    raise KeyError

def const_add_entropy_group():
    group_file = os.path.join(etpConst['systemroot'],'/etc/group')
    if not os.path.isfile(group_file):
        raise KeyError
    ids = set()
    f = open(group_file,"r")
    for line in f.readlines():
        if line and line.split(":"):
            try:
                myid = int(line.split(":")[2])
            except ValueError:
                pass
            ids.add(myid)
    if ids:
        # starting from 1000, get the first free
        while 1:
            new_id = 1000
            if new_id not in ids:
                break
    else:
        new_id = 10000

    f.close()
    f = open(group_file,"aw")
    f.seek(0,2)
    app_line = "entropy:x:%s:\n" % (new_id,)
    f.write(app_line)
    f.flush()
    f.close()

def const_islive():
    if not os.path.isfile("/proc/cmdline"):
        return False
    f = open("/proc/cmdline")
    cmdline = f.readline().strip().split()
    f.close()
    if "cdroot" in cmdline:
        return True
    return False

# load config
initConfig_entropyConstants(etpSys['rootdir'])
