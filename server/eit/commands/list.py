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
from entropy.output import brown, teal, purple, darkgreen

import entropy.dep

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitList(EitCommand):
    """
    Main Eit list command.
    """

    NAME = "list"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._repositories = []
        self._quiet = False
        self._verbose = False
        self._injected = False

    def _get_parser(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitList.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitList.NAME))

        parser.add_argument("repo", nargs='+', default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--quiet", "-q", action="store_true",
           default=self._quiet,
           help=_('quiet output, for scripting purposes'))
        parser.add_argument("--verbose", "-v", action="store_true",
           default=self._verbose,
           help=_('output more package info'))
        parser.add_argument("--injected", action="store_true",
           default=self._injected,
           help=_('only list injected packages'))

        return parser

    INTRODUCTION = """\
List packages in given repositories.
If you wonder what's inside a repository, you've found the right tool.
"""

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._quiet = nsargs.quiet
        self._verbose = nsargs.verbose
        self._injected = nsargs.injected
        self._repositories += nsargs.repo
        return self._call_shared, [self._list, None]

    def _list(self, entropy_server):
        rc = 0
        avail_repos = entropy_server.repositories()
        not_avail =  [x for x in self._repositories if \
                          x not in avail_repos]
        if not_avail:
            entropy_server.output(
                "%s %s" % (brown(not_avail[0]),
                           purple(_("not available"))),
                importance=1, level="error")
            return 1

        for repository_id in self._repositories:
            self._list_packages(entropy_server, repository_id)
        return 0

    def _list_packages(self, entropy_server, repository_id):
        """
        Actually do the freaking package listing and stfu.
        """
        entropy_repository = entropy_server.open_repository(repository_id)
        pkg_ids = entropy_repository.listAllPackageIds(order_by = "atom")
        if self._injected:
            pkg_ids = [x for x in pkg_ids if \
                           entropy_repository.isInjected(x)]

        for pkg_id in pkg_ids:
            atom = entropy_repository.retrieveAtom(pkg_id)
            if atom is None:
                continue
            if not self._verbose:
                atom = entropy.dep.dep_getkey(atom)

            branchinfo = ""
            sizeinfo = ""
            if self._verbose:
                branch = entropy_repository.retrieveBranch(pkg_id)
                branchinfo = darkgreen("[")+teal(branch)+darkgreen("]")
                mysize = entropy_repository.retrieveOnDiskSize(pkg_id)
                mysize = entropy.tools.bytes_into_human(mysize)
                sizeinfo = brown("[")+purple(mysize)+brown("]")

            if not self._quiet:
                entropy_server.output(
                    "%s %s %s" % (
                        atom, sizeinfo, branchinfo),
                    header="")
            else:
                entropy_server.output(atom, level="generic")

        if not pkg_ids and not self._quiet:
            entropy_server.output(
                darkgreen(_("No packages")),
                header=brown(" @@ "))


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitList,
        EitList.NAME,
        _("show repository content (packages)"))
    )
