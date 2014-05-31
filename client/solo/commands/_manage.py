# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import argparse
import errno
import os
import shlex
import subprocess
import sys

from entropy.const import const_convert_to_unicode, etpConst, \
    const_debug_write, const_mkstemp
from entropy.i18n import _, ngettext
from entropy.output import darkgreen, blue, purple, teal, brown, bold, \
    darkred, readtext, is_interactive
from entropy.exceptions import EntropyPackageException, \
    DependenciesCollision, DependenciesNotFound
from entropy.services.client import WebService
from entropy.client.interfaces.repository import Repository
from entropy.client.interfaces.package.preservedlibs import PreservedLibraries

import entropy.tools
import entropy.dep

from solo.utils import enlightenatom, get_entropy_webservice
from solo.commands.command import SoloCommand

class SoloManage(SoloCommand):
    """
    Abstract class used by Solo Package management
    modules (remove, install, etc...).
    This class contains all the shared code.
    """

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._interactive = is_interactive()
        self._nsargs = None

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

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

        # Python 3.3 bug #16308
        if not hasattr(nsargs, "func"):
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_shared, [nsargs.func]

    def _signal_ugc(self, entropy_client, package_keys):
        """
        Signal UGC activity.
        """
        for repository_id, pkgkeys in package_keys.items():
            try:
                webserv = get_entropy_webservice(entropy_client,
                    repository_id, tx_cb = False)
            except WebService.UnsupportedService:
                continue
            try:
                webserv.add_downloads(sorted(package_keys),
                    clear_available_cache = True)
            except WebService.WebServiceException as err:
                const_debug_write(__name__, repr(err))
                continue

    def _show_config_files_update(self, entropy_client):
        """
        Inform User about configuration file updates, if any.
        """
        entropy_client.output(
            blue(_("Scanning configuration files to update")),
            header=darkgreen(" @@ "),
            back=True)

        updates = entropy_client.ConfigurationUpdates()
        scandata = updates.get()

        if not scandata:
            entropy_client.output(
                blue(_("No configuration files to update.")),
                header=darkgreen(" @@ "))
            return

        mytxt = ngettext(
            "There is %s configuration file needing update",
            "There are %s configuration files needing update",
            len(scandata)) % (len(scandata),)
        entropy_client.output(
            darkgreen(mytxt),
            level="warning")

        mytxt = "%s: %s" % (
            purple(_("Please run")),
            bold("equo conf update"))
        entropy_client.output(
            darkgreen(mytxt),
            level="warning")

    def _show_preserved_libraries(self, entropy_client):
        """
        Inform User about preserved libraries living on the filesystem.
        This method is process and thread safe.
        """
        inst_repo = entropy_client.installed_repository()
        with inst_repo.shared():
            preserved_mgr = PreservedLibraries(
                inst_repo, None, frozenset(), root=etpConst['systemroot'])

            preserved = preserved_mgr.list()

        if preserved:
            mytxt = ngettext(
                "There is %s preserved library on the system",
                "There are %s preserved libraries on the system",
                len(preserved)) % (len(preserved),)
            entropy_client.output(
                darkgreen(mytxt),
                level="warning")

        for library, elfclass, path, atom in preserved:
            entropy_client.output(
                "%s [%s:%s -> %s]" % (
                    darkred(path),
                    purple(library),
                    teal(const_convert_to_unicode(elfclass)),
                    enlightenatom(atom),
                ))

    def _scan_packages_expand_tag(self, entropy_client, packages):
        """
        This function assists the user automatically adding package
        tags to package names passed in order to correctly
        select installed packages in case of multiple package
        tags available.
        A real-world example is kernel-dependent packages.
        We don't want to implicitly propose user new packages
        using newer kernels.
        """
        inst_repo = entropy_client.installed_repository()

        def expand_package(dep):
            tag = entropy.dep.dep_gettag(dep)
            if tag is not None:
                # do not override packages already providing a tag
                return dep

            # can dep be resolved as it is?
            pkg_match, pkg_repo = entropy_client.atom_match(dep)
            if pkg_repo == 1:
                # no, ignoring
                return dep

            pkg_ids, rc = inst_repo.atomMatch(dep, multiMatch = True)
            if rc != 0:
                # not doing anything then
                return dep

            tags = set()
            for pkg_id in pkg_ids:
                pkg_tag = inst_repo.retrieveTag(pkg_id)
                if not pkg_tag:
                    # at least one not tagged, abort
                    return dep
                tags.add(pkg_tag)

            best_tag = entropy.dep.sort_entropy_package_tags(tags)[-1]

            proposed_dep = "%s%s%s" % (
                dep, etpConst['entropytagprefix'], best_tag)
            # make sure this can be resolved ==
            #   if package is still available
            pkg_match, repo_id = entropy_client.atom_match(proposed_dep)
            if repo_id == 1:
                return dep

            return proposed_dep

        return list(map(expand_package, packages))

    def _show_masked_package_info(self, entropy_client,
                                  package, from_user = True):
        """
        Show information about a masked package.
        """
        def _find_belonging_dependency(package_atoms):
            crying_atoms = set()
            for atom in package_atoms:
                for repository_id in entropy_client.repositories():
                    repo = entropy_client.open_repository(
                        repository_id)
                    riddep = repo.searchDependency(atom)
                    if riddep == -1:
                        continue
                    rpackage_ids = repo.searchPackageIdFromDependencyId(
                        riddep)
                    for i in rpackage_ids:
                        i, r = repo.maskFilter(i)
                        if i == -1:
                            continue
                        iatom = repo.retrieveAtom(i)
                        crying_atoms.add((iatom, repository_id))
            return crying_atoms

        def _get_masked_package_reason(match):
            package_id, repository_id = match
            repo = entropy_client.open_repository(repository_id)
            package_id, reason_id = repo.maskFilter(package_id)
            masked = False
            if package_id == -1:
                masked = True
            settings = entropy_client.Settings()
            return masked, reason_id, settings['pkg_masking_reasons'].get(
                reason_id)

        masked_matches = entropy_client.atom_match(
            package, mask_filter = False,
            multi_match = True)
        if masked_matches[1] == 0:

            mytxt = "%s %s %s." % (
                # every package matching app-foo is masked
                darkred(_("Every package matching")),
                bold(package),
                darkred(_("is masked")),
            )
            entropy_client.output(
                mytxt, header=bold(" !!! "), level="warning")

            m_reasons = {}
            for match in masked_matches[0]:
                masked, reason_id, reason = _get_masked_package_reason(
                    match)
                if not masked:
                    continue
                reason_obj = (reason_id, reason,)
                obj = m_reasons.setdefault(reason_obj, [])
                obj.append(match)

            for reason_id, reason in sorted(m_reasons.keys()):
                entropy_client.output(
                    "%s: %s" % (
                        blue(_("Masking reason")),
                        darkgreen(reason)),
                    header=bold("    # "),
                    level="warning")

                for m_package_id, m_repo in m_reasons[(reason_id, reason)]:
                    repo = entropy_client.open_repository(m_repo)
                    try:
                        m_atom = repo.retrieveAtom(m_package_id)
                    except TypeError:
                        m_atom = "package_id: %s %s %s %s" % (
                            m_package_id,
                            _("matching"),
                            package,
                            _("is broken"),
                        )
                    entropy_client.output(
                        "%s: %s %s %s" % (
                            darkred(_("atom")),
                            brown(m_atom),
                            brown(_("in")),
                            purple(m_repo)),
                        header=blue("     <> "),
                        level="warning")

        elif from_user:
            mytxt = "%s %s %s." % (
                darkred(_("No match for")),
                bold(package),
                darkred(_("in repositories")),
            )
            entropy_client.output(
                mytxt, header=bold(" !!! "),
                level="warning")

            if len(package) > 3:
                self._show_did_you_mean(
                    entropy_client, package, False)

        else:
            entropy_client.output(
                "%s: %s" % (
                    blue(_("Not found")),
                    brown(package)),
                header=darkred("   # "),
                level="error")

            crying_atoms = _find_belonging_dependency([package])
            if crying_atoms:
                entropy_client.output(
                    "%s:" % (
                        blue(_("package needed by"))),
                    header=darkred("     # "),
                    level="error")
                for c_atom, c_repo in crying_atoms:
                    entropy_client.output(
                        "[%s: %s] %s" % (
                            blue(_("from")),
                            brown(c_repo),
                            darkred(c_atom)),
                        header=darkred("        # "),
                        level="error")

    def _scan_packages(self, entropy_client, packages, onlydeps=False):
        """
        Analyze the list of packages and expand, validate, rework
        it. This is used by equo install, equo source, and others.
        """
        package_names = []
        package_files = []
        for package in packages:
            if entropy.tools.is_entropy_package_file(package):
                package = os.path.abspath(package)
                package_files.append(package)
            else:
                package_names.append(package)
        package_names = entropy_client.packages_expand(package_names)

        final_package_names = []
        for package in self._scan_packages_expand_tag(
            entropy_client, package_names):

            # match the package string inside available repositories
            # if we find something, we're done, otherwise try to
            # guess something.
            match = entropy_client.atom_match(package)
            if match[0] != -1:
                if match not in final_package_names:
                    final_package_names.append(match)
                continue

            # if onlydeps is True and we find a package with
            # mask_filter=False, then take it.
            # We are only going to use its deps, anyway.
            if onlydeps:
                match = entropy_client.atom_match(package, mask_filter=False)
                if match[0] != -1:
                    if match not in final_package_names:
                        final_package_names.append(match)
                    continue

            # determine if a category should be added and package
            # matched. If removing the category we end up with the
            # same name, then there is no category part.
            if entropy.dep.remove_cat(package) != package:
                self._show_masked_package_info(entropy_client, package)
                continue

            # try to match inside the installed packages repository
            # and see if there is just one installed package with the same
            # category.
            inst_repo = entropy_client.installed_repository()
            inst_pkg_id, inst_rc = inst_repo.atomMatch(package)
            if inst_pkg_id == -1:
                self._show_masked_package_info(entropy_client, package)
                continue

            # get the category and guard against stale data.
            inst_pkg_cat = inst_repo.retrieveCategory(inst_pkg_id)
            if not inst_pkg_cat:
                self._show_masked_package_info(entropy_client, package)
                continue

            # match the package again, hope to find a good one
            # inside available repositories, otherwise give up.
            package = "%s/%s" % (inst_pkg_cat, package)
            match = entropy_client.atom_match(package)
            if match[0] != -1:
                if match not in final_package_names:
                    final_package_names.append(match)
                continue

            # if onlydeps is True and we find a package with
            # mask_filter=False, then take it.
            # We are only going to use its deps, anyway.
            if onlydeps:
                match = entropy_client.atom_match(package, mask_filter=False)
                if match[0] != -1:
                    if match not in final_package_names:
                        final_package_names.append(match)
                    continue

            # giving up completely
            self._show_masked_package_info(entropy_client, package)

        if package_files:
            for pkg in package_files:
                try:
                    names_found = entropy_client.add_package_repository(
                        pkg)
                except EntropyPackageException as err:
                    b_name = os.path.basename(pkg)
                    mytxt = "%s: %s %s. %s ..." % (
                        purple(_("Warning")),
                        teal(const_convert_to_unicode(b_name)),
                        repr(err),
                        teal(_("Skipped")),
                    )
                    entropy_client.output(mytxt, level="warning")
                    continue
                final_package_names += names_found[:]

        return final_package_names

    def _scan_installed_packages(self, entropy_client,
                                 inst_repo, packages):
        """
        Scan the Installed Packages repository for matches and
        return a list of matched package identifiers.
        """
        package_ids = []
        for package in packages:

            package_id, _result = inst_repo.atomMatch(package)
            if package_id != -1:
                package_ids.append(package_id)
                continue

            # support file paths and convert them to package_ids
            file_package_ids = inst_repo.isFileAvailable(
                package, get_id=True)
            if file_package_ids:
                package_ids.extend(file_package_ids)
                continue

            mytxt = "!!! %s: %s %s." % (
                purple(_("Warning")),
                teal(const_convert_to_unicode(package)),
                purple(_("is not installed")),
            )
            entropy_client.output("!!!", level="warning")
            entropy_client.output(mytxt, level="warning")
            entropy_client.output("!!!", level="warning")

            if len(package) > 3:
                self._show_did_you_mean(
                    entropy_client, package, True)
                entropy_client.output("!!!", level="warning")

        return package_ids

    def _generate_install_queue(self, entropy_client, packages, deps,
                                empty, deep, relaxed, onlydeps, bdeps,
                                recursive):
        """
        Generate a complete installation queue.
        """
        run_queue = []
        removal_queue = []

        if not deps:
            run_queue += packages[:]
            return run_queue, removal_queue

        entropy_client.output(
            "%s..." % (
                blue(_("Calculating dependencies")),),
            header=darkred(" @@ "))

        try:
            run_queue, removal_queue = \
                entropy_client.get_install_queue(
                    packages, empty, deep, relaxed=relaxed,
                    build=bdeps, recursive=recursive,
                    only_deps=onlydeps)
        except DependenciesNotFound as exc:
            run_deps = exc.value
            entropy_client.output(
                "%s:" % (blue(_("Dependencies not found")),),
                header=darkred(" @@ "), level="error")
            for package in run_deps:
                self._show_masked_package_info(
                    entropy_client, package, from_user=False)
            return None, None

        except DependenciesCollision as exc:
            col_deps = exc.value

            entropy_client.output(
                "%s:" % (blue(_("Conflicting packages were pulled in")),),
                header=darkred(" @@ "), level="error")
            # run_queue is a list of sets
            entropy_client.output("", level="warning")

            for pkg_matches in col_deps:
                for pkg_id, pkg_repo in pkg_matches:
                    repo = entropy_client.open_repository(pkg_repo)
                    entropy_client.output(
                        teal(repo.retrieveAtom(pkg_id)),
                        header=brown("  # "),
                        level="warning")
                entropy_client.output("", level="warning")

            entropy_client.output(
                "%s: %s" % (
                    purple(_("Please mask conflicts using")),
                    bold("equo mask <package>"),),
                header=darkred(" @@ "),
                level="error")
            return None, None

        return run_queue, removal_queue

    def _download_packages(self, entropy_client, package_matches,
                           downdata, multifetch=1):
        """
        Download packages from mirrors, essentially.
        """
        # read multifetch parameter from config if needed.
        client_settings = entropy_client.ClientSettings()
        misc_settings = client_settings['misc']
        if multifetch <= 1:
            multifetch = misc_settings.get('multifetch', 1)

        action_factory = entropy_client.PackageActionFactory()

        mymultifetch = multifetch
        if multifetch > 1:
            myqueue = []
            mystart = 0
            while True:
                mylist = package_matches[mystart:mymultifetch]
                if not mylist:
                    break
                myqueue.append(mylist)
                mystart += multifetch
                mymultifetch += multifetch

            count = 0
            total = len(myqueue)
            for matches in myqueue:
                count += 1

                for pkg_id, pkg_repo in matches:
                    obj = downdata.setdefault(pkg_repo, set())
                    repo = entropy_client.open_repository(pkg_repo)
                    pkg_atom = repo.retrieveAtom(pkg_id)
                    if pkg_atom:
                        obj.add(entropy.dep.dep_getkey(pkg_atom))

                pkg = None
                try:
                    pkg = action_factory.get(
                        action_factory.MULTI_FETCH_ACTION,
                        matches)

                    xterm_header = "equo (%s) :: %d of %d ::" % (
                        _("download"), count, total)
                    pkg.set_xterm_header(xterm_header)

                    entropy_client.output(
                        "%s %s" % (
                            darkgreen(
                                const_convert_to_unicode(len(matches))),
                            ngettext("package", "packages", len(matches))
                            ),
                        count=(count, total),
                        header=darkred(" ::: ") + ">>> ")

                    exit_st = pkg.start()
                    if exit_st != 0:
                        return 1

                finally:
                    if pkg is not None:
                        pkg.finalize()

            return 0

        total = len(package_matches)
        count = 0
        # normal fetch
        for match in package_matches:
            count += 1

            pkg = None
            try:
                package_id, repository_id = match

                atom = entropy_client.open_repository(
                    repository_id).retrieveAtom(package_id)
                if atom:
                    obj = downdata.setdefault(repository_id, set())
                    obj.add(entropy.dep.dep_getkey(atom))

                pkg = action_factory.get(
                    action_factory.FETCH_ACTION,
                    match)

                xterm_header = "equo (%s) :: %d of %d ::" % (
                    _("download"), count, total)
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

    def _advise_repository_update(self, entropy_client):
        """
        Warn user about old repositories if needed.
        """
        old_repos = Repository.are_repositories_old()
        if old_repos:
            entropy_client.output("")
            mytxt = "%s %s" % (
                purple(_("Repositories are old, please run:")),
                bold("equo update"),
            )
            entropy_client.output(
                mytxt, level="warning", importance=1)
            entropy_client.output("")

    def _advise_packages_update(self, entropy_client):
        """
        Warn user about critical package updates, if any.
        """
        client_settings = entropy_client.ClientSettings()
        misc_settings = client_settings['misc']
        splitdebug = misc_settings['splitdebug']
        forced_updates = misc_settings.get('forcedupdates')

        if forced_updates:
            crit_atoms, crit_matches = \
                entropy_client.calculate_critical_updates()

            if crit_atoms:
                entropy_client.output("")
                entropy_client.output("")

                update_msg = _("Please update the following "
                               "critical packages")
                entropy_client.output("%s:" % (purple(update_msg),),
                                      level="warning")
                for name in sorted(crit_atoms):
                    entropy_client.output(
                        brown(name),
                        header=darkred("   # "),
                        level="warning")

                entropy_client.output(
                    darkgreen(_("You should install them as "
                                "soon as possible")),
                    header=darkred(" !!! "),
                    level="warning")

                entropy_client.output("")
                entropy_client.output("")

    @staticmethod
    def _accept_license(entropy_client, inst_repo, package_matches):
        """
        Prompt user licenses to accept.
        """

        def _read_lic_selection():
            entropy_client.output(
                darkred(_("Please select an option")),
                header="    ")
            entropy_client.output(
                "(%d) %s" % (
                    1,
                    darkgreen(_("Read the license"))),
                header="      ")
            entropy_client.output(
                "(%d) %s" % (
                    2,
                    brown(_("Accept the license (I've read it)"))),
                header="      ")
            entropy_client.output(
                "(%d) %s" % (
                    3,
                    darkred(_("Accept the license and don't "
                              "ask anymore (I've read it)"))),
                header="      ")
            entropy_client.output(
                "(%d) %s" % (0, bold(_("Quit"))),
                header="      ")

            # wait user interaction
            try:
                action = readtext(
                    "       %s: " % (
                        _("Your choice (type a number and press enter)"),)
                    )
            except EOFError:
                action = None
            return action

        def _get_license_text(license_name, repository_id):
            repo = entropy_client.open_repository(repository_id)
            text = repo.retrieveLicenseText(license_name)
            tmp_fd, tmp_path = const_mkstemp(prefix="LICENSES.")
            # text is binary string, do not use codecs.open()
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                tmp_f.write(text)
            return tmp_path

        # before even starting the fetch, make sure
        # that the user accepts their licenses
        licenses = entropy_client.get_licenses_to_accept(
            package_matches)
        # ACCEPT_LICENSE env var support
        accept_license = os.getenv("ACCEPT_LICENSE", "").split()
        for mylic in accept_license:
            licenses.pop(mylic, None)

        if licenses:
            entropy_client.output(
                "%s:" % (
                    blue(_("You need to accept the licenses below")),),
                header=darkred(" @@ "))

        for key in sorted(licenses.keys()):
            entropy_client.output(
                "%s: %s, %s:" % (
                    darkred(_("License")),
                    bold(key),
                    darkred(_("needed by"))),
                header="    :: ")

            for package_id, repository_id in licenses[key]:
                repo = entropy_client.open_repository(repository_id)
                atom = repo.retrieveAtom(package_id)
                entropy_client.output(
                    "[%s:%s] %s" % (
                        brown(_("from")),
                        darkred(repository_id),
                        bold(atom),),
                    header=blue("     # "))

            while True:

                try:
                    choice = int(_read_lic_selection())
                except (ValueError, TypeError):
                    continue

                if choice not in (0, 1, 2, 3):
                    continue

                if choice == 0:
                    return 1

                elif choice == 1: # read

                    # pick one repository and read license text
                    # from there.
                    lic_repository_id = None
                    for package_id, repository_id in licenses[key]:
                        repo = entropy_client.open_repository(
                            repository_id)
                        if repo.isLicenseDataKeyAvailable(key):
                            lic_repository_id = repository_id
                            break
                    if lic_repository_id is None:
                        entropy_client.output(
                            "%s!" % (
                                brown(_("No license data available")),)
                            )
                        continue

                    filename = _get_license_text(key, lic_repository_id)

                    viewer = os.getenv("PAGER", "")
                    viewer_args = shlex.split(viewer)
                    if not viewer_args:
                        entropy_client.output(
                            "%s ! %s %s" % (
                                brown(_("No file viewer")),
                                darkgreen(_("License saved into")),
                                filename))
                        continue

                    subprocess.call(viewer_args + [filename])
                    try:
                        os.remove(filename)
                    except OSError as err:
                        if err.errno != errno.ENOENT:
                            raise
                    continue

                elif choice == 2:
                    break

                elif choice == 3:
                    inst_repo.acceptLicense(key)
                    break

        return 0
