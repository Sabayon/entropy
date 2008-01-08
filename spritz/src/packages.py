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

from etpgui.packages import PackageWrapper
import exceptionTools
import logging
import time

#import yum.misc as misc
#import yum.Errors as Errors
#from yum.packages import parsePackages

from i18n import _

color_normal = 'black'
color_install = 'darkgreen'
color_update = 'blue'
color_obsolete = 'red'

class EntropyPackage( PackageWrapper ):
    """ This class contains a yumPackage and some extra features used by
    yumex """

    def __init__( self, matched_atom, recentlimit, avail=True ):
        global color_normal
        PackageWrapper.__init__( self, matched_atom, avail )
        self.selected = False
        self.visible = True
        self.queued = None
        self.action = None
        self.obsolete = False
        self.obsolete_tup = None
        self.color = color_normal
        self.time = self._get_time()
        if float(self.time) > float(recentlimit):
            self.recent = True
        else:
            self.recent = False

    def set_select( self, state ):
        self.selected = state

    def set_visible( self, state ):
        self.visible = state



class EntropyPackages:
    def __init__(self, EquoInstance):
        self.Entropy = EquoInstance
        try:
            self.Entropy.instanceTest()
        except:
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")
        self.logger = logging.getLogger('yumex.Packages')
        self.filterCallback = None
        self._packages = {}
        self.currentCategory = None
        self._categoryPackages = {}
        self.recent = self.Entropy.entropyTools.getCurrentUnixTime()
        self.pkgInCats = PkgInCategoryList()

    def clearPackages(self):
        self._packages = {}

    def populatePackages(self,masks):
        for flt in masks:
            if self._packages.has_key(flt):
                continue
            if flt == 'available':
                self._packages[flt] = self.getAvailable()
            else:
                self._packages[flt] = [p for p in self._getPackages(flt)]

    def setCategoryPackages(self,pkgdict = {}):
        self._categoryPackages = pkgdict

    def getPackagesByCategory(self,cat=None):
        if not cat:
           cat =  self.currentCategory
        else:
           self.currentCategory = cat
        if self._categoryPackages.has_key(cat):
            return self._categoryPackages[cat]
        else:
            return []

    def populateCategories(self):
        global color_install,color_update,color_obsolete # FIXME: rename color_obsolete
        self.categories = self.Entropy.list_repo_categories()
        for category in self.categories:
            catsdata = self.Entropy.list_repo_packages_in_category(category)
            catsdata.update(set([(x,0) for x in self.Entropy.list_installed_packages_in_category(category)]))
            pkgsdata = []
            for pkgdata in catsdata:
                yp = EntropyPackage(pkgdata, self.recent, True)
                install_status = yp.install_status
                ok = False
                # FIXME: handle obsoletes in install_status == 3 whose are never install_status == 0
                if install_status == 0: # becomes from installed packages
                    yp.selected = True
                    yp.action = 'r'
                    yp.color = color_install
                    #ok = True
                elif install_status == 1:
                    yp.action = 'i'
                    yp.available = True
                    ok = True
                elif install_status == 2:
                    yp.action = 'u'
                    yp.color = color_update
                    yp.selected = None
                    # XXX: change to tri-state
                    ok = True
                elif install_status == 3:
                    yp.action = 'r'
                    yp.color = color_install
                    yp.selected = True
                    ok = True
                if ok: pkgsdata.append(yp)
            del catsdata
            self._categoryPackages[category] = pkgsdata

    def getPackages(self,flt):
        if flt == 'all':
            return self.getAllPackages()
        else:
            return self.doFiltering(self.getRawPackages(flt))

    def getAvailable(self):
        if not self._packages.has_key('updates'):
            self.populatePackages(['updates'])
        polist = []
        updlist = []
        for po in self._packages['updates']:
            polist.append(po)
            updlist.append(po.pkgtup)
        avail = [p for p in self._getPackages('available')]
        for po in avail:
            if not po.pkgtup in updlist:
                polist.append(po)
        return polist


    def getAllPackages(self):
        pkgs = []
        pkgs.extend(self.getPackages('installed'))
        pkgs.extend(self.getPackages('available'))
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

    def findPackages(self,userlist,typ):
        pkgs = self.getRawPackages(typ)
        foundlst = []
        for arg in userlist:
            print "Looking for : %s  in %s packages " % (arg,typ)
            exactmatch, matched, unmatched = parsePackages(pkgs, [arg], 
                                                           casematch=1)
            foundlst.extend(exactmatch)
            foundlst.extend(matched)
        return foundlst

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

    def _getPackages(self,mask):
        global color_install,color_update,color_obsolete
        if mask == 'installed':
            for idpackage in self.Entropy.clientDbconn.listAllIdpackages():
                yp = EntropyPackage((idpackage,0), self.recent, False)
                yp.selected = True
                yp.action = 'r'
                yp.color = color_install
                yield yp
        elif mask == 'available':
            # Get the rest of the available packages.
            available = self.Entropy.calculate_available_packages()
            for pkgdata in available:
                yp = EntropyPackage(pkgdata, self.recent, True)
                yp.action = 'i'
                yield yp
        elif mask == 'updates':
            # get updates
            #XXX add empty_deps and branch switching support
            updates, remove, fine = self.Entropy.calculate_world_updates()
            del remove, fine
            for pkgdata in updates:
                yp = EntropyPackage(pkgdata, self.recent, False)
                yp.action = 'u'
                yp.color = color_update
                yield yp

    def getByProperty( self, type, category ):
        list = self.getPackages(type)
        dict = {}
        for pkg in list:
            val = getattr( pkg, category )
            # Strip newline in keys
            if val:
                val = val.strip( '\n' )
            if dict.has_key( val ):
                dict[val].append( pkg )
            else:
                dict[val] = [pkg]
        return dict, dict.keys()
 
    def getByAttr( self, type, attr ):
        list = self.getPackages(type)
        dict = {}
        for pkg in list:
            val = pkg.getAttr( attr )
            # Strip newline in keys
            if val:
                val = val.strip( '\n' )
            if dict.has_key( val ):
                dict[val].append( pkg )
            else:
                dict[val] = [pkg]
        return dict, dict.keys()

    def getBySizes( self, type):
        list = self.getPackages(type)
        keys = [
            '0 KB - 100 KB', 
            '100 KB - 1 MB', 
            '1 MB - 10 MB' , 
            '10 MB - 50 MB', 
            '50+ MB']

        dict = {}
        for pkg in list:
            val = self._getSizeKey( pkg.size )
            if dict.has_key( val ):
                dict[val].append( pkg )
            else:
                dict[val] = [pkg]
        return dict , keys

    def _getSizeKey( self, size ):
        kb = 1024
        mb = 1024*1024
        if size < 100*kb:
            return '0 KB - 100 KB'
        elif size < mb:
            return '100 KB - 1 MB'
        elif size < 10*mb:
            return '1 MB - 10 MB' 
        elif size < 50*mb:
            return '10 MB - 50 MB'
        else:
            return '50+ MB'

    def getByAge( self, typ):
        list = self.getPackages(typ)
        keys = [
            '0 - 7 Days', 
            '7 - 14 Days', 
            '14 - 21 Days', 
            '21  - 30 days', 
            '30 - 90 days', 
            '90+ days']
        dict = {}
        for pkg in list:
            val = self._getAgeKey( pkg._get_time() )
            if dict.has_key( val ):
                dict[val].append( pkg )
            else:
                dict[val] = [pkg]
        return dict , keys

    def _getAgeKey( self, date ):
        now = time.time()
        days = 86400 # Seconds
        if date > now-7*days:
            return '0 - 7 Days'
        elif date > now-14*days:
            return '7 - 14 Days'
        elif date > now-21*days:
            return '14 - 21 Days'
        elif date > now-30*days:
            return '21  - 30 days'
        elif date > now-90*days:
            return '30 - 90 days'
        else:
            return '90+ days'

    def getCategories(self):
        catlist = []
        for cat in self.categories:
            catlist.append(cat)
        catlist.sort()
        return catlist

    def buildCategoryPackages(self,cat):
        for pkg in self.getPackagesByCategory(cat):
            self.pkgInCats.add(pkg,cat)

class PkgInCategory:
    def __init__(self, pkg, cat):
        self.name = pkg
        self.category = cat

    def __str__(self):
        return self.name

class PkgInCategoryList:
    def __init__(self):
        self._pkgDict = {}

    def add(self, pkg, cat):
        gpkg = PkgInGroup(pkg,cat)
        if self._pkgDict.has_key(pkg):
            self._pkgDict[pkg].append(gpkg)
        else:
            self._pkgDict[pkg] = [gpkg]

    def get(self,pkg):
        if self._pkgDict.has_key(pkg):
            return self._pkgDict[pkg]
        else:
            return None

    def getAll(self):
        lst = []
        for key in self._pkgDict.keys():
            lst.extend(self._pkgDict[key])
        return lst

    def getFullCategory(self,po):
        pkg = self.get(po.name)
        if pkg:
            return "%s/%s" % (pkg[0].category.name,pkg[0].group.name)
        else:
            return "No Category"


    def dump(self):
        for pkg in self.getAll():
            print "%-40s %s -> %s/%s" % (pkg.name,pkg.typ,pkg.category.name,pkg.group.name)
