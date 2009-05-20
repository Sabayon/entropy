#!/usr/bin/python -tt
# -*- coding: iso-8859-1 -*-
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

from entropy.const import *
from entropy.i18n import _
from sulfur.entropyapi import Equo
from sulfur.setup import cleanMarkupString, SulfurConf
EquoIntf = Equo()

class DummyEntropyPackage:

    def __init__(self, namedesc = None, dummy_type = -1, onlyname = ''):
        self.matched_atom = (0,0)
        self.namedesc = namedesc
        self.queued = None
        self.repoid = ''
        self.name = ''
        self.vote = -1
        self.voted = 0.0
        self.color = None
        self.action = None
        self.dbconn = None
        self.masked = None
        self.pkgset = False
        self.selected_by_user = False
        self.dummy_type = dummy_type
        self.onlyname = onlyname
        self.set_names = set()
        self.set_matches = set()
        self.set_installed_matches = set()
        self.set_from = None
        self.set_cat_namedesc = None
        self.set_category = False
        self.set_install_incomplete = False
        self.set_remove_incomplete = False

class EntropyPackage:

    import entropy.tools as entropyTools
    def __init__(self, matched_atom, remote = None, pkgset = None):

        self.pkgset = pkgset
        self.queued = None
        self.action = None
        self.dummy_type = None
        self.do_purge = False
        self.masked = None
        self.voted = 0.0
        self.color = SulfurConf.color_normal
        self.remote = remote
        self.selected_by_user = False
        self.set_names = set()
        self.set_matches = set()
        self.set_installed_matches = set()
        self.set_from = None
        self.set_cat_namedesc = None
        self.set_category = False
        self.set_install_incomplete = False
        self.set_remove_incomplete = False

        self.matched_atom = matched_atom
        self.installed_match = None

        if self.pkgset:

            # must be available!
            set_from, set_name, set_deps = EquoIntf.package_set_match(
                self.matched_atom[1:])[0]
            self.from_installed = False
            self.dbconn = None
            self.dummy_type = -2
            self.set_from = set_from
            self.is_set_dep = True
            self.set_name = set_name
            self.cat = self.set_name
            self.set_names = set()
            self.set_cat_namedesc = self.set_name
            self.set_matches = set_deps
            self.onlyname = self.matched_atom
            self.description = self.set_name
            self.name = self.matched_atom
            self.set_category = False
            self.matched_id = "@"
            self.matched_repo = set_name

        elif self.remote:

            self.dbconn = EquoIntf.open_memory_database()
            idpackage, revision, mydata_upd = self.dbconn.addPackage(self.remote)
            self.matched_atom = (idpackage,matched_atom[1])
            self.from_installed = False

        else:

            if matched_atom[1] == 0:
                self.dbconn = EquoIntf.clientDbconn
                self.from_installed = True
            else:
                self.dbconn = EquoIntf.open_repository(matched_atom[1])
                self.from_installed = False

        if isinstance(self.matched_atom,tuple):
            self.matched_id, self.matched_repo = self.matched_atom

    def __del__(self):
        if hasattr(self,'remote'):
            if self.remote:
                self.dbconn.closeDB()

    def __str__(self):
        if self.pkgset: return self.matched_atom
        return str(self.dbconn.retrieveAtom(self.matched_id) + "~" + \
            str(self.dbconn.retrieveRevision(self.matched_id)))

    def __cmp__(self, pkg):
        if pkg.matched_atom == self.matched_atom:
            return 0
        return 1

    def getPkg(self):
        return self.matched_atom

    def getTag(self):
        if self.pkgset: return ''

        return self.dbconn.retrieveVersionTag(self.matched_id)

    def getName(self):
        if self.pkgset: return self.matched_atom
        return self.dbconn.retrieveAtom(self.matched_id)

    def isMasked(self):

        if self.pkgset:
            return False

        idpackage, idmask = self.dbconn.idpackageValidator(self.matched_id)
        if idpackage != -1:
            return False
        return True

    def isUserMasked(self):
        if self.from_installed:
            key, slot = self.dbconn.retrieveKeySlot(self.matched_id)
            m_id, m_r = EquoIntf.atom_match(key, matchSlot = slot)
            if m_id == -1: return False
            return EquoIntf.is_match_masked_by_user((m_id, m_r,))
        return EquoIntf.is_match_masked_by_user(self.matched_atom)

    def isUserUnmasked(self):
        if self.from_installed:
            key, slot = self.dbconn.retrieveKeySlot(self.matched_id)
            m_id, m_r = EquoIntf.atom_match(key, matchSlot = slot)
            if m_id == -1: return False
            return EquoIntf.is_match_unmasked_by_user((m_id, m_r,))
        return EquoIntf.is_match_unmasked_by_user(self.matched_atom)

    def getNameDesc(self):

        if self.pkgset:
            t = self.matched_atom
            desc = _("Recursive Package Set")
            t += '\n<small><span foreground=\'%s\'>%s</span></small>' % (
                SulfurConf.color_pkgdesc,cleanMarkupString(desc),)
            return t

        ugc_string = ''
        atom = self.getName()
        if self.from_installed: repo = self.getRepoId()
        else: repo = self.matched_repo
        key = self.entropyTools.dep_getkey(atom)
        downloads = EquoIntf.UGC.UGCCache.get_package_downloads(repo,key)
        ugc_string = "<small>[%s]</small> " % (downloads,)

        t = ugc_string+'/'.join(atom.split("/")[1:])
        if self.masked:
            t +=  " <small>[<span foreground='%s'>%s</span>]</small>" % (
                SulfurConf.color_title2,
                EquoIntf.SystemSettings['pkg_masking_reasons'][self.masked],)

        desc = self.getDescription(markup = False)
        if len(desc) > 56:
            desc = desc[:56].rstrip()+"..."
        t += '\n<small><span foreground=\'%s\'>%s</span></small>' % (
            SulfurConf.color_pkgdesc, cleanMarkupString(desc),)
        return t

    def getOnlyName(self):
        if self.pkgset:
            return self.set_name
        return self.dbconn.retrieveName(self.matched_id)

    def getTup(self):
        if self.pkgset:
            return self.matched_atom

        return (self.getName(), self.getRepoId(),
            self.dbconn.retrieveVersion(self.matched_id),
            self.dbconn.retrieveVersionTag(self.matched_id),
            self.dbconn.retrieveRevision(self.matched_id))

    def versionData(self):
        if self.pkgset: return self.matched_atom
        return (self.dbconn.retrieveVersion(self.matched_id),
            self.dbconn.retrieveVersionTag(self.matched_id),
            self.dbconn.retrieveRevision(self.matched_id))

    def getRepoId(self):
        if self.pkgset:
            x = self.set_from
            if x == etpConst['userpackagesetsid']: x = _("User")
            return x
        if self.matched_atom[1] == 0:
            return self.dbconn.retrievePackageFromInstalledTable(self.matched_id)
        else: return self.matched_repo

    def getIdpackage(self):
        return self.matched_id

    def getRevision(self):
        if self.pkgset: return 0

        return self.dbconn.retrieveRevision(self.matched_id)

    def getSysPkg(self):
        if self.pkgset: return False

        match = self.matched_atom
        if (not self.from_installed) and (not self.installed_match):
            return False
        elif self.installed_match:
            match = self.installed_match

        # check if it's a system package
        s = EquoIntf.validate_package_removal(match[0])
        return not s

    # 0: from installed db, so it's installed for sure
    # 1: not installed
    # 2: updatable
    # 3: already updated to the latest
    def getInstallStatus(self):
        if self.pkgset: return 0

        if self.from_installed:
            return 0
        key, slot = self.dbconn.retrieveKeySlot(self.matched_id)
        matches = EquoIntf.clientDbconn.searchKeySlot(key,slot)
        if not matches: # not installed, new!
            return 1
        else:
            rc, matched = EquoIntf.check_package_update(key+":"+slot, deep = True)
            if rc: return 2
            return 3

    def getVer(self):
        if self.pkgset: return "0"

        tag = ""
        vtag = self.dbconn.retrieveVersionTag(self.matched_id)
        if vtag:
            tag = "#"+vtag
        tag += "~"+str(self.dbconn.retrieveRevision(self.matched_id))
        return self.dbconn.retrieveVersion(self.matched_id)+tag

    def getOnlyVer(self):
        if self.pkgset: return "0"
        return self.dbconn.retrieveVersion(self.matched_id)

    def getDownloadURL(self):
        if self.pkgset: return None
        return self.dbconn.retrieveDownloadURL(self.matched_id)

    def getSlot(self):
        if self.pkgset: return "0"
        return self.dbconn.retrieveSlot(self.matched_id)

    def getDependencies(self):
        if self.pkgset: self.set_matches.copy()
        return self.dbconn.retrieveDependencies(self.matched_id)

    def getDependsFmt(self):
        if self.pkgset: return []
        return self.dbconn.retrieveDepends(self.matched_id, atoms = True)

    def getConflicts(self):
        if self.pkgset: return []
        return self.dbconn.retrieveConflicts(self.matched_id)

    def getLicense(self):
        if self.pkgset: return ""
        return self.dbconn.retrieveLicense(self.matched_id)

    def getChangeLog(self):
        if self.pkgset: return ""
        return self.dbconn.retrieveChangelog(self.matched_id)

    def getDigest(self):
        if self.pkgset: return "0"
        return self.dbconn.retrieveDigest(self.matched_id)

    def getCategory(self):
        if self.pkgset: return self.cat
        return self.dbconn.retrieveCategory(self.matched_id)

    def getApi(self):
        if self.pkgset: return "0"
        return self.dbconn.retrieveApi(self.matched_id)

    def getUseflags(self):
        if self.pkgset: return []
        return self.dbconn.retrieveUseflags(self.matched_id)

    def getTrigger(self):
        if self.pkgset: return ""
        return self.dbconn.retrieveTrigger(self.matched_id)

    def getConfigProtect(self):
        if self.pkgset: return []
        return self.dbconn.retrieveProtect(self.matched_id)

    def getConfigProtectMask(self):
        if self.pkgset: return []
        return self.dbconn.retrieveProtectMask(self.matched_id)

    def getKeywords(self):
        if self.pkgset: return []
        return self.dbconn.retrieveKeywords(self.matched_id)

    def getNeeded(self):
        if self.pkgset: return []
        return self.dbconn.retrieveNeeded(self.matched_id)

    def getCompileFlags(self):
        if self.pkgset: return []
        flags = self.dbconn.retrieveCompileFlags(self.matched_id)
        return flags

    def getSources(self):
        if self.pkgset: return []
        return self.dbconn.retrieveSources(self.matched_id)

    def getEclasses(self):
        if self.pkgset: return []
        return self.dbconn.retrieveEclasses(self.matched_id)

    def getHomepage(self):
        if self.pkgset: return ""
        return self.dbconn.retrieveHomepage(self.matched_id)

    def getMessages(self):
        if self.pkgset: return []
        return self.dbconn.retrieveMessages(self.matched_id)

    def getKeySlot(self):
        if self.pkgset: return self.set_name,"0"
        return self.dbconn.retrieveKeySlot(self.matched_id)

    def getDescriptionNoMarkup(self):
        if self.pkgset: return self.set_cat_namedesc
        return self.getDescription(markup = False)

    def getDescription(self, markup = True):
        if self.pkgset: return self.set_cat_namedesc

        if markup:
            return cleanMarkupString(
                self.dbconn.retrieveDescription(self.matched_id))
        else:
            return self.dbconn.retrieveDescription(self.matched_id)

    def getDownSize(self):
        if self.pkgset:
            return 0
        return self.dbconn.retrieveSize(self.matched_id)

    def getDiskSize(self):
        if self.pkgset:
            return 0
        return self.dbconn.retrieveOnDiskSize(self.matched_id)

    def getIntelligentSize(self):
        if self.from_installed:
            return self.getDiskSizeFmt()
        else:
            return self.getDownSizeFmt()

    def getDownSizeFmt(self):
        if self.pkgset:
            return 0
        return EquoIntf.entropyTools.bytes_into_human(
            self.dbconn.retrieveSize(self.matched_id))

    def getDiskSizeFmt(self):
        if self.pkgset:
            return 0
        return EquoIntf.entropyTools.bytes_into_human(
            self.dbconn.retrieveOnDiskSize(self.matched_id))

    def getArch(self):
        return etpConst['currentarch']

    def getEpoch(self):
        if self.pkgset:
            return 0
        return self.dbconn.retrieveDateCreation(self.matched_id)

    def getEpochFmt(self):
        if self.pkgset:
            return 0
        return EquoIntf.entropyTools.convert_unix_time_to_human_time(
            float(self.dbconn.retrieveDateCreation(self.matched_id)))

    def getRel(self):
        if self.pkgset:
            return EquoIntf.SystemSettings['repositories']['branch']
        return self.dbconn.retrieveBranch(self.matched_id)

    def getUGCPackageVote(self):
        if self.pkgset:
            return -1
        atom = self.getName()
        if not atom:
            return None
        return EquoIntf.UGC.UGCCache.get_package_vote(self.getRepoId(),
            self.entropyTools.dep_getkey(atom))

    def getUGCPackageVoteInt(self):
        if self.pkgset:
            return 0
        atom = self.getName()
        if not atom:
            return 0
        vote = EquoIntf.UGC.UGCCache.get_package_vote(self.getRepoId(),
            self.entropyTools.dep_getkey(atom))
        if not isinstance(vote, float):
            return 0
        return int(vote)

    def getUGCPackageVoteFloat(self):
        if self.pkgset:
            return 0.0
        atom = self.getName()
        if not atom:
            return 0.0
        vote = EquoIntf.UGC.UGCCache.get_package_vote(self.getRepoId(),
            self.entropyTools.dep_getkey(atom))
        if not isinstance(vote, float):
            return 0.0
        return vote

    def getUGCPackageVoted(self):
        return self.voted

    def getUGCPackageDownloads(self):
        if self.pkgset: return 0
        if self.from_installed: return 0
        atom = self.getName()
        if not atom: return 0
        key = self.entropyTools.dep_getkey(atom)
        return EquoIntf.UGC.UGCCache.get_package_downloads(self.matched_repo,
            key)

    def getAttr(self,attr):
        x = None
        if attr == "description":
            x = cleanMarkupString(self.dbconn.retrieveDescription(self.matched_id))
        elif attr == "category":
            x = self.dbconn.retrieveCategory(self.matched_id)
        elif attr == "license":
            x = self.dbconn.retrieveLicense(self.matched_id)
        elif attr == "creationdate":
            x = self.dbconn.retrieveDateCreation(self.matched_id)
        elif attr == "version":
            x = self.dbconn.retrieveVersion(self.matched_id)
        elif attr == "revision":
            x = self.dbconn.retrieveRevision(self.matched_id)
        elif attr == "versiontag":
            x = self.dbconn.retrieveVersionTag(self.matched_id)
            if not x: x = "None"
        elif attr == "branch":
            x = self.dbconn.retrieveBranch(self.matched_id)
        elif attr == "name":
            x = self.dbconn.retrieveName(self.matched_id)
        elif attr == "namedesc":
            x = self.getNameDesc()
        elif attr == "slot":
            x = self.dbconn.retrieveSlot(self.matched_id)
        return x

    def _get_time( self ):
        if self.pkgset: return 0
        return self.dbconn.retrieveDateCreation(self.matched_id)

    def get_changelog( self ):
        return "No ChangeLog"

    def get_filelist( self ):
        if self.pkgset: return []
        mycont = sorted(list(self.dbconn.retrieveContent(self.matched_id)))
        return mycont

    def get_filelist_ext( self ):
        if self.pkgset: return []
        return self.dbconn.retrieveContent(self.matched_id, extended = True,
            order_by = 'file')

    def get_fullname( self ):
        if self.pkgset: return self.set_name
        return self.dbconn.retrieveAtom(self.matched_id)

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
    maskstat = property(fget=isMasked)
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
    description_nomarkup = property(fget=getDescriptionNoMarkup)
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
    vote = property(fget=getUGCPackageVote)
    voteint = property(fget=getUGCPackageVoteInt)
    votefloat = property(fget=getUGCPackageVoteFloat)
    voted = property(fget=getUGCPackageVoted)
    downloads = property(fget=getUGCPackageDownloads)
    user_unmasked = property(fget=isUserUnmasked)
    user_masked = property(fget=isUserMasked)
    changelog = property(fget=getChangeLog)
