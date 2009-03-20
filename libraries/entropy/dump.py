#!/usr/bin/python
"""
    # DESCRIPTION:
    # load/save a data to file by dumping its structure

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""
# pylint ok

from __future__ import with_statement
import os
from entropy.const import etpConst, const_setup_perms, const_setup_file
try:
    import cPickle as pickle
except ImportError:
    import pickle

D_EXT = etpConst['cachedumpext']
D_DIR = etpConst['dumpstoragedir']
E_GID = etpConst['entropygid']
if E_GID == None:
    E_GID = 0


def dumpobj(name, my_object, complete_path = False, ignore_exceptions = True):
    """
    Dump object to file

    @param name -- name of the object
    @param my_object -- object to dump
    @param complete_path -- name is a complete path
    @param ignore_exceptions -- ignore exceptions

    @return None
    """
    while 1: # trap ctrl+C
        try:
            if complete_path:
                dmpfile = name
            else:
                dump_path = os.path.join(D_DIR, name)
                dump_dir = os.path.dirname(dump_path)
                #dump_name = os.path.basename(dump_path)
                my_dump_dir = dump_dir
                d_paths = []
                while not os.path.isdir(my_dump_dir):
                    d_paths.append(my_dump_dir)
                    my_dump_dir = os.path.dirname(my_dump_dir)
                if d_paths:
                    d_paths = sorted(d_paths)
                    for d_path in d_paths:
                        os.mkdir(d_path, 0775)
                        const_setup_perms(d_path, E_GID)

                dmpfile = dump_path+D_EXT
            with open(dmpfile,"wb") as dmp_f:
                pickle.dump(my_object, dmp_f)
                dmp_f.flush()
            const_setup_file(dmpfile, E_GID, 0664)
        except RuntimeError:
            try:
                os.remove(dmpfile)
            except OSError:
                pass
        except (EOFError, IOError, OSError):
            if not ignore_exceptions:
                raise
        break

def serialize(myobj, ser_f, do_seek = True):
    """
    Serialize object to ser_f (file)

    @param myobj -- object to serialize
    @type myobj -- any picklable object
    @param ser_f -- file handle to write to
    @type ser_f -- file object
    @param do_seek -- move the file cursor to the beginning
    @type do_seek -- bool
    @return file object where data is stored to
    """
    pickle.dump(myobj, ser_f)
    ser_f.flush()
    if do_seek:
        ser_f.seek(0)
    return ser_f

def unserialize(serial_f):
    """
    Unserialize file to object (file)

    @param serial_f -- file object to read the stream to
    @type serial_f -- file object
    @return object reconstructed
    """
    return pickle.load(serial_f)

def unserialize_string(mystring):
    """
    Unserialize pickle string to object

    @param mystring -- data stream in string form to reconstruct
    @type mystring -- basestring
    @return reconstructed object
    """
    return pickle.loads(mystring)

def serialize_string(myobj):
    """
    Serialize object to string

    @param myobj -- object to serialize
    @type myobj -- any picklable object
    @return serialized string
    """
    return pickle.dumps(myobj)

def loadobj(name, complete_path = False):
    """
    Load object from a file
    @param name -- name of the object to load
    @type name -- basestring
    @param complete_path -- name is a complete serialized
        object file path to load
    @type complete_path -- basestring
    @return object or None
    """
    while 1:
        if complete_path:
            dmpfile = name
        else:
            dump_path = os.path.join(D_DIR, name)
            #dump_dir = os.path.dirname(dump_path)
            #dump_name = os.path.basename(dump_path)
            dmpfile = dump_path+D_EXT
        if os.path.isfile(dmpfile) and os.access(dmpfile, os.R_OK):
            try:
                with open(dmpfile,"rb") as dmp_f:
                    obj = None
                    try:
                        obj = pickle.load(dmp_f)
                    except (ValueError, EOFError, IOError,
                        OSError, pickle.UnpicklingError):
                        pass
                    return obj
            except (IOError, OSError,):
                pass
        break

def getobjmtime(name):
    """
    Get dumped object mtime

    @param name -- object name
    @type name -- basestring
    @return mtime -- integer
    """
    mtime = 0
    dump_path = os.path.join(D_DIR, name+D_EXT)
    if os.path.isfile(dump_path) and os.access(dump_path, os.R_OK):
        mtime = os.path.getmtime(dump_path)
    return int(mtime)

def removeobj(name):
    """
    Remove cached object through its object name

    @param name -- object name
    @type name -- basestring
    @return bool -- removed or not
    """
    filepath = D_DIR+"/"+name+D_EXT
    if os.path.isfile(filepath) and os.access(filepath, os.W_OK):
        os.remove(filepath)
        return True
    return False
