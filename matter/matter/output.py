# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework Output module}.

    This module contains Entropy (user) Output classes and routines.

"""
from datetime import datetime
import curses
import errno
import os
import sys

from matter.utils import is_python3


stuff = {}
stuff["cols"] = 30
try:
    curses.setupterm()
    stuff["cols"] = curses.tigetnum("cols")
except Exception:
    pass

stuff["cleanline"] = ""

def setcols():
    stuff["cleanline"] = ""
    count = stuff["cols"]
    while count:
        stuff["cleanline"] += " "
        count -= 1
setcols()
stuff["cursor"] = False
stuff["ESC"] = chr(27)

havecolor=1
global dotitles
dotitles=1

esc_seq = "\x1b["

g_attr = {}
g_attr["normal"]       =  0

g_attr["bold"]         =  1
g_attr["faint"]        =  2
g_attr["standout"]     =  3
g_attr["underline"]    =  4
g_attr["blink"]        =  5
g_attr["overline"]     =  6  # Why is overline actually useful?
g_attr["reverse"]      =  7
g_attr["invisible"]    =  8

g_attr["no-attr"]      = 22
g_attr["no-standout"]  = 23
g_attr["no-underline"] = 24
g_attr["no-blink"]     = 25
g_attr["no-overline"]  = 26
g_attr["no-reverse"]   = 27
# 28 isn't defined?
# 29 isn't defined?
g_attr["black"]        = 30
g_attr["red"]          = 31
g_attr["green"]        = 32
g_attr["yellow"]       = 33
g_attr["blue"]         = 34
g_attr["magenta"]      = 35
g_attr["cyan"]         = 36
g_attr["white"]        = 37
# 38 isn't defined?
g_attr["default"]      = 39
g_attr["bg_black"]     = 40
g_attr["bg_red"]       = 41
g_attr["bg_green"]     = 42
g_attr["bg_yellow"]    = 43
g_attr["bg_blue"]      = 44
g_attr["bg_magenta"]   = 45
g_attr["bg_cyan"]      = 46
g_attr["bg_white"]     = 47
g_attr["bg_default"]   = 49


# make_seq("blue", "black", "normal")
def color(fg, bg="default", attr=["normal"]):
        mystr = esc_seq[:] + "%02d" % g_attr[fg]
        for x in [bg]+attr:
                mystr += ";%02d" % g_attr[x]
        return mystr+"m"


codes = {}
codes["reset"]     = esc_seq + "39;49;00m"

codes["bold"]      = esc_seq + "01m"
codes["faint"]     = esc_seq + "02m"
codes["standout"]  = esc_seq + "03m"
codes["underline"] = esc_seq + "04m"
codes["blink"]     = esc_seq + "05m"
codes["overline"]  = esc_seq + "06m"  # Who made this up? Seriously.

ansi_color_codes = []
for x in range(30, 38):
        ansi_color_codes.append("%im" % x)
        ansi_color_codes.append("%i;01m" % x)

rgb_ansi_colors = ["0x000000", "0x555555", "0xAA0000", "0xFF5555", "0x00AA00",
        "0x55FF55", "0xAA5500", "0xFFFF55", "0x0000AA", "0x5555FF", "0xAA00AA",
        "0xFF55FF", "0x00AAAA", "0x55FFFF", "0xAAAAAA", "0xFFFFFF"]

for x in range(len(rgb_ansi_colors)):
        codes[rgb_ansi_colors[x]] = esc_seq + ansi_color_codes[x]

codes["black"]     = codes["0x000000"]
codes["darkgray"]  = codes["0x555555"]

codes["red"]       = codes["0xFF5555"]
codes["darkred"]   = codes["0xAA0000"]

codes["green"]     = codes["0x55FF55"]
codes["darkgreen"] = codes["0x00AA00"]

codes["yellow"]    = codes["0xFFFF55"]
codes["brown"]     = codes["0xAA5500"]

codes["blue"]      = codes["0x5555FF"]
codes["darkblue"]  = codes["0x0000AA"]

codes["fuchsia"]   = codes["0xFF55FF"]
codes["purple"]    = codes["0xAA00AA"]

codes["turquoise"] = codes["0x55FFFF"]
codes["teal"]      = codes["0x00AAAA"]

codes["white"]     = codes["0xFFFFFF"]
codes["lightgray"] = codes["0xAAAAAA"]

codes["darkteal"]   = codes["turquoise"]
codes["darkyellow"] = codes["brown"]
codes["fuscia"]     = codes["fuchsia"]
codes["white"]      = codes["bold"]


def is_stdout_a_tty():
    """
    Return whether current stdout is a TTY.

    @return: tty? => True
    @rtype: bool
    """
    # Paster LazyWriter (Pyramid/Pylons)
    if not hasattr(sys.stdout, "fileno"):
        return False
    fn = sys.stdout.fileno()
    return os.isatty(fn)

def nocolor():
    """
    Turn off colorization process-wide.
    """
    os.environ["MATTER_NO_COLOR"] = "1"
    global havecolor
    havecolor=0

def getcolor():
    """
    Return color status
    """
    return havecolor

nc = os.getenv("MATTER_NO_COLOR")
if nc:
    nocolor()

def _reset_color():
    """
    Reset terminal color currently set.
    """
    return codes["reset"]

def colorize(color_key, text):
    """
    Colorize text with given color key using bash/terminal codes.

    @param color_key: color identifier available in entropy.output.codes
    @type color_key: string
    @return: coloured text
    @rtype: string
    """
    global havecolor
    if havecolor:
        return codes[color_key] + text + codes["reset"]
    return text

def bold(text):
    """
    Make text bold using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("bold", text)

def white(text):
    """
    Make text white using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("white", text)

def teal(text):
    """
    Make text teal using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("teal", text)

def turquoise(text):
    """
    Make text turquoise using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("turquoise", text)

def darkteal(text):
    """
    Make text darkteal using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("darkteal", text)

def purple(text):
    """
    Make text purple using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("purple", text)

def blue(text):
    """
    Make text blue using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("blue", text)

def darkblue(text):
    """
    Make text darkblue using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("darkblue", text)

def green(text):
    """
    Make text green using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("green", text)

def darkgreen(text):
    """
    Make text darkgreen using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("darkgreen", text)

def yellow(text):
    """
    Make text yellow using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("yellow", text)

def brown(text):
    """
    Make text brown using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("brown", text)

def darkyellow(text):
    """
    Make text darkyellow using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("darkyellow", text)

def red(text):
    """
    Make text red using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("red", text)

def darkred(text):
    """
    Make text darkred using bash/terminal codes.

    @param text: text to colorize
    @type text: string
    @return: colorized text
    @rtype: string
    """
    return colorize("darkred", text)

def reset_cursor():
    """
    Print to stdout the terminal code to push back cursor at the beginning
    of the line.
    """
    if havecolor:
        sys.stdout.write(stuff["ESC"] + "[2K")
    _flush_stdouterr()

def _flush_stdouterr():
    for obj in (sys.stdout, sys.stderr,):
        try:
            obj.flush()
        except IOError:
            continue

def _std_write(msg, stderr = False):
    obj = sys.stdout
    if stderr:
        obj = sys.stderr

    try:
        obj.write(msg)
    except UnicodeEncodeError:
        msg = msg.encode("utf-8")
        if is_python3():
            obj.buffer.write(msg)
        else:
            obj.write(msg)

def _print_prio(msg, color_func, back = False, flush = True, end = "\n",
    stderr = False):
    if not back:
        setcols()
    reset_cursor()
    is_tty = is_stdout_a_tty()
    t = datetime.now()
    time_str = t.strftime("%Y-%m-%d %H:%M:%S")
    if is_tty:
        writechar("\r", stderr = stderr)
    msg = "%s %s %s" % (color_func(">>"), time_str, msg)
    if not back:
        msg += end

    _std_write(msg, stderr = stderr)
    if back and (not is_tty):
        # in this way files are properly written
        writechar("\n", stderr = stderr)
    if flush:
        _flush_stdouterr()

def print_error(msg, back = False, flush = True, end = "\n"):
    """
    Service function used by Entropy text client (will be moved from here)
    to write error messages to stdout (not stderr, atm).
    NOTE: don't use this directly but rather subclass TextInterface class.

    @param msg: text message to print
    @type msg: string
    @keyword back: move text cursor back to the beginning of the line
    @type back: bool
    @keyword flush: flush stdout and stderr
    @type flush: bool
    @return: None
    @rtype: None
    """
    return _print_prio(msg, darkred, back = back, flush = flush, end = end, 
        stderr = True)

def print_info(msg, back = False, flush = True, end = "\n"):
    """
    Service function used by Entropy text client (will be moved from here)
    to write info messages to stdout (not stderr, atm).
    NOTE: don't use this directly but rather subclass TextInterface class.

    @param msg: text message to print
    @type msg: string
    @keyword back: move text cursor back to the beginning of the line
    @type back: bool
    @keyword flush: flush stdout and stderr
    @type flush: bool
    @return: None
    @rtype: None
    """
    return _print_prio(msg, darkgreen, back = back, flush = flush, end = end)

def print_warning(msg, back = False, flush = True, end = "\n"):
    """
    Service function used by Entropy text client (will be moved from here)
    to write warning messages to stdout (not stderr, atm).
    NOTE: don't use this directly but rather subclass TextInterface class.

    @param msg: text message to print
    @type msg: string
    @keyword back: move text cursor back to the beginning of the line
    @type back: bool
    @keyword flush: flush stdout and stderr
    @type flush: bool
    @return: None
    @rtype: None
    """
    return _print_prio(msg, brown, back = back, flush = flush, end = end,
        stderr = True)

def print_generic(*args, **kwargs):
    """
    Service function used by Entropy text client (will be moved from here)
    to write generic messages to stdout (not stderr, atm).
    NOTE: don't use this directly but rather subclass TextInterface class.
    """
    stderr = kwargs.get("stderr", False)
    msg_idx = 1
    for msg in args:
        _std_write(msg, stderr = stderr)
        if len(args) != msg_idx:
            sys.stdout.write(" ")
        msg_idx += 1

    end = kwargs.get("end", "\n")
    _std_write(end, stderr = stderr)
    _flush_stdouterr()

def writechar(chars, stderr = False):
    """
    Write characters to stdout (will be moved from here).

    @param chars: chars to write
    @type chars: string
    """
    obj = sys.stdout
    if stderr:
        obj = sys.stderr
    try:
        obj.write(chars)
        obj.flush()
    except IOError as e:
        if e.errno == errno.EPIPE:
            return
        raise
