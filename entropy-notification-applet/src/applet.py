#!/usr/bin/python
#
# This file is a portion of the Red Hat Network Panel Applet
#
# Copyright (C) 1999-2002 Red Hat, Inc. All Rights Reserved.
# Distributed under GPL version 2.
#
# $Id: applet.py,v 1.10 2003/09/15 15:07:19 veillard Exp $

import sys, gtk
#import signal
sys.path.insert(0,'/usr/lib/entropy/client')
sys.path.insert(0,'/usr/lib/entropy/libraries')
sys.path.insert(0,'/usr/lib/entropy/spritz')
sys.path.insert(0,'../../client')
sys.path.insert(0,'../../libraries')
sys.path.insert(0,'../../spritz/src')
sys.path.insert(0,'../')
sys.argv.append('--no-pid-handling')

import etp_applet

if __name__ == "__main__":
    #signal.signal(signal.SIGINT, signal.SIG_DFL)
    applet = etp_applet.EntropyApplet()
    try:
        gtk.main()
    except KeyboardInterrupt:
        applet.close_service()
        raise

