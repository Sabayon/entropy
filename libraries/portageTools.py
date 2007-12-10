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

import os
from entropyConstants import *
import portage
import portage_const
from portage_dep import isvalidatom, isspecific, isjustname, dep_getkey, dep_getcpv
from portage_util import grabdict_package
from portage_const import USER_CONFIG_PATH

# colours support
from outputTools import *
# misc modules
import sys
import os
import commands
import entropyTools

# Logging initialization
import logTools
portageLog = logTools.LogFile(level=etpConst['spmbackendloglevel'],filename = etpConst['spmbackendlogfile'], header = "[Portage]")
# portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"testFunction: example. ")

############
# Functions and Classes
#####################################################################################

def getThirdPartyMirrors(mirrorname):
    try:
        return portage.thirdpartymirrors[mirrorname]
    except KeyError:
        return []

def getPortageEnv(var):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPortageEnv: called.")
    try:
	rc = portage.config(clone=portage.settings).environ()[var]
	portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPortageEnv: variable available -> "+str(var))
	return rc
    except KeyError:
	portageLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"getPortageEnv: variable not available -> "+str(var))
	return None

# Packages in system (in the Portage language -> emerge system, remember?)
def getPackagesInSystem():
    system = portage.settings.packages
    sysoutput = []
    for x in system:
	y = getInstalledAtoms(x)
	if (y != None):
	    for z in y:
	        sysoutput.append(z)
    sysoutput.append("sys-kernel/linux-sabayon") # our kernel
    sysoutput.append("dev-db/sqlite") # our interface
    sysoutput.append("dev-python/pysqlite") # our python interface to our interface (lol)
    sysoutput.append("virtual/cron") # our cron service
    sysoutput.append("app-admin/equo") # our package manager (client)
    sysoutput.append("sys-apps/entropy") # our package manager (server+client)
    return sysoutput

def getConfigProtectAndMask():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getConfigProtectAndMask: called.")
    config_protect = portage.settings['CONFIG_PROTECT']
    config_protect = config_protect.split()
    config_protect_mask = portage.settings['CONFIG_PROTECT_MASK']
    config_protect_mask = config_protect_mask.split()
    # explode
    protect = []
    for x in config_protect:
	if x.startswith("$"): #FIXME: small hack
	    x = commands.getoutput("echo "+x).split("\n")[0]
	protect.append(x)
    mask = []
    for x in config_protect_mask:
	if x.startswith("$"): #FIXME: small hack
	    x = commands.getoutput("echo "+x).split("\n")[0]
	mask.append(x)
    return ' '.join(protect),' '.join(mask)

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

# should be only used when a pkgcat/pkgname <-- is not specified (example: db, amarok, AND NOT media-sound/amarok)
def getAtomCategory(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getAtomCategory: called. ")
    try:
        rc = portage.portdb.xmatch("match-all",str(atom))[0].split("/")[0]
        return rc
    except:
	portageLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"getAtomCategory: error, can't extract category !")
	return None

# please always force =pkgcat/pkgname-ver if possible
def getInstalledAtom(atom):
    mypath = etpConst['systemroot']+"/"
    mytree = portage.vartree(root=mypath)
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getInstalledAtom: called -> "+str(atom))
    rc = mytree.dep_match(str(atom))
    if (rc != []):
	if (len(rc) == 1):
	    return rc[0]
	else:
            return rc[len(rc)-1]
    else:
        return None

def getPackageSlot(atom):
    mypath = etpConst['systemroot']+"/"
    mytree = portage.vartree(root=mypath)
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageSlot: called. ")
    if atom.startswith("="):
	atom = atom[1:]
    rc = mytree.getslot(atom)
    if rc != "":
	portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageSlot: slot found -> "+str(atom)+" -> "+str(rc))
	return rc
    else:
	portageLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"getPackageSlot: slot not found -> "+str(atom))
	return None

def getInstalledAtoms(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getInstalledAtoms: called -> "+atom)
    mypath = etpConst['systemroot']+"/"
    mytree = portage.vartree(root=mypath)
    rc = mytree.dep_match(str(atom))
    if (rc != []):
        return rc
    else:
        return None

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

# create a .tbz2 file in the specified path
def quickpkg(atom,dirpath):

    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"quickpkg: called -> "+atom+" | dirpath: "+dirpath)

    # getting package info
    pkgname = atom.split("/")[1]
    pkgcat = atom.split("/")[0]
    pkgfile = pkgname+".tbz2"
    if not os.path.isdir(dirpath):
        os.makedirs(dirpath)
    dirpath += "/"+pkgname+".tbz2"
    dbdir = getPortageAppDbPath()+"/"+pkgcat+"/"+pkgname+"/"

    import tarfile
    import stat
    from portage import dblink
    trees = portage.db["/"]
    vartree = trees["vartree"]
    dblnk = dblink(pkgcat, pkgname, "/", vartree.settings, treetype="vartree", vartree=vartree)
    dblnk.lockdb()
    tar = tarfile.open(dirpath,"w:bz2")

    contents = dblnk.getcontents()
    id_strings = {}
    paths = contents.keys()
    paths.sort()
    
    for path in paths:
	try:
	    exist = os.lstat(path)
	except OSError:
	    continue # skip file
	ftype = contents[path][0]
	lpath = path
	arcname = path[1:]
	if 'dir' == ftype and \
	    not stat.S_ISDIR(exist.st_mode) and \
	    os.path.isdir(lpath):
	    lpath = os.path.realpath(lpath)
	tarinfo = tar.gettarinfo(lpath, arcname)
	tarinfo.uname = id_strings.setdefault(tarinfo.uid, str(tarinfo.uid))
	tarinfo.gname = id_strings.setdefault(tarinfo.gid, str(tarinfo.gid))
	
	if stat.S_ISREG(exist.st_mode):
	    tarinfo.type = tarfile.REGTYPE
	    f = open(path)
	    try:
		tar.addfile(tarinfo, f)
	    finally:
		f.close()
	else:
	    tar.addfile(tarinfo)

    tar.close()
    
    # appending xpak informations
    import xpak
    tbz2 = xpak.tbz2(dirpath)
    tbz2.recompose(dbdir)
    
    dblnk.unlockdb()
    
    if os.path.isfile(dirpath):
	return dirpath
    else:
	return False

def getUSEFlags():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getUSEFlags: called.")
    return portage.settings['USE']

def getUSEForce():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getUSEForce: called.")
    return portage.settings.useforce

def getUSEMask():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getUSEMask: called.")
    return portage.settings.usemask

def getMAKEOPTS():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getMAKEOPTS: called.")
    return portage.settings['MAKEOPTS']

def getCFLAGS():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getCFLAGS: called.")
    return portage.settings['CFLAGS']

def getLDFLAGS():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getLDFLAGS: called.")
    return portage.settings['LDFLAGS']

# you must provide a complete atom
def getPackageIUSE(atom):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageIUSE: called.")
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
    conflicts = ' '.join(tmpData)

    tmpData = []
    tmpDeps = list(set(dependencies.split()))
    dependencies = ''
    for i in tmpDeps:
	tmpData.append(i)

    # now filter |or| and |and|
    _tmpData = []
    for dep in tmpData:
	
	if dep.find("|or|") != -1:
	    deps = dep.split("|or|")
	    # find the best
	    results = []
	    for x in deps:
		if x.find("|and|") != -1:
		    anddeps = x.split("|and|")
		    results.append(anddeps)
		else:
		    if x:
		        results.append([x])
	
	    # now parse results
	    for result in results:
		outdeps = result[:]
		for y in result:
		    yresult = getInstalledAtoms(y)
		    if (yresult != None):
			outdeps.remove(y)
		if (not outdeps):
		    # find it
		    for y in result:
			_tmpData.append(y)
		    break
	
	else:
	    _tmpData.append(dep)

    dependencies = ' '.join(_tmpData)

    return dependencies, conflicts

def getPortageAppDbPath():
    rc = etpConst['systemroot']+"/"+portage_const.VDB_PATH
    if (not rc.endswith("/")):
	return rc+"/"
    return rc

# Collect installed packages
def getInstalledPackages(dbdir = None):
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getInstalledPackages: called.")
    import os
    if not dbdir:
        appDbDir = getPortageAppDbPath()
    else:
        appDbDir = dbdir
    dbDirs = os.listdir(appDbDir)
    installedAtoms = []
    for pkgsdir in dbDirs:
	if os.path.isdir(appDbDir+pkgsdir):
	    pkgdir = os.listdir(appDbDir+pkgsdir)
	    for pdir in pkgdir:
	        pkgcat = pkgsdir.split("/")[len(pkgsdir.split("/"))-1]
	        pkgatom = pkgcat+"/"+pdir
	        if pkgatom.find("-MERGING-") == -1:
	            installedAtoms.append(pkgatom)
    return installedAtoms, len(installedAtoms)

def getInstalledPackagesCounters():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getInstalledPackagesCounters: called.")
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
		# get counter
		f = open(appDbDir+pkgsdir+"/"+pdir+"/"+dbCOUNTER,"r")
		counter = f.readline().strip()
		f.close()
	        installedAtoms.append([pkgatom,int(counter)])
    return installedAtoms, len(installedAtoms)

def refillCounter():
    portageLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"refillCounter: called.")
    import os
    appDbDir = getPortageAppDbPath()
    counters = set()
    for catdir in os.listdir(appDbDir):
        catdir = appDbDir+catdir
        if not os.path.isdir(catdir):
            continue
        for pkgdir in os.listdir(catdir):
            pkgdir = catdir+"/"+pkgdir
            if not os.path.isdir(pkgdir):
                continue
            counterfile = pkgdir+"/"+dbCOUNTER
            if not os.path.isfile(pkgdir+"/"+dbCOUNTER):
                continue
            try:
                f = open(counterfile,"r")
                counter = int(f.readline().strip())
                counters.add(counter)
            except:
                continue
    newcounter = max(counters)
    if not os.path.isdir(os.path.dirname(etpConst['edbcounter'])):
        os.makedirs(os.path.dirname(etpConst['edbcounter']))
    f = open(etpConst['edbcounter'],"w")
    f.write(str(newcounter))
    f.flush()
    f.close()
    return newcounter

