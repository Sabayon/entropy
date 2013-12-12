# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import sys
import argparse

from entropy.i18n import _
from entropy.output import bold, purple, darkgreen, blue, brown, teal

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitFiles(EitCommand):
    """
    Main Eit files command.
    """

    NAME = "files"
    ALIASES = ["f"]
    ALLOW_UNPRIVILEGED = True

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._quiet = False
        self._packages = []

    def _get_parser(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitFiles.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitFiles.NAME))

        parser.add_argument("packages", nargs='+',
                            metavar="<package>",
                            help=_("package names"))
        parser.add_argument("--quiet", "-q", action="store_true",
            default=self._quiet,
            help=_('quiet output, for scripting purposes'))

        return parser

    INTRODUCTION = """\
List files owned by given package dependencies. The same, are matched against
the repositories.
For example: *>=app-foo/bar-1.2.3::repo* is asking the *bar* package, which
version at least *1.2.3*, available inside the *repo* repository.
If you want to do the inverse operation (matching a file searching for
package owners), please use *eit own*.
"""
    SEE_ALSO = "eit-own(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError:
            return parser.print_help, []

        self._quiet = nsargs.quiet
        self._packages += nsargs.packages
        return self._call_shared, [self._files, None]

    def _files(self, entropy_server):
        """
        Actual Eit files code.
        """
        exit_st = 0
        for package in self._packages:
            pkg_id, pkg_repo = entropy_server.atom_match(package)
            if pkg_id == -1:
                exit_st = 1
                if not self._quiet:
                    entropy_server.output(
                        "%s: %s" % (
                            purple(_("Not matched")), teal(package)),
                        level="warning", importance=1)
                continue

            entropy_repository = entropy_server.open_repository(pkg_repo)
            files = entropy_repository.retrieveContent(
                pkg_id, order_by="file")
            atom = entropy_repository.retrieveAtom(pkg_id)
            if self._quiet:
                for path in files:
                    entropy_server.output(path, level="generic")
            else:
                for path in files:
                    entropy_server.output(path)
                entropy_server.output(
                    "[%s] %s: %s %s" % (
                        purple(pkg_repo),
                        darkgreen(atom),
                        bold(str(len(files))),
                        teal(_("files found"))))

        return exit_st


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitFiles,
        EitFiles.NAME,
        _('show files owned by packages'))
    )
