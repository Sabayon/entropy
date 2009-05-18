#!/usr/bin/python2 -O
# -*- coding: iso-8859-1 -*-
#    Sulfur (Entropy Interface)
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
import time

# Entropy Imports
sys.path.insert(0,"../../libraries")
sys.path.insert(1,"../../client")
sys.path.insert(2,"/usr/lib/entropy/libraries")
sys.path.insert(3,"/usr/lib/entropy/client")
from entropy.exceptions import *
import entropy.tools
from packages import EntropyPackages
from entropyapi import Equo, QueueExecutor
from entropy.const import *
from entropy.i18n import _
from entropy.misc import TimeScheduled, ParallelTask

# Sulfur Imports
import gtk, gobject
from etpgui.widgets import UI, Controller, SulfurConsole
from etpgui import *
from sulfur_setup import SulfurConf, const, fakeoutfile, fakeinfile, \
    cleanMarkupString
from misc import Queue
from views import *
from filters import Filter
from dialogs import *
from progress import Base as BaseProgress

class SulfurApplicationEventsMixin:

    def on_console_click(self, widget, event):
        self.console_menu.popup( None, None, None, event.button, event.time )
        return True

    def on_dbBackupButton_clicked(self, widget):
        self.show_wait_window()
        self.startWorking()
        status, err_msg = self.Equo.backup_database(etpConst['etpdatabaseclientfilepath'])
        self.endWorking()
        if not status:
            self.hide_wait_window()
            okDialog( self.ui.main, "%s: %s" % (_("Error during backup"),err_msg,) )
            return
        okDialog( self.ui.main, "%s" % (_("Backup complete"),) )
        self.fillPreferencesDbBackupPage()
        self.dbBackupView.queue_draw()
        self.hide_wait_window()

    def on_dbRestoreButton_clicked(self, widget):
        model, myiter = self.dbBackupView.get_selection().get_selected()
        if myiter == None: return
        dbpath = model.get_value(myiter, 0)
        self.show_wait_window()
        self.startWorking()
        status, err_msg = self.Equo.restore_database(dbpath, etpConst['etpdatabaseclientfilepath'])
        self.endWorking()
        self.Equo.reopen_client_repository()
        self.reset_cache_status()
        self.addPackages()
        if not status:
            self.hide_wait_window()
            okDialog( self.ui.main, "%s: %s" % (_("Error during restore"),err_msg,) )
            return
        self.fillPreferencesDbBackupPage()
        self.dbBackupView.queue_draw()
        self.hide_wait_window()
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

        rc = self.add_atoms_to_queue(atoms, always_ask = True)
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

        rc = self.add_atoms_to_queue(atoms, always_ask = True)
        if rc: okDialog( self.ui.main, _("Packages in all Advisories have been queued.") )

    def on_advInfoButton_clicked( self, widget ):
        if self.etpbase.selected_advisory_item:
            self.loadAdvInfoMenu(self.etpbase.selected_advisory_item)

    def on_pkgInfoButton_clicked( self, widget ):
        if self.etpbase.selected_treeview_item:
            self.loadPkgInfoMenu(self.etpbase.selected_treeview_item)

    def on_filesDelete_clicked( self, widget ):
        identifier, source, dest = self._get_Edit_filename()
        if not identifier:
            return True
        self.Equo.FileUpdates.remove_file(identifier)
        self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_filesMerge_clicked( self, widget ):
        identifier, source, dest = self._get_Edit_filename()
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
        identifier, source, dest = self._get_Edit_filename()
        if not identifier:
            return True

        """
        if not os.access(source, os.R_OK | os.W_OK | os.F_OK):
            return
        source_f = open(source)
        txt = source_f.read()
        source_f.close()
        TextReadDialog(source, txt, read_only = False, rw_save_path = source)
        """
        self.runEditor(source)

    def on_filesView_row_activated( self, widget, iterator, path ):
        self.on_filesViewChanges_clicked(widget)

    def on_filesViewChanges_clicked( self, widget ):
        import commands
        identifier, source, dest = self._get_Edit_filename()
        if not identifier:
            return True
        diffcmd = "diff -Nu "+dest+" "+source

        mybuffer = gtk.TextBuffer()
        red_tt = mybuffer.create_tag("red", foreground = "red")
        green_tt = mybuffer.create_tag("green", foreground = "darkgreen")

        for line in commands.getoutput(diffcmd).split("\n"):
            myiter = mybuffer.get_end_iter()
            if line.startswith("+"):
                mybuffer.insert_with_tags(myiter, line+"\n", green_tt)
            elif line.startswith("-"):
                mybuffer.insert_with_tags(myiter, line+"\n", red_tt)
            else:
                mybuffer.insert(myiter, line+"\n")
        TextReadDialog(dest, mybuffer)

    def on_filesViewRefresh_clicked( self, widget ):
        self.Equo.FileUpdates.scanfs(dcache = False)
        self.filesView.populate(self.Equo.FileUpdates.scandata)

    def on_shiftUp_clicked( self, widget ):
        idx, repoid, iterdata = self._get_selected_repo_index()
        if idx != None:
            path = iterdata[0].get_path(iterdata[1])[0]
            if path > 0 and idx > 0:
                idx -= 1
                self.Equo.shift_repository(repoid, idx)
                # get next iter
                prev = iterdata[0].get_iter(path-1)
                self.repoView.store.swap(iterdata[1],prev)

    def on_shiftDown_clicked( self, widget ):
        idx, repoid, iterdata = self._get_selected_repo_index()
        if idx != None:
            next = iterdata[0].iter_next(iterdata[1])
            if next:
                idx += 1
                self.Equo.shift_repository(repoid, idx)
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

    def on_repoSubmitEdit_clicked( self, widget ):
        repodata = self._get_repo_data()
        errors = self._validate_repo_submit(repodata, edit = True)
        if errors:
            msg = "%s: %s" % (_("Wrong entries, errors"),', '.join(errors),)
            okDialog( self.addrepo_ui.addRepoWin, msg )
            return True
        else:
            disable = False
            repo_excluded = self.Equo.SystemSettings['repositories']['excluded']
            if repo_excluded.has_key(repodata['repoid']):
                disable = True
            self.Equo.remove_repository(repodata['repoid'], disable = disable)
            if not disable:
                self.Equo.add_repository(repodata)
            self.reset_cache_status()

            self.setupRepoView()
            self.addrepo_ui.addRepoWin.hide()
            msg = "%s '%s' %s" % (_("You should press the button"),_("Regenerate Cache"),_("now"))
            okDialog( self.ui.main, msg )

    def on_repoSubmit_clicked( self, widget ):
        repodata = self._get_repo_data()
        # validate
        errors = self._validate_repo_submit(repodata)
        if not errors:
            self.Equo.add_repository(repodata)
            self.reset_cache_status()
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
                current_branch = self.Equo.SystemSettings['repositories']['branch']
                current_product = self.Equo.SystemSettings['repositories']['product']
                repoid, repodata = const_extract_cli_repo_params(text, current_branch, current_product)
                self._load_repo_data(repodata)
            else:
                okDialog( self.addrepo_ui.addRepoWin, _("This Repository identification string is malformed") )

    def on_removeRepo_clicked( self, widget ):
        # get selected repo
        selection = self.repoView.view.get_selection()
        repodata = selection.get_selected()
        # get text
        if repodata[1] != None:
            repoid = self.repoView.get_repoid(repodata)
            if repoid == self.Equo.SystemSettings['repositories']['default_repository']:
                okDialog( self.ui.main, _("You! Why do you want to remove the main repository ?"))
                return True
            self.Equo.remove_repository(repoid)
            self.reset_cache_status()
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
            repodata = self.Equo.get_repository_settings(repoid)
            self._load_repo_data(repodata)
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
        initconfig_entropy_constants(etpConst['systemroot'])
        # re-read configprotect
        self.reset_cache_status()
        self.addPackages()
        self.Equo.reload_repositories_config()
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
            self.Equo.remove_repository(newrepo)
            self.reset_cache_status()
            self.Equo.reopen_client_repository()
            # regenerate packages information
            self.setup_application()

        if not atomsfound:
            clean_n_quit(newrepo)
            return

        pkgs = []
        for idpackage, atom in atomsfound:
            yp, new = self.etpbase.getPackageItem((idpackage,newrepo,))
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

        try:
            rc = self.process_queue(self.queue.packages,
                remove_repos = [newrepo])
        except:
            if self.do_debug:
                entropy.tools.print_traceback()
                import pdb; pdb.set_trace()
            else:
                raise

        self.resetQueueProgressBars()
        if rc:
            self.queue.clear()
            self.queueView.refresh()
            return True
        else: # not done
            clean_n_quit(newrepo)
            return False

    def on_PageButton_changed( self, widget, page ):

        ''' Left Side Toolbar Handler'''
        # do not put here actions for 'packages' and 'output' but use on_PageButton_pressed
        if page == "filesconf":
            self.populateFilesUpdate()
        elif page == "glsa":
            self.populateAdvisories(None,'affected')
        self.setNotebookPage(const.PAGES[page])

    def on_queueReviewAndInstall_clicked(self, widget):
        self.switchNotebookPage("queue")

    def on_pkgFilter_toggled(self,rb,action):
        ''' Package Type Selection Handler'''
        if not rb.get_active(): return

        rb.grab_add()
        self.lastPkgPB = action

        # Only show add/remove all when showing updates
        if action == 'updates': self.ui.updatesButtonbox.show()
        else: self.ui.updatesButtonbox.hide()

        if action == "masked":
            self.setupMaskedPackagesWarningBox()
            self.ui.maskedWarningBox.show()
        else:
            self.ui.maskedWarningBox.hide()

        if action == "pkgsets": self.ui.pkgsetsButtonBox.show()
        else: self.ui.pkgsetsButtonBox.hide()

        if action == "queued": self.ui.queueReviewAndInstallBox.show()
        else: self.ui.queueReviewAndInstallBox.hide()

        self.addPackages()
        rb.grab_remove()

    def on_repoRefresh_clicked(self, widget):
        repos = self.repoView.get_selected()
        if not repos:
            okDialog( self.ui.main, _("Please select at least one repository") )
            return
        return self.do_repo_refresh(repos)

    def do_repo_refresh(self, repos):
        self.setPage('output')
        self.ui.main.queue_draw()
        self.uiLock(True)
        try:
            self.gtk_loop()
            self.startWorking()
            status = self.updateRepositories(repos)
            self.endWorking()
            self.progress.reset_progress()
            self.reset_cache_status()
            self.setupRepoView()
            self.setup_application()
            self.setupAdvisories()
            self.setPage('repos')
            if status:
                self.showNoticeBoard()
        finally:
            self.uiLock(False)

    def on_cacheButton_clicked(self,widget):
        self.repoView.get_selected()
        self.setPage('output')
        self.cleanEntropyCaches(alone = True)
        self.setPage('repos')

    def on_repoDeSelect_clicked(self,widget):
        self.repoView.deselect_all()

    def on_queueProcess_clicked( self, widget ):
        """ Process Queue Button Handler """
        if self.queue.total() == 0: # Check there are any packages in the queue
            self.setStatus(_('No packages in queue'))
            return

        fetch_only = self.ui.queueProcessFetchOnly.get_active()
        download_sources = self.ui.queueProcessDownloadSource.get_active()

        rc = True
        try:
            rc = self.process_queue(self.queue.packages,
                fetch_only = fetch_only, download_sources = download_sources)
        except:
            if self.do_debug:
                entropy.tools.print_traceback()
                import pdb; pdb.set_trace()
            else: raise
        self.resetQueueProgressBars()
        if rc and not fetch_only:
            self.queue.clear()       # Clear package queue
            self.queueView.refresh() # Refresh Package Queue
        #if fetch_only:
        #    self.setPage('queue')

    def on_queueSave_clicked( self, widget ):
        fn = FileChooser(action = gtk.FILE_CHOOSER_ACTION_SAVE, buttons = (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        if fn:
            pkgdata = self.queue.get().copy()
            for key in pkgdata.keys():
                if pkgdata[key]: pkgdata[key] = [x.matched_atom for x in pkgdata[key]]
            self.Equo.dumpTools.dumpobj(fn,pkgdata,True)

    def on_queueOpen_clicked( self, widget ):
        fn = FileChooser()
        if fn:

            try:
                pkgdata = self.Equo.dumpTools.loadobj(fn, complete_path = True)
            except:
                return

            if not isinstance(pkgdata,dict):
                return

            collected_items = []
            for key in pkgdata.keys():
                for pkg in pkgdata[key]:
                    try:
                        yp, new = self.etpbase.getPackageItem(pkg)
                    except:
                        okDialog( self.ui.main,
                            _("Queue is too old. Cannot load.") )
                        return
                    collected_items.append((key,yp))

            for key, pkg in collected_items:
                pkg.queued = key
                self.queue.packages[key].append(pkg)

            self.queueView.refresh()

    def on_queueClean_clicked(self, widget):
        self.reset_cache_status()
        self.addPackages()

    def on_adv_doubleclick( self, widget, iterator, path ):
        """ Handle selection of row in package view (Show Descriptions) """
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            data = model.get_value( iterator, 0 )
            if data:
                self.loadAdvInfoMenu(data)

    def on_pkg_doubleclick( self, widget, iterator, path ):
        """ Handle selection of row in package view (Show Descriptions) """
        objs = self.pkgView.collect_selected_items()
        for obj in objs:
            self.loadPkgInfoMenu(obj)

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
                    dbconn = self.Equo.open_repository(repoid)
                if dbconn.isLicensedataKeyAvailable(license_identifier):
                    license_text = dbconn.retrieveLicenseText(license_identifier)
                    found = True
            if found:
                mytitle = "%s -- %s" % (license_identifier, _("license text"),)
                TextReadDialog(mytitle, license_text)

    def on_select_clicked(self,widget):
        ''' Package Add All button handler '''
        self.show_wait_window()
        self.setBusy()
        self.startWorking()
        busyCursor(self.wait_ui.waitWindow)
        self.pkgView.selectAll()
        self.endWorking()
        self.unsetBusy()
        normalCursor(self.wait_ui.waitWindow)
        self.hide_wait_window()

    def on_deselect_clicked(self,widget):
        ''' Package Remove All button handler '''
        self.on_clear_clicked(widget)
        self.show_wait_window()
        self.setBusy()
        self.pkgView.deselectAll()
        self.hide_wait_window()
        self.unsetBusy()

    def on_skipMirror_clicked(self,widget):
        # set the working mirror as failing
        self.Equo.MirrorStatus.add_failing_working_mirror(75)
        self.skipMirrorNow = True

    def on_abortQueue_clicked(self,widget):
        msg = _("You have chosen to interrupt the processing. Are you sure you want to do it ?")
        rc = questionDialog(self.ui.main, msg)
        if rc: self.abortQueueNow = True

    def on_search_clicked(self,widget):
        self.etpbase.setFilter(Filter.processFilters)
        ''' Search entry+button handler'''
        txt = self.ui.pkgFilter.get_text()
        flt = Filter.get('KeywordFilter')
        if txt != '':
            flt.activate()
            lst = txt.split()
            flt.setKeys(lst)
            self.ui.pkgClr.show()
        else:
            flt.activate(False)
        action = self.lastPkgPB
        rb = self.packageRB[action]
        self.on_pkgFilter_toggled(rb,action)

    def on_clear_clicked(self,widget):
        self.etpbase.setFilter()
        ''' Search Clear button handler'''
        self.ui.pkgFilter.set_text("")
        self.on_search_clicked(None)
        self.ui.pkgClr.hide()

    def on_FileQuit( self, widget ):
        self.show_wait_window()
        self.quit()

    def on_HelpAbout( self, widget = None ):
        about = AboutDialog(const.PIXMAPS_PATH+'/spritz-about.png',const.CREDITS,SulfurConf.branding_title)
        about.show()

    def on_notebook1_switch_page(self, widget, page, page_num):
        if page_num == const.PREF_PAGES['ugc']:
            self.load_ugc_repositories()
        elif page_num == const.PREF_PAGES['colors']:
            self.load_color_settings()

    def on_ugcLoginButton_clicked(self, widget):
        if self.Equo.UGC == None: return
        model, myiter = self.ugcRepositoriesView.get_selection().get_selected()
        if (myiter == None) or (model == None): return
        obj = model.get_value( myiter, 0 )
        if obj:
            #logged_data = self.Equo.UGC.read_login(obj['repoid'])
            self.Equo.UGC.login(obj['repoid'], force = True)
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
        repo_excluded = self.Equo.SystemSettings['repositories']['excluded']
        avail_repos = self.Equo.SystemSettings['repositories']['available']
        for repoid in list(set(avail_repos.keys()+repo_excluded.keys())):
            self.Equo.UGC.UGCCache.clear_cache(repoid)
            self.setStatus("%s: %s ..." % (_("Cleaning UGC cache of"),repoid,))
        self.setStatus("%s" % (_("UGC cache cleared"),))

    def on_ugcClearCredentialsButton_clicked(self, widget):
        if self.Equo.UGC == None: return
        repo_excluded = self.Equo.SystemSettings['repositories']['excluded']
        avail_repos = self.Equo.SystemSettings['repositories']['available']
        for repoid in list(set(avail_repos.keys()+repo_excluded.keys())):
            if not self.Equo.UGC.is_repository_eapi3_aware(repoid): continue
            logged_data = self.Equo.UGC.read_login(repoid)
            if logged_data: self.Equo.UGC.remove_login(repoid)
        self.load_ugc_repositories()
        self.setStatus("%s" % (_("UGC credentials cleared"),))

    def on_repoManagerMenuItem_activate(self, widget):
        mymenu = RepositoryManagerMenu(self.Equo, self.ui.main)
        rc = mymenu.load()
        if not rc: del mymenu

    def on_noticeBoardMenuItem_activate(self, widget):
        self.showNoticeBoard()

    def on_pkgsetAddButton_clicked(self, widget):

        current_sets = self.Equo.package_set_list()
        def fake_callback(s):
            if (s not in current_sets) and (" " not in s) and (not s.startswith(etpConst['packagesetprefix'])):
                return True
            return False

        def lv_callback(atom):
            c_id, c_rc = self.Equo.clientDbconn.atomMatch(atom)
            if c_id != -1: return True
            c_id, c_rc = self.Equo.atom_match(atom)
            if c_id != -1: return True
            return False

        input_params = [
            ('name',_("Package Set name"),fake_callback,False),
            ('atoms',('list',(_('Package atoms'),[],),),lv_callback,False)
        ]

        data = self.Equo.inputBox(
            _('Choose what Package Set you want to add'),
            input_params,
            cancel_button = True
        )
        if data == None: return

        rc, msg = self.Equo.add_user_package_set(data.get("name"), data.get("atoms"))
        if rc != 0:
            okDialog(self.ui.main,"%s: %s" % (_("Error"),msg,))
            return

        self.etpbase.clearPackagesSingle("pkgsets")
        self.addPackages()

    def on_pkgsetRemoveButton_clicked(self, widget):

        def mymf(m):
            set_from, set_name, set_deps = m
            if set_from == etpConst['userpackagesetsid']:
                return set_name
            return 0
        avail_pkgsets = [x for x in map(mymf,self.Equo.package_set_list()) if x != 0]

        def fake_callback(s):
            return s
        input_params = [
            ('pkgset',('combo',(_('Removable Package Set'),avail_pkgsets),),fake_callback,False)
        ]

        data = self.Equo.inputBox(
            _('Choose what Package Set you want to remove'),
            input_params,
            cancel_button = True
        )
        if data == None: return
        x_id,set_name = data.get("pkgset")

        rc, msg = self.Equo.remove_user_package_set(set_name)
        if rc != 0:
            okDialog(self.ui.main,"%s: %s" % (_("Error"),msg,))
            return

        self.etpbase.clearPackagesSingle("pkgsets")
        self.addPackages()

    def on_deptestButton_clicked(self, widget):

        self.switchNotebookPage("output")
        self.uiLock(True)
        self.startWorking()
        deps_not_matched = self.Equo.dependencies_test()
        if not deps_not_matched:
            okDialog(self.ui.main,_("No missing dependencies found."))
            self.switchNotebookPage("preferences")
            self.uiLock(False)
            self.endWorking()
            self.progress.reset_progress()
            return

        found_deps = set()
        not_all = False
        for dep in deps_not_matched:
            match = self.Equo.atom_match(dep)
            if match[0] != -1:
                found_deps.add(dep)
                continue
            else:
                iddep = self.Equo.clientDbconn.searchDependency(dep)
                if iddep == -1: continue
                c_idpackages = self.Equo.clientDbconn.searchIdpackageFromIddependency(iddep)
                for c_idpackage in c_idpackages:
                    key, slot = self.Equo.clientDbconn.retrieveKeySlot(c_idpackage)
                    key_slot = "%s:%s" % (key,slot,)
                    match = self.Equo.atom_match(key, matchSlot = slot)
                    cmpstat = 0
                    if match[0] != -1:
                        cmpstat = self.Equo.get_package_action(match)
                    if cmpstat != 0:
                        found_deps.add(key_slot)
                        continue
                    else:
                        not_all = True
                continue
            not_all = True

        if not found_deps:
            okDialog(self.ui.main,_("Missing dependencies found, but none of them are on the repositories."))
            self.switchNotebookPage("preferences")
            self.uiLock(False)
            self.endWorking()
            self.progress.reset_progress()
            return

        if not_all:
            okDialog(self.ui.main,_("Some missing dependencies have not been matched, others are going to be added to the queue."))
        else:
            okDialog(self.ui.main,_("All the missing dependencies are going to be added to the queue"))

        rc = self.add_atoms_to_queue(found_deps)
        if rc: self.switchNotebookPage("queue")
        else: self.switchNotebookPage("preferences")
        self.uiLock(False)
        self.endWorking()
        self.progress.reset_progress()

    def on_libtestButton_clicked(self, widget):

        def do_start():
            self.switchNotebookPage("output")
            self.startWorking()
            self.uiLock(True)
            self.ui.abortQueue.show()

        def do_stop():
            self.endWorking()
            self.ui.abortQueue.hide()
            self.uiLock(False)
            self.progress.reset_progress()

        def task_bombing():
            if self.abortQueueNow:
                self.abortQueueNow = False
                mytxt = _("Aborting queue tasks.")
                self.ui.abortQueue.hide()
                raise QueueError('QueueError %s' % (mytxt,))

        do_start()

        packages_matched, broken_execs = {},set()
        self.libtest_abort = False
        def exec_task():
            try:
                x, y, z = self.Equo.libraries_test(task_bombing_func = task_bombing)
                packages_matched.update(x)
                broken_execs.update(y)
            except QueueError:
                self.libtest_abort = True

        t = ParallelTask(exec_task)
        t.start()
        while t.isAlive():
            time.sleep(0.2)
            self.gtk_loop()

        if self.do_debug and self.libtest_abort:
            print "on_libtestButton_clicked: scan abort"
        if self.do_debug:
            print "on_libtestButton_clicked: done scanning"

        if self.libtest_abort:
            do_stop()
            okDialog(self.ui.main,_("Libraries test aborted"))
            return

        matches = set()
        for key in packages_matched.keys():
            matches |= packages_matched[key]

        if broken_execs:
            okDialog(self.ui.main,_("Some broken packages have not been matched, others are going to be added to the queue."))
        else:
            okDialog(self.ui.main,_("All the broken packages are going to be added to the queue"))

        rc = self.add_atoms_to_queue([], matches = matches)
        if rc: self.switchNotebookPage("queue")
        else: self.switchNotebookPage("preferences")

        do_stop()

    def on_color_reset(self, widget):
        # get parent
        parent = widget.get_parent()
        if parent == None: return
        col_button = [x for x in parent.get_children() if isinstance(x,gtk.ColorButton)][0]
        setting = self.colorSettingsReverseMap.get(col_button)
        if setting == None: return
        default_color = SulfurConf.default_colors_config.get(setting)
        col_button.set_color(gtk.gdk.color_parse(default_color))
        self.on_Preferences_toggled(None,True)
        setattr(SulfurConf,setting,default_color)

    def on_ui_color_set(self, widget):
        key = self.colorSettingsReverseMap.get(widget)
        if not hasattr(SulfurConf,key):
            print "WARNING: no %s in SulfurConf" % (key,)
            return
        w_col = widget.get_color().to_string()
        self.on_Preferences_toggled(None,True)
        setattr(SulfurConf,key,w_col)

    def on_pkgSorter_changed(self, widget):
        busyCursor(self.ui.main)
        model = widget.get_model()
        sort_id = widget.get_active()
        if sort_id == -1:
            return
        sort_id_name = self.pkg_sorters_id.get(sort_id)
        sorter = self.avail_pkg_sorters.get(sort_id_name)
        self.pkgView.change_model_injector(sorter)
        self.addPackages()
        normalCursor(self.ui.main)


class SulfurApplication(Controller, SulfurApplicationEventsMixin):

    def __init__(self):

        self.Equo = Equo()

        self.do_debug = False
        locked = self.Equo._resources_run_check_lock()
        if locked:
            okDialog( None, _("Entropy resources are locked and not accessible. Another Entropy application is running. Sorry, can't load Sulfur.") )
            raise SystemExit(1)
        self.safe_mode_txt = ''
        # check if we'are running in safe mode
        if self.Equo.safe_mode:
            reason = etpConst['safemodereasons'].get(self.Equo.safe_mode)
            okDialog( None, "%s: %s. %s" % (
                _("Entropy is running in safe mode"), reason,
                _("Please fix as soon as possible"),)
            )
            self.safe_mode_txt = _("Safe Mode")

        self.isBusy = False
        self.etpbase = EntropyPackages(self.Equo)

        # Create and ui object contains the widgets.
        ui = UI( const.GLADE_FILE , 'main', 'entropy' )
        ui.main.hide()
        addrepo_ui = UI( const.GLADE_FILE , 'addRepoWin', 'entropy' )
        wait_ui = UI( const.GLADE_FILE , 'waitWindow', 'entropy' )
        # init the Controller Class to connect signals.
        Controller.__init__( self, ui, addrepo_ui, wait_ui )

    def init(self):

        self.show_wait_window()
        self.setup_gui()
        # show UI
        if "--nomaximize" not in sys.argv:
            self.ui.main.maximize()
        self.ui.main.show()
        self.hide_wait_window()

        self.warn_repositories()
        self.packages_install()

    def quit(self, widget = None, event = None, sysexit = True ):
        if hasattr(self,'ugcTask'):
            if self.ugcTask != None:
                self.ugcTask.kill()
                while self.ugcTask.isAlive():
                    time.sleep(0.2)
        if hasattr(self,'Equo'):
            self.Equo.destroy()

        if sysexit:
            self.exitNow()
            raise SystemExit(0)

    def exitNow(self):
        self.show_wait_window()
        try: gtk.main_quit()
        except RuntimeError: pass

    def gtk_loop(self):
        while gtk.events_pending():
           gtk.main_iteration()

    def setup_gui(self):

        self.clipboard = gtk.Clipboard()
        self.pty = pty.openpty()
        self.output = fakeoutfile(self.pty[1])
        self.input = fakeinfile(self.pty[1])
        self.do_debug = False
        if "--debug" in sys.argv:
            self.do_debug = True
        elif os.getenv('SULFUR_DEBUG') != None:
            self.do_debug = True
        if not self.do_debug:
            sys.stdout = self.output
            sys.stderr = self.output
            sys.stdin = self.input

        self.queue = Queue(self)
        self.etpbase.connect_queue(self.queue)
        self.queueView = EntropyQueueView(self.ui.queueView, self.queue)
        self.pkgView = EntropyPackageView(self.ui.viewPkg, self.queueView,
            self.ui, self.etpbase, self.ui.main, self)
        self.filesView = EntropyFilesView(self.ui.filesView)
        self.advisoriesView = EntropyAdvisoriesView(self.ui.advisoriesView,
            self.ui, self.etpbase)
        self.queue.connect_objects(self.Equo, self.etpbase, self.pkgView, self.ui)
        self.repoView = EntropyRepoView(self.ui.viewRepo, self.ui, self)
        self.repoMirrorsView = EntropyRepositoryMirrorsView(self.addrepo_ui.mirrorsView)
        # Left Side Toolbar
        self.pageButtons = {}    # Dict with page buttons
        self.firstButton = None  # first button
        self.activePage = 'repos'
        self.pageBootstrap = True
        # Progress bars
        self.progress = BaseProgress(self.ui,self.setPage,self)
        # Package Radiobuttons
        self.packageRB = {}
        self.lastPkgPB = 'updates'
        self.tooltip =  gtk.Tooltips()

        # color settings mapping dictionary
        self.colorSettingsMap = {
            "color_console_font": self.ui.color_console_font_picker,
            "color_normal": self.ui.color_normal_picker,
            "color_update": self.ui.color_update_picker,
            "color_install": self.ui.color_install_picker,
            "color_install": self.ui.color_install_picker,
            "color_remove": self.ui.color_remove_picker,
            "color_reinstall": self.ui.color_reinstall_picker,
            "color_title": self.ui.color_title_picker,
            "color_title2": self.ui.color_title2_picker,
            "color_pkgdesc": self.ui.color_pkgdesc_picker,
            "color_pkgsubtitle": self.ui.color_pkgsubtitle_picker,
            "color_subdesc": self.ui.color_subdesc_picker,
            "color_error": self.ui.color_error_picker,
            "color_good": self.ui.color_good_picker,
            "color_background_good": self.ui.color_background_good_picker,
            "color_background_error": self.ui.color_background_error_picker,
            "color_good_on_color_background": self.ui.color_good_on_color_background_picker,
            "color_error_on_color_background": self.ui.color_error_on_color_background_picker,
            "color_package_category": self.ui.color_package_category_picker,
        }
        self.colorSettingsReverseMap = {
            self.ui.color_console_font_picker: "color_console_font",
            self.ui.color_normal_picker: "color_normal",
            self.ui.color_update_picker: "color_update",
            self.ui.color_install_picker: "color_install",
            self.ui.color_install_picker: "color_install",
            self.ui.color_remove_picker: "color_remove",
            self.ui.color_reinstall_picker: "color_reinstall",
            self.ui.color_title_picker: "color_title",
            self.ui.color_title2_picker:  "color_title2",
            self.ui.color_pkgdesc_picker: "color_pkgdesc",
            self.ui.color_pkgsubtitle_picker: "color_pkgsubtitle",
            self.ui.color_subdesc_picker: "color_subdesc",
            self.ui.color_error_picker: "color_error",
            self.ui.color_good_picker: "color_good",
            self.ui.color_background_good_picker: "color_background_good",
            self.ui.color_background_error_picker: "color_background_error",
            self.ui.color_good_on_color_background_picker: "color_good_on_color_background",
            self.ui.color_error_on_color_background_picker: "color_error_on_color_background",
            self.ui.color_package_category_picker: "color_package_category",
        }

        # setup add repository window
        self.console_menu_xml = gtk.glade.XML( const.GLADE_FILE, "terminalMenu",domain="entropy" )
        self.console_menu = self.console_menu_xml.get_widget( "terminalMenu" )
        self.console_menu_xml.signal_autoconnect(self)

        self.ui.main.set_title( "%s %s %s" % (SulfurConf.branding_title, const.__spritz_version__, self.safe_mode_txt) )
        self.ui.main.connect( "delete_event", self.quit )
        self.ui.notebook.set_show_tabs( False )
        self.ui.main.present()
        self.setupPageButtons()        # Setup left side toolbar
        self.setPage(self.activePage)

        # put self.console in place
        self.console = SulfurConsole()
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

        self.ugcTask = None
        self.spawning_ugc = False
        self.Preferences = None
        self.skipMirrorNow = False
        self.abortQueueNow = False
        self.doProgress = False
        self.isWorking = False
        self.lastPkgPB = "updates"
        self.Equo.connect_to_gui(self)
        self.setupEditor()

        self.setPage("packages")

        self.setupAdvisories()
        # setup Repositories
        self.setupRepoView()
        self.firstTime = True
        # calculate updates
        self.setup_application()

        self.console.set_pty(self.pty[0])
        self.resetProgressText()
        self.pkgProperties_selected = None
        self.setupPreferences()
        self.setup_pkg_sorter()
        self.setupUgc()

    def setup_pkg_sorter(self):

        self.avail_pkg_sorters = {
            'default': DefaultPackageViewModelInjector,
            'name_az': NameSortPackageViewModelInjector,
            'name_za': NameRevSortPackageViewModelInjector,
            'downloads': DownloadSortPackageViewModelInjector,
            'votes': VoteSortPackageViewModelInjector,
            'repository': RepoSortPackageViewModelInjector,
        }
        self.pkg_sorters_desc = {
            'default': _("Default packages sorting"),
            'name_az': _("Sort by name [A-Z]"),
            'name_za': _("Sort by name [Z-A]"),
            'downloads': _("Sort by downloads"),
            'votes': _("Sort by votes"),
            'repository': _("Sort by repository"),
        }
        self.pkg_sorters_id = {
            0: 'default',
            1: 'name_az',
            2: 'name_za',
            3: 'downloads',
            4: 'votes',
            5: 'repository',
        }
        self.pkg_sorters_id_inverse = {
            'default': 0,
            'name_az': 1,
            'name_za': 2,
            'downloads': 3,
            'votes': 4,
            'repository': 5,
        }
        self.pkg_sorters_img_ids = {
            0: gtk.STOCK_PRINT_PREVIEW,
            1: gtk.STOCK_SORT_DESCENDING,
            2: gtk.STOCK_SORT_ASCENDING,
            3: gtk.STOCK_GOTO_BOTTOM,
            4: gtk.STOCK_INFO,
            5: gtk.STOCK_CONNECT,
        }

        # setup package sorter
        sorter_model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        sorter = self.ui.pkgSorter
        sorter.set_model(sorter_model)

        sorter_img_cell = gtk.CellRendererPixbuf()
        sorter.pack_start(sorter_img_cell, True)
        sorter.add_attribute(sorter_img_cell, 'stock-id', 0)

        sorter_cell = gtk.CellRendererText()
        sorter.pack_start(sorter_cell, True)
        sorter.add_attribute(sorter_cell, 'text', 1)

        first = True
        for s_id in sorted(self.pkg_sorters_id):
            s_id_name = self.pkg_sorters_id.get(s_id)
            s_id_desc = self.pkg_sorters_desc.get(s_id_name)
            stock_img_id = self.pkg_sorters_img_ids.get(s_id)
            item = sorter_model.append( (stock_img_id, s_id_desc,) )
            if first:
                sorter.set_active_iter(item)
                first = False

    def show_wait_window(self):
        self.ui.main.set_sensitive(False)
        self.wait_ui.waitWindow.show_all()
        self.wait_ui.waitWindow.queue_draw()
        self.ui.main.queue_draw()
        self.gtk_loop()

    def hide_wait_window(self):
        self.wait_ui.waitWindow.hide()
        self.ui.main.set_sensitive(True)

    def warn_repositories(self):
        all_repos = self.Equo.SystemSettings['repositories']['order']
        valid_repos = self.Equo.validRepositories
        invalid_repos = [x for x in all_repos if x not in valid_repos]
        invalid_repos = [x for x in invalid_repos if \
            (self.Equo.get_repository_revision(x) == -1)]
        if invalid_repos:
            mydialog = ConfirmationDialog(self.ui.main, invalid_repos,
                top_text = _("The repositories listed below are configured but not available. They should be downloaded."),
                sub_text = _("If you don't do this now, you won't be able to use them."), # the repositories
                simpleList = True)
            mydialog.okbutton.set_label(_("Download now"))
            mydialog.cancelbutton.set_label(_("Skip"))
            rc = mydialog.run()
            mydialog.destroy()
            if rc == -5:
                self.do_repo_refresh(invalid_repos)

    def packages_install(self):

        packages_install = os.getenv("SULFUR_PACKAGES")
        atoms_install = []
        do_fetch = False
        if "--fetch" in sys.argv:
            do_fetch = True
            sys.argv.remove("--fetch")

        if "--install" in sys.argv:
            atoms_install.extend(sys.argv[sys.argv.index("--install")+1:])

        if packages_install:
            packages_install = [x for x in packages_install.split(";") \
                if os.path.isfile(x)]

        for arg in sys.argv:
            if arg.endswith(etpConst['packagesext']) and os.path.isfile(arg):
                arg = os.path.realpath(arg)
                packages_install.append(arg)

        if packages_install:

            fn = packages_install[0]
            self.on_installPackageItem_activate(None,fn)

        elif atoms_install: # --install <atom1> <atom2> ... support

            rc = self.add_atoms_to_queue(atoms_install)
            if not rc:
                return
            self.setPage('output')

            try:
                rc = self.process_queue(self.queue.packages,
                    fetch_only = do_fetch)
            except:
                if self.do_debug:
                    entropy.tools.print_traceback()
                    import pdb; pdb.set_trace()
                else:
                    raise

            self.resetQueueProgressBars()
            if rc:
                self.queue.clear()
                self.queueView.refresh()

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
        self.setupPkgRadio(self.ui.rbAll,"all",_('Show All Packages'))
        self.setupPkgRadio(self.ui.rbPkgSets,"pkgsets",_('Show Package Sets'))
        self.setupPkgRadio(self.ui.rbPkgQueued,"queued",_('Show Queued Packages'))

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
            elif tag == "pkgsets":
                pix = self.ui.rbPackageSetsImage
            elif tag == "queued":
                pix = self.ui.rbQueuedImage
            elif tag == "all":
                pix = self.ui.rbAllImage
            pix.set_from_pixbuf( p )
            pix.show()
        except gobject.GError:
            pass

        self.tooltip.set_tip(widget,tip)
        self.packageRB[tag] = widget

    def setupPageButtons(self):
        # Setup Vertical Toolbar
        self.createButton( _( "Packages" ), "button-packages.png", 'packages', True )
        self.createButton( _( "Security Advisories" ), "button-glsa.png", 'glsa' )
        self.createButton( _( "Repository Selection" ), "button-repo.png", 'repos' )
        self.createButton( _( "Configuration Files" ), "button-conf.png", 'filesconf' )
        self.createButton( _( "Preferences" ), "preferences.png", 'preferences' )
        self.createButton( _( "Package Queue" ), "button-queue.png", 'queue' )
        self.createButton( _( "Output" ), "button-output.png", 'output' )

    def createButton( self, text, icon, page, first = None ):
        if first:
            button = gtk.RadioButton( None )
            self.firstButton = button
        else:
            button = gtk.RadioButton( self.firstButton )
        button.connect( "clicked", self.on_PageButton_changed, page )

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

    def setupUgc(self):
        self.ugcTask = TimeScheduled(30, self.spawnUgcUpdate)
        self.ugcTask.set_delay_before(True)
        if "--nougc" not in sys.argv:
            self.ugcTask.start()

    def spawnUgcUpdate(self):
        self.ugcTask.set_delay(300)
        if self.do_debug: print "entering UGC"
        try:
            self.ugc_update()
        except (SystemExit,):
            raise
        except:
            pass
        if self.do_debug: print "quitting UGC"

    def ugc_update(self):

        if self.spawning_ugc or self.isWorking or self.disable_ugc:
            return

        self.isWorking = True
        self.spawning_ugc = True
        if self.do_debug: print "are we connected?"
        connected = entropy.tools.get_remote_data(etpConst['conntestlink'])
        if self.do_debug:
            cr = False
            if connected: cr = True
            print "conn result",cr
        if (isinstance(connected,bool) and (not connected)) or (self.Equo.UGC == None):
            self.isWorking = False
            self.spawning_ugc = False
            return
        for repo in self.Equo.validRepositories:
            if self.do_debug:
                t1 = time.time()
                print "working UGC update for",repo
            self.Equo.update_ugc_cache(repo)
            if self.do_debug:
                t2 = time.time()
                td = t2 - t1
                print "completed UGC update for",repo,"took",td

        self.isWorking = False
        self.spawning_ugc = False

    def fillPreferencesDbBackupPage(self):
        self.dbBackupStore.clear()
        backed_up_dbs = self.Equo.list_backedup_client_databases()
        for mypath in backed_up_dbs:
            mymtime = entropy.tools.get_file_unix_mtime(mypath)
            mytime = entropy.tools.convert_unix_time_to_human_time(mymtime)
            self.dbBackupStore.append( (mypath,os.path.basename(mypath),mytime,) )

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
            return entropy.tools.write_parameter_to_file(config_file,name,data)

        sys_settings_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        self.Preferences = {
            etpConst['entropyconf']: [
                (
                    'ftp-proxy',
                    self.Equo.SystemSettings['system']['proxy']['ftp'],
                    basestring,
                    fillSetting,
                    saveSetting,
                    self.ui.ftpProxyEntry.set_text,
                    self.ui.ftpProxyEntry.get_text,
                ),
                (
                    'http-proxy',
                    self.Equo.SystemSettings['system']['proxy']['http'],
                    basestring,
                    fillSetting,
                    saveSetting,
                    self.ui.httpProxyEntry.set_text,
                    self.ui.httpProxyEntry.get_text,
                ),
                (
                    'proxy-username',
                    self.Equo.SystemSettings['system']['proxy']['username'],
                    basestring,
                    fillSetting,
                    saveSetting,
                    self.ui.usernameProxyEntry.set_text,
                    self.ui.usernameProxyEntry.get_text,
                ),
                (
                    'proxy-password',
                    self.Equo.SystemSettings['system']['proxy']['password'],
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
            etpConst['clientconf']: [
                (
                    'collisionprotect',
                    self.Equo.SystemSettings[sys_settings_plg_id]['misc']['collisionprotect'],
                    int,
                    fillSetting,
                    saveSetting,
                    self.ui.collisionProtectionCombo.set_active,
                    self.ui.collisionProtectionCombo.get_active,
                ),
                (
                    'configprotect',
                    self.Equo.SystemSettings[sys_settings_plg_id]['misc']['configprotect'],
                    list,
                    fillSettingView,
                    saveSettingView,
                    self.configProtectModel,
                    self.configProtectView,
                ),
                (
                    'configprotectmask',
                    self.Equo.SystemSettings[sys_settings_plg_id]['misc']['configprotectmask'],
                    list,
                    fillSettingView,
                    saveSettingView,
                    self.configProtectMaskModel,
                    self.configProtectMaskView,
                ),
                (
                    'configprotectskip',
                    self.Equo.SystemSettings[sys_settings_plg_id]['misc']['configprotectskip'],
                    list,
                    fillSettingView,
                    saveSettingView,
                    self.configProtectSkipModel,
                    self.configProtectSkipView,
                ),
                (
                    'filesbackup',
                    self.Equo.SystemSettings[sys_settings_plg_id]['misc']['filesbackup'],
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
                    self.Equo.SystemSettings['repositories']['transfer_limit'],
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

        rc, e = SulfurConf.save()
        if not rc: okDialog( self.ui.main, "%s: %s" % (_("Error saving preferences"),e) )
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

    def endWorking(self):
        self.isWorking = False
        self.ui.progressVBox.grab_remove()
        normalCursor(self.ui.main)

    def setup_application(self):
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

    def cleanEntropyCaches(self, alone = False):
        if alone:
            self.progress.total.hide()
        self.Equo.generate_cache(depcache = True, configcache = False)
        # clear views
        self.etpbase.clearPackages()
        self.etpbase.clearCache()
        self.setup_application()
        if alone:
            self.progress.total.show()

    def populateAdvisories(self, widget, show):
        self.setBusy()
        self.show_wait_window()
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
        self.hide_wait_window()

    def populateFilesUpdate(self):
        # load filesUpdate interface and fill self.filesView
        cached = None
        try:
            cached = self.Equo.FileUpdates.load_cache()
        except CacheCorruptionError:
            pass
        if cached == None:
            self.setBusy()
            cached = self.Equo.FileUpdates.scanfs(quiet = True)
            self.unsetBusy()
        if cached:
            self.filesView.populate(cached)

    def showNoticeBoard(self):
        repoids = {}
        for repoid in self.Equo.validRepositories:
            avail_repos = self.Equo.SystemSettings['repositories']['available']
            board_file = avail_repos[repoid]['local_notice_board']
            if not (os.path.isfile(board_file) and os.access(board_file,os.R_OK)):
                continue
            if entropy.tools.get_file_size(board_file) < 10:
                continue
            repoids[repoid] = board_file
        if repoids:
            self.loadNoticeBoard(repoids)

    def loadNoticeBoard(self, repoids):
        my = NoticeBoardWindow(self.ui.main, self.Equo)
        my.load(repoids)

    def updateRepositories(self, repos):

        self.disable_ugc = True
        """
        # set steps
        progress_step = float(1)/(len(repos))
        step = progress_step
        myrange = []
        while progress_step < 1.0:
            myrange.append(step)
            progress_step += step
        myrange.append(step)
        self.progress.total.setup( myrange )
        """
        self.progress.total.hide()

        self.progress.set_mainLabel(_('Initializing Repository module...'))
        forceUpdate = self.ui.forceRepoUpdate.get_active()

        try:
            repoConn = self.Equo.Repositories(repos, forceUpdate = forceUpdate)
        except PermissionDenied:
            self.progressLog(_('You must run this application as root'), extra = "repositories")
            self.disable_ugc = False
            return 1
        except MissingParameter:
            msg = "%s: %s" % (_('No repositories specified in'),etpConst['repositoriesconf'],)
            self.progressLog( msg, extra = "repositories")
            self.disable_ugc = False
            return 127
        except OnlineMirrorError:
            self.progressLog(_('You are not connected to the Internet. You should.'), extra = "repositories")
            self.disable_ugc = False
            return 126
        except Exception, e:
            msg = "%s: %s" % (_('Unhandled exception'),e,)
            self.progressLog(msg, extra = "repositories")
            self.disable_ugc = False
            return 2

        self.__repo_update_rc = -1000
        def run_up():
            self.__repo_update_rc = repoConn.sync()

        t = ParallelTask(run_up)
        t.start()
        while t.isAlive():
            time.sleep(0.2)
            if self.do_debug:
                print "updateRepositories: update thread still alive"
            self.gtk_loop()
        rc = self.__repo_update_rc

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

        initconfig_entropy_constants(etpSys['rootdir'])

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

        mytxt = []
        slice_count = self.console.get_column_count()
        while msg:
            my = msg[:slice_count]
            msg = msg[slice_count:]
            mytxt.append(my)

        for txt in mytxt:
            if extra:
                self.output.write_line("%s: %s\n" % (extra,txt,))
                continue
            self.output.write_line("%s\n" % (txt,))

    def progressLogWrite(self, msg):

        mytxt = []
        slice_count = self.console.get_column_count()
        while msg:
            my = msg[:slice_count]
            msg = msg[slice_count:]
            mytxt.append(my)

        for txt in mytxt: self.output.write_line("%s\n" % (txt,))

    def enableSkipMirror(self):
        self.ui.skipMirror.show()
        self.skipMirror = True

    def disableSkipMirror(self):
        self.ui.skipMirror.hide()
        self.skipMirror = False

    def addPackages(self, back_to_page = None):

        self.uiLock(True)
        action = self.lastPkgPB
        if action == 'all':
            masks = ['installed','available','masked','updates']
        else:
            masks = [action]

        self.disable_ugc = True
        self.setBusy()
        bootstrap = False
        if (self.Equo.get_world_update_cache(empty_deps = False) == None):
            if self.do_debug:
                print "addPackages: bootstrap True due to empty world cache"
            bootstrap = True
            self.setPage('output')
        elif (self.Equo.get_available_packages_cache() == None) and \
            (('available' in masks) or ('updates' in masks)):
            if self.do_debug:
                print "addPackages: bootstrap True due to empty avail cache"
            bootstrap = True
            self.setPage('output')
        self.progress.total.hide()

        if bootstrap:
            if self.do_debug:
                print "addPackages: bootstrap is enabled, clearing ALL cache"
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

        #if bootstrap: time.sleep(1)
        self.setStatus("%s: %s %s" % (_("Showing"),len(allpkgs),_("items"),))

        show_pkgsets = False
        if action == "pkgsets":
            show_pkgsets = True

        self.pkgView.populate(allpkgs, empty = empty, pkgsets = show_pkgsets)
        self.progress.total.show()

        if self.doProgress: self.progress.hide() #Hide Progress
        if back_to_page:
            self.setPage(back_to_page)
        elif bootstrap:
            self.setPage('packages')

        self.unsetBusy()
        self.uiLock(False)
        # reset labels
        self.resetProgressText()
        self.resetQueueProgressBars()
        self.disable_ugc = False

    def process_queue(self, pkgs, remove_repos = [], fetch_only = False, download_sources = False):

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
            self.setPage('output')
            queue = pkgs['i']+pkgs['u']+pkgs['rr']
            install_queue = [x.matched_atom for x in queue]
            selected_by_user = set([x.matched_atom for x in queue if x.selected_by_user])
            removal_queue = [x.matched_atom[0] for x in pkgs['r']]
            do_purge_cache = set([x.matched_atom[0] for x in pkgs['r'] if x.do_purge])

            if install_queue or removal_queue:

                # activate UI lock
                self.uiLock(True)

                controller = QueueExecutor(self)
                self.my_inst_errors = None
                self.my_inst_abort = False
                def run_tha_bstrd():
                    try:
                        e, i = controller.run(install_queue[:],
                            removal_queue[:], do_purge_cache,
                            fetch_only = fetch_only,
                            download_sources = download_sources,
                            selected_by_user = selected_by_user)
                    except QueueError:
                        self.my_inst_abort = True
                        e, i = 1, None
                    except:
                        entropy.tools.print_traceback()
                        e, i = 1, None
                    self.my_inst_errors = (e, i,)

                t = ParallelTask(run_tha_bstrd)
                t.start()
                while t.isAlive():
                    time.sleep(0.2)
                    if self.do_debug:
                        print "process_queue: QueueExecutor thread still alive"
                    self.gtk_loop()

                e,i = self.my_inst_errors
                if self.do_debug:
                    print "process_queue: left all"

                self.ui.skipMirror.hide()
                self.ui.abortQueue.hide()
                if self.do_debug:
                    print "process_queue: buttons now hidden"

                # deactivate UI lock
                if self.do_debug:
                    print "process_queue: unlocking gui?"
                self.uiLock(False)
                if self.do_debug:
                    print "process_queue: gui unlocked"

                if self.my_inst_abort:
                    okDialog(self.ui.main, _("Attention. You chose to abort the processing."))
                elif (e != 0):
                    okDialog(self.ui.main,
                        _("Attention. An error occured when processing the queue."
                        "\nPlease have a look in the processing terminal.")
                    )

            if self.do_debug:
                print "process_queue: endWorking?"
            self.endWorking()
            self.progress.reset_progress()
            if self.do_debug:
                print "process_queue: endWorking"

            if (not fetch_only) and (not download_sources):

                if self.do_debug:
                    print "process_queue: cleared caches"

                for myrepo in remove_repos:
                    self.Equo.remove_repository(myrepo)

                self.reset_cache_status()
                if self.do_debug:
                    print "process_queue: closed repo dbs"
                self.Equo.reopen_client_repository()
                if self.do_debug:
                    print "process_queue: cleared caches (again)"
                # regenerate packages information
                if self.do_debug:
                    print "process_queue: setting up Sulfur"
                self.setup_application()
                if self.do_debug:
                    print "process_queue: scanning for new files"
                self.Equo.FileUpdates.scanfs(dcache = False, quiet = True)
                if self.Equo.FileUpdates.scandata:
                    if len(self.Equo.FileUpdates.scandata) > 0:
                        self.setPage('filesconf')
                if self.do_debug:
                    print "process_queue: all done"

        else:
            self.setStatus( _( "No packages selected" ) )

        self.disable_ugc = False
        return state

    def uiLock(self, lock):
        self.ui.content.set_sensitive(not lock)
        self.ui.menubar.set_sensitive(not lock)

    def switchNotebookPage(self, page):
        rb = self.pageButtons[page]
        rb.set_active(True)
        self.on_PageButton_changed(None, page)

####### events

    def _get_selected_repo_index( self ):
        selection = self.repoView.view.get_selection()
        repodata = selection.get_selected()
        # get text
        if repodata[1] != None:
            repoid = self.repoView.get_repoid(repodata)
            # do it if it's enabled
            repo_order = self.Equo.SystemSettings['repositories']['order']
            if repoid in repo_order:
                idx = repo_order.index(repoid)
                return idx, repoid, repodata
        return None, None, None

    def runEditor(self, filename, delete = False):
        cmd = ' '.join([self.fileEditor,filename])
        task = ParallelTask(self.__runEditor, cmd, delete, filename)
        task.start()

    def __runEditor(self, cmd, delete, filename):
        os.system(cmd+"&> /dev/null")
        if delete and os.path.isfile(filename) and os.access(filename,os.W_OK):
            try:
                os.remove(filename)
            except OSError:
                pass

    def _get_Edit_filename(self):
        selection = self.filesView.view.get_selection()
        model, iterator = selection.get_selected()
        if model != None and iterator != None:
            identifier = model.get_value( iterator, 0 )
            destination = model.get_value( iterator, 2 )
            source = model.get_value( iterator, 1 )
            source = os.path.join(os.path.dirname(destination),source)
            return identifier, source, destination
        return 0,None,None

    def add_atoms_to_queue(self, atoms, always_ask = False, matches = set()):

        self.show_wait_window()
        self.setBusy()
        if not matches:
            # resolve atoms ?
            for atom in atoms:
                match = self.Equo.atom_match(atom)
                if match[0] != -1:
                    matches.add(match)
        if not matches:
            self.hide_wait_window()
            okDialog( self.ui.main, _("Packages not found in repositories, try again later.") )
            self.unsetBusy()
            return

        resolved = []

        self.etpbase.getPackages('installed')
        self.etpbase.getPackages('available')
        self.etpbase.getPackages('reinstallable')
        self.etpbase.getPackages('updates')

        for match in matches:
            resolved.append(self.etpbase.getPackageItem(match)[0])

        rc = True

        found_objs = []
        for obj in resolved:
            if obj in self.queue.packages['i'] + \
                        self.queue.packages['u'] + \
                        self.queue.packages['r'] + \
                        self.queue.packages['rr']:
                continue
            found_objs.append(obj)


        q_cache = {}
        for obj in found_objs:
            q_cache[obj.matched_atom] = obj.queued
            obj.queued = 'u'

        status, myaction = self.queue.add(found_objs, always_ask = always_ask)
        if status != 0:
            rc = False
            for obj in found_objs:
                obj.queued = q_cache.get(obj.matched_atom)

        self.queueView.refresh()
        self.ui.viewPkg.queue_draw()

        self.hide_wait_window()
        self.unsetBusy()
        return rc

    def _load_repo_data(self, repodata):
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

    def reset_cache_status(self):
        self.pkgView.clear()
        self.etpbase.clearPackages()
        self.etpbase.clearCache()
        self.queue.clear()
        self.queueView.refresh()
        # re-scan system settings, useful
        # if there are packages that have been
        # live masked, and anyway, better wasting
        # 2-3 more cycles than having unattended
        # behaviours
        self.Equo.SystemSettings.clear()
        self.Equo.close_all_repositories()

    def _validate_repo_submit(self, repodata, edit = False):
        errors = []
        if not repodata['repoid']:
            errors.append(_('No Repository Identifier'))
        if repodata['repoid'] and self.Equo.SystemSettings['repositories']['available'].has_key(repodata['repoid']):
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

    def _get_repo_data(self):
        repodata = {}
        repodata['repoid'] = self.addrepo_ui.repoidEntry.get_text()
        repodata['description'] = self.addrepo_ui.repoDescEntry.get_text()
        repodata['plain_packages'] = self.repoMirrorsView.get_all()
        repodata['dbcformat'] = self.addrepo_ui.repodbcformatEntry.get_active_text()
        repodata['plain_database'] = self.addrepo_ui.repodbEntry.get_text()
        repodata['service_port'] = self.addrepo_ui.repodbPort.get_text()
        repodata['ssl_service_port'] = self.addrepo_ui.repodbPortSSL.get_text()
        return repodata

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

    def queue_bombing(self):
        if self.abortQueueNow:
            self.abortQueueNow = False
            mytxt = _("Aborting queue tasks.")
            raise QueueError('QueueError %s' % (mytxt,))

    def mirror_bombing(self):
        if self.skipMirrorNow:
            self.skipMirrorNow = False
            mytxt = _("Skipping current mirror.")
            raise OnlineMirrorError('OnlineMirrorError %s' % (mytxt,))

    def load_ugc_repositories(self):
        self.ugcRepositoriesModel.clear()
        repo_order = self.Equo.SystemSettings['repositories']['order']
        repo_excluded = self.Equo.SystemSettings['repositories']['excluded']
        avail_repos = self.Equo.SystemSettings['repositories']['available']
        for repoid in repo_order+sorted(repo_excluded.keys()):
            repodata = avail_repos.get(repoid)
            if repodata == None:
                repodata = repo_excluded.get(repoid)
            if repodata == None: continue # wtf?
            self.ugcRepositoriesModel.append([repodata])

    def load_color_settings(self):
        for key,s_widget in self.colorSettingsMap.items():
            if not hasattr(SulfurConf,key):
                if self.do_debug: print "WARNING: no %s in SulfurConf" % (key,)
                continue
            color = getattr(SulfurConf,key)
            s_widget.set_color(gtk.gdk.color_parse(color))

if __name__ == "__main__":

    try:
        try:
            gtk.window_set_default_icon_from_file(const.PIXMAPS_PATH+"/sulfur-icon.png")
        except gobject.GError:
            pass
        mainApp = SulfurApplication()
        mainApp.init()
        gobject.threads_init()
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()
        entropy.tools.kill_threads()
        mainApp.quit()
    except SystemExit:
        print "Quit by User (SystemExit)"
        try:
            mainApp.quit()
        except NameError:
            pass
    except KeyboardInterrupt:
        print "Quit by User (KeyboardInterrupt)"
        try:
            mainApp.quit()
        except NameError:
            pass
    except: # catch other exception and write it to the logger.
        entropy.tools.kill_threads()
        try:
            mainApp.quit(sysexit = False)
        except NameError:
            pass
        my = ExceptionDialog()
        my.show()

    raise SystemExit(0)
