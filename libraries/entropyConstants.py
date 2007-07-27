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
import commands
import string
import random
import sys


# Specifications of the content of etpData
# THIS IS THE KEY PART OF ENTROPY BINARY PACKAGES MANAGEMENT
# DO NOT EDIT THIS UNLESS YOU KNOW WHAT YOU'RE DOING !!
etpData = {
    'name': u"", # the Package Name
    'version': u"", # the Package version plus our -etpXX revision
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
    'rundependencies': u"", # runtime dependencies
    'rundependenciesXT': u"", # runtime dependencies + version
    'conflicts': u"", # blockers
    'etpapi': u"", # Entropy API revision
    'datecreation': u"", # mtime of the .tbz2 file
    'neededlibs': u"", # libraries needed bye the applications in the package
    'size': u"", # the package size
    'versiontag': u"" # particular version tag
}

# Entropy database SQL initialization Schema and data structure
etpSQLInitDestroyAll = """
DROP TABLE IF EXISTS etpData;
DROP TABLE IF EXISTS baseinfo;
DROP TABLE IF EXISTS extrainfo;
DROP TABLE IF EXISTS content;
DROP TABLE IF EXISTS dependencies;
DROP TABLE IF EXISTS rundependencies;
DROP TABLE IF EXISTS rundependenciesxt;
DROP TABLE IF EXISTS conflicts;
DROP TABLE IF EXISTS neededlibs;
DROP TABLE IF EXISTS mirrorlinks;
DROP TABLE IF EXISTS sources;
DROP TABLE IF EXISTS useflags;
DROP TABLE IF EXISTS keywords;
DROP TABLE IF EXISTS binkeywords;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS licenses;
DROP TABLE IF EXISTS flags;
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
    etpapi INTEGER
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
    file VARCHAR
);

CREATE TABLE dependencies (
    idpackage INTEGER,
    dependency VARCHAR
);

CREATE TABLE rundependencies (
    idpackage INTEGER,
    dependency VARCHAR
);

CREATE TABLE rundependenciesxt (
    idpackage INTEGER,
    dependency VARCHAR
);

CREATE TABLE conflicts (
    idpackage INTEGER,
    conflict VARCHAR
);

CREATE TABLE neededlibs (
    idpackage INTEGER,
    library VARCHAR
);

CREATE TABLE mirrorlinks (
    mirrorname VARCHAR,
    mirrorlink VARCHAR
);

CREATE TABLE sources (
    idpackage INTEGER,
    source VARCHAR
);

CREATE TABLE useflags (
    idpackage INTEGER,
    flag VARCHAR
);

CREATE TABLE keywords (
    idpackage INTEGER,
    keyword VARCHAR
);

CREATE TABLE binkeywords (
    idpackage INTEGER,
    binkeyword VARCHAR
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

ETP_REVISION_CONST = "%ETPREV%"
ETP_DIR = "/var/lib/entropy"
ETP_TMPDIR = "/tmp"
ETP_RANDOM = str(random.random())[2:7]
ETP_TMPFILE = "/.random-"+ETP_RANDOM+".tmp"
ETP_REPODIR = "/packages/"+ETP_ARCH_CONST
ETP_PORTDIR = "/portage"
ETP_DISTFILESDIR = "/distfiles"
ETP_DBDIR = "/database/"+ETP_ARCH_CONST
ETP_DBFILE = "packages.db"
ETP_DBCLIENTFILE = "equo.db"
ETP_CLIENT_REPO_DIR = "/client"
ETP_UPLOADDIR = "/upload/"+ETP_ARCH_CONST
ETP_STOREDIR = "/store/"+ETP_ARCH_CONST
ETP_SMARTAPPSDIR = "/smartapps/"+ETP_ARCH_CONST
ETP_CONF_DIR = "/etc/entropy"
ETP_ROOT_DIR = "/"
ETP_LOG_DIR = ETP_DIR+"/"+"logs"
ETP_SYSLOG_DIR = "/var/log/entropy/"
ETP_LOGLEVEL_NORMAL = 1
ETP_LOGLEVEL_VERBOSE = 2
ETP_LOGPRI_INFO = "[ INFO ]"
ETP_LOGPRI_WARNING = "[ WARNING ]"
ETP_LOGPRI_ERROR = "[ ERROR ]"

# NEVER APPEND another \n to this file because it will break the md5 check of reagent
ETP_HEADER_TEXT = "# Sabayon Linux (C - 2007) - Entropy Package Specifications (GPLv2)\n"
MAX_ETP_REVISION_COUNT = 99999

etpConst = {
    'packagestmpdir': ETP_DIR+ETP_TMPDIR, # etpConst['packagestmpdir'] --> temp directory
    'packagestmpfile': ETP_DIR+ETP_TMPDIR+ETP_TMPFILE, # etpConst['packagestmpfile'] --> general purpose tmp file
    'packagesbindir': ETP_DIR+ETP_REPODIR, # etpConst['packagesbindir'] --> repository where the packages will be stored
    			# by the clients: to query if a package has been already downloaded
			# by the servers or rsync mirrors: to store already uploaded packages to the main rsync server
    'smartappsdir': ETP_DIR+ETP_SMARTAPPSDIR, # etpConst['smartappsdir'] location where smart apps files are places
    'packagesstoredir': ETP_DIR+ETP_STOREDIR, # etpConst['packagesstoredir'] --> directory where .tbz2 files are stored waiting for being processed by reagent
    'packagessuploaddir': ETP_DIR+ETP_UPLOADDIR, # etpConst['packagessuploaddir'] --> directory where .tbz2 files are stored waiting for being uploaded to our main mirror
    'portagetreedir': ETP_DIR+ETP_PORTDIR, # directory where is stored our local portage tree
    'distfilesdir': ETP_DIR+ETP_PORTDIR+ETP_DISTFILESDIR, # directory where our sources are downloaded
    'overlaysdir': ETP_DIR+ETP_PORTDIR+"/local/layman", # directory where overlays are stored
    'overlays': "", # variable PORTDIR_OVERLAY
    'overlaysconffile': ETP_CONF_DIR+"/layman.cfg", # layman configuration file
    'confdir': ETP_CONF_DIR, # directory where entropy stores its configuration
    'entropyconf': ETP_CONF_DIR+"/entropy.conf", # entropy.conf file
    'repositoriesconf': ETP_CONF_DIR+"/repositories.conf", # repositories.conf file
    'enzymeconf': ETP_CONF_DIR+"/enzyme.conf", # enzyme.conf file
    'activatorconf': ETP_CONF_DIR+"/activator.conf", # activator.conf file
    'reagentconf': ETP_CONF_DIR+"/reagent.conf", # reagent.conf file
    'databaseconf': ETP_CONF_DIR+"/database.conf", # database.conf file
    'spmbackendconf': ETP_CONF_DIR+"/spmbackend.conf", # Source Package Manager backend configuration (Portage now)
    'mirrorsconf': ETP_CONF_DIR+"/mirrors.conf", # mirrors.conf file
    'remoteconf': ETP_CONF_DIR+"/remote.conf", # remote.conf file
    'equoconf': ETP_CONF_DIR+"/equo.conf", # equo.conf file
    'activatoruploaduris': [], # list of URIs that activator can use to upload files (parsed from activator.conf)
    'activatordownloaduris': [], # list of URIs that activator can use to fetch data
    'binaryurirelativepath': "packages/"+ETP_ARCH_CONST+"/", # Relative remote path for the binary repository.
    'etpurirelativepath': "database/"+ETP_ARCH_CONST+"/", # Relative remote path for the .etp repository.
    							  # TO BE REMOVED? CHECK
    'etpdatabaserevisionfile': ETP_DBFILE+".revision", # the local/remote database revision file
    'etpdatabasehashfile': ETP_DBFILE+".md5", # its checksum
    'etpdatabaselockfile': ETP_DBFILE+".lock", # the remote database lock file
    'etpdatabasedownloadlockfile': ETP_DBFILE+".download.lock", # the remote database download lock file
    'etpdatabasetaintfile': ETP_DBFILE+".tainted", # when this file exists, the database is not synced anymore with the online one
    'etpdatabasefile': ETP_DBFILE, # Entropy sqlite database file ETP_DIR+ETP_DBDIR+"/packages.db"
    'etpdatabasefilegzip': ETP_DBFILE+".gz", # Entropy sqlite database file (gzipped)
    'packageshashfileext': ".md5", # Extension of the file that contains the checksum of its releated package file
    
    'databaseloglevel': 1, # Database log level (default: 1 - see database.conf for more info)
    'mirrorsloglevel': 1, # Mirrors log level (default: 1 - see mirrors.conf for more info)
    'remoteloglevel': 1, # Remote handlers (/handlers) log level (default: 1 - see remote.conf for more info)
    'enzymeloglevel': 1 , # Enzyme log level (default: 1 - see enzyme.conf for more info)
    'reagentloglevel': 1 , # Reagent log level (default: 1 - see reagent.conf for more info)
    'activatorloglevel': 1, # # Activator log level (default: 1 - see activator.conf for more info)
    'entropyloglevel': 1, # # Entropy log level (default: 1 - see entropy.conf for more info)
    'equologlevel': 1, # # Equo log level (default: 1 - see equo.conf for more info)
    'spmbackendloglevel': 1, # # Source Package Manager backend log level (default: 1 - see entropy.conf for more info)
    'logdir': ETP_LOG_DIR , # Log dir where ebuilds store their shit
    
    'syslogdir': ETP_SYSLOG_DIR, # Entropy system tools log directory
    'mirrorslogfile': ETP_SYSLOG_DIR+"/mirrors.log", # Mirrors operations log file
    'remotelogfile': ETP_SYSLOG_DIR+"/remote.log", # Mirrors operations log file
    'spmbackendlogfile': ETP_SYSLOG_DIR+"/spmbackend.log", # Source Package Manager backend configuration log file
    'databaselogfile': ETP_SYSLOG_DIR+"/database.log", # Database operations log file
    'enzymelogfile': ETP_SYSLOG_DIR+"/enzyme.log", # Enzyme operations log file
    'reagentlogfile': ETP_SYSLOG_DIR+"/reagent.log", # Reagent operations log file
    'activatorlogfile': ETP_SYSLOG_DIR+"/activator.log", # Activator operations log file
    'entropylogfile': ETP_SYSLOG_DIR+"/entropy.log", # Activator operations log file
    'equologfile': ETP_SYSLOG_DIR+"/equo.log", # Activator operations log file
    
    
    'distcc-status': False, # used by Enzyme, if True distcc is enabled
    'distccconf': "/etc/distcc/hosts", # distcc hosts configuration file
    'etpdatabasedir': ETP_DIR+ETP_DBDIR,
    'etpdatabasefilepath': ETP_DIR+ETP_DBDIR+"/"+ETP_DBFILE,
    'etpdatabaseclientdir': ETP_DIR+ETP_CLIENT_REPO_DIR+ETP_DBDIR,
    'etpdatabaseclientfilepath': ETP_DIR+ETP_CLIENT_REPO_DIR+ETP_DBDIR+"/"+ETP_DBCLIENTFILE, # path to equo.db - client side database file
    
    'etpapi': ETP_API, # Entropy database API revision
    'headertext': ETP_HEADER_TEXT, # header text that can be outputted to a file
    'currentarch': ETP_ARCH_CONST, # contains the current running architecture
    'supportedarchs': ETP_ARCHS, # Entropy supported Archs
    'preinstallscript': "preinstall.sh", # used by the client to run some pre-install actions
    'postinstallscript': "postinstall.sh", # used by the client to run some post-install actions
    
    'branches': ["stable","unstable"], # available branches, do not scramble!
    'branch': "unstable", # choosen branch
    'gentoo-compat': False, # Gentoo compatibility (/var/db/pkg + Portage availability)
    'filesystemdirs': ['/bin','/boot','/emul','/etc','/lib','/lib32','/lib64','/opt','/sbin','/usr','/var'], # directory of the filesystem
 }

# Handlers used by entropy to run and retrieve data remotely, using php helpers
etpHandlers = {
    'md5sum': "md5sum.php?arch="+ETP_ARCH_CONST+"&package=", # md5sum handler
}


# Create paths
if not os.path.isdir(ETP_DIR):
    import getpass
    if getpass.getuser() == "root":
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
        sys.exit(100)

# Client packages/database repositories
# used by equo
etpRepositories = {}

if os.path.isfile(etpConst['repositoriesconf']):
    f = open(etpConst['repositoriesconf'],"r")
    repositoriesconf = f.readlines()
    f.close()
    
    for line in repositoriesconf:
	line = line.strip()
        # populate etpRepositories
	if (line.find("repository|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 5):
	    reponame = line.split("|")[1]
	    repodesc = line.split("|")[2]
	    repopackages = line.split("|")[3]
	    repodatabase = line.split("|")[4]
	    if (repopackages.startswith("http://") or repopackages.startswith("ftp://")) and (repodatabase.startswith("http://") or repodatabase.startswith("ftp://")):
		etpRepositories[reponame] = {}
		etpRepositories[reponame]['description'] = repodesc
		etpRepositories[reponame]['packages'] = repopackages+"/"+etpConst['currentarch']
		etpRepositories[reponame]['database'] = repodatabase+"/"+etpConst['currentarch']
		etpRepositories[reponame]['dbpath'] = etpConst['etpdatabaseclientdir']+"/"+reponame+"/"+etpConst['currentarch']
	elif (line.find("branch|") != -1) and (not line.startswith("#")) and (len(line.split("|")) == 2):
	    branch = line.split("|")[1]
	    etpConst['branch'] = branch

if (commands.getoutput("q -V").find("portage-utils") != -1):
    pFindLibrary = "qfile -qC "
    pFindLibraryXT = "qfile -qeC "
else:
    pFindLibrary = "equery belongs -n "
    pFindLibraryXT = "equery belongs -en "

# configure layman.cfg properly
if (not os.path.isfile(etpConst['overlaysconffile'])):
    laymanConf = """
[MAIN]

#-----------------------------------------------------------
# Path to the config directory

config_dir: /etc/layman

#-----------------------------------------------------------
# Defines the directory where overlays should be installed

storage   : """+etpConst['overlaysdir']+"""

#-----------------------------------------------------------
# Remote overlay lists will be stored here
# layman will append _md5(url).xml to each filename

cache     : %(storage)s/cache

#-----------------------------------------------------------
# The list of locally installed overlays

local_list: %(storage)s/overlays.xml

#-----------------------------------------------------------
# Path to the make.conf file that should be modified by
# layman

make_conf : %(storage)s/make.conf

#-----------------------------------------------------------
# URLs of the remote lists of overlays (one per line) or
# local overlay definitions
#
#overlays  : http://www.gentoo.org/proj/en/overlays/layman-global.txt
#            http://dev.gentoo.org/~wrobel/layman/global-overlays.xml
#            http://mydomain.org/my-layman-list.xml
#            file:///usr/portage/local/layman/my-list.xml

overlays  : http://www.gentoo.org/proj/en/overlays/layman-global.txt

#-----------------------------------------------------------
# Proxy support
#
#proxy  : http://www.my-proxy.org:3128

#-----------------------------------------------------------
# Strict checking of overlay definitions
#
# Set either to "yes" or "no". If "no" layman will issue
# warnings if an overlay definition is missing either
# description or contact information.
#
nocheck  : yes
"""
    f = open(etpConst['overlaysconffile'],"w")
    f.writelines(laymanConf)
    f.flush()
    f.close()

# fill etpConst['overlays']
ovlst = os.listdir(etpConst['overlaysdir'])
_ovlst = []
for i in ovlst:
    if os.path.isdir(etpConst['overlaysdir']+"/"+i):
	_ovlst.append(etpConst['overlaysdir']+"/"+i)
etpConst['overlays'] = string.join(_ovlst," ")

# activator section
if (not os.path.isfile(etpConst['activatorconf'])):
    print "ERROR: "+etpConst['activatorconf']+" does not exist"
    sys.exit(50)
else:
    try:
	if (os.stat(etpConst['activatorconf'])[0] != 33152):
	    os.chmod(etpConst['activatorconf'],0600)
    except:
	print "ERROR: cannot chmod 0600 file: "+etpConst['activatorconf']
	sys.exit(50)
    # fill etpConst['activatoruploaduris'] and etpConst['activatordownloaduris']
    f = open(etpConst['activatorconf'],"r")
    actconffile = f.readlines()
    f.close()
    for line in actconffile:
	line = line.strip()
	if line.startswith("mirror-upload|") and (len(line.split("mirror-upload|")) == 2):
	    uri = line.split("mirror-upload|")[1]
	    if uri.endswith("/"):
		uri = uri[:len(uri)-1]
	    etpConst['activatoruploaduris'].append(uri)
	if line.startswith("mirror-download|") and (len(line.split("mirror-download|")) == 2):
	    uri = line.split("mirror-download|")[1]
	    if uri.endswith("/"):
		uri = uri[:len(uri)-1]
	    etpConst['activatordownloaduris'].append(uri)
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['activatorconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['activatorloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['activatorconf']
		import time
		time.sleep(5)

# enzyme section
if (not os.path.isfile(etpConst['enzymeconf'])):
    print "ERROR: "+etpConst['enzymeconf']+" does not exist"
    sys.exit(50)
else:
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    for line in enzymeconf:
	if line.startswith("distcc-status|") and (len(line.split("|")) == 2) and (line.strip().split("|")[1] == "enabled"):
	    etpConst['distcc-status'] = True
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['enzymeconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['enzymeloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['enzymeconf']
		import time
		time.sleep(5)
		

# reagent section
if (not os.path.isfile(etpConst['reagentconf'])):
    print "ERROR: "+etpConst['reagentconf']+" does not exist"
    sys.exit(50)
else:
    f = open(etpConst['reagentconf'],"r")
    reagentconf = f.readlines()
    f.close()
    for line in reagentconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['reagentconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['reagentloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['reagentconf']
		import time
		time.sleep(5)

# entropy section
if (not os.path.isfile(etpConst['entropyconf'])):
    print "ERROR: "+etpConst['entropyconf']+" does not exist"
    sys.exit(50)
else:
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
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['entropyloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['entropyconf']
		import time
		time.sleep(5)


# database section
if (not os.path.isfile(etpConst['databaseconf'])):
    print "ERROR: "+etpConst['databaseconf']+" does not exist"
    sys.exit(50)
else:
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
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['databaseloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['databaseconf']
		import time
		time.sleep(5)

# equo section
if (not os.path.isfile(etpConst['equoconf'])):
    print "ERROR: "+etpConst['equoconf']+" does not exist"
    sys.exit(50)
else:
    f = open(etpConst['equoconf'],"r")
    equoconf = f.readlines()
    f.close()
    for line in equoconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['equoconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['equologlevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['equoconf']
		import time
		time.sleep(5)

	if line.startswith("gentoo-compat|") and (len(line.split("|")) == 2):
	    compatopt = line.split("|")[1].strip()
	    if compatopt == "disable":
		etpConst['gentoo-compat'] = False
	    else:
		etpConst['gentoo-compat'] = True

# mirrors section
if (not os.path.isfile(etpConst['mirrorsconf'])):
    print "ERROR: "+etpConst['mirrorsconf']+" does not exist"
    sys.exit(50)
else:
    f = open(etpConst['mirrorsconf'],"r")
    databaseconf = f.readlines()
    f.close()
    for line in databaseconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['mirrorsconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['mirrorsloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['mirrorsconf']
		import time
		time.sleep(5)
	
# remote section
etpRemoteSupport = {}
if (not os.path.isfile(etpConst['remoteconf'])):
    print "ERROR: "+etpConst['remoteconf']+" does not exist"
    sys.exit(50)
else:
    f = open(etpConst['remoteconf'],"r")
    databaseconf = f.readlines()
    f.close()
    for line in databaseconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['remoteconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['remoteloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['remoteconf']
		import time
		time.sleep(5)

	if line.startswith("httphandler|") and (len(line.split("|")) > 2):
	    servername = line.split("|")[1].strip()
	    url = line.split("|")[2].strip()
	    if not url.endswith("/"):
		url = url+"/"
	    etpRemoteSupport[servername] = url


# spmbackend section
if (not os.path.isfile(etpConst['spmbackendconf'])):
    print "ERROR: "+etpConst['spmbackendconf']+" does not exist"
    sys.exit(50)
else:
    f = open(etpConst['spmbackendconf'],"r")
    spmconf = f.readlines()
    f.close()
    for line in spmconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['spmbackendconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['spmbackendloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['spmbackendconf']
		import time
		time.sleep(5)

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
dbDEPEND = "DEPEND"
dbRDEPEND = "RDEPEND"
dbPDEPEND = "PDEPEND"
dbNEEDED = "NEEDED"
dbOR = "|or|"
dbKEYWORDS = "KEYWORDS"
dbCONTENTS = "CONTENTS"
dbPORTAGE_ELOG_OPTS = 'PORTAGE_ELOG_CLASSES="warn info log" PORTAGE_ELOG_SYSTEM="save" PORT_LOGDIR="'+etpConst['logdir']+'"'

# Portage variables reference
# vdbVARIABLE --> $VARIABLE
vdbPORTDIR = "PORTDIR"
vdbPORTDIR_OVERLAY = "PORTDIR_OVERLAY"

# Portage & misc commands
cdbEMERGE = "emerge"
cdbRunEmerge = vdbPORTDIR+"='"+etpConst['portagetreedir']+"' "+vdbPORTDIR_OVERLAY+"='"+etpConst['overlays']+"' "+cdbEMERGE
cdbStartDistcc = "/etc/init.d/distccd start --nodeps"
cdbStopDistcc = "/etc/init.d/distccd stop --nodeps"
cdbStatusDistcc = "/etc/init.d/distccd status"

# Portage options
odbBuild = " -b "
odbNodeps = " --nodeps "