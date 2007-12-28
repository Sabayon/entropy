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

from yumgui import format_number
import time
import types


class PackageWrapper:
    def __init__(self,pkg,avail):
        self.__pkg = pkg
        self.available = avail

    def __str__( self ):
        return str(self.__pkg)

    def __cmp__( self,pkg):
        n1 = str(self.__pkg)
        n2 = str(pkg)
        if n1 > n2:
            return 1
        elif n1 == n2:
            return 0
        else:
            return -1
        
    

    def getPkg(self):
        return self.__pkg
        
    def getName(self):
        return self.__pkg.name
        
    def getTup(self):
        return self.__pkg.pkgtup

    def getRepoId(self):
        return self.__pkg.repoid
        
    def getVer(self):
        return self.__pkg.printVer()
        
    def getSummaryFirst(self):
        summary = self.__pkg.returnSimple( 'summary' )
        if summary:
            return self._toUTF(summary.splitlines()[0])
        else:
            return ''

    def getSummary(self):
        return self.__pkg.returnSimple( 'summary' )

    def getDescription(self):
        return self.__pkg.returnSimple( 'description' )
        
    def getSize(self):
        return float(self.__pkg.size)
    
    def getSizeFmt(self):
        return format_number(float(self.__pkg.size))
        
        
    def getArch(self):
        return self.__pkg.arch
        
    def getEpoch(self):
        return self.__pkg.epoch

    def getRel(self):
        return self.__pkg.release
        
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
        # Check for attributes, contained in the pkg object 
        if self.available:
            return self._get_available_attr(attr)
        else:
            return self._get_installed_attr(attr)

    def _get_available_attr(self,attr):
        if attr in self.__pkg.__dict__.keys(): # pkg attribute ?
           return getattr(self.__pkg,attr)        
        else:
           return self.__pkg.returnSimple(attr)   
    
    def _dumpAttrs(self,obj):
        attrList = [attr for attr in dir(obj) if not callable(getattr(self.__pkg, attr))] 
        print "\n".join(["%s =  %s" % (attr,getattr(obj,attr)) for attr in attrList])
                      
        
    def _get_installed_attr(self,attr):
        # we can't test for member so just try to get it.
        try: 
            return self.__pkg.returnSimple(attr)
        except KeyError:
           # We want a AttributeError Exception, if not found 
           raise AttributeError, attr
        
    def _get_time( self ):
        if not self.available: # Installed packages dont have filetime
            ftime = int( self.__pkg.returnSimple( 'installtime' ) )
        else:
            ftime = int( self.__pkg.returnSimple( 'filetime' ) )
        return ftime
        
    def get_changelog( self ):    
        """ Get changelog from package object"""
        cl = []
        if self.available: # YumAvailablePackage
            clog = self.__pkg.returnChangelog()
            for tim, name, text in clog:
                cl.append( str( time.ctime( float( tim ) ) )+" "+name+"\n"+text )
        else:  # YumInstalledPackage, get files from rpm header.
            cltime = self.__pkg.hdr['changelogtime']
            clname = self.__pkg.hdr['changelogname']
            cltext = self.__pkg.hdr['changelogtext']
            if not isinstance(cltime, types.ListType): # cltime should always be a list
                cltime = [cltime]
            for tim, name, text in zip( cltime, clname, cltext ):
                cl.append( str( time.ctime( tim ) )+" "+name+"\n"+text )
        return cl
        
    def get_filelist( self ):    
        """ Get filelist from package object"""
        if self.available: # YumAvailablePackage
            files = self.__pkg.returnFileEntries()
        else:  # YumInstalledPackage, get files from rpm header.
            files = []
            fn = self.__pkg.hdr['basenames']
            dn = self.__pkg.hdr['dirnames']
            for d, n in zip( dn, fn ):
                files.append( d+n )
        return files    
        
    def get_fullname( self ):
        """ return fullpackage name in format : <epoch>:<name>-<ver>.<arch>"""
        fe = self.ver.find( ":" )
        if fe > -1:
            epoch = self.ver[0:fe]
            ver = self.ver[fe+1:]
            add = "%s:%s-%s.%s" % ( epoch, self.name, ver, self.arch )
        else:
            add = "%s:%s-%s.%s" % ( '0', self.name, self.ver, self.arch )
        return add
        