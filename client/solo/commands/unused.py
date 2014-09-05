# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @author: Slawomir Nizio <slawomir.nizio@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani, Slawomir Nizio
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import sys
import argparse

from entropy.i18n import _
from entropy.const import etpConst
from entropy.misc import Lifo
from entropy.output import red, blue, brown, darkgreen

import entropy.tools

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand, sharedlock


class SoloUnused(SoloCommand):
    """
    Main Solo Unused command.
    """

    NAME = "unusedpackages"
    ALIASES = ["unused"]
    ALLOW_UNPRIVILEGED = True

    INTRODUCTION = """\
Report unused packages that could be removed.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._quiet = False
        self._sortbysize = False
        self._spm_wanted = False
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
        _commands = []
        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloUnused.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloUnused.NAME))

        parser.add_argument("--quiet", "-q", action="store_true",
                            default=self._quiet,
                            help=_("show less details (useful for scripting)"))
        _commands.append("--quiet")
        _commands.append("-q")

        parser.add_argument("--sortbysize", action="store_true",
                            default=self._sortbysize,
                            help=_("sort packages by size"))
        _commands.append("--sortbysize")

        # XXX: spm-db is recorded by 'equo rescue spmsync' and probably also 'equo generate.'
        # XXX: Are there any other cases to consider? SPM package installed differently, somehow?
        parser.add_argument("--spm-wanted", action="store_true",
                            default=self._spm_wanted,
                            help=_("consider packages installed with" \
                                   " a Source Package Manager to be wanted"))
        _commands.append("--spm-wanted")

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

        self._quiet = nsargs.quiet
        self._sortbysize = nsargs.sortbysize
        self._spm_wanted = nsargs.spm_wanted

        return self._call_shared, [self._unused]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        import sys

        self._get_parser()
        return self._bashcomp(sys.stdout, last_arg, self._commands)

    def _installed_pkg_ids(self, entropy_repository):
        """
        Return IDs list of packages from a given repository.
        """
        repository_id = entropy_repository.repository_id()
        return entropy_repository.listAllPackageIds()

    def _filter_user_packages(self, inst_repo, pkg_ids):
        """
        For a given repository and package IDs, return only
        the IDs of packages that are marked as being installed
        by user, and optionally also packages installed using
        SPM.
        """
        def _filter_user(pkg_id):
            return inst_repo.getInstalledPackageSource(pkg_id) == \
                    etpConst['install_sources']['user']

        def _filter_user_or_by_SPM(pkg_id):
            if _filter_user(pkg_id):
                return True

            # XXX: Should I also compare spmetprev?
            repo = inst_repo.getInstalledPackageRepository(x)
            if repo is None:
                # sensible default
                return False
            else:
                return repo == etpConst['spmdbid']

        if self._spm_wanted:
            filter_func = _filter_user_or_by_SPM
        else:
            filter_func = _filter_user

        return frozenset([x for x in pkg_ids if filter_func(x)])

    def _get_flat_deps(self, ids_to_check, get_deps_func):
        """
        Return a set (frozenset) of package IDs that are dependencies
        of provided packages, recursively.
        """
        stack = Lifo()

        result_deps = set()

        for pkg_id in ids_to_check:
            stack.push(pkg_id)

        while stack.is_filled():
            pkg_id = stack.pop()
            if pkg_id in result_deps:
                continue

            result_deps.add(pkg_id)

            for dep_id in get_deps_func(pkg_id):
                if dep_id not in result_deps:
                    stack.push(dep_id)

        return frozenset(result_deps)

    def _get_dep_ids(self, inst_repo):
        """
        Return a function that returns dependencies (frozenset of package IDs)
        of a given package.
        """
        def _get(pkg_id):
            dep_ids = []
            deps = inst_repo.retrieveDependencies(pkg_id)

            for dep in deps:
                package_id, pkg_rc = inst_repo.atomMatch(dep)
                # XXX: At least one of the cases when it's not 0 is when
                # a package is a build time dep., not present on the
                # system. Can this case (pkg_rc != 0) simply be ignored?
                if pkg_rc == 0:
                    dep_ids.append(package_id)

            return frozenset(dep_ids)

        return _get

    def _sorted(self, atom_size_pairs):
        """
        Helper function to sort the (atom, on_disk_size) pairs.
        """
        if self._sortbysize:
            sort_index = 1
        else:
            sort_index = 0

        return sorted(atom_size_pairs, key=lambda x: x[sort_index])

    # XXX: Locking: is this correct?
    @sharedlock
    def _unused(self, entropy_client, inst_repo):
        """
        Command implementation.
        """
        if not self._quiet:
            entropy_client.output(
                # XXX: Add again the information about false positives?
                # XXX: Note: it's in the command description to be careful with this already.
                "%s..." % (
                    blue(_("Running unused packages test")),),
                header=red(" @@ "))

        all_ids = self._installed_pkg_ids(inst_repo)
        user_packages = self._filter_user_packages(inst_repo, all_ids)
        wanted_ids = self._get_flat_deps(user_packages,
                                         self._get_dep_ids(inst_repo))
        not_needed = all_ids - wanted_ids

        not_needed_pkgs_data = self._sorted(
            [(inst_repo.retrieveAtom(x), inst_repo.retrieveOnDiskSize(x)) \
             for x in not_needed])

        if self._quiet:
            entropy_client.output(
                '\n'.join([x[0] for x in not_needed_pkgs_data]),
                level="generic")
        else:
            for atom, disk_size in not_needed_pkgs_data:
                disk_size = entropy.tools.bytes_into_human(disk_size)
                entropy_client.output(
                    "# %s%s%s %s" % (
                        blue("["), brown(disk_size),
                        blue("]"), darkgreen(atom),))

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloUnused,
        SoloUnused.NAME,
        _("show unused packages (pay attention)"))
    )
