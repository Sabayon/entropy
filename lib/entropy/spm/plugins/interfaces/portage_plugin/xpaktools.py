# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
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
    old, db = None, None
    try:
        old = open(tbz2file, "rb")
        db = open(xpakpath, "wb")
        # position old to the end
        old.seek(0, os.SEEK_END)
        # read backward until we find
        n_bytes = old.tell()
        counter = n_bytes - 1
        if const_is_python3():
            xpak_end = b"XPAKSTOP"
            xpak_start = b"XPAKPACK"
            xpak_entry_point = b"X"
        else:
            xpak_end = "XPAKSTOP"
            xpak_start = "XPAKPACK"
            xpak_entry_point = "X"

        xpak_tag_len = len(xpak_start)
        chunk_len = 3
        data_start_position = None
        data_end_position = None

        while counter >= (0 - chunk_len):

            old.seek(counter - n_bytes, os.SEEK_END)
            if (n_bytes - (abs(counter - n_bytes))) < chunk_len:
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
