#!/usr/bin/python
#
# This file is a portion of the Red Hat Network Panel Applet
#
# Copyright (C) 1999-2002 Red Hat, Inc. All Rights Reserved.
# Distributed under GPL version 2.
#
# $Id: applet.py,v 1.10 2003/09/15 15:07:19 veillard Exp $

import sys
import signal
sys.path.insert(0,'/usr/lib/entropy/client')
sys.path.insert(0,'/usr/lib/entropy/libraries')
sys.path.insert(0,'../../../client')
sys.path.insert(0,'../../../libraries')
sys.path.insert(0,'/usr/lib/entropy/spritz')
sys.path.insert(0,'../')


try:
    os.nice(10)
except:
    pass

args = filter(lambda s: s != "-d", sys.argv)
if args != sys.argv:
    sys.argv = args

import etp_applet

def child_reaper(*args):
    try:
        while os.waitpid(-1, os.WNOHANG):
            pass
    except:
        pass

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGCHLD, child_reaper)
    applet = etp_applet.rhnApplet()
    applet.run()

if __name__ == "__main__":
    main()

