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

class SoloDownload(SoloManage):
    """
    Main Solo Download command.
    """

    NAME = "download"
    ALIASES = ["fetch"]
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Download packages, essentially.
"""
    SEE_ALSO = "equo-source(1)"

    def __init__(self, args):
        SoloManage.__init__(self, args)
        self._commands = {}

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloDownload.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloDownload.NAME))
        parser.set_defaults(func=self._download)

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
            "--quiet", action="store_true",
            default=False,
            help=_("quiet output"))
        _commands["--quiet"] = {}

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
            "--multifetch",
            type=int, default=1,
            choices=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            help=_("download multiple packages in parallel (max 10)"))
        _commands["--multifetch"] = {}

        self._commands = _commands
        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        return self._hierarchical_bashcomp(last_arg, [], self._commands)

    def _download(self, entropy_client):
        """
        Solo Download command.
        """
        ask = self._nsargs.ask
        pretend = self._nsargs.pretend
        verbose = self._nsargs.verbose
        quiet = self._nsargs.quiet
        deep = self._nsargs.deep
        deps = not self._nsargs.nodeps
        recursive = not self._nsargs.norecursive
        relaxed = self._nsargs.relaxed
        onlydeps = self._nsargs.onlydeps
        bdeps = self._nsargs.bdeps
        multifetch = self._nsargs.multifetch

        inst_repo = entropy_client.installed_repository()
        with inst_repo.shared():

            packages = self._scan_packages(
                entropy_client, self._nsargs.packages)
            if not packages:
                entropy_client.output(
                    "%s." % (
                        darkred(_("No packages found")),),
                    level="error", importance=1)
                return 1

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

        down_data = {}
        exit_st = self._download_packages(
            entropy_client, run_queue, down_data, multifetch)

        if exit_st == 0:
            self._signal_ugc(entropy_client, down_data)
        return exit_st


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloDownload,
        SoloDownload.NAME,
        _("download packages, essentially"))
    )
