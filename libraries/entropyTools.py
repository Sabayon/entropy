#!/usr/bin/python
# Copyright Fabio Erculiani - Sabayon Linux 2007

# DESCRIPTION:
# generic tools for all the handlers applications

import portage
import portage_const
from portage_dep import isvalidatom, isjustname, dep_getkey

from entropyConstants import *
import commands

# resolve atoms automagically (best, not current!)
# sys-libs/application --> sys-libs/application-1.2.3-r1
def getBestAtom(atom):
    rc = portage.portdb.xmatch("bestmatch-visible",str(atom))
    return rc

def getArch():
    return portage.settings["ARCH"]

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

def print_help():
    print "* IIIII * : Sabayon Linux binary-metafile-builder - written by Fabio Erculiani (C - 2007)"
    print "* usage * : binary-metafile-builder <valid gentoo .tbz2 file>"

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
    pData['name'] = pkgname
    pData['version'] = pkgver  # FIXME: add -etpNN

    import xpak
    tbz2 = xpak.tbz2(tbz2File)
    tbz2TmpDir = pTmpDir+"/"+pData['name']+"-"+pData['version']+"/"
    tbz2.decompose(tbz2TmpDir)
    

    # Fill description
    try:
        f = open(tbz2TmpDir+dbDESCRIPTION,"r")
        pData['description'] = f.readline().strip()
        f.close()
    except IOError:
        pData['description'] = ""

    # Fill homepage
    try:
        f = open(tbz2TmpDir+dbHOMEPAGE,"r")
        pData['homepage'] = f.readline().strip()
        f.close()
    except IOError:
        pData['homepage'] = ""

    # Fill chost
    f = open(tbz2TmpDir+dbCHOST,"r")
    pData['chost'] = f.readline().strip()
    f.close()

    # Fill url
    pData['download'] = pBinHost+pData['name']+"-"+pData['version']+".tbz2"

    # Fill category
    f = open(tbz2TmpDir+dbCATEGORY,"r")
    pData['category'] = f.readline().strip()
    f.close()

    # Fill CFLAGS
    f = open(tbz2TmpDir+dbCFLAGS,"r")
    pData['cflags'] = f.readline().strip()
    f.close()

    # Fill CXXFLAGS
    try:
        f = open(tbz2TmpDir+dbCXXFLAGS,"r")
        pData['cxxflags'] = f.readline().strip()
        f.close()
    except IOError:
        pData['cxxflags'] = ""

    # Fill license
    try:
        f = open(tbz2TmpDir+dbLICENSE,"r")
        pData['license'] = f.readline().strip()
        f.close()
    except IOError:
        pData['license'] = ""

    # Fill sources
    # FIXME: resolve mirror:// in something useful
    # FIXME: resolve amd64? url x86? url
    # portage.thirdpartymirrors['openoffice'] for example
    # !! keep mirror:// but write at the beginning something like
    try:
        f = open(tbz2TmpDir+dbSRC_URI,"r")
        pData['sources'] = f.readline().strip()
        f.close()
    except IOError:
	pass
    
    # manage pData['sources'] to create pData['mirrorlinks']
    # =mirror://openoffice|link1|link2|link3
    tmpMirrorList = pData['sources'].split()
    for i in tmpMirrorList:
        if i.startswith("mirror://"):
	    # parse what mirror I need
	    x = i.split("/")[2]
	    mirrorlist = portage.thirdpartymirrors[x]
	    out = "="+i+"|"
	    for mirror in mirrorlist:
	        out += mirror+"|"
	    if out.endswith("|"):
		out = out[:len(out)-1]
	    pData['mirrorlinks'] += out+" "
    pData['mirrorlinks'] = removeSpaceAtTheEnd(pData['mirrorlinks'])

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
	    pData['useflags'] += i+" "
	else:
	    pData['useflags'] += "-"+i+" "

    # cleanup
    tmpUSE = pData['useflags'].split()
    tmpUSE = list(set(tmpUSE))
    pData['useflags'] = ''
    for i in tmpUSE:
        pData['useflags'] += i+" "
    pData['useflags'] = removeSpaceAtTheEnd(pData['useflags'])

    # fill KEYWORDS
    f = open(tbz2TmpDir+dbKEYWORDS,"r")
    pData['keywords'] = f.readline().strip()
    f.close()

    # fill ARCHs
    pkgArchs = pData['keywords']
    for i in pArchs:
        if pkgArchs.find(i) != -1 and (pkgArchs.find("-"+i) == -1): # in case we find something like -amd64...
	    pData['binkeywords'] += i+" "

    pData['binkeywords'] = removeSpaceAtTheEnd(pData['binkeywords'])

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
    # pData['dependencies']

    useMatch = False
    openParenthesis = 0
    openOr = False
    useFlagQuestion = False
    for atom in roughDependencies:

	if atom.endswith("?"):
	    # we need to see if that useflag is enabled
	    useFlag = atom.split("?")[0]
	    useFlagQuestion = True
	    for i in pData['useflags'].split():
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
		# remove last "_or_" from pData['dependencies']
		openOr = False
		if pData['dependencies'].endswith(dbOR):
		    pData['dependencies'] = pData['dependencies'][:len(pData['dependencies'])-len(dbOR)]
		    pData['dependencies'] += " "
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
		pData['dependencies'] += atom
		if (openOr):
		    pData['dependencies'] += dbOR
                else:
		    pData['dependencies'] += " "

        if atom.startswith("!") and (not atom.endswith("?")):
	    if ((useFlagQuestion) and (useMatch)) or ((not useFlagQuestion) and (not useMatch)):
		pData['conflicts'] += atom
		if (openOr):
		    pData['conflicts'] += dbOR
                else:
		    pData['conflicts'] += " "
		

    # format properly
    tmpConflicts = list(set(pData['conflicts'].split()))
    pData['conflicts'] = ''
    for i in tmpConflicts:
	i = i[1:] # remove "!"
	pData['conflicts'] += i+" "
    pData['conflicts'] = removeSpaceAtTheEnd(pData['conflicts'])

    tmpDeps = list(set(pData['dependencies'].split()))
    pData['dependencies'] = ''
    for i in tmpDeps:
	pData['dependencies'] += i+" "
    pData['dependencies'] = removeSpaceAtTheEnd(pData['dependencies'])

    # pData['rdependencies']
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
    
    # now keep only the ones not available in pData['dependencies']
    for i in runtimeNeededPackages:
        if pData['dependencies'].find(i) == -1:
	    # filter itself
	    if (i != pData['category']+"/"+pData['name']):
	        pData['rundependencies'] += i+" "

    for i in runtimeNeededPackagesXT:
	x = dep_getkey(i)
        if pData['dependencies'].find(x) == -1:
	    # filter itself
	    if (x != pData['category']+"/"+pData['name']):
	        pData['rundependenciesXT'] += i+" "

    # format properly
    pData['rundependencies'] = removeSpaceAtTheEnd(pData['rundependencies'])

    pData['rundependenciesXT'] = removeSpaceAtTheEnd(pData['rundependenciesXT'])

    # write API info
    pData['etpapi'] = ETP_API+ETP_API_SUBLEVEL

    return pData

# This function will handle all the shit needed to write the *.etp file in the
# right directory, under the right name and revision
def writeEtpSpecFile(etpOutputFile):
    return
