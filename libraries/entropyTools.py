#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for all the handlers applications

    Copyright (C) 2007-2008 Fabio Erculiani

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

from outputTools import *
from entropyConstants import *
import exceptionTools
import re
import threading, time

# Logging initialization
import logTools
entropyLog = logTools.LogFile(level=etpConst['entropyloglevel'],filename = etpConst['entropylogfile'], header = "[Entropy]")

global __etp_debug
__etp_debug = False
def enableDebug():
    import pdb
    pdb.set_trace()

def getDebug():
    return __etp_debug

def isRoot():
    if (etpConst['uid'] == 0):
        return True
    return False

class TimeScheduled(threading.Thread):
    def __init__(self, function, delay, dictData = {}):
        threading.Thread.__init__(self)
        self.function = function
        self.delay = delay
        self.data = dictData
    def run(self):
        self.alive = 1
        while self.alive:
            if self.data:
                self.function(self.data)
            else:
                self.function()
	    try:
                time.sleep(self.delay)
	    except:
		pass
    def kill(self):
        self.alive = 0

class parallelTask(threading.Thread):
    def __init__(self, function, dictData = {}):
        threading.Thread.__init__(self)
        self.function = function
        self.data = dictData.copy()

    def parallel_wait(self):
        while len(threading.enumerate()) > etpSys['maxthreads']:
            time.sleep(0.001)

    def run(self):
        if self.data:
            self.function(self.data)
        else:
            self.function()
    '''
    def destroy(self):
        del self.function
    '''

def printException(returndata = False):
    import traceback
    if not returndata: traceback.print_exc()
    data = []
    tb = sys.exc_info()[2]
    while 1:
        if not tb.tb_next:
            break
        tb = tb.tb_next
    stack = []
    stack.append(tb.tb_frame)
    #if not returndata: print
    for frame in stack:
        if not returndata:
            print
            print "Frame %s in %s at line %s" % (frame.f_code.co_name,
                                             frame.f_code.co_filename,
                                             frame.f_lineno)
        else:
            data.append("Frame %s in %s at line %s" % (frame.f_code.co_name,
                                             frame.f_code.co_filename,
                                             frame.f_lineno))
        for key, value in frame.f_locals.items():
            if not returndata:
                print "\t%20s = " % key,
            else:
                data.append("\t%20s = " % key,)
            try:
                if not returndata:
                    print value
                else:
                    data.append(value)
            except:
                if not returndata: print "<ERROR WHILE PRINTING VALUE>"
    return data

# Get the content of an online page
# @returns content: if the file exists
# @returns False: if the file is not found
def get_remote_data(url):

    import socket
    import urllib2
    socket.setdefaulttimeout(60)
    # now pray the server
    try:
        if etpConst['proxy']:
            proxy_support = urllib2.ProxyHandler(etpConst['proxy'])
            opener = urllib2.build_opener(proxy_support)
            urllib2.install_opener(opener)
        item = urllib2.urlopen(url)
        result = item.readlines()
        item.close()
        del item
        if (not result):
            socket.setdefaulttimeout(2)
            return False
        socket.setdefaulttimeout(2)
        return result
    except:
        socket.setdefaulttimeout(2)
        return False

def islive():
    if not os.path.isfile("/proc/cmdline"):
        return False
    f = open("/proc/cmdline")
    cmdline = f.readline().strip().split()
    f.close()
    if "cdroot" in cmdline:
        return True
    return False

def ebeep(count = 5):
    for x in range(count):
        os.system("sleep 0.35; echo -ne \"\a\"; sleep 0.35")

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
            sys.stdout.write(red(">> ")+what)
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

def md5sum_directory(directory):
    if not os.path.isdir(directory):
        raise exceptionTools.DirectoryNotFound("DirectoryNotFound: directory just does not exist.")
    myfiles = os.listdir(directory)
    if not myfiles:
        return "0" # no files means 0
    import md5
    m = md5.new()
    for currentdir,subdirs,files in os.walk(directory):
        for myfile in files:
            myfile = os.path.join(currentdir,myfile)
            readfile = file(myfile)
            block = readfile.read(1024)
            while block:
                m.update(block)
                block = readfile.read(1024)
    return m.hexdigest()

def unpackGzip(gzipfilepath):
    import gzip
    filepath = gzipfilepath[:-3] # remove .gz
    item = open(filepath,"wb")
    filegz = gzip.GzipFile(gzipfilepath,"rb")
    chunk = filegz.read(8192)
    while chunk:
        item.write(chunk)
        chunk = filegz.read(8192)
    filegz.close()
    item.flush()
    item.close()
    return filepath

def unpackBzip2(bzip2filepath):
    import bz2
    filepath = bzip2filepath[:-4] # remove .bz2
    item = open(filepath,"wb")
    filebz2 = bz2.BZ2File(bzip2filepath,"rb")
    chunk = filebz2.read(8192)
    while chunk:
        item.write(chunk)
        chunk = filebz2.read(8192)
    filebz2.close()
    item.flush()
    item.close()
    return filepath

def extractXpak(tbz2file,tmpdir = None):
    # extract xpak content
    xpakpath = suckXpak(tbz2file, etpConst['packagestmpdir'])
    return unpackXpak(xpakpath,tmpdir)

def readXpak(tbz2file):
    xpakpath = suckXpak(tbz2file, etpConst['entropyunpackdir'])
    f = open(xpakpath,"rb")
    data = f.read()
    f.close()
    os.remove(xpakpath)
    return data

def unpackXpak(xpakfile, tmpdir = None):
    try:
        import etpXpak
        import shutil
        if tmpdir is None:
            tmpdir = etpConst['packagestmpdir']+"/"+os.path.basename(xpakfile)[:-5]+"/"
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir,True)
        os.makedirs(tmpdir)
        xpakdata = etpXpak.getboth(xpakfile)
        etpXpak.xpand(xpakdata,tmpdir)
        del xpakdata
        try:
            os.remove(xpakfile)
        except:
            pass
    except:
        return None
    return tmpdir


def suckXpak(tbz2file, outputpath):

    xpakpath = outputpath+"/"+os.path.basename(tbz2file)[:-5]+".xpak"
    old = open(tbz2file,"rb")
    db = open(xpakpath,"wb")
    db_tmp = open(xpakpath+".reverse","wb")
    allowWrite = False

    # position old to the end
    old.seek(0,2)
    # read backward until we find
    bytes = old.tell()
    counter = bytes

    while counter >= 0:
        old.seek(counter-bytes,2)
        byte = old.read(1)
        if byte == "P" or byte == "K":
            old.seek(counter-bytes-7,2)
            chunk = old.read(7)+byte
            if chunk == "XPAKPACK":
                allowWrite = False
                db_tmp.write(chunk[::-1])
                break
            elif chunk == "XPAKSTOP":
                allowWrite = True
                old.seek(counter-bytes,2)
        if (allowWrite):
            db_tmp.write(byte)
        counter -= 1

    db_tmp.flush()
    db_tmp.close()
    db_tmp = open(xpakpath+".reverse","rb")
    # now reverse from db_tmp to db
    db_tmp.seek(0,2)
    bytes = db_tmp.tell()
    counter = bytes
    while counter >= 0:
        db_tmp.seek(counter-bytes,2)
        byte = db_tmp.read(1)
        db.write(byte)
        counter -= 1

    db.flush()
    db.close()
    db_tmp.close()
    old.close()
    try:
        os.remove(xpakpath+".reverse")
    except OSError:
        pass
    return xpakpath

def aggregateEdb(tbz2file,dbfile):
    f = open(tbz2file,"abw")
    f.write(etpConst['databasestarttag'])
    g = open(dbfile,"rb")
    chunk = g.read(8192)
    while chunk:
        f.write(chunk)
        chunk = g.read(8192)
    g.close()
    f.flush()
    f.close()

def extractEdb(tbz2file, dbpath = None):
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
    md5hash = md5sum(tbz2filepath)
    hashfile = tbz2filepath+etpConst['packageshashfileext']
    f = open(hashfile,"w")
    tbz2name = os.path.basename(tbz2filepath)
    f.write(md5hash+"  "+tbz2name+"\n")
    f.flush()
    f.close()
    return hashfile

def compareMd5(filepath,checksum):
    checksum = str(checksum)
    result = md5sum(filepath)
    result = str(result)
    if checksum == result:
        return True
    return False

def md5string(string):
    import md5
    m = md5.new()
    m.update(string)
    return m.hexdigest()

# used to properly sort /usr/portage/profiles/updates files
def sortUpdateFiles(update_list):
    sort_dict = {}
    # sort per year
    for item in update_list:
        # get year
        year = item.split("-")[1]
        if sort_dict.has_key(year):
            sort_dict[year].append(item)
        else:
            sort_dict[year] = []
            sort_dict[year].append(item)
    new_list = []
    keys = sort_dict.keys()
    keys.sort()
    for key in keys:
        sort_dict[key].sort()
        new_list += sort_dict[key]
    del sort_dict
    return new_list

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
    mydep = remove_tag(mydep)

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

    colon = dep.rfind(":")
    if colon != -1:
	mydep = dep[colon+1:]
	rslt = remove_tag(mydep)
	return rslt

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
    dep = removePackageOperators(mydep)
    operators = mydep[:-len(dep)]
    colon = dep.rfind("~")
    if colon != -1:
	mystring = operators+dep[:colon]
        return mystring
    return mydep

def dep_get_entropy_revision(mydep):
    dep = removePackageOperators(mydep)
    colon = mydep.rfind("~")
    if colon != -1:
        myrev = mydep[colon+1:]
        try:
            myrev = int(myrev)
        except ValueError:
            return None
        return myrev
    return None

def dep_get_match_in_repos(mydep):
    colon = mydep.rfind("@")
    if colon != -1:
        mydata = mydep[colon+1:]
        mydata = mydata.split(",")
        if not mydata:
            mydata = None
        return mydep[:colon],mydata
    else:
        return mydep,None

def dep_gettag(dep):

    """
    Retrieve the slot on a depend.

    Example usage:
        >>> dep_gettag('app-misc/test#2.6.23-sabayon-r1')
        '2.6.23-sabayon-r1'

    """

    colon = dep.rfind("#")
    if colon != -1:
        mydep = dep[colon+1:]
        rslt = remove_slot(mydep)
        return rslt
    return None


def removePackageOperators(atom):

    original = atom
    if atom[0] == ">" or atom[0] == "<":
        atom = atom[1:]
    if atom[0] == "=":
        atom = atom[1:]
    if atom[0] == "~":
        atom = atom[1:]

    return atom

# Version compare function taken from portage_versions.py
# portage_versions.py -- core Portage functionality
# Copyright 1998-2006 Gentoo Foundation
ver_regexp = re.compile("^(cvs\\.)?(\\d+)((\\.\\d+)*)([a-z]?)((_(pre|p|beta|alpha|rc)\\d*)*)(-r(\\d+))?$")
suffix_regexp = re.compile("^(alpha|beta|rc|pre|p)(\\d*)$")
suffix_value = {"pre": -2, "p": 0, "alpha": -4, "beta": -3, "rc": -1}
endversion_keys = ["pre", "p", "alpha", "beta", "rc"]
def compareVersions(ver1, ver2):
	
	if ver1 == ver2:
		return 0
	#mykey=ver1+":"+ver2
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
   @description: compare two lists composed by [version,tag,revision] and [version,tag,revision]
   			if listA > listB --> positive number
			if listA == listB --> 0
			if listA < listB --> negative number	
   @input package: listA[version,tag,rev] and listB[version,tag,rev]
   @output: integer number
'''
def entropyCompareVersions(listA,listB):
    if len(listA) != 3 or len(listB) != 3:
        raise exceptionTools.InvalidDataType("InvalidDataType: listA or listB are not properly formatted.")

    # if both are tagged, check tag first
    rc = 0
    if listA[1] and listB[1]:
        rc = cmp(listA[1],listB[1])
    if rc == 0:
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
def getNewerVersion(versions):

    if len(versions) == 1:
        return versions

    versionlist = versions[:]

    rc = False
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
    descendent order
    versions = [(version,tag,revision),(version,tag,revision)]
'''
def getEntropyNewerVersion(versions):

    if len(versions) == 1:
        return versions

    myversions = versions[:]
    # ease the work

    rc = False
    while not rc:
        change = False
        for x in range(len(myversions)):
            pkgA = myversions[x]
            try:
                pkgB = myversions[x+1]
            except:
                pkgB = ("0","",0)
            result = entropyCompareVersions(pkgA,pkgB)
            #print pkgA + "<->" +pkgB +" = " + str(result)
            if result < 0:
                # swap positions
                myversions[x] = pkgB
                myversions[x+1] = pkgA
                change = True
        if (not change):
            rc = True

    return myversions

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
        del t
	return True
    except:
	return False


def istextfile(filename, blocksize = 512):
    f = open(filename)
    r = istext(f.read(blocksize))
    f.close()
    return r

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
    mydata = {}
    return [mydata.setdefault(e,e) for e in alist if e not in mydata]


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
        for d in range(len(x)):
            if x[d] in mappings.keys():
                if x[d] in ("'", '"'):
                    if d+1<len(x):
                        if x[d+1]!=x[d]:
                            tmpstr+=mappings[x[d]]
                    else:
                        tmpstr+=mappings[x[d]]
                else:
                   tmpstr+=mappings[x[d]]
            else:
                tmpstr+=x[d]
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
	z = mycache.get(x)
	if z:
	    newlist.add(x)
	    continue
	mycache[x] = 1
    return newlist
	

# Tool to run commands
def spawnCommand(command, redirect = None):
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

# OLD tar.bz2 uncompress function...
def compat_uncompressTarBz2(filepath, extractPath = None):

    cmd = "tar xjf "+filepath+" -C "+extractPath+" &> /dev/null"
    rc = os.system(cmd)
    if rc != 0:
        return -1
    return 0

# tar* uncompress function...
def uncompressTarBz2(filepath, extractPath = None, catchEmpty = False):

    import tarfile

    if extractPath is None:
        extractPath = os.path.dirname(filepath)
    if not os.path.isfile(filepath):
        raise exceptionTools.FileNotFound('archive does not exist')

    ### XXX dirty bastard workaround for buggy python2.4's tarfile
    if sys.version[:3] == "2.4":
        rc = compat_uncompressTarBz2(filepath, extractPath)
        return rc

    try:
        try:
            tar = tarfile.open(filepath,"r")
        except tarfile.CompressionError:
            tar = tarfile.open(filepath,"r:bz2") # python 2.4 crashes above, so supporting only bz2
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
                tarinfo.name = tarinfo.name.encode(sys.getfilesystemencoding())
            except:  # default encoding failed
                tarinfo.name = tarinfo.name.decode("latin1") # try to convert to latin1 and then back to sys.getfilesystemencoding()
                tarinfo.name = tarinfo.name.encode(sys.getfilesystemencoding())
            tar.extract(tarinfo, extractPath.encode(sys.getfilesystemencoding()))
        del tar.members[:]

    # Reverse sort directories.
    #'''
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
        except tarfile.ExtractError:
            if tar.errorlevel > 1:
                raise
    #'''

    del directories
    tar.close()
    del tar
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

    newuri = uri.replace(ftppassword,"xxxxxxxx")
    return newuri

def getFileUnixMtime(path):
    return os.path.getmtime(path)

def getRandomTempFile():
    if not os.path.isdir(etpConst['packagestmpdir']):
        os.makedirs(etpConst['packagestmpdir'])
    path = os.path.join(etpConst['packagestmpdir'],"temp_"+str(getRandomNumber()))
    while os.path.isfile(path):
        path = os.path.join(etpConst['packagestmpdir'],"temp_"+str(getRandomNumber()))
    return path

def getFileTimeStamp(path):
    from datetime import datetime
    # used in this way for convenience
    unixtime = os.path.getmtime(path)
    humantime = datetime.fromtimestamp(unixtime)
    # format properly
    humantime = str(humantime)
    outputtime = ""
    for char in humantime:
        if char != "-" and char != " " and char != ":":
            outputtime += char
    return outputtime

def convertUnixTimeToMtime(unixtime):
    from datetime import datetime
    humantime = str(datetime.fromtimestamp(unixtime))
    outputtime = ""
    for char in humantime:
	if char != "-" and char != " " and char != ":":
	    outputtime += char
    return outputtime

def convertUnixTimeToHumanTime(unixtime):
    from datetime import datetime
    humantime = str(datetime.fromtimestamp(unixtime))
    return humantime

def getCurrentUnixTime():
    import time
    return time.time()

def convertSecondsToFancyOutput(seconds):

    mysecs = seconds
    myminutes = 0
    myhours = 0
    mydays = 0

    while mysecs >= 60:
        mysecs -= 60
        myminutes += 1

    while myminutes >= 60:
        myminutes -= 60
        myhours += 1

    while myhours >= 24:
        myhours -= 24
        mydays += 1

    output = []
    output.append(str(mysecs)+"s")
    if myminutes > 0 or myhours > 0:
        output.append(str(myminutes)+"m")
    if myhours > 0 or mydays > 0:
        output.append(str(myhours)+"h")
    if mydays > 0:
        output.append(str(mydays)+"d")
    output.reverse()
    return ':'.join(output)



# get a list, returns a sorted list
def alphaSorter(seq):
    def stripter(s, goodchrs):
        badchrs = set(s)
        for d in goodchrs:
            if d in badchrs:
                badchrs.remove(d)
        badchrs = ''.join(badchrs)
        return s.strip(badchrs)

    def chr_index(value, sortorder):
        result = []
        for d in stripter(value, order):
            dindex = sortorder.find(d)
            if dindex == -1:
                dindex = len(sortorder)+ord(d)
            result.append(dindex)
        return result

    order = ( '0123456789AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz' )
    deco = [(chr_index(a, order), a) for a in seq]
    deco.sort()
    return list(x[1] for x in deco)

# Temporary files cleaner
def cleanup(toCleanDirs = []):

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

def flatten(l, ltypes=(list, tuple)):
  i = 0
  while i < len(l):
    while isinstance(l[i], ltypes):
      if not l[i]:
        l.pop(i)
        if not len(l):
          break
      else:
        l[i:i+1] = list(l[i])
    i += 1
  return l

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

def read_repositories_conf():
    content = []
    if os.path.isfile(etpConst['repositoriesconf']):
        f = open(etpConst['repositoriesconf'])
        content = f.readlines()
        f.close()
    return content

def getRepositorySettings(repoid):
    try:
        repodata = etpRepositories[repoid].copy()
    except KeyError:
        if not etpRepositoriesExcluded.has_key(repoid):
            raise
        repodata = etpRepositoriesExcluded[repoid].copy()
    repodata['repoid'] = repoid
    # remove extra paths from database and packages
    repodata['packages'] = [x[:-len("/"+etpConst['product'])] for x in repodata['packages']]
    repodata['database'] = repodata['database'][:-len("/"+etpConst['product']+"/database/"+etpConst['currentarch'])]
    return repodata

def writeOrderedRepositoriesEntries():
    repoOrder = [x for x in etpRepositoriesOrder if not x.endswith(".tbz2")]
    content = read_repositories_conf()
    content = [x.strip() for x in content]
    repolines = [x for x in content if x.startswith("repository|") and (len(x.split("|")) == 5)]
    content = [x for x in content if x not in repolines]
    for repoid in etpRepositoriesOrder:
        # get repoid from repolines
        for x in repolines:
            repoidline = x.split("|")[1]
            if repoid == repoidline:
                content.append(x)
    _saveRepositoriesContent(content)

# etpRepositories and etpRepositoriesOrder must be already configured, see where this function is used
def saveRepositorySettings(repodata, remove = False, disable = False, enable = False):

    if repodata['repoid'].endswith(".tbz2"):
        return

    content = read_repositories_conf()
    content = [x.strip() for x in content]
    if not disable and not enable:
        content = [x for x in content if not x.startswith("repository|"+repodata['repoid'])]
        if remove:
            # also remove possible disable repo
            content = [x for x in content if not (x.startswith("#") and not x.startswith("##") and (x.find("repository|"+repodata['repoid']) != -1))]
    if not remove:

        repolines = [x for x in content if x.startswith("repository|") or (x.startswith("#") and not x.startswith("##") and (x.find("repository|") != -1))]
        content = [x for x in content if x not in repolines] # exclude lines from repolines
        # filter sane repolines lines
        repolines = [x for x in repolines if (len(x.split("|")) == 5)]
        repolines_data = {}
        repocount = 0
        for x in repolines:
            repolines_data[repocount] = {}
            repolines_data[repocount]['repoid'] = x.split("|")[1]
            repolines_data[repocount]['line'] = x
            if disable and x.split("|")[1] == repodata['repoid']:
                if not x.startswith("#"):
                    x = "#"+x
                repolines_data[repocount]['line'] = x
            elif enable and x.split("|")[1] == repodata['repoid'] and x.startswith("#"):
                repolines_data[repocount]['line'] = x[1:]
            repocount += 1

        if not disable and not enable: # so it's a add

            line = "repository|%s|%s|%s|%s#%s" % (   repodata['repoid'],
                                                    repodata['description'],
                                                    ' '.join(repodata['packages']),
                                                    repodata['database'],
                                                    repodata['dbcformat'],
                                                )

            # seek in repolines_data for a disabled entry and remove
            to_remove = set()
            for c in repolines_data:
                if repolines_data[c]['line'].startswith("#") and \
                    (repolines_data[c]['line'].find("repository|"+repodata['repoid']) != -1):
                    # then remove
                    to_remove.add(c)
            for x in to_remove:
                del repolines_data[x]

            repolines_data[repocount] = {}
            repolines_data[repocount]['repoid'] = repodata['repoid']
            repolines_data[repocount]['line'] = line

        # inject new repodata
        keys = repolines_data.keys()
        keys.sort()
        for c in keys:
            repoid = repolines_data[c]['repoid']
            # write the first
            line = repolines_data[c]['line']
            content.append(line)

    _saveRepositoriesContent(content)

def _saveRepositoriesContent(content):
    import shutil
    if os.path.isfile(etpConst['repositoriesconf']):
        if os.path.isfile(etpConst['repositoriesconf']+".old"):
            os.remove(etpConst['repositoriesconf']+".old")
        shutil.copy2(etpConst['repositoriesconf'],etpConst['repositoriesconf']+".old")
    f = open(etpConst['repositoriesconf'],"w")
    for x in content:
        f.write(x+"\n")
    f.flush()
    f.close()

def writeNewBranch(branch):

    content = read_repositories_conf()

    found = False
    new_content = []
    for line in content:
        if line.strip().startswith("branch|"):
            line = line.replace(line.strip(),"branch|"+str(branch))
            found = True
        new_content.append(line)
    if found:
        f = open(etpConst['repositoriesconf'],"w")
        f.writelines(new_content)
        f.flush()
        f.close()
    elif not new_content:
        f = open(etpConst['repositoriesconf'],"w")
        f.write("branch|"+str(branch)+"\n")
        f.flush()
        f.close()
    else:
        f = open(etpConst['repositoriesconf'],"aw")
        f.seek(0,2)
        f.write("\nbranch|"+str(branch)+"\n")
        f.flush()
        f.close()

def isEntropyTbz2(tbz2file):
    import tarfile
    if not os.path.exists(tbz2file):
        return False
    return tarfile.is_tarfile(tbz2file)

# @pkgdata: etpData mapping dictionary (retrieved from db using getPackageData())
# @dirpath: directory to save .tbz2
def quickpkg(pkgdata, dirpath, edb = True, portdbPath = None, fake = False, compression = "bz2"):

    import stat
    import tarfile
    import databaseTools

    if compression not in ("bz2","","gz"):
        compression = "bz2"

    # getting package info
    pkgtag = ''
    pkgrev = "~"+str(pkgdata['revision'])
    if pkgdata['versiontag']: pkgtag = "#"+pkgdata['versiontag']
    pkgname = pkgdata['name']+"-"+pkgdata['version']+pkgrev+pkgtag # + version + tag
    pkgcat = pkgdata['category']
    #pkgfile = pkgname+".tbz2"
    dirpath += "/"+pkgname+".tbz2"
    if os.path.isfile(dirpath):
        os.remove(dirpath)
    tar = tarfile.open(dirpath,"w:"+compression)

    if not fake:

        contents = [x for x in pkgdata['content']]
        id_strings = {}
        contents.sort()

        # collect files
        for path in contents:
            # convert back to filesystem str
            encoded_path = path
            path = path.encode('raw_unicode_escape')
            try:
                exist = os.lstat(path)
            except OSError, e:
                print e
                continue # skip file
            arcname = path[1:] # remove trailing /
            ftype = pkgdata['content'][encoded_path]
            if str(ftype) == '0': ftype = 'dir' # force match below, '0' means databases without ftype
            if 'dir' == ftype and \
                not stat.S_ISDIR(exist.st_mode) and \
                os.path.isdir(path): # workaround for directory symlink issues
                path = os.path.realpath(path)

            tarinfo = tar.gettarinfo(path, arcname)
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
        import etpXpak

        gentoo_name = remove_tag(pkgname)
        gentoo_name = remove_entropy_revision(gentoo_name)
        if portdbPath == None:
            from portageTools import getPortageAppDbPath
            dbdir = getPortageAppDbPath()+"/"+pkgcat+"/"+gentoo_name+"/"
        else:
            dbdir = portdbPath+"/"+pkgcat+"/"+gentoo_name+"/"
        if os.path.isdir(dbdir):
            tbz2 = etpXpak.tbz2(dirpath)
            tbz2.recompose(dbdir)

    if edb:
        # appending entropy metadata
        dbpath = etpConst['packagestmpdir']+"/"+str(getRandomNumber())
        while os.path.isfile(dbpath):
            dbpath = etpConst['packagestmpdir']+"/"+str(getRandomNumber())
        # create db
        mydbconn = databaseTools.openGenericDatabase(dbpath)
        mydbconn.initializeDatabase()
        mydbconn.addPackage(pkgdata, revision = pkgdata['revision'])
        mydbconn.closeDB()
        del mydbconn
        aggregateEdb(tbz2file = dirpath, dbfile = dbpath)

    if os.path.isfile(dirpath):
	return dirpath
    else:
	return None

def appendXpak(tbz2file, atom):
    import etpXpak
    from portageTools import getPortageAppDbPath
    dbdir = getPortageAppDbPath()+"/"+atom+"/"
    if os.path.isdir(dbdir):
        tbz2 = etpXpak.tbz2(tbz2file)
        tbz2.recompose(dbdir)
    return tbz2file

# This function extracts all the info from a .tbz2 file and returns them
def extractPkgData(package, etpBranch = etpConst['branch'], silent = False, inject = False):

    data = {}

    from portageTools import calculate_dependencies, getPackagesInSystem, getConfigProtectAndMask, getThirdPartyMirrors

    info_package = bold(os.path.basename(package))+": "

    filepath = package
    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package name/version..."),back = True)
    tbz2File = package
    package = package.split(".tbz2")[0]
    package = remove_entropy_revision(package)
    package = remove_tag(package)
    # remove category
    if package.find(":") != -1:
        package = ':'.join(package.split(":")[1:])

    package = package.split("-")
    pkgname = ""
    pkglen = len(package)
    if package[pkglen-1].startswith("r"):
        pkgver = package[pkglen-2]+"-"+package[pkglen-1]
        pkglen -= 2
    else:
        pkgver = package[-1]
        pkglen -= 1
    for i in range(pkglen):
        if i == pkglen-1:
            pkgname += package[i]
        else:
            pkgname += package[i]+"-"
    pkgname = pkgname.split("/")[-1]

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

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package injection information..."),back = True)
    # fill slot, if it is
    if inject:
        data['injected'] = True
    else:
        data['injected'] = False

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
    if os.path.isfile(tbz2TmpDir+dbCONTENTS):
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
                    raise exceptionTools.InvalidData("InvalidData: "+str(datafile)+" not supported. Probably portage API changed.")
                outcontent.add((datafile,datatype))
            except:
                pass

        _outcontent = set()
        for i in outcontent:
            i = list(i)
            datatype = i[1]
            _outcontent.add((i[0],i[1]))
        outcontent = list(_outcontent)
        outcontent.sort()
        for i in outcontent:
            data['content'][i[0]] = i[1]
 
    else:
        # CONTENTS is not generated when a package is emerged with portage and the option -B
        # we have to unpack the tbz2 and generate content dict
        import shutil
        mytempdir = etpConst['packagestmpdir']+"/"+os.path.basename(filepath)+".inject"
        if os.path.isdir(mytempdir):
            shutil.rmtree(mytempdir)
        if not os.path.isdir(mytempdir):
            os.makedirs(mytempdir)
        uncompressTarBz2(filepath, extractPath = mytempdir, catchEmpty = True)

        for currentdir, subdirs, files in os.walk(mytempdir):
            data['content'][currentdir[len(mytempdir):]] = "dir"
            for item in files:
                item = currentdir+"/"+item
                if os.path.islink(item):
                    data['content'][item[len(mytempdir):]] = "sym"
                else:
                    data['content'][item[len(mytempdir):]] = "obj"

        # now remove
        shutil.rmtree(mytempdir,True)
        try:
            os.rmdir(mytempdir)
        except:
            pass

    # files size on disk
    if (data['content']):
        data['disksize'] = 0
        for item in data['content']:
            try:
                size = os.stat(item)[6]
                data['disksize'] += size
            except:
                pass
    else:
        data['disksize'] = 0

    # [][][] Kernel dependent packages hook [][][]
    data['versiontag'] = ''
    kernelstuff = False
    kernelstuff_kernel = False
    for item in data['content']:
        if item.startswith("/lib/modules/"):
            kernelstuff = True
            # get the version of the modules
            kmodver = item.split("/lib/modules/")[1]
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
    if (kernelstuff):
        matchatom = "linux-"+kname+"-"+kver
        if (matchatom == data['name']+"-"+data['version']):
            kernelstuff_kernel = True

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package category..."),back = True)
    # Fill category
    f = open(tbz2TmpDir+dbCATEGORY,"r")
    data['category'] = f.readline().strip()
    f.close()

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package download URL..."),back = True)
    # Fill download relative URI
    if (kernelstuff):
        data['versiontag'] = kmodver
        if not kernelstuff_kernel:
            data['slot'] = kmodver # if you change this behaviour, you must change "reagent update" and "equo database gentoosync" consequentially
        versiontag = "#"+data['versiontag']
    else:
        versiontag = ""
    # remove etpConst['product'] from etpConst['binaryurirelativepath']
    downloadrelative = etpConst['binaryurirelativepath'][len(etpConst['product'])+1:]
    data['download'] = downloadrelative+data['branch']+"/"+data['category']+":"+data['name']+"-"+data['version']+versiontag+".tbz2"

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package counter..."),back = True)
    # Fill counter
    try:
        f = open(tbz2TmpDir+dbCOUNTER,"r")
        data['counter'] = int(f.readline().strip())
        f.close()
    except IOError:
        data['counter'] = -2 # -2 values will be insterted as incremental negative values into the database


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

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting source package supported ARCHs..."),back = True)
    # fill KEYWORDS
    data['keywords'] = []
    try:
        f = open(tbz2TmpDir+dbKEYWORDS,"r")
        cnt = f.readline().strip().split()
        if not cnt:
            data['keywords'].append("") # support for packages with no keywords
        else:
            for i in cnt:
                if i:
                    data['keywords'].append(i)
        f.close()
    except IOError:
        pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package dependencies..."),back = True)

    f = open(tbz2TmpDir+dbRDEPEND,"r")
    rdepend = f.readline().strip()
    f.close()

    f = open(tbz2TmpDir+dbPDEPEND,"r")
    pdepend = f.readline().strip()
    f.close()

    f = open(tbz2TmpDir+dbDEPEND,"r")
    depend = f.readline().strip()
    f.close()

    f = open(tbz2TmpDir+dbUSE,"r")
    use = f.readline().strip()
    f.close()

    try:
        f = open(tbz2TmpDir+dbIUSE,"r")
        iuse = f.readline().strip()
        f.close()
    except IOError:
        iuse = ""

    try:
        f = open(tbz2TmpDir+dbLICENSE,"r")
        lics = f.readline().strip()
        f.close()
    except IOError:
        lics = ""

    try:
        f = open(tbz2TmpDir+dbPROVIDE,"r")
        provide = f.readline().strip()
    except IOError:
        provide = ""

    try:
        f = open(tbz2TmpDir+dbSRC_URI,"r")
        sources = f.readline().strip()
        f.close()
    except IOError:
        sources = ""

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting package metadata information..."),back = True)
    portage_metadata = calculate_dependencies(iuse, use, lics, depend, rdepend, pdepend, provide, sources)

    data['provide'] = portage_metadata['PROVIDE'].split()
    data['license'] = portage_metadata['LICENSE']
    data['useflags'] = []
    for x in use.split():
        if x in portage_metadata['USE']:
            data['useflags'].append(x)
        else:
            data['useflags'].append("-"+x)
    data['sources'] = portage_metadata['SRC_URI'].split()
    data['dependencies'] = [x for x in portage_metadata['RDEPEND'].split()+portage_metadata['PDEPEND'].split() if not x.startswith("!") and not x in ("(","||",")","")]
    data['conflicts'] = [x[1:] for x in portage_metadata['RDEPEND'].split()+portage_metadata['PDEPEND'].split() if x.startswith("!") and not x in ("(","||",")","")]

    if (kernelstuff) and (not kernelstuff_kernel):
        # add kname to the dependency
        data['dependencies'].append("=sys-kernel/linux-"+kname+"-"+kver)
        key = data['category']+"/"+data['name']
        if etpConst['conflicting_tagged_packages'].has_key(key):
            myconflicts = etpConst['conflicting_tagged_packages'][key]
            for conflict in myconflicts:
                data['conflicts'].append(conflict)

    # Get License text if possible
    licenses_dir = None
    try:
        from portageTools import getPortageEnv
        licenses_dir = os.path.join(getPortageEnv('PORTDIR'),'licenses')
    except:
        pass
    data['licensedata'] = {}
    if licenses_dir:
        licdata = [str(x.strip()) for x in data['license'].split() if str(x.strip()) and is_valid_string(x.strip())]
        for mylicense in licdata:

            licfile = os.path.join(licenses_dir,mylicense)
            if os.access(licfile,os.R_OK):
                if istextfile(licfile):
                    f = open(licfile)
                    data['licensedata'][mylicense] = f.read()
                    f.close()

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

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting System Packages List..."),back = True)
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
        for item in elogfiles:
            if item.startswith(myelogfile):
                foundfiles.append(item)
        if foundfiles:
            elogfile = foundfiles[0]
            if len(foundfiles) > 1:
                # get the latest
                mtimes = []
                for item in foundfiles:
                    mtimes.append((getFileUnixMtime(etpConst['logdir']+"/elog/"+item),item))
                mtimes.sort()
                elogfile = mtimes[len(mtimes)-1][1]
            messages = extractElog(etpConst['logdir']+"/elog/"+elogfile)
            for message in messages:
                message = message.replace("emerge","equo install")
                data['messages'].append(message)
    else:
        if not silent: print_warning(red(etpConst['logdir']+"/elog")+" not set, have you configured make.conf properly?")

    if not silent: print_info(yellow(" * ")+red(info_package+"Getting Entropy API version..."),back = True)
    # write API info
    data['etpapi'] = etpConst['etpapi']

    # removing temporary directory
    import shutil
    shutil.rmtree(tbz2TmpDir,True)
    if os.path.isdir(tbz2TmpDir):
        try:
            os.remove(tbz2TmpDir)
        except OSError:
            pass

    if not silent: print_info(yellow(" * ")+red(info_package+"Done"),back = True)
    return data

def is_valid_string(string):
    mystring = str(string)
    for char in mystring:
        if ord(char) not in range(32,127):
            return False
    return True

def collectLinkerPaths():
    if linkerPaths:
        return linkerPaths
    ldpaths = set()
    try:
        f = open(etpConst['systemroot']+"/etc/ld.so.conf","r")
        paths = f.readlines()
        for path in paths:
            path = path.strip()
            if path:
                if path[0] == "/":
                    ldpaths.add(os.path.normpath(path))
        f.close()
    except:
        pass
    linkerPaths.clear()
    linkerPaths.update(ldpaths)
    return ldpaths

# this is especially used to try to guess portage bytecoded entries in CONTENTS
def string_to_utf8(string):
    done = False

    # simple unicode?
    try:
        newstring = unicode(string)
        done = True
    except:
        pass
    if done:
        return newstring

    # try utf8
    try:
        newstring = string.decode("iso-8859-1")
        done = True
    except:
        pass
    if done:
        return newstring

    # try latin1 + iso-8859-1
    try:
        newstring = string.decode("latin1")
        done = True
    except:
        pass
    if done:
        return newstring

    # otherwise return None
    print "DEBUG: cannot encode into filesystem encoding -> "+unicode(string)
    return None

def listToUtf8(mylist):
    mynewlist = []
    for item in mylist:
        try:
            mynewlist.append(item.decode("utf-8"))
        except UnicodeDecodeError:
            try:
                mynewlist.append(item.decode("latin1").decode("utf-8"))
            except:
                raise
    return mynewlist
