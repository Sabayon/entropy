#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) startup application}

"""
import os
import errno
import sys
import time
# never load entropy package here, --no-pid-handling is added below after this
# point and will cause lock stealing.

def _startup():
    sys.path.insert(0, '/usr/lib/entropy/client')
    sys.path.insert(0, '/usr/lib/entropy/lib')
    sys.path.insert(0, '/usr/lib/entropy/magneto')
    sys.path.insert(0, '../../client')
    sys.path.insert(0, '../../lib')
    sys.path.insert(0, '../')

    startup_delay = None
    for arg in sys.argv[1:]:
        if arg.startswith("--startup-delay="):
            try:
                delay = int(arg[len("--startup-delay="):])
                if delay < 1 and delay > 300:
                    raise ValueError()
                startup_delay = delay
            except ValueError:
                pass

    if startup_delay:
        time.sleep(startup_delay)

    kde_env = os.getenv("KDE_FULL_SESSION")

    if "--kde" in sys.argv:
        from magneto.kde.interfaces import Magneto
    elif "--gtk" in sys.argv:
        from magneto.gtk.interfaces import Magneto
    else:
        if kde_env is not None:
            # this is KDE!
            try:
                from magneto.kde.interfaces import Magneto
            except (ImportError, RuntimeError,):
                # try GTK
                from magneto.gtk.interfaces import Magneto
        else:
            # load GTK
            from magneto.gtk.interfaces import Magneto

    magneto = Magneto()
    try:
        magneto.startup()
        magneto.close_service()
    except KeyboardInterrupt:
        try:
            magneto.close_service()
        except:
            pass
        raise
    raise SystemExit(0)

if __name__ == "__main__":
    # acquire lock
    magneto_lock_dir = "/tmp"
    magneto_lock_file = ".magneto.lock"
    user_home = os.getenv("HOME")
    if user_home is not None:
        if os.path.isdir(user_home):
            magneto_lock_dir = user_home

    sys.argv.append('--no-pid-handling')
    import entropy.tools
    lock_map = {}
    magneto_lock = os.path.join(magneto_lock_dir, magneto_lock_file)
    acquired = entropy.tools.acquire_lock(magneto_lock, lock_map)
    try:
        if acquired:
            _startup()
        else:
            sys.stderr.write("Warning: another Magneto instance is already running.\n")
            raise SystemExit(1)
    finally:
        if acquired:
            entropy.tools.release_lock(magneto_lock, lock_map)
