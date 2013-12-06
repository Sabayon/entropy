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
import argparse

from entropy.i18n import _
from entropy.output import darkred, darkgreen, blue

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands._manage import SoloManage

class SoloSource(SoloManage):
    """
    Main Solo Source command.
    """

    NAME = "source"
    ALIASES = ["src"]
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Download source code of packages.
"""
    SEE_ALSO = "equo-install(1)"

    def __init__(self, args):
        SoloManage.__init__(self, args)
        self._commands = {}

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloSource.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloSource.NAME))
        parser.set_defaults(func=self._source)

        parser.add_argument(
            "packages", nargs='+',
            metavar="<package>", help=_("package name"))

        mg_group = parser.add_mutually_exclusive_group()
        mg_group.add_argument(
            "--ask", "-a", action="store_true",
            default=False,
            help=_("ask before making any changes"))
        _commands["--ask"] = {}
        _commands["-a"] = {}

        mg_group.add_argument(
            "--pretend", "-p", action="store_true",
            default=False,
            help=_("show what would be done"))
        _commands["--pretend"] = {}
        _commands["-p"] = {}

        parser.add_argument(
            "--verbose", "-v", action="store_true",
            default=False,
            help=_("verbose output"))
        _commands["--verbose"] = {}
        _commands["-v"] = {}

        parser.add_argument(
            "--quiet", "-q", action="store_true",
            default=False,
            help=_("quiet output"))
        _commands["--quiet"] = {}
        _commands["-q"] = {}

        parser.add_argument(
            "--nodeps", action="store_true",
            default=False,
            help=_("exclude package dependencies"))
        _commands["--nodeps"] = {}

        parser.add_argument(
            "--onlydeps", "-o", action="store_true",
            default=False,
            help=_("only include dependencies of selected packages"))
        _commands["--onlydeps"] = {}
        _commands["-o"] = {}

        parser.add_argument(
            "--norecursive", action="store_true",
            default=False,
            help=_("do not calculate dependencies recursively"))
        _commands["--norecursive"] = {}

        parser.add_argument(
            "--deep", action="store_true",
            default=False,
            help=_("include dependencies no longer needed"))
        _commands["--deep"] = {}

        parser.add_argument(
            "--relaxed", action="store_true",
            default=False,
            help=_("calculate dependencies relaxing constraints"))
        _commands["--relaxed"] = {}

        parser.add_argument(
            "--bdeps", action="store_true",
            default=False,
            help=_("include build-time dependencies"))
        _commands["--bdeps"] = {}

        parser.add_argument(
            "--savehere", action="store_true",
            default=False,
            help=_("save files into the current working directory"))
        _commands["--savehere"] = {}

        self._commands = _commands
        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        return self._hierarchical_bashcomp(last_arg, [], self._commands)

    def _source(self, entropy_client):
        """
        Solo Source command.
        """
        ask = self._nsargs.ask
        pretend = self._nsargs.pretend
        verbose = self._nsargs.verbose
        quiet = self._nsargs.quiet
        deep = self._nsargs.deep
        deps = not self._nsargs.nodeps
        savehere = self._nsargs.savehere
        recursive = not self._nsargs.norecursive
        relaxed = self._nsargs.relaxed
        onlydeps = self._nsargs.onlydeps
        bdeps = self._nsargs.bdeps

        inst_repo = entropy_client.installed_repository()
        with inst_repo.shared():

            packages = self._scan_packages(
                entropy_client, self._nsargs.packages)
            if not packages:
                entropy_client.output(
                    "%s." % (
                        darkred(_("No packages found")),),
                    level="error", importance=1)
                return 1, False

            run_queue, removal_queue = self._generate_install_queue(
                entropy_client, packages, deps, False, deep, relaxed,
                onlydeps, bdeps, recursive)

        if (run_queue is None) or (removal_queue is None):
            return 1
        elif not (run_queue or removal_queue):
            entropy_client.output(
                "%s." % (blue(_("Nothing to do")),),
                level="warning", header=darkgreen(" @@ "))
            return 0

        if pretend:
            entropy_client.output(
                "%s." % (blue(_("All done")),))
            return 0

        total = len(run_queue)
        count = 0
        metaopts = {}
        if savehere:
            metaopts['fetch_path'] = os.getcwd()

        action_factory = entropy_client.PackageActionFactory()

        for match in run_queue:

            package_id, repository_id = match
            repo = entropy_client.open_repository(repository_id)
            atom = repo.retrieveAtom(package_id)
            count += 1
            pkg = None

            try:
                pkg = action_factory.get(
                    action_factory.SOURCE_ACTION,
                    match, opts=metaopts)

                xterm_header = "equo (%s) :: %d of %d ::" % (
                    _("sources download"), count, total)
                pkg.set_xterm_header(xterm_header)

                entropy_client.output(
                    darkgreen(atom),
                    count=(count, total),
                    header=darkred(" ::: ") + ">>> ")

                exit_st = pkg.start()
                if exit_st != 0:
                    return 1

            finally:
                if pkg is not None:
                    pkg.finalize()

        return 0


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloSource,
        SoloSource.NAME,
        _("download packages source code"))
    )
