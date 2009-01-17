#!/usr/bin/python
'''
    # DESCRIPTION:
    # load/save a data to file by dumping its structure

    Copyright (C) 2007-2008 Fabio Erculiani

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
'''
from __future__ import with_statement
from entropyConstants import *
try:
    import cPickle as pickle
except ImportError:
    import pickle

d_ext = etpConst['cachedumpext']
d_dir = etpConst['dumpstoragedir']
e_gid = etpConst['entropygid']
if e_gid == None: e_gid = 0

'''
   @description: dump object to file
   @input: name of the object, object
   @output: status code
'''

def dumpobj(name, object, completePath = False, ignoreExceptions = True):
    while 1: # trap ctrl+C
        try:
            if completePath:
                dmpfile = name
            else:
                dump_path = os.path.join(d_dir,name)
                dump_dir = os.path.dirname(dump_path)
                #dump_name = os.path.basename(dump_path)
                if not os.path.isdir(dump_dir):
                    os.makedirs(dump_dir,0775)
                    const_setup_perms(dump_dir,e_gid)
                dmpfile = dump_path+d_ext
            with open(dmpfile,"wb") as f:
                pickle.dump(object,f)
                f.flush()
            const_setup_file(dmpfile, e_gid, 0664)
        except RuntimeError:
            try: os.remove(dmpfile)
            except OSError: pass
        except (EOFError,IOError,OSError):
            if not ignoreExceptions:
                raise
        break

'''
   @description: serialize object to f (file)
   @input: object, file object
   @output: file object, pointer to the beginning
'''
def serialize(myobj, f, do_seek = True):
    pickle.dump(myobj,f)
    f.flush()
    if do_seek:
        f.seek(0)
    return f

'''
   @description: unserialize file to object (file)
   @input: file object
   @output: object
'''
def unserialize(f):
    x = pickle.load(f)
    return x

'''
   @description: unserialize pickle string to object
   @input: string
   @output: object
'''
def unserialize_string(mystring):
    x = pickle.loads(mystring)
    return x

'''
   @description: serialize object to string
   @input: object, file object
   @output: file object, pointer to the beginning
'''
def serialize_string(myobj):
    return pickle.dumps(myobj)

'''
   @description: load object from a file
   @input: name of the object
   @output: object or, if error -1
'''
def loadobj(name, completePath = False):
    while 1:
        if completePath:
            dmpfile = name
        else:
            dump_path = os.path.join(d_dir,name)
            #dump_dir = os.path.dirname(dump_path)
            #dump_name = os.path.basename(dump_path)
            dmpfile = dump_path+d_ext
        if os.path.isfile(dmpfile) and os.access(dmpfile,os.R_OK):
            try:
                with open(dmpfile,"rb") as f:
                    x = None
                    try:
                        x = pickle.load(f)
                    except (ValueError,EOFError,IOError,OSError,pickle.UnpicklingError):
                        pass
                    return x
            except (IOError,OSError,):
                pass
        break

def getobjmtime(name):
    mtime = 0
    dump_path = os.path.join(d_dir,name+d_ext)
    if os.path.isfile(dump_path) and os.access(dump_path,os.R_OK):
        mtime = os.path.getmtime(dump_path)
    return int(mtime)

def removeobj(name):
    if os.path.isfile(d_dir+"/"+name+d_ext):
        try:
            os.remove(d_dir+"/"+name+d_ext)
        except OSError:
            pass