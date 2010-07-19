# -*- coding: utf-8 -*-
#    Sulfur (Entropy Interface)
#    Copyright: (C) 2007-2009 Fabio Erculiani < lxnay<AT>sabayonlinux<DOT>org >
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import gtk
import sys
import time
import thread
from sulfur.setup import const, SulfurConf
from sulfur.dialogs import LicenseDialog, okDialog, choiceDialog, inputDialog
import gobject

# Entropy Imports
from entropy.const import etpConst, etpUi
from entropy.output import print_generic, nocolor, decolorize
from entropy.client.interfaces import Client
from entropy.fetchers import UrlFetcher
from entropy.i18n import _
from entropy.misc import ParallelTask
from entropy.client.mirrors import StatusInterface
from entropy.exceptions import RepositoryError
from entropy.db.exceptions import OperationalError, IntegrityError

import entropy.tools

class QueueExecutor:

    def __init__(self, SulfurApplication):
        self.Sulfur = SulfurApplication
        self._entropy = Equo()
        self.__on_lic_request = False
        self.__on_lic_rc = None
        # clear download mirrors status
        StatusInterface().clear()

    def handle_licenses(self, queue):

        ### Before even starting the fetch, make sure
        ### that the user accepts their licenses
        licenses = self._entropy.get_licenses_to_accept(queue)
        if licenses:

            self.__on_lic_request = True
            def do_handle():
                dialog = LicenseDialog(self.Sulfur, self._entropy, licenses)
                accept = dialog.run()
                dialog.destroy()
                self.__on_lic_rc = accept, licenses
                self.__on_lic_request = False
                return False
            gobject.timeout_add(0, do_handle)
            while self.__on_lic_request:
                time.sleep(0.2)
            return self.__on_lic_rc

        return 0, licenses

    def ok_dialog(self, msg):
        def do_dialog():
            okDialog(self.Sulfur.ui.main, msg)
            return False
        gobject.timeout_add(0, do_dialog)

    def run(self, install_queue, removal_queue, do_purge_cache = [],
        fetch_only = False, download_sources = False, selected_by_user = None):

        """
        return statuses:
        0 = no errors
        1 = install/removal error
        2 = license massk error
        3 = license not accepted
        """

        if selected_by_user is None:
            selected_by_user = set()

        # unmask packages
        if (not fetch_only) and (not download_sources):
            for match in self.Sulfur.etpbase.unmaskingPackages:
                result = self._entropy.unmask_package(match)
                if not result or self._entropy.is_package_masked(match):
                    dbconn = self._entropy.open_repository(match[1])
                    atom = dbconn.retrieveAtom(match[0])
                    self.ok_dialog("%s: %s" % (
                        _("Error enabling masked package"), atom))
                    return 2

        removalQueue = []
        runQueue = install_queue
        conflicts_queue = []
        if (not fetch_only) and (not download_sources):
            runQueue, conflicts_queue, status = self._entropy.get_install_queue(
                install_queue, False, False,
                relaxed = (SulfurConf.relaxed_deps == 1)
            )
        if removal_queue:
            removalQueue += [(x, False) for x in removal_queue if x \
                not in conflicts_queue]

        rc, licenses = self.handle_licenses(runQueue)
        if rc != 0:
            return 3

        for lic in licenses:
            self._entropy.installed_repository().acceptLicense(lic)

        def do_skip_show():
            self.Sulfur.skipMirrorNow = False
            self.Sulfur.ui.skipMirror.show()
            self.Sulfur.ui.abortQueue.show()
            return False
        gobject.timeout_add(0, do_skip_show)

        fetch_action = "fetch"
        fetch_string = "%s: " % (_("Fetching"),)
        if download_sources:
            fetch_string = "%s: " % (_("Downloading sources"),)
            fetch_action = "source"

        totalqueue = len(runQueue)
        steps_here = 2
        if fetch_only or download_sources:
            steps_here = 1

        total_steps = (totalqueue*steps_here)+len(removalQueue)
        steps_counter = total_steps
        progress_step_count = 0

        mykeys = {}
        # manually handle progress
        old_prog_state = GuiUrlFetcher.get_progress_bar_enable()
        GuiUrlFetcher.enable_progress_bar(False)

        try:
            for pkg_info in runQueue:

                self.Sulfur.queue_bombing()

                progress_step_count += 1
                self._entropy.set_progress(float(progress_step_count)/total_steps)

                pkg = self._entropy.Package()
                metaopts = {}
                metaopts['fetch_abort_function'] = self.Sulfur.mirror_bombing
                pkg.prepare(pkg_info, fetch_action, metaopts)

                myrepo = pkg.pkgmeta['repository']
                if myrepo not in mykeys:
                    mykeys[myrepo] = set()
                mykeys[myrepo].add(
                    entropy.tools.dep_getkey(pkg.pkgmeta['atom']))

                self._entropy.output(
                    fetch_string+pkg.pkgmeta['atom'],
                    importance = 2,
                    count = (progress_step_count, total_steps)
                )
                rc = pkg.run()
                if rc != 0:
                    return 1
                pkg.kill()
                del pkg

            if not download_sources:
                def spawn_ugc():
                    try:
                        if self._entropy.UGC != None:
                            for myrepo in mykeys:
                                mypkgkeys = sorted(mykeys[myrepo])
                                self._entropy.UGC.add_download_stats(myrepo,
                                    mypkgkeys)
                    except:
                        pass
                spawn_ugc()

            def do_skip_hide():
                self.Sulfur.ui.skipMirror.hide()
                return False
            gobject.timeout_add(0, do_skip_hide)

            if fetch_only or download_sources:
                return 0

            # then removalQueue
            # NOT conflicts! :-)
            for rem_data in removalQueue:

                self.Sulfur.queue_bombing()

                idpackage = rem_data[0]
                progress_step_count += 1
                self._entropy.set_progress(float(progress_step_count)/total_steps)

                metaopts = {}
                metaopts['removeconfig'] = rem_data[1]
                if idpackage in do_purge_cache:
                    metaopts['removeconfig'] = True
                pkg = self._entropy.Package()
                pkg.prepare((idpackage,), "remove", metaopts)

                self._entropy.output(
                    "%s: %s" % (
                        _("Removing package"),
                        pkg.pkgmeta['removeatom'],
                    ),
                    importance = 2,
                    count = (progress_step_count, total_steps)
                )

                if 'remove_installed_vanished' not in pkg.pkgmeta:
                    self._entropy.output(
                        "%s: " % (_("Removing"),) + pkg.pkgmeta['removeatom'],
                        importance = 2,
                        count = (progress_step_count, total_steps)
                    )

                    rc = pkg.run()
                    if rc != 0:
                        return 1

                    pkg.kill()

                del metaopts
                del pkg

            def do_skip_one_show():
                self.Sulfur.skipMirrorNow = False
                self.Sulfur.ui.skipMirror.show()
                return False

            gobject.timeout_add(0, do_skip_one_show)

            for pkg_info in runQueue:

                progress_step_count += 1
                self._entropy.set_progress(float(progress_step_count)/total_steps)
                self.Sulfur.queue_bombing()

                metaopts = {}
                metaopts['fetch_abort_function'] = self.Sulfur.mirror_bombing
                metaopts['removeconfig'] = False

                if pkg_info in selected_by_user:
                    metaopts['install_source'] = \
                        etpConst['install_sources']['user']
                else:
                    metaopts['install_source'] = \
                        etpConst['install_sources']['automatic_dependency']

                pkg = self._entropy.Package()
                pkg.prepare(pkg_info, "install", metaopts)

                self._entropy.output(
                    "%s: %s" % (_("Installing"), pkg.pkgmeta['atom'],),
                    importance = 2,
                    count = (progress_step_count, total_steps)
                )

                rc = pkg.run()
                if rc != 0:
                    return 1

                pkg.kill()
                del metaopts
                del pkg

            def do_skip_hide_again():
                self.Sulfur.ui.skipMirror.hide()
                self.Sulfur.ui.abortQueue.hide()
                return False
            gobject.timeout_add(0, do_skip_hide_again)

        finally:
            GuiUrlFetcher.enable_progress_bar(old_prog_state)

        return 0


class Equo(Client):

    def init_singleton(self, *args, **kwargs):
        self.progress = None
        self.progress_log = None
        self.std_output = None
        self.urlFetcher = None
        Client.init_singleton(self, *args, **kwargs)
        self._progress_divider = 1
        self.xcache = True # force xcache enabling
        if etpUi['debug']:
            self.UGC.quiet = False
        self._mthread_rc = {
            'ask_question': {},
            'input_box': {},
        }

    def connect_to_gui(self, application):
        self.progress = application.progress
        GuiUrlFetcher.progress = application.progress
        self.urlFetcher = GuiUrlFetcher
        self.progress_log = application.progress_log_write
        self.std_output = application.std_output
        self.ui = application.ui

    def get_category_description(self, category):

        data = {}
        for repo in self._enabled_repos:
            try:
                dbconn = self.open_repository(repo)
            except RepositoryError:
                continue
            try:
                data = dbconn.retrieveCategoryDescription(category)
            except (OperationalError, IntegrityError,):
                continue
            if data:
                break

        return data

    def set_progress(self, frac, text = None):
        if text is None:
            text = str(int(frac * 100)) + "%"
        self.progress.set_progress(frac, text = text)

    def output(self, text, header = "", footer = "", back = False,
            importance = 0, level = "info", count = [], percent = False):

        count_str = ""
        if self.progress:

            if count:
                count_str = "(%s/%s) " % (str(count[0]), str(count[1]),)
                cur_prog = float(count[0])/count[1]
                if importance == 0:
                    progress_text = decolorize(text)
                else:
                    progress_text = str(int(cur_prog * 100)) + "%"
                self.progress.set_progress(cur_prog, progress_text)

            if importance < 1:
                myfunc = self.progress.set_extraLabel
            elif importance == 1:
                myfunc = self.progress.set_subLabel
            elif importance > 1:
                myfunc = self.progress.set_mainLabel
            myfunc(count_str+decolorize(text))

        if not back and hasattr(self, 'progress_log'):

            def update_gui():
                if hasattr(self.progress_log, '__call__'):
                    self.progress_log(header+count_str+text+footer)
                return False
            gobject.timeout_add(0, update_gui)

        elif not back:
            print_generic(count_str+text)

    def ask_question(self, question, importance = 0, responses = None,
        parent = None, from_myself = False):

        if responses is None:
            responses = (_("Yes"), _("No"),)

        if parent is None:
            try:
                parent = self.ui.main
            except AttributeError:
                parent = None

        th_id = thread.get_ident()

        def do_ask():
            choice = choiceDialog(parent, decolorize(question),
                _("Entropy needs your attention"),
                [_(x) for x in responses]
            )
            try:
                result = responses[choice]
            except IndexError:
                result = responses[0]
            self._mthread_rc['ask_question'][th_id] = result

        gobject.idle_add(do_ask)
        while th_id not in self._mthread_rc['ask_question']:
            while gtk.events_pending(): # otherwise it won't work
                gtk.main_iteration()
            time.sleep(0.4)
        return self._mthread_rc['ask_question'].pop(th_id)

    def input_box(self, title, input_parameters, cancel_button = True,
        parent = None):

        if parent is None:
            try:
                parent = self.ui.main
            except AttributeError:
                parent = None

        th_id = thread.get_ident()

        def do_ask():
            result = inputDialog(parent, decolorize(title), input_parameters,
                cancel = cancel_button)
            self._mthread_rc['input_box'][th_id] = result

        gobject.idle_add(do_ask)
        while th_id not in self._mthread_rc['input_box']:
            while gtk.events_pending(): # otherwise it won't work
                gtk.main_iteration()
            time.sleep(0.4)
        return self._mthread_rc['input_box'].pop(th_id)

# in this way, any singleton class that tries to directly load Client
# gets Equo in change
Client.__singleton_class__ = Equo

class GuiUrlFetcher(UrlFetcher):

    gui_last_avg = 0
    _default_divider = 1
    _use_progress_bar = True
    progress = None

    @staticmethod
    def enable_progress_bar(enable):
        GuiUrlFetcher._use_progress_bar = enable

    @staticmethod
    def get_progress_bar_enable():
        return GuiUrlFetcher._use_progress_bar

    def handle_statistics(self, th_id, downloaded_size, total_size,
            average, old_average, update_step, show_speed, data_transfer,
            time_remaining, time_remaining_secs):
        self.__average = average
        self.__downloadedsize = downloaded_size
        self.__remotesize = total_size
        self.__datatransfer = data_transfer

    def output(self):

        if self.progress == None:
            return

        myavg = abs(int(round(float(self.__average), 1)))
        if abs((myavg - GuiUrlFetcher.gui_last_avg)) < 1:
            return

        if (myavg > GuiUrlFetcher.gui_last_avg) or (myavg < 2) or (myavg > 97):

            if GuiUrlFetcher._use_progress_bar:
                cur_prog = float(self.__average)/100
                cur_prog_str = str(int(self.__average))
                self.progress.set_progress(cur_prog, cur_prog_str+"%")

            human_dt = entropy.tools.bytes_into_human(self.__datatransfer)
            self.progress.set_extraLabel("%s/%s kB @ %s" % (
                    str(round(float(self.__downloadedsize)/1024, 1)),
                    str(round(self.__remotesize, 1)),
                    str(human_dt) + "/sec",
                )
            )
            GuiUrlFetcher.gui_last_avg = myavg
