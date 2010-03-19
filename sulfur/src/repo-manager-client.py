# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Graphical Repository Administration tool}.

"""

# Base Python Imports
import sys
# Entropy Imports
if "--debugdev" not in sys.argv:
    sys.path.insert(0, "/usr/lib/entropy/repoman")
    sys.path.insert(0, "/usr/lib/entropy/sulfur")
    sys.path.insert(0, "/usr/lib/entropy/client")
    sys.path.insert(0, "/usr/lib/entropy/libraries")
sys.path.insert(0, "../../libraries")
sys.path.insert(0, "../../client")
sys.path.insert(0, "sulfur")
sys.path.insert(0, "repoman")

# Sulfur Imports
import gtk, gobject
from sulfur.setup import const
from sulfur.dialogs import ExceptionDialog
from sulfur.entropyapi import Equo
from repoman import RepositoryManagerMenu

class MyRepositoryManager(RepositoryManagerMenu):

    def __init__(self, equo, parent):
        RepositoryManagerMenu.__init__(self, equo, parent)

    def on_repoManagerClose_clicked(self, *args, **kwargs):
        self.QueueUpdater.kill()
        self.OutputUpdater.kill()
        self.PinboardUpdater.kill()
        self.destroy()
        raise SystemExit(1)

class ManagerApplication:

    def __init__(self):
        self._entropy = Equo()
        self.ui = None
        self.progress_log_write = sys.stdout
        self.std_output = sys.stdout
        self.progress = None
        self._entropy.connect_to_gui(self)

    def init(self):
        mymenu = MyRepositoryManager(self._entropy, None)
        rc_status = mymenu.load()
        if not rc_status:
            del mymenu
            raise SystemExit(1)

    def destroy(self):
        self._entropy.destroy()

    def dummy_func(self, *args, **kwargs):
        pass

if __name__ == "__main__":

    try:
        try:
            gtk.window_set_default_icon_from_file(
                const.PIXMAPS_PATH+"/sulfur-icon.png")
        except gobject.GError:
            pass
        main_app = ManagerApplication()
        main_app.init()
        gobject.threads_init()
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()
        from sulfur.entropyapi import Equo
        Equo().destroy()
    except SystemExit:
        print("Quit by User")
        main_app.destroy()
        raise SystemExit(0)
    except KeyboardInterrupt:
        print("Quit by User (KeyboardInterrupt)")
        main_app.destroy()
        raise SystemExit(0)
    except: # catch other exception and write it to the logger.
        my = ExceptionDialog()
        my.show()

    raise SystemExit(0)
