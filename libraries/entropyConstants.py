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

# Specifications of the content of .etp file
# THIS IS THE KEY PART OF ENTROPY BINARY PACKAGES MANAGEMENT
# DO NOT EDIT THIS UNLESS YOU KNOW WHAT YOU'RE DOING !!
etpData = {
    'name': "", # the Package Name
    'version': "", # the Package version plus our -etpXX revision
    'description': "", # the Package description
    'category': "", # the gentoo category
    'chost': "", # the CHOST used to compile it
    'cflags': "", # CFLAGS used
    'cxxflags': "", # CXXFLAGS used
    'homepage': "", # home page of the package
    'useflags': "", # USE flags used
    'license': "", # License adpoted
    'keywords': "", # supported ARCHs (by the SRC)
    'binkeywords': "", # supported ARCHs (by the BIN)
    'packagepath': "", # path where the .tbz2 file is stored
    'download': "", # link to download the binary package
    'digest': "", # md5 hash of the .tbz2 package
    'sources': "", # link to the sources
    'mirrorlinks': "", # =mirror://openoffice|link1|link2|link3
    'dependencies': "", # dependencies
    'rundependencies': "", # runtime dependencies
    'rundependenciesXT': "", # runtime dependencies + version
    'conflicts': "", # blockers
    'etpapi': "", # blockers
}

# Entropy directories specifications
# THIS IS THE KEY PART OF ENTROPY BINARY PACKAGES MANAGEMENT
# DO NOT EDIT THIS UNLESS YOU KNOW WHAT YOU'RE DOING !!
# the ARCHs that we support
ETP_ARCHS = ["x86", "amd64"] # maybe ppc someday
ETP_API_MAJOR = "1"
ETP_API_MINOR = "3"
ETP_API_SUBLEVEL = "0"
ETP_API = ETP_API_MAJOR+"."+ETP_API_MINOR+"."+ETP_API_SUBLEVEL
ETP_ARCH_CONST = "%ARCH%"
ETP_REVISION_CONST = "%ETPREV%"
ETP_DIR = "/var/lib/entropy"
ETP_TMPDIR = "/tmp"
ETP_RANDOM = str(random.random())[2:7]
ETP_TMPFILE = "/.random-"+ETP_RANDOM+".tmp"
ETP_REPODIR = "/repository"+"/"+ETP_ARCH_CONST
ETP_PORTDIR = "/portage"
ETP_DISTFILESDIR = "/distfiles"
ETP_DBDIR = "/database"+"/"+ETP_ARCH_CONST
ETP_UPLOADDIR = "/upload"+"/"+ETP_ARCH_CONST
ETP_STOREDIR = "/store"+"/"+ETP_ARCH_CONST
ETP_CONF_DIR = "/etc/entropy"
ETP_ROOT_DIR = "/"
ETP_LOG_DIR = ETP_DIR+"/"+"logs"
# NEVER APPEND another \n to this file because it will break the md5 check of reagent
ETP_HEADER_TEXT = "# Sabayon Linux (C - 2007) - Entropy Package Specifications (GPLv2)\n"
MAX_ETP_REVISION_COUNT = 99999

etpConst = {
    'packagestmpdir': ETP_DIR+ETP_TMPDIR, # etpConst['packagestmpdir'] --> temp directory
    'packagestmpfile': ETP_DIR+ETP_TMPDIR+ETP_TMPFILE, # etpConst['packagestmpfile'] --> general purpose tmp file
    'packagesbindir': ETP_DIR+ETP_REPODIR, # etpConst['packagesbindir'] --> repository where the packages will be stored
    			# by the clients: to query if a package has been already downloaded
			# by the servers or rsync mirrors: to store already uploaded packages to the main rsync server
    'packagesdatabasedir': ETP_DIR+ETP_DBDIR, # etpConst['packagesdatabasedir'] --> repository where .etp files will be stored
    'packagesstoredir': ETP_DIR+ETP_STOREDIR, # etpConst['packagesstoredir'] --> directory where .tbz2 files are stored waiting for being processed by reagent
    'packagessuploaddir': ETP_DIR+ETP_UPLOADDIR, # etpConst['packagessuploaddir'] --> directory where .tbz2 files are stored waiting for being uploaded to our main mirror
    'portagetreedir': ETP_DIR+ETP_PORTDIR, # directory where is stored our local portage tree
    'distfilesdir': ETP_DIR+ETP_PORTDIR+ETP_DISTFILESDIR, # directory where our sources are downloaded
    'overlaysdir': ETP_DIR+ETP_PORTDIR+"/local/layman", # directory where overlays are stored
    'overlays': "", # variable PORTDIR_OVERLAY
    'overlaysconffile': ETP_CONF_DIR+"/layman.cfg", # layman configuration file
    'confdir': ETP_CONF_DIR, # directory where entropy stores its configuration
    'repositoriesconf': ETP_CONF_DIR+"/repositories.conf", # repositories.conf file
    'enzymeconf': ETP_CONF_DIR+"/enzyme.conf", # enzyme.conf file
    'activatorconf': ETP_CONF_DIR+"/activator.conf", # activator.conf file
    'activatoruploaduris': [],# list of URIs that activator can use to upload files (parsed from activator.conf)
    'activatordownloaduris': [],# list of URIs that activator can use to fetch data
    'digestfile': "Manifest", # file that contains md5 hashes
    'extension': ".etp", # entropy files extension
    'binaryurirelativepath': "/packages/"+ETP_ARCH_CONST+"/", # Relative remote path for the binary repository.
    'etpurirelativepath': "/database/"+ETP_ARCH_CONST+"/", # Relative remote path for the .etp repository.
    'logdir': ETP_LOG_DIR , # Log dir where ebuilds store their shit
}

# Create paths
if not os.path.isdir(ETP_DIR):
    import getpass
    if getpass.getuser() == "root":
	import re
	for x in etpConst:
	    if (etpConst[x]) and (not etpConst[x].endswith(".conf")) and (not etpConst[x].endswith(".cfg")) and (not etpConst[x].endswith(".tmp")):
		
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

etpSources = {
    'packagesuri': "", # URIs where are stored binary packages
    'databaseuri': "", # URIs where are stored entropy files
}
etpSources['packagesuri'] = []

if os.path.isfile(etpConst['repositoriesconf']):
    f = open(etpConst['repositoriesconf'],"r")
    repositoriesconf = f.readlines()
    f.close()
    
    for line in repositoriesconf:
	line = line.strip()
        # populate etpSources['packagesuri']
	if (line.find("packages|") != -1) and (not line.startswith("#")):
	    repouri = line.split("packages|")[len(line.split("packages|"))-1]
	    if repouri.startswith("http://") or repouri.startswith("ftp://") or repouri.startswith("rsync://"):
	        etpSources['packagesuri'].append(repouri)
	# populate etpSources['databaseuri']
	elif (line.find("database|") != -1) and (not line.startswith("#")):
	    if (not etpSources['databaseuri']):
	        repouri = line.split("database|")[len(line.split("database|"))-1]
	        if repouri.startswith("http://") or repouri.startswith("ftp://") or repouri.startswith("rsync://"):
	            etpSources['databaseuri'] = repouri

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

# Portage commands
cdbEMERGE = "emerge"
cdbRunEmerge = vdbPORTDIR+"='"+etpConst['portagetreedir']+"' "+vdbPORTDIR_OVERLAY+"='"+etpConst['overlays']+"' "+cdbEMERGE

# Portage options
odbBuild = " -b "
odbNodeps = " --nodeps "