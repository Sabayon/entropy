# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import sys
import os
import argparse

from entropy.i18n import _
from entropy.output import teal, purple

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitInject(EitCommand):
    """
    Main Eit inject command.
    """

    NAME = "inject"
    ALIASES = ["fit"]

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._packages = []

    def parse(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitInject.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitInject.NAME))

        parser.add_argument("packages", nargs='+', metavar="<path>",
                            help=_("package paths"))
        parser.add_argument("--to", metavar="<repository>",
                            help=_("inject into given repository"),
                            default=None)

        try:
            nsargs = parser.parse_args(self._args)
        except IOError:
            return parser.print_help, []

        self._packages += nsargs.packages
        return self._call_locked, [self._inject, nsargs.to]

    def _inject(self, entropy_server):
        """
        Actual Eit inject code.
        """
        extensions = entropy_server.Spm_class(
            ).binary_packages_extensions()

        etp_pkg_files = []
        for pkg_path in self._packages:

            pkg_path = os.path.realpath(pkg_path)
            if not (os.path.isfile(pkg_path) and \
                        os.access(pkg_path, os.R_OK)):
                entropy_server.output(
                    "%s: %s" % (purple(pkg_path),
                                teal(_("no such file or directory"))),
                    importance=1, level="error")
                return 1

            found = False
            for ext in extensions:
                if pkg_path.endswith("."+ext):
                    etp_pkg_files.append(pkg_path)
                    found = True
                    break
            if not found:
                entropy_server.output(
                    "%s: %s" % (purple(pkg_path),
                                teal(_("unsupported extension"))),
                    importance=1, level="error")
                return 1

        if not etp_pkg_files:
            entropy_server.output(
                teal(_("no valid package paths")),
                importance=1, level="error")
            return 1

        # in this case, no split package files are provided
        repository_id = entropy_server.repository()
        etp_pkg_files = [([x], True,) for x in etp_pkg_files]
        package_ids = entropy_server.add_packages_to_repository(
            repository_id, etp_pkg_files)
        if package_ids:
            # checking dependencies and print issues
            entropy_server.extended_dependencies_test([repository_id])

        entropy_server.commit_repositories()
        if package_ids:
            return 0
        return 1


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitInject,
        EitInject.NAME,
        _('inject package files into repository'))
    )
