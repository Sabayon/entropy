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

from entropy.const import const_convert_to_unicode, etpConst, \
    const_debug_write
from entropy.i18n import _, ngettext
from entropy.output import darkgreen, blue, purple, teal, brown, bold, \
    darkred
from entropy.exceptions import EntropyPackageException, \
    DependenciesCollision, DependenciesNotFound
from entropy.services.client import WebService

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

        self._nsargs = nsargs
        return self._call_locked, [nsargs.func]

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

    def _show_did_you_mean(self, entropy_client, package, from_installed):
        """
        Show "Did you mean?" results for the given package name.
        """
        items = entropy_client.get_meant_packages(
            package, from_installed=from_installed)
        if not items:
            return

        mytxt = "%s %s %s %s %s" % (
            bold(const_convert_to_unicode("   ?")),
            teal(_("When you wrote")),
            bold(const_convert_to_unicode(package)),
            darkgreen(_("You Meant(tm)")),
            teal(_("one of these below?")),
        )
        entropy_client.output(mytxt)

        _cache = set()
        for pkg_id, repo_id in items:
            if from_installed:
                repo = entropy_client.installed_repository()
            else:
                repo = entropy_client.open_repository(repo_id)

            key_slot = repo.retrieveKeySlotAggregated(pkg_id)
            if key_slot not in _cache:
                entropy_client.output(
                    enlightenatom(key_slot),
                    header=brown("    # "))
                _cache.add(key_slot)

    def _show_packages_info(self, entropy_client, package_matches,
                            deps, ask, pretend, verbose, quiet,
                            action_name = None):
        """
        Show information about given package matches.
        """
        if (ask or pretend or verbose) and not quiet:

            entropy_client.output(
                "%s:" % (
                    blue(_("These are the selected packages")),),
                header=darkred(" @@ "))

            total = len(package_matches)
            count = 0
            inst_repo = entropy_client.installed_repository()

            for package_id, repository_id in package_matches:
                count += 1

                repo = entropy_client.open_repository(repository_id)
                pkgatom = repo.retrieveAtom(package_id)
                if not pkgatom:
                    continue

                pkgver = repo.retrieveVersion(package_id)
                pkgtag = repo.retrieveTag(package_id)
                if not pkgtag:
                    pkgtag = "NoTag"
                pkgrev = repo.retrieveRevision(package_id)
                pkgslot = repo.retrieveSlot(package_id)

                inst_ver = _("Not installed")
                inst_tag = "NoTag"
                inst_rev = "NoRev"
                inst_repo_s = _("Not available")

                inst_pkg_id, inst_rc = inst_repo.atomMatch(
                    entropy.dep.dep_getkey(pkgatom),
                    matchSlot = pkgslot)
                if inst_rc == 0:
                    inst_ver = inst_repo.retrieveVersion(inst_pkg_id)
                    inst_tag = inst_repo.retrieveTag(inst_pkg_id)
                    inst_repo_s = inst_repo.getInstalledPackageRepository(
                        inst_pkg_id)
                    if inst_repo_s is None:
                        inst_repo_s = _("Not available")
                    if not inst_tag:
                        inst_tag = "NoTag"
                    inst_rev = inst_repo.retrieveRevision(inst_pkg_id)

                mytxt = "%s%s/%s%s [%s] %s" % (
                    darkred("("),
                    bold("%d" % (count,)),
                    blue("%d" % (total,)),
                    darkred(")"),
                    darkred(repository_id),
                    bold(pkgatom),
                )
                entropy_client.output(
                    mytxt, header="   # ")

                mytxt = "%s: %s / %s / %s %s %s / %s / %s" % (
                    darkred(_("Versions")),
                    blue(inst_ver),
                    blue(inst_tag),
                    blue("%d" % (inst_rev,)),
                    bold("===>"),
                    darkgreen(pkgver),
                    darkgreen(pkgtag),
                    darkgreen("%d" % (pkgrev,)),
                )
                entropy_client.output(
                    mytxt, header="    ")

                is_installed = True
                if inst_ver == _("Not installed"):
                    is_installed = False
                    inst_ver = "0"
                if inst_rev == "NoRev":
                    inst_rev = 0

                pkgcmp = entropy_client.get_package_action(
                    (package_id, repository_id))
                if pkgcmp == 0 and is_installed:
                    if inst_repo_s != repository_id:
                        action = "%s | %s %s ===> %s" % (
                            darkgreen(_("Reinstall")),
                            _("Switch repo"),
                            blue(inst_repo_s),
                            darkgreen(repository_id),
                            )
                    else:
                        action = darkgreen(_("Reinstall"))
                elif pkgcmp == 1:
                    action = darkgreen(_("Install"))
                elif pkgcmp == 2:
                    action = blue(_("Upgrade"))
                else:
                    action = darkred(_("Downgrade"))

                # support for caller provided action name
                if action_name is not None:
                    action = action_name

                entropy_client.output(
                    "\t%s:\t\t %s" % (
                        darkred(_("Action")),
                        action,))

            entropy_client.output(
                "%s: %d" % (
                    blue(_("Packages involved")),
                    total,),
                header=darkred(" @@ "))

        if ask and not pretend:
            if deps:
                rc = entropy_client.ask_question("     %s" % (
                    _("Would you like to continue with "
                      "the dependencies calculation?"),) )
            else:
                rc = entropy_client.ask_question("     %s" % (
                    _("Would you like to continue ?"),) )
            if rc == _("No"):
                return 1
        return 0

    def _show_removal_info(self, entropy_client, package_ids,
                           manual = False):
        """
        Show packages removal information.
        """
        if manual:
            entropy_client.output(
                "%s:" % (
                    blue(_("These are the packages that "
                      "should be MANUALLY removed")),),
                header=darkred(" @@ "))
        else:
            entropy_client.output(
                "%s:" % (
                    blue(_("These are the packages that "
                      "would be removed")),),
                header=darkred(" @@ "))

        total = len(package_ids)
        count = 0
        inst_repo = entropy_client.installed_repository()

        for package_id in package_ids:
            count += 1
            atom = inst_repo.retrieveAtom(package_id)
            installedfrom = inst_repo.getInstalledPackageRepository(
                package_id)
            if installedfrom is None:
                installedfrom = _("Not available")

            on_disk_size = inst_repo.retrieveOnDiskSize(package_id)
            pkg_size = inst_repo.retrieveSize(package_id)
            extra_downloads = inst_repo.retrieveExtraDownload(package_id)
            for extra_download in extra_downloads:
                pkg_size += extra_download['size']
                on_disk_size += extra_download['disksize']

            disksize = entropy.tools.bytes_into_human(on_disk_size)
            disksize_info = "%s%s%s" % (
                bold("["),
                brown("%s" % (disksize,)),
                bold("]"))
            repo_info = bold("[") + brown(installedfrom) + bold("]")

            mytxt = "%s %s %s" % (
                repo_info,
                enlightenatom(atom),
                disksize_info)

            entropy_client.output(mytxt, header=darkred(" ## "))

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

    def _scan_packages(self, entropy_client, packages):
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
            entropy_client, packages):

            # clear masking reasons
            match = entropy_client.atom_match(package)
            if match[0] != -1:
                if match not in final_package_names:
                    final_package_names.append(match)
                continue
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
            if package_id == -1:
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
                continue
            package_ids.append(package_id)

        return package_ids

    def _generate_install_queue(self, entropy_client, packages, deps,
                                empty, deep, relaxed, bdeps, recursive):
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
                    build = bdeps, recursive = recursive)
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
                           downdata, multifetch=1, checksum=True):
        """
        Download packages from mirrors, essentially.
        """
        # read multifetch parameter from config if needed.
        client_settings = entropy_client.ClientSettings()
        misc_settings = client_settings['misc']
        if multifetch <= 1:
            multifetch = misc_settings.get('multifetch', 1)

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

                metaopts = {}
                metaopts['dochecksum'] = checksum
                pkg = None
                try:
                    pkg = entropy_client.Package()
                    pkg.prepare(matches, "multi_fetch", metaopts)
                    myrepo_data = pkg.pkgmeta['repository_atoms']
                    for myrepo in myrepo_data:
                        obj = downdata.setdefault(myrepo, set())
                        for atom in myrepo_data[myrepo]:
                            obj.add(entropy.dep.dep_getkey(atom))

                    xterm_header = "equo (%s) :: %d of %d ::" % (
                        _("download"), count, total)
                    entropy_client.output(
                        "%s %s" % (
                            darkgreen(
                                const_convert_to_unicode(len(matches))),
                            ngettext("package", "packages", len(matches))
                            ),
                        count=(count, total),
                        header=darkred(" ::: ") + ">>> ")

                    exit_st = pkg.run(xterm_header=xterm_header)
                    if exit_st != 0:
                        return 1

                finally:
                    if pkg is not None:
                        pkg.kill()

            return 0

        total = len(package_matches)
        count = 0
        # normal fetch
        for match in package_matches:
            count += 1

            metaopts = {}
            metaopts['dochecksum'] = checksum
            pkg = None
            try:
                package_id, repository_id = match
                atom = entropy_client.open_repository(
                    repository_id).retrieveAtom(package_id)
                pkg = entropy_client.Package()
                pkg.prepare(match, "fetch", metaopts)
                myrepo = pkg.pkgmeta['repository']

                obj = downdata.setdefault(myrepo, set())
                obj.add(entropy.dep.dep_getkey(atom))

                xterm_header = "equo (%s) :: %d of %d ::" % (
                    _("download"), count, total)

                entropy_client.output(
                    darkgreen(atom),
                    count=(count, total),
                    header=darkred(" ::: ") + ">>> ")

                exit_st = pkg.run(xterm_header=xterm_header)
                if exit_st != 0:
                    return 1

            finally:
                if pkg is not None:
                    pkg.kill()

        return 0
