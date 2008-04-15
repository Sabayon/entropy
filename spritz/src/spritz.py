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
import commands

# Entropy Imports
sys.path.insert(0,"../../libraries")
sys.path.insert(1,"../../client")
sys.path.insert(2,"/usr/lib/entropy/libraries")
sys.path.insert(3,"/usr/lib/entropy/client")
from entropyConstants import *
import exceptionTools
from packages import EntropyPackages
from entropyapi import EquoConnection, QueueExecutor
from entropy import ErrorReportInterface

# GTK Imports
import gtk,gobject
import thread
import exceptions
from etpgui.widgets import UI, Controller
from etpgui import *
from spritz_setup import fakeoutfile, fakeinfile,cleanMarkupSting


# spritz imports
import filters
from gui import SpritzGUI
from dialogs import *
from i18n import _
import time


class SpritzController(Controller):
    ''' This class contains all glade signal callbacks '''


    def __init__( self ):
        self.etpbase = EntropyPackages(EquoConnection)
        # Create and ui object contains the widgets.
        ui = UI( const.GLADE_FILE , 'main', 'spritz' )
        addrepo_ui = UI( const.GLADE_FILE , 'addRepoWin', 'spritz' )
        pkginfo_ui = UI( const.GLADE_FILE , 'pkgInfo', 'spritz' )
        wait_ui = UI( const.GLADE_FILE , 'waitWindow', 'spritz' )
        # init the Controller Class to connect signals.
        Controller.__init__( self, ui, addrepo_ui, pkginfo_ui, wait_ui )

        self.clipboard = gtk.Clipboard()
        self.pty = pty.openpty()
        self.output = fakeoutfile(self.pty[1])
        self.input = fakeinfile(self.pty[1])
        if "--debug" not in sys.argv:
            sys.stdout = self.output
            sys.stderr = self.output
            sys.stdin = self.input


    def quit(self, widget=None, event=None ):
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
        task = self.Equo.entropyTools.parallelTask(self.__runEditor, {'cmd': cmd, 'delete': delete,'file': filename})
        task.start()

    def __runEditor(self, data):
        os.system(data['cmd']+"&> /dev/null")
        delete = data['delete']
        if delete and os.path.isfile(data['file']):
            try:
                os.remove(data['file'])
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

    def on_advInfoButton_clicked( self, widget ):
        if self.etpbase.selected_advisory_item:
            print "load",self.etpbase.selected_advisory_item
            #self.loadAdvInfoMenu(self.etpbase.selected_advisory_item)

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
        randomfile = self.Equo.entropyTools.getRandomTempFile()+".diff"
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
        if not repodata['packages']:
            errors.append(_("No download mirrors"))
        if not repodata['database'] or not (repodata['database'].startswith("http://") or repodata['database'].startswith("ftp://") or repodata['database'].startswith("file://")):
            errors.append(_("Database URL must start either with http:// or ftp:// or file://"))
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
            repodata = self.Equo.entropyTools.getRepositorySettings(repoid)
            self.__loadRepodata(repodata)
            self.addrepo_ui.addRepoWin.show()

    def on_terminal_clear_activate(self, widget):
        self.output.text_written = []
        self.console.reset()

    def on_terminal_copy_activate(self, widget):
        self.clipboard.clear()
        self.clipboard.set_text(''.join(self.output.text_written))

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
        self.startWorking()
        self.updateRepositories(repos)
        # clear cache here too
        self.endWorking()
        self.etpbase.clearCache()
        self.setupRepoView()
        self.setupSpritz()
        self.setupAdvisories()
        self.setPage('repos')

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
            self.queue.clear()       # Clear package queue
            self.queueView.refresh() # Refresh Package Queue

    def on_queueSave_clicked( self, widget ):
        dialog = gtk.FileChooserDialog(title=None,action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        homedir = os.getenv('HOME')
        if not homedir:
            homedir = "/tmp"
        dialog.set_current_folder(homedir)
        dialog.set_current_name('queue.spritz')
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fn = dialog.get_filename()
        elif response == gtk.RESPONSE_CANCEL:
            fn = None
        dialog.destroy()
        if fn:
            self.logger.info("Saving queue to %s" % fn)
            pkgdata = self.queue.get()
            keys = pkgdata.keys()
            for key in keys:
                if pkgdata[key]:
                    pkgdata[key] = [str(x) for x in pkgdata[key]]
            self.Equo.dumpTools.dumpobj(fn,pkgdata,True)

    def on_queueOpen_clicked( self, widget ):
        dialog = gtk.FileChooserDialog(title=None,action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                  buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        homedir = os.getenv('HOME')
        if not homedir:
            homedir = "/tmp"
        dialog.set_current_folder(homedir)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fn = dialog.get_filename()
        elif response == gtk.RESPONSE_CANCEL:
            fn = None
        dialog.destroy()
        if fn:
            self.logger.info("Loading queue from %s" % fn)
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

    def on_pkg_doubleclick( self, widget, iterator, path ):
        """ Handle selection of row in package view (Show Descriptions) """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            pkg = model.get_value( iterator, 0 )
            if pkg:
                self.loadPkgInfoMenu(pkg)

    def loadPkgInfoMenu( self, pkg ):

        # set package image
        pkg_pixmap = const.PIXMAPS_PATH+'/package-x-generic.png'
        heart_pixmap = const.PIXMAPS_PATH+'/heart.png'

        self.pkginfo_ui.pkgImage.set_from_file(pkg_pixmap)
        self.pkginfo_ui.vote1.set_from_file(heart_pixmap)
        self.pkginfo_ui.vote2.set_from_file(heart_pixmap)
        self.pkginfo_ui.vote3.set_from_file(heart_pixmap)
        self.pkginfo_ui.vote4.set_from_file(heart_pixmap)
        self.pkginfo_ui.vote5.set_from_file(heart_pixmap)

        self.pkgProperties_selected = pkg
        self.pkginfo_ui.labelAtom.set_markup("<b>%s</b>" % (pkg.name,))
        self.pkginfo_ui.labelDescription.set_markup("<small>%s</small>" % (cleanMarkupSting(pkg.description),))

        bold_items = [  self.pkginfo_ui.locationLabel,
                        self.pkginfo_ui.homepageLabel,
                        self.pkginfo_ui.versionLabel,
                        self.pkginfo_ui.slotLabel,
                        self.pkginfo_ui.tagLabel,
                        self.pkginfo_ui.revisionLabel,
                        self.pkginfo_ui.branchLabel,
                        self.pkginfo_ui.eapiLabel,
                        self.pkginfo_ui.downloadLabel,
                        self.pkginfo_ui.checksumLabel,
                        self.pkginfo_ui.downSizeLabel,
                        self.pkginfo_ui.installSizeLabel,
                        self.pkginfo_ui.creationDateLabel,
                        self.pkginfo_ui.useFlagsLabel,
                        self.pkginfo_ui.chostLabel,
                        self.pkginfo_ui.cflagsLabel,
                        self.pkginfo_ui.cxxflagsLabel,
                        self.pkginfo_ui.eclassesLabel,
                        self.pkginfo_ui.maskedLabel,
                        self.pkginfo_ui.messagesLabel,
                        self.pkginfo_ui.triggerLabel,
                        self.pkginfo_ui.configProtectLabel
        ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<b>%s</b>" % (t,))

        dbconn = self.Entropy.clientDbconn
        repo = pkg.matched_atom[1]
        if repo == 0:
            # from installed
            self.pkginfo_ui.location.set_markup("%s" % (_("From your Operating System"),))
        else:
            dbconn = self.Entropy.openRepositoryDatabase(repo)
            self.pkginfo_ui.location.set_markup("%s" % (etpRepositories[repo]['description'],))

        self.pkginfo_ui.version.set_markup( "%s" % (pkg.onlyver,) )
        tag = pkg.tag
        if not tag: tag = "None"
        self.pkginfo_ui.tag.set_markup( "%s" % (tag,) )
        self.pkginfo_ui.slot.set_markup( "%s" % (pkg.slot,) )
        self.pkginfo_ui.revision.set_markup( "%s" % (pkg.revision,) )
        self.pkginfo_ui.branch.set_markup( "%s" % (pkg.release,) )
        self.pkginfo_ui.eapi.set_markup( "%s" % (pkg.api,) )
        self.pkginfo_ui.homepage.set_markup( "%s" % (pkg.homepage,) )

        # license view
        self.licenseModel.clear()
        self.licenseView.set_model( self.licenseModel )
        licenses = pkg.lic
        licenses = licenses.split()
        for x in licenses:
            self.licenseModel.append(None,[x])

        self.pkginfo_ui.download.set_markup( "%s" % (pkg.binurl,) )
        self.pkginfo_ui.checksum.set_markup( "%s" % (pkg.digest,) )
        self.pkginfo_ui.pkgsize.set_markup( "%s" % (pkg.sizeFmt,) )
        self.pkginfo_ui.instsize.set_markup( "%s" % (pkg.disksizeFmt,) )
        self.pkginfo_ui.creationdate.set_markup( "%s" % (pkg.epochFmt,) )
        self.pkginfo_ui.useflags.set_markup( "%s" % (' '.join(pkg.useflags),) )
        # compile flags
        chost, cflags, cxxflags = pkg.compileflags
        self.pkginfo_ui.cflags.set_markup( "%s" % (cflags,) )
        self.pkginfo_ui.cxxflags.set_markup( "%s" % (cxxflags,) )
        self.pkginfo_ui.chost.set_markup( "%s" % (chost,) )
        # messages
        messages = pkg.messages
        mbuffer = gtk.TextBuffer()
        mbuffer.set_text('\n'.join(messages))
        self.pkginfo_ui.messagesTextView.set_buffer(mbuffer)
        # eclasses
        eclasses = ' '.join(pkg.eclasses)
        self.pkginfo_ui.eclasses.set_markup( "%s" % (eclasses,) )
        # masked ?
        masked = 'False'
        idpackage_masked, idmasking_reason = dbconn.idpackageValidator(pkg.matched_atom[0])
        if idpackage_masked == -1:
            masked = 'True, %s' % (etpConst['packagemaskingreasons'][idmasking_reason],)
        self.pkginfo_ui.masked.set_markup( "%s" % (masked,) )

        # sources view
        self.sourcesModel.clear()
        self.sourcesView.set_model( self.sourcesModel )
        mirrors = set()
        sources = pkg.sources
        for x in sources:
            if x.startswith("mirror://"):
                mirrors.add(x.split("/")[2])
            self.sourcesModel.append(None,[x])

        # mirrors view
        self.mirrorsReferenceModel.clear()
        self.mirrorsReferenceView.set_model(self.mirrorsReferenceModel)
        for mirror in mirrors:
            mirrorinfo = dbconn.retrieveMirrorInfo(mirror)
            if mirrorinfo:
                # add parent
                parent = self.mirrorsReferenceModel.append(None,[mirror])
                for info in mirrorinfo:
                    self.mirrorsReferenceModel.append(parent,[info])

        # keywords view
        self.keywordsModel.clear()
        self.keywordsView.set_model( self.keywordsModel )
        keywords = pkg.keywords
        for x in keywords:
            self.keywordsModel.append(None,[x])

        # dependencies view
        self.dependenciesModel.clear()
        self.dependenciesView.set_model( self.dependenciesModel )
        deps = pkg.dependencies
        conflicts = pkg.conflicts
        for x in deps:
            self.dependenciesModel.append(None,[x])
        for x in conflicts:
            self.dependenciesModel.append(None,[x])

        # depends view
        self.dependsModel.clear()
        self.dependsView.set_model( self.dependsModel )
        depends = pkg.dependsFmt
        for x in depends:
            self.dependsModel.append(None,[x])

        # needed view
        self.neededModel.clear()
        self.neededView.set_model( self.neededModel )
        neededs = pkg.needed
        for x in neededs:
            self.neededModel.append(None,[x])

        # content view
        self.contentModel.clear()
        self.contentView.set_model( self.contentModel )

        # trigger
        trigger = pkg.trigger
        mtrigger = gtk.TextBuffer()
        mtrigger.set_text(trigger)
        self.pkginfo_ui.triggerTextView.set_buffer(mtrigger)

        # CONFIG_PROTECT Stuff
        protect = pkg.protect
        protect_mask = pkg.protect_mask
        for item in protect.split():
            self.configProtectModel.append(None,[item,'protect'])
        for item in protect_mask.split():
            self.configProtectModel.append(None,[item,'mask'])

        self.pkginfo_ui.pkgInfo.show()


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
                xml_licread = gtk.glade.XML( const.GLADE_FILE, 'licenseReadWindow',domain="spritz" )
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

    def on_showContentButton_clicked( self, widget ):
        content = self.pkgProperties_selected.contentExt
        for x in content:
            self.contentModel.append(None,[x[0],x[1]])

    def on_closeInfo_clicked( self, widget ):
        self.pkginfo_ui.pkgInfo.hide()

    def on_pkgInfo_delete_event(self, widget, path):
        self.pkginfo_ui.pkgInfo.hide()
        return True

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
        if self.skipMirror:
            self.logger.info('skipmirror')
            self.skipMirrorNow = True

    def on_search_clicked(self,widget):
        ''' Search entry+button handler'''
        txt = self.ui.pkgFilter.get_text()
        flt = filters.spritzFilter.get('KeywordFilter')
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

    def on_comps_cursor_changed(self, widget):
        self.setBusy()
        """ Handle selection of row in Comps Category  view  """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            id = model.get_value( iterator, 2 )
            isCategory = model.get_value( iterator, 4 )
            if isCategory:
                self.populateCategoryPackages(id)
        self.unsetBusy()

    def on_FileQuit( self, widget ):
        self.quit()

    def on_HelpAbout( self, widget ):
        about = AboutDialog(const.PIXMAPS_PATH+'/spritz-about.png',const.CREDITS,self.settings.branding_title)
        about.show()

class SpritzApplication(SpritzController,SpritzGUI):

    def __init__(self):

        # check if another instance is running
        cr = EquoConnection.entropyTools.applicationLockCheck("Spritz Loader", gentle = True)
        if cr:
            # warn the user
            msg = "<big><b>%s</b></big>\t\t\n%s <b>%s</b>. %s: <b>%s</b>" % (
                    _("Sorry to tell you"),
                    _("Another instance of Entropy"),
                    _("is running"),
                    _("Close it or remove"),
                    etpConst['pidfile'],
            )
            okDialog( None, msg )
            sys.exit()

        SpritzController.__init__( self )
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
        self.logger.info(_('Entropy Config Setup'))
        self.catsView.etpbase = self.etpbase
        self.lastPkgPB = "updates"
        self.etpbase.setFilter(filters.spritzFilter.processFilters)

        self.Equo.connect_to_gui(self.progress, self.progressLogWrite, self.output)
        self.setupEditor()
        # Setup GUI
        self.setupGUI()
        self.setPage("packages")

        self.logger.info(_('GUI Setup Completed'))
        # setup Repositories
        self.setupRepoView()
        self.firstTime = True
        # calculate updates
        self.setupSpritz()

        self.console.set_pty(self.pty[0])
        self.resetProgressText()
        self.setupPkgPropertiesView()
        self.setupAdvisories()

    def setupAdvisories(self):
        self.Advisories = self.Equo.Security()

    def setupPkgPropertiesView(self):
        # license view
        self.licenseView = self.pkginfo_ui.licenseView
        self.licenseModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "License name" ), cell, markup = 0 )
        self.licenseView.append_column( column )
        self.licenseView.set_model( self.licenseModel )

        # sources view
        self.sourcesView = self.pkginfo_ui.sourcesView
        self.sourcesModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Sources" ), cell, markup = 0 )
        self.sourcesView.append_column( column )
        self.sourcesView.set_model( self.sourcesModel )

        # mirrors view
        self.mirrorsReferenceView = self.pkginfo_ui.mirrorsReferenceView
        self.mirrorsReferenceModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Mirrors" ), cell, markup = 0 )
        self.mirrorsReferenceView.append_column( column )
        self.mirrorsReferenceView.set_model( self.mirrorsReferenceModel )

        # keywords view
        self.keywordsView = self.pkginfo_ui.keywordsView
        self.keywordsModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Keywords" ), cell, markup = 0 )
        self.keywordsView.append_column( column )
        self.keywordsView.set_model( self.keywordsModel )

        # dependencies view
        self.dependenciesView = self.pkginfo_ui.dependenciesView
        self.dependenciesModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Dependencies" ), cell, markup = 0 )
        self.dependenciesView.append_column( column )
        self.dependenciesView.set_model( self.dependenciesModel )

        # depends view
        self.dependsView = self.pkginfo_ui.dependsView
        self.dependsModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Depends" ), cell, markup = 0 )
        self.dependsView.append_column( column )
        self.dependsView.set_model( self.dependsModel )

        # needed view
        self.neededView = self.pkginfo_ui.neededView
        self.neededModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Needed libraries" ), cell, markup = 0 )
        self.neededView.append_column( column )
        self.neededView.set_model( self.neededModel )

        # protect view
        self.configProtectView = self.pkginfo_ui.configProtectView
        self.configProtectModel = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Protected item" ), cell, markup = 0 )
        self.configProtectView.append_column( column )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Type" ), cell, markup = 1 )
        self.configProtectView.append_column( column )
        self.configProtectView.set_model( self.configProtectModel )

        # content view
        self.contentView = self.pkginfo_ui.contentView
        self.contentModel = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "File" ), cell, markup = 0 )
        column.set_resizable( True )
        self.contentView.append_column( column )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Type" ), cell, markup = 1 )
        column.set_resizable( True )
        self.contentView.append_column( column )
        self.contentView.set_model( self.contentModel )

        self.pkgProperties_selected = None


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
        self.populateCategories()
        msg = _('Ready')
        self.setStatus(msg)

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
        if cached == None:
            self.setPage('output')
            cached = self.Advisories.get_advisories_metadata()
            self.setPage('glsa')
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

    def updateRepositories(self, repos):

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
            msg = "%s: %s" % (_('No repositories specified in'),etpConst['repositoriesconf'],)
            self.progressLog( msg, extra = "repositories")
            return 127
        except exceptionTools.OnlineMirrorError:
            self.progressLog(_('You are not connected to the Internet. You should.'), extra = "repositories")
            return 126
        except Exception, e:
            msg = "%s: %s" % (_('Unhandled exception'),e,)
            self.progressLog(msg, extra = "repositories")
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
                    msg = "%s %s" % (repoConn.alreadyUpdated,_("repositories were already up to date. Others have been updated."),)
                    self.progress.set_mainLabel(msg)
            if repoConn.newEquo:
                self.progress.set_extraLabel(_('sys-apps/entropy needs to be updated as soon as possible.'))

        initConfig_entropyConstants(etpSys['rootdir'])

    def resetProgressText(self):
        self.progress.set_mainLabel(_('Nothing to do. I am idle.'))
        self.progress.set_subLabel(_('Really, don\'t waste your time here. This is just a placeholder'))
        self.progress.set_extraLabel(_('I am still alive and kickin\''))

    def setupRepoView(self):
        self.repoView.populate()

    def setBusy(self):
        busyCursor(self.ui.main)

    def unsetBusy(self):
        normalCursor(self.ui.main)

    def addPackages(self):

        action = self.lastPkgPB
        if action == 'all':
            masks = ['installed','available']
        else:
            masks = [action]


        self.setBusy()
        bootstrap = False
        if (self.Equo.get_world_update_cache(empty_deps = False) == None):
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
            self.setStatus(_("Ready"))
        if self.doProgress: self.progress.total.next() # -> Sort Lists

        if action == "updates":
            msg = "%s: available" % (_('Calculating'),)
            self.setStatus(msg)
            self.etpbase.getPackages("available")
            self.setStatus(_("Ready"))

        if bootstrap:
            self.endWorking()

        self.pkgView.populate(allpkgs)
        self.progress.total.show()

        if self.doProgress: self.progress.hide() #Hide Progress
        if bootstrap:
            self.setPage('packages')

        self.unsetBusy()
        # reset labels
        self.resetProgressText()

    def processPackageQueue( self, pkgs, doAll=False):
        """ Workflow for processing package queue """
        self.setStatus( _( "Running tasks" ) )
        total = len( pkgs['i'] )+len( pkgs['u'] )+len( pkgs['r'] ) +len( pkgs['rr'] )
        state = True
        if total > 0:
            self.startWorking()
            self.progress.show()
            self.progress.set_mainLabel( _( "Processing Packages in queue" ) )

            queue = pkgs['i']+pkgs['u']+pkgs['rr']
            install_queue = [x.matched_atom for x in queue]
            removal_queue = [x.matched_atom[0] for x in pkgs['r']]
            do_purge_cache = set([x.matched_atom[0] for x in pkgs['r'] if x.do_purge])
            if install_queue or removal_queue:
                controller = QueueExecutor(self)
                e,i = controller.run(install_queue[:], removal_queue[:], do_purge_cache)
                if e != 0:
                    okDialog(   self.ui.main,
                                _("Attention. An error occured when processing the queue."
                                    "\nPlease have a look in the processing terminal.")
                    )
                # XXX let it sleep a bit to allow all other threads to flush
                self.endWorking()
                while gtk.events_pending():
                    time.sleep(0.1)
                self.etpbase.clearPackages()
                time.sleep(5)
            self.endWorking()
            self.progress.reset_progress()
            self.etpbase.clearPackages()
            self.etpbase.clearCache()
            self.Equo.closeAllRepositoryDatabases()
            self.Equo.reopenClientDbconn()
            # regenerate packages information

            self.setupSpritz()
            self.Equo.FileUpdates.scanfs(dcache = False)
            if self.Equo.FileUpdates.scandata:
                if len(self.Equo.FileUpdates.scandata) > 0:
                    self.setPage('filesconf')
            #self.progress.hide()
            return state
        else:
            self.setStatus( _( "No packages selected" ) )
            return state

    def get_confimation( self, task ):
        self.progress.hide( False )
        dlg = ConfirmationDialog(self.ui.main, [], 0 )
        rc = dlg.run()
        dlg.destroy()
        self.progress.show()
        return rc == gtk.RESPONSE_OK

    def populateCategories(self):
        self.setBusy()
        self.etpbase.populateCategories()
        self.catsView.populate(self.etpbase.getCategories())
        self.unsetBusy()

    def populateCategoryPackages(self, cat):
        pkgs = self.etpbase.getPackagesByCategory(cat)
        self.catPackages.populate(pkgs,self.ui.tvCatPackages)


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
    except KeyboardInterrupt:
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
        import entropyTools
        conntest = entropyTools.get_remote_data(etpConst['conntestlink'])
        rc, (name,mail,description) = errorMessage( None,
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
        sys.exit(1)