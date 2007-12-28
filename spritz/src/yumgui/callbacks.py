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

import rpm
import os
import sys
import yum
import logging
from yum.constants import *

from yumgui import doGtkEvents

# yum callback handlers


def _(text):
    return text



class RPMInstallCallback:
    ''' Generic RPM callback abstract class based on the one used in yum 
    The RPM callback loop in passed on into function there can be overloaded.
    '''
    def __init__( self,logger=None ):
        self.callbackfilehandles = {}
        self.total_actions = 0
        self.total_installed = 0
        self.installed_pkg_names = []
        self.total_removed = 0
        self.mark = "#"
        self.marks = 27
        self.logger = logger
        
        if yum.__version__ < '2.5.0':
            self.myprocess = { 'updating': 'Updating', 'erasing': 'Erasing',
                           'installing': 'Installing', 'obsoleted': 'Obsoleted',
                           'obsoleting': 'Installing'}
            self.mypostprocess = { 'updating': 'Updated', 'erasing': 'Erased',
                               'installing': 'Installed', 'obsoleted': 'Obsoleted',
                               'obsoleting': 'Installed'}

        else:
            self.myprocess = { TS_UPDATE : _( 'Updating' ), 
                           TS_ERASE: _( 'Erasing' ), 
                           TS_INSTALL: _( 'Installing' ), 
                           TS_TRUEINSTALL : _( 'Installing' ), 
                           TS_OBSOLETED: _( 'Obsoleted' ), 
                           TS_OBSOLETING: _( 'Installing' )}
            self.mypostprocess = { TS_UPDATE: _( 'Updated' ), 
                               TS_ERASE: _( 'Erased' ), 
                               TS_INSTALL: _( 'Installed' ), 
                               TS_TRUEINSTALL: _( 'Installed' ), 
                               TS_OBSOLETED: _( 'Obsoleted' ), 
                               TS_OBSOLETING: _( 'Installed' )}

        self.tsInfo = None # this needs to be set for anything else to work

    def _dopkgtup( self, hdr ):
        tmpepoch = hdr['epoch']
        if tmpepoch is None: epoch = '0'
        else: epoch = str( tmpepoch )

        return ( hdr['name'], hdr['arch'], epoch, hdr['version'], hdr['release'] )

    def _makeHandle( self, hdr ):
        handle = '%s:%s.%s-%s-%s' % ( hdr['epoch'], hdr['name'], hdr['version'], 
          hdr['release'], hdr['arch'] )

        return handle

    def _localprint( self, msg ):
        if self.logger:
            self.logger.debug(msg)
            
    def _percent( self, total, bytes ):
       if total == 0:
           percent = 0
       else:
           percent = ( bytes*100L )/total
       return percent
       
    def _process( self, hdr ):
        process = None
        pkgtup = self._dopkgtup( hdr )
        txmbr = self.tsInfo.getMembers( pkgtup=pkgtup )[0]
        try:
            process = self.myprocess[txmbr.output_state]
        except KeyError, e:
            print "Error: invalid output state: %s for %s" % \
               ( txmbr.output_state, hdr['name'] )
        return process

    def _postProcess( self, hdr ):
        postprocess = None
        pkgtup = self._dopkgtup( hdr )
        txmbr = self.tsInfo.getMembers( pkgtup=pkgtup )[0]
        try:
            postprocess = self.mypostprocess[txmbr.output_state]
        except KeyError, e:
            print "Error: invalid output state: %s for %s" % \
               ( txmbr.output_state, hdr['name'] )
        return postprocess
        

    def _logPkgString( self, hdr ):
        """return nice representation of the package for the log"""
        ( n, a, e, v, r ) = self._dopkgtup( hdr )
        if e == '0':
            pkg = '%s.%s %s-%s' % ( n, a, v, r )
        else:
            pkg = '%s.%s %s:%s-%s' % ( n, a, e, v, r )
        
        return pkg

    def callback( self, what, bytes, total, h, user ):
        doGtkEvents()
        if what == rpm.RPMCALLBACK_TRANS_START:
            self.transStart( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_TRANS_PROGRESS:
            self.transProgress( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_TRANS_STOP:
            self.transProgress( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_INST_OPEN_FILE:
            return self.instOpenFile( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            self.instCloseFile( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_INST_PROGRESS:
            self.instProgress( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_UNINST_START:
            self.unInstStart( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_UNINST_PROGRESS:
            self.unInstProgress( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_UNINST_STOP:
            self.unInstStop( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_REPACKAGE_START:
            self.rePackageStart( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_REPACKAGE_STOP:
            self.rePackageStop( what, bytes, total, h, user )
        elif what == rpm.RPMCALLBACK_REPACKAGE_PROGRESS:
            self.rePackageProgress( what, bytes, total, h, user )

    def transStart( self, what, bytes, total, h, user ):
        if bytes == 6:
            self.total_actions = total
        
    def transProgress( self, what, bytes, total, h, user ):
        pass
        
        
    def transStop( self, what, bytes, total, h, user ):
        pass

    def instOpenFile( self, what, bytes, total, h, user ):
        hdr = None
        if h is not None:
            hdr, rpmloc = h
            handle = self._makeHandle( hdr )
            fd = os.open( rpmloc, os.O_RDONLY )
            self.callbackfilehandles[handle]=fd
            self.total_installed += 1
            self.installed_pkg_names.append( hdr['name'] )
            return fd
        else:
            self._localprint( _( "No header - huh?" ) )


    def instCloseFile( self, what, bytes, total, h, user ):
        hdr = None
        if h is not None:
            hdr, rpmloc = h
            handle = self._makeHandle( hdr )
            os.close( self.callbackfilehandles[handle] )
            fd = 0

        
    def instProgress( self, what, bytes, total, h, user ):
        pass
        

    def unInstStart( self, what, bytes, total, h, user ):
        pass

    def unInstProgress( self, what, bytes, total, h, user ):
        pass

    def unInstStop( self, what, bytes, total, h, user ):
        self.total_removed += 1                  

    def rePackageStart( self, what, bytes, total, h, user ):
        pass
        
    def rePackageProgress( self, what, bytes, total, h, user ):
        pass
        
    def rePackageStop( self, what, bytes, total, h, user ):
        pass
        

        