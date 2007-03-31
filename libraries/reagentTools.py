#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for reagent application

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

# Never do "import portage" here, please use entropyTools binding

# EXIT STATUSES: 500-599

from entropyConstants import *
from entropyTools import *
import commands
import re
import sys
import string
from portageTools import unpackTbz2, synthetizeRoughDependencies, getPackageRuntimeDependencies, dep_getkey, getThirdPartyMirrors

def generator(package, enzymeRequestBump = False):

    # check if the package provided is valid
    validFile = False
    if os.path.isfile(package) and package.endswith(".tbz2"):
	validFile = True
    if (not validFile):
	print_error("no valid .tbz2 file specified")
        sys.exit(501)

    packagename = package.split("/")[len(package.split("/"))-1]

    print_info(yellow(" * ")+red("Processing: ")+bold(packagename)+red(", please wait..."))
    etpData = extractPkgData(package)

    # now import etpData inside the database
    dbconn = databaseTools.etpDatabase(readOnly = False, noUpload = True)
    updated, revision = dbconn.handlePackage(etpData,enzymeRequestBump)
    dbconn.closeDB()

    if (updated) and (revision != 0):
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" entry has been updated. Revision: ")+bold(str(revision)))
	return True
    elif (updated) and (revision == 0):
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" entry newly created."))
	return True
    else:
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" does not need to be updated. Current revision: ")+bold(str(revision)))
	return False


# This tool is used by Entropy after enzyme, it simply parses the content of etpConst['packagesstoredir']
def enzyme(options):

    enzymeRequestBump = False
    #_atoms = []
    for i in options:
        if ( i == "--force-bump" ):
	    enzymeRequestBump = True

    tbz2files = os.listdir(etpConst['packagesstoredir'])
    totalCounter = 0
    # counting the number of files
    for i in tbz2files:
	totalCounter += 1

    if (totalCounter == 0):
	print_info(yellow(" * ")+red("Nothing to do, check later."))
	# then exit gracefully
	sys.exit(0)

    counter = 0
    etpCreated = 0
    etpNotCreated = 0
    for tbz2 in tbz2files:
	counter += 1
	tbz2name = tbz2.split("/")[len(tbz2.split("/"))-1]
	print_info(" ("+str(counter)+"/"+str(totalCounter)+") Processing "+tbz2name)
	tbz2path = etpConst['packagesstoredir']+"/"+tbz2
	rc = generator(tbz2path, enzymeRequestBump)
	if (rc):
	    etpCreated += 1
	    os.system("mv "+tbz2path+" "+etpConst['packagessuploaddir']+"/ -f")
	else:
	    etpNotCreated += 1
	    os.system("rm -rf "+tbz2path)

    print_info(green(" * ")+red("Statistics: ")+blue("Entries created/updated: ")+bold(str(etpCreated))+yellow(" - ")+darkblue("Entries discarded: ")+bold(str(etpNotCreated)))

# This function extracts all the info from a .tbz2 file and returns them
def extractPkgData(package):

    # Clean the variables
    for i in etpData:
	etpData[i] = u""

    print_info(yellow(" * ")+red("Getting package name/version..."),back = True)
    tbz2File = package
    package = package.split(".tbz2")[0]
    package = package.split("-")
    pkgname = ""
    pkglen = len(package)
    if package[pkglen-1].startswith("r"):
        pkgver = package[pkglen-2]+"-"+package[pkglen-1]
	pkglen -= 2
    else:
	pkgver = package[len(package)-1]
	pkglen -= 1
    for i in range(pkglen):
	if i == pkglen-1:
	    pkgname += package[i]
	else:
	    pkgname += package[i]+"-"
    pkgname = pkgname.split("/")[len(pkgname.split("/"))-1]

    # Fill Package name and version
    etpData['name'] = pkgname
    etpData['version'] = pkgver

    print_info(yellow(" * ")+red("Getting package md5..."),back = True)
    # .tbz2 md5
    etpData['digest'] = md5sum(tbz2File)

    print_info(yellow(" * ")+red("Getting package mtime..."),back = True)
    # .tbz2 md5
    etpData['datecreation'] = str(getFileUnixMtime(tbz2File))

    print_info(yellow(" * ")+red("Unpacking package data..."),back = True)
    # unpack file
    tbz2TmpDir = etpConst['packagestmpdir']+"/"+etpData['name']+"-"+etpData['version']+"/"
    unpackTbz2(tbz2File,tbz2TmpDir)

    print_info(yellow(" * ")+red("Getting package CHOST..."),back = True)
    # Fill chost
    f = open(tbz2TmpDir+dbCHOST,"r")
    etpData['chost'] = f.readline().strip()
    f.close()

    print_info(yellow(" * ")+red("Setting package branch..."),back = True)
    # local path to the file
    etpData['branch'] = "unstable"

    print_info(yellow(" * ")+red("Getting package description..."),back = True)
    # Fill description
    try:
        f = open(tbz2TmpDir+dbDESCRIPTION,"r")
        etpData['description'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['description'] = ""

    print_info(yellow(" * ")+red("Getting package homepage..."),back = True)
    # Fill homepage
    try:
        f = open(tbz2TmpDir+dbHOMEPAGE,"r")
        etpData['homepage'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['homepage'] = ""

    print_info(yellow(" * ")+red("Getting package slot information..."),back = True)
    # fill slot, if it is
    try:
        f = open(tbz2TmpDir+dbSLOT,"r")
        etpData['slot'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['slot'] = ""

    print_info(yellow(" * ")+red("Getting package content..."),back = True)
    # dbCONTENTS
    try:
        f = open(tbz2TmpDir+dbCONTENTS,"r")
        content = f.readlines()
        f.close()
	outcontent = []
	for line in content:
	    line = line.strip().split()
	    if line[0] == "obj":
		outcontent.append(line[1].strip())
	import string
	# filter bad utf-8 chars
	_outcontent = []
	for i in outcontent:
	    try:
		i.encode("utf-8")
		_outcontent.append(i)
	    except:
		pass
	outcontent = _outcontent
	etpData['content'] = string.join(outcontent," ").encode("utf-8")
	
    except IOError:
        etpData['content'] = ""

    print_info(yellow(" * ")+red("Getting package download URL..."),back = True)
    # Fill download relative URI
    etpData['download'] = etpConst['binaryurirelativepath']+etpData['name']+"-"+etpData['version']+".tbz2"

    print_info(yellow(" * ")+red("Getting package category..."),back = True)
    # Fill category
    f = open(tbz2TmpDir+dbCATEGORY,"r")
    etpData['category'] = f.readline().strip()
    f.close()

    print_info(yellow(" * ")+red("Getting package CFLAGS..."),back = True)
    # Fill CFLAGS
    try:
        f = open(tbz2TmpDir+dbCFLAGS,"r")
        etpData['cflags'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['cflags'] = ""

    print_info(yellow(" * ")+red("Getting package CXXFLAGS..."),back = True)
    # Fill CXXFLAGS
    try:
        f = open(tbz2TmpDir+dbCXXFLAGS,"r")
        etpData['cxxflags'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['cxxflags'] = ""

    print_info(yellow(" * ")+red("Getting package License information..."),back = True)
    # Fill license
    try:
        f = open(tbz2TmpDir+dbLICENSE,"r")
        etpData['license'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['license'] = ""

    print_info(yellow(" * ")+red("Getting package sources information..."),back = True)
    # Fill sources
    try:
        f = open(tbz2TmpDir+dbSRC_URI,"r")
	tmpSources = f.readline().strip().split()
        f.close()
	tmpData = []
	for atom in tmpSources:
	    if atom.endswith("?"):
	        etpData['sources'] += "="+atom[:len(atom)-1]+"|"
	    elif (not atom.startswith("(")) and (not atom.startswith(")")):
		tmpData.append(atom)
	
	etpData['sources'] = string.join(tmpData," ")
    except IOError:
	etpData['sources'] = ""

    print_info(yellow(" * ")+red("Getting package mirrors list..."),back = True)
    # manage etpData['sources'] to create etpData['mirrorlinks']
    # =mirror://openoffice|link1|link2|link3
    tmpMirrorList = etpData['sources'].split()
    tmpData = []
    for i in tmpMirrorList:
        if i.startswith("mirror://"):
	    # parse what mirror I need
	    x = i.split("/")[2]
	    mirrorlist = getThirdPartyMirrors(x)
	    mirrorURI = "mirror://"+x
	    out = "="+mirrorURI+"|"
	    for mirror in mirrorlist:
	        out += mirror+"|"
	    if out.endswith("|"):
		out = out[:len(out)-1]
	    tmpData.append(out)
    etpData['mirrorlinks'] = string.join(tmpData," ")

    print_info(yellow(" * ")+red("Getting package USE flags..."),back = True)
    # Fill USE
    f = open(tbz2TmpDir+dbUSE,"r")
    tmpUSE = f.readline().strip()
    f.close()
    try:
        f = open(tbz2TmpDir+dbIUSE,"r")
        tmpIUSE = f.readline().strip().split()
        f.close()
    except IOError:
        tmpIUSE = ""

    for i in tmpIUSE:
	if tmpUSE.find(i) != -1:
	    etpData['useflags'] += i+" "
	else:
	    etpData['useflags'] += "-"+i+" "

    # cleanup
    tmpUSE = etpData['useflags'].split()
    tmpUSE = list(set(tmpUSE))
    etpData['useflags'] = ''
    tmpData = []
    for i in tmpUSE:
        tmpData.append(i)
    etpData['useflags'] = string.join(tmpData," ")

    print_info(yellow(" * ")+red("Getting sorce package supported ARCHs..."),back = True)
    # fill KEYWORDS
    try:
        f = open(tbz2TmpDir+dbKEYWORDS,"r")
        etpData['keywords'] = f.readline().strip()
        f.close()
    except IOError:
	etpData['keywords'] = ""

    print_info(yellow(" * ")+red("Getting package supported ARCHs..."),back = True)
    
    # fill ARCHs
    pkgArchs = etpData['keywords']
    tmpData = []
    for i in etpConst['supportedarchs']:
        if pkgArchs.find(i) != -1 and (pkgArchs.find("-"+i) == -1): # in case we find something like -amd64...
	    tmpData.append(i)
    etpData['binkeywords'] = string.join(tmpData," ")

    # FIXME: do we have to rewrite this and use Portage to query a better dependency list?
    print_info(yellow(" * ")+red("Getting package dependencies..."),back = True)
    # Fill dependencies
    # to fill dependencies we use *DEPEND files
    f = open(tbz2TmpDir+dbDEPEND,"r")
    roughDependencies = f.readline().strip()
    f.close()
    f = open(tbz2TmpDir+dbRDEPEND,"r")
    roughDependencies += " "+f.readline().strip()
    f.close()
    f = open(tbz2TmpDir+dbPDEPEND,"r")
    roughDependencies += " "+f.readline().strip()
    f.close()
    roughDependencies = roughDependencies.split()
    
    # variables filled
    # etpData['dependencies'], etpData['conflicts']
    etpData['dependencies'], etpData['conflicts'] = synthetizeRoughDependencies(roughDependencies,etpData['useflags'])

    # etpData['rdependencies']
    # Now we need to add environmental dependencies
    # Notes (take the example of mplayer that needed a newer libcaca release):
    # - we can use (from /var/db) "NEEDED" file to catch all the needed libraries to run the binary package
    # - we can use (from /var/db) "CONTENTS" to rapidly search the NEEDED files in the file above
    # return all the collected info

    print_info(yellow(" * ")+red("Getting package runtime dependencies..."),back = True)
    # start collecting needed libraries
    runtimeNeededPackages, runtimeNeededPackagesXT = getPackageRuntimeDependencies(tbz2TmpDir+"/"+dbNEEDED)

    tmpData = []
    # now keep only the ones not available in etpData['dependencies']
    for i in runtimeNeededPackages:
        if etpData['dependencies'].find(i) == -1:
	    # filter itself
	    if (i != etpData['category']+"/"+etpData['name']):
	        tmpData.append(i)
    etpData['rundependencies'] = string.join(tmpData," ")

    tmpData = []
    for i in runtimeNeededPackagesXT:
	x = dep_getkey(i)
        if etpData['dependencies'].find(x) == -1:
	    # filter itself
	    if (x != etpData['category']+"/"+etpData['name']):
	        tmpData.append(i)
    
    etpData['rundependenciesXT'] = string.join(tmpData," ")

    print_info(yellow(" * ")+red("Getting Reagent API version..."),back = True)
    # write API info
    etpData['etpapi'] = ETP_API

    print_info(yellow(" * ")+red("Done"),back = True)
    return etpData
