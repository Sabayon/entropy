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

import sys
import os
import re
import gtk
import rpm
import logging
from urlgrabber.progress import *

# Yumex imports
from misc import const
from yumgui.callbacks import RPMInstallCallback
from yumgui import *
from i18n import _

          
class YumexDownloadProgress( BaseMeter ):
    """ Customized version of progress.BaseMeter class """
    def __init__( self, progress ):
        BaseMeter.__init__( self )
        self.progress = progress
        self.totSize = ""
        self.downloadTotal = 0.0
        self.downloadNow = 0.0
        self.logger = logging.getLogger( 'yumex.YumexCallbacks' )   
     
    def clearStats( self ):
        self.downloadTotal = 0.0
        self.downloadNow = 0.0
         
    def setStats( self, total ):
        self.downloadTotal = total
        self.downloadNow = 0.0
          
    def update( self, amount_read, now=None ):
        BaseMeter.update( self, amount_read, now )           

    def _do_start( self, now=None ):
        if self.progress != None:
            self.progress.show() 
            text = self.basename
            if self.text is not None:
                if type( self.text ) == type( "" ):
                    text = self.text
            self.progress.set_progress( 0, " " )
            self.progress.set_extraLabel( text )
            self.progress.set_etaLabel( "" )
            if not self.size is None:
                self.totSize = format_number( self.size )
            if self.url:
                self.logger.debug( _( "Getting : %s" ) % self.url )
                
                
                

    def _do_update( self, amount_read, now=None ):
        etime = self.re.elapsed_time()
        fetime = format_time( etime )
        fread = format_number( amount_read )
        if self.downloadTotal > 0:
            now = self.downloadNow + amount_read
            self.progress.setTotal( now, self.downloadTotal )
        if self.text is not None:
            text = self.text
        else:
            text = self.basename
          
        if self.size is None:
              out = '%s' % ( text )
              eta = '%5sB %s' % ( fread, fetime )
               
              frac = 0.0
        else:
              rtime = self.re.remaining_time()
              frtime = format_time( rtime )
              frac = self.re.fraction_read()
              out = '%s' % ( text )
              eta = '%5sB/%5sB %8s ETA' % ( fread, self.totSize, frtime )
        if self.progress != None:
            percent  = "%3i%%" % int( frac*100 )
            self.progress.set_progress( frac, percent )
            self.progress.set_extraLabel( out )
            self.progress.set_etaLabel( eta )
              

    def _do_end( self, amount_read, now=None ):
        if self.downloadTotal> 0:
            if amount_read == self.size: # check if whole file has been downloaded
                self.downloadNow += amount_read 
        total_time = format_time( self.re.elapsed_time() )
        total_size = format_number( amount_read )
        if self.text is not None:
              text = self.text
        else:
              text = self.basename
        if self.progress != None:
            self.progress.set_progress( 1.0, "%3i%%" % 100 )
            self.progress.set_extraLabel( text )
            self.progress.set_etaLabel( "" )



class YumexRPMCallback( RPMInstallCallback ):

    def __init__( self, progress=None, filelog=None ):
        self.logger = logging.getLogger( 'yumex.yumexRPMCallback' )
        self.filelog = filelog
        RPMInstallCallback.__init__( self, self.logger )
        self.progress = progress
    
    def _makedone( self ):
        l = len( str( self.total_actions ) )
        size = "%s.%s" % ( l, l )
        fmt_done = "[%" + size + "s/%" + size + "s]"
        done = fmt_done % ( self.total_installed + self.total_removed, 
                           self.total_actions )
        return done       


    def instProgress( self, what, bytes, total, h, user ):
        hdr, rpmloc = h
        process =  self._process( hdr )
        out = "%s : %s" % ( process, hdr['name'] )
        self.progress.set_extraLabel( out )
        eta = self._makedone()
        self.progress.set_etaLabel( eta )
        percent = self._percent( total, bytes )
        now = float( self.total_installed-1 + self.total_removed )+float( percent )/100
        self.progress.setTotal( now, self.total_actions )
        self.progress.set_progress( float( percent )/100, "%3i%%" % percent )

    def instCloseFile( self, what, bytes, total, h, user ):
        RPMInstallCallback.instCloseFile( self, what, bytes, total, h, user )
        if h is not None:
            hdr, rpmloc = h
            if self.filelog:
                process = self._process( hdr )
                processed = self._postProcess( hdr )
                pkgrep = self._logPkgString( hdr )
                msg = '%s: %s' % ( processed, pkgrep )
                self.filelog.info( msg )


    def unInstStart( self, what, bytes, total, h, user ):
        if h not in self.installed_pkg_names:
            process = _( "Removing" )
        else:
            process = _( "Cleanup" )
        out = "%s : %s" % ( process, h )
        self.progress.set_extraLabel( out )
        eta = self._makedone()
        self.progress.set_etaLabel( eta )

    def unInstProgress( self, what, bytes, total, h, user ):
        percent = self._percent( total, bytes )
        now = float( self.total_installed + self.total_removed )+float( percent )/100
        self.progress.setTotal( now, self.total_actions )
        self.progress.set_progress( float( percent )/100, "%3i%%" % percent )
        
    def unInstStop( self, what, bytes, total, h, user ):
        RPMInstallCallback.unInstStop( self, what, bytes, total, h, user )
        percent = self._percent( total, bytes )
        now = float( self.total_installed + self.total_removed )+float( percent )/100
        self.progress.setTotal( now, self.total_actions )
        if h not in self.installed_pkg_names:
            logmsg = _( 'Erased: %s' % ( h ) )
            if self.filelog:
                self.filelog.info( logmsg )
        
        

class YumexCacheProgressCallback:

     '''
     The class handles text output callbacks during metadata cache updates.
     '''
     
     def __init__( self, progress ):
         self.logger = logging.getLogger('yumex.CacheCallback')
         self.progress = progress
            
     def progressbar( self, current, total, name=None ):
        if current == 1:
            self.logger.info( "Loading metadata from : %s" % name )
            if self.progress != None:
                if name:
                    self.progress.set_extraLabel( _( "Processing metadata from : %s" ) % name )
                else:
                    self.progress.set_extraLabel( _( "Processing metadata" ) )
                self.progress.set_etaLabel( "" )
                
        else:
            if self.progress != None:
                if current % 10 == 0 or current == total:
                    if total != 0:
                         frac = float( current )/float( total )
                    else:
                         frac = 0.0                    
                    txt = "%i/%i" % ( current, total )
                    self.progress.set_progress( frac, txt )                       


# This class was copied from /usr/share/yum-cli/output.py    
# The output string is made translateable

class YumexDepSolveProgressCallBack:
    """provides text output callback functions for Dependency Solver callback"""
    
    def __init__( self):
        """requires yum-cli log and errorlog functions as arguments"""
        self.logger = logging.getLogger('yumex.DepSolveCallback')
        self.loops = 0
  
            
    def pkgAdded( self, pkgtup, mode ):
        modedict = { 'i': 'installed', 
                     'u': 'updated', 
                     'o': 'obsoleted', 
                     'e': 'erased'}
        ( n, a, e, v, r ) = pkgtup
        modeterm = modedict[mode]
        msg = _( '---> Package %s.%s %s:%s-%s set to be %s' ) % ( n, a, e, v, r, modeterm )
        self.logger.info( msg )
        
    def start( self ):
        self.loops += 1
        
    def tscheck( self ):
        self.logger.info( _( '--> Running transaction check' ) )
        
    def restartLoop( self ):
        self.loops += 1
        self.logger.info( _( '--> Restarting Dependency Resolution with new changes.' ) )
        self.logger.debug( '---> Loop Number: %d' % self.loops )
    
    def end( self ):
        self.logger.info( _( '--> Finished Dependency Resolution' ) )

    
    def procReq( self, name, formatted_req ):
        msg = _( '--> Processing Dependency: %s for package: %s' ) % ( formatted_req, name )
        self.logger.info( msg )
        
    
    def unresolved( self, msg ):
        self.logger.info( _( '--> Unresolved Dependency: %s' ) % msg )

    
    def procConflict( self, name, confname ):
        self.logger.info( _( '--> Processing Conflict: %s conflicts %s' ) % ( name, confname ) )

    def transactionPopulation( self ):
        self.logger.info( _( '--> Populating transaction set with selected packages. Please wait.' ) )
    
    def downloadHeader( self, name ):
        msg = _( '---> Downloading header for %s to pack into transaction set.' ) % name
        self.logger.info( msg )
