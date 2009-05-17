#!/usr/bin/python2 -O
# -*- coding: iso-8859-1 -*-
#    Sulfur (Entropy Interface)
#    Copyright: (C) 2007-2009 Fabio Erculiani < lxnay<AT>sabayonlinux<DOT>org >
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
from sulfur_setup import SulfurConf
from entropy.i18n import _
from entropy.const import *
from entropy.exceptions import *

class EntropyPackages:

    def __init__(self, EquoInstance):
        self.Entropy = EquoInstance
        self.logger = logging.getLogger('yumex.Packages')
        self.filterCallback = None
        self._packages = {}
        self.pkgCache = {}
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
        self.unmaskingPackages.clear()

    def clearPackagesSingle(self, mask):
        if mask in self._packages:
            del self._packages[mask]
        self.selected_treeview_item = None
        self.selected_advisory_item = None
        self.unmaskingPackages.clear()

    def clearCache(self):
        self.pkgCache.clear()
        self._packages.clear()
        self.selected_treeview_item = None
        self.selected_advisory_item = None

    def populatePackages(self,masks):
        for flt in masks: self.populateSingle(flt)

    def populateSingle(self, mask, force = False):
        if self._packages.has_key(mask) and not force:
            return
        self._packages[mask] = self._getPackages(mask)

    def getPackages(self,flt):
        if flt == 'all': return self.getAllPackages()
        else: return self.doFiltering(self.getRawPackages(flt))

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
        return pkgs

    def getRawPackages(self,flt):
        self.populateSingle(flt)
        return self._packages[flt]

    def getPackageItem(self, pkgdata):
        new = False
        yp = self.pkgCache.get(pkgdata)
        if yp is None:
            new = True
            pkgset = None
            if isinstance(pkgdata, basestring): # package set
                pkgset = True
            yp = EntropyPackage(pkgdata, pkgset = pkgset)
            self.pkgCache[pkgdata] = yp
        return yp, new

    def _pkg_get_installed(self):

        gp_call = self.getPackageItem
        def fm(idpackage):
            try:
                yp, new = gp_call((idpackage,0))
            except RepositoryError:
                return 0
            yp.action = 'r'
            yp.color = SulfurConf.color_install
            return yp
        return [x for x in map(fm,self.Entropy.clientDbconn.listAllIdpackages(order_by = 'atom')) if type(x) != int]

    def _pkg_get_queued(self):
        data = []
        for qkey in self.queue.packages:
            data.extend(self.queue.packages[qkey])
        return data

    def _pkg_get_available(self):
        gp_call = self.getPackageItem
        # Get the rest of the available packages.
        def fm(match):
            try:
                yp, new = gp_call(match)
            except RepositoryError:
                return 0
            yp.action = 'i'
            return yp
        return [x for x in map(fm,self.Entropy.calculate_available_packages()) if type(x) != int]

    def _pkg_get_updates(self):

        gp_call = self.getPackageItem
        cdb_atomMatch = self.Entropy.clientDbconn.atomMatch
        def fm(match):
            try:
                yp, new = gp_call(match)
            except RepositoryError:
                return 0
            key, slot = yp.keyslot
            installed_match = cdb_atomMatch(key, matchSlot = slot)
            if installed_match[0] != -1: yp.installed_match = installed_match
            yp.action = 'u'
            yp.color = SulfurConf.color_update
            return yp
        updates, remove, fine, spm_fine = self.Entropy.calculate_world_updates()

        # we need to cache these too on getPackageItem
        map(fm, spm_fine)

        return [x for x in map(fm, updates) if type(x) != int]

    def _pkg_get_reinstallable(self):
        def fm(match):
            idpackage, matched = match
            try:
                yp, new = self.getPackageItem(matched)
            except RepositoryError:
                return 0
            yp.installed_match = (idpackage,0)
            yp.action = 'rr'
            yp.color = SulfurConf.color_install
            return yp
        return [x for x in map(fm,self.filterReinstallable(self.Entropy.clientDbconn.listAllPackages(get_scope = True,order_by = 'atom'))) if type(x) != int]

    def _pkg_get_masked(self):
        gp_call = self.getPackageItem
        gmp_action = self.getMaskedPackageAction
        gi_match = self.getInstalledMatch
        def fm(match):
            match, idreason = match
            try:
                yp, new = gp_call(match)
            except RepositoryError:
                return 0
            action = gmp_action(match)
            yp.action = action
            if action == 'rr': # setup reinstallables
                idpackage = gi_match(match)
                if idpackage == None: # wtf!?
                    yp.installed_match = None
                else:
                    yp.installed_match = (idpackage,0)
            yp.masked = idreason
            yp.color = SulfurConf.color_install
            return yp
        return [x for x in map(fm,self.getMaskedPackages()) if type(x) != 0]

    def _pkg_get_user_masked(self):
        masked_objs = self.getPackages("masked")
        return [x for x in masked_objs if x.user_masked]

    def _pkg_get_user_unmasked(self):
        objs = self.getPackages("updates") + self.getPackages("available") + self.getPackages('reinstallable')
        return [x for x in objs if x.user_unmasked]

    def _pkg_get_pkgset_matches_installed_matches(self, set_deps):
        set_matches = []
        set_installed_matches = []
        install_incomplete = False
        remove_incomplete = False
        for set_dep in set_deps:
            if set_dep.startswith(etpConst['packagesetprefix']):
                set_matches.append((set_dep,None,))
                set_installed_matches.append((set_dep,None,))
            else:
                set_match = self.Entropy.atom_match(set_dep)
                if set_match[0] != -1: set_matches.append(set_match)
                else: install_incomplete = True
                set_installed_match = self.Entropy.clientDbconn.atomMatch(set_dep)
                if set_match[0] != -1: set_installed_matches.append(set_installed_match)
                else: remove_incomplete = True
        return set_matches, set_installed_matches, install_incomplete, remove_incomplete

    def _pkg_get_pkgset_set_from_desc(self, set_from):
        my_set_from = _('Set from')
        set_from_desc = _('Unknown')
        if set_from in self.Entropy.validRepositories:
            avail_repos = self.Entropy.SystemSettings['repositories']['available']
            set_from_desc = avail_repos[set_from]['description']
        elif set_from == etpConst['userpackagesetsid']:
            set_from_desc = _("User configuration")
        return "%s: %s" % (my_set_from,set_from_desc,)

    def _pkg_get_pkgsets(self):

        gp_call = self.getPackageItem

        # make sure updates will be marked as such
        self.getPackages("updates")
        # make sure unavailable packages are marked as such
        self.getPackages("available")
        # make sure reinstallable packages will be marked as such
        self.getPackages("reinstallable")

        objects = []

        pkgsets = self.getPackageSets()
        for set_from, set_name, set_deps in pkgsets:

            set_matches, set_installed_matches, install_incomplete, remove_incomplete = self._pkg_get_pkgset_matches_installed_matches(set_deps)
            if not (set_matches and set_installed_matches): continue
            cat_namedesc = self._pkg_get_pkgset_set_from_desc(set_from)
            set_objects = []

            def update_yp(yp):
                yp.color = SulfurConf.color_install
                yp.set_cat_namedesc = cat_namedesc
                yp.set_names.add(set_name)
                yp.set_from = set_from
                yp.set_matches = set_matches
                yp.set_installed_matches = set_installed_matches

            myobjs = []
            broken = False
            for match in set_matches:
                # set dependency
                if match[1] == None:
                    yp, new = gp_call(match[0])
                    yp.action = "i"
                else:
                    try:
                        yp, new = gp_call(match)
                    except RepositoryError:
                        broken = True
                        break
                myobjs.append(yp)
            if broken: continue

            for yp in myobjs: yp.set_names.clear()
            for yp in myobjs: update_yp(yp)
            objects += myobjs

        return objects

    def _pkg_get_fake_updates(self):
        # load a pixmap inside the treeview
        msg2 = _("Try clicking the %s button in the %s page") % ( _("Update Repositories"),_("Repository Selection"),)

        msg = "<big><b><span foreground='%s'>%s</span></b></big>\n%s.\n%s" % (
            SulfurConf.color_title,
            _('No updates available'),
            _("It seems that your system is already up-to-date. Good!"),
            msg2,
        )
        myobj = DummyEntropyPackage(namedesc = msg, dummy_type = SulfurConf.dummy_empty)
        return [myobj]

    def _getPackages(self,mask):

        calls_dict = {
            "installed": self._pkg_get_installed,
            "queued": self._pkg_get_queued,
            "available": self._pkg_get_available,
            "updates": self._pkg_get_updates,
            "reinstallable": self._pkg_get_reinstallable,
            "masked": self._pkg_get_masked,
            "user_masked": self._pkg_get_user_masked,
            "user_unmasked": self._pkg_get_user_unmasked,
            "pkgsets": self._pkg_get_pkgsets,
            "fake_updates": self._pkg_get_fake_updates,
        }
        return calls_dict.get(mask)()


    def isReinstallable(self, atom, slot, revision):
        for repoid in self.Entropy.validRepositories:
            dbconn = self.Entropy.open_repository(repoid)
            idpackage, idreason = dbconn.isPackageScopeAvailable(atom, slot, revision)
            if idpackage == -1:
                continue
            return (repoid,idpackage,)
        return None

    def getPackageSets(self):
        return self.Entropy.package_set_list()

    def getMaskedPackages(self):
        maskdata = []

        for repoid in self.Entropy.validRepositories:
            dbconn = self.Entropy.open_repository(repoid)
            repodata = dbconn.listAllIdpackages(order_by = 'atom')
            def fm(idpackage):
                idpackage_filtered, idreason = dbconn.idpackageValidator(idpackage)
                if idpackage_filtered == -1:
                    return ((idpackage,repoid,),idreason)
                return 0
            maskdata += [x for x in map(fm,repodata) if type(x) != int]

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
        dbconn = self.Entropy.open_repository(match[1])
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
            dbconn = self.Entropy.open_repository(repoid)
            repodata = dbconn.listAllPackages(get_scope = True)
            mydata = {}
            for idpackage, atom, slot, revision in repodata:
                mydata[(atom, slot, revision)] = idpackage

            def fm_pre(item):
                if item in mydata:
                    return True
                return False

            def fm(item):
                idpackage = mydata[item]
                idpackage, idreason = dbconn.idpackageValidator(idpackage)
                if idpackage != -1:
                    return (clientdata[item],(mydata[item],repoid,))
                return 0

            matched_data |= set([x for x in map(fm,filter(fm_pre,clientdata)) if type(x) != int])

        return matched_data

