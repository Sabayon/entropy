#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import sys
import re
sys.path.insert(0, '/usr/lib/entropy/libraries')
sys.path.insert(0, '/usr/lib/entropy/server')
sys.path.insert(0, '/usr/lib/entropy/client')
sys.path.insert(0, '../libraries')
sys.path.insert(0, '../server')
sys.path.insert(0, '../client')
from entropy.exceptions import SystemDatabaseError, OnlineMirrorError, \
    RepositoryError, TransceiverError, PermissionDenied, FileNotFound, \
    SPMError, IncorrectParameter
from entropy.output import red, darkred, darkgreen, print_menu, TextInterface, \
    print_generic, print_error, print_warning, readtext, nocolor, \
    is_stdout_a_tty
from entropy.const import etpConst, etpUi, const_convert_to_rawstring
import entropy.tools
try:
    from entropy.i18n import _
except ImportError:
    def _(x):
        return x


dbapi2_exceptions = {}
try:
    from sqlite3 import dbapi2
    dbapi2_exceptions['OperationalError'] = dbapi2.OperationalError
except ImportError:
    dbapi2_exceptions['OperationalError'] = None

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

# Check if we need to disable colors
if not is_stdout_a_tty():
    nocolor()

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
    None,
    (0, _('Application Options'), 0, None),
    None,
    (1, 'update', 2, _('update configured repositories')),
    (2, '--force', 2, _('force sync regardless repositories status')),
    (1, 'repoinfo', 1, _('show repositories information')),
        (2, 'make.conf [repos]', 2, _('show make.conf for the chosen repositories')),
        (2, 'package.mask [repos]', 2, _('show package.mask for the chosen repositories')),
        (2, 'package.unmask [repos]', 2, _('show package.unmask for the chosen repositories')),
        (2, 'package.keywords [repos]', 1, _('show package.keywords for the chosen repositories')),
        (2, 'package.use [repos]', 2, _('show package.use for the chosen repositories')),
        (2, 'profile.link [repos]', 2, _('show make.profile link for the chosen repositories')),
    (1, 'notice [repos]', 1, _('repository notice board reader')),
    (1, 'status', 2, _('show respositories status')),
    None,
    (1, 'search', 2, _('search packages in repositories')),
    (1, 'match', 2, _('match a package in repositories')),
    (2, '--multimatch', 1, _('return all the possible matches')),
    (2, '--multirepo', 1, _('return matches from every repository')),
    (2, '--showrepo', 1, _('print repository information (w/--quiet)')),
    (2, '--showdesc', 1, _('print description too (w/--quiet)')),
    None,
    (1, 'hop <branch>', 1, _('upgrade your distribution to a new release (branch)')),
    None,
    (1, 'upgrade', 1, _('update system with the latest available packages')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--fetch', 1, _('just download packages')),
    (2, '--pretend', 1, _('only show what would be done')),
    (2, '--verbose', 1, _('show more details about what is going on')),
    (2, '--replay', 1, _('reinstall all the packages and their dependencies')),
    (2, '--empty', 1, _('same as --replay')),
    (2, '--resume', 1, _('resume previously interrupted operations')),
    (2, '--skipfirst', 1, _('used with --resume, makes the first package to be skipped')),
    (2, '--nochecksum', 1, _('disable package integrity check')),
    (2, '--multifetch', 1, _('download multiple packages in parallel (default 3)')),
    (2, '--multifetch=N', 1, _('download N packages in parallel (max 10)')),
    None,
    (1, 'security', 1, _('security infrastructure functions')),
    (2, 'update', 2, _('download the latest Security Advisories')),
    (3, '--force', 1, _('force download even if already up-to-date')),
    (2, 'list', 2, _('list all the available Security Advisories')),
    (3, '--affected', 1, _('list only affected')),
    (3, '--unaffected', 1, _('list only unaffected')),
    (2, 'info', 2, _('show information about provided advisories identifiers')),
    (2, 'install', 1, _('automatically install all the available security updates')),
    (3, '--ask', 2, _('ask before making any changes')),
    (3, '--fetch', 1, _('just download packages')),
    (3, '--pretend', 1, _('just show what would be done')),
    (3, '--quiet', 1, _('show less details (useful for scripting)')),
    None,
    (1, 'install', 1, _('install atoms or binary packages')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    (2, '--fetch', 1, _('just download packages without doing the install')),
    (2, '--nodeps', 1, _('do not pull in any dependency')),
    (2, '--resume', 1, _('resume previously interrupted operations')),
    (2, '--skipfirst', 1, _('used with --resume, makes the first package in queue to be skipped')),
    (2, '--clean', 1, _('remove downloaded packages after being used')),
    (2, '--empty', 1, _('pull all the dependencies in, regardless their state')),
    (2, '--relaxed', 1, _('calm down dependencies resolution algorithm (might be risky)')),
    (2, '--deep', 2, _('makes dependency rules stricter')),
    (2, '--verbose', 1, _('show more details about what is going on')),
    (2, '--configfiles', 1, _('makes old configuration files to be removed')),
    (2, '--nochecksum', 1, _('disable package integrity check')),
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
    (2, '--configfiles', 1, _('makes configuration files to be removed')),
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
    (2, '--quiet', 1, _('show less details (useful for scripting)')),
    (2, '--ask', 2, _('ask before making any changes')),
    (2, '--pretend', 1, _('just show what would be done')),
    None,
    (1, 'unusedpackages', 2, _('look for unused packages (pay attention)')),
    (2, '--quiet', 1, _('show less details (useful for scripting)')),
    (2, '--sortbysize', 1, _('sort packages by disk size')),
    None,
    (1, 'libtest', 2, _('look for missing libraries')),
        (2, '--dump', 2, _('dump results to files')),
        (2, '--listfiles', 1, _('print broken files to stdout')),
        (2, '--quiet', 1, _('show less details (useful for scripting)')),
        (2, '--ask', 2, _('ask before making any changes')),
        (2, '--pretend', 1, _('just show what would be done')),
    None,
    (1, 'conf', 2, _('configuration files update tool')),
    (2, 'info', 2, _('show configuration files to be updated')),
    (2, 'update', 2, _('run the configuration files update function')),
    None,
    (1, 'query', 2, _('do misc queries on repository and local databases')),
        (2, 'belongs', 1, _('search from what package a file belongs')),
        (2, 'changelog', 1, _('show packages changelog')),
        (2, 'revdeps', 1, _('search what packages depend on the provided atoms')),
        (2, 'description', 1, _('search packages by description')),
        (2, 'files', 2, _('show files owned by the provided atoms')),
        (2, 'installed', 1, _('search a package into the local database')),
        (2, 'license', 1, _('show packages owning the provided licenses')),
        (2, 'list', 2, _('list packages based on the chosen parameter below')),
            (3, 'installed', 2, _('list installed packages')),
            (3, 'available [repos]', 1, _('list available packages')),
        (2, 'needed', 2, _('show runtime libraries needed by the provided atoms')),
        (2, 'orphans', 1, _('search files that do not belong to any package')),
        (2, 'removal', 1, _('show the removal tree for the specified atoms')),
        (2, 'required', 1, _('show atoms needing the provided libraries')),
        (2, 'sets', 2, _('search available package sets')),
        (2, 'slot', 2, _('show packages owning the provided slot')),
        (2, 'tags', 2, _('show packages owning the provided tags')),
        (2, 'graph', 2, _('show direct depdendencies tree for provided installable atoms')),
            (3, '--complete', 2, _('include system packages, build deps and circularity information')),
        (2, 'revgraph', 1, _('show reverse depdendencies tree for provided installed atoms')),
            (3, '--complete', 2, _('include system packages, build deps and circularity information')),
        (2, '--verbose', 1, _('show more details')),
        (2, '--quiet', 1, _('print results in a scriptable way')),
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
    (2, 'application', 1, _('make a smart application for the provided atoms (experimental)')),
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
    (1, 'database', 1, _('handles installed packages database')),
        (2, 'check', 2, _('check System Database for errors')),
        (2, 'vacuum', 2, _('remove System Database internal indexes to save space')),
        (2, 'generate', 1, _('generate installed packages database using Source Package Manager repositories')),
        (2, 'resurrect', 1, _('generate installed packages database using files on the system [last hope]')),
        (2, 'revdeps', 1, _('regenerate reverse dependencies metadata')),
        (2, 'spmuids', 1, _('regenerate SPM UIDs map (SPM <-> Entropy packages)')),
        (2, 'spmsync', 1, _('makes Entropy aware of your Source Package Manager updated packages')),
        (2, 'backup', 2, _('backup the current Entropy installed packages database')),
        (2, 'restore', 1, _('restore a previously backed up Entropy installed packages database')),
    None,
    (1, 'community', 1, _('handles community-side features')),

        (2, 'repos', 2, _('community repositories management functions')),
            (3, 'update', 3, _('scan the System looking for newly compiled packages')),
                (4, '--seekstore', 2, _('analyze the Entropy Store directory directly')),
                (4, '--repackage <atoms>', 1, _('repackage the specified atoms')),
                (4, '--noask', 2, _('do not ask anything except critical things')),
                (4, '--atoms <atoms>', 1, _('manage only the specified atoms')),
                (4, '--interactive', 1, _('run in interactive mode (asking things one by one)')),
            (3, 'inject <packages>', 1, _('add binary packages to repository w/o affecting scopes (multipackages)')),
        (2, 'mirrors', 2, _('community repositories mirrors management functions')),
            (3, 'sync', 3, _('sync packages, database and also do some tidy')),
                (4, '--noask', 2, _('do not ask anything except critical things')),
                (4, '--syncall', 2, _('sync all the configured repositories')),
            (3, 'packages-sync', 2, _('sync packages across primary mirrors')),
                (4, '--ask', 3, _('ask before making any changes')),
                (4, '--pretend', 2, _('only show what would be done')),
                (4, '--syncall', 2, _('sync all the configured repositories')),
                (4, '--do-packages-check', 1, _('also verify packages integrity')),
            (3, 'db-sync', 3, _('sync the current repository database across primary mirrors')),
                (4, '--syncall', 2, _('sync all the configured repositories')),
            (3, 'db-lock', 3, _('lock the current repository database (server-side)')),
            (3, 'db-unlock', 2, _('unlock the current repository database (server-side)')),
            (3, 'db-download-lock', 1, _('lock the current repository database (client-side)')),
            (3, 'db-download-unlock', 1, _('unlock the current repository database (client-side)')),
            (3, 'db-lock-status', 2, _('show current lock status')),
            (3, 'tidy', 3, _('remove binary packages not in repositories and expired')),

        None,

        (2, 'database', 1, _('community repositories database functions')),
            (3, '--initialize', 2, _('(re)initialize the current repository database')),
                (4, '--empty', 2, _('do not refill database using packages on mirrors')),
                (4, '--repo=<repo>', 2, _('(re)create the database for the specified repository')),
            (3, 'bump', 3, _('manually force a revision bump for the current repository database')),
                (4, '--sync', 3, _('synchronize the database')),
            (3, 'flushback [branches]', 1, _('flush back old branches packages to current branch')),
            (3, 'remove', 3, _('remove the provided atoms from the current repository database')),
            (3, 'multiremove', 2, _('remove the provided injected atoms (all if no atom specified)')),
            (3, 'create-empty-database', 1, _('create an empty repository database in the provided path')),
            (3, 'switchbranch <from branch> <to branch>', 2, _('switch to the specified branch the provided atoms (or world)')),
            (3, 'md5remote', 2, _('verify remote integrity of the provided atoms (or world)')),
            (3, 'backup', 3, _('backup current repository database')),
            (3, 'restore', 3, _('restore a previously backed-up repository database')),
            (3, 'spmuids', 2, _('regenerate SPM UIDs map (SPM <-> Entropy packages)'),),

        None,

        (2, 'repo', 2, _('manage a repository')),
            (3, 'enable <repo>', 3, _('enable the specified repository')),
            (3, 'disable <repo>', 3, _('disable the specified repository')),
            (3, 'status <repo>', 3, _('show the current Server Interface status')),
            (3, 'manual-deps <repo> [atoms]', 1, _('handle packages manual dependencies')),
            (3, 'package-tag <repo> <tag-string> [atoms]', 1, _('clone a package inside a repository assigning it an arbitrary tag')),
            (3, 'move <from> <to> [atoms]', 1, _('move packages from a repository to another')),
                (4, '--deps', 3, _('pulls dependencies in')),
            (3, 'copy <from> <to> [atoms]', 1, _('copy packages from a repository to another')),
                (4, '--deps', 3, _('pulls dependencies in')),
            (3, 'default <repo_id>', 2, _('set the default repository')),

        None,

        (2, 'key', 2, _('manage repository digital signatures (OpenGPG)')),
            (3, 'create [repos]', 1, _('create keypair for repositories and sign packages')),
            (3, 'delete [repos]', 1, _('delete keypair (and digital signatures) of repository')),
            (3, 'status [repos]', 1, _('show currently configured keys information for given repositories')),
            (3, 'sign [repos]', 1, _('sign (or re-sign) packages in repository using currently set keypair')),
            (3, 'import <repo_id> <privkey_path> <pubkey_path>', 1, _('import keypair, bind to given repository')),
            (3, 'export-public <repo_id> <key_path>', 1, _('export public key of given repository')),
            (3, 'export-private <repo_id> <key_path>', 1, _('export private key of given repository')),

        None,

        (2, 'query', 2, _('do some searches into community repository databases')),
            (3, 'belongs', 2, _('show from what package the provided files belong')),
            (3, 'changelog', 2, _('show packages changelog')),
            (3, 'revdeps', 2, _('show what packages depend on the provided atoms')),
            (3, 'description', 2, _('search packages by description')),
            (3, 'eclass', 3, _('search packages using the provided eclasses')),
            (3, 'files', 3, _('show files owned by the provided atoms')),
            (3, 'list', 3, _('list all the packages in the default repository')),
            (3, 'needed', 3, _('show runtime libraries needed by the provided atoms')),
            (3, 'search', 3, _('search packages inside the default repository database')),
            (3, 'sets', 3, _('search available package sets')),
            (3, 'tags', 3, _('show packages owning the specified tags')),
            (3, '--verbose', 2, _('show more details')),
            (3, '--quiet', 3, _('print results in a scriptable way')),

        None,

        (2, 'spm', 2, _('source package manager functions')),
            (3, 'compile', 2, _('compilation function')),
                (4, 'categories', 2, _('compile packages belonging to the provided categories')),
                    (5, '--list', 2, _('just list packages')),
                    (5, '--nooldslots', 1, _('do not pull old package slots')),
                (4, 'pkgset', 3, _('compile packages in provided package set names')),
                    (5, '--list', 2, _('just list packages')),
                    (5, '--rebuild', 1, _('rebuild everything')),
                    (5, '--dbupdate', 1, _('run database update if all went fine')),
                    (5, '--dbsync', 1, _('run mirror sync if all went fine')),
            (3, 'orphans', 2, _('scan orphaned packages on SPM')),

        None,

        (2, 'notice', 2, _('notice board handling functions')),
            (3, 'add', 3, _('add a news item to the notice board')),
            (3, 'remove', 3, _('remove a news item from the notice board')),
            (3, 'read', 3, _('read the current notice board')),

        None,

        (2, 'deptest', 2, _('look for unsatisfied dependencies across community repositories')),
        (2, 'pkgtest', 2, _('verify the integrity of local package files')),
        (2, 'revdeps', 2, _('regenerate the reverse dependencies metadata')),

    None,
    (1, 'ugc', 2, _('handles User Generated Content features')),
        (2, 'login <repository>', 1, _('login against a specified repository')),
        (2, 'logout <repository>', 1, _('logout from a specified repository')),
            (3, '--force', 2, _('force action')),
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
        (2, '--quiet', 1, _('print results in a scriptable way')),
    None,
    (1, 'cleanup', 2, _('remove downloaded packages and clean temp. directories')),
    None,
    (1, '--info', 2, _('show system information')),
    None,
]

def _do_text_ui(main_cmd, options):
    import text_ui
    return text_ui.package([main_cmd] + options)

def _do_text_repos(main_cmd, options):
    import text_repositories
    return text_repositories.repositories([main_cmd] + options)

def _do_text_security(main_cmd, options):
    import text_security
    return text_security.security(options)

def _do_text_query(main_cmd, options):
    import text_query
    return text_query.query(options)

def _do_text_smart(main_cmd, options):
    import text_smart
    return text_smart.smart(options)

def _do_text_conf(main_cmd, options):
    import text_configuration
    return text_configuration.configurator(options)

def _do_text_cache(main_cmd, options):
    import text_cache
    return text_cache.cache(options)

def _do_search(main_cmd, options):
    import text_query
    return text_query.query([main_cmd] + options)

def _do_text_database(main_cmd, options):
    import text_rescue
    return text_rescue.database(options)

def _do_text_ugc(main_cmd, options):
    import text_ugc
    return text_ugc.ugc(options)

def _do_text_community(main_cmd, options):
    comm_err_msg = _("You need to install sys-apps/entropy-server. :-) Do it !")
    etpConst['community']['mode'] = True

    if not options:
        return -10

    rc = -10
    sub_cmd = options.pop(0)

    if sub_cmd == "repos":
        try:
            import server_reagent
        except ImportError:
            print_error(darkgreen(comm_err_msg))
            rc = 1
        else:
            if options:
                if options[0] == "update":
                    rc = server_reagent.update(options[1:])
                    server_reagent.Entropy.close_server_databases()
                elif options[0] == "inject":
                    rc = server_reagent.inject(options[1:])
                    server_reagent.Entropy.close_server_databases()
    elif sub_cmd == "mirrors":
        try:
            import server_activator
        except ImportError:
            print_error(darkgreen(comm_err_msg))
            rc = 1
        else:
            if options:
                if options[0] == "sync":
                    rc = server_activator.sync(options[1:])
                elif options[0] == "packages-sync":
                    rc = server_activator.sync(options[1:])
                elif options[0] == "tidy":
                    rc = server_activator.sync(options[1:], just_tidy = True)
                elif options[0].startswith("db-"):
                    options[0] = options[0][3:]
                    rc = server_activator.database(options)

    elif sub_cmd == "database":

        do = True
        # hook to support spmuids command, which is just
        # a duplicate of 'equo database counters'
        # put here for completeness
        if options:
            if options[0] == "spmuids":
                do = False
                import text_rescue
                rc = text_rescue.database(options)

        if do:
            try:
                import server_reagent
            except ImportError:
                print_error(darkgreen(comm_err_msg))
                rc = 1
            else:
                rc = server_reagent.database(options)
                server_reagent.Entropy.close_server_databases()

    elif sub_cmd == "repo":
        try:
            import server_reagent
        except ImportError:
            print_error(darkgreen(comm_err_msg))
            rc = 1
        else:
            rc = server_reagent.repositories(options)

    elif sub_cmd == "key":
        try:
            import server_key
        except ImportError:
            print_error(darkgreen(comm_err_msg))
            rc = 1
        else:
            rc = server_key.key(options)

    elif sub_cmd == "notice":
        try:
            import server_activator
            if not hasattr(server_activator, 'notice'):
                raise ImportError
        except ImportError:
            print_error(darkgreen(_("You need to install/update sys-apps/entropy-server. :-) Do it !")))
            rc = 1
        else:
            rc = server_activator.notice(options)

    elif sub_cmd == "query":
        try:
            import server_query
        except ImportError:
            print_error(darkgreen(comm_err_msg))
            rc = 1
        else:
            rc = server_query.query(options)

    elif sub_cmd == "spm":
            try:
                import server_reagent
            except ImportError:
                print_error(darkgreen(comm_err_msg))
                rc = 1
            else:
                rc = server_reagent.spm(options)
                server_reagent.Entropy.close_server_databases()

    elif sub_cmd == "deptest":
        try:
            import server_reagent
        except ImportError:
            print_error(darkgreen(comm_err_msg))
            rc = 1
        else:
            server_reagent.Entropy.dependencies_test()
            server_reagent.Entropy.close_server_databases()
            rc = 0

    elif sub_cmd == "pkgtest":
        try:
            import server_reagent
        except ImportError:
            print_error(darkgreen(comm_err_msg))
            rc = 1
        else:
            server_reagent.Entropy.verify_local_packages(["world"], ask = etpUi['ask'])
            server_reagent.Entropy.close_server_databases()
            rc = 0

    elif sub_cmd == "revdeps":
        try:
            import server_reagent
        except ImportError:
            print_error(darkgreen(comm_err_msg))
            rc = 1
        else:
            rc = server_reagent.Entropy.generate_reverse_dependencies_metadata()
            server_reagent.Entropy.close_server_databases()

    return rc

def _do_text_cleanup(main_cmd, options):
    import text_tools
    text_tools.cleanup([etpConst['packagestmpdir'],
        etpConst['logdir'], etpConst['entropyunpackdir'],
        etpConst['packagesbindir']])
    return 0

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
    "database": _do_text_database,
    "ugc": _do_text_ugc,
    "community": _do_text_community,

    "cleanup": _do_text_cleanup,

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

for opt in options:
    if opt in ["--nocolor", "-N"]:
        nocolor()
    elif opt == "--debug":
        continue
    elif opt in ["--quiet", "-q"]:
        etpUi['quiet'] = True
    elif opt in ["--verbose", "-v"]:
        etpUi['verbose'] = True
    elif opt in ["--ask", "-a"]:
        etpUi['ask'] = True
    elif opt in ["--pretend", "-p"]:
        etpUi['pretend'] = True
    elif (opt == "--ihateprint"):
        etpUi['mute'] = True
    elif (opt == "--clean"):
        etpUi['clean'] = True
    else:
        _options.append(opt)
options = _options

if "help" in options:
    options.insert(0, "--help")

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
    print_generic("equo: "+etpConst['entropyversion'])
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
    except (IOError, OSError,):
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

    if exc_class is SystemDatabaseError:
        print_error(darkred(" * ") + \
            red(_("Installed packages repository corrupted. Please re-generate it")))
        raise SystemExit(101)

    if exc_class is OnlineMirrorError:
        print_error("%s %s. %s." % (
            darkred(" * "), exc_instance, _("Cannot continue"),))
        raise SystemExit(101)

    if exc_class is RepositoryError:
        print_error("%s %s. %s." % (
            darkred(" * "), exc_instance, _("Cannot continue"),))
        raise SystemExit(101)

    if exc_class is TransceiverError:
        print_error("%s %s. %s." % (
            darkred(" * "), exc_instance, _("Cannot continue"),))
        raise SystemExit(101)

    if exc_class is PermissionDenied:
        print_error("%s %s. %s." % (
            darkred(" * "), exc_instance, _("Cannot continue"),))
        raise SystemExit(1)

    if exc_class is FileNotFound:
        print_error("%s %s. %s." % (
            darkred(" * "), exc_instance, _("Cannot continue"),))
        raise SystemExit(1)

    if exc_class is SPMError:
        print_error("%s %s. %s." % (
            darkred(" * "), exc_instance, _("Cannot continue"),))
        raise SystemExit(1)

    if exc_class is dbapi2_exceptions['OperationalError']:
        entropy.tools.print_exception(tb_data = exc_tb)
        print_error("%s %s. %s." % (darkred(" * "), exc_instance,
            _("Cannot continue. Your hard disk is probably faulty."),))
        raise SystemExit(101)

    if exc_class is SystemError:
        print_error("%s %s. %s." % (
            darkred(" * "), exc_instance, _("Cannot continue"),))
        raise SystemExit(1)

    if exc_class is SystemExit:
        raise

    if exc_class is IOError:
        if exc_instance.errno != 32:
            raise

    if exc_class is KeyboardInterrupt:
        raise SystemExit(1)

    t_back = entropy.tools.get_traceback(tb_obj = exc_tb)

    if exc_class is OSError:
        if exc_instance.errno == 28:
            print_generic(t_back)
            print_error("%s %s. %s." % (darkred(" * "), exc_instance,
                _("Your hard drive is full! Your fault!"),))
            raise SystemExit(5)

    Text = TextInterface()
    print_error(darkred(_("Hi. My name is Bug Reporter. I am sorry to inform you that Equo crashed. Well, you know, shit happens.")))
    print_error(darkred(_("But there's something you could do to help Equo to be a better application.")))
    print_error(darkred(_("-- EVEN IF I DON'T WANT YOU TO SUBMIT THE SAME REPORT MULTIPLE TIMES --")))
    print_error(darkgreen(_("Now I am showing you what happened. Don't panic, I'm here to help you.")))

    entropy.tools.print_exception(tb_data = exc_tb)

    error_file = "/tmp/equoerror.txt"
    try:
        ferror = open(error_file, "wb")
    except (OSError, IOError,):
        print_error(darkred(_("Oh well, I cannot even write to /tmp. So, please copy the error and mail lxnay@sabayon.org.")))
        raise SystemExit(1)

    exception_data = entropy.tools.print_exception(returndata = True,
        tb_data = exc_tb)
    exception_stack = t_back
    ferror.write(const_convert_to_rawstring("\nRevision: " + \
        etpConst['entropyversion'] + "\n\n"))
    ferror.write(const_convert_to_rawstring(exception_stack))
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
        raise SystemExit(2)

    print_error(darkgreen(_("If you want to be contacted back (and actively supported), also answer the questions below:")))
    name = readtext(_("Your Full name:"))
    email = readtext(_("Your E-Mail address:"))
    description = readtext(_("What you were doing:"))

    ferror = open(error_file, "r")
    error_text = ''.join(ferror.readlines())
    ferror.close()

    try:
        from entropy.client.interfaces.qa import UGCErrorReportInterface
        error = UGCErrorReportInterface()
    except (IncorrectParameter, OnlineMirrorError,
        AttributeError, ImportError,):
        error = None

    result = None
    if error is not None:
        error.prepare(error_text, name, email,
            '\n'.join([x for x in exception_data]), description)
        result = error.submit()

    if result:
        print_error(darkgreen(_("Thank you very much. The error has been reported and hopefully, the problem will be solved as soon as possible.")))
    else:
        print_error(darkred(_("Ugh. Cannot send the report. I saved the error to /tmp/equoerror.txt. When you want, mail the file to lxnay@sabayon.org.")))
    raise SystemExit(1)

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__



def main():

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

