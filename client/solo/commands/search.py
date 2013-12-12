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

from entropy.i18n import _, ngettext
from entropy.output import darkred, blue, brown, darkgreen, purple

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand, sharedlock
from solo.utils import print_table, print_package_info

import entropy.dep

class SoloSearch(SoloCommand):
    """
    Main Solo Search command.
    """

    NAME = "search"
    ALIASES = ["s"]
    ALLOW_UNPRIVILEGED = True

    INTRODUCTION = """\
Search for packages.
"""
    SEE_ALSO = ""

    def __init__(self, args, quiet=False, verbose=False, installed=False,
                 available=False, packages=None):
        SoloCommand.__init__(self, args)
        self._quiet = quiet
        self._verbose = verbose
        self._installed = installed
        self._available = available
        if packages is not None:
            self._packages = packages
        else:
            self._packages = []

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
            SoloSearch.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloSearch.NAME))

        parser.add_argument("string", nargs='+',
                            metavar="<string>", help=_("search keyword"))

        parser.add_argument("--quiet", "-q", action="store_true",
                            default=self._quiet,
                            help=_('quiet output, for scripting purposes'))

        parser.add_argument("--verbose", "-v", action="store_true",
                            default=self._verbose,
                            help=_('verbose output'))

        group = parser.add_mutually_exclusive_group()
        group.add_argument("--installed", action="store_true",
                           default=self._installed,
                           help=_('search among installed packages only'))

        group.add_argument("--available", action="store_true",
                           default=self._available,
                           help=_('search among available packages only'))

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

        self._quiet = nsargs.quiet
        self._verbose = nsargs.verbose
        self._installed = nsargs.installed
        self._available = nsargs.available
        self._packages = nsargs.string
        return self._call_shared, [self.search]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        args = [
            "--quiet", "-q", "--verbose", "-v",
            "--installed", "--available"]
        args.sort()
        return self._bashcomp(sys.stdout, last_arg, args)

    def _search_string(self, entropy_client, inst_repo, string):
        """
        Search method, returns search results.
        """
        search_data = set()
        found = False

        def _adv_search(dbconn, package):
            slot = entropy.dep.dep_getslot(package)
            tag = entropy.dep.dep_gettag(package)
            package = entropy.dep.remove_slot(package)
            package = entropy.dep.remove_tag(package)
            pkg_ids = set(dbconn.searchPackages(
                    package, slot = slot,
                    tag = tag, just_id = True, order_by = "atom"))
            if not pkg_ids: # look for something else?
                pkg_id, _rc = dbconn.atomMatch(
                    package, matchSlot = slot)
                if pkg_id != -1:
                    pkg_ids.add(pkg_id)
            return pkg_ids

        if not self._installed:
            for repo in entropy_client.repositories():
                dbconn = entropy_client.open_repository(repo)
                pkg_ids = _adv_search(dbconn, string)
                if pkg_ids:
                    found = True
                search_data.update(((x, repo) for x in pkg_ids))

        # try to actually match something in installed packages db
        if not found and (inst_repo is not None) \
            and not self._available:
            with inst_repo.shared():
                pkg_ids = _adv_search(inst_repo, string)
            if pkg_ids:
                found = True
            search_data.update(
                ((x, inst_repo.repository_id()) for x in pkg_ids))

        with inst_repo.shared():
            key_sorter = lambda x: \
                entropy_client.open_repository(x[1]).retrieveAtom(x[0])
            return sorted(search_data, key=key_sorter)

    @sharedlock
    def search(self, entropy_client, inst_repo):
        """
        Solo Search command.
        """
        if not self._quiet:
            entropy_client.output(
                "%s..." % (darkgreen(_("Searching")),),
                header=darkred(" @@ "))

        matches_found = 0
        for string in self._packages:
            results = self._search(
                entropy_client, inst_repo, string)
            matches_found += len(results)

        if not self._quiet:
            toc = []
            toc.append(("%s:" % (blue(_("Keywords")),),
                purple(', '.join(self._packages))))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                matches_found,
                brown(ngettext("entry", "entries", matches_found)),)))
            print_table(entropy_client, toc)

        if not matches_found:
            return 1
        return 0

    def _search(self, entropy_client, inst_repo, string):
        """
        Solo Search string command.
        """
        results = self._search_string(
            entropy_client, inst_repo, string)

        for pkg_id, pkg_repo in results:
            repo = entropy_client.open_repository(pkg_repo)
            print_package_info(
                pkg_id, entropy_client, repo,
                extended = self._verbose,
                installed_search = repo is inst_repo,
                quiet = self._quiet)

        return results


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloSearch,
        SoloSearch.NAME,
        _("search packages in repositories"))
    )
