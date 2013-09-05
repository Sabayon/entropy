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
from entropy.const import etpConst, const_convert_to_unicode
from entropy.output import print_error
import entropy.tools

from entropy.exceptions import OnlineMirrorError
from eit.commands.descriptor import EitCommandDescriptor


def handle_exception(exc_class, exc_instance, exc_tb):

    # restore original exception handler, to avoid loops
    uninstall_exception_handler()
    entropy.tools.kill_threads()

    if exc_class is KeyboardInterrupt:
        os._exit(1)

    if exc_class is OnlineMirrorError:
        print_error("Mirror error: %s" % (
                exc_instance,))
        os._exit(1)

    # always slap exception data (including stack content)
    entropy.tools.print_exception(tb_data=exc_tb, all_frame_data=True)

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
    # convert args to unicode, to avoid passing
    # raw string stuff down to entropy layers
    def _to_unicode(arg):
        try:
            return const_convert_to_unicode(
                arg, enctype=etpConst['conf_encoding'])
        except UnicodeDecodeError:
            print_error("invalid argument: %s" % (arg,))
            raise SystemExit(1)
    args = list(map(_to_unicode, args))

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
    if allowed:
        exit_st = func(*func_args)
        raise SystemExit(exit_st)
    else:
        print_error(_("superuser access required"))
        raise SystemExit(1)
