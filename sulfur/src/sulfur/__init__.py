#!/usr/bin/python2 -O
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

# Base Python Imports
import sys, os, pty, random
import time

# Entropy Imports
if "../../libraries" not in sys.path:
    sys.path.insert(0, "../../libraries")
if "../../client" not in sys.path:
    sys.path.insert(1, "../../client")
if "/usr/lib/entropy/libraries" not in sys.path:
    sys.path.insert(2, "/usr/lib/entropy/libraries")
if "/usr/lib/entropy/client" not in sys.path:
    sys.path.insert(3, "/usr/lib/entropy/client")
if "/usr/lib/entropy/sulfur" not in sys.path:
    sys.path.insert(4, "/usr/lib/entropy/sulfur")

from entropy.exceptions import OnlineMirrorError, QueueError
import entropy.tools
from entropy.const import *
from entropy.i18n import _
from entropy.misc import TimeScheduled, ParallelTask
from entropy.cache import EntropyCacher
from entropy.output import print_generic

# Sulfur Imports
import gtk, gobject
from sulfur.packages import EntropyPackages, Queue
from sulfur.entropyapi import Equo, QueueExecutor
from sulfur.setup import SulfurConf, const, fakeoutfile, fakeinfile, \
    cleanMarkupString
from sulfur.widgets import SulfurConsole
from sulfur.core import UI, Controller
from sulfur.misc import busy_cursor, normal_cursor
from sulfur.views import *
from sulfur.filters import Filter
from sulfur.dialogs import *
from sulfur.progress import Base as BaseProgress
from sulfur.events import SulfurApplicationEventsMixin
from sulfur.event import SulfurSignals


class SulfurApplication(Controller, SulfurApplicationEventsMixin):

    def __init__(self):

        self.Equo = Equo()
        self.Cacher = EntropyCacher()

        self.do_debug = False
        locked = self.Equo.application_lock_check()
        if locked:
            okDialog( None,
                _("Entropy resources are locked and not accessible. Another Entropy application is running. Sorry, can't load Sulfur.") )
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
        ui = UI( const.GLADE_FILE, 'main', 'entropy' )
        ui.main.hide()
        # init the Controller Class to connect signals.
        Controller.__init__( self, ui )

        self.wait_window = WaitWindow(self.ui.main)

    def init(self):

        self.wait_window.show()
        self.setup_gui()
        # show UI
        if "--nomaximize" not in sys.argv:
            self.ui.main.maximize()
        self.ui.main.show()
        self.wait_window.hide()

        if entropy.tools.is_april_first():
            okDialog( self.ui.main,
                _("April 1st, w0000h0000! Gonna erase your hard disk!"))

        self.warn_repositories()
        self.packages_install()

    def quit(self, widget = None, event = None, sysexit = True ):
        if hasattr(self, 'ugcTask'):
            if self.__ugc_task != None:
                self.__ugc_task.kill()
                while self.__ugc_task.isAlive():
                    time.sleep(0.2)
        if hasattr(self, 'Equo'):
            self.Equo.destroy()

        if sysexit:
            self.exit_now()
            raise SystemExit(0)

    def exit_now(self):
        entropy.tools.kill_threads()
        self.wait_window.show()
        try:
            gtk.main_quit()
        except RuntimeError:
            pass

    def gtk_loop(self):
        while gtk.events_pending():
           gtk.main_iteration()

    def setup_gui(self):

        self.pty = pty.openpty()
        self.output = fakeoutfile(self.pty[1])
        self.input = fakeinfile(self.pty[1])
        self.do_debug = const.debug

        if not self.do_debug:
            sys.stdout = self.output
            sys.stderr = self.output
            sys.stdin = self.input

        # load "loading" pix
        self._loading_pix_small = gtk.image_new_from_file(const.loading_pix_small)

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
        # Left Side Toolbar
        self._notebook_tabs_cache = {}
        self.firstButton = None  # first button
        self.activePage = 'repos'
        self.pageBootstrap = True
        # Progress bars
        self.progress = BaseProgress(self.ui, self.switch_notebook_page, self)
        # Package Radiobuttons
        self.packageRB = {}
        self.lastPkgPB = 'updates'

        # color settings mapping dictionary
        self.colorSettingsMap = {
            "color_console_font": self.ui.color_console_font_picker,
            "color_normal": self.ui.color_normal_picker,
            "color_update": self.ui.color_update_picker,
            "color_install": self.ui.color_install_picker,
            "color_install": self.ui.color_install_picker,
            "color_remove": self.ui.color_remove_picker,
            "color_reinstall": self.ui.color_reinstall_picker,
            "color_downgrade": self.ui.color_downgrade_picker,
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
            self.ui.color_downgrade_picker: "color_downgrade",
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
        self.console_menu_xml = gtk.glade.XML( const.GLADE_FILE, "terminalMenu",
            domain="entropy" )
        self.console_menu = self.console_menu_xml.get_widget( "terminalMenu" )
        self.console_menu_xml.signal_autoconnect(self)

        self.ui.main.set_title( "%s %s %s" % (SulfurConf.branding_title,
            const.__sulfur_version__, self.safe_mode_txt) )
        self.ui.main.connect( "delete_event", self.quit )

        #self.ui.notebook.set_show_tabs( False )

        self.ui.main.present()
        self.setup_page_buttons()        # Setup left side toolbar
        self.switch_notebook_page(self.activePage)

        # put self.console in place
        self.console = SulfurConsole()
        # this is a workaround for buggy vte.Terminal when using
        # file descriptors. This will make fakeoutfile to use
        # our external writer instead of using os.write
        self.output.external_writer = self.progress_log_write

        self.console.set_scrollback_lines(1024)
        self.console.set_scroll_on_output(True)
        self.console.connect("button-press-event", self.on_console_click)
        termScroll = gtk.VScrollbar(self.console.get_adjustment())
        self.ui.vteBox.pack_start(self.console, True, True)
        self.ui.termScrollBox.pack_start(termScroll, False)
        self.ui.termHBox.show_all()
        self.setup_packages_filter()
        self.setup_advisories_filter()

        self.setup_images()
        self.setup_labels()

        # init flags
        self.disable_ugc = False

        self.__ugc_task = None
        self._spawning_ugc = False
        self._preferences = None
        self.skipMirrorNow = False
        self.abortQueueNow = False
        self.doProgress = False
        self._is_working = False
        self.lastPkgPB = "updates"
        self.Equo.connect_to_gui(self)
        self.setup_editor()

        self.switch_notebook_page("packages")

        # setup Repositories
        self.setup_repoView()
        self.firstTime = True
        # setup app
        self.setup_application()

        self.console.set_pty(self.pty[0])
        self.reset_progress_text()
        self.pkgProperties_selected = None
        self.setup_pkg_sorter()
        self.setup_user_generated_content()

        simple_mode = 1
        if "--advanced" in sys.argv:
            simple_mode = 0
        elif not SulfurConf.simple_mode:
            simple_mode = 0
        self.in_mode_loading = True
        self.switch_application_mode(simple_mode)
        self.in_mode_loading = False

        # hide progress Tab by default
        self.ui.progressVBox.hide()

        self.setup_preferences()
        self.setup_events_handling()

    def setup_events_handling(self):

        def hide_queue(event):
            self.ui.rbPkgQueued.hide()

        def show_queue(event):
            self.ui.rbPkgQueued.show()

        def queue_changed(event, length):
            if not length and self.lastPkgPB == "queued":
                self.set_package_radio("updates")

        # setup queued/installation button events
        SulfurSignals.connect("install_queue_empty", hide_queue)
        SulfurSignals.connect("install_queue_filled", show_queue)
        SulfurSignals.connect("install_queue_changed", queue_changed)

    def switch_application_mode(self, do_simple):
        self.ui.UGCMessageLabel.hide()
        if do_simple:
            self.switch_simple_mode()
            self.ui.advancedMode.set_active(0)
        else:
            self.switch_advanced_mode()
            self.ui.advancedMode.set_active(1)
        SulfurConf.simple_mode = do_simple
        SulfurConf.save()

    def switch_simple_mode(self):
        self.ui.servicesMenuItem.hide()
        self.ui.repoRefreshButton.show()
        self.ui.vseparator1.hide()
        self.ui.pkgSorter.hide()
        self.ui.updateButtonView.hide()
        self.ui.rbAvailable.hide()
        self.ui.rbInstalled.hide()
        self.ui.rbMasked.hide()
        self.ui.rbPkgSets.hide()

        self.ui.securityVbox.hide()
        self.ui.prefsVbox.hide()
        self.ui.reposVbox.hide()

    def switch_advanced_mode(self):
        self.ui.servicesMenuItem.show()
        self.ui.repoRefreshButton.hide()
        self.ui.vseparator1.show()
        self.ui.pkgSorter.show()
        self.ui.updateButtonView.show()
        self.ui.rbAvailable.show()
        self.ui.rbInstalled.show()
        self.ui.rbMasked.show()
        self.ui.rbPkgSets.show()

        self.ui.securityVbox.show()
        self.ui.prefsVbox.show()
        self.ui.reposVbox.show()

    def setup_pkg_sorter(self):

        self.avail_pkg_sorters = {
            'default': DefaultPackageViewModelInjector,
            'name_az': NameSortPackageViewModelInjector,
            'name_za': NameRevSortPackageViewModelInjector,
            'downloads': DownloadSortPackageViewModelInjector,
            'votes': VoteSortPackageViewModelInjector,
            'repository': RepoSortPackageViewModelInjector,
            'date': DateSortPackageViewModelInjector,
            'date_grouped': DateGroupedSortPackageViewModelInjector,
            'license': LicenseSortPackageViewModelInjector,
            'groups': GroupSortPackageViewModelInjector,
        }
        self.pkg_sorters_desc = {
            'default': _("Default packages sorting"),
            'name_az': _("Sort by name [A-Z]"),
            'name_za': _("Sort by name [Z-A]"),
            'downloads': _("Sort by downloads"),
            'votes': _("Sort by votes"),
            'repository': _("Sort by repository"),
            'date': _("Sort by date (simple)"),
            'date_grouped': _("Sort by date (grouped)"),
            'license': _("Sort by license (grouped)"),
            'groups': _("Sort by Groups"),
        }
        self.pkg_sorters_id = {
            0: 'default',
            1: 'name_az',
            2: 'name_za',
            3: 'downloads',
            4: 'votes',
            5: 'repository',
            6: 'date',
            7: 'date_grouped',
            8: 'license',
            9: 'groups',
        }
        self.pkg_sorters_id_inverse = dict((y, x,) for x, y in \
            list(self.pkg_sorters_id.items()))

        self.pkg_sorters_img_ids = {
            0: gtk.STOCK_PRINT_PREVIEW,
            1: gtk.STOCK_SORT_DESCENDING,
            2: gtk.STOCK_SORT_ASCENDING,
            3: gtk.STOCK_GOTO_BOTTOM,
            4: gtk.STOCK_INFO,
            5: gtk.STOCK_CONNECT,
            6: gtk.STOCK_MEDIA_PLAY,
            7: gtk.STOCK_MEDIA_PLAY,
            8: gtk.STOCK_EDIT,
            9: gtk.STOCK_CDROM,
        }

        # setup package sorter
        sorter_model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        sorter = self.ui.pkgSorter
        sorter.set_model(sorter_model)

        sorter_img_cell = gtk.CellRendererPixbuf()
        sorter.pack_start(sorter_img_cell, False)
        sorter.add_attribute(sorter_img_cell, 'stock-id', 0)

        sorter_cell = gtk.CellRendererText()
        sorter.pack_start(sorter_cell, False)
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

        packages_install = os.environ.get("SULFUR_PACKAGES", '').split(";")
        atoms_install = []
        do_fetch = False
        if "--fetch" in sys.argv:
            do_fetch = True
            sys.argv.remove("--fetch")

        if "--install" in sys.argv:
            atoms_install.extend(sys.argv[sys.argv.index("--install")+1:])

        packages_install = [x for x in packages_install if \
            os.access(x, os.R_OK) and os.path.isfile(x)]

        for arg in sys.argv:
            if arg.endswith(etpConst['packagesext']) and \
                os.access(arg, os.R_OK) and os.path.isfile(arg):

                arg = os.path.realpath(arg)
                packages_install.append(arg)

        if packages_install:

            fn = packages_install[0]
            self.on_installPackageItem_activate(None, fn)

        elif atoms_install: # --install <atom1> <atom2> ... support

            rc = self.add_atoms_to_queue(atoms_install)
            if not rc:
                return
            self.switch_notebook_page('output')

            try:
                rc = self.process_queue(self.queue.packages,
                    fetch_only = do_fetch)
            except SystemExit:
                raise
            except:
                if self.do_debug:
                    entropy.tools.print_traceback()
                    import pdb; pdb.set_trace()
                else:
                    raise

            self.reset_queue_progress_bars()
            if rc:
                self.queue.clear()
                self.queueView.refresh()

        elif "--nonoticeboard" not in sys.argv:
            if not self.Equo.are_noticeboards_marked_as_read():
                self.show_notice_board(force = False)

    def setup_advisories_filter(self):
        widgets = [
                    (self.ui.rbAdvisories, 'affected'),
                    (self.ui.rbAdvisoriesApplied, 'applied'),
                    (self.ui.rbAdvisoriesAll, 'all')
        ]
        for w, tag in widgets:
            w.connect('toggled', self.populate_advisories, tag)
            w.set_mode(False)

    def setup_packages_filter(self):

        self.setup_package_radio_buttons(self.ui.rbUpdates, "updates")
        self.setup_package_radio_buttons(self.ui.rbAvailable, "available")
        self.setup_package_radio_buttons(self.ui.rbInstalled, "installed")
        self.setup_package_radio_buttons(self.ui.rbMasked, "masked")
        self.setup_package_radio_buttons(self.ui.rbAll, "all")
        self.setup_package_radio_buttons(self.ui.rbPkgSets, "pkgsets")
        self.setup_package_radio_buttons(self.ui.rbPkgQueued, "queued")

    def setup_package_radio_buttons(self, widget, tag):
        widget.connect('toggled', self.on_pkgFilter_toggled, tag)

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

        self.packageRB[tag] = widget

    def setup_page_buttons(self):

        # Setup Vertical Toolbar
        self.create_sidebar_button(self.ui.sideRadioPkgImage,
            "button-packages.png", 'packages')

        self.create_sidebar_button(self.ui.sideRadioSecurityImage,
            "button-glsa.png", 'glsa' )

        self.create_sidebar_button(self.ui.sideRadioReposImage,
            "button-repo.png", 'repos' )

        self.create_sidebar_button(self.ui.sideRadioSystemImage,
            "button-conf.png", 'filesconf' )

        self.create_sidebar_button(self.ui.sideRadioPrefsImage,
            "preferences.png", 'preferences' )

        self.create_sidebar_button(self.ui.sideRadioQueueImage,
            "button-queue.png", 'queue' )

        self.create_sidebar_button(self.ui.sideRadioInstallImage,
            "button-output.png", 'output' )

    def create_sidebar_button( self, image, icon, page):

        iconpath = os.path.join(const.PIXMAPS_PATH, icon)
        pix = None
        if os.path.isfile(iconpath) and os.access(iconpath, os.R_OK):
            try:
                p = gtk.gdk.pixbuf_new_from_file(iconpath)
                image.set_from_pixbuf(p)
                image.show()
            except gobject.GError:
                pass

        page_widget = self.ui.notebook.get_nth_page(const.PAGES[page])
        self._notebook_tabs_cache[page] = page_widget

    def setup_images(self):
        """ setup misc application images """

        # progressImage
        iconpath = os.path.join(const.PIXMAPS_PATH, "sabayon.png")
        if os.path.isfile(iconpath) and os.access(iconpath, os.R_OK):
            try:
                p = gtk.gdk.pixbuf_new_from_file( iconpath )
                self.ui.progressImage.set_from_pixbuf(p)
            except gobject.GError:
                pass

    def setup_labels(self):
        """ setup misc application labels """

        mytxt = "<span size='x-large' foreground='#8A381B'>%s</span>" % (
            _("Preferences"),)
        self.ui.preferencesTitleLabel.set_markup(mytxt)
        mytxt = "<span foreground='#084670'>%s</span>" % (
            _("Some configuration options are critical for the health of your System. Be careful."),)
        self.ui.preferencesLabel.set_markup(mytxt)

    def setup_user_generated_content(self):

        self.__ugc_task = TimeScheduled(30, self.spawn_user_generated_content)
        self.__ugc_task.set_delay_before(True)
        if "--nougc" not in sys.argv:
            self.__ugc_task.start()

    def spawn_user_generated_content(self):
        self.__ugc_task.set_delay(300)
        if self.do_debug:
            print_generic("entering UGC")
        try:
            self.ugc_update()
            self.Cacher.sync(wait = True)
        except (SystemExit,):
            raise
        except:
            pass
        if self.do_debug:
            print_generic("quitting UGC")

    def ugc_update(self):

        if self._spawning_ugc or self._is_working or self.disable_ugc:
            return

        self._is_working = True
        self._spawning_ugc = True
        if self.do_debug: print_generic("are we connected?")
        connected = entropy.tools.get_remote_data(etpConst['conntestlink'])
        if self.do_debug:
            cr = False
            if connected: cr = True
            print_generic("conn result", cr)
        if (isinstance(connected, bool) and (not connected)) or \
            (self.Equo.UGC == None):
            self._is_working = False
            self._spawning_ugc = False
            return

        for repo in self.Equo.validRepositories:
            if self.do_debug:
                t1 = time.time()
                print_generic("working UGC update for", repo)
            self.Equo.update_ugc_cache(repo)
            if self.do_debug:
                t2 = time.time()
                td = t2 - t1
                print_generic("completed UGC update for", repo, "took", td)

        # emit ugc update signal
        SulfurSignals.emit('ugc_data_update')

        self._is_working = False
        self._spawning_ugc = False

    def fill_pref_db_backup_page(self):
        self.dbBackupStore.clear()
        backed_up_dbs = self.Equo.list_backedup_client_databases()
        for mypath in backed_up_dbs:
            mymtime = entropy.tools.get_file_unix_mtime(mypath)
            mytime = entropy.tools.convert_unix_time_to_human_time(mymtime)
            self.dbBackupStore.append(
                (mypath, os.path.basename(mypath), mytime,) )

    def setup_preferences(self):

        # config protect
        self.configProtectView = self.ui.configProtectView
        for mycol in self.configProtectView.get_columns():
            self.configProtectView.remove_column(mycol)
        self.configProtectModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Item" ), cell, markup = 0 )
        self.configProtectView.append_column( column )
        self.configProtectView.set_model( self.configProtectModel )

        # config protect mask
        self.configProtectMaskView = self.ui.configProtectMaskView
        for mycol in self.configProtectMaskView.get_columns():
            self.configProtectMaskView.remove_column(mycol)
        self.configProtectMaskModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Item" ), cell, markup = 0 )
        self.configProtectMaskView.append_column( column )
        self.configProtectMaskView.set_model( self.configProtectMaskModel )

        # config protect skip
        self.configProtectSkipView = self.ui.configProtectSkipView
        for mycol in self.configProtectSkipView.get_columns():
            self.configProtectSkipView.remove_column(mycol)
        self.configProtectSkipModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Item" ), cell, markup = 0 )
        self.configProtectSkipView.append_column( column )
        self.configProtectSkipView.set_model( self.configProtectSkipModel )

        # database backup tool
        self.dbBackupView = self.ui.dbBackupView
        self.dbBackupStore = gtk.ListStore( gobject.TYPE_STRING,
            gobject.TYPE_STRING, gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Database" ), cell, markup = 1 )
        self.dbBackupView.append_column( column )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Date" ), cell, markup = 2 )
        self.dbBackupView.append_column( column )
        self.dbBackupView.set_model( self.dbBackupStore )
        self.fill_pref_db_backup_page()

        # UGC repositories

        def get_ugc_repo_text( column, cell, model, myiter ):
            obj = model.get_value( myiter, 0 )
            if obj:
                t = "[<b>%s</b>] %s" % (obj['repoid'], obj['description'],)
                cell.set_property('markup', t)

        def get_ugc_logged_text( column, cell, model, myiter ):
            obj = model.get_value( myiter, 0 )
            if obj:
                t = "<i>%s</i>" % (_("Not logged in"),)
                if self.Equo.UGC != None:
                    logged_data = self.Equo.UGC.read_login(obj['repoid'])
                    if logged_data != None:
                        t = "<i>%s</i>" % (logged_data[0],)
                cell.set_property('markup', t)

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
        def fill_setting_view(model, view, data):
            model.clear()
            view.set_model(model)
            view.set_property('headers-visible', False)
            for item in data:
                model.append([item])
            view.expand_all()

        def fill_setting(name, mytype, wgwrite, data):
            if not isinstance(data, mytype):
                if data == None: # empty parameter
                    return
                errorMessage(
                    self.ui.main,
                    cleanMarkupString("%s: %s") % (_("Error setting parameter"),
                        name,),
                    _("An issue occured while loading a preference"),
                    "%s %s %s: %s, %s: %s" % (_("Parameter"), name,
                        _("must be of type"), mytype, _("got"), type(data),),
                )
                return
            wgwrite(data)

        def save_setting_view(config_file, name, setting, mytype, model, view):

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
            if (not isinstance(data, mytype)) and (data != None):
                errorMessage(
                    self.ui.main,
                    cleanMarkupString("%s: %s") % (_("Error setting parameter"),
                        name,),
                    _("An issue occured while saving a preference"),
                    "%s %s %s: %s, %s: %s" % (_("Parameter"), name,
                        _("must be of type"), mytype, _("got"), type(data),),
                )
                return False

            if isinstance(data, int):
                writedata = str(data)
            elif isinstance(data, list):
                writedata = ' '.join(data)
            elif isinstance(data, bool):
                writedata = "disable"
                if data: writedata = "enable"
            elif isinstance(data, const_get_stringtype()):
                writedata = data
            return save_parameter(config_file, name, writedata)

        def save_parameter(config_file, name, data):
            return entropy.tools.write_parameter_to_file(config_file, name, data)

        sys_settings_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        self._preferences = {
            etpConst['entropyconf']: [
                (
                    'ftp-proxy',
                    self.Equo.SystemSettings['system']['proxy']['ftp'],
                    const_get_stringtype(),
                    fill_setting,
                    saveSetting,
                    self.ui.ftpProxyEntry.set_text,
                    self.ui.ftpProxyEntry.get_text,
                ),
                (
                    'http-proxy',
                    self.Equo.SystemSettings['system']['proxy']['http'],
                    const_get_stringtype(),
                    fill_setting,
                    saveSetting,
                    self.ui.httpProxyEntry.set_text,
                    self.ui.httpProxyEntry.get_text,
                ),
                (
                    'proxy-username',
                    self.Equo.SystemSettings['system']['proxy']['username'],
                    const_get_stringtype(),
                    fill_setting,
                    saveSetting,
                    self.ui.usernameProxyEntry.set_text,
                    self.ui.usernameProxyEntry.get_text,
                ),
                (
                    'proxy-password',
                    self.Equo.SystemSettings['system']['proxy']['password'],
                    const_get_stringtype(),
                    fill_setting,
                    saveSetting,
                    self.ui.passwordProxyEntry.set_text,
                    self.ui.passwordProxyEntry.get_text,
                ),
                (
                    'nice-level',
                    etpConst['current_nice'],
                    int,
                    fill_setting,
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
                    fill_setting,
                    saveSetting,
                    self.ui.collisionProtectionCombo.set_active,
                    self.ui.collisionProtectionCombo.get_active,
                ),
                (
                    'configprotect',
                    self.Equo.SystemSettings[sys_settings_plg_id]['misc']['configprotect'],
                    list,
                    fill_setting_view,
                    save_setting_view,
                    self.configProtectModel,
                    self.configProtectView,
                ),
                (
                    'configprotectmask',
                    self.Equo.SystemSettings[sys_settings_plg_id]['misc']['configprotectmask'],
                    list,
                    fill_setting_view,
                    save_setting_view,
                    self.configProtectMaskModel,
                    self.configProtectMaskView,
                ),
                (
                    'configprotectskip',
                    self.Equo.SystemSettings[sys_settings_plg_id]['misc']['configprotectskip'],
                    list,
                    fill_setting_view,
                    save_setting_view,
                    self.configProtectSkipModel,
                    self.configProtectSkipView,
                ),
                (
                    'filesbackup',
                    self.Equo.SystemSettings[sys_settings_plg_id]['misc']['filesbackup'],
                    bool,
                    fill_setting,
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
                    fill_setting,
                    saveSetting,
                    self.ui.speedLimitSpin.set_value,
                    self.ui.speedLimitSpin.get_value_as_int,
                )
            ],
        }

        # load data
        for config_file in self._preferences:
            for name, setting, mytype, fillfunc, savefunc, wgwrite, wgread in \
                self._preferences[config_file]:

                if mytype == list:
                    fillfunc(wgwrite, wgread, setting)
                else:
                    fillfunc(name, mytype, wgwrite, setting)

        rc, e = SulfurConf.save()
        if not rc:
            okDialog( self.ui.main, "%s: %s" % (_("Error saving preferences"), e) )
        self.on_Preferences_toggled(None, False)

    def setup_masked_pkgs_warning_box(self):
        mytxt = "<b><big><span foreground='#FF0000'>%s</span></big></b>\n%s" % (
            _("Attention"),
            _("These packages are masked either by default or due to your choice. Please be careful, at least."),
        )
        self.ui.maskedWarningLabel.set_markup(mytxt)

    def setup_editor(self):

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

        self._file_editor = '/usr/bin/xterm -e $EDITOR'
        de_session = os.getenv('DESKTOP_SESSION')
        if de_session == None: de_session = ''
        path = os.getenv('PATH').split(":")
        if os.access("/usr/bin/xdg-open", os.X_OK):
            self._file_editor = "/usr/bin/xdg-open"
        if de_session.find("kde") != -1:
            for item in path:
                itempath = os.path.join(item, 'kwrite')
                itempath2 = os.path.join(item, 'kedit')
                itempath3 = os.path.join(item, 'kate')
                if os.access(itempath, os.X_OK):
                    self._file_editor = itempath
                    break
                elif os.access(itempath2, os.X_OK):
                    self._file_editor = itempath2
                    break
                elif os.access(itempath3, os.X_OK):
                    self._file_editor = itempath3
                    break
        else:
            if os.access('/usr/bin/gedit', os.X_OK):
                self._file_editor = '/usr/bin/gedit'

    def start_working(self, do_busy = True):
        self._is_working = True
        if do_busy:
            busy_cursor(self.ui.main)
        self.ui.progressVBox.grab_add()

    def end_working(self):
        self._is_working = False
        self.ui.progressVBox.grab_remove()
        normal_cursor(self.ui.main)

    def setup_application(self):
        msg = _('Generating metadata. Please wait.')
        self.set_status_ticker(msg)
        count = 30
        while count:
            try:
                self.show_packages()
            except self.Equo.dbapi2.ProgrammingError as e:
                self.set_status_ticker("%s: %s, %s" % (
                        _("Error during list population"),
                        e,
                        _("Retrying in 1 second."),
                    )
                )
                time.sleep(1)
                count -= 1
                continue
            break

    def clean_entropy_caches(self, alone = False):
        if alone:
            self.progress.total.hide()
        self.Equo.generate_cache(depcache = True, configcache = False)
        # clear views
        self.etpbase.clear_groups()
        self.etpbase.clear_cache()
        self.setup_application()
        if alone:
            self.progress.total.show()

    def populate_advisories(self, widget, show):

        if widget is not None:
            if not widget.get_active():
                return
            widget.grab_add()

        meta_id = "glsa_metadata"
        meta_cached = self.etpbase.is_cached(meta_id)

        if not meta_cached:
            self.set_busy()
            self.wait_window.show()

        try:
            cached = self.etpbase.get_groups(meta_id)
        except Exception as e:
            okDialog( self.ui.main, "%s: %s" % (
                _("Error loading advisories"), e) )
            cached = {}

        if cached:
            self.advisoriesView.populate(self.Equo.Security(), cached, show,
                use_cache = meta_cached)

        if not meta_cached:
            self.unset_busy()
            self.wait_window.hide()

        if widget is not None:
            widget.grab_remove()

    def populate_files_update(self):
        # load filesUpdate interface and fill self.filesView
        cached = None
        try:
            cached = self.Equo.FileUpdates.load_cache()
        except CacheCorruptionError:
            pass
        if cached == None:
            self.set_busy()
            cached = self.Equo.FileUpdates.scanfs(quiet = True)
            self.unset_busy()
        if cached:
            self.filesView.populate(cached)

    def show_notice_board(self, force = True):
        repoids = {}
        for repoid in self.Equo.validRepositories:
            if self.Equo.is_noticeboard_marked_as_read(repoid) and not force:
                continue
            avail_repos = self.Equo.SystemSettings['repositories']['available']
            board_file = avail_repos[repoid]['local_notice_board']
            if not (os.path.isfile(board_file) and \
                os.access(board_file, os.R_OK)):
                continue
            if entropy.tools.get_file_size(board_file) < 10:
                continue
            repoids[repoid] = board_file
        if repoids:
            self.load_notice_board(repoids)

    def load_notice_board(self, repoids):
        my = NoticeBoardWindow(self.ui.main, self.Equo)
        my.load(repoids)

    def update_repositories(self, repos):

        self.disable_ugc = True
        self.hide_notebook_tabs_for_install()
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
            self.progress_log(_('You must run this application as root'),
                extra = "repositories")
            self.disable_ugc = False
            self.show_notebook_tabs_after_install()
            return 1
        except MissingParameter:
            msg = "%s: %s" % (_('No repositories specified in'),
                etpConst['repositoriesconf'],)
            self.progress_log( msg, extra = "repositories")
            self.disable_ugc = False
            self.show_notebook_tabs_after_install()
            return 127
        except OnlineMirrorError:
            self.progress_log(
                _('You are not connected to the Internet. You should.'),
                extra = "repositories")
            self.disable_ugc = False
            self.show_notebook_tabs_after_install()
            return 126
        except Exception as e:
            msg = "%s: %s" % (_('Unhandled exception'), e,)
            self.progress_log(msg, extra = "repositories")
            self.disable_ugc = False
            self.show_notebook_tabs_after_install()
            return 2

        self.__repo_update_rc = -1000
        def run_up():
            self.__repo_update_rc = repoConn.sync()

        t = ParallelTask(run_up)
        t.start()
        while t.isAlive():
            time.sleep(0.2)
            if self.do_debug:
                print_generic("update_repositories: update thread still alive")
            self.gtk_loop()
        rc = self.__repo_update_rc

        if repoConn.syncErrors or (rc != 0):
            self.progress.set_mainLabel(_('Errors updating repositories.'))
            self.progress.set_subLabel(
                _('Please check logs below for more info'))
        else:
            if repoConn.alreadyUpdated == 0:
                self.progress.set_mainLabel(
                    _('Repositories updated successfully'))
            else:
                if len(repos) == repoConn.alreadyUpdated:
                    self.progress.set_mainLabel(
                        _('All the repositories were already up to date.'))
                else:
                    msg = "%s %s" % (repoConn.alreadyUpdated,
                        _("repositories were already up to date. Others have been updated."),)
                    self.progress.set_mainLabel(msg)
            if repoConn.newEquo:
                self.progress.set_extraLabel(
                    _('sys-apps/entropy needs to be updated as soon as possible.'))

        self.set_package_radio('updates')
        initconfig_entropy_constants(etpSys['rootdir'])

        self.disable_ugc = False
        self.show_notebook_tabs_after_install()
        return not repoConn.syncErrors

    def reset_progress_text(self):
        self.progress.set_mainLabel(_('Nothing to do. I am idle.'))
        self.progress.set_subLabel(
            _('Really, don\'t waste your time here. This is just a placeholder'))
        self.progress.set_extraLabel(_('I am still alive and kickin\''))
        self.hide_progress_bars()

    def hide_progress_bars(self):
        self.progress.total.hide()
        self.ui.progressBar.hide()
        #self.progress.hide()

    def show_progress_bars(self):
        self.progress.total.show()
        self.ui.progressBar.show()
        #self.progress.show()

    def reset_queue_progress_bars(self):
        self.progress.reset_progress()
        self.progress.total.clear()

    def setup_repoView(self):
        self.repoView.populate()

    def set_busy(self):
        self.isBusy = True
        busy_cursor(self.ui.main)

    def unset_busy(self):
        self.isBusy = False
        normal_cursor(self.ui.main)

    def set_package_radio( self, tag ):
        self.lastPkgPB = tag
        widget = self.packageRB[tag]
        widget.set_active( True )

    def set_notebook_page(self, page):
        ''' Switch to Page in GUI'''
        self.ui.notebook.set_current_page(page)

    def set_status_ticker( self, text ):
        ''' Write Message to Statusbar'''
        context_id = self.ui.status.get_context_id( "Status" )
        self.ui.status.push( context_id, text )

    def progress_log(self, msg, extra = None):
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
                self.console.feed_child("%s: %s\n\r" % (extra, txt,))
                continue
            self.console.feed_child("%s\n\r" % (txt,))

    def progress_log_write(self, msg):
        self.console.feed_child(msg + "\n\r")

    def enable_skip_mirror(self):
        self.ui.skipMirror.show()
        self.skipMirror = True

    def disable_skip_mirror(self):
        self.ui.skipMirror.hide()
        self.skipMirror = False

    def show_packages(self, back_to_page = None):

        self.ui_lock(True)
        action = self.lastPkgPB
        if action == 'all':
            masks = ['installed', 'available', 'masked', 'updates']
        else:
            masks = [action]

        self.disable_ugc = True
        self.set_busy()
        bootstrap = False
        if (self.Equo.get_world_update_cache(empty_deps = False) == None):
            if self.do_debug:
                print_generic("show_packages: bootstrap True due to empty world cache")
            bootstrap = True
            self.switch_notebook_page('output')
        elif (self.Equo.get_available_packages_cache() == None) and \
            (('available' in masks) or ('updates' in masks)):
            if self.do_debug:
                print_generic("show_packages: bootstrap True due to empty avail cache")
            bootstrap = True
            self.switch_notebook_page('output')
        self.progress.total.hide()

        if bootstrap:
            if self.do_debug:
                print_generic("show_packages: bootstrap is enabled, clearing ALL cache")
            self.etpbase.clear_cache()
            self.start_working()

        allpkgs = []
        if self.doProgress: next(self.progress.total) # -> Get lists
        self.progress.set_mainLabel(_('Generating Metadata, please wait.'))
        self.progress.set_subLabel(
            _('Entropy is indexing the repositories. It will take a few seconds'))
        self.progress.set_extraLabel(
            _('While you are waiting, take a break and look outside. Is it rainy?'))
        for flt in masks:
            msg = "%s: %s" % (_('Calculating'), flt,)
            self.set_status_ticker(msg)
            allpkgs += self.etpbase.get_groups(flt)
        if self.doProgress: next(self.progress.total) # -> Sort Lists

        if action == "updates":
            msg = "%s: available" % (_('Calculating'),)
            self.set_status_ticker(msg)
            self.etpbase.get_groups("available")

        if bootstrap:
            self.end_working()

        empty = False
        if not allpkgs and action == "updates":
            allpkgs = self.etpbase.get_groups('fake_updates')
            empty = True

        #if bootstrap: time.sleep(1)
        self.set_status_ticker("%s: %s %s" % (_("Showing"), len(allpkgs), _("items"),))

        show_pkgsets = False
        if action == "pkgsets":
            show_pkgsets = True

        self.pkgView.populate(allpkgs, empty = empty, pkgsets = show_pkgsets)
        self.progress.total.show()

        if self.doProgress: self.progress.hide() #Hide Progress
        if back_to_page:
            self.switch_notebook_page(back_to_page)
        elif bootstrap:
            self.switch_notebook_page('packages')

        self.unset_busy()
        self.ui_lock(False)
        # reset labels
        self.reset_progress_text()
        self.reset_queue_progress_bars()
        self.disable_ugc = False

    def add_atoms_to_queue(self, atoms, always_ask = False, matches = set()):

        self.wait_window.show()
        self.set_busy()
        if not matches:
            # resolve atoms ?
            for atom in atoms:
                match = self.Equo.atom_match(atom)
                if match[0] != -1:
                    matches.add(match)
        if not matches:
            self.wait_window.hide()
            okDialog( self.ui.main,
                _("No packages need or can be queued at the moment.") )
            self.unset_busy()
            return

        resolved = []

        self.etpbase.get_groups('installed')
        self.etpbase.get_groups('available')
        self.etpbase.get_groups('reinstallable')
        self.etpbase.get_groups('updates')
        self.etpbase.get_groups("downgrade")

        for match in matches:
            resolved.append(self.etpbase.get_package_item(match)[0])

        rc = True

        found_objs = []
        master_queue = []
        for key in self.queue.packages:
            master_queue += self.queue.packages[key]
        for obj in resolved:
            if obj in master_queue:
                continue
            found_objs.append(obj)


        q_cache = {}
        for obj in found_objs:
            q_cache[obj.matched_atom] = obj.queued
            obj.queued = "u"

        status, myaction = self.queue.add(found_objs, always_ask = always_ask)
        if status != 0:
            rc = False
            for obj in found_objs:
                obj.queued = q_cache.get(obj.matched_atom)

        self.queueView.refresh()
        self.ui.viewPkg.queue_draw()

        self.wait_window.hide()
        self.unset_busy()
        return rc

    def reset_cache_status(self):
        self.pkgView.clear()
        self.etpbase.clear_groups()
        self.etpbase.clear_cache()
        self.queue.clear()
        self.queueView.refresh()
        # re-scan system settings, useful
        # if there are packages that have been
        # live masked, and anyway, better wasting
        # 2-3 more cycles than having unattended
        # behaviours
        self.Equo.SystemSettings.clear()
        self.Equo.close_all_repositories()

    def hide_notebook_tabs_for_install(self):
        self.ui.securityVbox.hide()
        self.ui.prefsVbox.hide()
        self.ui.reposVbox.hide()
        self.ui.queueVbox.hide()
        self.ui.systemVbox.hide()
        self.ui.packagesVbox.hide()
        self.ui.progressVBox.show()

    def show_notebook_tabs_after_install(self):
        self.ui.queueVbox.show()
        self.ui.systemVbox.show()
        self.ui.packagesVbox.show()
        self.switch_application_mode(SulfurConf.simple_mode)

    def check_restart_needed(self, to_be_installed_matches):

        entropy_pkg = "sys-apps/entropy"

        etp_matches, etp_rc = self.Equo.atom_match(entropy_pkg,
            multiMatch = True, multiRepo = True)
        if etp_rc != 0:
            return False

        found_match = None
        for etp_match in etp_matches:
            if etp_match in to_be_installed_matches:
                found_match = etp_match
                break

        if not found_match:
            return False
        rc, pkg_match = self.Equo.check_package_update(entropy_pkg, deep = True)
        if rc:
            return True
        return False

    def critical_updates_warning(self):
        sys_set_client_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        misc_set = self.Equo.SystemSettings[sys_set_client_plg_id]['misc']
        if misc_set.get('forcedupdates'):
            crit_atoms, crit_mtchs = self.Equo.calculate_critical_updates()
            if crit_atoms:
                crit_objs = []
                for crit_match in crit_mtchs:
                    crit_obj, c_new = self.etpbase.get_package_item(
                        crit_match)
                    if crit_obj:
                        crit_objs.append(crit_obj)

                crit_dialog = ConfirmationDialog(
                    self.ui.main,
                    crit_objs,
                    top_text = _("Please update the following critical packages"),
                    bottom_text = _("You should install them as soon as possible"),
                    simpleList = True
                )
                crit_dialog.okbutton.set_label(_("Abort action"))
                crit_dialog.cancelbutton.set_label(_("Ignore"))
                result = crit_dialog.run()
                crit_dialog.destroy()
                if result == -5: # ok
                    return True
        return False

    def process_queue(self, pkgs, remove_repos = None, fetch_only = False,
            download_sources = False):

        if remove_repos is None:
            remove_repos = []

        self.show_progress_bars()

        # preventive check against other instances
        locked = self.Equo.application_lock_check()
        if locked or not entropy.tools.is_root():
            okDialog(self.ui.main,
                _("Another Entropy instance is running. Cannot process queue."))
            self.progress.reset_progress()
            self.switch_notebook_page('packages')
            return False

        self.disable_ugc = True
        # acquire Entropy resources here to avoid surpises afterwards
        acquired = self.Equo.resources_create_lock()
        if not acquired:
            okDialog(self.ui.main,
                _("Another Entropy instance is locking this task at the moment. Try in a few minutes."))
            self.disable_ugc = False
            return False

        switch_back_page = None
        self.hide_notebook_tabs_for_install()
        self.set_status_ticker(_("Running tasks"))
        total = 0
        for key in pkgs:
            total += len(pkgs[key])
        state = True
        if total > 0:

            self.start_working(do_busy = True)
            normal_cursor(self.ui.main)
            self.progress.show()
            self.progress.set_mainLabel( _( "Processing Packages in queue" ) )
            self.switch_notebook_page('output')
            queue = []
            for key in pkgs:
                if key == "r":
                    continue
                queue += pkgs[key]
            install_queue = [x.matched_atom for x in queue]
            selected_by_user = set([x.matched_atom for x in queue if \
                x.selected_by_user])
            removal_queue = [x.matched_atom[0] for x in pkgs['r']]
            do_purge_cache = set([x.matched_atom[0] for x in pkgs['r'] if \
                x.do_purge])

            # look for critical updates
            crit_block = False
            if install_queue and ((not fetch_only) and (not download_sources)):
                crit_block = self.critical_updates_warning()
            # check if we also need to restart this application
            restart_needed = self.check_restart_needed(install_queue)

            if (install_queue or removal_queue) and not crit_block:

                # activate UI lock
                self.ui_lock(True)

                controller = QueueExecutor(self)
                self.my_inst_error = 0
                self.my_inst_abort = False
                def run_tha_bstrd():
                    try:
                        e = controller.run(install_queue[:],
                            removal_queue[:], do_purge_cache,
                            fetch_only = fetch_only,
                            download_sources = download_sources,
                            selected_by_user = selected_by_user)
                    except QueueError:
                        self.my_inst_abort = True
                        e, i = 1, None
                        # make sure that bool is reset back to False
                    except:
                        entropy.tools.print_traceback()
                        e, i = 1, None
                    self.my_inst_error = e

                t = ParallelTask(run_tha_bstrd)
                t.start()
                dbg_count = 0
                while t.isAlive():
                    if dbg_count > 2000:
                        dbg_count = 0
                    dbg_count += 1
                    time.sleep(0.2)
                    if self.do_debug and (dbg_count % 500 == 0):
                        print_generic("process_queue: QueueExecutor thread still alive")
                    self.gtk_loop()
                    if self.do_debug and (dbg_count % 500 == 0):
                        print_generic("process_queue: after QueueExecutor loop")

                err = self.my_inst_error
                if self.do_debug:
                    print_generic("process_queue: left all")

                self.ui.skipMirror.hide()
                self.ui.abortQueue.hide()
                if self.do_debug:
                    print_generic("process_queue: buttons now hidden")

                # deactivate UI lock
                if self.do_debug:
                    print_generic("process_queue: unlocking gui?")
                self.ui_lock(False)
                if self.do_debug:
                    print_generic("process_queue: gui unlocked")

                if (err == 0) and ((not fetch_only) and (not download_sources)):
                    # this triggers post-branch upgrade function inside
                    # Entropy Client SystemSettings plugin
                    self.Equo.SystemSettings.clear()

                if self.my_inst_abort:
                    okDialog(self.ui.main,
                        _("Attention. You chose to abort the processing."))
                elif err == 1: # install failed
                    okDialog(self.ui.main,
                        _("Attention. An error occured when processing the queue."
                        "\nPlease have a look in the processing terminal.")
                    )
                elif err in (2, 3):
                    # 2: masked package cannot be unmasked
                    # 3: license not accepted, move back to queue page
                    switch_back_page = 'queue'
                    state = False

                elif (err == 0) and restart_needed and \
                    ((not fetch_only) and (not download_sources)):
                    okDialog(self.ui.main,
                        _("Attention. You have updated Entropy."
                        "\nSulfur will be reloaded.")
                    )
                    self.Equo.resources_remove_lock()
                    self.quit(sysexit = False)
                    self.exit_now()
                    raise SystemExit(99)

            if self.do_debug:
                print_generic("process_queue: end_working?")
            self.end_working()
            self.progress.reset_progress()
            if self.do_debug:
                print_generic("process_queue: end_working")

            if (not fetch_only) and (not download_sources):

                if self.do_debug:
                    print_generic("process_queue: cleared caches")

                for myrepo in remove_repos:
                    self.Equo.remove_repository(myrepo)

                self.reset_cache_status()
                if self.do_debug:
                    print_generic("process_queue: closed repo dbs")
                self.Equo.reopen_client_repository()
                if self.do_debug:
                    print_generic("process_queue: cleared caches (again)")
                # regenerate packages information
                if self.do_debug:
                    print_generic("process_queue: setting up Sulfur")
                self.setup_application()
                if self.do_debug:
                    print_generic("process_queue: scanning for new files")
                self.Equo.FileUpdates.scanfs(dcache = False, quiet = True)
                if self.Equo.FileUpdates.scandata:
                    if len(self.Equo.FileUpdates.scandata) > 0:
                        switch_back_page = 'filesconf'
                if self.do_debug:
                    print_generic("process_queue: all done")

        else:
            self.set_status_ticker( _( "No packages selected" ) )

        self.show_notebook_tabs_after_install()
        self.disable_ugc = False
        if switch_back_page is not None:
            self.switch_notebook_page(switch_back_page)

        self.Equo.resources_remove_lock()
        return state

    def ui_lock(self, lock):
        self.ui.menubar.set_sensitive(not lock)

    def switch_notebook_page(self, page):
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

    def run_editor(self, filename, delete = False):
        cmd = ' '.join([self._file_editor, filename])
        task = ParallelTask(self.__run_editor, cmd, delete, filename)
        task.start()

    def __run_editor(self, cmd, delete, filename):
        os.system(cmd+"&> /dev/null")
        if delete and os.path.isfile(filename) and os.access(filename, os.W_OK):
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
            source = os.path.join(os.path.dirname(destination), source)
            return identifier, source, destination
        return 0, None, None

    def load_advisory_info_menu(self, item):
        my = SecurityAdvisoryMenu(self.ui.main)
        my.load(item)

    def load_package_info_menu(self, pkg):
        mymenu = PkgInfoMenu(self.Equo, pkg, self.ui.main)
        load_count = 6
        while True:
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
        if self.do_debug:
            print_generic("queue_bombing: bomb?")
        if self.abortQueueNow:
            if self.do_debug:
                print_generic("queue_bombing: BOMBING !!!")
            self.abortQueueNow = False
            mytxt = _("Aborting queue tasks.")
            raise QueueError('QueueError %s' % (mytxt,))

    def mirror_bombing(self):

        if self.skipMirrorNow:
            self.skipMirrorNow = False
            mytxt = _("Skipping current mirror.")
            raise OnlineMirrorError('OnlineMirrorError %s' % (mytxt,))

        if self.abortQueueNow:
            self.abortQueueNow = False
            print_generic("mirror_bombing: queue BOMB !!!")
            # do not reset self.abortQueueNow here, we need
            # mirror_bombing to keep crashing
            raise QueueError('QueueError %s' % (mytxt,))


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
        for key, s_widget in list(self.colorSettingsMap.items()):
            if not hasattr(SulfurConf, key):
                if self.do_debug: print_generic("WARNING: no %s in SulfurConf" % (key,))
                continue
            color = getattr(SulfurConf, key)
            s_widget.set_color(gtk.gdk.color_parse(color))


