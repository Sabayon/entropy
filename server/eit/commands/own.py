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
from entropy.const import etpUi

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitOwn(EitCommand):
    """
    Main Eit own command.
    """

    NAME = "own"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._paths = []
        self._quiet = False
        self._repository_id = None
        # use text_query from equo library
        from text_query import search_belongs
        self._query_func = search_belongs

    def _get_parser(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitOwn.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitOwn.NAME))

        parser.add_argument("paths", nargs='+', metavar="<path>",
                            help=_("path"))

        parser.add_argument("--quiet", "-q", action="store_true",
           default=self._quiet,
           help=_('quiet output, for scripting purposes'))
        parser.add_argument("--in", metavar="<repository>",
                            help=_("search packages in given repository"),
                            dest="inrepo", default=None)

        return parser

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError:
            return parser.print_help, []

        self._quiet = nsargs.quiet
        # search_belongs uses etpUi['quiet'] augh
        etpUi['quiet'] = self._quiet
        self._paths += nsargs.paths
        self._repository_id = nsargs.inrepo
        return self._call_unlocked, [self._own, self._repository_id]

    def _own(self, entropy_server):
        """
        Actual Eit own code.
        """
        if self._repository_id is None:
            repository_ids = entropy_server.repositories()
        else:
            repository_ids = [self._repository_id]
        exit_st = 1
        for repository_id in repository_ids:
            repo = entropy_server.open_repository(repository_id)
            sts = self._query_func(self._paths, entropy_server, repo)
            if sts != 0:
                exit_st = 1
        return exit_st


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitOwn,
        EitOwn.NAME,
        _('search packages owning paths'))
    )
