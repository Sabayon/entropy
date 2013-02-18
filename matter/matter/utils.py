# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

"""
import errno
import os
import sys
import tempfile
import traceback


MATTER_TMPDIR = os.getenv("MATTER_TMPDIR", "/var/tmp/matter")
_ENCODING = "UTF-8"
_RAW_ENCODING = "raw_unicode_escape"


def print_traceback(f = None):
    """
    Prints a simple Pythonic traceback.

    @keyword f: write to f (file) object instead of stdout
    @type f: valid file handle
    """
    traceback.print_exc(file = f)


def print_exception(silent=False, tb_data=None, all_frame_data=False):
    """
    Print last Python exception and frame variables values (if available)
    to stdout.

    @keyword silent: do not print to stdout
    @type silent: bool
    @keyword tb_data: Python traceback object
    @type tb_data: Python traceback instance
    @keyword all_frame_data: print all variables in every frame
    @type all_frame_data: bool
    @return: exception data
    @rtype: list of strings
    """
    if not silent:
        traceback.print_last()
    data = []
    if tb_data is not None:
        tb = tb_data
    else:
        last_type, last_value, last_traceback = sys.exc_info()
        tb = last_traceback

    stack = []
    while True:
        if not tb:
            break
        if not tb.tb_next:
            break
        tb = tb.tb_next
        if all_frame_data:
            stack.append(tb.tb_frame)

    if not all_frame_data:
        stack.append(tb.tb_frame)

    #if not returndata: print
    for frame in stack:
        if not silent:
            sys.stderr.write("\n")
            sys.stderr.write(
                "Frame %s in %s at line %s\n" % (
                    frame.f_code.co_name,
                    frame.f_code.co_filename, frame.f_lineno))
        data.append("Frame %s in %s at line %s\n" % (frame.f_code.co_name,
            frame.f_code.co_filename, frame.f_lineno))

        for key, value in list(frame.f_locals.items()):
            cur_str = ""
            cur_str = "\t%20s = " % key
            try:
                cur_str += repr(value) + "\n"
            except (AttributeError, NameError, TypeError):
                cur_str += "<ERROR WHILE PRINTING VALUE>\n"

            if not silent:
                sys.stdout.write(cur_str)
            data.append(cur_str)

    return data


def mkstemp(prefix=None, suffix=None):
    """
    Create temporary file into matter temporary directory.
    This is a tempfile.mkstemp() wrapper
    """
    if prefix is None:
        prefix = "matter"
    if suffix is None:
        suffix = ""
    tmp_dir = MATTER_TMPDIR
    if not os.path.isdir(tmp_dir):
        try:
            os.makedirs(tmp_dir)
        except OSError as err:
            # race condition
            if err.errno != errno.EEXIST:
                raise
    return tempfile.mkstemp(prefix=prefix,
                            suffix=suffix,
                            dir=tmp_dir)


def mkdtemp(prefix=None, suffix=None):
    """
    Create temporary directory into matter temporary directory.
    This is a tempfile.mkdtemp() wrapper
    """
    if prefix is None:
        prefix = "matter"
    tmp_dir = MATTER_TMPDIR
    if not os.path.isdir(tmp_dir):
        try:
            os.makedirs(tmp_dir)
        except OSError as err:
            # race condition
            if err.errno != errno.EEXIST:
                raise
    return tempfile.mkdtemp(prefix=prefix,
                            suffix=suffix,
                            dir=tmp_dir)


def is_python3():
    """
    Return whether Python3 is interpreting this code.
    """
    return sys.hexversion >= 0x3000000


def get_buffer():
    """
    Return generic buffer object (supporting both Python 2.x and Python 3.x)
    """
    if is_python3():
        return memoryview
    else:
        return buffer


def get_int():
    """
    Return generic int object (supporting both Python 2.x and Python 3.x).
    For Python 2.x a (long, int) tuple is returned.
    For Python 3.x a (int,) tuple is returned.
    """
    if is_python3():
        return (int,)
    else:
        return (long, int,)


def get_stringtype():
    """
    Return generic string type for usage in isinstance().
    On Python 2.x, it returns basestring while on Python 3.x it returns
    (str, bytes,)
    """
    if is_python3():
        return (str, bytes,)
    else:
        return (basestring,)


def is_unicode(obj):
    """
    Return whether obj is a unicode.

    @param obj: Python object
    @type obj: Python object
    @return: True, if object is unicode
    @rtype: bool
    """
    if is_python3():
        return isinstance(obj, str)
    else:
        return isinstance(obj, unicode)


def is_number(obj):
    """
    Return whether obj is an int, long object.
    """
    if is_python3():
        return isinstance(obj, int)
    else:
        return isinstance(obj, (int, long,))


def convert_to_unicode(obj, enctype = _RAW_ENCODING):
    """
    Convert generic string to unicode format, this function supports both
    Python 2.x and Python 3.x unicode bullshit.

    @param obj: generic string object
    @type obj: string
    @return: unicode string object
    @rtype: unicode object
    """

    # None support
    if obj is None:
        if is_python3():
            return "None"
        else:
            return unicode("None")

    # int support
    if isinstance(obj, get_int()):
        if is_python3():
            return str(obj)
        else:
            return unicode(obj)

    # buffer support
    if isinstance(obj, get_buffer()):
        if is_python3():
            return str(obj.tobytes(), enctype)
        else:
            return unicode(obj, enctype)

    # string/unicode support
    if is_unicode(obj):
        return obj
    if hasattr(obj, "decode"):
        return obj.decode(enctype)
    else:
        if is_python3():
            return str(obj, enctype)
        else:
            return unicode(obj, enctype)


def convert_to_rawstring(obj, from_enctype = _RAW_ENCODING):
    """
    Convert generic string to raw string (str for Python 2.x or bytes for
    Python 3.x).

    @param obj: input string
    @type obj: string object
    @keyword from_enctype: encoding which string is using
    @type from_enctype: string
    @return: raw string
    @rtype: bytes
    """
    if obj is None:
        return convert_to_rawstring("None")
    if is_number(obj):
        if is_python3():
            return bytes(str(obj), from_enctype)
        else:
            return str(obj)
    if isinstance(obj, get_buffer()):
        if is_python3():
            return obj.tobytes()
        else:
            return str(obj)
    if not is_unicode(obj):
        return obj
    return obj.encode(from_enctype)
