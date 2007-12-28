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

import logging

import yum
import yum.Errors as Errors
from yum.update_md import UpdateMetadata

from misc import const,cleanMarkupSting
from i18n import _
from yumgui import format_number
from packages import YumexPackages
from callbacks import *
from dialogs import questionDialog
from urlgrabber.grabber import URLGrabError


class YumexYumHandler(yum.YumBase,YumexPackages):
    def __init__(self,recent,settings,progress,mainwin,parser):
        yum.YumBase.__init__(self)
        YumexPackages.__init__(self)
        self.yumex_logger = logging.getLogger("yumex.YumHandler")
        self.filelog = logging.getLogger( "yum.filelogging" ) 
        self.recent = recent
        self.settings = settings  
        self.progress = progress
        self.mainwin = mainwin
        self.downloadProgress = YumexDownloadProgress(self.progress )
        self.dsCallback = YumexDepSolveProgressCallBack()
        # yum config setup
        self.doConfigSetup(fn=self.settings.conffile,init_plugins=self.settings.plugins,
                           plugin_types=( yum.plugins.TYPE_CORE, ),
                           debuglevel = self.settings.yumdebuglevel,
                           optparser = parser )
        self.filelog = logging.getLogger( "yum.filelogging" )
        self.doLock( const.YUM_PID_FILE )       
        self._setup_excludes() # Add yumex excludes to excludelist
        self.repos.callback = YumexCacheProgressCallback(self.progress)
        self.repos.setProgressBar( self.downloadProgress )       
        # Setup failure callback
        freport = ( self._failureReport, (), {} )
        self.repos.setFailureCallback( freport )       
        self.updateMetadata = UpdateMetadata()        
        self.yumex_logger.info("Yum Version : %s" % yum.__version__)        
        self.isSetup = False
        
    def _setupBase(self):
        ''' Basic Yum Setup '''
        self.progress.show()
        self.progressLog( _( "Setup Yum : Transaction Set" ) )
        self.doTsSetup()
        self.progressLog( _( "Setup Yum : RPM Db." ) )
        self.doRpmDBSetup()
        self.progress.total.next() # -> Repo Setup
        self.progressLog( _( "Setup Yum : Repositories." ) )
        self.doRepoSetup()
        self.progress.total.next() # -> Sack Setup
        self.progressLog( _( "Setup Yum : Package Sacks" ) )
        self.doSackSetup()
        self.progress.total.next() # -> Updates Setup
        self.progressLog( _( "Setup Yum : Updates" ) )
        self.doUpdateSetup()
        self._setupUpdateMetadata()        
        self.progress.total.next() # -> Group Setup
        self.progressLog( _( "Setup Yum : Groups" ) )
        self.doGroupSetup()      
        self.progressLog( _( "Setup Yum : Base setup completed" ) )
        self.isSetup = True

    def cleanup( self ):
        """ Clean out datastructures, so setup can be called again. """
        # Kill old RepoStorage and make new one.
        if yum.__version__ < '3.1.0':
            self.repos = yum.repos.RepoStorage()   
            # load repos into storage
            self.getReposFromConfig()
        # FIXME: this is some ugly shit    
        elif yum.__version__ < '3.2.1': 
            self.repos.repos =  {}
            del self.repos 
        else:
            self._repos = yum.repos.RepoStorage(self)   
            self.getReposFromConfig()

        # Kill the current pkgSack    
        if self.pkgSack:
            self.pkgSack=None
            
                
        self.closeRpmDB()
        self.isSetup = False
        

    def _setupAgain(self):    
        self.progress.show()
        self.closeRpmDB()
        self.progressLog( _( "Setup Yum : Transaction Set" ) )
        self.doTsSetup()
        self.progressLog( _( "Setup Yum : RPM Db." ) )
        self.doRpmDBSetup()
        self.progress.total.next() # -> Repo Setup
        self.progressLog( _( "Setup Yum : Repositories." ) )
        self.doRepoSetup()
        self.progress.total.next() # -> Sack Setup
        self.progressLog( _( "Setup Yum : Package Sacks" ) )
        self.doSackSetup()
        self.progress.total.next() # -> Sack Setup
        self.progressLog( _( "Setup Yum : Updates" ) )
        self.doUpdateSetup()        
        self.progress.total.next() # -> Sack Setup
        self.progressLog( _( "Setup Yum : Groups" ) )
        self.doGroupSetup()      
        self.progressLog( _( "Setup Yum : Base setup completed" ) )
        self.clearPackages()  # Force YumexPackages to repopulate
        self.isSetup = True

    def _setupUpdateMetadata(self):
        for repo in self.repos.listEnabled():
            try: # attempt to grab the updateinfo.xml.gz from the repodata
                self.updateMetadata.add(repo)
                self.yumex_logger.info(_("Loaded update Metadata from %s ") % repo.id)
            except yum.Errors.RepoMDError:
                self.yumex_logger.debug(_("No update Metadata found for %s ") % repo.id)

    def _resetTs(self):
        '''Clear the current tsInfo Transaction Set'''
        # clear current tsInfo, we want a empty one.
        # FIXME: Ugly hack, remove when yum 3.2.1 is released.
        if hasattr(self,"dcobj"):
            del self.dcobj
        # FIXME: This is crap, but it needed to work with
        # both current and old yum releases.    
        if hasattr(self,'_tsInfo'):
            self._tsInfo = None
        else:    
            del self.tsInfo
            self.tsInfo = self._transactionDataFactory()
            self.initActionTs()
        
    def _prepareTransaction(self,pkgs,updateAll = False):
        self._resetTs()
        self.yumex_logger.info( _( "Preparing for install/remove/update" ) )        
        try:
            # Install
            if len(pkgs['i'])> 0:
                self.yumex_logger.info(_( "--> Preparing for install" ) )
                for po in pkgs['i']:
                    tx = self.install( po.pkg )
            # Remove
            if len(pkgs['r'])> 0:
                self.yumex_logger.info( _( "--> Preparing for remove" ) )
                for po in pkgs['r']:
                    tx = self.remove( po.pkg )
            # Update
            # Check if full update or partial
            if len(pkgs['u'])> 0:
                if len(self.getPackages('updates')) == len(pkgs['u']):
                    self.yumex_logger.info( _( "--> Preparing for a full update" ) )
                    tx = self.update()
                else:
                    self.yumex_logger.info( _( "--> Preparing for a partial update" ) )
                    if self.settings.fullobsoletion:
                        self.yumex_logger.info( _( "--> Adding all obsoletion to transaction" ) )
                        self._doFullObsoletion()
                    for po in pkgs['u']:
                        tx = self.update( po.pkg )
            return self.buildTransaction() 
        except yum.Errors.YumBaseError, e:
            return 1, [str( e )]          
        
    def _doFullObsoletion( self ):
        # Handle obsoletes:
        if self.conf.obsoletes:
            obsoletes = self.up.getObsoletesTuples( newest=1 )
            for ( obsoleting, installed ) in obsoletes:
                obsoleting_pkg = self.getPackageObject( obsoleting )
                installed_pkg =  self.rpmdb.searchPkgTuple( installed )[0]                           
                self.tsInfo.addObsoleting( obsoleting_pkg, installed_pkg )
                self.tsInfo.addObsoleted( installed_pkg, obsoleting_pkg )

    def _getTransactionList( self ):
        list = []
        sublist = []
        self.tsInfo.makelists()        
        for ( action, pkglist ) in [( _( 'Installing' ), self.tsInfo.installed ), 
                            ( _( 'Updating' ), self.tsInfo.updated ), 
                            ( _( 'Removing' ), self.tsInfo.removed ), 
                            ( _( 'Installing for dependencies' ), self.tsInfo.depinstalled ), 
                            ( _( 'Updating for dependencies' ), self.tsInfo.depupdated ), 
                            ( _( 'Removing for dependencies' ), self.tsInfo.depremoved )]:
            for txmbr in pkglist:
                ( n, a, e, v, r ) = txmbr.pkgtup
                evr = txmbr.po.printVer()
                repoid = txmbr.repoid
                pkgsize = float( txmbr.po.size )
                size = format_number( pkgsize )
                alist=[]
                for ( obspo, relationship ) in txmbr.relatedto:
                    if relationship == 'obsoletes':
                        appended = 'replacing  %s.%s %s' % ( obspo.name, 
                            obspo.arch, obspo.printVer() )
                        alist.append( appended )
                el = ( n, a, evr, repoid, size, alist )
                sublist.append( el )
            if pkglist:
                list.append( [action, sublist] )
                sublist = []
        return list        

    def _getTransactionSize( self , asFloat=False ):       
        totsize = 0
        for txmbr in self.tsInfo.getMembers():
            if txmbr.ts_state in ['i', 'u']:
                po = self.getPackageObject( txmbr.pkgtup )
                if po:
                    size = int( po.size )
                    totsize += size
        if asFloat:
            return  float( totsize )
        else:
            return format_number( float( totsize ) )
 
    def _getDownloadSize( self ):
        totsize = 0
        for txmbr in self.tsInfo.getMembers():
            if txmbr.ts_state in ['i', 'u']:
                po = txmbr.po
                if po:
                    size = int( po.size )
                    totsize += size
        return float( totsize )

    def _failureReport( self, errobj ):
        """failure output for failovers from urlgrabber"""
        
        self.yumex_logger.error( _( 'Failure getting %s: ' ), errobj.url )
        lines = str( errobj.exception ).split( '\n' )
        #print lines
        for line in lines:
            self.yumex_logger.error( '  --> %s' % line )
        self.yumex_logger.error( 'Trying other mirror.' )
        raise errobj.exception

    def _interrupt_callback(self, cbobj):
        '''Handle CTRL-C's during downloads

        If a CTRL-C occurs a URLGrabError will be raised to push the download
        onto the next mirror.  
        
        @param cbobj: urlgrabber callback obj
        '''
        # Go to next mirror
        raise URLGrabError(15, 'user interrupt')
        
        
    def _downloadPackages(self):
        """ Downloading packages and check GPG Signature """
        self.progressLog( _( 'Downloading Packages:' ) )
        downloadpkgs = []
        for txmbr in self.tsInfo.getMembers():
            if txmbr.ts_state in ['i', 'u']:
                po = txmbr.po
                if po:
                    downloadpkgs.append( po )
    
        #self.log( 2, 'Downloading Packages:' )
        self.downloadProgress.setStats( self._getDownloadSize() ) 
        try:
            problems = self.downloadPkgs( downloadpkgs ) 
        except SystemExit,e: # Quit
            raise SystemExit
        except: # handle tracebacks error in yum & urlgrapper
            errstring = ''
            errstring += _( 'Error Downloading Packages:\n' )
            for err in sys.exc_info():
                errstring += str( err )
            raise yum.Errors.YumBaseError( errstring )
            
        self.downloadProgress.clearStats()
        if len( problems.keys() ) > 0:
            errstring = ''
            errstring += _( 'Error Downloading Packages:\n' )
            for key in problems.keys():
                errors = yum.misc.unique( problems[key] )
                for error in errors:
                    errstring += '  %s: %s\n' % ( key, error )
                raise yum.Errors.YumBaseError( errstring )
                  # Check GPG signatures
        self.progressLog( _( 'Checking GPG Signatures:' ) )
        try:
            self.gpgsigcheck( downloadpkgs )
        except Errors.YumBaseError, errmsg: # Handle gpg errors
            errstring = ''
            errstring += _( 'Error checking package signatures:\n' )
            errstring += str(errmsg)
            raise yum.Errors.YumBaseError( errstring )
            
        except: # handle tracebacks error in yum & urlgrapper
            errstring = ''
            errstring += _( 'Traceback in checking package signatures:\n' )
            for err in sys.exc_info():
                errstring += str( err )
            raise yum.Errors.YumBaseError( errstring )

    def _doTransactionTest(self):
        """ Do Traaction Test"""
        self.progressLog( _( 'Running Transaction Test' ))
        tsConf = {}
        for feature in ['diskspacecheck']: # more to come, I'm sure
            tsConf[feature] = getattr( self.conf, feature )
        #
        testcb = YumexRPMCallback( progress=self.progress )
        testcb.tsInfo = self.tsInfo
        # clean out the ts b/c we have to give it new paths to the rpms 
        del self.ts
  
        self.initActionTs()
        # save our dsCallback out
        dscb = self.dsCallback
        self.dsCallback = None # dumb, dumb dumb dumb!
        self.populateTs( keepold=0 ) # sigh
        tserrors = self.ts.test( testcb, conf=tsConf )
        del testcb
  
        self.progressLog( _( 'Finished Transaction Test' ))
        if len( tserrors ) > 0:
            errstring = _( 'Transaction Check Error: ' )
            for descr in tserrors:
                 errstring += '  %s\n' % descr 
            raise yum.Errors.YumBaseError( errstring ) 

        self.progressLog( _( 'Transaction Test Succeeded' ))
        del self.ts
        # put back our depcheck callback
        self.dsCallback = dscb
        pass

    def _runTransaction(self):
        self.initActionTs() # make a new, blank ts to populate
        self.populateTs( keepold=0 ) # populate the ts
        self.ts.check() #required for ordering
        self.ts.order() # order
        output = 1
        cb = YumexRPMCallback( progress=self.progress, filelog=self.filelog )
        cb.filelog = self.filelog # needed for log file output
        cb.tsInfo = self.tsInfo

        self.progressLog( _( 'Running Transaction' ) )
        self.runTransaction( cb=cb )

        # close things
        self._listPostTransaction()

    def _listPostTransaction(self):
        self.tsInfo.makelists()
        for (action, pkglist) in [('Removed', self.tsInfo.removed), 
                                  ('Dependency Removed', self.tsInfo.depremoved),
                                  ('Installed', self.tsInfo.installed), 
                                  ('Dependency Installed', self.tsInfo.depinstalled),
                                  ('Updated', self.tsInfo.updated),
                                  ('Dependency Updated', self.tsInfo.depupdated),
                                  ('Replaced', self.tsInfo.obsoleted)]:
            
            if len(pkglist) > 0:
                self.yumex_logger.info('%s:' % action)
                for txmbr in pkglist:
                    self.yumex_logger.info(' --> %s' % str(txmbr.po))

    def _setup_excludes( self ):
        """ Append the yumex excludes to the yum exclude list """
        try:
            excludelist = self.conf.exclude
            for ex in self.settings.exclude:
                excludelist.append( ex )
            self.conf.exclude = excludelist
        except yum.Errors.ConfigError, e:
            self.yumex_logger.error( e )
                   
    def progressLog(self,msg):
        self.yumex_logger.info(msg)
        self.progress.set_subLabel( msg )
        self.progress.set_progress( 0, " " ) # Blank the progress bar.

# Overloaded Methods from YumBase.
       
    def doGroupSetup(self):
        ''' Dont fail if no groups'''
        try:
            # call perent doGroupSetup
            yum.YumBase.doGroupSetup(self)    
        except Errors.GroupsError,e:
            self.yumex_logger.error(e)
        except Errors.CompsException,e:
            self.yumex_logger.error(e)
            
    def doSackSetup(self):      
        yum.YumBase.doSackSetup(self)      
        if self.settings.filelist:
            self.repos.populateSack(mdtype='filelists')      
        if self.settings.changelog:
            self.repos.populateSack(mdtype='otherdata')
        
    
    def gpgsigcheck(self, pkgs):
        '''Perform GPG signature verification on the given packages, installing
        keys if possible

        Returns non-zero if execution should stop (user abort).
        Will raise YumBaseError if there's a problem
        '''
        for po in pkgs:
            result, errmsg = self.sigCheckPkg(po)

            if result == 0:
                # Verified ok, or verify not req'd
                continue            

            elif result == 1:
               # the callback here expects to be able to take options which
               # userconfirm really doesn't... so fake it
               self.getKeyForPackage(po, self._askForGPGKeyImport)

            else:
                # Fatal error
                raise yum.Errors.YumBaseError, errmsg

        return 0
        
    def _askForGPGKeyImport(self, po, userid, hexkeyid):
        ''' ask callback for GPG Key import '''
        #print "po: %s userid: %s hexkey: %s " % (str(po),userid,hexkeyid)
        msg =  _('Do you want to import GPG Key : %s \n') % hexkeyid 
        msg += "  %s \n" % userid
        msg += _("Needed by %s") % str(po)
        print msg
        return questionDialog(self.mainwin, msg)
        
    def dumpTsInfo(self):
        for txmbr in self.tsInfo:        
            print str(txmbr)
            print " current_state = %s" % txmbr.current_state
            print " output_state  = %s" % txmbr.output_state
            print " po.state      = %s" % txmbr.po.state
            print " ts_state      = %s" % txmbr.ts_state
            print " relatedto     = %s" % txmbr.relatedto
            print " isDep         = %s" % txmbr.isDep
            
# methods from yum output.py

    def postTransactionOutput(self):
        out = ''
        
        self.tsInfo.makelists()

        for (action, pkglist) in [('Removed', self.tsInfo.removed), 
                                  ('Dependency Removed', self.tsInfo.depremoved),
                                  ('Installed', self.tsInfo.installed), 
                                  ('Dependency Installed', self.tsInfo.depinstalled),
                                  ('Updated', self.tsInfo.updated),
                                  ('Dependency Updated', self.tsInfo.depupdated),
                                  ('Replaced', self.tsInfo.obsoleted)]:
            
            if len(pkglist) > 0:
                out += '\n%s:' % action
                for txmbr in pkglist:
                    (n,a,e,v,r) = txmbr.pkgtup
                    msg =  "--> %s.%s %s:%s-%s \n" % (n,a,e,v,r)
                    out += msg
        
        return out
        
