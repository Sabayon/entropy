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
import sys, os, pty
import logging
import traceback


# Entropy Imports
sys.path.append("../../libraries")
sys.path.append("../../client")
sys.path.append("/usr/lib/entropy/libraries")
sys.path.append("/usr/lib/entropy/client")
from entropyConstants import *
import exceptionTools
from packages import EntropyPackages
from entropyapi import EquoConnection,QueueExecutor

# GTK Imports
import gtk,gobject
from threading import Thread,Event
import thread
import exceptions
from etpgui.widgets import UI, Controller
from etpgui import *


# yumex imports
import filters
from gui import SpritzGUI
from dialogs import *
from misc import const, SpritzOptions, fakeoutfile, fakeinfile
from i18n import _
import time


class SpritzController(Controller):
    ''' This class contains all glade signal callbacks '''


    def __init__( self ):
        self.etpbase = EntropyPackages(EquoConnection)
        # Create and ui object contains the widgets.
        ui = UI( const.GLADE_FILE , 'main', 'yumex' )
        addrepo_ui = UI( const.GLADE_FILE , 'addRepoWin', 'yumex' )
        # init the Controller Class to connect signals.
        Controller.__init__( self, ui, addrepo_ui )

        self.clipboard = gtk.Clipboard()
        self.pty = pty.openpty()
        self.output = fakeoutfile(self.pty[1])
        self.input = fakeinfile(self.pty[1])
        sys.stdout = self.output
        sys.stderr = self.output
        sys.stdin = self.input


    def quit(self, widget=None, event=None ):
        EquoConnection.save_cache()
        ''' Main destroy Handler '''
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
        try:
            gtk.main_quit()       # Exit gtk
        except RuntimeError,e:
            pass
        sys.exit( 1 )         # Terminate Program

    def on_repoMirrorAdd_clicked( self, widget ):
        text = inputBox(self.addrepo_ui.addRepoWin, _("Insert URL"), _("Enter a download mirror, HTTP or FTP")+"   ")
        # call liststore and tell to add
        if text:
            # validate url
            if not (text.startswith("http://") or text.startswith("ftp://")):
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
        self.repoMirrorsView.store.clear()
        for x in repodata['packages']:
            self.repoMirrorsView.add(x)
        idx = 0
        # XXX hackish way fix it
        while idx < 100:
            self.addrepo_ui.repodbcformatEntry.set_active(idx)
            if repodata['dbcformat'] == self.addrepo_ui.repodbcformatEntry.get_active_text():
                break
            idx += 1
        self.addrepo_ui.repodbEntry.set_text(repodata['database'])

    def on_repoSubmitEdit_clicked( self, widget ):
        repodata = self.__getRepodata()
        errors = self.__validateRepoSubmit(repodata, edit = True)
        if errors:
            okDialog( self.addrepo_ui.addRepoWin, _("Wrong entries, errors: %s") % (', '.join(errors),) )
            return True
        else:
            self.Equo.removeRepository(repodata['repoid'])
            initConfig_entropyConstants(etpSys['rootdir'])
            self.Equo.addRepository(repodata)
            initConfig_entropyConstants(etpSys['rootdir'])
            self.setupRepoView()
            self.addrepo_ui.addRepoWin.hide()
            okDialog( self.ui.main, _("You should press the %s button now") % (_("Regenerate Cache")) )

    def __validateRepoSubmit(self, repodata, edit = False):
        errors = []
        if not repodata['repoid']:
            errors.append(_('No Repository Identifier'))
        if repodata['repoid'] and etpRepositories.has_key(repodata['repoid']):
            if not edit:
                errors.append(_('Duplicated Repository Identifier'))
        if not repodata['description']:
            repodata['description'] = "No description"
        if not repodata['packages']:
            errors.append(_("No download mirrors"))
        if not repodata['database'] or not (repodata['database'].endswith("http://") or (not repodata['database'].endswith("ftp://"))):
            errors.append(_("Database URL must be HTTP or FTP"))
        return errors

    def __getRepodata(self):
        repodata = {}
        repodata['repoid'] = self.addrepo_ui.repoidEntry.get_text()
        repodata['description'] = self.addrepo_ui.repoDescEntry.get_text()
        repodata['packages'] = self.repoMirrorsView.get_all()
        repodata['dbcformat'] = self.addrepo_ui.repodbcformatEntry.get_active_text()
        repodata['database'] = self.addrepo_ui.repodbEntry.get_text()
        return repodata

    def on_repoSubmit_clicked( self, widget ):
        repodata = self.__getRepodata()
        # validate
        errors = self.__validateRepoSubmit(repodata)
        if not errors:
            self.Equo.addRepository(repodata)
            self.setupRepoView()
            self.addrepo_ui.addRepoWin.hide()
            okDialog( self.ui.main, _("You should now press the %s button now") % (_("Update Repositories"),) )
        else:
            okDialog( self.addrepo_ui.addRepoWin, _("Wrong entries, errors: %s") % (', '.join(errors),) )

    def on_addRepoWin_delete_event(self, widget, path):
        return True

    def on_repoCancel_clicked( self, widget ):
        self.addrepo_ui.addRepoWin.hide()

    def on_repoInsert_clicked( self, widget ):
        text = inputBox(self.addrepo_ui.addRepoWin, _("Insert Repository"), _("Insert Repository identification string")+"   ")
        if text:
            if (text.startswith("repository|")) and (len(text.split("|")) == 5):
                # filling dict
                textdata = text.split("|")
                repodata = {}
                repodata['repoid'] = textdata[1]
                repodata['description'] = textdata[2]
                repodata['packages'] = textdata[3].split()
                repodata['database'] = textdata[4].split("#")[0]
                dbcformat = textdata[4].split("#")[-1]
                if dbcformat in etpConst['etpdatabasesupportedcformats']:
                    repodata['dbcformat'] = dbcformat
                else:
                    repodata['dbcformat'] = etpConst['etpdatabasesupportedcformats'][0]
                # fill window
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
            okDialog( self.ui.main, _("You must now either press the %s or the %s button") % (_("Regenerate Cache"),_("Update Repositories")) )

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
            repodata = self.Equo.entropyTools.getRepositorySettings(repoid)
            self.__loadRepodata(repodata)
            self.addrepo_ui.addRepoWin.show()

    def on_terminal_clear_activate(self, widget):
        self.output.text_written = []
        self.console.reset()

    def on_terminal_copy_activate(self, widget):
        self.clipboard.clear()
        self.clipboard.set_text(''.join(self.output.text_written))

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

            self.addPackages()
            rb.grab_remove()

    def on_repoRefresh_clicked(self,widget):
        repos = self.repoView.get_selected()
        if not repos:
            okDialog( self.ui.main, _("Please select at least one repository") )
            return
        self.setPage('output')
        self.logger.info( "Enabled repositories : %s" % ",".join(repos))
        self.updateRepositories(repos)
        self.setupSpritz()

    def on_cacheButton_clicked(self,widget):
        repos = self.repoView.get_selected()
        self.setPage('output')
        self.logger.info( "Cleaning cache")
        self.cleanEntropyCaches(alone = True)

    def on_repoDeSelect_clicked(self,widget):
        self.repoView.deselect_all()


    def on_queueDel_clicked( self, widget ):
        """ Delete from Queue Button Handler """
        self.queueView.deleteSelected()

    def on_queueQuickAdd_activate(self,widget):
        txt = widget.get_text()
        arglist = txt.split(' ')
        self.doQuickAdd(arglist[0],arglist[1:])

    def on_queueProcess_clicked( self, widget ):
        """ Process Queue Button Handler """
        if self.queue.total() == 0: # Check there are any packages in the queue
            self.setStatus(_('No packages in queue'))
            return

        rc = self.processPackageQueue(self.queue.packages)
        if rc:
            if rc == 'QUIT':
                self.quit()
            else:
                self.queue.clear()       # Clear package queue
                self.queueView.refresh() # Refresh Package Queue

    def on_queueSave_clicked( self, widget ):
        dialog = gtk.FileChooserDialog(title=None,action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        dialog.set_current_folder("/tmp")
        dialog.set_current_name('queue.spritz')
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
            msg = _('You are about to add %s packages and their dependencies\n') % len(self.pkgView.store)
            msg += _('Do you want to continue ?')
            if not questionDialog(self.ui.main,msg):
                return
        busyCursor(self.ui.main)
        self.pkgView.selectAll()
        normalCursor(self.ui.main)

    def on_deselect_clicked(self,widget):
        ''' Package Remove All button handler '''
        self.on_clear_clicked(widget)
        if len(self.pkgView.store) > 50:
            msg = _('You are about to remove %s packages and their depends\n') % len(self.pkgView.store)
            msg += _('Do you want to continue ?')
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

    def on_schSlot_toggled(self,rb):
        ''' Search Arch Checkbox handler'''
        if rb.get_active():
            self.ui.schSlotText.set_sensitive(True)
        else:
            self.ui.schSlotText.set_text("")
            self.ui.schSlotText.set_sensitive(False)
            self.on_schSlotText_activate(self.ui.schSlotText)

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


    def on_schSlotText_activate(self,entry):
        ''' Search Arch Entry handler'''
        txt = entry.get_text()
        flt = filters.yumexFilter.get('SlotFilter')
        if txt != '':
            flt.activate()
            lst = txt.split(',')
            self.logger.debug('Search Slot : %s' % ','.join(lst))
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
            if isCategory:
                self.populateCategoryPackages(id)

    def on_compsPkg_cursor_changed(self, widget):
        """ Handle selection of row in Comps Category  view  """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            pkg = model.get_value( iterator, 0 )
            if pkg:
                self.catDesc.clear()
                self.catDesc.write_line(pkg.description)


# Menu Handlers

    def on_FileQuit( self, widget ):
        self.quit()

    def on_EditPreferences( self, widget ):
        Preferences()
        self.spritzOptions.reload()
        self.settings = self.spritzOptions.settings

    def on_HelpAbout( self, widget ):
        about = AboutDialog(const.PIXMAPS_PATH+'/spritz-about.png',const.CREDITS,self.settings.branding_title)
        about.show()

    def on_ToolsRepoCache( self, widget ):
        self.logger.info(_('Cleaning up all yum metadata'))

class SpritzApplication(SpritzController,SpritzGUI):

    def __init__(self):
        SpritzController.__init__( self )
        self.spritzOptions = SpritzOptions()
        self.spritzOptions.parseCmdOptions()
        self.Equo = EquoConnection
        SpritzGUI.__init__(self, self.Equo, self.etpbase)
        self.logger = logging.getLogger("yumex.main")
        # init flags
        self.skipMirror = False
        self.skipMirrorNow = False
        self.doProgress = False
        self.categoryOn = False
        self.quitNow = False
        self.isWorking = False
        if self.settings.debug:
            self.spritzOptions.dump()
            print self.spritzOptions.getArgs()
        self.logger.info(_('Entropy Config Setuo'))
        self.spritzOptions.parseCmdOptions()
        self.catsView.etpbase = self.etpbase
        self.lastPkgPB = "updates"
        self.etpbase.setFilter(filters.yumexFilter.processFilters)

        # Setup GUI
        self.setupGUI()
        self.setPage("packages")

        self.logger.info(_('GUI Setup Completed'))
        # setup Repositories
        self.setupRepoView()
        self.firstTime = True
        # calculate updates
        self.Equo.connect_to_gui(self.progress, self.progressLogWrite, self.output)
        self.setupSpritz()

        self.console.set_pty(self.pty[0])
        # setup pty


    def startWorking(self):
        self.isWorking = True
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
        self.addPackages()
        # XXX: if we'll re-enable categories listing, uncomment this
        #self.progressLog(_('Building Category Lists'))
        #self.populateCategories()
        #self.progressLog(_('Building Category Lists Completed'))
        msg = _('Ready')
        self.setStatus(msg)

    def cleanEntropyCaches(self, alone = False):
        if alone:
            self.progress.total.hide()
        self.Equo.generate_cache(depcache = True, configcache = False)
        # clear views
        self.etpbase.clearPackages()
        self.setupSpritz()
        if alone:
            self.progress.total.show()

    def updateRepositories(self, repos):
        self.setPage('output')
        self.startWorking()

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
            return 1
        except exceptionTools.MissingParameter:
            self.progressLog(_('No repositories specified in %s') % (etpConst['repositoriesconf'],), extra = "repositories")
            return 127
        except exceptionTools.OnlineMirrorError:
            self.progressLog(_('You are not connected to the Internet. You should.'), extra = "repositories")
            return 126
        except Exception, e:
            self.progressLog(_('Unhandled exception: %s') % (str(e),), extra = "repositories")
            return 2
        rc = repoConn.sync()
        if repoConn.syncErrors:
            self.progress.set_mainLabel(_('Errors updating repositories.'))
            self.progress.set_subLabel(_('Please check logs below for more info'))
        else:
            if repoConn.alreadyUpdated == 0:
                self.progress.set_mainLabel(_('Repositories updated successfully'))
            else:
                if len(repos) == repoConn.alreadyUpdated:
                    self.progress.set_mainLabel(_('All the repositories were already up to date.'))
                else:
                    self.progress.set_mainLabel(_('%s repositories were already up to date. Others have been updated.' % (str(repoConn.alreadyUpdated),)))
            if repoConn.newEquo:
                self.progress.set_extraLabel(_('app-admin/equo needs to be updated as soon as possible.'))

        initConfig_entropyConstants(etpSys['rootdir'])
        self.setupRepoView()
        self.endWorking()


    def setupRepoView(self):
        self.repoView.populate()

    def addPackages(self):
        bootstrap = False
        if (self.Equo.get_world_update_cache(empty_deps = False) == None):
            bootstrap = True
            self.setPage('output')
        self.progress.total.hide()
        busyCursor(self.ui.main)
        action = self.lastPkgPB
        if action == 'all':
            masks = ['installed','available']
        else:
            masks = [action]
        self.pkgView.store.clear()
        self.etpbase.clearPackages()
        allpkgs = []
        if self.doProgress: self.progress.total.next() # -> Get lists
        for flt in masks:
            msg = _('Calculating %s' ) % flt
            #self.progressLog(msg)
            self.setStatus(msg)
            pkgs = self.etpbase.getPackages(flt)
            #self.progressLog(_('Found %d %s') % (len(pkgs),flt))
            allpkgs.extend(pkgs)
            self.setStatus(_("Ready"))
        if self.doProgress: self.progress.total.next() # -> Sort Lists
        allpkgs.sort()
        self.ui.viewPkg.set_model(None)
        for po in allpkgs:
            self.pkgView.store.append([po,str(po)])
        self.ui.viewPkg.set_model(self.pkgView.store)
        self.progress.total.show()

        normalCursor(self.ui.main)
        if self.doProgress: self.progress.hide() #Hide Progress
        if bootstrap:
            self.setPage('packages')

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
        getterfn = getattr( self.etpbase, fn )
        if para != '':
            lst, keys = getterfn( self.lastPkgPB, para )
        else:
            lst, keys = getterfn( self.lastPkgPB )
        fkeys = [ key for key in keys if lst.has_key(key)]
        if sortkeys:
            fkeys.sort()
        if not splitkeys:
            self.catView.populate(fkeys)
        else:
            keydict = self.splitCategoryKeys(fkeys)
            self.catView.populate(keydict,True)
        self.etpbase.setCategoryPackages(lst)
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
        self.setStatus( _( "Running tasks" ) )
        total = len( pkgs['i'] )+len( pkgs['u'] )+len( pkgs['r'] )
        state = True
        quit = False
        if total > 0:
            self.startWorking()
            self.progress.show()
            self.progress.set_mainLabel( _( "Processing Packages in queue" ) )
            # XXX handle return codes
            queue = pkgs['i']+pkgs['u']
            install_queue = [x.matched_atom for x in queue]
            removal_queue = [x.matched_atom[0] for x in pkgs['r']]
            if install_queue or removal_queue:
                controller = QueueExecutor(self)
                e,i = controller.run(install_queue, removal_queue)
                print e,i
            # regenerate packages information
            self.etpbase.clearPackages()
            self.setupSpritz()
            self.endWorking()
            #self.progress.hide()
            if quit:
                return "QUIT"
            return state
        else:
            self.setStatus( _( "No packages selected" ) )
            return state

    def get_confimation( self, task ):
        self.progress.hide( False )
        dlg = ConfimationDialog(self.ui.main, [], size )
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
            #self.etpbase._downloadPackages()
            self.disableSkipMirror()   # Disable SkipMirror
            # Skip Transaction is downloadonly is set.
            if not self.settings.downloadonly:
                self.progress.total.next() # -> Transaction Test
                self.progress.total.next() # -> Run  Transaction
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
                pkgs = self.etpbase.findPackagesByTuples(pType,dict[repo])
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
            found = self.etpbase.findPackages(arglist,typ)
            self.setStatus(_('found %d packages, matching : %s') % (len(found)," ".join(arglist)))
            for po in found:
                self.queue.add(po)
            self.queueView.refresh()

    def populateCategories(self):
        busyCursor(self.ui.main)
        self.etpbase.populateCategories()
        self.catsView.populate(self.etpbase.getCategories())
        normalCursor(self.ui.main)

    def populateCategoryPackages(self, cat):
        #grp = self.etpbase.comps.return_group(id)
        self.catDesc.clear()
        #if grp.description:
        #    self.catDesc.write_line(grp.description)
        #pkgs = self.etpbase._getByGroup(grp,['m','d','o'])
        #pkgs.sort()
        pkgs = self.etpbase.getPackagesByCategory(cat)
        self.catPackages.store.clear()
        self.ui.tvCatPackages.set_model(None)
        for po in pkgs:
            self.catPackages.store.append([po,str(po)])
        self.ui.tvCatPackages.set_model(self.catPackages.store)


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
        gtk.window_set_default_icon_from_file(const.PIXMAPS_PATH+"/spritz-icon.png")
        mainApp = SpritzApplication()
        gtk.main()
    except SystemExit, e:
        print "Quit by User"
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