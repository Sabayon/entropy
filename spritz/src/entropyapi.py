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

#import logging

from misc import const,cleanMarkupSting
from i18n import _
from dialogs import questionDialog
#from urlgrabber.grabber import URLGrabError

# Entropy Imports
from entropyConstants import *
import entropyTools
import exceptionTools
from entropy import EquoInterface, urlFetcher

'''

   Classes reimplementation for use with a GUI

'''

class Equo(EquoInterface):

    def connect_to_gui(self, progress, progressLog):
        self.progress = progress
        self.urlFetcher = GuiUrlFetcher
        self.nocolor()
        self.progressLog = progressLog

    def updateProgress(self, text, header = "", footer = "", back = False, importance = 0, type = "info", count = [], percent = False):

        count_str = ""
        if count:
            if len(count) < 2:
                import exceptionTools
                raise exceptionTools.IncorrectParameter("IncorrectParameter: count length must be >= 2")
            count_str = " (%s/%s) " % (str(count[0]),str(count[1]),)
            self.progress.set_progress( round((float(count[0])/count[1]),1), str(int(round((float(count[0])/count[1])*100,1)))+"%" )

        myfunc = self.progress.set_extraLabel
        if importance == 1:
            myfunc = self.progress.set_subLabel
        elif importance == 2:
            myfunc = self.progress.set_mainLabel
        elif importance == 3:
            # show warning popup
            # FIXME: interface with popup !
            myfunc = self.progress.set_extraLabel
        myfunc(count_str+text)
        if not back:
            self.progressLog(count_str+text)

    def cycleDone(self):
        self.progress.total.next()


class GuiUrlFetcher(urlFetcher):
    """ hello my highness """
    
    def connect_to_gui(self, progress):
        self.progress = progress
    
    # reimplementing updateProgress
    def updateProgress(self):

        # use progress bar
        self.gather = self.downloadedsize # needed ?
        self.progress.set_progress( round(float(self.average)/100,1), str(int(round(float(self.average),1)))+"%" )
        self.progress.set_extraLabel("%s/%s kB @ %s" % (
                                        str(round(float(self.downloadedsize)/1024,1)),
                                        str(round(self.remotesize,1)),
                                        str(entropyTools.bytesIntoHuman(self.datatransfer))+"/sec",
                                    )
        )

