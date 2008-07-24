#!/usr/bin/python
'''
    # DESCRIPTION:
    # Text formatting and colouring tools

    Copyright 1998-2004 Gentoo Foundation
    # $Id: output.py 4906 2006-11-01 23:55:29Z zmedico $
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

import sys, os
import curses
from entropyConstants import etpUi
from entropy_i18n import _
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
for x in xrange(30, 38):
        ansi_color_codes.append("%im" % x)
        ansi_color_codes.append("%i;01m" % x)

rgb_ansi_colors = ['0x000000', '0x555555', '0xAA0000', '0xFF5555', '0x00AA00',
        '0x55FF55', '0xAA5500', '0xFFFF55', '0x0000AA', '0x5555FF', '0xAA00AA',
        '0xFF55FF', '0x00AAAA', '0x55FFFF', '0xAAAAAA', '0xFFFFFF']

for x in xrange(len(rgb_ansi_colors)):
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

def xtermTitle(mystr, raw=False):
    if dotitles and "TERM" in os.environ and sys.stderr.isatty():
        myt=os.environ["TERM"]
        legal_terms = ["xterm","Eterm","aterm","rxvt","screen","kterm","rxvt-unicode","gnome"]
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
        global default_xterm_title
        if default_xterm_title is None:
                prompt_command = os.getenv('PROMPT_COMMAND')
                if prompt_command == "":
                        default_xterm_title = ""
                elif prompt_command is not None:
                        import commands
                        default_xterm_title = commands.getoutput(prompt_command)
                else:
                        pwd = os.getenv('PWD','')
                        home = os.getenv('HOME', '')
                        if home != '' and pwd.startswith(home):
                                pwd = '~' + pwd[len(home):]
                        default_xterm_title = '\x1b]0;%s@%s:%s\x07' % (
                                os.getenv('LOGNAME', ''), os.getenv('HOSTNAME', '').split('.', 1)[0], pwd)
        xtermTitle(default_xterm_title, raw=True)

def notitles():
    "turn off title setting"
    global dotitles
    dotitles=0

def nocolor():
    "turn off colorization"
    os.environ['ETP_NO_COLOR'] = "1"
    global havecolor
    havecolor=0

nc = os.getenv("ETP_NO_COLOR")
if nc:
    nocolor()

def resetColor():
    return codes["reset"]

def colorize(color_key, text):
    if etpUi['mute']:
        return text
    global havecolor
    if havecolor:
        return codes[color_key] + text + codes["reset"]
    else:
        return text

compat_functions_colors = ["bold","white","teal","turquoise","darkteal",
        "fuscia","fuchsia","purple","blue","darkblue","green","darkgreen","yellow",
        "brown","darkyellow","red","darkred"]

def create_color_func(color_key):
    def derived_func(*args):
        newargs = list(args)
        newargs.insert(0, color_key)
        return colorize(*newargs)
    return derived_func

for c in compat_functions_colors:
    setattr(sys.modules[__name__], c, create_color_func(c))

def enlightenatom(atom):
    out = atom.split("/")
    return blue(out[0])+"/"+red(out[1])

def print_menu(data):

    def orig_myfunc(x):
        return x
    def orig_myfunc_desc(x):
        return x

    for item in data:

        myfunc = orig_myfunc
        myfunc_desc = orig_myfunc_desc

        if not item:
            writechar("\n")
        else:
            n_ident = item[0]
            name = item[1]
            n_d_ident = item[2]
            desc = item[3]

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
                print myfunc(name),
            except UnicodeEncodeError:
                print myfunc(name.encode('utf-8')),

            # write desc
            if desc:
                while n_d_ident > 0:
                    n_d_ident -= 1
                    writechar("\t")
                try:
                    print myfunc_desc(desc),
                except UnicodeEncodeError:
                    print myfunc_desc(desc.encode('utf-8')),
            writechar("\n")

def reset_cursor():
    if havecolor:
        sys.stdout.write(stuff['ESC'] + '[2K')
    flush_stdouterr()

def flush_stdouterr():
    sys.stdout.flush()
    sys.stderr.flush()

def print_error(msg, back = False, flush = True):
    if etpUi['mute']:
        return
    if not back:
        setcols()
    reset_cursor()
    writechar("\r")
    if back:
        try:
            print darkred(">>"),msg,
        except UnicodeEncodeError:
            print darkred(">>"),msg.encode('utf-8'),
    else:
        try:
            print darkred(">>"),msg
        except UnicodeEncodeError:
            print darkred(">>"),msg.encode('utf-8')
    if flush:
        flush_stdouterr()

def print_info(msg, back = False, flush = True):
    if etpUi['mute']:
        return
    if not back:
        setcols()
    reset_cursor()
    writechar("\r")
    if back:
        try:
            print darkgreen(">>"),msg,
        except UnicodeEncodeError:
            print darkgreen(">>"),msg.encode('utf-8'),
    else:
        try:
            print darkgreen(">>"),msg
        except UnicodeEncodeError:
            print darkgreen(">>"),msg.encode('utf-8')
    if flush:
        flush_stdouterr()

def print_warning(msg, back = False, flush = True):
    if etpUi['mute']:
        return
    if not back:
        setcols()
    reset_cursor()
    writechar("\r")
    if back:
        try:
            print red(">>"),msg,
        except UnicodeEncodeError:
            print red(">>"),msg.encode('utf-8'),
    else:
        try:
            print red(">>"),msg
        except UnicodeEncodeError:
            print red(">>"),msg.encode('utf-8')
    if flush:
        flush_stdouterr()

def print_generic(msg): # here we'll wrap any nice formatting
    if etpUi['mute']:
        return
    writechar("\r")
    try:
        print msg
    except UnicodeEncodeError:
        print msg.encode('utf-8')
    flush_stdouterr()

def writechar(char):
    if etpUi['mute']:
        return
    try:
        sys.stdout.write(char)
        sys.stdout.flush()
    except IOError, e:
        if e.errno == 32:
            return
        raise

def readtext(request, password = False):
    xtermTitle(_("Entropy needs your attention"))
    if password:
        from getpass import getpass
        try:
            text = getpass(request+" ")
        except UnicodeEncodeError:
            text = getpass(request.encode('utf-8')+" ")
    else:
        import readline
        try:
            print request,
        except UnicodeEncodeError:
            print request.encode('utf-8'),
        flush_stdouterr()
        text = raw_input() # using readline module
    return text

class TextInterface:

    import entropyTools

    # @input text: text to write
    # @input back: write on on the same line?
    # @input importance:
    #           values: 0,1,2,3 (latter is a blocker - popup menu on a GUI env)
    #           used to specify information importance, 0<important<2
    # @input type:
    #           values: "info, warning, error"
    #
    # @input count:
    #           if you need to print an incremental count ( 100/250...101/251..)
    #           just pass count = [first integer,second integer] or even a tuple!
    # @input header:
    #           text header (decoration?), that's it
    #
    # @input footer:
    #           text footer (decoration?), that's it
    #
    # @input percent:
    #           if percent is True: count will be treating as a percentual count[0]/count[1]*100
    #
    # feel free to reimplement this
    def updateProgress(self, text, header = "", footer = "", back = False, importance = 0, type = "info", count = [], percent = False):
        if (etpUi['quiet']) or (etpUi['mute']):
            return

        flush_stdouterr()

        myfunc = print_info
        if type == "warning":
            myfunc = print_warning
        elif type == "error":
            myfunc = print_error

        count_str = ""
        if count:
            if len(count) > 1:
                if percent:
                    count_str = " ("+str(round((float(count[0])/count[1])*100,1))+"%) "
                else:
                    count_str = " (%s/%s) " % (red(str(count[0])),blue(str(count[1])),)
        if importance == 0:
            myfunc(header+count_str+text+footer, back = back, flush = False)
        elif importance == 1:
            myfunc(header+count_str+text+footer, back = back, flush = False)
        elif importance in (2,3):
            myfunc(header+count_str+text+footer, back = back, flush = False)

        flush_stdouterr()

    # @input question: question to do
    #
    # @input importance:
    #           values: 0,1,2 (latter is a blocker - popup menu on a GUI env)
    #           used to specify information importance, 0<important<2
    #
    # @input responses:
    #           list of options whose users can choose between
    #
    # feel free to reimplement this
    def askQuestion(self, question, importance = 0, responses = ["Yes","No"]):

        colours = [green, red, blue, darkgreen, darkred, darkblue, brown, purple]
        if len(responses) > len(colours):
            import exceptionTools
            raise exceptionTools.IncorrectParameter("IncorrectParameter: %s = %s" % (_("maximum responses length"),len(colours),))
        try:
            print darkgreen(question),
        except UnicodeEncodeError:
            print darkgreen(question.encode('utf-8')),
        try:
            while True:
                xtermTitle(_("Entropy got a question for you"))
                response = raw_input("["+"/".join([colours[i](responses[i]) for i in range(len(responses))])+"] ")
                for key in responses:
                    # An empty response will match the first value in responses.
                    if response.upper() == key[:len(response)].upper():
                        xtermTitleReset()
                        return key
                    '''
                    try:
                        print "%s '%s'" % (_("I cannot understand"),response,),
                    except UnicodeEncodeError:
                        print "%s '%s'" % (_("I cannot understand"),response.encode('utf-8'),),
                    '''
                    flush_stdouterr()
        except (EOFError, KeyboardInterrupt):
            print "%s." % (_("Interrupted"),)
            xtermTitleReset()
            sys.exit(100)
        xtermTitleReset()
        flush_stdouterr()

    # @ title: title of the input box
    # @ input_parameters: [('identifier 1','input text 1',input_verification_callback,False), ('password','Password',input_verification_callback,True)]
    # @ cancel_button: show cancel button ?
    # @ output: dictionary as follows:
    #   {'identifier 1': result, 'identifier 2': result}
    def inputBox(self, title, input_parameters, cancel_button = True):
        results = {}
        try:
            print title
        except UnicodeEncodeError:
            print title.encode('utf-8')
        flush_stdouterr()

        for identifier, input_text, callback, password in input_parameters:
            while 1:
                try:
                    myresult = readtext(input_text+":", password = password)
                except (KeyboardInterrupt,EOFError,):
                    if not cancel_button: # use with care
                        continue
                    return None
                valid = callback(myresult)
                if valid:
                    results[identifier] = myresult
                    break
        return results

    # useful for reimplementation
    # in this wait you can send a signal to a widget (total progress bar?)
    def cycleDone(self):
        return

    def setTitle(self, title):
        xtermTitle(title)

    def setTotalCycles(self, total):
        return

    def outputInstanceTest(self):
        return

    def nocolor(self):
        nocolor()

    def notitles(self):
        notitles()