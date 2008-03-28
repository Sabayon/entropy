# This file is a portion of the Red Hat Network Panel Applet
#
# Copyright (C) 2008 Sabayon Linux
# Distributed under GPL version 2.
#
# $Id: applet.py,v 1.10 2003/09/15 15:07:19 veillard Exp $

import os
import dumpTools

APPLET_STATES = [ "STARTUP", "NOCONSENT", "CONFIGURING", "OKAY", "CRITICAL", "BUSY", "ERROR", "DISCONNECTED" ]

APPLET_STATE_CHANGES = {
    "STARTUP"     : [ "OKAY", "NOCONSENT" ],
    "NOCONSENT"   : [ "CONFIGURING" ],
    "CONFIGURING" : [ "NOCONSENT", "BUSY", "OKAY", "DISCONNECTED" ],
    "OKAY"        : [ "BUSY", "CONFIGURING", "CRITICAL", "DISCONNECTED" ],
    "CRITICAL"    : [ "OKAY", "BUSY", "CRITICAL", "CONFIGURING", "DISCONNECTED" ],
    "BUSY"        : [ "OKAY", "CRITICAL", "ERROR", "DISCONNECTED" ],
    "ERROR"       : [ "OKAY", "BUSY" ],
    "DISCONNECTED": [ "OKAY", "BUSY", "CONFIGURING", "CRITICAL", "ERROR"], 
    }

APPLET_MENUS = [ "about", "update_now", "web_panel", "web_site", "configure_applet", "check_now" ]

APPLET_SENSITIVE_MENU = {
    "STARTUP"     : [ "" ],
    "NOCONSENT"   : [ "about", "configure_applet", "update_now", "busy" ],
    "CONFIGURING" : [ "about", "update_now" ],
    "OKAY"        : APPLET_MENUS,
    "CRITICAL"    : APPLET_MENUS,
    "BUSY"        : [ ],
    "ERROR"       : [ "about", "update_now", "check_now" ],
    "DISCONNECTED": [ "about", "update_now", "check_now" ],
}

REFRESH_INTERVAL = 60 # seconds
NETWORK_RETRY_INTERVAL = 180
ERROR_THRESHOLD = 3

ANIMATION_TOTAL_TIME = 0.75

home = os.getenv("HOME")
if not home:
    home = "/tmp"
SETTINGS_FILE = os.path.join(home, ".config/entropy/settings")

def save_settings(settings):
    global SETTINGS_FILE
    try:
        if not os.path.isdir(os.path.dirname(SETTINGS_FILE)):
            os.makedirs(os.path.dirname(SETTINGS_FILE))
        dumpTools.dumpobj(SETTINGS_FILE, settings, completePath = True)
    except:
        pass

settings = dumpTools.loadobj(SETTINGS_FILE, completePath = True)
if settings == None:
    settings = {}

myconst = [
            ['REFRESH_INTERVAL',int],
            ['NETWORK_RETRY_INTERVAL',int],
            ['ERROR_THRESHOLD',int],
            ['ANIMATION_TOTAL_TIME',float]
          ]

for x in myconst:
    if not settings.has_key(x[0]):
        settings[x[0]] = eval(x[0])
    else:
        if not isinstance(settings[x[0]],x[1]):
            settings[x[0]] = eval(x[0])

save_settings(settings)
