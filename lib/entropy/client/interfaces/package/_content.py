# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import codecs
import sys

from entropy.const import etpConst

import entropy.tools


class FileContentReader(object):

    def __init__(self, path, enc=None):
        if enc is None:
            self._enc = etpConst['conf_encoding']
        else:
            self._enc = enc
        self._cpath = path
        self._file = None
        self._eof = False

    def _open_f(self):
        # opening the file in universal newline mode
        # fixes the readline() issues wrt
        # truncated lines.
        if isinstance(self._cpath, int):
            self._file = entropy.tools.codecs_fdopen(
                self._cpath, "rU", self._enc)
        else:
            self._file = codecs.open(
                self._cpath, "rU", self._enc)

    def __iter__(self):
        # reset object status, this makes possible
        # to reuse the iterator more than once
        # restarting from the beginning. It is really
        # important for scenarios where transactions
        # have to be rolled back and replayed.
        self.close()
        self._open_f()
        # reset EOF status on each new iteration
        self._eof = False
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, trace_obj):
        self.close()

    def __next__(self):
        return self.next()

    def next(self):
        if self._eof:
            raise StopIteration()
        if self._file is None:
            self._open_f()

        line = self._file.readline()
        if not line:
            self.close()
            self._eof = True
            raise StopIteration()

        # non-deterministic BUG with
        # ca-certificates and Python crappy
        # API causes readline() to return
        # partial lines when non ASCII cruft
        # is on the line. This is probably a
        # Python bug.
        # Example of partial readline():
        # 0|obj|/usr/share/ca-certificates/mozilla/NetLock_Arany_=Class_Gold=_F\xc3\x85
        # and the next call:
        # \xc2\x91tan\xc3\x83\xc2\xbas\xc3\x83\xc2\xadtv\xc3\x83\xc2\xa1ny.crt\n
        # Try to workaround it by reading ahead
        # if line does not end with \n
        # HOWEVER: opening the file in
        # Universal Newline mode fixes it.
        # But let's keep the check for QA.
        # 2012-08-14: is has been observed that
        # Universal Newline mode is not enough
        # to avoid this issue.
        while not line.endswith("\n"):
            part_line = self._file.readline()
            line += part_line
            sys.stderr.write(
                "FileContentReader, broken readline()"
                ", executing fixup code\n")
            sys.stderr.write("%s\n" % (repr(part_line),))
            # break infinite loops
            # and let it crash
            if not part_line: # EOF
                break

        _package_id, _ftype, _path = line[:-1].split("|", 2)
        # must be legal or die!
        _package_id = int(_package_id)
        return _package_id, _path, _ftype

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None


class FileContentWriter(object):

    TMP_SUFFIX = "__filter_tmp"

    def __init__(self, path, enc=None):
        self._file = None
        if enc is None:
            self._enc = etpConst['conf_encoding']
        else:
            self._enc = enc
        self._cpath = path
        # callers expect that file is created
        # on open object instantiation, don't
        # remove this or things like os.rename()
        # will fail
        self._open_f()

    def _open_f(self):
        if isinstance(self._cpath, int):
            self._file = entropy.tools.codecs_fdopen(
                self._cpath, "w", self._enc)
        else:
            self._file = codecs.open(
                self._cpath, "w", self._enc)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, trace_obj):
        self.close()

    def write(self, package_id, path, ftype):
        """
        Write an entry to file.
        """
        if self._file is None:
            self._open_f()

        if package_id is not None:
            self._file.write(str(package_id))
        else:
            self._file.write("0")
        self._file.write("|")
        self._file.write(ftype)
        self._file.write("|")
        self._file.write(path)
        self._file.write("\n")

    def close(self):
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None


class FileContentSafetyWriter(object):

    def __init__(self, path, enc=None):
        self._file = None
        if enc is None:
            self._enc = etpConst['conf_encoding']
        else:
            self._enc = enc
        self._cpath = path
        # callers expect that file is created
        # on open object instantiation, don't
        # remove this or things like os.rename()
        # will fail
        self._open_f()

    def _open_f(self):
        if isinstance(self._cpath, int):
            self._file = entropy.tools.codecs_fdopen(
                self._cpath, "w", self._enc)
        else:
            self._file = codecs.open(
                self._cpath, "w", self._enc)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, trace_obj):
        self.close()

    def write(self, path, sha256, mtime):
        """
        Write an entry to file.
        """
        if self._file is None:
            self._open_f()

        self._file.write("%f" % (mtime,))
        self._file.write("|")
        self._file.write(sha256)
        self._file.write("|")
        self._file.write(path)
        self._file.write("\n")

    def close(self):
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None


class FileContentSafetyReader(object):

    def __init__(self, path, enc=None):
        if enc is None:
            self._enc = etpConst['conf_encoding']
        else:
            self._enc = enc
        self._cpath = path
        self._file = None
        self._eof = False

    def _open_f(self):
        # opening the file in universal newline mode
        # fixes the readline() issues wrt
        # truncated lines.
        if isinstance(self._cpath, int):
            self._file = entropy.tools.codecs_fdopen(
                self._cpath, "rU", self._enc)
        else:
            self._file = codecs.open(
                self._cpath, "rU", self._enc)

    def __iter__(self):
        # reset object status, this makes possible
        # to reuse the iterator more than once
        # restarting from the beginning. It is really
        # important for scenarios where transactions
        # have to be rolled back and replayed.
        self.close()
        self._open_f()
        # reset EOF status on each new iteration
        self._eof = False
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, trace_obj):
        self.close()

    def __next__(self):
        return self.next()

    def next(self):
        if self._eof:
            raise StopIteration()
        if self._file is None:
            self._open_f()

        line = self._file.readline()
        if not line:
            self.close()
            self._eof = True
            raise StopIteration()

        # non-deterministic BUG with
        # ca-certificates and Python crappy
        # API causes readline() to return
        # partial lines when non ASCII cruft
        # is on the line. This is probably a
        # Python bug.
        # Example of partial readline():
        # 0|obj|/usr/share/ca-certificates/mozilla/NetLock_Arany_=Class_Gold=_F\xc3\x85
        # and the next call:
        # \xc2\x91tan\xc3\x83\xc2\xbas\xc3\x83\xc2\xadtv\xc3\x83\xc2\xa1ny.crt\n
        # Try to workaround it by reading ahead
        # if line does not end with \n
        # HOWEVER: opening the file in
        # Universal Newline mode fixes it.
        # But let's keep the check for QA.
        # 2012-08-14: is has been observed that
        # Universal Newline mode is not enough
        # to avoid this issue.
        while not line.endswith("\n"):
            part_line = self._file.readline()
            line += part_line
            sys.stderr.write(
                "FileContentReader, broken readline()"
                ", executing fixup code\n")
            sys.stderr.write("%s\n" % (repr(part_line),))
            # break infinite loops
            # and let it crash
            if not part_line: # EOF
                break

        _mtime, _sha256, _path = line[:-1].split("|", 2)
        # must be legal or die!
        _mtime = float(_mtime)
        return _path, _sha256, _mtime

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None
