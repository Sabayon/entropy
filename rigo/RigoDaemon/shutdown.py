#!/usr/bin/python
import sys
sys.path.insert(0, "./")
sys.path.insert(1, "/usr/lib/rigo")

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from RigoDaemon.config import DbusConfig

if __name__ == "__main__":
    mainloop = DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus(mainloop=mainloop)
    entropy_bus = bus.get_object(
        DbusConfig.BUS_NAME,
        DbusConfig.OBJECT_PATH)
    dbus.Interface(
        entropy_bus,
        dbus_interface=DbusConfig.BUS_NAME).reload()
    raise SystemExit(0)
