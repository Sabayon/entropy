#!/usr/bin/python2
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import os
import pdb
import sys
import errno
import re
import tempfile
sys.path.insert(0, '/usr/lib/entropy/lib')
sys.path.insert(0, '/usr/lib/entropy/server')
sys.path.insert(0, '/usr/lib/entropy/client')
sys.path.insert(0, '../lib')
sys.path.insert(0, '../server')
sys.path.insert(0, '../client')

from entropy.exceptions import SystemDatabaseError, OnlineMirrorError, \
    RepositoryError, PermissionDenied, FileNotFound, SPMError
try:
    from entropy.transceivers.exceptions import TransceiverError, \
        TransceiverConnectionError
except ImportError:
    TransceiverError = None
    TransceiverConnectionError = None

from entropy.output import red, darkred, darkgreen, TextInterface, \
    print_generic, print_error, print_warning, readtext, nocolor, \
    is_stdout_a_tty, bold, purple, teal, blue
from entropy.cli import print_menu, print_bashcomp, read_equo_release
from entropy.const import etpConst, etpUi, const_convert_to_rawstring
import entropy.tools
try:
    from entropy.i18n import _
except ImportError:
    def _(x):
        return x

etp_exit_messages = {
    0: _("You should run equo --help"),
    1: _("You didn't run equo --help, did you?"),
    2: _("Did you even read equo --help??"),
    3: _("I give up. Run that equo --help !!!!!!!"),
    4: _("OH MY GOD. RUN equo --heeeeeeeeeeeeeelp"),
    5: _("Illiteracy is a huge problem in this world"),
    6: _("Ok i give up, you are hopeless"),
    7: _("Go to hell."),
}

help_opts = [
    None,
    (0, " ~ %s ~ " % ("equo",), 2,
        'Entropy Framework Client - (C) 2007-%s' % (entropy.tools.get_year(),) ),
    None,
    (0, _('Basic Options'), 0, None),
    None,
    (1, '--help', 2, _('this output')),
    (1, '--version', 1, _('print version')),
    (1, '--nocolor', 1, _('disable colorized output')),
    (1, '--color', 2, _('force colorized output')),
    (1, '--bashcomp', 1, _('print a bash completion script to stdout')),
    None,
    (0, _('Application Options'), 0, None),
    None,
    (1, 'update', 2, _('update configured repositories')),
    (2, '--force', 2, _('force sync regardless repositories status')),
    None,
    (1, 'repo', 1, _('manage your repositories')),
        (2, 'enable', 3, _('enable given repository')),
        (2, 'disable', 3, _('disable given repository')),
        (2, 'add <string>', 2, _('add repository (pass repository string)')),
        (2, 'remove <id>', 2, _('remove repository')),
        (2, 'mirrorsort <id>', 2, _('reorder mirrors basing on response time')),
        (2, 'merge [sources] <dest>', 1, _('merge content of source repos to dest [for developers]')),
        (3, '--conflicts', 1, _('also remove dependency conflicts during merge')),
    (1, 'notice [repos]', 1, _('repository notice board reader')),
    (1, 'status', 2, _('show respositories status')),
    None,
    (1, 'search', 2, _('search packages in repositories'), ),
    (1, 'match', 2, _('match a package in repositories')),
    (2, '--multimatch', 1, _('return all the possible matches')),
    (2, '--installed', 1, _('match inside installed packages repository')),
    (2, '--multirepo', 1, _('return matches from every repository')),
    (2, '--showrepo', 1, _('print repository information (w/--quiet)')),
    (2, '--showdesc', 1, _('print description too (w/--quiet)')),
    None,
    (1, 'hop <branch>', 1, _('upgrade your distribution to a new release (branch)')),
    None,
    (1, 'upgrade', 1, _('update system with the latest available packages')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--fetch', 2, _('just download packages')),
    (2, '--pretend', 1, _('only show what would be done')),
    (2, '--verbose', 1, _('show more details about what is going on')),
    (2, '--replay', 1, _('reinstall all the packages and their dependencies')),
    (2, '--empty', 2, _('same as --replay')),
    (2, '--resume', 1, _('resume previously interrupted operations')),
    (2, '--skipfirst', 1, _('used with --resume, makes the first package to be skipped')),
    (2, '--multifetch', 1, _('download multiple packages in parallel (default 3)')),
    (2, '--multifetch=N', 1, _('download N packages in parallel (max 10)')),
    None,
    (1, 'security', 1, _('security infrastructure functions')),
    (2, 'oscheck', 2, _('verify installed files using stored checksums')),
    (3, '--mtime', 2, _('consider mtime instead of SHA256 (false positives ahead)')),
    (3, '--assimilate', 1, _('update hashes and mtime (useful after editing config files)')),
    (3, '--reinstall', 1, _('reinstall faulty packages')),
    (3, '--quiet', 2, _('show less details (useful for scripting)')),
    (3, '--verbose', 1, _('also list removed files')),
    (2, 'update', 2, _('download the latest Security Advisories')),
    (3, '--force', 2, _('force download even if already up-to-date')),
    (2, 'list', 2, _('list all the available Security Advisories')),
    (3, '--affected', 1, _('list only affected')),
    (3, '--unaffected', 1, _('list only unaffected')),
    (2, 'info', 2, _('show information about provided advisories identifiers')),
    (2, 'install', 2, _('automatically install all the available security updates')),
    (3, '--ask', 2, _('ask before making any changes')),
    (3, '--fetch', 2, _('just download packages')),
    (3, '--pretend', 1, _('just show what would be done')),
    (3, '--quiet', 2, _('show less details (useful for scripting)')),
    None,
    (1, 'install', 1, _('install atoms or binary packages')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    (2, '--fetch', 2, _('just download packages without doing the install')),
    (2, '--nodeps', 1, _('do not pull in any dependency')),
    (2, '--bdeps', 2, _('also pull in build-time dependencies')),
    (2, '--resume', 1, _('resume previously interrupted operations')),
    (2, '--skipfirst', 1, _('used with --resume, makes the first package in queue to be skipped')),
    (2, '--clean', 2, _('remove downloaded packages after being used')),
    (2, '--empty', 2, _('pull all the dependencies in, regardless their state')),
    (2, '--relaxed', 1, _('calm down dependencies resolution algorithm (might be risky)')),
    (2, '--deep', 2, _('makes dependency rules stricter')),
    (2, '--verbose', 1, _('show more details about what is going on')),
    (2, '--configfiles', 1, _('makes old configuration files to be removed')),
    (2, '--multifetch', 1, _('download multiple packages in parallel (default 3)')),
    (2, '--multifetch=N', 1, _('download N packages in parallel (max 10)')),
    None,
    (1, 'source', 2, _('download atoms source code')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    (2, '--nodeps', 1, _('do not pull in any dependency')),
    (2, '--relaxed', 1, _('calm down dependencies resolution algorithm (might be risky)')),
    (2, '--savehere', 1, _('save sources in current working directory')),
    None,
    (1, 'fetch', 2, _('just download packages without doing the install')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    (2, '--nodeps', 1, _('do not pull in any dependency')),
    (2, '--relaxed', 1, _('calm down dependencies resolution algorithm (might be risky)')),
    (2, '--multifetch', 1, _('download multiple packages in parallel (default 3)')),
    (2, '--multifetch=N', 1, _('download N packages in parallel (max 10)')),
    None,
    (1, 'remove', 2, _('remove one or more packages')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    (2, '--nodeps', 1, _('do not pull in any dependency')),
    (2, '--deep', 2, _('also pull unused dependencies where reverse deps list is empty')),
    (2, '--empty', 2, _('when used with --deep, helps the removal of virtual packages')),
    (2, '--configfiles', 1, _('makes configuration files to be removed')),
    (2, '--force-system', 1, _('dangerous: forces system packages removal, do not use this!')),
    (2, '--resume', 1, _('resume previously interrupted operations')),
    None,
    (1, 'mask', 2, _('mask one or more packages')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    (1, 'unmask', 2, _('unmask one or more packages')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    None,
    (1, 'config', 2, _('configure one or more installed packages')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    None,
    (1, 'deptest', 2, _('look for unsatisfied dependencies')),
    (2, '--quiet', 2, _('show less details (useful for scripting)')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    None,
    (1, 'unusedpackages', 2, _('look for unused packages (pay attention)')),
    (2, '--quiet', 2, _('show less details (useful for scripting)')),
    (2, '--sortbysize', 1, _('sort packages by disk size')),
    None,
    (1, 'libtest', 2, _('look for missing libraries')),
        (2, '--dump', 2, _('dump results to files')),
        (2, '--listfiles', 1, _('print broken files to stdout')),
        (2, '--quiet', 2, _('show less details (useful for scripting)')),
        (2, '--ask', 2, _('ask before making any changes')),
        (2, '--pretend', 1, _('just show what would be done')),
    None,
    (1, 'conf', 2, _('configuration files update tool')),
    (2, 'info', 2, _('show configuration files to be updated')),
    (2, 'update', 2, _('run the configuration files update function')),
    None,
    (1, 'query', 2, _('do misc queries on repository and local databases')),
        (2, 'belongs', 2, _('search from what package a file belongs')),
        (2, 'changelog', 1, _('show packages changelog')),
        (2, 'revdeps', 2, _('search what packages depend on the provided atoms')),
        (2, 'description', 1, _('search packages by description')),
        (2, 'files', 2, _('show files owned by the provided atoms')),
        (2, 'installed', 1, _('search a package into the local database')),
        (2, 'license', 2, _('show packages owning the provided licenses')),
        (2, 'list', 2, _('list packages based on the chosen parameter below')),
            (3, 'installed', 2, _('list installed packages')),
                (4, '--by-user', 2, _('only packages installed by user')),
            (3, 'available [repos]', 1, _('list available packages')),
        (2, 'mimetype', 1, _('search packages able to handle given mimetypes')),
            (3, '--installed', 2, _('search among installed packages')),
        (2, 'associate', 1, _('associate given file paths to applications able to read them')),
            (3, '--installed', 2, _('search among installed packages')),
        (2, 'needed', 2, _('show runtime libraries needed by the provided atoms')),
        (2, 'orphans', 2, _('search files that do not belong to any package')),
        (2, 'removal', 2, _('show the removal tree for the specified atoms')),
        (2, 'required', 1, _('show atoms needing the provided libraries')),
        (2, 'sets', 2, _('search available package sets')),
        (2, 'slot', 2, _('show packages owning the provided slot')),
        (2, 'tags', 2, _('show packages owning the provided tags')),
        (2, 'graph', 2, _('show direct depdendencies tree for provided installable atoms')),
            (3, '--complete', 2, _('include system packages, build deps and circularity information')),
        (2, 'revgraph', 1, _('show reverse depdendencies tree for provided installed atoms')),
            (3, '--complete', 2, _('include system packages, build deps and circularity information')),
        (2, '--verbose', 1, _('show more details')),
        (2, '--quiet', 2, _('print results in a scriptable way')),
    None,

]

help_opts_ext_info = [
    (0, _('!!! Use --verbose to get full help output'), 0, None),
    None,
]

help_opts_extended = [
    (0, _('Extended Options'), 0, None),
    None,
    (1, 'smart', 2, _('handles extended functionalities')),
    (2, 'package', 1, _('make a smart package for the provided atoms (multiple packages into one file)')),
    (2, 'quickpkg', 1, _('recreate an Entropy package from your System')),
    (3, '--savedir', 1, _('save new packages into the specified directory')),
    (2, 'inflate', 2, _('convert provided Source Package Manager package files into Entropy packages')),
    (3, '--savedir', 1, _('save new packages into the specified directory')),
    (2, 'deflate', 2, _('convert provided Entropy packages into Source Package Manager ones')),
    (3, '--savedir', 1, _('save new packages into the specified directory')),
    (2, 'extract', 2, _('extract Entropy metadata from provided Entropy package files')),
    (3, '--savedir', 1, _('save new metadata into the specified directory')),
    None,
    (1, 'rescue', 1, _('contains System rescue tools')),
        (2, 'check', 2, _('check installed packages repository for errors')),
        (2, 'vacuum', 2, _('remove installed packages repository internal indexes to save disk space')),
        (2, 'generate', 1, _('generate installed packages database using Source Package Manager repositories')),
        (2, 'resurrect', 1, _('generate installed packages database using files on the system [last hope]')),
        (2, 'spmuids', 2, _('regenerate SPM UIDs map (SPM <-> Entropy packages)')),
        (2, 'spmsync', 2, _('makes Entropy aware of your Source Package Manager updated packages')),
        (2, 'backup', 2, _('backup the current Entropy installed packages database')),
        (2, 'restore', 2, _('restore a previously backed up Entropy installed packages database')),
    None,
    (1, 'ugc', 2, _('handles User Generated Content features')),
        (2, 'login <repository>', 1, _('login against a specified repository')),
        (2, 'logout <repository>', 1, _('logout from a specified repository')),
            (3, '--force', 3, _('force action')),
        (2, 'documents <repository>', 1, _('manage package documents for the selected repository (comments, files, videos)')),
            (3, 'get <pkgkey>', 2, _('get available documents for the specified package key (example: x11-libs/qt)')),
            (3, 'add <pkgkey>', 2, _('add a new document to the specified package key (example: x11-libs/qt)')),
            (3, 'remove <docs ids>', 1, _('remove documents from database using their identifiers')),
        (2, 'vote <repository>', 1, _('manage package votes for the selected repository')),
            (3, 'get <pkgkey>', 2, _('get vote for the specified package key (example: x11-libs/qt)')),
            (3, 'add <pkgkey>', 2, _('add vote for the specified package key (example: x11-libs/qt)')),

    None,
    (1, 'cache', 2, _('handles Entropy cache')),
        (2, 'clean', 2, _('clean Entropy cache')),
        (2, '--verbose', 1, _('show more details')),
        (2, '--quiet', 2, _('print results in a scriptable way')),
    None,
    (1, 'cleanup', 2, _('remove downloaded packages and clean temp. directories')),
    None,
    (1, '--info', 2, _('show system information')),
    None,
]

def _warn_live_system():
    if entropy.tools.islive():
        print_warning("")
        print_warning(purple("Entropy is running off a Live System"))
        print_warning(teal("Performance and stability could get severely compromised"))
        print_warning("")

def _do_text_ui(main_cmd, options):
    _warn_live_system()
    import text_ui
    return text_ui.package([main_cmd] + options)

def _do_text_repos(main_cmd, options):
    _warn_live_system()
    import text_repositories
    return text_repositories.repositories([main_cmd] + options)

def _do_text_security(main_cmd, options):
    _warn_live_system()
    import text_security
    return text_security.security(options)

def _do_text_query(main_cmd, options):
    import text_query
    return text_query.query(options)

def _do_text_smart(main_cmd, options):
    _warn_live_system()
    import text_smart
    return text_smart.smart(options)

def _do_text_conf(main_cmd, options):
    _warn_live_system()
    import text_configuration
    return text_configuration.configurator(options)

def _do_text_cache(main_cmd, options):
    _warn_live_system()
    import text_cache
    return text_cache.cache(options)

def _do_search(main_cmd, options):
    import text_query
    return text_query.query([main_cmd] + options)

def _do_text_rescue(main_cmd, options):
    _warn_live_system()
    if main_cmd == "database":
        print_warning("")
        print_warning("'%s' %s: '%s'" % (
            purple("equo database"),
            blue(_("is deprecated, please use")),
            darkgreen("equo rescue"),))
        print_warning("")
    import text_rescue
    return text_rescue.database(options)

def _do_text_ugc(main_cmd, options):
    import text_ugc
    return text_ugc.ugc(options)

def _do_text_cleanup(main_cmd, options):

    if not entropy.tools.is_root():
        mytxt = _("You are not root")
        print_error(red(mytxt+"."))
        return 1

    acquired = False
    client = None
    try:
        from entropy.cli import cleanup
        from entropy.client.interfaces import Client
        client = Client(repo_validation = False,
            indexing = False, installed_repo = False)
        acquired = entropy.tools.acquire_entropy_locks(client)
        if not acquired:
            print_error(darkgreen(_("Another Entropy is currently running.")))
            return 1

        dirs = [etpConst['logdir'], etpConst['entropyunpackdir']]
        for rel in etpConst['packagesrelativepaths']:
            # backward compatibility, packages are moved to packages/ dir,
            # including nonfree, restricted etc.
            dirs.append(os.path.join(etpConst['entropyworkdir'], rel))
            # new location
            dirs.append(os.path.join(etpConst['entropypackagesworkdir'], rel))
        cleanup(dirs)
        return 0

    finally:
        if acquired:
            entropy.tools.release_entropy_locks(client)
        if client is not None:
            client.shutdown()

def do_moo(*args):
    t = """ _____________
< Entromoooo! >
 -------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\\
                ||----w |
                ||     ||
"""
    sys.stdout.write(t)
    sys.stdout.flush()

def do_lxnay(*args):
    t = """ _____________
< I love lxnay! >
 ---------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\\
                ||----w |
                ||     ||
"""
    sys.stdout.write(t)
    sys.stdout.flush()

CMDS_MAP = {
    "install": _do_text_ui,
    "remove": _do_text_ui,
    "config": _do_text_ui,
    "world": _do_text_ui,
    "upgrade": _do_text_ui,
    "deptest": _do_text_ui,
    "unusedpackages": _do_text_ui,
    "libtest": _do_text_ui,
    "source": _do_text_ui,
    "fetch": _do_text_ui,
    "hop": _do_text_ui,
    "mask": _do_text_ui,
    "unmask": _do_text_ui,

    "moo": do_moo,
    "lxnay": do_lxnay,
    "god": do_lxnay,
    "love_lxnay": do_lxnay,
    "w00t": do_lxnay,

    "repo": _do_text_repos,
    "update": _do_text_repos,
    "repoinfo": _do_text_repos,
    "status": _do_text_repos,
    "notice": _do_text_repos,

    "security": _do_text_security,
    "query": _do_text_query,
    "smart": _do_text_smart,
    "conf": _do_text_conf,
    "cache": _do_text_cache,

    "match": _do_search,
    "search": _do_search,
    "database": _do_text_rescue,
    "rescue": _do_text_rescue,
    "ugc": _do_text_ugc,

    "cleanup": _do_text_cleanup,

}

def _match_bashcomp(cmdline):
    # speed up loading, preload singleton with faster settings
    from entropy.client.interfaces import Client
    client = Client(repo_validation = False,
        indexing = False, installed_repo = False)
    try:
        if client.installed_repository() is None:
            return []
        import text_query
        return text_query.match_package([cmdline[-1]], client,
            get_results = True, multi_match = "--multimatch" in cmdline,
            multi_repo = "--multirepo" in cmdline)
    finally:
        client.shutdown()

def _search_bashcomp(cmdline, from_installed = False, ignore_installed = False):
    # speed up loading, preload singleton with faster settings
    from entropy.client.interfaces import Client
    client = Client(repo_validation = False,
        indexing = False, installed_repo = False)
    try:
        if client.installed_repository() is None:
            return []
        import text_query
        return text_query.search_package([cmdline[-1]], client,
            get_results = True, from_installed = from_installed,
                ignore_installed = ignore_installed)
    finally:
        client.shutdown()

def _remove_bashcomp(cmdline):
    return _search_bashcomp(cmdline, from_installed = True)

def _install_bashcomp(cmdline):
    return _search_bashcomp(cmdline, ignore_installed = True)

def _repo_enable_disable_bashcomp(cmdline):
    try:
        action = cmdline[1]
    except IndexError:
        return []
    from entropy.core.settings.base import SystemSettings as SysSet
    sys_settings = SysSet()
    if action == "enable":
        return sorted(sys_settings['repositories']['excluded'].keys())
    elif action == "disable":
        return sorted(sys_settings['repositories']['available'].keys())
    elif action == "remove":
        avail = list(sys_settings['repositories']['available'].keys())
        excl = list(sys_settings['repositories']['excluded'].keys())
        return sorted(set(avail+excl))
    return []

BASHCOMP_MAP = {
    'search': _search_bashcomp,
    'match': _match_bashcomp,
    'remove': _remove_bashcomp,
    'install': _install_bashcomp,
    'repo': _repo_enable_disable_bashcomp,
}

options = sys.argv[1:]
_options = []

supported_short_opts = ["-a", "-q", "-v", "-p", "-N"]

opt_r = re.compile("^(\\-)([a-z]+)$")
for n in range(len(options)):

    if opt_r.match(options[n]):
        x_found_opts = ["-%s" % (d,) for d in options[n][1:]]

        supported = True
        for x in x_found_opts:
            if x not in supported_short_opts:
                supported = False
                break

        if not supported or not x_found_opts:
            continue

        del options[n]
        options.extend(x_found_opts)

bashcomp_enabled = False
force_color = False
for opt in options:
    if opt in ["--nocolor", "-N"]:
        nocolor()
    elif opt in ["--color", "-C"]:
        force_color = True
    elif opt == "--debug":
        continue
    elif opt in ["--quiet", "-q"]:
        etpUi['quiet'] = True
    elif opt in ["--verbose", "-v"]:
        etpUi['verbose'] = True
    elif opt == "--bashcomp":
        bashcomp_enabled = True
    elif opt in ["--ask", "-a"]:
        etpUi['ask'] = True
    elif opt in ["--pretend", "-p"]:
        etpUi['pretend'] = True
    elif opt == "--ihateprint":
        etpUi['mute'] = True
    elif opt == "--clean":
        etpUi['clean'] = True
    else:
        _options.append(opt)
options = _options

# Check if we need to disable colors
if (not force_color) and (not is_stdout_a_tty()):
    nocolor()

if bashcomp_enabled:
    print_bashcomp(help_opts + help_opts_extended, options, BASHCOMP_MAP)
    raise SystemExit(0)

if "help" in options:
    options.insert(0, "--help")
    options = [x for x in options if x != "help"]

# print help
if (not options) or ("--help" in options):
    print_menu(help_opts, args = options[:])
    if etpUi['verbose'] or options:
        print_menu(help_opts_extended, args = options[:])
    else:
        print_menu(help_opts_ext_info, args = options[:])
    if not options:
        print_error(_("not enough parameters"))
        raise SystemExit(1)
    raise SystemExit(0)

# print version
if options[0] == "--version":
    print_generic("entropy: "+etpConst['entropyversion'])
    print_generic("equo: "+read_equo_release())
    raise SystemExit(0)
elif options[0] == "--info":
    import text_rescue
    text_rescue.database(["info"])
    raise SystemExit(0)

def readerrorstatus():
    try:
        f = open(etpConst['errorstatus'], "r")
        status = int(f.readline().strip())
        f.close()
        return status
    except (IOError, OSError, ValueError):
        writeerrorstatus(0)
        return 0

def writeerrorstatus(status):
    try:
        f = open(etpConst['errorstatus'], "w")
        f.write(str(status))
        f.flush()
        f.close()
    except (IOError, OSError,):
        pass

def handle_exception(exc_class, exc_instance, exc_tb):

    # restore original exception handler, to avoid loops
    uninstall_exception_handler()

    entropy.tools.kill_threads()

    def try_to_kill_cacher():
        try:
            from entropy.cache import EntropyCacher
        except ImportError:
            return
        EntropyCacher().stop()
        entropy.tools.kill_threads()

    if exc_class is SystemDatabaseError:
        print_error(darkred(" * ") + \
            red(_("Installed packages repository corrupted. Please re-generate it")))
        raise SystemExit(101)

    generic_exc_classes = (OnlineMirrorError, RepositoryError,
        TransceiverError, PermissionDenied, TransceiverConnectionError,
        FileNotFound, SPMError, SystemError)
    if exc_class in generic_exc_classes:
        print_error("%s %s. %s." % (
            darkred(" * "), exc_instance, _("Cannot continue"),))
        try_to_kill_cacher()
        raise SystemExit(1)

    if exc_class is SystemExit:
        try_to_kill_cacher()
        raise exc_instance

    if exc_class is IOError:
        if exc_instance.errno != errno.EPIPE:
            try_to_kill_cacher()
            raise exc_instance

    if exc_class is KeyboardInterrupt:
        try_to_kill_cacher()
        raise SystemExit(1)

    t_back = entropy.tools.get_traceback(tb_obj = exc_tb)
    if etpUi['debug']:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        sys.stdin = sys.__stdin__
        entropy.tools.print_exception(tb_data = exc_tb)
        pdb.set_trace()

    if exc_class is OSError:
        if exc_instance.errno == errno.ENOSPC:
            print_generic(t_back)
            print_error("%s %s. %s." % (darkred(" * "), exc_instance,
                _("Your hard drive is full! Your fault!"),))
            try_to_kill_cacher()
            raise SystemExit(5)
        elif exc_instance.errno == errno.ENOMEM:
            print_generic(t_back)
            print_error("%s %s. %s." % (darkred(" * "), exc_instance,
                _("No more memory dude! Your fault!"),))
            try_to_kill_cacher()
            raise SystemExit(5)

    Text = TextInterface()
    print_error(darkred(_("Hi. My name is Bug Reporter. I am sorry to inform you that Equo crashed. Well, you know, shit happens.")))
    print_error(darkred(_("But there's something you could do to help Equo to be a better application.")))
    print_error(darkred(_("-- EVEN IF I DON'T WANT YOU TO SUBMIT THE SAME REPORT MULTIPLE TIMES --")))
    print_error(darkgreen(_("Now I am showing you what happened. Don't panic, I'm here to help you.")))

    entropy.tools.print_exception(tb_data = exc_tb)

    error_fd, error_file = tempfile.mkstemp(prefix="entropy.error.report.",
        suffix=".txt")
    try:
        ferror = os.fdopen(error_fd, "wb")
    except (OSError, IOError,):
        print_error(darkred(_("Oh well, I cannot even write to /tmp. So, please copy the error and mail lxnay@sabayon.org.")))
        try_to_kill_cacher()
        raise SystemExit(1)

    exception_data = entropy.tools.print_exception(silent = True,
        tb_data = exc_tb, all_frame_data = True)

    exception_tback_raw = const_convert_to_rawstring(t_back)
    ferror.write(const_convert_to_rawstring("\nRevision: " + \
        etpConst['entropyversion'] + "\n\n"))
    ferror.write(exception_tback_raw)
    ferror.write(const_convert_to_rawstring("\n\n"))
    ferror.write(const_convert_to_rawstring(''.join(exception_data)))
    ferror.write(const_convert_to_rawstring("\n"))
    ferror.flush()
    ferror.close()

    print_generic("")

    print_error(darkgreen(_("Of course you are on the Internet...")))
    rc = Text.ask_question(_("Erm... Can I send the error, along with some information\nabout your hardware to my creators so they can fix me? (Your IP will be logged)"))
    if rc == _("No"):
        print_error(darkgreen(_("Ok, ok ok ok... Sorry!")))
        try_to_kill_cacher()
        raise SystemExit(2)

    print_error(darkgreen(_("If you want to be contacted back (and actively supported), also answer the questions below:")))
    name = readtext(_("Your Full name:"))
    email = readtext(_("Your E-Mail address:"))
    description = readtext(_("What you were doing:"))

    try:
        from entropy.client.interfaces.qa import UGCErrorReportInterface
        from entropy.core.settings.base import SystemSettings
        repository_id = SystemSettings()['repositories']['default_repository']
        error = UGCErrorReportInterface(repository_id)
    except (OnlineMirrorError, AttributeError, ImportError,):
        error = None

    result = None
    if error is not None:
        error.prepare(exception_tback_raw, name, email,
            '\n'.join([x for x in exception_data]), description)
        result = error.submit()

    if result:
        print_error(darkgreen(_("Thank you very much. The error has been reported and hopefully, the problem will be solved as soon as possible.")))
    else:
        print_error(darkred(_("Ugh. Cannot send the report. When you want, mail the file below to lxnay@sabayon.org.")))
        print_error("")
        print_error("==> %s" % (error_file,))
        print_error("")
    try_to_kill_cacher()
    raise SystemExit(1)

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__

def warn_version_mismatch():
    equo_ver = read_equo_release()
    entropy_ver = etpConst['entropyversion']
    if equo_ver != entropy_ver:
        print_warning("")
        print_warning("%s: %s" % (
            bold(_("Entropy/Equo version mismatch")),
            purple(_("it could make your system explode!")),))
        print_warning("(%s [equo] & %s [entropy])" % (
            blue(equo_ver),
            blue(entropy_ver),))
        print_warning("")

def main():

    warn_version_mismatch()

    install_exception_handler()

    rc = -10
    main_cmd = options.pop(0)

    cmd_cb = CMDS_MAP.get(main_cmd)
    if cmd_cb is not None:
        rc = cmd_cb(main_cmd, options)

    if rc == -10:
        status = readerrorstatus()
        print_error(darkred(etp_exit_messages[status]))
        # increment
        if status < len(etp_exit_messages)-1:
            writeerrorstatus(status+1)
        rc = 10
    else:
        writeerrorstatus(0)

    entropy.tools.kill_threads()
    uninstall_exception_handler()
    return rc

if __name__ == "__main__":
    main_rc = main()
    raise SystemExit(main_rc)

