# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{EntropyTransceiver SSH URI Handler module}.

"""
import os
import time
import tempfile

from entropy.output import brown, darkgreen
from entropy.i18n import _
from entropy.exceptions import ConnectionError
from entropy.transceivers.uri_handlers.skel import EntropyUriHandler

class EntropySshUriHandler(EntropyUriHandler):

    PLUGIN_API_VERSION = 0

    """
    EntropyUriHandler based SSH (with pubkey) transceiver plugin.
    """

    _DEFAULT_TIMEOUT = 60
    _DEFAULT_PORT = 22
    _TXC_CMD = "/usr/bin/scp"
    _SSH_CMD = "/usr/bin/ssh"

    @staticmethod
    def approve_uri(uri):
        if uri.startswith("ssh://"):
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

        import socket, subprocess, pty
        self._socket, self._subprocess = socket, subprocess
        self._pty = pty
        self.__host = EntropySshUriHandler.get_uri_name(self._uri)
        self.__user, self.__port, self.__dir = self.__extract_scp_data(
            self._uri)

        # as documentation suggests
        # test out connection first
        self.__test_connection()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __test_connection(self):
        tries = 5
        while tries:
            tries -= 1
            try:
                self._socket.create_connection((self.__host, self.__port), 5)
                break
            except self._socket.error:
                time.sleep(1)
                continue

        raise ConnectionError("cannot connect to %s on port %s" % (
            self.__host, self.__port,))

    def __extract_scp_data(self, uri):

        no_ssh_split = uri.split("ssh://")[-1]
        user = ''
        if "@" in no_ssh_split:
            user = no_ssh_split.split("@")[0]

        port = uri.split(":")[-1]
        try:
            port = int(port)
        except ValueError:
            port = EntropySshUriHandler._DEFAULT_PORT

        sdir = '~/'
        proposed_sdir = no_ssh_split.split(":", 1)[-1].split(":")[0]
        if proposed_sdir:
            sdir = proposed_sdir

        return user, port, sdir

    def _parse_progress_line(self, line):

        line_data = line.strip().split()
        if len(line_data) < 5:
            # mmh... not possible to properly parse data
            self.updateProgress(line.strip(), back = True)
            return

        percent = line_data[1]
        tx_speed = line_data[3]
        tx_size = line_data[2]
        eta = line_data[4]

        # create text
        mytxt = _("Transfer status")
        current_txt = brown("    <-> %s: " % (mytxt,)) + \
            darkgreen(tx_size) + " " + \
            brown("[") + str(percent) + brown("]") + \
            " " + eta + " " + tx_speed

        self.updateProgress(current_txt, back = True)

    def _update_progress(self, std_r):
        read_buf = ""
        try:
            char = std_r.read(1)
            while char:
                if (char == "\r") and read_buf:
                    self._parse_progress_line(read_buf)
                    read_buf = ""
                elif (char != "\r"):
                    read_buf += char
                char = std_r.read(1)
        except IOError:
            return

    def _fork_cmd(self, args):

        pid, fd = self._pty.fork()

        if pid == 0:
            proc = self._subprocess.Popen(args)
            os._exit(proc.wait())
        elif pid == -1:
            raise ConnectionError("cannot forkpty()")
        else:
            dead = False
            return_code = 1
            std_r = os.fdopen(fd, "r")
            while not dead:

                try:
                    dead, return_code = os.waitpid(pid, os.WNOHANG)
                except OSError as e:
                    if e.errno != 10:
                        raise
                    dead = True

                time.sleep(0.5)
                self._update_progress(std_r)
            std_r.close()

            return return_code

    def _exec_cmd(self, args):

        fd, tmp_path = tempfile.mkstemp()
        fd_err, tmp_path_err = tempfile.mkstemp()
        os.close(fd)
        os.close(fd_err)

        with open(tmp_path, "wb") as std_f:
            with open(tmp_path_err, "wb") as std_f_err:
                proc = self._subprocess.Popen(args, stdout = std_f,
                    stderr = std_f_err)
                exec_rc = proc.wait()

        std_f = open(tmp_path, "rb")
        output = std_f.read()
        std_f.close()
        std_f = open(tmp_path_err, "rb")
        error = std_f.read()
        std_f.close()

        os.remove(tmp_path)
        os.remove(tmp_path_err)
        return exec_rc, output, error

    def _setup_common_args(self, remote_path):
        args = []
        if self._speed_limit:
            args += ["-l", str(self._speed_limit*8)] # scp wants kbits/sec
        remote_ptr = os.path.join(self.__dir, remote_path)
        remote_str = ""
        if self.__user:
            remote_str += self.__user + "@"
        remote_str += self.__host + ":" + remote_ptr

        return args, remote_str

    def download(self, remote_path, save_path):
        args = [EntropySshUriHandler._TXC_CMD]
        c_args, remote_str = self._setup_common_args(remote_path)
        args.extend(c_args)
        args += ["-B", "-P", str(self.__port), remote_str, save_path]
        return self._fork_cmd(args) == 0

    def upload(self, load_path, remote_path):
        args = [EntropySshUriHandler._TXC_CMD]
        c_args, remote_str = self._setup_common_args(remote_path)
        args.extend(c_args)
        args += ["-B", "-P", str(self.__port), load_path, remote_str]
        return self._fork_cmd(args) == 0

    def _setup_fs_args(self):
        args = [EntropySshUriHandler._SSH_CMD]
        remote_str = ""
        if self.__user:
            remote_str += self.__user + "@"
        remote_str += self.__host
        return args, remote_str

    def rename(self, remote_path_old, remote_path_new):
        args, remote_str = self._setup_fs_args()
        remote_ptr_old = os.path.join(self.__dir, remote_path_old)
        remote_ptr_new = os.path.join(self.__dir, remote_path_new)
        args += [remote_str, "mv", remote_ptr_old, remote_ptr_new]
        return self._exec_cmd(args)[0] == 0

    def delete(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "rm", remote_ptr]
        return self._exec_cmd(args)[0] == 0

    def get_md5(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "md5sum", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        if exec_rc:
            return None
        return output.strip().split()[0]

    def list_content(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "ls", "-1", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        if exec_rc:
            return []
        return [x for x in output.split("\n") if x]

    def list_content_metadata(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "ls", "-1lA", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        if exec_rc:
            return []

        data = []
        for item in output.split("\n"):
            item = item.strip().split()
            if len(item) < 5:
                continue
            perms, owner, group, size, name = item[0], item[2], item[3], \
                item[4], item[-1]
            data.append((name, size, owner, group, perms,))
        return data

    def is_dir(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "test", "-d", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        return exec_rc == 0

    def is_file(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "test", "-f", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        return exec_rc == 0

    def is_path_available(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "stat", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        return exec_rc == 0

    def makedirs(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "mkdir", "-p", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        return exec_rc == 0

    def keep_alive(self):
        return

    def close(self):
        return
