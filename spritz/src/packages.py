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

from yumgui.packages import PackageWrapper
import logging
import time

import yum.misc as misc
import yum.Errors as Errors
from yum.packages import parsePackages

from i18n import _

color_normal = 'black'
color_install = 'darkgreen'
color_update = 'blue'
color_obsolete = 'red'

class YumexPackage( PackageWrapper ):
    """ This class contains a yumPackage and some extra features used by
    yumex """
    
    def __init__( self, pkg, recentlimit, avail=True ):
        global color_normal
        PackageWrapper.__init__( self, pkg, avail )
        self.selected = False
        self.visible = True
        self.queued = None 
        self.action = None
        self.obsolete = False
        self.obsolete_tup = None
        self.color = color_normal
        self.time = self._get_time()
        if self.time > recentlimit:
            self.recent = True
        else:
            self.recent = False
 
    def set_select( self, state ):
        self.selected = state

    def set_visible( self, state ):
        self.visible = state


        
class YumexPackages:
    def __init__(self):
        self.logger = logging.getLogger('yumex.Packages')
        self.filterCallback = None
        self._packages = {}
        self.currentCategory = None
        self._categoryPackages = {}
        self.pkgInGrps = PkgInGroupList()
        

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
            return False

    def getPackages(self,flt):
        if flt == 'all':
            return self.getAllPackages()
        else:
            return self.doFiltering(self.getRawPackages(flt))

    def getAvailable(self):
        if not self._packages.has_key('updates'):
            self.populatePackages('updates')
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

    def isInst(self,name): # fast check for if package is installed
        mi = self.ts.ts.dbMatch('name', name)
        if mi.count() > 0:
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
            for po in self.rpmdb:
                yp = YumexPackage(po,self.recent,False)
                yp.selected = True
                yp.action = 'r'
                yp.color = color_install
                yield yp
        elif mask == 'available':
            # Get the rest of the available packages.
            for po in self.pkgSack.returnNewestByNameArch():
                if not self.isInst(po.name):
                    yp = YumexPackage(po,self.recent,True)
                    yp.action = 'i'
                    yield yp
        elif mask == 'updates':
            obsoletes = self.up.getObsoletesTuples( newest=1 )
            for ( obsoleting, installed ) in obsoletes:
                obsoleting_pkg = self.getPackageObject( obsoleting )
                installed_pkg =  self.rpmdb.searchPkgTuple( installed )[0]                           
                yp = YumexPackage(obsoleting_pkg,self.recent,True)
                yp.action = 'u'
                yp.obsolete = True
                yp.obsolete_tup = installed_pkg.pkgtup
                yp.color = color_obsolete
                yield yp
            updates = self.up.getUpdatesList()
            obsoletes = self.up.getObsoletesList()
            for ( n, a, e, v, r ) in updates:
                if ( n, a, e, v, r ) in obsoletes:
                    continue
                matches = self.pkgSack.searchNevra( name=n, arch=a, epoch=e, 
                                               ver=v, rel=r )
                if len( matches ) > 0:
                    yp = YumexPackage(matches[0],self.recent,True)
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
        
        
    def getByCategory(self):        
        catlist = []
        catkeys = [ (c.name,c.categoryid) for c in self.comps.categories]
        catkeys.sort()
        for name,id in catkeys:
            grps = self._getGroupsInCategory(id)
            elem = ([name,id],grps)
            catlist.append(elem)
        return catlist
            
    def _getGroupsInCategory(self,category):
        for c in self.comps.categories:
            if c.categoryid == category:
                break
        grps = [self.comps.return_group(g) for g in c.groups if self.comps.return_group(g) != None]
        data = [(g.name,g.groupid,g.installed,) for g in grps]
        return data
        
    

    def _getByGroup(self,grp,flt):
        list = []
        list.extend(self.getRawPackages('installed'))
        list.extend(self.getRawPackages('available'))
        gpkgs = grp.packages
        pkgs = []        
        for pkg in list:
            if pkg.name in gpkgs:
                pkginfo = self.pkgInGrps.get(pkg.name)
                if pkginfo[0].typ in flt:
                    pkgs.append(pkg)
        return pkgs

    def buildGroups(self):
        cats = self.comps.categories
        catDict = {}
        for cat in cats:
            grps = map( lambda x: self.comps.return_group( x ), 
               filter( lambda x: self.comps.has_group( x ), cat.groups ) )
            grplist = []
            for grp in grps:
                grplist.append( grp.name )
                self.buildGroupPackages(grp,cat)
            catDict[cat.categoryid] = grplist
        #self.pkgInGrps.dump()

    def buildGroupPackages(self,group,cat):
        for pkg in group.mandatory_packages.keys():
            self.pkgInGrps.add(pkg,'m',group,cat)
        for pkg in group.default_packages.keys():
            self.pkgInGrps.add(pkg,'d',group,cat)
        for pkg in group.optional_packages.keys():
            self.pkgInGrps.add(pkg,'o',group,cat)
        for pkg in group.conditional_packages.keys():
            self.pkgInGrps.add(pkg,'c',group,cat)


class PkgInGroup:
    def __init__(self, pkg, typ, grp, cat):
        self.name = pkg
        self.typ = typ
        self.group = grp
        self.category = cat
        
    def __str__(self):
        return self.name

class PkgInGroupList:
    def __init__(self):
        self._pkgDict = {}
        
    def add(self, pkg, typ, grp, cat):
        gpkg = PkgInGroup(pkg,typ,grp,cat)
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
            return "!No Category/No Group"
        
        
    def dump(self):
        for pkg in self.getAll():
            print "%-40s %s -> %s/%s" % (pkg.name,pkg.typ,pkg.category.name,pkg.group.name)
        
class RPMGroupElement:
    '''
        This class handles a node in a tree of RPM Groups
        it contains a dictinary with subgroups and child objects
    '''
    def __init__(self):
        self.children = {}
        
    def addChild(self,key):
        '''
        add a subgroup to current node if it not exist already
        @param key: subgroup name 
        @return: the subgroup child object.
        '''
        if not self.children.has_key(key):
            self.children[key] = RPMGroupElement()
        return self.children[key]     
            
    def getKeys(self):
        '''
        Return a list of subgroup names for the current node.
        @return: list of subgroup names.
        '''
        return self.children.keys()
    
    def dump(self,prefix,sep = '->'):
        '''
        Dump all subgroups from the current node
        '''
        keys = self.getKeys()
        keys.sort()
        if keys: # has childen
            for key in keys:
                child = self.children[key]
                if prefix:
                    newprefix = '%s%s%s' % (prefix,sep,key)
                else:
                    newprefix = key
                child.dump(newprefix)
        else: # leaf node
            print prefix

    def addToModel(self,model,node,parent):
        '''
        Add all subgroups to a gtk.TreeStore model
        '''
        keys = self.getKeys()
        keys.sort()
        if keys: # has childen
            for key in keys:
                if parent:
                    newparent = '%s/%s' % (parent,key)
                else:
                    newparent = key
                child = self.children[key]
                if child.getKeys():
                    newnode = model.append(node,[key,''])
                    child.addToModel(model,newnode,newparent)
                else:
                    newnode = model.append(node,[key,newparent])
                    
        else: # leaf node
            pass

            
class RPMGroupTree:
    '''
    Container class containing the root node of the RPM Groups Tree 
    '''
    def __init__(self):
        self.root = RPMGroupElement()

    def add(self,keys):
        '''
        Add a the subgroup nodes to the tree
        @param keys: a list containing the ordered subgroups. ('level0','level1',...,'leveln')
        '''
        root = self.root
        for key in keys:
            root = root.addChild(key)
            
    def dump(self):
        '''
        dump all nodes on the screen
        '''
        self.root.dump(None)
            
    def populate(self,model):
        '''
        Populate a gtk.TreeStore model with all the subgroups in the tree.
        '''
        self.root.addToModel(model,None,None)
            
                    
                        