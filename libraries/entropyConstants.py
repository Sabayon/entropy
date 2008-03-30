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
    'needed': u"", # runtime libraries needed by the package
    'trigger': u"", # this will become a bool, containing info about external trigger presence
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
DROP TABLE IF EXISTS rundependencies;
DROP TABLE IF EXISTS rundependenciesxt;
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
    iddependency INTEGER
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
    idpackage INTEGER PRIMARY KEY,
    branch VARCHAR
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
    idneeded INTEGER
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
    branch VARCHAR
);

CREATE TABLE binkeywords (
    idpackage INTEGER,
    idkeyword INTEGER
);

CREATE TABLE licensedata (
    licensename VARCHAR UNIQUE,
    text BLOB,
    compressed INTEGER
);

CREATE TABLE licenses_accepted (
    licensename VARCHAR UNIQUE
);

"""

# ETP_ARCH_CONST setup
if os.uname()[4] == "x86_64":
    ETP_ARCH_CONST = "amd64"
else:
    ETP_ARCH_CONST = "x86"

etpSys = {
    'archs': ["x86", "amd64"],
    'api': '2',
    'arch': ETP_ARCH_CONST,
    'rootdir': "",
    'maxthreads': 100,
    'dirstoclean': set(),
    'serverside': False,
}

etpUi = {
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
    'dbInfo': 'info/db', # db data retrieval cache
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
    'repolist': 'repos/repolist'
}

# ahahaha
etpExitMessages = {
    0: "You should run equo --help",
    1: "You didn't run equo --help, did you?",
    2: "Did you even read equo --help??",
    3: "I give up. Run that equo --help !!!!!!!",
    4: "OH MY GOD. RUN equo --heeeeeeeeeeeeeelp",
    5: "Illiteracy is a huge problem in this world",
    6: "Ok i give up, you are hopeless",
    7: "Go to hell."
}

# information about what has been done on the database,
# those dicts will be dumped to a file and used by activator to update and upload .rss
etpRSSMessages = {
    'added': {}, # packages that has been added
    'removed': {}, # packages that has been removed
    'commitmessage': "", # commit message from the guy who is going to submit a repository update
    'light': {} # this stuff will be pushed to the light rss
}

# Handlers used by entropy to run and retrieve data remotely, using php helpers
etpHandlers = {}

# CACHING dictionaries
idpackageValidatorCache = {}
maskingReasonsStorage = {}
linkerPaths = set()
# repository atoms updates digest cache
repositoryUpdatesDigestCache_db = {}
repositoryUpdatesDigestCache_disk = {}
fetch_repository_if_not_available_cache = {}
repo_error_messages_cache = set()

### Application disk cache
def const_resetCache():
    idpackageValidatorCache.clear()
    linkerPaths.clear()
    repositoryUpdatesDigestCache_db.clear()
    repositoryUpdatesDigestCache_disk.clear()
    fetch_repository_if_not_available_cache.clear()
    repo_error_messages_cache.clear()
    maskingReasonsStorage.clear()

# Client packages/database repositories
etpRepositories = {}
etpRepositoriesExcluded = {}
etpRepositoriesOrder = []

# remote section
etpRemoteSupport = {}
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

    const_resetCache()
    const_defaultSettings(rootdir)
    const_defaultServerDbStatus()
    const_readEntropyRelease()
    const_createWorkingDirectories()
    if not "--no-pid-handling" in sys.argv:
        const_setupEntropyPid()
    const_readEntropySettings()
    const_readRepositoriesSettings()
    const_readRemoteSettings()
    const_readSocketSettings()
    const_configureLockPaths()
    initConfig_clientConstants()

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
    ETP_UPLOADDIR = "/upload/"+ETP_ARCH_CONST
    ETP_STOREDIR = "/store/"+ETP_ARCH_CONST
    ETP_TRIGGERSDIR = "/triggers/"+ETP_ARCH_CONST
    ETP_SMARTAPPSDIR = "/smartapps/"+ETP_ARCH_CONST
    ETP_SMARTPACKAGESDIR = "/smartpackages/"+ETP_ARCH_CONST
    ETP_CACHESDIR = "/caches/"
    ETP_SECURITYDIR = "/glsa/"
    ETP_LOG_DIR = ETP_DIR+"/"+"logs"
    ETP_CONF_DIR = rootdir+"/etc/entropy"
    ETP_SYSLOG_DIR = rootdir+"/var/log/entropy/"
    ETP_VAR_DIR = rootdir+"/var/tmp/entropy"
    edbCOUNTER = rootdir+"/var/cache/edb/counter"

    etpConst.clear()
    myConst = {
        'installdir': '/usr/lib/entropy', # entropy default installation directory
        'packagestmpdir': ETP_DIR+ETP_TMPDIR, # etpConst['packagestmpdir'] --> temp directory
        'packagestmpfile': ETP_DIR+ETP_TMPDIR+ETP_TMPFILE, # etpConst['packagestmpfile'] --> general purpose tmp file
        'packagesbindir': ETP_DIR+ETP_REPODIR, # etpConst['packagesbindir'] --> repository where the packages will be stored
                            # by the clients: to query if a package has been already downloaded
                            # by the servers or rsync mirrors: to store already uploaded packages to the main rsync server
        'smartappsdir': ETP_DIR+ETP_SMARTAPPSDIR, # etpConst['smartappsdir'] location where smart apps files are places
        'smartpackagesdir': ETP_DIR+ETP_SMARTPACKAGESDIR, # etpConst['smartpackagesdir'] location where smart packages files are places
        'triggersdir': ETP_DIR+ETP_TRIGGERSDIR, # etpConst['triggersdir'] location where external triggers are placed
        'packagesstoredir': ETP_DIR+ETP_STOREDIR, # etpConst['packagesstoredir'] --> directory where .tbz2 files are stored waiting for being processed by reagent
        'packagessuploaddir': ETP_DIR+ETP_UPLOADDIR, # etpConst['packagessuploaddir'] --> directory where .tbz2 files are stored waiting for being uploaded to our main mirror
        'portagetreedir': ETP_PORTDIR, # directory where is stored our local portage tree
        'distfilesdir': ETP_PORTDIR+ETP_DISTFILESDIR, # directory where our sources are downloaded
        'confdir': ETP_CONF_DIR, # directory where entropy stores its configuration
        'entropyconf': ETP_CONF_DIR+"/entropy.conf", # entropy.conf file
        'repositoriesconf': ETP_CONF_DIR+"/repositories.conf", # repositories.conf file
        'activatorconf': ETP_CONF_DIR+"/activator.conf", # activator.conf file
        'serverconf': ETP_CONF_DIR+"/server.conf", # server.conf file (generic server side settings)
        'reagentconf': ETP_CONF_DIR+"/reagent.conf", # reagent.conf file
        'remoteconf': ETP_CONF_DIR+"/remote.conf", # remote.conf file
        'equoconf': ETP_CONF_DIR+"/equo.conf", # equo.conf file
        'socketconf': ETP_CONF_DIR+"/socket.conf", # socket.conf file
        'activatoruploaduris': [], # list of URIs that activator can use to upload files (parsed from activator.conf)
        'activatordownloaduris': [], # list of URIs that activator can use to fetch data
        'binaryurirelativepath': "packages/"+ETP_ARCH_CONST+"/", # Relative remote path for the binary repository.
        'etpurirelativepath': "database/"+ETP_ARCH_CONST+"/", # database relative path

        'entropyworkdir': ETP_DIR, # Entropy workdir
        'entropyunpackdir': ETP_VAR_DIR, # Entropy unpack directory
        'entropyimagerelativepath': "image", # Entropy packages image directory
        'entropyxpakrelativepath': "xpak", # Gentoo xpak temp directory path
        'entropyxpakdatarelativepath': "data", # Gentoo xpak metadata directory path
        'entropyxpakfilename': "metadata.xpak", # Gentoo xpak metadata file name

        'etpdatabasemaskfile': ETP_DBFILE+".mask", # the local/remote database revision file
        'etpdatabaseupdatefile': ETP_DBFILE+".repo_updates", # the local/remote database revision file
        'etpdatabaselicwhitelistfile': ETP_DBFILE+".lic_whitelist", # the local/remote database revision file
        'etpdatabaserevisionfile': ETP_DBFILE+".revision", # the local/remote database revision file
        'etpdatabasehashfile': ETP_DBFILE+".md5", # its checksum
        'etpdatabasedumphashfilebz2': ETP_DBFILE+".dump.bz2.md5",
        'etpdatabasedumphashfilegzip': ETP_DBFILE+".dump.gz.md5",
        'etpdatabaselockfile': ETP_DBFILE+".lock", # the remote database lock file
        'etpdatabasedownloadlockfile': ETP_DBFILE+".download.lock", # the remote database download lock file
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

        'packageshashfileext': ".md5", # Extension of the file that contains the checksum of its releated package file
        'packagesexpirationfileext': ".expired", # Extension of the file that "contains" expiration mtime
        'packagesexpirationdays': 15, # number of days after a package will be removed from mirrors
        'triggername': "trigger", # name of the trigger file that would be executed by equo inside triggerTools
        'proxy': {}, # proxy configuration information, used system wide

        'reagentloglevel': 1 , # Reagent log level (default: 1 - see reagent.conf for more info)
        'activatorloglevel': 1, # # Activator log level (default: 1 - see activator.conf for more info)
        'entropyloglevel': 1, # # Entropy log level (default: 1 - see entropy.conf for more info)
        'equologlevel': 1, # # Equo log level (default: 1 - see equo.conf for more info)
        'logdir': ETP_LOG_DIR , # Log dir where ebuilds store their stuff

        'syslogdir': ETP_SYSLOG_DIR, # Entropy system tools log directory
        'reagentlogfile': ETP_SYSLOG_DIR+"reagent.log", # Reagent operations log file
        'activatorlogfile': ETP_SYSLOG_DIR+"activator.log", # Activator operations log file
        'entropylogfile': ETP_SYSLOG_DIR+"entropy.log", # Activator operations log file
        'equologfile': ETP_SYSLOG_DIR+"equo.log", # Activator operations log file
        'socketlogfile': ETP_SYSLOG_DIR+"socket.log", # Activator operations log file

        'etpdatabasedir': ETP_DIR+ETP_DBDIR,
        'etpdatabasefilepath': ETP_DIR+ETP_DBDIR+"/"+ETP_DBFILE,
        'etpdatabaseclientdir': ETP_DIR+ETP_CLIENT_REPO_DIR+ETP_DBDIR,
        'etpdatabaseclientfilepath': ETP_DIR+ETP_CLIENT_REPO_DIR+ETP_DBDIR+"/"+ETP_DBCLIENTFILE, # path to equo.db - client side database file
        'dbnamerepoprefix': "repo_", # prefix of the name of self.dbname in etpDatabase class for the repositories

        'etpapi': etpSys['api'], # Entropy database API revision
        'currentarch': etpSys['arch'], # contains the current running architecture
        'supportedarchs': etpSys['archs'], # Entropy supported Archs

        'branches': [], # available branches, this only exists for the server part, these settings will be overridden by server.conf ones
        'branch': "3.5", # default choosen branch (overridden by setting in repositories.conf)
        'keywords': set([etpSys['arch'],"~"+etpSys['arch']]), # default allowed package keywords
        'gentoo-compat': False, # Gentoo compatibility (/var/db/pkg + Portage availability)
        'edbcounter': edbCOUNTER,
        'filesystemdirs': ['/bin','/emul','/etc','/lib','/lib32','/lib64','/opt','/sbin','/usr','/var'], # directory of the filesystem
        'filesystemdirsmask': [
                                    '/var/cache','/var/db','/var/empty','/var/log','/var/mail','/var/tmp','/var/www', '/usr/portage', '/usr/src', '/etc/skel', '/etc/ssh', '/etc/ssl', '/var/run', '/var/spool/cron', '/var/lib/init.d', '/lib/modules', '/etc/env.d', '/etc/gconf', '/etc/runlevels', '/lib/splash/cache', '/usr/share/mime', '/etc/portage', '/var/spool', '/var/lib', '/usr/lib/locale','/lib64/splash/cache'
        ],
        'libtest_blacklist': [
            'www-client/mozilla-firefox-bin',
            'dev-java/blackdown-jdk',
        ],
        'libtest_files_blacklist': [
            '/usr/lib64/openmotif-2.2/libMrm.so.3',
            '/usr/lib64/openmotif-2.2/libXm.so.3',
            '/usr/lib/openmotif-2.2/libMrm.so.3',
            '/usr/lib/openmotif-2.2/libXm.so.3'
        ],
        'officialrepositoryid': "sabayonlinux.org", # our official repository name
        'conntestlink': "http://www.google.com", 
        'databasestarttag': "|ENTROPY:PROJECT:DB:MAGIC:START|", # tag to append to .tbz2 file before entropy database (must be 32bytes)
        'pidfile': "/var/run/equo.pid",
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
        'treeupdatescalled': False, # to avoid running tree updates functions multiple times
        'spm': {
                    'exec': "/usr/bin/emerge", # source package manager executable
                    'ask_cmd': "--ask",
                    'pretend_cmd': "--pretend",
                    'verbose_cmd': "--verbose",
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
                    'system_packages': [
                        "sys-kernel/linux-sabayon", # our kernel
                        "dev-db/sqlite", # our interface
                        "dev-python/pysqlite",  # our python interface to our interface
                        "virtual/cron", # our cron service
                        "app-admin/equo", # our package manager (client)
                        "sys-apps/entropy" # our package manager (server+client)
                    ],
        },

        'downloadspeedlimit': None, # equo packages download speed limit (in kb/sec)

        'dumpstoragedir': ETP_DIR+ETP_CACHESDIR, # data storage directory, useful to speed up equo across multiple issued commands
        'securitydir': ETP_DIR+ETP_SECURITYDIR, # where GLSAs are stored
        'securityurl': "http://packages.sabayonlinux.org/security/security-advisories.tar.bz2",

        # packages keywords/mask/unmask settings
        'packagemasking': None, # package masking information dictionary filled by the masking parser
        'packagemaskingreasons': {
            1: 'user package.mask',
            2: 'system keywords',
            3: 'user package.unmask',
            4: 'user repo package.keywords (all packages)',
            5: 'user repo package.keywords',
            6: 'user package.keywords',
            7: 'completely masked',
            8: 'repository general packages.db.mask',
            9: 'repository in branch packages.db.mask',
            10: 'user license.mask'
        },

        # packages whose need their other installs (different tag), to be removed
        'conflicting_tagged_packages': {
            'x11-drivers/nvidia-drivers': ['x11-drivers/nvidia-drivers'],
            'x11-drivers/ati-drivers': ['x11-drivers/ati-drivers'],
        },

        'clientdbid': "client",
        'serverdbid': "etpdb",
        'systemreleasefile': "/etc/sabayon-release",

        'socket_service': {
            'hostname': "localhost",
            'port': 999,
            'timeout': 200,
            'threads': 5,
            'session_ttl': 120,
            'default_uid': 0,
            'max_connections': 5,
            'answers': {
                'ok': chr(0)+"OK\n"+chr(0), # command run
                'er': chr(0)+"ER\n"+chr(1), # execution error
                'no': chr(0)+"NO\n"+chr(2), # not allowed
                'cl': chr(0)+"CL\n"+chr(3), # close connection
                'eot': chr(0)+"EOT\n"+chr(4), # end of transmittion
                'mcr': chr(0)+"MCR\n"+chr(4) # max connections reached
            },
        }

    }
    etpConst.update(myConst)

def const_readRepositoriesSettings():

    etpRepositories.clear()
    etpRepositoriesExcluded.clear()
    del etpRepositoriesOrder[:]
    if os.path.isfile(etpConst['repositoriesconf']):
        f = open(etpConst['repositoriesconf'],"r")
        repositoriesconf = f.readlines()
        f.close()

        # setup product first
        for line in repositoriesconf:
            if (line.strip().find("product|") != -1) and (not line.strip().startswith("#")) and (len(line.strip().split("|")) == 2):
                etpConst['product'] = line.strip().split("|")[1]

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

                reponame = line.split("|")[1]
                repodesc = line.split("|")[2]
                repopackages = line.split("|")[3]
                repodatabase = line.split("|")[4]
                dbformat = etpConst['etpdatabasefileformat']
                dbformatcolon = repodatabase.rfind("#")
                if dbformatcolon != -1:
                    if dbformat in etpConst['etpdatabasesupportedcformats']:
                        try:
                            dbformat = repodatabase[dbformatcolon+1:]
                        except:
                            pass
                    repodatabase = repodatabase[:dbformatcolon]

                if ((repopackages.startswith("http://") or repopackages.startswith("ftp://") or repopackages.startswith("file://")) and \
                        (repodatabase.startswith("http://") or repodatabase.startswith("ftp://") or repodatabase.startswith("file://"))) or \
                         ((not repodatabase) and (myRepodata.has_key(reponame))):

                    if not myRepodata.has_key(reponame):
                        myRepodata[reponame] = {}
                        myRepodata[reponame]['description'] = repodesc
                        myRepodata[reponame]['packages'] = []
                        myRepodata[reponame]['dbpath'] = etpConst['etpdatabaseclientdir']+"/"+reponame+"/"+etpConst['product']+"/"+etpConst['currentarch']
                        myRepodata[reponame]['dbcformat'] = dbformat
                        myRepodata[reponame]['database'] = repodatabase+"/"+etpConst['product']+"/database/"+etpConst['currentarch']

                        myRepodata[reponame]['dbrevision'] = "0"
                        dbrevision_file = os.path.join(myRepodata[reponame]['dbpath'],etpConst['etpdatabaserevisionfile'])
                        if os.path.isfile(dbrevision_file):
                            rev_file = open(dbrevision_file,"r")
                            myRepodata[reponame]['dbrevision'] = rev_file.readline().strip()
                            rev_file.close()
                            del rev_file

                        # initialize CONFIG_PROTECT - will be filled the first time the db will be opened
                        myRepodata[reponame]['configprotect'] = None
                        myRepodata[reponame]['configprotectmask'] = None

                        if not excluded:
                            etpRepositoriesOrder.append(reponame)

                    for x in repopackages.split():
                        myRepodata[reponame]['packages'].append(x+"/"+etpConst['product'])

            elif (line.find("branch|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                branch = line.split("|")[1]
                etpConst['branch'] = branch
                if not os.path.isdir(etpConst['packagesbindir']+"/"+branch):
                    if etpConst['uid'] == 0:
                        # check if we have a broken symlink
                        os.makedirs(etpConst['packagesbindir']+"/"+branch)

            elif (line.find("officialrepositoryid|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                officialreponame = line.split("|")[1]
                etpConst['officialrepositoryid'] = officialreponame

            elif (line.find("conntestlink|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                conntestlink = line.split("|")[1]
                etpConst['conntestlink'] = conntestlink

            elif (line.find("downloadspeedlimit|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                try:
                    etpConst['downloadspeedlimit'] = int(line.split("|")[1])
                except:
                    etpConst['downloadspeedlimit'] = None

            elif (line.find("securityurl|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
                try:
                    url = line.split("|")[1]
                    etpConst['securityurl'] = url
                except:
                    pass

    # handler settings
    etpHandlers.clear()
    etpHandlers['md5sum'] = "md5sum.php?arch="+etpConst['currentarch']+"&package=" # md5sum handler
    etpHandlers['errorsend'] = "http://svn.sabayonlinux.org/entropy/%s/handlers/http_error_report.php" % (etpConst['product'],)

    # align etpConst['binaryurirelativepath'] and etpConst['etpurirelativepath'] with etpConst['product']
    etpConst['binaryurirelativepath'] = etpConst['product']+"/"+etpConst['binaryurirelativepath']
    etpConst['etpurirelativepath'] = etpConst['product']+"/"+etpConst['etpurirelativepath']

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

def const_readEntropySettings():
    # entropy section
    if os.path.isfile(etpConst['entropyconf']):
        f = open(etpConst['entropyconf'],"r")
        entropyconf = f.readlines()
        f.close()
        for line in entropyconf:
            if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
                loglevel = line.split("loglevel|")[1]
                try:
                    loglevel = int(loglevel)
                except:
                    print "ERROR: invalid loglevel in: "+etpConst['entropyconf']
                if (loglevel > -1) and (loglevel < 3):
                    etpConst['entropyloglevel'] = loglevel
                else:
                    print "WARNING: invalid loglevel in: "+etpConst['entropyconf']

            elif line.startswith("ftp-proxy|") and (len(line.split("|")) == 2):
                ftpproxy = line.split("|")[1].strip().split()
                if ftpproxy:
                    etpConst['proxy']['ftp'] = ftpproxy[-1]
            elif line.startswith("http-proxy|") and (len(line.split("|")) == 2):
                httpproxy = line.split("|")[1].strip().split()
                if httpproxy:
                    etpConst['proxy']['http'] = httpproxy[-1]
            elif line.startswith("system-name|") and (len(line.split("|")) == 2):
                etpConst['systemname'] = line.split("|")[1].strip()

def const_readRemoteSettings():
    etpRemoteSupport.clear()
    etpRemoteFailures.clear()
    if (os.path.isfile(etpConst['remoteconf'])):
        f = open(etpConst['remoteconf'],"r")
        remoteconf = f.readlines()
        f.close()
        for line in remoteconf:
            if line.startswith("handler|") and (len(line.split("|")) > 2):
                servername = line.split("|")[1].strip()
                url = line.split("|")[2].strip()
                if not url.endswith("/"):
                    url = url+"/"
                url += etpConst['product']+"/handlers/"
                etpRemoteSupport[servername] = url

def const_defaultServerDbStatus():
    # load server database status
    myDatabase = {
        etpConst['etpdatabasefilepath']: {
            'bumped': False,
            'tainted': False
        }
    }
    if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile']):
        myDatabase[etpConst['etpdatabasefilepath']]['tainted'] = True
        myDatabase[etpConst['etpdatabasefilepath']]['bumped'] = True
    etpDbStatus.update(myDatabase)
    del myDatabase

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

            elif line.startswith("gentoo-compat|") and (len(line.split("|")) == 2):
                compatopt = line.split("|")[1].strip()
                if compatopt == "disable":
                    etpConst['gentoo-compat'] = False
                else:
                    etpConst['gentoo-compat'] = True

            elif line.startswith("filesbackup|") and (len(line.split("|")) == 2):
                compatopt = line.split("|")[1].strip()
                if compatopt == "disable":
                    etpConst['filesbackup'] = False

            elif line.startswith("collisionprotect|") and (len(line.split("|")) == 2):
                collopt = line.split("|")[1].strip()
                if collopt == "0" or collopt == "1" or collopt == "2":
                    etpConst['collisionprotect'] = int(collopt)

            elif line.startswith("configprotect|") and (len(line.split("|")) == 2):
                configprotect = line.split("|")[1].strip()
                for x in configprotect.split():
                    etpConst['configprotect'].append(x)

            elif line.startswith("configprotectmask|") and (len(line.split("|")) == 2):
                configprotect = line.split("|")[1].strip()
                for x in configprotect.split():
                    etpConst['configprotectmask'].append(x)

            elif line.startswith("configprotectskip|") and (len(line.split("|")) == 2):
                configprotect = line.split("|")[1].strip()
                for x in configprotect.split():
                    etpConst['configprotectskip'].append(etpConst['systemroot']+x)

def const_setupEntropyPid():
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
            else:
                # if root, write new pid
                if etpConst['uid'] == 0:
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

    else:
        if etpConst['uid'] == 0:

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
        w_gid = os.stat(etpConst['entropyworkdir'])[5]
        if w_gid != gid:
            const_setup_perms(etpConst['entropyworkdir'],gid)

        if not os.path.isdir(etpConst['entropyunpackdir']):
            try:
                os.makedirs(etpConst['entropyunpackdir'])
            except OSError:
                pass
        try:
            w_gid = os.stat(etpConst['entropyunpackdir'])[5]
            if w_gid != gid:
                if os.path.isdir(etpConst['entropyunpackdir']):
                    const_setup_perms(etpConst['entropyunpackdir'],gid)
        except OSError:
            pass
        # always setup /var/lib/entropy/client permissions
        const_setup_perms(etpConst['etpdatabaseclientdir'],gid)

def const_configureLockPaths():
    etpConst['locks'] = {
        'reposync': os.path.join(etpConst['etpdatabaseclientdir'],'.lock_reposync'),
        'securitysync': os.path.join(etpConst['securitydir'],'.lock_securitysync'),
        'packagehandling': os.path.join(etpConst['etpdatabaseclientdir'],'.lock_packagehandling'),
    }

def const_setup_perms(mydir, gid):
    if gid == None:
        return
    for currentdir,subdirs,files in os.walk(mydir):
        try:
            os.chown(currentdir,-1,gid)
            os.chmod(currentdir,0775)
        except OSError:
            pass
        for item in files:
            item = os.path.join(currentdir,item)
            try:
                os.chown(item,-1,gid)
                os.chmod(item,0664)
            except OSError:
                pass

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
    print new_id
    f.close()
    f = open(group_file,"aw")
    f.seek(0,2)
    app_line = "entropy:x:%s:\n" % (new_id,)
    f.write(app_line)
    f.flush()
    f.close()

# load config
initConfig_entropyConstants(etpSys['rootdir'])
