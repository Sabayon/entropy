# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import sys
import argparse
import time

from entropy.i18n import _
from entropy.output import blue, darkred, brown, purple, teal, darkgreen

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.install import SoloInstall

class SoloLibtest(SoloInstall):
    """
    Main Solo Libtest command.
    """

    NAME = "libtest"
    ALIASES = ["lt"]
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Test system integrity by looking for missing libraries.
"""
    SEE_ALSO = "equo-libtest(1)"

    def __init__(self, args):
        SoloInstall.__init__(self, args)
        self._nsargs = None
        self._commands = []

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloLibtest.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloLibtest.NAME))

        _commands = []
        parser.add_argument("--ask", "-a", action="store_true",
                            default=False,
                            help=_("ask before making any changes"))
        _commands.append("--ask")
        _commands.append("-a")

        parser.add_argument("--quiet", "-q", action="store_true",
                            default=False,
                            help=_("show less details "
                                   "(useful for scripting)"))
        _commands.append("--quiet")
        _commands.append("-q")

        parser.add_argument("--pretend", "-p", action="store_true",
                            default=False,
                            help=_("just show what would be done"))
        _commands.append("--pretend")
        _commands.append("-p")

        parser.add_argument("--listfiles", action="store_true",
                            default=False,
                            help=_("print broken files to stdout"))
        _commands.append("--listfiles")

        parser.add_argument("--dump", action="store_true",
                            default=False,
                            help=_("dump results to files"))
        _commands.append("--dump")

        self._commands = _commands
        return parser

    def parse(self):
        """
        Parse command
        """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_shared, [self._test]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        return self._bashcomp(sys.stdout, last_arg, self._commands)

    def _test(self, entropy_client):
        """
        Command implementation.
        """
        ask = self._nsargs.ask
        quiet = self._nsargs.quiet
        pretend = self._nsargs.pretend
        listfiles = self._nsargs.listfiles
        dump = self._nsargs.dump
        inst_repo = entropy_client.installed_repository()

        if listfiles:
            quiet = True

        qa = entropy_client.QA()

        with inst_repo.shared():
            pkgs_matched, brokenlibs, exit_st = qa.test_shared_objects(
                inst_repo, dump_results_to_file=dump, silent=quiet)
            if exit_st != 0:
                return 1

        if listfiles:
            for lib in brokenlibs:
                entropy_client.output(lib, level="generic")
            return 0

        if not (brokenlibs or pkgs_matched):
            if not quiet:
                entropy_client.output(
                    "%s." % (
                        blue(_("System is healthy")),),
                    header=darkred(" @@ "))
            return 0

        if pkgs_matched:

            # filter out reinstalls
            def _reinstall_filter(_match):
                _action = entropy_client.get_package_action(_match)
                if _action == 0:
                    # maybe notify this to user in future?
                    return False
                return True

            with inst_repo.shared():  # due to get_package_action
                for mylib in list(pkgs_matched.keys()):
                    pkgs_matched[mylib] = list(
                        filter(_reinstall_filter, pkgs_matched[mylib])
                    )
                    if not pkgs_matched[mylib]:
                        pkgs_matched.pop(mylib)

        if quiet:
            for mylib in pkgs_matched:
                for package_id, repository_id in pkgs_matched[mylib]:
                    repo = entropy_client.open_repository(
                        repository_id)
                    atom = repo.retrieveAtom(package_id)
                    entropy_client.output(atom, level="generic")
            return 0

        if not (brokenlibs or pkgs_matched):
            entropy_client.output(
                "%s." % (
                    blue(_("System is healthy")),),
                header=darkred(" @@ "))
            return 0

        entropy_client.output(
            "%s:" % (
                purple(_("Libraries/Executables statistics")),),
            header=darkgreen(" @@ "))

        if brokenlibs:
            entropy_client.output(
                "%s:" % (
                    teal(_("Not matched")),),
                header=brown(" ## "))
            brokenlibs = sorted(brokenlibs)

            for lib in brokenlibs:
                entropy_client.output(
                    brown(lib),
                    header=purple("    => "))

        package_matches = set()
        if pkgs_matched:
            entropy_client.output(
                "%s:" % (
                    teal(_("Matched")),),
                header=brown(" ## "))

            for mylib in pkgs_matched:
                for package_id, repository_id in pkgs_matched[mylib]:
                    repo = entropy_client.open_repository(
                        repository_id)
                    atom = repo.retrieveAtom(package_id)
                    package_matches.add((package_id, repository_id))
                    entropy_client.output(
                        "%s => %s [%s]" % (
                            darkgreen(mylib),
                            teal(atom),
                            purple(repository_id),),
                        header="   ")

        if pretend:
            return 0

        exit_st = 0
        if package_matches:
            if ask:
                exit_st = entropy_client.ask_question(
                    "     %s" % (_("Would you like to install them ?"),)
                    )
                if exit_st == _("No"):
                    return 1
            else:
                mytxt = "%s %s %s" % (
                    blue(_("Installing available packages in")),
                    darkred(_("10 seconds")),
                    blue("..."),
                )
                entropy_client.output(
                    mytxt, header=darkred(" @@ "))
                time.sleep(10)

            exit_st, _show_cfgupd = self._install_action(
                entropy_client, True, True,
                pretend, ask, False, quiet, False,
                False, False, False, False, False,
                False, 1, [],
                package_matches=package_matches)

        return exit_st


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloLibtest,
        SoloLibtest.NAME,
        _("look for missing libraries"))
    )
