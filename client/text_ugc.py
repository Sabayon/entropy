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
#Equo.UGC.quiet = False


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
    elif cmd == "comments":
        if options: rc = ugcComments(options)

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

def ugcComments(options):

    rc = -10
    repository = options[0]
    options = options[1:]
    if not options: return rc
    cmd = options[0]
    options = options[1:]
    if not options: return rc
    pkgkey = options[0]
    options = options[1:]

    rc = 0
    if cmd == "get":
        data, err_string = Equo.UGC.get_comments(repository, pkgkey)
        if not isinstance(data,tuple):
            print_error(
                "[%s:%s] %s: %s, %s" % (
                    darkgreen(repository),
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    data,
                    err_string,
                )
            )
            return 1
        for comment_dict in data:
            showComment(comment_dict, repository, pkgkey)

    return rc

def showComment(mydict, repository, pkgkey):

    title = unicode(mydict['title'],'raw_unicode_escape')
    if not title: title = _("No title")
    title = darkgreen(title)
    doctype = None
    for item in etpConst['ugc_doctypes']:
        if etpConst['ugc_doctypes'][item] == mydict['iddoctype']:
            doctype = item
            break
    if doctype == None: doctype = _("Unknown type")
    print_info(" %s [%s|%s|%s|%s|%s|%s]" % (
            bold(u"@@"),
            bold(unicode(mydict['iddoc'])),
            darkred(unicode(doctype)),
            darkgreen(unicode(repository)),
            purple(unicode(pkgkey)),
            blue(unicode(mydict['username'])),
            darkgreen(unicode(mydict['ts'])),
        )
    )
    print_info("\t%s: %s" % (
            blue(_("Title")),
            title,
        )
    )
    text = mydict['ddata'].tostring()
    text = unicode(text,'raw_unicode_escape')
    _my_formatted_print(text,"\t%s: " % (blue(_("Comment")),),"\t")

    print_info("\t%s: %s" % (
            blue(_("Keywords")),
            ', '.join(mydict['keywords']),
        )
    )



def _my_formatted_print(data,header,reset_columns, min_chars = 25, color = None):
    if type(data) is set:
        mydata = list(data)
    elif type(data) is not list:
        mydata = data.split()
    else:
        mydata = data
    fcount = 0
    desc_text = header
    for x in mydata:
        fcount += len(x)
        if color:
            desc_text += color(x)+" "
        else:
            desc_text += x+" "
        if fcount > min_chars:
            fcount = 0
            print_info(desc_text)
            desc_text = reset_columns
    if fcount > 0: print_info(desc_text)
