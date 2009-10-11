# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Source Package Manager "Portage" Plugin XPAK tools}.

"""
import sys
import os
import shutil
from entropy.output import TextInterface
from entropy.const import etpConst
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
    xpakpath = suck_xpak(tbz2file, etpConst['packagestmpdir'])
    return unpack_xpak(xpakpath, tmpdir)

def read_xpak(tbz2file):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @return: 
    @rtype: 
    """
    xpakpath = suck_xpak(tbz2file, etpConst['entropyunpackdir'])
    f = open(xpakpath, "rb")
    data = f.read()
    f.close()
    os.remove(xpakpath)
    return data

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
    try:
        if tmpdir is None:
            tmpdir = os.path.join(etpConst['packagestmpdir'],
                os.path.basename(xpakfile)[:-5])
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir, True)
        os.makedirs(tmpdir)
        xpakdata = xpak.getboth(xpakfile)
        xpak.xpand(xpakdata, tmpdir)
        try:
            os.remove(xpakfile)
        except OSError:
            pass
    except TypeError:
        return None
    return tmpdir

def suck_xpak(tbz2file, outputpath):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @param outputpath: 
    @type outputpath: 
    @return: 
    @rtype: 
    """

    dest_filename = os.path.basename(tbz2file)[:-5]+".xpak"
    xpakpath = os.path.join(outputpath, dest_filename)
    old = open(tbz2file, "rb")

    # position old to the end
    old.seek(0, os.SEEK_END)
    # read backward until we find
    bytes = old.tell()
    counter = bytes - 1
    # FIXME: when Python 2.x will phase out, use b"XPAKSTOP"...
    if sys.hexversion >= 0x3000000:
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

        old.seek(counter - bytes, os.SEEK_END)
        if (bytes - (abs(counter - bytes))) < chunk_len:
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
        return None
    if data_end_position is None:
        return None

    # now write to found metadata to file
    # starting from data_start_position
    # ending to data_end_position
    db = open(xpakpath, "wb")
    old.seek(data_start_position)
    to_read = data_end_position - data_start_position
    while to_read > 0:
        data = old.read(to_read)
        db.write(data)
        to_read -= len(data)

    db.flush()
    db.close()
    old.close()
    return xpakpath

def append_xpak(tbz2file, atom):
    """
    docstring_title

    @param tbz2file: 
    @type tbz2file: 
    @param atom: 
    @type atom: 
    @return: 
    @rtype: 
    """
    text = TextInterface()
    spm = get_default_instance(text)
    dbbuild = spm.get_installed_package_build_script_path(atom)
    dbdir = os.path.dirname(dbbuild)
    if os.path.isdir(dbdir):
        tbz2 = xpak.tbz2(tbz2file)
        tbz2.recompose(dbdir)
    return tbz2file