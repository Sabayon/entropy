#!/usr/bin/python
'''
    Copyright (C) 2007-2008 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

from entropyConstants import *
from outputTools import *
from entropy import EquoInterface
from entropy_i18n import _
Equo = EquoInterface()
Equo.UGC.quiet = False


def ugc(options):

    if len(options) < 1:
        return 0
    cmd = options[0]
    do_force = False
    myopts = []
    for opt in options[1:]:
        if opt == "--force":
            do_force = True
        else:
            myopts.append(opt)
    options = myopts
    rc = -10

    if cmd == "login":
        if options: rc = ugcLogin(options[0], force = do_force)
    elif cmd == "logout":
        if options: rc = ugcLogout(options[0])

    return rc


def ugcLogin(repository, force = False):

    if repository not in Equo.validRepositories:
        print_error(red("%s: %s." % (_("Invalid repository"),repository,)))
        Equo.UGC.remove_login(repository)
        return 1

    login_data = Equo.UGC.read_login(repository)
    if (login_data != None) and not force:
        print_info(
            "[%s] %s %s. %s." % (
                darkgreen(repository),
                blue(_("Already logged in as")),
                bold(login_data[0]),
                blue(_("Please logout first"))
            )
        )
        return 0
    elif (login_data != None) and force:
        Equo.UGC.remove_login(repository)

    status, msg = Equo.UGC.login(repository)
    if status:
        login_data = Equo.UGC.read_login(repository)
        print_info(
            "[%s:uid:%s] %s: %s. %s." % (
                darkgreen(repository),
                etpConst['uid'],
                blue(_("Successfully logged in as")),
                bold(login_data[0]),
                blue(_("From now on, any UGC action will be committed as this user"))
            )
        )
        return 0
    else:
        print_info(
            "[%s] %s." % (
                darkgreen(repository),
                blue(_("Login error. Not logged in.")),
            )
        )
        return 1


def ugcLogout(repository):

    if repository not in Equo.validRepositories:
        print_error(red("%s: %s." % (_("Invalid repository"),repository,)))
        return 1

    login_data = Equo.UGC.read_login(repository)
    if login_data == None:
        print_info(
            "[%s] %s." % (
                darkgreen(repository),
                blue(_("Not logged in")),
            )
        )
    else:
        Equo.UGC.remove_login(repository)
        print_info(
            "[%s] %s %s %s." % (
                darkgreen(repository),
                blue(_("User")),
                bold(login_data[0]),
                blue(_("has been logged out")),
            )
        )
    return 0