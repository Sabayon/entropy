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
    darkred, brown, purple, teal, print_error, print_warning, readtext, \
        print_generic
from entropy.server.interfaces import Server
from entropy.server.interfaces.rss import ServerRssMetadata
from entropy.transceivers import EntropyTransceiver
from entropy.i18n import _

from text_tools import acquire_entropy_locks, release_entropy_locks

def get_entropy_server():
    """
    Return Entropy Server interface object.
    """
    return Server(community_repo = etpConst['community']['mode'])

DEFAULT_REPO_COMMIT_MSG = """
# This is Entropy Server repository commit message handler.
# Please friggin' enter the commit message for your changes. Lines starting
# with '#' will be ignored. To avoid encoding issue, write stuff in plain ASCII.
"""

def sync(options, just_tidy = False):
    acquired = False
    server = None
    try:
        server = get_entropy_server()
        acquired = acquire_entropy_locks(server)
        if not acquired:
            print_error(darkgreen(_("Another Entropy is currently running.")))
            return 1
        return _sync(server, options, just_tidy)
    finally:
        if server is not None:
            if acquired:
                release_entropy_locks(server)
            server.shutdown()

def _sync(entropy_server, options, just_tidy):

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

    repository_id = entropy_server.repository()
    sys_settings_plugin_id = \
        etpConst['system_settings_plugins_ids']['server_plugin']
    srv_data = entropy_server.Settings()[sys_settings_plugin_id]['server']
    rss_enabled = srv_data['rss']['enabled']
    repos = [repository_id]
    if sync_all:
        repos = entropy_server.repositories()

    rc = 0
    for repo in repos:

        # avoid __default__
        if repo == etpConst['clientserverrepoid']:
            continue

        errors = False
        if not just_tidy:

            mirrors_tainted, mirrors_errors, successfull_mirrors, \
                broken_mirrors, check_data = \
                    entropy_server.Mirrors.sync_packages(
                        repo, ask = not do_noask, pretend = etpUi['pretend'])

            if mirrors_errors and not successfull_mirrors:
                errors = True
                print_error(darkred(" !!! ")+red(_("Aborting !")))
                continue

            if not successfull_mirrors:
                continue

            if mirrors_tainted:

                if (not do_noask) and rss_enabled:
                    tmp_fd, tmp_commit_path = tempfile.mkstemp()
                    with os.fdopen(tmp_fd, "w") as tmp_f:
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

            sts = _sync_remote_databases(entropy_server, repo)
            if sts == 0:
                entropy_server.Mirrors.lock_mirrors(repo, False)
            if (sts == 0) and not do_noask:
                q_rc = entropy_server.ask_question(
                    _("Should I continue with the tidy procedure ?"))
                if q_rc == _("No"):
                    continue
            elif sts != 0:
                errors = True
                print_error(darkred(" !!! ")+red(_("Aborting !")))
                continue

        if not errors:
            entropy_server.Mirrors.tidy_mirrors(repo, ask = not do_noask,
                pretend = etpUi['pretend'])
        else:
            rc = 1

    return rc

def packages(options):
    acquired = False
    server = None
    try:
        server = get_entropy_server()
        acquired = acquire_entropy_locks(server)
        if not acquired:
            print_error(darkgreen(_("Another Entropy is currently running.")))
            return 1
        return _packages(server, options)
    finally:
        if server is not None:
            if acquired:
                release_entropy_locks(server)
            server.shutdown()

def _packages(entropy_server, options):

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

    repository_id = entropy_server.repository()

    if options[0] == "sync":

        repos = [repository_id]
        if sync_all:
            repos = entropy_server.repositories()

        rc = 0
        for repo in repos:

            # avoid __default__
            if repo == etpConst['clientserverrepoid']:
                continue

            mirrors_tainted, mirrors_errors, successfull_mirrors, \
            broken_mirrors, check_data = entropy_server.Mirrors.sync_packages(
                repo, ask = etpUi['ask'],
                pretend = etpUi['pretend'],
                packages_check = do_pkg_check)

            if mirrors_errors:
                rc = 1

        return rc

    return -10

def notice(options):
    acquired = False
    server = None
    try:
        server = get_entropy_server()
        acquired = acquire_entropy_locks(server)
        if not acquired:
            print_error(darkgreen(_("Another Entropy is currently running.")))
            return 1
        return _notice(server, options)
    finally:
        if server is not None:
            if acquired:
                release_entropy_locks(server)
            server.shutdown()

def _notice(entropy_server, options):

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
        data = entropy_server.input_box('', input_params, cancel_button = True)


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
        input_params = [('id', blue(_('Choose one by typing its identifier')),
            fake_callback, False)]
        data = entropy_server.input_box(title, input_params,
            cancel_button = True)
        if not isinstance(data, dict):
            return -1
        try:
            return int(data['id'])
        except ValueError:
            return -2

    repository_id = entropy_server.repository()

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

        data = entropy_server.input_box(blue("%s") % (
            _("Repository notice board, new item insertion"),),
                input_params, cancel_button = True)
        if data is None:
            return 0
        status = entropy_server.Mirrors.update_notice_board(
            repository_id, data['title'], data['text'],
            link = data['url'])
        if status:
            return 0
        return 1

    elif options[0] == "read":

        data = entropy_server.Mirrors.read_notice_board(repository_id)
        if data is None:
            print_error(darkred(" * ")+blue("%s" % (
                _("Notice board not available"),) ))
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

        data = entropy_server.Mirrors.read_notice_board(repository_id)
        if data is None:
            print_error(darkred(" * ")+blue("%s" % (
                _("Notice board not available"),) ))
            return 1
        items, counter = data
        changed = False
        while True:
            try:
                sel = show_notice_selector(
                    darkgreen(_("Choose the one you want to remove")), items)
            except KeyboardInterrupt:
                break
            if (sel >= 0) and (sel <= counter):
                show_notice(sel, items.get(sel))
                q_rc = entropy_server.ask_question(
                    _("Are you sure you want to remove this?"))
                if q_rc == _("Yes"):
                    changed = True
                    entropy_server.Mirrors.remove_from_notice_board(
                        repository_id, sel)
                    data = entropy_server.Mirrors.read_notice_board(
                        repository_id, do_download = False)
                    items, counter = data
            elif sel == -1:
                break

        if changed or (counter == 0):
            if counter == 0:
                status = entropy_server.Mirrors.remove_notice_board(
                    repository_id)
            else:
                status = entropy_server.Mirrors.upload_notice_board(
                    repository_id)
            if not status:
                return 1
        return 0

    return -10

def repo(options):
    acquired = False
    server = None
    try:
        server = get_entropy_server()
        acquired = acquire_entropy_locks(server)
        if not acquired:
            print_error(darkgreen(_("Another Entropy is currently running.")))
            return 1
        return _repo(server, options)
    finally:
        if server is not None:
            if acquired:
                release_entropy_locks(server)
            server.shutdown()

def _repo(entropy_server, options):

    if not options:
        return -10

    cmd, args = options[0], options[1:]

    repository_id = entropy_server.repository()

    if cmd == "lock":

        print_info(green(" * ")+green("%s ..." % (
            _("Starting to lock mirrors databases"),) ))
        done = entropy_server.Mirrors.lock_mirrors(repository_id, True)
        rc = 0
        if not done:
            rc = 1
            print_info(green(" * ")+red("%s !" % (
                _("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Repositories lock complete")))
        return rc

    elif cmd == "unlock":

        print_info(green(" * ")+green("%s ..." % (
            _("Starting to unlock mirrors databases"),)))
        done = entropy_server.Mirrors.lock_mirrors(repository_id, False)
        rc = 0
        if not done:
            rc = 1
            print_info(green(" * ")+green("%s !" % (
                _("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(
                _("Repositories unlock complete")))
        return rc

    elif cmd == "download-lock":

        print_info(green(" * ")+green("%s ..." % (
            _("Starting to lock download mirrors databases"),) ))
        done = entropy_server.Mirrors.lock_mirrors_for_download(
            repository_id, True)
        rc = 0
        if not done:
            rc = 1
            print_info(green(" * ")+green("%s !" % (
                _("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Download mirrors lock complete")))
        return rc

    elif cmd == "download-unlock":

        print_info(green(" * ")+green("%s ..." % (
            _("Starting to unlock download mirrors databases"),) ))
        done = entropy_server.Mirrors.lock_mirrors_for_download(repository_id,
            False)
        rc = 0
        if not done:
            rc = 1
            print_info(green(" * ")+green("%s ..." % (
                _("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Download mirrors unlock complete")))
        return rc

    elif cmd == "lock-status":

        print_info(brown(" * ")+green("%s:" % (_("Mirrors status table"),) ))
        dbstatus = entropy_server.Mirrors.mirrors_status(repository_id)
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

        repos = [repository_id]
        if "--syncall" in args:
            repos = entropy_server.repositories()

        rc = 0
        for repo in repos:

            # avoid __default__
            if repo == etpConst['clientserverrepoid']:
                continue

            print_info(green(" * ")+red("%s ..." % (_("Syncing repositories"),) ))
            sts = _sync_remote_databases(entropy_server, repo)
            if sts != 0:
                print_error(darkred(" !!! ") + \
                    green(_("Repositories sync error, cannot continue.")))
                rc = 1

        return rc

    elif cmd == "vacuum":

        days = 0
        for arg in args:
            if arg.startswith("--days="):
                s_days = arg[len("--days="):]
                try:
                    days = int(s_days)
                    if days < 0:
                        raise ValueError()
                except ValueError:
                    return -10
                break
            else:
                return -10

        print_info(green(" * ")+darkgreen("%s ..." % (
            _("Cleaning unavailable packages from repository"),) ))
        print_warning(teal(" * ") + \
            purple(_("Removing unavailable packages, overriding Entropy defaults is generally bad.")))
        print_warning(teal(" * ") + \
            purple(_("Users with outdated repositories, won't be able to find package files remotely.")))
        sts = entropy_server.Mirrors.tidy_mirrors(repository_id, ask = True,
            pretend = etpUi['pretend'], expiration_days = days)
        if sts:
            return 0
        return 1

    return -10

def sync_remote_databases():
    acquired = False
    server = None
    try:
        server = get_entropy_server()
        acquired = acquire_entropy_locks(server)
        if not acquired:
            print_error(darkgreen(_("Another Entropy is currently running.")))
            return 1
        return _sync_remote_databases(server, server.repository())
    finally:
        if server is not None:
            if acquired:
                release_entropy_locks(server)
            server.shutdown()

def _sync_remote_databases(entropy_server, repository_id):

    print_info(green(" * ")+red("%s:" % (
        _("Remote Entropy Repository Status"),) ))
    remote_db_status = entropy_server.Mirrors.remote_repository_status(
        repository_id)
    for url, revision in remote_db_status.items():
        host = EntropyTransceiver.get_uri_name(url)
        print_info(green("    %s: " % (_("Host"),) )+bold(host))
        print_info(red("     * %s: " % (_("Revision"),) ) + \
            blue(str(revision)))

    local_revision = entropy_server.local_repository_revision(repository_id)
    print_info(red("      * %s: " % (
        _("Local revision currently at"),) ) + \
            blue(str(local_revision)))

    # do the rest
    sts = entropy_server.Mirrors.sync_repository(repository_id)

    print_info(darkgreen(" * ")+red("%s:" % (
        _("Remote Entropy Repository Status"),) ))
    remote_status = entropy_server.Mirrors.remote_repository_status(
        repository_id)
    for url, revision in remote_status.items():
        host = EntropyTransceiver.get_uri_name(url)
        print_info(darkgreen("    %s: " % (_("Host"),) )+bold(host))
        print_info(red("      * %s: " % (_("Revision"),) ) + \
            blue(str(revision)))

    return sts
