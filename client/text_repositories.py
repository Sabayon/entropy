# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""

########################################################
####
##   Repositories Tools
#
import os
import sys
from entropy.const import etpConst, etpUi
from entropy.output import red, darkred, blue, brown, bold, darkgreen, green, \
    print_info, print_warning, print_error
from entropy.core.settings.base import SystemSettings as SysSet
from entropy.i18n import _
import entropy.tools
SystemSettings = SysSet()

def repositories(options):

    # Options available for all the packages submodules
    myopts = options[1:]
    e_req_force_update = False
    rc = 0
    repo_names = []

    for opt in myopts:
        if opt == "--force":
            e_req_force_update = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return -10
        elif opt in SystemSettings['repositories']['order']:
            repo_names.append(opt)

    from entropy.client.interfaces import Client
    entropy_client = Client(noclientdb = True)
    try:
        if options[0] == "update":
            # check if I am root
            er_txt = darkred(_("You must be either root or in this group:")) + \
                " " +  etpConst['sysgroup']
            if not entropy.tools.is_user_in_entropy_group():
                print_error(er_txt)
                return 1

            rc = _do_sync(entropy_client, repo_identifiers = repo_names,
                force = e_req_force_update)

        elif options[0] == "status":
            for repo in SystemSettings['repositories']['order']:
                _show_repository_info(entropy_client, repo)

        elif options[0] == "repoinfo":
            myopts = options[1:]
            if not myopts:
                rc = -10
            else:
                rc = _show_repository_file(myopts[0], myopts[1:])

        elif options[0] == "notice":
            myopts = options[1:]
            myopts = [x for x in myopts if x in \
                SystemSettings['repositories']['available']]
            if not myopts:
                rc = -10
            else:
                rc = 0
                for repoid in myopts:
                    _notice_board_reader(entropy_client, repoid)
        else:
            rc = -10
    finally:
        entropy_client.destroy()

    return rc


def _show_repository_file(myfile, repos):

    if myfile not in ["make.conf", "profile.link", "package.use", \
        "package.mask", "package.unmask", "package.keywords"]:
            return - 10

    if not repos:
        return -10

    myrepos = []
    for repo in repos:
        if repo in SystemSettings['repositories']['available']:
            myrepos.append(repo)
    if not myrepos:
        if not etpUi['quiet']:
            print_error(darkred(" * ")+darkred("%s." % (_("No valid repositories"),) ))
        return 1

    for repo in myrepos:
        mypath = os.path.join(SystemSettings['repositories']['available'][repo]['dbpath'], myfile)
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

def _show_repository_info(entropy_client, reponame):

    repo_number = 0
    for repo in SystemSettings['repositories']['order']:
        repo_number += 1
        if repo == reponame:
            break

    avail_data = SystemSettings['repositories']['available']
    repo_data = avail_data[reponame]

    print_info(blue("#"+str(repo_number))+bold(" "+repo_data['description']))
    if os.path.isfile(repo_data['dbpath']+"/"+etpConst['etpdatabasefile']):
        status = _("active")
    else:
        status = _("never synced")
    print_info( darkgreen("\t%s: %s") % (_("Status"), darkred(status),) )
    urlcount = 0

    for repourl in repo_data['packages'][::-1]:
        urlcount += 1
        print_info( red("\t%s #%s: %s") % (
            _("Packages URL"), urlcount, darkgreen(repourl),) )

    print_info( red("\t%s: %s") % (_("Database URL"),
        darkgreen(repo_data['database']),) )
    print_info( red("\t%s: %s") % (_("Repository name"), bold(reponame),) )
    print_info( red("\t%s: %s") % (_("Repository database path"),
        blue(repo_data['dbpath']),) )
    revision = entropy_client.get_repository_revision(reponame)
    print_info( red("\t%s: %s") % (_("Repository revision"),
        darkgreen(str(revision)),) )

    return 0

def _do_sync(entropy_client, repo_identifiers = None, force = False):

    if repo_identifiers is None:
        repo_identifiers = []

    # load repository class
    try:
        repo_intf = entropy_client.Repositories(repo_identifiers, force = force)
    except AttributeError:
        print_error(darkred(" * ")+red("%s %s" % (
            _("No repositories specified in"), etpConst['repositoriesconf'],)))
        return 127
    except Exception as err:
        print_error(darkred(" @@ ")+red("%s: %s" % (
            _("Unhandled exception"), err,)))
        return 2

    rc = repo_intf.sync()
    if not rc:
        for reponame in repo_identifiers:
            # inform UGC that we are syncing this repo
            if entropy_client.UGC is not None:
                entropy_client.UGC.add_download_stats(reponame, [reponame])

        for reponame in repo_identifiers:
            _show_notice_board_summary(entropy_client, reponame)

    return rc

def _check_notice_board_availability(entropy_client, reponame):

    def show_err():
        print_error(darkred(" @@ ")+blue("%s" % (
            _("Notice board not available"),) ))

    data = entropy_client.get_noticeboard(reponame)
    if not data:
        show_err()
        return

    return data

def _show_notice(entropy_client, key, mydict):

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
    entropy_client.input_box('', input_params, cancel_button = True)
    return


def _show_notice_selector(entropy_client, title, mydict):
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
    input_params = [('id',
        blue(_('Choose one by typing its identifier')), fake_callback, False)]
    data = entropy_client.input_box(title, input_params, cancel_button = True)
    if not isinstance(data, dict):
        return -1
    try:
        return int(data['id'])
    except ValueError:
        return -2

def _notice_board_reader(entropy_client, reponame):

    data = _check_notice_board_availability(entropy_client, reponame)
    if not data:
        return
    counter = len(data)
    while True:
        try:
            sel = _show_notice_selector(entropy_client, '', data)
        except KeyboardInterrupt:
            return 0
        if (sel >= 0) and (sel < counter):
            _show_notice(entropy_client, sel, data.get(sel))
        elif sel == -1:
            return 0


def _show_notice_board_summary(entropy_client, reponame):

    mytxt = "%s %s: %s" % (darkgreen(" @@ "),
        brown(_("Notice board")), bold(reponame),)
    print_info(mytxt)

    mydict = _check_notice_board_availability(entropy_client, reponame)
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
