# -*- coding: utf-8 -*-
# Entropy miscellaneous tools module
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy miscellaneous tools module}.
    In this module are enclosed all the miscellaneous functions
    used around the Entropy codebase.

"""
import stat
import collections
import errno
import fcntl
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
import traceback
import gzip
import bz2
import mmap
import codecs
import struct

from entropy.output import print_generic
from entropy.const import etpConst, const_kill_threads, const_islive, \
    const_isunicode, const_convert_to_unicode, const_convert_to_rawstring, \
    const_israwstring, const_secure_config_file, const_is_python3, \
    const_mkstemp, const_file_readable
from entropy.exceptions import FileNotFound, InvalidAtom, DirectoryNotFound


_READ_SIZE = 1024000


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

    if uid is None:
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
    traceback.print_exc(file = f)

def get_traceback(tb_obj = None):
    """
    Return last available Python traceback.

    @return: traceback data
    @rtype: string
    @keyword tb_obj: Python traceback object
    @type tb_obj: Python traceback instance
    """
    if const_is_python3():
        from io import StringIO
    else:
        from cStringIO import StringIO
    buf = StringIO()
    if tb_obj is not None:
        if const_is_python3():
            traceback.print_tb(tb_obj, file = buf)
        else:
            traceback.print_last(tb_obj, file = buf)
    else:
        last_type, last_value, last_traceback = sys.exc_info()
        traceback.print_exception(last_type, last_value, last_traceback,
                        file = buf)
        # cannot use this due to Python 2.6.x bug
        #traceback.print_last(file = buf)
    return buf.getvalue()

def print_exception(silent = False, tb_data = None, all_frame_data = False):
    """
    Print last Python exception and frame variables values (if available)
    to stdout.

    @keyword silent: do not print to stdout
    @type silent: bool
    @keyword tb_data: Python traceback object
    @type tb_data: Python traceback instance
    @keyword all_frame_data: print all variables in every frame
    @type all_frame_data: bool
    @return: exception data
    @rtype: list of strings
    """
    if not silent:
        traceback.print_last()
    data = []
    if tb_data is not None:
        tb = tb_data
    else:
        last_type, last_value, last_traceback = sys.exc_info()
        tb = last_traceback

    stack = []
    while True:
        if not tb:
            break
        if not tb.tb_next:
            break
        tb = tb.tb_next
        if all_frame_data:
            stack.append(tb.tb_frame)

    if not all_frame_data:
        stack.append(tb.tb_frame)

    #if not returndata: print
    for frame in stack:
        if not silent:
            print_generic("")
            print_generic("Frame %s in %s at line %s" % (frame.f_code.co_name,
                frame.f_code.co_filename, frame.f_lineno))
        data.append("Frame %s in %s at line %s\n" % (frame.f_code.co_name,
            frame.f_code.co_filename, frame.f_lineno))

        for key, value in list(frame.f_locals.items()):
            cur_str = ''
            cur_str = "\t%20s = " % key
            try:
                cur_str += repr(value) + "\n"
            except (AttributeError, NameError, TypeError):
                cur_str += "<ERROR WHILE PRINTING VALUE>\n"

            if not silent:
                sys.stdout.write(cur_str)
            data.append(cur_str)

    return data

def get_remote_data(url, timeout = 5):
    """
    Fetch data at given URL (all the ones supported by Python urllib) and
    return it.

    @param url: URL string
    @type url: string
    @keyword timeout: fetch timeout in seconds
    @type timeout: int
    @return: fetched data or False (when error occurred)
    @rtype: string or bool
    """
    import socket
    if const_is_python3():
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

    item = None
    try:
        item = urlmod.urlopen(url, timeout = timeout)
        result = item.readlines()
    except Exception:
        # urllib2.HTTPError
        # urllib2.URLError
        # httplib.BadStatusLine
        # httplib.InvalidURL
        # ValueError
        # IOError
        return False
    finally:
        if item is not None:
            item.close()
        socket.setdefaulttimeout(2)

    if not result:
        return False
    return result

def _is_png_file(path):
    with open(path, "rb") as f:
        x = f.read(4)
    if x == const_convert_to_rawstring('\x89PNG'):
        return True
    return False

def _is_jpeg_file(path):
    with open(path, "rb") as f:
        x = f.read(10)
    if x == const_convert_to_rawstring('\xff\xd8\xff\xe0\x00\x10JFIF'):
        return True
    return False

def _is_bmp_file(path):
    with open(path, "rb") as f:
        x = f.read(2)
    if x == const_convert_to_rawstring('BM'):
        return True
    return False

def _is_gif_file(path):
    with open(path, "rb") as f:
        x = f.read(5)
    if x == const_convert_to_rawstring('GIF89'):
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

def is_xmas():
    """
    Return whether today is April, 1st.
    Please keep the joke.

    @return: True if April 1st
    @rtype: bool
    """
    xmas = "25-12"
    cur_time = time.strftime("%d-%m")
    if xmas == cur_time:
        return True
    return False

def is_author_bday():
    """
    Return whether today is lxnay's birthday.

    @return: True if November 15
    @rtype: bool
    """
    xmas = "15-11"
    cur_time = time.strftime("%d-%m")
    if xmas == cur_time:
        return True
    return False

def is_st_valentine():
    """
    Return whether today is April, 1st.
    Please keep the joke.

    @return: True if April 1st
    @rtype: bool
    """
    st_val = "14-02"
    cur_time = time.strftime("%d-%m")
    if st_val == cur_time:
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
    if not isinstance(module, types.ModuleType):
        AttributeError("not a module")
    if not data:
        return

    username = None
    password = None
    authinfo = None
    if 'password' in data:
        username = data.pop('username')
    if 'password' in data:
        username = data.pop('password')
    if username is None or password is None:
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
    for elem in string:
        if not ((ord(elem) >= 0x20) and (ord(elem) <= 0x80)):
            return False
    return True

def is_valid_unicode(string):
    """
    Return whether passed string is unicode.

    @param string: string to test
    @type string: string
    @return: True if string is unicode
    @rtype: bool
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
    NOTE: This function does NOT consider hardlinks, roughly summing up
    file_list elements.

    @param file_list: list of file paths
    @type file_list: list
    @return: summed size in bytes
    @rtype: int
    """
    size = 0
    for myfile in file_list:
        try:
            mystat = os.lstat(myfile)
        except (OSError, IOError,):
            continue
        size += mystat.st_size
    return size

def sum_file_sizes_hardlinks(file_list):
    """
    Return file size sum of given list of paths.
    NOTE: This function does consider hardlinks, not counting the same files
    more than once.

    @param file_list: list of file paths
    @type file_list: list
    @return: summed size in bytes
    @rtype: int
    """
    size = 0
    inode_cache = set()
    for myfile in file_list:
        try:
            mystat = os.lstat(myfile)
        except (OSError, IOError,):
            continue
        inode = (mystat.st_ino, mystat.st_dev)
        if inode in inode_cache:
            continue
        inode_cache.add(inode)
        size += mystat.st_size
    inode_cache.clear()
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
    st = os.statvfs(mountpoint)
    freeblocks = st.f_bfree
    blocksize = st.f_bsize
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
    if sts is None:
        sts = 0
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
    try:
        sstat = os.lstat(src)
    except (OSError, IOError,) as err:
        print_generic("!!! Failed to lstat source in movefile()")
        print_generic("!!!", src)
        print_generic("!!!", repr(err))
        return False

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
            try:
                os.unlink(src)
            except OSError:
                pass
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
        except OSError as err:
            if err.errno != errno.EXDEV:
                # Some random error.
                print_generic("!!! Failed to move", src, "to", dest)
                print_generic("!!!", repr(err))
                return False
            # Invalid cross-device-link 'bind' mounted or actually Cross-Device

    if renamefailed:
        didcopy = True
        if stat.S_ISREG(sstat[stat.ST_MODE]):
            try: # For safety copy then move it over.
                while True:
                    tmp_dest = "%s#entropy_new_%s" % (dest, get_random_number(),)
                    if not os.path.lexists(tmp_dest):
                        break
                shutil.copyfile(src, tmp_dest)
                os.rename(tmp_dest, dest)
                didcopy = True
            except SystemExit as e:
                raise
            except (OSError, IOError, shutil.Error) as e:
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

def rename_keep_permissions(src, dest):
    """
    Call rename() for src -> dest files keeping dest permission
    bits and ownership. Useful in combination with mkstemp()
    If dest doesn't exist, ownership and permissions will
    be set through entropy.const's const_secure_config_file().
    File is moved using entropy.tools.movefile()

    @param src: path to source file
    @type src: string
    @param dest: path to dest file
    @type dest: string
    @raise OSError: if file cannot be moved.
    """
    dest_avail = True
    try:
        user = os.stat(dest)[stat.ST_UID]
        group = os.stat(dest)[stat.ST_GID]
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
        user = 0
        group = 0
        dest_avail = False
    if dest_avail:
        os.chown(src, user, group)
        shutil.copymode(dest, src)
    else:
        const_secure_config_file(src)
    if not movefile(src, dest):
        raise OSError(errno.EPERM, "cannot rename")

def atomic_write(filepath, content_str, encoding):
    """
    Atomically write string at content_str using given
    encoding to file.

    @param filepath: path where to write data atomically
    @type filepath: string
    @param content_str: string to write
    @type content_str: string
    @param encoding: encoding to use
    @type encoding: string
    @raise IOError: if data cannot be written
    @raise OSError: same as above
    """
    tmp_fd, tmp_path = None, None
    try:
        tmp_fd, tmp_path = const_mkstemp(prefix="atomic_write.")
        with codecs_fdopen(tmp_fd, "w", encoding) as tmp_f:
            tmp_f.write(content_str)
        rename_keep_permissions(tmp_path, filepath)
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError as err:
                if err.errno != errno.EBADF:
                    raise
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise

def get_random_number():
    """
    Return a random number between 10000 and 99999.

    @return: random number
    @rtype: int
    """
    random.seed()
    return random.randint(10000, 99999)

def split_indexable_into_chunks(mystr, chunk_len):
    """
    Split indexable object into chunks.

    @param mystr: indexable object
    @type mystr: Python object
    @param chunk_len: maximum length of a single chunk
    @type chunk_len: int
    @return: list of chunks
    @rtype: list
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

def md5sum(filepath):
    """
    Calculate md5 hash of given file at path.

    @param filepath: path to file
    @type filepath: string
    @return: md5 hex digest
    @rtype: string
    """
    m = hashlib.md5()
    with open(filepath, "rb") as readfile:
        block = readfile.read(_READ_SIZE)
        while block:
            m.update(block)
            block = readfile.read(_READ_SIZE)
    return m.hexdigest()

def sha512(filepath):
    """
    Calculate SHA512 hash of given file at path.

    @param filepath: path to file
    @type filepath: string
    @return: SHA512 hex digest
    @rtype: string
    """
    m = hashlib.sha512()
    with open(filepath, "rb") as readfile:
        block = readfile.read(_READ_SIZE)
        while block:
            m.update(block)
            block = readfile.read(_READ_SIZE)
    return m.hexdigest()

def sha256(filepath):
    """
    Calculate SHA256 hash of given file at path.

    @param filepath: path to file
    @type filepath: string
    @return: SHA256 hex digest
    @rtype: string
    """
    m = hashlib.sha256()
    with open(filepath, "rb") as readfile:
        block = readfile.read(_READ_SIZE)
        while block:
            m.update(block)
            block = readfile.read(_READ_SIZE)
    return m.hexdigest()

def sha1(filepath):
    """
    Calculate SHA1 hash of given file at path.

    @param filepath: path to file
    @type filepath: string
    @return: SHA1 hex digest
    @rtype: string
    """
    m = hashlib.sha1()
    with open(filepath, "rb") as readfile:
        block = readfile.read(_READ_SIZE)
        while block:
            m.update(block)
            block = readfile.read(_READ_SIZE)
    return m.hexdigest()

def md5sum_directory(directory):
    """
    Return md5 hex digest of files in given directory

    @param directory: path to directory
    @type directory: string
    @return: md5 hex digest
    @rtype: string
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
            with open(myfile, "rb") as readfile:
                block = readfile.read(_READ_SIZE)
                while block:
                    m.update(block)
                    block = readfile.read(_READ_SIZE)
    return m.hexdigest()

def md5obj_directory(directory):
    """
    Return hashlib.md5 instance of calculated md5 of files in given directory

    @param directory: path to directory
    @type directory: string
    @return: hashlib.md5 instance
    @rtype: hashlib.md5
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
            with open(myfile, "rb") as readfile:
                block = readfile.read(_READ_SIZE)
                while block:
                    m.update(block)
                    block = readfile.read(_READ_SIZE)
    return m

def uncompress_file(file_path, destination_path, opener):
    """
    Uncompress file at file_path into destination_path using file opener
    function passed.

    @param file_path: path to file
    @type file_path: string
    @param destination_path: destination path
    @type destination_path: string
    @param opener: file_path opener function
    @type opener: function
    """
    with open(destination_path, "wb") as f_out:
        f_in = opener(file_path, "rb")
        data = f_in.read(_READ_SIZE)
        while data:
            f_out.write(data)
            data = f_in.read(_READ_SIZE)
        f_in.close()

def compress_file(file_path, destination_path, opener, compress_level = None):
    """
    Compress file at file_path into destination_path (file path) using
    transparent compression file opener and given compression level (from 0
    to 9).

    @param file_path: path to compress
    @type file_path: string
    @param destination_path: path where to save compressed file
    @type destination_path: string
    @param opener: compressed file_path open function
    @type opener: function
    @keyword compress_level: compression level, from 0 to 9
    @type compress_level: int
    """
    with open(file_path, "rb") as f_in:
        f_out = None
        try:
            if compress_level is not None:
                f_out = opener(destination_path, "wb",
                    compresslevel = compress_level)
            else:
                f_out = opener(destination_path, "wb")
            data = f_in.read(_READ_SIZE)
            while data:
                f_out.write(data)
                data = f_in.read(_READ_SIZE)
        finally:
            if f_out is not None:
                f_out.close()

def compress_files(dest_file, files_to_compress, compressor = "bz2"):
    """
    Compress file paths listed inside files_to_compress into dest_file using
    given compression type "compressor". Supported compression types are
    "bz2" and "gz".

    @param dest_file: path where to save compressed file
    @type dest_file: string
    @param files_to_compress: list of file paths to compress
    @type files_to_compress: list
    @keyword compressor: compressor type
    @type compressor: string
    @raise AttributeError: if compressor value is unsupported
    """

    if compressor not in ("bz2", "gz",):
        AttributeError("invalid compressor specified")

    id_strings = {}
    tar = None
    try:
        tar = tarfile.open(dest_file, "w:%s" % (compressor,))
        for path in files_to_compress:
            exist = os.lstat(path)
            tarinfo = tar.gettarinfo(path, os.path.basename(path))
            tarinfo.uname = id_strings.setdefault(tarinfo.uid, str(tarinfo.uid))
            tarinfo.gname = id_strings.setdefault(tarinfo.gid, str(tarinfo.gid))
            if not stat.S_ISREG(exist.st_mode):
                continue
            # explicitly NOT supporting hard links!
            if tarinfo.issym():
                # zap symlinks to empty files
                tarinfo.type = tarfile.REGTYPE
            with open(path, "rb") as f:
                tar.addfile(tarinfo, f)
    finally:
        if tar is not None:
            tar.close()

def universal_uncompress(compressed_file, dest_path, catch_empty = False):
    """
    Universally uncompress (automatic detection) compressed file at
    compressed_file into dest_path. "catch_empty" is used in case of
    empty compressed files, in which case a tarfile.ReadError exception
    is raised.

    @param compressed_file: path to compressed file
    @type compressed_file: string
    @param dest_path: path where to uncompress compressed file content
    @type dest_path: string
    @keyword catch_empty: if True, empty compressed file won't cause
        tarfile.ReadError exception to be raised
    @type catch_empty: bool
    """

    tar = None
    try:

        try:
            tar = tarfile.open(compressed_file, "r")
        except tarfile.ReadError:
            if catch_empty:
                return True
            return False
        except EOFError:
            return False

        if not const_is_python3():
            dest_path = dest_path.encode('utf-8')
        directories = []
        for tarinfo in tar:
            if tarinfo.isdir():
                # Extract directory with a safe mode, so that
                # all files below can be extracted as well.
                try:
                    os.makedirs(os.path.join(dest_path, tarinfo.name), 0o777)
                except EnvironmentError:
                    pass
                directories.append(tarinfo)
            tar.extract(tarinfo, dest_path)
            del tar.members[:]
            directories.append(tarinfo)

        directories.sort(key = lambda x: x.name, reverse = True)

        # Set correct owner, mtime and filemode on directories.
        for tarinfo in directories:
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

    except EOFError:
        return False

    finally:
        if tar is not None:
            tar.close()

    return True

def get_uncompressed_size(compressed_file):
    """
    Return the size of uncompressed data of a tarball (compression algos that
    tarfile supports).

    @param compressed_file: path to compressed file
    @type compressed_file: string
    @return: size of the data inside the tarball
    @rtype: int
    """
    tar = None
    accounted_size = 0
    try:

        try:
            tar = tarfile.open(compressed_file, "r")
        except tarfile.ReadError:
            return accounted_size
        except EOFError:
            return accounted_size

        for tarinfo in tar:
            accounted_size += tarinfo.size
        del tar.members[:]

    except EOFError:
        return accounted_size

    finally:
        if tar is not None:
            tar.close()

    return accounted_size

def unpack_gzip(gzipfilepath):
    """
    Unpack .gz file.

    @param gzipfilepath: path to .gz file
    @type gzipfilepath: string
    @return: path to uncompressed file
    @rtype: string
    """
    filepath = gzipfilepath[:-3] # remove .gz
    fd, tmp_path = const_mkstemp(
        prefix="unpack_gzip.", dir=os.path.dirname(filepath))
    with os.fdopen(fd, "wb") as item:
        filegz = gzip.GzipFile(gzipfilepath, "rb")
        chunk = filegz.read(_READ_SIZE)
        while chunk:
            item.write(chunk)
            chunk = filegz.read(_READ_SIZE)
        filegz.close()
    os.rename(tmp_path, filepath)
    return filepath

def unpack_bzip2(bzip2filepath):
    """
    Unpack .bz2 file.

    @param bzip2filepath: path to .bz2 file
    @type bzip2filepath: string
    @return: path to uncompressed file
    @rtype: string
    """
    filepath = bzip2filepath[:-4] # remove .bz2
    fd, tmp_path = const_mkstemp(
        prefix="unpack_bzip2.",
        dir=os.path.dirname(filepath))
    with os.fdopen(fd, "wb") as item:
        filebz2 = bz2.BZ2File(bzip2filepath, "rb")
        chunk = filebz2.read(_READ_SIZE)
        while chunk:
            item.write(chunk)
            chunk = filebz2.read(_READ_SIZE)
        filebz2.close()
    os.rename(tmp_path, filepath)
    return filepath

def generate_entropy_delta_file_name(pkg_name_a, pkg_name_b, hash_tag):
    """
    Generate Entropy package binary delta file name basing on package file names
    given (from pkg_path_a to pkg_path_b). hash_tag is by convention an md5 hash

    @param pkg_name_a: package file name A
    @type pkg_name_a: string
    @param pkg_name_b: package file name B
    @type pkg_name_b: string
    @param hash_tag: arbitrary hash tag appended to file name
    @type hash_tag: string
    @return: package delta file name (not full path!)
    @rtype: string
    @raise AttributeError: if api is unsupported
    """
    from_pkg_name = os.path.splitext(pkg_name_a.replace(":", "+"))[0]
    delta_hashed_name = "%s~%s%s" % (from_pkg_name,
        hash_tag, etpConst['packagesdeltaext'])
    return delta_hashed_name

def _delta_extract_bz2(bz2_path, new_path_fd):
    with os.fdopen(new_path_fd, "wb") as item:
        filebz2 = bz2.BZ2File(bz2_path, "rb")
        chunk = filebz2.read(_READ_SIZE)
        while chunk:
            item.write(chunk)
            chunk = filebz2.read(_READ_SIZE)
        filebz2.close()

def _delta_extract_gzip(gzip_path, new_path_fd):
    with os.fdopen(new_path_fd, "wb") as item:
        file_gz = gzip.GzipFile(gzip_path, "rb")
        chunk = file_gz.read(_READ_SIZE)
        while chunk:
            item.write(chunk)
            chunk = file_gz.read(_READ_SIZE)
        file_gz.close()

_BSDIFF_EXEC = "/usr/bin/bsdiff"
_BSPATCH_EXEC = "/usr/bin/bspatch"
_DELTA_DECOMPRESSION_MAP = {
    "bz2": _delta_extract_bz2,
    "gz": _delta_extract_gzip,
}
_DELTA_COMPRESSION_MAP = {
    "bz2": "bz2.BZ2File",
    "gzip": "gzip.GzipFile",
}
_DEFAULT_PKG_COMPRESSION = "bz2"

def is_entropy_delta_available():
    """
    Return whether Entropy delta packages support is enabled by checking
    if bsdiff executables are available. Moreover, if ETP_NO_EDELTA environment
    variable is set, this function will return False.

    @return: True, if service is available
    @rtype: bool
    """
    if os.getenv("ETP_NO_EDELTA") is not None:
        return False
    if os.path.isfile(_BSDIFF_EXEC) and os.path.isfile(_BSPATCH_EXEC):
        return True
    return False

def generate_entropy_delta(pkg_path_a, pkg_path_b, hash_tag,
    pkg_compression = None):
    """
    Generate Entropy package delta between pkg_path_a (from file) and
    pkg_path_b (to file).

    @param pkg_path_a: package path A (from file)
    @type pkg_path_a: string
    @param pkg_path_a: package path B (to file)
    @type pkg_path_a: string
    @param hash_tag: hash tag to append to Entropy package delta file name
    @type hash_tag: string
    @keyword pkg_compression: default package compression, can be "bz2" or "gz".
        if None, "bz2" is selected.
    @type: string
    @return: path to newly created delta file, return None if error
    @rtype: string or None
    @raise KeyError: if pkg_compression is unsupported
    @raise IOError: if delta cannot be generated
    @raise OSError: if some other error happens during the generation
    """
    from entropy.spm.plugins.factory import get_default_class as get_spm_class

    if pkg_compression is None:
        _delta_extractor = _DELTA_DECOMPRESSION_MAP[_DEFAULT_PKG_COMPRESSION]
    else:
        _delta_extractor = _DELTA_DECOMPRESSION_MAP[pkg_compression]

    close_fds = []
    remove_paths = []

    try:

        tmp_fd_a, tmp_path_a = const_mkstemp(
            prefix="generate_entropy_delta.",
            dir=os.path.dirname(pkg_path_a))
        close_fds.append(tmp_fd_a)
        remove_paths.append(tmp_path_a)

        tmp_fd_b, tmp_path_b = const_mkstemp(
            prefix="generate_entropy_delta.",
            dir=os.path.dirname(pkg_path_b))
        close_fds.append(tmp_fd_b)
        remove_paths.append(tmp_path_b)

        tmp_fd, tmp_path = const_mkstemp(
            prefix="entropy.tools.generate_entropy_delta")
        close_fds.append(tmp_fd)
        remove_paths.append(tmp_path)

        tmp_fd_spm, tmp_path_spm = const_mkstemp(
            prefix="entropy.tools.generate_entropy_delta")
        close_fds.append(tmp_fd_spm)
        remove_paths.append(tmp_path_spm)

        _delta_extractor(pkg_path_a, tmp_fd_a)
        _delta_extractor(pkg_path_b, tmp_fd_b)

        pkg_path_b_dir = os.path.dirname(pkg_path_b)
        delta_fn = generate_entropy_delta_file_name(
            os.path.basename(pkg_path_a), os.path.basename(pkg_path_b),
            hash_tag)

        delta_file = os.path.join(pkg_path_b_dir,
            etpConst['packagesdeltasubdir'], delta_fn)
        delta_dir = os.path.dirname(delta_file)
        if not os.path.isdir(delta_dir):
            os.mkdir(delta_dir, 0o775)

        args = (_BSDIFF_EXEC, tmp_path_a, tmp_path_b, delta_file)
        try:
            rc = subprocess.call(args)
        except OSError:
            # probably "ENOENT", but any OSError will be caught
            return None
        if rc != 0:
            return None

        # append Spm metadata
        get_spm_class().dump_package_metadata(pkg_path_b, tmp_path_spm)
        get_spm_class().aggregate_package_metadata(delta_file, tmp_path_spm)

        # append Entropy metadata
        dump_entropy_metadata(pkg_path_b, tmp_path)
        aggregate_entropy_metadata(delta_file, tmp_path)

    finally:
        for fd in close_fds:
            try:
                os.close(fd)
            except OSError as err:
                if err.errno != errno.EBADF:
                    raise

        for pkg_f in remove_paths:
            try:
                os.remove(pkg_f)
            except (IOError, OSError):
                continue

    return delta_file

def apply_entropy_delta(pkg_path_a, delta_path, new_pkg_path_b,
    pkg_compression = None):
    """
    Apply Entropy package delta file to pkg_path_a generating pkg_path_b (which
    is returned in case of success). If delta cannot be generated, IOError is
    raised.

    @param pkg_path_a: path to package A
    @type pkg_path_a: string
    @param delta_path: path to entropy package delta
    @type delta_path: string
    @param new_pkg_path_b: path where to store newly created package B
    @type new_pkg_path_b: string
    @keyword pkg_compression: default package compression, can be "bz2" or "gz".
        if None, "bz2" is selected.
    @type: string
    @raise IOError: if delta cannot be generated.
    """
    from entropy.spm.plugins.factory import get_default_class as get_spm_class

    if pkg_compression is None:
        _pkg_extractor = _DELTA_DECOMPRESSION_MAP[_DEFAULT_PKG_COMPRESSION]
        used_compression = _DELTA_COMPRESSION_MAP[_DEFAULT_PKG_COMPRESSION]
    else:
        _pkg_extractor = _DELTA_DECOMPRESSION_MAP[pkg_compression]
        used_compression = _DELTA_COMPRESSION_MAP[pkg_compression]

    close_fds = []
    remove_paths = []

    try:

        tmp_fd, tmp_delta_path = const_mkstemp(
            prefix="apply_entropy_delta.",
            dir=os.path.dirname(delta_path))
        close_fds.append(tmp_fd)
        remove_paths.append(tmp_delta_path)

        tmp_spm_fd, tmp_spm_path = const_mkstemp(
            prefix="apply_entropy_delta.",
            dir=os.path.dirname(delta_path))
        close_fds.append(tmp_spm_fd)
        remove_paths.append(tmp_spm_path)

        tmp_fd_a, tmp_path_a = const_mkstemp(
            prefix="apply_entropy_delta.",
            dir=os.path.dirname(pkg_path_a))
        close_fds.append(tmp_fd_a)
        remove_paths.append(tmp_path_a)

        tmp_meta_fd, tmp_metadata_path = const_mkstemp(
            prefix="apply_entropy_delta.",
            dir=os.path.dirname(new_pkg_path_b))
        close_fds.append(tmp_meta_fd)
        remove_paths.append(tmp_metadata_path)

        tmp_fd_null, tmp_path_null = const_mkstemp(
            prefix="apply_entropy_delta.",
            dir=os.path.dirname(delta_path))
        close_fds.append(tmp_fd_null)
        remove_paths.append(tmp_path_null)

        new_pkg_path_b_tmp = new_pkg_path_b + ".edelta_work"
        new_pkg_path_b_tmp_compressed = new_pkg_path_b_tmp + ".compress"

        # remove entropy metadata from pkg delta, will be appended to package
        # right after
        remove_entropy_metadata(delta_path, tmp_delta_path)
        # get spm metadata
        get_spm_class().dump_package_metadata(delta_path, tmp_spm_path)

        _pkg_extractor(pkg_path_a, tmp_fd_a)

        with os.fdopen(tmp_fd_null, "w") as null_f:
            argv = (_BSPATCH_EXEC, tmp_path_a, new_pkg_path_b_tmp,
                tmp_delta_path)
            try:
                rc = subprocess.call(argv, stdout = null_f, stderr = null_f)
            except OSError as err:
                raise IOError("%s OSError: %s" % (_BSPATCH_EXEC, err.errno,))
            if rc != 0:
                raise IOError("%s returned error: %s" % (_BSPATCH_EXEC, rc,))

        # extract entropy metadata
        dump_entropy_metadata(delta_path, tmp_metadata_path)
        compress_file(new_pkg_path_b_tmp, new_pkg_path_b_tmp_compressed,
            eval(used_compression), compress_level = 9)

        # add spm metadata
        get_spm_class().aggregate_package_metadata(
            new_pkg_path_b_tmp_compressed, tmp_spm_path)
        # add entropy metadata
        aggregate_entropy_metadata(new_pkg_path_b_tmp_compressed,
            tmp_metadata_path)
        os.rename(new_pkg_path_b_tmp_compressed, new_pkg_path_b)

    finally:
        for fd in close_fds:
            try:
                os.close(fd)
            except OSError as err:
                if err.errno != errno.EBADF:
                    raise

        for path in remove_paths:
            try:
                os.remove(path)
            except (IOError, OSError):
                pass


def aggregate_entropy_metadata(entropy_package_file, entropy_metadata_file):
    """
    Add Entropy metadata dump file to given Entropy package file.

    @param entropy_package_file: path to Entropy package file
    @type entropy_package_file: string
    @param entropy_metadata_file: path to Entropy metadata file
    @type entropy_metadata_file: string
    """
    mmap_size_th = 4096000 # 4mb threshold
    with open(entropy_package_file, "ab") as f:
        f.write(const_convert_to_rawstring(etpConst['databasestarttag']))
        with open(entropy_metadata_file, "rb") as g:
            f_size = os.lstat(entropy_metadata_file).st_size
            mmap_f = None
            try:
                if f_size > mmap_size_th:
                    try:
                        mmap_f = mmap.mmap(g.fileno(), f_size,
                            flags = mmap.MAP_PRIVATE,
                            prot = mmap.PROT_READ)
                    except MemoryError:
                        mmap_f = None

                while True:
                    if mmap_f is not None:
                        chunk = mmap_f.read(_READ_SIZE)
                    else:
                        chunk = g.read(_READ_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
            finally:
                if mmap_f is not None:
                    mmap_f.close()

def dump_entropy_metadata(entropy_package_file, entropy_metadata_file):
    """
    Dump Entropy package metadata from Entropy package file to
    entropy_metadata_file

    @param entropy_package_file: path to Entropy package file
    @type entropy_package_file: string
    @keyword entropy_metadata_file: path where to store extracted metadata
    @type entropy_metadata_file: string
    @return: True, if extraction went successful
    @rtype: bool
    """
    mmap_size_th = 4096000 # 4mb threshold
    with open(entropy_package_file, "r+b") as old:
        old_mmap = None
        try:
            try:
                f_size = os.stat(entropy_package_file).st_size
            except OSError as err:
                return False

            if f_size <= 0:
                # WTF!
                return False
            # avoid security flaw caused by file size growing race condition
            # we conside the file size static
            start_position = None
            if f_size < mmap_size_th:
                # use mmap
                try:
                    old_mmap = mmap.mmap(old.fileno(), f_size,
                        flags = mmap.MAP_PRIVATE,
                        prot = mmap.PROT_READ)
                except MemoryError:
                    old_mmap = None
                if old_mmap is not None:
                    start_position = _locate_edb(old_mmap)

            if old_mmap is None:
                start_position = _locate_edb(old)
            if start_position is None:
                return False

            with open(entropy_metadata_file, "wb") as db:
                while True:
                    if old_mmap is None:
                        data = old.read(_READ_SIZE)
                    else:
                        data = old_mmap.read(_READ_SIZE)
                    if not data:
                        break
                    db.write(data)
        finally:
            if old_mmap is not None:
                old_mmap.close()

    return True

def _locate_edb(fileobj):

    # position old to the end
    fileobj.seek(0, os.SEEK_END)
    # read backward until we find
    xbytes = fileobj.tell()
    counter = xbytes - 1

    db_tag = etpConst['databasestarttag']
    # for Python 3.x
    raw_db_tag = const_convert_to_rawstring(db_tag)
    db_tag_len = len(db_tag)
    # NOTE: it was 30Mb, but app-doc/php-docs db size was 31MB
    # xonotic-data wants more, raise to 500Mb and forget
    give_up_threshold = 1024000 * 500 # 500Mb
    # cannot index a bytes object in Python3, it returns int !
    entry_point = const_convert_to_rawstring(db_tag[::-1][0])
    max_read_len = 8
    start_position = None

    while counter >= 0:
        cur_threshold = abs((counter-xbytes))
        if cur_threshold >= give_up_threshold:
            start_position = None
            break
        fileobj.seek(counter-xbytes, os.SEEK_END)
        read_bytes = fileobj.read(max_read_len)
        read_len = len(read_bytes)
        entry_idx = read_bytes.rfind(entry_point)
        if entry_idx != -1:
            rollback = (read_len - entry_idx) * -1
            fileobj.seek(rollback, os.SEEK_CUR)
            chunk = fileobj.read(db_tag_len)
            if chunk == raw_db_tag:
                start_position = fileobj.tell()
                break
        counter -= read_len

    return start_position

def remove_entropy_metadata(entropy_package_file, save_path):
    """
    Remove Entropy metadata from Entropy package file. Save new Entropy package
    file into save_path.

    @param entropy_package_file: path to Entropy package file
    @type entropy_package_file: string
    @param save_path: path where to save new "Entropy" package file (without
        Entropy metadata)
    @type save_path: string
    @return: True, if removal went successful
    @rtype: bool
    """
    with open(entropy_package_file, "rb") as old:

        start_position = _locate_edb(old)
        if not start_position:
            old.close()
            return False

        with open(save_path, "wb") as new:
            old.seek(0)
            counter = 0
            max_read_len = 1024
            db_tag = const_convert_to_rawstring(etpConst['databasestarttag'])
            db_tag_len = len(db_tag)
            start_position -= db_tag_len

            while counter < start_position:
                delta = start_position - counter
                if delta < max_read_len:
                    max_read_len = delta
                xbytes = old.read(max_read_len)
                read_bytes = len(xbytes)
                new.write(xbytes)
                counter += read_bytes

    return True

def create_md5_file(filepath):
    """
    Create valid MD5 file off filepath.

    @param filepath: file path to read
    @type filepath: string
    @return: path to MD5 file
    @rtype: string
    """
    md5hash = md5sum(filepath)
    hashfile = filepath+etpConst['packagesmd5fileext']
    enc = etpConst['conf_encoding']
    with codecs.open(hashfile, "w", encoding=enc) as f:
        name = os.path.basename(filepath)
        f.write(md5hash)
        f.write("  ")
        f.write(name)
        f.write("\n")
    return hashfile

def create_sha512_file(filepath):
    """
    Create valid SHA512 file off filepath.

    @param filepath: file path to read
    @type filepath: string
    @return: path to SHA512 file
    @rtype: string
    """
    sha512hash = sha512(filepath)
    hashfile = filepath+etpConst['packagessha512fileext']
    enc = etpConst['conf_encoding']
    with codecs.open(hashfile, "w", encoding=enc) as f:
        fname = os.path.basename(filepath)
        f.write(sha512hash)
        f.write("  ")
        f.write(fname)
        f.write("\n")
    return hashfile

def create_sha256_file(filepath):
    """
    Create valid SHA256 file off filepath.

    @param filepath: file path to read
    @type filepath: string
    @return: path to SHA256 file
    @rtype: string
    """
    sha256hash = sha256(filepath)
    hashfile = filepath+etpConst['packagessha256fileext']
    enc = etpConst['conf_encoding']
    with codecs.open(hashfile, "w", encoding=enc) as f:
        fname = os.path.basename(filepath)
        f.write(sha256hash)
        f.write("  ")
        f.write(fname)
        f.write("\n")
    return hashfile

def create_sha1_file(filepath):
    """
    Create valid SHA1 file off filepath.

    @param filepath: file path to read
    @type filepath: string
    @return: path to SHA1 file
    @rtype: string
    """
    sha1hash = sha1(filepath)
    hashfile = filepath+etpConst['packagessha1fileext']
    enc = etpConst['conf_encoding']
    with codecs.open(hashfile, "w", encoding=enc) as f:
        fname = os.path.basename(filepath)
        f.write(sha1hash)
        f.write("  ")
        f.write(fname)
        f.write("\n")
    return hashfile

def compare_md5(filepath, checksum):
    """
    Compare MD5 of filepath with the one given (checksum).

    @param filepath: path to file to "md5sum"
    @type filepath: string
    @param checksum: known to be good MD5 checksum
    @type checksum: string
    @return: True, if MD5 matches
    @rtype: bool
    """
    checksum = str(checksum)
    result = md5sum(filepath)
    result = str(result)
    if checksum == result:
        return True
    return False

def get_hash_from_md5file(md5path):
    """
    Extract md5 hash from md5 file.
    If md5 file is corrupted or invalid, raise ValueError.

    @param md5path: path to .md5 file
    @type md5path: string
    @return: md5 hex digest
    @rtype: string
    @raise ValueError: if md5path contains invalid data
    """
    enc = etpConst['conf_encoding']
    with codecs.open(md5path, "r", encoding=enc) as md5_f:
        md5_str = md5_f.read(32)
        if (not is_valid_md5(md5_str)) or len(md5_str) < 32:
            raise ValueError("invalid md5 file")
        return md5_str

def compare_sha512(filepath, checksum):
    """
    Compare SHA512 of filepath with the one given (checksum).

    @param filepath: path to file to check
    @type filepath: string
    @param checksum: known to be good SHA512 checksum
    @type checksum: string
    @return: True, if SHA512 matches
    @rtype: bool
    """
    checksum = str(checksum)
    result = sha512(filepath)
    result = str(result)
    if checksum == result:
        return True
    return False

def compare_sha256(filepath, checksum):
    """
    Compare SHA256 of filepath with the one given (checksum).

    @param filepath: path to file to check
    @type filepath: string
    @param checksum: known to be good SHA256 checksum
    @type checksum: string
    @return: True, if SHA256 matches
    @rtype: bool
    """
    checksum = str(checksum)
    result = sha256(filepath)
    result = str(result)
    if checksum == result:
        return True
    return False

def compare_sha1(filepath, checksum):
    """
    Compare SHA1 of filepath with the one given (checksum).

    @param filepath: path to file to check
    @type filepath: string
    @param checksum: known to be good SHA1 checksum
    @type checksum: string
    @return: True, if SHA1 matches
    @rtype: bool
    """
    checksum = str(checksum)
    result = sha1(filepath)
    result = str(result)
    if checksum == result:
        return True
    return False

def md5string(string):
    """
    Return md5 hex digest of given string

    @param string: string to "md5"
    @type string: string
    @return: md5 hex digest
    @rtype: string
    """
    if const_isunicode(string):
        string = const_convert_to_rawstring(string)
    m = hashlib.md5()
    m.update(string)
    return m.hexdigest()

def generic_file_content_parser(filepath, comment_tag = "#",
    filter_comments = True, encoding = None):
    """
    Generic unix-style file content parser. Return a list of parsed lines with
    filtered comments.

    @param filepath: configuration file to parse
    @type filepath: string
    @keyword comment_tag: default comment tag (column where comments starts) if
        line already contains valid data (doesn't start with comment_tag)
    @type comment_tag: string
    @keyword filter_comments: filter out comments, True by default.
        Are considered comments the lines starting with "#"
    @type filter_comments: bool
    @return: list representing file content
    @rtype: list
    """
    data = []
    content = []

    try:
        if encoding is None:
            with open(filepath, "r") as gen_f:
                content += gen_f.readlines()
        else:
            with codecs.open(filepath, "r", encoding=encoding) as gen_f:
                content += gen_f.readlines()
    except (OSError, IOError) as err:
        if err.errno != errno.ENOENT:
            raise
    else:
        # filter comments and white lines
        content = [x.strip().rsplit(comment_tag, 1)[0].strip() for x \
            in content if x.strip()]
        # filter out empty lines
        content = [x for x in content if x.strip()]
        if filter_comments:
            content = [x for x in content if not x.startswith("#")]
        for line in content:
            if line in data:
                continue
            data.append(line)

    return data

def isnumber(x):
    """
    Determine whether x is a number of any sort. "x" can be a string or float.

    @param x: misterious object
    @type x: Python object
    @return: True, if x can be converted to int
    @rtype: bool
    """
    try:
        int(x)
        return True
    except ValueError:
        return False


def istextfile(filename, blocksize = 512):
    """
    Return whether file at filename is a text file by reading the first
    blocksize bytes.

    @param filename: file path to parse
    @type filename: string
    @keyword blocksize: chunk of bytes to read
    @type blocksize: int
    @return: True, if text file
    @rtype: bool
    """
    try:
        with open(filename, "r") as f:
            r = istext(f.read(blocksize))
    except (OSError, IOError):
        return False
    return r

def istext(mystring):
    """
    Determine whether given string is text.

    @param mystring: string to parse
    @type mystring: string
    @return: True, if string is text
    @rtype: bool
    """
    if const_is_python3():
        char_map = list(map(chr, list(range(32, 127))))
        text_characters = "".join(char_map + list("\n\r\t\b"))
        _null_trans = str.maketrans(text_characters, text_characters)
    else:
        import string
        _null_trans = string.maketrans("", "")
        text_characters = "".join(list(map(chr, list(range(32, 127)))) + \
            list("\n\r\t\b"))

    if "\0" in mystring:
        return False

    if not mystring:  # Empty files are considered text
        return True

    # Get the non-text characters (maps a character to itself then
    # use the 'remove' option to get rid of the text characters.)
    if const_is_python3():
        t = mystring.translate(_null_trans)
        # If more than 30% non-text characters, then
        # this is considered a binary file
        if float(len(t))/len(mystring) > 0.70:
            return True
        return False
    else:
        t = mystring.translate(_null_trans, text_characters)
        # If more than 30% non-text characters, then
        # this is considered a binary file
        if float(len(t))/len(mystring) > 0.30:
            return False
        return True

def spliturl(url):
    """
    Split any URL (ftp, file, http) into separate entities using urllib Python
    module. 

    @param url: URL sto split
    @type url: string
    @return: urllib.parse instance
    @rtype: urllib.parse
    """
    if const_is_python3():
        import urllib.parse as urlmod
    else:
        import urlparse as urlmod
    return urlmod.urlsplit(url)

def is_valid_uri(url):
    """
    Determine whether given url string is a valid URI, this function internally
    calls spliturl and looks for a set scheme. Anything that matches the
    string "something://" will be considered valid.

    @param url: URL sto split
    @type url: string
    @return: True if URI
    @rtype: bool
    """
    try:
        if spliturl(url).scheme:
            return True
        return False
    except ValueError:
        # invalid IPv6 URL
        return False

def _fix_uid_gid(tarinfo, epath):
    # workaround for buggy tar files
    uname = tarinfo.uname
    gname = tarinfo.gname
    ugdata_valid = False
    # the bug was caused by Portage bad quickpkg code that
    # added gname and uname values as string representation of
    # gid and uid respectively. So, since there are no groups and users
    # being full numbers, if we are able to convert them to int() it means
    # that tar metadata is fucked up.
    try:
        int(gname)
        int(uname)
    except ValueError:
        ugdata_valid = True
    try:
        if ugdata_valid: # NOTE: backward compat. remove after 2012
            # get uid/gid
            # if not found, returns -1 that won't change anything
            uid, gid = get_uid_from_user(uname), \
                get_gid_from_group(gname)
            if tarinfo.issym() and hasattr(os, "lchown"):
                os.lchown(epath, uid, gid)
            else:
                os.chown(epath, uid, gid)
    except OSError:
        pass

def apply_tarball_ownership(filepath, prefix_path):
    """
    Given an already extracted tarball available at prefix_path, and the
    original tarball file path at filepath, apply files and directories
    ownership to belonged files in prefix_path looking at tar metadata.
    This is required because users and groups referenced in tarballs are
    created at package setup phase during install.
    """

    tar = None
    try:
        try:
            tar = tarfile.open(filepath, "r")
        except tarfile.ReadError:
            return
        except EOFError:
            return

        encoded_path = prefix_path
        if not const_is_python3():
            encoded_path = encoded_path.encode('utf-8')
        entries = []

        deleter_counter = 3
        for tarinfo in tar:
            epath = os.path.join(encoded_path, tarinfo.name)

            try:
                tar.chown(tarinfo, epath)
                _fix_uid_gid(tarinfo, epath)
                if not os.path.islink(epath):
                    # make sure we keep the same permissions
                    tar.chmod(tarinfo, epath)
            except tarfile.ExtractError as err:
                raise IOError(err)

            deleter_counter -= 1
            if deleter_counter == 0:
                del tar.members[:]
                deleter_counter = 3

        del tar.members[:]

    finally:
        if tar is not None:
            del tar.members[:]
            tar.close()


def uncompress_tarball(filepath, extract_path = None, catch_empty = False):
    """
    Unpack tarball file (supported compression algorithm is given by tarfile
    module) respecting directory structure, mtime and permissions.

    @param filepath: path to tarball file
    @type filepath: string
    @keyword extract_path: path where to extract tarball
    @type extract_path: string
    @keyword catch_empty: do not raise exceptions when trying to unpack empty
        file
    @type catch_empty: bool
    @return: exit status
    @rtype: int
    """
    if extract_path is None:
        extract_path = os.path.dirname(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFound('FileNotFound: archive does not exist')

    def _setup_file_metadata(tarinfo, epath):
        try:
            tar.chown(tarinfo, epath)
            _fix_uid_gid(tarinfo, epath)

            # no longer touch utime using Tarinfo, behaviour seems
            # buggy and introduces an unwanted delay on some conditions.
            # match /bin/tar behaviour to not fuck touch mtime/atime at all
            # I wonder who are the idiots who didn't even test how
            # tar.utime behaves. Or perhaps it's just me that I've found
            # a new bug. Issue is, packages are prepared on PC A, and
            # mtime is checked on PC B.
            # tar.utime(tarinfo, epath)

            # mode = tarinfo.mode
            # xorg-server /usr/bin/X symlink of /usr/bin/Xorg
            # which is setuid. Symlinks don't need chmod. PERIOD!
            if not os.path.islink(epath):
                tar.chmod(tarinfo, epath)

        except tarfile.ExtractError:
            if tar.errorlevel > 1:
                raise

    is_python_3 = const_is_python3()
    tar = None
    extracted_something = False
    try:

        try:
            tar = tarfile.open(filepath, "r")
        except tarfile.ReadError:
            if catch_empty:
                return 0
            raise
        except EOFError:
            return -1

        encoded_path = extract_path
        if not is_python_3:
            encoded_path = encoded_path.encode('utf-8')
        entries = []

        deleter_counter = 3
        for tarinfo in tar:
            epath = os.path.join(encoded_path, tarinfo.name)

            if tarinfo.isdir():
                # Extract directory with a safe mode, so that
                # all files below can be extracted as well.
                try:
                    os.makedirs(epath, 0o777)
                except EnvironmentError:
                    pass

            if is_python_3:
                tar.extract(tarinfo, encoded_path,
                    set_attrs=not tarinfo.isdir())
            else:
                tar.extract(tarinfo, encoded_path)

            if tarinfo.isreg():
                # apply metadata to files instantly
                # not wasting RAM growing entries.
                _setup_file_metadata(tarinfo, epath)
            else:
                # delay file metadata setup for dirs
                # or syms that might be dirs or other
                # things. This because entries can grow
                # big and use a lot of RAM.
                entries.append((tarinfo, epath))

            extracted_something = True

            if not is_python_3:
                # this does work only with Python 2.x
                # doing that in Python 3.x will result in
                # partial extraction
                deleter_counter -= 1
                if deleter_counter == 0:
                    del tar.members[:]
                    deleter_counter = 3

        if not is_python_3:
            del tar.members[:]

        entries.sort(key = lambda x: x[0].name)
        entries.reverse()
        # set correct owner, mtime and filemode on files
        # we need to check both files and directories because
        #  we have to fix uid and gid from broken archives
        for tarinfo, epath in entries:
            _setup_file_metadata(tarinfo, epath)

    except EOFError:
        return -1
    finally:
        if tar is not None:
            tar.close()
            del tar.members[:]

    if extracted_something:
        return 0
    if catch_empty:
        return 0
    return -1

def bytes_into_human(xbytes):
    """
    Convert byte size into human readable format.

    @param xbytes: number of bytes
    @type xbytes: int
    @return: number of bytes in human readable format
    @rtype: string
    """
    size = str(round(float(xbytes) / 1000, 1))
    if xbytes < 1000:
        size = str(round(float(xbytes)))+"b"
    elif xbytes < 1000000:
        size += "kB"
    elif xbytes >= 1000000:
        size = str(round(float(size)/1000, 1))
        size += "MB"
    return size

def convert_unix_time_to_human_time(unixtime):
    """
    Convert UNIX time (int) into human readable time format.

    @param unixtime: UNIX time
    @type unixtime: int
    @return: human readable time format
    @rtype: string
    """
    from datetime import datetime
    humantime = str(datetime.fromtimestamp(unixtime))
    return humantime

def get_year():
    """
    Return current year string.

    @return: current year (20xx)
    @rtype: string
    """
    return time.strftime("%Y")

def convert_seconds_to_fancy_output(seconds):
    """
    Convert seconds (int) into a more fancy and human readable output.

    @param seconds: number of seconds
    @type seconds: int
    @return: human readable output
    @rtype: string
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

def write_parameter_to_file(config_file, name, data):
    """
    Write configuration file parameter to file. name is used as key and data
    as value. Any older setting will be replaced. Disabled parameters won't
    be enabled (lines starting with "#").

    @param config_file: path to configuration file
    @type config_file: string
    @param name: configuration parameter name
    @type name: string
    @param data: configuration parameter value
    @type data: string
    @return: True, if executed properly
    @rtype: bool
    """
    content = []
    enc = etpConst['conf_encoding']
    try:
        with codecs.open(config_file, "r", encoding=enc) as f:
            content = [x.strip() for x in f.readlines()]
    except (OSError, IOError) as err:
        if err.errno == errno.ENOENT:
            return False
        raise

    # write new
    config_file_tmp = config_file + ".tmp"
    try:
        with codecs.open(config_file_tmp, "w", encoding=enc) as f:
            param_found = False
            if data:
                proposed_line = const_convert_to_unicode(
                    "%s = %s" % (name, data,))
            else:
                proposed_line = const_convert_to_unicode("# %s =" % (name,))

                new_content = []
                # remove older setting
                for line in content:
                    key, value = extract_setting(line)
                    if key == name:
                        continue
                    new_content.append(line)
                content = new_content

            for line in content:
                key, value = extract_setting(line)
                if key == name:
                    param_found = True
                    line = proposed_line
                f.write(line)
                f.write("\n")
            if (not param_found) and data:
                f.write(proposed_line)
                f.write("\n")

    except (OSError, IOError) as err:
        if err.errno == errno.ENOENT:
            return False
        raise

    try:
        os.rename(config_file_tmp, config_file)
    except OSError as err:
        if err.errno != errno.EXDEV:
            raise
        shutil.move(config_file_tmp, config_file)
    return True

_optcre_old = re.compile(
    r'(?P<option>[^\|\s][^\|]*)'
    r'\s*(?P<vi>[\|])\s*'
    r'(?P<value>.*)$'
)
_optcre_new = re.compile(
    r'(?P<option>[^=\s][^=]*)'
    r'\s*(?P<vi>[=])\s*'
    r'(?P<value>.*)$'
)
def extract_setting(raw_line):
    """
    Extract configuration file setting key and value from string representing
    a configuration file line.

    @param raw_line: configuration file line
    @type raw_line: string
    @return: extracted setting key and value, if found, otherwise (None, None)
        if setting|key or setting=key is not found.
    @rtype: tuple
    """
    if not raw_line.strip():
        return None, None
    if raw_line.strip() == "#":
        return None, None

    m_obj = _optcre_new.match(raw_line)
    if m_obj is not None:
        option, vi, value = m_obj.group('option', 'vi', 'value')
        if value:
            return option.strip(), value

    # old style setting
    m_obj = _optcre_old.match(raw_line)
    if m_obj is not None:
        option, vi, value = m_obj.group('option', 'vi', 'value')
        if value:
            return option.strip(), value

    return None, None

def setting_to_bool(setting):
    """
    Convert entropy setting string which should represent a bool setting into
    a bool type, if possible, otherwise return None.

    @param setting: raw setting value that should represent a bool
    @type setting: string
    @return: bool value, or None
    @rtype: bool or None
    """
    if setting in ("disable", "disabled", "false", "0", "no",):
        return False
    elif setting in ("enable", "enabled", "true", "1", "yes",):
        return True
    return None

def setting_to_int(setting, lower_bound, upper_bound):
    """
    Convert entropy setting string which should represent a int setting into
    a int type, if possible, otherwise return None. Also check against
    lower and upper bounds, if different than None.

    @param setting: raw setting value that should represent a bool
    @type setting: string
    @return: bool value, or None
    @rtype: bool or None
    """
    try:
        data = int(setting)
        if lower_bound is not None:
            if data < lower_bound:
                raise ValueError()
        if upper_bound is not None:
            if data > upper_bound:
                raise ValueError()
        return data
    except ValueError:
        return None

def expand_plain_package_mirror(mirror, product, repository_id):
    """
    Expand plain mirror URL adding product and repository identifier data to it.

    @param mirror: mirror URL
    @type mirror: string
    @param product: Entropy repository product
    @type product: string
    @param repository_id: repository identifier
    @type repository_id: string
    @return: expanded URL or None if invalid
    @rtype: string or None
    """
    if not is_valid_uri(mirror):
        return None
    sep = const_convert_to_unicode("/")
    return mirror + sep + product + sep + repository_id

def expand_plain_database_mirror(mirror, product, repository_id, branch):
    """
    Expand plain database mirror URL adding product, repository identifier
    and branch data to it.

    @param mirror: mirror URL
    @type mirror: string
    @param product: Entropy repository product
    @type product: string
    @param repository_id: repository identifier
    @type repository_id: string
    @return: expanded URL or None if invalid
    @rtype: string or None
    """
    if not is_valid_uri(mirror):
        return None
    sep = const_convert_to_unicode("/")
    return mirror + sep + product + sep + repository_id + sep + \
        etpConst['databaserelativepath_basedir'] + sep + \
        etpConst['currentarch'] + sep + branch

_repo_re = re.compile("^(([a-zA-Z]|[a-zA-Z][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z]|[A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9])$", re.IGNORECASE)
def validate_repository_id(repository_id):
    """
    Validate Entropy repository identifier string.

    @param repository_id: entropy repository identifier
    @type repository_id: string
    @return: True if repository_id is a valid string, False otherwise
    @rtype: bool
    """
    if _repo_re.match(repository_id):
        return True
    return False

_package_re = re.compile('[a-zA-Z_0-9/\-\.\+#~@]+$')
def validate_package_name(package_name):
    """
    Validate Entropy package name string.

    @param package_name; the actual package name (either key or version)
    @type package_name: string
    @return: True, if package_name is a valid package name
    @rtype: bool
    """
    if _package_re.match(package_name):
        return True
    return False

_branch_re = re.compile('[a-zA-Z_0-9\-\.+]+$')
def validate_branch_name(branch):
    """
    Validate Entropy branch name string.

    @param branch; the actual branch name
    @type branch: string
    @return: True, if branch is valid
    @rtype: bool
    """
    if _branch_re.match(branch):
        return True
    return False

def is_entropy_package_file(entropy_package_path):
    """
    Determine whether given package path is a valid Entropy package file.

    @param entropy_package_path: path to Entropy package file
    @type entropy_package_path: string
    @return: True, if valid
    @rtype: bool
    """
    if not os.path.exists(entropy_package_path):
        return False
    try:
        with open(entropy_package_path, "rb") as obj:
            entry_point = _locate_edb(obj)
            if entry_point is None:
                return False
            return True
    except (IOError, OSError,):
        return False

def is_valid_string(string):
    """
    Return whether given string only contains ASCII printable chars (from
    0x20 to 0xFF).

    @param string: string to test
    @type string: string
    @return: True, if valid
    @rtype: bool
    """
    invalid = [ord(x) for x in string if ord(x) not in list(range(32, 127))]
    if invalid:
        return False
    return True

valid_path_regexp = re.compile("^([A-Za-z0-9/\.:\-_]+)$")
def is_valid_path_string(path):
    """
    Return whether given path is a valid path string (whitelisting valid
    characters). Regexp is ^([A-Za-z0-9/\.:-]+)$ and only works with ASCII
    paths.

    @param path: path to test
    @type path: string
    @return: True, if valid
    @rtype: bool
    """
    if valid_path_regexp.match(path):
        return True
    return False

def is_valid_path(path):
    """
    Return whether given path is valid (it uses os.stat()). Broken symlinks
    will return False.

    @param path: path to test
    @type path: string
    @return: True, if valid
    @rtype: bool
    """
    try:
        os.stat(path)
    except OSError:
        return False
    return True

def is_valid_md5(string):
    """
    Return whether given string is a valid md5 hex digest.

    @param string: string to test
    @type string: string
    @return: True, if valid
    @rtype: bool
    """
    if re.findall(r'(?i)(?<![a-z0-9])[a-f0-9]{32}(?![a-z0-9])', string):
        return True
    return False

def elf_class_strtoint(elf_class_str):
    """
    Convert an ELF class metadataum string to its int value.

    @param elf_class_str: the ELF class string
    @type elf_class_str: string
    @return: ELF class int value
    @rtype: int
    """
    if elf_class_str in ("X86_64", "ELFCLASS64"):
        return 2
    elif elf_class_str in ("ARM", "386", "ELFCLASS32"):
        return 1
    else:
        raise ValueError('unsupported %s' % (elf_class_str,))

def read_elf_class(elf_file):
    """
    Read ELF class metadatum from ELF file.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: ELF class metadatum value
    @rtype: int
    """
    with open(elf_file, "rb") as f:
        f.seek(4)
        elf_class = f.read(1)
    elf_class = struct.unpack('B', elf_class)[0]
    return elf_class

def is_elf_file(elf_file):
    """
    Determine whether given file path points to an ELF file object.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: True, if file at path is ELF file
    @rtype: bool
    """
    with open(elf_file, "rb") as f:
        data = f.read(4)
    try:
        data = struct.unpack('BBBB', data)
    except struct.error:
        return False
    if data == (127, 69, 76, 70):
        return True
    return False

def parse_rpath(rpath):
    """
    Parse RPATH metadata stored in repository and return an ordered
    list of paths.

    @param rpath: raw RPATH metadata string
    @type rpath: string
    @return: a list of paths
    @rtype: list
    """
    return rpath.split(":")

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
    def do_resolve(mypaths, elf_class):
        found_path = None
        for ld_dir in mypaths:
            mypath = os.path.join(ld_dir, library)
            if os.path.isdir(mypath):
                continue
            if not const_file_readable(mypath):
                continue
            if not is_elf_file(mypath):
                continue
            elif read_elf_class(mypath) != elf_class:
                continue
            found_path = mypath
            break
        return found_path

    elf_class = read_elf_class(requiring_executable)
    ld_paths = collect_linker_paths()
    found_path = do_resolve(ld_paths, elf_class)

    if not found_path:
        ld_paths = read_elf_linker_paths(requiring_executable)
        found_path = do_resolve(ld_paths, elf_class)

    return found_path

def read_elf_dynamic_libraries(elf_file):
    """
    Extract NEEDED metadatum from ELF file at path.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: list (set) of strings in NEEDED metadatum
    @rtype: set
    """
    proc = None
    args = ("/usr/bin/scanelf", "-qF", "%n", elf_file)

    out = None
    try:
        proc = subprocess.Popen(args, stdout = subprocess.PIPE)
        exit_st = proc.wait()
        if exit_st != 0:
            raise FileNotFound("scanelf failure")
        out = proc.stdout.read()

    except (OSError, IOError) as err:
        if err.errno != errno.ENOENT:
            raise
        raise FileNotFound("/usr/bin/scanelf not found")

    finally:
        if proc is not None:
            try:
                proc.stdout.close()
            except (OSError, IOError):
                pass

    outcome = set()
    if out is not None:
        if const_is_python3():
            out = const_convert_to_unicode(out)
        for line in out.split("\n"):
            if line:
                libs = line.strip().split(" ", -1)[0].split(",")
                outcome.update(libs)
    return outcome

def read_elf_metadata(elf_file):
    """
    Extract soname, elf class, runpath and NEEDED metadata from ELF file.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: dict with "soname", "class", "runpath" and "needed" keys. None if
        no metadata is found.
    @rtype: dict or None
    """
    proc = None
    args = ("/usr/bin/scanelf", "-qF", "%M;%S;%r;%n", elf_file)

    out = None
    try:
        proc = subprocess.Popen(args, stdout = subprocess.PIPE)
        exit_st = proc.wait()
        if exit_st != 0:
            raise FileNotFound("scanelf failure")
        out = proc.stdout.read()

    except (OSError, IOError) as err:
        if err.errno != errno.ENOENT:
            raise
        raise FileNotFound("/usr/bin/scanelf not found")

    finally:
        if proc is not None:
            try:
                proc.stdout.close()
            except (OSError, IOError):
                pass

    if out is not None:
        if const_is_python3():
            out = const_convert_to_unicode(out)
        if not out:
            # no metadata.
            return None

        for line in out.split("\n"):
            if line:
                data = line.strip().split(" ", -1)[0]
                elfclass_str, soname, runpath, libs = data.split(";")
                libs = set(libs.split(","))
                return {
                    'soname': soname,
                    'class': elf_class_strtoint(elfclass_str),
                    'runpath': runpath,
                    'needed': libs,
                }

    raise FileNotFound("scanelf failure")

def read_elf_real_dynamic_libraries(elf_file):
    """
    This function is similar to read_elf_dynamic_libraries but uses ldd to
    retrieve a list of "real" .so library dependencies used by the ELF file.
    This is useful to ensure that there are no .so libraries missing in the
    dependencies, because ldd expands and resolves the .so dependency graph.
    This is anyway dangerous because the output returned by ldd is somehow
    environment-dependent, so make sure this function is only used for
    informative purposes, and not for adding real dependencies to a package.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: list (set) of strings in NEEDED metadatum
    @rtype: set
    @raise FileNotFound: if ldd is not found
    """
    # use the real path, so that it can be dropped from the resulting set
    elf_file = os.path.realpath(elf_file)

    proc = None
    output = None
    args = ("/usr/bin/lddtree", "-l", elf_file)

    try:
        proc = subprocess.Popen(args, stdout = subprocess.PIPE)

        output = const_convert_to_unicode("")

        while True:

            out = proc.stdout.read()
            if not out:
                break

            if const_is_python3():
                out = const_convert_to_unicode(out)
            output += out

        exit_st = proc.wait()
        if exit_st != 0:
            raise FileNotFound("lddtree returned error %d on %s" % (
                exit_st, elf_file))

    except (OSError, IOError) as err:
        if err.errno != errno.ENOENT:
            raise
        raise FileNotFound("/usr/bin/lddtree not found")

    finally:
        if proc is not None:
            proc.stdout.close()

    outcome = set()
    if output is not None:
        for line in output.split("\n"):
            if line == elf_file:
                continue
            if line:
                outcome.add(os.path.basename(line))

    return outcome

def read_elf_broken_symbols(elf_file):
    """
    Extract broken symbols from ELF file.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: list of broken symbols in ELF file.
    @rtype: set
    """
    proc = None
    args = ("/usr/bin/ldd", "-r", elf_file)
    output = None
    stdout = None

    try:
        stdout = open(os.devnull, "wb")

        proc = subprocess.Popen(
            args, stdout = stdout,
            stderr = subprocess.PIPE)

        output = const_convert_to_unicode("")

        while True:

            err = proc.stderr.read()
            if not err:
                break

            if const_is_python3():
                err = const_convert_to_unicode(err)
            output += err

        exit_st = proc.wait()
        if exit_st != 0:
            raise FileNotFound("ldd error")

    except (OSError, IOError) as err:
        if err.errno != errno.ENOENT:
            raise
        raise FileNotFound("/usr/bin/ldd not found")

    finally:
        if proc is not None:
            proc.stderr.close()
        if stdout is not None:
            stdout.close()

    outcome = set()
    if output is not None:
        for line in output.split("\n"):
            if line.startswith("undefined symbol: "):
                symbol = line.split("\t")[0].split()[-1]
                outcome.add(symbol)

    return outcome

def read_elf_linker_paths(elf_file):
    """
    Extract built-in linker paths (RUNPATH and RPATH) from ELF file.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: list of extracted built-in linker paths.
    @rtype: list
    """
    proc = None
    args = ("/usr/bin/scanelf", "-qF", "%r", elf_file)
    out = None

    try:
        proc = subprocess.Popen(args, stdout = subprocess.PIPE)
        exit_st = proc.wait()
        if exit_st != 0:
            raise FileNotFound("scanelf error")

        out = proc.stdout.read()

    except (OSError, IOError) as err:
        if err.errno != errno.ENOENT:
            raise
        raise FileNotFound("/usr/bin/scanelf not found")

    finally:
        if proc is not None:
            proc.stdout.close()

    outcome = []
    if out is not None:

        elf_dir = os.path.dirname(elf_file)
        if const_is_python3():
            out = const_convert_to_unicode(out)
        for line in out.split("\n"):
            if line:
                paths = line.strip().split(" ", -1)[0].split(",")
                for path in paths:
                    path = path.replace("$ORIGIN", elf_dir)
                    path = path.replace("${ORIGIN}", elf_dir)
                    outcome.append(path)

    return outcome

def xml_from_dict_extended(dictionary):
    """
    Serialize a simple dict object into an XML string.

    @param dictionary: dict object
    @type dictionary: dict
    @return: XML string representing the dict object
    @rtype: string
    """
    from xml.dom import minidom
    doc = minidom.Document()
    ugc = doc.createElement("entropy")
    for key, value in list(dictionary.items()):
        item = doc.createElement('item')
        item.setAttribute('value', key)
        if const_isunicode(value):
            mytype = "unicode"
        elif isinstance(value, str):
            mytype = "str"
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
        elif value is None:
            mytype = "None"
            value = "None"
        else:
            raise TypeError()
        item.setAttribute('type', mytype)
        item_value = doc.createTextNode("%s" % (value,))
        item.appendChild(item_value)
        ugc.appendChild(item)
    doc.appendChild(ugc)
    return doc.toxml()

def dict_from_xml_extended(xml_string):
    """
    Deserialize an XML string representing a dict object back into a dict
    object.
    WARNING: eval() is used for non-string, non-bool types.

    @param xml_string: string to deserialize
    @type xml_string: string
    @return: reconstructed dict object
    @rtype: dict
    """
    if const_isunicode(xml_string):
        xml_string = const_convert_to_rawstring(xml_string, 'utf-8')
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

    def convert_raw(obj):
        if const_israwstring(obj):
            return obj
        return const_convert_to_rawstring(obj)

    my_map = {
        "str": convert_raw,
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
        if not key:
            continue

        mytype = item.getAttribute('type')
        mytype_m = my_map.get(mytype, 0)
        if mytype_m == 0:
            raise TypeError("%s is unsupported" % (mytype,))

        try:
            data = item.firstChild.data
        except AttributeError:
            data = ''

        if mytype in ("list", "set", "frozenset", "dict", "tuple",):

            valid_strs = ("(", "[", "set(", "frozenset(", "{")
            valid = False
            for xts in valid_strs:
                if data.startswith(xts):
                    valid = True
                    break
            if not valid:
                data = ''
            if not data:
                mydict[key] = None
            else:
                mydict[key] = eval(data)

        elif mytype == "None":
            mydict[key] = None
        else:
            mydict[key] = mytype_m(data)

    return mydict

def xml_from_dict(dictionary):
    """
    Serialize a dict object into a "simple" XML string. This method is faster
    and safer than xml_from_dict_extended but it doesn't support dict values
    and keys different from strings.

    @param dictionary: dictionary object
    @type dictionary: dict
    @return: serialized XML string
    @rtype: string
    """
    from xml.dom import minidom
    doc = minidom.Document()
    ugc = doc.createElement("entropy")
    for key, value in dictionary.items():
        item = doc.createElement('item')
        item.setAttribute('value', key)
        item_value = doc.createTextNode(value)
        item.appendChild(item_value)
        ugc.appendChild(item)
    doc.appendChild(ugc)
    return doc.toxml()

def dict_from_xml(xml_string):
    """
    Deserialize an XML string representing a dict (created by xml_from_dict)
    back into a dict object. This method is faster and safer than
    dict_from_xml_extended but it doesn't support dict values and keys different
    from strings.

    @param xml_string: XML string to deserialize
    @type xml_string: string
    @return: deserialized dict object
    @rtype: dict
    """
    if const_isunicode(xml_string):
        xml_string = const_convert_to_rawstring(xml_string, 'utf-8')
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

def collect_linker_paths():
    """
    Collect dynamic linker paths set into /etc/ld.so.conf. This function is
    ROOT safe.

    @return: list of dynamic linker paths set
    @rtype: tuple
    """
    paths = collections.deque()

    ld_confs = ["/etc/ld.so.conf"]
    ld_so_conf_d_base = "etc/ld.so.conf.d"
    root = etpConst['systemroot'] + "/"

    ld_so_conf_d = os.path.join(root, ld_so_conf_d_base)
    try:
        ld_confs += ["/" + os.path.join(ld_so_conf_d_base, x)
                     for x in os.listdir(ld_so_conf_d)]
    except (IOError, OSError) as err:
        if err.errno not in (errno.ENOENT, errno.EACCES):
            raise

    enc = etpConst['conf_encoding']

    for ld_conf in ld_confs:
        ld_conf = os.path.join(root, ld_conf.lstrip("/"))

        try:
            with codecs.open(ld_conf, "r", encoding=enc) as ld_f:
                for x in ld_f.readlines():
                    if x.startswith("/"):
                        paths.append(os.path.normpath(x.strip()))

        except (IOError, OSError) as err:
            if err.errno not in (errno.ENOENT, errno.EACCES):
                raise

    # Add built-in paths.
    paths.append("/lib")
    paths.append("/usr/lib")

    return tuple(paths)

def collect_paths():
    """
    Return env var PATH value split using ":" as separator.

    @return: list of PATHs
    @rtype: list
    """
    return os.getenv("PATH", "").split(":")

def create_package_dirpath(branch, nonfree = False, restricted = False):
    """
    Create Entropy package relative directory path used for building
    EntropyRepository "download" metadatum and for handling package file life
    by Entropy Server.

    @param branch: Entropy branch id
    @type branch: string
    @keyword nonfree: if package belongs to free or nonfree dir
    @type nonfree: bool
    @return: complete relative path
    @rtype: string
    """
    if nonfree:
        down_rel_basedir = etpConst['packagesrelativepath_basedir_nonfree']
    elif restricted:
        down_rel_basedir = etpConst['packagesrelativepath_basedir_restricted']
    else:
        down_rel_basedir = etpConst['packagesrelativepath_basedir']
    down_rel_basename = etpConst['packagesrelativepath_basename']
    # don't use os.path.join, because it's OS dependent, this is valid as URL
    # too...
    dirpath = down_rel_basedir + "/" + down_rel_basename + "/" + branch
    return dirpath

def recursive_directory_relative_listing(empty_list, base_directory,
    _nested = False):
    """
    Takes an array(list) and appends all files from dir down
    the directory tree. Returns nothing. list is modified.
    """
    if not _nested:
        base_directory = os.path.normpath(base_directory)
    for x in os.listdir(base_directory):
        x_path = os.path.join(base_directory, x)
        if os.path.isdir(x_path):
            recursive_directory_relative_listing(empty_list, x_path,
                _nested = True)
        elif x_path not in empty_list:
            empty_list.append(x_path)

    if not _nested:
        for idx in range(len(empty_list)):
            empty_list[idx] = empty_list[idx][len(base_directory)+1:]

def flatten(mylist):
    """
    Recursively traverse nested lists and return a single list containing
    all non-list elements that are found.

    @param mylist: A list containing nested lists and non-list elements.
    @type mylist: List
    @rtype: List
    @return: A single list containing only non-list elements.
    """
    newlist = []
    for x in mylist:
        if isinstance(x, (list, tuple, set, frozenset)):
            newlist.extend(flatten(x))
        else:
            newlist.append(x)
    return newlist

def codecs_fdopen(fd, mode, encoding, errors='strict'):
    """
    Copycats codecs.open() but accepts fd (file descriptors) as input
    file handle.
    """
    if encoding is not None:
        if 'U' in mode:
            # No automatic conversion of '\n' is done on reading and writing
            mode = mode.strip().replace('U', '')
            if mode[:1] not in set('rwa'):
                mode = 'r' + mode
        if 'b' not in mode:
            # Force opening of the file in binary mode
            mode = mode + 'b'
    file = os.fdopen(fd, mode, 4096)
    if encoding is None:
        return file
    info = codecs.lookup(encoding)
    srw = codecs.StreamReaderWriter(
        file, info.streamreader, info.streamwriter, errors)
    # Add attributes to simplify introspection
    srw.encoding = encoding
    return srw

def total_memory():
    """
    Return the amount of total system memory in megabytes.

    @return: the total system memory available
    @rtype: int
    """
    try:
        with open("/proc/meminfo", "r") as mem_f:
            line = mem_f.readline()
            while line:
                if line.startswith("MemTotal"):
                    args = line.split()
                    try:
                        return int(args[1]) / 1000
                    except ValueError:
                        pass
                line = mem_f.readline()

    except (OSError, IOError) as err:
        if err.errno == errno.ENOENT:
            return 0
        raise

    return 0
