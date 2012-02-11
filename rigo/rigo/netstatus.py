# Copyright (C) 2009 Canonical
#
# Authors:
#   Matthew McGowan
#   Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


import dbus
import logging

from dbus.mainloop.glib import DBusGMainLoop

from gi.repository import GObject

# enums
class NetState(object):
    """ enums for network manager status """
    # Old enum values are for NM 0.7

    # The NetworkManager daemon is in an unknown state. 
    NM_STATE_UNKNOWN            = 0   
    NM_STATE_UNKNOWN_LIST       = [NM_STATE_UNKNOWN]
    # The NetworkManager daemon is asleep and all interfaces managed by it are inactive. 
    NM_STATE_ASLEEP_OLD         = 1
    NM_STATE_ASLEEP             = 10
    NM_STATE_ASLEEP_LIST        = [NM_STATE_ASLEEP_OLD,
                                   NM_STATE_ASLEEP]
    # The NetworkManager daemon is connecting a device.
    NM_STATE_CONNECTING_OLD     = 2
    NM_STATE_CONNECTING         = 40
    NM_STATE_CONNECTING_LIST    = [NM_STATE_CONNECTING_OLD,
                                   NM_STATE_CONNECTING]
    # The NetworkManager daemon is connected. 
    NM_STATE_CONNECTED_OLD      = 3
    NM_STATE_CONNECTED_LOCAL    = 50
    NM_STATE_CONNECTED_SITE     = 60
    NM_STATE_CONNECTED_GLOBAL   = 70
    NM_STATE_CONNECTED_LIST     = [NM_STATE_CONNECTED_OLD,
                                   NM_STATE_CONNECTED_LOCAL,
                                   NM_STATE_CONNECTED_SITE,
                                   NM_STATE_CONNECTED_GLOBAL]
    # The NetworkManager daemon is disconnecting.
    NM_STATE_DISCONNECTING      = 30
    NM_STATE_DISCONNECTING_LIST = [NM_STATE_DISCONNECTING]
    # The NetworkManager daemon is disconnected.
    NM_STATE_DISCONNECTED_OLD   = 4
    NM_STATE_DISCONNECTED       = 20
    NM_STATE_DISCONNECTED_LIST  = [NM_STATE_DISCONNECTED_OLD,
                                   NM_STATE_DISCONNECTED]


class NetworkStatusWatcher(GObject.GObject):
    """ simple watcher which notifys subscribers to network events..."""
    __gsignals__ = {'changed':(GObject.SIGNAL_RUN_FIRST,
                               GObject.TYPE_NONE,
                               (int,)),
                   }

    def __init__(self):
        GObject.GObject.__init__(self)
        return

# internal helper
NETWORK_STATE = 0
def __connection_state_changed_handler(state):
    global NETWORK_STATE

    NETWORK_STATE = int(state)
    __WATCHER__.emit("changed", NETWORK_STATE)
    return

# init network state
def __init_network_state():
    global NETWORK_STATE

    # check is SOFTWARE_CENTER_NET_DISCONNECTED is in the environment variables
    # if so force the network status to be disconnected
    import os
    if ("SOFTWARE_CENTER_NET_DISCONNECTED" in os.environ and
        os.environ["SOFTWARE_CENTER_NET_DISCONNECTED"] == 1):
        NETWORK_STATE = NetState.NM_STATE_DISCONNECTED
        print('forced netstate into disconnected mode...')
        return

    dbus_loop = DBusGMainLoop()
    try:
        bus = dbus.SystemBus(mainloop=dbus_loop)
        nm = bus.get_object('org.freedesktop.NetworkManager',
                            '/org/freedesktop/NetworkManager')
        NETWORK_STATE = nm.state(dbus_interface='org.freedesktop.NetworkManager')
        bus.add_signal_receiver(__connection_state_changed_handler,
                                dbus_interface="org.freedesktop.NetworkManager",
                                signal_name="StateChanged")
    except Exception as e:
        logging.warn("failed to init network state watcher '%s'" % e)
        NETWORK_STATE = NetState.NM_STATE_UNKNOWN

# global watcher
__WATCHER__ = NetworkStatusWatcher()
def get_network_watcher():
    return __WATCHER__

# simply query
def get_network_state():
    """ get the NetState state """
    global NETWORK_STATE
    return NETWORK_STATE

# simply query even more
def network_state_is_connected():
    """ get bool if we are connected """
    # unkown because in doubt, just assume we have network
    return get_network_state() in NetState.NM_STATE_UNKNOWN_LIST + \
                                  NetState.NM_STATE_CONNECTED_LIST

# init it once
__init_network_state()

if __name__ == '__main__':
    loop = GObject.MainLoop()
    loop.run()

