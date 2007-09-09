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
import random
import commands

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

def applicationLockCheck(option = None):
    if (etpConst['applicationlock']):
	print_error(red("Another instance of Equo is running. Action: ")+bold(str(option))+red(" denied."))
	print_error(red("If I am lying (maybe). Please remove ")+bold(etpConst['pidfile']))
	sys.exit(10)

def getRandomNumber():
    return int(str(random.random())[2:7])

def countdown(secs=5,what="Counting...", back = False):
    import time
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
    
def unpackGzip(gzipfilepath):
    import gzip
    filepath = gzipfilepath[:len(gzipfilepath)-3] # remove .gz
    file = open(filepath,"wb")
    filegz = gzip.GzipFile(gzipfilepath,"rb")
    filecont = filegz.readlines()
    filegz.close()
    file.writelines(filecont)
    file.flush()
    file.close()
    del filecont
    return filepath

def extractXpak(tbz2File,tmpdir = None):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"unpackTbz2: called -> "+tbz2File)
    import xpak
    if tmpdir is None:
	tmpdir = etpConst['packagestmpdir']+"/"+tbz2File.split("/")[len(tbz2File.split("/"))-1].split(".tbz2")[0]+"/"
    if (not tmpdir.endswith("/")):
	tmpdir += "/"
    tbz2 = xpak.tbz2(tbz2File)
    if os.path.isdir(tmpdir):
	spawnCommand("rm -rf "+tmpdir+"*")
    tbz2.decompose(tmpdir)
    return tmpdir

# This function creates the .hash file related to the given package file
# @returns the complete hash file path
# FIXME: add more hashes, SHA1 for example
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

def ververify(myverx, silent=1):
    myver = myverx[:]
    if myver.endswith("*"):
	myver = myver[:len(myver)-1]
    if ver_regexp.match(myver):
	return 1
    else:
	if not silent:
	    print "!!! syntax error in version: %s" % myver
	return 0

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
    myparts = mypkg.split('-')
    for x in myparts:
	if ververify(x):
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
	return None
    retval.extend(p_split)
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

def dep_striptag(mydepx):
    mydep = mydepx[:]
    if not (isjustname(mydep)):
	if mydep.split("-")[len(mydep.split("-"))-1].startswith("t"): # tag -> remove
	    tag = mydep.split("-")[len(mydep.split("-"))-1]
	    mydep = mydep[:len(mydep)-len(tag)-1]
    return mydep

def istagged(mydepx):
    x = dep_striptag(mydepx)
    if x != mydepx:
	return 1
    return 0

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
    mydep = mydepx[:]
    mydep = dep_striptag(mydep)
    
    mydep = dep_getcpv(mydep)
    if mydep and isspecific(mydep):
	mysplit = catpkgsplit(mydep)
	if not mysplit:
	    return mydep
	return mysplit[0] + "/" + mysplit[1]
    else:
	return mydep

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
    return mydep

def removePackageOperators(atom):
    if atom.startswith(">") or atom.startswith("<"):
	atom = atom[1:]
    if atom.startswith("="):
	atom = atom[1:]
    if atom.startswith("~"):
	atom = atom[1:]
    return atom

# Version compare function taken from portage_versions.py
# portage_versions.py -- core Portage functionality
# Copyright 1998-2006 Gentoo Foundation
ver_regexp = re.compile("^(cvs\\.)?(\\d+)((\\.\\d+)*)([a-z]?)((_(pre|p|beta|alpha|rc)\\d*)*)(-r(\\d+))?$")
suffix_regexp = re.compile("^(alpha|beta|rc|pre|p)(\\d*)$")
suffix_value = {"pre": -2, "p": 0, "alpha": -4, "beta": -3, "rc": -1}
endversion_keys = ["pre", "p", "alpha", "beta", "rc"]
def compareVersions(ver1, ver2, silent=1):
	
	if ver1 == ver2:
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
			return -1
		elif len(list2) <= i:
			return 1
		elif list1[i] != list2[i]:
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
			return suffix_value[s1[0]] - suffix_value[s2[0]]
		if s1[1] != s2[1]:
			# it's possible that the s(1|2)[1] == ''
			# in such a case, fudge it.
			try:			r1 = int(s1[1])
			except ValueError:	r1 = 0
			try:			r2 = int(s2[1])
			except ValueError:	r2 = 0
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
	return r1 - r2

'''
   @description: reorder a version list
   @input versionlist: a list
   @output: the ordered list
   FIXME: using Bubble Sorting is not the fastest way
'''
def getNewerVersion(InputVersionlist):
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
    return versionlist

'''
   @description: reorder a list of strings converted into ascii
   @input versionlist: a string list
   @output: the ordered string list
'''
def getNewerVersionTag(InputVersionlist):
    rc = False
    versionlist = InputVersionlist[:]
    while not rc:
	change = False
        for x in range(len(versionlist)):
	    pkgA = versionlist[x]
	    if (not pkgA):
		pkgA = "0"
	    try:
	        pkgB = versionlist[x+1]
		if (not pkgB):
		    pkgB = "0"
	    except:
	        pkgB = "0"
	    # translate pkgA into numeric string
	    if pkgA < pkgB:
	        # swap positions
	        versionlist[x] = pkgB
	        versionlist[x+1] = pkgA
		change = True
	if (not change):
	    rc = True
    return versionlist

def isnumber(x):
    try:
	t = int(x)
	return True
    except:
	return False

# this functions removes duplicates without breaking the list order
# nameslist: a list that contains duplicated names
# @returns filtered list
def filterDuplicatedEntries(alist):
    set = {}
    return [set.setdefault(e,e) for e in alist if e not in set]


import string

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
def extactDuplicatedEntries(inputlist):
    filteredList = filterDuplicatedEntries(inputlist)
    if len(inputlist) == len(filteredList):
	return []
    else:
	newinputlist = inputlist[:]
	for x in inputlist:
	    try:
		while 1:
		    filteredList.remove(x)
		    newinputlist.remove(x)
	    except:
		pass
	return newinputlist
	

# Tool to run commands
def spawnCommand(command, redirect = None):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"spawnCommand: called for: "+command)
    if redirect is not None:
        command += " "+redirect
    rc = os.system(command)
    return rc

def extractFTPHostFromUri(uri):
    ftphost = uri.split("ftp://")[len(uri.split("ftp://"))-1]
    ftphost = ftphost.split("@")[len(ftphost.split("@"))-1]
    ftphost = ftphost.split("/")[0]
    ftphost = ftphost.split(":")[0]
    return ftphost

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

    for dir in toCleanDirs:
        print_info(red(" * ")+"Cleaning "+darkgreen(dir)+" directory...", back = True)
	if os.path.isdir(dir):
	    dircontent = os.listdir(dir)
	    if dircontent != []:
	        for data in dircontent:
		    spawnCommand("rm -rf "+dir+"/"+data)
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