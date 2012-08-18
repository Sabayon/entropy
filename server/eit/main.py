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

from eit.commands.descriptor import EitCommandDescriptor


def handle_exception(exc_class, exc_instance, exc_tb):

    # restore original exception handler, to avoid loops
    uninstall_exception_handler()
    entropy.tools.kill_threads()

    if exc_class is KeyboardInterrupt:
        raise SystemExit(1)

    # always slap exception data (including stack content)
    entropy.tools.print_exception(tb_data = exc_tb)

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__

def main():

    install_exception_handler()

    descriptors = EitCommandDescriptor.obtain()
    args_map = {}
    catch_all = None
    for descriptor in descriptors:
        klass = descriptor.get_class()
        if klass.CATCH_ALL:
            catch_all = klass
        args_map[klass.NAME] = klass
        for alias in klass.ALIASES:
            args_map[alias] = klass

    args = sys.argv[1:]
    is_bashcomp = False
    if "--bashcomp" in args:
        is_bashcomp = True
        args.remove("--bashcomp")
        # the first eit, because bash does:
        # argv -> eit --bashcomp eit add
        # and we need to drop --bashcomp and
        # argv[2]
        args.pop(0)

    cmd = None
    last_arg = None
    if args:
        last_arg = args[-1]
        cmd = args[0]
        args = args[1:]
    cmd_class = args_map.get(cmd)

    if cmd_class is None:
        cmd_class = catch_all

    cmd_obj = cmd_class(args)
    if is_bashcomp:
        try:
            cmd_obj.bashcomp(last_arg)
        except NotImplementedError:
            pass
        raise SystemExit(0)

    # non-root users not allowed
    allowed = True
    if os.getuid() != 0 and \
            cmd_class is not catch_all:
        if not cmd_class.ALLOW_UNPRIVILEGED:
            cmd_class = catch_all
            allowed = False

    func, func_args = cmd_obj.parse()
    exit_st = func(*func_args)
    if allowed:
        raise SystemExit(exit_st)
    else:
        print_error(_("superuser access required"))
        raise SystemExit(1)

