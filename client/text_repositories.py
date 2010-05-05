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
from entropy.exceptions import TimeoutError
from entropy.const import etpConst, etpUi
from entropy.output import red, darkred, blue, brown, bold, darkgreen, green, \
    print_info, print_warning, print_error, purple, teal
from entropy.core.settings.base import SystemSettings as SysSet
from entropy.i18n import _
from text_tools import print_table
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

        elif options[0] == "repo":

            er_txt = darkred(_("You must be root"))
            if not entropy.tools.is_root():
                print_error(er_txt)
                return 1

            myopts = options[1:]
            if not myopts:
                rc = -10
            else:
                repo_opt = myopts.pop(0)
                if not myopts:
                    rc = -10
                elif repo_opt == "enable":
                    rc = _enable_repositories(entropy_client, myopts)
                elif repo_opt == "disable":
                    rc = _disable_repositories(entropy_client, myopts)
                elif repo_opt == "add":
                    rc = _add_repository(entropy_client, myopts)
                elif repo_opt == "remove":
                    rc = _remove_repository(entropy_client, myopts)
                else:
                    rc = -10

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
        entropy_client.shutdown()

    return rc

def _add_repository(entropy_client, repo_strings):

    current_branch = SystemSettings['repositories']['branch']
    current_product = SystemSettings['repositories']['product']
    available_repos = SystemSettings['repositories']['available']

    for repo_string in repo_strings:
        if not repo_string:
            print_warning("[%s] %s" % (
                purple(repo_string), blue(_("invalid data, skipping")),))
            continue
        if not ((repo_string.startswith("repository|")) and \
            (len(repo_string.split("|")) == 5)):
            print_warning("[%s] %s" % (
                purple(repo_string),
                blue(_("invalid repository string, skipping")),)
            )
            continue

        print_info("%s: %s" % (
            teal(_("Adding repository string")), blue(repo_string),))

        repoid, repodata = SystemSettings._analyze_client_repo_string(
            repo_string, current_branch, current_product)

        # print some info
        toc = []
        toc.append((purple(_("Repository id:")), teal(repoid)))
        toc.append((darkgreen(_("Description:")), teal(repodata['description'])))
        toc.append((purple(_("Repository format:")), darkgreen(repodata['dbcformat'])))
        toc.append((brown(_("Service port:")), teal(str(repodata['service_port']))))
        toc.append((brown(_("Service port (SSL):")), teal(str(repodata['ssl_service_port']))))
        for pkg_url in repodata['plain_packages']:
            toc.append((purple(_("Packages URL:")), pkg_url))
        db_url = repodata['plain_database']
        if not db_url:
            db_url = _("None given")
        toc.append((purple(_("Repository URL:")), darkgreen(db_url)))
        toc.append(" ")
        print_table(toc)
        entropy_client.add_repository(repodata)
        print_info("[%s] %s" % (
            purple(repoid), blue(_("repository added succesfully")),))

def _remove_repository(entropy_client, repo_ids):

    excluded_repos = SystemSettings['repositories']['excluded']
    available_repos = SystemSettings['repositories']['available']
    repos = set(list(excluded_repos.keys()) + list(available_repos.keys()))
    for repo_id in repo_ids:
        if repo_id not in repos:
            print_warning("[%s] %s" % (
                purple(repo_id), blue(_("repository id not available")),))
            continue

        entropy_client.remove_repository(repo_id)
        print_info("[%s] %s" % (
            purple(repo_id), blue(_("repository removed succesfully")),))

def _enable_repositories(entropy_client, repos):
    excluded_repos = SystemSettings['repositories']['excluded']
    available_repos = SystemSettings['repositories']['available']
    for repo in repos:
        if repo in available_repos:
            print_warning("[%s] %s" % (
                purple(repo), blue(_("repository already enabled")),))
            continue
        if repo not in excluded_repos:
            print_warning("[%s] %s" % (
                purple(repo), blue(_("repository not available")),))
            continue
        entropy_client.enable_repository(repo)
        print_info("[%s] %s" % (
            teal(repo), blue(_("repository enabled")),))
    return 0

def _disable_repositories(entropy_client, repos):
    excluded_repos = SystemSettings['repositories']['excluded']
    available_repos = SystemSettings['repositories']['available']
    default_repo = SystemSettings['repositories']['default_repository']
    for repo in repos:
        if repo in excluded_repos:
            print_warning("[%s] %s" % (
                purple(repo), blue(_("repository already disabled")),))
            continue
        if repo not in available_repos:
            print_warning("[%s] %s" % (
                purple(repo), blue(_("repository not available")),))
            continue
        if repo == default_repo:
            print_warning("[%s] %s" % (
                purple(repo), blue(_("cannot disable default repository")),))
            continue
        entropy_client.disable_repository(repo)
        print_info("[%s] %s" % (
            teal(repo), blue(_("repository disabled")),))
    return 0

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
        repo_identifiers = list(SystemSettings['repositories']['available'])

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
                try:
                    entropy_client.UGC.add_download_stats(reponame, [reponame])
                except TimeoutError:
                    continue

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
