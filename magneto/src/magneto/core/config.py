"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) configuration module}

"""
import os
import entropy.dump

ICON_PATH = os.getenv("MAGNETO_ICON_PATH", "/usr/share/magneto/icons")
DATA_DIR = os.getenv("MAGNETO_DATA_DIR", "/usr/share/magneto")
PIXMAPS_PATH = os.getenv("MAGNETO_PIXMAPS_PATH", "/usr/share/pixmaps/magneto")

APPLET_STATES = [ "STARTUP", "NOCONSENT", "CONFIGURING", "OKAY",
    "CRITICAL", "BUSY", "ERROR", "DISCONNECTED", "DISABLE" ]
APPLET_MENUS = [ "about", "update_now", "web_panel", "web_site",
    "configure_applet", "check_now" ]

APPLET_SENSITIVE_MENU = {
    "STARTUP": [ "" ],
    "NOCONSENT": [ "about", "configure_applet", "update_now", "busy" ],
    "CONFIGURING": [ "about", "update_now" ],
    "OKAY": APPLET_MENUS,
    "CRITICAL": APPLET_MENUS,
    "BUSY": [ ],
    "ERROR": [ "about", "update_now", "check_now" ],
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
    ".config/entropy/magneto.conf")

def save_settings(settings):
    global SETTINGS_FILE
    try:
        if not os.path.isdir(os.path.dirname(SETTINGS_FILE)):
            os.makedirs(os.path.dirname(SETTINGS_FILE))
        entropy.dump.dumpobj(SETTINGS_FILE, settings, complete_path = True)
    except:
        pass

settings = entropy.dump.loadobj(SETTINGS_FILE, complete_path = True)
if settings == None:
    settings = {}

myconst = [
            ['ERROR_THRESHOLD', int],
            ['ANIMATION_TOTAL_TIME', float],
            ['APPLET_ENABLED', int],
          ]

for x in myconst:
    if x[0] not in settings:
        settings[x[0]] = eval(x[0])
    else:
        if not isinstance(settings[x[0]], x[1]):
            settings[x[0]] = eval(x[0])

save_settings(settings)
