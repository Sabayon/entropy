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
from sys import exit, stdout, getfilesystemencoding
import threading, time, tarfile

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
	    exit(10)
	else:
	    return True
    return False

def getRandomNumber():
    import random
    return int(str(random.random())[2:7])

def countdown(secs=5,what="Counting...", back = False):
    if secs:
	if back:
	    stdout.write(red(">> ")+what)
	else:
	    print what
        for i in range(secs)[::-1]:
            stdout.write(red(str(i+1)+" "))
            stdout.flush()
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
    return unpackXpak(xpakpath,tmpdir)

def readXpak(tbz2file):
    xpakpath = suckXpak(tbz2file, etpConst['entropyunpackdir'])
    f = open(xpakpath,"rb")
    f.seek(0,2)
    size = f.tell()
    f.seek(0)
    data = f.read(size)
    f.close()
    os.remove(xpakpath)
    return data

def unpackXpak(xpakfile, tmpdir = None):
    try:
        import xpak
        import shutil
        if tmpdir is None:
            tmpdir = etpConst['packagestmpdir']+"/"+os.path.basename(xpakfile)[:-5]+"/"
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir,True)
        os.makedirs(tmpdir)
        xpakdata = xpak.getboth(xpakfile)
        xpak.xpand(xpakdata,tmpdir)
        try:
            os.remove(xpakfile)
        except:
            pass
    except:
        return None
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

def removeEdb(tbz2file, savedir):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removeEdb: called -> "+tbz2file)
    old = open(tbz2file,"rb")
    new = open(savedir+"/"+os.path.basename(tbz2file),"wb")
    
    # position old to the end
    old.seek(0,2)
    # read backward until we find
    bytes = old.tell()
    counter = bytes
    
    while counter >= 0:
	old.seek(counter-bytes,2)
	byte = old.read(1)
	if byte == "|":
	    old.seek(counter-bytes-31,2) # wth I can't use len(etpConst['databasestarttag']) ???
	    chunk = old.read(31)+byte
	    if chunk == etpConst['databasestarttag']:
                old.seek(counter-bytes-32,2)
                break
	counter -= 1

    endingbyte = old.tell()
    old.seek(0)
    while old.tell() <= endingbyte:
        byte = old.read(1)
        new.write(byte)
        counter += 1
    
    new.flush()
    new.close()
    old.close()
    return savedir+"/"+os.path.basename(tbz2file)

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
def allocateMaskedFile(file, fromfile): 

    # check if file and tofile are equal
    if os.path.isfile(file) and os.path.isfile(fromfile):
        old = md5sum(fromfile)
        new = md5sum(file)
        if old == new:
            return file, False

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
            
            # compare fromfile with previousfile
            new = md5sum(fromfile)
            old = md5sum(previousfile)
            if new == old:
                return previousfile, False
            
	    # compare old and new, if they match, suggest previousfile directly
	    new = md5sum(file)
	    old = md5sum(previousfile)
	    if (new == old):
		return previousfile, False
            
    return newfile, True

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
    mydep = remove_tag(mydep)
    
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
	return '-'.join(myver[:-1])
    return ver

def remove_tag(mydep):
    colon = mydep.rfind("#")
    if colon != -1:
	mystring = mydep[:colon]
        return mystring
    return mydep

def remove_entropy_revision(mydep):
    colon = mydep.rfind("~")
    if colon != -1:
	mystring = mydep[:colon]
        return mystring
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
   @description: compare two lists composed by [version,tag,revision] and [version,tag,revision]
   			if listA > listB --> positive number
			if listA == listB --> 0
			if listA < listB --> negative number	
   @input package: listA[version,tag,rev] and listB[version,tag,rev]
   @output: integer number
'''
def entropyCompareVersions(listA,listB):
    if len(listA) != 3 or len(listB) != 3:
	raise Exception, "compareVersions: listA and/or listB must be long 3"
    # start with version
    rc = compareVersions(listA[0],listB[0])
    
    if (rc == 0):
	# check tag
	if listA[1] > listB[1]:
	    return 1
	elif listA[1] < listB[1]:
	    return -1
	else:
	    # check rev
	    if listA[2] > listB[2]:
		return 1
	    elif listA[2] < listB[2]:
		return -1
	    else:
		return 0
    return rc

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


def istextfile(filename, blocksize = 512):
    return istext(open(filename).read(blocksize))

def istext(s):
    import string
    _null_trans = string.maketrans("", "")
    text_characters = "".join(map(chr, range(32, 127)) + list("\n\r\t\b"))
    
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
            val=val.replace(item,key)
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
    rc = spawnCommand("cd "+pathtocompress+" && "+cmd, "&> /dev/null")
    return rc

# tar.bz2 uncompress function...
def uncompressTarBz2(filepath, extractPath = None, catchEmpty = False):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"uncompressTarBz2: called.")
    if extractPath is None:
	extractPath = os.path.dirname(filepath)
    if not os.path.isfile(filepath):
        raise OSError
    try:
        tar = tarfile.open(filepath,"r:bz2")
    except tarfile.ReadError:
        if catchEmpty:
            return 0
        else:
            raise

    directories = []
    for tarinfo in tar:
        if tarinfo.isdir():
            # Extract directory with a safe mode, so that
            # all files below can be extracted as well.
            try:
                os.makedirs(os.path.join(extractPath, tarinfo.name), 0777)
            except EnvironmentError:
                pass
            directories.append(tarinfo)
        else:
            try:
                tarinfo.name = tarinfo.name.encode(getfilesystemencoding())
            except:  # default encoding failed
                try:
                    tarinfo.name = tarinfo.name.decode("latin1") # try to convert to latin1 and then back to sys.getfilesystemencoding()
                    tarinfo.name = tarinfo.name.encode(getfilesystemencoding())
                except:
                    raise
            tar.extract(tarinfo, extractPath.encode(getfilesystemencoding()))

    # Reverse sort directories.
    directories.sort(lambda a, b: cmp(a.name, b.name))
    directories.reverse()

    origpath = extractPath
    # Set correct owner, mtime and filemode on directories.
    for tarinfo in directories:
        extractPath = os.path.join(extractPath, tarinfo.name)
        try:
            tar.chown(tarinfo, extractPath)
            tar.utime(tarinfo, extractPath)
            tar.chmod(tarinfo, extractPath)
        except tarfile.ExtractError, e:
            if tar.errorlevel > 1:
                raise

    tar.close()
    if os.listdir(origpath):
        return 0
    else:
        return -1

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
	ftppassword = '@'.join(ftppassword)
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
    return 0

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
    xtermTitle("Entropy got a question for you")
    responses, colours = ["Yes", "No"], [green, red]
    print darkgreen(prompt),
    try:
	while True:
	    response=raw_input("["+"/".join([colours[i](responses[i]) for i in range(len(responses))])+"] ")
	    for key in responses:
		# An empty response will match the first value in responses.
		if response.upper()==key[:len(response)].upper():
                    xtermTitleReset()
		    return key
		    print "I cannot understand '%s'" % response,
    except (EOFError, KeyboardInterrupt):
	print "Interrupted."
        xtermTitleReset()
	exit(100)

class lifobuffer:
    
    def __init__(self):
        self.counter = -1
        self.buf = {}
    
    def push(self,item):
        self.counter += 1
        self.buf[self.counter] = item
    
    def pop(self):
        if self.counter == -1:
            return None
        self.counter -= 1
        return self.buf[self.counter+1]

def writeNewBranch(branch):
    if os.path.isfile(etpConst['repositoriesconf']):
        f = open(etpConst['repositoriesconf'])
        content = f.readlines()
        branchline = [x for x in content if x.startswith("branch|")]
        if branchline:
            # update
            f = open(etpConst['repositoriesconf'],"w")
            for line in content:
                if line.startswith("branch|"):
                    line = "branch|"+str(branch)+"\n"
                f.write(line)
        else:
            # append
            f.seek(0,2)
            f.write("\nbranch|"+str(branch)+"\n")
        f.flush()
        f.close()

# @pkgdata: etpData mapping dictionary (retrieved from db using getPackageData())
# @dirpath: directory to save .tbz2
def quickpkg(pkgdata,dirpath):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"quickpkg: called -> "+str(pkgdata)+" | dirpath: "+dirpath)
    import stat
    import databaseTools

    # getting package info
    pkgtag = ''
    if pkgdata['versiontag']: pkgtag = "#"+pkgdata['versiontag']
    pkgname = pkgdata['name']+"-"+pkgdata['version']+pkgtag # + version + tag
    pkgcat = pkgdata['category']
    pkgfile = pkgname+".tbz2"
    dirpath += "/"+pkgname+".tbz2"
    if os.path.isfile(dirpath):
        os.remove(dirpath)
    tar = tarfile.open(dirpath,"w:bz2")

    contents = [x for x in pkgdata['content']]
    id_strings = {}
    contents.sort()
    
    # collect files
    for path in contents:
	try:
	    exist = os.lstat(path)
	except OSError:
	    continue # skip file
	lpath = path
	arcname = path[1:] # remove trailing /
        ftype = pkgdata['content'][path]
        if str(ftype) == '0': ftype = 'dir' # force match below, '0' means databases without ftype
        if 'dir' == ftype and \
	    not stat.S_ISDIR(exist.st_mode) and \
	    os.path.isdir(lpath): # workaround for directory symlink issues
	    lpath = os.path.realpath(lpath)
        
	tarinfo = tar.gettarinfo(lpath, str(arcname)) # FIXME: casting to str() cause of python <2.5.1 bug
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
    
    # appending xpak metadata
    if etpConst['gentoo-compat']:
        import xpak
        from portageTools import getPortageAppDbPath
        dbdir = getPortageAppDbPath()+"/"+pkgcat+"/"+pkgname+"/"
        if os.path.isdir(dbdir):
            tbz2 = xpak.tbz2(dirpath)
            tbz2.recompose(dbdir)

    # appending entropy metadata
    dbpath = etpConst['packagestmpdir']+"/"+str(getRandomNumber())
    while os.path.isfile(dbpath):
        dbpath = etpConst['packagestmpdir']+"/"+str(getRandomNumber())
    # create db
    mydbconn = databaseTools.openGenericDatabase(dbpath)
    mydbconn.initializeDatabase()
    mydbconn.addPackage(pkgdata, revision = pkgdata['revision'])
    mydbconn.closeDB()
    aggregateEdb(tbz2file = dirpath, dbfile = dbpath)

    if os.path.isfile(dirpath):
	return dirpath
    else:
	return None

def appendXpak(tbz2file, atom):
    import xpak
    from portageTools import getPortageAppDbPath
    dbdir = getPortageAppDbPath()+"/"+atom+"/"
    if os.path.isdir(dbdir):
        tbz2 = xpak.tbz2(tbz2file)
        tbz2.recompose(dbdir)
    return tbz2file

# This function extracts all the info from a .tbz2 file and returns them
def extractPkgData(package, etpBranch = etpConst['branch'], silent = False):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"extractPkgData: called -> package: "+str(package))
    data = {}

    from portageTools import synthetizeRoughDependencies, getPackagesInSystem, getConfigProtectAndMask, getThirdPartyMirrors

    info_package = bold(os.path.basename(package))+": "

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package name/version..."),back = True)
    tbz2File = package
    package = package.split(".tbz2")[0]
    package = remove_entropy_revision(package)
    package = remove_tag(package)
    
    # FIXME: deprecated - will be removed soonly
    if package.split("-")[len(package.split("-"))-1].startswith("t"):
        package = '-t'.join(package.split("-t")[:-1])
    
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
    data['name'] = pkgname
    data['version'] = pkgver

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package md5..."),back = True)
    # .tbz2 md5
    data['digest'] = md5sum(tbz2File)

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package mtime..."),back = True)
    # .tbz2 md5
    data['datecreation'] = str(getFileUnixMtime(tbz2File))
    
    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package size..."),back = True)
    # .tbz2 byte size
    data['size'] = str(os.stat(tbz2File)[6])
    
    if not silent: print_info(yellow(" * ")+red(info_package+"Unpacking package data..."),back = True)
    # unpack file
    tbz2TmpDir = etpConst['packagestmpdir']+"/"+data['name']+"-"+data['version']+"/"
    extractXpak(tbz2File,tbz2TmpDir)

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package CHOST..."),back = True)
    # Fill chost
    f = open(tbz2TmpDir+dbCHOST,"r")
    data['chost'] = f.readline().strip()
    f.close()

    if not silent: print_info(yellow(" * ")+red(info_package+"Setting package branch..."),back = True)
    data['branch'] = etpBranch

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package description..."),back = True)
    # Fill description
    data['description'] = ""
    try:
        f = open(tbz2TmpDir+dbDESCRIPTION,"r")
        data['description'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package homepage..."),back = True)
    # Fill homepage
    data['homepage'] = ""
    try:
        f = open(tbz2TmpDir+dbHOMEPAGE,"r")
        data['homepage'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package slot information..."),back = True)
    # fill slot, if it is
    data['slot'] = ""
    try:
        f = open(tbz2TmpDir+dbSLOT,"r")
        data['slot'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package eclasses information..."),back = True)
    # fill eclasses list
    data['eclasses'] = []
    try:
        f = open(tbz2TmpDir+dbINHERITED,"r")
        data['eclasses'] = f.readline().strip().split()
        f.close()
    except IOError:
        pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package needed libraries information..."),back = True)
    # fill needed list
    data['needed'] = set()
    try:
        f = open(tbz2TmpDir+dbNEEDED,"r")
	lines = f.readlines()
	f.close()
	for line in lines:
	    line = line.strip()
	    if line:
	        needed = line.split()
		if len(needed) == 2:
		    libs = needed[1].split(",")
		    for lib in libs:
			if (lib.find(".so") != -1):
			    data['needed'].add(lib)
    except IOError:
        pass
    data['needed'] = list(data['needed'])

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package content..."),back = True)
    # dbCONTENTS
    data['content'] = {}
    try:
        f = open(tbz2TmpDir+dbCONTENTS,"r")
        content = f.readlines()
        f.close()
	outcontent = set()
	for line in content:
	    line = line.strip().split()
            try:
                datatype = line[0]
                datafile = line[1:]
                if datatype == 'obj':
                    datafile = datafile[:-2]
                    datafile = ' '.join(datafile)
                elif datatype == 'dir':
                    datafile = ' '.join(datafile)
                elif datatype == 'sym':
                    datafile = datafile[:-3]
                    datafile = ' '.join(datafile)
                else:
                    print "unhandled !!!!!!!",datafile
                    raise Exception
                outcontent.add((datafile,datatype))
            except:
                pass
	
        # convert to plain str() since it's that's used by portage
        # when portage will use utf, test utf-8 encoding
	_outcontent = set()
	for i in outcontent:
            i = list(i)
            datatype = i[1]
            try:
                i[0] = i[0].encode(getfilesystemencoding())
            except:  # default encoding failed
                try:
                    i[0] = i[0].decode("latin1") # try to convert to latin1 and then back to sys.getfilesystemencoding()
                    i[0] = i[0].encode(getfilesystemencoding())
                except:
                    print "DEBUG: cannot encode into filesystem encoding -> "+str(i[0])
                    continue
            _outcontent.add((i[0],i[1]))
        outcontent = list(_outcontent)
        outcontent.sort()
	for i in outcontent:
            data['content'][str(i[0])] = i[1]
	
    except IOError:
        pass

    # files size on disk
    if (data['content']):
	data['disksize'] = 0
	for file in data['content']:
	    try:
		size = os.stat(file)[6]
		data['disksize'] += size
	    except:
		pass
    else:
	data['disksize'] = 0

    # [][][] Kernel dependent packages hook [][][]
    data['versiontag'] = ''
    kernelDependentModule = False
    kernelItself = False
    for file in data['content']:
	if file.find("/lib/modules/") != -1:
	    kernelDependentModule = True
	    # get the version of the modules
	    kmodver = file.split("/lib/modules/")[1]
	    kmodver = kmodver.split("/")[0]

	    lp = kmodver.split("-")[len(kmodver.split("-"))-1]
	    if lp.startswith("r"):
	        kname = kmodver.split("-")[len(kmodver.split("-"))-2]
	        kver = kmodver.split("-")[0]+"-"+kmodver.split("-")[len(kmodver.split("-"))-1]
	    else:
	        kname = kmodver.split("-")[len(kmodver.split("-"))-1]
	        kver = kmodver.split("-")[0]
	    break
    # validate the results above
    if (kernelDependentModule):
	matchatom = "linux-"+kname+"-"+kver
	if (matchatom == data['name']+"-"+data['version']):
	    # discard, it's the kernel itself, add other deps instead
	    kernelItself = True
	    kernelDependentModule = False

    # add strict kernel dependency
    # done below
    
    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package download URL..."),back = True)
    # Fill download relative URI
    if (kernelDependentModule):
	data['versiontag'] = kmodver
	# force slot == tag:
	data['slot'] = kmodver # if you change this behaviour, you must change "reagent update" and "equo database gentoosync" consequentially
	versiontag = "#"+data['versiontag']
    else:
	versiontag = ""
    # remove etpConst['product'] from etpConst['binaryurirelativepath']
    downloadrelative = etpConst['binaryurirelativepath'][len(etpConst['product'])+1:]
    data['download'] = downloadrelative+data['branch']+"/"+data['name']+"-"+data['version']+versiontag+".tbz2"

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package counter..."),back = True)
    # Fill counter
    f = open(tbz2TmpDir+dbCOUNTER,"r")
    data['counter'] = f.readline().strip()
    f.close()

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package category..."),back = True)
    # Fill category
    f = open(tbz2TmpDir+dbCATEGORY,"r")
    data['category'] = f.readline().strip()
    f.close()
    
    data['trigger'] = ""
    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package external trigger availability..."),back = True)
    if os.path.isfile(etpConst['triggersdir']+"/"+data['category']+"/"+data['name']+"/"+etpConst['triggername']):
        f = open(etpConst['triggersdir']+"/"+data['category']+"/"+data['name']+"/"+etpConst['triggername'],"rb")
        f.seek(0,2)
        size = f.tell()
        f.seek(0)
	data['trigger'] = f.read(size)
        f.close()

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package CFLAGS..."),back = True)
    # Fill CFLAGS
    data['cflags'] = ""
    try:
        f = open(tbz2TmpDir+dbCFLAGS,"r")
        data['cflags'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package CXXFLAGS..."),back = True)
    # Fill CXXFLAGS
    data['cxxflags'] = ""
    try:
        f = open(tbz2TmpDir+dbCXXFLAGS,"r")
        data['cxxflags'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package License information..."),back = True)
    # Fill license
    data['license'] = []
    try:
        f = open(tbz2TmpDir+dbLICENSE,"r")
	# strip away || ( )
	tmpLic = f.readline().strip().split()
	f.close()
	for x in tmpLic:
	    if x:
		if (not x.startswith("|")) and (not x.startswith("(")) and (not x.startswith(")")):
		    data['license'].append(x)
	data['license'] = ' '.join(data['license'])
    except IOError:
	data['license'] = ""
        pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package USE flags..."),back = True)
    # Fill USE
    data['useflags'] = []
    f = open(tbz2TmpDir+dbUSE,"r")
    tmpUSE = f.readline().strip()
    f.close()

    try:
        f = open(tbz2TmpDir+dbIUSE,"r")
        tmpIUSE = f.readline().strip().split()
        f.close()
    except IOError:
        tmpIUSE = []

    PackageFlags = []
    for x in tmpUSE.split():
	if (x):
	    PackageFlags.append(x)

    for i in tmpIUSE:
	try:
	    PackageFlags.index(i)
	    data['useflags'].append(i)
	except:
	    data['useflags'].append("-"+i)

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package provide content..."),back = True)
    # Fill Provide
    data['provide'] = []
    try:
        f = open(tbz2TmpDir+dbPROVIDE,"r")
        provide = f.readline().strip()
        f.close()
	if (provide):
	    provide = provide.split()
	    for x in provide:
		data['provide'].append(x)
    except:
        pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package sources information..."),back = True)
    # Fill sources
    data['sources'] = []
    try:
        f = open(tbz2TmpDir+dbSRC_URI,"r")
	sources = f.readline().strip().split()
        f.close()
	tmpData = []
	cnt = -1
	skip = False
	data['sources'] = []
	
	for source in sources:
	    cnt += +1
	    if source.endswith("?"):
		# it's an use flag
		source = source[:len(source)-1]
		direction = True
		if source.startswith("!"):
		    direction = False
		    source = source[1:]
		# now get the useflag
		useflag = False
		try:
		    data['useflags'].index(source)
		    useflag = True
		except:
		    pass
		
		
		if (useflag) and (direction): # useflag is enabled and it's asking for sources or useflag is not enabled and it's not not (= True) asking for sources
		    # ack parsing from ( to )
		    skip = False
		elif (useflag) and (not direction):
		    # deny parsing from ( to )
		    skip = True
		elif (not useflag) and (direction):
		    # deny parsing from ( to )
		    skip = True
		else:
		    # ack parsing from ( to )
		    skip = False

	    elif source.startswith(")"):
		# reset skip
		skip = False

	    elif (not source.startswith("(")):
		if (not skip):
		    data['sources'].append(source)
    
    except IOError:
	pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package mirrors list..."),back = True)
    # manage data['sources'] to create data['mirrorlinks']
    # =mirror://openoffice|link1|link2|link3
    data['mirrorlinks'] = []
    for i in data['sources']:
        if i.startswith("mirror://"):
            # parse what mirror I need
            mirrorURI = i.split("/")[2]
            mirrorlist = getThirdPartyMirrors(mirrorURI)
            data['mirrorlinks'].append([mirrorURI,mirrorlist]) # mirrorURI = openoffice and mirrorlist = [link1, link2, link3]


    if not silent: print_info(yellow(" * ")+red(info_package+"Getting source package supported ARCHs..."),back = True)
    # fill KEYWORDS
    data['keywords'] = []
    try:
        f = open(tbz2TmpDir+dbKEYWORDS,"r")
        cnt = f.readline().strip().split()
	for i in cnt:
	    if i:
		data['keywords'].append(i)
        f.close()
    except IOError:
	pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package supported ARCHs..."),back = True)
    
    # fill ARCHs
    kwords = data['keywords']
    _kwords = []
    for i in kwords:
	if i.startswith("~"):
	    i = i[1:]
	_kwords.append(i)
    data['binkeywords'] = []
    for i in etpConst['supportedarchs']:
	try:
	    x = _kwords.index(i)
	    data['binkeywords'].append(i)
	except:
	    pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package dependencies..."),back = True)
    # Fill dependencies
    # to fill dependencies we use *DEPEND files
    f = open(tbz2TmpDir+dbRDEPEND,"r")
    roughDependencies = f.readline().strip()
    f.close()
    if (not roughDependencies):
        f = open(tbz2TmpDir+dbDEPEND,"r")
        roughDependencies = f.readline().strip()
        f.close()
    f = open(tbz2TmpDir+dbPDEPEND,"r")
    roughDependencies += " "+f.readline().strip()
    f.close()
    roughDependencies = roughDependencies.split()
    
    # variables filled
    # data['dependencies'], data['conflicts']
    deps,conflicts = synthetizeRoughDependencies(roughDependencies,' '.join(PackageFlags))
    data['dependencies'] = []
    for i in deps.split():
	data['dependencies'].append(i)
    data['conflicts'] = []
    for i in conflicts.split():
	# check if i == PROVIDE
	if i not in data['provide']: # we handle these conflicts using emerge, so we can just filter them out
	    data['conflicts'].append(i)
    
    if (kernelDependentModule):
	# add kname to the dependency
	data['dependencies'].append("=sys-kernel/linux-"+kname+"-"+kver)

    if (kernelItself):
	# it's the kernel, add dependency on all tagged packages
	try:
	    data['dependencies'].append("=sys-kernel/linux-"+kname+"-modules-"+kver)
	except:
	    pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting System package List..."),back = True)
    # write only if it's a systempackage
    data['systempackage'] = ''
    systemPackages = getPackagesInSystem()
    for x in systemPackages:
	x = dep_getkey(x)
	y = data['category']+"/"+data['name']
	if x == y:
	    # found
	    data['systempackage'] = "xxx"
	    break

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting CONFIG_PROTECT/CONFIG_PROTECT_MASK List..."),back = True)
    # write only if it's a systempackage
    protect, mask = getConfigProtectAndMask()
    data['config_protect'] = protect
    data['config_protect_mask'] = mask
    
    # fill data['messages']
    # etpConst['logdir']+"/elog"
    if not os.path.isdir(etpConst['logdir']+"/elog"):
        os.makedirs(etpConst['logdir']+"/elog")
    data['messages'] = []
    if os.path.isdir(etpConst['logdir']+"/elog"):
        elogfiles = os.listdir(etpConst['logdir']+"/elog")
	myelogfile = data['category']+":"+data['name']+"-"+data['version']
	foundfiles = []
	for file in elogfiles:
	    if file.startswith(myelogfile):
		foundfiles.append(file)
	if foundfiles:
	    elogfile = foundfiles[0]
	    if len(foundfiles) > 1:
		# get the latest
		mtimes = []
		for file in foundfiles:
		    mtimes.append((getFileUnixMtime(etpConst['logdir']+"/elog/"+file),file))
		mtimes.sort()
		elogfile = mtimes[len(mtimes)-1][1]
	    messages = extractElog(etpConst['logdir']+"/elog/"+elogfile)
	    for message in messages:
		out = re.subn("emerge","equo install",message)
		message = out[0]
		data['messages'].append(message)
    else:
	if not silent: print_warning(red(etpConst['logdir']+"/elog")+" not set, have you configured make.conf properly?")

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting Entropy API version..."),back = True)
    # write API info
    data['etpapi'] = etpConst['etpapi']
    
    # removing temporary directory
    os.system("rm -rf "+tbz2TmpDir)

    if not silent: print_info(yellow(" * ")+red(info_package+"Done"),back = True)
    return data

def collectLinkerPaths():
    ldpaths = set()
    try:
        f = open("/etc/ld.so.conf","r")
        paths = f.readlines()
        for path in paths:
            if path.strip():
                if path[0] == "/":
                    ldpaths.add(os.path.normpath(path.strip()))
        f.close()
    except:
        pass
    return ldpaths

def listToUtf8(mylist):
    mynewlist = []
    for item in mylist:
        try:
            mynewlist.append(item.decode("utf8"))
        except UnicodeDecodeError:
            try:
                mynewlist.append(item.decode("latin1").encode("utf8"))
            except:
                raise
    return mynewlist