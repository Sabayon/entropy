# This file is a portion of the Red Hat Network Panel Applet
#
# Copyright (C) 2008 Sabayon Linux
# Distributed under GPL version 2.
#
# $Id: applet.py,v 1.10 2003/09/15 15:07:19 veillard Exp $

import os
import entropy.dump as dumpTools

APPLET_STATES = [ "STARTUP", "NOCONSENT", "CONFIGURING", "OKAY",
    "CRITICAL", "BUSY", "ERROR", "DISCONNECTED", "DISABLE" ]
APPLET_MENUS = [ "about", "update_now", "web_panel", "web_site",
    "configure_applet", "check_now" ]

APPLET_SENSITIVE_MENU = {
    "STARTUP"     : [ "" ],
    "NOCONSENT"   : [ "about", "configure_applet", "update_now", "busy" ],
    "CONFIGURING" : [ "about", "update_now" ],
    "OKAY"        : APPLET_MENUS,
    "CRITICAL"    : APPLET_MENUS,
    "BUSY"        : [ ],
    "ERROR"       : [ "about", "update_now", "check_now" ],
    "DISCONNECTED": [ "about", "update_now", "check_now" ],
    "DISABLE": [ "about", "update_now", "check_now" ],
}

RANDOM_REFRESH_DELTA = abs(hash(os.urandom(2)))%1800
REFRESH_INTERVAL = 3600+RANDOM_REFRESH_DELTA # seconds
NETWORK_RETRY_INTERVAL = 180
ERROR_THRESHOLD = 3
APPLET_ENABLED = 1

ANIMATION_TOTAL_TIME = 0.75

home = os.getenv("HOME")
if not home: home = "/tmp"
SETTINGS_FILE = os.path.join(home,
    ".config/entropy/entropy-notification-applet.conf")

def save_settings(settings):
    global SETTINGS_FILE
    try:
        if not os.path.isdir(os.path.dirname(SETTINGS_FILE)):
            os.makedirs(os.path.dirname(SETTINGS_FILE))
        dumpTools.dumpobj(SETTINGS_FILE, settings, complete_path = True)
    except:
        pass

settings = dumpTools.loadobj(SETTINGS_FILE, complete_path = True)
if settings == None:
    settings = {}

myconst = [
            ['ERROR_THRESHOLD',int],
            ['ANIMATION_TOTAL_TIME',float],
            ['APPLET_ENABLED',int],
          ]

for x in myconst:
    if not settings.has_key(x[0]):
        settings[x[0]] = eval(x[0])
    else:
        if not isinstance(settings[x[0]],x[1]):
            settings[x[0]] = eval(x[0])

save_settings(settings)
