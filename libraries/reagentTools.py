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
import os
import string
from portageTools import unpackTbz2, synthetizeRoughDependencies, getPackageRuntimeDependencies, dep_getkey, getThirdPartyMirrors

# Logging initialization
import logTools
reagentLog = logTools.LogFile(level=etpConst['reagentloglevel'],filename = etpConst['reagentlogfile'])

def generator(package, enzymeRequestBump = False, dbconnection = None):

    # check if the package provided is valid
    validFile = False
    if os.path.isfile(package) and package.endswith(".tbz2"):
	validFile = True
    if (not validFile):
	print_warning(package+" does not exist !")

    packagename = os.path.basename(package)

    print_info(yellow(" * ")+red("Processing: ")+bold(packagename)+red(", please wait..."))
    etpData = extractPkgData(package)
    
    if dbconnection is None:
	dbconn = databaseTools.etpDatabase(readOnly = False, noUpload = True)
    else:
	dbconn = dbconnection

    updated, revision, etpDataUpdated = dbconn.handlePackage(etpData,enzymeRequestBump)
    
    # return back also the new possible package filename, so that we can make decisions on that
    newFileName = os.path.basename(etpDataUpdated['download'])
    
    if dbconnection is None:
	dbconn.commitChanges()
	dbconn.closeDB()

    if (updated) and (revision != 0):
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" entry has been updated. Revision: ")+bold(str(revision)))
	return True, newFileName
    elif (updated) and (revision == 0):
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" entry newly created."))
	return True, newFileName
    else:
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" does not need to be updated. Current revision: ")+bold(str(revision)))
	return False, newFileName


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

    # open db connection
    dbconn = databaseTools.etpDatabase(readOnly = False, noUpload = True)

    counter = 0
    etpCreated = 0
    etpNotCreated = 0
    for tbz2 in tbz2files:
	counter += 1
	tbz2name = tbz2.split("/")[len(tbz2.split("/"))-1]
	print_info(" ("+str(counter)+"/"+str(totalCounter)+") Processing "+tbz2name)
	tbz2path = etpConst['packagesstoredir']+"/"+tbz2
	rc, newFileName = generator(tbz2path, enzymeRequestBump, dbconn)
	if (rc):
	    etpCreated += 1
	    # create .hash file
	    os.system("mv "+tbz2path+" "+etpConst['packagessuploaddir']+"/"+newFileName+" -f")
	    hashFilePath = createHashFile(etpConst['packagessuploaddir']+"/"+newFileName)
	else:
	    etpNotCreated += 1
	    os.system("rm -rf "+tbz2path)
	dbconn.commitChanges()

    dbconn.commitChanges()
    dbconn.closeDB()

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
	    if (line[0] == "obj") or (line[0] == "sym"):
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

    # [][][] Kernel dependent packages hook [][][]
    kernelDependentModule = False
    for file in etpData['content'].split():
	if file.find("/lib/modules/") != -1:
	    kernelDependentModule = True
	    # get the version of the modules
	    kmodver = file.split("/lib/modules/")[1]
	    kmodver = kmodver.split("/")[0]
	    break

    # add strict kernel dependency
    # done below
    
    # modify etpData['download']
    # done below

    print_info(yellow(" * ")+red("Getting package download URL..."),back = True)
    # Fill download relative URI
    if (kernelDependentModule):
	extrakernelinfo = "-linux-core-"+kmodver
    else:
	extrakernelinfo = ""
    etpData['download'] = etpConst['binaryurirelativepath']+etpData['name']+"-"+etpData['version']+extrakernelinfo+".tbz2"

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
    if (kernelDependentModule):
	# add kmodver to the dependency
	etpData['dependencies'] += " sys-kernel/linux-core-"+kmodver

    # etpData['rdependencies']
    # Now we need to add environmental dependencies
    # Notes (take the example of mplayer that needed a newer libcaca release):
    # - we can use (from /var/db) "NEEDED" file to catch all the needed libraries to run the binary package
    # - we can use (from /var/db) "CONTENTS" to rapidly search the NEEDED files in the file above
    # return all the collected info

    print_info(yellow(" * ")+red("Getting package runtime dependencies..."),back = True)
	
    # start collecting needed libraries
    runtimeNeededPackages, runtimeNeededPackagesXT, neededLibraries = getPackageRuntimeDependencies(tbz2TmpDir+"/"+dbNEEDED)
    
    if len(neededLibraries) > 0:
	etpData['neededlibs'] = string.join(neededLibraries," ")
    else:
	etpData['neededlibs'] = ""

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


def smartapps(options):
    
    if (len(options) == 0):
        print_error(yellow(" * ")+red("No valid tool specified."))
	sys.exit(501)
    
    if (options[0] == "create"):
        myopts = options[1:]
	
	if (len(myopts) == 0):
	    print_error(yellow(" * ")+red("No packages specified."))
	    sys.exit(502)
	
	# open db
	dbconn = databaseTools.etpDatabase(readOnly = True)
	
	# seek valid apps (in db)
	validPackages = []
	for opt in myopts:
	    pkgsfound = dbconn.searchPackages(opt)
	    for pkg in pkgsfound:
		validPackages.append(pkg[0])

	dbconn.closeDB()

	if (len(validPackages) == 0):
	    print_error(yellow(" * ")+red("No valid packages specified."))
	    sys.exit(503)

	# print the list
	print_info(green(" * ")+red("This is the list of the packages that would be worked out:"))
	for pkg in validPackages:
	    print_info(green("\t[SMART] - ")+bold(pkg))

	rc = askquestion(">>   Would you like to create the packages above ?")
	if rc == "No":
	    sys.exit(0)
	
	for pkg in validPackages:
	    print_info(green(" * ")+red("Creating smartapp package from ")+bold(pkg))
	    smartgenerator(pkg)

	print_info(green(" * ")+red("Smartapps creation done, remember to test them before publishing."))

    
# tool that generates .tar.bz2 packages with all the binary dependencies included
# @returns the package file path
# NOTE: this section is highly portage dependent
def smartgenerator(atom):
    
    dbconn = databaseTools.etpDatabase(readOnly = True)
    
    # handle branch management:
    # if unstable package is found, that will be used
    # otherwise we revert to the stable one
    if (dbconn.isSpecificPackageAvailable(package, branch == "unstable")):
	branch = "unstable"
    else:
	branch = "stable"
    
    # check if the application package is available, otherwise, download
    pkgfilepath = dbconn.retrievePackageVar(atom,"download", branch)
    pkgneededlibs = dbconn.retrievePackageVar(atom,"neededlibs", branch)
    pkgneededlibs = pkgneededlibs.split()
    pkgcontent = dbconn.retrievePackageVar(atom,"content", branch)
    pkgfilename = pkgfilepath.split("/")[len(pkgfilepath.split("/"))-1]
    pkgname = pkgfilename.split(".tbz2")[0]
    
    # extra dependency check
    extraDeps = []
    
    pkgdependencies = dbconn.retrievePackageVar(atom,"dependencies", branch).split()
    for dep in pkgdependencies:
	# remove unwanted dependencies
	if (dep.find("sys-devel") == -1) \
		and (dep.find("dev-util") == -1) \
		and (dep.find("dev-lang") == -1) \
		and (dep.find("x11-libs") == -1) \
		and (dep.find("x11-proto") == -1):
	    extraDeps.append(dep_getkey(dep))

    # expand dependencies
    _extraDeps = []
    for dep in extraDeps:
	depnames = dbconn.searchPackages(dep)
	for depname in depnames:
	    _extraDeps.append(depname[0])
	    if depname[0].find("dev-libs/glib") != -1:
		# add pango
		pangopkgs = dbconn.searchSimilarPackages("x11-libs/pango")
		for pangopkg in pangopkgs:
		    extraDeps.append(pangopkg)
    
    extraDeps = list(set(_extraDeps))
    
    extraPackages = []
    # get their files
    for dep in extraDeps:
	depcontent = dbconn.retrievePackageVar(dep,"download", branch)
	extraPackages.append(depcontent.split("/")[len(depcontent.split("/"))-1])
	
    pkgneededlibs = list(set(pkgneededlibs))
    extraPackages = list(set(extraPackages))
    
    print_info(green(" * ")+red("This is the list of the dependencies that would be included:"))
    for i in extraPackages:
        print_info(green("    [] ")+red(i))
	
    pkgdlpaths = [
    		etpConst['packagesbindir'],
		etpConst['packagessuploaddir'],
    ]
    
    mainBinaryPath = ""
    # check the main binary
    for path in pkgdlpaths:
	if os.path.isfile(path+"/"+pkgfilename):
	    mainBinaryPath = path+"/"+pkgfilename
	    break
    # now check - do a for cycle
    if (mainBinaryPath == ""):
	# I have to download it
	# FIXME: complete this
	# do it when we have all the atoms that should be downloaded
	print "download needed: not yet implemented"

    extraPackagesPaths = []
    # check dependencies
    for dep in extraPackages:
	for path in pkgdlpaths:
	    if os.path.isfile(path+"/"+dep):
		extraPackagesPaths.append(path+"/"+dep)
		break
    
    #print mainBinaryPath
    #print extraPackagesPaths
    
    # create the working directory
    pkgtmpdir = etpConst['packagestmpdir']+"/"+pkgname
    #print "DEBUG: "+pkgtmpdir
    if os.path.isdir(pkgtmpdir):
	os.system("rm -rf "+pkgtmpdir)
    os.makedirs(pkgtmpdir)
    uncompressTarBz2(mainBinaryPath,pkgtmpdir)

    binaryExecs = []
    pkgcontent = pkgcontent.split()
    for file in pkgcontent:
	# remove /
	filepath = pkgtmpdir+file
	import commands
	if os.access(filepath,os.X_OK):
	    # test if it's an exec
	    out = commands.getoutput("file "+filepath).split("\n")[0]
	    if out.find("LSB executable") != -1:
		binaryExecs.append(file)
	# check if file is executable

    # now uncompress all the rest
    for dep in extraPackagesPaths:
	uncompressTarBz2(dep,pkgtmpdir)

    # remove unwanted files (header files)
    for (dir, subdirs, files) in os.walk(pkgtmpdir):
	for file in files:
	    if file.endswith(".h"):
		try:
		    os.remove(file)
		except:
		    pass

    librariesBlacklist = []
    # add glibc libraries to the blacklist
    glibcPkg = dbconn.searchPackages("sys-libs/glibc")
    if len(glibcPkg) > 0:
        glibcContent = dbconn.retrievePackageVar(glibcPkg[0][0],"content", branch)
	for file in glibcContent.split():
	    if ((file.startswith("/lib/")) or (file.startswith("/lib64/"))) and (file.find(".so") != -1):
		librariesBlacklist.append(file)
    # add here more blacklisted files
    
    # now copy all the needed libraries inside the tmpdir
    # FIXME: should we rely on the libraries in the packages instead of copying them from the system?
    # FIXME: in this case, we have to d/l them if they're not in the packages directory
    _pkgneededlibs = []
    for lib in pkgneededlibs:
	# extract dir, filter /lib because it causes troubles ?
	# FIXME: I think that sould be better creating a blacklist instead
	fileOk = True
	for file in librariesBlacklist:
	    if lib == file:
		fileOk = False
		break
	if (fileOk):
	    _pkgneededlibs.append(lib)
	    libdir = os.path.dirname(lib)
	    #print lib
	    if not os.path.isdir(pkgtmpdir+libdir):
	        os.makedirs(pkgtmpdir+libdir)
	    os.system("cp -p "+lib+" "+pkgtmpdir+libdir)
    pkgneededlibs = _pkgneededlibs
    # collect libraries in the directories
    
    # catch /usr/lib/gcc/
    gcclibpath = ""
    for i in pkgneededlibs:
	if i.startswith("/usr/lib/gcc"):
	    gcclibpath += ":"+os.path.dirname(i)
	    break
    
    # now create the bash script for each binaryExecs
    os.makedirs(pkgtmpdir+"/wrp")
    bashScript = []
    bashScript.append(
    			'#!/bin/sh\n'
			'cd $1\n'

			'MYPYP=$(find $PWD/lib/python2.4/site-packages/ -type d -printf %p: 2> /dev/null)\n'
			'MYPYP2=$(find $PWD/lib/python2.5/site-packages/ -type d -printf %p: 2> /dev/null)\n'
			'export PYTHONPATH=$MYPYP:MYPYP2:$PYTHONPATH\n'

			'export PATH=$PWD:$PWD/sbin:$PWD/bin:$PWD/usr/bin:$PWD/usr/sbin:$PWD/usr/X11R6/bin:$PWD/libexec:$PWD/usr/local/bin:$PWD/usr/local/sbin:$PATH\n'
			
			'export LD_LIBRARY_PATH='
			'$PWD/lib:'
			'$PWD/lib64'+gcclibpath+':'
			'$PWD/usr/lib:'
			'$PWD/usr/lib64:'
			'$PWD/usr/lib/nss:'
			'$PWD/usr/lib/nspr:'
			'$PWD/usr/lib64/nss:'
			'$PWD/usr/lib64/nspr:'
			'$PWD/usr/qt/3/lib:'
			'$PWD/usr/qt/3/lib64:'
			'$PWD/usr/kde/3.5/lib:'
			'$PWD/usr/kde/3.5/lib64:'
			'$LD_LIBRARY_PATH\n'
			
			'export KDEDIRS=$PWD/usr/kde/3.5:$PWD/usr:$KDEDIRS\n'
			
			'export PERL5LIB=$PWD/usr/lib/perl5:$PWD/share/perl5:$PWD/usr/lib/perl5/5.8.1'
			':$PWD/usr/lib/perl5/5.8.2:'
			':$PWD/usr/lib/perl5/5.8.3:'
			':$PWD/usr/lib/perl5/5.8.4:'
			':$PWD/usr/lib/perl5/5.8.5:'
			':$PWD/usr/lib/perl5/5.8.6:'
			':$PWD/usr/lib/perl5/5.8.7:'
			':$PWD/usr/lib/perl5/5.8.8:'
			':$PWD/usr/lib/perl5/5.8.9:'
			':$PWD/usr/lib/perl5/5.8.10\n'
			
			'export MANPATH=$PWD/share/man:$MANPATH\n'
			'export GUILE_LOAD_PATH=$PWD/share/:$GUILE_LOAD_PATH\n'
			'export SCHEME_LIBRARY_PATH=$PWD/share/slib:$SCHEME_LIBRARY_PATH\n'
			
			'# Setup pango\n'
			'MYPANGODIR=$(find $PWD/usr/lib/pango -name modules)\n'
			'if [ -n "$MYPANGODIR" ]; then\n'
			'    export PANGO_RC_FILE=$PWD/etc/pango/pangorc\n'
			'    echo "[Pango]" > $PANGO_RC_FILE\n'
			'    echo "ModulesPath=${MYPANGODIR}" >> $PANGO_RC_FILE\n'
			'    echo "ModuleFiles=${PWD}/etc/pango/pango.modules" >> $PANGO_RC_FILE\n'
			'    pango-querymodules > ${PWD}/etc/pango/pango.modules\n'
			'fi\n'
			'$2\n'
    )
    f = open(pkgtmpdir+"/wrp/wrapper","w")
    f.writelines(bashScript)
    f.flush()
    f.close()
    # chmod
    os.chmod(pkgtmpdir+"/wrp/wrapper",0755)



    # now list files in /sh and create .desktop files
    for file in binaryExecs:
	file = file.split("/")[len(file.split("/"))-1]
	runFile = []
	runFile.append(
			'#include <cstdlib>\n'
			'#include <cstdio>\n'
			'#include <stdio.h>\n'
			'int main() {\n'
			'  int rc = system(\n'
			'                "pid=$(pidof '+file+'.exe);"\n'
			'                "listpid=$(ps x | grep $pid);"\n'
			'                "filename=$(echo $listpid | cut -d\' \' -f 5);"'
			'                "currdir=$(dirname $filename);"\n'
			'                "/bin/sh $currdir/wrp/wrapper $currdir '+file+'" );\n'
			'  return rc;\n'
			'}\n'
	)
	f = open(pkgtmpdir+"/"+file+".cc","w")
	f.writelines(runFile)
	f.flush()
	f.close()
	# now compile
	os.system("cd "+pkgtmpdir+"/ ; g++ -Wall "+file+".cc -o "+file+".exe")
	os.remove(pkgtmpdir+"/"+file+".cc")

    # now compress in .tar.bz2 and place in etpConst['smartappsdir']
    #print etpConst['smartappsdir']+"/"+pkgname+"-"+etpConst['currentarch']+".tar.bz2"
    #print pkgtmpdir+"/"
    compressTarBz2(etpConst['smartappsdir']+"/"+pkgname+"-"+etpConst['currentarch']+".tbz2",pkgtmpdir+"/")
    
    dbconn.closeDB()