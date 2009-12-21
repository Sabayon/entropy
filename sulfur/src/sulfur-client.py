#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Graphical Client}.

"""

import sys
import gtk
import gobject
sys.path.insert(0, "../../libraries")
sys.path.insert(1, "../../client")
sys.path.insert(2, "./")
sys.path.insert(3, "/usr/lib/entropy/libraries")
sys.path.insert(4, "/usr/lib/entropy/client")
sys.path.insert(5, "/usr/lib/entropy/sulfur")
import entropy.tools
from sulfur import SulfurApplication
from sulfur.dialogs import ExceptionDialog
from sulfur.setup import const

exit_status = 0
try:
    try:
        gtk.window_set_default_icon_from_file(
            const.PIXMAPS_PATH+"/sulfur-icon.png")
    except gobject.GError:
        pass
    mainApp = SulfurApplication()
    mainApp.init()
    gobject.threads_init()
    gtk.gdk.threads_enter()
    gtk.main()
    gtk.gdk.threads_leave()
    entropy.tools.kill_threads()
    mainApp.quit()
except SystemExit as e:
    entropy.tools.kill_threads()
    print("Quit by User (SystemExit)")
    try:
        mainApp.quit()
    except NameError:
        pass
    exit_status = e.code
except KeyboardInterrupt:
    entropy.tools.kill_threads()
    print("Quit by User (KeyboardInterrupt)")
    try:
        mainApp.quit()
    except NameError:
        pass
except: # catch other exception and write it to the logger.

    if "--debug" in sys.argv:
        entropy.tools.print_exception()
        import pdb
        pdb.set_trace()

    my = ExceptionDialog()
    my.show()
    entropy.tools.kill_threads()
    try:
        mainApp.quit(sysexit = False)
    except NameError:
        pass

raise SystemExit(exit_status)