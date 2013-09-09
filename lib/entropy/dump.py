# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework object disk serializer module}.

    This module contains Entropy Python object serialization functions and
    disk dumpers.

    Serialized objects are stored to disk with proper permissions by default
    into path given by entropy.const's etpConst['dumpstoragedir'].

    Permissions are set using entropy.const's const_setup_perms and
    const_setup_file functions.

    Objects are serialized using Python's cPickle/pickle modules, thus
    they must be "pickable". Please read Python Library reference for
    more information.

"""

import sys
import os
import time

from entropy.const import etpConst, const_setup_file, const_is_python3, \
    const_mkstemp
# Always use MAX pickle protocol to <=2, to allow Python 2 and 3 support
COMPAT_PICKLE_PROTOCOL = 0

if const_is_python3():
    import pickle
else:
    try:
        import cPickle as pickle
    except ImportError:
        import pickle

pickle.HIGHEST_PROTOCOL = COMPAT_PICKLE_PROTOCOL
pickle.DEFAULT_PROTOCOL = COMPAT_PICKLE_PROTOCOL

D_EXT = etpConst['cachedumpext']
D_DIR = etpConst['dumpstoragedir']
E_GID = etpConst['entropygid']
if E_GID == None:
    E_GID = 0


def dumpobj(name, my_object, complete_path = False, ignore_exceptions = True,
    dump_dir = None, custom_permissions = None):
    """
    Dump pickable object to file

    @param name: name of the object
    @type name: string
    @param my_object: object to dump
    @type my_object: any Python "pickable" object
    @keyword complete_path: consider "name" argument as
        a complete path (this overrides the default dump
        path given by etpConst['dumpstoragedir'])
    @type complete_path: bool
    @keyword ignore_exceptions: ignore any possible exception
        (EOFError, IOError, OSError,)
    @type ignore_exceptions: bool
    @keyword dump_dir: alternative dump directory
    @type dump_dir: string
    @keyword custom_permissions: give custom permission bits
    @type custom_permissions: octal
    @return: None
    @rtype: None
    @raise EOFError: could be caused by pickle.dump, ignored if
        ignore_exceptions is True
    @raise IOError: could be caused by pickle.dump, ignored if
        ignore_exceptions is True
    @raise OSError: could be caused by pickle.dump, ignored if
        ignore_exceptions is True
    """
    if dump_dir is None:
        dump_dir = D_DIR
    if custom_permissions is None:
        custom_permissions = 0o664

    while True: # trap ctrl+C
        tmp_fd, tmp_dmpfile = None, None
        try:
            if complete_path:
                dmpfile = name
                c_dump_dir = os.path.dirname(name)
            else:
                _dmp_path = os.path.join(dump_dir, name)
                dmpfile = _dmp_path+D_EXT
                c_dump_dir = os.path.dirname(_dmp_path)

            my_dump_dir = c_dump_dir
            d_paths = []
            while not os.path.isdir(my_dump_dir):
                d_paths.append(my_dump_dir)
                my_dump_dir = os.path.dirname(my_dump_dir)
            if d_paths:
                d_paths = sorted(d_paths)
                for d_path in d_paths:
                    os.mkdir(d_path)
                    const_setup_file(d_path, E_GID, 0o775)

            dmp_name = os.path.basename(dmpfile)
            tmp_fd, tmp_dmpfile = const_mkstemp(
                dir=c_dump_dir, prefix=dmp_name)
            # WARNING: it has been observed that using
            # os.fdopen() below in multi-threaded scenarios
            # is causing EBADF. There is probably a race
            # condition down in the stack.
            with open(tmp_dmpfile, "wb") as dmp_f:
                if const_is_python3():
                    pickle.dump(my_object, dmp_f,
                        protocol = COMPAT_PICKLE_PROTOCOL, fix_imports = True)
                else:
                    pickle.dump(my_object, dmp_f)

            const_setup_file(tmp_dmpfile, E_GID, custom_permissions)
            os.rename(tmp_dmpfile, dmpfile)

        except RuntimeError:
            try:
                os.remove(dmpfile)
            except OSError:
                pass
        except (EOFError, IOError, OSError):
            if not ignore_exceptions:
                raise
        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except (IOError, OSError):
                    pass
            if tmp_dmpfile is not None:
                try:
                    os.remove(tmp_dmpfile)
                except (IOError, OSError):
                    pass
        break

def serialize(myobj, ser_f, do_seek = True):
    """
    Serialize object to ser_f (file)

    @param myobj: Python object to serialize
    @type myobj: any Python picklable object
    @param ser_f: file object to write to
    @type ser_f: file object
    @keyword do_seek: move file cursor back to the beginning
        of ser_f
    @type do_seek: bool
    @return: file object where data has been written
    @rtype: file object
    @raise RuntimeError: caused by pickle.dump in case of
        system errors
    @raise EOFError: caused by pickle.dump in case of
        race conditions on multi-processing or multi-threading
    @raise IOError: caused by pickle.dump in case of
        race conditions on multi-processing or multi-threading
    @raise pickle.PicklingError: when object cannot be recreated
    """
    if const_is_python3():
        pickle.dump(myobj, ser_f, protocol = COMPAT_PICKLE_PROTOCOL,
            fix_imports = True)
    else:
        pickle.dump(myobj, ser_f)
    ser_f.flush()
    if do_seek:
        ser_f.seek(0)
    return ser_f

def unserialize(serial_f):
    """
    Unserialize file to object (file)

    @param serial_f: file object which data will be read from
    @type serial_f: file object
    @return: rebuilt object
    @rtype: any Python pickable object
    @raise pickle.UnpicklingError: when object cannot be recreated
    """
    if const_is_python3():
        return pickle.load(serial_f, fix_imports = True,
            encoding = etpConst['conf_raw_encoding'])
    else:
        return pickle.load(serial_f)

def unserialize_string(mystring):
    """
    Unserialize pickle string to object

    @param mystring: data stream in string form to reconstruct
    @type mystring: string
    @return: reconstructed object
    @rtype: any Python pickable object
    @raise pickle.UnpicklingError: when object cannot be recreated
    """
    if const_is_python3():
        return pickle.loads(mystring, fix_imports = True,
            encoding = etpConst['conf_raw_encoding'])
    else:
        return pickle.loads(mystring)

def serialize_string(myobj):
    """
    Serialize object to string

    @param myobj: object to serialize
    @type myobj: any Python picklable object
    @return: serialized string
    @rtype: string
    @raise pickle.PicklingError: when object cannot be recreated
    """
    if const_is_python3():
        return pickle.dumps(myobj, protocol = COMPAT_PICKLE_PROTOCOL,
            fix_imports = True, encoding = etpConst['conf_raw_encoding'])
    else:
        return pickle.dumps(myobj)

def loadobj(name, complete_path = False, dump_dir = None, aging_days = None):
    """
    Load object from a file
    @param name: name of the object to load
    @type name: string
    @keyword complete_path: determine whether name argument
        is a complete disk path to serialized object
    @type complete_path: bool
    @keyword dump_dir: alternative dump directory
    @type dump_dir: string
    @keyword aging_days: if int, consider the cached file invalid
        if older than aging_days.
    @type aging_days: int
    @return: object or None
    @rtype: any Python pickable object or None
    """
    if dump_dir is None:
        dump_dir = D_DIR

    while True:
        if complete_path:
            dmpfile = name
        else:
            dump_path = os.path.join(dump_dir, name)
            dmpfile = dump_path + D_EXT

        if aging_days is not None:
            cur_t = time.time()
            try:
                mtime = os.path.getmtime(dmpfile)
            except (IOError, OSError):
                mtime = 0.0
            if abs(cur_t - mtime) > (aging_days * 86400):
                # do not unlink since other consumers might
                # have different aging settings.
                #try:
                #    os.remove(dmpfile)
                #except (OSError, IOError):
                #    # did my best
                #    pass
                return None

        try:
            with open(dmpfile, "rb") as dmp_f:
                obj = None
                try:
                    if const_is_python3():
                        obj = pickle.load(dmp_f, fix_imports = True,
                            encoding = etpConst['conf_raw_encoding'])
                    else:
                        obj = pickle.load(dmp_f)
                except (ValueError, EOFError, IOError,
                    OSError, pickle.UnpicklingError, TypeError,
                    AttributeError, ImportError, SystemError,):
                    pass
                return obj
        except (IOError, OSError,):
            pass
        break

def getobjmtime(name, dump_dir = None):
    """
    Get dumped object mtime

    @param name: object name
    @type name: string
    @keyword dump_dir: alternative dump directory
    @type dump_dir: string
    @return: mtime of the file containing the serialized object or 0
        if not found
    @rtype: int
    """
    if dump_dir is None:
        dump_dir = D_DIR
    mtime = 0
    dump_path = os.path.join(dump_dir, name+D_EXT)
    try:
        mtime = os.path.getmtime(dump_path)
    except (IOError, OSError):
        mtime = 0
    return int(mtime)

def removeobj(name, dump_dir = None):
    """
    Remove cached object referenced by its object name

    @param name: object name
    @type name: string
    @keyword dump_dir: alternative dump directory
    @type dump_dir: string
    @return: bool representing whether object has been
        removed or not
    @rtype: bool
    @raise OSError: in case of troubles with os.remove()
    """
    if dump_dir is None:
        dump_dir = D_DIR
    filepath = dump_dir + os.path.sep + name + D_EXT
    try:
        os.remove(filepath)
        return True
    except (OSError, IOError) as err:
        if err.errno not in (errno.ENOENT, errno.ENOTDIR):
            raise
        return False
