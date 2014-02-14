# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import sys
import argparse

from entropy.i18n import _
from entropy.output import darkred, red, brown, purple, teal, blue, \
    darkgreen, bold
from entropy.misc import ParallelTask
from entropy.const import etpConst, const_debug_write
from entropy.services.client import WebService
from entropy.client.interfaces.noticeboard import NoticeBoard

import entropy.tools

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand

class SoloUpdate(SoloCommand):
    """
    Main Solo Update command.
    """

    NAME = "update"
    ALIASES = ["up"]
    ALLOW_UNPRIVILEGED = True

    INTRODUCTION = """\
Update Entropy Repositories.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._force = False
        self._repositories = []

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloUpdate.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloUpdate.NAME))

        parser.add_argument("repo", nargs='*', default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--force", action="store_true",
                            default=self._force,
                            help=_("force update"))

        return parser

    def parse(self):
        """
        Parse command
        """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._force = nsargs.force
        self._repositories += nsargs.repo

        return self._call_exclusive, [self._update]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        import sys

        entropy_client = self._entropy_bashcomp()
        repos = entropy_client.repositories()
        outcome = ["--force"] + repos
        return self._bashcomp(sys.stdout, last_arg, outcome)

    def _update(self, entropy_client):
        """
        Command implementation.
        """
        er_txt = "%s: %s" % (
            darkred(_("You must be either root or in this group:")),
            etpConst['sysgroup'],)
        if not entropy.tools.is_user_in_entropy_group():
            entropy_client.output(
                er_txt,level="error",
                importance=1)
            return 1

        if not entropy.tools.is_root():
            rc = self._dbus_update(entropy_client)
        else:
            rc = self._normal_update(entropy_client)
        return rc

    def _dbus_update(self, entropy_client):
        """
        Execute update through RigoDaemon.
        """

        info_txt = \
            _("Sending the update request to Entropy Services")
        info_txt2 = _("Repositories will be updated in background")

        entropy_client.output(purple(info_txt))
        entropy_client.output(teal(info_txt2))

        def bail_out(err):
            entropy_client.output(
                "%s%s" % (
                    darkred(" @@ "),
                    brown(_("app-admin/rigo-daemon not installed. "
                            "Update not allowed.")),),
                level="error", importance=1)
            if err:
                entropy_client.output(
                    "%s" % (err,), level="error", importance=1)

        # try with introspection first, Gtk3.x stuff
        glib_err = None
        try:
            from gi.repository import GLib as glib
        except ImportError as err:
            glib = None
            glib_err = err

        if glib is None:
            # fallback to good old GLib, Gtk2.x style
            try:
                import glib
            except ImportError as err:
                glib = None # make things clear
                glib_err = err

        if glib is None:
            bail_out(glib_err)
            return 1

        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
        except ImportError as err:
            bail_out(err)
            return 1

        dbus_loop = DBusGMainLoop(set_as_default = True)
        loop = glib.MainLoop()
        glib.threads_init()

        _entropy_dbus_object = None
        tries = 5
        try:
            _system_bus = dbus.SystemBus(mainloop=dbus_loop)
            _entropy_dbus_object = _system_bus.get_object(
                "org.sabayon.Rigo", "/")
        except dbus.exceptions.DBusException as err:
            bail_out(err)
            return 1

        if _entropy_dbus_object is not None:

            repos = self._repositories[:]
            settings = entropy_client.Settings()
            if not repos:
                repos = list(settings['repositories']['available'].keys())

            iface = dbus.Interface(_entropy_dbus_object,
                dbus_interface = "org.sabayon.Rigo")
            accepted = False
            try:
                if repos:
                    accepted = iface.update_repositories(
                        repos, self._force)
            except dbus.exceptions.DBusException as err:
                bail_out(err)
                return 1

            if accepted:
                info_txt = _("Have a nice day")
                entropy_client.output(
                    brown(info_txt))
                return 0
            else:
                info_txt = _("Repositories update not allowed")
                entropy_client.output(
                    brown(info_txt))
                return 1

        bail_out(None)
        return 1

    def _normal_update(self, entropy_client):
        """
        Execute update from this instance.
        """
        repos = self._repositories[:]
        settings = entropy_client.Settings()
        if not repos:
            repos = list(settings['repositories']['available'].keys())

        repo_conf = settings.get_setting_files_data()['repositories']
        try:
            repo_intf = entropy_client.Repositories(
                repos, force=self._force)
        except AttributeError:
            entropy_client.output(
                "%s%s %s" % (
                    darkred(" * "),
                    purple(_("No repositories specified in")),
                    repo_conf,),
                level="error", importance=1)
            return 127

        rc = repo_intf.sync()
        if not rc:
            for repository in repos:
                self._show_notice_board_summary(
                    entropy_client, repository)
        return rc

    def _check_notice_board_availability(self, entropy_client, repository):
        """
        Determine if a NoticeBoard for the given repository is
        available.
        """
        def show_err():
            entropy_client.output(
                "%s%s" % (
                    darkred(" @@ "),
                    blue(_("Notice board not available"))),
                    level="error", importance=1)

        nb = NoticeBoard(repository)

        try:
            data = nb.data()
        except KeyError:
            data = None
            show_err()

        if not data:
            return None

        return data

    def _show_notice_board_summary(self, entropy_client, repository):
        """
        Show NoticeBoard information to user after repository update.
        """
        mytxt = "%s %s: %s" % (darkgreen(" @@ "),
            brown(_("Notice board")), bold(repository),)
        entropy_client.output(mytxt)

        mydict = self._check_notice_board_availability(
            entropy_client, repository)
        if not mydict:
            return

        for key in sorted(mydict.keys()):
            mydata = mydict.get(key)
            mytxt = "    [%s] [%s] %s: %s" % (
                blue(str(key)),
                brown(mydata['pubDate']),
                _("Title"),
                darkred(mydata['title']),
            )
            entropy_client.output(mytxt)

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloUpdate,
        SoloUpdate.NAME,
        _("update repositories"))
    )
