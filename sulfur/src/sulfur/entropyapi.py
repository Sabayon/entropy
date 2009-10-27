#!/usr/bin/python2 -O
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
from sulfur.setup import const
from sulfur.dialogs import LicenseDialog, okDialog, choiceDialog, inputDialog
import gobject

# Entropy Imports
from entropy.const import etpConst
from entropy.output import print_generic
from entropy.client.interfaces import Client as EquoInterface
from entropy.transceivers import UrlFetcher
from entropy.i18n import _
from entropy.misc import ParallelTask

class QueueExecutor:

    def __init__(self, SulfurApplication):
        self.Sulfur = SulfurApplication
        self.Entropy = SulfurApplication.Equo
        self.__on_lic_request = False
        self.__on_lic_rc = None
        # reset fetcher last average count
        GuiUrlFetcher.gui_last_avg = 0
        # clear download mirrors status
        self.Entropy.MirrorStatus.clear()

    def handle_licenses(self, queue):

        ### Before even starting the fetch, make sure
        ### that the user accepts their licenses
        licenses = self.Entropy.get_licenses_to_accept(queue)
        if licenses:

            self.__on_lic_request = True
            def do_handle():
                dialog = LicenseDialog(self.Sulfur, self.Entropy, licenses)
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

        if selected_by_user == None:
            selected_by_user = set()

        # unmask packages
        for match in self.Sulfur.etpbase.unmaskingPackages:
            result = self.Entropy.unmask_match(match)
            if not result or self.Entropy.is_match_masked(match):
                dbconn = self.Entropy.open_repository(match[1])
                atom = dbconn.retrieveAtom(match[0])
                self.ok_dialog("%s: %s" % (
                    _("Error enabling masked package"), atom))
                return 2

        removalQueue = []
        runQueue = []
        conflicts_queue = []
        if install_queue:
            runQueue, conflicts_queue, status = self.Entropy.get_install_queue(
                install_queue, False, False)
        if removal_queue:
            removalQueue += [(x, False) for x in removal_queue if x \
                not in conflicts_queue]

        rc, licenses = self.handle_licenses(runQueue)
        if rc != 0:
            return 3

        for lic in licenses:
            self.Entropy.clientDbconn.acceptLicense(lic)

        totalqueue = len(runQueue)
        steps_here = 2
        if fetch_only:
            steps_here = 1
        progress_step = float(1)/((totalqueue*steps_here)+len(removalQueue))
        step = progress_step
        myrange = []
        while progress_step < 1.0:
            myrange.append(step)
            progress_step += step
        myrange.append(step)

        def do_total_setup():
            self.Entropy.progress.total.setup( myrange )
            return False
        gobject.timeout_add(0, do_total_setup)


        def do_skip_show():
            self.Sulfur.skipMirrorNow = False
            self.Sulfur.ui.skipMirror.show()
            self.Sulfur.ui.abortQueue.show()
            return False
        gobject.timeout_add(0, do_skip_show)

        # first fetch all
        fetchqueue = 0
        mykeys = {}

        fetch_action = "fetch"
        fetch_string = "%s: " % (_("Fetching"),)
        if download_sources:
            fetch_string = "%s: " % (_("Downloading sources"),)
            fetch_action = "source"

        for packageInfo in runQueue:

            self.Sulfur.queue_bombing()

            fetchqueue += 1
            Package = self.Entropy.Package()
            metaopts = {}
            metaopts['fetch_abort_function'] = self.Sulfur.mirror_bombing
            Package.prepare(packageInfo, fetch_action, metaopts)

            myrepo = Package.pkgmeta['repository']
            if myrepo not in mykeys:
                mykeys[myrepo] = set()
            mykeys[myrepo].add(self.Entropy.entropyTools.dep_getkey(
                Package.pkgmeta['atom']))

            self.Entropy.updateProgress(
                fetch_string+Package.pkgmeta['atom'],
                importance = 2,
                count = (fetchqueue, totalqueue)
            )
            rc = Package.run()
            if rc != 0:
                return 1
            Package.kill()
            del Package
            self.Entropy.cycleDone()

        if not download_sources:
            def spawn_ugc():
                try:
                    if self.Entropy.UGC != None:
                        for myrepo in mykeys:
                            mypkgkeys = sorted(mykeys[myrepo])
                            self.Entropy.UGC.add_download_stats(myrepo,
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
        totalremovalqueue = len(removalQueue)
        currentremovalqueue = 0
        for rem_data in removalQueue:

            self.Sulfur.queue_bombing()

            idpackage = rem_data[0]
            currentremovalqueue += 1

            metaopts = {}
            metaopts['removeconfig'] = rem_data[1]
            if idpackage in do_purge_cache:
                metaopts['removeconfig'] = True
            Package = self.Entropy.Package()
            Package.prepare((idpackage,), "remove", metaopts)

            if 'remove_installed_vanished' not in Package.pkgmeta:
                self.Entropy.updateProgress(
                    "Removing: "+Package.pkgmeta['removeatom'],
                    importance = 2,
                    count = (currentremovalqueue, totalremovalqueue)
                )

                rc = Package.run()
                if rc != 0:
                    return 1

                Package.kill()

            self.Entropy.cycleDone()
            del metaopts
            del Package

        def do_skip_one_show():
            self.Sulfur.skipMirrorNow = False
            self.Sulfur.ui.skipMirror.show()
            return False

        gobject.timeout_add(0, do_skip_one_show)

        totalqueue = len(runQueue)
        currentqueue = 0
        for packageInfo in runQueue:
            currentqueue += 1

            self.Sulfur.queue_bombing()

            metaopts = {}
            metaopts['fetch_abort_function'] = self.Sulfur.mirror_bombing
            metaopts['removeconfig'] = False

            if packageInfo in selected_by_user:
                metaopts['install_source'] = etpConst['install_sources']['user']
            else:
                metaopts['install_source'] = \
                    etpConst['install_sources']['automatic_dependency']

            Package = self.Entropy.Package()
            Package.prepare(packageInfo, "install", metaopts)

            self.Entropy.updateProgress(
                "Installing: "+Package.pkgmeta['atom'],
                importance = 2,
                count = (currentqueue, totalqueue)
            )

            rc = Package.run()
            if rc != 0:
                return 1

            Package.kill()
            self.Entropy.cycleDone()
            del metaopts
            del Package

        def do_skip_hide_again():
            self.Sulfur.ui.skipMirror.hide()
            self.Sulfur.ui.abortQueue.hide()
            return False
        gobject.timeout_add(0, do_skip_hide_again)

        return 0


class Equo(EquoInterface):

    def init_singleton(self, *args, **kwargs):
        EquoInterface.init_singleton(self, *args, **kwargs)
        self.progress_log = None
        self.output = None
        self.progress = None
        self.urlFetcher = None
        self.xcache = True # force xcache enabling
        if "--debug" in sys.argv:
            self.UGC.quiet = False

    def connect_to_gui(self, application):
        self.progress = application.progress
        self.urlFetcher = GuiUrlFetcher
        self.nocolor()
        self.progress_log = application.progress_log_write
        self.output = application.output
        self.ui = application.ui

    def updateProgress(self, text, header = "", footer = "", back = False,
            importance = 0, type = "info", count = [], percent = False):

        count_str = ""
        if self.progress:
            if count:
                count_str = "(%s/%s) " % (str(count[0]), str(count[1]),)
                if importance == 0:
                    progress_text = text
                else:
                    percent_int = int(round((float(count[0])/count[1])*100, 1))
                    progress_text = str(percent_int) + "%"
                self.progress.set_progress(
                    round((float(count[0])/count[1]), 1), progress_text )
            if importance == 1:
                myfunc = self.progress.set_subLabel
            elif importance == 2:
                myfunc = self.progress.set_mainLabel
            elif importance == 3:
                myfunc = self.progress.set_extraLabel
            if importance > 0:
                myfunc(count_str+text)

        if not back and hasattr(self, 'progress_log'):

            def update_gui():
                if hasattr(self.progress_log, '__call__'):
                    self.progress_log(count_str+text)
                return False
            gobject.timeout_add(0, update_gui)

        elif not back:
            print_generic(count_str+text)

    def cycleDone(self):
        def update_gui():
            next(self.progress.total)
            return False
        gobject.timeout_add(0, update_gui)

    def setTotalCycles(self, total):
        def update_gui():
            self.progress.total.setup( list(range(total)) )
            return False
        gobject.timeout_add(0, update_gui)

    def askQuestion(self, question, importance = 0, responses = None,
        parent = None):

        if responses is None:
            responses = (_("Yes"), _("No"),)

        if parent is None:
            try:
                parent = self.ui.main
            except AttributeError:
                parent = None

        choice = choiceDialog(parent, question,
            _("Entropy needs your attention"), [_(x) for x in responses])
        try:
            return responses[choice]
        except IndexError:
            return responses[0]

    def inputBox(self, title, input_parameters, cancel_button = True,
        parent = None):
        # @ title: title of the input box
        # @ input_parameters: [('identifier 1','input text 1',
        #       input_verification_callback,False),
        #       ('password','Password',input_verification_callback,True)]
        # @ cancel_button: show cancel button ?
        # @ output: dictionary as follows:
        #   {'identifier 1': result, 'identifier 2': result}
        if parent is None:
            try:
                parent = self.ui.main
            except AttributeError:
                parent = None
        return inputDialog(parent, title, input_parameters,
            cancel = cancel_button)

class GuiUrlFetcher(UrlFetcher):

    gui_last_avg = 0

    def connect_to_gui(self, progress):
        self.progress = progress
        self.__average = 0
        self.__downloadedsize = 0
        self.__remotesize = 0
        self.__datatransfer = 0

    def handle_statistics(self, th_id, downloaded_size, total_size,
            average, old_average, update_step, show_speed, data_transfer,
            time_remaining, time_remaining_secs):
        self.__average = average
        self.__downloadedsize = downloaded_size
        self.__remotesize = total_size
        self.__datatransfer = data_transfer

    def updateProgress(self):

        if self.progress == None:
            return

        myavg = abs(int(round(float(self.__average), 1)))
        if abs((myavg - GuiUrlFetcher.gui_last_avg)) < 1:
            return

        if (myavg > GuiUrlFetcher.gui_last_avg) or (myavg < 2) or (myavg > 97):

            self.progress.set_progress(round(float(self.__average)/100, 1),
                str(myavg)+"%")
            human_dt = self.entropyTools.bytes_into_human(self.__datatransfer)
            self.progress.set_extraLabel("%s/%s kB @ %s" % (
                    str(round(float(self.__downloadedsize)/1024, 1)),
                    str(round(self.__remotesize, 1)),
                    str(human_dt) + "/sec",
                )
            )
            GuiUrlFetcher.gui_last_avg = myavg
