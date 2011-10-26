# -*- coding: utf-8 -*-
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

import os
import gtk
import gobject
import time

try:
    from subprocess import getoutput
except ImportError:
    from commands import getoutput

from entropy.exceptions import QueueError, EntropyPackageException, \
    InvalidPackageSet
import entropy.tools
from entropy.const import etpConst, initconfig_entropy_constants, \
    const_isunicode, const_convert_to_unicode
from entropy.output import print_generic
from entropy.i18n import _
from entropy.misc import ParallelTask
from entropy.client.mirrors import StatusInterface
from entropy.services.client import WebService
import entropy.dump

from sulfur.filters import Filter
from sulfur.setup import SulfurConf, const, cleanMarkupString
from sulfur.dialogs import okDialog, input_box, TextReadDialog, questionDialog, \
    FileChooser, AboutDialog, errorMessage, AddRepositoryWindow, TipsWindow
from sulfur.core import busy_cursor, normal_cursor


class SulfurApplicationEventsMixin:

    def on_console_click(self, widget, event):
        if event.button == 3:
            self.console_menu.popup( None, None, None, event.button, event.time )
            return True

    def on_dbBackupButton_clicked(self, widget):

        def _run_backup(callback):
            with self._privileges:
                with self._async_event_execution_lock:
                    status, err_msg = self._entropy.backup_repository(
                        etpConst['clientdbid'],
                        os.path.dirname(etpConst['etpdatabaseclientfilepath']))
                    gobject.idle_add(callback, status, err_msg)

        def _backup_complete(status, err_msg):
            self.ui_lock(False)
            self.end_working()
            if not status:
                okDialog( self.ui.main, "%s: %s" % (_("Error during backup"),
                    err_msg,) )
                return
            okDialog(self.ui.main, "%s" % (_("Backup complete"),))
            self.fill_pref_db_backup_page()
            self.dbBackupView.queue_draw()

        self.start_working()
        self.ui_lock(True)
        with self._privileges:
            # make sure to commit any transaction before backing-up
            self._entropy.installed_repository().commit()
            t = ParallelTask(_run_backup, _backup_complete)
            t.start()

    def on_dbRestoreButton_clicked(self, widget):
        model, myiter = self.dbBackupView.get_selection().get_selected()
        if myiter is None:
            return
        dbpath = model.get_value(myiter, 0)

        def _run_restore(callback):
            with self._async_event_execution_lock:
                with self._privileges:
                    status, err_msg = self._entropy.restore_repository(dbpath,
                        etpConst['etpdatabaseclientfilepath'],
                        etpConst['clientdbid'])
                    gobject.idle_add(callback, status, err_msg)

        def _restore_done(status, err_msg):
            self.ui_lock(False)
            self.end_working()
            self._entropy.reopen_installed_repository()
            self.reset_cache_status()
            self.show_packages()
            if not status:
                okDialog(self.ui.main, "%s: %s" % (_("Error during restore"),
                    err_msg,))
                return
            self.fill_pref_db_backup_page()
            self.dbBackupView.queue_draw()
            okDialog(self.ui.main, "%s" % (_("Restore complete"),))

        self.start_working()
        self.ui_lock(True)
        with self._privileges:
            # make sure to commit any transaction before restoring
            self._entropy.installed_repository().commit()
            t = ParallelTask(_run_restore, _restore_done)
            t.start()

    def on_dbDeleteButton_clicked(self, widget):
        model, myiter = self.dbBackupView.get_selection().get_selected()
        if myiter == None:
            return
        dbpath = model.get_value(myiter, 0)

        with self._privileges:
            try:
                if os.path.isfile(dbpath) and os.access(dbpath, os.W_OK):
                    os.remove(dbpath)
            except OSError as e:
                okDialog( self.ui.main, "%s: %s" % (_("Error during removal"), e,) )
                return
        self.fill_pref_db_backup_page()
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

        security = self._entropy.Security()
        adv_data = security.get_advisories_metadata()
        atoms = set()
        for key in adv_data:
            affected = security.is_affected(key)
            if not affected:
                continue
            for mykey in adv_data[key]['affected']:
                affected_data = adv_data[key]['affected'][mykey][0]
                atoms |= set(affected_data['unaff_atoms'])

        rc = self.add_atoms_to_queue(atoms, always_ask = True)
        if rc:
            okDialog( self.ui.main,
                _("Packages in all Advisories have been queued.") )

    def on_advInfoButton_clicked( self, widget ):
        if self.etpbase.selected_advisory_item:
            self.load_advisory_info_menu(self.etpbase.selected_advisory_item)

    def on_filesDelete_clicked( self, widget ):
        identifier, source, dest = self._get_Edit_filename()
        if not identifier:
            return True
        with self._privileges:
            file_updates = self._get_file_updates()
            try:
                file_updates.remove(identifier)
            except KeyError:
                pass # cope with multithreading requests
            self.filesView.populate(file_updates.scan())

    def on_filesMerge_clicked( self, widget ):
        identifier, source, dest = self._get_Edit_filename()
        if not identifier:
            return True
        with self._privileges:
            file_updates = self._get_file_updates()
            try:
                file_updates.merge(identifier)
            except KeyError:
                pass # code with multithreaded requests
            self.filesView.populate(file_updates.scan())

    def on_mergeFiles_clicked( self, widget ):
        with self._privileges:
            file_updates = self._get_file_updates()
            file_updates.scan(dcache = True)
            keys = list(file_updates.scan().keys())
            for key in keys:
                try:
                    file_updates.merge(key)
                    # it's cool watching it runtime
                except KeyError:
                    pass
            self.filesView.populate(file_updates.scan())

    def on_deleteFiles_clicked( self, widget ):
        with self._privileges:
            file_updates = self._get_file_updates()
            file_updates.scan(dcache = True)
            keys = list(file_updates.scan().keys())
            for key in keys:
                try:
                    file_updates.remove(key)
                    # it's cool watching it runtime
                except KeyError:
                    pass
            self.filesView.populate(file_updates.scan())

    def on_filesEdit_clicked( self, widget ):
        identifier, source, dest = self._get_Edit_filename()
        if not identifier:
            return True

        """
        if not (os.access(source, os.R_OK | os.W_OK) os.path.isfile(source)):
            return
        source_f = open(source)
        txt = source_f.read()
        source_f.close()
        TextReadDialog(source, txt, read_only = False, rw_save_path = source)
        """
        self.run_editor(source)

    def on_filesView_row_activated( self, widget, iterator, path ):
        self.on_filesViewChanges_clicked(widget)

    def on_filesViewChanges_clicked( self, widget ):
        import subprocess
        identifier, source, dest = self._get_Edit_filename()
        if not identifier:
            return True
        diffcmd = "diff -Nu "+dest+" "+source

        mybuffer = gtk.TextBuffer()
        red_tt = mybuffer.create_tag("red", foreground = "red")
        green_tt = mybuffer.create_tag("green", foreground = "darkgreen")

        for line in getoutput(diffcmd).split("\n"):
            myiter = mybuffer.get_end_iter()
            if line.startswith("+"):
                mybuffer.insert_with_tags(myiter, line+"\n", green_tt)
            elif line.startswith("-"):
                mybuffer.insert_with_tags(myiter, line+"\n", red_tt)
            else:
                mybuffer.insert(myiter, line+"\n")
        TextReadDialog(dest, mybuffer)

    def on_filesViewRefresh_clicked( self, widget ):
        with self._privileges:
            file_updates = self._get_file_updates()
            file_updates.scan(dcache = False)
            self.filesView.populate(file_updates.scan())

    def on_shiftUp_clicked( self, widget ):
        idx, repoid, iterdata = self._get_selected_repo_index()
        if idx != None:
            path = iterdata[0].get_path(iterdata[1])[0]
            if path > 0 and idx > 0:
                idx -= 1
                self._entropy.shift_repository(repoid, idx)
                # get next iter
                prev = iterdata[0].get_iter(path-1)
                self.repoView.store.swap(iterdata[1], prev)

    def on_shiftDown_clicked( self, widget ):
        idx, repoid, iterdata = self._get_selected_repo_index()
        if idx != None:
            next = iterdata[0].iter_next(iterdata[1])
            if next:
                idx += 1
                self._entropy.shift_repository(repoid, idx)
                self.repoView.store.swap(iterdata[1], next)

    def on_addRepo_clicked( self, widget ):
        my = AddRepositoryWindow(self, self.ui.main, self._entropy)
        my.load()

    def on_removeRepo_clicked( self, widget ):
        # get selected repo
        selection = self.repoView.view.get_selection()
        repodata = selection.get_selected()
        # get text
        if repodata[1] != None:
            repoid = self.repoView.get_repoid(repodata)
            if repoid == self._settings['repositories']['default_repository']:
                rc = self._entropy.ask_question(
                    _("Are you sure you want to remove the default repository?"))
                if rc != _("Yes"):
                    return True
            removed = self._entropy.remove_repository(repoid)
            if not removed:
                okDialog(self.ui.main, _("Unable to remove repository"))
            self.reset_cache_status()
            self.setup_repoView()

    def on_repoEdit_clicked(self, widget):

        def get_repository_settings(repoid):
            try:
                repodata = self._settings['repositories']['available'][repoid]
            except KeyError:
                if repoid not in self._settings['repositories']['excluded']:
                    raise
                repodata = self._settings['repositories']['excluded'][repoid]
            return repodata.copy()

        my = AddRepositoryWindow(self, self.ui.main, self._entropy)
        my.addrepo_ui.repoSubmit.hide()
        my.addrepo_ui.repoSubmitEdit.show()
        my.addrepo_ui.repoInsert.hide()
        my.addrepo_ui.repoidEntry.set_editable(False)
        # get selection
        selection = self.repoView.view.get_selection()
        repostuff = selection.get_selected()
        if repostuff[1] != None:
            repoid = self.repoView.get_repoid(repostuff)
            repodata = get_repository_settings(repoid)
            my._load_repo_data(repodata)
            my.load()

    def on_terminal_clear_activate(self, widget):
        self.console.reset()

    def on_terminal_copy_activate(self, widget):
        self.console.copy_clipboard()

    def on_Preferences_toggled(self, widget, toggle = True):
        self.ui.preferencesSaveButton.set_sensitive(toggle)
        self.ui.preferencesRestoreButton.set_sensitive(toggle)

    def on_preferencesSaveButton_clicked(self, widget):
        sure = questionDialog(self.ui.main, _("Are you sure ?"))
        if not sure:
            return
        for config_file in self._preferences:
            for name, setting, mytype, fillfunc, savefunc, wgwrite, wgread in self._preferences[config_file]:
                if mytype == list:
                    with self._privileges:
                        savefunc(config_file, name, setting, mytype,
                            wgwrite, wgread)
                else:
                    data = wgread()
                    with self._privileges:
                        result = savefunc(config_file, name, setting,
                            mytype, data)
                    if not result:
                        errorMessage(
                            self.ui.main,
                            cleanMarkupString("%s: %s") % (_("Error saving parameter"), name,),
                            _("An issue occured while saving a preference"),
                            "%s %s: %s" % (_("Parameter"), name, _("not saved"),),
                        )

        initconfig_entropy_constants(etpConst['systemroot'])
        # re-read configprotect
        self.reset_cache_status()
        self.show_packages()
        self.setup_preferences()

    def on_preferencesRestoreButton_clicked(self, widget):
        self.setup_preferences()

    def on_configProtectNew_clicked(self, widget):
        data = input_box( self.ui.main, _("New"), _("Please insert a new path"))
        if not data:
            return
        self.configProtectModel.append([data])

    def on_configProtectMaskNew_clicked(self, widget):
        data = input_box( self.ui.main, _("New"), _("Please insert a new path"))
        if not data:
            return
        self.configProtectMaskModel.append([data])

    def on_configProtectSkipNew_clicked(self, widget):
        data = input_box( self.ui.main, _("New"), _("Please insert a new path"))
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
            data = input_box( self.ui.main, _("New"),
                _("Please edit the selected path"), input_text = item)
            if not data:
                return
            model.remove(myiter)
            self.configProtectModel.append([data])

    def on_configProtectMaskEdit_clicked(self, widget):
        model, myiter = self.configProtectMaskView.get_selection().get_selected()
        if myiter:
            item = model.get_value( myiter, 0 )
            data = input_box( self.ui.main, _("New"),
                _("Please edit the selected path"), input_text = item)
            if not data:
                return
            model.remove(myiter)
            self.configProtectMaskModel.append([data])

    def on_configProtectSkipEdit_clicked(self, widget):
        model, myiter = self.configProtectSkipView.get_selection().get_selected()
        if myiter:
            item = model.get_value( myiter, 0 )
            data = input_box( self.ui.main, _("New"),
                _("Please edit the selected path"), input_text = item)
            if not data:
                return
            model.remove(myiter)
            self.configProtectSkipModel.append([data])

    def on_installPackageItem_activate(self, widget = None, fn = None, get_st = False):

        if (widget and self._is_working) or self.isBusy:
            return False

        if not fn:
            mypattern = '*'+etpConst['packagesext']
            fn = FileChooser(pattern = mypattern)
        if not fn:
            if get_st:
                return False
            return
        elif not os.access(fn, os.R_OK):
            if get_st:
                return False
            return

        msg = "%s: %s. %s" % (
            _("You have chosen to install this package"),
            os.path.basename(fn),
            _("Are you sure?"),
        )
        rc = questionDialog(self.ui.main, msg)
        if not rc:
            if get_st:
                return False
            return

        # clear all caches
        self.reset_cache_status()
        self.pkgView.store.clear()

        newrepo = os.path.basename(fn)
        # we have it !
        try:
            atomsfound = self._entropy.add_package_repository(fn)
        except EntropyPackageException as err:
            okDialog(self.ui.main, str(err))
            if get_st:
                return False
            return

        def clean_n_quit(newrepo):
            self._entropy.remove_repository(newrepo) # ignore outcome
            self.reset_cache_status(quick=True)
            # regenerate packages information
            self.setup_application()

        if not atomsfound:
            clean_n_quit(newrepo)
            if get_st:
                return False
            return

        pkgs = []
        for idpackage, atom in atomsfound:
            yp, new = self.etpbase.get_package_item((idpackage, newrepo,))
            pkgs.append(yp)

        busy_cursor(self.ui.main)

        done = self.add_to_queue(pkgs, "i", False)
        if not done:
            clean_n_quit(newrepo)
            normal_cursor(self.ui.main)
            if get_st:
                return False
            return

        normal_cursor(self.ui.main)
        self.switch_notebook_page('output')

        def status_cb(status):
            if not status:
                clean_n_quit(newrepo)

        self.install_queue(remove_repos = [newrepo], status_cb = status_cb)
        self.reset_queue_progress_bars()
        if get_st:
            return True


    def on_PageButton_changed(self, widget, page, do_set = True):

        # do not put here actions for 'packages' and 'output'
        # but use on_PageButton_pressed
        if page == "filesconf":
            self._populate_files_update()
        elif page == "glsa":

            def adv_populate():
                self.populate_advisories(None, "affected")

            def setup_metadata():
                self.advisoriesView.populate_loading_message()
                self.gtk_loop()
                security = self._entropy.Security()
                security.get_advisories_metadata()
                gobject.timeout_add(0, adv_populate)

            gobject.idle_add(setup_metadata)

        if do_set:
            self.set_notebook_page(const.PAGES[page])

    def on_queueReviewAndInstall_clicked(self, widget):
        self.switch_notebook_page("packages")

    def on_advancedMode_toggled(self, widget):
        if not self.in_mode_loading:
            new_mode = 1
            if SulfurConf.simple_mode:
                new_mode = 0
            self.switch_application_mode(new_mode)

    def on_pkgFilter_toggled(self, rb, action, on_init = False):

        if not rb.get_active():
            # filter out on-release events
            return
        rb.grab_add()

        do_clear_filter_bar = False
        if action != self.lastPkgPB:
            # disabled for now, users are complaining
            do_clear_filter_bar = False

        if action == "updates":
            self.ui.updatesButtonbox.show()
        else:
            self.ui.updatesButtonbox.hide()

        if action == "masked":
            self.setup_masked_pkgs_warning_box()
            self.ui.maskedWarningBox.show()
        else:
            self.ui.maskedWarningBox.hide()

        if action == "pkgsets":
            self.ui.pkgsetsButtonBox.show()
        else:
            self.ui.pkgsetsButtonBox.hide()

        if action == "queued":
            self.ui.queueTabBox.show()
        else:
            self.ui.queueTabBox.hide()

        do_show = True
        if action == "search":
            if do_clear_filter_bar and self.etpbase.get_search():
                pass # if I moved and there's already a search running
                # do not run a new search
            else:
                gobject.timeout_add(0, self.run_search_package_dialog)
                do_show = False

        self.lastPkgPB = action
        if do_show:
            self.show_packages(on_init = on_init)
        rb.grab_remove()

        if do_clear_filter_bar:
            # clear filter bar
            self.ui.pkgFilter.set_text("")

    def on_repoRefreshButton_clicked(self, widget):
        self.on_repoRefresh_clicked(widget)
        self.switch_notebook_page('packages')

    def on_repoRefresh_clicked(self, widget):
        repos = self.repoView.get_selected()
        if not repos:
            okDialog( self.ui.main, _("Please select at least one repository") )
            return
        return self.do_repo_refresh(repos)

    def do_repo_refresh(self, repos):
        self.switch_notebook_page('output')
        def _complete_cb(status):
            self.switch_notebook_page('repos')
            if status:
                self.show_notice_board()
        self.update_repositories(repos, complete_cb = _complete_cb)

    def on_cacheButton_clicked(self, widget):
        self.repoView.get_selected()
        self.switch_notebook_page('output')
        self.switch_notebook_page('repos')

    def on_repoDeSelect_clicked(self, widget):
        self.repoView.deselect_all()

    def on_queueProcess_clicked(self, widget):

        if self.queue.total() == 0: # Check there are any packages in the queue
            self.set_status_ticker(_('No packages in queue'))
            return

        fetch_only = self.ui.queueProcessFetchOnly.get_active()
        download_sources = self.ui.queueProcessDownloadSource.get_active()

        self.install_queue(fetch = fetch_only,
            download_sources = download_sources)
        self.reset_queue_progress_bars()

    def on_queueSave_clicked( self, widget ):
        fn = FileChooser(action = gtk.FILE_CHOOSER_ACTION_SAVE, buttons = (
            gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        if fn:
            pkgdata = self.queue.get().copy()
            for key in list(pkgdata.keys()):
                if pkgdata[key]: pkgdata[key] = [x.matched_atom for x in pkgdata[key]]
            entropy.dump.dumpobj(fn, pkgdata, True)

    def on_queueOpen_clicked( self, widget ):
        fn = FileChooser()
        if fn:

            try:
                pkgdata = entropy.dump.loadobj(fn, complete_path = True)
            except:
                return

            if not isinstance(pkgdata, dict):
                return

            collected_items = []
            for key in list(pkgdata.keys()):
                for pkg in pkgdata[key]:
                    try:
                        yp, new = self.etpbase.get_package_item(pkg)
                    except:
                        okDialog( self.ui.main,
                            _("Queue is too old. Cannot load.") )
                        return
                    collected_items.append((key, yp))

            for key, pkg in collected_items:
                pkg.queued = key
                self.queue.packages[key].append(pkg)

    def on_queueClean_clicked(self, widget):
        self.reset_cache_status()
        self.set_package_radio("updates")
        self.show_packages()

    def on_adv_doubleclick( self, widget, iterator, path ):
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            data = model.get_value( iterator, 0 )
            if data and data != (None, None, None):
                self.load_advisory_info_menu(data)

    def on_pkg_click(self, widget):
        """
        When Packages View gtk.TreeView elements are single clicked.
        """
        objs = self.pkgView.collect_selected_items()
        obj = None
        for x in objs:
            if x.is_pkgset_cat:
                obj = x
                break
        if obj is None:
            # disable edit set button
            self.ui.pkgsetEditButton.set_sensitive(False)
        else:
            # enable edit set button
            self.ui.pkgsetEditButton.set_sensitive(True)


    def on_license_double_clicked( self, widget, iterator, path ):
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            license_identifier = model.get_value( iterator, 0 )
            found = False
            license_text = ''
            if license_identifier:
                repoid = self.pkgProperties_selected.matched_atom[1]
                if isinstance(repoid, int):
                    dbconn = self._entropy.installed_repository()
                else:
                    dbconn = self._entropy.open_repository(repoid)
                if dbconn.isLicenseDataKeyAvailable(license_identifier):
                    license_text = dbconn.retrieveLicenseText(license_identifier)
                    found = True
            if found:
                mytitle = "%s -- %s" % (license_identifier, _("license text"),)
                TextReadDialog(mytitle, license_text)

    def on_select_clicked(self, widget):

        self.start_working()
        sts = self.pkgView.select_all()
        self.end_working()
        normal_cursor(self.ui.main)
        # now start updating the system
        if not sts:
            rc = self._entropy.ask_question(_("Update your system now ?"))
            if rc == _("Yes"):
                self.install_queue()

    def on_deselect_clicked(self, widget):
        # @deprecated
        self.ui.pkgFilter.set_text("")
        self.on_clear_clicked(widget)
        self.pkgView.deselect_all()

    def on_skipMirror_clicked(self, widget):
        StatusInterface().add_failing_working_mirror(75)
        self.skipMirrorNow = True

    def on_abortQueue_clicked(self, widget):
        msg = _("You have chosen to interrupt the processing. Are you sure you want to do it ?")
        rc = questionDialog(self.ui.main, msg)
        if rc:
            if self.do_debug:
                print_generic("on_abortQueue_clicked: abort is now on")
            self.abortQueueNow = True

    def on_pkgFilter_icon_release(self, entry, icon_pos, event):
        entry.set_text("")

    def on_pkg_search_change(self, entry):

        def go(entry, old_txt):

            txt = entry.get_text()
            if old_txt != txt:
                self._filterbar_previous_txt = txt
                return False

            # parse string as action only if pasted
            if (not self._filterbar_previous_txt) and txt:
                accepted = self._parse_entropy_action_string(txt)
                if accepted:
                    entry.set_text("")

            flt = Filter.get('KeywordFilter')
            self.etpbase.set_filter(Filter.processFilters)

            if not txt:
                self.etpbase.set_filter()
                flt.activate(False)
            else:
                flt.activate()
                flt.setKeys(txt.split(), self._entropy.get_package_groups())
                self.pkgView.expand()

            self.show_packages()
            self._filterbar_previous_txt = txt
            return False

        gobject.timeout_add(400, go, entry, entry.get_text())

    def on_FileQuit( self, widget ):
        self.quit()

    def on_HelpAbout( self, widget = None ):
        about = AboutDialog(const.PIXMAPS_PATH+'/sulfur-about.png',
            const.CREDITS, SulfurConf.branding_title)
        about.show()

    def on_HelpTips(self, widget = None):
        win = TipsWindow(self.ui.main)
        win.show()

    def on_notebook1_switch_page(self, widget, page, page_num):
        if page_num == const.PREF_PAGES['ugc']:
            self.load_ugc_repositories()
        elif page_num == const.PREF_PAGES['colors']:
            self.load_color_settings()

    def on_ugcLoginButton_clicked(self, widget):
        if not self._ugc_status:
            return
        model, myiter = self.ugcRepositoriesView.get_selection().get_selected()
        if (myiter == None) or (model == None):
            return
        obj = model.get_value( myiter, 0 )
        if obj:
            webserv = self._get_webservice(obj['repoid'])
            if webserv is None:
                return

            def fake_callback(*args, **kwargs):
                return True

            # use input box to read login
            input_params = [
                ('username', _('Username'), fake_callback, False),
                ('password', _('Password'), fake_callback, True)
            ]
            login_data = self._entropy.input_box(
                "%s %s %s" % (
                    _('Please login against'), obj['repoid'], _('repository'),),
                input_params,
                cancel_button = True
            )
            if not login_data:
                okDialog(self.ui.main, _("Login aborted. Not logged in."))
                return

            username, password = login_data['username'], login_data['password']
            with self._privileges:
                webserv.add_credentials(username, password)
                try:
                    webserv.validate_credentials()
                except WebService.AuthenticationFailed:
                    webserv.remove_credentials()
                    okDialog(self.ui.main,
                        _("Authentication error. Not logged in."))
                    return
                except WebService.RequestError:
                    okDialog(self.window,
                        _("Communication error. Not logged in."))
                    return False
            self.load_ugc_repositories()

    def on_ugcClearLoginButton_clicked(self, widget):
        if not self._ugc_status:
            return
        model, myiter = self.ugcRepositoriesView.get_selection().get_selected()
        if (myiter == None) or (model == None):
            return
        obj = model.get_value( myiter, 0 )
        if obj:
            webserv = self._get_webservice(obj['repoid'])
            if webserv is None:
                return
            with self._privileges:
                webserv.remove_credentials()
            self.load_ugc_repositories()

    def on_ugcClearCredentialsButton_clicked(self, widget):
        if not self._ugc_status:
            return
        repo_excluded = self._settings['repositories']['excluded']
        avail_repos = self._settings['repositories']['available']
        for repoid in list(set(list(avail_repos.keys())+list(repo_excluded.keys()))):
            webserv = self._get_webservice(repoid)
            if webserv is None:
                continue
            with self._privileges:
                webserv.remove_credentials()
        self.load_ugc_repositories()
        self.set_status_ticker("%s" % (_("UGC credentials cleared"),))

    def on_noticeBoardMenuItem_activate(self, widget):
        self.show_notice_board()

    def on_pkgsetEditButton_clicked(self, widget):
        self.on_pkgsetAddButton_clicked(widget, edit = True)

    def on_pkgsetAddButton_clicked(self, widget, edit = False):

        sets = self._entropy.Sets()
        current_sets = sets.available()
        def fake_callback(s):

            ## check if package set name is sane
            #if not entropy.tools.is_valid_string(s):
            #    return False

            # does it exist?
            if not const_isunicode(s):
                s = s.decode('utf-8')
            set_match = sets.match(s)
            if set_match:
                return False

            # is the name valid after all?
            if (s not in current_sets) and (" " not in s) and \
                (not s.startswith(etpConst['packagesetprefix'])):
                return True
            return False

        def lv_callback(atom):
            c_id, c_rc = self._entropy.installed_repository().atomMatch(atom)
            if c_id != -1:
                return True
            c_id, c_rc = self._entropy.atom_match(atom)
            if c_id != -1:
                return True
            return False

        edit_title = _('Choose what Package Set you want to add')
        if edit:
            edit_title = _('Choose what Package Set you want to edit')
            # pull the set list
            objs = self.pkgView.collect_selected_items()
            obj = None
            for x in objs:
                if x.is_pkgset_cat:
                    obj = x
                    break
            if obj is None:
                return # sorry
            set_name = obj.onlyname
            set_match = sets.match(set_name)
            if not set_match: # set does not exist
                return
            repoid, set_name, set_pkgs_list = set_match
            input_params = [
                ('name', ('filled_text', (_("Package Set name"), set_name,),), fake_callback, False), 
                ('atoms', ('list', (_('Package atoms'), sorted(set_pkgs_list),),), lv_callback, False)
            ]
        else:
            input_params = [
                ('name', _("Package Set name"), fake_callback, False),
                ('atoms', ('list', (_('Package atoms'), [],),), lv_callback, False)
            ]

        data = self._entropy.input_box(
            edit_title,
            input_params,
            cancel_button = True
        )
        if data == None:
            return

        if edit:
            try:
                sets.remove(const_convert_to_unicode(data.get("name")))
            except InvalidPackageSet as err:
                okDialog(self.ui.main, "%s: %s" % (_("Error"), err.value,))
                return

        with self._privileges:
            try:
                sets.add(
                    const_convert_to_unicode(data.get("name"), enctype="utf-8"),
                        data.get("atoms"))
            except InvalidPackageSet as err:
                okDialog(self.ui.main, "%s: %s" % (_("Error"), err.value,))
                return

        self.etpbase.clear_single_group("pkgsets")
        self.show_packages()

    def on_pkgsetRemoveButton_clicked(self, widget):

        sets = self._entropy.Sets()
        def mymf(m):
            set_from, set_name, set_deps = m
            if set_from == etpConst['userpackagesetsid']:
                return set_name
            return 0
        avail_pkgsets = [x for x in map(mymf, sets.available()) if \
            x != 0]

        if not avail_pkgsets:
            okDialog(self.ui.main, _("No package sets available for removal."))
            return

        def fake_callback(s):
            return s
        input_params = [
            ('pkgset', ('combo', (_('Removable Package Set'), avail_pkgsets),),
                fake_callback, False)
        ]

        data = self._entropy.input_box(
            _('Choose what Package Set you want to remove'),
            input_params,
            cancel_button = True
        )
        if data == None:
            return
        x_id, set_name = data.get("pkgset")

        with self._privileges:
            try:
                sets.remove(const_convert_to_unicode(set_name, enctype="utf-8"))
            except InvalidPackageSet as err:
                okDialog(self.ui.main, "%s: %s" % (_("Error"), err.value,))
                return

        self.etpbase.clear_single_group("pkgsets")
        self.show_packages()

    def on_deptestButton_clicked(self, widget):
        self.dependencies_test()

    def on_libtestButton_clicked(self, widget):
        self.libraries_test()

    def on_color_reset(self, widget):
        # get parent
        parent = widget.get_parent()
        if parent == None: return
        col_button = [x for x in parent.get_children() if \
            isinstance(x, gtk.ColorButton)][0]
        setting = self.colorSettingsReverseMap.get(col_button)
        if setting == None: return
        default_color = SulfurConf.default_colors_config.get(setting)
        col_button.set_color(gtk.gdk.color_parse(default_color))
        self.on_Preferences_toggled(None, True)
        setattr(SulfurConf, setting, default_color)

    def on_ui_color_set(self, widget):
        key = self.colorSettingsReverseMap.get(widget)
        if not hasattr(SulfurConf, key):
            print_generic("WARNING: no %s in SulfurConf" % (key,))
            return
        w_col = widget.get_color().to_string()
        self.on_Preferences_toggled(None, True)
        setattr(SulfurConf, key, w_col)

    def on_notebook_switch_page(self, widget, page_w, page_num):
        page = "packages"
        for page_n, c_page in list(const.PAGES.items()):
            if c_page == page_num:
                page = page_n
                break
        return self.on_PageButton_changed(widget, page, do_set = False)

    def on_pkgSorter_changed(self, widget):
        busy_cursor(self.ui.main)
        model = widget.get_model()
        sort_id = widget.get_active()
        if sort_id == -1:
            return
        sort_id_name = self.pkg_sorters_id.get(sort_id)
        sorter = self.avail_pkg_sorters.get(sort_id_name)
        self.pkgView.change_model_injector(sorter)
        self.show_packages()
        normal_cursor(self.ui.main)
