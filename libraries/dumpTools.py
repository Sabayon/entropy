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
from entropyConstants import *
try:
    import cPickle as pickle
except ImportError:
    import pickle

'''
   @description: dump object to file
   @input: name of the object, object
   @output: status code
'''
def dumpobj(name, object, completePath = False):
    while 1: # trap ctrl+C
        if completePath:
            dmpfile = name
        else:
            dump_path = os.path.join(etpConst['dumpstoragedir'],name)
            dump_dir = os.path.dirname(dump_path)
            #dump_name = os.path.basename(dump_path)
            if not os.path.isdir(dump_dir):
                os.makedirs(dump_dir)
            dmpfile = dump_path+".dmp"
        f = open(dmpfile,"wb")
        pickle.dump(object,f)
        f.flush()
        f.close()
        break


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
            dump_path = os.path.join(etpConst['dumpstoragedir'],name)
            #dump_dir = os.path.dirname(dump_path)
            #dump_name = os.path.basename(dump_path)
            dmpfile = dump_path+".dmp"
        if os.path.isfile(dmpfile) and os.access(dmpfile,os.R_OK):
            f = open(dmpfile,"rb")
            x = None
            try:
                x = pickle.load(f)
            except pickle.UnpicklingError, ValueError:
                pass
            f.close()
            return x
        break

def removeobj(name):
    if os.path.isfile(etpConst['dumpstoragedir']+"/"+name+".dmp"):
        try:
            os.remove(etpConst['dumpstoragedir']+"/"+name+".dmp")
        except OSError:
            pass