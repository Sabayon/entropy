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

        self.from_installed = False
        if matched_atom[1] == 0:
            self.from_installed = True
        self.matched_atom = matched_atom
        self.installed_match = None
        self.available = avail
        self.do_purge = False

    def __str__(self):
        dbc = self.get_dbconn()
        return str(dbc.retrieveAtom(self.matched_atom[0])+"~"+str(dbc.retrieveRevision(self.matched_atom[0])))

    def __cmp__(self, pkg):
        n1 = str(self)
        n2 = str(pkg)
        if n1 > n2:
            return 1
        elif n1 == n2:
            return 0
        else:
            return -1

    def get_dbconn(self):
        if self.from_installed:
            return EquoConnection.clientDbconn
        else:
            return EquoConnection.openRepositoryDatabase(self.matched_atom[1])

    def getPkg(self):
        return self.matched_atom

    def getTag(self):
        dbc = self.get_dbconn()
        return dbc.retrieveVersionTag(self.matched_atom[0])

    def getName(self):
        dbc = self.get_dbconn()
        return dbc.retrieveAtom(self.matched_atom[0])

    def getNameDesc(self):
        t = self.getName()
        desc = self.getDescription()
        if len(desc) > 43:
            desc = desc[:43]+"..."
        t += "\n<small>%s</small>" % (desc,)
        return t

    def getOnlyName(self):
        dbc = self.get_dbconn()
        return dbc.retrieveName(self.matched_atom[0])

    def getTup(self):
        dbc = self.get_dbconn()
        return (    self.getName(),
                    self.getRepoId(),
                    dbc.retrieveVersion(self.matched_atom[0]),
                    dbc.retrieveVersionTag(self.matched_atom[0]),
                    dbc.retrieveRevision(self.matched_atom[0]),
        )

    def versionData(self):
        dbc = self.get_dbconn()
        return (    dbc.retrieveVersion(self.matched_atom[0]),
                    dbc.retrieveVersionTag(self.matched_atom[0]),
                    dbc.retrieveRevision(self.matched_atom[0]),
        )

    def getRepoId(self):
        if self.matched_atom[1] == 0:
            dbc = self.get_dbconn()
            return dbc.retrievePackageFromInstalledTable(self.matched_atom[0])
        else:
            return self.matched_atom[1]

    def getIdpackage(self):
        return self.matched_atom[0]

    def getRevision(self):
        dbc = self.get_dbconn()
        return dbc.retrieveRevision(self.matched_atom[0])

    def getSysPkg(self):
        if not self.from_installed:
            return False
        # check if it's a system package
        s = EquoConnection.validatePackageRemoval(self.matched_atom[0])
        return not s

    # 0: from installed db, so it's installed for sure
    # 1: not installed
    # 2: updatable
    # 3: already updated to the latest
    def getInstallStatus(self):
        if self.from_installed:
            return 0
        dbc = self.get_dbconn()
        key, slot = dbc.retrieveKeySlot(self.matched_atom[0])
        matches = EquoConnection.clientDbconn.searchKeySlot(key,slot)
        if not matches: # not installed, new!
            return 1
        else:
            rc, matched = EquoConnection.check_package_update(key+":"+slot, deep = True)
            if rc:
                return 2
            else:
                return 3

    def getVer(self):
        dbc = self.get_dbconn()
        tag = ""
        vtag = dbc.retrieveVersionTag(self.matched_atom[0])
        if vtag:
            tag = "#"+vtag
        tag += "~"+str(dbc.retrieveRevision(self.matched_atom[0]))
        return dbc.retrieveVersion(self.matched_atom[0])+tag

    def getOnlyVer(self):
        dbc = self.get_dbconn()
        return dbc.retrieveVersion(self.matched_atom[0])

    def getDownloadURL(self):
        dbc = self.get_dbconn()
        return dbc.retrieveDownloadURL(self.matched_atom[0])

    def getSlot(self):
        dbc = self.get_dbconn()
        return dbc.retrieveSlot(self.matched_atom[0])

    def getDependencies(self):
        dbc = self.get_dbconn()
        return dbc.retrieveDependencies(self.matched_atom[0])

    def getDependsFmt(self):
        dbc = self.get_dbconn()
        return dbc.retrieveDepends(self.matched_atom[0], atoms = True)

    def getConflicts(self):
        dbc = self.get_dbconn()
        return dbc.retrieveConflicts(self.matched_atom[0])

    def getLicense(self):
        dbc = self.get_dbconn()
        return dbc.retrieveLicense(self.matched_atom[0])

    def getDigest(self):
        dbc = self.get_dbconn()
        return dbc.retrieveDigest(self.matched_atom[0])

    def getCategory(self):
        dbc = self.get_dbconn()
        return dbc.retrieveCategory(self.matched_atom[0])

    def getApi(self):
        dbc = self.get_dbconn()
        return dbc.retrieveApi(self.matched_atom[0])

    def getUseflags(self):
        dbc = self.get_dbconn()
        return dbc.retrieveUseflags(self.matched_atom[0])

    def getTrigger(self):
        dbc = self.get_dbconn()
        return dbc.retrieveTrigger(self.matched_atom[0])

    def getConfigProtect(self):
        dbc = self.get_dbconn()
        return dbc.retrieveProtect(self.matched_atom[0])

    def getConfigProtectMask(self):
        dbc = self.get_dbconn()
        return dbc.retrieveProtectMask(self.matched_atom[0])

    def getKeywords(self):
        dbc = self.get_dbconn()
        return dbc.retrieveKeywords(self.matched_atom[0])

    def getNeeded(self):
        dbc = self.get_dbconn()
        return dbc.retrieveNeeded(self.matched_atom[0])

    def getCompileFlags(self):
        dbc = self.get_dbconn()
        return dbc.retrieveCompileFlags(self.matched_atom[0])

    def getSources(self):
        dbc = self.get_dbconn()
        return dbc.retrieveSources(self.matched_atom[0])

    def getEclasses(self):
        dbc = self.get_dbconn()
        return dbc.retrieveEclasses(self.matched_atom[0])

    def getHomepage(self):
        dbc = self.get_dbconn()
        return dbc.retrieveHomepage(self.matched_atom[0])

    def getMessages(self):
        dbc = self.get_dbconn()
        return dbc.retrieveMessages(self.matched_atom[0])

    def getKeySlot(self):
        dbc = self.get_dbconn()
        return dbc.retrieveKeySlot(self.matched_atom[0])

    def getDescription(self):
        dbc = self.get_dbconn()
        return dbc.retrieveDescription(self.matched_atom[0])

    def getDownSize(self):
        dbc = self.get_dbconn()
        return dbc.retrieveSize(self.matched_atom[0])

    def getDiskSize(self):
        dbc = self.get_dbconn()
        return dbc.retrieveOnDiskSize(self.matched_atom[0])

    def getIntelligentSize(self):
        if self.from_installed:
            return self.getDiskSizeFmt()
        else:
            return self.getDownSizeFmt()

    def getDownSizeFmt(self):
        dbc = self.get_dbconn()
        return EquoConnection.entropyTools.bytesIntoHuman(dbc.retrieveSize(self.matched_atom[0]))

    def getDiskSizeFmt(self):
        dbc = self.get_dbconn()
        return EquoConnection.entropyTools.bytesIntoHuman(dbc.retrieveOnDiskSize(self.matched_atom[0]))

    def getArch(self):
        return etpConst['currentarch']

    def getEpoch(self):
        dbc = self.get_dbconn()
        return dbc.retrieveDateCreation(self.matched_atom[0])

    def getEpochFmt(self):
        dbc = self.get_dbconn()
        return EquoConnection.entropyTools.convertUnixTimeToHumanTime(
                                        float(dbc.retrieveDateCreation(self.matched_atom[0]))
        )

    def getRel(self):
        dbc = self.get_dbconn()
        return dbc.retrieveBranch(self.matched_atom[0])

    def getAttr(self,attr):
        dbc = self.get_dbconn()
        if attr == "description":
            return dbc.retrieveDescription(self.matched_atom[0])
        elif attr == "category":
            return dbc.retrieveCategory(self.matched_atom[0])
        elif attr == "license":
            return dbc.retrieveLicense(self.matched_atom[0])
        elif attr == "creationdate":
            return dbc.retrieveDateCreation(self.matched_atom[0])
        elif attr == "version":
            return dbc.retrieveVersion(self.matched_atom[0])
        elif attr == "revision":
            return dbc.retrieveRevision(self.matched_atom[0])
        elif attr == "versiontag":
            t = dbc.retrieveVersionTag(self.matched_atom[0])
            if not t: return "None"
            return t
        elif attr == "branch":
            return dbc.retrieveBranch(self.matched_atom[0])
        elif attr == "name":
            return dbc.retrieveName(self.matched_atom[0])
        elif attr == "namedesc":
            return self.getNameDesc()
        elif attr == "slot":
            return dbc.retrieveSlot(self.matched_atom[0])

    def _get_time( self ):
        dbc = self.get_dbconn()
        return dbc.retrieveDateCreation(self.matched_atom[0])

    def get_changelog( self ):
        return "No ChangeLog"

    def get_filelist( self ):
        dbc = self.get_dbconn()
        m = list(dbc.retrieveContent(self.matched_atom[0]))
        m.sort()
        return m

    def get_filelist_ext( self ):
        dbc = self.get_dbconn()
        m = dbc.retrieveContent(self.matched_atom[0], extended = True)
        m = list(m)
        m.sort()
        return m

    def get_fullname( self ):
        dbc = self.get_dbconn()
        return dbc.retrieveAtom(self.matched_atom[0])

    pkg =  property(fget=getPkg)
    name =  property(fget=getName)
    namedesc = property(fget=getNameDesc)
    onlyname = property(fget=getOnlyName)
    cat = property(fget=getCategory)
    repoid =  property(fget=getRepoId)
    ver =  property(fget=getVer)
    binurl = property(fget=getDownloadURL)
    onlyver = property(fget=getOnlyVer)
    tag = property(fget=getTag)
    revision = property(fget=getRevision)
    digest = property(fget=getDigest)
    version = property(fget=getVer)
    release = property(fget=getRel)
    slot = property(fget=getSlot)
    keywords = property(fget=getKeywords)
    useflags = property(fget=getUseflags)
    homepage = property(fget=getHomepage)
    messages = property(fget=getMessages)
    protect = property(fget=getConfigProtect)
    protect_mask = property(fget=getConfigProtectMask)
    trigger = property(fget=getTrigger)
    compileflags = property(fget=getCompileFlags)
    dependencies = property(fget=getDependencies)
    needed = property(fget=getNeeded)
    conflicts = property(fget=getConflicts)
    dependsFmt = property(fget=getDependsFmt)
    api = property(fget=getApi)
    content = property(fget=get_filelist)
    contentExt = property(fget=get_filelist_ext)
    eclasses = property(fget=getEclasses)
    lic = property(fget=getLicense)
    sources = property(fget=getSources)
    keyslot = property(fget=getKeySlot)
    description =  property(fget=getDescription)
    size =  property(fget=getDownSize)
    intelligentsizeFmt = property(fget=getIntelligentSize)
    sizeFmt =  property(fget=getDownSizeFmt)
    disksize =  property(fget=getDiskSize)
    disksizeFmt =  property(fget=getDiskSizeFmt)
    arch = property(fget=getArch)
    epoch = property(fget=getEpoch)
    epochFmt = property(fget=getEpochFmt)
    pkgtup = property(fget=getTup)
    syspkg = property(fget=getSysPkg)
    install_status = property(fget=getInstallStatus)