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
from entropy.output import purple, darkgreen, teal, bold

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand
from eit.utils import print_package_info


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
        self._verbose = False
        self._repository_id = None

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
        parser.add_argument("--verbose", "-v", action="store_true",
           default=self._verbose,
           help=_('output more package info'))
        parser.add_argument("--in", metavar="<repository>",
                            help=_("search packages in given repository"),
                            dest="inrepo", default=None)

        return parser

    INTRODUCTION = """\
List packages owning given file paths.
Paths are searched through all the currently available repositories,
even though you can restrict the search to a certain repository by using
the *--in* argument.
If you want to do the inverse operation (listing files owned by packages),
please use *eit files*.
"""
    SEE_ALSO = "eit-files(1)"

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
        self._quiet = nsargs.quiet
        self._paths += nsargs.paths
        self._repository_id = nsargs.inrepo
        return self._call_shared, [self._own, self._repository_id]

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
            sts = self._search(entropy_server, repository_id, repo)
            if sts != 0:
                exit_st = 1
        return exit_st

    def _search(self, entropy_server, repository_id, repo):

        results = {}
        flatresults = {}
        reverse_symlink_map = self._settings()['system_rev_symlinks']
        for xfile in self._paths:
            results[xfile] = set()
            pkg_ids = repo.searchBelongs(xfile)
            if not pkg_ids:
                # try real path if possible
                pkg_ids = repo.searchBelongs(os.path.realpath(xfile))
            if not pkg_ids:
                # try using reverse symlink mapping
                for sym_dir in reverse_symlink_map:
                    if xfile.startswith(sym_dir):
                        for sym_child in reverse_symlink_map[sym_dir]:
                            my_file = sym_child+xfile[len(sym_dir):]
                            pkg_ids = repo.searchBelongs(my_file)
                            if pkg_ids:
                                break

            for pkg_id in pkg_ids:
                if not flatresults.get(pkg_id):
                    results[xfile].add(pkg_id)
                    flatresults[pkg_id] = True

        if results:
            key_sorter = lambda x: repo.retrieveAtom(x)
            for result in results:

                # print info
                xfile = result
                result = results[result]

                for pkg_id in sorted(result, key = key_sorter):
                    if self._quiet:
                        entropy_server.output(
                            repo.retrieveAtom(pkg_id),
                            level="generic")
                    else:
                        print_package_info(pkg_id, entropy_server,
                                     repo, installed_search = True,
                                     extended = self._verbose,
                                     quiet = self._quiet)

                if not self._quiet:
                    entropy_server.output(
                        "[%s] %s: %s %s" % (
                            purple(repository_id),
                            darkgreen(xfile),
                            bold(str(len(result))),
                            teal(_("packages found"))))

        return 0


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitOwn,
        EitOwn.NAME,
        _('search packages owning paths'))
    )
