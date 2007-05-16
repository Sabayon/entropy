#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy log facility

    Copyright (C) 2007 Fabio Erculiani <lxnay@sabayonlinux.org>
    # Most of the code taken from Anaconda, copyrighted by:
    # Alexander Larsson <alexl@redhat.com>
    # Matt Wilson <msw@redhat.com>
    #
    # Copyright 2002 Red Hat, Inc.

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

import sys

class LogFile:
    def __init__ (self, level = 0, filename = None):
	self.handler = self.default_handler
        self.level = level
        self.logFile = None
        self.open(filename)

    def close (self):
        try:
            self.logFile.close ()
        except:
            pass

    def open (self, file = None):
	if type(file) == type("hello"):
            try:
                self.logFile = open(file, "aw")
            except:
                self.logFile = sys.stderr
	elif file:
	    self.logFile = file
	else:
            self.logFile = sys.stderr
        
    def getFile (self):
        return self.logFile.fileno ()

    def __call__(self, format, *args):
	self.handler (format % args)

    def default_handler (self, string):
	self.logFile.write ("* %s\n" % (string))
	self.logFile.flush ()

    def set_loglevel(self, level):
        self.level = level

    def log(self, level, message):
        if self.level >= level:
            self.handler(message)

    def ladd(self, level, file, message):
        if self.level >= level:
            self.handler("++ %s \t%s" % (file, message))

    def ldel(self, level, file, message):
        if self.level >= level:
            self.handler("-- %s \t%s" % (file, message))

    def lch(self, level, file, message):
        if self.level >= level:
            self.handler("-+ %s \t%s" % (file, message))

log = LogFile()
