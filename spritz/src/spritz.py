#!/usr/bin/python -tt
# -*- coding: iso-8859-1 -*-
#    It was: Yum Exteder (yumex) - A GUI for yum
#    Copyright (C) 2006 Tim Lauridsen < tim<AT>yum-extender<DOT>org > 
#    Now is: Spritz (Entropy Interface)
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

# Base Python Imports
import sys, os, pty, random
import logging
import traceback
import commands
import time

# Entropy Imports
sys.path.insert(0,"../../libraries")
sys.path.insert(1,"../../client")
sys.path.insert(2,"/usr/lib/entropy/libraries")
sys.path.insert(3,"/usr/lib/entropy/client")
from entropyConstants import *
import exceptionTools, entropyTools
from packages import EntropyPackages
from entropyapi import EquoConnection, QueueExecutor
from entropy import ErrorReportInterface
from entropy_i18n import _

# Spritz Imports
import gtk, gobject
from etpgui.widgets import UI, Controller, SpritzConsole
from etpgui import *
from spritz_setup import SpritzConf, const, fakeoutfile, fakeinfile, cleanMarkupString
from misc import SpritzQueue
from views import *
import filters
from dialogs import *


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

    def hide( self ):
        self.progress.hide()

    def show( self ):
        self.progress.show()

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
        if (now == self.lastFrac) or (now >= 1.0) or (now < 0.0):
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

class SpritzProgress:

    def __init__( self, ui, set_page_func, parent ):
        self.ui = ui
        self.set_page_func = set_page_func
        self.parent = parent
        self.ui.progressMainLabel.set_text( "" )
        self.ui.progressSubLabel.set_text( "" )
        self.ui.progressExtraLabel.set_text( "" )
        self.total = ProgressTotal( self.ui.totalProgressBar )
        self.ui.progressBar.set_fraction( 0 )
        self.ui.progressBar.set_text( " " )
        self.lastFrac = -1

    def show( self ):
        self.ui.progressBox.show()
        self.set_page_func( 'output' )
        self.lastFrac = -1

    def reset_progress( self ):
        self.lastFrac = -1
        self.ui.progressBar.set_fraction( 0 )
        self.ui.progressBar.set_text(" ")

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

        if frac == self.lastFrac:
            return

        if self.parent.quitNow:
            self.parent.exitNow()

        if frac > 1 or frac == 0.0:
            return

        if frac >= 0 and frac <= 1:
            self.ui.progressBar.set_fraction( frac )
        else:
            self.ui.progressBar.set_fraction( 0 )
        if text != None:
            self.ui.progressBar.set_text( text )

        self.lastFrac = frac

        while gtk.events_pending():
           gtk.main_iteration()

    def set_text(self, text):
        self.ui.progressBar.set_text( text )

    def set_mainLabel( self, text ):
        self.ui.progressMainLabel.set_markup( "<b>%s</b>" % text )
        self.ui.progressSubLabel.set_text( "" )
        self.ui.progressExtraLabel.set_text( "" )

    def set_subLabel( self, text ):
        self.ui.progressSubLabel.set_markup( "%s" % text )
        self.ui.progressExtraLabel.set_text( "" )

    def set_extraLabel( self, text ):
        self.ui.progressExtraLabel.set_markup( "<span size=\"small\">%s</span>" % cleanMarkupString(text) )
        self.lastFrac = -1

class SpritzApplication(Controller):

    def __init__(self):

        self.Equo = EquoConnection
        locked = self.Equo._resources_run_check_lock()
        if locked:
            okDialog( None, _("Entropy resources are locked and not accessible. Another Entropy application is running. Sorry, can't load Spritz.") )
            raise SystemExit(1)
        self.safe_mode_txt = ''
        # check if we'are running in safe mode
        if self.Equo.safe_mode:
            reason = etpConst['safemodereasons'].get(self.Equo.safe_mode)
            okDialog( None, "%s: %s. %s" % (_("Entropy is running in safe mode"),reason,_("Please fix as soon as possible"),) )
            self.safe_mode_txt = _("Safe Mode")

        self.isBusy = False
        self.etpbase = EntropyPackages(EquoConnection)

        # Create and ui object contains the widgets.
        ui = UI( const.GLADE_FILE , 'main', 'entropy' )
        addrepo_ui = UI( const.GLADE_FILE , 'addRepoWin', 'entropy' )
        wait_ui = UI( const.GLADE_FILE , 'waitWindow', 'entropy' )
        # init the Controller Class to connect signals.
        Controller.__init__( self, ui, addrepo_ui, wait_ui )

        # Setup GUI
        self.setupGUI()
        self.packagesInstall()

    def quit(self, widget=None, event=None ):
        if self.ugcTask != None:
            self.ugcTask.kill()
        ''' Main destroy Handler '''

        threads = entropyTools.threading.enumerate()
        for thread in threads:
            if hasattr(thread,'nuke'):
                thread.nuke()

        gtkEventThread.doQuit()
        if self.isWorking:
            self.quitNow = True

        self.exitNow()

    def exitNow(self):
        try:
            gtk.main_quit()
        except RuntimeError:
            pass

    def load_url(self, url):
        import subprocess
        subprocess.call(['xdg-open',url])

    def setupGUI(self):

        self.clipboard = gtk.Clipboard()
        self.pty = pty.openpty()
        self.output = fakeoutfile(self.pty[1])
        self.input = fakeinfile(self.pty[1])
        self.do_debug = False
        if "--debug" in sys.argv:
            self.do_debug = True
        elif os.getenv('SPRITZ_DEBUG') != None:
            self.do_debug = True
        if not self.do_debug:
            sys.stdout = self.output
            sys.stderr = self.output
            sys.stdin = self.input

        self.settings = SpritzConf()
        self.queue = SpritzQueue()
        self.queueView = EntropyQueueView(self.ui.queueView,self.queue)
        self.pkgView = EntropyPackageView(self.ui.viewPkg, self.queueView, self.ui, self.etpbase, self.ui.main)
        self.filesView = EntropyFilesView(self.ui.filesView)
        self.advisoriesView = EntropyAdvisoriesView(self.ui.advisoriesView, self.ui, self.etpbase)
        self.queue.connect_objects(self.Equo, self.etpbase, self.pkgView, self.ui)
        #self.catView = SpritzCategoryView(self.ui.tvCategory)
        self.catsView = CategoriesView(self.ui.tvComps,self.queueView)
        self.catsView.etpbase = self.etpbase
        self.catPackages = EntropyPackageView(self.ui.tvCatPackages,self.queueView, self.ui, self.etpbase, self.ui.main)
        self.repoView = EntropyRepoView(self.ui.viewRepo, self.ui)
        self.repoMirrorsView = EntropyRepositoryMirrorsView(self.addrepo_ui.mirrorsView)
        # Left Side Toolbar
        self.pageButtons = {}    # Dict with page buttons
        self.firstButton = None  # first button
        self.activePage = 'repos'
        self.pageBootstrap = True
        # Progress bars
        self.progress = SpritzProgress(self.ui,self.setPage,self)
        # Package Radiobuttons
        self.packageRB = {}
        self.lastPkgPB = 'updates'
        self.tooltip =  gtk.Tooltips()

        # setup add repository window
        self.console_menu_xml = gtk.glade.XML( const.GLADE_FILE, "terminalMenu",domain="entropy" )
        self.console_menu = self.console_menu_xml.get_widget( "terminalMenu" )
        self.console_menu_xml.signal_autoconnect(self)

        ''' Setup the GUI'''
        self.ui.main.set_title( "%s %s %s" % (self.settings.branding_title, const.__spritz_version__, self.safe_mode_txt) )
        self.ui.main.connect( "delete_event", self.quit )
        self.ui.notebook.set_show_tabs( False )
        self.ui.main.present()
        self.setupPageButtons()        # Setup left side toolbar
        self.setPage(self.activePage)

        # put self.console in place
        self.console = SpritzConsole(self.settings)
        self.console.set_scrollback_lines(1024)
        self.console.set_scroll_on_output(True)
        self.console.connect("button-press-event", self.on_console_click)
        termScroll = gtk.VScrollbar(self.console.get_adjustment())
        self.ui.vteBox.pack_start(self.console, True, True)
        self.ui.termScrollBox.pack_start(termScroll, False)
        self.ui.termHBox.show_all()
        self.setupPkgFilter()
        self.setupAdvisoriesFilter()

        self.setupImages()
        self.setupLabels()

        # init flags
        self.disable_ugc = False
        self.ad_list_url = 'http://www.sabayonlinux.org/entropy_ads/LIST'
        self.ad_uri_dir = os.path.dirname(self.ad_list_url)
        self.previous_ad_index = None
        self.previous_ad_image_path = None
        self.ad_url = None
        self.ad_pix = gtk.image_new_from_file(const.plain_ad_pix)
        self.adTask = None
        self.ugcTask = None
        self.spawning_ugc = False
        self.Preferences = None
        self.skipMirrorNow = False
        self.abortQueueNow = False
        self.doProgress = False
        self.categoryOn = False
        self.quitNow = False
        self.isWorking = False
        self.lastPkgPB = "updates"
        self.etpbase.setFilter(filters.spritzFilter.processFilters)
        self.Equo.connect_to_gui(self)
        self.setupEditor()

        self.setPage("packages")

        self.setupAdvisories()
        # setup Repositories
        self.setupRepoView()
        self.firstTime = True
        # calculate updates
        self.setupSpritz()

        self.console.set_pty(self.pty[0])
        self.resetProgressText()
        self.pkgProperties_selected = None
        self.setupPreferences()

        self.setupUgc()
        self.setupAds()

    def packagesInstall(self):

        packages_install = os.getenv("SPRITZ_PACKAGES")
        if packages_install:
            packages_install = [x for x in packages_install.split(";") if os.path.isfile(x)]
        for arg in sys.argv:
            if arg.endswith(etpConst['packagesext']) and os.path.isfile(arg):
                arg = os.path.realpath(arg)
                packages_install.append(arg)
        if packages_install:
            fn = packages_install[0]
            self.on_installPackageItem_activate(None,fn)
        else:
            self.showNoticeBoard()

    def setupAdvisoriesFilter(self):
        self.advisoryRB = {}
        widgets = [
                    (self.ui.rbAdvisories,'affected'),
                    (self.ui.rbAdvisoriesApplied,'applied'),
                    (self.ui.rbAdvisoriesAll,'all')
        ]
        for w,tag in widgets:
            w.connect('toggled',self.populateAdvisories,tag)
            w.set_mode(False)
            self.advisoryRB[tag] = w

    def setupPkgFilter(self):
        ''' set callbacks for package radio buttons (all,updates, ...)'''
        self.setupPkgRadio(self.ui.rbUpdates,"updates",_('Show Package Updates'))
        self.setupPkgRadio(self.ui.rbAvailable,"available",_('Show available Packages'))
        self.setupPkgRadio(self.ui.rbInstalled,"installed",_('Show Installed Packages'))
        self.setupPkgRadio(self.ui.rbMasked,"masked",_('Show Masked Packages'))

    def setupPkgRadio(self, widget, tag, tip):
        widget.connect('toggled',self.on_pkgFilter_toggled,tag)

        #widget.set_relief( gtk.RELIEF_NONE )
        widget.set_mode( False )

        try:
            p = gtk.gdk.pixbuf_new_from_file( const.PIXMAPS_PATH+"/"+tag+".png" )
            pix = self.ui.rbUpdatesImage
            if tag == "available":
                pix = self.ui.rbAvailableImage
            elif tag == "installed":
                pix = self.ui.rbInstalledImage
            elif tag == "masked":
                pix = self.ui.rbMaskedImage
            pix.set_from_pixbuf( p )
            pix.show()
        except gobject.GError:
            pass

        self.tooltip.set_tip(widget,tip)
        self.packageRB[tag] = widget

    def setupPageButtons(self):
        # Setup Vertical Toolbar
        self.createButton( _( "Packages" ), "button-packages.png", 'packages',True )
        self.createButton( _( "Package Categories" ), "button-group.png", 'group')
        self.createButton( _( "Security Advisories" ), "button-glsa.png", 'glsa' )
        self.createButton( _( "Repository Selection" ), "button-repo.png", 'repos' )
        self.createButton( _( "Configuration Files" ), "button-conf.png", 'filesconf' )
        self.createButton( _( "Preferences" ), "preferences.png", 'preferences' )
        self.createButton( _( "Package Queue" ), "button-queue.png", 'queue' )
        self.createButton( _( "Output" ), "button-output.png", 'output' )

    def createButton( self, text, icon, page,first = None ):
        if first:
            button = gtk.RadioButton( None )
            self.firstButton = button
        else:
            button = gtk.RadioButton( self.firstButton )
        button.connect( "clicked", self.on_PageButton_changed, page )
        #button.connect( "pressed", self.on_PageButton_pressed, page )

        button.set_relief( gtk.RELIEF_NONE )
        button.set_mode( False )

        iconpath = os.path.join(const.PIXMAPS_PATH,icon)
        pix = None
        if os.path.isfile(iconpath) and os.access(iconpath,os.R_OK):
            try:
                p = gtk.gdk.pixbuf_new_from_file( iconpath )
                pix = gtk.Image()
                pix.set_from_pixbuf( p )
                pix.show()
            except gobject.GError:
                pass

        self.tooltip.set_tip(button,text)
        if pix != None:
            button.add(pix)
        button.show()
        self.ui.content.pack_start( button, False )
        self.pageButtons[page] = button

    def setupImages(self):
        """ setup misc application images """

        # progressImage
        iconpath = os.path.join(const.PIXMAPS_PATH,"sabayon.png")
        if os.path.isfile(iconpath) and os.access(iconpath,os.R_OK):
            try:
                p = gtk.gdk.pixbuf_new_from_file( iconpath )
                self.ui.progressImage.set_from_pixbuf(p)
            except gobject.GError:
                pass

    def setupLabels(self):
        """ setup misc application labels """

        mytxt = "<span size='x-large' foreground='#8A381B'>%s</span>" % (_("Preferences"),)
        self.ui.preferencesTitleLabel.set_markup(mytxt)
        mytxt = "<span foreground='#084670'>%s</span>" % (_("Some configuration options are critical for the health of your System. Be careful."),)
        self.ui.preferencesLabel.set_markup(mytxt)

    def setupAds(self):
        self.ui.bannerEventBox.add(self.ad_pix)
        self.ui.adsLabel.set_markup("<small><b>%s</b></small>" % (_("Advertisement"),))
        self.ad_url = 'http://www.silkbit.com'
        self.ui.bannerEventBox.show_all()
        self.adTask = entropyTools.TimeScheduled(self.spawnAdRotation, 60)
        self.adTask.start()

    def setupUgc(self):
        self.ugcTask = entropyTools.TimeScheduled(self.spawnUgcUpdate, 120)
        self.ugcTask.start()

    def spawnAdRotation(self):
        try:
            self.ad_rotation()
        except:
            pass

    def ad_rotation(self):

        if self.isWorking or self.disable_ugc:
            return

        tries = 5
        while tries:

            ads_data = entropyTools.get_remote_data(self.ad_list_url)
            if not ads_data:
                tries -= 1
                continue

            ads_data = [x.strip() for x in ads_data if x.strip() and x.split() > 1]
            length = len(ads_data)
            myrand = int(random.random()*length)
            while myrand == self.previous_ad_index:
                myrand = int(random.random()*length)

            mydata = ads_data[myrand].split()
            mypix_url = os.path.join(self.ad_uri_dir,mydata[0])
            myurl = ' '.join(mydata[1:])

            pix_tmp_path = entropyTools.getRandomTempFile()
            fetchConn = self.Equo.urlFetcher(mypix_url, pix_tmp_path, resume = False)
            rc = fetchConn.download()
            if rc in ("-1","-2","-3"):
                tries -= 1
                continue

            # load the image
            try:
                myadpix = gtk.image_new_from_file(pix_tmp_path)
            except:
                tries -= 1
                continue

            gtk.gdk.threads_enter()

            self.ui.bannerEventBox.remove(self.ad_pix)
            self.ad_pix = myadpix
            self.ui.bannerEventBox.add(self.ad_pix)
            self.ui.bannerEventBox.show_all()
            self.ad_url = myurl

            if self.previous_ad_image_path != None:
                if os.path.isfile(self.previous_ad_image_path) and os.access(self.previous_ad_image_path,os.W_OK):
                    try:
                        os.remove(self.previous_ad_image_path)
                    except (OSError,IOError,):
                        pass
            self.previous_ad_image_path = pix_tmp_path
            self.previous_ad_index = myrand

            gtk.gdk.threads_leave()
            break

    def spawnUgcUpdate(self):
        try:
            self.ugc_update()
        except:
            pass

    def ugc_update(self):

        if self.spawning_ugc or self.isWorking or self.disable_ugc:
            return

        self.isWorking = True
        self.spawning_ugc = True
        connected = entropyTools.get_remote_data(etpConst['conntestlink'])
        if (isinstance(connected,bool) and (not connected)) or (self.Equo.UGC == None):
            self.isWorking = False
            self.spawning_ugc = False
            return
        for repo in self.Equo.validRepositories:
            self.Equo.update_ugc_cache(repo)

        self.isWorking = False
        self.spawning_ugc = False

    def fillPreferencesDbBackupPage(self):
        self.dbBackupStore.clear()
        backed_up_dbs = self.Equo.list_backedup_client_databases()
        for mypath in backed_up_dbs:
            mymtime = self.Equo.entropyTools.getFileUnixMtime(mypath)
            mytime = self.Equo.entropyTools.convertUnixTimeToHumanTime(mymtime)
            self.dbBackupStore.append( (mypath,os.path.basename(mypath),mytime,) )

    def on_console_click(self, widget, event):
        self.console_menu.popup( None, None, None, event.button, event.time )
        return True

    def on_dbBackupButton_clicked(self, widget):
        self.startWorking()
        status, err_msg = self.Equo.backupDatabase(etpConst['etpdatabaseclientfilepath'])
        self.endWorking()
        if not status:
            okDialog( self.ui.main, "%s: %s" % (_("Error during backup"),err_msg,) )
            return
        okDialog( self.ui.main, "%s" % (_("Backup complete"),) )
        self.fillPreferencesDbBackupPage()
        self.dbBackupView.queue_draw()

    def on_dbRestoreButton_clicked(self, widget):
        model, myiter = self.dbBackupView.get_selection().get_selected()
        if myiter == None: return
        dbpath = model.get_value(myiter, 0)
        self.startWorking()
        status, err_msg = self.Equo.restoreDatabase(dbpath, etpConst['etpdatabaseclientfilepath'])
        self.endWorking()
        self.etpbase.clearPackages()
        self.etpbase.clearCache()
        self.Equo.reopenClientDbconn()
        self.etpbase.clearPackages()
        self.etpbase.clearCache()
        self.pkgView.clear()
        self.addPackages()
        if not status:
            okDialog( self.ui.main, "%s: %s" % (_("Error during restore"),err_msg,) )
            return
        self.fillPreferencesDbBackupPage()
        self.dbBackupView.queue_draw()
        okDialog( self.ui.main, "%s" % (_("Restore complete"),) )

    def on_dbDeleteButton_clicked(self, widget):
        model, myiter = self.dbBackupView.get_selection().get_selected()
        if myiter == None: return
        dbpath = model.get_value(myiter, 0)
        try:
            if os.path.isfile(dbpath) and os.access(dbpath,os.W_OK):
                os.remove(dbpath)
        except OSError, e:
            okDialog( self.ui.main, "%s: %s" % (_("Error during removal"),e,) )
            return
        self.fillPreferencesDbBackupPage()
        self.dbBackupView.queue_draw()

    def setupPreferences(self):

        # config protect
        self.configProtectView = self.ui.configProtectView
        for mycol in self.configProtectView.get_columns(): self.configProtectView.remove_column(mycol)
        self.configProtectModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Item" ), cell, markup = 0 )
        self.configProtectView.append_column( column )
        self.configProtectView.set_model( self.configProtectModel )

        # config protect mask
        self.configProtectMaskView = self.ui.configProtectMaskView
        for mycol in self.configProtectMaskView.get_columns(): self.configProtectMaskView.remove_column(mycol)
        self.configProtectMaskModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Item" ), cell, markup = 0 )
        self.configProtectMaskView.append_column( column )
        self.configProtectMaskView.set_model( self.configProtectMaskModel )

        # config protect skip
        self.configProtectSkipView = self.ui.configProtectSkipView
        for mycol in self.configProtectSkipView.get_columns(): self.configProtectSkipView.remove_column(mycol)
        self.configProtectSkipModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Item" ), cell, markup = 0 )
        self.configProtectSkipView.append_column( column )
        self.configProtectSkipView.set_model( self.configProtectSkipModel )

        # database backup tool
        self.dbBackupView = self.ui.dbBackupView
        self.dbBackupStore = gtk.ListStore( gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Database" ), cell, markup = 1 )
        self.dbBackupView.append_column( column )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Date" ), cell, markup = 2 )
        self.dbBackupView.append_column( column )
        self.dbBackupView.set_model( self.dbBackupStore )
        self.fillPreferencesDbBackupPage()

        # UGC repositories

        def get_ugc_repo_text( column, cell, model, myiter ):
            obj = model.get_value( myiter, 0 )
            if obj:
                t = "[<b>%s</b>] %s" % (obj['repoid'],obj['description'],)
                cell.set_property('markup',t)

        def get_ugc_logged_text( column, cell, model, myiter ):
            obj = model.get_value( myiter, 0 )
            if obj:
                t = "<i>%s</i>" % (_("Not logged in"),)
                if self.Equo.UGC != None:
                    logged_data = self.Equo.UGC.read_login(obj['repoid'])
                    if logged_data != None:
                        t = "<i>%s</i>" % (logged_data[0],)
                cell.set_property('markup',t)

        def get_ugc_status_pix( column, cell, model, myiter ):
            if self.Equo.UGC == None:
                cell.set_property( 'icon-name', 'gtk-cancel' )
                return
            obj = model.get_value( myiter, 0 )
            if obj:
                if self.Equo.UGC.is_repository_eapi3_aware(obj['repoid']):
                    cell.set_property( 'icon-name', 'gtk-apply' )
                else:
                    cell.set_property( 'icon-name', 'gtk-cancel' )
                return
            cell.set_property( 'icon-name', 'gtk-cancel' )

        self.ugcRepositoriesView = self.ui.ugcRepositoriesView
        self.ugcRepositoriesModel = gtk.ListStore( gobject.TYPE_PYOBJECT )

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Repository" ), cell )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 300 )
        column.set_expand(True)
        column.set_cell_data_func( cell, get_ugc_repo_text )
        self.ugcRepositoriesView.append_column( column )

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Logged in as" ), cell )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 150 )
        column.set_cell_data_func( cell, get_ugc_logged_text )
        self.ugcRepositoriesView.append_column( column )

        cell = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn( _( "UGC Status" ), cell)
        column.set_cell_data_func( cell, get_ugc_status_pix )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 120 )

        self.ugcRepositoriesView.append_column( column )
        self.ugcRepositoriesView.set_model( self.ugcRepositoriesModel )

        # prepare generic config to allow filling of data
        def fillSettingView(model, view, data):
            model.clear()
            view.set_model(model)
            view.set_property('headers-visible',False)
            for item in data:
                model.append([item])
            view.expand_all()

        def fillSetting(name, mytype, wgwrite, data):
            if not isinstance(data,mytype):
                if data == None: # empty parameter
                    return
                errorMessage(
                    self.ui.main,
                    cleanMarkupString("%s: %s") % (_("Error setting parameter"),name,),
                    _("An issue occured while loading a preference"),
                    "%s %s %s: %s, %s: %s" % (_("Parameter"),name,_("must be of type"),mytype,_("got"),type(data),),
                )
                return
            wgwrite(data)

        def saveSettingView(config_file, name, setting, mytype, model, view):

            data = []
            iterator = model.get_iter_first()
            while iterator != None:
                item = model.get_value( iterator, 0 )
                if item:
                    data.append(item)
                iterator = model.iter_next( iterator )

            return saveSetting(config_file, name, setting, mytype, data)


        def saveSetting(config_file, name, myvariable, mytype, data):
            # saving setting
            writedata = ''
            if (not isinstance(data,mytype)) and (data != None):
                errorMessage(
                    self.ui.main,
                    cleanMarkupString("%s: %s") % (_("Error setting parameter"),name,),
                    _("An issue occured while saving a preference"),
                    "%s %s %s: %s, %s: %s" % (_("Parameter"),name,_("must be of type"),mytype,_("got"),type(data),),
                )
                return False

            if isinstance(data,int):
                writedata = str(data)
            elif isinstance(data,list):
                writedata = ' '.join(data)
            elif isinstance(data,bool):
                writedata = "disable"
                if data: writedata = "enable"
            elif isinstance(data,basestring):
                writedata = data
            return saveParameter(config_file, name, writedata)

        def saveParameter(config_file, name, data):
            return entropyTools.writeParameterToFile(config_file,name,data)

        self.Preferences = {
            etpConst['entropyconf']: [
                (
                    'ftp-proxy',
                    etpConst['proxy']['ftp'],
                    basestring,
                    fillSetting,
                    saveSetting,
                    self.ui.ftpProxyEntry.set_text,
                    self.ui.ftpProxyEntry.get_text,
                ),
                (
                    'http-proxy',
                    etpConst['proxy']['http'],
                    basestring,
                    fillSetting,
                    saveSetting,
                    self.ui.httpProxyEntry.set_text,
                    self.ui.httpProxyEntry.get_text,
                ),
                (
                    'proxy-username',
                    etpConst['proxy']['username'],
                    basestring,
                    fillSetting,
                    saveSetting,
                    self.ui.usernameProxyEntry.set_text,
                    self.ui.usernameProxyEntry.get_text,
                ),
                (
                    'proxy-password',
                    etpConst['proxy']['password'],
                    basestring,
                    fillSetting,
                    saveSetting,
                    self.ui.passwordProxyEntry.set_text,
                    self.ui.passwordProxyEntry.get_text,
                ),
                (
                    'nice-level',
                    etpConst['current_nice'],
                    int,
                    fillSetting,
                    saveSetting,
                    self.ui.niceSpinSelect.set_value,
                    self.ui.niceSpinSelect.get_value_as_int,
                )
            ],
            etpConst['equoconf']: [
                (
                    'collisionprotect',
                    etpConst['collisionprotect'],
                    int,
                    fillSetting,
                    saveSetting,
                    self.ui.collisionProtectionCombo.set_active,
                    self.ui.collisionProtectionCombo.get_active,
                ),
                (
                    'configprotect',
                    etpConst['configprotect'],
                    list,
                    fillSettingView,
                    saveSettingView,
                    self.configProtectModel,
                    self.configProtectView,
                ),
                (
                    'configprotectmask',
                    etpConst['configprotectmask'],
                    list,
                    fillSettingView,
                    saveSettingView,
                    self.configProtectMaskModel,
                    self.configProtectMaskView,
                ),
                (
                    'configprotectskip',
                    etpConst['configprotectskip'],
                    list,
                    fillSettingView,
                    saveSettingView,
                    self.configProtectSkipModel,
                    self.configProtectSkipView,
                ),
                (
                    'filesbackup',
                    etpConst['filesbackup'],
                    bool,
                    fillSetting,
                    saveSetting,
                    self.ui.filesBackupCheckbutton.set_active,
                    self.ui.filesBackupCheckbutton.get_active,
                )
            ],
            etpConst['repositoriesconf']: [
                (
                    'downloadspeedlimit',
                    etpConst['downloadspeedlimit'],
                    int,
                    fillSetting,
                    saveSetting,
                    self.ui.speedLimitSpin.set_value,
                    self.ui.speedLimitSpin.get_value_as_int,
                )
            ],
        }

        # load data
        for config_file in self.Preferences:
            for name, setting, mytype, fillfunc, savefunc, wgwrite, wgread in self.Preferences[config_file]:
                if mytype == list:
                    fillfunc(wgwrite,wgread,setting)
                else:
                    fillfunc(name, mytype, wgwrite, setting)

        self.on_Preferences_toggled(None,False)

    def setupMaskedPackagesWarningBox(self):
        mytxt = "<b><big><span foreground='#FF0000'>%s</span></big></b>\n%s" % (
            _("Attention"),
            _("These packages are masked either by default or due to your choice. Please be careful, at least."),
        )
        self.ui.maskedWarningLabel.set_markup(mytxt)

    def setupAdvisories(self):
        self.Advisories = self.Equo.Security()

    def setupEditor(self):

        pathenv = os.getenv("PATH")
        if os.path.isfile("/etc/profile.env"):
            f = open("/etc/profile.env")
            env_file = f.readlines()
            for line in env_file:
                line = line.strip()
                if line.startswith("export PATH='"):
                    line = line[len("export PATH='"):]
                    line = line.rstrip("'")
                    for path in line.split(":"):
                        pathenv += ":"+path
                    break
        os.environ['PATH'] = pathenv

        self.fileEditor = '/usr/bin/xterm -e $EDITOR'
        de_session = os.getenv('DESKTOP_SESSION')
        if de_session == None: de_session = ''
        path = os.getenv('PATH').split(":")
        if os.access("/usr/bin/xdg-open",os.X_OK):
            self.fileEditor = "/usr/bin/xdg-open"
        if de_session.find("kde") != -1:
            for item in path:
                itempath = os.path.join(item,'kwrite')
                itempath2 = os.path.join(item,'kedit')
                itempath3 = os.path.join(item,'kate')
                if os.access(itempath,os.X_OK):
                    self.fileEditor = itempath
                    break
                elif os.access(itempath2,os.X_OK):
                    self.fileEditor = itempath2
                    break
                elif os.access(itempath3,os.X_OK):
                    self.fileEditor = itempath3
                    break
        else:
            if os.access('/usr/bin/gedit',os.X_OK):
                self.fileEditor = '/usr/bin/gedit'

    def startWorking(self, do_busy = True):
        self.isWorking = True
        if do_busy:
            busyCursor(self.ui.main)
        self.ui.progressVBox.grab_add()
        gtkEventThread.startProcessing()

    def endWorking(self):
        self.isWorking = False
        self.ui.progressVBox.grab_remove()
        normalCursor(self.ui.main)
        gtkEventThread.endProcessing()

    def setupSpritz(self):
        msg = _('Generating metadata. Please wait.')
        self.setStatus(msg)
        count = 30
        while count:
            try:
                self.addPackages()
            except self.Equo.dbapi2.ProgrammingError, e:
                self.setStatus("%s: %s, %s" % (
                        _("Error during list population"),
                        e,
                        _("Retrying in 1 second."),
                    )
                )
                time.sleep(1)
                count -= 1
                continue
            break
        self.populateCategories()

    def cleanEntropyCaches(self, alone = False):
        if alone:
            self.progress.total.hide()
        self.Equo.generate_cache(depcache = True, configcache = False)
        # clear views
        self.etpbase.clearPackages()
        self.etpbase.clearCache()
        self.setupSpritz()
        if alone:
            self.progress.total.show()

    def populateAdvisories(self, widget, show):
        self.setBusy()
        cached = None
        try:
            cached = self.Advisories.get_advisories_cache()
        except (IOError, EOFError):
            pass
        except AttributeError:
            time.sleep(5)
            cached = self.Advisories.get_advisories_cache()
        if cached == None:
            try:
                cached = self.Advisories.get_advisories_metadata()
            except Exception, e:
                okDialog( self.ui.main, "%s: %s" % (_("Error loading advisories"),e) )
                cached = {}
        if cached:
            self.advisoriesView.populate(self.Advisories, cached, show)
        self.unsetBusy()

    def populateFilesUpdate(self):
        # load filesUpdate interface and fill self.filesView
        cached = None
        try:
            cached = self.Equo.FileUpdates.load_cache()
        except exceptionTools.CacheCorruptionError:
            pass
        if cached == None:
            self.setBusy()
            cached = self.Equo.FileUpdates.scanfs()
            self.unsetBusy()
        if cached:
            self.filesView.populate(cached)

    def showNoticeBoard(self):
        repoids = {}
        for repoid in self.Equo.validRepositories:
            board_file = etpRepositories[repoid]['local_notice_board']
            if not (os.path.isfile(board_file) and os.access(board_file,os.R_OK)):
                continue
            if self.Equo.entropyTools.get_file_size(board_file) < 10:
                continue
            repoids[repoid] = board_file
        if repoids:
            self.loadNoticeBoard(repoids)

    def loadNoticeBoard(self, repoids):
        my = NoticeBoardWindow(self.ui.main, self.Equo)
        my.load(repoids)

    def updateRepositories(self, repos):

        self.disable_ugc = True
        # set steps
        progress_step = float(1)/(len(repos))
        step = progress_step
        myrange = []
        while progress_step < 1.0:
            myrange.append(step)
            progress_step += step
        myrange.append(step)

        self.progress.total.setup( myrange )
        self.progress.set_mainLabel(_('Initializing Repository module...'))
        forceUpdate = self.ui.forceRepoUpdate.get_active()

        try:
            repoConn = self.Equo.Repositories(repos, forceUpdate = forceUpdate)
        except exceptionTools.PermissionDenied:
            self.progressLog(_('You must run this application as root'), extra = "repositories")
            self.disable_ugc = False
            return 1
        except exceptionTools.MissingParameter:
            msg = "%s: %s" % (_('No repositories specified in'),etpConst['repositoriesconf'],)
            self.progressLog( msg, extra = "repositories")
            self.disable_ugc = False
            return 127
        except exceptionTools.OnlineMirrorError:
            self.progressLog(_('You are not connected to the Internet. You should.'), extra = "repositories")
            self.disable_ugc = False
            return 126
        except Exception, e:
            msg = "%s: %s" % (_('Unhandled exception'),e,)
            self.progressLog(msg, extra = "repositories")
            self.disable_ugc = False
            return 2
        rc = repoConn.sync()
        if repoConn.syncErrors or (rc != 0):
            self.progress.set_mainLabel(_('Errors updating repositories.'))
            self.progress.set_subLabel(_('Please check logs below for more info'))
        else:
            if repoConn.alreadyUpdated == 0:
                self.progress.set_mainLabel(_('Repositories updated successfully'))
            else:
                if len(repos) == repoConn.alreadyUpdated:
                    self.progress.set_mainLabel(_('All the repositories were already up to date.'))
                else:
                    msg = "%s %s" % (repoConn.alreadyUpdated,_("repositories were already up to date. Others have been updated."),)
                    self.progress.set_mainLabel(msg)
            if repoConn.newEquo:
                self.progress.set_extraLabel(_('sys-apps/entropy needs to be updated as soon as possible.'))

        initConfig_entropyConstants(etpSys['rootdir'])

        self.disable_ugc = False
        return not repoConn.syncErrors

    def resetProgressText(self):
        self.progress.set_mainLabel(_('Nothing to do. I am idle.'))
        self.progress.set_subLabel(_('Really, don\'t waste your time here. This is just a placeholder'))
        self.progress.set_extraLabel(_('I am still alive and kickin\''))

    def resetQueueProgressBars(self):
        self.progress.reset_progress()
        self.progress.total.clear()

    def setupRepoView(self):
        self.repoView.populate()

    def setBusy(self):
        self.isBusy = True
        busyCursor(self.ui.main)

    def unsetBusy(self):
        self.isBusy = False
        normalCursor(self.ui.main)

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

    def progressLog(self, msg, extra = None):
        self.progress.set_subLabel( msg )
        self.progress.set_progress( 0, " " ) # Blank the progress bar.
        if extra:
            self.output.write_line(extra+": "+msg+"\n")
        else:
            self.output.write_line(msg+"\n")

    def progressLogWrite(self, msg, extra = None):
        if extra:
            self.output.write_line(extra+": "+msg+"\n")
        else:
            self.output.write_line(msg+"\n")

    def enableSkipMirror(self):
        self.ui.skipMirror.show()
        self.skipMirror = True

    def disableSkipMirror(self):
        self.ui.skipMirror.hide()
        self.skipMirror = False

    def addPackages(self):

        action = self.lastPkgPB
        if action == 'all':
            masks = ['installed','available']
        else:
            masks = [action]

        self.disable_ugc = True
        self.setBusy()
        bootstrap = False
        if (self.Equo.get_world_update_cache(empty_deps = False) == None):
            bootstrap = True
            self.setPage('output')
        elif (self.Equo.get_available_packages_cache() == None) and ('available' in masks):
            bootstrap = True
            self.setPage('output')
        self.progress.total.hide()

        self.etpbase.clearPackages()
        if bootstrap:
            self.etpbase.clearCache()
            self.startWorking()

        allpkgs = []
        if self.doProgress: self.progress.total.next() # -> Get lists
        self.progress.set_mainLabel(_('Generating Metadata, please wait.'))
        self.progress.set_subLabel(_('Entropy is indexing the repositories. It will take a few seconds'))
        self.progress.set_extraLabel(_('While you are waiting, take a break and look outside. Is it rainy?'))
        for flt in masks:
            msg = "%s: %s" % (_('Calculating'),flt,)
            self.setStatus(msg)
            allpkgs += self.etpbase.getPackages(flt)
        if self.doProgress: self.progress.total.next() # -> Sort Lists

        if action == "updates":
            msg = "%s: available" % (_('Calculating'),)
            self.setStatus(msg)
            self.etpbase.getPackages("available")

        if bootstrap:
            self.endWorking()

        empty = False
        if not allpkgs and action == "updates":
            allpkgs = self.etpbase.getPackages('fake_updates')
            empty = True

        if bootstrap: time.sleep(3)
        self.setStatus("%s: %s %s" % (_("Showing"),len(allpkgs),_("items"),))

        self.pkgView.populate(allpkgs, empty = empty)
        self.progress.total.show()

        if self.doProgress: self.progress.hide() #Hide Progress
        if bootstrap:
            self.setPage('packages')

        self.unsetBusy()
        # reset labels
        self.resetProgressText()
        self.resetQueueProgressBars()
        self.disable_ugc = False

    def processPackageQueue(self, pkgs, remove_repos = []):

        # preventive check against other instances
        locked = self.Equo.application_lock_check()
        if locked:
            okDialog(self.ui.main, _("Another Entropy instance is running. Cannot process queue."))
            self.progress.reset_progress()
            self.setPage('packages')
            return False

        self.disable_ugc = True
        self.setStatus( _( "Running tasks" ) )
        total = len( pkgs['i'] )+len( pkgs['u'] )+len( pkgs['r'] ) +len( pkgs['rr'] )
        state = True
        if total > 0:
            self.startWorking(do_busy = True)
            normalCursor(self.ui.main)
            self.progress.show()
            self.progress.set_mainLabel( _( "Processing Packages in queue" ) )

            queue = pkgs['i']+pkgs['u']+pkgs['rr']
            install_queue = [x.matched_atom for x in queue]
            removal_queue = [x.matched_atom[0] for x in pkgs['r']]
            do_purge_cache = set([x.matched_atom[0] for x in pkgs['r'] if x.do_purge])
            if install_queue or removal_queue:
                controller = QueueExecutor(self)
                try:
                    e,i = controller.run(install_queue[:], removal_queue[:], do_purge_cache)
                except exceptionTools.QueueError:
                    e = 1
                self.ui.skipMirror.hide()
                self.ui.abortQueue.hide()
                if e != 0:
                    okDialog(   self.ui.main,
                                _("Attention. An error occured when processing the queue."
                                    "\nPlease have a look in the processing terminal.")
                    )
                self.endWorking()
                self.etpbase.clearPackages()
                time.sleep(5)
            self.endWorking()
            self.progress.reset_progress()
            self.etpbase.clearPackages()
            self.etpbase.clearCache()
            for myrepo in remove_repos:
                self.Equo.removeRepository(myrepo)
            self.Equo.closeAllRepositoryDatabases()
            self.Equo.reopenClientDbconn()
            # regenerate packages information

            self.setupSpritz()
            self.Equo.FileUpdates.scanfs(dcache = False)
            if self.Equo.FileUpdates.scandata:
                if len(self.Equo.FileUpdates.scandata) > 0:
                    self.setPage('filesconf')
            #self.progress.hide()
        else:
            self.setStatus( _( "No packages selected" ) )

        self.disable_ugc = False
        return state

    def populateCategories(self):
        self.setBusy()
        self.etpbase.populateCategories()
        self.catsView.populate(self.etpbase.getCategories())
        self.unsetBusy()

    def populateCategoryPackages(self, cat):
        pkgs = self.etpbase.getPackagesByCategory(cat)
        self.catPackages.populate(pkgs,self.ui.tvCatPackages)

####### events

    def __getSelectedRepoIndex( self ):
        selection = self.repoView.view.get_selection()
        repodata = selection.get_selected()
        # get text
        if repodata[1] != None:
            repoid = self.repoView.get_repoid(repodata)
            # do it if it's enabled
            if repoid in etpRepositoriesOrder:
                idx = etpRepositoriesOrder.index(repoid)
                return idx, repoid, repodata
        return None, None, None

    def runEditor(self, filename, delete = False):
        cmd = ' '.join([self.fileEditor,filename])
        task = entropyTools.parallelTask(self.__runEditor, cmd, delete, filename)
        task.start()

    def __runEditor(self, cmd, delete, filename):
        os.system(cmd+"&> /dev/null")
        if delete and os.path.isfile(filename) and os.access(filename,os.W_OK):
            try:
                os.remove(filename)
            except OSError:
                pass

    def __get_Edit_filename(self):
        selection = self.filesView.view.get_selection()
        model, iterator = selection.get_selected()
        if model != None and iterator != None:
            identifier = model.get_value( iterator, 0 )
            destination = model.get_value( iterator, 2 )
            source = model.get_value( iterator, 1 )
            source = os.path.join(os.path.dirname(destination),source)
            return identifier, source, destination
        return 0,None,None

    def on_updateAdvSelected_clicked( self, widget ):

        if not self.etpbase.selected_advisory_item:
            return

        key, affected, data = self.etpbase.selected_advisory_item
        if not affected:
            okDialog( self.ui.main, _("The chosen package is not vulnerable") )
            return
        atoms = set()
        for mykey in data['affected']:
            affected_data = data['affected'][mykey][0]
            atoms |= set(affected_data['unaff_atoms'])

        self.add_atoms_to_queue(atoms)
        if rc: okDialog( self.ui.main, _("Packages in Advisory have been queued.") )

    def on_updateAdvAll_clicked( self, widget ):

        adv_data = self.Advisories.get_advisories_metadata()
        atoms = set()
        for key in adv_data:
            affected = self.Advisories.is_affected(key)
            if not affected:
                continue
            for mykey in adv_data[key]['affected']:
                affected_data = adv_data[key]['affected'][mykey][0]
                atoms |= set(affected_data['unaff_atoms'])

        rc = self.add_atoms_to_queue(atoms)
        if rc: okDialog( self.ui.main, _("Packages in all Advisories have been queued.") )

    def add_atoms_to_queue(self, atoms):

        self.setBusy()
        # resolve atoms
        matches = set()
        for atom in atoms:
            match = self.Equo.atomMatch(atom)
            if match[0] != -1:
                matches.add(match)
        if not matches:
            okDialog( self.ui.main, _("Packages not found in repositories, try again later.") )
            self.unsetBusy()
            return

        resolved = []
        self.etpbase.getPackages('updates')
        self.etpbase.getPackages('available')
        self.etpbase.getPackages('reinstallable')
        for match in matches:
            resolved.append(self.etpbase.getPackageItem(match,True)[0])

        for obj in resolved:
            if obj in self.queue.packages['i'] + \
                        self.queue.packages['u'] + \
                        self.queue.packages['r'] + \
                        self.queue.packages['rr']:
                continue
            oldqueued = obj.queued
            obj.queued = 'u'
            status, myaction = self.queue.add(obj)
            if status != 0:
                obj.queued = oldqueued
            self.queueView.refresh()
            self.ui.viewPkg.queue_draw()

        self.unsetBusy()
        return True


    def on_advInfoButton_clicked( self, widget ):
        if self.etpbase.selected_advisory_item:
            self.loadAdvInfoMenu(self.etpbase.selected_advisory_item)

    def on_pkgInfoButton_clicked( self, widget ):
        if self.etpbase.selected_treeview_item:
            self.loadPkgInfoMenu(self.etpbase.selected_treeview_item)

    def on_filesDelete_clicked( self, widget ):
        identifier, source, dest = self.__get_Edit_filename()
        if not identifier:
            return True
        self.Equo.FileUpdates.remove_file(identifier)
        self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_filesMerge_clicked( self, widget ):
        identifier, source, dest = self.__get_Edit_filename()
        if not identifier:
            return True
        self.Equo.FileUpdates.merge_file(identifier)
        self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_mergeFiles_clicked( self, widget ):
        self.Equo.FileUpdates.scanfs(dcache = True)
        keys = self.Equo.FileUpdates.scandata.keys()
        for key in keys:
            self.Equo.FileUpdates.merge_file(key)
            # it's cool watching it runtime
            self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_deleteFiles_clicked( self, widget ):
        self.Equo.FileUpdates.scanfs(dcache = True)
        keys = self.Equo.FileUpdates.scandata.keys()
        for key in keys:
            self.Equo.FileUpdates.remove_file(key)
            # it's cool watching it runtime
            self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_filesEdit_clicked( self, widget ):
        identifier, source, dest = self.__get_Edit_filename()
        if not identifier:
            return True
        self.runEditor(source)

    def on_filesView_row_activated( self, widget, iterator, path ):
        self.on_filesViewChanges_clicked(widget)

    def on_filesViewChanges_clicked( self, widget ):
        identifier, source, dest = self.__get_Edit_filename()
        if not identifier:
            return True
        randomfile = entropyTools.getRandomTempFile()+".diff"
        diffcmd = "diff -Nu "+dest+" "+source+" > "+randomfile
        os.system(diffcmd)
        self.runEditor(randomfile, delete = True)

    def on_switchBranch_clicked( self, widget ):
        branch = inputBox(self.ui.main, _("Branch switching"), _("Enter a valid branch you want to switch to")+"     ", input_text = etpConst['branch'])
        branches = self.Equo.listAllAvailableBranches()
        if branch not in branches:
            okDialog( self.ui.main, _("The selected branch is not available.") )
        else:
            self.Equo.move_to_branch(branch)
            msg = "%s %s. %s." % (_("New branch is"),etpConst['branch'],_("It is suggested to synchronize repositories"),)
            okDialog( self.ui.main, msg )

    def on_shiftUp_clicked( self, widget ):
        idx, repoid, iterdata = self.__getSelectedRepoIndex()
        if idx != None:
            path = iterdata[0].get_path(iterdata[1])[0]
            if path > 0 and idx > 0:
                idx -= 1
                self.Equo.shiftRepository(repoid, idx)
                # get next iter
                prev = iterdata[0].get_iter(path-1)
                self.repoView.store.swap(iterdata[1],prev)

    def on_shiftDown_clicked( self, widget ):
        idx, repoid, iterdata = self.__getSelectedRepoIndex()
        if idx != None:
            next = iterdata[0].iter_next(iterdata[1])
            if next:
                idx += 1
                self.Equo.shiftRepository(repoid, idx)
                self.repoView.store.swap(iterdata[1],next)

    def on_mirrorDown_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        # get text
        if urldata[1] != None:
            next = urldata[0].iter_next(urldata[1])
            if next:
                self.repoMirrorsView.store.swap(urldata[1],next)

    def on_mirrorUp_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        # get text
        if urldata[1] != None:
            path = urldata[0].get_path(urldata[1])[0]
            if path > 0:
                # get next iter
                prev = urldata[0].get_iter(path-1)
                self.repoMirrorsView.store.swap(urldata[1],prev)

    def on_repoMirrorAdd_clicked( self, widget ):
        text = inputBox(self.addrepo_ui.addRepoWin, _("Insert URL"), _("Enter a download mirror, HTTP or FTP")+"   ")
        # call liststore and tell to add
        if text:
            # validate url
            if not (text.startswith("http://") or text.startswith("ftp://") or text.startswith("file://")):
                okDialog( self.addrepo_ui.addRepoWin, _("You must enter either a HTTP or a FTP url.") )
            else:
                self.repoMirrorsView.add(text)

    def on_repoMirrorRemove_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        if urldata[1] != None:
            self.repoMirrorsView.remove(urldata)

    def on_repoMirrorEdit_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        # get text
        if urldata[1] != None:
            text = self.repoMirrorsView.get_text(urldata)
            self.repoMirrorsView.remove(urldata)
            text = inputBox(self.addrepo_ui.addRepoWin, _("Insert URL"), _("Enter a download mirror, HTTP or FTP")+"   ", input_text = text)
            # call liststore and tell to add
            self.repoMirrorsView.add(text)

    def on_addRepo_clicked( self, widget ):
        self.addrepo_ui.repoSubmit.show()
        self.addrepo_ui.repoSubmitEdit.hide()
        self.addrepo_ui.repoInsert.show()
        self.addrepo_ui.repoidEntry.set_editable(True)
        self.addrepo_ui.repodbcformatEntry.set_active(0)
        self.addrepo_ui.repoidEntry.set_text("")
        self.addrepo_ui.repoDescEntry.set_text("")
        self.addrepo_ui.repodbEntry.set_text("")
        self.addrepo_ui.addRepoWin.show()
        self.repoMirrorsView.populate()

    def __loadRepodata(self, repodata):
        self.addrepo_ui.repoidEntry.set_text(repodata['repoid'])
        self.addrepo_ui.repoDescEntry.set_text(repodata['description'])
        self.addrepo_ui.repodbPort.set_text(str(repodata['service_port']))
        self.addrepo_ui.repodbPortSSL.set_text(str(repodata['ssl_service_port']))
        self.repoMirrorsView.store.clear()
        for x in repodata['plain_packages']:
            self.repoMirrorsView.add(x)
        idx = 0
        # XXX hackish way fix it
        while idx < 100:
            self.addrepo_ui.repodbcformatEntry.set_active(idx)
            if repodata['dbcformat'] == self.addrepo_ui.repodbcformatEntry.get_active_text():
                break
            idx += 1
        self.addrepo_ui.repodbEntry.set_text(repodata['plain_database'])

    def on_repoSubmitEdit_clicked( self, widget ):
        repodata = self.__getRepodata()
        errors = self.__validateRepoSubmit(repodata, edit = True)
        if errors:
            msg = "%s: %s" % (_("Wrong entries, errors"),', '.join(errors),)
            okDialog( self.addrepo_ui.addRepoWin, msg )
            return True
        else:
            disable = False
            if etpRepositoriesExcluded.has_key(repodata['repoid']):
                disable = True
            self.Equo.removeRepository(repodata['repoid'], disable = disable)
            if not disable:
                self.Equo.addRepository(repodata)
            self.setupRepoView()
            self.addrepo_ui.addRepoWin.hide()
            msg = "%s '%s' %s" % (_("You should press the button"),_("Regenerate Cache"),_("now"))
            okDialog( self.ui.main, msg )

    def __validateRepoSubmit(self, repodata, edit = False):
        errors = []
        if not repodata['repoid']:
            errors.append(_('No Repository Identifier'))
        if repodata['repoid'] and etpRepositories.has_key(repodata['repoid']):
            if not edit:
                errors.append(_('Duplicated Repository Identifier'))
        if not repodata['description']:
            repodata['description'] = "No description"
        if not repodata['plain_packages']:
            errors.append(_("No download mirrors"))
        if not repodata['plain_database'] or not (repodata['plain_database'].startswith("http://") or repodata['plain_database'].startswith("ftp://") or repodata['plain_database'].startswith("file://")):
            errors.append(_("Database URL must start either with http:// or ftp:// or file://"))

        if not repodata['service_port']:
            repodata['service_port'] = int(etpConst['socket_service']['port'])
        else:
            try:
                repodata['service_port'] = int(repodata['service_port'])
            except (ValueError,):
                errors.append(_("Repository Services Port not valid"))

        if not repodata['ssl_service_port']:
            repodata['ssl_service_port'] = int(etpConst['socket_service']['ssl_port'])
        else:
            try:
                repodata['ssl_service_port'] = int(repodata['ssl_service_port'])
            except (ValueError,):
                errors.append(_("Secure Services Port not valid"))
        return errors

    def __getRepodata(self):
        repodata = {}
        repodata['repoid'] = self.addrepo_ui.repoidEntry.get_text()
        repodata['description'] = self.addrepo_ui.repoDescEntry.get_text()
        repodata['plain_packages'] = self.repoMirrorsView.get_all()
        repodata['dbcformat'] = self.addrepo_ui.repodbcformatEntry.get_active_text()
        repodata['plain_database'] = self.addrepo_ui.repodbEntry.get_text()
        repodata['service_port'] = self.addrepo_ui.repodbPort.get_text()
        repodata['ssl_service_port'] = self.addrepo_ui.repodbPortSSL.get_text()
        return repodata

    def on_repoSubmit_clicked( self, widget ):
        repodata = self.__getRepodata()
        # validate
        errors = self.__validateRepoSubmit(repodata)
        if not errors:
            self.Equo.addRepository(repodata)
            self.setupRepoView()
            self.addrepo_ui.addRepoWin.hide()
            msg = "%s '%s' %s" % (_("You should press the button"),_("Update Repositories"),_("now"))
            okDialog( self.ui.main, msg )
        else:
            msg = "%s: %s" % (_("Wrong entries, errors"),', '.join(errors),)
            okDialog( self.addrepo_ui.addRepoWin, msg )

    def on_addRepoWin_delete_event(self, widget, path):
        return True

    def on_repoCancel_clicked( self, widget ):
        self.addrepo_ui.addRepoWin.hide()

    def on_repoInsert_clicked( self, widget ):
        text = inputBox(self.addrepo_ui.addRepoWin, _("Insert Repository"), _("Insert Repository identification string")+"   ")
        if text:
            if (text.startswith("repository|")) and (len(text.split("|")) == 5):
                repoid, repodata = const_extractClientRepositoryParameters(text)
                self.__loadRepodata(repodata)
            else:
                okDialog( self.addrepo_ui.addRepoWin, _("This Repository identification string is malformed") )

    def on_removeRepo_clicked( self, widget ):
        # get selected repo
        selection = self.repoView.view.get_selection()
        repodata = selection.get_selected()
        # get text
        if repodata[1] != None:
            repoid = self.repoView.get_repoid(repodata)
            if repoid == etpConst['officialrepositoryid']:
                okDialog( self.ui.main, _("You! Why do you want to remove the main repository ?"))
                return True
            self.Equo.removeRepository(repoid)
            self.setupRepoView()
            msg = "%s '%s' %s '%s' %s" % (_("You must now either press the"),_("Update Repositories"),_("or the"),_("Regenerate Cache"),_("now"))
            okDialog( self.ui.main, msg )

    def on_repoEdit_clicked( self, widget ):
        self.addrepo_ui.repoSubmit.hide()
        self.addrepo_ui.repoSubmitEdit.show()
        self.addrepo_ui.repoInsert.hide()
        self.addrepo_ui.repoidEntry.set_editable(False)
        # get selection
        selection = self.repoView.view.get_selection()
        repostuff = selection.get_selected()
        if repostuff[1] != None:
            repoid = self.repoView.get_repoid(repostuff)
            repodata = entropyTools.getRepositorySettings(repoid)
            self.__loadRepodata(repodata)
            self.addrepo_ui.addRepoWin.show()

    def on_terminal_clear_activate(self, widget):
        self.output.text_written = []
        self.console.reset()

    def on_terminal_copy_activate(self, widget):
        self.clipboard.clear()
        self.clipboard.set_text(''.join(self.output.text_written))

    def on_Preferences_toggled(self, widget, toggle = True):
        self.ui.preferencesSaveButton.set_sensitive(toggle)
        self.ui.preferencesRestoreButton.set_sensitive(toggle)

    def on_preferencesSaveButton_clicked(self, widget):
        sure = questionDialog(self.ui.main, _("Are you sure ?"))
        if not sure:
            return
        for config_file in self.Preferences:
            for name, setting, mytype, fillfunc, savefunc, wgwrite, wgread in self.Preferences[config_file]:
                if mytype == list:
                    savefunc(config_file, name, setting, mytype, wgwrite, wgread)
                else:
                    data = wgread()
                    result = savefunc(config_file, name, setting, mytype, data)
                    if not result:
                        errorMessage(
                            self.ui.main,
                            cleanMarkupString("%s: %s") % (_("Error saving parameter"),name,),
                            _("An issue occured while saving a preference"),
                            "%s %s: %s" % (_("Parameter"),name,_("not saved"),),
                        )
        initConfig_entropyConstants(etpConst['systemroot'])
        # re-read configprotect
        self.Equo.parse_masking_settings()
        self.Equo.reloadRepositoriesConfigProtect()
        self.setupPreferences()

    def on_preferencesRestoreButton_clicked(self, widget):
        self.setupPreferences()

    def on_configProtectNew_clicked(self, widget):
        data = inputBox( self.ui.main, _("New"), _("Please insert a new path"))
        if not data:
            return
        self.configProtectModel.append([data])

    def on_configProtectMaskNew_clicked(self, widget):
        data = inputBox( self.ui.main, _("New"), _("Please insert a new path"))
        if not data:
            return
        self.configProtectMaskModel.append([data])

    def on_configProtectSkipNew_clicked(self, widget):
        data = inputBox( self.ui.main, _("New"), _("Please insert a new path"))
        if not data:
            return
        self.configProtectSkipModel.append([data])

    def on_configProtectDelete_clicked(self, widget):
        model, myiter = self.configProtectView.get_selection().get_selected()
        if myiter:
            model.remove(myiter)

    def on_configProtectMaskDelete_clicked(self, widget):
        model, myiter = self.configProtectMaskView.get_selection().get_selected()
        if myiter:
            model.remove(myiter)

    def on_configProtectSkipDelete_clicked(self, widget):
        model, myiter = self.configProtectSkipView.get_selection().get_selected()
        if myiter:
            model.remove(myiter)

    def on_configProtectEdit_clicked(self, widget):
        model, myiter = self.configProtectView.get_selection().get_selected()
        if myiter:
            item = model.get_value( myiter, 0 )
            data = inputBox( self.ui.main, _("New"), _("Please edit the selected path"), input_text = item)
            if not data:
                return
            model.remove(myiter)
            self.configProtectModel.append([data])

    def on_configProtectMaskEdit_clicked(self, widget):
        model, myiter = self.configProtectMaskView.get_selection().get_selected()
        if myiter:
            item = model.get_value( myiter, 0 )
            data = inputBox( self.ui.main, _("New"), _("Please edit the selected path"), input_text = item)
            if not data:
                return
            model.remove(myiter)
            self.configProtectMaskModel.append([data])

    def on_configProtectSkipEdit_clicked(self, widget):
        model, myiter = self.configProtectSkipView.get_selection().get_selected()
        if myiter:
            item = model.get_value( myiter, 0 )
            data = inputBox( self.ui.main, _("New"), _("Please edit the selected path"), input_text = item)
            if not data:
                return
            model.remove(myiter)
            self.configProtectSkipModel.append([data])

    def on_installPackageItem_activate(self, widget = None, fn = None):

        if (widget and self.isWorking) or self.isBusy:
            return

        if not fn:
            mypattern = '*'+etpConst['packagesext']
            fn = FileChooser(pattern = mypattern)
        if not fn:
            return
        elif not os.access(fn,os.R_OK):
            return

        msg = "%s: %s. %s" % (
            _("You have chosen to install this package"),
            os.path.basename(fn),
            _("Are you supa sure?"),
        )
        rc = questionDialog(self.ui.main, msg)
        if not rc:
            return

        self.pkgView.store.clear()

        newrepo = os.path.basename(fn)
        # we have it !
        status, atomsfound = self.Equo.add_tbz2_to_repos(fn)
        if status != 0:
            errtxt = _("is not a valid Entropy package")
            if status == -3:
                errtxt = _("is not compiled with the same architecture of the system")
            mytxt = "%s %s. %s." % (
                os.path.basename(fn),
                errtxt,
                _("Cannot install"),
            )
            okDialog(self.ui.main, mytxt)
            return

        def clean_n_quit(newrepo):
            self.etpbase.clearPackages()
            self.etpbase.clearCache()
            self.Equo.removeRepository(newrepo)
            self.Equo.closeAllRepositoryDatabases()
            self.Equo.reopenClientDbconn()
            # regenerate packages information
            self.setupSpritz()

        if not atomsfound:
            clean_n_quit(newrepo)
            return

        pkgs = []
        for idpackage, atom in atomsfound:
            yp, new = self.etpbase.getPackageItem((idpackage,newrepo,),True)
            yp.action = 'i'
            yp.queued = 'i'
            pkgs.append(yp)

        busyCursor(self.ui.main)
        status, myaction = self.queue.add(pkgs)
        if status != 0:
            for obj in pkgs:
                obj.queued = None
            clean_n_quit(newrepo)
            normalCursor(self.ui.main)
            return

        normalCursor(self.ui.main)
        self.setPage('output')

        rc = self.processPackageQueue(self.queue.packages, remove_repos = [newrepo])
        self.resetQueueProgressBars()
        if rc:
            self.queue.clear()
            self.queueView.refresh()
            return True
        else: # not done
            clean_n_quit(newrepo)
            return False


    def on_PageButton_pressed( self, widget, page ):
        pass

    def on_PageButton_changed( self, widget, page ):

        ''' Left Side Toolbar Handler'''
        # do not put here actions for 'packages' and 'output' but use on_PageButton_pressed
        if page == "filesconf":
            self.populateFilesUpdate()
        elif page == "glsa":
            self.populateAdvisories(None,'affected')
        self.setNotebookPage(const.PAGES[page])

    def on_pkgFilter_toggled(self,rb,action):
        ''' Package Type Selection Handler'''
        if rb.get_active(): # Only act on select, not deselect.
            rb.grab_add()
            self.lastPkgPB = action
            # Only show add/remove all when showing updates
            if action == 'updates':
                self.ui.updatesButtonbox.show()
            else:
                self.ui.updatesButtonbox.hide()
            if action == "masked":
                self.setupMaskedPackagesWarningBox()
                self.ui.maskedWarningBox.show()
            else:
                self.ui.maskedWarningBox.hide()

            self.addPackages()
            rb.grab_remove()

    def on_repoRefresh_clicked(self,widget):
        repos = self.repoView.get_selected()
        if not repos:
            okDialog( self.ui.main, _("Please select at least one repository") )
            return
        self.setPage('output')
        self.startWorking()
        status = self.updateRepositories(repos)
        # clear cache here too
        self.endWorking()
        self.etpbase.clearCache()
        self.setupRepoView()
        self.setupSpritz()
        self.setupAdvisories()
        self.setPage('repos')
        if status:
            self.showNoticeBoard()

    def on_cacheButton_clicked(self,widget):
        self.repoView.get_selected()
        self.setPage('output')
        self.cleanEntropyCaches(alone = True)

    def on_repoDeSelect_clicked(self,widget):
        self.repoView.deselect_all()


    def on_queueDel_clicked( self, widget ):
        """ Delete from Queue Button Handler """
        self.queueView.deleteSelected()

    def on_queueProcess_clicked( self, widget ):
        """ Process Queue Button Handler """
        if self.queue.total() == 0: # Check there are any packages in the queue
            self.setStatus(_('No packages in queue'))
            return

        rc = self.processPackageQueue(self.queue.packages)
        self.resetQueueProgressBars()
        if rc:
            self.queue.clear()       # Clear package queue
            self.queueView.refresh() # Refresh Package Queue

    def on_queueSave_clicked( self, widget ):
        fn = FileChooser()
        if fn:
            pkgdata = self.queue.get()
            keys = pkgdata.keys()
            for key in keys:
                if pkgdata[key]:
                    pkgdata[key] = [str(x) for x in pkgdata[key]]
            self.Equo.dumpTools.dumpobj(fn,pkgdata,True)

    def on_queueOpen_clicked( self, widget ):
        fn = FileChooser()
        if fn:
            try:
                pkgdata = self.Equo.dumpTools.loadobj(fn,True)
            except:
                return

            try:
                pkgdata_keys = pkgdata.keys()
            except:
                return
            packages = self.etpbase.getAllPackages()
            collected_items = []
            for key in pkgdata_keys:
                for pkg in pkgdata[key]:
                    found = False
                    for x in packages:
                        if (pkg == str(x)) and (x.action == key):
                            found = True
                            collected_items.append([key,x])
                            break
                    if not found:
                        okDialog( self.ui.main, _("Queue is too old. Cannot load.") )
                        return

            for pkgtuple in collected_items:
                key = pkgtuple[0]
                pkg = pkgtuple[1]
                pkg.queued = key
                self.queue.packages[key].append(pkg)

            self.queueView.refresh()


    def on_adv_doubleclick( self, widget, iterator, path ):
        """ Handle selection of row in package view (Show Descriptions) """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            data = model.get_value( iterator, 0 )
            if data:
                self.loadAdvInfoMenu(data)

    def loadAdvInfoMenu(self, item):
        my = SecurityAdvisoryMenu(self.ui.main)
        my.load(item)

    def loadPkgInfoMenu(self, pkg):
        mymenu = PkgInfoMenu(self.Equo, pkg, self.ui.main)
        load_count = 6
        while 1:
            try:
                mymenu.load()
            except:
                if load_count < 0:
                    raise
                load_count -= 1
                time.sleep(1)
                continue
            break

    def on_pkg_doubleclick( self, widget, iterator, path ):
        """ Handle selection of row in package view (Show Descriptions) """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            pkg = model.get_value( iterator, 0 )
            if pkg:
                self.loadPkgInfoMenu(pkg)

    def on_license_double_clicked( self, widget, iterator, path ):
        """ Handle selection of row in package view (Show Descriptions) """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            license_identifier = model.get_value( iterator, 0 )
            found = False
            license_text = ''
            if license_identifier:
                repoid = self.pkgProperties_selected.matched_atom[1]
                if type(repoid) is int:
                    dbconn = self.Equo.clientDbconn
                else:
                    dbconn = self.Equo.openRepositoryDatabase(repoid)
                if dbconn.isLicensedataKeyAvailable(license_identifier):
                    license_text = dbconn.retrieveLicenseText(license_identifier)
                    found = True
            if found:
                # prepare textview
                mybuffer = gtk.TextBuffer()
                mybuffer.set_text(license_text)
                xml_licread = gtk.glade.XML( const.GLADE_FILE, 'licenseReadWindow',domain="entropy" )
                read_dialog = xml_licread.get_widget( "licenseReadWindow" )
                okReadButton = xml_licread.get_widget( "okReadButton" )
                okReadButton.connect( 'clicked', self.destroy_read_license_dialog )
                licenseView = xml_licread.get_widget( "licenseTextView" )
                licenseView.set_buffer(mybuffer)
                read_dialog.set_title(license_identifier+" license text")
                read_dialog.show_all()
                self.read_license_dialog = read_dialog

    def destroy_read_license_dialog( self, widget ):
        self.read_license_dialog.destroy()

    def on_select_clicked(self,widget):
        ''' Package Add All button handler '''
        self.setBusy()
        self.startWorking()
        self.wait_ui.waitWindow.show_all()
        busyCursor(self.wait_ui.waitWindow)
        self.pkgView.selectAll()
        self.endWorking()
        self.unsetBusy()
        normalCursor(self.wait_ui.waitWindow)
        self.wait_ui.waitWindow.hide()

    def on_deselect_clicked(self,widget):
        ''' Package Remove All button handler '''
        self.on_clear_clicked(widget)
        self.setBusy()
        self.pkgView.deselectAll()
        self.unsetBusy()

    def on_skipMirror_clicked(self,widget):
        self.skipMirrorNow = True

    def on_abortQueue_clicked(self,widget):
        msg = _("You have chosen to interrupt the queue processing. Doing so could be risky and you should let Entropy to close all its tasks. Are you sure you want it?")
        rc = questionDialog(self.ui.main, msg)
        if rc:
            self.abortQueueNow = True

    def queue_bombing(self):
        if self.abortQueueNow:
            self.abortQueueNow = False
            mytxt = _("Aborting queue tasks.")
            raise exceptionTools.QueueError('QueueError %s' % (mytxt,))

    def mirror_bombing(self):
        if self.skipMirrorNow:
            self.skipMirrorNow = False
            mytxt = _("Skipping current mirror.")
            raise exceptionTools.OnlineMirrorError('OnlineMirrorError %s' % (mytxt,))

    def on_search_clicked(self,widget):
        ''' Search entry+button handler'''
        txt = self.ui.pkgFilter.get_text()
        flt = filters.spritzFilter.get('KeywordFilter')
        if txt != '':
            flt.activate()
            lst = txt.split(' ')
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

    def on_comps_cursor_changed(self, widget):
        self.setBusy()
        """ Handle selection of row in Comps Category  view  """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            myid = model.get_value( iterator, 0 )
            self.populateCategoryPackages(myid)
        self.unsetBusy()

    def on_FileQuit( self, widget ):
        self.quit()

    def on_HelpAbout( self, widget = None ):
        about = AboutDialog(const.PIXMAPS_PATH+'/spritz-about.png',const.CREDITS,self.settings.branding_title)
        about.show()

    def on_notebook1_switch_page(self, widget, page, page_num):
        if page_num == const.PREF_PAGES['ugc']:
            self.load_ugc_repositories()

    def on_ugcLoginButton_clicked(self, widget):
        if self.Equo.UGC == None: return
        model, myiter = self.ugcRepositoriesView.get_selection().get_selected()
        if (myiter == None) or (model == None): return
        obj = model.get_value( myiter, 0 )
        if obj:
            logged_data = self.Equo.UGC.read_login(obj['repoid'])
            if logged_data:
                self.Equo.UGC.remove_login(obj['repoid'])
            self.Equo.UGC.login(obj['repoid'])
            self.load_ugc_repositories()

    def on_ugcClearLoginButton_clicked(self, widget):
        if self.Equo.UGC == None: return
        model, myiter = self.ugcRepositoriesView.get_selection().get_selected()
        if (myiter == None) or (model == None): return
        obj = model.get_value( myiter, 0 )
        if obj:
            if not self.Equo.UGC.is_repository_eapi3_aware(obj['repoid']): return
            logged_data = self.Equo.UGC.read_login(obj['repoid'])
            if logged_data: self.Equo.UGC.remove_login(obj['repoid'])
            self.load_ugc_repositories()

    def on_ugcClearCacheButton_clicked(self, widget):
        if self.Equo.UGC == None: return
        for repoid in list(set(etpRepositories.keys()+etpRepositoriesExcluded.keys())):
            self.Equo.UGC.UGCCache.clear_cache(repoid)
            self.setStatus("%s: %s ..." % (_("Cleaning UGC cache of"),repoid,))
        self.setStatus("%s" % (_("UGC cache cleared"),))

    def on_ugcClearCredentialsButton_clicked(self, widget):
        if self.Equo.UGC == None: return
        for repoid in list(set(etpRepositories.keys()+etpRepositoriesExcluded.keys())):
            if not self.Equo.UGC.is_repository_eapi3_aware(repoid): continue
            logged_data = self.Equo.UGC.read_login(repoid)
            if logged_data: self.Equo.UGC.remove_login(repoid)
        self.load_ugc_repositories()
        self.setStatus("%s" % (_("UGC credentials cleared"),))

    def on_bannerEventBox_button_release_event(self, widget, event):
        if self.ad_url != None:
            self.load_url(self.ad_url)

    def on_bannerEventBox_enter_notify_event(self, widget, event):
        busyCursor(self.ui.main, cur = gtk.gdk.Cursor(gtk.gdk.HAND2))

    def on_bannerEventBox_leave_notify_event(self, widget, event):
        busyCursor(self.ui.main, cur = CURRENT_CURSOR)

    def load_ugc_repositories(self):
        self.ugcRepositoriesModel.clear()
        for repoid in etpRepositoriesOrder+sorted(etpRepositoriesExcluded.keys()):
            self.ugcRepositoriesModel.append([etpRepositories[repoid]])

    def on_repoManagerMenuItem_activate(self, widget):
        mymenu = RepositoryManagerMenu(self.Equo, self.ui.main)
        rc = mymenu.load()
        if not rc: del mymenu

    def on_noticeBoardMenuItem_activate(self, widget):
        self.showNoticeBoard()


if __name__ == "__main__":

    def killThreads():
        # kill threads
        threads = entropyTools.threading.enumerate()
        for thread in threads:
            if thread.getName().startswith("download::"): # equo current download speed thread
                thread.kill()

    gtkEventThread = ProcessGtkEventsThread()
    try:
        gtkEventThread.start()
        try:
            gtk.window_set_default_icon_from_file(const.PIXMAPS_PATH+"/spritz-icon.png")
        except gobject.GError:
            pass
        mainApp = SpritzApplication()
        gobject.threads_init()
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()
        killThreads()
    except SystemExit:
        print "Quit by User"
        gtkEventThread.doQuit()
        killThreads()
        raise SystemExit
    except KeyboardInterrupt:
        print "Quit by User (KeyboardInterrupt)"
        gtkEventThread.doQuit()
        killThreads()
        raise SystemExit
    except: # catch other exception and write it to the logger.

        etype = sys.exc_info()[0]
        evalue = sys.exc_info()[1]
        etb = traceback.extract_tb(sys.exc_info()[2])
        errmsg = 'Error Type: %s \n' % str(etype)
        errmsg += 'Error Value: %s \n' % str(evalue)
        for tub in etb:
            f,l,m,c = tub # file,lineno, function, codeline
            errmsg += '  File : %s , line %s, in %s\n' % (f,str(l),m)
            errmsg += '    %s \n' % c

        conntest = entropyTools.get_remote_data(etpConst['conntestlink'])
        rc, (name,mail,description) = errorMessage(
            None,
            _( "Exception caught" ),
            _( "Spritz crashed! An unexpected error occured." ),
            errmsg,
            showreport = conntest
        )
        if rc == -1:
            error = ErrorReportInterface()
            error.prepare(errmsg, name, mail, description = description)
            result = error.submit()
            if result:
                okDialog(None,_("Your report has been submitted successfully! Thanks a lot."))
            else:
                okDialog(None,_("Cannot submit your report. Not connected to Internet?"))
        gtkEventThread.doQuit()
        killThreads()
        sys.exit(1)

    gtkEventThread.doQuit()
    killThreads()
