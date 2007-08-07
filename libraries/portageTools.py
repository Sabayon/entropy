#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy Portage Interface

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

# EXIT STATUSES: 600-699



############
# Portage initialization
#####################################################################################

'''
def initializePortageTree():
    portage.settings.unlock()
    portage.settings['PORTDIR'] = etpConst['portagetreedir']
    portage.settings['DISTDIR'] = etpConst['distfilesdir']
    portage.settings['PORTDIR_OVERLAY'] = etpConst['overlays']
    portage.settings.lock()
    portage.portdb.__init__(etpConst['portagetreedir'])
'''

# Fix for wrong cache entries - DO NOT REMOVE
import os
from entropyConstants import *
#os.environ['PORTDIR'] = etpConst['portagetreedir']
#os.environ['PORTDIR_OVERLAY'] = etpConst['overlays']
#os.environ['DISTDIR'] = etpConst['distfilesdir']
import portage
import portage_const
from portage_dep import isvalidatom, isspecific, isjustname, dep_getkey, dep_getcpv #FIXME: Use the ones from entropyTools
#from serverConstants import *
#initializePortageTree()

# colours support
from outputTools import *
# misc modules
import string
import re
import sys
import os
import commands
import entropyTools

# Logging initialization
try:
    import logTools
    portageLog = logTools.LogFile(level=etpConst['spmbackendloglevel'],filename = etpConst['spmbackendlogfile'], header = "[Portage]")
    # portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"testFunction: example. ")
except:
    pass

############
# Functions and Classes
#####################################################################################

def getThirdPartyMirrors(mirrorname):
    return portage.thirdpartymirrors[mirrorname]

def getPortageEnv(var):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPortageEnv: called. ")
    try:
	rc = portage.config(clone=portage.settings).environ()[var]
	portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPortageEnv: variable available -> "+str(var))
	return rc
    except KeyError:
	portageLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"getPortageEnv: variable not available -> "+str(var))
	return None

# resolve atoms automagically (best, not current!)
# sys-libs/application --> sys-libs/application-1.2.3-r1
def getBestAtom(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getBestAtom: called -> "+str(atom))
    try:
        rc = portage.portdb.xmatch("bestmatch-visible",str(atom))
	portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getBestAtom: result -> "+str(rc))
        return rc
    except ValueError:
	portageLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"getBestAtom: conflict found. ")
	return "!!conflicts"

# same as above but includes masked ebuilds
def getBestMaskedAtom(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getBestAtom: called. ")
    atoms = portage.portdb.xmatch("match-all",str(atom))
    # find the best
    from portage_versions import best
    rc = best(atoms)
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getBestAtom: result -> "+str(rc))
    return rc

# I need a valid complete atom...
def calculateFullAtomsDependencies(atoms, deep = False, extraopts = ""):

    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"calculateFullAtomsDependencies: called -> "+str(atoms)+" | extra options: "+extraopts)

    # in order... thanks emerge :-)
    deepOpt = ""
    if (deep):
	deepOpt = "-Du"
    deplist = []
    blocklist = []
    
    useflags = " USE='"
    useflags += getUSEFlags()
    useflags += "' "

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
	portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"calculateFullAtomsDependencies: deplist -> "+str(len(deplist))+" | blocklist -> "+str(len(blocklist)))
        return deplist, blocklist
    else:
	portageLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"calculateFullAtomsDependencies: deplist empty. Giving up.")
	rc = entropyTools.spawnCommand(cmd)
	sys.exit(100)


def calculateAtomUSEFlags(atom):
    
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"calculateAtomUSEFlags: called -> "+str(atom))

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
    
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"calculateAtomUSEFlags: USE flags -> "+str(useparm))
    
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
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getAtomCategory: called. ")
    try:
        rc = portage.portdb.xmatch("match-all",str(atom))[0].split("/")[0]
        return rc
    except:
	portageLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"getAtomCategory: error, can't extract category !")
	return None

# This function compare the version number of two atoms
# This function needs a complete atom, pkgcat (not mandatory) - pkgname - pkgver
# if atom1 < atom2 --> returns a NEGATIVE number
# if atom1 > atom2 --> returns a POSITIVE number
# if atom1 == atom2 --> returns 0
def compareAtoms(atom1,atom2):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"compareAtoms: called -> "+atom1+" && "+atom2)
    # filter pkgver
    x, atom1 = extractPkgNameVer(atom1)
    x, atom2 = extractPkgNameVer(atom2)
    from portage_versions import vercmp
    return vercmp(atom1,atom2)

# please always force =pkgcat/pkgname-ver if possible
def getInstalledAtom(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getInstalledAtom: called -> "+str(atom))
    rc = portage.db['/']['vartree'].dep_match(str(atom))
    if (rc != []):
	if (len(rc) == 1):
	    return rc[0]
	else:
            return rc[len(rc)-1]
    else:
        return None

def getPackageSlot(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageSlot: called. ")
    if atom.startswith("="):
	atom = atom[1:]
    rc = portage.db['/']['vartree'].getslot(atom)
    if rc != "":
	portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageSlot: slot found -> "+str(atom)+" -> "+str(rc))
	return rc
    else:
	portageLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"getPackageSlot: slot not found -> "+str(atom))
	return None

# you must provide a complete atom
def collectBinaryFilesForInstalledPackage(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"collectBinaryFilesForInstalledPackage: called. ")
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
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getEbuildDbPath: called -> "+atom)
    return portage.db['/']['vartree'].getebuildpath(atom)

def getEbuildTreePath(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getEbuildTreePath: called -> "+atom)
    if atom.startswith("="):
	atom = atom[1:]
    rc = portage.portdb.findname(atom)
    if rc != "":
	return rc
    else:
	return None

def getPackageDownloadSize(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageDownloadSize: called -> "+atom)
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
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getInstalledAtoms: called -> "+atom)
    rc = portage.db['/']['vartree'].dep_match(str(atom))
    if (rc != []):
        return rc
    else:
        return None



# YOU MUST PROVIDE A COMPLETE ATOM with a pkgcat !
def unmerge(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"umerge: called -> "+atom)
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
    import enzymeTools
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"extractPkgNameVer: called -> "+atom)
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
    import enzymeTools
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"emerge: called -> "+atom+" | options: "+str(options)+" | redirect: "+str(redirect)+" | outfile: "+str(outfile)+" | simulate: "+str(simulate))
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
	    entropyTools.spawnCommand("rm -rf "+outfile)

    # Get specified USE flags
    useflags = " USE='"
    useflags += getUSEFlags()
    useflags += "' "
    # Get specified MAKEOPTS
    makeopts = " MAKEOPTS='"
    makeopts += getMAKEOPTS()
    makeopts += "' "
    # Get specified CFLAGS
    cflags = " CFLAGS='"
    cflags += getCFLAGS()
    cflags += "' "
    # Get specified LDFLAGS
    ldflags = " LDFLAGS='"
    ldflags += getLDFLAGS()
    ldflags += "' "

    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"emerge: USE: "+useflags+" | CFLAGS: "+cflags+" | MAKEOPTS: "+makeopts+" | LDFLAGS: "+ldflags)
    
    # elog configuration
    elogopts = dbPORTAGE_ELOG_OPTS+" "
    # clean elog shit
    elogfile = atom.split("=")[len(atom.split("="))-1]
    elogfile = elogfile.split(">")[len(atom.split(">"))-1]
    elogfile = elogfile.split("<")[len(atom.split("<"))-1]
    elogfile = elogfile.split("/")[len(atom.split("/"))-1]
    elogfile = etpConst['logdir']+"/elog/*"+elogfile+"*"
    entropyTools.spawnCommand("rm -rf "+elogfile)
    
    distccopts = ""
    if (enzymeTools.getDistCCStatus()):
	# FIXME: add MAKEOPTS too
	distccopts += 'FEATURES="distcc" '
	distccjobs = str(len(enzymeTools.getDistCCHosts())+3)
	distccopts += 'MAKEOPTS="-j'+distccjobs+'" '
	#distccopts += 'MAKEOPTS="-j4" '
    rc = entropyTools.spawnCommand(distccopts+cflags+ldflags+useflags+makeopts+elogopts+cdbRunEmerge+" "+options+" "+atom, redirect+outfile)
    return rc, outfile

def parseElogFile(atom):

    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"parseElogFile: called. ")

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
    
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"compareLibraryLists: called. ")
    
    brokenBinariesList = []
    # check if there has been a API breakage
    if pkgBinaryFiles != newPkgBinaryFiles:
	_pkgBinaryFiles = []
	_newPkgBinaryFiles = []
	# extract only similar packages
	for pkg in pkgBinaryFiles:
	    if (pkg.find(".so") == -1):
		continue
	    _pkg = pkg.split(".so")[0]
	    for newpkg in newPkgBinaryFiles:
		if (pkg.find(".so") == -1):
		    continue
		_newpkg = newpkg.split(".so")[0]
		if (_newpkg == _pkg):
		    _pkgBinaryFiles.append(pkg)
		    _newPkgBinaryFiles.append(newpkg)
	pkgBinaryFiles = _pkgBinaryFiles
	newPkgBinaryFiles = _newPkgBinaryFiles
	
	#print "DEBUG:"
	#print pkgBinaryFiles
	#print newPkgBinaryFiles
	
	# check for version bumps
	for pkg in pkgBinaryFiles:
	    _pkgver = pkg.split(".so")[len(pkg.split(".so"))-1]
	    _pkg = pkg.split(".so")[0]
	    for newpkg in newPkgBinaryFiles:
		_newpkgver = newpkg.split(".so")[len(newpkg.split(".so"))-1]
		_newpkg = newpkg.split(".so")[0]
		if (_newpkg == _pkg):
		    # check version
		    if (_pkgver != _newpkgver):
			brokenBinariesList.append([ pkg, newpkg ])
    return brokenBinariesList


# create a .tbz2 file in the specified path
def quickpkg(atom,dirpath):

    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"quickpkg: called -> "+atom+" | dirpath: "+dirpath)

    # getting package info
    pkgname = atom.split("/")[1]
    pkgcat = atom.split("/")[0]
    pkgfile = pkgname+".tbz2"
    dirpath += "/"+pkgname+".tbz2"
    tmpdirpath = etpConst['packagestmpdir']+"/"+pkgname+".tbz2"+"-tmpdir"
    if os.path.isdir(tmpdirpath): entropyTools.spawnCommand("rm -rf "+tmpdirpath)
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
    rc = entropyTools.spawnCommand("tar cjf "+dirpath+" -C / --files-from='"+tmpdirpath+"/"+dbCONTENTS+"' --no-recursion", redirect = "&>/dev/null")
    
    # appending xpak informations
    import xpak
    tbz2 = xpak.tbz2(dirpath)
    tbz2.recompose(dbdir)
    
    # Remove tmp file
    entropyTools.spawnCommand("rm -rf "+tmpdirpath)
    
    if os.path.isfile(dirpath):
	return dirpath
    else:
	return False

# NOTE: atom must be a COMPLETE atom, with version!
def isTbz2PackageAvailable(atom, verbose = False, stable = False, unstable = True):

    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isTbz2PackageAvailable: called -> "+atom)

    # check if the package have been already merged
    atomName = atom.split("/")[len(atom.split("/"))-1]
    tbz2Available = False
    
    paths = []
    if (unstable):
	paths.append(etpConst['packagessuploaddir']+"/"+atomName+"-unstable.tbz2")
	paths.append(etpConst['packagesstoredir']+"/"+atomName+"-unstable.tbz2")
	paths.append(etpConst['packagesbindir']+"/"+atomName+"-unstable.tbz2")
    if (stable):
	paths.append(etpConst['packagessuploaddir']+"/"+atomName+"-stable.tbz2")
	paths.append(etpConst['packagesstoredir']+"/"+atomName+"-stable.tbz2")
	paths.append(etpConst['packagesbindir']+"/"+atomName+"-stable.tbz2")

    for path in paths:
	if (verbose): print_info("testing in directory: "+path)
	if os.path.isfile(path):
	    tbz2Available = path
	    if (verbose): print_info("found here: "+str(path))
	    break

    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isTbz2PackageAvailable: result -> "+str(tbz2Available))
    return tbz2Available

def checkAtom(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"checkAtom: called -> "+str(atom))
    bestAtom = getBestAtom(atom)
    if bestAtom == "!!conflicts":
	bestAtom = ""
    if (isvalidatom(atom) == 1) or ( bestAtom != ""):
        return True
    return False


def getPackageDependencyList(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageDependencyList: called -> "+str(atom))
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

def getUSEFlags():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getUSEFlags: called. ")
    return portage.settings['USE']

def getMAKEOPTS():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getMAKEOPTS: called. ")
    return portage.settings['MAKEOPTS']

def getCFLAGS():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getCFLAGS: called. ")
    return portage.settings['CFLAGS']

def getLDFLAGS():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getLDFLAGS: called. ")
    return portage.settings['LDFLAGS']

# you must provide a complete atom
def getPackageIUSE(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageIUSE: called. ")
    return getPackageVar(atom,"IUSE")

def getPackageVar(atom,var):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageVar: called -> "+atom+" | var: "+var)
    if atom.startswith("="):
	atom = atom[1:]
    # can't check - return error
    if (atom.find("/") == -1):
	return 1
    return portage.portdb.aux_get(atom,[var])[0]

def synthetizeRoughDependencies(roughDependencies, useflags = None):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"synthetizeRoughDependencies: called. ")
    if useflags is None:
        useflags = getUSEFlags()
    # returns dependencies, conflicts

    useMatch = False
    openParenthesis = 0
    openParenthesisFromOr = 0
    openOr = False
    useFlagQuestion = False
    dependencies = ""
    conflicts = ""
    useflags = useflags.split()
    
    length = len(roughDependencies)
    global atomcount
    atomcount = -1

    while atomcount < length:
	
	atomcount += 1
	try:
	    atom = roughDependencies[atomcount]
	except:
	    break
	
        if atom.startswith("("):
	    if (openOr):
		openParenthesisFromOr += 1
	    openParenthesis += 1
	    curparenthesis = openParenthesis # 2
	    if (useFlagQuestion == True) and (useMatch == False):
		skip = True
		while (skip == True):
		    atomcount += 1
		    atom = roughDependencies[atomcount]
		    if atom.startswith("("):
			curparenthesis += 1
		    elif atom.startswith(")"):
		        if (curparenthesis == openParenthesis):
			    skip = False
			curparenthesis -= 1
		useFlagQuestion = False

	elif atom.endswith("?"):
	    
	    #if (useFlagQuestion) and (not useMatch): # if we're already in a question and the question is not accepted, skip the cycle
	    #    continue
	    # we need to see if that useflag is enabled
	    useFlag = atom.split("?")[0]
	    useFlagQuestion = True # V
	    #openParenthesisFromLastUseFlagQuestion = 0
	    if useFlag.startswith("!"):
		checkFlag = useFlag[1:]
		try:
		    useflags.index(checkFlag)
		    useMatch = False
		except:
		    useMatch = True
	    else:
		try:
		    useflags.index(useFlag)
		    useMatch = True # V
		except:
		    useMatch = False
	
        elif atom.startswith(")"):
	
	    openParenthesis -= 1
	    if (openParenthesis == 0):
		useFlagQuestion = False
		useMatch = False
	    
	    if (openOr):
		# remove last "_or_" from dependencies
		if (openParenthesisFromOr == 1):
		    openOr = False
		    if dependencies.endswith(dbOR):
		        dependencies = dependencies[:len(dependencies)-len(dbOR)]
		        dependencies += " "
		elif (openParenthesisFromOr == 2):
		    if dependencies.endswith("|and|"):
		        dependencies = dependencies[:len(dependencies)-len("|and|")]
		        dependencies += dbOR
		openParenthesisFromOr -= 1

        elif atom.startswith("||"):
	    openOr = True # V
	
	elif (atom.find("/") != -1) and (not atom.startswith("!")) and (not atom.endswith("?")):
	    # it's a package name <pkgcat>/<pkgname>-???
	    if ((useFlagQuestion == True) and (useMatch == True)) or ((useFlagQuestion == False) and (useMatch == False)):
	        # check if there's an OR
		if (openOr):
		    dependencies += atom
		    # check if the or is fucked up
		    if openParenthesisFromOr > 1:
			dependencies += "|and|" # !!
		    else:
		        dependencies += dbOR
                else:
		    dependencies += atom
		    dependencies += " "

        elif atom.startswith("!") and (not atom.endswith("?")):
	    if ((useFlagQuestion) and (useMatch)) or ((not useFlagQuestion) and (not useMatch)):
		conflicts += atom
		if (openOr):
		    conflicts += dbOR
                else:
		    conflicts += " "
    

    # format properly
    tmpConflicts = list(set(conflicts.split()))
    conflicts = ''
    tmpData = []
    for i in tmpConflicts:
	i = i[1:] # remove "!"
	tmpData.append(i)
    conflicts = string.join(tmpData," ")

    tmpData = []
    tmpDeps = list(set(dependencies.split()))
    dependencies = ''
    for i in tmpDeps:
	tmpData.append(i)
    dependencies = string.join(tmpData," ")

    return dependencies, conflicts

def getPortageAppDbPath():
    rc = getPortageEnv("ROOT")+portage_const.VDB_PATH
    if (not rc.endswith("/")):
	return rc+"/"
    return rc

# Collect installed packages
def getInstalledPackages():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getInstalledPackages: called. ")
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

def packageSearch(keyword):

    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packageSearch: called. ")

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
