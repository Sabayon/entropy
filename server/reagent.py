#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server}.

"""
import os, sys
sys.path.insert(0, '../libraries')
sys.path.insert(1, '../client')
sys.path.insert(2, '../server')
sys.path.insert(3, '/usr/lib/entropy/client')
sys.path.insert(4, '/usr/lib/entropy/libraries')
sys.path.insert(5, '/usr/lib/entropy/server')
from entropy.i18n import _
import entropy.tools
from entropy.output import red, print_error, print_generic, \
    is_stdout_a_tty, nocolor, etpUi, darkgreen
from entropy.const import etpConst, const_kill_threads
from entropy.server.interfaces import Server
from text_tools import print_menu, acquire_entropy_locks, release_entropy_locks

# Check if we need to disable colors
if not is_stdout_a_tty():
    nocolor()

help_opts = [
    None,
    (0, " ~ reagent ~ ", 1,
        'Entropy Framework Server - (C) %s' % (entropy.tools.get_year(),) ),
    None,
    (0, _('Basic Options'), 0, None),
    None,
    (1, '--help', 2, _('this output')),
    (1, '--version', 1, _('print version')),
    (1, '--nocolor', 1, _('disable colorized output')),
    None,
    (0, _('Application Options'), 0, None),
    None,
    (1, 'status', 3, _('show current repositories status')),
    None,
    (1, 'update', 3, _('scan the System looking for newly compiled packages')),
        (2, '--seekstore', 2, _('analyze the Entropy Store directory directly')),
        (2, '--repackage <atoms>', 1, _('repackage the specified atoms')),
        (2, '--noask', 2, _('do not ask anything except critical things')),
        (2, '--atoms <atoms>', 1, _('manage only the specified atoms')),
        (2, '--interactive', 2, _('run in interactive mode (asking things one by one)')),
    None,
    (1, 'inject <packages>', 1, _('add binary packages to repository w/o affecting scopes (multipackages)')),
    None,
    (1, 'query', 3, _('do some searches into repository databases')),
        (2, 'search', 3, _('search packages inside the default repository database')),
        (2, 'match', 3, _('match package dependency inside the default repository database')),
        (2, 'needed', 3, _('show runtime libraries needed by the provided atoms')),
        (2, 'revdeps', 2, _('show what packages depend on the provided atoms')),
        (2, 'tags', 3, _('show packages owning the specified tags')),
        (2, 'sets', 3, _('search available package sets')),
        (2, 'files', 3, _('show files owned by the provided atoms')),
        (2, 'belongs', 2, _('show from what package the provided files belong')),
        (2, 'description', 2, _('search packages by description')),
        (2, 'list', 3, _('list all the packages in the default repository')),
        (2, 'graph', 3, _('show direct depdendencies tree for provided installable atoms')),
            (3, '--complete', 1, _('include system packages, build deps and circularity information')),
        (2, 'revgraph', 2, _('show reverse depdendencies tree for provided installed atoms')),
            (3, '--complete', 1, _('include system packages, build deps and circularity information')),
        (2, '--verbose', 2, _('show more details')),
        (2, '--quiet', 2, _('print results in a scriptable way')),
    None,
    (1, 'repo', 3, _('manage a repository')),
        (2, '--initialize', 3, _('(re)initialize the current repository database')),
            (3, '--repo=<repo>', 2, _('(re)create the database for the specified repository')),
        (2, 'bump', 4, _('manually force a revision bump for the current repository database')),
            (3, '--sync', 3, _('synchronize the database')),
        (2, 'flushback [branches]', 2, _('flush back old branches packages to current branch')),
        (2, 'remove', 4, _('remove the provided atoms from the current repository database')),
            (3, '--nodeps', 2, _('do not include reverse dependencies')),
        (2, 'multiremove', 3, _('remove the provided injected atoms (all if no atom specified)')),
        (2, 'create-empty-database', 2, _('create an empty repository database in the provided path')),
        (2, 'switchbranch <from branch> <to branch>', 3, _('switch to the specified branch the repository')),
        (2, 'md5remote [atoms]', 3, _('verify remote integrity of the provided atoms')),
        (2, 'backup', 4, _('backup current repository database')),
        (2, 'restore', 4, _('restore a previously backed-up repository database')),
        (2, 'enable <repo>', 3, _('enable the specified repository')),
        (2, 'disable <repo>', 3, _('disable the specified repository')),
        (2, 'package-dep <repo> [atoms]', 1, _('handle packages dependencies')),
        (2, 'package-tag <repo> <tag-string> [atoms]', 1, _('clone a package assigning it an arbitrary tag')),
        (2, 'package-mask <repo> [atoms]', 1, _('mask given package in given repository')),
        (2, 'package-unmask <repo> [atoms]', 1, _('unmask given packages in given repository')),
        (2, 'move <from> <to> [atoms]', 1, _('move packages from a repository to another')),
            (3, '--deps', 3, _('pulls dependencies in')),
        (2, 'copy <from> <to> [atoms]', 1, _('copy packages from a repository to another')),
            (3, '--deps', 3, _('pulls dependencies in')),
        (2, 'default <repo_id>', 2, _('set the default repository')),
    None,
    (1, 'key', 3, _('manage repository digital signatures (OpenGPG)')),
        (2, 'create [repos]', 1, _('create keypair for repositories and sign packages')),
        (2, 'delete [repos]', 1, _('delete keypair (and digital signatures) of repository')),
        (2, 'status [repos]', 1, _('show currently configured keys information for given repositories')),
        (2, 'sign [repos]', 1, _('sign (or re-sign) packages in repository using currently set keypair')),
        (2, 'import <repo_id> <privkey_path> <pubkey_path>', 1, _('import keypair, bind to given repository')),
        (2, 'export-public <repo_id> <key_path>', 1, _('export public key of given repository')),
        (2, 'export-private <repo_id> <key_path>', 1, _('export private key of given repository')),
    None,
    (1, 'spm', 3, _('source package manager functions')),
        (2, 'compile', 3, _('compilation function')),
            (3, 'categories', 2, _('compile packages belonging to the provided categories')),
                (4, '--list', 2, _('just list packages')),
                (4, '--nooldslots', 1, _('do not pull old package slots')),
            (3, 'pkgset', 3, _('compile packages in provided package set names')),
                (4, '--list', 2, _('just list packages')),
                (4, '--rebuild', 1, _('rebuild everything')),
                (4, '--dbupdate', 1, _('run database update if all went fine')),
                (4, '--dbsync', 1, _('run mirror sync if all went fine')),
        (2, 'orphans', 3, _('scan orphaned packages in SPM')),
        (2, 'new [categories]', 2, _('scan new packages available in SPM')),
    None,
    (1, 'deptest', 2, _('look for unsatisfied dependencies')),
    (1, 'libtest', 2, _('look for missing libraries')),
        (2, '--dump', 2, _('dump results to files')),
    (1, 'pkgtest', 2, _('verify the integrity of local package files')),
    None,
    (1, 'cleanup', 2, _('remove downloaded packages and clean temp. directories)')),
    None,
]

def handle_exception(exc_class, exc_instance, exc_tb):

    # restore original exception handler, to avoid loops
    uninstall_exception_handler()
    entropy.tools.kill_threads()

    if exc_class is KeyboardInterrupt:
        raise SystemExit(1)

    raise exc_instance

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__

def get_entropy_server():
    return Server(community_repo = etpConst['community']['mode'])

options = sys.argv[1:]

# print version
if ("--version" in options) or ("-V" in options):
    print_generic("reagent: "+etpConst['entropyversion'])
    raise SystemExit(0)

import re
opt_r = re.compile("^(\\-)([a-z]+)$")
for n in range(len(options)):
    if opt_r.match(options[n]):
        x = options[n]
        del options[n]
        options.extend(["-%s" % (d,) for d in x[1:]])

# preliminary options parsing
_options = []
for opt in options:
    if opt == "--nocolor":
        nocolor()
    elif opt in ["--quiet", "-q"]:
        etpUi['quiet'] = True
    elif opt in ["--verbose", "-v"]:
        etpUi['verbose'] = True
    elif opt in ["--ask", "-a"]:
        etpUi['ask'] = True
    elif opt in ["--pretend", "-p"]:
        etpUi['pretend'] = True
    else:
        _options.append(opt)
options = _options

# print help
if not options or ("--help" in options) or ("-h" in options):
    print_menu(help_opts)
    if len(options) < 1:
        print_error("not enough parameters")
    raise SystemExit(1)

rc = -10
if not entropy.tools.is_root():
    print_error("you must be root in order to run "+sys.argv[0])

install_exception_handler()
main_cmd = options.pop(0)

acquired = False
server = None
try:
    server = get_entropy_server()
    acquired = acquire_entropy_locks(server)

    if not acquired:
        print_error(darkgreen(_("Another Entropy is currently running.")))
        rc = 1

    elif main_cmd == "update":
        import server_reagent
        rc = server_reagent.update(options)
        get_entropy_server().close_repositories()

    elif main_cmd == "inject":
        import server_reagent
        rc = server_reagent.inject(options)
        get_entropy_server().close_repositories()

    elif main_cmd == "query":
        import server_query
        rc = server_query.query(options)

    elif main_cmd == "repo":
        if "switchbranch" in options:
            etpUi['warn'] = False
        import server_reagent
        rc = server_reagent.repositories(options)
        get_entropy_server().close_repositories()

    elif main_cmd == "status":
        import server_reagent
        server_reagent.status()
        get_entropy_server().close_repositories()
        rc = 0

    elif main_cmd == "key":
        import server_key
        rc = server_key.key(options)

    elif main_cmd == "deptest":
        server = get_entropy_server()
        server.dependencies_test()
        server.close_repositories()
        rc = 0

    elif main_cmd == "pkgtest":
        server = get_entropy_server()
        server.verify_local_packages([], ask = etpUi['ask'])
        server.close_repositories()
        rc = 0

    elif main_cmd == "libtest":
        server = get_entropy_server()
        dump = "--dump" in options
        rc, pkgs = server.test_shared_objects(
            dump_results_to_file = dump)
        x = server.close_repositories()

    # cleanup
    elif main_cmd == "cleanup":
        import text_tools
        rc = text_tools.cleanup([etpConst['packagestmpdir'], etpConst['logdir']])

    # deptest tool
    elif main_cmd == "spm":
        import server_reagent
        rc = server_reagent.spm(options)
        get_entropy_server().close_repositories()
finally:
    if server is not None:
        if acquired:
            release_entropy_locks(server)
        server.shutdown()

if rc == -10:
    print_menu(help_opts)
    print_error(red(" %s." % (_("Wrong parameters"),) ))
    rc = 10

uninstall_exception_handler()
entropy.tools.kill_threads()
raise SystemExit(rc)
