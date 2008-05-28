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
from spritz_setup import cleanMarkupString, SpritzConf

class DummyEntropyPackage:

    def __init__(self, namedesc = None, dummy_type = -1, onlyname = ''):
        self.matched_atom = (0,0)
        self.namedesc = namedesc
        self.queued = None
        self.repoid = ''
        self.color = None
        self.action = None
        self.dbconn = None
        self.dummy_type = dummy_type
        self.onlyname = onlyname

class EntropyPackage:

    def __init__(self, matched_atom, avail):

        self.queued = None
        self.action = None
        self.dummy_type = None
        self.available = avail
        self.do_purge = False
        self.color = SpritzConf.color_normal

        if matched_atom[1] == 0:
            self.dbconn = EquoConnection.clientDbconn
            self.from_installed = True
        else:
            self.dbconn = EquoConnection.openRepositoryDatabase(matched_atom[1])
            self.from_installed = False

        self.matched_atom = matched_atom
        self.installed_match = None

    def __str__(self):
        return str(self.dbconn.retrieveAtom(self.matched_atom[0])+"~"+str(self.dbconn.retrieveRevision(self.matched_atom[0])))

    def __cmp__(self, pkg):
        if pkg.matched_atom == self.matched_atom:
            return 0
        return 1

    def getPkg(self):
        return self.matched_atom

    def getTag(self):
        return self.dbconn.retrieveVersionTag(self.matched_atom[0])

    def getName(self):
        return self.dbconn.retrieveAtom(self.matched_atom[0])

    def getNameDesc(self):
        t = cleanMarkupString('/'.join(self.getName().split("/")[1:]))
        desc = self.getDescription(markup = False)
        if len(desc) > 56:
            desc = desc[:56].rstrip()+"..."
        t += '\n<small><span foreground=\'#FF0000\'>%s</span></small>' % (cleanMarkupString(desc),)
        return t

    def getOnlyName(self):
        return self.dbconn.retrieveName(self.matched_atom[0])

    def getTup(self):
        return (self.getName(),self.getRepoId(),self.dbconn.retrieveVersion(self.matched_atom[0]),self.dbconn.retrieveVersionTag(self.matched_atom[0]),self.dbconn.retrieveRevision(self.matched_atom[0]))

    def versionData(self):
        return (self.dbconn.retrieveVersion(self.matched_atom[0]),self.dbconn.retrieveVersionTag(self.matched_atom[0]),self.dbconn.retrieveRevision(self.matched_atom[0]))

    def getRepoId(self):
        if self.matched_atom[1] == 0:
            return self.dbconn.retrievePackageFromInstalledTable(self.matched_atom[0])
        else:
            return self.matched_atom[1]

    def getIdpackage(self):
        return self.matched_atom[0]

    def getRevision(self):
        return self.dbconn.retrieveRevision(self.matched_atom[0])

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
        key, slot = self.dbconn.retrieveKeySlot(self.matched_atom[0])
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
        tag = ""
        vtag = self.dbconn.retrieveVersionTag(self.matched_atom[0])
        if vtag:
            tag = "#"+vtag
        tag += "~"+str(self.dbconn.retrieveRevision(self.matched_atom[0]))
        return self.dbconn.retrieveVersion(self.matched_atom[0])+tag

    def getOnlyVer(self):
        return self.dbconn.retrieveVersion(self.matched_atom[0])

    def getDownloadURL(self):
        return self.dbconn.retrieveDownloadURL(self.matched_atom[0])

    def getSlot(self):
        return self.dbconn.retrieveSlot(self.matched_atom[0])

    def getDependencies(self):
        return self.dbconn.retrieveDependencies(self.matched_atom[0])

    def getDependsFmt(self):
        return self.dbconn.retrieveDepends(self.matched_atom[0], atoms = True)

    def getConflicts(self):
        return self.dbconn.retrieveConflicts(self.matched_atom[0])

    def getLicense(self):
        return self.dbconn.retrieveLicense(self.matched_atom[0])

    def getDigest(self):
        return self.dbconn.retrieveDigest(self.matched_atom[0])

    def getCategory(self):
        return self.dbconn.retrieveCategory(self.matched_atom[0])

    def getApi(self):
        return self.dbconn.retrieveApi(self.matched_atom[0])

    def getUseflags(self):
        return self.dbconn.retrieveUseflags(self.matched_atom[0])

    def getTrigger(self):
        return self.dbconn.retrieveTrigger(self.matched_atom[0])

    def getConfigProtect(self):
        return self.dbconn.retrieveProtect(self.matched_atom[0])

    def getConfigProtectMask(self):
        return self.dbconn.retrieveProtectMask(self.matched_atom[0])

    def getKeywords(self):
        return self.dbconn.retrieveKeywords(self.matched_atom[0])

    def getNeeded(self):
        return self.dbconn.retrieveNeeded(self.matched_atom[0])

    def getCompileFlags(self):
        flags = self.dbconn.retrieveCompileFlags(self.matched_atom[0])
        return flags

    def getSources(self):
        return self.dbconn.retrieveSources(self.matched_atom[0])

    def getEclasses(self):
        return self.dbconn.retrieveEclasses(self.matched_atom[0])

    def getHomepage(self):
        return self.dbconn.retrieveHomepage(self.matched_atom[0])

    def getMessages(self):
        return self.dbconn.retrieveMessages(self.matched_atom[0])

    def getKeySlot(self):
        return self.dbconn.retrieveKeySlot(self.matched_atom[0])

    def getDescription(self, markup = True):
        if markup:
            return cleanMarkupString(self.dbconn.retrieveDescription(self.matched_atom[0]))
        else:
            return self.dbconn.retrieveDescription(self.matched_atom[0])

    def getDownSize(self):
        return self.dbconn.retrieveSize(self.matched_atom[0])

    def getDiskSize(self):
        return self.dbconn.retrieveOnDiskSize(self.matched_atom[0])

    def getIntelligentSize(self):
        if self.from_installed:
            return self.getDiskSizeFmt()
        else:
            return self.getDownSizeFmt()

    def getDownSizeFmt(self):
        return EquoConnection.entropyTools.bytesIntoHuman(self.dbconn.retrieveSize(self.matched_atom[0]))

    def getDiskSizeFmt(self):
        return EquoConnection.entropyTools.bytesIntoHuman(self.dbconn.retrieveOnDiskSize(self.matched_atom[0]))

    def getArch(self):
        return etpConst['currentarch']

    def getEpoch(self):
        return self.dbconn.retrieveDateCreation(self.matched_atom[0])

    def getEpochFmt(self):
        return EquoConnection.entropyTools.convertUnixTimeToHumanTime(float(self.dbconn.retrieveDateCreation(self.matched_atom[0])))

    def getRel(self):
        return self.dbconn.retrieveBranch(self.matched_atom[0])

    def getAttr(self,attr):
        x = None
        if attr == "description":
            x = cleanMarkupString(self.dbconn.retrieveDescription(self.matched_atom[0]))
        elif attr == "category":
            x = self.dbconn.retrieveCategory(self.matched_atom[0])
        elif attr == "license":
            x = self.dbconn.retrieveLicense(self.matched_atom[0])
        elif attr == "creationdate":
            x = self.dbconn.retrieveDateCreation(self.matched_atom[0])
        elif attr == "version":
            x = self.dbconn.retrieveVersion(self.matched_atom[0])
        elif attr == "revision":
            x = self.dbconn.retrieveRevision(self.matched_atom[0])
        elif attr == "versiontag":
            x = self.dbconn.retrieveVersionTag(self.matched_atom[0])
            if not x: x = "None"
        elif attr == "branch":
            x = self.dbconn.retrieveBranch(self.matched_atom[0])
        elif attr == "name":
            x = self.dbconn.retrieveName(self.matched_atom[0])
        elif attr == "namedesc":
            x = self.getNameDesc()
        elif attr == "slot":
            x = self.dbconn.retrieveSlot(self.matched_atom[0])
        return x

    def _get_time( self ):
        return self.dbconn.retrieveDateCreation(self.matched_atom[0])

    def get_changelog( self ):
        return "No ChangeLog"

    def get_filelist( self ):
        c = list(self.dbconn.retrieveContent(self.matched_atom[0]))
        c.sort()
        return c

    def get_filelist_ext( self ):
        c = self.dbconn.retrieveContent(self.matched_atom[0], extended = True)
        data = list(c)
        data.sort()
        return data

    def get_fullname( self ):
        return self.dbconn.retrieveAtom(self.matched_atom[0])

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