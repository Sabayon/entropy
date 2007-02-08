#!/usr/bin/python
# Copyright Fabio Erculiani - Sabayon Linux 2007

# DESCRIPTION:
# Variables container

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
ETP_API_MINOR = "2"
ETP_API_SUBLEVEL = "2"
ETP_API = ETP_API_MAJOR+"."+ETP_API_MINOR+"."+ETP_API_SUBLEVEL
ETP_ARCH_CONST = "%ARCH%"
ETP_REVISION_CONST = "%ETPREV%"
ETP_DIR = "/var/lib/entropy"
ETP_TMPDIR = "/tmp"
ETP_REPODIR = "/repository"+"/"+ETP_ARCH_CONST
ETP_DBDIR = "/database"+"/"+ETP_ARCH_CONST
ETP_UPDIR = "/upload"+"/"+ETP_ARCH_CONST
ETP_STOREDIR = "/store"+"/"+ETP_ARCH_CONST
ETP_CONF_DIR = "/etc/entropy"
ETP_HEADER_TEXT = "# Entropy specifications file (released under the GPLv2)\n"
MAX_ETP_REVISION_COUNT = 99999

etpConst = {
    'packagestmpdir': ETP_DIR+ETP_TMPDIR, # etpConst['packagestmpdir'] --> temp directory
    'packagesbindir': ETP_DIR+ETP_REPODIR, # etpConst['packagesbindir'] --> repository where the packages will be stored
    'packagesdatabasedir': ETP_DIR+ETP_DBDIR, # etpConst['packagesdatabasedir'] --> repository where .etp files will be stored
    'packagesstoredir': ETP_DIR+ETP_DBDIR, # etpConst['packagesstoredir'] --> directory where .tbz2 files are stored waiting for being processed by entropy-specifications-generator
    'packagessuploaddir': ETP_DIR+ETP_UPDIR, # etpConst['packagessuploaddir'] --> directory where .tbz2 files are stored waiting for being uploaded to our main mirror
    'confdir': ETP_CONF_DIR, # directory where entropy stores its configuration
    'repositoriesconf': ETP_CONF_DIR+"/repositories.conf", # repositories.conf file
    'digestfile': "Manifest", # file that contains md5 hashes
    'extension': ".etp", # entropy files extension
}

import os
# Create paths
if not os.path.isdir(ETP_DIR):
    import getpass
    if getpass.getuser() == "root":
	import re
	for x in etpConst:
	    if (etpConst[x]):
		
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
        entropyTools.print_error("you need to run this as root at least once.")
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
	if line.startswith("packages|"):
	    repouri = line.split("packages|")[len(line.split("packages|"))-1]
	    if repouri.startswith("http://") or repouri.startswith("ftp://") or repouri.startswith("rsync://"):
	        etpSources['packagesuri'].append(repouri)
	# populate etpSources['databaseuri']
	elif line.startswith("database|"):
	    if (not etpSources['databaseuri']):
	        repouri = line.split("database|")[len(line.split("database|"))-1]
	        if repouri.startswith("http://") or repouri.startswith("ftp://") or repouri.startswith("rsync://"):
	            etpSources['databaseuri'] = repouri

import commands
if (commands.getoutput("q -V").find("portage-utils") != -1):
    pFindLibrary = "qfile -qC "
    pFindLibraryXT = "qfile -qeC "
else:
    pFindLibrary = "equery belongs -n "
    pFindLibraryXT = "equery belongs -en "

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