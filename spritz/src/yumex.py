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

# Base Python Imports
import sys,os

import time
import logging
import traceback


# GTK Imports
import gtk,gobject
from threading import Thread,Event
import thread
import exceptions
# Other Imports
import yum
import yum.Errors as Errors
from yumgui.widgets import UI, Controller
from yumgui import *

# yumex imports
import filters
from yumapi import YumexYumHandler
from gui import YumexGUI
from dialogs import *
from misc import const,YumexOptions,YumexRepoList,YumexProfile
from i18n import _
from packages import RPMGroupTree
       
class YumexController(Controller):
    ''' This class contains all glade signal callbacks '''
    
    
    def __init__( self ):
         self.yumbase = None
         # Create and ui object contains the widgets.
         ui = UI( const.GLADE_FILE , 'main', 'yumex' )
         # init the Controller Class to connect signals.
         Controller.__init__( self, ui )

         
    def quit(self, widget=None, event=None ):
        ''' Main destroy Handler '''
        if self.rpmTransactionIsRunning:
            self.logger.critical(_('Cant Quit while running RPM Transactions'))
            return True # Dont quit
        gtkEventThread.doQuit()        
        if self.isWorking:
            self.quitNow = True
            self.logger.critical(_('Quiting, please wait !!!!!!'))
            time.sleep(3)
            self.exitNow()               
            return False
        else:
            self.exitNow()   
            return False

    def exitNow(self):
        self.yumbase.doUnlock( const.YUM_PID_FILE )  
        try:
            gtk.main_quit()       # Exit gtk
        except RuntimeError,e:
            pass
        sys.exit( 1 )         # Terminate Program
        
    def on_PageButton_changed( self, widget, page ):
        ''' Left Side Toolbar Handler'''
        self.setNotebookPage(const.PAGES[page])
        
    def on_category_selected(self,widget):
        ''' Category Change Handler '''
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            category = model.get_value( iterator, 1 )
            if category != '':
                self.addCategoryPackages(category)
            else:
                self.pkgView.store.clear()
                
        
    def on_Category_changed(self,widget):
        ''' Category Type Change Handler'''
        ndx = self.ui.cbCategory.get_active()
        if ndx == 0: # None
           self.categoryOn = False
           self.packageInfo.clear()
           self.ui.swCategory.hide()
           self.addPackages() 
        else:
           self.categoryOn = True
           self.ui.swCategory.show()
           self.packageInfo.clear()
           tub = const.PACKAGE_CATEGORY_DICT[ndx]
           (label,fn,attr,sortcat,splitcat) = tub
           self.addCategories(fn,attr,sortcat,splitcat)           
           
        
    def on_pkgFilter_toggled(self,rb,action):
        ''' Package Type Selection Handler'''
        if rb.get_active(): # Only act on select, not deselect.
            rb.grab_add()                    
            self.packageInfo.clear()
            self.lastPkgPB = action
            # Only show add/remove all when showing updates
            if action == 'updates':
                self.ui.pkgSelect.show()
                self.ui.pkgDeSelect.show()
            else:
                self.ui.pkgSelect.hide()
                self.ui.pkgDeSelect.hide()
                
            if self.yumbase.currentCategory:
                self.on_Category_changed(None)
            else:
                self.addPackages()                
            rb.grab_remove()                    

    def on_repoRefresh_clicked(self,widget):
        repos = self.repoView.get_selected()
        self.setPage('output')
        self.logger.info( "Enabled repositories : %s" % ",".join(repos))
        self.repoList.clear() # Reset Repositories
        self.repoList.enableOnly(repos)        
        self.setupYum()

    def on_repoDeSelect_clicked(self,widget):
        self.repoView.deselect_all()

        
    def on_queueDel_clicked( self, widget ):
        """ Delete from Queue Button Handler """
        self.queueView.deleteSelected()

    def on_queueQuickAdd_activate(self,widget):
        if self.initYum: # Yum has to be initialised
            txt = widget.get_text()
            arglist = txt.split(' ')
            self.doQuickAdd(arglist[0],arglist[1:])
        else:
            self.setStatus(_('Yum has not been initialized yet'))
            widget.set_text('')
        
    def on_queueProcess_clicked( self, widget ):
        """ Process Queue Button Handler """
        if self.queue.total() == 0: # Check there are any packages in the queue
            self.setStatus(_('No packages in queue'))
            return
        self.queue.dump()
        fn = '/tmp/last-queue.yumex'
        cp = self.queue.getParser()
        fp = open(fn,"w")
        cp.save(fp)
        fp.close()

        rc = self.processPackageQueue(self.queue.packages)
        if rc:
            if rc == 'QUIT':
                self.quit()
            else:
                self.queue.clear()       # Clear package queue    
                self.queueView.refresh() # Refresh Package Queue 
                self.setupYum()

    def on_queueSave_clicked( self, widget ):
        dialog = gtk.FileChooserDialog(title=None,action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        dialog.set_current_folder("/tmp")
        dialog.set_current_name('queue.yumex')
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fn = dialog.get_filename()
        elif response == gtk.RESPONSE_CANCEL:
            fn = None
        dialog.destroy()
        if fn:
            self.logger.info("Saving queue to %s" % fn)
            cp = self.queue.getParser()
            fp = open(fn,"w")
            cp.save(fp)
            fp.close()

    def on_queueOpen_clicked( self, widget ):
        dialog = gtk.FileChooserDialog(title=None,action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        dialog.set_current_folder("/tmp")
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fn = dialog.get_filename()
        elif response == gtk.RESPONSE_CANCEL:
            fn = None
        dialog.destroy()
        if fn:
            self.logger.info("Loading queue from %s" % fn)
            cp = self.queue.getParser()
            fp = open(fn,"r")
            rc,msg = cp.load(fp)
            fp.close()
            print rc,msg
            found = 0
            total = 0
            f,t = self.doQueueAdd(cp,'update')
            found += f
            total += t
            f,t = self.doQueueAdd(cp,'install')
            found += f
            total += t
            f,t = self.doQueueAdd(cp,'remove')
            found += f
            total += t
            self.logger.info(' Loaded : %i of %i' % (found,total))
                
    def on_view_cursor_changed( self, widget ):
        """ Handle selection of row in package view (Show Descriptions) """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            pkg = model.get_value( iterator, 0 )
            if pkg:
                self.packageInfo.showInfo(pkg)

    def on_select_clicked(self,widget):
        ''' Package Add All button handler '''
        if len(self.pkgView.store) > 50:
            msg = _('You are about to add %s packages\n') % len(self.pkgView.store)
            msg += _('It will take some time\n')
            msg += _('do you want to continue ?')
            if not questionDialog(self.ui.main,msg):
                return
        busyCursor(self.ui.main)
        self.pkgView.selectAll()        
        normalCursor(self.ui.main)
        
    def on_deselect_clicked(self,widget):
        ''' Package Remove All button handler '''
        if len(self.pkgView.store) > 50:
            msg = _('You are about to remove %s packages\n') % len(self.pkgView.store)
            msg += _('It will take some time\n')
            msg += _('do you want to continue ?')
            if not questionDialog(self.ui.main,msg):
                return
        busyCursor(self.ui.main)
        self.pkgView.deselectAll()        
        normalCursor(self.ui.main)

    def on_skipMirror_clicked(self,widget):
        if self.skipMirror:
            self.logger.info('skipmirror')
            self.skipMirrorNow = True

    def on_search_clicked(self,widget):
        ''' Search entry+button handler'''
        txt = self.ui.pkgFilter.get_text()
        flt = filters.yumexFilter.get('KeywordFilter')
        if txt != '':
            flt.activate()
            lst = txt.split(' ')
            self.logger.debug('Search Keyword : %s' % ','.join(lst))
            flt.setKeys(lst)
        else:
            flt.activate(False)
        action = self.lastPkgPB  
        rb = self.packageRB[action]
        self.on_pkgFilter_toggled(rb,action)      

    def on_clear_clicked(self,widget):
        ''' Search Clear button handler'''
        self.ui.pkgFilter.set_text("")
        self.on_search_clicked(None)
        
    def on_schRepo_toggled(self,rb):  
        ''' Search Repo Checkbox handler'''
        if rb.get_active():
            self.ui.schRepoText.set_sensitive(True)
        else:
            self.ui.schRepoText.set_text("")
            self.ui.schRepoText.set_sensitive(False)
            self.on_schRepoText_activate(self.ui.schRepoText)
            
    def on_schArch_toggled(self,rb):      
        ''' Search Arch Checkbox handler'''
        if rb.get_active():
            self.ui.schArchText.set_sensitive(True)
        else:
            self.ui.schArchText.set_text("")
            self.ui.schArchText.set_sensitive(False)
            self.on_schArchText_activate(self.ui.schArchText)

    def on_schRepoText_activate(self,entry):      
        ''' Search Repo Entry handler'''
        txt = entry.get_text()
        flt = filters.yumexFilter.get('RepoFilter')
        if txt != '':
            flt.activate()
            lst = txt.split(',')
            self.logger.debug('Search Repo : %s' % ','.join(lst))
            flt.setFilterList(lst)
        else:
            flt.activate(False)
        action = self.lastPkgPB  
        rb = self.packageRB[action]
        self.on_pkgFilter_toggled(rb,action)      
            
            
    def on_schArchText_activate(self,entry):      
        ''' Search Arch Entry handler'''
        txt = entry.get_text()
        flt = filters.yumexFilter.get('ArchFilter')
        if txt != '':
            flt.activate()
            lst = txt.split(',')
            self.logger.debug('Search Arch : %s' % ','.join(lst))
            flt.setFilterList(lst)
        else:
            flt.activate(False)
        action = self.lastPkgPB  
        rb = self.packageRB[action]
        self.on_pkgFilter_toggled(rb,action)      

    def on_comps_cursor_changed(self, widget):
        """ Handle selection of row in Comps Category  view  """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            id = model.get_value( iterator, 2 )
            isCategory = model.get_value( iterator, 4 )
            if not isCategory:
                self.populateGroupPackages(id)

    def on_compsPkg_cursor_changed(self, widget):
        """ Handle selection of row in Comps Category  view  """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            pkg = model.get_value( iterator, 0 )
            if pkg:
                self.grpDesc.clear()
                self.grpDesc.write_line(pkg.description)            
 
            
# Menu Handlers

    def on_profile( self, data ):
        """ Profiles Menu Handler """
        self.setStatus( _( "Selected the %s profile" ) % data )
        self.profile.setActive(data)
        self.setupRepoView()        


    def on_FileQuit( self, widget ):
        self.quit()
    
    def on_EditPreferences( self, widget ):
        Preferences()
        self.yumexOptions.reload()
        self.settings = self.yumexOptions.settings       
        
    def on_HelpAbout( self, widget ):
        about = AboutDialog(const.PIXMAPS_PATH+'/yumex-about.png',const.CREDITS,self.settings.branding_title)
        about.show()
        
    def on_ProfileSave( self, widget ):
        repos = self.repoView.get_selected()
        if self.profile.writeProfile(repos):
            self.setStatus( _( "Profile : %s saved ok" ) % self.profile.getActive() )
        else:
            self.setStatus( _( "Profile : %s save failed" ) % self.profile.getActive() )
            
        
            
    def on_ProfileNew( self, widget ):
        name = inputBox(self.ui.main,_("Create New Profile"),_("Name of new profile"))
        if name:
            repos = self.repoView.get_selected()
            if self.profile.addProfile(name,repos):
                self.setStatus( _( "Profile : %s created ok" ) % name )
                self._addToProfileMenu(name,group=self.firstProfile)
            else:
                self.setStatus( _( "Profile : %s creation failed" ) % name )

    def on_ToolsRepoCache( self, widget ):
        if self.yumbase:
            self.logger.info(_('Cleaning up all yum metadata'))
            self.yumbase.cleanPackages()
            self.yumbase.cleanHeaders()
            self.yumbase.cleanMetadata()
            self.yumbase.cleanSqlite()            
            
                        
class YumexApplication(YumexController,YumexGUI):    

    def __init__(self):
        YumexController.__init__( self )
        self.yumexOptions = YumexOptions()
        self.yumexOptions.parseCmdOptions()
        self.settings = self.yumexOptions.settings
        YumexGUI.__init__(self)
        self.logger = logging.getLogger("yumex.main")
        # init flags
        self.rpmTransactionIsRunning = False
        self.skipMirror = False
        self.skipMirrorNow = False       
        self.doProgress = False
        self.categoryOn = False
        self.quitNow = False
        self.isWorking = False
        if self.settings.debug:
            self.yumexOptions.dump()
            print self.yumexOptions.getArgs()
        self.logger.info(_('Yum Config Setup'))
        self.yumbase = YumexYumHandler(self.getRecentTime(),self.settings,self.progress,self.ui.main,self.yumexOptions._optparser)
        self.yumexOptions.parseCmdOptions()
        # Let the plugins know the commandline options
        self.yumbase.plugins.setCmdLine(self.yumexOptions.cmd_options,
                                        self.yumexOptions.cmd_args)
        
        self.packageInfo.yumbase = self.yumbase
        self.compsView.yumbase = self.yumbase
        # Try to set the Logging application shown in syslog
        try:
            yum.logginglevels.setLoggingApp('yumex')
        except:
            pass
        # Setup GUI
        self.setupGUI()
        self.logger.info(_('GUI Setup Completed'))
        self.profile = YumexProfile()
        self.setupProfilesMenu()
        # setup Repositories
        self.repoList = YumexRepoList(self.yumbase)
        self.setupRepoView()
        self.firstTime = True
        # Adding Package filter fn.
        self.yumbase.setFilter(filters.yumexFilter.processFilters)
        self.initYum = False
        if self.settings.autorefresh:
            self.setupYum()
        else:
            self.setPage('repos')

    def startWorking(self):
        self.isWorking = True
        busyCursor(self.ui.main)        
        self.ui.progressVBox.grab_add()
        if not self.settings.nothreads:
            gtkEventThread.startProcessing()        
        
    def endWorking(self):
        self.isWorking = False
        self.ui.progressVBox.grab_remove()
        normalCursor(self.ui.main)
        if not self.settings.nothreads:
            gtkEventThread.endProcessing()
            
    def setupYum(self):
        self.setPage('output')
        self.startWorking()
        self.progress.total.setup( const.SETUP_PROGRESS_STEPS )        
        # Run yum setup in background thread
        try:
            if self.firstTime:
                self.yumbase._setupBase()
                self.firstTime = False
            else:
                self.yumbase._setupAgain()
        except Errors.YumBaseError, e:
            self.endWorking()
            errorMessage( self.ui.main, _( "Error" ), _( "Error in Yum Setup" ), str(e) )   
            self.logger.error(str(e))
            return         
        # prepare package lists
        self.progress.total.next() # -> List setup        
        self.progressLog(_('Building Package Lists'))
        self.yumbase.populatePackages(['installed','updates','available'])
        self.progressLog(_('Building Package Lists Completed'))
        self.progressLog(_('Building Groups Lists'))
        self.yumbase.buildGroups()
        self.populateGroupCategories()
        self.progressLog(_('Building Group Lists Completed'))
        # populate the package view
        self.doProgress = True
        self.addPackages()
        self.doProgress = False
        self.setPage('packages')
        self.initYum = True
        self.endWorking()
        
    
    def setupRepoView(self):
        self.repoList.setFilter(self.settings.repo_exclude)
        if self.profile.getActive() == 'yum-enabled':
            enablelist = self.repoList.getEnabledList()
        else:
            enablelist = self.profile.getProfile()
        data = self.repoList.getReposToView(enablelist)
        self.repoView.populate(data)
                
    def addPackages(self):
        if not self.yumbase or not self.yumbase.isSetup:
            return
        busyCursor(self.ui.main)
        action = self.lastPkgPB
        if action == 'all':
            masks = ['installed','available']
        else:
            masks = [action]
        self.pkgView.store.clear()
        allpkgs = []
        if self.doProgress: self.progress.total.next() # -> Get lists                
        for flt in masks:
            msg = _('Getting packages : %s' ) % flt
            self.progressLog(msg)
            self.setStatus(msg)
            pkgs = self.yumbase.getPackages(flt)
            self.progressLog(_('Found %d %s packages') % (len(pkgs),flt))
            allpkgs.extend(pkgs)
        if self.doProgress: self.progress.total.next() # -> Sort Lists        
        self.progressLog(_('Sorting packages'))
        allpkgs.sort()
        self.progressLog(_('Population view with packages'))
        self.ui.viewPkg.set_model(None)
        for po in allpkgs:
            self.pkgView.store.append([po,str(po)])
        self.ui.viewPkg.set_model(self.pkgView.store)
        
        msg = _('Population Completed')
        self.progressLog(msg)
        self.setStatus(msg)
        normalCursor(self.ui.main)
        if self.doProgress: self.progress.hide() #Hide Progress        

    def addCategoryPackages(self,cat = None):
        msg = _('Package View Population')
        self.setStatus(msg)
        busyCursor(self.ui.main)
        self.pkgView.store.clear()
        pkgs = self.yumbase.getPackagesByCategory(cat)
        if pkgs:
            pkgs.sort()
            self.ui.viewPkg.set_model(None)
            for po in pkgs:
                self.pkgView.store.append([po,str(po)])
            self.ui.viewPkg.set_model(self.pkgView.store)
            self.ui.viewPkg.set_search_column( 2 )
            msg = _('Package View Population Completed')
            self.setStatus(msg)
        normalCursor(self.ui.main)
              

    def addCategories(self, fn, para, sortkeys,splitkeys ):
        msg = _('Category View Population')
        self.setStatus(msg)
        busyCursor(self.ui.main)
        getterfn = getattr( self.yumbase, fn )
        if para != '':
            lst, keys = getterfn( self.lastPkgPB, para )
        else:
            lst, keys = getterfn( self.lastPkgPB)
        fkeys = [ key for key in keys if lst.has_key(key)]
        if sortkeys:
            fkeys.sort()
        if not splitkeys:
            self.catView.populate(fkeys)
        else:
            keydict = self.splitCategoryKeys(fkeys)
            self.catView.populate(keydict,True)
        self.yumbase.setCategoryPackages(lst)
        self.catView.view.set_cursor((0,))
        normalCursor(self.ui.main)
        msg = _('Category View Population Completed')
        self.setStatus(msg)
       
    def splitCategoryKeys(self,keys,sep='/'):
        tree = RPMGroupTree()
        for k in keys:
            lst = k.split(sep)
            tree.add(lst)
        return tree    
        
    def getRecentTime(self,recentdays = 14):
        recentdays = float( recentdays )
        now = time.time()
        return now-( recentdays*const.DAY_IN_SECONDS )   

    def processPackageQueue( self, pkgs, doAll=False):
        """ Workflow for processing package queue """
        self.setStatus( _( "Preparing for install/remove/update" ) )
        self.progress.total.setup( const.PACKAGE_PROGRESS_STEPS )        
        total = len( pkgs['i'] )+len( pkgs['u'] )+len( pkgs['r'] )
        state = True
        quit = False
        if total > 0:
            self.startWorking()
            self.progress.show()
            self.progress.set_mainLabel( _( "Processing Packages in queue" ) )
            # build transaction and resolv dependencies.
            rc, msg = self.yumbase._prepareTransaction(pkgs,doAll)        
            self.endWorking()
            if rc != 2:
                m = '\n'.join(msg)
                msg = _( "Error in Dependency Resolution" )
                rc = errorMessage( self.ui.main, _( "Error" ), msg, m )
                self.logger.error(msg)
                self.logger.error(m)
                state=False
            else:
                if self.get_confimation( "" ):
                    quit = self.processTransaction()
                    if quit == None: # Check if Transaction failed.
                        state = False
                else:
                    state = False
            self.progress.hide()
            if quit:
                return "QUIT"
            return state
        else:
            self.setStatus( _( "No packages selected" ) )
            return state

    def get_confimation( self, task ):
        self.progress.hide( False )
        pkgs = self.yumbase._getTransactionList()
        if len(pkgs) == 0:
            okDialog(self.ui.main,_('No packages in transaction'))
            return False 
        size = self.yumbase._getTransactionSize()
        dlg = ConfimationDialog(self.ui.main, pkgs, size )
        rc = dlg.run()
        dlg.destroy()
        self.progress.show()
        return rc == gtk.RESPONSE_OK        

    def processTransaction( self ):
        self.setStatus( _( "Processing packages (See output for details)" ) )
        try:
            self.startWorking()
            self.progress.show()
            self.progress.total.next() # -> Download
            self.enableSkipMirror()   # Enable SkipMirror
            self.yumbase._downloadPackages()
            self.disableSkipMirror()   # Disable SkipMirror
            # Skip Transaction is downloadonly is set.
            if not self.settings.downloadonly:
                self.progress.total.next() # -> Transaction Test
                self.yumbase._doTransactionTest()
                self.progress.total.next() # -> Run  Transaction
                self.rpmTransactionIsRunning = True # Disable Quit
                self.yumbase._runTransaction()
                self.rpmTransactionIsRunning = False
            self.progress.hide()
            self.endWorking()
            rc = infoMessage( self.ui.main, _( "Packages Processing" ), _( "Packages Processing completed ok" ) )
            return rc
        except Errors.YumBaseError, e:
            self.endWorking()
            errorMessage( self.ui.main, _( "Error" ), _( "Error in Transaction" ), str(e) )   
            self.logger.error(str(e))         
            return None
                   
    def doQueueAdd(self,parser,qType):
        self.logger.debug( _("Parsing packages to %s ") % qType)
        pTypeDict = {'install':'available',
                     'update':'updates',
                     'remove':'installed'}
        dict = parser.getList(qType)
        pType = pTypeDict[qType]
        repos = self.repoList.getEnabledList()
        repos.append('installed')
        no = 0
        found = 0
        for repo in dict.keys():
            if repo in repos:
                self.logger.debug('--> Repo : %s' % repo)
                no += len(dict[repo])
                pkgs = self.yumbase.findPackagesByTuples(pType,dict[repo])
                found += len(pkgs)
                for po in pkgs:
                    self.logger.debug("---> %s " % str(po))
                    self.queue.add(po)
                    self.queueView.refresh()
            else:
                self.logger.debug('--> Skipping Repo (Not Enabled): %s' % repo)
        self.logger.debug("-> found %i of %i" % (found,no))
        return found,no

    def doQuickAdd(self,cmd,arglist):
        cmd = cmd.lower()
        typ = None
        if cmd == 'install':
            typ = 'available'
        elif cmd == 'remove' or cmd == 'erase' or cmd == 'delete':
            typ = 'installed'
        if typ:
            found = self.yumbase.findPackages(arglist,typ)
            self.setStatus(_('found %d packages, matching : %s') % (len(found)," ".join(arglist)))
            for po in found:
                #print str(po),po.action
                self.queue.add(po)
            self.queueView.refresh()

    def populateGroupCategories(self):
        data = self.yumbase.getByCategory()
        self.compsView.populate(data)

    def populateGroups(self,id):
        for c in self.yumbase.comps.categories:
            if c.categoryid == id:
                break
        grps = [self.yumbase.comps.return_group(g) for g in c.groups]
        data = [(g.name,g.groupid,g.installed,) for g in grps]
        self.grpGroups.populate(data,id)
        
    def populateGroupPackages(self,id):
        grp = self.yumbase.comps.return_group(id)
        self.grpDesc.clear()
        if grp.description:
            self.grpDesc.write_line(grp.description)
        pkgs = self.yumbase._getByGroup(grp,['m','d','o'])
        pkgs.sort()
        self.grpPackages.store.clear()
        self.ui.tvGrpPackages.set_model(None)
        for po in pkgs:
            self.grpPackages.store.append([po,str(po)])
        self.ui.tvGrpPackages.set_model(self.grpPackages.store)
       

class ProcessGtkEventsThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.__quit = False
        self.__active = Event()
        self.__active.clear()
        
    def run(self):      
        while self.__quit == False:
            while not self.__active.isSet():
                self.__active.wait()
            time.sleep(0.1)
            while gtk.events_pending():      # process gtk events
                gtk.main_iteration()    
            time.sleep(0.1)
            
    def doQuit(self):
        self.__quit = True
        self.__active.set()
        
    def startProcessing(self):
        self.__active.set()

    def endProcessing(self):
        self.__active.clear()
            
if __name__ == "__main__":
    try:
        gtkEventThread = ProcessGtkEventsThread()
        gtkEventThread.start()
        gtk.window_set_default_icon_from_file(const.PIXMAPS_PATH+"/yumex-icon.png")        
        mainApp = YumexApplication()
        gtk.main()
    except Errors.LockError, e:       
        logger = logging.getLogger('yumex.main')
        msg = _('Yum is locked by another application')
        logger.error(msg)
        errorMessage(None, _( "Error" ),_("Error in Yumex"),msg)
        gtkEventThread.doQuit()
        sys.exit(1)
    except SystemExit, e:
        print "Quit by User"
        gtkEventThread.doQuit()
        sys.exit(1)        
    except yum.plugins.PluginYumExit,e:
        errorMessage(None, _( "Error" ),_("Error in plugin, Yum Extender will exit"),str(e))
        gtkEventThread.doQuit()
        sys.exit(1)        
    except: # catch other exception and write it to the logger.
        logger = logging.getLogger('yumex.main')
        etype = sys.exc_info()[0]
        evalue = sys.exc_info()[1]
        etb = traceback.extract_tb(sys.exc_info()[2])
        logger.error('Error Type: %s' % str(etype) )
        errmsg = 'Error Type: %s \n' % str(etype)
        logger.error('Error Value: ' + str(evalue))
        errmsg += 'Error Value: %s \n' % str(evalue)
        logger.error('Traceback: \n')
        for tub in etb:
            f,l,m,c = tub # file,lineno, function, codeline
            logger.error('  File : %s , line %s, in %s' % (f,str(l),m))
            errmsg += '  File : %s , line %s, in %s\n' % (f,str(l),m)
            logger.error('    %s ' % c)
            errmsg += '    %s \n' % c
        errorMessage(None, _( "Error" ), _( "Error in Yumex" ), errmsg )  
        gtkEventThread.doQuit()
        sys.exit(1)
        