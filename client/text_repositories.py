# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""

########################################################
####
##   Repositories Tools
#

from entropy.const import *
from entropy.output import *
from entropy.exceptions import *
from entropy.client.interfaces import Client
Equo = Client(noclientdb = True)
from entropy.i18n import _

def repositories(options):

    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestForceUpdate = False
    rc = 0
    repo_names = []
    for opt in myopts:
        if (opt == "--force"):
            equoRequestForceUpdate = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return -10
        elif opt in Equo.SystemSettings['repositories']['order']:
            repo_names.append(opt)

    if (options[0] == "update"):
        # check if I am root
        if not Equo.entropyTools.is_user_in_entropy_group():
            mytxt = darkred(_("You must be either root or in the %s group.")) % (etpConst['sysgroup'],)
            print_error(mytxt)
            return 1
        rc = do_sync(reponames = repo_names, forceUpdate = equoRequestForceUpdate)
    elif (options[0] == "status"):
        for repo in Equo.SystemSettings['repositories']['order']:
            showRepositoryInfo(repo)
    elif (options[0] == "repoinfo"):
        myopts = options[1:]
        if not myopts:
            rc = -10
        else:
            rc = showRepositoryFile(myopts[0], myopts[1:])

    elif (options[0] == "notice"):
        myopts = options[1:]
        myopts = [x for x in myopts if x in Equo.SystemSettings['repositories']['available']]
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
        "package.mask", "package.unmask", "package.keywords"]:
            return - 10

    if not repos:
        return -10

    myrepos = []
    for repo in repos:
        if repo in Equo.SystemSettings['repositories']['available']:
            myrepos.append(repo)
    if not myrepos:
        if not etpUi['quiet']:
            print_error(darkred(" * ")+darkred("%s." % (_("No valid repositories"),) ))
        return 1

    for repo in myrepos:
        mypath = os.path.join(Equo.SystemSettings['repositories']['available'][repo]['dbpath'], myfile)
        if (not os.path.isfile(mypath)) or (not os.access(mypath, os.R_OK)):
            if not etpUi['quiet']:
                mytxt = "%s: %s." % (blue(os.path.basename(mypath)), darkred(_("not available")),)
                print_error(darkred(" [%s] " % (repo,) )+mytxt)
            continue
        f = open(mypath, "r")
        line = f.readline()
        if not line:
            if not etpUi['quiet']:
                mytxt = "%s: %s." % (blue(os.path.basename(mypath)), darkred(_("is empty")),)
                print_error(darkred(" [%s] " % (repo,) )+mytxt)
            continue
        if not etpUi['quiet']:
            mytxt = "%s: %s." % (darkred(_("showing")), blue(os.path.basename(mypath)),)
            print_info(darkred(" [%s] " % (repo,) )+mytxt)
        while line:
            sys.stdout.write(line)
            line = f.readline()
        f.close()
        sys.stdout.write("\n")

def showRepositories():
    print_info(darkred(" * ")+darkgreen("%s:" % (_("Active Repositories"),) ))
    repoNumber = 0
    for repo in Equo.SystemSettings['repositories']['order']:
        repoNumber += 1
        print_info(blue("\t#"+str(repoNumber))+bold(" "+Equo.SystemSettings['repositories']['available'][repo]['description']))
        sourcecount = 0
        for pkgrepo in Equo.SystemSettings['repositories']['available'][repo]['packages']:
            sourcecount += 1
            print_info( red("\t\t%s #%s : %s") % (_("Packages Mirror"), sourcecount, darkgreen(pkgrepo),) )
        print_info( red("\t\t%s: %s") % (_("Database URL"), darkgreen(Equo.SystemSettings['repositories']['available'][repo]['database']),))
        print_info( red("\t\t%s: %s") % (_("Repository identifier"), bold(repo),) )
        print_info( red("\t\t%s: %s") % (_("Repository database path"), blue(Equo.SystemSettings['repositories']['available'][repo]['dbpath']),) )
    return 0

def showRepositoryInfo(reponame):

    repoNumber = 0
    for repo in Equo.SystemSettings['repositories']['order']:
        repoNumber += 1
        if repo == reponame:
            break
    print_info(blue("#"+str(repoNumber))+bold(" "+Equo.SystemSettings['repositories']['available'][reponame]['description']))
    if os.path.isfile(Equo.SystemSettings['repositories']['available'][reponame]['dbpath']+"/"+etpConst['etpdatabasefile']):
        status = _("active")
    else:
        status = _("never synced")
    print_info( darkgreen("\t%s: %s") % (_("Status"), darkred(status),) )
    urlcount = 0
    for repourl in Equo.SystemSettings['repositories']['available'][reponame]['packages'][::-1]:
        urlcount += 1
        print_info( red("\t%s #%s: %s") % (_("Packages URL"), urlcount, darkgreen(repourl),) )
    print_info( red("\t%s: %s") % (_("Database URL"), darkgreen(Equo.SystemSettings['repositories']['available'][reponame]['database']),) )
    print_info( red("\t%s: %s") % (_("Repository name"), bold(reponame),) )
    print_info( red("\t%s: %s") % (_("Repository database path"), blue(Equo.SystemSettings['repositories']['available'][reponame]['dbpath']),) )
    revision = Equo.get_repository_revision(reponame)
    mhash = Equo.get_repository_db_file_checksum(reponame)
    print_info( red("\t%s: %s") % (_("Repository database checksum"), mhash,) )
    print_info( red("\t%s: %s") % (_("Repository revision"), darkgreen(str(revision)),) )

    return 0

def do_sync(reponames = [], forceUpdate = False):

    # load repository class
    try:
        repoConn = Equo.Repositories(reponames, forceUpdate)
    except PermissionDenied:
        mytxt = darkred(_("You must be either root or in the %s group.")) % (etpConst['sysgroup'],)
        print_error("\t"+mytxt)
        return 1
    except MissingParameter:
        print_error(darkred(" * ")+red("%s %s" % (_("No repositories specified in"), etpConst['repositoriesconf'],)))
        return 127
    except Exception as e:
        print_error(darkred(" @@ ")+red("%s: %s" % (_("Unhandled exception"), e,)))
        return 2

    rc = repoConn.sync()
    if not rc:
        for reponame in reponames:
            showNoticeBoardSummary(reponame)
    return rc

def check_notice_board_availability(reponame):
    def show_err():
        print_error(darkred(" @@ ")+blue("%s" % (_("Notice board not available"),) ))

    data = Equo.get_noticeboard(reponame)
    if not data:
        show_err()
        return

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

    input_params = [('idx', _('Press Enter to continue'), fake_callback, False)]
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
    input_params = [('id', blue(_('Choose one by typing its identifier')), fake_callback, False)]
    data = Equo.inputBox(title, input_params, cancel_button = True)
    if not isinstance(data, dict):
        return -1
    try:
        return int(data['id'])
    except ValueError:
        return -2

def noticeBoardReader(reponame):

    data = check_notice_board_availability(reponame)
    if not data:
        return
    counter = len(data)
    while 1:
        try:
            sel = show_notice_selector('', data)
        except KeyboardInterrupt:
            return 0
        if (sel >= 0) and (sel < counter):
            show_notice(sel, data.get(sel))
        elif sel == -1:
            return 0


def showNoticeBoardSummary(reponame):

    mytxt = "%s %s: %s" % (darkgreen(" @@ "), brown(_("Notice board")), bold(reponame),)
    print_info(mytxt)

    mydict = check_notice_board_availability(reponame)
    if not mydict:
        return

    for key in sorted(mydict):
        mydata = mydict.get(key)
        mytxt = "    [%s] [%s] %s: %s" % (
            blue(str(key)),
            brown(mydata['pubDate']),
            _("Title"),
            darkred(mydata['title']),
        )
        print_info(mytxt)
