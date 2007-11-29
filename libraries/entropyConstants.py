#!/usr/bin/python
'''
    # DESCRIPTION:
    # Variables container

    Copyright (C) 2007 Fabio Erculiani

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

import os
import random
from sys import exit


# Specifications of the content of etpData
'''
etpData = {
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
    'binkeywords': u"", # supported ARCHs (by the BIN)
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
}
'''

# Entropy database SQL initialization Schema and data structure
etpSQLInitDestroyAll = """
DROP TABLE IF EXISTS etpData;
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
"""

etpSQLInit = """

CREATE TABLE baseinfo (
    idpackage INTEGER PRIMARY KEY,
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
    idpackage INTEGER,
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
    iddependency INTEGER PRIMARY KEY,
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
    idsource INTEGER PRIMARY KEY,
    source VARCHAR
);

CREATE TABLE useflags (
    idpackage INTEGER,
    idflag INTEGER
);

CREATE TABLE useflagsreference (
    idflag INTEGER PRIMARY KEY,
    flagname VARCHAR
);

CREATE TABLE keywords (
    idpackage INTEGER,
    idkeyword INTEGER
);

CREATE TABLE binkeywords (
    idpackage INTEGER,
    idkeyword INTEGER
);

CREATE TABLE keywordsreference (
    idkeyword INTEGER PRIMARY KEY,
    keywordname VARCHAR
);

CREATE TABLE categories (
    idcategory INTEGER PRIMARY KEY,
    category VARCHAR
);

CREATE TABLE licenses (
    idlicense INTEGER PRIMARY KEY,
    license VARCHAR
);

CREATE TABLE flags (
    idflags INTEGER PRIMARY KEY,
    chost VARCHAR,
    cflags VARCHAR,
    cxxflags VARCHAR
);

CREATE TABLE configprotect (
    idpackage INTEGER,
    idprotect INTEGER
);

CREATE TABLE configprotectmask (
    idpackage INTEGER,
    idprotect INTEGER
);

CREATE TABLE configprotectreference (
    idprotect INTEGER PRIMARY KEY,
    protect VARCHAR
);

CREATE TABLE systempackages (
    idpackage INTEGER
);

CREATE TABLE installedtable (
    idpackage INTEGER,
    repositoryname VARCHAR
);

CREATE TABLE sizes (
    idpackage INTEGER,
    size INTEGER
);

CREATE TABLE messages (
    idpackage INTEGER,
    message VARCHAR
);

CREATE TABLE counters (
    counter INTEGER PRIMARY KEY,
    idpackage INTEGER
);

CREATE TABLE eclasses (
    idpackage INTEGER,
    idclass INTEGER
);

CREATE TABLE eclassesreference (
    idclass INTEGER PRIMARY KEY,
    classname VARCHAR
);

CREATE TABLE needed (
    idpackage INTEGER,
    idneeded INTEGER
);

CREATE TABLE neededreference (
    idneeded INTEGER PRIMARY KEY,
    library VARCHAR
);

"""

# Entropy directories specifications
# THIS IS THE KEY PART OF ENTROPY BINARY PACKAGES MANAGEMENT
# DO NOT EDIT THIS UNLESS YOU KNOW WHAT YOU'RE DOING !!
# the ARCHs that we support
ETP_ARCHS = ["x86", "amd64"] # maybe ppc someday
ETP_API = "1"
# ETP_ARCH_CONST setup
if os.uname()[4] == "x86_64":
    ETP_ARCH_CONST = "amd64"
else:
    ETP_ARCH_CONST = "x86"

ETP_DIR = "/var/lib/entropy"
ETP_TMPDIR = "/tmp"
ETP_RANDOM = str(random.random())[2:7]
ETP_TMPFILE = "/.random-"+ETP_RANDOM+".tmp"
ETP_REPODIR = "/packages/"+ETP_ARCH_CONST
ETP_PORTDIR = "/usr/portage"
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
ETP_XMLDIR = "/xml/"
ETP_CONF_DIR = "/etc/entropy"
ETP_ROOT_DIR = "/"
ETP_LOG_DIR = ETP_DIR+"/"+"logs"
ETP_SYSLOG_DIR = "/var/log/entropy/"
ETP_VAR_DIR = "/var/tmp/entropy"
ETP_LOGLEVEL_NORMAL = 1
ETP_LOGLEVEL_VERBOSE = 2
ETP_LOGPRI_INFO = "[ INFO ]"
ETP_LOGPRI_WARNING = "[ WARNING ]"
ETP_LOGPRI_ERROR = "[ ERROR ]"

etpConst = {
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
    'databaseconf': ETP_CONF_DIR+"/database.conf", # database.conf file
    'mirrorsconf': ETP_CONF_DIR+"/mirrors.conf", # mirrors.conf file
    'remoteconf': ETP_CONF_DIR+"/remote.conf", # remote.conf file
    'spmbackendconf': ETP_CONF_DIR+"/spmbackend.conf", # spmbackend.conf file
    'equoconf': ETP_CONF_DIR+"/equo.conf", # equo.conf file
    'activatoruploaduris': [], # list of URIs that activator can use to upload files (parsed from activator.conf)
    'activatordownloaduris': [], # list of URIs that activator can use to fetch data
    'binaryurirelativepath': "packages/"+ETP_ARCH_CONST+"/", # Relative remote path for the binary repository.
    'etpurirelativepath': "database/"+ETP_ARCH_CONST+"/", # database relative path

    'entropyworkdir': ETP_DIR, # Entropy workdir
    'entropyunpackdir': ETP_VAR_DIR, # Entropy unpack directory

    'etpdatabaserevisionfile': ETP_DBFILE+".revision", # the local/remote database revision file
    'etpdatabasehashfile': ETP_DBFILE+".md5", # its checksum
    'etpdatabaselockfile': ETP_DBFILE+".lock", # the remote database lock file
    'etpdatabasedownloadlockfile': ETP_DBFILE+".download.lock", # the remote database download lock file
    'etpdatabasetaintfile': ETP_DBFILE+".tainted", # when this file exists, the database is not synced anymore with the online one
    'etpdatabasefile': ETP_DBFILE, # Entropy sqlite database file ETP_DIR+ETP_DBDIR+"/packages.db"
    'etpdatabasefilegzip': ETP_DBFILE+".gz", # Entropy sqlite database file (gzipped)
    'etpdatabasefilebzip2': ETP_DBFILE+".bz2", # Entropy sqlite database file (bzipped2)
    'etpdatabasefileformat': "bz2", # Entropy default compressed database format
    'etpdatabasesupportedcformats': ["bz2","gz"], # Entropy compressed databases format support
    'etpdatabasecompressclasses': {
    					"bz2": ("bz2.BZ2File","unpackBzip2","etpdatabasefilebzip2",),
					"gz": ("gzip.GzipFile","unpackGzip","etpdatabasefilegzip",)
    },
    'packageshashfileext': ".md5", # Extension of the file that contains the checksum of its releated package file
    'packagesexpirationfileext': ".expired", # Extension of the file that "contains" expiration mtime
    'packagesexpirationdays': 15, # number of days after a package will be removed from mirrors
    'triggername': "trigger", # name of the trigger file that would be executed by equo inside triggerTools
    'proxy': {}, # proxy configuration information, used system wide
    
    'databaseloglevel': 1, # Database log level (default: 1 - see database.conf for more info)
    'mirrorsloglevel': 1, # Mirrors log level (default: 1 - see mirrors.conf for more info)
    'remoteloglevel': 1, # Remote handlers (/handlers) log level (default: 1 - see remote.conf for more info)
    'reagentloglevel': 1 , # Reagent log level (default: 1 - see reagent.conf for more info)
    'activatorloglevel': 1, # # Activator log level (default: 1 - see activator.conf for more info)
    'entropyloglevel': 1, # # Entropy log level (default: 1 - see entropy.conf for more info)
    'equologlevel': 1, # # Equo log level (default: 1 - see equo.conf for more info)
    'spmbackendloglevel': 1, # # Source Package Manager backend log level (default: 1 - see entropy.conf for more info)
    'logdir': ETP_LOG_DIR , # Log dir where ebuilds store their stuff
    
    'syslogdir': ETP_SYSLOG_DIR, # Entropy system tools log directory
    'mirrorslogfile': ETP_SYSLOG_DIR+"/mirrors.log", # Mirrors operations log file
    'remotelogfile': ETP_SYSLOG_DIR+"/remote.log", # Mirrors operations log file
    'spmbackendlogfile': ETP_SYSLOG_DIR+"/spmbackend.log", # Source Package Manager backend configuration log file
    'databaselogfile': ETP_SYSLOG_DIR+"/database.log", # Database operations log file
    'reagentlogfile': ETP_SYSLOG_DIR+"/reagent.log", # Reagent operations log file
    'activatorlogfile': ETP_SYSLOG_DIR+"/activator.log", # Activator operations log file
    'entropylogfile': ETP_SYSLOG_DIR+"/entropy.log", # Activator operations log file
    'equologfile': ETP_SYSLOG_DIR+"/equo.log", # Activator operations log file
    
    'distccconf': "/etc/distcc/hosts", # distcc hosts configuration file FIXME: remove this?
    'etpdatabasedir': ETP_DIR+ETP_DBDIR,
    'etpdatabasefilepath': ETP_DIR+ETP_DBDIR+"/"+ETP_DBFILE,
    'etpdatabaseclientdir': ETP_DIR+ETP_CLIENT_REPO_DIR+ETP_DBDIR,
    'etpdatabaseclientfilepath': ETP_DIR+ETP_CLIENT_REPO_DIR+ETP_DBDIR+"/"+ETP_DBCLIENTFILE, # path to equo.db - client side database file
    'dbnamerepoprefix': "repo_", # prefix of the name of self.dbname in etpDatabase class for the repositories
    
    'etpapi': ETP_API, # Entropy database API revision
    'currentarch': ETP_ARCH_CONST, # contains the current running architecture
    'supportedarchs': ETP_ARCHS, # Entropy supported Archs
    
    'branches': [], # available branches, this only exists for the server part, these settings will be overridden by server.conf ones
    'branch': "3.5", # default choosen branch (overridden by setting in repositories.conf)
    'keywords': set([ETP_ARCH_CONST,"~"+ETP_ARCH_CONST]), # default allowed package keywords
    'gentoo-compat': False, # Gentoo compatibility (/var/db/pkg + Portage availability)
    'filesystemdirs': ['/bin','/boot','/emul','/etc','/lib','/lib32','/lib64','/opt','/sbin','/usr','/var'], # directory of the filesystem
    'filesystemdirsmask': [
    				'/var/cache','/var/db','/var/empty','/var/lib/portage','/var/lib/entropy','/var/log','/var/mail','/var/tmp','/var/www', '/usr/portage',
    				'/var/lib/scrollkeeper', '/usr/src', '/etc/skel', '/etc/ssh', '/etc/ssl', '/var/run', '/var/spool/cron', '/var/lib/init.d',
				'/lib/modules', '/etc/env.d', '/etc/gconf', '/etc/runlevels', '/lib/splash/cache', '/usr/share/mime', '/etc/portage'
    ],
    'officialrepositoryname': "sabayonlinux.org", # our official repository name
    'databasestarttag': "|ENTROPY:PROJECT:DB:MAGIC:START|", # tag to append to .tbz2 file before entropy database (must be 32bytes)
    'pidfile': "/var/run/equo.pid",
    'applicationlock': False,
    'collisionprotect': 1, # collision protection option, read equo.conf for more info
    'configprotect': [], # list of user specified CONFIG_PROTECT directories (see Gentoo manual to understand the meaining of this parameter)
    'configprotectmask': [], # list of user specified CONFIG_PROTECT_MASK directories
    'configprotectskip': [], # list of user specified configuration files that should be ignored and kept as they are
    'dbconfigprotect': [], # installed database CONFIG_PROTECT directories
    'dbconfigprotectmask': [], # installed database CONFIG_PROTECT_MASK directories
    'configprotectcounter': 0, # this will be used to show the number of updated files at the end of the processes
    'entropyversion': "1.0", # default Entropy release version
    'systemname': "Sabayon Linux", # default system name
    'product': "standard", # Product identificator (standard, professional...)
    'errorstatus': ETP_CONF_DIR+"/code",
    
    'dumpstoragedir': ETP_DIR+ETP_XMLDIR, # data storage directory, useful to speed up equo across multiple issued commands

    # packages keywords/mask/unmask settings
    'packagemasking': {}, # package masking information dictionary filled by maskingparser.py

}

# disk caching dictionary
etpCache = {
    'configfiles': 'scanfs', # used to store information about files that should be merged using "equo conf merge"
    'dbMatch': 'cache_', # used by the database controller as prefix to the cache files belonging to etpDatabase class (dep solving)
    'dbSearch': 'search_', # used by the database controller as prefix to the cache files belonging to etpDatabase class (searches)
    'dbInfo': 'info_', # used by the database controller as prefix to the cache files belonging to etpDatabase class (info retrival)
    'atomMatch': 'atomMatchCache', # used to store info about repository dependencies solving
    'generateDependsTree': 'generateDependsTreeCache', # used to store info about removal dependencies
    'install': 'resume_install', # resume cache (install)
    'remove': 'resume_remove', # resume cache (remove)
    'world': 'resume_world', # resume cache (world)
}

# byte sizes of disk caches
etpCacheSizes = {
    'dbMatch': 3000000, # bytes
    'dbInfo': 6000000, # bytes
    'dbSearch': 2000000, # bytes
    'atomMatch': 3000000, # bytes
    'generateDependsTree': 3000000, # bytes
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

### Application disk cache
dbCacheStore = {}
atomMatchCache = {}
atomClientMatchCache = {}
generateDependsTreeCache = {}
idpackageValidatorCache = {}
def const_resetCache():
    dbCacheStore.clear()
    atomMatchCache.clear()
    atomClientMatchCache.clear()
    generateDependsTreeCache.clear()
    idpackageValidatorCache.clear()

# handle Entropy Version
ETP_REVISION_FILE = "../libraries/revision"
if os.path.isfile(ETP_REVISION_FILE):
    f = open(ETP_REVISION_FILE,"r")
    myrev = f.readline().strip()
    etpConst['entropyversion'] = myrev

# handle pid file
piddir = os.path.dirname(etpConst['pidfile'])
if not os.path.exists(piddir):
    if os.getuid() == 0:
	os.makedirs(piddir)
    else:
        print "you need to run this as root at least once."
        exit(100)
# PID creation
pid = os.getpid()
if os.path.exists(etpConst['pidfile']):
    f = open(etpConst['pidfile'],"r")
    foundPid = f.readline().strip()
    f.close()
    if foundPid != str(pid):
	# is foundPid still running ?
	import commands
	pids = commands.getoutput("pidof python").split("\n")[0].split()
	try:
	    pids.index(foundPid)
	    etpConst['applicationlock'] = True
	except:
	    # if root, write new pid
	    if os.getuid() == 0:
		f = open(etpConst['pidfile'],"w")
		f.write(str(pid))
		f.flush()
		f.close()
	    pass
else:
    if os.getuid() == 0:
        f = open(etpConst['pidfile'],"w")
        f.write(str(pid))
        f.flush()
        f.close()
    else:
        print "you need to run this as root at least once."
        exit(100)

### file transfer settings
etpFileTransfer = {
    'datatransfer': 0,
    'oldgather': 0,
    'gather': 0,
    'elapsed': 0.0,
    'transferpollingtime': float(1)/4 # 0.25secs = 4Hz
}

# Create paths
if not os.path.isdir(etpConst['entropyworkdir']):
    if os.getuid() == 0:
	import re
	for x in etpConst:
	    if (type(etpConst[x]) is str):
		
	        if (not etpConst[x]) or (etpConst[x].endswith(".conf")) or (not etpConst[x].startswith("/")) or (etpConst[x].endswith(".cfg")) or (etpConst[x].endswith(".tmp")) or (etpConst[x].find(".db") != -1) or (etpConst[x].find(".log") != -1):
		    continue
		
		if etpConst[x].find("%ARCH%") != -1:
		    for i in ETP_ARCHS:
			try:
			    mdir = re.subn("%ARCH%",i, etpConst[x])[0]
			    os.makedirs(mdir,0755)
                            os.chown(mdir,0,0)
			except OSError:
			    pass
		else:
		    try:
		        os.makedirs(etpConst[x],0755)
		        os.chown(etpConst[x],0,0)
		    except OSError:
			pass
    else:
        print "you need to run this as root at least once."
        exit(100)


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
		exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['entropyloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['entropyconf']
		import time
		time.sleep(5)
        
	elif line.startswith("ftp-proxy|") and (len(line.split("|")) == 2):
	    ftpproxy = line.split("|")[1].strip()
	    for x in ftpproxy.split():
		etpConst['proxy']['ftp'] = ftpproxy
	elif line.startswith("http-proxy|") and (len(line.split("|")) == 2):
	    httpproxy = line.split("|")[1].strip()
	    for x in httpproxy.split():
		etpConst['proxy']['http'] = httpproxy
    


# Client packages/database repositories
etpRepositories = {}
etpRepositoriesOrder = set()
ordercount = 0
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
	if (line.find("repository|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 5):
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
	    if (repopackages.startswith("http://") or repopackages.startswith("ftp://")) and (repodatabase.startswith("http://") or repodatabase.startswith("ftp://")):
		etpRepositories[reponame] = {}
                ordercount += 1
		etpRepositoriesOrder.add((ordercount,reponame))
		etpRepositories[reponame]['description'] = repodesc
		etpRepositories[reponame]['packages'] = []
		for x in repopackages.split():
		    etpRepositories[reponame]['packages'].append(x+"/"+etpConst['product'])
		etpRepositories[reponame]['dbpath'] = etpConst['etpdatabaseclientdir']+"/"+reponame+"/"+etpConst['product']+"/"+etpConst['currentarch']
		etpRepositories[reponame]['dbcformat'] = dbformat
		etpRepositories[reponame]['database'] = repodatabase+"/"+etpConst['product']+"/database/"+etpConst['currentarch']
		# initialize CONFIG_PROTECT - will be filled the first time the db will be opened
		etpRepositories[reponame]['configprotect'] = None
		etpRepositories[reponame]['configprotectmask'] = None
	elif (line.find("branch|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
	    branch = line.split("|")[1]
	    etpConst['branch'] = branch
            if not os.path.isdir(etpConst['packagesbindir']+"/"+branch):
                if os.getuid() == 0:
                    os.makedirs(etpConst['packagesbindir']+"/"+branch)
                else:
                    print "ERROR: please run this as root at least once or create: "+str(etpConst['packagesbindir']+"/"+branch)
                    exit(49)

# align etpConst['binaryurirelativepath'] and etpConst['etpurirelativepath'] with etpConst['product']
etpConst['binaryurirelativepath'] = etpConst['product']+"/"+etpConst['binaryurirelativepath']
etpConst['etpurirelativepath'] = etpConst['product']+"/"+etpConst['etpurirelativepath']

# check for packages and upload directories
if os.getuid() == 0:
    for x in etpConst['branches']:
        if not os.path.isdir(etpConst['packagesbindir']+"/"+x):
	    os.makedirs(etpConst['packagesbindir']+"/"+x)
        if not os.path.isdir(etpConst['packagessuploaddir']+"/"+x):
	    os.makedirs(etpConst['packagessuploaddir']+"/"+x)

# database section
if os.path.isfile(etpConst['databaseconf']):
    f = open(etpConst['databaseconf'],"r")
    databaseconf = f.readlines()
    f.close()
    for line in databaseconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['databaseconf']
		exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['databaseloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['databaseconf']
		import time
		time.sleep(5)

# Handlers used by entropy to run and retrieve data remotely, using php helpers
etpHandlers = {
    'md5sum': "md5sum.php?arch="+ETP_ARCH_CONST+"&package=", # md5sum handler
    'errorsend': "http://svn.sabayonlinux.org/entropy/"+etpConst['product']+"/handlers/error_report.php?arch="+ETP_ARCH_CONST+"&stacktrace=",
}

# remote section
etpRemoteSupport = {}
etpRemoteFailures = {} # dict of excluded mirrors due to failures, it contains mirror name and failure count | > 5 == ignore mirror
if (os.path.isfile(etpConst['remoteconf'])):
    f = open(etpConst['remoteconf'],"r")
    remoteconf = f.readlines()
    f.close()
    for line in remoteconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "WARNING: invalid loglevel in: "+etpConst['remoteconf']
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['remoteloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['remoteconf']

	if line.startswith("handler|") and (len(line.split("|")) > 2):
	    servername = line.split("|")[1].strip()
	    url = line.split("|")[2].strip()
	    if not url.endswith("/"):
		url = url+"/"
            url += etpConst['product']+"/handlers/"
	    etpRemoteSupport[servername] = url

# generate masking dictionary
# MUST BE INSTANTIANTED BEFORE ANY DB CONNECTION BEGINS
import maskingparser
etpConst['packagemasking'] = maskingparser.parse()
# merge universal keywords
for x in etpConst['packagemasking']['keywords']['universal']:
    etpConst['keywords'].add(x)

# Portage /var/db/<pkgcat>/<pkgname-pkgver>/*
# you never know if gentoo devs change these things
dbDESCRIPTION = "DESCRIPTION"
dbHOMEPAGE = "HOMEPAGE"
dbCHOST = "CHOST"
dbCATEGORY = "CATEGORY"
dbCFLAGS = "CFLAGS"
dbCXXFLAGS = "CXXFLAGS"
dbLICENSE = "LICENSE"
dbSRC_URI = "SRC_URI"
dbUSE = "USE"
dbIUSE = "IUSE"
dbSLOT = "SLOT"
dbPROVIDE = "PROVIDE"
dbDEPEND = "DEPEND"
dbRDEPEND = "RDEPEND"
dbPDEPEND = "PDEPEND"
dbNEEDED = "NEEDED"
dbINHERITED = "INHERITED"
dbOR = "|or|"
dbKEYWORDS = "KEYWORDS"
dbCONTENTS = "CONTENTS"
dbCOUNTER = "COUNTER"
edbCOUNTER = "/var/cache/edb/counter"

