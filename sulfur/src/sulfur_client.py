#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Graphical Client}.

"""
import os
import sys
import signal
import atexit

import gtk
import gobject

sys.path.insert(0, "../../libraries")
sys.path.insert(1, "../../client")
sys.path.insert(2, "./")
sys.path.insert(3, "/usr/lib/entropy/libraries")
sys.path.insert(4, "/usr/lib/entropy/client")
sys.path.insert(5, "/usr/lib/entropy/sulfur")
import entropy.tools
from entropy.exceptions import PermissionDenied
from sulfur import SulfurApplication
from sulfur.dialogs import ExceptionDialog
from sulfur.setup import const
from sulfur.core import FORK_PIDS

MAIN_APP = None

def kill_pid(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass

def kill_threads():
    entropy.tools.kill_threads()
    for pid in FORK_PIDS:
        kill_pid(pid)

"""
debug options:
    --debug => make debug output to be printed to stdout
    --debug-catch => catch exceptions (after the error reporter) and
                     start the Python Debugger
    --nougc => disable UGC
    --locked => start the application in "locked" mode
    --maximize => maximize application on load
    --nonoticeboard => disable noticeboard popup
    --advanced => start application in advanced mode
"""

def handle_exception(exc_class, exc_instance, exc_tb):

    # restore original exception handler, to avoid loops
    uninstall_exception_handler()

    if exc_class is KeyboardInterrupt:
        kill_threads()
        print("Quit by User (KeyboardInterrupt)")
        if MAIN_APP is not None:
            MAIN_APP.quit()
        raise SystemExit(0)

    if exc_class is SystemExit:
        kill_threads()
        print("Quit by User (SystemExit)")
        if MAIN_APP is not None:
            MAIN_APP.quit()
        exit_status = exc_instance.code
        raise SystemExit(exit_status)

    submitmsg = entropy.tools.get_traceback(tb_obj = exc_tb)
    t_back = submitmsg + "\n"
    t_back += ''.join(entropy.tools.print_exception(silent = True,
        tb_data = exc_tb))

    if "--debug-catch" in sys.argv:
        print(t_back)
        import pdb
        pdb.set_trace()

    exc_data = entropy.tools.print_exception(silent = True,
        tb_data = exc_tb, all_frame_data = True)

    my = ExceptionDialog()
    my.show(errmsg = t_back, submitmsg = submitmsg, exc_data = exc_data)
    kill_threads()
    if MAIN_APP is not None:
        MAIN_APP.quit(sysexit = -1)
    raise SystemExit(1)

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__

install_exception_handler()
try:
    gtk.window_set_default_icon_from_file(
        const.PIXMAPS_PATH+"/sulfur-icon.png")
except gobject.GError:
    pass

OLD_TERM_SIGNAL_HANDLER = None
def term_signal_thread_killer(*args, **kwargs):
    kill_threads()
    if OLD_TERM_SIGNAL_HANDLER is not None:
        return OLD_TERM_SIGNAL_HANDLER(*args, **kwargs)

def install_term_signal_handler():
    global OLD_TERM_SIGNAL_HANDLER
    old_handler = signal.signal(signal.SIGTERM, term_signal_thread_killer)
    OLD_TERM_SIGNAL_HANDLER = old_handler

def startup():
    global MAIN_APP
    install_term_signal_handler()
    try:
        MAIN_APP = SulfurApplication()
    except PermissionDenied:
        # another entropy is running
        raise SystemExit(1)
    MAIN_APP.init()
    atexit.register(kill_threads)
    #import cProfile
    #MAIN_APP._entropy.clear_cache()
    #MAIN_APP.etpbase.clear_groups()
    #MAIN_APP.etpbase.clear_cache()
    #cProfile.run("MAIN_APP.setup_application()")
    #raise SystemExit(1)
    gobject.threads_init()
    gtk.gdk.threads_enter()
    gtk.main()
    gtk.gdk.threads_leave()
    kill_threads()
    app = MAIN_APP
    MAIN_APP = None
    app.quit()

if __name__ == "__main__":
    startup()
    raise SystemExit(0)
