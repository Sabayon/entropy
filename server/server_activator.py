# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server}.

"""
import os
import tempfile
import subprocess
from entropy.const import etpConst, etpUi
from entropy.output import red, green, print_info, bold, darkgreen, blue, \
    darkred, brown, print_error, readtext, print_generic
from entropy.server.interfaces import Server
from entropy.server.interfaces.rss import ServerRssMetadata
from entropy.transceivers import EntropyTransceiver
from entropy.i18n import _
Entropy = Server(community_repo = etpConst['community']['mode'])

DEFAULT_REPO_COMMIT_MSG = """
# This is Entropy Server repository commit message handler.
# Please friggin' enter the commit message for your changes. Lines starting
# with '#' will be ignored. To avoid encoding issue, write stuff in plain ASCII.
"""

def sync(options, just_tidy = False):

    do_noask = False
    sync_all = False
    myopts = []
    for opt in options:
        if opt == "--noask":
            do_noask = True
        elif opt == "--syncall":
            sync_all = True
        elif opt.startswith("--"):
            return -10
        else:
            myopts.append(opt)
    options = myopts

    print_info(green(" * ")+red("%s ..." % (
        _("Starting to sync data across mirrors (packages/database)"),) ))

    old_default = Entropy.default_repository

    sys_settings_plugin_id = \
        etpConst['system_settings_plugins_ids']['server_plugin']
    srv_data = Entropy.Settings()[sys_settings_plugin_id]['server']

    repos = [Entropy.default_repository]
    if sync_all:
        repos = sorted(srv_data['repositories'].keys())

    rss_enabled = srv_data['rss']['enabled']

    rc = 0
    for repo in repos:

        # avoid __default__
        if repo == etpConst['clientserverrepoid']:
            continue

        if repo != Entropy.default_repository:
            Entropy.switch_default_repository(repo)

        errors = False
        if not just_tidy:

            mirrors_tainted, mirrors_errors, successfull_mirrors, \
                broken_mirrors, check_data = Entropy.Mirrors.sync_packages(
                    ask = not do_noask, pretend = etpUi['pretend'])

            if mirrors_errors and not successfull_mirrors:
                errors = True
                print_error(darkred(" !!! ")+red(_("Aborting !")))
                continue

            if not successfull_mirrors:
                continue

            if mirrors_tainted:

                if (not do_noask) and rss_enabled:
                    tmp_fd, tmp_commit_path = tempfile.mkstemp()
                    os.close(tmp_fd)
                    with open(tmp_commit_path, "w") as tmp_f:
                        tmp_f.write(DEFAULT_REPO_COMMIT_MSG)
                        if successfull_mirrors:
                            tmp_f.write("# Changes to be committed:\n")
                        for sf_mirror in sorted(successfull_mirrors):
                            tmp_f.write("#\t updated:   %s\n" % (sf_mirror,))

                    # spawn editor
                    editor = os.getenv('EDITOR', '/bin/nano')
                    cm_msg_rc = subprocess.call([editor, tmp_commit_path])
                    if cm_msg_rc:
                        # wtf?, fallback to old way
                        ServerRssMetadata()['commitmessage'] = \
                            readtext(">> %s: " % (
                                _("Please insert a commit message"),) )
                    else:
                        commit_msg = ''
                        with open(tmp_commit_path, "r") as tmp_f:
                            for line in tmp_f.readlines():
                                if line.strip().startswith("#"):
                                    continue
                                commit_msg += line
                        print_generic(commit_msg)
                        ServerRssMetadata()['commitmessage'] = commit_msg

                elif rss_enabled:
                    ServerRssMetadata()['commitmessage'] = "Autodriven Update"

            errors, fine, broken = sync_remote_databases()
            if not errors:
                Entropy.Mirrors.lock_mirrors(lock = False)
            if not errors and not do_noask:
                q_rc = Entropy.ask_question(
                    _("Should I continue with the tidy procedure ?"))
                if q_rc == _("No"):
                    continue
            elif errors:
                print_error(darkred(" !!! ")+red(_("Aborting !")))
                continue

        if not errors:
            Entropy.Mirrors.tidy_mirrors(ask = not do_noask,
                pretend = etpUi['pretend'])
        else:
            rc = 1

    if old_default != Entropy.default_repository:
        Entropy.switch_default_repository(old_default)

    return rc


def packages(options):

    sync_all = False
    do_pkg_check = False
    for opt in options:
        if opt == "--do-packages-check":
            do_pkg_check = True
        elif opt == "--syncall":
            sync_all = True
        elif opt.startswith("--"):
            return -10

    if not options:
        return -10

    if options[0] == "sync":

        repos = [Entropy.default_repository]
        old_default = Entropy.default_repository
        if sync_all:
            sys_settings_plugin_id = \
                etpConst['system_settings_plugins_ids']['server_plugin']
            srv_data = Entropy.Settings()[sys_settings_plugin_id]['server']
            repos = sorted(srv_data['repositories'].keys())

        rc = 0
        for repo in repos:

            # avoid __default__
            if repo == etpConst['clientserverrepoid']:
                continue

            if repo != Entropy.default_repository:
                Entropy.switch_default_repository(repo)

            mirrors_tainted, mirrors_errors, successfull_mirrors, \
            broken_mirrors, check_data = Entropy.Mirrors.sync_packages(
                ask = etpUi['ask'],
                pretend = etpUi['pretend'],
                packages_check = do_pkg_check)

            if mirrors_errors:
                rc = 1

        if old_default != Entropy.default_repository:
            Entropy.switch_default_repository(old_default)

        return rc

    return -10

def notice(options):

    if not options:
        return -10

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
        data = Entropy.input_box('', input_params, cancel_button = True)


    def show_notice_selector(title, mydict):
        print_info('')
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

        print_info('')
        mytxt = "[%s] %s" % (
            blue("-1"),
            darkred(_("Exit/Commit")),
        )
        print_info(mytxt)

        def fake_callback(s):
            return s
        input_params = [('id', blue(_('Choose one by typing its identifier')), fake_callback, False)]
        data = Entropy.input_box(title, input_params, cancel_button = True)
        if not isinstance(data, dict):
            return -1
        try:
            return int(data['id'])
        except ValueError:
            return -2

    if options[0] == "add":

        def fake_callback(s):
            return s

        def fake_callback_tr(s):
            return True

        input_params = [
            ('title', _('Title'), fake_callback, False),
            ('text', _('Notice text'), fake_callback, False),
            ('url', _('Relevant URL (optional)'), fake_callback_tr, False),
        ]

        data = Entropy.input_box(blue("%s") % (_("Repository notice board, new item insertion"),), input_params, cancel_button = True)
        if data is None:
            return 0
        status = Entropy.Mirrors.update_notice_board(title = data['title'], notice_text = data['text'], link = data['url'])
        if status:
            return 0
        return 1

    elif options[0] == "read":

        data = Entropy.Mirrors.read_notice_board()
        if data is None:
            print_error(darkred(" * ")+blue("%s" % (_("Notice board not available"),) ))
            return 1
        items, counter = data
        while True:
            try:
                sel = show_notice_selector('', items)
            except KeyboardInterrupt:
                return 0
            if (sel >= 0) and (sel <= counter):
                show_notice(sel, items.get(sel))
            elif sel == -1:
                return 0

        return 0

    elif options[0] == "remove":

        data = Entropy.Mirrors.read_notice_board()
        if data is None:
            print_error(darkred(" * ")+blue("%s" % (_("Notice board not available"),) ))
            return 1
        items, counter = data
        changed = False
        while True:
            try:
                sel = show_notice_selector(darkgreen(_("Choose the one you want to remove")), items)
            except KeyboardInterrupt:
                break
            if (sel >= 0) and (sel <= counter):
                show_notice(sel, items.get(sel))
                q_rc = Entropy.ask_question(
                    _("Are you sure you want to remove this?"))
                if q_rc == _("Yes"):
                    changed = True
                    Entropy.Mirrors.remove_from_notice_board(sel)
                    data = Entropy.Mirrors.read_notice_board(do_download = False)
                    items, counter = data
            elif sel == -1:
                break

        if changed or (counter == 0):
            if counter == 0:
                status = Entropy.Mirrors.remove_notice_board()
            else:
                status = Entropy.Mirrors.upload_notice_board()
            if not status:
                return 1
        return 0

    return -10

def repo(options):

    cmd = options[0]
    sync_all = False
    for opt in options:
        if opt == "--syncall":
            sync_all = True
        elif opt.startswith("--"):
            return -10

    if cmd == "lock":

        print_info(green(" * ")+green("%s ..." % (
            _("Starting to lock mirrors databases"),) ))
        rc = Entropy.Mirrors.lock_mirrors(lock = True)
        if rc:
            print_info(green(" * ")+red("%s !" % (
                _("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Databases lock complete")))
        return rc

    elif cmd == "unlock":

        print_info(green(" * ")+green("%s ..." % (
            _("Starting to unlock mirrors databases"),)))
        rc = Entropy.Mirrors.lock_mirrors(lock = False)
        if rc:
            print_info(green(" * ")+green("%s !" % (
                _("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(
                _("Databases unlock complete")))
        return rc

    elif cmd == "download-lock":

        print_info(green(" * ")+green("%s ..." % (
            _("Starting to lock download mirrors databases"),) ))
        rc = Entropy.Mirrors.lock_mirrors_for_download(lock = True)
        if rc:
            print_info(green(" * ")+green("%s !" % (
                _("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Download mirrors lock complete")))
        return rc

    elif cmd == "download-unlock":

        print_info(green(" * ")+green("%s ..." % (
            _("Starting to unlock download mirrors databases"),) ))
        rc = Entropy.Mirrors.lock_mirrors_for_download(lock = False)
        if rc:
            print_info(green(" * ")+green("%s ..." % (
                _("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Download mirrors unlock complete")))
        return rc

    elif cmd == "lock-status":

        print_info(brown(" * ")+green("%s:" % (_("Mirrors status table"),) ))
        dbstatus = Entropy.Mirrors._get_mirrors_lock()
        for db in dbstatus:
            if (db[1]):
                db[1] = red(_("Locked"))
            else:
                db[1] = green(_("Unlocked"))
            if (db[2]):
                db[2] = red(_("Locked"))
            else:
                db[2] = green(_("Unlocked"))
            host = EntropyTransceiver.get_uri_name(db[0])
            print_info(bold("\t"+host+": ") + red("[") + \
                brown("%s: " % (_("DATABASE"),) ) + db[1] + red("] [") + \
                brown("%s: " % (_("DOWNLOAD"),) ) + db[2] + red("]"))
        return 0

    elif cmd == "sync":

        repos = [Entropy.default_repository]
        old_default = Entropy.default_repository
        if sync_all:
            sys_settings_plugin_id = \
                etpConst['system_settings_plugins_ids']['server_plugin']
            srv_data = Entropy.Settings()[sys_settings_plugin_id]['server']
            repos = sorted(srv_data['repositories'].keys())

        problems = 0
        for repo in repos:

            # avoid __default__
            if repo == etpConst['clientserverrepoid']:
                continue

            if repo != Entropy.default_repository:
                Entropy.switch_default_repository(repo)

            print_info(green(" * ")+red("%s ..." % (_("Syncing databases"),) ))
            errors, fine, broken = sync_remote_databases()
            if errors:
                print_error(darkred(" !!! ") + \
                    green(_("Database sync errors, cannot continue.")))
                problems = 1

        if old_default != Entropy.default_repository:
            Entropy.switch_default_repository(old_default)

        return problems

    return -10


def sync_remote_databases():

    remote_db_status = Entropy.Mirrors.get_remote_repositories_status()
    print_info(green(" * ")+red("%s:" % (
        _("Remote Entropy Database Repository Status"),) ))

    for dbstat in remote_db_status:
        host = EntropyTransceiver.get_uri_name(dbstat[0])
        print_info(green("    %s: " % (_("Host"),) )+bold(host))
        print_info(red("     * %s: " % (_("Database revision"),) ) + \
            blue(str(dbstat[1])))

    local_revision = Entropy.get_local_repository_revision()
    print_info(red("      * %s: " % (
        _("Database local revision currently at"),) ) + \
            blue(str(local_revision)))

    # do the rest
    errors, fine_uris, broken_uris = Entropy.Mirrors.sync_repositories(
        conf_files_qa_test = False)
    remote_status = Entropy.Mirrors.get_remote_repositories_status()
    print_info(darkgreen(" * ")+red("%s:" % (
        _("Remote Entropy Database Repository Status"),) ))
    for dbstat in remote_status:
        host = EntropyTransceiver.get_uri_name(dbstat[0])
        print_info(darkgreen("    %s: " % (_("Host"),) )+bold(host))
        print_info(red("      * %s: " % (_("Database revision"),) ) + \
            blue(str(dbstat[1])))

    return errors, fine_uris, broken_uris
