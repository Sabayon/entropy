#!/usr/bin/python -tt
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

#    
# Authors:
#    Tim Lauridsen <tla@rasmil.dk>

from entropyConstants import *
from entropyapi import EquoConnection
import types

class PackageWrapper:
    def __init__(self, matched_atom, avail):

        if matched_atom[1] == 0:
            self.dbconn = EquoConnection.clientDbconn
        else:
            self.dbconn = EquoConnection.openRepositoryDatabase(matched_atom[1])
        self.matched_atom = matched_atom
        self.idpackage = self.matched_atom[0]
        self.repository = self.matched_atom[1]
        self.atom = self.dbconn.retrieveAtom(self.idpackage)
        self.version = self.dbconn.retrieveVersion(self.idpackage)
        self.versiontag = self.dbconn.retrieveVersionTag(self.idpackage)
        self.revision = self.dbconn.retrieveRevision(self.idpackage)
        self.pkgtuple = (self.version,self.versiontag,self.revision)
        match = self.dbconn.atomMatch(self.atom)
        if match[0] != -1:
            self.available = True
        else:
            self.available = False

    def __str__(self):
        return str(self.atom)

    def __cmp__(self, pkg):
        pkgcmp = EquoConnection.entropyTools.entropyCompareVersions(self.pkgtuple,pkg.pkgtuple)
        return pkgcmp

    def getPkg(self):
        return self.matched_atom

    def getName(self):
        return self.atom

    def getTup(self):
        return self.pkgtuple

    def getRepoId(self):
        return self.repository

    def getIdpackage(self):
        return self.idpackage

    def getVer(self):
        tag = ""
        if self.versiontag:
            tag = "#"+self.versiontag
        tag += "~"+str(self.revision)
        return self.version+tag


    def getSummaryFirst(self):
        return str(self.dbconn.getBaseData(self.idpackage))

    def getSummary(self):
        return str(self.dbconn.getScopeData(self.idpackage))

    def getDescription(self):
        return self.dbconn.retrieveDescription(self.idpackage)

    def getSize(self):
        return self.dbconn.retrieveSize(self.idpackage)

    def getSizeFmt(self):
        return EquoConnection.entropyTools.bytesIntoHuman(self.dbconn.retrieveSize(self.idpackage))


    def getArch(self):
        return etpConst['currentarch']

    def getEpoch(self):
        return self.dbconn.retrieveDateCreation(self.idpackage)

    def getRel(self):
        return self.dbconn.retrieveBranch(self.idpackage)

    def _toUTF( self, txt ):
        """ this function convert a string to unicode to make gtk happy"""
        rc=""
        if isinstance(txt,types.UnicodeType):
            return txt
        else:
            try:
                rc = unicode( txt, 'utf-8' )
            except UnicodeDecodeError, e:
                rc = unicode( txt, 'iso-8859-1' )
            return rc

    def getAttr(self,attr): # XXX
        return eval("self.dbconn.retrieve"+attr)(self.idpackage)

    def _get_time( self ):
        return self.dbconn.retrieveDateCreation(self.idpackage)

    def get_changelog( self ):
        return "No ChangeLog"

    def get_filelist( self ):
        return self.dbconn.retrieveContent(self.idpackage)

    def get_fullname( self ):
        return self.atom # XXX

    pkg =  property(fget=getPkg)
    name =  property(fget=getName)
    repoid =  property(fget=getRepoId)
    ver =  property(fget=getVer)
    version = property(fget=getVer)
    release = property(fget=getRel)
    summary =  property(fget=getSummary)
    description =  property(fget=getDescription)
    summaryFirst =  property(fget=getSummaryFirst)
    size =  property(fget=getSize)
    sizeFmt =  property(fget=getSizeFmt)
    arch = property(fget=getArch)
    epoch = property(fget=getEpoch)
    pkgtup = property(fget=getTup)