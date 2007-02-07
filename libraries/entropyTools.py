#!/usr/bin/python
# Copyright Fabio Erculiani - Sabayon Linux 2007

# DESCRIPTION:
# generic tools for all the handlers applications

import portage
import portage_const
from portage_dep import isvalidatom, isjustname, dep_getkey

from entropyConstants import *
import commands
import re

# resolve atoms automagically (best, not current!)
# sys-libs/application --> sys-libs/application-1.2.3-r1
def getBestAtom(atom):
    return portage.portdb.xmatch("bestmatch-visible",str(atom))

def getArchFromChost(chost):
	# when we'll add new archs, we'll have to add a testcase here
	if chost.startswith("x86_64"):
	    resultingArch = "amd64"
	elif chost.split("-")[0].startswith("i") and chost.split("-")[0].endswith("86"):
	    resultingArch = "x86"
	else:
	    resultingArch = "ERROR"
	
	return resultingArch

def translateArch(string,chost):
    if string.find(ETP_ARCH_CONST) != -1:
        # substitute %ARCH%
        resultingArch = getArchFromChost(chost)
	return re.subn(ETP_ARCH_CONST,resultingArch, string)[0]
    else:
	return string

def getInstalledAtom(atom):
    if (isjustname(atom) == 1):
        # resolve name to atom
	rc = portage.db['/']['vartree'].dep_match(str(atom))
	return rc[len(rc)-1]
    else:
	return atom

def removeSpaceAtTheEnd(string):
    if string.endswith(" "):
        return string[:len(string)-1]
    else:
	return string

def print_error(msg):
    print "* erro *  : "+msg

def print_info(msg):
    print "* info *  : "+msg

def print_warning(msg):
    print "* warn *  : "+msg

def print_generic(msg): # here we'll wrap any nice formatting
    print msg

# This function extracts all the info from a .tbz2 file and returns them
def extractPkgData(package):

    tbz2File = package
    
    package = package.split(".tbz2")
    package = package[0].split("-")
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

    import xpak
    tbz2 = xpak.tbz2(tbz2File)
    tbz2TmpDir = etpConst['packagestmpdir']+"/"+etpData['name']+"-"+etpData['version']+"/"
    tbz2.decompose(tbz2TmpDir)

    # Fill chost
    f = open(tbz2TmpDir+dbCHOST,"r")
    etpData['chost'] = f.readline().strip()
    f.close()

    # Fill description
    try:
        f = open(tbz2TmpDir+dbDESCRIPTION,"r")
        etpData['description'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['description'] = ""

    # Fill homepage
    try:
        f = open(tbz2TmpDir+dbHOMEPAGE,"r")
        etpData['homepage'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['homepage'] = ""

    # Fill url
    for i in etpSources['packagesuri']:
        etpData['download'] += translateArch(i+etpData['name']+"-"+etpData['version']+".tbz2",etpData['chost'])+" "
    if (not etpData['download']):
        print_error("no 'packages|<uri>' specified in "+etpConst['repositoriesconf'])
	sys.exit(101)
    etpData['download'] = removeSpaceAtTheEnd(etpData['download'])

    # Fill category
    f = open(tbz2TmpDir+dbCATEGORY,"r")
    etpData['category'] = f.readline().strip()
    f.close()

    # Fill CFLAGS
    f = open(tbz2TmpDir+dbCFLAGS,"r")
    etpData['cflags'] = f.readline().strip()
    f.close()

    # Fill CXXFLAGS
    try:
        f = open(tbz2TmpDir+dbCXXFLAGS,"r")
        etpData['cxxflags'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['cxxflags'] = ""

    # Fill license
    try:
        f = open(tbz2TmpDir+dbLICENSE,"r")
        etpData['license'] = f.readline().strip()
        f.close()
    except IOError:
        etpData['license'] = ""

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
    
    # manage etpData['sources'] to create etpData['mirrorlinks']
    # =mirror://openoffice|link1|link2|link3
    tmpMirrorList = etpData['sources'].split()
    for i in tmpMirrorList:
        if i.startswith("mirror://"):
	    # parse what mirror I need
	    x = i.split("/")[2]
	    mirrorlist = portage.thirdpartymirrors[x]
	    mirrorURI = "mirror://"+x
	    out = "="+mirrorURI+"|"
	    for mirror in mirrorlist:
	        out += mirror+"|"
	    if out.endswith("|"):
		out = out[:len(out)-1]
	    etpData['mirrorlinks'] += out+" "
    etpData['mirrorlinks'] = removeSpaceAtTheEnd(etpData['mirrorlinks'])

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

    # fill KEYWORDS
    f = open(tbz2TmpDir+dbKEYWORDS,"r")
    etpData['keywords'] = f.readline().strip()
    f.close()

    # fill ARCHs
    pkgArchs = etpData['keywords']
    for i in ETP_ARCHS:
        if pkgArchs.find(i) != -1 and (pkgArchs.find("-"+i) == -1): # in case we find something like -amd64...
	    etpData['binkeywords'] += i+" "

    etpData['binkeywords'] = removeSpaceAtTheEnd(etpData['binkeywords'])

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
    # etpData['dependencies']

    useMatch = False
    openParenthesis = 0
    openOr = False
    useFlagQuestion = False
    for atom in roughDependencies:

	if atom.endswith("?"):
	    # we need to see if that useflag is enabled
	    useFlag = atom.split("?")[0]
	    useFlagQuestion = True
	    for i in etpData['useflags'].split():
		if i.startswith("!"):
		    if (i != useFlag):
			useMatch = True
			break
		else:
		    if (i == useFlag):
		        useMatch = True
		        break

        if atom.startswith("("):
	    openParenthesis += 1

        if atom.startswith(")"):
	    if (openOr):
		# remove last "_or_" from etpData['dependencies']
		openOr = False
		if etpData['dependencies'].endswith(dbOR):
		    etpData['dependencies'] = etpData['dependencies'][:len(etpData['dependencies'])-len(dbOR)]
		    etpData['dependencies'] += " "
	    openParenthesis -= 1
	    if (openParenthesis == 0):
		useFlagQuestion = False
		useMatch = False

        if atom.startswith("||"):
	    openOr = True
	
	if atom.find("/") != -1 and (not atom.startswith("!")) and (not atom.endswith("?")):
	    # it's a package name <pkgcat>/<pkgname>-???
	    if ((useFlagQuestion) and (useMatch)) or ((not useFlagQuestion) and (not useMatch)):
	        # check if there's an OR
		etpData['dependencies'] += atom
		if (openOr):
		    etpData['dependencies'] += dbOR
                else:
		    etpData['dependencies'] += " "

        if atom.startswith("!") and (not atom.endswith("?")):
	    if ((useFlagQuestion) and (useMatch)) or ((not useFlagQuestion) and (not useMatch)):
		etpData['conflicts'] += atom
		if (openOr):
		    etpData['conflicts'] += dbOR
                else:
		    etpData['conflicts'] += " "
		

    # format properly
    tmpConflicts = list(set(etpData['conflicts'].split()))
    etpData['conflicts'] = ''
    for i in tmpConflicts:
	i = i[1:] # remove "!"
	etpData['conflicts'] += i+" "
    etpData['conflicts'] = removeSpaceAtTheEnd(etpData['conflicts'])

    tmpDeps = list(set(etpData['dependencies'].split()))
    etpData['dependencies'] = ''
    for i in tmpDeps:
	etpData['dependencies'] += i+" "
    etpData['dependencies'] = removeSpaceAtTheEnd(etpData['dependencies'])

    # etpData['rdependencies']
    # Now we need to add environmental dependencies
    # Notes (take the example of mplayer that needed a newer libcaca release):
    # - we can use (from /var/db) "NEEDED" file to catch all the needed libraries to run the binary package
    # - we can use (from /var/db) "CONTENTS" to rapidly search the NEEDED files in the file above
    # return all the collected info

    # start collecting needed libraries
    try:
        f = open(tbz2TmpDir+"/"+dbNEEDED,"r")
        includedBins = f.readlines()
        f.close()
    except IOError:
	includedBins = ""
    
    neededLibraries = []
    # filter the first word
    for line in includedBins:
        line = line.strip().split()
	line = line[0]
	depLibs = commands.getoutput("ldd "+line).split("\n")
	for i in depLibs:
	    i = i.strip()
	    if i.find("=>") != -1:
	        i = i.split("=>")[1]
	    # format properly
	    if i.startswith(" "):
	        i = i[1:]
	    if i.startswith("//"):
	        i = i[1:]
	    i = i.split()[0]
	    neededLibraries.append(i)
    neededLibraries = list(set(neededLibraries))

    runtimeNeededPackages = []
    runtimeNeededPackagesXT = []
    for i in neededLibraries:
	if i.startswith("/"): # filter garbage
	    pkgs = commands.getoutput(pFindLibraryXT+i).split("\n")
	    if (pkgs[0] != ""):
	        for y in pkgs:
	            runtimeNeededPackagesXT.append(y)
		    y = dep_getkey(y)
		    runtimeNeededPackages.append(y)

    runtimeNeededPackages = list(set(runtimeNeededPackages))
    runtimeNeededPackagesXT = list(set(runtimeNeededPackagesXT))
    
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

    # write API info
    etpData['etpapi'] = ETP_API

    return etpData

# This function generates the right path for putting the .etp file
# and take count of already available ones bumping version only if needed
def allocateFile(etpData):

    # this will be the first thing to return
    etpOutput = []
    # append header
    etpOutput.append(ETP_HEADER_TEXT)
    for i in etpData:
        if (etpData[i]):
            etpOutput.append(i+": "+etpData[i]+"\n")

    # locate directory structure
    etpOutfileDir = etpConst['packagesdatabasedir']+"/"+etpData['category']+"/"+etpData['name']
    etpOutfileDir = translateArch(etpOutfileDir,etpData['chost'])
    etpOutfileName = etpData['name']+"-"+etpData['version']+"-etp"+ETP_REVISION_CONST+".etp"
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
		if md5A.digest() == md5B.digest():
		    etpOutfilePath = None
		else:
		    # add 1 to: packagename-1.2.3-r1-etpX.etp
		    newFileCounter = int(possibleOldFile.split("-")[len(possibleOldFile.split("-"))-1].split(".etp")[0].split("etp")[1])
		    newFileCounter += 1
		    etpOutfilePath = re.subn(ETP_REVISION_CONST,str(newFileCounter), etpOutfilePath)[0]
	    except OSError:
		etpOutfilePath = possibleOldFile

    return etpOutput, etpOutfilePath