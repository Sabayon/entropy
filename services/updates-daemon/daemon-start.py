#!/usr/bin/python

import sys
sys.path.insert(0,'/usr/lib/entropy/libraries')
sys.path.insert(0,'/usr/lib/entropy/server')
sys.path.insert(0,'/usr/lib/entropy/client')
sys.path.insert(0,'../libraries')
sys.path.insert(0,'../server')
sys.path.insert(0,'../client')

import gobject
import dbus
import dbus.service
import dbus.mainloop.glib
from daemon import equo_daemon


def run():
    
    dbus.mainloop.glib.DBusGMainLoop(set_as_default = True)
    session_bus = dbus.SessionBus()
    name = dbus.service.BusName("org.sabayon.entropy", session_bus)

    backend = equo_daemon(session_bus)

    mainloop = gobject.MainLoop ()
    print "equo daemon now running..."
    mainloop.run ()

if __name__ == "__main__":
    run()
    raise SystemExit(0)
