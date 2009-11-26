# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{EntropyTransceiver FTP URI Handler module}.

"""
import os
import time

from entropy.tools import print_traceback, get_file_size, \
    convert_seconds_to_fancy_output, bytes_into_human, spliturl
from entropy.output import blue, brown, darkgreen, red
from entropy.i18n import _
from entropy.exceptions import ConnectionError, TransceiverError
from entropy.transceivers.uri_handlers.skel import EntropyUriHandler

class EntropyFtpUriHandler(EntropyUriHandler):

    PLUGIN_API_VERSION = 0

    """
    EntropyUriHandler based FTP transceiver plugin.
    """

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

        import socket, ftplib
        self.socket, self.ftplib = socket, ftplib
        self.__connected = False
        self.__ftpconn = None
        self.__currentdir = '.'
        self.__ftphost = EntropyFtpUriHandler.get_uri_name(self._uri)
        self.__ftpuser, self.__ftppassword, self.__ftpport, self.__ftpdir = \
            self.__extract_ftp_data(self._uri)

        self._init_vars()

        # as documentation suggests
        # test out connection first
        self._connect()
        self._disconnect()

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
        except ConnectionError:
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
            except (self.socket.gaierror,) as e:
                raise ConnectionError('ConnectionError: %s' % (e,))
            except (self.socket.error,) as e:
                if not count:
                    raise ConnectionError('ConnectionError: %s' % (e,))
            except:
                if not count:
                    raise

        if self._verbose:
            mytxt = _("connecting with user")
            self.updateProgress(
                "[ftp:%s] %s: %s" % (
                    darkgreen(self.__ftphost), mytxt, blue(self.__ftpuser),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        try:
            self.__ftpconn.login(self.__ftpuser, self.__ftppassword)
        except self.ftplib.error_perm as e:
            raise ConnectionError('ConnectionError: %s' % (e,))

        if self._verbose:
            mytxt = _("switching to")
            self.updateProgress(
                "[ftp:%s] %s: %s" % (
                    darkgreen(self.__ftphost), mytxt, blue(self.__ftpdir),
                ),
                importance = 1,
                type = "info",
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
            except (EOFError, self.socket, self.socket.timeout,
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
            self.updateProgress(
                "[ftp:%s] %s: %s" % (darkgreen(self.__ftphost),
                    mytxt, blue(mydir),),
                importance = 1,
                type = "info",
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
            round_fsize = int(round(self.__filesize*1024, 0))
            round_rsize = int(round(self.__transfersize, 0))
            self.__time_remaining_secs = int(round((round_fsize - \
                round_rsize)/self.__datatransfer, 0))
            self.__time_remaining = \
                convert_seconds_to_fancy_output(self.__time_remaining_secs)
        except (ValueError, TypeError,):
            self.__time_remaining = "(%s)" % (_("infinite"),)

    def _speed_limit_loop(self):
        if self._speed_limit:
            while self.__datatransfer > self._speed_limit * 1024:
                time.sleep(0.1)
                self._update_speed()
                self._update_progress()

    def _commit_buffer_update(self, buf_len):
        # get the buffer size
        self.__filekbcount += float(buf_len)/1024
        self.__transfersize += buf_len

    def _update_progress(self, force = False):

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

            self.updateProgress(current_txt, back = True)
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

    def download(self, remote_path, save_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)
        tmp_save_path = save_path + ".dtmp"

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
            try:

                self.__filekbcount = 0
                # get the file size
                self.__filesize = self._get_file_size_compat(path)
                if (self.__filesize):
                    self.__filesize = round(float(int(self.__filesize))/1024, 1)
                    if (self.__filesize == 0):
                        self.__filesize = 1
                elif not self.is_path_available(path):
                    return False
                else:
                    self.__filesize = 0

                with open(tmp_save_path, "wb") as f:
                    rc = self.__ftpconn.retrbinary('RETR ' + path, writer, 8192)
                    f.flush()
                self._update_progress(force = True)

                done = rc.find("226") != -1
                if done:
                    # download complete, atomic mv
                    os.rename(tmp_save_path, save_path)

                return done

            except Exception as e: # connection reset by peer

                print_traceback()
                mytxt = red("%s: %s, %s... #%s") % (
                    _("Download issue"),
                    e,
                    _("retrying"),
                    tries+1,
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = "  "
                    )
                self._reconnect() # reconnect

    def upload(self, load_path, remote_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        tmp_path = path + ".dtmp"
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
                self.__filesize = round(float(file_size)/ 1024, 1)
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
                    e,
                    _("retrying"),
                    tries+1,
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = "  "
                    )
                self._reconnect() # reconnect
                self.delete(tmp_path)
                self.delete(path)

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
            raise ConnectionError("keep_alive when not connected")
        try:
            self.__ftpconn.sendcmd("NOOP")
        except (self.ftplib.error_temp, self.ftplib.error_reply,):
            raise ConnectionError("cannot execute keep_alive")

    def close(self):
        """ just call our disconnect method """
        self._disconnect()