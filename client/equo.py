#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import sys
sys.path.insert(0,'/usr/lib/entropy/libraries')
sys.path.insert(0,'/usr/lib/entropy/server')
sys.path.insert(0,'/usr/lib/entropy/client')
sys.path.insert(0,'../libraries')
sys.path.insert(0,'../server')
sys.path.insert(0,'../client')
from entropy.exceptions import *
from entropy.const import *
from entropy.output import *
import entropy.tools as entropyTools
from entropy.core.settings.base import SystemSettings
SysSettings = SystemSettings()
try:
    from entropy.i18n import _
except ImportError:
    def _(x): return x

dbapi2Exceptions = {}
dbapi2Exceptions['OperationalError'] = None
dbapi2_done = False
try: # try with sqlite3 from python 2.5 - default one
    from sqlite3 import dbapi2
    dbapi2_done = True
except: # fallback to embedded pysqlite
    try:
        from pysqlite2 import dbapi2
        dbapi2_done = True
    except:
        pass
if dbapi2_done:
    dbapi2Exceptions['OperationalError'] = dbapi2.OperationalError

etpExitMessages = {
    0: _("You should run equo --help"),
    1: _("You didn't run equo --help, did you?"),
    2: _("Did you even read equo --help??"),
    3: _("I give up. Run that equo --help !!!!!!!"),
    4: _("OH MY GOD. RUN equo --heeeeeeeeeeeeeelp"),
    5: _("Illiteracy is a huge problem in this world"),
    6: _("Ok i give up, you are hopeless"),
    7: _("Go to hell."),
}

myopts = [
    None,
    (0," ~ %s ~ " % (SysSettings['system']['name'],) ,1,'Entropy Package Manager - (C) %s' % (entropyTools.get_year(),) ),
    None,
    (0,_('Basic Options'),0,None),
    None,
    (1,'--help',2,_('this output')),
    (1,'--version',1,_('print version')),
    (1,'--nocolor',1,_('disable colorized output')),
    None,
    (0,_('Application Options'),0,None),
    None,
    (1,'update',2,_('update configured repositories')),
    (2,'--force',2,_('force sync regardless repositories status')),
    (1,'repoinfo',1,_('show repositories information')),
        (2,'make.conf [repos]',2,_('show make.conf for the chosen repositories')),
        (2,'package.mask [repos]',2,_('show package.mask for the chosen repositories')),
        (2,'package.unmask [repos]',2,_('show package.unmask for the chosen repositories')),
        (2,'package.keywords [repos]',1,_('show package.keywords for the chosen repositories')),
        (2,'package.use [repos]',2,_('show package.use for the chosen repositories')),
        (2,'profile.link [repos]',2,_('show make.profile link for the chosen repositories')),
    (1,'notice [repos]',1,_('repository notice board reader')),
    (1,'status',2,_('show respositories status')),
    None,
    (1,'search',2,_('search packages in repositories')),
    (1,'match',2,_('match a package in repositories')),
    (2,'--multimatch',1,_('return all the possible matches')),
    (2,'--multirepo',1,_('return matches from every repository')),
    (2,'--showrepo',1,_('print repository information (w/--quiet)')),
    (2,'--showdesc',1,_('print description too (w/--quiet)')),
    None,
    (1,'hop <branch>',1,_('upgrade your distribution to a new release (branch)')),
    None,
    (1,'world (or upgrade)',1,_('update system with the latest available packages')),
    (2,'--ask',2,_('ask before making any changes')),
    (2,'--fetch',2,_('just download packages')),
    (2,'--pretend',1,_('only show what would be done')),
    (2,'--verbose',1,_('show more details about what is going on')),
    (2,'--replay',1,_('reinstall all the packages and their dependencies')),
    (2,'--empty',2,_('same as --replay')),
    (2,'--resume',1,_('resume previously interrupted operations')),
    (2,'--skipfirst',1,_('used with --resume, makes the first package to be skipped')),
    (2,'--nochecksum',1,_('disable package integrity check')),
    (2,'--multifetch',1,_('download multiple packages in parallel (default 3)')),
    (2,'--multifetch=N',1,_('download N packages in parallel (max 10)')),
    None,
    (1,'security',1,_('security infrastructure functions')),
    (2,'update',2,_('download the latest Security Advisories')),
    (2,'list',2,_('list all the available Security Advisories')),
    (3,'--affected',1,_('list only affected')),
    (3,'--unaffected',1,_('list only unaffected')),
    (2,'info',2,_('show information about provided advisories identifiers')),
    (2,'install',2,_('automatically install all the available security updates')),
    (3,'--ask',2,_('ask before making any changes')),
    (3,'--fetch',2,_('just download packages')),
    (3,'--pretend',1,_('just show what would be done')),
    (3,'--quiet',2,_('show less details (useful for scripting)')),
    None,
    (1,'install',2,_('install atoms or .tbz2 packages')),
    (2,'--ask',2,_('ask before making any changes')),
    (2,'--pretend',1,_('just show what would be done')),
    (2,'--fetch',2,_('just download packages without doing the install')),
    (2,'--nodeps',1,_('do not pull in any dependency')),
    (2,'--resume',1,_('resume previously interrupted operations')),
    (2,'--skipfirst',1,_('used with --resume, makes the first package in queue to be skipped')),
    (2,'--clean',2,_('remove downloaded packages after being used')),
    (2,'--empty',2,_('pull all the dependencies in, regardless their state')),
    (2,'--deep',2,_('makes dependency rules stricter')),
    (2,'--verbose',1,_('show more details about what is going on')),
    (2,'--configfiles',1,_('makes old configuration files to be removed')),
    (2,'--nochecksum',1,_('disable package integrity check')),
    (2,'--multifetch',1,_('download multiple packages in parallel (default 3)')),
    (2,'--multifetch=N',1,_('download N packages in parallel (max 10)')),
    None,
    (1,'source',2,_('download atoms source code')),
    (2,'--ask',2,_('ask before making any changes')),
    (2,'--pretend',1,_('just show what would be done')),
    (2,'--savehere',1,_('save sources in current working directory')),
    None,
    (1,'remove',2,_('remove one or more packages')),
    (2,'--ask',2,_('ask before making any changes')),
    (2,'--pretend',1,_('just show what would be done')),
    (2,'--nodeps',1,_('do not pull in any dependency')),
    (2,'--deep',2,_('also pull unused dependencies where depends list is empty')),
    (2,'--configfiles',1,_('makes configuration files to be removed')),
    (2,'--resume',1,_('resume previously interrupted operations')),
    None,
    (1,'config',2,_('configure one or more installed packages')),
    (2,'--ask',2,_('ask before making any changes')),
    (2,'--pretend',1,_('just show what would be done')),
    None,
    (1,'deptest',2,_('look for unsatisfied dependencies')),
    (2,'--quiet',2,_('show less details (useful for scripting)')),
    (2,'--ask',2,_('ask before making any changes')),
    (2,'--pretend',1,_('just show what would be done')),
    None,
    (1,'unusedpackages',2,_('look for unused packages (pay attention)')),
    (2,'--quiet',2,_('show less details (useful for scripting)')),
    (2,'--sortbysize',1,_('sort packages by disk size')),
    None,
    (1,'libtest',2,_('look for missing libraries')),
        (2,'--dump',2,_('dump results to files')),
        (2,'--listfiles',1,_('print broken files to stdout')),
        (2,'--quiet',2,_('show less details (useful for scripting)')),
        (2,'--ask',2,_('ask before making any changes')),
        (2,'--pretend',1,_('just show what would be done')),
    None,
    (1,'conf',2,_('configuration files update tool')),
    (2,'info',2,_('show configuration files to be updated')),
    (2,'update',2,_('run the configuration files update function')),
    None,
    (1,'query',2,_('do misc queries on repository and local databases')),
        (2,'belongs',2,_('search from what package a file belongs')),
        (2,'changelog',1,_('show packages changelog')),
        (2,'depends',2,_('search what packages depend on the provided atoms')),
        (2,'description',1,_('search packages by description')),
        (2,'files',2,_('show files owned by the provided atoms')),
        (2,'installed',1,_('search a package into the local database')),
        (2,'license',2,_('show packages owning the provided licenses')),
        (2,'list',2,_('list packages based on the chosen parameter below')),
            (3,'installed',2,_('list installed packages')),
            (3,'available [repos]',1,_('list available packages')),
        (2,'needed',2,_('show runtime libraries needed by the provided atoms')),
        (2,'orphans',2,_('search files that do not belong to any package')),
        (2,'removal',2,_('show the removal tree for the specified atoms')),
        (2,'required',1,_('show atoms needing the provided libraries')),
        (2,'sets',2,_('search available package sets')),
        (2,'slot',2,_('show packages owning the provided slot')),
        (2,'tags',2,_('show packages owning the provided tags')),
        (2,'--verbose',1,_('show more details')),
        (2,'--quiet',2,_('print results in a scriptable way')),
    None,

]

myopts_ext_info = [
    (0,_('!!! Use --verbose to get full help output'),0,None),
    None,
]

myopts_extended = [
    (0,_('Extended Options'),0,None),
    None,
    (1,'smart',2,_('handles extended functionalities')),
    (2,'application',1,_('make a smart application for the provided atoms (experimental)')),
    (2,'package',2,_('make a smart package for the provided atoms (multiple packages into one file)')),
    (2,'quickpkg',1,_('recreate an Entropy package from your System')),
    (3,'--savedir',1,_('save new packages into the specified directory')),
    (2,'inflate',2,_('convert provided Gentoo .tbz2s into Entropy packages (Portage needed)')),
    (3,'--savedir',1,_('save new packages into the specified directory')),
    (2,'deflate',2,_('convert provided Entropy packages into Gentoo ones (Portage needed)')),
    (3,'--savedir',1,_('save new packages into the specified directory')),
    (2,'extract',2,_('extract Entropy metadata from provided .tbz2 packages')),
    (3,'--savedir',1,_('save new metadata into the specified directory')),
    None,
    (1,'database',1,_('handles installed packages database')),
        (2,'check',2,_('check System Database for errors')),
        (2,'vacuum',2,_('remove System Database internal indexes to save space')),
        (2,'generate',1,'generate installed packages database using Portage database (Portage needed)'),
        (2,'resurrect',1,_('generate installed packages database using files on the system [last hope]')),
        (2,'depends',2,_('regenerate depends caching table')),
        (2,'counters',1,_('update/generate counters table (Portage <-> Entropy packages table)')),
        (2,'gentoosync',1,_('makes Entropy aware of your Portage-updated packages')),
        (2,'backup',2,_('backup the current Entropy installed packages database')),
        (2,'restore',2,_('restore a previously backed up Entropy installed packages database')),
    None,
    (1,'community',1,_('handles community-side features')),

        (2,'repos',2,_('community repositories management functions')),
            (3,'update',3,_('scan the System looking for newly compiled packages')),
                (4,'--seekstore',2,_('analyze the Entropy Store directory directly')),
                (4,'--repackage <atoms>',1,_('repackage the specified atoms')),
                (4,'--noask',3,_('do not ask anything except critical things')),
                (4,'--atoms <atoms>',1,_('manage only the specified atoms')),
                (4,'--interactive',1,_('run in interactive mode (asking things one by one)')),
            (3,'inject <packages>',1,_('add binary packages to repository w/o affecting scopes (multipackages)')),
        (2,'mirrors',2,_('community repositories mirrors management functions')),
            (3,'sync',3,_('sync packages, database and also do some tidy')),
                (4,'--noask',3,_('do not ask anything except critical things')),
                (4,'--syncall',2,_('sync all the configured repositories')),
            (3,'packages-sync',2,_('sync packages across primary mirrors')),
                (4,'--ask',3,_('ask before making any changes')),
                (4,'--pretend',2,_('only show what would be done')),
                (4,'--syncall',2,_('sync all the configured repositories')),
                (4,'--do-packages-check',1,_('also verify packages integrity')),
            (3,'db-sync',3,_('sync the current repository database across primary mirrors')),
                (4,'--syncall',2,_('sync all the configured repositories')),
            (3,'db-lock',3,_('lock the current repository database (server-side)')),
            (3,'db-unlock',2,_('unlock the current repository database (server-side)')),
            (3,'db-download-lock',1,_('lock the current repository database (client-side)')),
            (3,'db-download-unlock',1,_('unlock the current repository database (client-side)')),
            (3,'db-lock-status',2,_('show current lock status')),
            (3,'tidy',3,_('remove binary packages not in repositories and expired')),

        None,

        (2,'database',1,_('community repositories database functions')),
            (3,'--initialize',2,_('(re)initialize the current repository database')),
                (4,'--empty',3,_('do not refill database using packages on mirrors')),
                (4,'--repo=<repo>',2,_('(re)create the database for the specified repository')),
            (3,'bump',3,_('manually force a revision bump for the current repository database')),
                (4,'--sync',3,_('synchronize the database')),
            (3,'flushback [branches]',1,_('flush back old branches packages to current branch')),
            (3,'remove',3,_('remove the provided atoms from the current repository database')),
            (3,'multiremove',2,_('remove the provided injected atoms (all if no atom specified)')),
            (3,'create-empty-database',1,_('create an empty repository database in the provided path')),
            (3,'switchbranch <from branch> <to branch>',2,_('switch to the specified branch the provided atoms (or world)')),
            (3,'md5remote',2,_('verify remote integrity of the provided atoms (or world)')),
            (3,'backup',3,_('backup current repository database')),
            (3,'restore',3,_('restore a previously backed-up repository database')),
            (3,'counters',2,_('resync counters table (Portage <-> Entropy matching scheme)'),),

        None,

        (2,'repo',2,_('manage a repository')),
            (3,'enable <repo>',3,_('enable the specified repository')),
            (3,'disable <repo>',3,_('disable the specified repository')),
            (3,'status <repo>',3,_('show the current Server Interface status')),
            (3,'manual-deps <repo> [atoms]',1,_('handle packages manual dependencies')),
            (3,'package-tag <repo> <tag-string> [atoms]',1,_('clone a package inside a repository assigning it an arbitrary tag')),
            (3,'move <from> <to> [atoms]',1,_('move packages from a repository to another')),
                (4,'--deps',2,_('pulls dependencies in')),
            (3,'copy <from> <to> [atoms]',1,_('copy packages from a repository to another')),
                (4,'--deps',2,_('pulls dependencies in')),
            (3,'default <repo_id>',2,_('set the default repository')),

        None,

        (2,'query',2,_('do some searches into community repository databases')),
            (3,'belongs',3,_('show from what package the provided files belong')),
            (3,'changelog',2,_('show packages changelog')),
            (3,'depends',3,_('show what packages depend on the provided atoms')),
            (3,'description',2,_('search packages by description')),
            (3,'eclass',3,_('search packages using the provided eclasses')),
            (3,'files',3,_('show files owned by the provided atoms')),
            (3,'list',3,_('list all the packages in the default repository')),
            (3,'needed',3,_('show runtime libraries needed by the provided atoms')),
            (3,'search',3,_('search packages inside the default repository database')),
            (3,'sets',3,_('search available package sets')),
            (3,'tags',3,_('show packages owning the specified tags')),
            (3,'--verbose',2,_('show more details')),
            (3,'--quiet',3,_('print results in a scriptable way')),

        None,

        (2,'spm',2,_('source package manager functions')),
            (3,'compile',2,_('compilation function')),
                (4,'categories',1,_('compile packages belonging to the provided categories')),
                    (5,'--list',1,_('just list packages')),
                    (5,'--nooldslots',1,_('do not pull old package slots')),
                (4,'pkgset',2,_('compile packages in provided package set names')),
                    (5,'--list',1,_('just list packages')),
                    (5,'--rebuild',1,_('rebuild everything')),
                    (5,'--dbupdate',1,_('run database update if all went fine')),
                    (5,'--dbsync',1,_('run mirror sync if all went fine')),
            (3,'orphans',2,_('scan orphaned packages on SPM')),

        None,

        (2,'notice',2,_('notice board handling functions')),
            (3,'add',3,_('add a news item to the notice board')),
            (3,'remove',3,_('remove a news item from the notice board')),
            (3,'read',3,_('read the current notice board')),

        None,

        (2,'deptest',2,_('look for unsatisfied dependencies across community repositories')),
        (2,'pkgtest',2,_('verify the integrity of local package files')),
        (2,'depends',2,_('regenerate the depends table')),

    None,
    (1,'ugc',2,_('handles User Generated Content features')),
        (2,'login <repository>',1,_('login against a specified repository')),
        (2,'logout <repository>',1,_('logout from a specified repository')),
            (3,'--force',3,_('force action')),
        (2,'documents <repository>',1,_('manage package documents for the selected repository (comments, files, videos)')),
            (3,'get <pkgkey>',2,_('get available documents for the specified package key (example: x11-libs/qt)')),
            (3,'add <pkgkey>',2,_('add a new document to the specified package key (example: x11-libs/qt)')),
            (3,'remove <docs ids>',1,_('remove documents from database using their identifiers')),
        (2,'vote <repository>',1,_('manage package votes for the selected repository')),
            (3,'get <pkgkey>',2,_('get vote for the specified package key (example: x11-libs/qt)')),
            (3,'add <pkgkey>',2,_('add vote for the specified package key (example: x11-libs/qt)')),

    None,
    (1,'cache',2,_('handles Entropy cache')),
        (2,'clean',2,_('clean Entropy cache')),
        (2,'generate',1,_('regenerate Entropy cache')),
        (2,'--verbose',1,_('show more details')),
        (2,'--quiet',2,_('print results in a scriptable way')),
    None,
    (1,'cleanup',2,_('remove downloaded packages and clean temp. directories')),
    None,
    (1,'--info',2,_('show system information')),
    None,
]


options = sys.argv[1:]
_options = []

import re
opt_r = re.compile("^(\\-)([a-z]+)$")
for n in range(len(options)):
    if opt_r.match(options[n]):
        x = options[n]
        del options[n]
        options.extend(["-%s" % (d,) for d in x[1:]])

for opt in options:
    if opt in ["--nocolor","-N"]:
        nocolor()
    elif opt == "--debug":
        continue
    elif opt in ["--quiet","-q"]:
        etpUi['quiet'] = True
    elif opt in ["--verbose","-v"]:
        etpUi['verbose'] = True
    elif opt in ["--ask","-a"]:
        etpUi['ask'] = True
    elif opt in ["--pretend","-p"]:
        etpUi['pretend'] = True
    elif (opt == "--ihateprint"):
        etpUi['mute'] = True
    elif (opt == "--clean"):
        etpUi['clean'] = True
    else:
        _options.append(opt)
options = _options

# 'equo help' support
if options:
    if options[0] == "help":
        options.insert(0,"--help")

# print help
if (not options) or ("--help" in options):
    print_menu(myopts)
    if etpUi['verbose']:
        print_menu(myopts_extended)
    else:
        print_menu(myopts_ext_info)
    if not options:
        print_error(_("not enough parameters"))
    raise SystemExit(1)
# sure we don't need this after
del myopts

# print version
if (options[0] == "--version"):
    print_generic("Equo: v"+etpConst['entropyversion'])
    raise SystemExit(0)
elif (options[0] == "--info"):
    import text_rescue
    text_rescue.getinfo()
    raise SystemExit(0)

def do_moo():
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

def readerrorstatus():
    try:
        f = open(etpConst['errorstatus'],"r")
        status = int(f.readline().strip())
        f.close()
        return status
    except:
        writeerrorstatus(0)
        return 0

def writeerrorstatus(status):
    try:
        f = open(etpConst['errorstatus'],"w")
        f.write(str(status))
        f.flush()
        f.close()
    except:
        pass

def reset_cache():
    try:
        from entropy.client.interfaces import Client
        Equo = Client(noclientdb = 2)
        Equo.purge_cache()
        Equo.destroy()
    except:
        pass

def load_conf_cache():
    from entropy.client.interfaces import Client
    Equo = Client(noclientdb = 2)
    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue(_("Caching equo conf")), back = True)
    try:
        while 1:
            try:
                scandata = Equo.FileUpdates.scanfs(dcache = True, quiet = True)
                break
            except KeyboardInterrupt:
                continue
    except:
        if not etpUi['quiet']:
            print_info(red(" @@ ")+blue(_("Caching not run.")))
        Equo.destroy()
        return

    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue(_("Caching complete.")))

    if scandata: # can be None
        if len(scandata) > 0: # strict check
            if not etpUi['quiet']:
                mytxt = "%s %s %s." % (
                    _("There are"),
                    len(scandata),
                    _("configuration file(s) needing update"),
                )
                print_warning(darkgreen(mytxt))
                mytxt = "%s: %s" % (red(_("Please run")),bold("equo conf update"))
                print_warning(mytxt)
    Equo.destroy()

def main():
    try:
        rc = 0
        # sync mirrors tool
        if options[0] in ("update","repoinfo","status","notice",):
            import text_repositories
            rc = text_repositories.repositories(options)
            text_repositories.Equo.destroy()

        elif options[0] == "moo":
            do_moo()

        elif options[0] in ("install", "remove", "config", "world", "upgrade",
            "deptest", "unusedpackages", "libtest", "source", "hop"):

            import text_ui
            rc = text_ui.package(options)
            if options[0] not in ("hop",):
                load_conf_cache()
            else:
                text_ui.Equo.destroy()

        elif options[0] == "security":
            import text_security
            rc = text_security.security(options[1:])
            text_security.Equo.destroy()

        elif (options[0] == "query"):
            import text_query
            rc = text_query.query(options[1:])

        # smartapps tool
        elif (options[0] == "smart"):
            rc = -10
            if len(options) > 1:
                import text_smart
                rc = text_smart.smart(options[1:])

        elif (options[0] == "conf"):
            import text_configuration
            rc = text_configuration.configurator(options[1:])
            text_configuration.Equo.destroy()

        elif (options[0] == "cache"):
            import text_cache
            rc = text_cache.cache(options[1:])

        elif (options[0] == "search"):
            rc = -10
            if len(options) > 1:
                import text_query
                rc = text_query.search_package(options[1:])
            else:
                rc = -10

        elif (options[0] == "match"):
            rc = -10
            multiMatch = False
            multiRepo = False
            showRepo = False
            showDesc = False
            myoptions = []
            for opt in options:
                if opt == "--multimatch":
                    multiMatch = True
                elif opt == "--multirepo":
                    multiRepo = True
                elif opt == "--showrepo":
                    showRepo = True
                elif opt == "--showdesc":
                    showDesc = True
                else:
                    myoptions.append(opt)
            if len(myoptions) > 1:
                import text_query
                # repoMatch can be made using @repository  
                rc = text_query.match_package(myoptions[1:],
                                                multiMatch = multiMatch,
                                                multiRepo = multiRepo,
                                                showRepo = showRepo,
                                                showDesc = showDesc
                                            )
            else:
                rc = -10

        elif (options[0] == "database"):
            import text_rescue
            rc = text_rescue.database(options[1:])
            text_rescue.Equo.destroy()

        elif (options[0] == "ugc"):
            import text_ugc
            rc = text_ugc.ugc(options[1:])
            text_ugc.Equo.destroy()

        elif (options[0] == "community"):
            etpConst['community']['mode'] = True
            myopts = options[1:]
            if myopts:
                if myopts[0] == "repos":
                    try:
                        import server_reagent
                    except ImportError:
                        print_error(darkgreen(_("You need to install sys-apps/entropy-server. :-) Do it !")))
                        rc = 1
                    else:
                        repos_opts = myopts[1:]
                        if repos_opts:
                            if repos_opts[0] == "update":
                                rc = server_reagent.update(repos_opts[1:])
                                server_reagent.Entropy.close_server_databases()
                            elif repos_opts[0] == "inject":
                                rc = server_reagent.inject(repos_opts[1:])
                                server_reagent.Entropy.close_server_databases()
                elif myopts[0] == "mirrors":
                    try:
                        import server_activator
                    except ImportError:
                        print_error(darkgreen(_("You need to install sys-apps/entropy-server. :-) Do it !")))
                        rc = 1
                    else:
                        mirrors_opts = myopts[1:]
                        if mirrors_opts:
                            if mirrors_opts[0] == "sync":
                                server_activator.sync(mirrors_opts[1:])
                            elif mirrors_opts[0] == "packages-sync":
                                server_activator.sync(mirrors_opts[1:])
                            elif mirrors_opts[0] == "tidy":
                                server_activator.sync(mirrors_opts[1:], justTidy = True)
                            elif mirrors_opts[0].startswith("db-"):
                                mirrors_opts[0] = mirrors_opts[0][3:]
                                server_activator.database(mirrors_opts)

                elif myopts[0] == "database":

                    do = True
                    # hook to support counters command, which is just
                    # a duplicate of 'equo database counters'
                    # put here for completeness
                    if len(myopts) > 1:
                        if myopts[1] == "counters":
                            do = False
                            import text_rescue
                            rc = text_rescue.database(myopts[1:])
                            text_rescue.Equo.destroy()

                    if do:
                        try:
                            import server_reagent
                        except ImportError:
                            print_error(darkgreen(_("You need to install sys-apps/entropy-server. :-) Do it !")))
                            rc = 1
                        else:
                            rc = server_reagent.database(myopts[1:])
                            server_reagent.Entropy.close_server_databases()

                elif myopts[0] == "repo":
                    try:
                        import server_reagent
                    except ImportError:
                        print_error(darkgreen(_("You need to install sys-apps/entropy-server. :-) Do it !")))
                        rc = 1
                    else:
                        rc = server_reagent.repositories(myopts[1:])

                elif myopts[0] == "notice":
                    try:
                        import server_activator
                        if not hasattr(server_activator,'notice'):
                            raise ImportError
                    except ImportError:
                        print_error(darkgreen(_("You need to install/update sys-apps/entropy-server. :-) Do it !")))
                        rc = 1
                    else:
                        rc = server_activator.notice(myopts[1:])

                elif myopts[0] == "query":
                    try:
                        import server_query
                    except ImportError:
                        print_error(darkgreen(_("You need to install sys-apps/entropy-server. :-) Do it !")))
                        rc = 1
                    else:
                        rc = server_query.query(myopts[1:])

                elif myopts[0] == "spm":
                        try:
                            import server_reagent
                        except ImportError:
                            print_error(darkgreen(_("You need to install sys-apps/entropy-server. :-) Do it !")))
                            rc = 1
                        else:
                            rc = server_reagent.spm(myopts[1:])
                            server_reagent.Entropy.close_server_databases()

                elif myopts[0] == "deptest":
                    try:
                        import server_reagent
                    except ImportError:
                        print_error(darkgreen(_("You need to install sys-apps/entropy-server. :-) Do it !")))
                        rc = 1
                    else:
                        server_reagent.Entropy.dependencies_test()
                        server_reagent.Entropy.close_server_databases()

                elif myopts[0] == "pkgtest":
                    try:
                        import server_reagent
                    except ImportError:
                        print_error(darkgreen(_("You need to install sys-apps/entropy-server. :-) Do it !")))
                        rc = 1
                    else:
                        server_reagent.Entropy.verify_local_packages(["world"], ask = etpUi['ask'])
                        server_reagent.Entropy.close_server_databases()

                elif myopts[0] == "depends":
                    try:
                        import server_reagent
                    except ImportError:
                        print_error(darkgreen(_("You need to install sys-apps/entropy-server. :-) Do it !")))
                        rc = 1
                    else:
                        rc = server_reagent.Entropy.depends_table_initialize()
                        server_reagent.Entropy.close_server_databases()

        elif (options[0] == "cleanup"):
            entropyTools.cleanup([ etpConst['packagestmpdir'], etpConst['logdir'], etpConst['entropyunpackdir'], etpConst['packagesbindir'] ])
            rc = 0
        else:
            rc = -10

        if rc == -10:
            status = readerrorstatus()
            print_error(darkred(etpExitMessages[status]))
            # increment
            if status < len(etpExitMessages)-1:
                writeerrorstatus(status+1)
            rc = 10
        else:
            writeerrorstatus(0)

        entropyTools.kill_threads()
        raise SystemExit(rc)

    except SystemDatabaseError:

        reset_cache()
        print_error(darkred(" * ")+red(_("Installed Packages Database not found or corrupted. Please generate it using 'equo database' tools")))
        raise SystemExit(101)

    except OnlineMirrorError as e:

        print_error(darkred(" * ")+red(unicode(e)+". %s." % (_("Cannot continue"),) ))
        raise SystemExit(101)

    except RepositoryError as e:

        reset_cache()
        print_error(darkred(" * ")+red(unicode(e)+". %s." % (_("Cannot continue"),) ))
        raise SystemExit(101)

    except FtpError as e:

        print_error(darkred(" * ")+red(unicode(e)+". %s." % (_("Cannot continue"),) ))
        raise SystemExit(101)

    except PermissionDenied as e:

        print_error(darkred(" * ")+red(unicode(e)+". %s." % (_("Cannot continue"),) ))
        raise SystemExit(1)

    except FileNotFound as e:

        print_error(darkred(" * ")+red(unicode(e)+". %s." % (_("Cannot continue"),) ))
        raise SystemExit(1)

    except SPMError as e:

        print_error(darkred(" * ")+red(unicode(e)+". %s." % (_("Cannot continue"),) ))
        raise SystemExit(1)

    except dbapi2Exceptions['OperationalError'] as e:

        if unicode(e).find("disk I/O error") == -1:
            raise
        print_error(darkred(" * ")+red(unicode(e)+". %s." % (_("Cannot continue. Your hard disk is probably faulty."),) ))
        raise SystemExit(101)

    except SystemError as e: # becoming from entropy.db

        print_error(darkred(" * ")+red(unicode(e)+". %s." % (_("Cannot continue"),) ))
        raise SystemExit(1)

    except SystemExit:
        raise

    except IOError as e:

        reset_cache()
        if e.errno != 32:
            raise

    except OSError as e:

        if e.errno == 28:
            entropyTools.print_exception()
            print_error(darkred(_("Your hard drive is full! Next time remember to have a look at it before starting. I'm sorry, there's nothing I can do for you. It's your fault :-(")))
            raise SystemExit(5)
        else:
            raise

    except KeyboardInterrupt:
        raise SystemExit(1)

    except:

        reset_cache()
        entropyTools.kill_threads()

        Text = TextInterface()
        print_error(darkred(_("Hi. My name is Bug Reporter. I am sorry to inform you that Equo crashed. Well, you know, shit happens.")))
        print_error(darkred(_("But there's something you could do to help Equo to be a better application.")))
        print_error(darkred(_("-- EVEN IF I DON'T WANT YOU TO SUBMIT THE SAME REPORT MULTIPLE TIMES --")))
        print_error(darkgreen(_("Now I am showing you what happened. Don't panic, I'm here to help you.")))

        entropyTools.print_exception()

        import traceback
        exception_data = ""
        try:
            ferror = open("/tmp/equoerror.txt","w")
            traceback.print_exc(file = ferror)
            ferror.write("\nRevision: "+etpConst['entropyversion']+"\n\n")
            exception_data = entropyTools.print_exception(True)
            ferror.write("\n")
            ferror.flush()
            ferror.close()
            f = open("/tmp/equoerror.txt","r")
            errorText = f.readlines()
            f.close()
            ferror = open("/tmp/equoerror.txt","aw")
            ferror.write("\n\n")
            for x in exception_data:
                ferror.write(unicode(x)+"\n")
            ferror.flush()
            ferror.close()
        except Exception as e:
            print()
            print_error(darkred(_("Oh well, I cannot even write to /tmp. So, please copy the error and mail lxnay@sabayonlinux.org.")))
            raise SystemExit(1)

        print_generic("")

        print_error(darkgreen(_("Of course you are on the Internet...")))
        rc = Text.askQuestion(_("Erm... Can I send the error, along with some information\n   about your hardware to my creators so they can fix me? (Your IP will be logged)"))
        if rc == _("No"):
            print_error(darkgreen(_("Ok, ok ok ok... Sorry!")))
            raise SystemExit(2)

        print_error(darkgreen(_("If you want to be contacted back (and actively supported), also answer the questions below:")))
        name = readtext(_("Your Full name:"))
        email = readtext(_("Your E-Mail address:"))
        description = readtext(_("What you were doing:"))
        errorText = ''.join(errorText)

        from entropy.client.interfaces.qa import UGCErrorReportInterface
        try:
            error = UGCErrorReportInterface()
        except (IncorrectParameter, OnlineMirrorError,):
            from entropy.qa import ErrorReportInterface
            post_url = "http://svn.sabayonlinux.org/entropy/standard" + \
                "/sabayonlinux.org/handlers/http_error_report.php"
            error = ErrorReportInterface(post_url)

        error.prepare(errorText, name, email, '\n'.join([unicode(x) for x in exception_data]), description)
        result = error.submit()
        if result:
            print_error(darkgreen(_("Thank you very much. The error has been reported and hopefully, the problem will be solved as soon as possible.")))
        else:
            print_error(darkred(_("Ugh. Cannot send the report. I saved the error to /tmp/equoerror.txt. When you want, mail the file to lxnay@sabayonlinux.org.")))
            raise SystemExit(4)

    raise SystemExit(1)

if __name__ == "__main__":
    main()

