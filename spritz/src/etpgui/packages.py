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
            self.from_installed = True
        else:
            self.dbconn = EquoConnection.openRepositoryDatabase(matched_atom[1])
            self.from_installed = False
        self.matched_atom = matched_atom
        self.idpackage = self.matched_atom[0]

    def __str__(self):
        return str(self.dbconn.retrieveAtom(self.idpackage))

    def __cmp__(self, pkg):
        pkgcmp = EquoConnection.entropyTools.entropyCompareVersions(self.getTup(),pkg.getTup())
        return pkgcmp

    def getPkg(self):
        return self.matched_atom

    def getName(self):
        return self.dbconn.retrieveAtom(self.idpackage)

    def getTup(self):
        return (self.dbconn.retrieveVersion(self.idpackage),self.dbconn.retrieveVersionTag(self.idpackage),self.dbconn.retrieveRevision(self.idpackage))

    def getRepoId(self):
        if self.matched_atom[1] == 0:
            return self.dbconn.retrievePackageFromInstalledTable(self.idpackage)
        else:
            return self.matched_atom[1]

    def getIdpackage(self):
        return self.idpackage

    def getRevision(self):
        return self.dbconn.retrieveRevision(self.idpackage)

    def getVer(self):
        tag = ""
        vtag = self.dbconn.retrieveVersionTag(self.idpackage)
        if vtag:
            tag = "#"+vtag
        tag += "~"+str(self.dbconn.retrieveRevision(self.idpackage))
        return self.dbconn.retrieveVersion(self.idpackage)+tag

    def getSlot(self):
        return self.dbconn.retrieveSlot(self.idpackage)

    def getDescription(self):
        return self.dbconn.retrieveDescription(self.idpackage)

    def getDownSize(self):
        return self.dbconn.retrieveSize(self.idpackage)

    def getDiskSize(self):
        return self.dbconn.retrieveOnDiskSize(self.idpackage)

    def getIntelligentSize(self):
        if self.from_installed:
            return self.getDiskSizeFmt()
        else:
            return self.getDownSizeFmt()

    def getDownSizeFmt(self):
        return EquoConnection.entropyTools.bytesIntoHuman(self.dbconn.retrieveSize(self.idpackage))

    def getDiskSizeFmt(self):
        return EquoConnection.entropyTools.bytesIntoHuman(self.dbconn.retrieveOnDiskSize(self.idpackage))

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

    def getAttr(self,attr):
        if attr == "description":
            return self.dbconn.retrieveDescription(self.idpackage)
        elif attr == "category":
            return self.dbconn.retrieveCategory(self.idpackage)
        elif attr == "license":
            return self.dbconn.retrieveLicense(self.idpackage)
        elif attr == "creationdate":
            return self.dbconn.retrieveDateCreation(self.idpackage)
        elif attr == "version":
            return self.dbconn.retrieveVersion(self.idpackage)
        elif attr == "revision":
            return self.dbconn.retrieveRevision(self.idpackage)
        elif attr == "versiontag":
            t = self.dbconn.retrieveVersionTag(self.idpackage)
            if not t: return "None"
            return t
        elif attr == "branch":
            return self.dbconn.retrieveBranch(self.idpackage)
        elif attr == "name":
            return self.dbconn.retrieveName(self.idpackage)
        elif attr == "slot":
            return self.dbconn.retrieveSlot(self.idpackage)

    def _get_time( self ):
        return self.dbconn.retrieveDateCreation(self.idpackage)

    def get_changelog( self ):
        return "No ChangeLog"

    def get_filelist( self ):
        c = list(self.dbconn.retrieveContent(self.idpackage))
        c.sort()
        return c

    def get_fullname( self ):
        return self.dbconn.retrieveAtom(self.idpackage)

    pkg =  property(fget=getPkg)
    name =  property(fget=getName)
    repoid =  property(fget=getRepoId)
    ver =  property(fget=getVer)
    revision = property(fget=getRevision)
    version = property(fget=getVer)
    release = property(fget=getRel)
    slot = property(fget=getSlot)
    description =  property(fget=getDescription)
    size =  property(fget=getDownSize)
    intelligentsizeFmt = property(fget=getIntelligentSize)
    sizeFmt =  property(fget=getDownSizeFmt)
    disksize =  property(fget=getDiskSize)
    disksizeFmt =  property(fget=getDiskSizeFmt)
    arch = property(fget=getArch)
    epoch = property(fget=getEpoch)
    pkgtup = property(fget=getTup)