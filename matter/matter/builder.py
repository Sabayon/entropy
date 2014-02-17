# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

"""
import copy
import errno
import fcntl
import gc
import os
import shlex
import shutil
import subprocess
import tempfile

from matter.utils import mkstemp, mkdtemp, print_traceback
from matter.output import is_stdout_a_tty, print_info, print_warning, \
    print_error, getcolor, darkgreen, purple, brown

# default mandatory features
os.environ['ACCEPT_PROPERTIES'] = "* -interactive"
os.environ['FEATURES'] = "split-log"
os.environ['CMAKE_NO_COLOR'] = "yes"

from _emerge.actions import adjust_configs, apply_priorities
from _emerge.depgraph import backtrack_depgraph
try:
    from _emerge.actions import validate_ebuild_environment
except ImportError:
    # older portage versions
    from _emerge.main import validate_ebuild_environment
try:
    from _emerge.post_emerge import post_emerge
except ImportError:
    # older portage versions
    from _emerge.main import post_emerge
from _emerge.create_depgraph_params import create_depgraph_params
from _emerge.main import parse_opts
from _emerge.stdout_spinner import stdout_spinner
from _emerge.Scheduler import Scheduler
from _emerge.clear_caches import clear_caches
from _emerge.unmerge import unmerge
from _emerge.Blocker import Blocker

import portage.versions
import portage.dep
import portage.exception
import portage


class PackageBuilder(object):
    """
    Portage Package builder class
    """

    DEFAULT_PORTAGE_SYNC_CMD = "emerge --sync"
    PORTAGE_SYNC_CMD = shlex.split(os.getenv("MATTER_PORTAGE_SYNC_CMD",
        DEFAULT_PORTAGE_SYNC_CMD))

    DEFAULT_OVERLAYS_SYNC_CMD = "layman -S"
    OVERLAYS_SYNC_CMD = shlex.split(os.getenv("MATTER_OVERLAYS_SYNC_CMD",
        DEFAULT_OVERLAYS_SYNC_CMD))

    PORTAGE_BUILTIN_ARGS = ["--accept-properties=-interactive"]

    def __init__(self, binary_pms, emerge_config, packages, params,
        spec_number, tot_spec, pkg_number, tot_pkgs, pretend):
        self._binpms = binary_pms
        self._emerge_config = emerge_config
        self._packages = packages
        self._params = params
        self._spec_number = spec_number
        self._tot_spec = tot_spec
        self._pkg_number = pkg_number
        self._tot_pkgs = tot_pkgs
        self._pretend = pretend
        self._built_packages = []
        self._uninstalled_packages = []
        self._not_found_packages = []
        self._not_installed_packages = []
        self._not_merged_packages = []

        self._missing_use_packages = {}
        self._needed_unstable_keywords = set()
        self._needed_package_mask_changes = set()
        self._needed_license_changes = {}

    @classmethod
    def _build_standard_environment(cls, repository=None):
        env = os.environ.copy()
        if repository is not None:
            env["MATTER_REPOSITORY_ID"] = repository
        return env

    @classmethod
    def setup(cls, executable_hook_f, cwd):

        # ignore exit status
        subprocess.call(["env-update"])

        hook_name = executable_hook_f.name
        if not hook_name.startswith("/"):
            # complete with current directory
            hook_name = os.path.join(cwd, hook_name)

        print_info("spawning pre hook: %s" % (hook_name,))
        return subprocess.call([hook_name],
            env = cls._build_standard_environment())

    @classmethod
    def teardown(cls, executable_hook_f, cwd, exit_st):
        hook_name = executable_hook_f.name
        if not hook_name.startswith("/"):
            # complete with current directory
            hook_name = os.path.join(cwd, hook_name)

        print_info("spawning post hook: %s, passing exit status: %d" % (
            hook_name, exit_st,))
        env = cls._build_standard_environment()
        env["MATTER_EXIT_STATUS"] = str(exit_st)
        return subprocess.call([hook_name], env = env)

    def _build_execution_header_output(self):
        """
        Return a string used as stdout/stderr header text.
        """
        my_str = "{%s of %s particles | %s of %s packages | %s} " % (
            darkgreen(str(self._spec_number)),
            purple(str(self._tot_spec)),
            darkgreen(str(self._pkg_number)),
            purple(str(self._tot_pkgs)),
            brown(self._params["__name__"]),)  # file name
        return my_str

    def get_built_packages(self):
        """
        Return the list of successfully built packages.
        """
        return self._built_packages

    def get_uninstalled_packages(self):
        """
        Return the list of successfully uninstalled packages.
        """
        return self._uninstalled_packages

    def get_not_found_packages(self):
        """
        Return the list of packages that haven't been found in Portage.
        """
        return self._not_found_packages

    def get_not_installed_packages(self):
        """
        Return the list of packages that haven't been found on the System.
        """
        return self._not_installed_packages

    def get_not_merged_packages(self):
        """
        Return the list of packages that haven't been able to compile.
        """
        return self._not_merged_packages

    def get_missing_use_packages(self):
        """
        Return the list of packages that haven't been merged due to missing
        USE flags.
        """
        return self._missing_use_packages

    def get_needed_unstable_keywords(self):
        """
        Return the list of packages that haven't been merged due to the need
        of unstable keywords. For instance, if a needed package is unstable
        keyword masked in package.keywords, it will end up in this list.
        """
        return self._needed_unstable_keywords

    def get_needed_package_mask_changes(self):
        """
        Return the list of packages that haven't been merged due to the need
        of package.mask changes.
        """
        return self._needed_package_mask_changes

    def get_needed_license_changes(self):
        """
        Return the list of packages that haven't been merged due to the need
        of package.license changes.
        """
        return self._needed_license_changes

    def run(self):
        """
        Execute Package building action.
        """
        header = self._build_execution_header_output()
        print_info(
            header + "spawning package build: %s" % (
                " ".join(self._packages),))

        std_env = self._build_standard_environment(
            repository=self._params["repository"])

        matter_package_names = " ".join(self._packages)
        std_env["MATTER_PACKAGE_NAMES"] = matter_package_names

        # run pkgpre, if any
        pkgpre = self._params["pkgpre"]
        if pkgpre is not None:
            print_info("spawning --pkgpre: %s" % (pkgpre,))
            tmp_fd, tmp_path = mkstemp()
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                with open(pkgpre, "rb") as pkgpre_f:
                    tmp_f.write(pkgpre_f.read())
            try:
                # now execute
                os.chmod(tmp_path, 0o700)
                exit_st = subprocess.call([tmp_path], env = std_env)
                if exit_st != 0:
                    return exit_st
            finally:
                os.remove(tmp_path)
                # data might have become stale
                self._binpms.clear_cache()

        dirs_cleanup = []
        exit_st = self._run_builder(dirs_cleanup)

        std_env["MATTER_BUILT_PACKAGES"] = " ".join(self._built_packages)
        std_env["MATTER_FAILED_PACKAGES"] = " ".join(self._not_merged_packages)
        std_env["MATTER_NOT_INSTALLED_PACKAGES"] = " ".join(
            self._not_installed_packages)
        std_env["MATTER_NOT_FOUND_PACKAGES"] = " ".join(
            self._not_found_packages)
        std_env["MATTER_UNINSTALLED_PACKAGES"] = " ".join(
            self._uninstalled_packages)

        print_info("builder terminated, exit status: %d" % (exit_st,))

        # cleanup temporary directories registered on the queue
        for tmp_dir in dirs_cleanup:
            self.__cleanup_dir(tmp_dir)

        # run pkgpost, if any
        pkgpost = self._params["pkgpost"]
        if pkgpost is not None:
            print_info("spawning --pkgpost: %s" % (pkgpost,))
            tmp_fd, tmp_path = mkstemp()
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                with open(pkgpost, "rb") as pkgpost_f:
                    tmp_f.write(pkgpost_f.read())
            try:
                # now execute
                os.chmod(tmp_path, 0o700)
                post_exit_st = subprocess.call([tmp_path, str(exit_st)],
                    env = std_env)
                if post_exit_st != 0:
                    return post_exit_st
            finally:
                os.remove(tmp_path)
                # data might have become stale
                self._binpms.clear_cache()

        return exit_st

    def __cleanup_dir(self, tmp_dir):
        if os.path.isdir(tmp_dir) \
            and (not os.path.islink(tmp_dir)):
            shutil.rmtree(tmp_dir, True)

    def _get_sets_mod(self):
        """
        Return a portage.sets module object.
        """
        try:
            import portage._sets as sets
        except ImportError:
            try:
                # older portage, <= 2.2_rc67
                import portage.sets as sets
            except ImportError:
                sets = None
        return sets

    def _pre_graph_filters(self, package, portdb, vardb):
        """
        Execute basic, pre-graph generation (dependencies calculation)
        filters against the package dependency to see if it's eligible
        for the graph.
        """
        allow_rebuild = self._params["rebuild"] == "yes"
        allow_not_installed = self._params["not-installed"] == "yes"
        allow_downgrade = self._params["downgrade"] == "yes"
        accepted = []

        # now determine what's the installed version.
        best_installed = portage.best(vardb.match(package, use_cache=0))
        if (not best_installed) and (not allow_not_installed):
            # package not installed
            print_error("package not installed: %s, ignoring this one" % (
                    package,))
            self._not_installed_packages.append(package)
            return accepted

        if (not best_installed) and allow_not_installed:
            print_warning(
                "%s not installed, but 'not-installed: yes' provided" % (
                    package,))

        best_visibles = []
        try:
            best_visibles += portdb.xmatch("match-visible", package)
        except portage.exception.InvalidAtom:
            print_error("cannot match: %s, invalid atom" % (package,))

        # map all the cpvs to their slots
        cpv_slot_map = {}
        for pkg in best_visibles:
            obj = cpv_slot_map.setdefault(pkg.slot, [])
            obj.append(pkg)

        # then pick the best for each slot
        del best_visibles[:]
        for slot, pkgs in cpv_slot_map.items():
            pkg = portage.best(pkgs)
            best_visibles.append(pkg)
        best_visibles.sort()  # deterministic is better

        if not best_visibles:
            # package not found, return error
            print_error("cannot match: %s, ignoring this one" % (package,))
            self._not_found_packages.append(package)
            return accepted

        print_info("matched: %s for %s" % (", ".join(best_visibles), package,))

        for best_visible in best_visibles:

            cp = best_visible.cp
            slot = best_visible.slot
            cp_slot = "%s:%s" % (cp, slot)

            # determine what's the installed version.
            # we know that among all the best_visibles, there is one that
            # is installed. The question is whether we got it now.
            best_installed = portage.best(vardb.match(cp_slot, use_cache=0))
            if (not best_installed) and (not allow_not_installed):
                # package not installed
                print_warning("%s not installed, skipping" % (cp_slot,))
                continue

            build_only = self._params["build-only"] == "yes"
            cmp_res = -1
            if best_installed:
                print_info("found installed: %s for %s" % (
                        best_installed, package,))
                # now compare
                # -1 if best_installed is older than best_visible
                # 1 if best_installed is newer than best_visible
                # 0 if they are equal
                cmp_res = portage.versions.pkgcmp(
                    portage.versions.pkgsplit(best_installed),
                    portage.versions.pkgsplit(best_visible))
            elif (not best_installed) and build_only:
                # package is not installed, and build-only
                # is provided. We assume that the package
                # is being built and added to repositories directly.
                # This means that we need to query binpms to know
                # about the current version.
                print_info("package is not installed, and 'build-only: yes'. "
                           "Asking the binpms about the package state.")
                best_available = self._binpms.best_available(cp_slot)
                print_info("found available: %s for %s" % (
                        best_available, cp_slot))
                if best_available:
                    cmp_res = portage.versions.pkgcmp(
                        portage.versions.pkgsplit(best_available),
                        portage.versions.pkgsplit(best_visible))

            is_rebuild = cmp_res == 0

            if (cmp_res == 1) and (not allow_downgrade):
                # downgrade in action and downgrade not allowed, aborting!
                print_warning(
                    "%s would be downgraded, %s to %s, ignoring" % (
                        cp_slot, best_installed, best_visible,))
                continue

            if is_rebuild and (not allow_rebuild):
                # rebuild in action and rebuild not allowed, aborting!
                print_warning(
                    "%s would be rebuilt to %s, ignoring" % (
                        cp_slot, best_visible,))
                continue

            # at this point we can go ahead accepting package in queue
            print_info("package: %s [%s], accepted in queue" % (
                    best_visible, cp_slot,))
            accepted.append(best_visible)

        return accepted

    def _post_graph_filters(self, graph, vardb, portdb):
        """
        Execute post-graph generation (dependencies calculation)
        filters against the package dependencies to see if they're
        eligible for building.
        """
        # list of _emerge.Package.Package objects
        package_queue = graph.altlist()

        allow_soft_blocker = self._params["soft-blocker"] == "yes"
        if not allow_soft_blocker:
            blockers = [x for x in package_queue if isinstance(x, Blocker)]
            if blockers:
                # sorry, we're not allowed to have soft-blockers
                print_warning("the following soft-blockers were found:")
                print_warning("\n  ".join([x.atom for x in blockers]))
                print_warning("but 'soft-blocker: no' in config, aborting")
                return None

        # filter out blockers
        real_queue = [x for x in package_queue if not isinstance(
                x, Blocker)]
        # filter out broken or corrupted objects
        real_queue = [x for x in real_queue if x.cpv]

        # package_queue can also contain _emerge.Blocker.Blocker objects
        # not exposing .cpv field (but just .cp).
        dep_list = []
        for pobj in package_queue:
            if isinstance(pobj, Blocker):
                # blocker, list full atom
                dep_list.append(pobj.atom)
                continue
            cpv = pobj.cpv
            repo = pobj.repo
            if repo:
                repo = "::" + repo
            if cpv:
                dep_list.append(cpv+repo)
            else:
                print_warning(
                    "attention, %s has broken cpv: '%s', ignoring" % (
                        pobj, cpv,))

        # calculate dependencies, if --dependencies is not enabled
        # because we have to validate it
        if (self._params["dependencies"] == "no") \
                and (len(package_queue) > 1):
            deps = "\n  ".join(dep_list)
            print_warning("dependencies pulled in:")
            print_warning(deps)
            print_warning("but 'dependencies: no' in config, aborting")
            return None

        # protect against unwanted package unmerges
        if self._params["unmerge"] == "no":
            unmerges = [x for x in real_queue if x.operation == "uninstall"]
            if unmerges:
                deps = "\n  ".join([x.cpv for x in unmerges])
                print_warning("found package unmerges:")
                print_warning(deps)
                print_warning("but 'unmerge: no' in config, aborting")
                return None

        # inspect use flags changes
        allow_new_useflags = self._params["new-useflags"] == "yes"
        allow_removed_useflags = \
            self._params["removed-useflags"] == "yes"

        use_flags_give_up = False
        if (not allow_new_useflags) or (not allow_removed_useflags):
            # checking for use flag changes
            for pkg in real_queue:
                # frozenset
                enabled_flags = pkg.use.enabled
                inst_atom = portage.best(
                    vardb.match(pkg.slot_atom, use_cache=0))
                if not inst_atom:
                    # new package, ignore check
                    continue
                installed_flags = frozenset(
                    vardb.aux_get(inst_atom, ["USE"])[0].split())

                new_flags = enabled_flags - installed_flags
                removed_flags = installed_flags - enabled_flags

                if (not allow_new_useflags) and new_flags:
                    print_warning(
                        "ouch: %s wants these new USE flags: %s" % (
                            pkg.cpv+"::"+pkg.repo,
                            " ".join(sorted(new_flags)),))
                    use_flags_give_up = True
                if (not allow_removed_useflags) and removed_flags:
                    print_warning(
                        "ouch: %s has these USE flags removed: %s" % (
                            pkg.cpv+"::"+pkg.repo,
                        " ".join(sorted(removed_flags)),))
                    use_flags_give_up = True

        if use_flags_give_up:
            print_warning("cannot continue due to unmet "
                          "USE flags constraint")
            return None

        allow_downgrade = self._params["downgrade"] == "yes"
        # check the whole queue against downgrade directive
        if not allow_downgrade:
            allow_downgrade_give_ups = []
            for pkg in real_queue:
                inst_atom = portage.best(
                    vardb.match(pkg.slot_atom, use_cache=0))
                cmp_res = -1
                if inst_atom:
                    # -1 if inst_atom is older than pkg.cpv
                    # 1 if inst_atom is newer than pkg.cpv
                    # 0 if they are equal
                    cmp_res = portage.versions.pkgcmp(
                        portage.versions.pkgsplit(inst_atom),
                        portage.versions.pkgsplit(pkg.cpv))
                if cmp_res > 0:
                    allow_downgrade_give_ups.append((inst_atom, pkg.cpv))

            if allow_downgrade_give_ups:
                print_warning(
                    "cannot continue due to package "
                    "downgrade not allowed for:")
                for inst_atom, avail_atom in allow_downgrade_give_ups:
                    print_warning("  installed: %s | wanted: %s" % (
                        inst_atom, avail_atom,))
                return None

        changing_repo_pkgs = []
        for pkg in real_queue:
            wanted_repo = pkg.repo
            inst_atom = portage.best(
                vardb.match(pkg.slot_atom, use_cache=0))
            current_repo = vardb.aux_get(inst_atom, ["repository"])[0]
            if current_repo:
                if current_repo != wanted_repo:
                    changing_repo_pkgs.append(
                        (pkg.cpv, pkg.slot, current_repo, wanted_repo))

        if changing_repo_pkgs:
            print_warning("")
            print_warning(
                "Attention, packages are moving across SPM repositories:")
            for pkg_atom, pkg_slot, c_repo, w_repo in changing_repo_pkgs:
                print_warning("  %s:%s [%s->%s]" % (pkg_atom, pkg_slot,
                    c_repo, w_repo,))
            print_warning("")

        allow_spm_repo_change = self._params["spm-repository-change"] \
            == "yes"
        allow_spm_repo_change_if_ups = \
            self._params["spm-repository-change-if-upstreamed"] == "yes"

        if (not allow_spm_repo_change) and allow_spm_repo_change_if_ups:
            print_info("SPM repository change allowed if the original "
                       "repository does no longer contain "
                       "current packages.")

            # check if source repository still contains the package
            # in this case, set allow_spm_repo_change to True
            _allow = True
            for pkg_atom, pkg_slot, c_repo, w_repo in changing_repo_pkgs:
                pkg_key = portage.dep.dep_getkey("=%s" % (pkg_atom,))
                pkg_target = "%s:%s::%s" % (
                    pkg_key, pkg_slot, c_repo)
                pkg_match = portdb.xmatch("bestmatch-visible", pkg_target)
                if pkg_match:
                    # package still available in source repo
                    _allow = False
                    print_warning("  %s:%s, still in repo: %s" % (
                        pkg_atom, pkg_slot, c_repo,))
                    # do not break, print all the list
                    # break

            if _allow and changing_repo_pkgs:
                print_info(
                    "current packages are no longer in their "
                    "original repository, SPM repository change allowed.")
                allow_spm_repo_change = True

        if changing_repo_pkgs and (not allow_spm_repo_change):
            print_warning(
                "cannot continue due to unmet SPM repository "
                "change constraint")
            return None

        print_info("USE flags constraints are met for all "
                   "the queued packages")
        return real_queue

    def _setup_keywords(self, portdb, settings):
        """
        Setup ACCEPT_KEYWORDS for package.
        """
        # setup stable keywords if needed
        force_stable_keywords = self._params["stable"] == "yes"
        inherit_keywords = self._params["stable"] == "inherit"
        arch = settings["ARCH"][:]

        # reset match cache, or the new keywords setting
        # won't be considered
        portdb.melt()  # this unfreezes and clears xcache

        keywords = None
        if force_stable_keywords:
            keywords = "%s -~%s" % (arch, arch)
        elif inherit_keywords:
            pass # don't do anything
        else:
            keywords = "%s ~%s" % (arch, arch)

        settings.unlock()
        backupenv = settings.configdict["backupenv"]
        if keywords is not None:
            # this is just FYI, if the below method fails
            # this acts as a guard.
            settings["ACCEPT_KEYWORDS"] = keywords

            # this makes the trick, but might break in future
            # Portage versions. However, that's what Portage uses
            # internally.
            backupenv["ACCEPT_KEYWORDS"] = keywords
        else:
            # reset keywords to the environment default, if any
            env_keywords = os.getenv("ACCEPT_KEYWORDS")
            if env_keywords:
                backupenv["ACCEPT_KEYWORDS"] = env_keywords
            else:
                backupenv.pop("ACCEPT_KEYWORDS", None)

        settings.lock()
        # make sure that portdb is using our settings object and not
        # its own instance, or keyword masking won't work at its full
        # potential.
        portdb.settings = settings

    @classmethod
    def _setup_build_args(cls, spec):
        """
        Filter out invalid or unwanted Portage build arguments,
        like --ask and --buildpkgonly and add other ones.
        """
        unwanted_args = ["--ask", "-a", "--buildpkgonly", "-B"]

        for builtin_arg in cls.PORTAGE_BUILTIN_ARGS:
            yield builtin_arg

        for build_arg in spec["build-args"]:
            if build_arg not in unwanted_args:
                yield build_arg
            else:
                print_warning("cannot use emerge %s argument, you idiot",
                              build_arg)

        build_only = spec["build-only"] == "yes"
        if build_only:
            yield "--buildpkg"
            yield "--buildpkgonly"

    def _run_builder(self, dirs_cleanup_queue):
        """
        This method is called by _run and executes the whole package build
        logic, including constraints validation given by argv parameters.
        NOTE: negative errors indicate warnings that can be skipped.
        """
        if self._packages:
            first_package = self._packages[0]
        else:
            first_package = "_empty_"

        log_dir = mkdtemp(prefix="matter_build.",
            suffix="." + first_package.replace("/", "_").lstrip("<>=~"))
        dirs_cleanup_queue.append(log_dir)

        emerge_settings, emerge_trees, mtimedb = self._emerge_config

        # reset settings to original state, variables will be reconfigured
        # while others may remain saved due to backup_changes().
        emerge_settings.unlock()
        emerge_settings.reset()
        emerge_settings.lock()

        # Setup stable/unstable keywords, must be done on
        # emerge_settings bacause the reference is spread everywhere
        # in emerge_trees.
        # This is not thread-safe, but Portage isn't either, so
        # who cares!
        # ACCEPT_KEYWORDS is not saved and reset every time by the
        # reset() call above.
        portdb = emerge_trees[emerge_settings["ROOT"]]["porttree"].dbapi

        self._setup_keywords(portdb, emerge_settings)

        portdb.freeze()
        vardb = emerge_trees[emerge_settings["ROOT"]]["vartree"].dbapi
        vardb.settings.unlock()
        vardb.settings["PORT_LOGDIR"] = log_dir
        vardb.settings.backup_changes("PORT_LOGDIR")
        vardb.settings.lock()

        # Load the most current variables from /etc/profile.env, which
        # has been re-generated by the env-update call in _run()
        emerge_settings.unlock()
        emerge_settings.reload()
        emerge_settings.regenerate()
        emerge_settings.lock()

        sets = self._get_sets_mod()  # can be None
        sets_conf = None
        if sets is not None:
            sets_conf = sets.load_default_config(
                emerge_settings,
                emerge_trees[emerge_settings["ROOT"]])

        packages = []
        # execute basic, pre-graph generation filters against each
        # package dependency in self._packages.
        # This is just fast pruning of obvious obviousness.
        for package in self._packages:
            expanded_pkgs = []

            # package sets support
            if package.startswith("@") and sets_conf:
                try:
                    set_pkgs = sets_conf.getSetAtoms(package[1:])
                    expanded_pkgs.extend(sorted(set_pkgs))
                except sets.PackageSetNotFound:
                    # make it fail, add set directly
                    expanded_pkgs.append(package)
            else:
                expanded_pkgs.append(package)

            for exp_pkg in expanded_pkgs:
                accepted = self._pre_graph_filters(
                    exp_pkg, portdb, vardb)
                for best_visible in accepted:
                    packages.append((exp_pkg, best_visible))

        if not packages:
            print_warning("No remaining packages in queue, aborting.")
            return 0

        # at this point we can go ahead building packages
        print_info("starting to build:")
        for package, best_visible in packages:
            print_info(": %s -> %s" % (
                    package, best_visible,))

        if not getcolor():
            portage.output.nocolor()

        # non interactive properties, this is not really required
        # accept-properties just sets os.environ...
        build_args = list(self._setup_build_args(self._params))
        build_args += ["=" + best_v for _x, best_v in packages]

        myaction, myopts, myfiles = parse_opts(build_args)
        adjust_configs(myopts, emerge_trees)
        apply_priorities(emerge_settings)

        spinner = stdout_spinner()
        if "--quiet" in myopts:
            spinner.update = spinner.update_basic
        elif "--nospinner" in myopts:
            spinner.update = spinner.update_basic
        if emerge_settings.get("TERM") == "dumb" or not is_stdout_a_tty():
            spinner.update = spinner.update_basic

        print_info("emerge args: %s" % (" ".join(build_args),))

        params = create_depgraph_params(myopts, myaction)
        success, graph, favorites = backtrack_depgraph(emerge_settings,
            emerge_trees, myopts, params, myaction, myfiles, spinner)

        if not success:
            # print issues to stdout and give up
            print_warning("dependencies calculation failed, aborting")
            graph.display_problems()

            # try to collect some info about the failure
            bt_config = (graph.get_backtrack_infos() or {}).get("config", {})
            for k, v in bt_config.items():
                if k == "needed_use_config_changes":
                    for tup in v:
                        try:
                            pkg, (new_use, new_changes) = tup
                        except (ValueError, TypeError):
                            print_error(
                                "unsupported needed_use_config_changes: %s" % (
                                    tup,))
                            continue
                        obj = self._missing_use_packages.setdefault(
                            "%s" % (pkg.cpv,), {})
                        obj["cp:slot"] = "%s" % (pkg.slot_atom,)
                        changes = obj.setdefault("changes", {})
                        changes.update(copy.deepcopy(new_changes))
                elif k == "needed_unstable_keywords":
                    for pkg in v:
                        self._needed_unstable_keywords.add("%s" % (pkg.cpv,))
                elif k == "needed_p_mask_changes":
                    for pkg in v:
                        self._needed_package_mask_changes.add(
                            "%s" % (pkg.cpv,))
                elif k == "needed_license_changes":
                    for pkg, lics in v:
                        obj = self._needed_license_changes.setdefault(
                            "%s" % (pkg.cpv,), set())
                        obj.update(lics)
                else:
                    print_warning("unsupported backtrack info: %s -> %s" % (
                            k, v,))

            return 0
        print_info("dependency graph generated successfully")

        real_queue = self._post_graph_filters(graph, vardb, portdb)
        if real_queue is None:
            # post-graph filters not passed, giving up
            return 0

        merge_queue = [x for x in real_queue if x.operation == "merge"]
        unmerge_queue = [x for x in real_queue if x.operation == "uninstall"]
        if merge_queue:
            print_info("about to build the following packages:")
            for pkg in merge_queue:
                print_info("  %s" % (pkg.cpv,))
        if unmerge_queue:
            print_info("about to uninstall the following packages:")
            for pkg in unmerge_queue:
                print_info("  %s" % (pkg.cpv,))

        if self._pretend:
            print_info("portage spawned with --pretend, done!")
            return 0

        # re-calling action_build(), deps are re-calculated though
        validate_ebuild_environment(emerge_trees)
        mergetask = Scheduler(emerge_settings, emerge_trees, mtimedb,
            myopts, spinner, favorites=favorites,
            graph_config=graph.schedulerGraph())
        del graph
        self.clear_caches(self._emerge_config)
        retval = mergetask.merge()

        not_merged = []
        real_queue_map = dict((pkg.cpv, pkg) for pkg in real_queue)
        failed_package = None
        if retval != 0:
            merge_list = mtimedb.get("resume", {}).get("mergelist", [])
            for _merge_type, _merge_root, merge_atom, _merge_act in merge_list:
                merge_atom = "%s" % (merge_atom,)
                if failed_package is None:
                    # we consider the first encountered package the one
                    # that failed. It makes sense since packages are built
                    # serially as of today.
                    # Also, the package object must be available in our
                    # package queue, so grab it from there.
                    failed_package = real_queue_map.get(merge_atom)
                not_merged.append(merge_atom)
                self._not_merged_packages.append(merge_atom)

        for pkg in real_queue:
            cpv = pkg.cpv
            if not cpv:
                print_warning("package: %s, has broken cpv: '%s', ignoring" % (
                        pkg, cpv,))
            elif cpv not in not_merged:
                if pkg.operation == "merge":
                    # add to build queue
                    print_info("package: %s, successfully built" % (cpv,))
                    self._built_packages.append("%s" % (cpv,))
                else:
                    # add to uninstall queue
                    print_info("package: %s, successfully uninstalled" % (cpv,))
                    self._uninstalled_packages.append("%s" % (cpv,))

        post_emerge(myaction, myopts, myfiles, emerge_settings["ROOT"],
            emerge_trees, mtimedb, retval)

        subprocess.call(["env-update"])

        if failed_package is not None:
            print_warning("failed package: %s::%s" % (failed_package.cpv,
                failed_package.repo,))

        if self._params["buildfail"] and (failed_package is not None):

            std_env = self._build_standard_environment(
                repository=self._params["repository"])
            std_env["MATTER_PACKAGE_NAMES"] = " ".join(self._packages)
            std_env["MATTER_PORTAGE_FAILED_PACKAGE_NAME"] = failed_package.cpv
            std_env["MATTER_PORTAGE_REPOSITORY"] = failed_package.repo
            # call pkgfail hook if defined
            std_env["MATTER_PORTAGE_BUILD_LOG_DIR"] = os.path.join(log_dir,
                "build")

            buildfail = self._params["buildfail"]
            print_info("spawning buildfail: %s" % (buildfail,))
            tmp_fd, tmp_path = mkstemp()
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                with open(buildfail, "rb") as buildfail_f:
                    tmp_f.write(buildfail_f.read())
            try:
                # now execute
                os.chmod(tmp_path, 0o700)
                exit_st = subprocess.call([tmp_path], env = std_env)
                if exit_st != 0:
                    return exit_st
            finally:
                os.remove(tmp_path)

        print_info("portage spawned, return value: %d" % (retval,))
        return retval

    @classmethod
    def clear_caches(cls, emerge_config):
        """
        Clear Portage and Binary PMS caches.
        """
        emerge_settings, emerge_trees, _mtimedb = emerge_config
        clear_caches(emerge_trees)
        # clearing vartree.dbapi.cpcache doesn't seem to make a big diff
        root_tree = emerge_trees[emerge_settings["ROOT"]]
        vdb = root_tree["vartree"].dbapi
        for method_name in ("_clear_cache",):
            method = getattr(vdb, method_name, None)
            if method is not None:
                method()
            else:
                print_error(
                    "vartree does not have a %s method anymore" % (
                        method_name,))

        root_tree["porttree"].dbapi.close_caches()
        root_tree["porttree"].dbapi = portage.dbapi.porttree.portdbapi(
            root_tree["porttree"].settings)

        for x in range(10):
            count = gc.collect()
            if not count:
                break

    @classmethod
    def post_build(cls, spec, emerge_config):
        """
        Execute Portage post-build tasks.
        """
        print_info("executing post-build operations, please wait...")

        emerge_settings, emerge_trees, mtimedb = emerge_config
        if "yes" == emerge_settings.get("AUTOCLEAN"):
            build_args = list(cls._setup_build_args(spec))
            _action, opts, _files = parse_opts(build_args)
            unmerge(emerge_trees[emerge_settings["ROOT"]]["root_config"],
                    opts, "clean", [], mtimedb["ldpath"], autoclean=1)

    @classmethod
    def sync(cls):
        """
        Execute Portage and Overlays sync
        """
        portdir = os.getenv("PORTDIR", "/usr/portage")
        portdir_lock_file = os.path.join(portdir, ".matter_sync.lock")

        print_info("synchronizing the repositories...")
        print_info("About to acquire %s..." % (portdir_lock_file,))
        with open(portdir_lock_file, "a+") as lock_f:
            while True:
                try:
                    fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
                    break
                except IOError as err:
                    if err.errno == errno.EINTR:
                        continue
                    raise

            sync_cmd = cls.PORTAGE_SYNC_CMD
            std_env = cls._build_standard_environment()
            exit_st = subprocess.call(sync_cmd, env = std_env)
            if exit_st != 0:
                return exit_st

            # overlays update
            overlay_cmd = cls.OVERLAYS_SYNC_CMD
            return subprocess.call(overlay_cmd, env = std_env)
