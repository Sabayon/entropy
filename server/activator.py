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
from entropy.output import red, is_stdout_a_tty, nocolor, print_generic, \
    etpUi, print_menu, print_error
from entropy.const import etpConst, const_kill_threads
from entropy.core.settings.base import SystemSettings
SysSettings = SystemSettings()

# Check if we need to disable colors
if not is_stdout_a_tty():
    nocolor()

help_opts = [
    None,
    (0, " ~ "+SysSettings['system']['name']+" ~ "+sys.argv[0]+" ~ ", 1,
        'Entropy Package Manager - (C) %s' % (entropy.tools.get_year(),) ),
    None,
    (0, _('Basic Options'), 0, None),
    None,
    (1, '--help', 2, _('this output')),
    (1, '--version', 1, _('print version')),
    (1, '--nocolor', 1, _('disable colorized output')),
    None,
    (0, _('Application Options'), 0, None),
    None,
    (1, 'sync', 2, _('sync packages, database and also do some tidy')),
    (2, '--branch=<branch>', 1, _('choose on what branch operating')),
    (2, '--noask', 2, _('do not ask anything except critical things')),
    (2, '--syncall', 2, _('sync all the configured repositories')),
    None,
    (1, 'tidy', 2, _('remove binary packages not in repositories and expired')),
    None,
    (1, 'packages', 1, _('package repositories handling functions')),
    (2, 'sync', 3, _('sync package repositories across primary mirrors')),
    (3, '--ask', 3, _('ask before making any changes')),
    (3, '--pretend', 2, _('only show what would be done')),
    (3, '--syncall', 2, _('sync all the configured repositories')),
    (3, '--do-packages-check', 1, _('also verify packages integrity')),
    None,
    (1, 'database', 1, _('database handling functions')),
    (2, 'sync', 3, _('sync the current repository database across primary mirrors')),
    (2, 'lock', 3, _('lock the current repository database (server-side)')),
    (2, 'unlock', 3, _('unlock the current repository database (server-side)')),
    (2, 'download-lock', 2, _('lock the current repository database (client-side)')),
    (2, 'download-unlock', 1, _('unlock the current repository database (client-side)')),
    (2, 'lock-status', 2, _('show current lock status')),
    (2, '--syncall', 2, _('sync all the configured repositories')),
    None,
    (1, 'notice', 1, _('notice board handling functions')),
    (2, 'add', 2, _('add a news item to the notice board')),
    (2, 'remove', 2, _('remove a news item from the notice board')),
    (2, 'read', 2, _('read the current notice board')),
    None,
]

options = sys.argv[1:]

# print version
if ("--version" in options) or ("-V" in options):
    print_generic("activator: "+etpConst['entropyversion'])
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
    print_error("you must be root in order to run activator")
    rc = 2

main_cmd = options.pop(0)

elif main_cmd == "sync":
    import server_activator
    rc = server_activator.sync(options)

elif main_cmd == "tidy":
    import server_activator
    rc = server_activator.sync(options, just_tidy = True)

elif main_cmd == "database":
    import server_activator
    rc = server_activator.database(options)

elif main_cmd == "packages":
    import server_activator
    rc = server_activator.packages(options)

# database tool
elif main_cmd == "notice":
    import server_activator
    rc = server_activator.notice(options)

if rc == -10:
    print_menu(help_opts)
    print_error(red(" %s." % (_("Wrong parameters"),) ))

const_kill_threads()
raise SystemExit(rc)
