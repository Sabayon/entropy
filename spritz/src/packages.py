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

from etpgui.packages import EntropyPackage, DummyEntropyPackage
import logging
from spritz_setup import SpritzConf
from entropy_i18n import _
from entropyConstants import *
import exceptionTools

class EntropyPackages:

    def __init__(self, EquoInstance):
        self.Entropy = EquoInstance
        self.logger = logging.getLogger('yumex.Packages')
        self.filterCallback = None
        self._packages = {}
        self.pkgCache = {}
        self.currentCategory = None
        self._categoryPackages = {}
        self.categories = set()
        self.unmaskingPackages = set()
        self.selected_treeview_item = None
        self.selected_advisory_item = None
        self.queue = None

    def connect_queue(self, queue):
        self.queue = queue

    def clearPackages(self):
        self._packages.clear()
        self.selected_treeview_item = None
        self.selected_advisory_item = None
        self._categoryPackages.clear()
        self.unmaskingPackages.clear()

    def clearCache(self):
        self.pkgCache.clear()
        self.selected_treeview_item = None
        self.selected_advisory_item = None

    def populatePackages(self,masks):
        for flt in masks:
            if self._packages.has_key(flt):
                continue
            self._packages[flt] = [p for p in self._getPackages(flt)]

    def setCategoryPackages(self,pkgdict = {}):
        self._categoryPackages = pkgdict

    def getPackagesByCategory(self,cat=None):
        if not cat:
           cat =  self.currentCategory
        else:
           self.currentCategory = cat
        if not self._categoryPackages.has_key(cat):
            self.populateCategory(cat)
        return self._categoryPackages[cat]

    def populateCategory(self, category):

        catsdata = self.Entropy.list_repo_packages_in_category(category)
        catsdata.update(set([(x,0) for x in self.Entropy.list_installed_packages_in_category(category)]))
        pkgsdata = []
        for pkgdata in catsdata:
            try:
                yp, new = self.getPackageItem(pkgdata,True)
            except exceptionTools.RepositoryError:
                continue
            install_status = yp.install_status
            ok = False
            if install_status == 1:
                yp.action = 'i'
                ok = True
            elif install_status == 2:
                yp.action = 'u'
                yp.color = SpritzConf.color_update
                ok = True
            #elif install_status == 3:
            #    yp.action = 'r'
            #    yp.color = SpritzConf.color_install
            #    ok = True
            if ok: pkgsdata.append(yp)
        del catsdata
        self._categoryPackages[category] = pkgsdata

    def populateCategories(self):
        self.categories = self.Entropy.list_repo_categories()

    def getPackages(self,flt):
        if flt == 'all':
            return self.getAllPackages()
        else:
            return self.doFiltering(self.getRawPackages(flt))

    def getAllPackages(self):
        pkgs = []
        pkgs.extend(self.getPackages('installed'))
        pkgs.extend(self.getPackages('available'))
        pkgs.extend(self.getPackages('reinstallable'))
        pkgs.extend(self.getPackages('updates'))
        return pkgs

    def setFilter(self,fn = None):
        self.filterCallback = fn

    def doFiltering(self,pkgs):
        if self.filterCallback:
            return filter(self.filterCallback,pkgs)
        else:
            return pkgs

    def isInst(self,atom): # fast check for if package is installed
        m = self.Entropy.clientDbconn.atomMatch(atom)
        if m[0] != -1:
            return True
        return False

    def findPackagesByTuples(self,typ,tuplist):
        pkgs = self.getRawPackages(typ)
        foundlst = []
        for pkg in pkgs:
            tup = pkg.pkgtup
            if tup in tuplist:
                foundlst.append(pkg)
        return foundlst

    def getRawPackages(self,flt):
        self.populatePackages([flt])
        return self._packages[flt]

    def getPackageItem(self, pkgdata, avail):
        new = False
        if self.pkgCache.has_key((pkgdata,avail)):
            yp = self.pkgCache[(pkgdata,avail)]
        else:
            new = True
            pkgset = None
            if isinstance(pkgdata,basestring): # package set
                pkgset = True
            yp = EntropyPackage(pkgdata, avail, pkgset = pkgset)
            self.pkgCache[(pkgdata,avail)] = yp
        return yp, new

    def _getPackages(self,mask):

        if mask == 'installed':

            for idpackage in self.Entropy.clientDbconn.listAllIdpackages(order_by = 'atom'):
                try:
                    yp, new = self.getPackageItem((idpackage,0),True)
                except exceptionTools.RepositoryError:
                    continue
                yp.action = 'r'
                yp.color = SpritzConf.color_install
                yield yp

        elif mask == "queued":

            for qkey in self.queue.packages:
                for item in self.queue.packages[qkey]:
                    yield item


        elif mask == 'available':

            # Get the rest of the available packages.
            available = self.Entropy.calculate_available_packages()
            for pkgdata in available:
                try:
                    yp, new = self.getPackageItem(pkgdata,True)
                except exceptionTools.RepositoryError:
                    continue
                yp.action = 'i'
                yield yp

        elif mask == 'updates':

            updates, remove, fine = self.Entropy.calculate_world_updates()
            del remove, fine
            for pkgdata in updates:
                try:
                    yp, new = self.getPackageItem(pkgdata,True)
                except exceptionTools.RepositoryError:
                    continue
                key, slot = yp.keyslot
                installed_match = self.Entropy.clientDbconn.atomMatch(key, matchSlot = slot)
                if installed_match[0] != -1: yp.installed_match = installed_match
                yp.action = 'u'
                yp.color = SpritzConf.color_update
                yield yp

        elif mask == "reinstallable":

            pkgdata = self.Entropy.clientDbconn.listAllPackages(get_scope = True,order_by = 'atom')
            pkgdata = self.filterReinstallable(pkgdata)
            # (idpackage,(idpackage,repoid,))
            for idpackage, matched in pkgdata:
                try:
                    yp, new = self.getPackageItem(matched,True)
                except exceptionTools.RepositoryError:
                    continue
                yp.installed_match = (idpackage,0)
                yp.action = 'rr'
                yp.color = SpritzConf.color_install
                yield yp

        elif mask == "masked":

            for match, idreason in self.getMaskedPackages():
                try:
                    yp, new = self.getPackageItem(match,True)
                except exceptionTools.RepositoryError:
                    continue
                action = self.getMaskedPackageAction(match)
                yp.action = action
                if action == 'rr': # setup reinstallables
                    idpackage = self.getInstalledMatch(match)
                    if idpackage == None: # wtf!?
                        yp.installed_match = None
                    else:
                        yp.installed_match = (idpackage,0)
                yp.masked = idreason
                yp.color = SpritzConf.color_install
                yield yp

        elif mask == "pkgsets":

            # make sure updates will be marked as such
            self.getPackages("updates")
            # make sure unavailable packages are marked as such
            self.getPackages("available")
            # make sure reinstallable packages will be marked as such
            self.getPackages("reinstallable")

            my_set_from = _('Set from')
            for set_from, set_name, set_deps in self.getPackageSets():

                set_matches = []
                set_installed_matches = []
                for set_dep in set_deps:

                    if set_dep.startswith(etpConst['packagesetprefix']):
                        set_matches.append((set_dep,None,))
                        set_installed_matches.append((set_dep,None,))
                    else:
                        set_match = self.Entropy.atomMatch(set_dep)
                        if set_match[0] != -1:
                            set_matches.append(set_match)
                        set_installed_match = self.Entropy.clientDbconn.atomMatch(set_dep)
                        if set_match[0] != -1:
                            set_installed_matches.append(set_installed_match)

                if not (set_matches and set_installed_matches): continue

                set_from_desc = _('Unknown')
                if set_from in self.Entropy.validRepositories:
                    set_from_desc = etpRepositories[set_from]['description']
                elif set_from == etpConst['userpackagesetsid']:
                    set_from_desc = _("User configuration")

                cat_namedesc = "%s: %s" % (my_set_from,set_from_desc,)

                set_objects = []

                satisfied = True
                for match in set_matches:

                    # set dependency
                    if match[1] == None:
                        yp, new = self.getPackageItem(match[0],True)
                        yp.action = "i"
                    else:
                        try:
                            yp, new = self.getPackageItem(match,True)
                        except exceptionTools.RepositoryError:
                            satisfied = False
                            break
                    yp.color = SpritzConf.color_install
                    yp.set_cat_namedesc = cat_namedesc
                    yp.set_names.add(set_name)
                    yp.set_from = set_from
                    yp.set_matches = set_matches
                    yp.set_installed_matches = set_installed_matches
                    set_objects.append(yp)

                if satisfied:
                    for obj in set_objects:
                        yield obj

        elif mask == "fake_updates":
            # load a pixmap inside the treeview
            msg2 = _("Try clicking the %s button in the %s page") % ( _("Update Repositories"),_("Repository Selection"),)

            msg = "<big><b><span foreground='#FF0000'>%s</span></b></big>\n<span foreground='darkblue'>%s.\n%s</span>" % (
                    _('No updates available'),
                    _("It seems that your system is already up-to-date. Good!"),
                    msg2,
                )
            myobj = DummyEntropyPackage(namedesc = msg, dummy_type = SpritzConf.dummy_empty)
            yield myobj

    def isReinstallable(self, atom, slot, revision):
        for repoid in self.Entropy.validRepositories:
            dbconn = self.Entropy.openRepositoryDatabase(repoid)
            idpackage, idreason = dbconn.isPackageScopeAvailable(atom, slot, revision)
            if idpackage == -1:
                continue
            return (repoid,idpackage,)
        return None

    def getPackageSets(self):
        return self.Entropy.packageSetList()

    def getMaskedPackages(self):
        maskdata = []
        for repoid in self.Entropy.validRepositories:
            dbconn = self.Entropy.openRepositoryDatabase(repoid)
            repodata = dbconn.listAllIdpackages(branch = etpConst['branch'], branch_operator = "<=", order_by = 'atom')
            for idpackage in repodata:
                idpackage_filtered, idreason = dbconn.idpackageValidator(idpackage)
                if idpackage_filtered == -1:
                    maskdata.append(((idpackage,repoid,),idreason))
        return maskdata

    def getMaskedPackageAction(self, match):
        action = self.Entropy.get_package_action(match)
        if action in [2,-1]:
            return 'u'
        elif action == 1:
            return 'i'
        else:
            return 'rr'

    def getInstalledMatch(self, match):
        dbconn = self.Entropy.openRepositoryDatabase(match[1])
        try:
            atom, slot, revision = dbconn.getStrictScopeData(match[0])
        except TypeError:
            return None
        idpackage, idresult = self.Entropy.clientDbconn.isPackageScopeAvailable(atom, slot, revision)
        if idpackage == -1:
            return None
        return idpackage

    def filterReinstallable(self, client_scope_data):
        clientdata = {}
        for idpackage, atom, slot, revision in client_scope_data:
            clientdata[(atom,slot,revision,)] = idpackage
        del client_scope_data

        matched_data = set()
        for repoid in self.Entropy.validRepositories:
            dbconn = self.Entropy.openRepositoryDatabase(repoid)
            repodata = dbconn.listAllPackages(get_scope = True, branch = etpConst['branch'], branch_operator = "<=")
            mydata = {}
            for idpackage, atom, slot, revision in repodata:
                mydata[(atom, slot, revision)] = idpackage
            del repodata
            for item in clientdata:
                if item in mydata:
                    idpackage = mydata[item]
                    idpackage, idreason = dbconn.idpackageValidator(idpackage)
                    if idpackage != -1:
                        matched_data.add((clientdata[item],(mydata[item],repoid,)))
        return matched_data

    def getCategories(self):
        catlist = []
        for cat in self.categories:
            catlist.append(cat)
        catlist.sort()
        return catlist
