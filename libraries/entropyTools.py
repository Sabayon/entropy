#!/usr/bin/python
# -*- coding: iso-8859-1 -*-
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
import threading
import time

def isRoot():
    if (etpConst['uid'] == 0):
        return True
    return False

def is_user_in_entropy_group(uid = None):

    import grp,pwd

    if uid == None:
        uid = os.getuid()
    if uid == 0:
        return True

    try:
        username = pwd.getpwuid(uid)[0]
    except KeyError:
        return False

    try:
        data = grp.getgrnam(etpConst['sysgroup'])
    except KeyError:
        return False

    #etp_gid = data[2]
    etp_group_users = data[3]

    if not etp_group_users or \
        username not in etp_group_users:
            return False

    return True

class TimeScheduled(threading.Thread):
    def __init__(self, function, delay, dictData = {}):
        threading.Thread.__init__(self)
        self.function = function
        self.delay = delay
        self.exc = SystemExit
        self.data = dictData
        self.accurate = True
    def run(self):
        self.alive = 1
        while self.alive:
            if self.data:
                self.function(self.data)
            else:
                self.function()
            try:
                if (self.delay > 5) and not self.accurate:
                    mydelay = int(self.delay)
                    broke = False
                    while mydelay:
                        if not self.alive:
                            broke = True
                            break
                        time.sleep(1)
                        mydelay -= 1
                    if broke: break
                else:
                    time.sleep(self.delay)
            except:
                pass
    def kill(self):
        self.alive = 0

    def nuke(self):
        raise self.exc

class parallelTask(threading.Thread):
    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self)
        self.function = args[0]
        self.args = args[1:][:]
        self.exc = SystemExit
        self.kwargs = kwargs.copy()
        self.result = None

    def parallel_wait(self):
        while len(threading.enumerate()) > etpSys['maxthreads']:
            time.sleep(0.001)

    def run(self):
        self.result = self.function(*self.args,**self.kwargs)

    def nuke(self):
        raise self.exc

    def kill(self):
        pass


def printTraceback(f = None):
    import traceback
    traceback.print_exc(file = f)

def getTraceback():
    import traceback
    from cStringIO import StringIO
    buf = StringIO()
    traceback.print_exc(file = buf)
    return buf.getvalue()

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
        mydict = {}
        if etpConst['proxy']['ftp']:
            mydict['ftp'] = etpConst['proxy']['ftp']
        if etpConst['proxy']['http']:
            mydict['http'] = etpConst['proxy']['http']
        if mydict:
            mydict['username'] = etpConst['proxy']['username']
            mydict['password'] = etpConst['proxy']['password']
            add_proxy_opener(urllib2, mydict)
        else:
            # unset
            urllib2._opener = None
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

def is_png_file(path):
    f = open(path,"r")
    x = f.read(4)
    if x == '\x89PNG':
        return True
    return False

def is_jpeg_file(path):
    f = open(path,"r")
    x = f.read(10)
    if x == '\xff\xd8\xff\xe0\x00\x10JFIF':
        return True
    return False

def is_bmp_file(path):
    f = open(path,"r")
    x = f.read(2)
    if x == 'BM':
        return True
    return False

def is_gif_file(path):
    f = open(path,"r")
    x = f.read(5)
    if x == 'GIF89':
        return True
    return False

def is_supported_image_file(path):
    calls = [is_png_file, is_jpeg_file, is_bmp_file, is_gif_file]
    for mycall in calls:
        if mycall(path): return True
    return False

def add_proxy_opener(module, data):
    import types
    if type(module) != types.ModuleType: # FIXME: check if it's urllib2
        raise exceptionTools.InvalidDataType("InvalidDataType: not a module")
    if not data:
        return

    username = None
    password = None
    authinfo = None
    if data.has_key('password'):
        username = data.pop('username')
    if data.has_key('password'):
        username = data.pop('password')
    if username == None or password == None:
        username = None
        password = None
    else:
        passmgr = module.HTTPPasswordMgrWithDefaultRealm()
        if data['http']:
            passmgr.add_password(None, data['http'], username, password)
        if data['ftp']:
            passmgr.add_password(None, data['ftp'], username, password)
        authinfo = module.ProxyBasicAuthHandler(passmgr)

    proxy_support = module.ProxyHandler(data)
    if authinfo:
        opener = module.build_opener(proxy_support, authinfo)
    else:
        opener = module.build_opener(proxy_support)
    module.install_opener(opener)

def is_valid_ascii(string):
    try:
        mystring = str(string)
    except:
        return False
    return True

def is_valid_unicode(string):
    try:
        mystring = unicode(string)
    except:
        return False
    return True

def is_valid_email(email):
    import re
    monster = "(?:[a-z0-9!#$%&'*+/=?^_{|}~-]+(?:.[a-z0-9!#$%" + \
        "&'*+/=?^_{|}~-]+)*|\"(?:" + \
        "[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]" + \
        "|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*\")@(?:(?:[a-z0-9]" + \
        "(?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?" + \
        "|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.)" + \
        "{3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?" + \
        "|[a-z0-9-]*[a-z0-9]:(?:" + \
        "[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]"  + \
        "|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"
    evil = re.compile(monster)
    if evil.match(email):
        return True
    return False

def islive():
    return const_islive()

def get_file_size(file_path):
    mystat = os.lstat(file_path)
    return int(mystat.st_size)

def check_required_space(mountpoint, bytes_required):
    import statvfs
    st = os.statvfs(mountpoint)
    freeblocks = st[statvfs.F_BFREE]
    blocksize = st[statvfs.F_BSIZE]
    freespace = freeblocks*blocksize
    if bytes_required > freespace:
        # it's NOT fine
        return False
    return True

def ebeep(count = 5):
    mycount = count
    while mycount > 0:
        os.system("sleep 0.35; echo -ne \"\a\"; sleep 0.35")
        mycount -= 1

def applicationLockCheck(option = None, gentle = False, silent = False):
    if etpConst['applicationlock']:
        if not silent:
            print_error(red("Another instance of Equo is running. Action: ")+bold(str(option))+red(" denied."))
            print_error(red("If I am lying (maybe). Please remove ")+bold(etpConst['pidfile']))
        if not gentle:
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
            try:
                print red(">>"), what,
            except UnicodeEncodeError:
                print red(">>"),what.encode('utf-8'),
        else:
            try:
                print what
            except UnicodeEncodeError:
                print what.encode('utf-8')
        for i in range(secs)[::-1]:
            sys.stdout.write(red(str(i+1)+" "))
            sys.stdout.flush()
            time.sleep(1)

def md5sum(filepath):
    import md5
    m = md5.new()
    readfile = open(filepath)
    block = readfile.read(1024)
    while block:
        m.update(block)
        block = readfile.read(1024)
    readfile.close()
    return m.hexdigest()

def md5sum_directory(directory, get_obj = False):
    if not os.path.isdir(directory):
        raise exceptionTools.DirectoryNotFound("DirectoryNotFound: directory just does not exist.")
    myfiles = os.listdir(directory)
    import md5
    m = md5.new()
    if not myfiles:
        if get_obj:
            return m
        else:
            return "0" # no files means 0

    for currentdir,subdirs,files in os.walk(directory):
        for myfile in files:
            myfile = os.path.join(currentdir,myfile)
            readfile = open(myfile)
            block = readfile.read(1024)
            while block:
                m.update(block)
                block = readfile.read(1024)
            readfile.close()
    if get_obj:
        return m
    else:
        return m.hexdigest()

# kindly stolen from Anaconda
# Copyright 1999-2008 Red Hat, Inc. <iutil.py>
def getfd(filespec, readOnly = 0):
    import types
    if type(filespec) == types.IntType:
        return filespec
    if filespec == None:
        filespec = "/dev/null"

    flags = os.O_RDWR | os.O_CREAT
    if (readOnly):
        flags = os.O_RDONLY
    return os.open(filespec, flags)

def execWithRedirect(argv, stdin = 0, stdout = 1, stderr = 2, root = '/', newPgrp = 0, ignoreTermSigs = 0):

    import signal

    childpid = os.fork()
    etpSys['killpids'].add(childpid)
    if (not childpid):
        if (root and root != '/'):
            os.chroot (root)
            os.chdir("/")

        if ignoreTermSigs:
            signal.signal(signal.SIGTSTP, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)

        stdin = getfd(stdin)
        if stdout == stderr:
            stdout = getfd(stdout)
            stderr = stdout
        else:
            stdout = getfd(stdout)
            stderr = getfd(stderr)

        if stdin != 0:
            os.dup2(stdin, 0)
            os.close(stdin)
        if stdout != 1:
            os.dup2(stdout, 1)
            if stdout != stderr:
                os.close(stdout)
        if stderr != 2:
            os.dup2(stderr, 2)
            os.close(stderr)

        try:
            os.execvp(argv[0], argv)
        except OSError:
            # let the caller deal with the exit code of 1.
            pass

        os._exit(1)

    if newPgrp:
        os.setpgid(childpid, childpid)
        oldPgrp = os.tcgetpgrp(0)
        os.tcsetpgrp(0, childpid)

    status = -1
    try:
        (pid, status) = os.waitpid(childpid, 0)
    except OSError, (errno, msg):
        print __name__, "waitpid:", msg
    except KeyboardInterrupt:
        return None

    if newPgrp:
        os.tcsetpgrp(0, oldPgrp)

    if childpid in etpSys['killpids']:
        etpSys['killpids'].remove(childpid)
    return status

def uncompress_file(file_path, destination_path, opener):
    f_out = open(destination_path,"wb")
    f_in = opener(file_path,"rb")
    data = f_in.read(8192)
    while data:
        f_out.write(data)
        data = f_in.read(8192)
    f_out.flush()
    f_out.close()
    f_in.close()

def compress_file(file_path, destination_path, opener, compress_level = None):
    f_in = open(file_path,"rb")
    if compress_level != None:
        f_out = opener(destination_path,"wb",compresslevel = compress_level)
    else:
        f_out = opener(destination_path,"wb")
    data = f_in.read(8192)
    while data:
        f_out.write(data)
        data = f_in.read(8192)
    if hasattr(f_out,'flush'):
        f_out.flush()
    f_out.close()
    f_in.close()

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

def backupClientDatabase():
    import shutil
    if os.path.isfile(etpConst['etpdatabaseclientfilepath']):
        rnd = getRandomNumber()
        source = etpConst['etpdatabaseclientfilepath']
        dest = etpConst['etpdatabaseclientfilepath']+".backup."+str(rnd)
        shutil.copy2(source,dest)
        user = os.stat(source)[4]
        group = os.stat(source)[5]
        os.chown(dest,user,group)
        shutil.copystat(source,dest)
        return dest
    return ""

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

ver_regexp = re.compile("^(cvs\\.)?(\\d+)((\\.\\d+)*)([a-z]?)((_(pre|p|beta|alpha|rc)\\d*)*)(-r(\\d+))?$")
suffix_regexp = re.compile("^(alpha|beta|rc|pre|p)(\\d*)$")
suffix_value = {"pre": -2, "p": 0, "alpha": -4, "beta": -3, "rc": -1}
endversion_keys = ["pre", "p", "alpha", "beta", "rc"]


def isjustpkgname(mypkg):
    myparts = mypkg.split('-')
    for x in myparts:
        if ververify(x):
            return 0
    return 1

def ververify(myverx, silent=1):

    myver = myverx[:]
    if myver.endswith("*"):
        myver = myver[:-1]
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
    mydep = remove_usedeps(mydep)

    mydep = dep_getcpv(mydep)
    if mydep and isspecific(mydep):
        mysplit = catpkgsplit(mydep)
        if not mysplit:
            return mydep
        return mysplit[0] + "/" + mysplit[1]

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

def dep_getslot(mydep):
    """

    # Imported from portage.dep
    # $Id: dep.py 11281 2008-07-30 06:12:19Z zmedico $

    Retrieve the slot on a depend.

    Example usage:
            >>> dep_getslot('app-misc/test:3')
            '3'

    @param mydep: The depstring to retrieve the slot of
    @type mydep: String
    @rtype: String
    @return: The slot
    """
    colon = mydep.find(":")
    if colon != -1:
        bracket = mydep.find("[", colon)
        if bracket == -1:
            return mydep[colon+1:]
        else:
            return mydep[colon+1:bracket]
    return None

def dep_getusedeps(depend):

    """

    # Imported from portage.dep
    # $Id: dep.py 11281 2008-07-30 06:12:19Z zmedico $

    Pull a listing of USE Dependencies out of a dep atom.

    Example usage:
            >>> dep_getusedeps('app-misc/test:3[foo,-bar]')
            ('foo','-bar')

    @param depend: The depstring to process
    @type depend: String
    @rtype: List
    @return: List of use flags ( or [] if no flags exist )
    """

    use_list = []
    open_bracket = depend.find('[')
    # -1 = failure (think c++ string::npos)
    comma_separated = False
    bracket_count = 0
    while( open_bracket != -1 ):
        bracket_count += 1
        if bracket_count > 1:
            raise exceptionTools.InvalidAtom("USE Dependency with more " + \
                "than one set of brackets: %s" % (depend,))
        close_bracket = depend.find(']', open_bracket )
        if close_bracket == -1:
            raise exceptionTools.InvalidAtom("USE Dependency with no closing bracket: %s" % depend )
        use = depend[open_bracket + 1: close_bracket]
        # foo[1:1] may return '' instead of None, we don't want '' in the result
        if not use:
            raise exceptionTools.InvalidAtom("USE Dependency with " + \
                "no use flag ([]): %s" % depend )
        if not comma_separated:
            comma_separated = "," in use

        if comma_separated and bracket_count > 1:
            raise exceptionTools.InvalidAtom("USE Dependency contains a mixture of " + \
                "comma and bracket separators: %s" % depend )

        if comma_separated:
            for x in use.split(","):
                if x:
                    use_list.append(x)
                else:
                    raise exceptionTools.InvalidAtom("USE Dependency with no use " + \
                            "flag next to comma: %s" % depend )
        else:
            use_list.append(use)

        # Find next use flag
        open_bracket = depend.find( '[', open_bracket+1 )

    return tuple(use_list)

def remove_usedeps(depend):
    mydepend = depend[:]

    close_bracket = mydepend.find(']')
    after_closebracket = ''
    if close_bracket != -1: after_closebracket = mydepend[close_bracket+1:]

    open_bracket = mydepend.find('[')
    if open_bracket != -1: mydepend = mydepend[:open_bracket]

    return mydepend+after_closebracket

def remove_slot(mydep):
    """

    # Imported from portage.dep
    # $Id: dep.py 11281 2008-07-30 06:12:19Z zmedico $

    Removes dep components from the right side of an atom:
            * slot
            * use
            * repo
    """
    colon = mydep.find(":")
    if colon != -1:
        mydep = mydep[:colon]
    else:
        bracket = mydep.find("[")
        if bracket != -1:
            mydep = mydep[:bracket]
    return mydep

# input must be a valid package version or a full atom
def remove_revision(ver):
    myver = ver.split("-")
    if myver[-1][0] == "r":
        return '-'.join(myver[:-1])
    return ver

def remove_tag(mydep):
    colon = mydep.rfind("#")
    if colon == -1:
        return mydep
    return mydep[:colon]

def remove_entropy_revision(mydep):
    dep = removePackageOperators(mydep)
    operators = mydep[:-len(dep)]
    colon = dep.rfind("~")
    if colon == -1:
        return mydep
    return operators+dep[:colon]

def dep_get_entropy_revision(mydep):
    #dep = removePackageOperators(mydep)
    colon = mydep.rfind("~")
    if colon != -1:
        myrev = mydep[colon+1:]
        try:
            myrev = int(myrev)
        except ValueError:
            return None
        return myrev
    return None


dep_revmatch = re.compile('^r[0-9]')
def dep_get_portage_revision(mydep):
    myver = mydep.split("-")
    myrev = myver[-1]
    if dep_revmatch.match(myrev):
        return myrev
    else:
        return "r0"


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

    if not atom:
        return atom

    try:
        if atom[0] in [">","<"]:
            atom = atom[1:]
        if atom[0] == "=":
            atom = atom[1:]
        if atom[0] == "~":
            atom = atom[1:]
    except IndexError:
        pass

    return atom

# Version compare function taken from portage_versions.py
# portage_versions.py -- core Portage functionality
# Copyright 1998-2006 Gentoo Foundation

def compareVersions(ver1, ver2):

    if ver1 == ver2:
        return 0
    #mykey=ver1+":"+ver2
    match1 = None
    match2 = None
    if ver1:
        match1 = ver_regexp.match(ver1)
    if ver2:
        match2 = ver_regexp.match(ver2)

    # checking that the versions are valid
    if not match1:
        return None,0
    elif not match1.groups():
        return None,0
    elif not match2:
        return None,1
    elif not match2.groups():
        return None,1

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

def spawnFunction(f, *args, **kwds):

    uid = kwds.get('spf_uid')
    if uid != None: kwds.pop('spf_uid')

    gid = kwds.get('spf_gid')
    if gid != None: kwds.pop('spf_gid')

    write_pid_func = kwds.get('write_pid_func')
    if write_pid_func != None:
        kwds.pop('write_pid_func')

    try:
        import cPickle as pickle
    except ImportError:
        import pickle
    pread, pwrite = os.pipe()
    pid = os.fork()
    if pid > 0:
        if write_pid_func != None:
            write_pid_func(pid)
        os.close(pwrite)
        f = os.fdopen(pread, 'rb')
        status, result = pickle.load(f)
        os.waitpid(pid, 0)
        f.close()
        if status == 0:
            return result
        else:
            raise result
    else:
        os.close(pread)
        if gid != None:
            os.setgid(gid)
        if uid != None:
            os.setuid(uid)
        try:
            result = f(*args, **kwds)
            status = 0
        except Exception, exc:
            result = exc
            status = 1
        f = os.fdopen(pwrite, 'wb')
        try:
            pickle.dump((status,result), f, pickle.HIGHEST_PROTOCOL)
        except pickle.PicklingError, exc:
            pickle.dump((2,exc), f, pickle.HIGHEST_PROTOCOL)
        f.close()
        os._exit(0)

# tar* uncompress function...
def uncompressTarBz2(filepath, extractPath = None, catchEmpty = False):

    if extractPath == None:
        extractPath = os.path.dirname(filepath)
    if not os.path.isfile(filepath):
        raise exceptionTools.FileNotFound('FileNotFound: archive does not exist')

    _tarfile = True
    try:
        import tarfile
    except ImportError:
        _tarfile = False

    ### XXX dirty bastard workaround for buggy python2.4's tarfile
    if sys.version[:3] == "2.4" or not _tarfile:
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
        epath = os.path.join(extractPath, tarinfo.name)
        try:
            tar.chown(tarinfo, epath)
            tar.utime(tarinfo, epath)
            tar.chmod(tarinfo, epath)
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
        size = str(round(float(bytes)))+"b"
    elif bytes < 1023999:
        size += "kB"
    elif bytes > 1023999:
        size = str(round(float(size)/1024,1))
        size += "MB"
    return size

# hide password from full ftp URI
def hideFTPpassword(uri):
    ftppassword = uri.split("@")[:-1]
    if len(ftppassword) > 1:
        ftppassword = '@'.join(ftppassword)
        ftppassword = ftppassword.split(":")[-1]
        if (ftppassword == ""):
            return uri
    else:
        ftppassword = ftppassword[0]
        ftppassword = ftppassword.split(":")[-1]
        if (ftppassword == ""):
            return uri

    newuri = uri.replace(ftppassword,"xxxxxxxx")
    return newuri

def extract_ftp_data(ftpuri):
    ftpuser = ftpuri.split("ftp://")[-1].split(":")[0]
    if (ftpuser == ""):
        ftpuser = "anonymous@"
        ftppassword = "anonymous"
    else:
        ftppassword = ftpuri.split("@")[:-1]
        if len(ftppassword) > 1:
            ftppassword = '@'.join(ftppassword)
            ftppassword = ftppassword.split(":")[-1]
            if (ftppassword == ""):
                ftppassword = "anonymous"
        else:
            ftppassword = ftppassword[0]
            ftppassword = ftppassword.split(":")[-1]
            if (ftppassword == ""):
                ftppassword = "anonymous"

    ftpport = ftpuri.split(":")[-1]
    try:
        ftpport = int(ftpport)
    except ValueError:
        ftpport = 21

    ftpdir = '/'
    if ftpuri.count("/") > 2:
        ftpdir = ftpuri.split("ftp://")[-1]
        ftpdir = ftpdir.split("/")[-1]
        ftpdir = ftpdir.split(":")[0]
        if ftpdir.endswith("/"):
            ftpdir = ftpdir[:len(ftpdir)-1]
        if not ftpdir: ftpdir = "/"

    return ftpuser, ftppassword, ftpport, ftpdir

def getFileUnixMtime(path):
    return os.path.getmtime(path)

def getRandomTempFile():
    if not os.path.isdir(etpConst['packagestmpdir']):
        os.makedirs(etpConst['packagestmpdir'])
    path = os.path.join(etpConst['packagestmpdir'],"temp_"+str(getRandomNumber()))
    while os.path.lexists(path):
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
    return time.time()

def getYear():
    return time.strftime("%Y")

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
    return repodata

def writeOrderedRepositoriesEntries():
    #repoOrder = [x for x in etpRepositoriesOrder if not x.endswith(".tbz2")]
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

            line = "repository|%s|%s|%s|%s#%s#%s,%s" % (   repodata['repoid'],
                                                    repodata['description'],
                                                    ' '.join(repodata['plain_packages']),
                                                    repodata['plain_database'],
                                                    repodata['dbcformat'],
                                                    repodata['service_port'],
                                                    repodata['ssl_service_port'],
                                                )

            # seek in repolines_data for a disabled entry and remove
            to_remove = set()
            for cc in repolines_data:
                if repolines_data[cc]['line'].startswith("#") and \
                    (repolines_data[cc]['line'].find("repository|"+repodata['repoid']) != -1):
                    # then remove
                    to_remove.add(cc)
            for x in to_remove:
                del repolines_data[x]

            repolines_data[repocount] = {}
            repolines_data[repocount]['repoid'] = repodata['repoid']
            repolines_data[repocount]['line'] = line

        # inject new repodata
        keys = repolines_data.keys()
        keys.sort()
        for cc in keys:
            #repoid = repolines_data[cc]['repoid']
            # write the first
            line = repolines_data[cc]['line']
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

def writeParameterToFile(config_file, name, data):

    # check write perms
    if not os.access(os.path.dirname(config_file),os.W_OK):
        return False

    import shutil
    content = []
    if os.path.isfile(config_file):
        f = open(config_file,"r")
        content = [x.strip() for x in f.readlines()]
        f.close()

    # write new
    config_file_tmp = config_file+".tmp"
    f = open(config_file_tmp,"w")
    param_found = False
    if data:
        proposed_line = "%s|%s" % (name,data,)
        myreg = re.compile('^(%s)?[|].*$' % (name,))
    else:
        proposed_line = "# %s|" % (name,)
        myreg_rem = re.compile('^(%s)?[|].*$' % (name,))
        myreg = re.compile('^#([ \t]+?)?(%s)?[|].*$' % (name,))
        new_content = []
        for line in content:
            if myreg_rem.match(line):
                continue
            new_content.append(line)
        content = new_content

    for line in content:
        if myreg.match(line):
            param_found = True
            line = proposed_line
        f.write(line+"\n")
    if not param_found:
        f.write(proposed_line+"\n")
    f.flush()
    f.close()
    shutil.move(config_file_tmp,config_file)
    return True

def writeNewBranch(branch):
    return writeParameterToFile(etpConst['repositoriesconf'],"branch",branch)


def isEntropyTbz2(tbz2file):
    import tarfile
    if not os.path.exists(tbz2file):
        return False
    return tarfile.is_tarfile(tbz2file)

def appendXpak(tbz2file, atom):
    import etpXpak
    from entropy import SpmInterface
    SpmIntf = SpmInterface(None)
    Spm = SpmIntf.intf
    dbdir = Spm.get_vdb_path()+"/"+atom+"/"
    if os.path.isdir(dbdir):
        tbz2 = etpXpak.tbz2(tbz2file)
        tbz2.recompose(dbdir)
    return tbz2file

def is_valid_string(string):
    mystring = str(string)
    for char in mystring:
        if ord(char) not in range(32,127):
            return False
    return True

def open_buffer():
    try:
        import cStringIO as stringio
    except ImportError:
        import StringIO as stringio
    return stringio.StringIO()

def seek_till_newline(f):
    count = 0
    f.seek(count,2)
    size = f.tell()
    while count > (size*-1):
        count -= 1
        f.seek(count,2)
        myc = f.read(1)
        if myc == "\n":
            break
    f.seek(count+1,2)
    pos = f.tell()
    f.truncate(pos)

def read_elf_class(elf_file):
    import struct
    f = open(elf_file,"rb")
    f.seek(4)
    elf_class = f.read(1)
    f.close()
    elf_class = struct.unpack('B',elf_class)[0]
    return elf_class

def is_elf_file(elf_file):
    import struct
    f = open(elf_file,"rb")
    data = f.read(4)
    f.close()
    try:
        data = struct.unpack('BBBB',data)
    except struct.error:
        return False
    if data == (127, 69, 76, 70):
        return True
    return False

# FIXME: reimplement this
def read_elf_dynamic_libraries(elf_file):
    import commands
    if not os.access(etpConst['systemroot']+"/usr/bin/readelf",os.X_OK):
        raise exceptionTools.FileNotFound('FileNotFound: no readelf')
    data = commands.getoutput('readelf -d %s' % (elf_file,)).split("\n")
    mylibs = set()
    for line in data:
        if line.find("(NEEDED)") == -1:
            continue
        mylib = line.strip().split()[-1]
        if not (mylib.endswith("]") and mylib.startswith("[")):
            continue
        mylibs.add(mylib[1:-1])
    return mylibs

# FIXME: reimplement this
def read_elf_linker_paths(elf_file):
    import commands
    if not os.access(etpConst['systemroot']+"/usr/bin/readelf",os.X_OK):
        raise exceptionTools.FileNotFound('FileNotFound: no readelf')
    data = commands.getoutput('readelf -d %s' % (elf_file,)).split("\n")
    mypaths = []
    for line in data:
        if (line.find("(RPATH)") == -1) and (line.find("(RUNPATH)") == -1):
            continue
        mylib = line.strip().split()[-1]
        if not (mylib.endswith("]") and mylib.startswith("[")):
            continue
        mypath = mylib[1:-1].split(":")
        for xpath in mypath:
            xpath = xpath.replace("$ORIGIN",os.path.dirname(elf_file))
            mypaths.append(xpath)
    return mypaths

def xml_from_dict(dictionary):
    from xml.dom import minidom
    doc = minidom.Document()
    ugc = doc.createElement("entropy")
    for key, value in dictionary.items():
        item = doc.createElement('item')
        item.setAttribute('value',key)
        item_value = doc.createTextNode(value)
        item.appendChild(item_value)
        ugc.appendChild(item)
    doc.appendChild(ugc)
    return doc.toxml()

def dict_from_xml(xml_string):
    from xml.dom import minidom
    doc = minidom.parseString(xml_string)
    entropies = doc.getElementsByTagName("entropy")
    if not entropies:
        return {}
    entropy = entropies[0]
    items = entropy.getElementsByTagName('item')
    mydict = {}
    for item in items:
        key = item.getAttribute('value')
        if not key: continue
        try:
            data = item.firstChild.data
        except AttributeError:
            data = ''
        mydict[key] = data
    return mydict


def collectLinkerPaths():
    if linkerPaths:
        return linkerPaths
    ldpaths = []
    try:
        f = open(etpConst['systemroot']+"/etc/ld.so.conf","r")
        paths = f.readlines()
        for path in paths:
            path = path.strip()
            if path:
                if path[0] == "/":
                    ldpaths.append(os.path.normpath(path))
        f.close()
    except:
        pass

    # can happen that /lib /usr/lib are not in LDPATH
    if "/lib" not in ldpaths:
        ldpaths.append("/lib")
    if "/usr/lib" not in ldpaths:
        ldpaths.append("/usr/lib")

    del linkerPaths[:]
    linkerPaths.extend(ldpaths)
    return ldpaths[:]

def collectPaths():
    path = set()
    paths = os.getenv("PATH")
    if paths != None:
        paths = set(paths.split(":"))
        path |= paths
    return path

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
