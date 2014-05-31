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
from entropy.const import etpConst
from entropy.output import purple, darkgreen, brown, teal, blue

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitDeps(EitCommand):
    """
    Main Eit deps command.
    """

    NAME = "deps"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._packages = []

    def _get_parser(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitDeps.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitDeps.NAME))

        parser.add_argument("packages", nargs='+', metavar="<package>",
                            help=_("package name"))
        parser.add_argument("--in", metavar="<repository>",
                            help=_("inject into given repository"),
                            dest="inrepo", default=None)

        return parser

    INTRODUCTION = """\
Through this tool it's possible to add, remove and edit dependencies of
any package.
This might be helpful for small tweaks or trivial changes in order to
avoid a complete repackage.
Please do not abuse it, package file metadata are not updated accordingly,
and the same is for Source Package Manager metadata.
Consider this a last resort for updating package dependencies in a
non-permanent way.
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
        except IOError:
            return parser.print_help, []

        self._packages += nsargs.packages
        return self._call_exclusive, [self._deps, nsargs.inrepo]

    def _show_dependencies_legend(self, entropy_server, indent = None):
        """
        Print dependency types legend.
        """
        if indent is None:
            indent = ""
        dep_types = etpConst['dependency_type_ids']
        dep_descs = etpConst['dependency_type_ids_desc']

        for dep_id, dep_val in sorted(dep_types.items(),
                key = lambda x: x[0], reverse = True):
            dep_desc = dep_descs.get(dep_id, _("N/A"))
            txt = '%s%s%s%s %s' % (
                indent, teal("{"), dep_val+1, teal("}"), dep_desc,)
            entropy_server.output(txt)

    def _show_package_dependencies(self, entropy_server, atom,
                                   orig_deps, orig_conflicts,
                                   partial = False):
        """
        Print package dependencies for atom.
        """
        if not partial:
            entropy_server.output(
                "%s, %s" % (
                    blue(atom), darkgreen(_("package dependencies"))),
                header=brown(" @@ "))
        else:
            entropy_server.output("")

        for dep_str, dep_id in orig_deps:
            entropy_server.output(
                "[%s: %s] %s" % (
                    brown(_("type")),
                    darkgreen(str(dep_id+1)),
                    purple(dep_str)),
                header=brown("  #"))

        if not orig_deps:
            entropy_server.output(
                _("No dependencies"),
                header=brown("    # "))

        for dep_str in orig_conflicts:
            entropy_server.output(
                "[%s] %s" % (
                    teal(_("conflict")),
                    purple(dep_str)),
                header=brown("  #"))

        if not orig_conflicts:
            entropy_server.output(
                _("No conflicts"),
                header=brown("    # "))

        if orig_deps:
            self._show_dependencies_legend(entropy_server, "  ")

        if partial:
            entropy_server.output("")

    def _deps(self, entropy_server):
        """
        Actual Eit deps code.
        """
        repository_id = entropy_server.repository()

        # match
        package_ids = []
        for package in self._packages:
            match = entropy_server.atom_match(
                package, match_repo = [repository_id])
            if match[1] == repository_id:
                package_ids.append(match[0])
            else:
                entropy_server.output(
                    "[%s] %s %s" % (
                        purple(repository_id),
                        darkgreen(package),
                        teal(_("not found"))),
                    importance=1, level="warning")
        if not package_ids:
            entropy_server.output(
                purple(_("No packages found")),
                importance=1, level="error")
            return 1

        avail_dep_type_desc = []
        d_type_ids = etpConst['dependency_type_ids']
        d_type_desc = etpConst['dependency_type_ids_desc']
        for dep_val, dep_id in sorted(d_type_ids.items(),
                                      key = lambda x: x[1]):
            avail_dep_type_desc.append(d_type_desc[dep_val])

        def pkg_dep_types_cb(s):
            try:
                avail_dep_type_desc.index(s[1])
            except IndexError:
                return False
            return True

        repo = entropy_server.open_repository(repository_id)
        for package_id in package_ids:
            atom = repo.retrieveAtom(package_id)

            orig_deps = repo.retrieveDependencies(
                package_id, extended = True,
                resolve_conditional_deps = False)
            dep_type_map = dict(orig_deps)

            orig_conflicts = ["!%s" % (x,) for x in
                              repo.retrieveConflicts(package_id)]
            orig_conflicts.sort()

            def dep_check_cb(s):

                is_conflict = s.startswith("!")
                changes_made_type_map = {}
                confl_changes_made = []

                if is_conflict:
                    confl_changes_made.append(s[1:])
                else:
                    input_params = [
                        ('dep_type', ('combo', (_("Dependency type"),
                            avail_dep_type_desc),),
                        pkg_dep_types_cb, False)
                    ]

                    data = entropy_server.input_box(
                        ("%s: %s" % (_('Select a dependency type for'), s,)),
                        input_params
                    )
                    if data is None:
                        return False

                    rc_dep_type = avail_dep_type_desc.index(
                        data['dep_type'][1])
                    dep_type_map[s] = rc_dep_type

                    changes_made_type_map.update({s: rc_dep_type})

                self._show_package_dependencies(
                    entropy_server,
                    atom, changes_made_type_map.items(),
                    confl_changes_made, partial = True)

                return True

            self._show_package_dependencies(
                    entropy_server, atom, orig_deps,
                    orig_conflicts)

            entropy_server.output("")
            current_deps = [x[0] for x in orig_deps]
            current_deps += orig_conflicts
            input_params = [
                ('new_deps', ('list', (_('Dependencies'), current_deps),),
                    dep_check_cb, True)
            ]
            data = entropy_server.input_box(
                _("Dependencies editor"), input_params)
            if data is None:
                continue

            orig_deps = []
            orig_conflicts = []
            for x in data.get('new_deps', []):
                if x.startswith("!"):
                    orig_conflicts.append(x[1:])
                else:
                    orig_deps.append((x, dep_type_map[x],))

            self._show_package_dependencies(
                entropy_server, atom, orig_deps, orig_conflicts)
            rc_ask = entropy_server.ask_question(_("Confirm ?"))
            if rc_ask == _("No"):
                continue

            w_repo = entropy_server.open_server_repository(
                repository_id, read_only = False)

            # save new dependencies
            while True:
                try:
                    w_repo.removeDependencies(package_id)
                    w_repo.insertDependencies(package_id, orig_deps)
                    w_repo.removeConflicts(package_id)
                    w_repo.insertConflicts(package_id, orig_conflicts)
                    w_repo.commit()
                except (KeyboardInterrupt, SystemExit,):
                    continue
                break

            # now bump, this makes EAPI=3 differential db sync happy
            old_pkg_data = w_repo.getPackageData(package_id)
            w_repo.handlePackage(old_pkg_data)

            entropy_server.output(
                "%s: %s" % (
                    blue(atom),
                    darkgreen(_("dependencies updated successfully"))),
                header=brown(" @@ "))

        entropy_server.commit_repositories()
        return 0


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitDeps,
        EitDeps.NAME,
        _('edit dependencies for packages in repository'))
    )
