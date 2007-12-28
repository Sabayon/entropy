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

from yumgui import *
from misc import YumexQueue,const,cleanMarkupSting
from views import *
from yumgui.widgets import TextViewConsole
from i18n import _


class YumexPackageInfo:
    def __init__(self,ui,settings):
        self.ui = ui
        self.settings = settings
        self.pkgDesc = TextViewConsole( self.ui.pkgDesc, font=self.settings.font_pkgdesc, color=self.settings.color_pkgdesc )
        self.pkgInfo = TextViewConsole( self.ui.pkgInfo, font=self.settings.font_pkgdesc, color=self.settings.color_pkgdesc )
        self.pkgFiles = TextViewConsole( self.ui.pkgFiles, font=self.settings.font_pkgdesc, color=self.settings.color_pkgdesc )
        self.pkgChangeLog = TextViewConsole( self.ui.pkgCLog, font=self.settings.font_pkgdesc, color=self.settings.color_pkgdesc )
        self.pkgOther = TextViewConsole( self.ui.pkgOther, font=self.settings.font_pkgdesc, color=self.settings.color_pkgdesc )
        self.yumbase = None
        
    def clear( self ):
        self.pkgDesc.clear()
        self.pkgInfo.clear()
        self.pkgFiles.clear()
        self.pkgChangeLog.clear()
        self.pkgOther.clear()

    def goTop( self ):
        self.pkgDesc.goTop()
        self.pkgInfo.goTop()
        self.pkgFiles.goTop()
        self.pkgChangeLog.goTop()
        self.pkgOther.goTop()
        
    def showInfo(self,pkg):
        self.clear()
        self.writePkg( self.pkgDesc, pkg, "%s", "description" )
        if pkg.repoid == 'installed' or self.settings.filelist:
            files = pkg.get_filelist()
            for f in files:
                self.pkgFiles.write_line( "%s\n" % f ) 
        if pkg.repoid == 'installed' or self.settings.changelog:
            cl = pkg.get_changelog()
            for l in cl:
                self.pkgChangeLog.write_line( "%s\n" % l ) 
        if pkg.action == 'u':
            if not pkg.obsolete:
                lst = self.yumbase.rpmdb.searchNevra(name=pkg.name)
                txt = _( "Updating : %s\n\n" ) % str(lst[0])
                self.pkgInfo.write_line( txt ) 
            else:
                obsoletes = self.yumbase.up.getObsoletesTuples( newest=1 )
                for ( obsoleting, installed ) in obsoletes:
                    if obsoleting[0] == pkg.name:
                        po =  self.yumbase.rpmdb.searchPkgTuple( installed )[0]                           
                        txt = _( "Obsoleting : %s\n\n" ) % str(po)
                        self.pkgInfo.write_line( txt ) 
                        break

        self.writePkg( self.pkgInfo, pkg, 'RPM Group    : %s\n', "group", True )
        self.writePkg( self.pkgInfo, pkg, 'Source       : %s\n', "sourcerpm" )
        gp = self.yumbase.pkgInGrps.get(pkg.name)
        if gp:
            self.pkgInfo.write_line('Yum Group    : %s/%s\n' % (gp[0].category.name,gp[0].group.name))        
            gpType = const.GROUP_PACKAGE_TYPE[gp[0].typ]
            self.pkgInfo.write_line(' -> Type     : %s\n' % (gpType))        
        self.writePkgTime( self.pkgInfo, pkg, 'Build Time   : %s\n', "buildtime" )
        if pkg.action =='r':
            self.writePkgTime( self.pkgInfo, pkg, 'Install Time : %s\n', "installtime" )
            self.writePkg( self.pkgInfo, pkg, 'License      : %s\n', 'license' )
            self.pkgOther.write_line( _( "Requires:\n\n" ) ) 
            reqList = pkg.pkg.requiresList()
            for req in reqList:
                self.pkgOther.write_line( "%s\n" % req )                     
        self.goTop()

    def writePkg( self, outobj, pkg, markup, attr, remove_newline=False ):
        try:
            data = pkg.getAttr( attr )
            if remove_newline:
                out = markup % data.replace( "\n", "" )
            else:
                out = markup % data 
            outobj.write_line( out )
        except AttributeError, e:
            msg = _( 'Can not read the %s attribute' ) % attr
            print msg

    def writePkgTime( self, outobj, pkg, markup, attr ):
        try:
            data = pkg.getAttr( attr )
            data = str( time.ctime( float( data ) ) )
            out = markup % data 
            outobj.write_line( out )
        except AttributeError, e:
            msg = _( 'Can not read the %s attribute' ) % attr
            print msg

class ProgressTotal:
    def __init__( self, widget ): 
        self.progress = widget
        self.steps = []
        self.nowProgres = 0.0
        self.numSteps=0
        self.currentStep=0 
        self.stepError = False
        self.lastFrac = -1
        self.clear()
    
    def setup( self, steps ):
        self.steps = steps
        self.numSteps=len( steps )
        self.currentStep=0 
        self.nowProgress = 0.0
        self.stepError = False
        self.clear()

    def next( self ):
        now = 0.0
        if self.currentStep < self.numSteps:
            self.currentStep += 1
            for i in range( 0, self.currentStep ):
                now += self.steps[i]
                self.nowProgress = now
                self.setAbsProgress( now )
            return True
        else:
            return False

    def _percent( self, total, now ):
       if total == 0:
           percent = 0
       else:
           percent = ( now*100L )/total
       return percent
       
    def clear( self ):
        self.progress.set_fraction( 0 )
        self.progress.set_text( " " )
        self.lastFrac = -1
            
    def setProgress( self, now, total, prefix=None ):
        relStep = float( now )/float( total )
        if self.currentStep < self.numSteps:
            curStep =self.steps[self.currentStep]
            absStep = curStep * relStep
            absProgress = self.nowProgress + absStep
            self.setAbsProgress( absProgress, prefix )
        else: # This should not happen but it does sometimes.
            if not self.stepError:
                print "=" * 60
                print "Something stranged has happend in the ProgressTotal: (setProgress)"
                print "Dumping some vars for debug"
                print self.steps
                print self.currentStep
                print self.numSteps
                print now
                print total
                print "-" * 60
                traceback.print_stack( file=sys.stdout )
                print "=" * 60
                self.stepError = True # Only dump vars first time.
        return False
        
    def setAbsProgress( self, now, prefix=None ):
        if not now >= self.lastFrac and now < 1:
            return
        while gtk.events_pending():      # process gtk events
           gtk.main_iteration()    
        self.lastFrac = now+0.01
        procent = long( self._percent( 1, now ) )
        self.progress.set_fraction( now )
        if prefix:
            text = "%s : %3i%%" % ( prefix, procent )
        else:
            text = "%3i%%" % procent
        self.progress.set_text( text )
                     
class YumexProgress:
    """ Progress Class """
    def __init__( self, ui, set_page_func,parent ):
        self.ui = ui
        self.set_page_func = set_page_func
        self.parent = parent
        self.ui.progressMainLabel.set_text( "" )
        self.ui.progressSubLabel.set_text( "" )
        self.ui.progressExtraLabel.set_text( "" )
        self.ui.progressETALabel.set_text( "" )
        self.total = ProgressTotal( self.ui.totalProgressBar )
        self.ui.progressBar.set_fraction( 0 )
        self.ui.progressBar.set_text( " " )
        self.lastFrac = -1
            
    def show( self ):
        self.ui.progressBox.show()
        self.set_page_func( 'output' )
        self.lastFrac = -1
        
    def hide( self, clean=False ):
        self.ui.progressBox.hide()
        if clean:
            self.ui.progressMainLabel.set_text( "" )
            self.ui.progressSubLabel.set_text( "" )
            self.ui.progressExtraLabel.set_text( "" )
            self.ui.progressBar.set_fraction( 0 )
            self.ui.progressBar.set_text( " " )
        
    def setTotal( self, now, total ):
        self.total.setProgress( now, total )
    
    def set_progress( self, frac, text=None ): 
        if self.parent.quitNow:
            self.parent.exitNow()
        # Skip if fraction not have changed
        if not frac >= self.lastFrac and frac < 1:
            return
        while gtk.events_pending():      # process gtk events
           gtk.main_iteration()    
    
        self.lastFrac = frac + 0.01
        if frac >= 0 and frac <= 1:
            self.ui.progressBar.set_fraction( frac )
        else:
            self.ui.progressBar.set_fraction( 0 )
        if text != None:
            self.ui.progressBar.set_text( text )
        # Check if skip mirror has been pressed
        if self.parent.skipMirrorNow:
            self.parent.skipMirrorNow = False
            self.parent.yumbase._interrupt_callback(None)
            
       
    def set_mainLabel( self, text ):
        self.ui.progressMainLabel.set_markup( "<span size=\"large\"><b>%s</b></span>" % text )
        self.ui.progressSubLabel.set_text( "" )
        self.ui.progressExtraLabel.set_text( "" )
           
    def set_subLabel( self, text ):
        self.ui.progressSubLabel.set_markup( "%s" % text )
        self.ui.progressExtraLabel.set_text( "" )
        self.ui.progressETALabel.set_text( "" )

    def set_extraLabel( self, text ):
        self.ui.progressExtraLabel.set_markup( "<span size=\"small\">%s</span>" % cleanMarkupSting(text) )
        self.ui.progressETALabel.set_text( "" )
        self.lastFrac = -1
        
    def set_etaLabel( self, text ):
        self.ui.progressETALabel.set_markup( "<span size=\"small\">%s</span>" % text )
                             
        
class YumexGUI:   
    ''' This class contains GUI related methods '''
    def __init__(self):
        self.output = TextViewConsole( self.ui.viewOutput,font=self.settings.font_console, color=self.settings.color_console)         
        self.setupLogging()
        # Package & Queue Views
        self.queue = YumexQueue()
        self.queueView = YumexQueueView(self.ui.queueView,self.queue)
        self.pkgView = YumexPackageView(self.ui.viewPkg,self.queueView) 
        self.catView = YumexCategoryView(self.ui.tvCategory)
        self.compsView = YumexCompsView(self.ui.tvComps,self.queueView)
        self.grpPackages = YumexPackageView(self.ui.tvGrpPackages,self.queueView) 
        self.grpDesc = TextViewConsole(self.ui.grpDesc)
        self.repoView = YumexRepoView(self.ui.viewRepo)
        # Left Side Toolbar      
        self.pageButtons = {}    # Dict with page buttons
        self.firstButton = None  # first button
        self.activePage = 'packages'
        # Package info notebook
        self.packageInfo = YumexPackageInfo(self.ui,self.settings)
        # Progress bars
        self.progress = YumexProgress(self.ui,self.setPage,self)
        # Package Radiobuttons
        self.packageRB = {}
        self.lastPkgPB = 'updates'
        self.tooltip =  gtk.Tooltips()   

    def setupGUI(self):
        ''' Setup the GUI'''
        self.ui.main.set_title( "%s %s" % (self.settings.branding_title, const.__yumex_version__) )        
        self.ui.main.connect( "delete_event", self.quit )
        self.ui.notebook.set_show_tabs( False )        
        self.ui.main.present()
        self.setupPageButtons()        # Setup left side toolbar
        self.setPage(self.activePage)
        self.setupCategory()
        self.setupPkgFilter()
        
    def setupLogging(self):
        self.logHandler = TextViewLogHandler(self.output,self.settings.nothreads)
        formatter = logging.Formatter('%(asctime)s : %(message)s', "%H:%M:%S")
        self.logHandler.setFormatter(formatter)
        if self.settings.debug:
            loglvl = logging.DEBUG
        else:
            loglvl = logging.INFO
        logger = self.loggerSetup( "yumex",loglvl )       
        logger.propagate = False
        console_stdout = logging.StreamHandler(sys.stdout)
        console_stdout.setFormatter(formatter)
        logger.addHandler(console_stdout)
        self.loggerSetup( "yum")       
        self.loggerSetup( "yum.verbose")       
        
    
    def loggerSetup(self,logroot,loglvl=None):
        logger = logging.getLogger(logroot)
        if loglvl:
            logger.setLevel(loglvl)
        logger.addHandler(self.logHandler)
        return logger
        

        
    def setupProfilesMenu(self):
        profiles = self.profile.getList()
        profiles.sort()
        self.firstProfile = self._addToProfileMenu('yum-enabled')
        for pro in profiles:
            self._addToProfileMenu(pro,self.firstProfile)
        
        
    def _addToProfileMenu( self, label,group=None):
        menu = self.ui.profileMenu.get_submenu()
        item = gtk.RadioMenuItem(group, label, False )
        item.show()
        if self.profile.getActive() == label:
            item.set_active( True )
        menu.append( item )
        item.connect_object( "activate", self.on_profile, label )
        return item
            
        
    def setupCategory(self):
        ''' Populate Category Combobox'''
        model = gtk.ListStore( str )
        keyDict = const.PACKAGE_CATEGORY_DICT
        no = const.PACKAGE_CATEGORY_NO
        for i in range(no+1):
            if i == 0:
                model.append( ['None'] )
            else:
                tup = keyDict[i]
                model.append( [tup[0]] )
        self.ui.cbCategory.set_model( model )
        self.ui.cbCategory.set_active(0) 
        self.ui.swCategory.hide()
        
    def setupPkgFilter(self):
        ''' set callbacks for package radio buttons (all,updates, ...)'''
        self.setupPkgRadio(self.ui.rbAll,"all",_('Show All Packages'))
        self.setupPkgRadio(self.ui.rbUpdates,"updates",_('Show Package Updates'))
        self.setupPkgRadio(self.ui.rbAvailable,"available",_('Show available Packages'))
        self.setupPkgRadio(self.ui.rbInstalled,"installed",_('Show Installed Packages'))

    def setupPkgRadio(self,widget,tag,tip):
        widget.connect('toggled',self.on_pkgFilter_toggled,tag)
        self.tooltip.set_tip(widget,tip)
        self.packageRB[tag] = widget

    def setupPageButtons(self):
        # Setup Vertical Toolbar
        self.createButton( _( "Package View" ), "button-packages.png", 'packages',True )
        self.createButton( _( "Group View" ), "button-group.png", 'group')
        self.createButton( _( "Package Queue View" ), "button-queue.png", 'queue' )
        if not self.settings.disable_repo_page:
            self.createButton( _( "Repository Selection View" ), "button-repo.png", 'repos' )
        self.createButton( _( "Output View" ), "button-output.png", 'output' )    
        style = self.ui.leftEvent.get_style()
        
        # Set the background of the horisontal buttonbar to the same as the views.
        # To make it look good on other than default gtk themes.
        style = self.ui.viewOutput.get_style()
        self.ui.leftEvent.modify_bg( gtk.STATE_NORMAL, style.base[0])
        # Setup Page Icons
        self.ui.pageImage0.set_from_file ( const.PIXMAPS_PATH + '/button-repo.png' )
        self.ui.pageImage2.set_from_file ( const.PIXMAPS_PATH + '/button-output.png' )
        self.ui.pageImage3.set_from_file ( const.PIXMAPS_PATH + '/button-group.png' )
        self.ui.pageImage4.set_from_file ( const.PIXMAPS_PATH + '/button-group.png' )

    def createButton( self, text, icon, page,first = None ):
          if first:
              button = gtk.RadioButton( None )
              self.firstButton = button
          else:
              button = gtk.RadioButton( self.firstButton )
          button.connect( "clicked", self.on_PageButton_changed, page )

          button.set_relief( gtk.RELIEF_NONE )
          button.set_mode( False )

          p = gtk.gdk.pixbuf_new_from_file( const.PIXMAPS_PATH+"/"+icon )
          pix = gtk.Image()
          pix.set_from_pixbuf( p )
          pix.show()

          self.tooltip.set_tip(button,text)
          button.add(pix)
          button.show()
          self.ui.content.pack_start( button, False )
          self.pageButtons[page] = button

    def setPage( self, page ):
        self.activePage = page
        widget = self.pageButtons[page]
        widget.set_active( True )

    def setPkgRB( self, tag ):
        self.lastPkgPB = tag
        widget = self.packageRB[tag]
        widget.set_active( True )

    def setNotebookPage(self,page):
        ''' Switch to Page in GUI'''
        self.ui.notebook.set_current_page(page)        
        
    def setStatus( self, text ):
        ''' Write Message to Statusbar'''
        context_id = self.ui.status.get_context_id( "Status" )
        self.ui.status.push( context_id, text )

    def progressLog(self,msg):
        self.logger.info(msg)
        self.progress.set_subLabel( msg )
        self.progress.set_progress( 0, " " ) # Blank the progress bar.
     
    def pkgInfoClear( self ):
        self.pkgDesc.clear()
        self.pkgInfo.clear()
        self.pkgFiles.clear()
        self.pkgChangeLog.clear()
        self.pkgOther.clear()

    def pkgInfoGoTop( self ):
        self.pkgDesc.goTop()
        self.pkgInfo.goTop()
        self.pkgFiles.goTop()
        self.pkgChangeLog.goTop()
        self.pkgOther.goTop()
        
    def enableSkipMirror(self):
        self.ui.skipMirror.show()
        self.skipMirror = True

    def disableSkipMirror(self):
        self.ui.skipMirror.hide()
        self.skipMirror = False
    