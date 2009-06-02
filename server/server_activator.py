#!/usr/bin/python
'''
    # DESCRIPTION:
    # activator textual interface

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

from entropy.const import *
from entropy.output import *
from entropy.server.interfaces import Server
from entropy.i18n import _
Entropy = Server(community_repo = etpConst['community']['mode'])


def sync(options, justTidy = False):

    do_noask = False
    sync_all = False
    myopts = []
    for opt in options:
        if opt == "--noask":
            do_noask = True
        elif opt == "--syncall":
            sync_all = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return 1
        else:
            myopts.append(opt)
    options = myopts

    print_info(green(" * ")+red("%s ..." % (_("Starting to sync data across mirrors (packages/database)"),) ))

    repos = [Entropy.default_repository]
    if sync_all:
        sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        repos = Entropy.SystemSettings[sys_settings_plugin_id]['server']['repositories'].keys()
        repos.sort()
    old_default = Entropy.default_repository

    for repo in repos:

        # avoid __default__
        if repo == etpConst['clientserverrepoid']:
            continue

        if repo != Entropy.default_repository:
            Entropy.switch_default_repository(repo)

        errors = False
        if not justTidy:

            mirrors_tainted, mirrors_errors, successfull_mirrors, \
                broken_mirrors, check_data = Entropy.MirrorsService.sync_packages(
                    ask = not do_noask, pretend = etpUi['pretend'])

            if mirrors_errors and not successfull_mirrors:
                errors = True
                print_error(darkred(" !!! ")+red(_("Aborting !")))
                continue

            if not successfull_mirrors:
                continue
            elif not mirrors_errors:
                if mirrors_tainted:
                    if (not do_noask) and etpConst['rss-feed']:
                        Entropy.rssMessages['commitmessage'] = readtext(">> %s: " % (_("Please insert a commit message"),) )
                    elif etpConst['rss-feed']:
                        Entropy.rssMessages['commitmessage'] = "Autodriven Update"
                errors, fine, broken = sync_remote_databases()
                if not errors:
                    Entropy.MirrorsService.lock_mirrors(lock = False)
                if not errors and not do_noask:
                    rc = Entropy.askQuestion(_("Should I continue with the tidy procedure ?"))
                    if rc == "No":
                        continue
                elif errors:
                    print_error(darkred(" !!! ")+red(_("Aborting !")))
                    continue

        if not errors:
            Entropy.MirrorsService.tidy_mirrors(ask = not do_noask, pretend = etpUi['pretend'])

    if old_default != Entropy.default_repository:
        Entropy.switch_default_repository(old_default)

    return 0


def packages(options):

    sync_all = False
    do_pkg_check = False
    for opt in options:
        if opt == "--do-packages-check":
            do_pkg_check = True
        elif opt == "--syncall":
            sync_all = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return

    if not options:
        return

    if options[0] == "sync":

        repos = [Entropy.default_repository]
        if sync_all:
            sys_settings_plugin_id = \
                etpConst['system_settings_plugins_ids']['server_plugin']
            repos = Entropy.SystemSettings[sys_settings_plugin_id]['server']['repositories'].keys()
            repos.sort()
        old_default = Entropy.default_repository

        for repo in repos:

            # avoid __default__
            if repo == etpConst['clientserverrepoid']:
                continue

            if repo != Entropy.default_repository:
                Entropy.switch_default_repository(repo)

            Entropy.MirrorsService.sync_packages(    ask = etpUi['ask'],
                                                            pretend = etpUi['pretend'],
                                                            packages_check = do_pkg_check
                                                    )
        if old_default != Entropy.default_repository:
            Entropy.switch_default_repository(old_default)

    return 0

def notice(options):

    if not options:
        return

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
        data = Entropy.inputBox('', input_params, cancel_button = True)
        return


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
        input_params = [('id',blue(_('Choose one by typing its identifier')),fake_callback,False)]
        data = Entropy.inputBox(title, input_params, cancel_button = True)
        if not isinstance(data,dict):
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
            ('title',_('Title'),fake_callback,False),
            ('text',_('Notice text'),fake_callback,False),
            ('url',_('Relevant URL (optional)'),fake_callback_tr,False),
        ]

        data = Entropy.inputBox(blue("%s") % (_("Repository notice board, new item insertion"),), input_params, cancel_button = True)
        if data == None: return 0
        status = Entropy.MirrorsService.update_notice_board(title = data['title'], notice_text = data['text'], link = data['url'])
        if status:
            return 0
        return 1

    if options[0] == "read":

        data = Entropy.MirrorsService.read_notice_board()
        if data == None:
            print_error(darkred(" * ")+blue("%s" % (_("Notice board not available"),) ))
            return 1
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

    if options[0] == "remove":

        data = Entropy.MirrorsService.read_notice_board()
        if data == None:
            print_error(darkred(" * ")+blue("%s" % (_("Notice board not available"),) ))
            return 1
        items, counter = data
        changed = False
        while 1:
            try:
                sel = show_notice_selector(darkgreen(_("Choose the one you want to remove")), items)
            except KeyboardInterrupt:
                break
            if (sel >= 0) and (sel <= counter):
                show_notice(sel, items.get(sel))
                rc = Entropy.askQuestion(_("Are you sure you want to remove this?"))
                if rc == "Yes":
                    changed = True
                    Entropy.MirrorsService.remove_from_notice_board(sel)
                    data = Entropy.MirrorsService.read_notice_board(do_download = False)
                    items, counter = data
            elif sel == -1:
                break

        if changed:
            status = Entropy.MirrorsService.upload_notice_board()
            if not status:
                return 1
        return 0

    return 0

def database(options):

    cmd = options[0]
    sync_all = False
    for opt in options:
        if opt == "--syncall":
            sync_all = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return

    if cmd == "lock":

        print_info(green(" * ")+green("%s ..." % (_("Starting to lock mirrors databases"),) ))
        rc = Entropy.MirrorsService.lock_mirrors(lock = True)
        if rc:
            print_info(green(" * ")+red("%s !" % (_("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Databases lock complete")))
        return rc

    elif cmd == "unlock":

        print_info(green(" * ")+green("%s ..." % (_("Starting to unlock mirrors databases"),)))
        rc = Entropy.MirrorsService.lock_mirrors(lock = False)
        if rc:
            print_info(green(" * ")+green("%s !" % (_("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Databases unlock complete")))
        return rc

    elif cmd == "download-lock":

        print_info(green(" * ")+green("%s ..." % (_("Starting to lock download mirrors databases"),) ))
        rc = Entropy.MirrorsService.lock_mirrors_for_download(lock = True)
        if rc:
            print_info(green(" * ")+green("%s !" % (_("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Download mirrors lock complete")))
        return rc

    elif cmd == "download-unlock":

        print_info(green(" * ")+green("%s ..." % (_("Starting to unlock download mirrors databases"),) ))
        rc = Entropy.MirrorsService.lock_mirrors_for_download(lock = False)
        if rc:
            print_info(green(" * ")+green("%s ..." % (_("A problem occured on at least one mirror"),) ))
        else:
            print_info(green(" * ")+green(_("Download mirrors unlock complete")))
        return rc

    elif cmd == "lock-status":

        print_info(brown(" * ")+green("%s:" % (_("Mirrors status table"),) ))
        dbstatus = Entropy.MirrorsService.get_mirrors_lock()
        for db in dbstatus:
            if (db[1]):
                db[1] = red(_("Locked"))
            else:
                db[1] = green(_("Unlocked"))
            if (db[2]):
                db[2] = red(_("Locked"))
            else:
                db[2] = green(_("Unlocked"))
            print_info(bold("\t"+Entropy.entropyTools.extract_ftp_host_from_uri(db[0])+": ")+red("[")+brown("%s: " % (_("DATABASE"),) )+db[1]+red("] [")+brown("%s: " % (_("DOWNLOAD"),) )+db[2]+red("]"))
        return 0

    elif cmd == "sync":

        repos = [Entropy.default_repository]
        if sync_all:
            sys_settings_plugin_id = \
                etpConst['system_settings_plugins_ids']['server_plugin']
            repos = Entropy.SystemSettings[sys_settings_plugin_id]['server']['repositories'].keys()
            repos.sort()
        old_default = Entropy.default_repository

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
                print_error(darkred(" !!! ")+green(_("Database sync errors, cannot continue.")))
                problems = 1

        if old_default != Entropy.default_repository:
            Entropy.switch_default_repository(old_default)

        return problems


def sync_remote_databases(noUpload = False, justStats = False):

    remoteDbsStatus = Entropy.MirrorsService.get_remote_databases_status()
    print_info(green(" * ")+red("%s:" % (_("Remote Entropy Database Repository Status"),) ))
    for dbstat in remoteDbsStatus:
        print_info(green("\t %s:\t" % (_("Host"),) )+bold(Entropy.entropyTools.extract_ftp_host_from_uri(dbstat[0])))
        print_info(red("\t  * %s: " % (_("Database revision"),) )+blue(str(dbstat[1])))

    local_revision = Entropy.get_local_database_revision()
    print_info(red("\t  * %s: " % (_("Database local revision currently at"),) )+blue(str(local_revision)))

    if justStats:
        return 0,set(),set()

    # do the rest
    errors, fine_uris, broken_uris = Entropy.MirrorsService.sync_databases(no_upload = noUpload)
    remote_status = Entropy.MirrorsService.get_remote_databases_status()
    print_info(darkgreen(" * ")+red("%s:" % (_("Remote Entropy Database Repository Status"),) ))
    for dbstat in remote_status:
        print_info(darkgreen("\t %s:\t" % (_("Host"),) )+bold(Entropy.entropyTools.extract_ftp_host_from_uri(dbstat[0])))
        print_info(red("\t  * %s: " % (_("Database revision"),) )+blue(str(dbstat[1])))

    return errors, fine_uris, broken_uris
