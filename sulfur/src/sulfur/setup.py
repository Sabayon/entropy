#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
#    Sulfur (Entropy Interface)
#    Copyright: (C) 2007-2009 Fabio Erculiani < lxnay<AT>sabayonlinux<DOT>org >
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os, sys
import entropy.tools as entropyTools
from entropy.const import *
from entropy.i18n import _

class const:

    ''' This Class contains all the Constants in Yumex'''
    __sulfur_version__   = etpConst['entropyversion']
    # Paths
    MAIN_PATH = os.path.abspath( os.path.dirname( sys.argv[0] ) )
    GLADE_FILE = MAIN_PATH+'/sulfur.glade'

    if not os.path.isfile(GLADE_FILE):
        GLADE_FILE = MAIN_PATH+'/sulfur/sulfur.glade'

    if not os.path.isfile(GLADE_FILE):
        MAIN_PATH = '/usr/lib/entropy/sulfur'
        GLADE_FILE = MAIN_PATH+'/sulfur/sulfur.glade'

    if MAIN_PATH == '/usr/lib/entropy/sulfur':
        PIXMAPS_PATH = '/usr/share/pixmaps/sulfur'
    else:
        PIXMAPS_PATH = MAIN_PATH+'/../gfx'
    if MAIN_PATH == '/usr/lib/entropy/sulfur':
        ICONS_PATH = '/usr/share/pixmaps/sulfur'
    else:
        ICONS_PATH = MAIN_PATH+'/pixmaps'

    debug = '--debug' in sys.argv
    if os.getenv('SULFUR_DEBUG') is not None:
        debug = True

    home = os.getenv("HOME")
    if not home: home = "/tmp"
    SETTINGS_FILE = os.path.join(home, ".config/entropy/sulfur.conf")

    pkg_pixmap = PIXMAPS_PATH+'/package-x-generic.png'
    ugc_small_pixmap = PIXMAPS_PATH+'/ugc.png'
    ugc_pixmap = PIXMAPS_PATH+'/ugc/icon.png'
    ugc_pixmap_small = PIXMAPS_PATH+'/ugc/icon_small.png'
    refresh_pixmap = PIXMAPS_PATH+'/ugc/refresh.png'
    star_normal_pixmap = PIXMAPS_PATH+'/star.png'
    star_selected_pixmap = PIXMAPS_PATH+'/star_selected.png'
    star_half_pixmap = PIXMAPS_PATH+'/star_half.png'
    star_empty_pixmap = PIXMAPS_PATH+'/star_empty.png'
    empty_background = PIXMAPS_PATH+'/empty.png'
    loading_pix = PIXMAPS_PATH+'/loading.gif'
    loading_pix_small = PIXMAPS_PATH+'/loading_small.gif'

    # UGC
    ugc_ok_pix = PIXMAPS_PATH+'/ugc/ok.png'
    ugc_error_pix = PIXMAPS_PATH+'/ugc/error.png'
    ugc_generic_pix = PIXMAPS_PATH+'/ugc/generic.png'
    ugc_text_pix = PIXMAPS_PATH+'/ugc/text.png'
    ugc_video_pix = PIXMAPS_PATH+'/ugc/video.png'
    ugc_image_pix = PIXMAPS_PATH+'/ugc/image.png'
    ugc_view_pix = PIXMAPS_PATH+'/ugc/view.png'

    DAY_IN_SECONDS = 86400
    # Page -> Notebook page numbers
    PAGE_REPOS = 2
    PAGE_PKG = 0
    PAGE_OUTPUT = 6
    PAGE_QUEUE = 5
    PAGE_FILESCONF = 3
    PAGE_GLSA = 1
    PAGE_PREFERENCES = 4
    PAGES = {
       'packages'  : PAGE_PKG,
       'repos'     : PAGE_REPOS,
       'output'    : PAGE_OUTPUT,
       'queue'     : PAGE_QUEUE,
       'filesconf' : PAGE_FILESCONF,
       'glsa'      : PAGE_GLSA,
       'preferences': PAGE_PREFERENCES
    }

    PREF_PAGE_SYSTEM = 0
    PREF_PAGE_NETWORKING = 1
    PREF_PAGE_UGC = 2
    PREF_PAGE_COLORS = 3
    PREF_PAGES = {
        'system': PREF_PAGE_SYSTEM,
        'networking': PREF_PAGE_NETWORKING,
        'ugc': PREF_PAGE_UGC,
        'colors': PREF_PAGE_COLORS
    }

    PACKAGE_PROGRESS_STEPS = ( 0.1, # Depsolve
                               0.5, # Download
                               0.1, # Transaction Test
                               0.3 ) # Running Transaction

    SETUP_PROGRESS_STEPS = ( 0.1, # Yum Config
                             0.2, # Repo Setup
                             0.1, # Sacksetup
                             0.2, # Updates
                             0.1, # Group
                             0.3) # get package Lists

    CREDITS = (
           (('Sulfur Package Manager - %s' % __sulfur_version__),
           ('Copyright 2007-2009','Fabio Erculiani')),

           (_("Programming:"),
           ("Fabio Erculiani",)),

           (_("Translation:"),
            (
                "ca - Roger Calvò",
                "de - N/A",
                "es - Daniel Halens Rodriguez",
                "fr - Suffys Nicolas",
                "fr_CA - Benjamin Guay",
                "it - Fabio Erculiani",
                "nl - Andre Parhan",
                "pt - Lucas Paulino Azevedo",
                "ru - Maksim Belyanovskiy",
                "zh - N/A",
                )
            ),


           (_("Dedicated to:"),
                ("Sergio Erculiani",)
           )

          )


class SulfurConf:

    autorefresh = True
    recentdays = 14
    debug = False
    plugins = True
    usecache = False
    proxy = ""
    font_console = 'Monospace 8'
    font_pkgdesc = 'Monospace 8'

    color_console_font = '#FFFFFF' # black
    color_normal = '#000000' # black
    color_install = '#418C0F' # dark green
    color_update = '#418C0F' #  dark green
    color_remove = '#A71B1B' # red
    color_reinstall = '#A71B1B'
    color_downgrade = '#A71B1B'
    color_title = '#A71B1B' # red
    color_title2 = '#2A6AFF' # light blue
    # description below package atoms
    color_pkgdesc = '#FF1D1D' # red
    # description for masked packages and for pkg description in dialogs, notice board desc items
    color_pkgsubtitle = '#418C0F' # dark green
    color_subdesc = '#837350' # brown
    color_error = '#A71B1B' # red
    color_good = '#418C0F' # dark green
    color_background_good = '#418C0F' # red
    color_background_error = '#A71B1B' # dark green
    color_good_on_color_background = '#FFFFFF'
    color_error_on_color_background = '#FFFFFF'
    color_package_category = '#9C7234' # brown
    simple_mode = 1

    filelist = True
    changelog = False
    disable_repo_page = False
    branding_title = 'Sulfur'
    dummy_empty = 0
    dummy_category = 1

    @staticmethod
    def getconf_validators():

        def validate_color_conf(s):
            try:
                import gtk
                gtk.gdk.color_parse(s)
                return True
            except ValueError:
                return False

        def foo_validator(s):
            return True

        config_data = {
            "color_console_font": validate_color_conf,
            "color_normal": validate_color_conf,
            "color_install": validate_color_conf,
            "color_update": validate_color_conf,
            "color_remove": validate_color_conf,
            "color_reinstall": validate_color_conf,
            "color_downgrade": validate_color_conf,
            "color_title": validate_color_conf,
            "color_title2": validate_color_conf,
            "color_pkgdesc": validate_color_conf,
            "color_pkgsubtitle": validate_color_conf,
            "color_subdesc": validate_color_conf,
            "color_error": validate_color_conf,
            "color_good": validate_color_conf,
            "color_background_good": validate_color_conf,
            "color_background_error": validate_color_conf,
            "color_good_on_color_background": validate_color_conf,
            "color_error_on_color_background": validate_color_conf,
            "color_package_category": validate_color_conf,
            "simple_mode": foo_validator,
        }
        return config_data

    @staticmethod
    def getconf():

        config_data = {
            "color_console_font": SulfurConf.color_console_font,
            "color_normal": SulfurConf.color_normal,
            "color_install": SulfurConf.color_install,
            "color_update": SulfurConf.color_update,
            "color_remove": SulfurConf.color_remove,
            "color_reinstall": SulfurConf.color_reinstall,
            "color_downgrade": SulfurConf.color_downgrade,
            "color_title": SulfurConf.color_title,
            "color_title2": SulfurConf.color_title2,
            "color_pkgdesc": SulfurConf.color_pkgdesc,
            "color_pkgsubtitle": SulfurConf.color_pkgsubtitle,
            "color_subdesc": SulfurConf.color_subdesc,
            "color_error": SulfurConf.color_error,
            "color_good": SulfurConf.color_good,
            "color_background_good": SulfurConf.color_background_good,
            "color_background_error": SulfurConf.color_background_error,
            "color_good_on_color_background": SulfurConf.color_good_on_color_background,
            "color_error_on_color_background": SulfurConf.color_error_on_color_background,
            "color_package_category": SulfurConf.color_package_category,
            "simple_mode": SulfurConf.simple_mode,
        }
        return config_data

    @staticmethod
    def save():

        def do_save():
            if not os.path.isdir(os.path.dirname(const.SETTINGS_FILE)):
                os.makedirs(os.path.dirname(const.SETTINGS_FILE), 0755)
            myxml = entropyTools.xml_from_dict_extended(SulfurConf.getconf())
            try:
                f = open(const.SETTINGS_FILE,"w")
            except (IOError,OSError,), e:
                return False, e
            f.write(myxml+"\n")
            f.flush()
            f.close()
            return True, None

        try:
            return do_save()
        except Exception, e:
            entropyTools.print_traceback()
            return False,e
        return True,None

    @staticmethod
    def read():

        def do_read():
            if os.path.isfile(const.SETTINGS_FILE) and os.access(const.SETTINGS_FILE,os.R_OK):
                f = open(const.SETTINGS_FILE,"r")
                xml_string = f.read()
                f.close()
                return entropyTools.dict_from_xml_extended(xml_string)

        try:
            return do_read()
        except:
            entropyTools.print_traceback()
            return None

    @staticmethod
    # update config reading it from user settings
    def update():
        saved_conf = SulfurConf.read()
        validators = SulfurConf.getconf_validators()
        if not saved_conf: return
        if not isinstance(saved_conf,dict): return
        for key, val in saved_conf.items():
            if not hasattr(SulfurConf,key): continue
            vf = validators.get(key)
            if not callable(vf):
                sys.stderr.write("WARNING: SulfurConf, no callable validator for %s" % (key,))
                continue
            valid = vf(val)
            if not valid: continue
            setattr(SulfurConf,key,val)

SulfurConf.default_colors_config = SulfurConf.getconf()
SulfurConf.update()

def cleanMarkupString(msg):
    import gobject
    msg = str(msg) # make sure it is a string
    msg = gobject.markup_escape_text(msg)
    return msg

from htmlentitydefs import codepoint2name
def unicode2htmlentities(u):
   htmlentities = list()
   for c in u:
      if ord(c) < 128:
         htmlentities.append(c)
      else:
         htmlentities.append('&%s;' % codepoint2name[ord(c)])
   return ''.join(htmlentities)

class fakeoutfile:
    """
    A general purpose fake output file object.
    """

    def __init__(self, fn):
        self.fn = fn
        self.external_writer = None

    def close(self):
        pass

    def flush(self):
        pass

    def fileno(self):
        return self.fn

    def isatty(self):
        return False

    def read(self, a):
        return ''

    def readline(self):
        return ''

    def readlines(self):
        return []

    def write(self, s):
        if self.external_writer is None:
            os.write(self.fn, s)
        else:
            self.external_writer(s)

    def write_line(self, s):
        self.write(s)

    def writelines(self, l):
        for s in l:
            self.write(s)

    def seek(self, a):
        raise IOError, (29, 'Illegal seek')

    def tell(self):
        raise IOError, (29, 'Illegal seek')

    def truncate(self):
        self.tell()

class fakeinfile:
    """
    A general purpose fake input file object.
    """
    def __init__(self, fn):
        self.fn = fn
        self.text_read = ''

    def close(self):
        pass

    def flush(self):
        pass

    def fileno(self):
        return self.fn

    def isatty(self):
        return False

    def read(self, a):
        return self.readline(count = a)

    def readline(self, count = 2048):
        x = os.read(self.fn,count)
        self.text_read += x
        return x

    def readlines(self):
        return self.readline().split("\n")

    def write(self, s):
        raise IOError, (29, 'Illegal seek')

    def writelines(self, l):
        raise IOError, (29, 'Illegal seek')

    def seek(self, a):
        raise IOError, (29, 'Illegal seek')

    def tell(self):
        raise IOError, (29, 'Illegal seek')

    truncate = tell
