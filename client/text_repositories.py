#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo repositories handling library

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

########################################################
####
##   Repositories Tools
#

from entropyConstants import *
from outputTools import *
import exceptionTools
from entropy import EquoInterface, rssFeed
Equo = EquoInterface(noclientdb = True)
from entropy_i18n import _

def repositories(options):

    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestForceUpdate = False
    rc = 0
    repo_names = []
    for opt in myopts:
        if (opt == "--force"):
            equoRequestForceUpdate = True
        elif opt in etpRepositoriesOrder:
            repo_names.append(opt)

    if (options[0] == "update"):
        # check if I am root
        if not Equo.entropyTools.is_user_in_entropy_group():
            mytxt = darkred(_("You must be either root or in the %s group.")) % (etpConst['sysgroup'],)
            print_error(mytxt)
            return 1
        rc = do_sync(reponames = repo_names, forceUpdate = equoRequestForceUpdate)
    elif (options[0] == "status"):
        for repo in etpRepositories:
            showRepositoryInfo(repo)
    elif (options[0] == "repoinfo"):
        myopts = options[1:]
        if not myopts:
            rc = -10
        else:
            rc = showRepositoryFile(myopts[0], myopts[1:])

    elif (options[0] == "notice"):
        myopts = options[1:]
        myopts = [x for x in myopts if x in etpRepositories]
        if not myopts:
            rc = -10
        else:
            rc = 0
            for repoid in myopts:
                noticeBoardReader(repoid)
    else:
        rc = -10
    return rc


def showRepositoryFile(myfile, repos):

    if myfile not in ["make.conf", "profile.link", "package.use", \
        "package.mask", "package.unmask","package.keywords"]:
            return - 10

    if not repos:
        return -10

    myrepos = []
    for repo in repos:
        if repo in etpRepositories:
            myrepos.append(repo)
    if not myrepos:
        if not etpUi['quiet']:
            print_error(darkred(" * ")+darkred("%s." % (_("No valid repositories"),) ))
        return 1

    for repo in myrepos:
        mypath = os.path.join(etpRepositories[repo]['dbpath'],myfile)
        if (not os.path.isfile(mypath)) or (not os.access(mypath,os.R_OK)):
            if not etpUi['quiet']:
                mytxt = "%s: %s." % (blue(os.path.basename(mypath)),darkred(_("not available")),)
                print_error(darkred(" [%s] " % (repo,) )+mytxt)
            continue
        f = open(mypath,"r")
        line = f.readline()
        if not line:
            if not etpUi['quiet']:
                mytxt = "%s: %s." % (blue(os.path.basename(mypath)),darkred(_("is empty")),)
                print_error(darkred(" [%s] " % (repo,) )+mytxt)
            continue
        if not etpUi['quiet']:
            mytxt = "%s: %s." % (darkred(_("showing")),blue(os.path.basename(mypath)),)
            print_info(darkred(" [%s] " % (repo,) )+mytxt)
        while line:
            sys.stdout.write(line)
            line = f.readline()
        f.close()

def showRepositories():
    print_info(darkred(" * ")+darkgreen("%s:" % (_("Active Repositories"),) ))
    repoNumber = 0
    for repo in etpRepositories:
        repoNumber += 1
        print_info(blue("\t#"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
        sourcecount = 0
        for pkgrepo in etpRepositories[repo]['packages']:
            sourcecount += 1
            print_info( red("\t\t%s #%s : %s") % (_("Packages Mirror"),sourcecount,darkgreen(pkgrepo),) )
        print_info( red("\t\t%s: %s") % (_("Database URL"),darkgreen(etpRepositories[repo]['database']),))
        print_info( red("\t\t%s: %s") % (_("Repository identifier"),bold(repo),) )
        print_info( red("\t\t%s: %s") % (_("Repository database path"),blue(etpRepositories[repo]['dbpath']),) )
    return 0

def showRepositoryInfo(reponame):

    repoNumber = 0
    for repo in etpRepositories:
        repoNumber += 1
        if repo == reponame:
            break
    print_info(blue("#"+str(repoNumber))+bold(" "+etpRepositories[reponame]['description']))
    if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']):
        status = _("active")
    else:
        status = _("never synced")
    print_info( darkgreen("\t%s: %s") % (_("Status"),darkred(status),) )
    urlcount = 0
    for repourl in etpRepositories[reponame]['packages'][::-1]:
        urlcount += 1
        print_info( red("\t%s #%s: %s") % (_("Packages URL"),urlcount,darkgreen(repourl),) )
    print_info( red("\t%s: %s") % (_("Database URL"),darkgreen(etpRepositories[reponame]['database']),) )
    print_info( red("\t%s: %s") % (_("Repository name"),bold(reponame),) )
    print_info( red("\t%s: %s") % (_("Repository database path"),blue(etpRepositories[reponame]['dbpath']),) )
    revision = Equo.get_repository_revision(reponame)
    mhash = Equo.get_repository_db_file_checksum(reponame)
    print_info( red("\t%s: %s") % (_("Repository database checksum"),mhash,) )
    print_info( red("\t%s: %s") % (_("Repository revision"),darkgreen(str(revision)),) )

    return 0

def do_sync(reponames = [], forceUpdate = False):

    # load repository class
    try:
        repoConn = Equo.Repositories(reponames, forceUpdate)
    except exceptionTools.PermissionDenied:
        mytxt = darkred(_("You must be either root or in the %s group.")) % (etpConst['sysgroup'],)
        print_error("\t"+mytxt)
        return 1
    except exceptionTools.MissingParameter:
        print_error(darkred(" * ")+red("%s %s" % (_("No repositories specified in"),etpConst['repositoriesconf'],)))
        return 127
    except exceptionTools.OnlineMirrorError:
        print_error(darkred(" @@ ")+red(_("You are not connected to the Internet. You should.")))
        return 126
    except Exception, e:
        print_error(darkred(" @@ ")+red("%s: %s" % (_("Unhandled exception"),e,)))
        return 2

    rc = repoConn.sync()
    if not rc:
        for reponame in reponames:
            showNoticeBoardSummary(reponame)
    return rc

def check_notice_board_availability(reponame):
    def show_err():
        print_error(darkred(" @@ ")+blue("%s" % (_("Notice board not available"),) ))

    board_file = etpRepositories[reponame]['local_notice_board']
    if not (os.path.isfile(board_file) and os.access(board_file,os.R_OK)):
        show_err()
        return
    if Equo.entropyTools.get_file_size(board_file) < 10:
        show_err()
        return

    try:
        myrss = rssFeed(board_file,'','')
    except:
        show_err()
        return None
    data = myrss.getEntries()
    if data == None:
        show_err()
    return data

def show_notice(key, mydict):

    mytxt = "[%s] [%s] %s: %s" % (
        blue(str(key)),
        brown(mydict['pubDate']),
        _("Title"),
        darkred(mydict['title']),
    )
    print_info(mytxt)

    mytxt = "\t%s: %s" % (
        darkgreen(_("Content")),
        blue(mydict['description']),
    )
    print_info(mytxt)
    mytxt = "\t%s: %s" % (
        darkgreen(_("Link")),
        blue(mydict['link']),
    )
    print_info(mytxt)

    def fake_callback(s):
        return True

    input_params = [('idx',_('Press Enter to continue'),fake_callback,False)]
    Equo.inputBox('', input_params, cancel_button = True)
    return


def show_notice_selector(title, mydict):
    mykeys = sorted(mydict.keys())

    for key in mykeys:
        mydata = mydict.get(key)
        mytxt = "[%s] [%s] %s: %s" % (
            blue(str(key)),
            brown(mydata['pubDate']),
            _("Title"),
            darkred(mydata['title']),
        )
        print_info(mytxt)

    mytxt = "[%s] %s" % (
        blue("-1"),
        darkred(_("Exit")),
    )
    print_info(mytxt)

    def fake_callback(s):
        return s
    input_params = [('id',blue(_('Choose one by typing its identifier')),fake_callback,False)]
    data = Equo.inputBox(title, input_params, cancel_button = True)
    if not isinstance(data,dict):
        return -1
    try:
        return int(data['id'])
    except ValueError:
        return -2

def noticeBoardReader(reponame):

    data = check_notice_board_availability(reponame)
    if data == None: return
    items, counter = data
    while 1:
        try:
            sel = show_notice_selector('', items)
        except KeyboardInterrupt:
            return 0
        if (sel >= 0) and (sel <= counter):
            show_notice(sel, items.get(sel))
        elif sel == -1:
            return 0


def showNoticeBoardSummary(reponame):

    mytxt = "%s %s: %s" % (darkgreen(" @@ "),brown(_("Notice board")),bold(reponame),)
    print_info(mytxt)

    data = check_notice_board_availability(reponame)
    if data == None: return

    mydict, mylen = data
    mykeys = sorted(mydict.keys())
    for key in mykeys:
        mydata = mydict.get(key)
        mytxt = "    [%s] [%s] %s: %s" % (
            blue(str(key)),
            brown(mydata['pubDate']),
            _("Title"),
            darkred(mydata['title']),
        )
        print_info(mytxt)
