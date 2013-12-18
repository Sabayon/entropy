# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework Output module}.

    This module contains Entropy (user) Output classes and routines.

"""
import os
import sys
import errno
import curses
import subprocess
import threading

from entropy.const import const_convert_to_rawstring, \
    const_isstring, const_convert_to_unicode, const_isunicode, \
    const_is_python3
from entropy.i18n import _

stuff = {}
stuff['cols'] = 30
try:
    curses.setupterm()
    stuff['cols'] = curses.tigetnum('cols')
except:
    pass
stuff['cleanline'] = ""
def setcols():
    stuff['cleanline'] = ""
    count = stuff['cols']
    while count:
        stuff['cleanline'] += ' '
        count -= 1
setcols()
stuff['cursor'] = False
stuff['ESC'] = chr(27)

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

rgb_ansi_colors = ['0x000000', '0x555555', '0xAA0000', '0xFF5555', '0x00AA00',
        '0x55FF55', '0xAA5500', '0xFFFF55', '0x0000AA', '0x5555FF', '0xAA00AA',
        '0xFF55FF', '0x00AAAA', '0x55FFFF', '0xAAAAAA', '0xFFFFFF']

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


# mute flag, will mute any stdout/stderr output.
_MUTE = os.getenv("ETP_MUTE") is not None
# interactive flag, this will go away at some point in future
_INTERACTIVE = os.getenv("ETP_NONINTERACTIVE") is None

def is_mute():
    """
    Return whether writing to stderr/stdout is allowed.

    @return: mute status
    @rtype: bool
    """
    return _MUTE

def set_mute(status):
    """
    Set mute status.

    @param status: new mute status
    @type status: bool
    """
    global _MUTE
    _MUTE = bool(status)

def is_interactive():
    """
    Return whether interactive mode is enabled.

    @return: True, if interactive is enabled
    @rtype: bool
    """
    return _INTERACTIVE

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

def xterm_title(mystr, raw = False):
    """
    Set new xterm title.

    @param mystr: new xterm title
    @type mystr: string
    @keyword raw: write title in raw mode
    @type raw: bool
    """
    if dotitles and "TERM" in os.environ and sys.stderr.isatty():
        myt = os.environ["TERM"]
        legal_terms = ("xterm", "Eterm", "aterm", "rxvt", "screen",
            "kterm", "rxvt-unicode", "gnome")
        if myt in legal_terms:
            if not raw:
                mystr = "\x1b]0;%s\x07" % mystr
            try:
                sys.stderr.write(mystr)
            except UnicodeEncodeError:
                sys.stderr.write(mystr.encode('utf-8'))
            sys.stderr.flush()

default_xterm_title = None

def xterm_title_reset():
    """
    Reset xterm title to default.
    """
    global default_xterm_title
    if default_xterm_title is None:
        prompt_command = os.getenv('PROMPT_COMMAND')
        if not prompt_command:
            default_xterm_title = ""
        elif prompt_command is not None:
            from entropy.tools import getstatusoutput
            default_xterm_title = getstatusoutput(prompt_command)[1]
        else:
            pwd = os.getenv('PWD', '')
            home = os.getenv('HOME', '')
            if home != '' and pwd.startswith(home):
                pwd = '~' + pwd[len(home):]
            default_xterm_title = '\x1b]0;%s@%s:%s\x07' % (
                os.getenv('LOGNAME', ''),
                os.getenv('HOSTNAME', '').split('.', 1)[0],
                pwd)
    xterm_title(default_xterm_title, raw = True)

def notitles():
    """
    Turn off title setting. In this way, xterm title won't be touched.
    """
    global dotitles
    dotitles=0

def nocolor():
    """
    Turn off colorization process-wide.
    """
    os.environ['ETP_NO_COLOR'] = "1"
    global havecolor
    havecolor=0

def getcolor():
    """
    Return color status
    """
    return havecolor

nc = os.getenv("ETP_NO_COLOR")
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
    if is_mute():
        return text
    global havecolor
    if havecolor:
        return codes[color_key] + text + codes["reset"]
    return text

def decolorize(text):
    my_esc_seq = "\x1b"
    new_text = ''
    append = True
    for char in text:
        if char == my_esc_seq:
            append = False
            continue
        elif char == "m" and not append:
            append = True
            continue
        if append:
            new_text += char
    return new_text

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
        sys.stdout.write(stuff['ESC'] + '[2K')
    _flush_stdouterr()

def _flush_stdouterr():
    for obj in (sys.stdout, sys.stderr,):
        try:
            obj.flush()
        except IOError:
            continue

def _std_write(msg, stderr = False):
    if not const_isstring(msg):
        msg = repr(msg)
    obj = sys.stdout
    if stderr:
        obj = sys.stderr

    try:
        obj.write(msg)
    except UnicodeEncodeError:
        msg = msg.encode('utf-8')
        if const_is_python3():
            obj.buffer.write(msg)
        else:
            obj.write(msg)

MESSAGE_HEADER = const_convert_to_unicode("\u2560 ") # ╠
ERROR_MESSAGE_HEADER = const_convert_to_unicode("\u2622 ") # ☢
WARNING_MESSAGE_HEADER = const_convert_to_unicode("\u261B ") # ☛

def _print_prio(msg, color_func, back = False, flush = True, end = '\n',
                stderr = False, msg_header = None):
    if is_mute():
        return
    if not back:
        setcols()
    reset_cursor()
    is_tty = is_stdout_a_tty()
    if is_tty:
        writechar("\r", stderr = stderr)

    if msg_header is None:
        msg_header = MESSAGE_HEADER
    header = color_func(msg_header)

    _std_write(header, stderr = stderr)
    _std_write(msg, stderr = stderr)
    if not back:
        _std_write(end, stderr = stderr)

    if back and (not is_tty):
        # in this way files are properly written
        writechar("\n", stderr = stderr)
    if flush:
        _flush_stdouterr()

def print_error(msg, back = False, flush = True, end = '\n'):
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
                       stderr = True, msg_header = ERROR_MESSAGE_HEADER)

def print_info(msg, back = False, flush = True, end = '\n'):
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

def print_warning(msg, back = False, flush = True, end = '\n'):
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
                       stderr = True, msg_header = WARNING_MESSAGE_HEADER)

def print_generic(*args, **kwargs):
    """
    Service function used by Entropy text client (will be moved from here)
    to write generic messages to stdout (not stderr, atm).
    NOTE: don't use this directly but rather subclass TextInterface class.
    """
    if is_mute():
        return

    stderr = kwargs.get('stderr', False)
    msg_idx = 1
    for msg in args:
        _std_write(msg, stderr = stderr)
        if len(args) != msg_idx:
            sys.stdout.write(" ")
        msg_idx += 1

    end = kwargs.get('end', '\n')
    _std_write(end, stderr = stderr)
    _flush_stdouterr()

def writechar(chars, stderr = False):
    """
    Write characters to stdout (will be moved from here).

    @param chars: chars to write
    @type chars: string
    """
    if is_mute():
        return
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

def readtext(request, password = False):
    """
    Read text from stdin and return it (will be moved from here).

    @param request: textual request to print
    @type request: string
    @keyword password: if you are requesting a password, set this to True
    @type password: bool
    @return: text read back from stdin
    @rtype: string
    @raise EOFError: if CTRL+D is pressed
    """
    xterm_title(_("Entropy needs your attention"))
    if password:
        from getpass import getpass
        try:
            text = getpass(request+" ")
        except UnicodeEncodeError:
            text = getpass(request.encode('utf-8')+" ")
    else:
        try:
            sys.stdout.write(request)
        except UnicodeEncodeError:
            sys.stdout.write(request.encode('utf-8'))
        _flush_stdouterr()
        text = _my_raw_input()
    return text

def _my_raw_input(txt = ''):
    try:
        import readline
    except ImportError:
        # not available? ignore
        pass

    if not txt:
        txt = ""
    if const_is_python3():
        try:
            response = input(darkgreen(txt))
        except UnicodeEncodeError:
            response = input(darkgreen(txt.encode('utf-8')))
    else:
        try:
            response = raw_input(darkgreen(txt))
        except UnicodeEncodeError:
            response = raw_input(darkgreen(txt.encode('utf-8')))
    _flush_stdouterr()

    # try to convert to unicode, because responses are stored that
    # way, fix bug #2006.
    if not const_isunicode(response):
        try:
            response = const_convert_to_unicode(response, enctype = "utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            # be fault tolerant, we just tried
            pass
    return response

class TextInterface(object):

    """
    TextInterface is a base class for handling the communication between
    user and Entropy-based applications.

    This class works for text-based applications, it must be inherited
    from subclasses and its methods reimplemented to make Entropy working
    on situations where a terminal is not used as UI (Graphical applications,
    web-based interfaces, remote interfaces, etc).

    Every part of Entropy is using the methods in this class to communicate
    with the user, channel is bi-directional.
    """

    OUTPUT_LOCK = threading.RLock()

    @classmethod
    def output(cls, text, header = "", footer = "", back = False,
        importance = 0, level = "info", count = None, percent = False):

        """
        Text output print function. By default text is written to stdout.

        @param text: text to write to stdout
        @type text: string
        @keyword header: text header (decoration?)
        @type header: string
        @keyword footer: text footer (decoration?)
        @type footer: string
        @keyword back: push back cursor to the beginning of the line
        @type back: bool
        @keyword importance: message importance (default valid values:
            0, 1, 2, 3
        @type importance: int
        @keyword level: message type (default valid values: "info", "warning",
            "error", "generic")
        @type level: string
        @keyword count: tuple of lengh 2, containing count information to make
            function print something like "(10/100) doing stuff". In this case
            tuple would be: (10, 100,)
        @type count: tuple
        @keyword percent: determine whether "count" argument should be printed
            as percentual value (for values like (10, 100,), "(10%) doing stuff"
            will be printed.
        @keyword percent: bool
        @return: None
        @rtype: None
        """

        if is_mute():
            return

        _flush_stdouterr()

        myfunc = print_info
        if level == "warning":
            myfunc = print_warning
        elif level == "error":
            myfunc = print_error
        elif level == "generic":
            myfunc = print_generic

        count_str = ""
        if count:
            if len(count) > 1:
                if percent:
                    percent_str = str(round((float(count[0])/count[1])*100, 1))
                    count_str = " ("+percent_str+"%) "
                else:
                    count_str = " (%s/%s) " % (red(str(count[0])),
                        blue(str(count[1])),)

        with TextInterface.OUTPUT_LOCK:
            myfunc(header+count_str+text+footer, back = back, flush = False)
            _flush_stdouterr()

    @classmethod
    def ask_question(cls, question, importance = 0, responses = None):

        """
        Questions asking function. It asks the user to answer the question given
        by choosing between a preset list of answers given by the "reposonses"
        argument.

        @param question: question text
        @type question: string
        @keyword importance: question importance (no default valid values)
        @type importance: int
        @keyword responses: list of valid answers which user has to choose from
        @type responses: tuple or list
        @return: None
        @rtype: None
        """

        if responses is None:
            responses = (_("Yes"), _("No"),)

        colours = [green, red, blue, darkgreen, darkred, darkblue,
            brown, purple]
        colours_len = len(colours)

        try:
            sys.stdout.write(question + " ")
        except UnicodeEncodeError:
            sys.stdout.write(question.encode('utf-8') + " ")
        _flush_stdouterr()

        try:
            while True:

                xterm_title(_("Entropy got a question for you"))
                _flush_stdouterr()
                answer_items = [colours[x % colours_len](responses[x]) \
                    for x in range(len(responses))]
                response = _my_raw_input("["+"/".join(answer_items)+"] ")
                _flush_stdouterr()

                for key in responses:
                    if response.upper() == key[:len(response)].upper():
                        xterm_title_reset()
                        return key
                    _flush_stdouterr()

        except (EOFError, KeyboardInterrupt):
            msg = "%s.\n" % (_("Interrupted"),)
            try:
                sys.stdout.write(msg)
            except UnicodeEncodeError:
                sys.stdout.write(msg.encode("utf-8"))
            xterm_title_reset()
            raise KeyboardInterrupt()

        xterm_title_reset()
        _flush_stdouterr()

    @classmethod
    def input_box(cls, title, input_parameters, cancel_button = True):
        """
        Generic input box (form) creator and data collector.

        @param title: input box title
        @type title: string
        @param input_parameters: list of properly formatted tuple items.
        @type input_parameters: list
        @keyword cancel_button: make possible to "cancel" the input request.
        @type cancel_button: bool
        @return: dict containing input box answers
        @rtype: dict

        input_parameters supported items:

        [input id], [input text title], [input verification callback], [
            no text echo?]
        ('identifier 1', 'input text 1', input_verification_callback, False)

        ('item_3', ('checkbox', 'Checkbox option (boolean request) - please choose',),
            input_verification_callback, True)

        ('item_4', ('combo', ('Select your favorite option', ['option 1', 'option 2', 'option 3']),),
            input_verification_callback, True)

        ('item_4',('list',('Setup your list',['default list item 1', 'default list item 2']),),
            input_verification_callback, True)

        """
        results = {}
        if title:
            try:
                sys.stdout.write(title + "\n")
            except UnicodeEncodeError:
                sys.stdout.write(title.encode('utf-8') + "\n")
        _flush_stdouterr()

        def option_chooser(option_data):
            mydict = {}
            counter = 1
            option_text, option_list = option_data
            cls.output(option_text)
            for item in option_list:
                mydict[counter] = item
                txt = "[%s] %s" % (darkgreen(str(counter)), blue(item),)
                cls.output(txt)
                counter += 1
            while True:
                try:
                    if const_is_python3():
                        myresult = const_convert_to_unicode(
                            readtext("%s: " % (_('Selected number'),)),
                            enctype = "utf-8")
                    else:
                        myresult = readtext(
                            "%s: " % (_('Selected number'),)).decode('utf-8')
                except UnicodeDecodeError:
                    continue
                except UnicodeEncodeError:
                    continue
                try:
                    myresult = int(myresult)
                except ValueError:
                    continue
                selected = mydict.get(myresult)
                if selected != None:
                    return myresult, selected

        def list_editor(option_data, can_cancel, callback):

            def selaction():
                cls.output('')
                cls.output(darkred(_("Please select an option")))
                if can_cancel:
                    cls.output("  ("+blue("-1")+") "+darkred(_("Discard all")))
                cls.output("  ("+blue("0")+")  "+darkgreen(_("Confirm")))
                cls.output("  ("+blue("1")+")  "+brown(_("Add item")))
                cls.output("  ("+blue("2")+")  "+brown(_("Edit item")))
                cls.output("  ("+blue("3")+")  "+darkblue(_("Remove item")))
                cls.output("  ("+blue("4")+")  "+darkgreen(_("Show current list")))
                # wait user interaction
                cls.output('')
                try:
                    action = readtext(darkgreen(_("Your choice (type a number and press enter):"))+" ")
                except UnicodeDecodeError:
                    return ''
                return action

            mydict = {}
            counter = 1
            valid_actions = [0, 1, 2, 3, 4]
            if can_cancel:
                valid_actions.insert(0, -1)
            option_text, option_list = option_data
            txt = "%s:" % (blue(option_text),)
            cls.output(txt)

            for item in option_list:
                mydict[counter] = item
                txt = "[%s] %s" % (darkgreen(str(counter)), blue(item),)
                cls.output(txt)
                counter += 1

            def show_current_list():
                for key in sorted(mydict):
                    txt = "[%s] %s" % (darkgreen(str(key)), blue(mydict[key]),)
                    cls.output(txt)

            while True:
                try:
                    sel_action = selaction()
                    if not sel_action:
                        show_current_list()
                    action = int(sel_action)
                except (ValueError, TypeError,):
                    cls.output(_("You don't have typed a number."), level = "warning")
                    continue
                if action not in valid_actions:
                    cls.output(_("Invalid action."), level = "warning")
                    continue
                if action == -1:
                    raise KeyboardInterrupt()
                elif action == 0:
                    break
                elif action == 1: # add item
                    while True:
                        try:
                            try:
                                s_el = readtext(darkred(_("String to add (-1 to go back):"))+" ")
                            except UnicodeDecodeError:
                                raise ValueError()
                            if s_el == "-1":
                                break
                            if not callback(s_el):
                                raise ValueError()
                            mydict[counter] = s_el
                            counter += 1
                        except (ValueError,):
                            cls.output(_("Invalid string."), level = "warning")
                            continue
                        break
                    show_current_list()
                    continue
                elif action == 2: # edit item
                    while True:
                        try:
                            edit_msg = _("Element number to edit (-1 to go back):")
                            try:
                                s_el = int(readtext(darkred(edit_msg)+" "))
                            except UnicodeDecodeError:
                                raise ValueError()
                            if s_el == -1:
                                break
                            if s_el not in mydict:
                                raise ValueError()
                            try:
                                new_s_val = readtext("[%s: %s] %s " % (
                                    _("old"), mydict[s_el], _("new value:"),)
                                )
                            except UnicodeDecodeError:
                                new_s_val = ''
                            if not callback(new_s_val):
                                raise ValueError()
                            mydict[s_el] = new_s_val[:]
                        except (ValueError, TypeError,):
                            cls.output(_("Invalid element."), level = "warning")
                            continue
                        break
                    show_current_list()
                    continue
                elif action == 3: # remove item
                    while True:
                        try:
                            try:
                                s_el = int(readtext(darkred(_("Element number to remove (-1 to go back):"))+" "))
                            except UnicodeDecodeError:
                                raise ValueError()
                            if s_el == -1:
                                break
                            if s_el not in mydict:
                                raise ValueError()
                            del mydict[s_el]
                        except (ValueError, TypeError,):
                            cls.output(_("Invalid element."), level = "warning")
                            continue
                        break
                    show_current_list()
                    continue
                elif action == 4: # show current list
                    show_current_list()
                    continue
                break

            mylist = [mydict[x] for x in sorted(mydict)]
            return mylist

        for identifier, input_text, callback, password in input_parameters:
            while True:
                use_cb = True
                try:
                    if isinstance(input_text, tuple):
                        myresult = False
                        input_type, data = input_text
                        if input_type == "checkbox":
                            answer = cls.ask_question(data)
                            if answer == _("Yes"):
                                myresult = True
                        elif input_type == "combo":
                            myresult = option_chooser(data)
                        elif input_type == "list":
                            use_cb = False
                            myresult = list_editor(data, cancel_button, callback)
                    else:
                        while True:
                            try:
                                myresult = readtext(input_text+": ", password = password).decode('utf-8')
                            except UnicodeDecodeError:
                                continue
                            break
                except (KeyboardInterrupt, EOFError,):
                    if not cancel_button: # use with care
                        continue
                    return None
                valid = True
                if use_cb:
                    valid = callback(myresult)
                if valid:
                    results[identifier] = myresult
                    break
        return results

    @classmethod
    def edit_file(cls, file_path):
        """
        Open a file editor on given file path (file_path).

        @param file_path: path to a writeable file
        @type file_path: string
        @return: True for successful edit, False otherwise
        @rtype: bool
        """
        editor = os.getenv("EDITOR", "/bin/nano")
        return subprocess.call((editor, file_path)) == 0

    @classmethod
    def set_title(cls, title):
        """
        Set application title.

        @param title: new application title
        @type title: string
        """
        xterm_title(title)
