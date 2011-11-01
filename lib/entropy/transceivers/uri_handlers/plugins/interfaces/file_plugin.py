# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @copyright: Copyright (C) 2002 Lars Gustaebel <lars@gustaebel.de>
    @license: GPL-2

    B{EntropyTransceiver File URI Handler module}.

"""
import os
import pwd
import grp
import shutil
import errno
import fcntl

from entropy.const import const_setup_perms, etpConst, const_debug_write
from entropy.transceivers.uri_handlers.skel import EntropyUriHandler
from entropy.tools import md5sum

#---------------------------------------------------------
# Bits used in the mode field, values in octal.
#---------------------------------------------------------
S_IFLNK = 0o120000        # symbolic link
S_IFREG = 0o100000        # regular file
S_IFBLK = 0o060000        # block device
S_IFDIR = 0o040000        # directory
S_IFCHR = 0o020000        # character device
S_IFIFO = 0o010000        # fifo

TSUID   = 0o4000          # set UID on execution
TSGID   = 0o2000          # set GID on execution
TSVTX   = 0o1000          # reserved

TUREAD  = 0o400           # read by owner
TUWRITE = 0o200           # write by owner
TUEXEC  = 0o100           # execute/search by owner
TGREAD  = 0o040           # read by group
TGWRITE = 0o020           # write by group
TGEXEC  = 0o010           # execute/search by group
TOREAD  = 0o004           # read by other
TOWRITE = 0o002           # write by other
TOEXEC  = 0o001           # execute/search by other

_filemode_table = (
    ((S_IFLNK,      "l"),
     (S_IFREG,      "-"),
     (S_IFBLK,      "b"),
     (S_IFDIR,      "d"),
     (S_IFCHR,      "c"),
     (S_IFIFO,      "p")),

    ((TUREAD,       "r"),),
    ((TUWRITE,      "w"),),
    ((TUEXEC|TSUID, "s"),
     (TSUID,        "S"),
     (TUEXEC,       "x")),

    ((TGREAD,       "r"),),
    ((TGWRITE,      "w"),),
    ((TGEXEC|TSGID, "s"),
     (TSGID,        "S"),
     (TGEXEC,       "x")),

    ((TOREAD,       "r"),),
    ((TOWRITE,      "w"),),
    ((TOEXEC|TSVTX, "t"),
     (TSVTX,        "T"),
     (TOEXEC,       "x"))
)

def filemode(mode):
    """Convert a file's mode to a string of the form
       -rwxrwxrwx.
       Used by TarFile.list()
    """
    perm = []
    for table in _filemode_table:
        for bit, char in table:
            if mode & bit == bit:
                perm.append(char)
                break
        else:
            perm.append("-")
    return "".join(perm)

class EntropyFileUriHandler(EntropyUriHandler):

    """
    EntropyUriHandler based FILE (local) transceiver plugin.
    """

    PLUGIN_API_VERSION = 4

    @staticmethod
    def approve_uri(uri):
        if uri.startswith("file://"):
            return True
        return False

    @staticmethod
    def get_uri_name(uri):
        myuri = uri.split("/")[2:][0].split(":")[0]
        myuri = myuri.split("@")[-1]
        return myuri

    @staticmethod
    def hide_sensible_data(uri):
        return uri

    def __init__(self, uri):
        EntropyUriHandler.__init__(self, uri)
        self.__dir = os.path.expanduser(
            os.path.expandvars(self._drop_file_protocol(uri)))

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _drop_file_protocol(self, uri_str):
        return uri_str[len("file://"):]

    def _setup_remote_path(self, remote_path):
        return os.path.join(self.__dir, remote_path)

    def download(self, remote_path, save_path):
        remote_str = self._setup_remote_path(remote_path)
        if not os.path.isfile(remote_str):
            return False # remote path not available
        tmp_save_path = save_path + EntropyUriHandler.TMP_TXC_FILE_EXT
        shutil.copyfile(remote_str, tmp_save_path)
        os.rename(tmp_save_path, save_path)
        return True

    def download_many(self, remote_paths, save_dir):
        for remote_path in remote_paths:
            save_path = os.path.join(save_dir, os.path.basename(remote_path))
            rc = self.download(remote_path, save_path)
            if not rc:
                return rc
        return rc

    def upload(self, load_path, remote_path):
        remote_str = self._setup_remote_path(remote_path)
        tmp_remote_str = remote_str + EntropyUriHandler.TMP_TXC_FILE_EXT
        shutil.copyfile(load_path, tmp_remote_str)
        os.rename(tmp_remote_str, remote_str)
        return True

    def lock(self, remote_path):
        remote_str = self._setup_remote_path(remote_path)
        remote_str_lock = os.path.join(
            os.path.dirname(remote_str),
            "." + os.path.basename(remote_str) + ".lock")
        const_debug_write(__name__,
            "lock(): remote_str: %s, lock: %s" % (
                remote_str, remote_str_lock,))

        # Use low level IO because Python open() and with stmt
        # do unwanted things like creating the file on close() or
        # context exit. I didn't investigate nor I do care actually.
        lock_fd = None
        try:
            lock_fd = os.open(remote_str_lock, os.O_RDWR | os.O_CREAT)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError as err:
                if err.errno not in (errno.EACCES, errno.EAGAIN,):
                    # ouch, wtf?
                    raise
                return False
            # create file
            if os.path.isfile(remote_str):
                # locked, ouch
                return False
            # we run in mutual exclusion, so it's safe
            # to do test-and-set here
            with open(remote_str, "wb") as remote_f:
                pass
            # cleanup the lock file
            os.remove(remote_str_lock)
            # release the resource
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            return True
        finally:
            if lock_fd is not None:
                os.close(lock_fd)

    def upload_many(self, load_path_list, remote_dir):
        for load_path in load_path_list:
            remote_path = os.path.join(remote_dir, os.path.basename(load_path))
            rc = self.upload(load_path, remote_path)
            if not rc:
                return rc
        return True

    def rename(self, remote_path_old, remote_path_new):
        remote_ptr_old = self._setup_remote_path(remote_path_old)
        remote_ptr_new = self._setup_remote_path(remote_path_new)
        try:
            os.rename(remote_ptr_old, remote_ptr_new)
        except OSError:
            tmp_remote_ptr_new = remote_ptr_new + \
                EntropyUriHandler.TMP_TXC_FILE_EXT
            shutil.move(remote_ptr_old, tmp_remote_ptr_new)
            os.rename(tmp_remote_ptr_new, remote_ptr_new)
        return True

    def copy(self, remote_path_old, remote_path_new):
        tmp_remote_path_new = remote_path_new + \
            EntropyUriHandler.TMP_TXC_FILE_EXT
        remote_ptr_old = self._setup_remote_path(remote_path_old)
        remote_ptr_new = self._setup_remote_path(tmp_remote_path_new)
        try:
            shutil.copy2(remote_ptr_old, remote_ptr_new)
        except (OSError, IOError):
            self.delete(tmp_remote_path_new)
            return False
        # atomic rename
        done = self.rename(tmp_remote_path_new, remote_path_new)
        if not done:
            self.delete(tmp_remote_path_new)
        return done

    def delete(self, remote_path):
        remote_str = self._setup_remote_path(remote_path)
        try:
            os.remove(remote_str)
        except OSError:
            return False
        return True

    def delete_many(self, remote_paths):
        for remote_path in remote_paths:
            rc = self.delete(remote_path)
            if not rc:
                return rc
        return True

    def get_md5(self, remote_path):
        remote_str = self._setup_remote_path(remote_path)
        if not os.path.isfile(remote_str):
            return None
        return md5sum(remote_str)

    def list_content(self, remote_path):
        remote_str = self._setup_remote_path(remote_path)
        if os.path.isdir(remote_str):
            return os.listdir(remote_str)
        return []

    def list_content_metadata(self, remote_path):
        content = self.list_content(remote_path)
        remote_str = self._setup_remote_path(remote_path)
        data = []
        for item in content:
            item_path = os.path.join(remote_str, item)
            st = os.lstat(item_path)
            try:
                owner = pwd.getpwuid(st.st_uid).pw_name
            except KeyError:
                owner = "nobody"
            try:
                group = grp.getgrgid(st.st_gid).gr_name
            except KeyError:
                group = "nobody"
            data.append((item, st.st_size, owner, group, filemode(st.st_mode)))

        return data

    def is_dir(self, remote_path):
        remote_str = self._setup_remote_path(remote_path)
        return os.path.isdir(remote_str)

    def is_file(self, remote_path):
        remote_str = self._setup_remote_path(remote_path)
        return os.path.isfile(remote_str)

    def is_path_available(self, remote_path):
        remote_str = self._setup_remote_path(remote_path)
        return os.path.lexists(remote_str)

    def makedirs(self, remote_path):
        remote_str = self._setup_remote_path(remote_path)
        if not os.path.isdir(remote_str):
            os.makedirs(remote_str, 0o755)
        const_setup_perms(remote_str, etpConst['entropygid'], recursion = False)
        return True

    def keep_alive(self):
        return

    def close(self):
        return
