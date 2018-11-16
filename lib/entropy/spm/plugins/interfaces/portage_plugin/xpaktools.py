# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @author: Slawomir Nizio <slawomir.nizio@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Source Package Manager "Portage" Plugin XPAK tools}.

"""
import sys
import os
import errno
import shutil
from entropy.const import etpConst, const_is_python3, const_mkdtemp, \
    const_mkstemp
from entropy.output import TextInterface
from entropy.spm.plugins.factory import get_default_instance
from entropy.spm.plugins.interfaces.portage_plugin import xpak

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
    tmp_fd, tmp_path = const_mkstemp(
        prefix="entropy.spm.portage.extract_xpak")
    os.close(tmp_fd)
    try:
        done = suck_xpak(tbz2file, tmp_path)
        if not done:
            return None
        return unpack_xpak(tmp_path, tmpdir = tmpdir)
    finally:
        try:
            # unpack_xpak already removes it
            os.remove(tmp_path)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise

def read_xpak(tbz2file):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @return: 
    @rtype: 
    """
    tmp_fd, tmp_path = const_mkstemp(
        prefix="entropy.spm.portage.read_xpak")
    os.close(tmp_fd)
    try:
        done = suck_xpak(tbz2file, tmp_path)
        if not done:
            return None
        with open(tmp_path, "rb") as f:
            data = f.read()
        return data
    finally:
        os.remove(tmp_path)

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
    if tmpdir is None:
        tmpdir = const_mkdtemp(prefix="unpack_xpak")
    elif not os.path.isdir(tmpdir):
        raise AttributeError("tmpdir %s does not exist" % (tmpdir,))
    try:
        xpakdata = xpak.getboth(xpakfile)
        xpak.xpand(xpakdata, tmpdir)
        return tmpdir
    except TypeError:
        return None
    finally:
        try:
            os.remove(xpakfile)
        except OSError:
            pass

def suck_xpak(tbz2file, xpakpath):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @param xpakpath: 
    @type xpakpath: 
    @return: 
    @rtype: 
    """
    if const_is_python3():
        xpak_end = b"XPAKSTOP"
        xpak_start = b"XPAKPACK"
    else:
        xpak_end = "XPAKSTOP"
        xpak_start = "XPAKPACK"

    chunk_size = 2048

    # Sanity check: makes the position calculations easier (seek_length below).
    assert len(xpak_end) == len(xpak_start)

    old, db = None, None
    try:
        old = open(tbz2file, "rb")
        db = open(xpakpath, "wb")
        data_start_position = None
        data_end_position = None
        # position old to the end
        old.seek(0, os.SEEK_END)
        n_bytes = old.tell()

        chunk_size = min(chunk_size, n_bytes)

        # position one chunk from the end, then continue
        seek_pos = n_bytes - chunk_size

        while True:
            old.seek(seek_pos, os.SEEK_SET)
            read_bytes = old.read(chunk_size)

            end_idx = read_bytes.rfind(xpak_end)
            if end_idx != -1:
                if data_start_position is None:
                    data_end_position = seek_pos + end_idx + len(xpak_end)
                    # avoid START after END in rfind()
                    read_bytes = read_bytes[:end_idx]

            start_idx = read_bytes.rfind(xpak_start)
            if start_idx != -1:
                if data_end_position is not None:
                    data_start_position = seek_pos + start_idx
                    break

            if seek_pos == 0:
                break

            # Make sure the seeks are so that there is enough overlap.
            seek_length = chunk_size - (len(xpak_start) - 1)
            seek_pos -= seek_length
            if seek_pos < 0:
                seek_pos = 0

        if data_start_position is None:
            return False
        if data_end_position is None:
            return False

        # now write to found metadata to file
        # starting from data_start_position
        # ending to data_end_position
        old.seek(data_start_position)
        to_read = data_end_position - data_start_position
        while to_read > 0:
            data = old.read(to_read)
            db.write(data)
            to_read -= len(data)
        return True

    finally:
        if old is not None:
            old.close()
        if db is not None:
            db.close()

def aggregate_xpak(tbz2file, xpakfile):
    """
    Aggregate xpakfile content to tbz2file

    @param tbz2file: 
    @type tbz2file: 
    @param xpakfile: 
    @type xpakfile: 
    @return: 
    @rtype: 
    """
    tbz2 = xpak.tbz2(tbz2file)
    with open(xpakfile, "rb") as xpak_f:
        # put all in memory
        xpak_data = xpak_f.read()
        tbz2.recompose_mem(xpak_data)
        del xpak_data
