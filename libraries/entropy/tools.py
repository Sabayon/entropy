# -*- coding: utf-8 -*-
# Entropy miscellaneous tools module
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy miscellaneous tools module}.
    In this module are enclosed all the miscellaneous functions
    used arount the Entropy codebase.

"""
import stat
import errno
import re
import sys
import os
import time
import shutil
import tarfile
import subprocess
import grp
import pwd
import hashlib
import random
from entropy.output import TextInterface, print_info, print_generic, red, \
    darkgreen, green
from entropy.const import etpConst, const_kill_threads, const_islive, \
    const_isunicode, const_convert_to_unicode
from entropy.exceptions import FileNotFound, InvalidAtom, InvalidDataType, \
    DirectoryNotFound

def is_root():
    """
    Return whether running process has root priviledges.

    @return: root priviledges
    @rtype: bool
    """
    return not etpConst['uid']

def is_user_in_entropy_group(uid = None):
    """
    Return whether UID or given UID (through uid keyword argument) is in
    the "entropy" group (see entropy.const.etpConst['sysgroup']).

    @keyword uid: valid system uid
    @type uid: int
    @return: True, if UID is in the "entropy" group
    @rtype: bool
    """

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

    etp_group_users = data[3]

    if not etp_group_users or \
        username not in etp_group_users:
            return False

    return True

def get_uid_from_user(username):
    """
    Return UID for given username or -1 if not available.

    @param username: valid system username
    @type username: string
    @return: UID if username is valid, otherwise -1
    @rtype: int
    """
    try:
        return pwd.getpwnam(username)[2]
    except (KeyError, IndexError,):
        return -1

def get_gid_from_group(groupname):
    """
    Return GID value for given system group name if exists, otherwise
    return -1.

    @param groupname: valid system group
    @type groupname: string
    @return: resolved GID or -1 if not available
    @rtype: int
    """
    try:
        return grp.getgrnam(groupname)[2]
    except (KeyError, IndexError,):
        return -1

def get_user_from_uid(uid):
    """
    Return username belonging to given system UID.

    @param uid: valid system UID
    @type uid: int
    @return: username
    @rtype: string or None
    """
    try:
        return pwd.getpwuid(uid)[0]
    except KeyError:
        return None

def get_group_from_gid(gid):
    """
    Return group name belonging to given system GID

    @param gid: valid system GID
    @type gid: int
    @return: group name
    @rtype: string or None
    """
    try:
        return grp.getgrgid(gid)[0]
    except (KeyError, IndexError,):
        return None

def kill_threads():
    """
    Call entropy.const's const_kill_threads() method. Service function
    available also here.
    """
    const_kill_threads()

def print_traceback(f = None):
    """
    Function called by Entropy when an exception occurs with the aim to give
    user a clue of what went wrong.

    @keyword f: write to f (file) object instead of stdout
    @type f: valid file handle
    """
    import traceback
    traceback.print_exc(file = f)

def get_traceback():
    """
    Return last available Python traceback.

    @return: traceback data
    @rtype: string
    """
    import traceback
    from io import StringIO
    buf = StringIO()
    traceback.print_exc(file = buf)
    return buf.getvalue()

def print_exception(returndata = False):
    """
    Print last Python exception and frame variables values (if available)
    to stdout.

    @keyword returndata: do not print data but return
    @type returndata: bool
    @return: exception data
    @rtype: string
    """
    import traceback
    if not returndata:
        traceback.print_exc()
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
            sys.stdout.write("\n")
            print_generic("Frame %s in %s at line %s" % (frame.f_code.co_name,
                                             frame.f_code.co_filename,
                                             frame.f_lineno))
        else:
            data.append("Frame %s in %s at line %s" % (frame.f_code.co_name,
                                             frame.f_code.co_filename,
                                             frame.f_lineno))
        for key, value in list(frame.f_locals.items()):
            if not returndata:
                sys.stdout.write("\t%20s = " % key)
            else:
                data.append("\t%20s = " % key,)
            try:
                if not returndata:
                    sys.stdout.write(repr(value) + "\n")
                else:
                    data.append(repr(value))
            except:
                if not returndata:
                    sys.stdout.write("<ERROR WHILE PRINTING VALUE>\n")
    return data

# Get the content of an online page
# @returns content: if the file exists
# @returns False: if the file is not found
def get_remote_data(url, timeout = 5):
    """
    Fetch data at given URL (all the ones supported by Python urllib) and
    return it.

    @param url: URL string
    @type url: string
    @keyword timeout: fetch timeout in seconds
    @type timeout: int
    @return: fetched data or False (when error occured)
    @rtype: string or bool
    """
    import socket
    if sys.hexversion >= 0x3000000:
        import urllib.request as urlmod
    else:
        import urllib2 as urlmod

    # now pray the server
    from entropy.core.settings.base import SystemSettings
    sys_settings = SystemSettings()
    proxy_settings = sys_settings['system']['proxy']

    mydict = {}
    if proxy_settings['ftp']:
        mydict['ftp'] = proxy_settings['ftp']
    if proxy_settings['http']:
        mydict['http'] = proxy_settings['http']
    if mydict:
        mydict['username'] = proxy_settings['username']
        mydict['password'] = proxy_settings['password']
        add_proxy_opener(urlmod, mydict)
    else:
        # unset
        urlmod._opener = None

    try:
        item = urlmod.urlopen(url, timeout = timeout)

        result = item.readlines()
        item.close()
    except:
        return False
    finally:
        socket.setdefaulttimeout(2)

    if not result:
        return False
    return result

def _is_png_file(path):
    with open(path, "r") as f:
        x = f.read(4)
    if x == '\x89PNG':
        return True
    return False

def _is_jpeg_file(path):
    with open(path, "r") as f:
        x = f.read(10)
    if x == '\xff\xd8\xff\xe0\x00\x10JFIF':
        return True
    return False

def _is_bmp_file(path):
    with open(path, "r") as f:
        x = f.read(2)
    if x == 'BM':
        return True
    return False

def _is_gif_file(path):
    with open(path, "r") as f:
        x = f.read(5)
    if x == 'GIF89':
        return True
    return False

def is_supported_image_file(path):
    """
    Return whether passed image file path "path" references a valid image file.
    Currently supported image file types are: PNG, JPEG, BMP, GIF.

    @param path: path pointing to a possibly valid image file
    @type path: string
    @return: True if path references a valid image file 
    @rtype: bool
    """
    calls = [_is_png_file, _is_jpeg_file, _is_bmp_file, _is_gif_file]
    for mycall in calls:
        if mycall(path):
            return True
    return False

def is_april_first():
    """
    Return whether today is April, 1st.
    Please keep the joke.

    @return: True if April 1st
    @rtype: bool
    """
    april_first = "01-04"
    cur_time = time.strftime("%d-%m")
    if april_first == cur_time:
        return True
    return False

def add_proxy_opener(module, data):
    """
    Add proxy opener to urllib module.

    @param module: urllib module
    @type module: Python module
    @param data: proxy settings
    @type data: dict
    """
    import types
    if type(module) != types.ModuleType:
        InvalidDataType("InvalidDataType: not a module")
    if not data:
        return

    username = None
    password = None
    authinfo = None
    if 'password' in data:
        username = data.pop('username')
    if 'password' in data:
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
    """
    Return whether passed string only contains valid ASCII characters.

    @param string: string to test
    @type string: string
    @return: True if string contains pure ASCII
    @rtype: bool
    """
    try:
        mystring = str(string)
        del mystring
    except (UnicodeDecodeError, UnicodeEncodeError,):
        return False
    return True

def is_valid_unicode(string):
    """
    Return whether passed string is unicode.

    @param string: string to test
    @type string: string
    @return: True if string is unicode
    @rtype: 
    """
    if const_isunicode(string):
        return True

    # try to convert bytes to unicode
    try:
        const_convert_to_unicode(string)
    except (UnicodeEncodeError, UnicodeDecodeError,):
        return False
    return True

def is_valid_email(email):
    """
    Return whether passed string is contains a valid email address.

    @param email: string to test
    @type email: string
    @return: True if string is a valid email
    @rtype: bool
    """
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
    """
    Return whether System is running in Live mode (off a CD/DVD).
    See entropy.const.const_islive() for more information.

    @return: True if System is running in Live mode
    @rtype: bool
    """
    return const_islive()

def get_file_size(file_path):
    """
    Return size of given path passed in "file_path".

    @param file_path: path to an existing file
    @type file_path: string
    @return: file size in bytes
    @rtype: int
    @raise OSError: if file referenced in file_path is not available
    """
    my = file_path[:]
    if const_isunicode(my):
        my = my.encode("utf-8")
    mystat = os.lstat(my)
    return int(mystat.st_size)

def sum_file_sizes(file_list):
    """
    Return file size sum of given list of paths.

    @param file_list: list of file paths
    @type file_list: list
    @return: summed size in bytes
    @rtype: int
    """
    size = 0
    for myfile in file_list:
        try:
            size += get_file_size(myfile)
        except (OSError, IOError,):
            continue
    return size

def check_required_space(mountpoint, bytes_required):
    """
    Check available space in mount point and if it satisfies
    the amount of required bytes given.

    @param mountpoint: mount point
    @type mountpoint: string
    @param bytes_required: amount of bytes required to make function return True
    @type bytes_required: bool
    @return: if True, required space is available
    @rtype: bool
    """
    import statvfs
    st = os.statvfs(mountpoint)
    freeblocks = st[statvfs.F_BFREE]
    blocksize = st[statvfs.F_BSIZE]
    freespace = freeblocks*blocksize
    if bytes_required > freespace:
        # it's NOT fine
        return False
    return True

def getstatusoutput(cmd):
    """Return (status, output) of executing cmd in a shell."""
    pipe = os.popen('{ ' + cmd + '; } 2>&1', 'r')
    text = pipe.read()
    sts = pipe.close()
    if sts is None: sts = 0
    if text[-1:] == '\n':
        text = text[:-1]
    return sts, text

# Copyright 1998-2004 Gentoo Foundation
# Copyright 2009 Fabio Erculiani (reducing code complexity)
# Distributed under the terms of the GNU General Public License v2
# $Id: __init__.py 12159 2008-12-05 00:08:58Z zmedico $
# atomic file move function
def movefile(src, dest, src_basedir = None):
    """
    Move a file from source to destination in an atomic way.

    @param src: source path
    @type src: string
    @param dest: destination path
    @type dest: string
    @keyword src_basedir: source path base directory, used to properly handle
        symlink under certain circumstances
    @type src_basedir: string
    @return: True, if file was moved successfully
    @rtype: bool
    """

    sstat = os.lstat(src)
    destexists = 1
    try:
        dstat = os.lstat(dest)
    except (OSError, IOError,):
        dstat = os.lstat(os.path.dirname(dest))
        destexists = 0

    if destexists:
        if stat.S_ISLNK(dstat[stat.ST_MODE]):
            try:
                os.unlink(dest)
                destexists = 0
            except (OSError, IOError,):
                pass

    if stat.S_ISLNK(sstat[stat.ST_MODE]):
        try:
            target = os.readlink(src)
            if src_basedir is not None:
                if target.find(src_basedir) == 0:
                    target = target[len(src_basedir):]
            if destexists and not stat.S_ISDIR(dstat[stat.ST_MODE]):
                os.unlink(dest)
            os.symlink(target, dest)
            os.lchown(dest, sstat[stat.ST_UID], sstat[stat.ST_GID])
            return True
        except SystemExit:
            raise
        except Exception as e:
            print_generic("!!! failed to properly create symlink:")
            print_generic("!!!", dest, "->", target)
            print_generic("!!!", repr(e))
            return False

    renamefailed = True
    if sstat.st_dev == dstat.st_dev:
        try:
            os.rename(src, dest)
            renamefailed = False
        except Exception as e:
            if e[0] != errno.EXDEV:
                # Some random error.
                print_generic("!!! Failed to move", src, "to", dest)
                print_generic("!!!", repr(e))
                return False
            # Invalid cross-device-link 'bind' mounted or actually Cross-Device

    if renamefailed:
        didcopy = True
        if stat.S_ISREG(sstat[stat.ST_MODE]):
            try: # For safety copy then move it over.
                while 1:
                    tmp_dest = "%s#entropy_new_%s" % (dest, get_random_number(),)
                    if not os.path.lexists(tmp_dest):
                        break
                shutil.copyfile(src, tmp_dest)
                os.rename(tmp_dest, dest)
                didcopy = True
            except SystemExit as e:
                raise
            except Exception as e:
                print_generic('!!! copy', src, '->', dest, 'failed.')
                print_generic("!!!", repr(e))
                return False
        else:
            #we don't yet handle special, so we need to fall back to /bin/mv
            a = getstatusoutput("mv -f '%s' '%s'" % (src, dest,))
            if a[0] != 0:
                print_generic("!!! Failed to move special file:")
                print_generic("!!! '" + src + "' to '" + dest + "'")
                print_generic("!!!", str(a))
                return False
        try:
            if didcopy:
                if stat.S_ISLNK(sstat[stat.ST_MODE]):
                    os.lchown(dest, sstat[stat.ST_UID], sstat[stat.ST_GID])
                else:
                    os.chown(dest, sstat[stat.ST_UID], sstat[stat.ST_GID])
                os.chmod(dest, stat.S_IMODE(sstat[stat.ST_MODE])) # Sticky is reset on chown
                os.unlink(src)
        except SystemExit as e:
            raise
        except Exception as e:
            print_generic("!!! Failed to chown/chmod/unlink in movefile()")
            print_generic("!!!", dest)
            print_generic("!!!", repr(e))
            return False

    try:
        os.utime(dest, (sstat.st_atime, sstat.st_mtime))
    except OSError:
        # The utime can fail here with EPERM even though the move succeeded.
        # Instead of failing, use stat to return the mtime if possible.
        try:
            int(os.stat(dest).st_mtime)
            return True
        except OSError as e:
            print_generic("!!! Failed to stat in movefile()\n")
            print_generic("!!! %s\n" % dest)
            print_generic("!!! %s\n" % (e,))
            return False

    return True

def ebeep(count = 5):
    """
    docstring_title

    @keyword count: 
    @type count: 
    @return: 
    @rtype: 
    """
    mycount = count
    while mycount > 0:
        os.system("sleep 0.35; echo -ne \"\a\"; sleep 0.35")
        mycount -= 1

def application_lock_check(gentle = False):
    """
    docstring_title

    @keyword gentle: 
    @type gentle: 
    @return: 
    @rtype: 
    """
    if etpConst['applicationlock']:
        if not gentle:
            SystemExit(10)
        return True
    return False

def get_random_number():
    """
    docstring_title

    @return: 
    @rtype: 
    """
    try:
        return abs(hash(os.urandom(2)))%99999
    except NotImplementedError:
        random.seed()
        return random.randint(10000, 99999)

def split_indexable_into_chunks(mystr, chunk_len):
    """
    docstring_title

    @param mystr: 
    @type mystr: 
    @param chunk_len: 
    @type chunk_len: 
    @return: 
    @rtype: 
    """
    chunks = []
    my = mystr[:]
    mylen = len(my)
    while mylen:
        chunk = my[:chunk_len]
        chunks.append(chunk)
        my_chunk_len = len(chunk)
        my = my[my_chunk_len:]
        mylen -= my_chunk_len
    return chunks

def countdown(secs = 5, what = "Counting...", back = False):
    """
    docstring_title

    @keyword secs: 
    @type secs: 
    @keyword what: 
    @type what: 
    @keyword back: 
    @type back: 
    @return: 
    @rtype: 
    """
    if secs:
        if back:
            try:
                print_generic(red(">>") + " " + what)
            except UnicodeEncodeError:
                print_generic(red(">>") + " " + what.encode('utf-8'))
        else:
            print_generic(what)
        for i in range(secs)[::-1]:
            sys.stdout.write(red(str(i+1)+" "))
            sys.stdout.flush()
            time.sleep(1)

def md5sum(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    m = hashlib.md5()
    readfile = open(filepath)
    block = readfile.read(1024)
    while block:
        m.update(block)
        block = readfile.read(1024)
    readfile.close()
    return m.hexdigest()

def sha512(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    m = hashlib.sha512()
    readfile = open(filepath)
    block = readfile.read(1024)
    while block:
        m.update(block)
        block = readfile.read(1024)
    readfile.close()
    return m.hexdigest()

def sha256(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    m = hashlib.sha256()
    readfile = open(filepath)
    block = readfile.read(1024)
    while block:
        m.update(block)
        block = readfile.read(1024)
    readfile.close()
    return m.hexdigest()

def sha1(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    m = hashlib.sha1()
    readfile = open(filepath)
    block = readfile.read(1024)
    while block:
        m.update(block)
        block = readfile.read(1024)
    readfile.close()
    return m.hexdigest()

def md5sum_directory(directory):
    """
    docstring_title

    @param directory: 
    @type directory: 
    @return: 
    @rtype: 
    """
    if not os.path.isdir(directory):
        DirectoryNotFound("DirectoryNotFound: directory just does not exist.")
    myfiles = os.listdir(directory)
    m = hashlib.md5()
    if not myfiles:
        return "0" # no files means 0

    for currentdir, subdirs, files in os.walk(directory):
        for myfile in files:
            myfile = os.path.join(currentdir, myfile)
            readfile = open(myfile)
            block = readfile.read(1024)
            while block:
                m.update(block)
                block = readfile.read(1024)
            readfile.close()
    return m.hexdigest()

def md5obj_directory(directory):
    """
    docstring_title

    @param directory: 
    @type directory: 
    @return: 
    @rtype: 
    """
    if not os.path.isdir(directory):
        DirectoryNotFound("DirectoryNotFound: directory just does not exist.")
    myfiles = os.listdir(directory)
    m = hashlib.md5()
    if not myfiles:
        return m

    for currentdir, subdirs, files in os.walk(directory):
        for myfile in files:
            myfile = os.path.join(currentdir, myfile)
            readfile = open(myfile)
            block = readfile.read(1024)
            while block:
                m.update(block)
                block = readfile.read(1024)
            readfile.close()
    return m

# kindly stolen from Anaconda
# Copyright 1999-2008 Red Hat, Inc. <iutil.py>
def getfd(filespec, readOnly = 0):
    """
    docstring_title

    @param filespec: 
    @type filespec: 
    @keyword readOnly: 
    @type readOnly: 
    @return: 
    @rtype: 
    """
    import types
    if type(filespec) == int:
        return filespec
    if filespec == None:
        filespec = "/dev/null"

    flags = os.O_RDWR | os.O_CREAT
    if (readOnly):
        flags = os.O_RDONLY
    return os.open(filespec, flags)

def uncompress_file(file_path, destination_path, opener):
    """
    docstring_title

    @param file_path: 
    @type file_path: 
    @param destination_path: 
    @type destination_path: 
    @param opener: 
    @type opener: 
    @return: 
    @rtype: 
    """
    f_out = open(destination_path, "wb")
    f_in = opener(file_path, "rb")
    data = f_in.read(8192)
    while data:
        f_out.write(data)
        data = f_in.read(8192)
    f_out.flush()
    f_out.close()
    f_in.close()

def compress_file(file_path, destination_path, opener, compress_level = None):
    """
    docstring_title

    @param file_path: 
    @type file_path: 
    @param destination_path: 
    @type destination_path: 
    @param opener: 
    @type opener: 
    @keyword compress_level: 
    @type compress_level: 
    @return: 
    @rtype: 
    """
    f_in = open(file_path, "rb")
    if compress_level != None:
        f_out = opener(destination_path, "wb", compresslevel = compress_level)
    else:
        f_out = opener(destination_path, "wb")
    data = f_in.read(8192)
    while data:
        f_out.write(data)
        data = f_in.read(8192)
    if hasattr(f_out, 'flush'):
        f_out.flush()
    f_out.close()
    f_in.close()

# files_to_compress must be a list of valid file paths
def compress_files(dest_file, files_to_compress, compressor = "bz2"):
    """
    docstring_title

    @param dest_file: 
    @type dest_file: 
    @param files_to_compress: 
    @type files_to_compress: 
    @keyword compressor: 
    @type compressor: 
    @return: 
    @rtype: 
    """

    if compressor not in ("bz2", "gz",):
        AttributeError("invalid compressor specified")

    id_strings = {}
    tar = tarfile.open(dest_file, "w:%s" % (compressor,))
    try:
        for path in files_to_compress:
            exist = os.lstat(path)
            tarinfo = tar.gettarinfo(path, os.path.basename(path))
            tarinfo.uname = id_strings.setdefault(tarinfo.uid, str(tarinfo.uid))
            tarinfo.gname = id_strings.setdefault(tarinfo.gid, str(tarinfo.gid))
            if not stat.S_ISREG(exist.st_mode): continue
            tarinfo.type = tarfile.REGTYPE
            with open(path) as f:
                tar.addfile(tarinfo, f)
    finally:
        tar.close()

def universal_uncompress(compressed_file, dest_path, catch_empty = False):
    """
    docstring_title

    @param compressed_file: 
    @type compressed_file: 
    @param dest_path: 
    @type dest_path: 
    @keyword catch_empty: 
    @type catch_empty: 
    @return: 
    @rtype: 
    """

    try:
        tar = tarfile.open(compressed_file, "r")
    except tarfile.ReadError:
        if catch_empty:
            return True
        return False
    except EOFError:
        return False

    try:

        dest_path = dest_path.encode('utf-8')
        def mymf(tarinfo):
            """
            docstring_title

            @param tarinfo: 
            @type tarinfo: 
            @return: 
            @rtype: 
            """
            if tarinfo.isdir():
                # Extract directory with a safe mode, so that
                # all files below can be extracted as well.
                try:
                    os.makedirs(os.path.join(dest_path, tarinfo.name), 0o777)
                except EnvironmentError:
                    pass
                return tarinfo
            tar.extract(tarinfo, dest_path)
            del tar.members[:]
            return tarinfo

        def mycmp(a, b):
            """
            docstring_title

            @param a: 
            @type a: 
            @param b: 
            @type b: 
            @return: 
            @rtype: 
            """
            return cmp(a.name, b.name)

        directories = sorted(map(mymf, tar), mycmp, reverse = True)

        # Set correct owner, mtime and filemode on directories.
        def mymf2(tarinfo):
            """
            docstring_title

            @param tarinfo: 
            @type tarinfo: 
            @return: 
            @rtype: 
            """
            epath = os.path.join(dest_path, tarinfo.name)
            try:
                tar.chown(tarinfo, epath)

                # this is mandatory on uid/gid that don't exist
                # and in this strict order !!
                uname = tarinfo.uname
                gname = tarinfo.gname
                ugdata_valid = False
                try:
                    int(gname)
                    int(uname)
                except ValueError:
                    ugdata_valid = True

                try:
                    if ugdata_valid:
                        # get uid/gid
                        # if not found, returns -1 that won't change anything
                        uid, gid = get_uid_from_user(uname), \
                            get_gid_from_group(gname)
                        os.lchown(epath, uid, gid)
                except OSError:
                    pass

                tar.utime(tarinfo, epath)
                tar.chmod(tarinfo, epath)
            except tarfile.ExtractError:
                if tar.errorlevel > 1:
                    return False
        done = list(map(mymf2, directories))
        del done

    except EOFError:
        return False

    finally:
        tar.close()

    return True

def unpack_gzip(gzipfilepath):
    """
    docstring_title

    @param gzipfilepath: 
    @type gzipfilepath: 
    @return: 
    @rtype: 
    """
    import gzip
    filepath = gzipfilepath[:-3] # remove .gz
    item = open(filepath, "wb")
    filegz = gzip.GzipFile(gzipfilepath, "rb")
    chunk = filegz.read(8192)
    while chunk:
        item.write(chunk)
        chunk = filegz.read(8192)
    filegz.close()
    item.flush()
    item.close()
    return filepath

def unpack_bzip2(bzip2filepath):
    """
    docstring_title

    @param bzip2filepath: 
    @type bzip2filepath: 
    @return: 
    @rtype: 
    """
    import bz2
    filepath = bzip2filepath[:-4] # remove .bz2
    item = open(filepath, "wb")
    filebz2 = bz2.BZ2File(bzip2filepath, "rb")
    chunk = filebz2.read(8192)
    while chunk:
        item.write(chunk)
        chunk = filebz2.read(8192)
    filebz2.close()
    item.flush()
    item.close()
    return filepath

def backup_client_repository():
    """
    docstring_title

    @return: 
    @rtype: 
    """
    if os.path.isfile(etpConst['etpdatabaseclientfilepath']):
        rnd = get_random_number()
        source = etpConst['etpdatabaseclientfilepath']
        dest = etpConst['etpdatabaseclientfilepath']+".backup."+str(rnd)
        shutil.copy2(source, dest)
        user = os.stat(source)[4]
        group = os.stat(source)[5]
        os.chown(dest, user, group)
        shutil.copystat(source, dest)
        return dest
    return ""

def extract_xpak(tbz2file, tmpdir = None):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @keyword tmpdir: 
    @type tmpdir: 
    @return: 
    @rtype: 
    """
    # extract xpak content
    xpakpath = suck_xpak(tbz2file, etpConst['packagestmpdir'])
    return unpack_xpak(xpakpath, tmpdir)

def read_xpak(tbz2file):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @return: 
    @rtype: 
    """
    xpakpath = suck_xpak(tbz2file, etpConst['entropyunpackdir'])
    f = open(xpakpath, "rb")
    data = f.read()
    f.close()
    os.remove(xpakpath)
    return data

def unpack_xpak(xpakfile, tmpdir = None):
    """
    docstring_title

    @param xpakfile: 
    @type xpakfile: 
    @keyword tmpdir: 
    @type tmpdir: 
    @return: 
    @rtype: 
    """
    try:
        import entropy.xpak as xpak
        if tmpdir is None:
            tmpdir = etpConst['packagestmpdir']+"/"+os.path.basename(xpakfile)[:-5]+"/"
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir, True)
        os.makedirs(tmpdir)
        xpakdata = xpak.getboth(xpakfile)
        xpak.xpand(xpakdata, tmpdir)
        del xpakdata
        try:
            os.remove(xpakfile)
        except OSError:
            pass
    except:
        return None
    return tmpdir

def suck_xpak(tbz2file, outputpath):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @param outputpath: 
    @type outputpath: 
    @return: 
    @rtype: 
    """

    dest_filename = os.path.basename(tbz2file)[:-5]+".xpak"
    xpakpath = os.path.join(outputpath, dest_filename)
    old = open(tbz2file, "rb")

    # position old to the end
    old.seek(0, os.SEEK_END)
    # read backward until we find
    bytes = old.tell()
    counter = bytes - 1
    xpak_end = "XPAKSTOP"
    xpak_start = "XPAKPACK"
    xpak_entry_point = "X"
    xpak_tag_len = len(xpak_start)
    chunk_len = 3
    data_start_position = None
    data_end_position = None

    while counter >= (0 - chunk_len):

        old.seek(counter - bytes, os.SEEK_END)
        if (bytes - (abs(counter - bytes))) < chunk_len:
            chunk_len = 1
        read_bytes = old.read(chunk_len)
        read_len = len(read_bytes)

        entry_idx = read_bytes.rfind(xpak_entry_point)
        if entry_idx != -1:

            cut_gotten = read_bytes[entry_idx:]
            offset = xpak_tag_len - len(cut_gotten)
            chunk = cut_gotten + old.read(offset)

            if (chunk == xpak_end) and (data_start_position is None):
                data_end_position = old.tell()

            elif (chunk == xpak_start) and (data_end_position is not None):
                data_start_position = old.tell() - xpak_tag_len
                break

        counter -= read_len

    if data_start_position is None:
        return None
    if data_end_position is None:
        return None

    # now write to found metadata to file
    # starting from data_start_position
    # ending to data_end_position
    db = open(xpakpath, "wb")
    old.seek(data_start_position)
    to_read = data_end_position - data_start_position
    while to_read > 0:
        data = old.read(to_read)
        db.write(data)
        to_read -= len(data)

    db.flush()
    db.close()
    old.close()
    return xpakpath

def append_xpak(tbz2file, atom):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @param atom: 
    @type atom: 
    @return: 
    @rtype: 
    """
    import entropy.xpak as xpak
    from entropy.spm.plugins.factory import get_default_instance
    text = TextInterface()
    spm = get_default_instance(text)
    dbbuild = spm.get_installed_package_build_script_path(atom)
    dbdir = os.path.dirname(dbbuild)
    if os.path.isdir(dbdir):
        tbz2 = xpak.tbz2(tbz2file)
        tbz2.recompose(dbdir)
    return tbz2file

def aggregate_edb(tbz2file, dbfile):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @param dbfile: 
    @type dbfile: 
    @return: 
    @rtype: 
    """
    f = open(tbz2file, "abw")
    f.write(etpConst['databasestarttag'])
    g = open(dbfile, "rb")
    chunk = g.read(8192)
    while chunk:
        f.write(chunk)
        chunk = g.read(8192)
    g.close()
    f.flush()
    f.close()

def extract_edb(tbz2file, dbpath = None):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @keyword dbpath: 
    @type dbpath: 
    @return: 
    @rtype: 
    """

    old = open(tbz2file, "rb")
    if not dbpath:
        dbpath = tbz2file[:-5] + ".db"

    start_position = locate_edb(old)
    if not start_position:
        old.close()
        try:
            os.remove(dbpath)
        except OSError:
            return None
        return None

    db = open(dbpath, "wb")
    data = old.read(1024)
    while data:
        db.write(data)
        data = old.read(1024)
    db.flush()
    db.close()

    return dbpath

def locate_edb(fileobj):
    """
    docstring_title

    @param fileobj: 
    @type fileobj: 
    @return: 
    @rtype: 
    """

    # position old to the end
    fileobj.seek(0, os.SEEK_END)
    # read backward until we find
    bytes = fileobj.tell()
    counter = bytes - 1

    db_tag = etpConst['databasestarttag']
    db_tag_len = len(db_tag)
    give_up_threshold = 1024000 * 30 # 30Mb
    entry_point = db_tag[::-1][0]
    max_read_len = 8
    start_position = None

    while counter >= 0:
        cur_threshold = abs((counter-bytes))
        if cur_threshold >= give_up_threshold:
            start_position = None
            break
        fileobj.seek(counter-bytes, os.SEEK_END)
        read_bytes = fileobj.read(max_read_len)
        read_len = len(read_bytes)
        entry_idx = read_bytes.rfind(entry_point)
        if entry_idx != -1:
            rollback = (read_len - entry_idx) * -1
            fileobj.seek(rollback, os.SEEK_CUR)
            chunk = fileobj.read(db_tag_len)
            if chunk == db_tag:
                start_position = fileobj.tell()
                break
        counter -= read_len

    return start_position

def remove_edb(tbz2file, savedir):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @param savedir: 
    @type savedir: 
    @return: 
    @rtype: 
    """
    old = open(tbz2file, "rb")

    start_position = locate_edb(old)
    if not start_position:
        old.close()
        return None

    new_path = os.path.join(savedir, os.path.basename(tbz2file))
    new = open(new_path, "wb")

    old.seek(0)
    counter = 0
    max_read_len = 1024
    db_tag = etpConst['databasestarttag']
    db_tag_len = len(db_tag)
    start_position -= db_tag_len

    while counter < start_position:
        delta = start_position - counter
        if delta < max_read_len:
            max_read_len = delta
        bytes = old.read(max_read_len)
        read_bytes = len(bytes)
        new.write(bytes)
        counter += read_bytes

    new.flush()
    new.close()
    old.close()
    return savedir+"/"+os.path.basename(tbz2file)

# This function creates the .md5 file related to the given package file
def create_md5_file(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    md5hash = md5sum(filepath)
    hashfile = filepath+etpConst['packagesmd5fileext']
    f = open(hashfile, "w")
    name = os.path.basename(filepath)
    f.write(md5hash+"  "+name+"\n")
    f.flush()
    f.close()
    return hashfile

def create_sha512_file(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    sha512hash = sha512(filepath)
    hashfile = filepath+etpConst['packagessha512fileext']
    f = open(hashfile, "w")
    tbz2name = os.path.basename(filepath)
    f.write(sha512hash+"  "+tbz2name+"\n")
    f.flush()
    f.close()
    return hashfile

def create_sha256_file(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    sha256hash = sha256(filepath)
    hashfile = filepath+etpConst['packagessha256fileext']
    f = open(hashfile, "w")
    tbz2name = os.path.basename(filepath)
    f.write(sha256hash+"  "+tbz2name+"\n")
    f.flush()
    f.close()
    return hashfile

def create_sha1_file(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    sha1hash = sha1(filepath)
    hashfile = filepath+etpConst['packagessha1fileext']
    f = open(hashfile, "w")
    tbz2name = os.path.basename(filepath)
    f.write(sha1hash+"  "+tbz2name+"\n")
    f.flush()
    f.close()
    return hashfile

def compare_md5(filepath, checksum):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @param checksum: 
    @type checksum: 
    @return: 
    @rtype: 
    """
    checksum = str(checksum)
    result = md5sum(filepath)
    result = str(result)
    if checksum == result:
        return True
    return False

def compare_sha512(filepath, checksum):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @param checksum: 
    @type checksum: 
    @return: 
    @rtype: 
    """
    checksum = str(checksum)
    result = sha512(filepath)
    result = str(result)
    if checksum == result:
        return True
    return False

def compare_sha256(filepath, checksum):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @param checksum: 
    @type checksum: 
    @return: 
    @rtype: 
    """
    checksum = str(checksum)
    result = sha256(filepath)
    result = str(result)
    if checksum == result:
        return True
    return False

def compare_sha1(filepath, checksum):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @param checksum: 
    @type checksum: 
    @return: 
    @rtype: 
    """
    checksum = str(checksum)
    result = sha1(filepath)
    result = str(result)
    if checksum == result:
        return True
    return False

def md5string(string):
    """
    docstring_title

    @param string: 
    @type string: 
    @return: 
    @rtype: 
    """
    m = hashlib.md5()
    m.update(string)
    return m.hexdigest()

# used to properly sort /usr/portage/profiles/updates files
def sort_update_files(update_list):
    """
    docstring_title

    @param update_list: 
    @type update_list: 
    @return: 
    @rtype: 
    """
    sort_dict = {}
    # sort per year
    for item in update_list:
        # get year
        year = item.split("-")[1]
        if year in sort_dict:
            sort_dict[year].append(item)
        else:
            sort_dict[year] = []
            sort_dict[year].append(item)
    new_list = []
    keys = list(sort_dict.keys())
    keys.sort()
    for key in keys:
        sort_dict[key].sort()
        new_list += sort_dict[key]
    del sort_dict
    return new_list

def generic_file_content_parser(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    data = []
    if os.access(filepath, os.R_OK) and os.path.isfile(filepath):
        gen_f = open(filepath, "r")
        content = gen_f.readlines()
        gen_f.close()
        # filter comments and white lines
        content = [x.strip().rsplit("#", 1)[0].strip() for x in content \
            if not x.startswith("#") and x.strip()]
        for line in content:
            if line in data:
                continue
            data.append(line)
    return data

# used by equo, this function retrieves the new safe Gentoo-aware file path
def allocate_masked_file(file, fromfile):
    """
    docstring_title

    @param file: 
    @type file: 
    @param fromfile: 
    @type fromfile: 
    @return: 
    @rtype: 
    """

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
        txtcounter_len = 4-len(txtcounter)
        cnt = 0
        while cnt < txtcounter_len:
            txtcounter = "0"+txtcounter
            oldtxtcounter = "0"+oldtxtcounter
            cnt += 1
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

def extract_elog(file):
    """
    docstring_title

    @param file: 
    @type file: 
    @return: 
    @rtype: 
    """

    logline = False
    logoutput = []
    f = open(file, "r")
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
    """
    docstring_title

    @param mypkg: 
    @type mypkg: 
    @return: 
    @rtype: 
    """
    myparts = mypkg.split('-')
    for x in myparts:
        if ververify(x):
            return 0
    return 1

def ververify(myverx, silent = 1):
    """
    docstring_title

    @param myverx: 
    @type myverx: 
    @keyword silent: 
    @type silent: 
    @return: 
    @rtype: 
    """

    myver = myverx[:]
    if myver.endswith("*"):
        myver = myver[:-1]
    if ver_regexp.match(myver):
        return 1
    else:
        if not silent:
            print_generic("!!! syntax error in version: %s" % myver)
        return 0


# Copyright 2003-2004 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Id: dep.py 11813 2008-11-06 04:56:17Z zmedico $
valid_category = re.compile("^\w[\w-]*")
invalid_atom_chars_regexp = re.compile("[()|@]")

def isvalidatom(myatom, allow_blockers = True):
    """
    Check to see if a depend atom is valid

    Example usage:
            >>> isvalidatom('media-libs/test-3.0')
            0
            >>> isvalidatom('>=media-libs/test-3.0')
            1

    @param atom: The depend atom to check against
    @type atom: String
    @rtype: Integer
    @return: One of the following:
            1) 0 if the atom is invalid
            2) 1 if the atom is valid
    """
    atom = remove_tag(myatom)
    atom = remove_usedeps(atom)
    if invalid_atom_chars_regexp.search(atom):
        return 0
    if allow_blockers and atom[:1] == "!":
        if atom[1:2] == "!":
            atom = atom[2:]
        else:
            atom = atom[1:]

    # media-sound/amarok/x ?
    if atom.count("/") > 1:
        return 0

    cpv = dep_getcpv(atom)
    cpv_catsplit = catsplit(cpv)
    mycpv_cps = None
    if cpv:
        if len(cpv_catsplit) == 2:
            if valid_category.match(cpv_catsplit[0]) is None:
                return 0
            if cpv_catsplit[0] == "null":
                # "null" category is valid, missing category is not.
                mycpv_cps = catpkgsplit(cpv.replace("null/", "cat/", 1))
                if mycpv_cps:
                    mycpv_cps = list(mycpv_cps)
                    mycpv_cps[0] = "null"
        if not mycpv_cps:
            mycpv_cps = catpkgsplit(cpv)

    operator = get_operator(atom)
    if operator:
        if operator[0] in "<>" and remove_slot(atom).endswith("*"):
            return 0
        if mycpv_cps:
            if len(cpv_catsplit) == 2:
                # >=cat/pkg-1.0
                return 1
            else:
                return 0
        else:
            # >=cat/pkg or >=pkg-1.0 (no category)
            return 0
    if mycpv_cps:
        # cat/pkg-1.0
        return 0

    if len(cpv_catsplit) == 2:
        # cat/pkg
        return 1
    return 0

def catsplit(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    return mydep.split("/", 1)

def get_operator(mydep):
    """
    Return the operator used in a depstring.

    Example usage:
            >>> from portage.dep import *
            >>> get_operator(">=test-1.0")
            '>='

    @param mydep: The dep string to check
    @type mydep: String
    @rtype: String
    @return: The operator. One of:
            '~', '=', '>', '<', '=*', '>=', or '<='
    """
    if mydep:
        mydep = remove_slot(mydep)
    if not mydep:
        return None
    if mydep[0] == "~":
        operator = "~"
    elif mydep[0] == "=":
        if mydep[-1] == "*":
            operator = "=*"
        else:
            operator = "="
    elif mydep[0] in "><":
        if len(mydep) > 1 and mydep[1] == "=":
            operator = mydep[0:2]
        else:
            operator = mydep[0]
    else:
        operator = None

    return operator

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


def catpkgsplit(mydata, silent = 1):
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
    mysplit = mydata.split("/")
    p_split = None
    if len(mysplit) == 1:
        retval = ["null"]
        p_split = pkgsplit(mydata, silent=silent)
    elif len(mysplit) == 2:
        retval = [mysplit[0]]
        p_split = pkgsplit(mysplit[1], silent=silent)
    if not p_split:
        return None
    retval.extend(p_split)
    return retval

def pkgsplit(mypkg, silent=1):
    """
    docstring_title

    @param mypkg: 
    @type mypkg: 
    @keyword silent=1: 
    @type silent=1: 
    @return: 
    @rtype: 
    """
    myparts = mypkg.split("-")

    if len(myparts) < 2:
        if not silent:
            print_generic("!!! Name error in", mypkg+": missing a version or name part.")
            return None
    for x in myparts:
        if len(x) == 0:
            if not silent:
                print_generic("!!! Name error in", mypkg+": empty \"-\" part.")
                return None

    #verify rev
    revok = 0
    myrev = myparts[-1]

    if len(myrev) and myrev[0] == "r":
        try:
            int(myrev[1:])
            revok = 1
        except ValueError: # from int()
            pass
    if revok:
        verPos = -2
        revision = myparts[-1]
    else:
        verPos = -1
        revision = "r0"

    if ververify(myparts[verPos]):
        if len(myparts) == (-1*verPos):
            return None
        else:
            for x in myparts[:verPos]:
                if ververify(x):
                    return None
                    #names can't have versiony looking parts
            myval = ["-".join(myparts[:verPos]), myparts[verPos], revision]
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
    if not mydepx:
        return mydepx
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
            ('foo', '-bar')

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
            InvalidAtom("USE Dependency with more " + \
                "than one set of brackets: %s" % (depend,))
        close_bracket = depend.find(']', open_bracket )
        if close_bracket == -1:
            InvalidAtom("USE Dependency with no closing bracket: %s" % depend )
        use = depend[open_bracket + 1: close_bracket]
        # foo[1:1] may return '' instead of None, we don't want '' in the result
        if not use:
            InvalidAtom("USE Dependency with " + \
                "no use flag ([]): %s" % depend )
        if not comma_separated:
            comma_separated = "," in use

        if comma_separated and bracket_count > 1:
            InvalidAtom("USE Dependency contains a mixture of " + \
                "comma and bracket separators: %s" % depend )

        if comma_separated:
            for x in use.split(","):
                if x:
                    use_list.append(x)
                else:
                    InvalidAtom("USE Dependency with no use " + \
                            "flag next to comma: %s" % depend )
        else:
            use_list.append(use)

        # Find next use flag
        open_bracket = depend.find( '[', open_bracket+1 )

    return tuple(use_list)

def remove_usedeps(depend):
    """
    docstring_title

    @param depend: 
    @type depend: 
    @return: 
    @rtype: 
    """
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
    """
    docstring_title

    @param ver: 
    @type ver: 
    @return: 
    @rtype: 
    """
    myver = ver.split("-")
    if myver[-1][0] == "r":
        return '-'.join(myver[:-1])
    return ver

def remove_tag(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    colon = mydep.rfind("#")
    if colon == -1:
        return mydep
    return mydep[:colon]

def remove_entropy_revision(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    dep = remove_package_operators(mydep)
    operators = mydep[:-len(dep)]
    colon = dep.rfind("~")
    if colon == -1:
        return mydep
    return operators+dep[:colon]

def dep_get_entropy_revision(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    #dep = remove_package_operators(mydep)
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
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    myver = mydep.split("-")
    myrev = myver[-1]
    if dep_revmatch.match(myrev):
        return myrev
    else:
        return "r0"


def dep_get_match_in_repos(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    colon = mydep.rfind("@")
    if colon != -1:
        mydata = mydep[colon+1:]
        mydata = mydata.split(",")
        if not mydata:
            mydata = None
        return mydep[:colon], mydata
    else:
        return mydep, None

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

def remove_package_operators(atom):
    """
    docstring_title

    @param atom: 
    @type atom: 
    @return: 
    @rtype: 
    """
    try:
        while atom:
            if atom[0] in ('>', '<', '=', '~',):
                atom = atom[1:]
                continue
            break
    except IndexError:
        pass
    return atom

# Version compare function taken from portage_versions.py
# portage_versions.py -- core Portage functionality
# Copyright 1998-2006 Gentoo Foundation
def compare_versions(ver1, ver2):
    """
    docstring_title

    @param ver1: 
    @type ver1: 
    @param ver2: 
    @type ver2: 
    @return: 
    @rtype: 
    """

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
    invalid = False
    invalid_rc = 0
    if not match1:
        invalid = True
    elif not match1.groups():
        invalid = True
    elif not match2:
        invalid_rc = 1
        invalid = True
    elif not match2.groups():
        invalid_rc = 1
        invalid = True
    if invalid: return invalid_rc

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
            s1 = ("p", "0")
        else:
            s1 = suffix_regexp.match(list1[i]).groups()
        if len(list2) <= i:
            s2 = ("p", "0")
        else:
            s2 = suffix_regexp.match(list2[i]).groups()
        if s1[0] != s2[0]:
            return suffix_value[s1[0]] - suffix_value[s2[0]]
        if s1[1] != s2[1]:
            # it's possible that the s(1|2)[1] == ''
            # in such a case, fudge it.
            try:
                r1 = int(s1[1])
            except ValueError:
                r1 = 0
            try:
                r2 = int(s2[1])
            except ValueError:
                r2 = 0
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

def entropy_compare_versions(listA, listB):
    '''
    @description: compare two lists composed by
        [version,tag,revision] and [version,tag,revision]
        if listA > listB --> positive number
        if listA == listB --> 0
        if listA < listB --> negative number	
    @input package: listA[version,tag,rev] and listB[version,tag,rev]
    @output: integer number
    '''

    # if both are tagged, check tag first
    rc = 0
    if listA[1] and listB[1]:
        rc = cmp(listA[1], listB[1])
    if rc == 0:
        rc = compare_versions(listA[0], listB[0])

    if rc == 0:
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

def g_n_w_cmp(a, b):
    '''
    @description: reorder a version list
    @input versionlist: a list
    @output: the ordered list
    '''
    rc = compare_versions(a, b)
    if rc < 0:
        return -1
    elif rc > 0:
        return 1
    else:
        return 0

def get_newer_version(versions):
    """
    docstring_title

    @param versions: 
    @type versions: 
    @return: 
    @rtype: 
    """
    return sorted(versions, g_n_w_cmp, reverse = True)

def get_newer_version_stable(versions):
    """
    docstring_title

    @param versions: 
    @type versions: 
    @return: 
    @rtype: 
    """

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
            result = compare_versions(pkgA, pkgB)
            if result < 0:
                versionlist[x] = pkgB
                versionlist[x+1] = pkgA
                change = True
        if not change:
            rc = True

    return versionlist

def get_entropy_newer_version(versions):
    """
    Sort a list of entropy package versions.

    @param versions: list of package versions
    @type versions: list
    @return: sorted list
    @rtype: list
    """
    if len(versions) < 2:
        return versions[:]

    vers = versions[:]
    max_idx = len(vers)

    while 1:
        changed = False
        for idx in range(max_idx):
            second_idx = idx+1
            if second_idx == max_idx:
                continue
            str_a = vers[idx]
            str_b = vers[second_idx]
            if entropy_compare_versions(str_a, str_b) < 0:
                vers[idx] = str_b
                vers[second_idx] = str_a
                changed = True
        if not changed:
            break

    return vers

def isnumber(x):
    """
    docstring_title

    @param x: 
    @type x: 
    @return: 
    @rtype: 
    """
    try:
        int(x)
        return True
    except ValueError:
        return False


def istextfile(filename, blocksize = 512):
    """
    docstring_title

    @param filename: 
    @type filename: 
    @keyword blocksize: 
    @type blocksize: 
    @return: 
    @rtype: 
    """
    f = open(filename)
    r = istext(f.read(blocksize))
    f.close()
    return r

def istext(s):
    """
    docstring_title

    @param s: 
    @type s: 
    @return: 
    @rtype: 
    """
    import string
    _null_trans = string.maketrans("", "")
    text_characters = "".join(list(map(chr, list(range(32, 127)))) + list("\n\r\t\b"))

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
def filter_duplicated_entries(alist):
    """
    docstring_title

    @param alist: 
    @type alist: 
    @return: 
    @rtype: 
    """
    mydata = {}
    return [mydata.setdefault(e, e) for e in alist if e not in mydata]


# Escapeing functions
mappings = {
	"'":"''",
	'"':'""',
	' ':'+'
}

def escape(*args):
    """
    docstring_title

    @param *args: 
    @type *args: 
    @return: 
    @rtype: 
    """
    arg_lst = []
    if len(args)==1:
        return escape_single(args[0])
    for x in args:
        arg_lst.append(escape_single(x))
    return tuple(arg_lst)

def escape_single(x):
    """
    docstring_title

    @param x: 
    @type x: 
    @return: 
    @rtype: 
    """
    if type(x) == type(()) or type(x) == type([]):
        return escape(x)
    if type(x) == type(""):
        tmpstr = ''
        for d in range(len(x)):
            if x[d] in list(mappings.keys()):
                if x[d] in ("'", '"'):
                    if d+1 < len(x):
                        if x[d+1] != x[d]:
                            tmpstr += mappings[x[d]]
                    else:
                        tmpstr += mappings[x[d]]
                else:
                   tmpstr += mappings[x[d]]
            else:
                tmpstr += x[d]
    else:
        tmpstr = x
    return tmpstr

def unescape(val):
    """
    docstring_title

    @param val: 
    @type val: 
    @return: 
    @rtype: 
    """
    if type(val)==type(""):
        tmpstr = ''
        for key, item in list(mappings.items()):
            val = val.replace(item, key)
        tmpstr = val
    else:
        tmpstr = val
    return tmpstr

def unescape_list(*args):
    """
    docstring_title

    @param *args: 
    @type *args: 
    @return: 
    @rtype: 
    """
    arg_lst = []
    for x in args:
        arg_lst.append(unescape(x))
    return tuple(arg_lst)

def extract_ftp_host_from_uri(uri):
    """
    docstring_title

    @param uri: 
    @type uri: 
    @return: 
    @rtype: 
    """
    myuri = spliturl(uri)[1]
    # remove username:pass@
    myuri = myuri.split("@")[len(myuri.split("@"))-1]
    return myuri

def spliturl(url):
    """
    docstring_title

    @param url: 
    @type url: 
    @return: 
    @rtype: 
    """
    if sys.hexversion >= 0x3000000:
        import urllib.parse as urlmod
    else:
        import urlparse as urlmod
    return urlmod.urlsplit(url)

def compress_tar_bz2(storepath, pathtocompress):
    """
    docstring_title

    @param storepath: 
    @type storepath: 
    @param pathtocompress: 
    @type pathtocompress: 
    @return: 
    @rtype: 
    """
    cmd = "cd \""+pathtocompress+"\" && tar cjf \""+storepath+"\" " + \
        ". &> /dev/null"
    return subprocess.call(cmd, shell = True)

def spawn_function(f, *args, **kwds):
    """
    docstring_title

    @param f: 
    @type f: 
    @param *args: 
    @type *args: 
    @param **kwds: 
    @type **kwds: 
    @return: 
    @rtype: 
    """

    uid = kwds.get('spf_uid')
    if uid != None: kwds.pop('spf_uid')

    gid = kwds.get('spf_gid')
    if gid != None: kwds.pop('spf_gid')

    write_pid_func = kwds.get('write_pid_func')
    if write_pid_func != None:
        kwds.pop('write_pid_func')

    try:
        import pickle as pickle
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
            result
    else:
        os.close(pread)
        if gid != None:
            os.setgid(gid)
        if uid != None:
            os.setuid(uid)
        try:
            result = f(*args, **kwds)
            status = 0
        except Exception as exc:
            result = exc
            status = 1
        f = os.fdopen(pwrite, 'wb')
        try:
            pickle.dump((status, result), f, pickle.HIGHEST_PROTOCOL)
        except pickle.PicklingError as exc:
            pickle.dump((2, exc), f, pickle.HIGHEST_PROTOCOL)
        f.close()
        os._exit(0)

# tar* uncompress function...
def uncompress_tar_bz2(filepath, extractPath = None, catchEmpty = False):
    """
    docstring_title
    # FIXME: rename this and make bz2 independent

    @param filepath: 
    @type filepath: 
    @keyword extractPath: 
    @type extractPath: 
    @keyword catchEmpty: 
    @type catchEmpty: 
    @return: 
    @rtype: 
    """

    if extractPath == None:
        extractPath = os.path.dirname(filepath)
    if not os.path.isfile(filepath):
        FileNotFound('FileNotFound: archive does not exist')

    try:
        tar = tarfile.open(filepath, "r")
    except tarfile.ReadError:
        if catchEmpty:
            return 0
        raise
    except EOFError:
        return -1

    def fix_uid_gid(tarinfo, epath):
        """
        docstring_title

        @param tarinfo: 
        @type tarinfo: 
        @param epath: 
        @type epath: 
        @return: 
        @rtype: 
        """
        # workaround for buggy tar files
        uname = tarinfo.uname
        gname = tarinfo.gname
        ugdata_valid = False
        try:
            int(gname)
            int(uname)
        except ValueError:
            ugdata_valid = True
        try:
            if ugdata_valid: # FIXME: will be removed in 2011
                # get uid/gid
                # if not found, returns -1 that won't change anything
                uid, gid = get_uid_from_user(uname), \
                    get_gid_from_group(gname)
                os.lchown(epath, uid, gid)
        except OSError:
            pass

    def mycmp(a, b):
        """
        docstring_title

        @param a: 
        @type a: 
        @param b: 
        @type b: 
        @return: 
        @rtype: 
        """
        return cmp(a[0].name, b[0].name)

    try:

        encoded_path = extractPath.encode('utf-8')
        def mymf(tarinfo):
            """
            docstring_title

            @param tarinfo: 
            @type tarinfo: 
            @return: 
            @rtype: 
            """
            epath = os.path.join(encoded_path, tarinfo.name)
            if tarinfo.isdir():
                # Extract directory with a safe mode, so that
                # all files below can be extracted as well.
                try:
                    os.makedirs(epath, 0o777)
                except EnvironmentError:
                    pass
                return tarinfo, epath

            tar.extract(tarinfo, encoded_path)

            del tar.members[:]
            return tarinfo, epath

        entries = sorted(map(mymf, tar), mycmp, reverse = True)

        # Set correct owner, mtime and filemode on directories.
        def mymf2(tardata):
            """
            docstring_title

            @param tardata: 
            @type tardata: 
            @return: 
            @rtype: 
            """
            tarinfo, epath = tardata
            try:

                tar.chown(tarinfo, epath)
                fix_uid_gid(tarinfo, epath)
                tar.utime(tarinfo, epath)
                # mode = tarinfo.mode
                # xorg-server /usr/bin/X symlink of /usr/bin/Xorg
                # which is setuid. Symlinks don't need chmod. PERIOD!
                if not os.path.islink(epath):
                    tar.chmod(tarinfo, epath)

            except tarfile.ExtractError:
                if tar.errorlevel > 1:
                    raise

        done = list(map(mymf2, entries))
        del done

    except EOFError:
        return -1

    finally:
        tar.close()

    if os.listdir(extractPath):
        return 0
    return -1

def bytes_into_human(bytes):
    """
    docstring_title

    @param bytes: 
    @type bytes: 
    @return: 
    @rtype: 
    """
    size = str(round(float(bytes)/1024, 1))
    if bytes < 1024:
        size = str(round(float(bytes)))+"b"
    elif bytes < 1023999:
        size += "kB"
    elif bytes > 1023999:
        size = str(round(float(size)/1024, 1))
        size += "MB"
    return size

def hide_ftp_password(uri):
    """
    docstring_title

    @param uri: 
    @type uri: 
    @return: 
    @rtype: 
    """
    ftppassword = uri.split("@")[:-1]
    if not ftppassword: return uri
    ftppassword = '@'.join(ftppassword)
    ftppassword = ftppassword.split(":")[-1]
    if not ftppassword:
        return uri
    newuri = uri.replace(ftppassword, "xxxxxxxx")
    return newuri

def extract_ftp_data(ftpuri):
    """
    docstring_title

    @param ftpuri: 
    @type ftpuri: 
    @return: 
    @rtype: 
    """
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

def get_file_unix_mtime(path):
    """
    docstring_title

    @param path: 
    @type path: 
    @return: 
    @rtype: 
    """
    return os.path.getmtime(path)

def get_random_temp_file():
    """
    docstring_title

    @return: 
    @rtype: 
    """
    if not os.path.isdir(etpConst['packagestmpdir']):
        os.makedirs(etpConst['packagestmpdir'])
    path = os.path.join(etpConst['packagestmpdir'],
        "temp_"+str(get_random_number()))
    while os.path.lexists(path):
        path = os.path.join(etpConst['packagestmpdir'],
            "temp_"+str(get_random_number()))
    return path

def get_file_timestamp(path):
    """
    docstring_title

    @param path: 
    @type path: 
    @return: 
    @rtype: 
    """
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

def convert_unix_time_to_human_time(unixtime):
    """
    docstring_title

    @param unixtime: 
    @type unixtime: 
    @return: 
    @rtype: 
    """
    from datetime import datetime
    humantime = str(datetime.fromtimestamp(unixtime))
    return humantime

def convert_unix_time_to_datetime(unixtime):
    """
    docstring_title

    @param unixtime: 
    @type unixtime: 
    @return: 
    @rtype: 
    """
    from datetime import datetime
    return datetime.fromtimestamp(unixtime)

def get_current_unix_time():
    """
    docstring_title

    @return: 
    @rtype: 
    """
    return time.time()

def get_year():
    """
    docstring_title

    @return: 
    @rtype: 
    """
    return time.strftime("%Y")

def convert_seconds_to_fancy_output(seconds):
    """
    docstring_title

    @param seconds: 
    @type seconds: 
    @return: 
    @rtype: 
    """

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

# Temporary files cleaner
def cleanup(toCleanDirs = []):
    """
    docstring_title

    @keyword toCleanDirs: 
    @type toCleanDirs: 
    @return: 
    @rtype: 
    """

    if not toCleanDirs:
        toCleanDirs = [ etpConst['packagestmpdir'], etpConst['logdir'] ]
    counter = 0

    for xdir in toCleanDirs:
        print_info(red(" * ")+"Cleaning "+darkgreen(xdir)+" directory...", back = True)
        if os.path.isdir(xdir):
            dircontent = os.listdir(xdir)
            if dircontent != []:
                for data in dircontent:
                    subprocess.call(["rm", "-rf", os.path.join(xdir, data)])
                    counter += 1

    print_info(green(" * ")+"Cleaned: "+str(counter)+" files and directories")
    return 0

def flatten(l, ltypes = (list, tuple)):
    """
    docstring_title

    @param l: 
    @type l: 
    @keyword ltypes: 
    @type ltypes: 
    @param tuple: 
    @type tuple: 
    @return: 
    @rtype: 
    """
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

def read_repositories_conf():
    """
    docstring_title

    @return: 
    @rtype: 
    """
    content = []
    if os.path.isfile(etpConst['repositoriesconf']):
        f = open(etpConst['repositoriesconf'])
        content = f.readlines()
        f.close()
    return content

def write_ordered_repositories_entries(ordered_repository_list):
    """
    docstring_title

    @param ordered_repository_list: 
    @type ordered_repository_list: 
    @return: 
    @rtype: 
    """
    content = read_repositories_conf()
    content = [x.strip() for x in content]
    repolines = [x for x in content if x.startswith("repository|") and (len(x.split("|")) == 5)]
    content = [x for x in content if x not in repolines]
    for repoid in ordered_repository_list:
        # get repoid from repolines
        for x in repolines:
            repoidline = x.split("|")[1]
            if repoid == repoidline:
                content.append(x)
    _save_repositories_content(content)

def save_repository_settings(repodata, remove = False, disable = False, enable = False):
    """
    docstring_title

    @param repodata: 
    @type repodata: 
    @keyword remove: 
    @type remove: 
    @keyword disable: 
    @type disable: 
    @keyword enable: 
    @type enable: 
    @return: 
    @rtype: 
    """

    if repodata['repoid'].endswith(etpConst['packagesext']):
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
        keys = list(repolines_data.keys())
        keys.sort()
        for cc in keys:
            #repoid = repolines_data[cc]['repoid']
            # write the first
            line = repolines_data[cc]['line']
            content.append(line)

    try:
        _save_repositories_content(content)
    except OSError: # permission denied?
        return False
    return True

def _save_repositories_content(content):
    """
    docstring_title

    @param content: 
    @type content: 
    @return: 
    @rtype: 
    """
    if os.path.isfile(etpConst['repositoriesconf']):
        if os.path.isfile(etpConst['repositoriesconf']+".old"):
            os.remove(etpConst['repositoriesconf']+".old")
        shutil.copy2(etpConst['repositoriesconf'], etpConst['repositoriesconf']+".old")
    f = open(etpConst['repositoriesconf'], "w")
    for x in content:
        f.write(x+"\n")
    f.flush()
    f.close()

def write_parameter_to_file(config_file, name, data):
    """
    docstring_title

    @param config_file: 
    @type config_file: 
    @param name: 
    @type name: 
    @param data: 
    @type data: 
    @return: 
    @rtype: 
    """

    # check write perms
    if not os.access(os.path.dirname(config_file), os.W_OK):
        return False

    content = []
    if os.path.isfile(config_file):
        f = open(config_file, "r")
        content = [x.strip() for x in f.readlines()]
        f.close()

    # write new
    config_file_tmp = config_file+".tmp"
    f = open(config_file_tmp, "w")
    param_found = False
    if data:
        proposed_line = "%s|%s" % (name, data,)
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
    shutil.move(config_file_tmp, config_file)
    return True

def write_new_branch(branch):
    """
    docstring_title

    @param branch: 
    @type branch: 
    @return: 
    @rtype: 
    """
    return write_parameter_to_file(etpConst['repositoriesconf'], "branch",
        branch)

def is_entropy_package_file(tbz2file):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @return: 
    @rtype: 
    """
    if not os.path.exists(tbz2file):
        return False
    try:
        obj = open(tbz2file, "r")
        entry_point = locate_edb(obj)
        if entry_point is None:
            obj.close()
            return False
        obj.close()
        return True
    except (IOError, OSError,):
        return False

def is_valid_string(string):
    """
    docstring_title

    @param string: 
    @type string: 
    @return: 
    @rtype: 
    """
    invalid = [ord(x) for x in string if ord(x) not in list(range(32, 127))]
    if invalid: return False
    return True

def is_valid_path(path):
    """
    docstring_title

    @param path: 
    @type path: 
    @return: 
    @rtype: 
    """
    try:
        os.stat(path)
    except OSError:
        return False
    return True

def is_valid_md5(myhash):
    """
    docstring_title

    @param myhash: 
    @type myhash: 
    @return: 
    @rtype: 
    """
    if re.findall(r'(?i)(?<![a-z0-9])[a-f0-9]{32}(?![a-z0-9])', myhash):
        return True
    return False

def open_buffer():
    """
    docstring_title

    @return: 
    @rtype: 
    """
    try:
        import io as stringio
    except ImportError:
        import io as stringio
    return stringio.StringIO()

def seek_till_newline(f):
    """
    docstring_title

    @param f: 
    @type f: 
    @return: 
    @rtype: 
    """
    count = 0
    f.seek(count, os.SEEK_END)
    size = f.tell()
    while count > (size*-1):
        count -= 1
        f.seek(count, os.SEEK_END)
        myc = f.read(1)
        if myc == "\n":
            break
    f.seek(count+1, os.SEEK_END)
    pos = f.tell()
    f.truncate(pos)

def read_elf_class(elf_file):
    """
    docstring_title

    @param elf_file: 
    @type elf_file: 
    @return: 
    @rtype: 
    """
    import struct
    f = open(elf_file, "rb")
    f.seek(4)
    elf_class = f.read(1)
    f.close()
    elf_class = struct.unpack('B', elf_class)[0]
    return elf_class

def is_elf_file(elf_file):
    """
    docstring_title

    @param elf_file: 
    @type elf_file: 
    @return: 
    @rtype: 
    """
    import struct
    f = open(elf_file, "rb")
    data = f.read(4)
    f.close()
    try:
        data = struct.unpack('BBBB', data)
    except struct.error:
        return False
    if data == (127, 69, 76, 70):
        return True
    return False

def resolve_dynamic_library(library, requiring_executable):
    """
    Resolve given library name (as contained into ELF metadata) to
    a library path.

    @param library: library name (as contained into ELF metadata)
    @type library: string
    @param requiring_executable: path to ELF object that contains the given
        library name
    @type requiring_executable: string
    @return: resolved library path
    @rtype: string
    """
    def do_resolve(mypaths):
        """
        docstring_title

        @param mypaths: 
        @type mypaths: 
        @return: 
        @rtype: 
        """
        found_path = None
        for mypath in mypaths:
            mypath = os.path.join(etpConst['systemroot']+mypath, library)
            if not os.access(mypath, os.R_OK):
                continue
            if os.path.isdir(mypath):
                continue
            if not is_elf_file(mypath):
                continue
            found_path = mypath
            break
        return found_path

    mypaths = collect_linker_paths()
    found_path = do_resolve(mypaths)

    if not found_path:
        mypaths = read_elf_linker_paths(requiring_executable)
        found_path = do_resolve(mypaths)

    return found_path

readelf_avail_check = False
ldd_avail_check = False
def read_elf_dynamic_libraries(elf_file):
    """
    docstring_title

    @param elf_file: 
    @type elf_file: 
    @return: 
    @rtype: 
    """
    global readelf_avail_check
    if not readelf_avail_check:
        if not os.access(etpConst['systemroot']+"/usr/bin/readelf", os.X_OK):
            FileNotFound('FileNotFound: no readelf')
        readelf_avail_check = True
    return set([x.strip().split()[-1][1:-1] for x in getstatusoutput('/usr/bin/readelf -d %s' % (elf_file,))[1].split("\n") if (x.find("(NEEDED)") != -1)])

def read_elf_broken_symbols(elf_file):
    """
    docstring_title

    @param elf_file: 
    @type elf_file: 
    @return: 
    @rtype: 
    """
    global ldd_avail_check
    if not ldd_avail_check:
        if not os.access(etpConst['systemroot']+"/usr/bin/ldd", os.X_OK):
            FileNotFound('FileNotFound: no ldd')
        ldd_avail_check = True
    return set([x.strip().split("\t")[0].split()[-1] for x in getstatusoutput('/usr/bin/ldd -r %s' % (elf_file,))[1].split("\n") if (x.find("undefined symbol:") != -1)])

def read_elf_linker_paths(elf_file):
    """
    docstring_title

    @param elf_file: 
    @type elf_file: 
    @return: 
    @rtype: 
    """
    global readelf_avail_check
    if not readelf_avail_check:
        if not os.access(etpConst['systemroot']+"/usr/bin/readelf", os.X_OK):
            FileNotFound('FileNotFound: no readelf')
        readelf_avail_check = True
    data = [x.strip().split()[-1][1:-1].split(":") for x in getstatusoutput('readelf -d %s' % (elf_file,))[1].split("\n") if not ((x.find("(RPATH)") == -1) and (x.find("(RUNPATH)") == -1))]
    mypaths = []
    for mypath in data:
        for xpath in mypath:
            xpath = xpath.replace("$ORIGIN", os.path.dirname(elf_file))
            mypaths.append(xpath)
    return mypaths

def xml_from_dict_extended(dictionary):
    """
    docstring_title

    @param dictionary: 
    @type dictionary: 
    @return: 
    @rtype: 
    """
    from xml.dom import minidom
    doc = minidom.Document()
    ugc = doc.createElement("entropy")
    for key, value in list(dictionary.items()):
        item = doc.createElement('item')
        item.setAttribute('value', key)
        if isinstance(value, str):
            mytype = "str"
        elif const_isunicode(value):
            mytype = "unicode"
        elif isinstance(value, list):
            mytype = "list"
        elif isinstance(value, set):
            mytype = "set"
        elif isinstance(value, frozenset):
            mytype = "frozenset"
        elif isinstance(value, dict):
            mytype = "dict"
        elif isinstance(value, tuple):
            mytype = "tuple"
        elif isinstance(value, int):
            mytype = "int"
        elif isinstance(value, float):
            mytype = "float"
        elif value == None:
            mytype = "None"
            value = "None"
        else: TypeError
        item.setAttribute('type', mytype)
        item_value = doc.createTextNode("%s" % (value,))
        item.appendChild(item_value)
        ugc.appendChild(item)
    doc.appendChild(ugc)
    return doc.toxml()

def dict_from_xml_extended(xml_string):
    """
    docstring_title

    @param xml_string: 
    @type xml_string: 
    @return: 
    @rtype: 
    """
    from xml.dom import minidom
    doc = minidom.parseString(xml_string)
    entropies = doc.getElementsByTagName("entropy")
    if not entropies:
        return {}
    entropy = entropies[0]
    items = entropy.getElementsByTagName('item')

    def convert_unicode(obj):
        if const_isunicode(obj):
            return obj
        return const_convert_to_unicode(obj)

    my_map = {
        "str": str,
        "unicode": convert_unicode,
        "list": list,
        "set": set,
        "frozenset": frozenset,
        "dict": dict,
        "tuple": tuple,
        "int": int,
        "float": float,
        "None": None,
    }

    mydict = {}
    for item in items:
        key = item.getAttribute('value')
        if not key: continue
        mytype = item.getAttribute('type')
        mytype_m = my_map.get(mytype)
        if mytype_m == None:
            raise TypeError()
        try:
            data = item.firstChild.data
        except AttributeError:
            data = ''
        if mytype in ("list", "set", "frozenset", "dict", "tuple",):
            if data:
                if data[0] not in ("(", "[", "s", "{",):
                    data = ''
            mydict[key] = eval(data)
        elif mytype == "None":
            mydict[key] = None
        else:
            mydict[key] = mytype_m(data)
    return mydict

def xml_from_dict(dictionary):
    """
    docstring_title

    @param dictionary: 
    @type dictionary: 
    @return: 
    @rtype: 
    """
    from xml.dom import minidom
    doc = minidom.Document()
    ugc = doc.createElement("entropy")
    for key, value in list(dictionary.items()):
        item = doc.createElement('item')
        item.setAttribute('value', key)
        item_value = doc.createTextNode(value)
        item.appendChild(item_value)
        ugc.appendChild(item)
    doc.appendChild(ugc)
    return doc.toxml()

def dict_from_xml(xml_string):
    """
    docstring_title

    @param xml_string: 
    @type xml_string: 
    @return: 
    @rtype: 
    """
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
        if not key:
            continue
        try:
            data = item.firstChild.data
        except AttributeError:
            data = ''
        mydict[key] = data
    return mydict

def create_package_filename(category, name, version, package_tag):
    """
    docstring_title

    @param category: 
    @type category: 
    @param name: 
    @type name: 
    @param version: 
    @type version: 
    @param package_tag: 
    @type package_tag: 
    @return: 
    @rtype: 
    """
    if package_tag:
        package_tag = "#%s" % (package_tag,)
    else:
        package_tag = ''

    package_name = "%s:%s-%s" % (category, name, version,)
    package_name += package_tag
    package_name += etpConst['packagesext']
    return package_name

def create_package_atom_string(category, name, version, package_tag):
    """
    docstring_title

    @param category: 
    @type category: 
    @param name: 
    @type name: 
    @param version: 
    @type version: 
    @param package_tag: 
    @type package_tag: 
    @return: 
    @rtype: 
    """
    if package_tag:
        package_tag = "#%s" % (package_tag,)
    else:
        package_tag = ''
    package_name = "%s/%s-%s" % (category, name, version,)
    package_name += package_tag
    return package_name

def extract_packages_from_set_file(filepath):
    """
    docstring_title

    @param filepath: 
    @type filepath: 
    @return: 
    @rtype: 
    """
    f = open(filepath, "r")
    items = set()
    line = f.readline()
    while line:
        x = line.strip().rsplit("#", 1)[0]
        if x and (not x.startswith('#')):
            items.add(x)
        line = f.readline()
    f.close()
    return items

def collect_linker_paths():
    """
    docstring_title

    @return: 
    @rtype: 
    """

    ldpaths = []
    try:
        f = open(etpConst['systemroot']+"/etc/ld.so.conf", "r")
        paths = f.readlines()
        for path in paths:
            path = path.strip()
            if path:
                if path[0] == "/":
                    ldpaths.append(os.path.normpath(path))
        f.close()
    except (IOError, OSError, TypeError, ValueError, IndexError,):
        pass

    # can happen that /lib /usr/lib are not in LDPATH
    if "/lib" not in ldpaths:
        ldpaths.append("/lib")
    if "/usr/lib" not in ldpaths:
        ldpaths.append("/usr/lib")

    return ldpaths

def collect_paths():
    """
    docstring_title

    @return: 
    @rtype: 
    """
    path = set()
    paths = os.getenv("PATH")
    if paths != None:
        paths = set(paths.split(":"))
        path |= paths
    return path

def list_to_utf8(mylist):
    """
    docstring_title

    @param mylist: 
    @type mylist: 
    @return: 
    @rtype: 
    """
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
