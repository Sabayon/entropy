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

# FIXME: this depends on portage, should be moved from here ASAP
from outputTools import *
from entropyConstants import *
import os
import re
import sys
import threading, time
import string

# Instantiate the databaseStatus:
import databaseTools
dbStatus = databaseTools.databaseStatus()

# Logging initialization
import logTools
entropyLog = logTools.LogFile(level=etpConst['entropyloglevel'],filename = etpConst['entropylogfile'], header = "[Entropy]")
# example: entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"testFuncton: called.")

# EXIT STATUSES: 100-199

global __etp_debug
__etp_debug = False
def enableDebug():
    __etp_debug = True
    import pdb
    pdb.set_trace()

def getDebug():
    return __etp_debug

def isRoot():
    if (os.getuid() == 0):
        return True
    return False

class TimeScheduled(threading.Thread):
    def __init__(self, function, delay):
        threading.Thread.__init__(self)
        self.function = function
        self.delay = delay
    def run(self):
        self.alive = 1
        while self.alive:
            self.function()
	    try:
                time.sleep(self.delay)
	    except:
		pass
    def kill(self):
        self.alive = 0

def applicationLockCheck(option = None, gentle = False):
    if (etpConst['applicationlock']):
	print_error(red("Another instance of Equo is running. Action: ")+bold(str(option))+red(" denied."))
	print_error(red("If I am lying (maybe). Please remove ")+bold(etpConst['pidfile']))
	if (not gentle):
	    sys.exit(10)
	else:
	    return True
    return False

def getRandomNumber():
    import random
    return int(str(random.random())[2:7])

def countdown(secs=5,what="Counting...", back = False):
    if secs:
	if back:
	    sys.stdout.write(what)
	else:
	    print what
        for i in range(secs)[::-1]:
            sys.stdout.write(red(str(i+1)+" "))
            sys.stdout.flush()
	    time.sleep(1)

def spinner(rotations, interval, message=''):
	for x in xrange(rotations):
		writechar(message + '|/-\\'[x%4] + '\r')
		time.sleep(interval)
	writechar(' ')
	for i in xrange(len(message)): print ' ',
	writechar('\r')

def md5sum(filepath):
    import md5
    m = md5.new()
    readfile = file(filepath)
    block = readfile.read(1024)
    while block:
        m.update(block)
	block = readfile.read(1024)
    return m.hexdigest()
    
def unpackGzip(gzipfilepath):
    import gzip
    filepath = gzipfilepath[:-3] # remove .gz
    file = open(filepath,"wb")
    filegz = gzip.GzipFile(gzipfilepath,"rb")
    filecont = filegz.readlines()
    filegz.close()
    file.writelines(filecont)
    file.flush()
    file.close()
    del filecont
    return filepath

def unpackBzip2(bzip2filepath):
    import bz2
    filepath = bzip2filepath[:-4] # remove .gz
    file = open(filepath,"wb")
    filebz2 = bz2.BZ2File(bzip2filepath,"rb")
    filecont = filebz2.readlines()
    filebz2.close()
    file.writelines(filecont)
    file.flush()
    file.close()
    del filecont
    return filepath

def extractXpak(tbz2file,tmpdir = None):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"extractXpak: called -> "+tbz2file)
    # extract xpak content
    xpakpath = suckXpak(tbz2file, etpConst['packagestmpdir'])
    
    import xpak
    if tmpdir is None:
	tmpdir = etpConst['packagestmpdir']+"/"+os.path.basename(tbz2file)[:-5]+"/"
    if os.path.isdir(tmpdir):
	spawnCommand("rm -rf "+tmpdir)
    os.makedirs(tmpdir)
    xpakdata = xpak.getboth(xpakpath)
    xpak.xpand(xpakdata,tmpdir)
    try:
	os.remove(xpakpath)
    except:
        pass
    return tmpdir
    
def suckXpak(tbz2file, outputpath):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"suckXpak: called -> "+tbz2file+" and "+outputpath)
    
    xpakpath = outputpath+"/"+os.path.basename(tbz2file)[:-5]+".xpak"
    old = open(tbz2file,"rb")
    db = open(xpakpath,"wb")
    allowWrite = False
    
    # position old to the end
    old.seek(0,2)
    # read backward until we find
    bytes = old.tell()
    counter = bytes
    dbcontent = []
    
    while counter >= 0:
	old.seek(counter-bytes,2)
	byte = old.read(1)
	if byte == "P" or byte == "K":
	    old.seek(counter-bytes-7,2)
	    chunk = old.read(7)+byte
	    if chunk == "XPAKPACK":
		allowWrite = False
		dbcontent.append(chunk)
		break
	    elif chunk == "XPAKSTOP":
		allowWrite = True
		old.seek(counter-bytes,2)
	if (allowWrite):
	    dbcontent.append(byte)
	counter -= 1
    dbcontent.reverse()
    for x in dbcontent:
	db.write(x)
    
    db.flush()
    db.close()
    old.close()
    return xpakpath

def aggregateEdb(tbz2file,dbfile):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"aggregateEntropyDb: called -> "+tbz2file+" and "+dbfile)
    f = open(tbz2file,"abw")
    g = open(dbfile,"rb")
    dbx = g.readlines()
    # append tag
    f.write(etpConst['databasestarttag'])
    for x in dbx:
	f.write(x)
    f.flush()
    f.close()

def extractEdb(tbz2file, dbpath = None):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"extractEdb: called -> "+tbz2file)
    old = open(tbz2file,"rb")
    if not dbpath:
        dbpath = tbz2file[:-5]+".db"
    db = open(dbpath,"wb")
    
    # position old to the end
    old.seek(0,2)
    # read backward until we find
    bytes = old.tell()
    counter = bytes
    dbcontent = []
    
    while counter >= 0:
	old.seek(counter-bytes,2)
	byte = old.read(1)
	if byte == "|":
	    old.seek(counter-bytes-31,2)
	    chunk = old.read(31)+byte
	    if chunk == etpConst['databasestarttag']:
		break
	dbcontent.append(byte)
	counter -= 1
    if not dbcontent:
        old.close()
        db.close()
        try:
            os.remove(dbpath)
        except:
            pass
        return None
    dbcontent.reverse()
    for x in dbcontent:
	db.write(x)
    
    db.flush()
    db.close()
    old.close()
    return dbpath


# This function creates the .md5 file related to the given package file
# @returns the complete hash file path
def createHashFile(tbz2filepath):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createHashFile: for "+tbz2filepath)
    md5hash = md5sum(tbz2filepath)
    hashfile = tbz2filepath+etpConst['packageshashfileext']
    f = open(hashfile,"w")
    tbz2name = os.path.basename(tbz2filepath)
    f.write(md5hash+"  "+tbz2name+"\n")
    f.flush()
    f.close()
    return hashfile

def compareMd5(filepath,checksum):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"compareMd5: called. ")
    checksum = str(checksum)
    result = md5sum(filepath)
    result = str(result)
    if checksum == result:
        entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"compareMd5: match. ")
	return True
    entropyLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"compareMd5: no match. ")
    return False

def md5string(string):
    import md5
    m = md5.new()
    m.update(string)
    return m.hexdigest()

# used by equo, this function retrieves the new safe Gentoo-aware file path
def allocateMaskedFile(file):
    counter = -1
    newfile = ""
    previousfile = ""
    while 1:
	counter += 1
	txtcounter = str(counter)
	oldtxtcounter = str(counter-1)
	for x in range(4-len(txtcounter)):
	    txtcounter = "0"+txtcounter
	    oldtxtcounter = "0"+oldtxtcounter
	newfile = os.path.dirname(file)+"/"+"._cfg"+txtcounter+"_"+os.path.basename(file)
	if counter > 0:
	    previousfile = os.path.dirname(file)+"/"+"._cfg"+oldtxtcounter+"_"+os.path.basename(file)
	else:
	    previousfile = os.path.dirname(file)+"/"+"._cfg0000_"+os.path.basename(file)
	if not os.path.exists(newfile):
	    break
    if not newfile:
	newfile = os.path.dirname(file)+"/"+"._cfg0000_"+os.path.basename(file)
    else:
	if os.path.exists(previousfile):
	    # compare old and new, if they match, suggest previousfile directly
	    new = md5sum(file)
	    old = md5sum(previousfile)
	    if (new == old):
		newfile = previousfile
    return newfile

def extractElog(file):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"extractElog: called.")

    logline = False
    logoutput = []
    f = open(file,"r")
    reallog = f.readlines()
    f.close()
    
    for line in reallog:
	if line.startswith("INFO: postinst") or line.startswith("LOG: postinst"):
	    logline = True
	    continue
	    # disable all the others
	elif line.startswith("LOG:"):
	    logline = False
	    continue
	if (logline) and (line.strip()):
	    # trap !
	    logoutput.append(line.strip())
    return logoutput

# Imported from Gentoo portage_dep.py
# Copyright 2003-2004 Gentoo Foundation
# done to avoid the import of portage_dep here
ver_regexp = re.compile("^(cvs\\.)?(\\d+)((\\.\\d+)*)([a-z]?)((_(pre|p|beta|alpha|rc)\\d*)*)(-r(\\d+))(-t(\\S+))?$")
def isjustpkgname(mypkg):
    myparts = mypkg.split('-')
    for x in myparts:
	if ververify(x):
	    return 0
    return 1

ververifyCache = {}
def ververify(myverx, silent=1):
    
    cached = ververifyCache.get(myverx)
    if cached != None:
	return cached
    
    ververifyCache[myverx] = 1
    myver = myverx[:]
    if myver.endswith("*"):
	myver = myver[:len(myver)-1]
    if ver_regexp.match(myver):
	return 1
    else:
	if not silent:
	    print "!!! syntax error in version: %s" % myver
	ververifyCache[myverx] = 0
	return 0

isjustnameCache = {}
def isjustname(mypkg):
    """
    Checks to see if the depstring is only the package name (no version parts)

    Example usage:
	>>> isjustname('media-libs/test-3.0')
	0
	>>> isjustname('test')
	1
	>>> isjustname('media-libs/test')
	1

    @param mypkg: The package atom to check
    @param mypkg: String
    @rtype: Integer
    @return: One of the following:
	1) 0 if the package string is not just the package name
	2) 1 if it is
    """
    
    cached = isjustnameCache.get(mypkg)
    if cached != None:
	return cached
    
    isjustnameCache[mypkg] = 1
    myparts = mypkg.split('-')
    for x in myparts:
	if ververify(x):
	    isjustnameCache[mypkg] = 0
	    return 0
    return 1

def isspecific(mypkg):
    """
    Checks to see if a package is in category/package-version or package-version format,
    possibly returning a cached result.

    Example usage:
	>>> isspecific('media-libs/test')
	0
	>>> isspecific('media-libs/test-3.0')
	1

    @param mypkg: The package depstring to check against
    @type mypkg: String
    @rtype: Integer
    @return: One of the following:
	1) 0 if the package string is not specific
	2) 1 if it is
    """
    mysplit = mypkg.split("/")
    if not isjustname(mysplit[-1]):
	return 1
    return 0

catpkgsplitCache = {}
def catpkgsplit(mydata,silent=1):
    """
    Takes a Category/Package-Version-Rev and returns a list of each.

    @param mydata: Data to split
    @type mydata: string 
    @param silent: suppress error messages
    @type silent: Boolean (integer)
    @rype: list
    @return:
	1.  If each exists, it returns [cat, pkgname, version, rev]
	2.  If cat is not specificed in mydata, cat will be "null"
	3.  if rev does not exist it will be '-r0'
	4.  If cat is invalid (specified but has incorrect syntax)
 		an InvalidData Exception will be thrown
    """
    
    cached = catpkgsplitCache.get(mydata)
    if cached != None:
	return cached
    
    # Categories may contain a-zA-z0-9+_- but cannot start with -
    mysplit=mydata.split("/")
    p_split=None
    if len(mysplit)==1:
	retval=["null"]
	p_split=pkgsplit(mydata,silent=silent)
    elif len(mysplit)==2:
	retval=[mysplit[0]]
	p_split=pkgsplit(mysplit[1],silent=silent)
    if not p_split:
	catpkgsplitCache[mydata] = None
	return None
    retval.extend(p_split)
    catpkgsplitCache[mydata] = retval
    return retval

def pkgsplit(mypkg,silent=1):
    myparts=mypkg.split("-")

    if len(myparts)<2:
	if not silent:
	    print "!!! Name error in",mypkg+": missing a version or name part."
	    return None
    for x in myparts:
	if len(x)==0:
	    if not silent:
		print "!!! Name error in",mypkg+": empty \"-\" part."
		return None
	
    #verify rev
    revok=0
    myrev=myparts[-1]
    
    if len(myrev) and myrev[0]=="r":
	try:
	    int(myrev[1:])
	    revok=1
	except ValueError: # from int()
	    pass
    if revok:
	verPos = -2
	revision = myparts[-1]
    else:
	verPos = -1
	revision = "r0"

    if ververify(myparts[verPos]):
	if len(myparts)== (-1*verPos):
	    return None
	else:
	    for x in myparts[:verPos]:
		if ververify(x):
		    return None
		    #names can't have versiony looking parts
	    myval=["-".join(myparts[:verPos]),myparts[verPos],revision]
	    return myval
    else:
	return None

# FIXME: deprecated, use remove_tag - will be removed soonly
dep_striptagCache = {}
def dep_striptag(mydepx):

    cached = dep_striptagCache.get(mydepx)
    if cached != None:
	return cached

    mydep = mydepx[:]
    if not (isjustname(mydep)):
	if mydep.split("-")[len(mydep.split("-"))-1].startswith("t"): # tag -> remove
	    tag = mydep.split("-")[len(mydep.split("-"))-1]
	    mydep = mydep[:len(mydep)-len(tag)-1]
    
    dep_striptagCache[mydepx] = mydep
    return mydep

dep_getkeyCache = {}
def dep_getkey(mydepx):
    """
    Return the category/package-name of a depstring.

    Example usage:
	>>> dep_getkey('media-libs/test-3.0')
	'media-libs/test'

    @param mydep: The depstring to retrieve the category/package-name of
    @type mydep: String
    @rtype: String
    @return: The package category/package-version
    """
    
    cached = dep_getkeyCache.get(mydepx)
    if cached != None:
	return cached
    
    mydep = mydepx[:]
    mydep = dep_striptag(mydep)
    
    mydep = dep_getcpv(mydep)
    if mydep and isspecific(mydep):
	mysplit = catpkgsplit(mydep)
	if not mysplit:
	    dep_getkeyCache[mydepx] = mydep
	    return mydep
	dep_getkeyCache[mydepx] = mysplit[0] + "/" + mysplit[1]
	return mysplit[0] + "/" + mysplit[1]
    else:
	dep_getkeyCache[mydepx] = mydep
	return mydep

dep_getcpvCache = {}
def dep_getcpv(mydep):
    """
    Return the category-package-version with any operators/slot specifications stripped off

    Example usage:
	>>> dep_getcpv('>=media-libs/test-3.0')
	'media-libs/test-3.0'

    @param mydep: The depstring
    @type mydep: String
    @rtype: String
    @return: The depstring with the operator removed
    """
    
    cached = dep_getcpvCache.get(mydep)
    if cached != None:
	return cached
    
    mydep_orig = mydep
    if mydep and mydep[0] == "*":
	mydep = mydep[1:]
    if mydep and mydep[-1] == "*":
	mydep = mydep[:-1]
    if mydep and mydep[0] == "!":
	mydep = mydep[1:]
    if mydep[:2] in [">=", "<="]:
	mydep = mydep[2:]
    elif mydep[:1] in "=<>~":
	mydep = mydep[1:]
    colon = mydep.rfind(":")
    if colon != -1:
	mydep = mydep[:colon]

    dep_getcpvCache[mydep] = mydep
    return mydep

dep_getslotCache = {}
def dep_getslot(dep):
    """
    Retrieve the slot on a depend.
    
    Example usage:
	>>> dep_getslot('app-misc/test:3')
	'3'
    	
    @param mydep: The depstring to retrieve the slot of
    @type dep: String
    @rtype: String
    @return: The slot
    """
    
    cached = dep_getslotCache.get(dep)
    if cached != None:
	return cached
    
    colon = dep.rfind(":")
    if colon != -1:
	mydep = dep[colon+1:]
	rslt = remove_tag(mydep)
	dep_getslotCache[dep] = rslt
	return rslt
    
    dep_getslotCache[dep] = None
    return None

def remove_slot(mydep):
    colon = mydep.rfind(":")
    if colon != -1:
	mydep = mydep[:colon]
    return mydep

# input must be a valid package version or a full atom
def remove_revision(ver):
    myver = ver.split("-")
    if myver[-1][0] == "r":
	return string.join(myver[:-1],"-")
    return ver

def remove_tag(mydep):
    colon = mydep.rfind("#")
    if colon != -1:
	mydep = mydep[:colon]
    return mydep

dep_gettagCache = {}
def dep_gettag(dep):
    """
    Retrieve the slot on a depend.
    
    Example usage:
	>>> dep_gettag('app-misc/test#2.6.23-sabayon-r1')
	'2.6.23-sabayon-r1'
    
    """

    cached = dep_gettagCache.get(dep)
    if cached != None:
	return cached

    colon = dep.rfind("#")
    if colon != -1:
	mydep = dep[colon+1:]
	rslt = remove_slot(mydep)
	dep_gettagCache[dep] = rslt
	return rslt
    dep_gettagCache[dep] = None
    return None

removePackageOperatorsCache = {}
def removePackageOperators(atom):

    cached = removePackageOperatorsCache.get(atom)
    if cached != None:
	return cached

    original = atom
    if atom[0] == ">" or atom[0] == "<":
	atom = atom[1:]
    if atom[0] == "=":
	atom = atom[1:]
    if atom[0] == "~":
	atom = atom[1:]
    
    removePackageOperatorsCache[original] = atom
    return atom

# Version compare function taken from portage_versions.py
# portage_versions.py -- core Portage functionality
# Copyright 1998-2006 Gentoo Foundation
ver_regexp = re.compile("^(cvs\\.)?(\\d+)((\\.\\d+)*)([a-z]?)((_(pre|p|beta|alpha|rc)\\d*)*)(-r(\\d+))?$")
suffix_regexp = re.compile("^(alpha|beta|rc|pre|p)(\\d*)$")
suffix_value = {"pre": -2, "p": 0, "alpha": -4, "beta": -3, "rc": -1}
endversion_keys = ["pre", "p", "alpha", "beta", "rc"]
compareVersionsCache = {}
def compareVersions(ver1, ver2, silent=1):
	
	cached = compareVersionsCache.get(tuple([ver1,ver2]))
	if cached != None:
	    return cached
	
	if ver1 == ver2:
		compareVersionsCache[tuple([ver1,ver2])] = 0
		return 0
	mykey=ver1+":"+ver2
	match1 = ver_regexp.match(ver1)
	match2 = ver_regexp.match(ver2)
	
	# building lists of the version parts before the suffix
	# first part is simple
	list1 = [int(match1.group(2))]
	list2 = [int(match2.group(2))]

	# this part would greatly benefit from a fixed-length version pattern
	if len(match1.group(3)) or len(match2.group(3)):
		vlist1 = match1.group(3)[1:].split(".")
		vlist2 = match2.group(3)[1:].split(".")
		for i in range(0, max(len(vlist1), len(vlist2))):
			# Implcit .0 is given a value of -1, so that 1.0.0 > 1.0, since it
			# would be ambiguous if two versions that aren't literally equal
			# are given the same value (in sorting, for example).
			if len(vlist1) <= i or len(vlist1[i]) == 0:
				list1.append(-1)
				list2.append(int(vlist2[i]))
			elif len(vlist2) <= i or len(vlist2[i]) == 0:
				list1.append(int(vlist1[i]))
				list2.append(-1)
			# Let's make life easy and use integers unless we're forced to use floats
			elif (vlist1[i][0] != "0" and vlist2[i][0] != "0"):
				list1.append(int(vlist1[i]))
				list2.append(int(vlist2[i]))
			# now we have to use floats so 1.02 compares correctly against 1.1
			else:
				list1.append(float("0."+vlist1[i]))
				list2.append(float("0."+vlist2[i]))

	# and now the final letter
	if len(match1.group(5)):
		list1.append(ord(match1.group(5)))
	if len(match2.group(5)):
		list2.append(ord(match2.group(5)))

	for i in range(0, max(len(list1), len(list2))):
		if len(list1) <= i:
			compareVersionsCache[tuple([ver1,ver2])] = -1
			return -1
		elif len(list2) <= i:
			compareVersionsCache[tuple([ver1,ver2])] = 1
			return 1
		elif list1[i] != list2[i]:
			compareVersionsCache[tuple([ver1,ver2])] = list1[i] - list2[i]
			return list1[i] - list2[i]
	
	# main version is equal, so now compare the _suffix part
	list1 = match1.group(6).split("_")[1:]
	list2 = match2.group(6).split("_")[1:]
	
	for i in range(0, max(len(list1), len(list2))):
		if len(list1) <= i:
			s1 = ("p","0")
		else:
			s1 = suffix_regexp.match(list1[i]).groups()
		if len(list2) <= i:
			s2 = ("p","0")
		else:
			s2 = suffix_regexp.match(list2[i]).groups()
		if s1[0] != s2[0]:
			compareVersionsCache[tuple([ver1,ver2])] = suffix_value[s1[0]] - suffix_value[s2[0]]
			return suffix_value[s1[0]] - suffix_value[s2[0]]
		if s1[1] != s2[1]:
			# it's possible that the s(1|2)[1] == ''
			# in such a case, fudge it.
			try:			r1 = int(s1[1])
			except ValueError:	r1 = 0
			try:			r2 = int(s2[1])
			except ValueError:	r2 = 0
			compareVersionsCache[tuple([ver1,ver2])] = r1 - r2
			return r1 - r2
	
	# the suffix part is equal to, so finally check the revision
	if match1.group(10):
		r1 = int(match1.group(10))
	else:
		r1 = 0
	if match2.group(10):
		r2 = int(match2.group(10))
	else:
		r2 = 0
	compareVersionsCache[tuple([ver1,ver2])] = r1 - r2
	return r1 - r2

'''
   @description: reorder a version list
   @input versionlist: a list
   @output: the ordered list
'''
getNewerVersionCache = {}
def getNewerVersion(InputVersionlist):

    cached = getNewerVersionCache.get(tuple(InputVersionlist))
    if cached != None:
	return cached

    rc = False
    versionlist = InputVersionlist[:]
    while not rc:
	change = False
        for x in range(len(versionlist)):
	    pkgA = versionlist[x]
	    try:
	        pkgB = versionlist[x+1]
	    except:
	        pkgB = "0"
            result = compareVersions(pkgA,pkgB)
	    #print pkgA + "<->" +pkgB +" = " + str(result)
	    if result < 0:
	        # swap positions
	        versionlist[x] = pkgB
	        versionlist[x+1] = pkgA
		change = True
	if (not change):
	    rc = True
    
    getNewerVersionCache[tuple(InputVersionlist)] = versionlist
    return versionlist

'''
   @description: reorder a list of strings converted into ascii
   @input versionlist: a string list
   @output: the ordered string list
'''
def getNewerVersionTag(InputVersionlist):
    versionlist = InputVersionlist[:]
    versionlist.reverse()
    return versionlist

def isnumber(x):
    try:
	t = int(x)
	return True
    except:
	return False


text_characters = "".join(map(chr, range(32, 127)) + list("\n\r\t\b"))
_null_trans = string.maketrans("", "")

def istextfile(filename, blocksize = 512):
    return istext(open(filename).read(blocksize))

def istext(s):
    if "\0" in s:
        return False
    
    if not s:  # Empty files are considered text
        return True

    # Get the non-text characters (maps a character to itself then
    # use the 'remove' option to get rid of the text characters.)
    t = s.translate(_null_trans, text_characters)

    # If more than 30% non-text characters, then
    # this is considered a binary file
    if len(t)/len(s) > 0.30:
        return False
    return True

# this functions removes duplicates without breaking the list order
# nameslist: a list that contains duplicated names
# @returns filtered list
def filterDuplicatedEntries(alist):
    set = {}
    return [set.setdefault(e,e) for e in alist if e not in set]


# Escapeing functions
mappings = {
	"'":"''",
	'"':'""',
	' ':'+'
}

def escape(*args):
    arg_lst = []
    if len(args)==1:
        return escape_single(args[0])
    for x in args:
        arg_lst.append(escape_single(x))
    return tuple(arg_lst)

def escape_single(x):
    if type(x)==type(()) or type(x)==type([]):
        return escape(x)
    if type(x)==type(""):
        tmpstr=''
        for c in range(len(x)):
            if x[c] in mappings.keys():
                if x[c] in ("'", '"'):
                    if c+1<len(x):
                        if x[c+1]!=x[c]:
                            tmpstr+=mappings[x[c]]
                    else:
                        tmpstr+=mappings[x[c]]
                else:
                   tmpstr+=mappings[x[c]]
            else:
                tmpstr+=x[c]
    else:
        tmpstr=x
    return tmpstr

def unescape(val):
    if type(val)==type(""):
        tmpstr=''
        for key,item in mappings.items():
            val=string.replace(val,item,key)
        tmpstr = val
    else:
        tmpstr=val
    return tmpstr

def unescape_list(*args):
    arg_lst = []
    for x in args:
        arg_lst.append(unescape(x))
    return tuple(arg_lst)

# this function returns a list of duplicated entries found in the input list
def extractDuplicatedEntries(inputlist):
    mycache = {}
    newlist = set()
    for x in inputlist:
	c = mycache.get(x)
	if c:
	    newlist.add(x)
	    continue
	mycache[x] = 1
    return newlist
	

# Tool to run commands
def spawnCommand(command, redirect = None):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"spawnCommand: called for: "+command)
    if redirect is not None:
        command += " "+redirect
    rc = os.system(command)
    return rc

def extractFTPHostFromUri(uri):
    myuri = spliturl(uri)[1]
    # remove username:pass@
    myuri = myuri.split("@")[len(myuri.split("@"))-1]
    return myuri

def spliturl(url):
    import urlparse
    return urlparse.urlsplit(url)

# tar.bz2 compress function...
def compressTarBz2(storepath,pathtocompress):
    
    cmd = "tar cjf "+storepath+" ."
    rc = spawnCommand(
    		"cd "+pathtocompress+";"
    		""+cmd, "&> /dev/null"
		)
    return rc

# tar.bz2 uncompress function...
def uncompressTarBz2(filepath, extractPath = None):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"uncompressTarBz2: called. ")
    if extractPath is None:
	extractPath = os.path.dirname(filepath)
    cmd = "tar xjf "+filepath+" -C "+extractPath
    rc = spawnCommand(cmd, "&> /dev/null")
    return rc

def bytesIntoHuman(bytes):
    size = str(round(float(bytes)/1024,1))
    if bytes < 1024:
	size = str(bytes)+"b"
    elif bytes < 1023999:
	size += "kB"
    elif bytes > 1023999:
	size = str(round(float(size)/1024,1))
	size += "MB"
    return size

# hide password from full ftp URI
def hideFTPpassword(uri):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"hideFTPpassword: called. ")
    ftppassword = uri.split("@")[:len(uri.split("@"))-1]
    if len(ftppassword) > 1:
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

def convertUnixTimeToHumanTime(unixtime):
    from datetime import datetime
    humantime = str(datetime.fromtimestamp(unixtime))
    return humantime

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
def cleanup(toCleanDirs = []):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanup: called.")

    if (not toCleanDirs):
        toCleanDirs = [ etpConst['packagestmpdir'], etpConst['logdir'] ]
    counter = 0

    for xdir in toCleanDirs:
        print_info(red(" * ")+"Cleaning "+darkgreen(xdir)+" directory...", back = True)
	if os.path.isdir(xdir):
	    dircontent = os.listdir(xdir)
	    if dircontent != []:
	        for data in dircontent:
		    spawnCommand("rm -rf "+xdir+"/"+data)
		    counter += 1

    print_info(green(" * ")+"Cleaned: "+str(counter)+" files and directories")

def mountProc():
    # check if it's already mounted
    procfiles = os.listdir("/proc")
    if len(procfiles) > 2:
	return True
    else:
	spawnCommand("mount -t proc proc /proc", "&> /dev/null")
	return True

def umountProc():
    # check if it's already mounted
    procfiles = os.listdir("/proc")
    if len(procfiles) > 2:
	spawnCommand("umount /proc", " &> /dev/null")
	spawnCommand("umount /proc", " &> /dev/null")
	spawnCommand("umount /proc", " &> /dev/null")
	return True
    else:
	return True

def askquestion(prompt):
    responses, colours = ["Yes", "No"], [green, red]
    print darkgreen(prompt),
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