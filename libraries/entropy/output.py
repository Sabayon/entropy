# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework Output module}.

    This module contains Entropy (user) Output classes and routines.

"""
import sys, os
import curses
from entropy.const import etpUi
from entropy.exceptions import IncorrectParameter
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



codes={}
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

del x

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

# Colors from /sbin/functions.sh
codes["GOOD"]       = codes["green"]
codes["WARN"]       = codes["yellow"]
codes["BAD"]        = codes["red"]
codes["HILITE"]     = codes["teal"]
codes["BRACKET"]    = codes["blue"]

# Portage functions
codes["INFORM"] = codes["darkgreen"]
codes["UNMERGE_WARN"] = codes["red"]
codes["MERGE_LIST_PROGRESS"] = codes["yellow"]

def xtermTitle(mystr, raw = False):
    """
    Set new xterm title.

    @param mystr: new xterm title
    @type mystr: string
    @keyword raw: write title in raw mode
    @type raw: bool
    """
    if dotitles and "TERM" in os.environ and sys.stderr.isatty():
        myt = os.environ["TERM"]
        legal_terms = ["xterm", "Eterm", "aterm", "rxvt", "screen", "kterm", "rxvt-unicode", "gnome"]
        if myt in legal_terms:
            if not raw:
                mystr = "\x1b]0;%s\x07" % mystr
            try:
                sys.stderr.write(mystr)
            except UnicodeEncodeError:
                sys.stderr.write(mystr.encode('utf-8'))
            sys.stderr.flush()

default_xterm_title = None

def xtermTitleReset():
    """
    Reset xterm title to default.
    """
    global default_xterm_title
    if default_xterm_title is None:
        prompt_command = os.getenv('PROMPT_COMMAND')
        if prompt_command == "":
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
    xtermTitle(default_xterm_title)

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

nc = os.getenv("ETP_NO_COLOR")
if nc:
    nocolor()

def resetColor():
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
    if etpUi['mute']:
        return text
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

def enlightenatom(atom):
    """
    Colorize package atoms with standard colors.

    @param atom: atom string
    @type atom: string
    @return: colorized string
    @rtype: string
    """
    out = atom.split("/")
    return blue(out[0])+"/"+red(out[1])

def print_menu(data, args = None):
    """
    Function used by Entropy text client (will be moved from here) to
    print the menu output given a properly formatted list.
    This method is not intended for general used and will be moved away from
    here.
    """
    if args == None:
        args = []

    def orig_myfunc(x):
        return x
    def orig_myfunc_desc(x):
        return x

    try:
        i = args.index("--help")
        del args[i]
        command = args.pop(0)
    except ValueError:
        command = None
    except IndexError:
        command = None
    section_found = False
    search_depth = 1


    for item in data:
        myfunc = orig_myfunc
        myfunc_desc = orig_myfunc_desc

        if not item:
            if command == None or section_found:
                writechar("\n")
        else:
            n_ident = item[0]
            name = item[1]
            n_d_ident = item[2]
            desc = item[3]
            if command != None: 
                #print "searching ",name, command, n_ident, search_depth
                if name == command and n_ident == search_depth:
                    try:
                        command = args.pop(0)
                        search_depth = n_ident + 1
                    except IndexError:
                        command = "##unused_from_now_on"
                        section_found = True
                        indent_level = n_ident
                elif section_found:
                    if n_ident <= indent_level:
                        return
                else:
                    continue

            if n_ident == 0:
                writechar("  ")
            # setup identation
            while n_ident > 0:
                n_ident -= 1
                writechar("\t")
            n_ident = item[0]

            # write name
            if n_ident == 0:
                myfunc = darkgreen
            elif n_ident == 1:
                myfunc = blue
                myfunc_desc = darkgreen
            elif n_ident == 2:
                if not name.startswith("--"):
                    myfunc = red
                myfunc_desc = brown
            elif n_ident == 3:
                myfunc = darkblue
                myfunc_desc = purple
            try:
                sys.stdout.write(myfunc(name))
            except UnicodeEncodeError:
                    sys.stdout.write(myfunc(name.encode('utf-8')))

            # write desc
            if desc:
                while n_d_ident > 0:
                    n_d_ident -= 1
                    writechar("\t")
                try:
                    sys.stdout.write(myfunc_desc(desc))
                except UnicodeEncodeError:
                    sys.stdout.write(myfunc_desc(desc.encode('utf-8')))
            writechar("\n")

def reset_cursor():
    """
    Print to stdout the terminal code to push back cursor at the beginning
    of the line.
    """
    if havecolor:
        sys.stdout.write(stuff['ESC'] + '[2K')
    _flush_stdouterr()

def _flush_stdouterr():
    sys.stdout.flush()
    sys.stderr.flush()

def print_error(msg, back = False, flush = True):
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
    if etpUi['mute']:
        return
    if not back:
        setcols()
    reset_cursor()
    writechar("\r")
    if back:
        try:
            sys.stdout.write(darkred(">>") + " " + msg)
        except UnicodeEncodeError:
            sys.stdout.write(darkred(">>") + " " + msg.encode('utf-8'))
    else:
        try:
            sys.stdout.write(darkred(">>") + " " + msg + "\n")
        except UnicodeEncodeError:
            sys.stdout.write(darkred(">>") + " " + msg.encode('utf-8') + "\n")
    if flush:
        _flush_stdouterr()

def print_info(msg, back = False, flush = True):
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
    if etpUi['mute']:
        return
    if not back:
        setcols()
    reset_cursor()
    writechar("\r")
    if back:
        try:
            sys.stdout.write(darkgreen(">>") + " " + msg)
        except UnicodeEncodeError:
            sys.stdout.write(darkgreen(">>") + " " + msg.encode('utf-8'))
    else:
        try:
            sys.stdout.write(darkgreen(">>") + " " + msg + "\n")
        except UnicodeEncodeError:
            sys.stdout.write(darkgreen(">>") + " " + msg.encode('utf-8') + "\n")
    if flush:
        _flush_stdouterr()

def print_warning(msg, back = False, flush = True):
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
    if etpUi['mute']:
        return
    if not back:
        setcols()
    reset_cursor()
    writechar("\r")
    if back:
        try:
            sys.stdout.write(red(">>") + " " + msg)
        except UnicodeEncodeError:
            sys.stdout.write(red(">>") + " " + msg.encode('utf-8'))
    else:
        try:
            sys.stdout.write(red(">>") + " " + msg + "\n")
        except UnicodeEncodeError:
            sys.stdout.write(red(">>") + " " + msg.encode('utf-8') + "\n")
    if flush:
        _flush_stdouterr()

def print_generic(*args):
    """
    Service function used by Entropy text client (will be moved from here)
    to write generic messages to stdout (not stderr, atm).
    NOTE: don't use this directly but rather subclass TextInterface class.

    @param msg: text message to print
    @type msg: string
    @return: None
    @rtype: None
    """
    if etpUi['mute']:
        return
    # disabled, because it causes quite a mess when writing to files
    # writechar("\r")
    for msg in args:
        try:
            sys.stdout.write(msg + " ")
        except UnicodeEncodeError:
            sys.stdout.write(msg.encode('utf-8') + " ")
    sys.stdout.write("\n")
    _flush_stdouterr()

def writechar(chars):
    """
    Write characters to stdout (will be moved from here).

    @param chars: chars to write
    @type chars: string
    """
    if etpUi['mute']:
        return
    try:
        sys.stdout.write(chars)
        sys.stdout.flush()
    except IOError as e:
        if e.errno == 32:
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
    """
    xtermTitle(_("Entropy needs your attention"))
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
    if txt:
        try:
            sys.stdout.write(darkgreen(txt))
        except UnicodeEncodeError:
            sys.stdout.write(darkgreen(txt.encode('utf-8')))
    _flush_stdouterr()
    response = ''
    while 1:
        y = sys.stdin.read(1)
        if y in ('\n', '\r',): break
        response += y
        _flush_stdouterr()
    return response

class TextInterface:

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

    def updateProgress(self, text, header = "", footer = "", back = False,
        importance = 0, type = "info", count = None, percent = False):

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
        @keyword type: message type (default valid values: "info", "warning",
            "error")
        @type type: string
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

        if etpUi['quiet'] or etpUi['mute']:
            return

        _flush_stdouterr()

        myfunc = print_info
        if type == "warning":
            myfunc = print_warning
        elif type == "error":
            myfunc = print_error

        count_str = ""
        if count:
            if len(count) > 1:
                if percent:
                    percent_str = str(round((float(count[0])/count[1])*100, 1))
                    count_str = " ("+percent_str+"%) "
                else:
                    count_str = " (%s/%s) " % (red(str(count[0])),
                        blue(str(count[1])),)

        myfunc(header+count_str+text+footer, back = back, flush = False)
        _flush_stdouterr()

    def askQuestion(self, question, importance = 0, responses = None):

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
            sys.stdout.write(darkgreen(question) + " ")
        except UnicodeEncodeError:
            sys.stdout.write(darkgreen(question.encode('utf-8')) + " ")
        _flush_stdouterr()

        try:
            while 1:

                xtermTitle(_("Entropy got a question for you"))
                _flush_stdouterr()
                answer_items = [colours[x % colours_len](responses[x]) \
                    for x in range(len(responses))]
                response = _my_raw_input("["+"/".join(answer_items)+"] ")
                _flush_stdouterr()

                for key in responses:
                    if response.upper() == key[:len(response)].upper():
                        xtermTitleReset()
                        return key
                    _flush_stdouterr()

        except (EOFError, KeyboardInterrupt):
            msg = "%s.\n" % (_("Interrupted"),)
            try:
                sys.stdout.write(msg)
            except UnicodeEncodeError:
                sys.stdout.write(msg.encode("utf-8"))
            xtermTitleReset()
            raise SystemExit(100)

        xtermTitleReset()
        _flush_stdouterr()

    def inputBox(self, title, input_parameters, cancel_button = True):
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
            self.updateProgress(option_text)
            for item in option_list:
                mydict[counter] = item
                txt = "[%s] %s" % (darkgreen(str(counter)), blue(item),)
                self.updateProgress(txt)
                counter += 1
            while 1:
                myresult = readtext("%s:" % (_('Selected number'),)).decode('utf-8')
                try:
                    myresult = int(myresult)
                except ValueError:
                    continue
                selected = mydict.get(myresult)
                if selected != None:
                    return myresult, selected

        def list_editor(option_data, can_cancel, callback):

            def selaction():
                self.updateProgress('')
                self.updateProgress(darkred(_("Please select an option")))
                if can_cancel:
                    self.updateProgress("  ("+blue("-1")+") "+darkred(_("Discard all")))
                self.updateProgress("  ("+blue("0")+")  "+darkgreen(_("Confirm")))
                self.updateProgress("  ("+blue("1")+")  "+brown(_("Add item")))
                self.updateProgress("  ("+blue("2")+")  "+darkblue(_("Remove item")))
                self.updateProgress("  ("+blue("3")+")  "+darkgreen(_("Show current list")))
                # wait user interaction
                self.updateProgress('')
                action = readtext(darkgreen(_("Your choice (type a number and press enter):"))+" ")
                return action

            mydict = {}
            counter = 1
            valid_actions = [0, 1, 2, 3]
            if can_cancel: valid_actions.insert(0, -1)
            option_text, option_list = option_data
            txt = "%s:" % (blue(option_text),)
            self.updateProgress(txt)

            for item in option_list:
                mydict[counter] = item
                txt = "[%s] %s" % (darkgreen(str(counter)), blue(item),)
                self.updateProgress(txt)
                counter += 1

            def show_current_list():
                for key in sorted(mydict):
                    txt = "[%s] %s" % (darkgreen(str(key)), blue(mydict[key]),)
                    self.updateProgress(txt)

            while 1:
                try:
                    action = int(selaction())
                except (ValueError, TypeError,):
                    self.updateProgress(_("You don't have typed a number."), type = "warning")
                    continue
                if action not in valid_actions:
                    self.updateProgress(_("Invalid action."), type = "warning")
                    continue
                if action == -1:
                    raise KeyboardInterrupt
                elif action == 0:
                    break
                elif action == 1:
                    while 1:
                        try:
                            s_el = readtext(darkred(_("String to add:"))+" ")
                            if not callback(s_el):
                                raise ValueError
                            mydict[counter] = s_el
                            counter += 1
                        except (ValueError,):
                            self.updateProgress(_("Invalid string."), type = "warning")
                            continue
                        break
                    show_current_list()
                    continue
                elif action == 2:
                    while 1:
                        try:
                            s_el = int(readtext(darkred(_("Element number to remove:"))+" "))
                            if s_el not in mydict:
                                raise ValueError
                            del mydict[s_el]
                        except (ValueError, TypeError,):
                            self.updateProgress(_("Invalid element."), type = "warning")
                            continue
                        break
                    show_current_list()
                    continue
                elif action == 3:
                    show_current_list()
                    continue
                break

            mylist = [mydict[x] for x in sorted(mydict)]
            return mylist

        for identifier, input_text, callback, password in input_parameters:
            while 1:
                use_cb = True
                try:
                    if isinstance(input_text, tuple):
                        myresult = False
                        input_type, data = input_text
                        if input_type == "checkbox":
                            answer = self.askQuestion(data)
                            if answer == "Yes": myresult = True
                        elif input_type == "combo":
                            myresult = option_chooser(data)
                        elif input_type == "list":
                            use_cb = False
                            myresult = list_editor(data, cancel_button, callback)
                    else:
                        myresult = readtext(input_text+":", password = password).decode('utf-8')
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

    # useful for reimplementation
    # in this wait you can send a signal to a widget (total progress bar?)
    def cycleDone(self):
        """
        Not actually implemented. Can be useful for external applications and
        its used to determine when a certain transaction is done.
        """
        pass

    def setTitle(self, title):
        """
        Set application title.

        @param title: new application title
        @type title: string
        """
        xtermTitle(title)

    def setTotalCycles(self, total):
        """
        Not actually implemented. Can be useful for external applications and
        its used to set the amount of logical transactions that this interface
        has to go through.
        """
        pass

    def nocolor(self):
        """
        Disable coloured output. Used for terminals.
        """
        nocolor()

    def notitles(self):
        """
        Disable the ability to effectively set the application title.
        """
        notitles()
