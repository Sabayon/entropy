# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

"""
import importlib
import os
import sys
import errno
import argparse

# keep these before PackageBuilder due to the os.environ stuff inside
from matter.binpms.base import BaseBinaryPMS, BaseBinaryResourceLock
from matter.builder import PackageBuilder
from matter.lock import MatterResourceLock
from matter.output import purple, darkgreen, print_info, \
    print_warning, print_error, is_stdout_a_tty, nocolor
from matter.spec import SpecParser, MatterSpec
from matter.utils import print_exception


def install_exception_handler():
    sys.excepthook = handle_exception


def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__


def handle_exception(exc_class, exc_instance, exc_tb):

    # restore original exception handler, to avoid loops
    uninstall_exception_handler()

    if exc_class is KeyboardInterrupt:
        raise SystemExit(1)

    # always slap exception data (including stack content)
    print_exception(tb_data = exc_tb)


def matter_main(binary_pms, nsargs, cwd, specs):
    """
    Main application code run after all the resources setup.
    """

    try:
        binary_pms.validate_system()
    except BaseBinaryPMS.SystemValidationError as err:
        print_error("%s" % (err,))
        return 1

    print_info("matter loaded, starting to scan particles, pid: %s" % (
        os.getpid(),))

    def _teardown(_exit_st):
        if nsargs.post:
            _rc = PackageBuilder.teardown(
                nsargs.post, cwd, _exit_st)
            if _exit_st == 0 and _rc != 0:
                _exit_st = _rc
        return _exit_st

    # setup
    if nsargs.pre:
        _rc = PackageBuilder.setup(nsargs.pre, cwd)
        if _rc != 0:
            return _teardown(_rc)

    # sync portage
    if nsargs.sync:
        _rc = PackageBuilder.sync()
        if _rc != 0 and not nsargs.sync_best_effort:
            return _teardown(_rc)

    exit_st = 0
    completed = []
    not_found = []
    not_installed = []
    not_merged = []
    tainted_repositories = set()
    spec_count = 0
    tot_spec = len(specs)
    preserved_libs = False
    emerge_config = binary_pms.load_emerge_config()

    for spec in specs:

        spec_count += 1
        keep_going = spec["keep-going"] == "yes"
        local_completed = []

        tot_pkgs = len(spec['packages'])
        for pkg_count, packages in enumerate(spec['packages'], 1):

            builder = PackageBuilder(
                emerge_config, packages,
                spec, spec_count, tot_spec, pkg_count, tot_pkgs)
            _rc = builder.run()

            not_found.extend(builder.get_not_found_packages())
            not_installed.extend(
                builder.get_not_installed_packages())
            not_merged.extend(
                builder.get_not_merged_packages())
            preserved_libs = binary_pms.check_preserved_libraries(
                emerge_config)

            if preserved_libs and not nsargs.disable_preserved_libs:
                # abort, library breakages detected
                exit_st = 1
                print_error(
                    "preserved libraries detected, aborting")
                break

            # ignore _rc, we may have built pkgs even if _rc != 0
            built_packages = builder.get_built_packages()
            if built_packages:
                print_info("built packages, in queue: %s" % (
                        " ".join(built_packages),))
                local_completed.extend(
                    [x for x in built_packages \
                         if x not in local_completed])
                tainted_repositories.add(spec['repository'])

            # make some room
            print_info("")
            if _rc < 0:
                # ignore warning and go ahead
                continue
            else:
                exit_st = _rc
                if not keep_going:
                    break

        # call post-build cleanup operations,
        # run it unconditionally
        PackageBuilder.post_build(emerge_config)

        if preserved_libs and not nsargs.disable_preserved_libs:
            # completely abort
            break

        completed.extend([x for x in local_completed \
            if x not in completed])
        # portage calls setcwd()
        os.chdir(cwd)

        if local_completed and nsargs.commit:
            _rc = binary_pms.commit(
                spec['repository'],
                local_completed)
            if exit_st == 0 and _rc != 0:
                exit_st = _rc
                if not keep_going:
                    break

    if tainted_repositories and nsargs.push and nsargs.commit:
        if preserved_libs and nsargs.disable_preserved_libs:
            # cannot push anyway
            print_warning("Preserved libraries detected, cannot push !")
        elif not preserved_libs:
            for repository in tainted_repositories:
                _rc = binary_pms.push(repository)
                if exit_st == 0 and _rc != 0:
                    exit_st = _rc

    # print summary
    print_info("")
    print_info("Summary")
    print_info("Packages built:\n  %s" % (
        "\n  ".join(sorted(completed)),))
    print_info("Packages not built:\n  %s" % (
        "\n  ".join(sorted(not_merged)),))
    print_info("Packages not found:\n  %s" % (
        "\n  ".join(sorted(not_found)),))
    print_info("Packages not installed:\n  %s" % (
        "\n  ".join(sorted(not_installed)),))
    print_info("Preserved libs: %s" % (
        preserved_libs,))
    print_info("")

    return _teardown(exit_st)


def main():
    """
    Main App.
    """
    install_exception_handler()

    # disable color if standard output is not a TTY
    if not is_stdout_a_tty():
        nocolor()

    # Load Binary PMS modules
    import matter.binpms as _pms
    pms_dir = os.path.dirname(_pms.__file__)
    for thing in os.listdir(pms_dir):
        if thing.startswith("__init__.py"):
            continue

        thing = os.path.join(pms_dir, thing)
        if not os.path.isfile(thing):
            continue
        if not thing.endswith(".py"):
            continue

        name = os.path.basename(thing)
        name = name.rstrip(".py")
        package = "matter.binpms.%s" % (name,)

        try:
            importlib.import_module(package)  # they will then register
        except ImportError as err:
            pass
    avail_binpms = BaseBinaryPMS.available_pms

    matter_spec = MatterSpec()
    parser_data = matter_spec.parser_data_path()
    matter_spec_params = ""
    for spec_key in sorted(parser_data.keys()):
        par = parser_data[spec_key]
        matter_spec_params += "%s: %s\n" % (
            purple(spec_key),
            darkgreen(par.get("desc", "N/A")),)

    _env_vars_help = """\

Environment variables for Package Builder module:
%s       =  repository identifier
%s    =  alternative command used to sync Portage
                              default: %s
%s   =  alternative command used to sync Portage overlays
                              default: %s
%s  = custom emerge arguments
                              default: %s

Environment variables passed to --post executables:
%s        = exit status from previous execution phases, useful for detecting
                             execution errors.

Matter Resources Lock file you can use to detect if matter is running:
%s (--blocking switch makes it acquire in blocking mode)

Matter .spec file supported parameters:
%s

Available Binary PMSs:
%s
""" % (
        purple("MATTER_REPOSITORY_ID"),
        purple("MATTER_PORTAGE_SYNC_CMD"),
        darkgreen(PackageBuilder.DEFAULT_PORTAGE_SYNC_CMD),
        purple("MATTER_OVERLAYS_SYNC_CMD"),
        darkgreen(PackageBuilder.DEFAULT_OVERLAYS_SYNC_CMD),
        purple("MATTER_PORTAGE_BUILD_ARGS"),
        darkgreen(PackageBuilder.DEFAULT_PORTAGE_BUILD_ARGS),
        purple("MATTER_EXIT_STATUS"),
        darkgreen(MatterResourceLock.LOCK_FILE_PATH),
        matter_spec_params,
        "\n".join(
        ["%s: %s" % (purple(k.NAME), darkgreen(k.__name__)) \
             for k in avail_binpms]),)

    parser = argparse.ArgumentParser(
        description='Automated Packages Builder',
        epilog=_env_vars_help,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # * instead of + in order to support --sync only tasks
    parser.add_argument(
        "spec", nargs='+', metavar="<spec>", type=file,
        help="matter spec file")

    default_pms = avail_binpms[0]
    for k in avail_binpms:
        if k.DEFAULT:
            default_pms = k
            break
    parser.add_argument(
        "--pms", default=default_pms.NAME,
        help="specify an alternative Binary PMS (see --help for a list), "
        "current default: %s" % (default_pms.NAME,))

    parser.add_argument(
        "--blocking",
        help="when trying to acquire Binary PMS locks, "
        "block until success.",
        action="store_true")

    parser.add_argument("--commit",
        help="commit built packages to repository.",
        action="store_true")

    parser.add_argument(
        "--gentle",
        help="increase the system validation checks, be extremely "
        "careful wrt the current system status.",
        action="store_true")

    parser.add_argument("--pre", metavar="<exec>", type=file,
        help="executable to be called once for setup purposes.",
        default=None)

    parser.add_argument("--post", metavar="<exec>", type=file,
        help="executable to be called once for teardown purposes.",
        default=None)

    parser.add_argument(
        "--push",
        help="push Binary PMS package updates to online "
        "repository (only if --commit).",
        action="store_true")

    parser.add_argument(
        "--sync",
        help="sync Portage tree, and attached overlays, before starting.",
        action="store_true")

    parser.add_argument(
        "--sync-best-effort", default=False,
        help="sync Portage tree and attached overlays, as --sync, but do "
        "not exit if sync fails.",
        action="store_true")

    parser.add_argument(
        "--disable-preserved-libs",
        dest="disable_preserved_libs", default=False,
        help="disable prerserved libraries check.",
        action="store_true")

    # extend parser arguments
    for k in avail_binpms:
        k.extend_parser(parser)

    try:
        nsargs = parser.parse_args(sys.argv[1:])
    except IOError as err:
        if err.errno == errno.ENOENT:
            print_error(err.strerror + ": " + err.filename)
            return 1
        raise

    if os.getuid() != 0:
        # root access required
        print_error("superuser access required")
        return 1

    # parse spec files
    specs = []
    for spec_f in nsargs.spec:
        spec = SpecParser(spec_f)
        data = spec.parse()
        if data:
            specs.append(data)

    if not specs:
        print_error("invalid spec files provided")
        return 1

    # O(n) determine what is the BinaryPMS to use
    klass = None
    for k in avail_binpms:
        if k.NAME == nsargs.pms:
            klass = k
            break
    if klass is None:
        print_error("invalid Binary PMS specified: %s" % (nsargs.pms,))
        return 1

    binary_pms = None
    exit_st = 0
    cwd = os.getcwd()
    try:
        try:
            binary_pms = klass(cwd, nsargs)
        except BaseBinaryPMS.BinaryPMSLoadError as err:
            # repository not available or not configured
            print_error("Cannot load Binary Package Manager: %s" % (err,))
            return 3

        print_info("Loaded Binary PMS: %s" % (klass.NAME,))

        # validate repository entries of spec metadata
        for spec in specs:
            try:
                binary_pms.validate_spec(spec)
            except BaseBinaryPMS.SpecParserError as err:
                print_error("%s" % (err,))
                return 1

        if nsargs.blocking:
            print_info("--blocking enabled, please wait for locks...")

        resource_lock = binary_pms.get_resource_lock(nsargs.blocking)
        with resource_lock:
            with MatterResourceLock(nsargs.blocking):
                exit_st = matter_main(binary_pms, nsargs, cwd, specs)

    except BaseBinaryResourceLock.NotAcquired:
        print_error("unable to acquire PMS Resources lock")
        return 42
    except MatterResourceLock.NotAcquired:
        print_error("unable to acquire Matter Resources lock")
        return 42
    except KeyboardInterrupt:
        print_error("Keyboard Interrupt, pid: %s" % (os.getpid(),))
        return 42
    finally:
        if binary_pms is not None:
            binary_pms.shutdown()

    print_warning("")
    print_warning("")
    print_warning("Tasks complete, exit status: %d" % (exit_st,))
    return exit_st
