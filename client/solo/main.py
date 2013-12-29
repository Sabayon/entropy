# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import sys
import errno
import pdb

from entropy.i18n import _
from entropy.output import print_error, print_warning, bold, purple, \
    teal, blue, darkred, darkgreen, readtext, print_generic, TextInterface, \
    is_stdout_a_tty, nocolor
from entropy.const import etpConst, const_convert_to_rawstring, \
    const_convert_to_unicode, const_debug_enabled, const_mkstemp
from entropy.exceptions import SystemDatabaseError, OnlineMirrorError, \
    RepositoryError, PermissionDenied, FileNotFound, SPMError

import entropy.tools

from solo.commands.descriptor import SoloCommandDescriptor
from solo.utils import read_client_release

def handle_exception(exc_class, exc_instance, exc_tb):

    # restore original exception handler, to avoid loops
    uninstall_exception_handler()

    _text = TextInterface()

    if exc_class is SystemDatabaseError:
        _text.output(
            darkred(_("Installed packages repository corrupted. "
              "Please re-generate it")),
            importance=1,
            level="error")
        os._exit(101)

    generic_exc_classes = (OnlineMirrorError, RepositoryError,
        PermissionDenied, FileNotFound, SPMError, SystemError)
    if exc_class in generic_exc_classes:
        _text.output(
            "%s: %s" % (exc_instance, darkred(_("Cannot continue")),),
            importance=1,
            level="error")
        os._exit(1)

    if exc_class is SystemExit:
        return

    if exc_class is IOError:
        if exc_instance.errno != errno.EPIPE:
            return

    if exc_class is KeyboardInterrupt:
        os._exit(1)

    t_back = entropy.tools.get_traceback(tb_obj = exc_tb)
    if const_debug_enabled():
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        sys.stdin = sys.__stdin__
        entropy.tools.print_exception(tb_data = exc_tb)
        pdb.set_trace()

    if exc_class is OSError:
        if exc_instance.errno == errno.ENOSPC:
            print_generic(t_back)
            _text.output(
                "%s: %s" % (
                    exc_instance,
                    darkred(_("Your hard drive is full! Your fault!")),),
                importance=1,
                level="error")
            os._exit(5)
        elif exc_instance.errno == errno.ENOMEM:
            print_generic(t_back)
            _text.output(
                "%s: %s" % (
                    exc_instance,
                    darkred(_("No more memory dude! Your fault!")),),
                importance=1,
                level="error")
            os._exit(5)

    _text.output(
        darkred(_("Hi. My name is Bug Reporter. "
          "I am sorry to inform you that the program crashed. "
          "Well, you know, shit happens.")),
        importance=1,
        level="error")
    _text.output(
        darkred(_("But there's something you could "
                  "do to help me to be a better application.")),
        importance=1,
        level="error")
    _text.output(
        darkred(
            _("-- BUT, DO NOT SUBMIT THE SAME REPORT MORE THAN ONCE --")),
        importance=1,
        level="error")
    _text.output(
        darkred(
            _("Now I am showing you what happened. "
              "Don't panic, I'm here to help you.")),
        importance=1,
        level="error")

    entropy.tools.print_exception(tb_data = exc_tb)

    exception_data = entropy.tools.print_exception(silent = True,
        tb_data = exc_tb, all_frame_data = True)
    exception_tback_raw = const_convert_to_rawstring(t_back)

    error_fd, error_file = None, None
    try:
        error_fd, error_file = const_mkstemp(
            prefix="entropy.error.report.",
            suffix=".txt")

        with os.fdopen(error_fd, "wb") as ferror:
            ferror.write(
                const_convert_to_rawstring(
                    "\nRevision: %s\n\n" % (
                        etpConst['entropyversion'],))
                )
            ferror.write(
                exception_tback_raw)
            ferror.write(
                const_convert_to_rawstring("\n\n"))
            ferror.write(
                const_convert_to_rawstring(''.join(exception_data)))
            ferror.write(
                const_convert_to_rawstring("\n"))

    except (OSError, IOError) as err:
        _text.output(
            "%s: %s" % (
                err,
                darkred(
                    _("Oh well, I cannot even write to TMPDIR. "
                      "So, please copy the error and "
                      "mail lxnay@sabayon.org."))),
            importance=1,
            level="error")
        os._exit(1)
    finally:
        if error_fd is not None:
            try:
                os.close(error_fd)
            except OSError:
                pass

    _text.output("", level="error")

    ask_msg = _("Erm... Can I send the error, "
                "along with some other information\nabout your "
                "hardware to my creators so they can fix me? "
                "(Your IP will be logged)")
    rc = _text.ask_question(ask_msg)
    if rc == _("No"):
        _text.output(
            darkgreen(_("Ok, ok ok ok... Sorry!")),
            level="error")
        os._exit(2)

    _text.output(
        darkgreen(
            _("If you want to be contacted back "
              "(and actively supported), also answer "
              "the questions below:")
            ),
        level="error")

    try:
        name = readtext(_("Your Full name:"))
        email = readtext(_("Your E-Mail address:"))
        description = readtext(_("What you were doing:"))
    except EOFError:
        os._exit(2)

    try:
        from entropy.client.interfaces.qa import UGCErrorReport
        from entropy.core.settings.base import SystemSettings
        _settings = SystemSettings()
        repository_id = _settings['repositories']['default_repository']
        error = UGCErrorReport(repository_id)
    except (OnlineMirrorError, AttributeError, ImportError,):
        error = None

    result = None
    if error is not None:
        error.prepare(exception_tback_raw, name, email,
            '\n'.join([x for x in exception_data]), description)
        result = error.submit()

    if result:
        _text.output(
            darkgreen(
                _("Thank you very much. The error has been "
                  "reported and hopefully, the problem will "
                  "be solved as soon as possible.")),
            level="error")
    else:
        _text.output(
            darkred(_("Ugh. Cannot send the report. "
                      "Please mail the file below "
                      "to lxnay@sabayon.org.")),
            level="error")
        _text.output("", level="error")
        _text.output("==> %s" % (error_file,), level="error")
        _text.output("", level="error")

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__

def warn_version_mismatch():
    equo_ver = read_client_release()
    entropy_ver = etpConst['entropyversion']
    if equo_ver != entropy_ver:
        print_warning("")
        print_warning("%s: %s" % (
            bold(_("Entropy/Equo version mismatch")),
            purple(_("it could make your system explode!")),))
        print_warning("(%s [equo] & %s [entropy])" % (
            blue(equo_ver),
            blue(entropy_ver),))
        print_warning("")

def warn_live_system():
    print_warning("")
    print_warning(
        purple(_("Entropy is running off a Live System")))
    print_warning(
        teal(_("Performance and stability could get"
             " severely compromised")))
    print_warning("")

def main():

    is_color = "--color" in sys.argv
    if is_color:
        sys.argv.remove("--color")

    if not is_color and not is_stdout_a_tty():
        nocolor()

    warn_version_mismatch()

    install_exception_handler()

    descriptors = SoloCommandDescriptor.obtain()
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
        # argv -> equo --bashcomp equo repo
        # and we need to drop --bashcomp and
        # argv[2]
        if args:
            args.pop(0)

    cmd = None
    last_arg = None
    if args:
        last_arg = args[-1]
        cmd = args[0]
        args = args[1:]
    cmd_class = args_map.get(cmd)
    yell_class = args_map.get("yell")

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
            cmd_class is not catch_all and \
            not cmd_class.ALLOW_UNPRIVILEGED and \
            "--help" not in args:
            cmd_class = catch_all
            allowed = False

    if allowed:

        if not cmd_class.ALLOW_UNPRIVILEGED:
            if entropy.tools.islive():
                warn_live_system()

        func, func_args = cmd_obj.parse()
        exit_st = func(*func_args)
        if exit_st == -10:
            # syntax error, yell at user
            func, func_args = yell_class(args).parse()
            func(*func_args)
            raise SystemExit(10)
        else:
            yell_class.reset()
        raise SystemExit(exit_st)

    else:
        # execute this anyway so that commands are
        # incomplete or invalid, the command error
        # message will take precedence.
        _func, _func_args = cmd_obj.parse()
        print_error(_("superuser access required"))
        raise SystemExit(1)
