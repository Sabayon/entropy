# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import codecs
import errno
import sys
import os

from entropy.const import etpConst, const_mkstemp

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


def generate_content_safety_file(content_safety):
    """
    Generate a file containing the "content_safety" metadata,
    reading by content_safety list or iterator. Each item
    of "content_safety" must contain (path, sha256, mtime).
    Each item shall be written to file, one per line,
    in the following form: "<mtime>|<sha256>|<path>".
    The order of the element in "content_safety" will be kept.
    """
    tmp_dir = os.path.join(
        etpConst['entropyunpackdir'],
        "__generate_content_safety_file_f")
    try:
        os.makedirs(tmp_dir, 0o755)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise

    tmp_fd, tmp_path = None, None
    generated = False
    try:
        tmp_fd, tmp_path = const_mkstemp(
            prefix="PackageContentSafety",
            dir=tmp_dir)
        with FileContentSafetyWriter(tmp_fd) as tmp_f:
            for path, sha256, mtime in content_safety:
                tmp_f.write(path, sha256, mtime)

        generated = True
        return tmp_path
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path is not None and not generated:
            try:
                os.remove(tmp_path)
            except (OSError, IOError):
                pass


def generate_content_file(content, package_id = None,
                          filter_splitdebug = False,
                          splitdebug = None,
                          splitdebug_dirs = None):
    """
    Generate a file containing the "content" metadata,
    reading by content list or iterator. Each item
    of "content" must contain (path, ftype).
    Each item shall be written to file, one per line,
    in the following form: "[<package_id>|]<ftype>|<path>".
    The order of the element in "content" will be kept.
    """
    tmp_dir = os.path.join(
        etpConst['entropyunpackdir'],
        "__generate_content_file_f")
    try:
        os.makedirs(tmp_dir, 0o755)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise

    tmp_fd, tmp_path = None, None
    generated = False
    try:
        tmp_fd, tmp_path = const_mkstemp(
            prefix="PackageContent",
            dir=tmp_dir)
        with FileContentWriter(tmp_fd) as tmp_f:
            for path, ftype in content:
                if filter_splitdebug and not splitdebug:
                    # if filter_splitdebug is enabled, this
                    # code filters out all the paths starting
                    # with splitdebug_dirs, if splitdebug is
                    # disabled for package.
                    _skip = False
                    for split_dir in splitdebug_dirs:
                        if path.startswith(split_dir):
                            _skip = True
                            break
                    if _skip:
                        continue
                tmp_f.write(package_id, path, ftype)

        generated = True
        return tmp_path
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path is not None and not generated:
            try:
                os.remove(tmp_path)
            except (OSError, IOError):
                pass


def merge_content_file(content_file, sorted_content,
                       cmp_func):
    """
    Given a sorted content_file content and a sorted list of
    content (sorted_content), apply the "merge" step of a merge
    sort algorithm. In other words, add the sorted_content to
    content_file keeping content_file content ordered.
    It is of couse O(n+m) where n = lines in content_file and
    m = sorted_content length.
    """
    tmp_content_file = content_file + FileContentWriter.TMP_SUFFIX

    sorted_ptr = 0
    _sorted_path = None
    _sorted_ftype = None
    _package_id = 0 # will be filled
    try:
        with FileContentWriter(tmp_content_file) as tmp_w:
            with FileContentReader(content_file) as tmp_r:
                for _package_id, _path, _ftype in tmp_r:

                    while True:

                        try:
                            _sorted_path, _sorted_ftype = \
                                sorted_content[sorted_ptr]
                        except IndexError:
                            _sorted_path = None
                            _sorted_ftype = None

                        if _sorted_path is None:
                            tmp_w.write(_package_id, _path, _ftype)
                            break

                        cmp_outcome = cmp_func(_path, _sorted_path)
                        if cmp_outcome < 0:
                            tmp_w.write(_package_id, _path, _ftype)
                            break

                        # always privilege _ftype over _sorted_ftype
                        # _sorted_ftype might be invalid
                        tmp_w.write(
                            _package_id, _sorted_path, _ftype)
                        sorted_ptr += 1
                        if cmp_outcome == 0:
                            # write only one
                            break

                # add the remainder
                if sorted_ptr < len(sorted_content):
                    _sorted_rem = sorted_content[sorted_ptr:]
                    for _sorted_path, _sorted_ftype in _sorted_rem:
                        tmp_w.write(
                            _package_id, _sorted_path, _sorted_ftype)

        os.rename(tmp_content_file, content_file)
    finally:
        try:
            os.remove(tmp_content_file)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise


def filter_content_file(content_file, filter_func):
    """
    This method rewrites the content of content_file by applying
    a filter to the path elements.
    """
    tmp_content_file = content_file + FileContentWriter.TMP_SUFFIX
    try:
        with FileContentWriter(tmp_content_file) as tmp_w:
            with FileContentReader(content_file) as tmp_r:
                for _package_id, _path, _ftype in tmp_r:
                    if filter_func(_path):
                        tmp_w.write(_package_id, _path, _ftype)
        os.rename(tmp_content_file, content_file)
    finally:
        try:
            os.remove(tmp_content_file)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
