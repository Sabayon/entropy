#!/usr/bin/python
#
# This file is a portion of the Red Hat Network Panel Applet
#
# Copyright (C) 1999-2002 Red Hat, Inc. All Rights Reserved.
# Distributed under GPL version 2.
#
# $Id: applet.py,v 1.10 2003/09/15 15:07:19 veillard Exp $

import sys
#import signal
sys.path.insert(0,'/usr/lib/entropy/client')
sys.path.insert(0,'/usr/lib/entropy/libraries')
sys.path.insert(0,'/usr/lib/entropy/sulfur')
sys.path.insert(0,'../../client')
sys.path.insert(0,'../../libraries')
sys.path.insert(0,'../../sulfur/src')
sys.path.insert(0,'../')
sys.argv.append('--no-pid-handling')
import gtk
import gtk.gdk
import gobject

import etp_applet

if __name__ == "__main__":
    #signal.signal(signal.SIGINT, signal.SIG_DFL)
    applet = etp_applet.EntropyApplet()
    try:
        gobject.threads_init()
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()
    except KeyboardInterrupt:
        try:
            applet.close_service()
        except:
            pass
        gobject.timeout_add(0, applet.exit_applet)
        gtk.gdk.threads_leave()
        raise

