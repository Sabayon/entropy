#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for all the handlers applications

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

def initializePortageTree():
    portage.settings.unlock()
    portage.settings['PORTDIR'] = etpConst['portagetreedir']
    portage.settings['DISTDIR'] = etpConst['distfilesdir']
    portage.settings['PORTDIR_OVERLAY'] = etpConst['overlays']
    portage.settings.lock()
    portage.portdb.__init__(etpConst['portagetreedir'])

# Fix for wrong cache entries - DO NOT REMOVE
import os
from entropyConstants import *
os.environ['PORTDIR'] = etpConst['portagetreedir']
os.environ['PORTDIR_OVERLAY'] = etpConst['overlays']
os.environ['DISTDIR'] = etpConst['distfilesdir']
import portage
import portage_const
from portage_dep import isvalidatom, isspecific, isjustname, dep_getkey, dep_getcpv
from entropyConstants import *

initializePortageTree()

# colours support
import output
from output import bold, colorize, green, darkred, red, yellow, blue, darkblue, nocolor
import re
import sys
import random
import commands

# EXIT STATUSES: 100-199

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

def translateArchFromUname(string):
    rc = commands.getoutput("uname -m").split("\n")[0]
    return translateArch(string,rc)

# initialize %ARCH% in etpConst['x']
for i in etpConst:
    if (type(etpConst[i]) is list):
	for x in range(len(etpConst[i])):
	    etpConst[i][x] = translateArchFromUname(etpConst[i][x])
    elif (type(etpConst[i]) is str):
	etpConst[i] = translateArchFromUname(etpConst[i])

def isRoot():
    import getpass
    if (getpass.getuser() == "root"):
        return True
    return False

def getPortageEnv(var):
    try:
	rc = portage.config(clone=portage.settings).environ()[var]
	return rc
    except KeyError:
	return None

def getRandomNumber():
    return int(str(random.random())[2:7])

def getThirdPartyMirrors(mirrorname):
    return portage.thirdpartymirrors[mirrorname]

# resolve atoms automagically (best, not current!)
# sys-libs/application --> sys-libs/application-1.2.3-r1
def getBestAtom(atom):
    try:
        rc = portage.portdb.xmatch("bestmatch-visible",str(atom))
        return rc
    except ValueError:
	return "!!conflicts"

# same as above but includes masked ebuilds
def getBestMaskedAtom(atom):
    atoms = portage.portdb.xmatch("match-all",str(atom))
    # find the best
    from portage_versions import best
    return best(atoms)

# I need a valid complete atom...
def calculateFullAtomsDependencies(atoms, deep = False, extraopts = ""):
    # in order... thanks emerge :-)
    deepOpt = ""
    if (deep):
	deepOpt = "-Du"
    deplist = []
    blocklist = []
    
    try:
	useflags = "USE='"+os.environ['USE']+"' "
    except:
	useflags = ""
    cmd = useflags+cdbRunEmerge+" --pretend --color=n --quiet "+deepOpt+" "+extraopts+" "+atoms
    result = commands.getoutput(cmd).split("\n")
    for line in result:
	if line.startswith("[ebuild"):
	    line = line.split("] ")[1].split(" [")[0].split()[0].strip()
	    deplist.append(line)
	if line.startswith("[blocks"):
	    line = line.split("] ")[1].split()[0].strip()
	    blocklist.append(line)

    # filter garbage
    _deplist = []
    for i in deplist:
	if (i != "") and (i != " "):
	    _deplist.append(i)
    deplist = _deplist
    _blocklist = []
    for i in blocklist:
	if (i != "") and (i != " "):
	    _blocklist.append(i)
    blocklist = _blocklist

    if deplist != []:
        return deplist, blocklist
    else:
	rc = os.system(cmd)
	sys.exit(100)

def calculateAtomUSEFlags(atom):
    try:
	useflags = "USE='"+os.environ['USE']+"' "
    except:
	useflags = ""
    cmd = useflags+cdbRunEmerge+" --pretend --color=n --nodeps --quiet --verbose "+atom
    result = commands.getoutput(cmd).split("\n")
    useparm = ""
    for line in result:
	if line.startswith("[ebuild") and (line.find("USE=") != -1):
	    useparm = line.split('USE="')[len(line.split('USE="'))-1].split('"')[0].strip()
    useparm = useparm.split()
    _useparm = []
    for use in useparm:
	# -cups
	if use.startswith("-") and (not use.endswith("*")):
	    use = darkblue(use)
	# -cups*
	elif use.startswith("-") and (use.endswith("*")):
	    use = yellow(use)
	# use flag not available
	elif use.startswith("("):
	    use = blue(use)
	# cups*
	elif use.endswith("*"):
	    use = green(use)
	else:
	    use = darkred(use)
	_useparm.append(use)
    useparm = string.join(_useparm," ")
    return useparm

# should be only used when a pkgcat/pkgname <-- is not specified (example: db, amarok, AND NOT media-sound/amarok)
def getAtomCategory(atom):
    try:
        rc = portage.portdb.xmatch("match-all",str(atom))[0].split("/")[0]
        return rc
    except:
	return None

# This function compare the version number of two atoms
# This function needs a complete atom, pkgcat (not mandatory) - pkgname - pkgver
# if atom1 < atom2 --> returns a NEGATIVE number
# if atom1 > atom2 --> returns a POSITIVE number
# if atom1 == atom2 --> returns 0
def compareAtoms(atom1,atom2):
    # filter pkgver
    x, atom1 = extractPkgNameVer(atom1)
    x, atom2 = extractPkgNameVer(atom2)
    from portage_versions import vercmp
    return vercmp(atom1,atom2)

def countdown(secs=5,what="Counting..."):
    import time
    if secs:
	print what
        for i in range(secs):
            sys.stdout.write(str(i)+" ")
            sys.stdout.flush()
	    time.sleep(1)

def spinner(rotations, interval, message=''):
	for x in xrange(rotations):
		writechar(message + '|/-\\'[x%4] + '\r')
		time.sleep(interval)
	writechar(' ')
	for i in xrange(len(message)): print ' ',
	writechar('\r')

def writechar(char):
	sys.stdout.write(char); sys.stdout.flush()

# please always force =pkgcat/pkgname-ver if possible
def getInstalledAtom(atom):
    rc = portage.db['/']['vartree'].dep_match(str(atom))
    if (rc != []):
	if (len(rc) == 1):
	    return rc[0]
	else:
            return rc[len(rc)-1]
    else:
        return None

def getPackageSlot(atom):
    if atom.startswith("="):
	atom = atom[1:]
    rc = portage.db['/']['vartree'].getslot(atom)
    if rc != "":
	return rc
    else:
	return None

def removePackageOperators(atom):
    atom = dep_getcpv(atom)
    return atom

# you must provide a complete atom
def collectBinaryFilesForInstalledPackage(atom):
    if atom.startswith("="):
	atom = atom[1:]
    pkgcat = atom.split("/")[0]
    pkgnamever = atom.split("/")[1]
    dbentrypath = "/var/db/pkg/"+pkgcat+"/"+pkgnamever+"/CONTENTS"
    binarylibs = []
    if os.path.isfile(dbentrypath):
	f = open(dbentrypath,"r")
	contents = f.readlines()
	f.close()
	for i in contents:
	    file = i.split()[1]
	    if i.startswith("obj") and (file.find("lib") != -1) and (file.find(".so") != -1) and (not file.endswith(".la")):
		# FIXME: rough way
		binarylibs.append(i.split()[1].split("/")[len(i.split()[1].split("/"))-1])
        return binarylibs
    else:
	return binarylibs

def getEbuildDbPath(atom):
    return portage.db['/']['vartree'].getebuildpath(atom)

def getEbuildTreePath(atom):
    if atom.startswith("="):
	atom = atom[1:]
    rc = portage.portdb.findname(atom)
    if rc != "":
	return rc
    else:
	return None

def getPackageDownloadSize(atom):
    if atom.startswith("="):
	atom = atom[1:]

    ebuild = getEbuildTreePath(atom)
    if (ebuild is not None):
	import portage_manifest
	dirname = os.path.dirname(ebuild)
	manifest = portage_manifest.Manifest(dirname, portage.settings["DISTDIR"])
	fetchlist = portage.portdb.getfetchlist(atom, portage.settings, all=True)[1]
	summary = [0,0]
	try:
	    summary[0] = manifest.getDistfilesSize(fetchlist)
	    counter = str(summary[0]/1024)
	    filler=len(counter)
	    while (filler > 3):
		filler-=3
		counter=counter[:filler]+","+counter[filler:]
	    summary[0]=counter+" kB"
	except KeyError, e:
	    return "N/A"
	return summary[0]
    else:
	return "N/A"

def getInstalledAtoms(atom):
    rc = portage.db['/']['vartree'].dep_match(str(atom))
    if (rc != []):
        return rc
    else:
        return None

# YOU MUST PROVIDE A COMPLETE ATOM with a pkgcat !
def unmerge(atom):
    if isjustname(atom) or (not isvalidatom(atom)) or (atom.find("/") == -1):
	return 1
    else:
	pkgcat = atom.split("/")[0]
	pkgnamever = atom.split("/")[1]
	portage.settings.unlock()
	rc = portage.unmerge(pkgcat, pkgnamever, ETP_ROOT_DIR, portage.settings, 1)
	portage.settings.lock()
	return rc

# TO THIS FUNCTION:
# must be provided a valid and complete atom
def extractPkgNameVer(atom):
    package = dep_getcpv(atom)
    package = atom.split("/")[len(atom.split("/"))-1]
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
    return pkgname,pkgver

def emerge(atom, options, outfile = None, redirect = "&>", simulate = False):
    if (simulate):
	return 0,"" # simulation enabled
    if (outfile is None) and (redirect == "&>"):
	outfile = etpConst['packagestmpdir']+"/.emerge-"+str(getRandomNumber())
    elif (redirect is None):
	outfile = ""
	redirect = ""
    if os.path.isfile(outfile):
	try:
	    os.remove(outfile)
	except:
	    spawnCommand("rm -rf "+outfile)

    # Get specified USE flags
    try:
	useflags = " USE='"+os.environ['USE']+"' "
    except:
	useflags = " "

    # Get specified MAKEOPTS
    try:
	makeopts = " MAKEOPTS='"+os.environ['MAKEOPTS']+"' "
    except:
	makeopts = " "

    # Get specified CFLAGS
    try:
	cflags = " CFLAGS='"+os.environ['CFLAGS']+"' "
    except:
	cflags = " "

    # Get specified LDFLAGS
    try:
	ldflags = " LDFLAGS='"+os.environ['LDFLAGS']+"' "
    except:
	ldflags = " "

    # elog configuration
    elogopts = dbPORTAGE_ELOG_OPTS+" "
    # clean elog shit
    elogfile = atom.split("=")[len(atom.split("="))-1]
    elogfile = elogfile.split(">")[len(atom.split(">"))-1]
    elogfile = elogfile.split("<")[len(atom.split("<"))-1]
    elogfile = elogfile.split("/")[len(atom.split("/"))-1]
    elogfile = etpConst['logdir']+"/elog/*"+elogfile+"*"
    os.system("rm -rf "+elogfile)
    
    distccopts = ""
    if (getDistCCStatus()):
	# FIXME: add MAKEOPTS too
	distccopts += 'FEATURES="distcc" '
	distccjobs = str(len(getDistCCHosts())+3)
	distccopts += 'MAKEOPTS="-j'+distccjobs+'" '
	#distccopts += 'MAKEOPTS="-j4" '
    rc = spawnCommand(distccopts+cflags+ldflags+useflags+makeopts+elogopts+cdbRunEmerge+" "+options+" "+atom, redirect+outfile)
    return rc, outfile

def parseElogFile(atom):
    if atom.startswith("="):
	atom = atom[1:]
    if atom.startswith(">"):
	atom = atom[1:]
    if atom.startswith("<"):
	atom = atom[1:]
    if (atom.find("/") != -1):
	pkgcat = atom.split("/")[0]
	pkgnamever = atom.split("/")[1]+"*.log"
    else:
	pkgcat = "*"
	pkgnamever = atom+"*.log"
    elogfile = pkgcat+":"+pkgnamever
    reallogfile = commands.getoutput("find "+etpConst['logdir']+"/elog/ -name '"+elogfile+"'").split("\n")[0].strip()
    if os.path.isfile(reallogfile):
	# FIXME: improve this part
	logline = False
	logoutput = []
	f = open(reallogfile,"r")
	reallog = f.readlines()
	f.close()
	for line in reallog:
	    if line.startswith("INFO: postinst") or line.startswith("LOG: postinst"):
		logline = True
		continue
		# disable all the others
	    elif line.startswith("INFO:") or line.startswith("LOG:"):
		logline = False
		continue
	    if (logline) and (line.strip() != ""):
		# trap !
		logoutput.append(line.strip())
	return logoutput
    else:
	return []

def compareLibraryLists(pkgBinaryFiles,newPkgBinaryFiles):
    brokenBinariesList = []
    # check if there has been a API breakage
    if pkgBinaryFiles != newPkgBinaryFiles:
	_pkgBinaryFiles = []
	_newPkgBinaryFiles = []
	# extract only similar packages
	for pkg in pkgBinaryFiles:
	    _pkg = pkg.split(".so")[0]
	    for newpkg in newPkgBinaryFiles:
		_newpkg = newpkg.split(".so")[0]
		if (_newpkg == _pkg):
		    _pkgBinaryFiles.append(pkg)
		    _newPkgBinaryFiles.append(newpkg)
	pkgBinaryFiles = _pkgBinaryFiles
	newPkgBinaryFiles = _newPkgBinaryFiles
	
	# check for version bumps
	for pkg in pkgBinaryFiles:
	    _pkgver = pkg.split(".so.")[len(pkg.split(".so."))-1]
	    _pkg = pkg.split(".so.")[0]
	    for newpkg in newPkgBinaryFiles:
		_newpkgver = newpkg.split(".so.")[len(newpkg.split(".so."))-1]
		_newpkg = newpkg.split(".so.")[0]
		if (_newpkg == _pkg):
		    # check version
		    if (_pkgver != _newpkgver):
			brokenBinariesList.append([ pkg, newpkg ])
    return brokenBinariesList


# create a .tbz2 file in the specified path
def quickpkg(atom,dirpath):
    # getting package info
    pkgname = atom.split("/")[1]
    pkgcat = atom.split("/")[0]
    pkgfile = pkgname+".tbz2"
    dirpath += "/"+pkgname+".tbz2"
    tmpdirpath = etpConst['packagestmpdir']+"/"+pkgname+".tbz2"+"-tmpdir"
    if os.path.isdir(tmpdirpath): spawnCommand("rm -rf "+tmpdirpath)
    os.makedirs(tmpdirpath)
    dbdir = "/var/db/pkg/"+pkgcat+"/"+pkgname+"/"

    # crate file list
    f = open(dbdir+dbCONTENTS,"r")
    pkgcontent = f.readlines()
    f.close()
    _pkgcontent = []
    for line in pkgcontent:
	line = line.strip().split()[1]
	if not ((os.path.isdir(line)) and (os.path.islink(line))):
	    _pkgcontent.append(line)
    pkgcontent = _pkgcontent
    f = open(tmpdirpath+"/"+dbCONTENTS,"w")
    for i in pkgcontent:
	f.write(i+"\n")
    f.flush()
    f.close()

    # package them into a file
    rc = spawnCommand("tar cjf "+dirpath+" -C / --files-from='"+tmpdirpath+"/"+dbCONTENTS+"' --no-recursion", redirect = "&>/dev/null")
    
    # appending xpak informations
    import xpak
    tbz2 = xpak.tbz2(dirpath)
    tbz2.recompose(dbdir)
    
    # Remove tmp file
    os.system("rm -rf "+tmpdirpath)
    
    if os.path.isfile(dirpath):
	return dirpath
    else:
	return False

def unpackTbz2(tbz2File,tmpdir = None):
    import xpak
    if tmpdir is None:
	tmpdir = etpConst['packagestmpdir']+"/"+tbz2File.split("/")[len(tbz2File.split("/"))-1].split(".tbz2")[0]+"/"
    if (not tmpdir.endswith("/")):
	tmpdir += "/"
    tbz2 = xpak.tbz2(tbz2File)
    if os.path.isdir(tmpdir):
	os.system("rm -rf "+tmpdir+"*")
    tbz2.decompose(tmpdir)
    return tmpdir

# NOTE: atom must be a COMPLETE atom, with version!
def isTbz2PackageAvailable(atom, verbose = False):
    # check if the package have been already merged
    atomName = atom.split("/")[len(atom.split("/"))-1]
    tbz2Available = False
    
    uploadPath = etpConst['packagessuploaddir']+"/"+atomName+".tbz2"
    storePath = etpConst['packagesstoredir']+"/"+atomName+".tbz2"
    packagesPath = etpConst['packagesbindir']+"/"+atomName+".tbz2"
    
    if (verbose): print "testing in directory: "+packagesPath
    if os.path.isfile(packagesPath):
        tbz2Available = packagesPath
    if (verbose): print "testing in directory: "+storePath
    if os.path.isfile(storePath):
        tbz2Available = storePath
    if (verbose): print "testing in directory: "+uploadPath
    if os.path.isfile(uploadPath):
        tbz2Available = uploadPath
    if (verbose): print "found here: "+str(tbz2Available)

    return tbz2Available

def checkAtom(atom):
    bestAtom = getBestAtom(atom)
    if bestAtom == "!!conflicts":
	bestAtom = ""
    if (isvalidatom(atom) == 1) or ( bestAtom != ""):
        return True
    return False

def removeSpaceAtTheEnd(string):
    if string.endswith(" "):
        return string[:len(string)-1]
    else:
	return string

def md5sum(filepath):
    import md5
    m = md5.new()
    readfile = file(filepath)
    block = readfile.read(1024)
    while block:
        m.update(block)
	block = readfile.read(1024)
    return m.hexdigest()

# Tool to run commands
def spawnCommand(command, redirect = None):
    if redirect is not None:
        command += " "+redirect
    rc = os.system(command)
    return rc

def getPackageDependencyList(atom):
    pkgSplittedDeps = []
    tmp = portage.portdb.aux_get(atom, ["DEPEND"])[0].split()
    for i in tmp:
	pkgSplittedDeps.append(i)
    tmp = portage.portdb.aux_get(atom, ["RDEPEND"])[0].split()
    for i in tmp:
	pkgSplittedDeps.append(i)
    tmp = portage.portdb.aux_get(atom, ["PDEPEND"])[0].split()
    for i in tmp:
	pkgSplittedDeps.append(i)
    return pkgSplittedDeps

# parser of the gentoo db "NEEDED" file
# this file is contained in the .tbz2->.xpak file
def getPackageRuntimeDependencies(NEEDED):

    if not os.path.isfile(NEEDED):
	return [],[] # both empty

    f = open(NEEDED,"r")
    includedBins = f.readlines()
    f.close()

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
    return runtimeNeededPackages, runtimeNeededPackagesXT

def getUSEFlags():
    return getPortageEnv('USE')

# you must provide a complete atom
def getPackageIUSE(atom):
    return getPackageVar(atom,"IUSE")

def getPackageVar(atom,var):
    if atom.startswith("="):
	atom = atom[1:]
    # can't check - return error
    if (atom.find("/") == -1):
	return 1
    return portage.portdb.aux_get(atom,[var])[0]

def synthetizeRoughDependencies(roughDependencies, useflags = None):
    if useflags is None:
        useflags = getUSEFlags()
    # returns dependencies, conflicts

    useMatch = False
    openParenthesis = 0
    openOr = False
    useFlagQuestion = False
    dependencies = ""
    conflicts = ""
    for atom in roughDependencies:

	if atom.endswith("?"):
	    # we need to see if that useflag is enabled
	    useFlag = atom.split("?")[0]
	    useFlagQuestion = True
	    for i in useflags.split():
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
		# remove last "_or_" from dependencies
		openOr = False
		if dependencies.endswith(dbOR):
		    dependencies = dependencies[:len(dependencies)-len(dbOR)]
		    dependencies += " "
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
		dependencies += atom
		if (openOr):
		    dependencies += dbOR
                else:
		    dependencies += " "

        if atom.startswith("!") and (not atom.endswith("?")):
	    if ((useFlagQuestion) and (useMatch)) or ((not useFlagQuestion) and (not useMatch)):
		conflicts += atom
		if (openOr):
		    conflicts += dbOR
                else:
		    conflicts += " "
		

    # format properly
    tmpConflicts = list(set(conflicts.split()))
    conflicts = ''
    for i in tmpConflicts:
	i = i[1:] # remove "!"
	conflicts += i+" "
    conflicts = removeSpaceAtTheEnd(conflicts)

    tmpDeps = list(set(dependencies.split()))
    dependencies = ''
    for i in tmpDeps:
	dependencies += i+" "
    dependencies = removeSpaceAtTheEnd(dependencies)

    return dependencies, conflicts

# Collect installed packages
def getInstalledPackages():
    import os
    appDbDir = getPortageAppDbPath()
    dbDirs = os.listdir(appDbDir)
    installedAtoms = []
    for pkgsdir in dbDirs:
	pkgdir = os.listdir(appDbDir+pkgsdir)
	for pdir in pkgdir:
	    pkgcat = pkgsdir.split("/")[len(pkgsdir.split("/"))-1]
	    pkgatom = pkgcat+"/"+pdir
	    if pkgatom.find("-MERGING-") == -1:
	        installedAtoms.append(pkgatom)
    return installedAtoms, len(installedAtoms)

def getPortageAppDbPath():
    rc = getPortageEnv("ROOT")+portage_const.VDB_PATH
    if (not rc.endswith("/")):
	return rc+"/"
    return rc

# ------ BEGIN: activator tools ------

class activatorFTP:

    # ftp://linuxsabayon:asdasd@silk.dreamhost.com/sabayon.org
    # this must be run before calling the other functions
    def __init__(self, ftpuri):
	
	from ftplib import FTP
	
	self.ftpuri = ftpuri
	
	self.ftphost = extractFTPHostFromUri(self.ftpuri)
	
	self.ftpuser = ftpuri.split("ftp://")[len(ftpuri.split("ftp://"))-1].split(":")[0]
	if (self.ftpuser == ""):
	    self.ftpuser = "anonymous@"
	    self.ftppassword = "anonymous"
	else:
	    self.ftppassword = ftpuri.split("@")[:len(ftpuri.split("@"))-1]
	    if len(self.ftppassword) > 1:
		import string
		self.ftppassword = string.join(self.ftppassword,"@")
		self.ftppassword = self.ftppassword.split(":")[len(self.ftppassword.split(":"))-1]
		if (self.ftppassword == ""):
		    self.ftppassword = "anonymous"
	    else:
		self.ftppassword = self.ftppassword[0]
		self.ftppassword = self.ftppassword.split(":")[len(self.ftppassword.split(":"))-1]
		if (self.ftppassword == ""):
		    self.ftppassword = "anonymous"
	
	self.ftpport = ftpuri.split(":")[len(ftpuri.split(":"))-1]
	try:
	    self.ftpport = int(self.ftpport)
	except:
	    self.ftpport = 21
	
	self.ftpdir = ftpuri.split("ftp://")[len(ftpuri.split("ftp://"))-1]
	self.ftpdir = self.ftpdir.split("/")[len(self.ftpdir.split("/"))-1]
	self.ftpdir = self.ftpdir.split(":")[0]
	if self.ftpdir.endswith("/"):
	    self.ftpdir = self.ftpdir[:len(self.ftpdir)-1]

	self.ftpconn = FTP(self.ftphost)
	self.ftpconn.login(self.ftpuser,self.ftppassword)
	# change to our dir
	self.ftpconn.cwd(self.ftpdir)
	self.currentdir = self.ftpdir


    # this can be used in case of exceptions
    def reconnectHost(self):
	self.ftpconn = FTP(self.ftphost)
	self.ftpconn.login(self.ftpuser,self.ftppassword)
	self.ftpconn.cwd(self.currentdir)

    def getFTPHost(self):
	return self.ftphost

    def getFTPPort(self):
	return self.ftpport

    def getFTPDir(self):
	return self.ftpdir

    def getCWD(self):
	return self.ftpconn.pwd()

    def setCWD(self,dir):
	self.ftpconn.cwd(dir)
	self.currentdir = dir

    def getFileMtime(self,path):
	rc = self.ftpconn.sendcmd("mdtm "+path)
	return rc.split()[len(rc.split())-1]

    def spawnFTPCommand(self,cmd):
	rc = self.ftpconn.sendcmd(cmd)
	return rc

    # list files and directory of a FTP
    # @returns a list
    def listFTPdir(self):
	# directory is: self.ftpdir
	try:
	    rc = self.ftpconn.nlst()
	    _rc = []
	    for i in rc:
		_rc.append(i.split("/")[len(i.split("/"))-1])
	    rc = _rc
	except:
	    return []
	return rc

    # list if the file is available
    # @returns True or False
    def isFileAvailable(self,filename):
	# directory is: self.ftpdir
	try:
	    rc = self.ftpconn.nlst()
	    _rc = []
	    for i in rc:
		_rc.append(i.split("/")[len(i.split("/"))-1])
	    rc = _rc
	    for i in rc:
		if i == filename:
		    return True
	    return False
	except:
	    return False

    def deleteFile(self,file):
	try:
	    rc = self.ftpconn.delete(file)
	    if rc.startswith("250"):
		return True
	    else:
		return False
	except:
	    return False

    def uploadFile(self,file,ascii = False):
	for i in range(10): # ten tries
	    f = open(file)
	    filename = file.split("/")[len(file.split("/"))-1]
	    try:
		if (ascii):
		    rc = self.ftpconn.storlines("STOR "+filename+".tmp",f)
		else:
		    rc = self.ftpconn.storbinary("STOR "+filename+".tmp",f)
		# now we can rename the file with its original name
		self.renameFile(filename+".tmp",filename)
	        return rc
	    except socket.error: # connection reset by peer
		print_info(red("Upload issue, retrying..."))
		self.reconnectHost() # reconnect
		self.deleteFile(filename)
		self.deleteFile(filename+".tmp")
		f.close()
		continue

    def downloadFile(self,filepath,downloaddir,ascii = False):
	file = filepath.split("/")[len(filepath.split("/"))-1]
	if (not ascii):
	    f = open(downloaddir+"/"+file,"wb")
	    rc = self.ftpconn.retrbinary('RETR '+file,f.write)
	else:
	    f = open(downloaddir+"/"+file,"w")
	    rc = self.ftpconn.retrlines('RETR '+file,f.write)
	f.flush()
	f.close()
	return rc

    # also used to move files
    # FIXME: beautify !
    def renameFile(self,fromfile,tofile):
	self.ftpconn.rename(fromfile,tofile)

    # not supported by dreamhost.com
    def getFileSize(self,file):
	return self.ftpconn.size(file)
    
    def getFileSizeCompat(self,file):
	list = getRoughList()
	for item in list:
	    if item.find(file) != -1:
		# extact the size
		return item.split()[4]
	return ""

    def bufferizer(self,buf):
	self.FTPbuffer.append(buf)

    def getRoughList(self):
	self.FTPbuffer = []
	self.ftpconn.dir(self.bufferizer)
	return self.FTPbuffer

    def closeFTPConnection(self):
	self.ftpconn.quit()

# ------ END: activator tools ------

def extractFTPHostFromUri(uri):
    ftphost = uri.split("ftp://")[len(uri.split("ftp://"))-1]
    ftphost = ftphost.split("@")[len(ftphost.split("@"))-1]
    ftphost = ftphost.split("/")[0]
    ftphost = ftphost.split(":")[0]
    return ftphost

# This function check the Entropy online database status
def getEtpRemoteDatabaseStatus():

    uriDbInfo = []
    for uri in etpConst['activatoruploaduris']:
	ftp = activatorFTP(uri)
	ftp.setCWD(etpConst['etpurirelativepath'])
	rc = ftp.isFileAvailable(translateArchFromUname(ETP_ARCH_CONST)+etpConst['etpdatabasefile'])
	if (rc):
	    # then get the file revision, if exists
	    rc = ftp.isFileAvailable(translateArchFromUname(ETP_ARCH_CONST)+etpConst['etpdatabasefile']+".revision")
	    if (rc):
		# get the revision number
		ftp.downloadFile(translateArchFromUname(ETP_ARCH_CONST) + etpConst['etpdatabasefile'] + ".revision",etpConst['packagestmpdir'],True)
		f = open( etpConst['packagestmpdir'] + "/" + translateArchFromUname(ETP_ARCH_CONST) + etpConst['etpdatabasefile'] + ".revision","r")
		revision = int(f.readline().strip())
		f.close()
		os.system("rm -f "+etpConst['packagestmpdir']+translateArchFromUname(ETP_ARCH_CONST)+etpConst['etpdatabasefile']+".revision")
	    else:
		revision = 0
	else:
	    # then set mtime to 0 and quit
	    revision = 0
	info = [uri+"/"+etpConst['etpurirelativepath']+translateArchFromUname(ETP_ARCH_CONST)+etpConst['etpdatabasefile'],revision]
	uriDbInfo.append(info)
	ftp.closeFTPConnection()

    return uriDbInfo

def syncRemoteDatabases():

    print_info(green(" * ")+red("Checking the status of the remote Entropy Database Repository"))
    remoteDbsStatus = getEtpRemoteDatabaseStatus()
    print_info(green(" * ")+red("Remote Entropy Database Repository Status:"))
    for dbstat in remoteDbsStatus:
	print_info(green("\t Host:\t")+bold(extractFTPHostFromUri(dbstat[0])))
	print_info(red("\t  * Database revision: ")+blue(str(dbstat[1])))

    # check if the local DB exists
    etpDbLocalPath = etpConst['etpurirelativepath']
    etpDbLocalFile = etpConst['etpdatabasedir']
    if etpDbLocalFile.endswith("/"):
	etpDbLocalFile = etpDbLocalFile[:len(etpDbLocalFile)-1]
    etpDbLocalFile += etpConst['etpdatabasefile']
    if os.path.isfile(etpDbLocalFile) and os.path.isfile(etpDbLocalFile+".revision"):
	# file exist, get revision
	f = open(etpDbLocalFile+".revision","r")
	etpDbLocalRevision = int(f.readline().strip())
	f.close()
    else:
	etpDbLocalRevision = 0
    
    
    generateAndUpload = False
    downloadLatest = []
    uploadLatest = False
    uploadList = []
    
    # if the local DB does not exist, get the latest
    if (etpDbLocalRevision == 0):
	# seek mirrors
	latestRemoteDb = []
	etpDbRemotePaths = []
	for dbstat in remoteDbsStatus:
	    if ( dbstat[1] != 0 ):
		# collect
		etpDbRemotePaths.append(dbstat)
	if etpDbRemotePaths == []:
	    #print "DEBUG: generate and upload"
	    # (to all!)
	    generateAndUpload = True
	else:
	    #print "DEBUG: get the latest ?"
	    revisions = []
	    for dbstat in etpDbRemotePaths:
		revisions.append(dbstat[1])
	    latestrevision = alphaSorter(revisions)[len(revisions)-1]
	    for dbstat in etpDbRemotePaths:
		if dbstat[1] == latestrevision:
		    # found !
		    downloadLatest.append(dbstat)
		    break
	    # Now check if we need to upload back the files to the other mirrors
	    #print "DEBUG: check the others, if they're also updated, quit"
	    for dbstat in remoteDbsStatus:
		if (downloadLatest[1] != dbstat[1]):
		    uploadLatest = True
		    uploadList.append(dbstat)
    else:
	# while if it exists
	# seek mirrors
	latestRemoteDb = []
	etpDbRemotePaths = []
	for dbstat in remoteDbsStatus:
	    if ( dbstat[1] != 0 ):
		# collect
		etpDbRemotePaths.append(dbstat)
	if etpDbRemotePaths == []:
	    #print "DEBUG: upload our version"
	    uploadLatest = True
	    # upload to all !
	    uploadList = remoteDbsStatus
	else:
	    #print "DEBUG: get the latest?"
	    revisions = []
	    for dbstat in etpDbRemotePaths:
		revisions.append(dbstat[1])
	    latestrevision = int(alphaSorter(str(revisions))[len(str(revisions))-1])
	    for dbstat in etpDbRemotePaths:
		if dbstat[1] == latestrevision:
		    # found !
		    latestRemoteDb = dbstat
		    break
	    
	    # now compare downloadLatest with our local file mtime
	    if (etpDbLocalRevision < latestRemoteDb[1]):
		# download !
		#print "appending a download"
		downloadLatest = latestRemoteDb
	    elif (etpDbLocalRevision > latestRemoteDb[1]):
		# upload to all !
		#print str(etpDbLocalRevision)
		#print str(latestRemoteDb[1])
		#print "appending the upload to all"
		uploadLatest = True
		uploadList = remoteDbsStatus

	    # If the uploadList is not filled, this means that the other mirror might need an update
	    if (not uploadLatest):
	        for dbstat in remoteDbsStatus:
		    if (latestRemoteDb[1] != dbstat[1]):
		        uploadLatest = True
		        uploadList.append(dbstat)
    
    if (downloadLatest == []) and (not uploadLatest) and (not generateAndUpload):
	print_info(green(" * ")+red("Online database does not need to be updated."))
    
    # now run the selected task!
    if (downloadLatest != []):
	# match the proper URI
	for uri in etpConst['activatoruploaduris']:
	    if downloadLatest[0].startswith(uri):
		downloadLatest[0] = uri
	downloadDatabase(downloadLatest[0],etpDbLocalFile)
	
    if (uploadLatest):
	print_info(green(" * ")+red("Starting to update the needed mirrors ..."))
	# FIXME: UploadList is wrong?!
	_uploadList = []
	for uri in etpConst['activatoruploaduris']:
	    for list in uploadList:
		if list[0].startswith(uri):
		    list[0] = uri
		    break
	    _uploadList.append(list[0])
	
	uploadDatabase(_uploadList,etpDbLocalFile)
	print_info(green(" * ")+red("All the mirrors have been updated."))
	
    if (generateAndUpload):
	print_info(green(" * ")+red("Compressing ETP Repository to ")+bold(etpDbLocalFile),back = True)
	rc = compressTarBz2(etpDbLocalFile,etpConst['etpdatabasedir'])
	if (rc):
	    print_error(red(" * Cannot compress "+etpDbLocalFile))
	    print_error(red(" *** Cannot continue"))
	    sys.exit(120)
	print_info(green(" * ")+bold(etpDbLocalFile)+red(" has been succesfully created"))
	# create revision file
	f = open(etpDbLocalFile+".revision","w")
	f.write("1\n")
	f.flush()
	f.close()
	# digesting
	hexdigest = digestFile(etpDbLocalFile)
	f = open(etpDbLocalFile+".md5","w")
	filename = etpDbLocalFile.split("/")[len(etpDbLocalFile.split("/"))-1]
	f.write(hexdigest+"  "+filename+"\n")
	f.flush()
	f.close()
	print_info(green(" * ")+red("Starting to update all the mirrors ..."))
	uploadDatabase(etpConst['activatoruploaduris'],etpDbLocalFile)
	print_info(green(" * ")+red("All the mirrors have been updated, it seems."))


def uploadDatabase(uris,dbfile):
    for uri in uris:
	lockDatabases(True,[uri])
	downloadLockDatabases(True,[uri])
	print_info(green(" * ")+red("Uploading database to ")+bold(extractFTPHostFromUri(uri))+red(" ..."))
	print_info(green(" * ")+red("Connecting to ")+bold(extractFTPHostFromUri(uri))+red(" ..."), back = True)
	ftp = activatorFTP(uri)
	print_info(green(" * ")+red("Changing directory to ")+bold(etpConst['etpurirelativepath'])+red(" ..."), back = True)
	ftp.setCWD(etpConst['etpurirelativepath'])
	print_info(green(" * ")+red("Uploading file ")+bold(dbfile)+red(" ..."), back = True)
	# uploading database file
	rc = ftp.uploadFile(dbfile)
	if (rc.startswith("226")):
	    print_info(green(" * ")+red("Upload of ")+bold(dbfile)+red(" completed."))
	else:
	    print_warning(yellow(" * ")+red("Cannot properly upload to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
	print_info(green(" * ")+red("Uploading file ")+bold(dbfile+".revision")+red(" ..."), back = True)
	# uploading revision file
	rc = ftp.uploadFile(dbfile+".revision",True)
	if (rc.startswith("226")):
	    print_info(green(" * ")+red("Upload of ")+bold(dbfile+".revision")+red(" completed."))
	else:
	    print_warning(yellow(" * ")+red("Cannot properly upload to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
	# upload digest
	print_info(green(" * ")+red("Uploading file ")+bold(dbfile+".md5")+red(" ..."), back = True)
	rc = ftp.uploadFile(dbfile+".md5",True)
	if (rc.startswith("226")):
	    print_info(green(" * ")+red("Upload of ")+bold(dbfile+".md5")+red(" completed. Disconnecting."))
	else:
	    print_warning(yellow(" * ")+red("Cannot properly upload to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
	downloadLockDatabases(False,[uri])
	lockDatabases(False,[uri])

def downloadDatabase(uri,dbfile):
    print_info(green(" * ")+red("Downloading database from ")+bold(extractFTPHostFromUri(uri))+red(" ..."))
    print_info(green(" * ")+red("Connecting to ")+bold(extractFTPHostFromUri(uri))+red(" ..."), back = True)
    ftp = activatorFTP(uri)
    print_info(green(" * ")+red("Changing directory to ")+bold(etpConst['etpurirelativepath'])+red(" ..."), back = True)
    ftp.setCWD(etpConst['etpurirelativepath'])
    print_info(green(" * ")+red("Downloading file to ")+bold(dbfile)+red(" ..."), back = True)
    # downloading database file
    rc = ftp.downloadFile(dbfile.split("/")[len(dbfile.split("/"))-1],os.path.dirname(dbfile))
    if (rc.startswith("226")):
	print_info(green(" * ")+red("Download of ")+bold(dbfile)+red(" completed."))
    else:
	print_warning(yellow(" * ")+red("Cannot properly download to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
    print_info(green(" * ")+red("Downloading file to ")+bold(dbfile+".revision")+red(" ..."), back = True)
    # downloading revision file
    rc = ftp.downloadFile(dbfile.split("/")[len(dbfile.split("/"))-1]+".revision",os.path.dirname(dbfile),True)
    if (rc.startswith("226")):
	print_info(green(" * ")+red("Download of ")+bold(dbfile+".revision")+red(" completed."))
    else:
	print_warning(yellow(" * ")+red("Cannot properly download to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
    # downlading digest
    print_info(green(" * ")+red("Downloading file to ")+bold(dbfile+".md5")+red(" ..."), back = True)
    rc = ftp.downloadFile(dbfile.split("/")[len(dbfile.split("/"))-1]+".md5",os.path.dirname(dbfile),True)
    if (rc.startswith("226")):
	print_info(green(" * ")+red("Download of ")+bold(dbfile+".md5")+red(" completed. Disconnecting."))
    else:
	print_warning(yellow(" * ")+red("Cannot properly download to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
    # removing old tree
    print_info(green(" * ")+red("Uncompressing downloaded database ..."),back = True)
    os.system("rm -rf "+etpConst['etpdatabasedir']+"/*")
    rc = uncompressTarBz2(dbfile,"/")
    if (rc):
	print_error(red(" * Cannot uncompress "+dbfile))
	print_error(red(" *** Cannot continue"))
	sys.exit(120)
    else:
        print_info(green(" * ")+red("Downloaded database succesfully uncompressed."))


# Reports in a list form the lock status of the mirrors
# @ [ uri , True/False, True/False ] --> True = locked, False = unlocked
# @ the second parameter is referred to upload locks, while the second to download ones
def getMirrorsLock():
    # parse etpConst['activatoruploaduris']
    dbstatus = []
    for uri in etpConst['activatoruploaduris']:
	data = [ uri, False , False ]
	ftp = activatorFTP(uri)
	ftp.setCWD(etpConst['etpurirelativepath'])
	if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
	    # Upload is locked
	    data[1] = True
	if (ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
	    # Upload is locked
	    data[2] = True
	ftp.closeFTPConnection()
	dbstatus.append(data)
    return dbstatus


# tar.bz2 compress function...
def compressTarBz2(storepath,pathtocompress):
    cmd = "tar cjf "+storepath+" -C "+pathtocompress
    rc = os.system(cmd+" &> /dev/null")
    return rc

# tar.bz2 uncompress function...
def uncompressTarBz2(filepath, extractPath = None):
    if extractPath is None:
	extractPath = os.path.dirname(filepath)
    cmd = "tar xjf "+filepath+" -C "+extractPath
    rc = os.system(cmd+" &> /dev/null")
    return rc

# FIXME: improve support by reading a line at a time
def digestFile(filepath):
    import md5
    df = open(filepath,"r")
    content = df.readlines()
    df.close()
    digest = md5.new()
    for line in content:
	digest.update(line)
    return digest.hexdigest()

def bytesIntoHuman(bytes):
    bytes = str(bytes)
    kbytes = str(int(bytes)/1024)
    if len(kbytes) > 3:
	kbytes = str(int(kbytes)/1024)
	kbytes += "MB"
    else:
	kbytes += "kB"
    return kbytes

# hide password from full ftp URI
def hideFTPpassword(uri):
    ftppassword = uri.split("@")[:len(uri.split("@"))-1]
    if len(ftppassword) > 1:
	import string
	ftppassword = string.join(ftppassword,"@")
	ftppassword = ftppassword.split(":")[len(ftppassword.split(":"))-1]
	if (ftppassword == ""):
	    return uri
    else:
	ftppassword = ftppassword[0]
	ftppassword = ftppassword.split(":")[len(ftppassword.split(":"))-1]
	if (ftppassword == ""):
	    return uri

    newuri = re.subn(ftppassword,"xxxxxxxx",uri)[0]
    return newuri

def lockDatabases(lock = True, mirrorList = []):
    outstat = False
    if (mirrorList == []):
	mirrorList = etpConst['activatoruploaduris']
    for uri in mirrorList:
	if (lock):
	    print_info(yellow(" * ")+red("Locking ")+bold(extractFTPHostFromUri(uri))+red(" mirror..."),back = True)
	else:
	    print_info(yellow(" * ")+red("Unlocking ")+bold(extractFTPHostFromUri(uri))+red(" mirror..."),back = True)
	ftp = activatorFTP(uri)
	# upload the lock file to database/%ARCH% directory
	ftp.setCWD(etpConst['etpurirelativepath'])
	# check if the lock is already there
	if (lock):
	    if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
	        print_info(green(" * ")+red("Mirror database at ")+bold(extractFTPHostFromUri(uri))+red(" already locked."))
	        ftp.closeFTPConnection()
	        continue
	else:
	    if (not ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
	        print_info(green(" * ")+red("Mirror database at ")+bold(extractFTPHostFromUri(uri))+red(" already unlocked."))
	        ftp.closeFTPConnection()
	        continue
	if (lock):
	    f = open(etpConst['packagestmpdir']+"/"+etpConst['etpdatabaselockfile'],"w")
	    f.write("database locked\n")
	    f.flush()
	    f.close()
	    rc = ftp.uploadFile(etpConst['packagestmpdir']+"/"+etpConst['etpdatabaselockfile'],ascii= True)
	    if (rc.startswith("226")):
	        print_info(green(" * ")+red("Succesfully locked ")+bold(extractFTPHostFromUri(uri))+red(" mirror."))
	    else:
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while locking ")+bold(extractFTPHostFromUri(uri))+red(" mirror. Please have a look."))
	else:
	    rc = ftp.deleteFile(etpConst['etpdatabaselockfile'])
	    if (rc):
		print_info(green(" * ")+red("Succesfully unlocked ")+bold(extractFTPHostFromUri(uri))+red(" mirror."))
	    else:
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while unlocking ")+bold(extractFTPHostFromUri(uri))+red(" mirror. Please have a look."))
	ftp.closeFTPConnection()
    return outstat

def downloadLockDatabases(lock = True, mirrorList = []):
    outstat = False
    if (mirrorList == []):
	mirrorList = etpConst['activatoruploaduris']
    for uri in mirrorList:
	if (lock):
	    print_info(yellow(" * ")+red("Locking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror..."),back = True)
	else:
	    print_info(yellow(" * ")+red("Unlocking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror..."),back = True)
	ftp = activatorFTP(uri)
	# upload the lock file to database/%ARCH% directory
	ftp.setCWD(etpConst['etpurirelativepath'])
	# check if the lock is already there
	if (lock):
	    if (ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
	        print_info(green(" * ")+red("Download mirror at ")+bold(extractFTPHostFromUri(uri))+red(" already locked."))
	        ftp.closeFTPConnection()
	        continue
	else:
	    if (not ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
	        print_info(green(" * ")+red("Download mirror at ")+bold(extractFTPHostFromUri(uri))+red(" already unlocked."))
	        ftp.closeFTPConnection()
	        continue
	if (lock):
	    f = open(etpConst['packagestmpdir']+"/"+etpConst['etpdatabasedownloadlockfile'],"w")
	    f.write("database locked\n")
	    f.flush()
	    f.close()
	    rc = ftp.uploadFile(etpConst['packagestmpdir']+"/"+etpConst['etpdatabasedownloadlockfile'],ascii= True)
	    if (rc.startswith("226")):
	        print_info(green(" * ")+red("Succesfully locked ")+bold(extractFTPHostFromUri(uri))+red(" download mirror."))
	    else:
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while locking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror. Please have a look."))
	else:
	    rc = ftp.deleteFile(etpConst['etpdatabasedownloadlockfile'])
	    if (rc):
		print_info(green(" * ")+red("Succesfully unlocked ")+bold(extractFTPHostFromUri(uri))+red(" download mirror."))
	    else:
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while unlocking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror. Please have a look."))
	ftp.closeFTPConnection()
    return outstat

# parse a dumped .etp file and returns etpData
def parseEtpDump(file):
    myEtpData = tmpEtpData.copy()
    # reset
    for i in myEtpData:
	myEtpData[i] = ""
    f = open(file,"r")
    myDump = f.readlines()
    f.close()
    for line in myDump:
	line = line.strip()
	var = line.split(":")[0]
	myEtpData[var] = line.split(var+": ")[1:][0]

    return myEtpData



def packageSearch(keyword):

    SearchDirs = []
    # search in etpConst['portagetreedir']
    # and in overlays after etpConst['overlays']
    # fill the list
    portageRootDir = etpConst['portagetreedir']
    if not portageRootDir.endswith("/"):
	portageRootDir = portageRootDir+"/"
    ScanningDirectories = []
    ScanningDirectories.append(portageRootDir)
    for dir in etpConst['overlays'].split():
	if (not dir.endswith("/")):
	    dir = dir+"/"
	if os.path.isdir(dir):
	    ScanningDirectories.append(dir)

    for directoryTree in ScanningDirectories:
	treeList = os.listdir(directoryTree)
	_treeList = []
	# filter unwanted dirs
	for dir in treeList:
	    if (dir.find("-") != -1) and os.path.isdir(directoryTree+dir):
		_treeList.append(directoryTree+dir)
	treeList = _treeList

	for dir in treeList:
	    subdirs = os.listdir(dir)
	    for sub in subdirs:
		if (not sub.startswith(".")) and (sub.find(keyword) != -1):
		    if os.path.isdir(dir+"/"+sub):
			reldir = re.subn(directoryTree,"", dir+"/"+sub)[0]
			SearchDirs.append(reldir)
    
    # filter dupies
    SearchDirs = list(set(SearchDirs))
    return SearchDirs

# Distcc check status function
def setDistCC(status = True):
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    if (status):
	distccSwitch = "enabled"
    else:
	distccSwitch = "disabled"
    newenzymeconf = []
    for line in enzymeconf:
	if line.startswith("distcc-status|"):
	    line = "distcc-status|"+distccSwitch+"\n"
	newenzymeconf.append(line)
    f = open(etpConst['enzymeconf'],"w")
    f.writelines(newenzymeconf)
    f.flush()
    f.close()

def getDistCCHosts():
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    hostslist = []
    for line in enzymeconf:
	if line.startswith("distcc-hosts|") and (len(line.split("|")) == 2):
	    line = line.strip().split("|")[1].split()
	    for host in line:
		hostslist.append(host)
	    return hostslist
    return []

# you must provide a list
def addDistCCHosts(hosts):
    
    # FIXME: add host validation
    hostslist = getDistCCHosts()
    for host in hosts:
	hostslist.append(host)

    # filter dupies
    hostslist = list(set(hostslist))
   
    # write back to file
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    newenzymeconf = []
    distcchostslinefound = False
    for line in enzymeconf:
	if line.startswith("distcc-hosts|"):
	    distcchostslinefound = True
    if (distcchostslinefound):
	for line in enzymeconf:
	    if line.startswith("distcc-hosts|"):
		hostsline = string.join(hostslist," ")
		line = "distcc-hosts|"+hostsline+"\n"
	    newenzymeconf.append(line)
    else:
	newenzymeconf = enzymeconf
	hostsline = string.join(hostslist," ")
	newenzymeconf.append("distcc-hosts|"+hostsline+"\n")

    # write distcc config file too
    f = open(etpConst['distccconf'],"w")
    f.write(hostsline+"\n")
    f.flush()
    f.close()

    f = open(etpConst['enzymeconf'],"w")
    f.writelines(newenzymeconf)
    f.flush()
    f.close()

# you must provide a list
def removeDistCCHosts(hosts):
    
    # FIXME: add host validation
    hostslist = getDistCCHosts()
    cleanedhosts = []
    for host in hostslist:
	rmfound = False
	for rmhost in hosts:
	    if (rmhost == host):
		# remove
		rmfound = True
	if (not rmfound):
	    cleanedhosts.append(host)


    # filter dupies
    cleanedhosts = list(set(cleanedhosts))
   
    # write back to file
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    newenzymeconf = []
    distcchostslinefound = False
    for line in enzymeconf:
	if line.startswith("distcc-hosts|"):
	    distcchostslinefound = True
    if (distcchostslinefound):
	for line in enzymeconf:
	    if line.startswith("distcc-hosts|"):
		hostsline = string.join(cleanedhosts," ")
		line = "distcc-hosts|"+hostsline+"\n"
	    newenzymeconf.append(line)
    else:
	newenzymeconf = enzymeconf
	hostsline = string.join(cleanedhosts," ")
	newenzymeconf.append("distcc-hosts|"+hostsline+"\n")

    # write distcc config file too
    f = open(etpConst['distccconf'],"w")
    f.write(hostsline+"\n")
    f.flush()
    f.close()

    f = open(etpConst['enzymeconf'],"w")
    f.writelines(newenzymeconf)
    f.flush()
    f.close()

def getDistCCStatus():
    return etpConst['distcc-status']

def isIPAvailable(ip):
    rc = os.system("ping -c 1 "+ip+" &> /dev/null")
    if (rc):
	return False
    return True

def getFileUnixMtime(path):
    return os.path.getmtime(path)

def getFileTimeStamp(path):
    from datetime import datetime
    # used in this way for convenience
    unixtime = os.path.getmtime(path)
    humantime = datetime.fromtimestamp(unixtime)
    # format properly
    humantime = str(humantime)
    outputtime = ""
    for chr in humantime:
	if chr != "-" and chr != " " and chr != ":":
	    outputtime += chr
    return outputtime

def convertUnixTimeToMtime(unixtime):
    from datetime import datetime
    humantime = str(datetime.fromtimestamp(unixtime))
    outputtime = ""
    for chr in humantime:
	if chr != "-" and chr != " " and chr != ":":
	    outputtime += chr
    return outputtime

# get a list, returns a sorted list
def alphaSorter(seq):
    def stripter(s, goodchrs):
        badchrs = set(s)
        for c in goodchrs:
            if c in badchrs:
                badchrs.remove(c)
        badchrs = ''.join(badchrs)
        return s.strip(badchrs)
    
    def chr_index(value, sortorder):
        result = []
        for c in stripter(value, order):
            cindex = sortorder.find(c)
            if cindex == -1:
                cindex = len(sortorder)+ord(c)
            result.append(cindex)
        return result
    
    order = ( '0123456789AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz' )
    deco = [(chr_index(a, order), a) for a in seq]
    deco.sort()
    return list(x[1] for x in deco)

# Temporary files cleaner
def cleanup(options):

    toCleanDirs = [ etpConst['packagestmpdir'], etpConst['logdir'] ]
    counter = 0

    for dir in toCleanDirs:
        print_info(red(" * ")+"Cleaning "+yellow(dir)+" directory...", back = True)
	dircontent = os.listdir(dir)
	if dircontent != []:
	    for data in dircontent:
		os.system("rm -rf "+dir+"/"+data)
		counter += 1

    print_info(green(" * ")+"Cleaned: "+str(counter)+" files and directories")

def mountProc():
    # check if it's already mounted
    procfiles = os.listdir("/proc")
    if len(procfiles) > 2:
	return True
    else:
	os.system("mount -t proc proc /proc &> /dev/null")
	return True

def umountProc():
    # check if it's already mounted
    procfiles = os.listdir("/proc")
    if len(procfiles) > 2:
	os.system("umount /proc &> /dev/null")
	os.system("umount /proc &> /dev/null")
	os.system("umount /proc &> /dev/null")
	return True
    else:
	return True

def askquestion(prompt):
    responses, colours = ["Yes", "No"], [green, red]
    print green(prompt),
    try:
	while True:
	    response=raw_input("["+"/".join([colours[i](responses[i]) for i in range(len(responses))])+"] ")
	    for key in responses:
		# An empty response will match the first value in responses.
		if response.upper()==key[:len(response)].upper():
		    return key
		    print "I cannot understand '%s'" % response,
    except (EOFError, KeyboardInterrupt):
	print "Interrupted."
	sys.exit(100)

def print_error(msg):
    print red(">>")+" "+msg

def print_info(msg, back = False):
    writechar("\r                                                                                                           \r")
    if (back):
	writechar("\r"+green(">>")+" "+msg)
	return
    print green(">>")+" "+msg

def print_warning(msg):
    print yellow(">>")+" "+msg

def print_generic(msg): # here we'll wrap any nice formatting
    print msg