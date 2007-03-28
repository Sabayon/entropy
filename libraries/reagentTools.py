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

from entropyConstants import *
from entropyTools import *
import databaseTools
import commands
import re
import sys

# Create the manifest file inside the directory provided by
# 'path' and hash all the *.etpConst['extension'] files
def createDigest(path):
    if path.endswith(etpConst['extension']):
        # remove file name and keep the rest of the path
	_path = path.split("/")[:len(path.split("/"))-1]
	path = ""
	for i in _path:
            if (i):
	        path += "/"+i
    if (not os.path.isdir(path)):
	print_error(path+" does not exist")
        sys.exit(102)
    digestContent = os.listdir(path)
    # only .etp files
    _digestContent = digestContent
    digestContent = []
    for i in _digestContent:
	if i.endswith(etpConst['extension']):
            digestContent.append(i)
    if (not digestContent[0].endswith(etpConst['extension'])):
	print_error(path+" does not contain "+etpConst['extension']+" files")
        sys.exit(103)
    print_info(green(" * ")+red("Digesting files in ")+path)
    digestOut = []
    for i in digestContent:
        digestOut.append("MD5 "+md5sum(path+"/"+i)+" "+i+"\n")
    f = open(path+"/"+etpConst['digestfile'],"w")
    f.writelines(digestOut)
    f.flush()
    f.close()


def generator(packages, enzymeRequestBump = False):
    
    _packages = []
    # filter options
    for opt in packages:
	if (opt == "--force-bump"):
	    enzymeRequestBump = True
	else:
	    _packages.append(opt)
    packages = _packages
    
    for package in packages:
        # check if the package provided is valid
        validFile = False
        if os.path.isfile(package) and package.endswith(".tbz2"):
	    validFile = True
        if (not validFile):
	    print_error("no valid .tbz2 file specified")
            sys.exit(4)

        packagename = package.split("/")[len(package.split("/"))-1]

        print_info(yellow(" * ")+red("Processing: ")+bold(packagename)+red(", please wait..."))
        etpData = extractPkgData(package)

        # now try to import etpData inside the database
        dbconn = databaseTools.etpDatabase()
	#dbconn.searchPackages(etpData['name'])
	#dbconn.retrievePackageInfo(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])
	#dbconn.removePackage(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])
	dbconn.searchPackages(etpData['name'])
	
	#dbconn.retrievePackageInfo(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])
        #dbconn.addPackage(etpData)
        dbconn.closeDB()

        # look where I can store the file and return its path
        etpOutput, etpOutfilePath = allocateFile(etpData,enzymeRequestBump)

        rc = False

        if etpOutfilePath is not None:
	    print_info(green(" * ")+red("Writing Entropy Specifications file: ")+etpOutfilePath)
	    f = open(etpOutfilePath,"w")
	    f.writelines(etpOutput)
	    f.flush()
	    f.close()
	    # digesting directory
	    createDigest(etpOutfilePath)
	    rc = True
        else:
	    print_info(green(" * ")+red("Not generating a new Entropy Specifications file, not needed for ")+bold(packagename))
        # clean garbage
        os.system("rm -rf "+etpConst['packagestmpdir']+"/"+etpData['name']+"-"+etpData['version'])

# Enzyme tool called, we need to parse the Store directory and call generator()
def enzyme(options):

    enzymeRequestBump = False
    _atoms = []
    for i in atoms:
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
	rc = generator([tbz2path], enzymeRequestBump)
	if (rc):
	    etpCreated += 1
	    os.system("mv "+tbz2path+" "+etpConst['packagessuploaddir']+"/ -f")
	else:
	    etpNotCreated += 1
	    os.system("rm -rf "+tbz2path)

    print_info(green(" * ")+red("Statistics: ")+blue("etp created: ")+bold(str(etpCreated))+yellow(" - ")+darkblue("etp discarded: ")+bold(str(etpNotCreated)))

# This function extracts all the info from a .tbz2 file and returns them
def extractPkgData(package):

    # Clean the variables
    for i in etpData:
	etpData[i] = ""

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

    print_info(yellow(" * ")+red("Unpacking package data..."),back = True)
    # unpack file
    tbz2TmpDir = etpConst['packagestmpdir']+"/"+etpData['name']+"-"+etpData['version']+"/"
    unpackTbz2(tbz2File,tbz2TmpDir)

    print_info(yellow(" * ")+red("Getting package CHOST..."),back = True)
    # Fill chost
    f = open(tbz2TmpDir+dbCHOST,"r")
    etpData['chost'] = f.readline().strip()
    f.close()

    print_info(yellow(" * ")+red("Getting package location path..."),back = True)
    # local path to the file
    etpData['packagepath'] = etpConst['packagesbindir']+"/"+pkgname+"-"+pkgver+".tbz2"

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
	for atom in tmpSources:
	    if atom.endswith("?"):
	        etpData['sources'] += "="+atom[:len(atom)-1]+"|"
	    elif (not atom.startswith("(")) and (not atom.startswith(")")):
		etpData['sources'] += atom+" "
    except IOError:
	etpData['sources'] = ""

    print_info(yellow(" * ")+red("Getting package mirrors list..."),back = True)
    # manage etpData['sources'] to create etpData['mirrorlinks']
    # =mirror://openoffice|link1|link2|link3
    tmpMirrorList = etpData['sources'].split()
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
	    etpData['mirrorlinks'] += out+" "
    etpData['mirrorlinks'] = removeSpaceAtTheEnd(etpData['mirrorlinks'])

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
    for i in tmpUSE:
        etpData['useflags'] += i+" "
    etpData['useflags'] = removeSpaceAtTheEnd(etpData['useflags'])

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
    for i in ETP_ARCHS:
        if pkgArchs.find(i) != -1 and (pkgArchs.find("-"+i) == -1): # in case we find something like -amd64...
	    etpData['binkeywords'] += i+" "
    etpData['binkeywords'] = removeSpaceAtTheEnd(etpData['binkeywords'])

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

    # now keep only the ones not available in etpData['dependencies']
    for i in runtimeNeededPackages:
        if etpData['dependencies'].find(i) == -1:
	    # filter itself
	    if (i != etpData['category']+"/"+etpData['name']):
	        etpData['rundependencies'] += i+" "

    for i in runtimeNeededPackagesXT:
	x = dep_getkey(i)
        if etpData['dependencies'].find(x) == -1:
	    # filter itself
	    if (x != etpData['category']+"/"+etpData['name']):
	        etpData['rundependenciesXT'] += i+" "
    
    # format properly
    etpData['rundependencies'] = removeSpaceAtTheEnd(etpData['rundependencies'])
    etpData['rundependenciesXT'] = removeSpaceAtTheEnd(etpData['rundependenciesXT'])

    print_info(yellow(" * ")+red("Getting Reagent API version..."),back = True)
    # write API info
    etpData['etpapi'] = ETP_API

    print_info(yellow(" * ")+red("Done"),back = True)
    return etpData

# This function generates the right path for putting the .etp file
# and take count of already available ones bumping version only if needed
def allocateFile(etpData, enzymeRequestBump = False):

    # this will be the first thing to return
    etpOutput = []
    # append header
    etpOutput.append(ETP_HEADER_TEXT)
    
    # order keys
    keys = []
    for i in etpData:
	keys.append(i)
    
    sortedKeys = alphaSorter(keys)
    
    for i in sortedKeys:
        if (etpData[i]):
            etpOutput.append(i+": "+etpData[i]+"\n")

    # locate directory structure
    etpOutfileDir = etpConst['packagesdatabasedir']+"/"+etpData['category']+"/"+etpData['name']
    #etpOutfileDir = translateArch(etpOutfileDir,etpData['chost'])
    etpOutfileName = etpData['name']+"-"+etpData['version']+"-etp"+ETP_REVISION_CONST+etpConst['extension']
    etpOutfilePath = etpOutfileDir+"/"+etpOutfileName

    # we've the directory, then create it
    if (not os.path.isdir(etpOutfileDir)):
	try:
	    os.makedirs(etpOutfileDir)
	except OSError:
	    pass
	# it's a brand new dir
	etpOutfilePath = re.subn(ETP_REVISION_CONST,"1", etpOutfilePath)[0]
    else: # directory already exists, check for already available files
        alreadyAvailableFiles = []
	for i in range(MAX_ETP_REVISION_COUNT+1):
	    testfile = re.subn(ETP_REVISION_CONST,str(i), etpOutfilePath)[0]
	    if (os.path.isfile(testfile)):
	        alreadyAvailableFiles.append(testfile)
	if (alreadyAvailableFiles == []):
	    etpOutfilePath = re.subn(ETP_REVISION_CONST,"1", etpOutfilePath)[0]
        else:
	    # grab the last one
	    possibleOldFile = alreadyAvailableFiles[len(alreadyAvailableFiles)-1]
	    # now compares both to see if they're equal or not
	    try:
	        import md5
	        import string
		a = open(possibleOldFile,"r")
		cntA = a.readlines()
		cntB = etpOutput
		cntA = string.join(cntA)
		cntB = string.join(cntB)
		a.close()
		md5A = md5.new()
		md5B = md5.new()
		md5A.update(cntA)
		md5B.update(cntB)
		
		if (md5A.digest() == md5B.digest()) and (not enzymeRequestBump):
		    etpOutfilePath = None
		else:
		    # add 1 to: packagename-1.2.3-r1-etpX.etp
		    newFileCounter = int(possibleOldFile.split("-")[len(possibleOldFile.split("-"))-1].split(etpConst['extension'])[0].split(etpConst['extension'][1:])[1])
		    newFileCounter += 1
		    etpOutfilePath = re.subn(ETP_REVISION_CONST,str(newFileCounter), etpOutfilePath)[0]
	    except OSError:
		etpOutfilePath = possibleOldFile

    return etpOutput, etpOutfilePath
