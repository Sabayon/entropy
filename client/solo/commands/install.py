# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import argparse
import os
import sys

from entropy.i18n import _
from entropy.const import etpConst, const_convert_to_unicode
from entropy.locks import UpdatesNotificationResourceLock
from entropy.misc import ParallelTask
from entropy.output import brown, purple, darkred, red, \
    blue, darkblue, darkgreen, bold
from entropy.client.interfaces.package.actions.action import PackageAction

import entropy.tools

from solo.utils import enlightenatom
from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands._manage import SoloManage

class SoloInstall(SoloManage):
    """
    Main Solo Install command.
    """

    NAME = "install"
    ALIASES = ["i"]
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Install or update packages or package files.
"""
    SEE_ALSO = "equo-remove(1), equo-config(1)"

    def __init__(self, args):
        SoloManage.__init__(self, args)
        self._commands = {}
        self._check_critical_updates = True

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloInstall.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloInstall.NAME))
        parser.set_defaults(func=self._install)

        parser.add_argument(
            "packages", nargs='+',
            metavar="<package>", help=_("package name"))

        mg_group = parser.add_mutually_exclusive_group()
        mg_group.add_argument(
            "--ask", "-a", action="store_true",
            default=False,
            help=_("ask before making any changes"))
        _commands["--ask"] = {}
        _commands["-a"] = {}

        mg_group.add_argument(
            "--pretend", "-p", action="store_true",
            default=False,
            help=_("show what would be done"))
        _commands["--pretend"] = {}
        _commands["-p"] = {}

        parser.add_argument(
            "--verbose", "-v", action="store_true",
            default=False,
            help=_("verbose output"))
        _commands["--verbose"] = {}
        _commands["-v"] = {}

        parser.add_argument(
            "--quiet", "-q", action="store_true",
            default=False,
            help=_("quiet output"))
        _commands["--quiet"] = {}
        _commands["-q"] = {}

        parser.add_argument(
            "--fetch", action="store_true",
            default=False,
            help=_("just download packages"))
        _commands["--fetch"] = {}

        parser.add_argument(
            "--bdeps", action="store_true",
            default=False,
            help=_("include build-time dependencies"))
        _commands["--bdeps"] = {}

        parser.add_argument(
            "--nodeps", action="store_true",
            default=False,
            help=_("exclude package dependencies"))
        _commands["--nodeps"] = {}

        parser.add_argument(
            "--onlydeps", "-o", action="store_true",
            default=False,
            help=_("only include dependencies of selected packages"))
        _commands["--onlydeps"] = {}
        _commands["-o"] = {}

        parser.add_argument(
            "--norecursive", action="store_true",
            default=False,
            help=_("do not calculate dependencies recursively"))
        _commands["--norecursive"] = {}

        parser.add_argument(
            "--deep", action="store_true",
            default=False,
            help=_("include dependencies no longer needed"))
        _commands["--deep"] = {}

        parser.add_argument(
            "--empty", action="store_true",
            default=False,
            help=_("when used with --deep, include virtual packages"))
        _commands["--empty"] = {}

        parser.add_argument(
            "--configfiles", action="store_true",
            default=False,
            help=_("remove package configuration files no longer needed"))
        _commands["--configfiles"] = {}

        parser.add_argument(
            "--relaxed", action="store_true",
            default=False,
            help=_("relax dependencies constraints during calculation"))
        _commands["--relaxed"] = {}

        parser.add_argument(
            "--multifetch",
            type=int, default=1,
            choices=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            help=_("download multiple packages in parallel (max 10)"))
        _commands["--multifetch"] = {}

        self._commands = _commands
        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        return self._hierarchical_bashcomp(last_arg, [], self._commands)

    def _install(self, entropy_client):
        """
        Solo Install command.
        """
        deps = not self._nsargs.nodeps
        recursive = not self._nsargs.norecursive
        pretend = self._nsargs.pretend
        ask = self._nsargs.ask
        verbose = self._nsargs.verbose
        quiet = self._nsargs.quiet
        empty = self._nsargs.empty
        config_files = self._nsargs.configfiles
        deep = self._nsargs.deep
        fetch = self._nsargs.fetch
        bdeps = self._nsargs.bdeps
        onlydeps = self._nsargs.onlydeps
        relaxed = self._nsargs.relaxed
        multifetch = self._nsargs.multifetch
        packages = self._nsargs.packages

        exit_st, _show_cfgupd = self._install_action(
            entropy_client, deps, recursive,
            pretend, ask, verbose, quiet, empty,
            config_files, deep, fetch, bdeps, onlydeps,
            relaxed, multifetch, packages)
        if _show_cfgupd:
            self._show_config_files_update(entropy_client)
            self._show_preserved_libraries(entropy_client)

        return exit_st

    @classmethod
    def _show_install_queue(cls, entropy_client, inst_repo,
                            run_queue, removal_queue, ask, pretend,
                            quiet, verbose):
        """
        Show expanded installation queue to user.
        """
        download_size = 0
        unpack_size = 0
        on_disk_used_size = 0
        on_disk_freed_size = 0
        pkgs_install = 0
        pkgs_update = 0
        pkgs_reinstall = 0
        pkgs_downgrade = 0
        pkgs_remove = len(removal_queue)
        client_settings = entropy_client.ClientSettings()
        splitdebug = client_settings['misc']['splitdebug']

        if run_queue and ((ask or pretend) and not quiet):
            inst_msg = _("These are the packages that would be installed")
            entropy_client.output(
                "%s:" % (blue(inst_msg),),
                header=darkred(" @@ "))

        for package_id, repository_id in run_queue:

            repo = entropy_client.open_repository(repository_id)
            atom = repo.retrieveAtom(package_id)

            pkgver = repo.retrieveVersion(package_id)
            pkgtag = repo.retrieveTag(package_id)
            pkgrev = repo.retrieveRevision(package_id)
            pkgslot = repo.retrieveSlot(package_id)
            pkgfile = repo.retrieveDownloadURL(package_id)
            on_disk_used_size += repo.retrieveOnDiskSize(package_id)

            pkgsize = repo.retrieveSize(package_id)
            extra_downloads = repo.retrieveExtraDownload(package_id)
            for extra_download in extra_downloads:
                if not splitdebug and (extra_download['type'] == "debug"):
                    continue
                pkgsize += extra_download['size']
                on_disk_used_size += extra_download['disksize']

            unpack_size += int(pkgsize) * 2

            fetch_path = PackageAction.get_standard_fetch_disk_path(pkgfile)
            if not os.path.exists(fetch_path):
                download_size += int(pkgsize)
            else:
                try:
                    f_size = entropy.tools.get_file_size(fetch_path)
                except OSError:
                    f_size = 0
                download_size += pkgsize - f_size

            installed_ver = '-1'
            installed_tag = ''
            installed_rev = 0
            inst_repo_s = None

            inst_pkg_id, inst_pkg_rc = inst_repo.atomMatch(
                entropy.dep.dep_getkey(atom), matchSlot = pkgslot)
            if inst_pkg_rc == 0:
                installed_ver = inst_repo.retrieveVersion(
                    inst_pkg_id)
                installed_tag = inst_repo.retrieveTag(
                    inst_pkg_id)
                installed_rev = inst_repo.retrieveRevision(
                    inst_pkg_id)
                inst_repo_s = \
                    inst_repo.getInstalledPackageRepository(
                        inst_pkg_id)
                if inst_repo_s is None:
                    inst_repo_s = _("Not available")
                on_disk_freed_size += inst_repo.retrieveOnDiskSize(
                    inst_pkg_id)
                extra_downloads = inst_repo.retrieveExtraDownload(
                    inst_pkg_id)
                for extra_download in extra_downloads:
                    on_disk_freed_size += extra_download['disksize']

            # statistics generation complete
            # if --quiet, we're done doing stuff
            if quiet:
                continue

            inst_meta = (installed_ver, installed_tag, installed_rev,)
            avail_meta = (pkgver, pkgtag, pkgrev,)
            action = 0
            repo_switch = False
            if (repository_id != inst_repo_s) and \
                    (inst_repo_s is not None):
                repo_switch = True

            if repo_switch:
                flags = darkred(" [")
            else:
                flags = " ["
            if inst_repo_s is None:
                inst_repo_s = _('Not available')

            pkgcmp = entropy_client.get_package_action(
                (package_id, repository_id))

            if pkgcmp == 0:
                pkgs_reinstall += 1
                flags += red("R")
                action = 1
            elif pkgcmp == 1:
                pkgs_install += 1
                flags += darkgreen("N")
            elif pkgcmp == 2:
                pkgs_update += 1
                if avail_meta == inst_meta:
                    flags += blue("U") + red("R")
                else:
                    flags += blue("U")
                action = 2
            else:
                pkgs_downgrade += 1
                flags += darkblue("D")
                action = -1

            if repo_switch:
                flags += darkred("] ")
            else:
                flags += "] "

            if repo_switch:
                repo_info = "[%s->%s] " % (
                    brown(inst_repo_s),
                    darkred(repository_id),)
            else:
                repo_info = "[%s] " % (
                    brown(repository_id),)

            old_info = ""
            if action != 0:
                old_info = "   [%s|%s" % (
                    blue(installed_ver),
                    darkred(const_convert_to_unicode(installed_rev)),)

                old_tag = "]"
                if installed_tag:
                    old_tag = "|%s%s" % (
                        darkred(installed_tag),
                        old_tag,)
                old_info += old_tag

            entropy_client.output(
                "%s%s%s|%s%s" % (
                    flags,
                    repo_info,
                    enlightenatom(atom),
                    darkred(const_convert_to_unicode(pkgrev)),
                    old_info,),
                header=darkred(" ##"))

        delta_size = on_disk_used_size - on_disk_freed_size
        needed_size = delta_size
        if unpack_size > 0:
            needed_size += unpack_size

        if (ask or pretend or verbose) and removal_queue:
            mytxt = "%s (%s):" % (
                blue(_("These are the packages that would be removed")),
                bold(_("conflicting/substituted")),
            )
            entropy_client.output(
                mytxt, header=darkred(" @@ "))

        for package_id in removal_queue:

            atom = inst_repo.retrieveAtom(package_id)
            on_disk_freed_size += inst_repo.retrieveOnDiskSize(
                package_id)
            extra_downloads = inst_repo.retrieveExtraDownload(
                package_id)

            for extra_download in extra_downloads:
                on_disk_freed_size += extra_download['disksize']

            installedfrom = inst_repo.getInstalledPackageRepository(
                package_id)
            if installedfrom is None:
                installedfrom = _("Not available")

            mytxt = "[%s] %s%s: %s%s %s" % (
                purple("W"),
                darkred("["),
                brown(_("from")),
                bold(installedfrom),
                darkred("]"),
                enlightenatom(atom))
            entropy_client.output(mytxt, header=darkred("   ## "))

        # if --quiet, there is nothing else to show
        if quiet:
            return

        mytxt = "%s: %s" % (
            blue(_("Packages needing to be installed/updated/downgraded")),
            darkred(const_convert_to_unicode(len(run_queue))),)
        entropy_client.output(mytxt, header=darkred(" @@ "))

        mytxt = "%s: %s" % (
            blue(_("Packages needing to be removed")),
            darkred(const_convert_to_unicode(pkgs_remove)),)
        entropy_client.output(mytxt, header=darkred(" @@ "))

        if ask or verbose or pretend:

            mytxt = "%s: %s" % (
                darkgreen(_("Packages needing to be installed")),
                darkgreen(const_convert_to_unicode(pkgs_install)),
            )
            entropy_client.output(
                mytxt, header=darkred(" @@ "))

            mytxt = "%s: %s" % (
                brown(_("Packages needing to be reinstalled")),
                brown(const_convert_to_unicode(pkgs_reinstall)),
            )
            entropy_client.output(
                mytxt, header=darkred(" @@ "))

            mytxt = "%s: %s" % (
                blue(_("Packages needing to be updated")),
                blue(const_convert_to_unicode(pkgs_update)),
            )
            entropy_client.output(
                mytxt, header=darkred(" @@ "))

            mytxt = "%s: %s" % (
                darkred(_("Packages needing to be downgraded")),
                darkred(const_convert_to_unicode(pkgs_downgrade)),
            )
            entropy_client.output(
                mytxt, header=darkred(" @@ "))

        if download_size > 0:
            mysize = const_convert_to_unicode(
                entropy.tools.bytes_into_human(download_size))
        else:
            mysize = const_convert_to_unicode("0b")

        mytxt = "%s: %s" % (
            blue(_("Download size")),
            bold(mysize),
        )
        entropy_client.output(
            mytxt, header=darkred(" @@ "))

        if delta_size > 0:
            mysizetxt = _("Used disk space")
        else:
            mysizetxt = _("Freed disk space")
            delta_size = -delta_size
        delta_human = entropy.tools.bytes_into_human(delta_size)

        mytxt = "%s: %s" % (
            blue(mysizetxt),
            bold(delta_human),
        )
        entropy_client.output(mytxt, header=darkred(" @@ "))

        if needed_size < 0:
            needed_size = -needed_size

        mytxt = "%s: %s %s" % (
            blue(_("You need at least")),
            bold(entropy.tools.bytes_into_human(needed_size)),
            blue(_("of free space")),
        )
        entropy_client.output(
            mytxt, header=darkred(" @@ "))

        # check for disk space and print a warning
        target_dir = etpConst['entropyunpackdir']
        while not os.path.isdir(target_dir):
            target_dir = os.path.dirname(target_dir)
        size_match = entropy.tools.check_required_space(target_dir,
            needed_size)

        if not size_match:
            mytxt = "%s: %s" % (
                blue(_("You don't have enough space for "
                  "the installation. Free some space into")),
                darkred(target_dir),)

            entropy_client.output(
                bold(_("Attention")),
                header=darkred(" !!! "))
            entropy_client.output(
                bold(_("Attention")),
                header=darkred(" !!! "))

            entropy_client.output(
                mytxt, header=darkred(" !!! "))

            entropy_client.output(
                bold(_("Attention")),
                header=darkred(" !!! "))
            entropy_client.output(
                bold(_("Attention")),
                header=darkred(" !!! "))

    def _install_action(self, entropy_client, deps, recursive,
                        pretend, ask, verbose, quiet, empty,
                        config_files, deep, fetch, bdeps,
                        onlydeps, relaxed, multifetch, packages,
                        package_matches=None):
        """
        Solo Install action implementation.
        """
        inst_repo = entropy_client.installed_repository()
        action_factory = entropy_client.PackageActionFactory()

        with inst_repo.shared():

            self._advise_repository_update(entropy_client)
            if self._check_critical_updates:
                self._advise_packages_update(entropy_client)

            if package_matches is None:
                packages = self._scan_packages(
                    entropy_client, packages,
                    onlydeps=onlydeps)
                if not packages:
                    entropy_client.output(
                        "%s." % (
                            darkred(_("No packages found")),),
                        level="error", importance=1)
                    return 1, False
            else:
                packages = package_matches

            run_queue, removal_queue = self._generate_install_queue(
                entropy_client, packages, deps, empty, deep, relaxed,
                onlydeps, bdeps, recursive)
            if (run_queue is None) or (removal_queue is None):
                return 1, False
            elif not (run_queue or removal_queue):
                entropy_client.output(
                    "%s." % (blue(_("Nothing to do")),),
                    level="warning", header=darkgreen(" @@ "))
                return 0, True

            self._show_install_queue(
                entropy_client, inst_repo,
                run_queue, removal_queue, ask, pretend, quiet, verbose)

        if ask:
            rc = entropy_client.ask_question(
                "     %s" % (_("Would you like to continue ?"),))
            if rc == _("No"):
                return 1, False

        if pretend:
            return 0, True # yes, tell user

        if self._interactive:
            exit_st = self._accept_license(
                entropy_client, inst_repo, run_queue)
            if exit_st != 0:
                return 1, False

        ugc_thread = None
        down_data = {}
        exit_st = self._download_packages(
            entropy_client, run_queue, down_data, multifetch)
        if exit_st == 0:
            ugc_thread = ParallelTask(
                self._signal_ugc, entropy_client, down_data)
            ugc_thread.name = "UgcThread"
            ugc_thread.start()

        elif exit_st != 0:
            return 1, False

        # is --fetch on? then quit.
        if fetch:
            if ugc_thread is not None:
                ugc_thread.join()
            entropy_client.output(
                "%s." % (
                    blue(_("Download complete")),),
                header=darkred(" @@ "))
            return 0, False

        notification_lock = UpdatesNotificationResourceLock(
            output=entropy_client)
        package_set = set(packages)
        total = len(run_queue)

        notif_acquired = False
        try:
            # this is a best effort, we will not sleep if the lock
            # is not acquired because we may get blocked for an eternity
            # (well, for a very long time) in this scenario:
            # 1. RigoDaemon is running some action queue
            # 2. Another thread in RigoDaemon is stuck on the activity
            #    mutex with the notification lock held.
            # 3. We cannot move on here because of 2.
            # Nothing bad will happen if we just ignore the acquisition
            # state.
            notif_acquired = notification_lock.try_acquire_shared()

            for count, pkg_match in enumerate(run_queue, 1):

                metaopts = {
                    'removeconfig': config_files,
                }

                if onlydeps:
                    metaopts['install_source'] = \
                        etpConst['install_sources']['automatic_dependency']
                elif pkg_match in package_set:
                    metaopts['install_source'] = \
                        etpConst['install_sources']['user']
                else:
                    metaopts['install_source'] = \
                        etpConst['install_sources']['automatic_dependency']

                package_id, repository_id = pkg_match
                atom = entropy_client.open_repository(
                    repository_id).retrieveAtom(package_id)

                pkg = None
                try:
                    pkg = action_factory.get(
                        action_factory.INSTALL_ACTION,
                        pkg_match, opts=metaopts)

                    xterm_header = "equo (%s) :: %d of %d ::" % (
                        _("install"), count, total)

                    pkg.set_xterm_header(xterm_header)

                    entropy_client.output(
                        purple(atom),
                        count=(count, total),
                        header=darkgreen(" +++ ") + ">>> ")

                    exit_st = pkg.start()
                    if exit_st != 0:
                        if ugc_thread is not None:
                            ugc_thread.join()
                        return 1, True

                finally:
                    if pkg is not None:
                        pkg.finalize()

        finally:
            if notif_acquired:
                notification_lock.release()

        if ugc_thread is not None:
            ugc_thread.join()

        entropy_client.output(
            "%s." % (
                blue(_("Installation complete")),),
            header=darkred(" @@ "))
        return 0, True


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloInstall,
        SoloInstall.NAME,
        _("install or update packages or package files"))
    )
