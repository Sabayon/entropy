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
import readline
from entropyConstants import etpUi
stuff = {}
stuff['cleanline'] = ''
stuff['cols'] = 30
try:
    curses.setupterm()
    stuff['cols'] = curses.tigetnum('cols')
except:
    pass
for x in range(stuff['cols']):
    stuff['cleanline'] += ' '

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
                        sys.stderr.write(mystr)
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
    global havecolor
    havecolor=0

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

def print_error(msg, back = False):
    if etpUi['mute']:
        return
    if (back):
        writechar("\r   "+stuff['cleanline']+"\r")
        writechar("\r"+red(">>")+" "+msg)
        return
    writechar("\r"+stuff['cleanline']+"\r")
    print darkred(">>")+" "+msg

def print_info(msg, back = False):
    if etpUi['mute']:
        return
    if back:
        writechar("\r"+stuff['cleanline']+"\r")
        writechar("\r"+green(">>")+" "+msg)
        return
    writechar("\r"+stuff['cleanline']+"\r")
    print green(">>")+" "+msg

def print_warning(msg, back = False):
    if etpUi['mute']:
        return
    if back:
        writechar("\r"+stuff['cleanline']+"\r")
        writechar("\r"+red(">>")+" "+msg)
        return
    writechar("\r"+stuff['cleanline']+"\r")
    print red(">>")+" "+msg

def print_generic(msg): # here we'll wrap any nice formatting
    if etpUi['mute']:
        return
    print msg

def writechar(char):
    if etpUi['mute']:
        return
    sys.stdout.write(char); sys.stdout.flush()

def readtext(request):
    xtermTitle("Entropy needs your attention")
    text = raw_input(request) # using readline module
    return text

class TextInterface:

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

        myfunc = print_info
        if type == "warning":
            myfunc = print_warning
        elif type == "error":
            myfunc = print_error

        count_str = ""
        if count:
            if len(count) < 2:
                import exceptionTools
                raise exceptionTools.IncorrectParameter("IncorrectParameter: count length must be >= 2")
            if percent:
                count_str = " ("+str(round((float(count[0])/count[1])*100,1))+"%) "
            else:
                count_str = " (%s/%s) " % (red(str(count[0])),blue(str(count[1])),)
        if importance == 0:
            myfunc(header+count_str+text+footer, back = back)
        elif importance == 1:
            myfunc(header+count_str+text+footer, back = back)
        elif importance in (2,3):
            myfunc(header+count_str+text+footer, back = back)

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
            raise exceptionTools.IncorrectParameter("IncorrectParameter: maximum responses length = %s" % (len(colours),))
        print darkgreen(question),
        try:
            while True:
                xtermTitle("Entropy got a question for you")
                response = raw_input("["+"/".join([colours[i](responses[i]) for i in range(len(responses))])+"] ")
                for key in responses:
                    # An empty response will match the first value in responses.
                    if response.upper()==key[:len(response)].upper():
                        xtermTitleReset()
                        return key
                        print "I cannot understand '%s'" % response,
        except (EOFError, KeyboardInterrupt):
            print "Interrupted."
            xtermTitleReset()
            sys.exit(100)
        xtermTitleReset()

    # useful for reimplementation
    # in this wait you can send a signal to a widget (total progress bar?)
    def cycleDone(self):
        return

    def outputInstanceTest(self):
        return

    def nocolor(self):
        nocolor()

    def notitles(self):
        notitles()