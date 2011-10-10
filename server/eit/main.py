# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import os
import sys
import argparse

from entropy.i18n import _
from entropy.output import print_error
import entropy.tools

from eit.commands.status import EitStatus
from eit.commands.help import EitHelp
from eit.commands.commit import EitCommit
from eit.commands.add import EitAdd


def handle_exception(exc_class, exc_instance, exc_tb):

    # restore original exception handler, to avoid loops
    uninstall_exception_handler()
    entropy.tools.kill_threads()

    if exc_class is KeyboardInterrupt:
        raise SystemExit(1)

    # always slap exception data (including stack content)
    entropy.tools.print_exception(tb_data = exc_tb)

    raise exc_instance

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__

def main():

    install_exception_handler()

    args_map = {
        EitHelp.NAME: EitHelp,
        "-h": EitHelp,
        "--help": EitHelp,
        EitStatus.NAME: EitStatus,
        EitCommit.NAME: EitCommit,
        EitAdd.NAME: EitAdd,
    }

    args = sys.argv[1:]
    cmd = None
    if args:
        cmd = args[0]
        args = args[1:]
    cmd_class = args_map.get(cmd)

    if cmd_class is None:
        cmd_class = args_map.get(EitHelp.NAME)

    # non-root users not allowed
    allowed = True
    if os.getuid() != 0 and \
            cmd_class is not EitHelp:
        cmd_class = EitHelp
        allowed = False

    cmd_obj = cmd_class(args)
    func, func_args = cmd_obj.parse()
    exit_st = func(*func_args)
    if allowed:
        raise SystemExit(exit_st)
    else:
        print_error(_("superuser access required"))
        raise SystemExit(1)

