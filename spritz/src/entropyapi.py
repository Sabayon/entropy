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
from clientConstants import *
import entropyTools
import repositoriesTools
import remoteTools
import cacheTools
import equoTools
Equo = equoTools.Equo()

'''

   Classes reimplementation for use with a GUI

'''

class GuiUrlFetcher(remoteTools.urlFetcher):
    """ hello my highness """
    
    def connectProgressObject(self, progress, item):
        self.progress = progress
        self.item = item
    
    # reimplementing updateProgress
    def updateProgress(self):

        # create progress bar
        self.gather = self.downloadedsize # needed ?
        self.progress.set_progress( round(float(self.average)/100,1), str(int(round(float(self.average),1)))+"%" )
        self.progress.set_extraLabel("%s/%s kB @ %s" % (
                                        str(round(float(self.downloadedsize)/1024,1)),
                                        str(round(self.remotesize,1)),
                                        str(entropyTools.bytesIntoHuman(self.datatransfer))+"/sec",
                                    )
        )

class GuiRepositoryController(repositoriesTools.repositoryController):
    """ hello world """

    def connectProgressObject(self, progress):
        self.progress = progress

    # reimplementing
    def downloadItem(self, item, repo, cmethod = None):

        self.validateRepositoryId(repo)
        url, filepath = self.constructPaths(item, repo, cmethod)

        fetchConn = GuiUrlFetcher(url, filepath)
        fetchConn.connectProgressObject(self.progress, item)
	rc = fetchConn.download()
        if rc in ("-1","-2","-3"):
            del fetchConn
            return False
        del fetchConn
        return True

class GuiCacheHelper(cacheTools.cacheHelper):
    """ ich liebe dich """
    
    def connectProgressObject(self, progress):
        self.progress = progress

    def updateProgress(self, text, back = False, importance = 0, type = "info", count = []):

        if importance == 0:
            if count:
                percent = float(count[0])/count[1]
                self.progress.set_progress( round(percent,1), text)
        elif importance == 1:
            self.progress.set_subLabel(text)
        else:
            self.progress.set_mainLabel(text)

        if count and importance > 0:
            percent = float(count[0])/count[1]
            self.progress.set_progress( round(percent,1), str(int(round(percent*100,1)))+"%")
        #else:
           # bouncing! 
