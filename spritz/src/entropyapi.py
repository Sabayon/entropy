#!/usr/bin/python -tt
# -*- coding: iso-8859-1 -*-
#    Yum Exteder (yumex) - A GUI for yum
#    Copyright (C) 2006 Tim Lauridsen < tim<AT>yum-extender<DOT>org > 
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
from spritz_setup import const
from dialogs import questionDialog, LicenseDialog, okDialog, choiceDialog, inputDialog

# Entropy Imports
from entropyConstants import *
import exceptionTools
from entropy import EquoInterface, urlFetcher
from entropy_i18n import _

'''

   Classes reimplementation for use with a GUI

'''

class QueueExecutor:

    def __init__(self, SpritzApplication):
        self.Spritz = SpritzApplication
        self.Entropy = SpritzApplication.Equo

    def handle_licenses(self, queue):

        ### Before even starting the fetch, make sure that the user accepts their licenses
        licenses = self.Entropy.get_licenses_to_accept(queue)
        if licenses:
            gtk.gdk.threads_enter()
            try:
                dialog = LicenseDialog(self.Spritz, self.Entropy, licenses)
                accept = dialog.run()
                dialog.destroy()
                return accept,licenses
            finally:
                gtk.gdk.threads_leave()
        else:
            return 0,licenses

    def run(self, install_queue, removal_queue, do_purge_cache = [], fetch_only = False, download_sources = False):

        # unmask packages
        for match in self.Spritz.etpbase.unmaskingPackages:
            result = self.Entropy.unmask_match(match)
            if not result or self.Entropy.is_match_masked(match):
                dbconn = self.Entropy.openRepositoryDatabase(match[1])
                atom = dbconn.retrieveAtom(match[0])
                okDialog( self.Spritz.ui.main, "%s: %s" % (_("Error enabling masked package"),atom) )
                return -2,1

        removalQueue = []
        runQueue = []
        conflicts_queue = []
        if install_queue:
            runQueue, conflicts_queue, status = self.Entropy.retrieveInstallQueue(install_queue,False,False)
        if removal_queue:
            removalQueue += [(x,False) for x in removal_queue if x not in conflicts_queue]

        # XXX handle for eva too, move db configuration to LicenseDialog and forget
        rc, licenses = self.handle_licenses(runQueue)
        if rc != 0:
            return 0,0

        for lic in licenses:
            self.Entropy.clientDbconn.acceptLicense(lic)

        totalqueue = len(runQueue)
        steps_here = 2
        if fetch_only: steps_here = 1
        progress_step = float(1)/((totalqueue*steps_here)+len(removalQueue))
        step = progress_step
        myrange = []
        while progress_step < 1.0:
            myrange.append(step)
            progress_step += step
        myrange.append(step)
        self.Entropy.progress.total.setup( myrange )

        self.Spritz.skipMirrorNow = False
        self.Spritz.ui.skipMirror.show()
        self.Spritz.ui.abortQueue.show()
        # first fetch all
        fetchqueue = 0
        mykeys = {}

        fetch_action = "fetch"
        fetch_string = "%s: " % (_("Fetching"),)
        if download_sources:
            fetch_string = "%s: " % (_("Downloading sources"),)
            fetch_action = "source"

        for packageInfo in runQueue:

            self.Spritz.queue_bombing()

            fetchqueue += 1
            Package = self.Entropy.Package()
            metaopts = {}
            metaopts['fetch_abort_function'] = self.Spritz.mirror_bombing
            Package.prepare(packageInfo,fetch_action,metaopts)

            myrepo = Package.infoDict['repository']
            if not mykeys.has_key(myrepo):
                mykeys[myrepo] = set()
            mykeys[myrepo].add(self.Entropy.entropyTools.dep_getkey(Package.infoDict['atom']))

            self.Entropy.updateProgress(
                fetch_string+Package.infoDict['atom'],
                importance = 2,
                count = (fetchqueue,totalqueue)
            )
            rc = Package.run()
            if rc != 0:
                return -1,rc
            Package.kill()
            del Package
            self.Entropy.cycleDone()

        def spawn_ugc():
            try:
                if self.Entropy.UGC != None:
                    for myrepo in mykeys:
                        mypkgkeys = list(mykeys[myrepo])
                        self.Entropy.UGC.add_downloads(myrepo, mypkgkeys)
            except:
                pass
        if not download_sources:
            t = self.Entropy.entropyTools.parallelTask(spawn_ugc)
            t.start()

        self.Spritz.ui.skipMirror.hide()

        if fetch_only or download_sources:
            return 0,0

        # then removalQueue
        # NOT conflicts! :-)
        totalremovalqueue = len(removalQueue)
        currentremovalqueue = 0
        for rem_data in removalQueue:

            self.Spritz.queue_bombing()

            idpackage = rem_data[0]
            currentremovalqueue += 1

            metaopts = {}
            metaopts['removeconfig'] = rem_data[1]
            if idpackage in do_purge_cache:
                metaopts['removeconfig'] = True
            Package = self.Entropy.Package()
            Package.prepare((idpackage,),"remove", metaopts)

            if not Package.infoDict.has_key('remove_installed_vanished'):
                self.Entropy.updateProgress(
                    "Removing: "+Package.infoDict['removeatom'],
                    importance = 2,
                    count = (currentremovalqueue,totalremovalqueue)
                )

                rc = Package.run()
                if rc != 0:
                    return -1,rc

                Package.kill()

            self.Entropy.cycleDone()
            del metaopts
            del Package

        self.Spritz.skipMirrorNow = False
        self.Spritz.ui.skipMirror.show()
        totalqueue = len(runQueue)
        currentqueue = 0
        for packageInfo in runQueue:
            currentqueue += 1

            self.Spritz.queue_bombing()

            metaopts = {}
            metaopts['fetch_abort_function'] = self.Spritz.mirror_bombing
            metaopts['removeconfig'] = False
            Package = self.Entropy.Package()
            Package.prepare(packageInfo,"install", metaopts)

            self.Entropy.updateProgress(
                "Installing: "+Package.infoDict['atom'],
                importance = 2,
                count = (currentqueue,totalqueue)
            )

            rc = Package.run()
            if rc != 0:
                return -1,rc

            Package.kill()
            self.Entropy.cycleDone()
            del metaopts
            del Package

        self.Spritz.ui.skipMirror.hide()
        self.Spritz.ui.abortQueue.hide()

        return 0,0


class Equo(EquoInterface):

    def __init__(self, *args, **kwargs):
        self.progressLog = None
        self.output = None
        self.progress = None
        self.urlFetcher = None
        EquoInterface.__init__(self, *args, **kwargs)
        self.xcache = True # force xcache enabling
        if "--debug" in sys.argv:
            self.UGC.quiet = False

    def connect_to_gui(self, spritz_app):
        self.progress = spritz_app.progress
        self.urlFetcher = GuiUrlFetcher
        self.nocolor()
        self.progressLog = spritz_app.progressLogWrite
        self.output = spritz_app.output
        self.ui = spritz_app.ui

    def updateProgress(self, text, header = "", footer = "", back = False, importance = 0, type = "info", count = [], percent = False):

        count_str = ""
        if self.progress:
            if count:
                count_str = "(%s/%s) " % (str(count[0]),str(count[1]),)
                if importance == 0:
                    progress_text = text
                else:
                    progress_text = str(int(round((float(count[0])/count[1])*100,1)))+"%"
                self.progress.set_progress( round((float(count[0])/count[1]),1), progress_text )
            if importance == 1:
                myfunc = self.progress.set_subLabel
            elif importance == 2:
                myfunc = self.progress.set_mainLabel
            elif importance == 3:
                # show warning popup
                # FIXME: interface with popup !
                myfunc = self.progress.set_extraLabel
            if importance > 0:
                myfunc(count_str+text)

        if not back and self.progressLog:
            if callable(self.progressLog):
                self.progressLog(count_str+text)
        elif not back:
            print count_str+text

    def cycleDone(self):
        self.progress.total.next()

    def setTotalCycles(self, total):
        self.progress.total.setup( range(total) )

    # @input question: question to do
    #
    # @input importance:
    #           values: 0,1,2 (latter is a blocker - popup menu on a GUI env)
    #           used to specify information importance, 0<important<2
    #
    # @input responses:
    #           list of options whose users can choose between
    #
    # feel free to reimplement this
    def askQuestion(self, question, importance = 0, responses = ["Yes","No"]):

        try:
            parent = self.ui.main
        except AttributeError:
            parent = None

        choice = choiceDialog(parent, question, _("Entropy needs your attention"), responses)
        try:
            return responses[choice]
        except IndexError:
            return responses[0]

    # @ title: title of the input box
    # @ input_parameters: [('identifier 1','input text 1',input_verification_callback,False), ('password','Password',input_verification_callback,True)]
    # @ cancel_button: show cancel button ?
    # @ output: dictionary as follows:
    #   {'identifier 1': result, 'identifier 2': result}
    def inputBox(self, title, input_parameters, cancel_button = True):
        try:
            parent = self.ui.main
        except AttributeError:
            parent = None
        return inputDialog(parent, title, input_parameters, cancel = cancel_button)

class GuiUrlFetcher(urlFetcher):

    gui_last_avg = 100

    def connect_to_gui(self, progress):
        self.progress = progress

    # reimplementing updateProgress
    def updateProgress(self):

        if self.progress == None: return

        myavg = abs(int(round(float(self.average),1)))
        if abs((myavg - self.gui_last_avg)) < 1: return

        if (myavg > self.gui_last_avg) or (myavg < 2) or (myavg > 97):

            self.progress.set_progress( round(float(self.average)/100,1), str(myavg)+"%" )
            self.progress.set_extraLabel("%s/%s kB @ %s" % (
                                            str(round(float(self.downloadedsize)/1024,1)),
                                            str(round(self.remotesize,1)),
                                            str(self.entropyTools.bytesIntoHuman(self.datatransfer))+"/sec",
                                        )
            )
            self.gui_last_avg = myavg


EquoConnection = Equo(url_fetcher = GuiUrlFetcher)
