# -*- coding: utf-8 -*-
# Entropy miscellaneous tools module
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
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
import tempfile
import subprocess
import grp
import pwd
import hashlib
import random
import traceback
from entropy.output import print_generic
from entropy.const import etpConst, const_kill_threads, const_islive, \
    const_isunicode, const_convert_to_unicode, const_convert_to_rawstring, \
    const_cmp, const_israwstring, const_cmp
from entropy.exceptions import FileNotFound, InvalidAtom, DirectoryNotFound

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
    if sys.hexversion >= 0x3000000:
        from io import StringIO
    else:
        from cStringIO import StringIO
    buf = StringIO()
    if tb_obj is not None:
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
        except OSError as e:
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
    readfile = open(filepath, "rb")
    block = readfile.read(16384)
    while block:
        m.update(block)
        block = readfile.read(16384)
    readfile.close()
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
    readfile = open(filepath, "rb")
    block = readfile.read(16384)
    while block:
        m.update(block)
        block = readfile.read(16384)
    readfile.close()
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
    readfile = open(filepath, "rb")
    block = readfile.read(16384)
    while block:
        m.update(block)
        block = readfile.read(16384)
    readfile.close()
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
    readfile = open(filepath, "rb")
    block = readfile.read(16384)
    while block:
        m.update(block)
        block = readfile.read(16384)
    readfile.close()
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
            readfile = open(myfile, "rb")
            block = readfile.read(16384)
            while block:
                m.update(block)
                block = readfile.read(16384)
            readfile.close()
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
            readfile = open(myfile, "rb")
            block = readfile.read(16384)
            while block:
                m.update(block)
                block = readfile.read(16384)
            readfile.close()
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
    f_out = open(destination_path, "wb")
    f_in = opener(file_path, "rb")
    data = f_in.read(16384)
    while data:
        f_out.write(data)
        data = f_in.read(16384)
    f_out.flush()
    f_out.close()
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
    f_in = open(file_path, "rb")
    if compress_level is not None:
        f_out = opener(destination_path, "wb", compresslevel = compress_level)
    else:
        f_out = opener(destination_path, "wb")
    data = f_in.read(16384)
    while data:
        f_out.write(data)
        data = f_in.read(16384)
    if hasattr(f_out, 'flush'):
        f_out.flush()
    f_out.close()
    f_in.close()

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

        if sys.hexversion < 0x3000000:
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

def unpack_gzip(gzipfilepath):
    """
    Unpack .gz file.

    @param gzipfilepath: path to .gz file
    @type gzipfilepath: string
    @return: path to uncompressed file
    @rtype: string
    """
    import gzip
    filepath = gzipfilepath[:-3] # remove .gz
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(filepath))

    item = os.fdopen(fd, "wb")
    filegz = gzip.GzipFile(gzipfilepath, "rb")
    chunk = filegz.read(8192)
    while chunk:
        item.write(chunk)
        chunk = filegz.read(8192)
    filegz.close()
    item.flush()
    item.close()
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
    import bz2
    filepath = bzip2filepath[:-4] # remove .bz2
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(filepath))
    item = os.fdopen(fd, "wb")
    filebz2 = bz2.BZ2File(bzip2filepath, "rb")
    chunk = filebz2.read(16384)
    while chunk:
        item.write(chunk)
        chunk = filebz2.read(16384)
    filebz2.close()
    item.flush()
    item.close()
    os.rename(tmp_path, filepath)
    return filepath

def aggregate_entropy_metadata(entropy_package_file, entropy_metadata_file):
    """
    Add Entropy metadata dump file to given Entropy package file.

    @param entropy_package_file: path to Entropy package file
    @type entropy_package_file: string
    @param entropy_metadata_file: path to Entropy metadata file
    @type entropy_metadata_file: string
    """
    f = open(entropy_package_file, "ab")
    f.write(const_convert_to_rawstring(etpConst['databasestarttag']))
    g = open(entropy_metadata_file, "rb")
    chunk = g.read(16384)
    while chunk:
        f.write(chunk)
        chunk = g.read(16384)
    g.close()
    f.flush()
    f.close()

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
    old = open(entropy_package_file, "rb")
    start_position = _locate_edb(old)
    if not start_position:
        old.close()
        return False

    db = open(entropy_metadata_file, "wb")
    data = old.read(16384)
    while data:
        db.write(data)
        data = old.read(16384)
    db.flush()
    db.close()

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
    give_up_threshold = 1024000 * 30 # 30Mb
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

            new.flush()

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
    f = open(hashfile, "w")
    name = os.path.basename(filepath)
    if sys.hexversion >= 0x3000000:
        f.write(md5hash+"  "+name+"\n")
    else:
        f.write(md5hash+"  "+name.encode('utf-8')+"\n")
    f.flush()
    f.close()
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
    f = open(hashfile, "w")
    fname = os.path.basename(filepath)
    if sys.hexversion >= 0x3000000:
        f.write(sha512hash+"  "+fname+"\n")
    else:
        f.write(sha512hash+"  "+fname.encode('utf-8')+"\n")
    f.flush()
    f.close()
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
    f = open(hashfile, "w")
    fname = os.path.basename(filepath)
    if sys.hexversion >= 0x3000000:
        f.write(sha256hash+"  "+fname+"\n")
    else:
        f.write(sha256hash+"  "+fname.encode('utf-8')+"\n")
    f.flush()
    f.close()
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
    f = open(hashfile, "w")
    fname = os.path.basename(filepath)
    if sys.hexversion >= 0x3000000:
        f.write(sha1hash+"  "+fname+"\n")
    else:
        f.write(sha1hash+"  "+fname.encode('utf-8')+"\n")
    f.flush()
    f.close()
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
    filter_comments = True):
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
    if os.access(filepath, os.R_OK) and os.path.isfile(filepath):
        gen_f = open(filepath, "r")
        content = gen_f.readlines()
        gen_f.close()
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

# Imported from Gentoo portage_dep.py
# Copyright 1999-2010 Gentoo Foundation

# 2.1.1 A category name may contain any of the characters [A-Za-z0-9+_.-].
# It must not begin with a hyphen or a dot.
_cat = r'[\w+][\w+.-]*'

# 2.1.2 A package name may contain any of the characters [A-Za-z0-9+_-].
# It must not begin with a hyphen,
# and must not end in a hyphen followed by one or more digits.
_pkg = r'[\w+][\w+-]*?'

_v = r'(cvs\.)?(\d+)((\.\d+)*)([a-z]?)((_(pre|p|beta|alpha|rc)\d*)*)'
_rev = r'\d+'
_vr = _v + '(-r(' + _rev + '))?'

_cp = '(' + _cat + '/' + _pkg + '(-' + _vr + ')?)'
_cpv = '(' + _cp + '-' + _vr + ')'
_pv = '(?P<pn>' + _pkg + '(?P<pn_inval>-' + _vr + ')?)' + '-(?P<ver>' + _v + ')(-r(?P<rev>' + _rev + '))?'

ver_regexp = re.compile("^" + _vr + "$")
suffix_regexp = re.compile("^(alpha|beta|rc|pre|p)(\\d*)$")
suffix_value = {"pre": -2, "p": 0, "alpha": -4, "beta": -3, "rc": -1}
endversion_keys = ["pre", "p", "alpha", "beta", "rc"]

valid_category = re.compile("^\w[\w-]*")
invalid_atom_chars_regexp = re.compile("[()|@]")

def _ververify(myver):
    if myver.endswith("*"):
        m = ver_regexp.match(myver[:-1])
    else:
        m = ver_regexp.match(myver)
    if m:
        return True
    return False

def isjustname(mypkg):
    """
    Checks to see if the depstring is only the package name (no version parts)

    Example usage:
        >>> isjustname('media-libs/test-3.0')
        False
        >>> isjustname('test')
        True
        >>> isjustname('media-libs/test')
        True

    @param mypkg: The package atom to check
    @param mypkg: String
    @rtype: int
    @return: if the package string is not just the package name
    """
    for chunk in mypkg.split('-')[-2:]:
        if _ververify(chunk):
            return False
    return True

def _isspecific(mypkg):
    """
    Checks to see if a package is in category/package-version or package-version format,
    possibly returning a cached result.

    Example usage:
        >>> _isspecific('media-libs/test')
        False
        >>> _isspecific('media-libs/test-3.0')
        True

    @param mypkg: The package depstring to check against
    @type mypkg: String
    @rtype: Integer
    @return: One of the following:
        1) 0 if the package string is not specific
        2) 1 if it is
    """
    mysplit = mypkg.split("/")
    if not isjustname(mysplit[-1]):
        return True
    return False


def catpkgsplit(mydata):
    """
    Takes a Category/Package-Version-Rev and returns a list of each.

    @param mydata: Data to split
    @type mydata: string
    @rype: tuple
    @return:
        1.  If each exists, it returns (cat, pkgname, version, rev)
        2.  If cat is not specificed in mydata, cat will be "null"
        3.  if rev does not exist it will be '-r0'
    """

    # Categories may contain a-zA-z0-9+_- but cannot start with -
    mysplit = mydata.split("/")
    p_split = None
    if len(mysplit) == 1:
        retval = ("null",)
        p_split = _pkgsplit(mydata)
    elif len(mysplit) == 2:
        retval = (mysplit[0],)
        p_split = _pkgsplit(mysplit[1])
    if not p_split:
        return None
    retval += p_split
    return retval

_pv_re = re.compile('^' + _pv + '$', re.VERBOSE)
def _pkgsplit(mypkg):
    """
    @param mypkg: pv
    @return:
    1. None if input is invalid.
    2. (pn, ver, rev) if input is pv
    """
    m = _pv_re.match(mypkg)
    if m is None:
        return None

    if m.group('pn_inval') is not None:
        # package name appears to have a version-like suffix
        return None

    rev = m.group('rev')
    if rev is None:
        rev = '0'
    rev = 'r' + rev

    return  (m.group('pn'), m.group('ver'), rev)

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
    if mydep and _isspecific(mydep):
        mysplit = catpkgsplit(mydep)
        if not mysplit:
            return mydep
        return mysplit[0] + "/" + mysplit[1]

    return mydep

def dep_getcat(mydep):
    """
    Extract package category from dependency.
    """
    return dep_getkey(mydep).split("/")[0]

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
    new_depend = ""
    skip = 0
    for char in depend:
        if char == "[":
            skip += 1
        elif char == "]":
            skip -= 1
            continue
        if skip == 0:
            new_depend += char

    return new_depend

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
    colon = mydep.rfind(etpConst['entropytagprefix'])
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

def dep_split_or_deps(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    dep = mydep.rstrip(etpConst['entropyordepquestion'])
    return dep.split(etpConst['entropyordepsep'])

dep_revmatch = re.compile('^r[0-9]')
def dep_get_spm_revision(mydep):
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

def dep_gettag(mydep):

    """
    Retrieve the slot on a depend.

    Example usage:
        >>> dep_gettag('app-misc/test#2.6.23-sabayon-r1')
        '2.6.23-sabayon-r1'

    """
    dep = mydep[:]
    dep = remove_entropy_revision(dep)
    colon = dep.rfind(etpConst['entropytagprefix'])
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
    return atom.lstrip("><=~")

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
    if invalid:
        return invalid_rc

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

tag_regexp = re.compile("^([A-Za-z0-9+_.-]+)?$")
def is_valid_package_tag(dep):
    """
    docstring_title

    @param dep: 
    @type dep: 
    @return: 
    @rtype: 
    """
    match = tag_regexp.match(dep)
    if not match:
        return False
    if not match.groups():
        return False
    return True

def entropy_compare_package_tags(tag_a, tag_b):
    """
    Compare two Entropy package tags using builtin cmp().

    @param tag_a: Entropy package tag
    @type tag_a: string
    @param tag_b: Entropy package tag
    @type tag_b: string
    return: negative number if tag_a < tag_b, positive number if tag_a > tag_b.
        zero if tag_a == tag_b.
    rtype: int
    """
    return const_cmp(tag_a, tag_b)

def sort_entropy_package_tags(tags):
    """
    Return a sorted list of Entropy package tags.

    @param tags: list of Entropy package tags
    @type tags: list
    @return: sorted list of Entropy package tags
    @rtype: list
    """
    return sorted(tags)

def entropy_compare_versions(listA, listB):
    """
    @description: compare two lists composed by
        [version,tag,revision] and [version,tag,revision]
        if listA > listB --> positive number
        if listA == listB --> 0
        if listA < listB --> negative number
    @input package: listA[version,tag,rev] and listB[version,tag,rev]
    @output: integer number
    """
    a_ver, a_tag, a_rev = listA
    b_ver, b_tag, b_rev = listB

    # if both are tagged, check tag first
    rc = 0
    if a_tag and b_tag:
        rc = const_cmp(a_tag, b_tag)
    if rc == 0:
        rc = compare_versions(a_ver, b_ver)

    if rc == 0:
        # check tag
        tag_cmp = entropy_compare_package_tags(a_tag, b_tag)
        if tag_cmp < 0:
            return -1
        elif tag_cmp > 0:
            return 1
        else:
            # check rev
            if a_rev > b_rev:
                return 1
            elif a_rev < b_rev:
                return -1
            return 0

    return rc

def get_newer_version(versions):
    """
    Return a sorted list of versions

    @param versions: input version list
    @type versions: list
    @return: sorted version list
    @rtype: list
    """
    return _generic_sorter(versions, compare_versions)

def _generic_sorter(inputlist, cmp_func):

    inputs = inputlist[:]
    if len(inputs) < 2:
        return inputs
    max_idx = len(inputs)

    while True:
        changed = False
        for idx in range(max_idx):
            second_idx = idx+1
            if second_idx == max_idx:
                continue
            str_a = inputs[idx]
            str_b = inputs[second_idx]
            if cmp_func(str_a, str_b) < 0:
                inputs[idx] = str_b
                inputs[second_idx] = str_a
                changed = True
        if not changed:
            break

    return inputs

def get_entropy_newer_version(versions):
    """
    Sort a list of entropy package versions.

    @param versions: list of package versions
    @type versions: list
    @return: sorted list
    @rtype: list
    """
    return _generic_sorter(versions, entropy_compare_versions)

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
    f = open(filename, "r")
    r = istext(f.read(blocksize))
    f.close()
    return r

def istext(mystring):
    """
    Determine whether given string is text.

    @param mystring: string to parse
    @type mystring: string
    @return: True, if string is text
    @rtype: bool
    """

    if sys.hexversion >= 0x3000000:
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
    if sys.hexversion >= 0x3000000:
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
    if sys.hexversion >= 0x3000000:
        import urllib.parse as urlmod
    else:
        import urlparse as urlmod
    return urlmod.urlsplit(url)

def compress_tar_bz2(store_path, path_to_compress):
    """
    Compress path_to_compress path into store_path path using tar and bzip2.

    @param store_path: file path where to write .tar.bz2
    @type store_path: string
    @param path_to_compress: path to compress to .tar.bz2 file
    @type path_to_compress: string
    @return: execution return code
    @rtype: int
    """
    pid = os.fork()
    if pid == 0:
        os.chdir(path_to_compress)
        proc = subprocess.Popen(("tar", "cjf", store_path),
            stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        rc = proc.wait()
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stdout is not None:
            proc.stderr.close()
        os._exit(rc)
    else:
        return os.waitpid(pid, 0)[1] # return rc

def spawn_function(f, *args, **kwds):
    """
    Spawn given function with given arguments in a separate process and
    return back its value (using pipes).

    @param f: function to call
    @type f: callable
    @param *args: function arguments
    @type *args: tuple
    @param **kwds: function keyword arguments
    @type **kwds: dict
    @return: function result
    @rtype: Python object
    """

    uid = kwds.get('spf_uid')
    if uid is not None:
        kwds.pop('spf_uid')

    gid = kwds.get('spf_gid')
    if gid is not None:
        kwds.pop('spf_gid')

    write_pid_func = kwds.get('write_pid_func')
    if write_pid_func is not None:
        kwds.pop('write_pid_func')

    try:
        import cPickle as pickle
    except ImportError:
        import pickle
    pread, pwrite = os.pipe()
    pid = os.fork()
    if pid > 0:
        if write_pid_func is not None:
            write_pid_func(pid)
        os.close(pwrite)
        f = os.fdopen(pread, 'rb')
        status, result = pickle.load(f)
        os.waitpid(pid, 0)
        f.close()
        if status == 0:
            return result
        raise result
    else:
        os.close(pread)
        if gid is not None:
            os.setgid(gid)
        if uid is not None:
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

    def fix_uid_gid(tarinfo, epath):
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
            if ugdata_valid: # NOTE: backward compat. remove after 2012
                # get uid/gid
                # if not found, returns -1 that won't change anything
                uid, gid = get_uid_from_user(uname), \
                    get_gid_from_group(gname)
                os.lchown(epath, uid, gid)
        except OSError:
            pass

    tar = None
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
        if sys.hexversion < 0x3000000:
            encoded_path = encoded_path.encode('utf-8')
        entries = []
        for tarinfo in tar:

            epath = os.path.join(encoded_path, tarinfo.name)
            if tarinfo.isdir():
                # Extract directory with a safe mode, so that
                # all files below can be extracted as well.
                try:
                    os.makedirs(epath, 0o777)
                except EnvironmentError:
                    pass
                entries.append((tarinfo, epath,))

            tar.extract(tarinfo, encoded_path)
            del tar.members[:]
            entries.append((tarinfo, epath,))

        entries.sort(key = lambda x: x[0].name, reverse = True)
        # Set correct owner, mtime and filemode on directories.
        for tarinfo, epath in entries:
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

    except EOFError:
        return -1
    finally:
        if tar is not None:
            del tar.members[:]
            tar.close()

    if os.listdir(extract_path):
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
    size = str(round(float(xbytes)/1024, 1))
    if xbytes < 1024:
        size = str(round(float(xbytes)))+"b"
    elif xbytes < 1023999:
        size += "kB"
    elif xbytes > 1023999:
        size = str(round(float(size)/1024, 1))
        size += "MB"
    return size

def get_random_temp_file():
    """
    Return random temporary file path.
    @deprecated

    @return: temporary, random file path
    @rtype: string
    """
    fd, tmp_path = tempfile.mkstemp()
    os.close(fd)
    return tmp_path

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

def read_elf_class(elf_file):
    """
    Read ELF class metadatum from ELF file.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: ELF class metadatum value
    @rtype: int
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
    Determine whether given file path points to an ELF file object.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: True, if file at path is ELF file
    @rtype: bool
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
    def do_resolve(mypaths, elf_class):
        found_path = None
        for ld_dir in mypaths:
            mypath = os.path.join(ld_dir, library)
            if not os.access(mypath, os.R_OK):
                continue
            if os.path.isdir(mypath):
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

readelf_avail_check = False
ldd_avail_check = False
def read_elf_dynamic_libraries(elf_file):
    """
    Extract NEEDED metadatum from ELF file at path.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: list (set) of strings in NEEDED metadatum
    @rtype: set
    """
    global readelf_avail_check
    if not readelf_avail_check:
        if not os.access("/usr/bin/readelf", os.X_OK):
            FileNotFound('FileNotFound: no readelf')
        readelf_avail_check = True
    return set([x.strip().split()[-1][1:-1] for x in \
        getstatusoutput('/usr/bin/readelf -d %s' % (elf_file,))[1].split("\n") \
            if (x.find("(NEEDED)") != -1)])

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
    global ldd_avail_check
    if not ldd_avail_check:
        if not os.access("/usr/bin/ldd", os.X_OK):
            FileNotFound('FileNotFound: no ldd')
    sts, output = getstatusoutput('/usr/bin/ldd "%s"' % (elf_file,))
    if sts != 0:
        # garbage file
        # non-dynamic executables cause this
        return []
    return set((x.split()[0].strip() for x in output.split("\n") if "=>" in x \
        and not x.split()[-1].startswith("(")))

def read_elf_broken_symbols(elf_file):
    """
    Extract broken symbols from ELF file.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: list of broken symbols in ELF file.
    @rtype: set
    """
    global ldd_avail_check
    if not ldd_avail_check:
        if not os.access("/usr/bin/ldd", os.X_OK):
            FileNotFound('FileNotFound: no ldd')
        ldd_avail_check = True
    return set([x.strip().split("\t")[0].split()[-1] for x in \
        getstatusoutput('/usr/bin/ldd -r "%s"' % (elf_file,))[1].split("\n") \
            if (x.find("undefined symbol:") != -1)])

def read_elf_linker_paths(elf_file):
    """
    Extract built-in linker paths (RUNPATH and RPATH) from ELF file.

    @param elf_file: path to ELF file
    @type elf_file: string
    @return: list of extracted built-in linker paths.
    @rtype: list
    """
    global readelf_avail_check
    if not readelf_avail_check:
        if not os.access("/usr/bin/readelf", os.X_OK):
            FileNotFound('FileNotFound: no readelf')
        readelf_avail_check = True
    data = [x.strip().split()[-1][1:-1].split(":") for x in \
        getstatusoutput('readelf -d %s' % (elf_file,))[1].split("\n") if not \
            ((x.find("(RPATH)") == -1) and (x.find("(RUNPATH)") == -1))]
    mypaths = []
    for mypath in data:
        for xpath in mypath:
            xpath = xpath.replace("$ORIGIN", os.path.dirname(elf_file))
            mypaths.append(xpath)
    return mypaths

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
        package_tag = "%s%s" % (etpConst['entropytagprefix'], package_tag,)
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
        package_tag = "%s%s" % (etpConst['entropytagprefix'], package_tag,)
    else:
        package_tag = ''
    package_name = "%s/%s-%s" % (category, name, version,)
    package_name += package_tag
    return package_name

def collect_linker_paths():
    """
    Collect dynamic linker paths set into /etc/ld.so.conf. This function is
    ROOT safe.

    @return: list of dynamic linker paths set
    @rtype: list
    """
    builtin_paths = ["/lib", "/usr/lib"]

    ld_conf = etpConst['systemroot']+"/etc/ld.so.conf"
    if not (os.path.isfile(ld_conf) and os.access(ld_conf, os.R_OK)):
        return builtin_paths

    ld_f = open(ld_conf, "r")
    paths = [os.path.normpath(x.strip()) for x in ld_f.readlines() \
        if x.startswith("/")]
    ld_f.close()

    for b_path in builtin_paths:
        if b_path not in paths:
            paths.append(b_path)

    return paths

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
        for idx in xrange(len(empty_list)):
            empty_list[idx] = empty_list[idx][len(base_directory)+1:]
