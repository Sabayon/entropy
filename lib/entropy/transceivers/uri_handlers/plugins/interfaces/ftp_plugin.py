# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{EntropyTransceiver FTP URI Handler module}.

"""
import os
import time
import socket

from entropy.const import const_debug_write, const_mkstemp
from entropy.tools import print_traceback, get_file_size, \
    convert_seconds_to_fancy_output, bytes_into_human, spliturl
from entropy.output import blue, brown, darkgreen, red
from entropy.i18n import _
from entropy.transceivers.exceptions import TransceiverError, \
    TransceiverConnectionError
from entropy.transceivers.uri_handlers.skel import EntropyUriHandler

class EntropyFtpUriHandler(EntropyUriHandler):

    """
    EntropyUriHandler based FTP transceiver plugin.
    """

    PLUGIN_API_VERSION = 4

    _DEFAULT_TIMEOUT = 60

    @staticmethod
    def approve_uri(uri):
        if uri.startswith("ftp://"):
            return True
        return False

    @staticmethod
    def get_uri_name(uri):
        myuri = spliturl(uri)[1]
        # remove username:pass@
        myuri = myuri.split("@")[-1]
        return myuri

    @staticmethod
    def hide_sensible_data(uri):
        ftppassword = uri.split("@")[:-1]
        if not ftppassword:
            return uri
        ftppassword = '@'.join(ftppassword)
        ftppassword = ftppassword.split(":")[-1]
        if not ftppassword:
            return uri
        newuri = uri.replace(ftppassword, "xxxxxxxx")
        return newuri

    def __init__(self, uri):
        EntropyUriHandler.__init__(self, uri)

        import ftplib
        self.ftplib = ftplib
        self.__connected = False
        self.__ftpconn = None
        self.__currentdir = '.'
        self.__ftphost = EntropyFtpUriHandler.get_uri_name(self._uri)
        self.__ftpuser, self.__ftppassword, self.__ftpport, self.__ftpdir = \
            self.__extract_ftp_data(self._uri)

        self._init_vars()

    def __enter__(self):
        pass # self.__connect_if_not()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __extract_ftp_data(self, ftpuri):
        ftpuser = ftpuri.split("ftp://")[-1].split(":")[0]
        if (not ftpuser):
            ftpuser = "anonymous@"
            ftppassword = "anonymous"
        else:
            ftppassword = ftpuri.split("@")[:-1]
            if len(ftppassword) > 1:
                ftppassword = '@'.join(ftppassword)
                ftppassword = ftppassword.split(":")[-1]
                if (not ftppassword):
                    ftppassword = "anonymous"
            else:
                ftppassword = ftppassword[0]
                ftppassword = ftppassword.split(":")[-1]
                if not ftppassword:
                    ftppassword = "anonymous"

        ftpport = ftpuri.split(":")[-1]
        try:
            ftpport = int(ftpport)
        except ValueError:
            ftpport = 21

        ftpdir = '/'
        if ftpuri.count("/") > 2:
            ftpdir = ftpuri[6:]
            ftpdir = "/" + ftpdir.split("/", 1)[-1]
            ftpdir = ftpdir.split(":")[0]
            if not ftpdir:
                ftpdir = '/'
            elif ftpdir.endswith("/") and (ftpdir != "/"):
                ftpdir = ftpdir[:-1]

        return ftpuser, ftppassword, ftpport, ftpdir

    def __connect_if_not(self):
        """
        Handy internal method.
        """
        if not self.__connected:
            self._connect()
        try:
            self.keep_alive()
        except TransceiverConnectionError:
            self._connect()

    def _connect(self):
        """
        Connect to FTP host.
        """
        timeout = self._timeout
        if timeout is None:
            # default timeout set to 60 seconds
            timeout = EntropyFtpUriHandler._DEFAULT_TIMEOUT

        count = 10
        while True:
            count -= 1
            try:
                self.__ftpconn = self.ftplib.FTP()
                self.__ftpconn.connect(self.__ftphost, self.__ftpport, timeout)
                break
            except (socket.gaierror,) as e:
                raise TransceiverConnectionError(repr(e))
            except (socket.error,) as e:
                if not count:
                    raise TransceiverConnectionError(repr(e))
            except:
                if not count:
                    raise

        if self._verbose:
            mytxt = _("connecting with user")
            self.output(
                "[ftp:%s] %s: %s" % (
                    darkgreen(self.__ftphost), mytxt, blue(self.__ftpuser),
                ),
                importance = 1,
                level = "info",
                header = darkgreen(" * ")
            )
        try:
            self.__ftpconn.login(self.__ftpuser, self.__ftppassword)
        except self.ftplib.error_perm as e:
            raise TransceiverConnectionError(repr(e))

        if self._verbose:
            mytxt = _("switching to")
            self.output(
                "[ftp:%s] %s: %s" % (
                    darkgreen(self.__ftphost), mytxt, blue(self.__ftpdir),
                ),
                importance = 1,
                level = "info",
                header = darkgreen(" * ")
            )
        # create dirs if they don't exist
        self._set_cwd(self.__ftpdir, dodir = True)
        self.__connected = True

    def _disconnect(self):
        if self.__ftpconn is not None:
            # try to disconnect
            try:
                self.__ftpconn.quit()
            except (EOFError, socket.error, socket.timeout,
                self.ftplib.error_reply,):
                # AttributeError is raised when socket gets trashed
                # EOFError is raised when the connection breaks
                # timeout, who cares!
                pass
            self.__ftpconn = None
        self.__connected = False

    def _reconnect(self):
        self._disconnect()
        self._connect()

    def _init_vars(self):
        self.__oldprogress_t = time.time()
        self.__datatransfer = 0
        self.__filesize = 0
        self.__filekbcount = 0
        self.__transfersize = 0
        self.__startingposition = 0
        self.__elapsed = 0.0
        self.__time_remaining_secs = 0
        self.__time_remaining = "(%s)" % (_("infinite"),)
        self.__starttime = time.time()

    def _get_cwd(self):
        return self.__ftpconn.pwd()

    def _set_cwd(self, mydir, dodir = False):
        try:
            return self.__set_cwd(mydir, dodir)
        except self.ftplib.error_perm as e:
            raise TransceiverError('TransceiverError: %s' % (e,))

    def __set_cwd(self, mydir, dodir = False):
        if self._verbose:
            mytxt = _("switching to")
            self.output(
                "[ftp:%s] %s: %s" % (darkgreen(self.__ftphost),
                    mytxt, blue(mydir),),
                importance = 1,
                level = "info",
                header = darkgreen(" * ")
            )
        try:
            self.__ftpconn.cwd(mydir)
        except self.ftplib.error_perm as e:
            if e[0][:3] == '550' and dodir:
                self.makedirs(mydir)
                self.__ftpconn.cwd(mydir)
            else:
                raise
        self.__currentdir = self._get_cwd()

    def _set_pasv(self, pasv):
        self.__ftpconn.set_pasv(pasv)

    def _set_chmod(self, chmodvalue, filename):
        return self.__ftpconn.voidcmd("SITE CHMOD " + str(chmodvalue) + " " + \
            str(filename))

    def _get_file_mtime(self, path):
        rc = self.__ftpconn.sendcmd("mdtm " + path)
        return rc.split()[-1]

    def _send_cmd(self, cmd):
        return self.__ftpconn.sendcmd(cmd)

    def _update_speed(self):
        current_time = time.time()
        self.__elapsed = current_time - self.__starttime
        # we have the diff size
        pos_diff = self.__transfersize - self.__startingposition
        self.__datatransfer = pos_diff / self.__elapsed
        if self.__datatransfer < 0:
            self.__datatransfer = 0
        try:
            round_fsize = int(round(self.__filesize * 1000, 0))
            round_rsize = int(round(self.__transfersize, 0))
            self.__time_remaining_secs = int(round((round_fsize - \
                round_rsize)/self.__datatransfer, 0))
            self.__time_remaining = \
                convert_seconds_to_fancy_output(self.__time_remaining_secs)
        except (ValueError, TypeError,):
            self.__time_remaining = "(%s)" % (_("infinite"),)

    def _speed_limit_loop(self):
        if self._speed_limit:
            while self.__datatransfer > self._speed_limit * 1000:
                time.sleep(0.1)
                self._update_speed()
                self._update_progress()

    def _commit_buffer_update(self, buf_len):
        # get the buffer size
        self.__filekbcount += float(buf_len) / 1000
        self.__transfersize += buf_len

    def _update_progress(self, force = False):
        if self._silent:
            # stfu !
            return
        upload_percent = 100.0
        upload_size = round(self.__filekbcount, 1)

        if self.__filesize >= 1:
            kbcount_round = round(self.__filekbcount, 1)
            upload_percent = round((kbcount_round / self.__filesize) * 100, 1)

        delta_secs = 0.5
        cur_t = time.time()
        if (cur_t > (self.__oldprogress_t + delta_secs)) or force:

            upload_percent = str(upload_percent)+"%"
            # create text
            mytxt = _("Transfer status")
            current_txt = brown("    <-> %s: " % (mytxt,)) + \
                darkgreen(str(upload_size)) + "/" + \
                red(str(self.__filesize)) + " kB " + \
                brown("[") + str(upload_percent) + brown("]") + \
                " " + self.__time_remaining + " " + \
                bytes_into_human(self.__datatransfer) + \
                "/" + _("sec")

            self.output(current_txt, back = True)
            self.__oldprogress_t = cur_t

    def _get_file_size(self, filename):
        return self.__ftpconn.size(filename)

    def _get_file_size_compat(self, filename):
        try:
            sc = self.__ftpconn.sendcmd
            data = [x.split() for x in sc("stat %s" % (filename,)).split("\n")]
        except self.ftplib.error_temp:
            return ""
        for item in data:
            if item[-1] == filename:
                return item[4]
        return ""

    def _mkdir(self, directory):
        return self.__ftpconn.mkd(directory)

    def _rmdir(self, directory):
        return self.__ftpconn.rmd(directory)

    def download(self, remote_path, save_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)
        tmp_save_path = save_path + EntropyUriHandler.TMP_TXC_FILE_EXT

        def writer(buf):
            # writing file buffer
            f.write(buf)
            self._commit_buffer_update(len(buf))
            self._update_speed()
            self._update_progress()
            self._speed_limit_loop()

        tries = 10
        while tries:

            tries -= 1
            self._init_vars()
            self.__filekbcount = 0
            rc = ''

            try:

                # get the file size
                self.__filesize = self._get_file_size_compat(path)
                if (self.__filesize):
                    self.__filesize = round(float(int(self.__filesize))/1000, 1)
                    if (self.__filesize == 0):
                        self.__filesize = 1
                elif not self.is_path_available(path):
                    return False
                else:
                    self.__filesize = 0

                with open(tmp_save_path, "wb") as f:
                    rc = self.__ftpconn.retrbinary('RETR ' + path, writer, 8192)

                self._update_progress(force = True)
                done = rc.find("226") != -1
                if done:
                    # download complete, atomic mv
                    os.rename(tmp_save_path, save_path)

            except (IOError, self.ftplib.error_reply, socket.error) as e:
                # connection reset by peer

                print_traceback()
                mytxt = red("%s: %s, %s... #%s") % (
                    _("Download issue"),
                    repr(e),
                    _("retrying"),
                    tries+1,
                )
                self.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = "  "
                    )
                self._reconnect() # reconnect
                continue

            finally:
                if os.path.isfile(tmp_save_path):
                    os.remove(tmp_save_path)

            return done


    def download_many(self, remote_paths, save_dir):
        for remote_path in remote_paths:
            save_path = os.path.join(save_dir, os.path.basename(remote_path))
            rc = self.download(remote_path, save_path)
            if not rc:
                return rc
        return True

    def upload(self, load_path, remote_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        tmp_path = path + EntropyUriHandler.TMP_TXC_FILE_EXT
        tries = 0

        def updater(buf):
            self._commit_buffer_update(len(buf))
            self._update_speed()
            self._update_progress()
            self._speed_limit_loop()

        while tries < 10:

            tries += 1
            self._init_vars()

            try:

                file_size = get_file_size(load_path)
                self.__filesize = round(float(file_size)/ 1000, 1)
                self.__filekbcount = 0

                with open(load_path, "r") as f:
                    rc = self.__ftpconn.storbinary("STOR " + tmp_path, f,
                        8192, updater)

                self._update_progress(force = True)
                # now we can rename the file with its original name
                self.rename(tmp_path, path)

                done = rc.find("226") != -1
                return done

            except Exception as e: # connection reset by peer

                print_traceback()
                mytxt = red("%s: %s, %s... #%s") % (
                    _("Upload issue"),
                    repr(e),
                    _("retrying"),
                    tries+1,
                )
                self.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = "  "
                    )
                self._reconnect() # reconnect
                self.delete(tmp_path)
                self.delete(path)

    def lock(self, remote_path):
        # The only atomic operation on FTP seems to be mkdir()
        # But there is no actual guarantee because it really depends
        # on the server implementation.
        # FTP is very old, got to live with it.
        self.__connect_if_not()

        remote_path_lock = os.path.join(
            os.path.dirname(remote_path),
            "." + os.path.basename(remote_path) + ".lock")
        remote_ptr = os.path.join(self.__ftpdir, remote_path)
        remote_ptr_lock = os.path.join(self.__ftpdir, remote_path_lock)

        const_debug_write(__name__,
            "lock(): remote_ptr: %s, lock: %s" % (
                remote_ptr, remote_ptr_lock,))

        try:
            self._mkdir(remote_ptr_lock)
        except self.ftplib.error_perm as e:
            return False

        # now we can create the lock file reliably
        tmp_fd, tmp_path = None, None
        try:
            tmp_fd, tmp_path = const_mkstemp(prefix="entropy.txc.ftp.lock")
            # check if remote_ptr is already there
            if self._is_path_available(remote_ptr):
                return False
            with open(tmp_path, "rb") as f:
                rc = self.__ftpconn.storbinary(
                    "STOR " + remote_ptr, f)
            done = rc.find("226") != -1
            if not done:
                # wtf?
                return False
            return True
        finally:
            if tmp_fd is not None:
                os.close(tmp_fd)
            if tmp_path is not None:
                os.remove(tmp_path)
            # and always remove the directory created with _mkdir()
            # we hope that, if we were able to create it, we're also
            # able to remove it.
            self._rmdir(remote_ptr_lock)

    def upload_many(self, load_path_list, remote_dir):
        for load_path in load_path_list:
            remote_path = os.path.join(remote_dir, os.path.basename(load_path))
            rc = self.upload(load_path, remote_path)
            if not rc:
                return rc
        return True

    def rename(self, remote_path_old, remote_path_new):

        self.__connect_if_not()

        old = os.path.join(self.__ftpdir, remote_path_old)
        new = os.path.join(self.__ftpdir, remote_path_new)
        try:
            rc = self.__ftpconn.rename(old, new)
        except self.ftplib.error_perm as err:
            # if err[0][:3] in ('553',):
            # workaround for some servers
            # try to delete old file first, and then call rename again
            self.delete(remote_path_new)
            rc = self.__ftpconn.rename(old, new)

        done = rc.find("250") != -1
        return done

    def __ftp_copy(self, fromname, toname):
        """
        FTP copy is not officially part of FTP RFCs.
        But for example, proftpd with mod_copy does support it.
        http://www.castaglia.org/proftpd/modules/mod_copy.html
        So it's worth a try.
        """
        resp = self.__ftpconn.sendcmd('CPFR ' + fromname)
        if resp[0] != '3':
            raise self.ftplib.error_reply(resp)
        return self.__ftpconn.voidcmd('CPTO ' + toname)

    def copy(self, remote_path_old, remote_path_new):

        self.__connect_if_not()

        tmp_suffix = EntropyUriHandler.TMP_TXC_FILE_EXT
        old = os.path.join(self.__ftpdir, remote_path_old)
        new = os.path.join(self.__ftpdir, remote_path_new)
        try:
            rc = self.__ftp_copy(old, new + tmp_suffix)
        except self.ftplib.Error as err:
            # FTP server doesn't support non-standard copy command
            return False

        done = rc.find("250") != -1
        if not done:
            return False

        # then rename to final name
        done = self.rename(remote_path_new + tmp_suffix, remote_path_new)
        if not done:
            # delete temp file, try at least
            self.delete(remote_path_new + tmp_suffix)
        return done

    def delete(self, remote_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        done = False
        try:
            rc = self.__ftpconn.delete(path)
            if rc.startswith("250"):
                done = True
        except self.ftplib.error_perm as err:
            if err[0][:3] == '550':
                done = True
            # otherwise not found

        return done

    def delete_many(self, remote_paths):
        for remote_path in remote_paths:
            rc = self.delete(remote_path)
            if not rc:
                return rc
        return True

    def get_md5(self, remote_path):
        # PROFTPD with mod_md5 supports it!
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        try:
            rc_data = self.__ftpconn.sendcmd("SITE MD5 %s" % (path,))
        except self.ftplib.error_perm:
            return None # not supported

        try:
            return rc_data.split("\n")[0].split("\t")[0].split("-")[1]
        except (IndexError, TypeError,): # wrong output
            return None

    def list_content(self, remote_path):
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)
        try:
            return [os.path.basename(x) for x in self.__ftpconn.nlst(path)]
        except self.ftplib.error_temp:
            raise ValueError("No such file or directory")

    def list_content_metadata(self, remote_path):
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        mybuffer = []
        def bufferizer(buf):
            mybuffer.append(buf)

        try:
            self.__ftpconn.dir(path, bufferizer)
        except self.ftplib.error_temp:
            raise ValueError("No such file or directory")

        data = []
        for item in mybuffer:
            item = item.split()
            name, size, owner, group, perms = item[8], item[4], item[2], \
                item[3], item[0]
            data.append((name, size, owner, group, perms,))

        return data

    def is_dir(self, remote_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        cwd = self._get_cwd()
        data = True
        try:
            self.__set_cwd(path)
        except self.ftplib.error_perm:
            data = False
        finally:
            self.__set_cwd(cwd)

        return data

    def is_file(self, remote_path):

        if self.is_dir(remote_path):
            return False
        return self.is_path_available(remote_path)

    def _is_path_available(self, full_path):

        path, fn = os.path.split(full_path)
        content = []
        def cb(x):
            y = os.path.basename(x)
            if y == fn:
                content.append(y)

        try:
            self.__ftpconn.retrlines('NLST %s' % (path,), cb)
        except self.ftplib.error_temp as err:
            if not str(err).startswith("450"):
                raise # wtf?
            # path does not exist if FTP error 450 is raised

        if content:
            return True
        return False

    def is_path_available(self, remote_path):
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)
        return self._is_path_available(path)

    def makedirs(self, remote_path):
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)
        mydirs = [x for x in path.split("/") if x]

        mycurpath = ""
        for mydir in mydirs:
            mycurpath = os.path.join(mycurpath, mydir)
            if not self._is_path_available(mycurpath):
                try:
                    self._mkdir(mycurpath)
                except self.ftplib.error_perm as e:
                    if e[0].lower().find("permission denied") != -1:
                        raise
                    elif e[0][:3] != '550':
                        raise

    def keep_alive(self):
        """
        Send a keep-alive ping to handler.
        """
        if not self.__connected:
            raise TransceiverConnectionError("keep_alive when not connected")
        try:
            self.__ftpconn.sendcmd("NOOP")
        except (self.ftplib.error_temp, self.ftplib.error_reply,):
            raise TransceiverConnectionError("cannot execute keep_alive")

    def close(self):
        """ just call our disconnect method """
        self._disconnect()
