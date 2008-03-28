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

from spritz_setup import const,cleanMarkupSting
from i18n import _
from dialogs import questionDialog,LicenseDialog

# Entropy Imports
from entropyConstants import *
import exceptionTools
from entropy import EquoInterface, urlFetcher

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
            dialog = LicenseDialog(self.Spritz.ui.main, licenses, self.Entropy)
            accept = dialog.run()
            dialog.destroy()
            return accept,licenses
        else:
            return 0,licenses

    def run(self, install_queue, removal_queue, do_purge_cache = []):
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
        progress_step = float(1)/((totalqueue*2)+len(removalQueue))
        step = progress_step
        myrange = []
        while progress_step < 1.0:
            myrange.append(step)
            progress_step += step
        myrange.append(step)
        self.Entropy.progress.total.setup( myrange )

        # first fetch all
        fetchqueue = 0
        for packageInfo in runQueue:
            fetchqueue += 1
            Package = self.Entropy.Package()
            Package.prepare(packageInfo,"fetch")
            self.Entropy.updateProgress(
                                            "Fetching: "+Package.infoDict['atom'],
                                            importance = 2,
                                            count = (fetchqueue,totalqueue)
                                        )
            rc = Package.run()
            if rc != 0:
                return -1,rc
            Package.kill()
            del Package
            self.Entropy.cycleDone()

        # then removalQueue
        # NOT conflicts! :-)
        totalremovalqueue = len(removalQueue)
        currentremovalqueue = 0
        for rem_data in removalQueue:
            idpackage = rem_data[0]
            currentremovalqueue += 1

            metaopts = {}
            metaopts['removeconfig'] = rem_data[1]
            if idpackage in do_purge_cache:
                metaopts['removeconfig'] = True
            Package = self.Entropy.Package()
            Package.prepare((idpackage,),"remove", metaopts)

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

        totalqueue = len(runQueue)
        currentqueue = 0
        for packageInfo in runQueue:
            currentqueue += 1

            metaopts = {}
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

        return 0,0


class Equo(EquoInterface):

    def __init__(self):
        EquoInterface.__init__(self)
        self.xcache = True # force xcache enabling

    def connect_to_gui(self, progress, progressLog, viewOutput):
        self.progress = progress
        self.urlFetcher = GuiUrlFetcher
        self.nocolor()
        self.progressLog = progressLog
        self.output = viewOutput

    def updateProgress(self, text, header = "", footer = "", back = False, importance = 0, type = "info", count = [], percent = False):

        count_str = ""
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
        if not back:
            self.progressLog(count_str+text)

    def cycleDone(self):
        self.progress.total.next()

    def setTotalCycles(self, total):
        self.progress.total.setup( range(total) )

class GuiUrlFetcher(urlFetcher):

    def connect_to_gui(self, progress):
        self.progress = progress

    # reimplementing updateProgress
    def updateProgress(self):

        # use progress bar
        self.progress.set_progress( round(float(self.average)/100,1), str(int(round(float(self.average),1)))+"%" )
        self.progress.set_extraLabel("%s/%s kB @ %s" % (
                                        str(round(float(self.downloadedsize)/1024,1)),
                                        str(round(self.remotesize,1)),
                                        str(self.entropyTools.bytesIntoHuman(self.datatransfer))+"/sec",
                                    )
        )


EquoConnection = Equo()
