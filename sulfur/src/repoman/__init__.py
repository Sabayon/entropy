# -*- coding: utf-8 -*-
#    Repository Manager Interface for Entropy
#    Copyright: (C) 2007-2010 Fabio Erculiani < lxnay<AT>sabayonlinux<DOT>org >
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

import threading
import time, gtk, gobject, pty, sys
from entropy.i18n import _
from entropy.exceptions import *
from entropy.const import *
from entropy.misc import TimeScheduled, ParallelTask
from entropy.output import print_generic
import entropy.dump

from sulfur.core import UI
from sulfur.setup import const, cleanMarkupString, fakeoutfile, fakeinfile
from sulfur.dialogs import RmNoticeBoardMenu, okDialog, MenuSkel, PkgInfoMenu, \
    SecurityAdvisoryMenu

class RemoteConnectionMenu(MenuSkel):

    store_path = 'connection_manager'
    def __init__( self, Entropy, verification_callback, window ):

        self.Entropy = Entropy
        # hostname, port, username, password, ssl will be passed as parameters
        self.verification_callback = verification_callback
        self.window = window
        self.cm_ui = UI( const.GLADE_FILE, 'remoteConnManager', 'entropy' )
        self.cm_ui.signal_autoconnect(self._getAllMethods())
        self.cm_ui.remoteConnManager.set_transient_for(self.window)
        self.cm_ui.remoteConnManager.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.connStore = gtk.ListStore( gobject.TYPE_PYOBJECT )
        self.connView = self.cm_ui.connManagerConnView
        self.connView.set_model(self.connStore)
        self.button_pressed = False
        self.loaded = False
        self.parameters = None
        self.connection_data = self.get_stored_connection_data()
        self.setup_view()
        if self.connection_data:  self.set_connection_object(self.connection_data[0])

    def on_connManagerAddConnButton_clicked(self, widget):

        def fake_callback(s):
            return s

        def fake_callback_cb(s):
            return True

        input_params = [
            ('name', _("Connection name"), fake_callback, False),
            ('hostname', _("Hostname"), fake_callback, False),
            ('port', _("Port"), fake_callback, False),
            ('user', _("Username"), fake_callback, False),
            ('ssl', ('checkbox', _('SSL Connection'),), fake_callback_cb, False),
        ]
        data = self.Entropy.input_box(
            _('Choose what kind of test you would like to run'),
            input_params,
            cancel_button = True
        )
        if data == None: return
        self.store_connection_data_item(data)
        self.fill_connection_view()
        self.store_connection_data()

    def on_connManagerConnView_row_activated(self, treeview, path, column):
        self.on_connManagerSetConnButton_clicked(treeview)

    def set_connection_object(self, obj):
        self.cm_ui.connManagerHostnameEntry.set_text(obj['hostname'])
        try:
            self.cm_ui.connManagerPortSpinButton.set_value(float(obj['port']))
        except ValueError:
            if obj['ssl']:
                self.cm_ui.connManagerPortSpinButton.set_value(
                    float(etpConst['socket_service']['ssl_port']))
            else:
                self.cm_ui.connManagerPortSpinButton.set_value(
                    float(etpConst['socket_service']['port']))

        self.cm_ui.connManagerUsernameEntry.set_text(obj['user'])
        self.cm_ui.connManagerPasswordEntry.set_text('')
        self.cm_ui.connManagerSSLCheckButton.set_active(obj['ssl'])

    def on_connManagerSetConnButton_clicked(self, widget):
        model, myiter = self.connView.get_selection().get_selected()
        if not myiter: return
        obj = model.get_value(myiter, 0)
        self.set_connection_object(obj)

    def on_connManagerRemoveConnButton_clicked(self, widget):
        model, myiter = self.connView.get_selection().get_selected()
        if not myiter: return
        obj = model.get_value(myiter, 0)
        self.remove_connection_data_item(obj)
        self.fill_connection_view()
        self.store_connection_data()

    def get_stored_connection_data(self):
        obj = entropy.dump.loadobj(self.store_path)
        if not obj: return []
        return obj

    def remove_connection_data_item(self, item):
        if item in self.connection_data:
            self.connection_data.remove(item)

    def store_connection_data_item(self, item):
        self.connection_data.append(item)

    def store_connection_data(self):
        entropy.dump.dumpobj(self.store_path, self.connection_data)

    def fill_connection_view(self):
        self.connStore.clear()
        for item in self.connection_data:
            self.connStore.append( (item,) )
        self.connView.queue_draw()

    def setup_view(self):

        self.create_text_column( self.connView, _( "Connection" ), 'name', size = 200, expand = True)
        self.create_text_column( self.connView, _( "Hostname" ), 'hostname', size = 100)
        self.create_text_column( self.connView, _( "Port" ), 'port', size = 50)

        # SSL
        cell = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn( _("SSL"), cell ) # Document Type
        column.set_cell_data_func( cell, self.ssl_pixbuf )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 50 )
        column.set_sort_column_id( -1 )
        self.connView.append_column( column )

        self.fill_connection_view()


    def ssl_pixbuf( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 )
        if obj:
            if obj['ssl']:
                cell.set_property( 'stock-id', 'gtk-apply' )
                return
        cell.set_property( 'stock-id', 'gtk-cancel' )

    def get_data_text( self, column, cell, model, myiter, property ):
        obj = model.get_value( myiter, 0 )
        if obj: cell.set_property('markup', obj[property])

    def create_text_column( self, view, hdr, property, size, sortcol = None, expand = False, set_height = 0, cell_data_func = None, sort_col_id = -1):
        if cell_data_func == None: cell_data_func = self.get_data_text
        cell = gtk.CellRendererText()
        if set_height: cell.set_property('height', set_height)
        column = gtk.TreeViewColumn( hdr, cell )
        column.set_resizable( True )
        column.set_cell_data_func( cell, cell_data_func, property )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( size )
        column.set_expand(expand)
        column.set_sort_column_id( sort_col_id )
        view.append_column( column )
        return column

    def load( self ):
        bold_items = [
            self.cm_ui.connManagerTitleLabel,
        ]
        for item in bold_items:
            item.set_markup("<b>%s</b>" % ( item.get_text(),))

        self.loaded = True
        self.cm_ui.remoteConnManager.show_all()

    def run(self):

        if not self.loaded:
            return None

        tries = 3
        while tries:

            while not self.button_pressed:
                time.sleep(0.05)
                while gtk.events_pending():
                    gtk.main_iteration()
                continue

            if self.parameters:
                valid, error_msg = self.verification_callback(
                        self.parameters['hostname'],
                        self.parameters['port'],
                        self.parameters['username'],
                        self.parameters['password'],
                        self.parameters['ssl']
                    )
                if not valid:
                    okDialog(self.window, error_msg, title = _("Connection Error"))
                    self.button_pressed = False
                    tries -= 1
                    continue
            break

        self.destroy()
        if not tries:
            return None
        return self.parameters

    def on_remoteConnEventBox_key_release_event(self, widget, event):
        if event.string == "\r":
            self.cm_ui.connManagerConnectButton.clicked()
            return True
        return False # propagate

    def on_connManagerConnectButton_clicked(self, widget):
        self.parameters = {
            'hostname': self.cm_ui.connManagerHostnameEntry.get_text(),
            'port': self.cm_ui.connManagerPortSpinButton.get_value(),
            'username': self.cm_ui.connManagerUsernameEntry.get_text(),
            'password': self.cm_ui.connManagerPasswordEntry.get_text(),
            'ssl': self.cm_ui.connManagerSSLCheckButton.get_active()
        }
        self.button_pressed = True

    def on_remoteConnCloseButton_clicked(self, widget):
        self.parameters = None
        self.button_pressed = True

    def destroy( self ):
        self.cm_ui.remoteConnManager.hide()
        self.cm_ui.remoteConnManager.destroy()

class RepositoryManagerMenu(MenuSkel):

    class SocketLock:
        """ Socket lock, this is used for stopping updaters too """

        def __init__(self, repoman_intf):
            self.__intf = repoman_intf
            self.__lock = threading.Lock()

        def __enter__(self):
            self.__intf.pause_updaters(True)
            return self.__lock.acquire()

        def __exit__(self, exc_type, exc_value, traceback):
            self.__intf.pause_updaters(False)
            self.__lock.release()


    def __init__(self, Entropy, window):
        self.ui_locked = True
        self.do_debug = False
        if etpUi['debug']:
            self.do_debug = True
        self.BufferLock = RepositoryManagerMenu.SocketLock(self)
        self.Entropy = Entropy
        self.window = window
        self.sm_ui = UI( const.GLADE_FILE, 'repositoryManager', 'entropy' )
        self.sm_ui.signal_autoconnect(self._getAllMethods())
        self.sm_ui.repositoryManager.set_transient_for(self.window)

        self.DataStore = None
        self.DataView = None
        self.QueueLock = threading.Lock()
        self.OutputLock = threading.Lock()
        self.paused_queue_id = None
        self.is_processing = None
        self.is_writing_output = False
        self.Output = None
        self.output_pause = False
        self.queue_pause = False
        self.ssl_mode = True
        self.repos_loaded = False
        self.PinboardData = {}
        self.Queue = {}

        self.setup_queue_view()
        self.setup_pinboard_view()
        self.setup_console()

        self.queue_timer = 5
        self.output_timer = 3
        self.pinboard_timer = 60
        self.QueueUpdater = TimeScheduled(self.queue_timer,
            self.update_queue_view)
        self.OutputUpdater = TimeScheduled(self.output_timer,
            self.update_output_view)
        self.PinboardUpdater = TimeScheduled(self.pinboard_timer,
            self.update_pinboard_view)
        self.notebook_pages = {
            'queue': 0,
            'commands': 1,
            'data': 2,
            'output': 3
        }
        self.dict_queue_keys = ['queue', 'processing', 'processed', 'errored']
        self.DataScroll = self.sm_ui.dataViewScrollWin
        self.DataViewBox = self.sm_ui.repoManagerDataViewBox
        self.DataViewButtons = {}
        self.setup_data_view_buttons()
        self.data_tree_selection_mode = None
        self.DataViewVbox = self.sm_ui.dataViewVbox

        from entropy.client.services.system.interfaces import Client as \
            SystemManagerClientInterface
        from entropy.client.services.system.commands import Repository as \
            SystemManagerRepositoryClientCommands
        from entropy.client.services.system.methods import Repository as \
            SystemManagerRepositoryMethodsInterface
        self.Service = SystemManagerClientInterface(
            self.Entropy,
            MethodsInterface = SystemManagerRepositoryMethodsInterface,
            ClientCommandsInterface = SystemManagerRepositoryClientCommands
        )
        self.CommandsStore = None
        self.setup_commands_view()
        self.fill_commands_view(self.Service.get_available_client_commands())
        self.ServiceStatus = True
        self.connection_done = False
        self.setup_available_repositories()

    def __del__(self):
        if hasattr(self, 'connection_done'):
            if self.connection_done:
                self.Service.kill_all_connections()

    def pause_updaters(self, pause):
        self.debug_print("pause_updaters", str(pause))
        self.QueueUpdater.pause(pause)
        self.OutputUpdater.pause(pause)
        self.PinboardUpdater.pause(pause)

    def ui_lock(self, action):
        self.ui_locked = action
        self.sm_ui.repositoryManager.set_sensitive(not action)

    def set_notebook_page(self, page):
        self.sm_ui.repoManagerNotebook.set_current_page(page)

    def stdout_writer(self, txt):
        self.console.feed_child(txt + '\n\r')

    def setup_console(self):

        self.pty = pty.openpty()
        self.std_output = fakeoutfile(self.pty[1])
        self.std_input = fakeinfile(self.pty[1])

        # setup add repository window
        self.console_menu_xml = gtk.glade.XML( const.GLADE_FILE, "terminalMenu", domain="entropy" )
        self.console_menu = self.console_menu_xml.get_widget( "terminalMenu" )
        self.console_menu_xml.signal_autoconnect(self)

        from sulfur.widgets import SulfurConsole
        self.console = SulfurConsole()
        self.console.set_scrollback_lines(1024)
        self.console.set_scroll_on_output(True)
        # this is a workaround for buggy vte.Terminal when using
        # file descriptors. This will make fakeoutfile to use
        # our external writer instead of using os.write
        self.std_output.external_writer = self.stdout_writer

        self.console.set_pty(self.pty[0])
        self.console.connect("button-press-event", self.on_console_click)
        self.console.connect("commit", self.on_console_commit)
        termScroll = gtk.VScrollbar(self.console.get_adjustment())
        self.sm_ui.repoManagerVteBox.pack_start(self.console, True, True)
        self.sm_ui.repoManagerTermScrollBox.pack_start(termScroll, False)
        self.sm_ui.repoManagerTermHBox.show_all()

    def debug_print(self, f, msg):
        if self.do_debug:
            print_generic("repoman debug:", repr(self), f, msg)

    def clear_console(self):
        self.std_input.text_read = ''
        self.console.reset()

    def clear_data_store_and_view(self):
        self.debug_print("clear_data_store_and_view", "enter")
        self.reset_data_view()
        self.hide_all_data_view_buttons()
        self.DataViewVbox.queue_draw()
        while gtk.events_pending():
            gtk.main_iteration()

    def reset_data_view(self):
        if self.DataView != None:
            self.debug_print("reset_data_view", "removing old DataView")
            self.DataScroll.remove(self.DataView)
            self.DataScroll.queue_draw()
            self.DataView.destroy()
            self.DataView = None
            self.debug_print("reset_data_view", "removal of old DataView done")

    def on_repoManagerConsoleEvent_enter_notify_event(self, widget, event):
        self.console.grab_focus()

    def on_console_click(self, widget, event):
        if event.button == 3:
            self.console_menu.popup( None, None, None, event.button, event.time )
        return True

    def on_console_commit(self, widget, txt, txtlen):
        if txt == "\r":
            self.on_repoManagerStdinEntry_activate(None, False, self.std_input.text_read)
            self.std_input.text_read = ''
        elif txt == '\x7f':
            self.std_input.text_read = self.std_input.text_read[:-1]
        else:
            self.std_input.text_read += txt

    def on_terminal_clear_activate(self, widget):
        self.clear_console()

    def on_terminal_copy_activate(self, widget):
        self.console.select_all()
        self.console.copy_clipboard()
        self.console.select_none()

    def setup_data_view_buttons(self):

        glsa_package_info_button = gtk.Button(label = _("Packages information"))
        glsa_package_info_image = gtk.Image()
        glsa_package_info_image.set_from_stock(gtk.STOCK_INFO, 4)
        glsa_package_info_button.set_image(glsa_package_info_image)

        glsa_adv_info_button = gtk.Button(label = _("Advisory information"))
        glsa_adv_info_image = gtk.Image()
        glsa_adv_info_image.set_from_stock(gtk.STOCK_EDIT, 4)
        glsa_adv_info_button.set_image(glsa_adv_info_image)

        #

        mirror_updates_execute_button = gtk.Button(label = _("Execute"))
        mirror_updates_execute_button_image = gtk.Image()
        mirror_updates_execute_button_image.set_from_stock(gtk.STOCK_EXECUTE, 4)
        mirror_updates_execute_button.set_image(mirror_updates_execute_button_image)

        #

        database_updates_package_info_button = gtk.Button(label = _("Packages information"))
        database_updates_package_info_image = gtk.Image()
        database_updates_package_info_image.set_from_stock(gtk.STOCK_INFO, 4)
        database_updates_package_info_button.set_image(database_updates_package_info_image)

        database_updates_change_repo_button = gtk.Button(label = _("Destination repository"))
        database_updates_change_repo_image = gtk.Image()
        database_updates_change_repo_image.set_from_stock(gtk.STOCK_CONVERT, 4)
        database_updates_change_repo_button.set_image(database_updates_change_repo_image)

        database_updates_execute_button = gtk.Button(label = _("Execute"))
        database_updates_execute_button_image = gtk.Image()
        database_updates_execute_button_image.set_from_stock(gtk.STOCK_EXECUTE, 4)
        database_updates_execute_button.set_image(database_updates_execute_button_image)

        #

        available_packages_package_info_button = gtk.Button(label = _("Packages information"))
        available_packages_package_info_image = gtk.Image()
        available_packages_package_info_image.set_from_stock(gtk.STOCK_INFO, 4)
        available_packages_package_info_button.set_image(available_packages_package_info_image)

        available_packages_remove_package_button = gtk.Button(label = _("Remove packages"))
        available_packages_remove_package_image = gtk.Image()
        available_packages_remove_package_image.set_from_stock(gtk.STOCK_REMOVE, 4)
        available_packages_remove_package_button.set_image(available_packages_remove_package_image)

        available_packages_move_package_button = gtk.Button(label = _("Copy/move packages"))
        available_packages_move_package_image = gtk.Image()
        available_packages_move_package_image.set_from_stock(gtk.STOCK_COPY, 4)
        available_packages_move_package_button.set_image(available_packages_move_package_image)

        categories_updates_compile_button = gtk.Button(label = _("Compile selected"))
        categories_updates_compile_image = gtk.Image()
        categories_updates_compile_image.set_from_stock(gtk.STOCK_GOTO_BOTTOM, 4)
        categories_updates_compile_button.set_image(categories_updates_compile_image)

        categories_updates_add_use_button = gtk.Button(label = _("Add USE"))
        categories_updates_add_use_image = gtk.Image()
        categories_updates_add_use_image.set_from_stock(gtk.STOCK_ADD, 4)
        categories_updates_add_use_button.set_image(categories_updates_add_use_image)

        categories_updates_remove_use_button = gtk.Button(label = _("Remove USE"))
        categories_updates_remove_use_image = gtk.Image()
        categories_updates_remove_use_image.set_from_stock(gtk.STOCK_REMOVE, 4)
        categories_updates_remove_use_button.set_image(categories_updates_remove_use_image)

        #

        notice_board_view_button = gtk.Button(label = _("View"))
        notice_board_view_image = gtk.Image()
        notice_board_view_image.set_from_stock(gtk.STOCK_ZOOM_IN, 4)
        notice_board_view_button.set_image(notice_board_view_image)

        notice_board_add_button = gtk.Button(label = _("Add"))
        notice_board_add_image = gtk.Image()
        notice_board_add_image.set_from_stock(gtk.STOCK_ADD, 4)
        notice_board_add_button.set_image(notice_board_add_image)

        notice_board_remove_button = gtk.Button(label = _("Remove"))
        notice_board_remove_image = gtk.Image()
        notice_board_remove_image.set_from_stock(gtk.STOCK_REMOVE, 4)
        notice_board_remove_button.set_image(notice_board_remove_image)

        notice_board_refresh_button = gtk.Button(label = _("Refresh"))
        notice_board_refresh_image = gtk.Image()
        notice_board_refresh_image.set_from_stock(gtk.STOCK_REFRESH, 4)
        notice_board_refresh_button.set_image(notice_board_refresh_image)

        self.DataViewButtons = {
            'glsa': {
                'package_info_button': glsa_package_info_button,
                'adv_info_button': glsa_adv_info_button,
                'order': ['package_info_button', 'adv_info_button'],
                'handler_ids': [],
            },
            'mirror_updates': {
                'execute_button': mirror_updates_execute_button,
                'order': ['execute_button'],
                'handler_ids': [],
            },
            'database_updates': {
                'package_info_button': database_updates_package_info_button,
                'change_repo_button': database_updates_change_repo_button,
                'execute_button': database_updates_execute_button,
                'order': ['package_info_button', 'change_repo_button', 'execute_button'],
                'handler_ids': [],
            },
            'available_packages': {
                'package_info_button': available_packages_package_info_button,
                'remove_package_button': available_packages_remove_package_button,
                'move_package_button': available_packages_move_package_button,
                'order': ['package_info_button', 'remove_package_button', 'move_package_button'],
                'handler_ids': [],
            },
            'categories_updates': {
                'compile_button': categories_updates_compile_button,
                'add_use_button': categories_updates_add_use_button,
                'remove_use_button': categories_updates_remove_use_button,
                'order': ['compile_button', 'add_use_button', 'remove_use_button'],
                'handler_ids': [],
            },
            'notice_board': {
                'add_button': notice_board_add_button,
                'remove_button': notice_board_remove_button,
                'refresh_button': notice_board_refresh_button,
                'view_button': notice_board_view_button,
                'order': ['view_button', 'add_button', 'remove_button', 'refresh_button'],
                'handler_ids': [],
            }
        }

        for cat in self.DataViewButtons:
            for w_id in self.DataViewButtons[cat]['order']:
                self.DataViewBox.pack_start(self.DataViewButtons[cat][w_id], False, False, 1)

    def show_data_view_buttons_cat(self, cat):
        if cat in self.DataViewButtons:
            for w_id in self.DataViewButtons[cat]['order']:
                self.DataViewButtons[cat][w_id].show()
                # disconnect all signal handlers
                for h_id in self.DataViewButtons[cat]['handler_ids']:
                    w = self.DataViewButtons[cat][w_id]
                    if w.handler_is_connected(h_id): w.disconnect(h_id)
            del self.DataViewButtons[cat]['handler_ids'][:]

    def hide_all_data_view_buttons(self):
        self.debug_print("hide_all_data_view_buttons", "enter")
        for cat in self.DataViewButtons:
            for w_id in self.DataViewButtons[cat]['order']:
                self.debug_print("hide_all_data_view_buttons", "hiding button %s,%s" % (cat, w_id,))
                self.DataViewButtons[cat][w_id].hide()
        self.debug_print("hide_all_data_view_buttons", "quit")

    def setup_available_repositories(self):
        self.EntropyRepositories = {
            'available': [],
            'current': ''
        }
        self.EntropyRepositoryCombo = self.sm_ui.repoManagerRepositoryCombo
        self.EntropyRepositoryStore = gtk.ListStore( gobject.TYPE_STRING )
        self.EntropyRepositoryCombo.set_model(self.EntropyRepositoryStore)
        cell = gtk.CellRendererText()
        self.EntropyRepositoryCombo.pack_start(cell, True)
        self.EntropyRepositoryCombo.add_attribute(cell, 'text', 0)
        self.EntropyRepositoryComboLoader = ParallelTask(self.load_available_repositories)

    def setup_commands_view(self):

        # setup commands view
        self.CommandsView = self.sm_ui.repoManagerCommandsView
        self.CommandsStore = gtk.ListStore( gobject.TYPE_PYOBJECT )
        self.CommandsView.set_model( self.CommandsStore )

        # command col
        self.create_text_column( self.CommandsView, _( "Command" ), 'commands:command', size = 270, set_height = 40)
        # desc col
        self.create_text_column( self.CommandsView, _( "Description" ), 'commands:desc', size = 200, expand = True, set_height = 40)

    def fill_commands_view(self, data):
        self.CommandsStore.clear()
        keys = sorted(data.keys())
        for key in keys:
            if data[key]['private']: continue
            item = data[key].copy()
            item['key'] = key
            params = ' | '.join([cleanMarkupString(str(x)) for x in item['params']])
            if not params:
                params = _("None")
            txt = "<small><b>%s</b>: %s\n<b>%s</b>: %s</small>" % (
                _("Description"),
                cleanMarkupString(item['desc']),
                _("Parameters"),
                params,
            )
            item['myinfo'] = txt
            self.CommandsStore.append((item,))
        self.CommandsView.queue_draw()

    def setup_queue_view(self):

        # setup queue view
        self.QueueView = self.sm_ui.repoManagerQueueView
        self.QueueStore = gtk.ListStore( gobject.TYPE_PYOBJECT, gobject.TYPE_STRING )
        self.QueueView.set_model( self.QueueStore )

        # selection pixmap
        cell = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn( _("Status"), cell )
        column.set_cell_data_func( cell, self.queue_pixbuf )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 80 )
        column.set_sort_column_id( 0 )
        self.QueueView.append_column( column )

        # command col
        self.create_text_column( self.QueueView, _( "Command" ), 'queue:command_name', size = 180)
        # description col
        self.create_text_column( self.QueueView, _( "Parameters" ), 'queue:command_text', size = 200, expand = True)
        # date col
        self.create_text_column( self.QueueView, _( "Date" ), 'queue:ts', size = 120, sort_col_id = 1)

    def setup_data_view(self):

        store = gtk.TreeStore( gobject.TYPE_PYOBJECT )
        self.debug_print("setup_data_view", "enter")
        self.reset_data_view()
        self.debug_print("setup_data_view", "creating new DataView")
        dv = gtk.TreeView()
        dv.set_model(store)
        self.data_tree_selection_mode = dv.get_selection().get_mode()
        self.DataStore = store
        self.DataView = dv
        self.debug_print("setup_data_view", "quit")

    def show_data_view(self):
        self.DataScroll.add(self.DataView)
        self.debug_print("show_data_view", "adding to DataScroll")
        self.DataView.show()
        self.debug_print("show_data_view", "showing DataView")

    def setup_pinboard_view(self):

        # setup pinboard view
        self.PinboardView = self.sm_ui.repoManagerPinboardView
        self.PinboardStore = gtk.ListStore( gobject.TYPE_PYOBJECT, gobject.TYPE_STRING )
        self.PinboardView.set_model( self.PinboardStore )
        self.PinboardView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.PinboardView.set_rubber_banding(True)

        # selection pixmap
        cell = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn( _("Status"), cell )
        column.set_cell_data_func( cell, self.pinboard_pixbuf )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 80 )
        column.set_sort_column_id( 0 )
        self.PinboardView.append_column( column )

        # date
        self.create_text_column( self.PinboardView, _( "Date" ), 'pinboard:date', size = 130, sort_col_id = 1)
        # note
        self.create_text_column( self.PinboardView, _( "Note" ), 'pinboard:note', size = 200, expand = True)

    def create_text_column( self, view, hdr, property, size, sortcol = None, expand = False, set_height = 0, cell_data_func = None, sort_col_id = -1):
        if cell_data_func == None: cell_data_func = self.get_data_text
        cell = gtk.CellRendererText()
        if set_height: cell.set_property('height', set_height)
        column = gtk.TreeViewColumn( hdr, cell )
        column.set_resizable( True )
        column.set_cell_data_func( cell, cell_data_func, property )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( size )
        column.set_expand(expand)
        column.set_sort_column_id( sort_col_id )
        view.append_column( column )
        return column

    def queue_pixbuf( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 )
        if isinstance(obj, dict):
            st = self.get_status_from_queue_item(obj.copy())
            if st != None:
                cell.set_property('stock-id', st)

    def pinboard_pixbuf( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 )
        if isinstance(obj, dict):
            if obj['done']:
                cell.set_property('stock-id', 'gtk-apply')
            else:
                cell.set_property('stock-id', 'gtk-cancel')

    def spm_package_obj_to_cell(self, obj, cell):
        use_data = []
        if 'use' in obj:
            if 'use_string' in obj['use']:
                use_data = obj['use']['use_string'].split()
        max_chars = 100
        use_string = []
        for use in use_data:
            max_chars -= len(use)
            use_string.append(use)
            if max_chars < 0:
                use_string.append("\n")
                max_chars = 100
        use_string = ' '.join(use_string).strip()
        installed_string = ''
        available_string = ''
        if 'installed_atom' in obj:
            installed_string = '<b>%s</b>: %s\n' % (_("Installed"), cleanMarkupString(str(obj['installed_atom'])),)
        if 'available_atom' in obj:
            available_string = '<b>%s</b>: %s\n' % (_("Available"), cleanMarkupString(str(obj['available_atom'])),)

        atom = obj.get('atom')
        key = obj.get('key')
        slot = obj.get('slot')
        description = obj.get('description')

        txt = "<i>%s</i>\n<small><b>%s</b>: %s, <b>%s</b>: %s\n" % (
            cleanMarkupString(atom),
            _("Key"),
            cleanMarkupString(key),
            _("Slot"),
            cleanMarkupString(slot),
        )
        txt += installed_string
        txt += available_string
        if len(use_string) > 160:
            use_string = use_string[:160]
        txt += "<b>%s</b>: %s\n<b>%s</b>: %s</small>" % (
            _("Description"),
            cleanMarkupString(description),
            _("USE Flags"),
            cleanMarkupString(use_string),
        )
        cell.set_property('markup', txt)

    def entropy_package_obj_to_cell(self, obj, cell):
        mytxt = '<small><i>%s</i>\n%s\n<b>%s</b>: %s | <b>%s</b>: %s | <b>%s</b>: %s | <b>%s</b>: %s | <b>%s</b>: %s\n<b>%s</b>: %s</small>' % (
            obj['atom'],
            cleanMarkupString(obj['description']),
            _("Size"),
            entropy.tools.bytes_into_human(obj['size']),
            _("Branch"),
            obj['branch'],
            _("Slot"),
            cleanMarkupString(obj['slot']),
            _("Tag"),
            cleanMarkupString(obj['versiontag']),
            _("Injected"),
            obj['injected'],
            _("Homepage"),
            cleanMarkupString(obj['homepage']),
        )
        cell.set_property('markup', mytxt)

    def get_status_from_queue_item(self, item):
        if 'errored_ts' in item:
            return "gtk-cancel"
        elif 'processed_ts' in item:
            return "gtk-apply"
        elif 'processing_ts' in item:
            return "gtk-refresh"
        elif 'queue_ts' in item:
            return "gtk-up"
        return "gtk-apply"

    def get_ts_from_queue_item(self, item):
        if 'errored_ts' in item:
            return item['errored_ts']
        elif 'processed_ts' in item:
            return item['processed_ts']
        elif 'processing_ts' in item:
            return item['processing_ts']
        elif 'queue_ts' in item:
            return item['queue_ts']
        return None

    def get_data_text( self, column, cell, model, myiter, property ):
        obj = model.get_value( myiter, 0 )
        if isinstance(obj, dict):
            if property == "queue:ts":
                cell.set_property('markup', self.get_ts_from_queue_item(obj))
            elif property == "queue:command_text":
                cell.set_property('markup', cleanMarkupString(obj['command_text']))
            elif property == "queue:command_name":
                cell.set_property('markup', cleanMarkupString(obj['command_name']))
            elif property == "commands:command":
                cell.set_property('markup', obj['key'])
            elif property == "commands:desc":
                cell.set_property('markup', obj['myinfo'])
            elif property == "pinboard:date":
                cell.set_property('markup', str(obj['ts']))
            elif property == "pinboard:note":
                cell.set_property('markup', cleanMarkupString(obj['note']))

    def connection_verification_callback(self, host, port, username, password, ssl):
        self.Service.setup_connection(
            host,
            int(port),
            username,
            password,
            ssl
        )
        # test connection
        srv = self.Service.get_service_connection(timeout = 5)
        if srv == None:
            return False, _("No connection to host, please check your data")
        try:
            session = srv.open_session()
            if session == None:
                return False, _("Unable to create a remote session. Try again later.")
            try:
                logged, error = self.Service.login(srv, session)
                if not logged:
                    return False, _("Login failed. Please retry.")
            except Exception as e:
                entropy.tools.print_traceback()
                return False, "%s: %s" % (_("Connection Error"), e,)
            srv.close_session(session)
            srv.disconnect()
            self.connection_done = True
            return True, None
        except SSLError:
            return False, _("SSL Error, are you sure the server supports SSL?")

    def load(self):

        my = RemoteConnectionMenu(self.Entropy, self.connection_verification_callback, self.window)
        my.load()
        login_data = my.run()
        if not login_data:
            return False

        self.sm_ui.repositoryManager.show_all()
        self.hide_all_data_view_buttons()

        # spawn parallel tasks
        self.QueueUpdater.start()
        self.OutputUpdater.start()
        self.PinboardUpdater.start()

        # ui will be unlocked by the thread below
        self.ui_lock(True)
        self.EntropyRepositoryComboLoader.start()
        return True

    def get_item_by_queue_id(self, queue_id):
        with self.QueueLock:
            for key in self.Queue:
                if key not in self.dict_queue_keys:
                    continue
                item = self.Queue[key].get(queue_id)
                if item != None:
                    return item, key
        return None, None

    def service_status_message(self, e):
        entropy.tools.print_traceback()
        def do_ok():
            okDialog(self.sm_ui.repositoryManager, str(e),
                title = _("Communication error"))
            return False
        gobject.idle_add(do_ok)

    def get_available_repositories(self):
        with self.BufferLock:
            try:
                status, repo_info = self.Service.Methods.get_available_repositories()
                if not status:
                    return None
            except Exception as e:
                self.service_status_message(e)
                return
        return repo_info

    def load_available_repositories(self, repo_info = None):

        if repo_info == None:
            repo_info = self.get_available_repositories()
            if not repo_info:
                return

        if isinstance(repo_info, dict):

            def task(repo_info):

                self.EntropyRepositories = repo_info.copy()
                self.EntropyRepositoryStore.clear()
                for repoid in list(self.EntropyRepositories['available'].keys()):
                    item = self.EntropyRepositoryStore.append( (repoid,) )
                    if repoid == self.EntropyRepositories['current']:
                        self.EntropyRepositoryCombo.set_active_iter(item)
                mytxt = "<small><b>%s</b>: %s [<b>%s</b>: %s | <b>%s</b>: %s | <b>%s</b>: %s]</small>" % (
                    _("Current"),
                    self.EntropyRepositories['current'],
                    _("c.mode"),
                    self.EntropyRepositories['community_mode'],
                    _("branch"),
                    self.EntropyRepositories['branch'],
                    _("repositories"),
                    len(self.EntropyRepositories['available']),
                )
                try:
                    self.sm_ui.repoManagerCurrentRepoLabel.set_markup(mytxt)
                except AttributeError: # user might have closed the win
                    pass
                if not self.repos_loaded:
                    self.repos_loaded = True
                    self.ui_lock(False)
                return False

            gobject.idle_add(task, repo_info)

    def update_queue_view(self):

        def task():
            self.do_update_queue_view()

        t = ParallelTask(task)
        t.start()

    def do_update_queue_view(self):
        with self.BufferLock:
            try:
                status, queue = self.Service.Methods.get_queue()
                if not status:
                    return
            except ConnectionError as err:
                self.debug_print("do_update_queue_view", str(err))
                return
            except Exception as e:
                self.service_status_message(e)
                return

        with self.QueueLock:
            if queue == self.Queue:
                return
            self.Queue = queue.copy()
            gobject.idle_add(self.fill_queue_view, queue)

    def fill_queue_view(self, queue):

        self.QueueStore.clear()
        keys = list(queue.keys())

        if "processing_order" in keys:
            for queue_id in queue['processing_order']:
                item = queue['processing'].get(queue_id)
                if item == None: continue
                item = item.copy()
                item['from'] = "processing"
                self.QueueStore.append((item, item['queue_ts'],))
            if not queue['processing']:
                self.is_processing = None
                self.is_writing_output = False
        else:
            self.is_processing = None
            self.is_writing_output = False

        if "processed_order" in keys:
            mylist = queue['processed_order'][:]
            mylist.reverse()
            for queue_id in mylist:
                item = queue['processed'].get(queue_id)
                if item == None: continue
                item = item.copy()
                item['from'] = "processed"
                self.QueueStore.append((item, item['queue_ts'],))

        if "queue_order" in keys:
            for queue_id in queue['queue_order']:
                item = queue['queue'].get(queue_id)
                if item == None: continue
                item = item.copy()
                item['from'] = "queue"
                self.QueueStore.append((item, item['queue_ts'],))

        if "errored_order" in keys:
            mylist = queue['errored_order'][:]
            mylist.reverse()
            for queue_id in mylist:
                item = queue['errored'].get(queue_id)
                if item == None: continue
                item = item.copy()
                item['from'] = "errored"
                self.QueueStore.append((item, item['queue_ts'],))

        return False

    def update_pinboard_view(self, force = False):

        with self.BufferLock:
            try:
                status, pindata = self.Service.Methods.get_pinboard_data()
            except Exception as e:
                self.service_status_message(e)
                return

        if (pindata == self.PinboardData) and (not force):
            return

        if isinstance(pindata, dict):
            def task(pindata):
                self.fill_pinboard_view(pindata)
                self.PinboardData = pindata.copy()
                return False
            gobject.idle_add(task, pindata)

    def fill_pinboard_view(self, pinboard_data):
        if isinstance(pinboard_data, dict):
            gtk.gdk.threads_enter()
            self.PinboardStore.clear()
            identifiers = sorted(pinboard_data.keys())
            for identifier in identifiers:
                item = pinboard_data[identifier].copy()
                item['pinboard_id'] = identifier
                self.PinboardStore.append((item, item['ts'],))
            gtk.gdk.threads_leave()

    def update_output_view(self, force = False, queue_id = None, n_bytes = 40000):

        def clean_output(myin):
            s = ''
            for x in myin:
                if ord(x) < 8:
                    continue
                s += x
            return s

        with self.OutputLock:

            if self.output_pause and not force: return

            if not queue_id:
                if self.is_processing == None: return
                if not self.is_writing_output: return
                obj = self.is_processing.copy()
                if 'queue_id' not in obj: return
                queue_id = obj['queue_id']

            with self.BufferLock:
                try:
                    status, stdout = self.Service.Methods.get_queue_id_stdout(queue_id, n_bytes)
                except Exception as e:
                    self.service_status_message(e)
                    return

            if not status: return
            stdout = stdout[-1*n_bytes:]
            if (stdout == self.Output) and (not force): return
            self.Output = stdout

            self.clear_console()
            stdout = stdout.replace("\n", "\n\r")
            self.console.feed_child(stdout)

        return False

    def load_queue_info_menu(self, obj):
        my = SmQueueMenu(self.window)
        my.load(obj)

    def clear_data_view(self):
        self.debug_print("clear_data_view", "enter")
        self.setup_data_view()
        ts_mode = self.DataView.get_selection().get_mode()
        if ts_mode != self.data_tree_selection_mode:
            self.DataView.get_selection().set_mode(self.data_tree_selection_mode)
        self.debug_print("clear_data_view", "ts_mode set")
        self.DataView.set_rubber_banding(False)
        self.debug_print("clear_data_view", "rubber banding set")
        self.debug_print("clear_data_view", "exit")

    def collect_data_view_iters(self):
        self.debug_print("collect_data_view_iters", "enter")
        model, paths = self.DataView.get_selection().get_selected_rows()
        if not model:
            self.debug_print("collect_data_view_iters", "quit (nothing)")
            return [], model
        data = []
        for path in paths:
            myiter = model.get_iter(path)
            data.append(myiter)
        self.debug_print("collect_data_view_iters", "quit")
        return data, model

    def wait_queue_id_to_complete(self, queue_id):

        self.debug_print("wait_queue_id_to_complete", "waiting for queue id %s" % (queue_id,))

        key = None
        while key not in ("processed", "errored",):
            item, key = self.get_item_by_queue_id(queue_id)
            time.sleep(0.5)

        with self.BufferLock:
            try:
                rcvd_data = self.Service.Methods.get_queue_id_result(queue_id)
                if rcvd_data is None:
                    raise SystemError("received malformed data")
                status, (result, extended_result,) = rcvd_data
                if not status:
                    return
            except Exception as e:
                self.service_status_message(e)
                return

        self.debug_print("wait_queue_id_to_complete", "done waiting for queue id %s" % (queue_id,))

        item = item.copy()

        if extended_result != None:
            item['result'] = True, extended_result

        if key == "errored":
            return
        return item

    def glsa_data_view(self, data):

        self.debug_print("glsa_data_view", "enter")

        self.clear_data_view()
        self.debug_print("glsa_data_view", "setting GFX")

        self.debug_print("glsa_data_view", "all buttons hidden")
        self.show_data_view_buttons_cat('glsa')
        self.debug_print("glsa_data_view", "all glsa buttons shown")
        self.DataView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.DataView.set_rubber_banding(True)
        self.debug_print("glsa_data_view", "done setting DataView rb")

        self.debug_print("glsa_data_view", "done setting GFX")

        def is_affected(obj):
            if obj['status'] == "[A]":
                return False
            elif obj['status'] == "[N]":
                return True
            else:
                return False

        def my_data_text( column, cell, model, myiter, property ):
            obj = model.get_value( myiter, 0 )
            if obj:
                if property == "glsa_id":
                    cell.set_property('markup', cleanMarkupString(obj['number']))
                elif property == "title":
                    cell.set_property('markup', cleanMarkupString(obj['title']))
                cell.set_property('cell-background', obj['color'])

        def my_data_pix( column, cell, model, myiter ):
            obj = model.get_value( myiter, 0 )
            if obj:
                affected = is_affected(obj)
                if affected:
                    cell.set_property( 'stock-id', 'gtk-cancel' )
                else:
                    cell.set_property( 'stock-id', 'gtk-apply' )
                cell.set_property('cell-background', obj['color'])

        def package_info_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            if model == None: return
            atoms = set()
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                for atom in obj['packages']:
                    for atom_info in obj['packages'][atom]:
                        if 'unaff_atoms' in atom_info:
                            atoms |= set(atom_info['unaff_atoms'])
            if atoms:
                self.on_repoManagerPkgInfo_clicked(None, atoms = atoms, clear = True)

        def adv_info_button_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            if model == None: return
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                my = SecurityAdvisoryMenu(self.window)
                item = obj['number'], is_affected(obj), obj
                my.load(item)

        self.debug_print("glsa_data_view", "done setting functions")
        # Package information
        h1 = self.DataViewButtons['glsa']['package_info_button'].connect('clicked', package_info_clicked)
        # GLSA information button
        h2 = self.DataViewButtons['glsa']['adv_info_button'].connect('clicked', adv_info_button_clicked)
        self.DataViewButtons['glsa']['handler_ids'].extend([h1, h2])
        self.debug_print("glsa_data_view", "done connecting buttons")

        # selection pixmap
        cell = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn( _("Status"), cell )
        column.set_cell_data_func( cell, my_data_pix )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 80 )
        column.set_sort_column_id( -1 )
        self.debug_print("glsa_data_view", "appending status img to DataView")
        self.DataView.append_column( column )

        self.debug_print("glsa_data_view", "creating glsa column")
        # glsa id
        self.create_text_column( self.DataView, _( "GLSA Id." ), 'glsa_id', size = 80, cell_data_func = my_data_text)
        self.debug_print("glsa_data_view", "creating title column")
        # glsa title
        self.create_text_column( self.DataView, _( "Title" ), 'title', size = 300, cell_data_func = my_data_text, expand = True)

        self.debug_print("glsa_data_view", "done setting DataView columns")

        colors = ["#CDEEFF", "#AFCBDA"]
        counter = 0
        for myid in data:
            counter += 1
            obj = data[myid].copy()
            obj['color'] = colors[counter%len(colors)]
            self.DataStore.append( None, (obj,) )

        self.debug_print("glsa_data_view", "done adding to DataStore")
        self.set_notebook_page(self.notebook_pages['data'])
        self.debug_print("glsa_data_view", "done switching page")
        self.show_data_view()
        self.debug_print("glsa_data_view", "done unmasking widgets")
        self.debug_print("glsa_data_view", "exit")
        return False

    def retrieve_entropy_idpackage_data_and_show(self, idpackage, repoid):

        with self.BufferLock:
            try:
                self.debug_print("retrieve_entropy_idpackage_data_and_show",
                    "called for: %s, %s" % (idpackage, repoid,))
                status, package_data = self.Service.Methods.get_entropy_idpackage_information(idpackage, repoid)
                self.debug_print("retrieve_entropy_idpackage_data_and_show",
                    "done for: %s, %s" % (idpackage, repoid,))
                if not status:
                    return
            except Exception as e:
                self.service_status_message(e)
                return

        if not package_data:
            return
        from sulfur.packages import EntropyPackage
        pkg = EntropyPackage((idpackage, repoid,), remote = package_data)
        mymenu = PkgInfoMenu(self.Entropy, pkg, self.window)
        mymenu.load(remote = True)

    def remove_entropy_packages(self, matched_atoms, reload_func = None):

        rc = self.Entropy.ask_question(_("Are you sure you want to remove the selected packages ? (For EVA!)"))
        if rc != _("Yes"):
            return

        rc = self.Entropy.ask_question(_("This is your last chance, are you really really really sure?"))
        if rc != _("Yes"):
            return

        with self.BufferLock:
            try:
                status, msg = self.Service.Methods.remove_entropy_packages(matched_atoms)
            except Exception as e:
                self.service_status_message(e)
                return

        if not status:
            self.service_status_message(msg)
            return

        if status and hasattr(reload_func, '__call__'):
            reload_func()

    def handle_uses_for_atoms(self, atoms, use):

        def fake_callback(s):
            return s

        input_params = []
        data = {}
        data['atoms'] = atoms
        data['use'] = use
        if not atoms:
            input_params.append(('atoms', _('Atoms, space separated'), fake_callback, False),)
        if not use:
            input_params.append(('use', _('USE flags, space separated'), fake_callback, False),)
        if input_params:
            mydata = self.Entropy.input_box(
                _('Insert command parameters'),
                input_params,
                cancel_button = True
            )
            if mydata == None:
                return
            data.update(mydata)
            if not atoms:
                data['atoms'] = data['atoms'].split()
            if not use:
                data['use'] = data['use'].split()
        return data

    def run_get_notice_board(self, repoid):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.get_noticeboard(repoid)
            except Exception as e:
                self.service_status_message(e)
                return

        def task(queue_id, repoid):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None:
                return
            status, repo_data = item['result']
            if not status:
                return
            self.update_notice_board_data_view(repo_data, repoid)

        if status:
            t = ParallelTask(task, queue_id, repoid)
            t.start()

    def run_write_to_running_command_pipe(self, queue_id, write_to_stdout, txt):

        with self.BufferLock:
            try:
                status, data = self.Service.Methods.write_to_running_command_pipe(queue_id, write_to_stdout, txt)
            except Exception as e:
                self.service_status_message(e)
                return

    def run_remove_from_pinboard(self, remove_ids):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.remove_from_pinboard(remove_ids)
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.on_repoManagerPinboardRefreshButton_clicked(None)

    def run_add_to_pinboard(self, note, extended_text):

        with self.BufferLock:
            try:
                status, err_msg = self.Service.Methods.add_to_pinboard(note, extended_text)
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.on_repoManagerPinboardRefreshButton_clicked(None)
        else:
            self.service_status_message(err_msg)

    def run_run_custom_shell_command(self, command):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.run_custom_shell_command(command)
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.is_writing_output = True
            self.is_processing = {'queue_id': queue_id}
            self.set_notebook_page(self.notebook_pages['output'])

    def run_get_spm_categories_installed(self, categories, world):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.get_spm_categories_installed(categories)
            except Exception as e:
                self.service_status_message(e)
                return

        def task(queue_id, categories, world):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None:
                return
            status, data = item['result']
            if not status:
                return
            def reload_function():
                self.on_repoManagerInstalledPackages_clicked(None,
                    categories = categories, world = world)
                return False
            gobject.idle_add(self.categories_updates_data_view, data,
                categories, True, reload_function)

        if status:
            t = ParallelTask(task, queue_id, categories, world)
            t.start()

    def run_sync_spm(self):

        with self.BufferLock:
            try:
                status, data = self.Service.Methods.sync_spm()
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.set_notebook_page(self.notebook_pages['output'])

    def run_spm_remove_atoms(self, data):

        def task(data):

            with self.BufferLock:
                try:
                    status, queue_id = self.Service.Methods.spm_remove_atoms(
                        data['atoms'],
                        data['pretend'],
                        data['verbose'],
                        data['nocolor'],
                    )
                except Exception as e:
                    self.service_status_message(e)
                    return

            if status:
                self.is_writing_output = True
                self.is_processing = {'queue_id': queue_id}
                self.set_notebook_page(self.notebook_pages['output'])

        t = ParallelTask(task, data)
        t.start()

    def run_compile_atoms(self, data):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.compile_atoms(
                    data['atoms'],
                    data['pretend'],
                    data['oneshot'],
                    data['verbose'],
                    data['nocolor'],
                    data['fetchonly'],
                    data['buildonly'],
                    data['nodeps'],
                    data['custom_use'],
                    data['ldflags'],
                    data['cflags'],
                )
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.is_writing_output = True
            self.is_processing = {'queue_id': queue_id}
            self.set_notebook_page(self.notebook_pages['output'])

    def run_spm_info(self):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.run_spm_info()
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.is_writing_output = True
            self.is_processing = {'queue_id': queue_id}
            self.set_notebook_page(self.notebook_pages['output'])

    # fine without ParallelTask
    def run_enable_uses_for_atoms(self, atoms, use, load_view):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.enable_uses_for_atoms(atoms, use)
            except Exception as e:
                self.service_status_message(e)
                return

        if load_view and status:
            self.on_repoManagerPkgInfo_clicked(None, atoms = atoms)

        return status

    # fine without ParallelTask
    def run_disable_uses_for_atoms(self, atoms, use, load_view):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.disable_uses_for_atoms(atoms, use)
            except Exception as e:
                self.service_status_message(e)
                return

        if load_view and status:
            self.clear_data_store_and_view()
            self.on_repoManagerPkgInfo_clicked(None, atoms = atoms)
        return status

    def run_get_spm_atoms_info(self, categories, atoms, clear):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.get_spm_atoms_info(atoms)
            except Exception as e:
                self.service_status_message(e)
                return

        def task(categories, atoms):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None: return
            status, data = item['result']
            if not status: return
            def reload_function():
                self.on_repoManagerPkgInfo_clicked(None, atoms = atoms, clear = clear)
            gobject.idle_add(self.categories_updates_data_view, data,
                categories, True, reload_function)

        if status:
            t = ParallelTask(task, categories, atoms)
            t.start()

    def run_kill_processing_queue_id(self, queue_id):

        with self.BufferLock:
            try:
                self.Service.Methods.kill_processing_queue_id(queue_id)
            except Exception as e:
                self.service_status_message(e)
                return

    def run_remove_queue_ids(self, queue_ids):

        with self.BufferLock:
            try:
                self.Service.Methods.remove_queue_ids(queue_ids)
            except Exception as e:
                self.service_status_message(e)
                return

    def run_spm_categories_updates(self, categories, expand):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.get_spm_categories_updates(categories)
            except Exception as e:
                self.service_status_message(e)
                return

        def task(queue_id, categories, expand):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None: return
            status, data = item['result']
            if not status: return
            gobject.idle_add(self.categories_updates_data_view, data,
                categories, expand)

        if status:
            t = ParallelTask(queue_id, task, categories, expand)
            t.start()

    def run_entropy_deptest(self):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.run_entropy_dependency_test()
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.is_writing_output = True
            self.is_processing = {'queue_id': queue_id }
            self.set_notebook_page(self.notebook_pages['output'])
        else:
            self.service_status_message(queue_id)

    def run_entropy_treeupdates(self, repoid):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.run_entropy_treeupdates(repoid)
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.is_writing_output = True
            self.is_processing = {'queue_id': queue_id }
            self.set_notebook_page(self.notebook_pages['output'])
        else:
            self.service_status_message(queue_id)

    def run_entropy_checksum_test(self, repoid, mode):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.run_entropy_checksum_test(repoid, mode)
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.is_writing_output = True
            self.is_processing = {'queue_id': queue_id }
            self.set_notebook_page(self.notebook_pages['output'])
        else:
            self.service_status_message(queue_id)

    def run_entropy_mirror_updates(self, repos):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.scan_entropy_mirror_updates(repos)
            except Exception as e:
                self.service_status_message(e)
                return

        def task(queue_id, repos):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None: return
            status, repo_data = item['result']
            if not status: return
            gobject.idle_add(self.entropy_mirror_updates_data_view,
                repo_data)

        if status:
            t = ParallelTask(task, queue_id, repos)
            t.start()
        else:
            self.service_status_message(queue_id)

    def execute_entropy_mirror_updates(self, repo_data):

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.run_entropy_mirror_updates(repo_data)
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            self.is_writing_output = True
            self.is_processing = {'queue_id': queue_id }
            self.set_notebook_page(self.notebook_pages['output'])
        else:
            self.service_status_message(queue_id)

    def run_entropy_libtest(self):

        with self.BufferLock:
            status = False
            data = {}
            try:
                status, queue_id = self.Service.Methods.run_entropy_library_test()
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            # enable output
            self.is_writing_output = True
            self.is_processing = {'queue_id': queue_id }
            self.set_notebook_page(self.notebook_pages['output'])
        else:
            self.service_status_message(queue_id)

    def run_package_search(self, search_type, search_string, repoid):

        with self.BufferLock:
            try:
                status, data = self.Service.Methods.search_entropy_packages(search_type, search_string, repoid)
            except Exception as e:
                self.service_status_message(e)
                return

        if status:
            def reload_func():
                self.run_package_search(search_type, search_string, repoid)
            gobject.idle_add(self.entropy_available_packages_data_view,
                data, repoid, reload_func)
        else:
            self.service_status_message(data)

    def move_entropy_packages(self, matches, reload_function):

        idpackages = []
        repoids = set()
        for idpackage, repoid in matches:
            repoids.add(repoid)
            idpackages.append(idpackage)

        if len(repoids) > 1:
            self.service_status_message(_("Cannot move/copy packages from different repositories"))
            return

        from_repo = list(repoids)[0]

        avail_repos = list(self.EntropyRepositories['available'].keys())
        if not avail_repos: return

        def fake_callback_repos(s):
            entryid, myrepoid = s
            if myrepoid == from_repo:
                return False
            return True

        def fake_callback_cb(s):
            return True

        input_params = [
            ('to_repo', ('combo', (_('To repository'), avail_repos),), fake_callback_repos, False),
            ('do_copy', ('checkbox', _('Execute copy'),), fake_callback_cb, False),
        ]
        data = self.Entropy.input_box(
            _('Entropy packages move/copy'),
            input_params,
            cancel_button = True
        )
        if data == None: return

        data['to_repo'] = data['to_repo'][1]

        with self.BufferLock:
            status = False
            try:
                status, queue_id = self.Service.Methods.move_entropy_packages_to_repository(idpackages, from_repo, data['to_repo'], do_copy = data['do_copy'])
            except Exception as e:
                self.service_status_message(e)
                return

        if not status:
            self.service_status_message(queue_id)
            return

        self.reload_after_package_move(queue_id, reload_function)


    def reload_after_package_move(self, queue_id, reload_func):

        def task(queue_id, reload_func):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None: return
            status, data = item['result']
            if not status: return
            gobject.idle_add(reload_func)

        t = ParallelTask(task, queue_id, reload_func)
        t.start()

    def run_entropy_database_updates_scan(self):

        with self.BufferLock:
            status = False
            data = {}
            try:
                status, queue_id = self.Service.Methods.scan_entropy_packages_database_changes()
            except Exception as e:
                self.service_status_message(e)
                return

        def task(queue_id):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None:
                return
            status, data = item['result']
            if not status:
                return
            gobject.idle_add(self.entropy_database_updates_data_view,
                data)

        if status:
            t = ParallelTask(task, queue_id)
            t.start()
        else:
            self.service_status_message(queue_id)

    def run_entropy_database_updates(self, to_add, to_remove, to_inject, reload_func = None):

        if reload_func == None:
            def reload_func():
                return False

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.run_entropy_database_updates(to_add, to_remove, to_inject)
            except Exception as e:
                self.service_status_message(e)
                return

        def task(queue_id, reload_func):
            self.reload_after_package_move(queue_id, reload_func)

        if status:
            self.is_writing_output = True
            self.is_processing = {'queue_id': queue_id }
            self.set_notebook_page(self.notebook_pages['output'])
            t = ParallelTask(task, queue_id, reload_func)
            t.start()
        else:
            self.service_status_message(queue_id)

    def run_add_notice_board_entry(self, repoid, title, notice_text, link, reload_func = None):

        if reload_func == None:
            def reload_func():
                return False

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.add_notice_board_entry(repoid, title, notice_text, link)
            except Exception as e:
                self.service_status_message(e)
                return

        def task(queue_id, repoid, title, notice_text, link, reload_func):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None: return
            status, result = item['result']
            if not status: return
            gobject.idle_add(reload_func)

        if status:
            t = ParallelTask(task, queue_id, repoid, title, notice_text, link, reload_func)
            t.start()

    def run_remove_notice_board_entries(self, repoid, ids, reload_func = None):

        if reload_func == None:
            def reload_func():
                return False

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.remove_notice_board_entries(repoid, list(ids))
            except Exception as e:
                self.service_status_message(e)
                return

        def task(queue_id, repoid, ids, reload_func):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None: return
            status, result = item['result']
            if not status: return
            gobject.idle_add(reload_func)

        if status:
            t = ParallelTask(task, queue_id, repoid, ids, reload_func)
            t.start()

    def update_notice_board_data_view(self, repo_data, repoid):

        self.clear_data_view()
        self.show_data_view_buttons_cat('notice_board')
        self.DataView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.DataView.set_rubber_banding(True)

        def my_data_text( column, cell, model, myiter, property ):
            obj = model.get_value( myiter, 0 )
            if obj:
                mytxt = '<b><u>%s</u></b>\n<small><b>%s</b>: %s</small>' % (
                    cleanMarkupString(obj['pubDate']),
                    _("Title"),
                    cleanMarkupString(obj['title']),
                )
                cell.set_property('markup', mytxt)
                cell.set_property('cell-background', obj['color'])

        def add_button_clicked(widget):

            def fake_callback(s):
                return s

            input_params = [
                ('title', _('Notice title'), fake_callback, False),
                ('link', _('Link (URL)'), fake_callback, False),
                ('notice_text', ("text", _('Notice text'),), fake_callback, False),
            ]
            data = self.Entropy.input_box(
                _('Insert your new notice board entry'),
                input_params,
                cancel_button = True
            )
            if data == None: return
            def reload_func():
                self.on_repoManagerNoticeBoardButton_clicked(None, repoid = repoid)
            self.run_add_notice_board_entry(repoid, data['title'], data['notice_text'], data['link'], reload_func)

        def remove_button_clicked(widget):

            myiters, model = self.collect_data_view_iters()
            if model == None: return
            ids = set()
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                ids.add(obj['id'])
            if ids:
                def reload_func():
                    self.on_repoManagerNoticeBoardButton_clicked(None, repoid = repoid)
                self.run_remove_notice_board_entries(repoid, ids, reload_func)

        def refresh_button_clicked(widget):
            self.on_repoManagerNoticeBoardButton_clicked(None, repoid = repoid)

        def view_button_clicked(widget):

            myiters, model = self.collect_data_view_iters()
            if model == None: return

            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                my = RmNoticeBoardMenu(self.window)
                my.load(obj)

        h1 = self.DataViewButtons['notice_board']['add_button'].connect('clicked', add_button_clicked)
        h2 = self.DataViewButtons['notice_board']['remove_button'].connect('clicked', remove_button_clicked)
        h3 = self.DataViewButtons['notice_board']['refresh_button'].connect('clicked', refresh_button_clicked)
        h4 = self.DataViewButtons['notice_board']['view_button'].connect('clicked', view_button_clicked)
        self.DataViewButtons['notice_board']['handler_ids'].extend([h1, h2, h3, h4])

        self.create_text_column( self.DataView, _( "Notice board" ), 'nb', size = 300, cell_data_func = my_data_text, expand = True, set_height = 36)
        self.fill_notice_board_view(repo_data)

        self.set_notebook_page(self.notebook_pages['data'])
        self.show_data_view()

    def fill_notice_board_view(self, repo_data):
        colors = ["#CDEEFF", "#AFCBDA"]
        counter = 0
        items, lenght = repo_data
        keys = sorted(items.keys())
        for key in keys:
            counter += 1
            item = items[key].copy()
            item['color'] = colors[counter%len(colors)]
            item['id'] = key
            self.DataStore.append( None, (item,) )


    def entropy_mirror_updates_data_view(self, repo_data):

        self.clear_data_view()
        self.show_data_view_buttons_cat('mirror_updates')
        self.DataView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.DataView.set_rubber_banding(True)

        def my_data_text( column, cell, model, myiter, property ):
            obj = model.get_value( myiter, 0 ) # cleanMarkupString
            if obj:
                if 'is_master' in obj:
                    if obj['from'] == "repoid":
                        cell.set_property('markup', "<big><b>%s</b>: <i>%s</i></big>" % (_("Repository"), cleanMarkupString(obj['text']),))
                    elif obj['from'] == "pkg_master":
                        cell.set_property('markup', "<b>%s</b>: <i>%s</i>" % (_("Action"), cleanMarkupString(obj['text']),))
                    elif obj['from'] == "uri":
                        cell.set_property('markup', "<b>%s</b>: <u>%s</u>" % (_("Server"), cleanMarkupString(obj['text']),))
                    elif obj['from'] == "db":
                        yes = _("Yes")
                        no = _("No")
                        up_action = yes
                        if not obj['upload_queue']: up_action = no
                        down_action = yes
                        if not obj['download_latest']: down_action = no
                        cell.set_property('markup', "<b>%s</b>: %s: %s, %s: %s, %s: %s, %s: %s" % (
                                _("Database"),
                                _("current revision"),
                                obj['current_revision'],
                                _("remote revision"),
                                obj['remote_revision'],
                                _("upload"),
                                up_action,
                                _("download"),
                                down_action,
                            )
                        )
                else:
                    if obj['from'] == "pkg":
                        cell.set_property('markup', "%s [%s]" % (cleanMarkupString(obj['filename']), cleanMarkupString(obj['size']),))

                cell.set_property('cell-background', obj['color'])

        def execute_button_clicked(widget):

            def fake_callback(s):
                return s

            input_params = [
                ('exec_type', ('combo', (_('Execution mode'), [_("Execute all"), _("Execute only selected")]),), fake_callback, False)
            ]
            mydata = self.Entropy.input_box(
                _('Choose the execution mode'),
                input_params,
                cancel_button = True
            )
            if mydata == None: return
            myiters = []
            if mydata['exec_type'][0] == 0:
                self.DataView.get_selection().select_all()
            myiters, model = self.collect_data_view_iters()
            if model == None: return

            objects = []
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                #if not obj.has_key('is_master'): continue
                objects.append(obj)

            run_data = {}
            for obj in objects:
                repoid, dbsync, pkgsync = obj['run']
                if repoid in run_data: continue
                run_data[repoid] = {
                    'db': dbsync,
                    'pkg': pkgsync,
                    'pretend': True,
                    'mirrors': [],
                }
            if not run_data: return

            def fake_callback_cb(s):
                return True

            def fake_callback(s):
                return True

            # now ask for mirrors
            for repoid in list(run_data.keys()):

                input_params = [
                    ('commit_msg', _("Commit message"), fake_callback, False,),
                    ('do_pretend', ('checkbox', _("Pretend mode"),), fake_callback_cb, False,),
                    ('pkg_check', ('checkbox', _("Packages check"),), fake_callback_cb, False,),
                ]

                data = self.Entropy.input_box(
                    "[%s] %s" % (repoid, _('Choose sync options'),),
                    input_params,
                    cancel_button = True
                )
                if data == None:
                    run_data.pop(repoid)
                    continue

                run_data[repoid]['pretend'] = data['do_pretend']
                run_data[repoid]['pkg_check'] = data['pkg_check']
                run_data[repoid]['commit_msg'] = data['commit_msg']

            if run_data:
                self.clear_data_store_and_view()
                t = ParallelTask(self.execute_entropy_mirror_updates, run_data)
                t.start()

        h1 = self.DataViewButtons['mirror_updates']['execute_button'].connect('clicked', execute_button_clicked)
        self.DataViewButtons['mirror_updates']['handler_ids'].extend([h1])

        self.create_text_column( self.DataView, _( "Mirror updates information" ), 'info', size = 300, cell_data_func = my_data_text, expand = True)
        self.fill_mirror_updates_view(repo_data)
        self.set_notebook_page(self.notebook_pages['data'])
        self.show_data_view()
        return False

    def entropy_database_updates_data_view(self, data):

        self.clear_data_view()
        self.show_data_view_buttons_cat('database_updates')
        self.DataView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.DataView.set_rubber_banding(True)

        def my_data_text( column, cell, model, myiter, property ):
            obj = model.get_value( myiter, 0 )
            if obj:
                if property == "package":
                    is_cat = False
                    if 'is_master' in obj:
                        is_cat = True
                    if is_cat:
                        mytxt = "<big><b>%s</b></big>" % (obj['text'],)
                        cell.set_property('markup', mytxt)
                    elif obj['from'] == "add":
                        self.spm_package_obj_to_cell(obj, cell)
                    else:
                        self.entropy_package_obj_to_cell(obj, cell)

                elif property == "repoid":
                    if 'repoid' in obj:
                        cell.set_property('markup', "<small>%s</small>" % (cleanMarkupString(obj['repoid']),))
                    else:
                        cell.set_property('markup', '')

                elif property == "toggle":
                    cell.set_active(obj['select'])

                cell.set_property('cell-background', obj['color'])

        def package_info_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            if model == None: return
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                if 'is_master' in obj: continue
                if obj['from'] != "add":
                    self.retrieve_entropy_idpackage_data_and_show(obj['idpackage'], obj['repoid'])

        def change_repo_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            if model == None: return

            avail_repos = list(self.EntropyRepositories['available'].keys())
            if not avail_repos: return

            def fake_callback(s):
                return s

            input_params = [
                ('repoid', ('combo', (_('Repository'), avail_repos),), fake_callback, False)
            ]

            objects = []
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                if 'is_master' in obj: continue
                if obj['from'] != "add": continue
                objects.append(obj)

            if objects:
                mydata = self.Entropy.input_box(
                    _('Choose the destination repository'),
                    input_params,
                    cancel_button = True
                )
                if mydata == None: return
                to_repoid = mydata['repoid'][1]
                for obj in objects:
                    obj['repoid'] = to_repoid

                self.DataView.queue_draw()

        def execute_button_clicked(widget):

            def fake_callback(s):
                return s

            input_params = [
                ('exec_type', ('combo', (_('Execution mode'), [_("Execute all"), _("Execute only selected")]),), fake_callback, False)
            ]
            mydata = self.Entropy.input_box(
                _('Choose the execution mode'),
                input_params,
                cancel_button = True
            )
            if mydata == None: return
            myiters = []
            if mydata['exec_type'][0] == 0:
                self.DataView.get_selection().select_all()
            myiters, model = self.collect_data_view_iters()
            if model == None: return

            objects = []
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                if 'is_master' in obj: continue
                objects.append(obj)

            to_add = []
            to_remove = []
            to_inject = []
            for obj in objects:
                if obj['from'] == "add":
                    to_add.append(obj['match_key']+(obj['repoid'],))
                elif obj['from'] == "remove":
                    to_remove.append(obj['match_key'])
                elif obj['from'] == "inject":
                    to_inject.append(obj['match_key'])

            if to_add or to_remove or to_inject:
                def reload_func():
                    self.on_repoManagerEntropyDbUpdatesButton_clicked(None)
                self.clear_data_store_and_view()
                self.run_entropy_database_updates(to_add, to_remove, to_inject, reload_func)


        h1 = self.DataViewButtons['database_updates']['change_repo_button'].connect('clicked', change_repo_clicked)
        h2 = self.DataViewButtons['database_updates']['package_info_button'].connect('clicked', package_info_clicked)
        h3 = self.DataViewButtons['database_updates']['execute_button'].connect('clicked', execute_button_clicked)
        self.DataViewButtons['database_updates']['handler_ids'].extend([h1, h2, h3])

        cell_height = 80

        # package
        self.create_text_column( self.DataView, _( "Package" ), 'package', size = 300, set_height = cell_height, cell_data_func = my_data_text, expand = True)
        # repository
        self.create_text_column( self.DataView, _( "Repository" ), 'repoid', size = 130, set_height = cell_height, cell_data_func = my_data_text)
        self.fill_db_updates_view(data)
        self.set_notebook_page(self.notebook_pages['data'])
        self.show_data_view()
        return False


    def fill_db_updates_view(self, data):

        master_add = {
            'is_master': True,
            'type': "add",
            'text': _("To be added"),
            'color': '#CDEEFF',
            'select': True,
        }
        master_remove = {
            'is_master': True,
            'type': "remove",
            'text': _("To be removed"),
            'color': '#CDEEFF',
            'select': True,
        }
        master_inject = {
            'is_master': True,
            'type': "inject",
            'text': _("To be injected"),
            'color': '#CDEEFF',
            'select': True,
        }

        add_cats_data = {}
        for spm_atom, spm_counter in data['add_data']:
            cat = entropy.tools.dep_getkey(spm_atom).split("/")[0]
            if cat not in add_cats_data:
                add_cats_data[cat] = []
            item = data['add_data'][(spm_atom, spm_counter,)]
            item['repoid'] = self.EntropyRepositories['current']
            item['select'] = True
            item['match_key'] = (spm_atom, spm_counter,)
            add_cats_data[cat].append(item)

        remove_cats_data = {}
        for idpackage, repoid in data['remove_data']:
            if (idpackage, repoid,) not in data['remove_data']:
                continue
            item = data['remove_data'][(idpackage, repoid,)]
            if not item: continue
            item['select'] = True
            item['match_key'] = (idpackage, repoid,)
            cat = item['category']
            if cat not in remove_cats_data:
                remove_cats_data[cat] = []
            remove_cats_data[cat].append(item)

        inject_cats_data = {}
        for idpackage, repoid in data['inject_data']:
            if (idpackage, repoid,) not in data['inject_data']:
                continue
            item = data['inject_data'][(idpackage, repoid,)]
            if not item: continue
            item['select'] = True
            item['match_key'] = (idpackage, repoid,)
            cat = item['category']
            if cat not in inject_cats_data:
                inject_cats_data[cat] = []
            inject_cats_data[cat].append(item)

        colors = ["#CDEEFF", "#AFCBDA"]
        cat_counter = 0
        counter = 0
        add_cat_keys = sorted(add_cats_data.keys())
        remove_cat_keys = sorted(remove_cats_data.keys())
        inject_cat_keys = sorted(inject_cats_data.keys())

        # first add
        if add_cats_data: add_parent = self.DataStore.append( None, (master_add,) )
        if remove_cats_data: remove_parent = self.DataStore.append( None, (master_remove,) )
        if inject_cats_data: inject_parent = self.DataStore.append( None, (master_inject,) )

        for category in add_cat_keys:
            cat_counter += 1
            mydict = {
                'color': colors[cat_counter%len(colors)],
                'is_master': True,
                'type': "category",
                'text': category,
                'select': True,
            }
            myparent = self.DataStore.append( add_parent, (mydict,) )
            for item in add_cats_data[category]:
                counter += 1
                item['color'] = colors[counter%len(colors)]
                item['from'] = 'add'
                item['select'] = True
                self.DataStore.append( myparent, (item,) )

        cat_counter = 0
        counter = 0
        for category in remove_cat_keys:
            cat_counter += 1
            mydict = {
                'color': colors[cat_counter%len(colors)],
                'is_master': True,
                'type': "category",
                'text': category,
                'select': True,
            }
            myparent = self.DataStore.append( remove_parent, (mydict,) )
            for item in remove_cats_data[category]:
                counter += 1
                item['color'] = colors[counter%len(colors)]
                item['from'] = 'remove'
                item['select'] = True
                self.DataStore.append( myparent, (item,) )

        cat_counter = 0
        counter = 0
        for category in inject_cat_keys:
            cat_counter += 1
            mydict = {
                'color': colors[cat_counter%len(colors)],
                'is_master': True,
                'type': "category",
                'text': category,
                'select': True,
            }
            myparent = self.DataStore.append( inject_parent, (mydict,) )
            for item in inject_cats_data[category]:
                counter += 1
                item['color'] = colors[counter%len(colors)]
                item['from'] = 'inject'
                item['select'] = True
                self.DataStore.append( myparent, (item,) )

        self.DataView.expand_all()


    def fill_mirror_updates_view(self, data):

        color_odd = '#FFF7C2'
        color_even = '#E6FFCA'


        repos = list(data.keys())
        for repoid in repos:
            color = color_odd
            master = {
                'is_master': True,
                'text': repoid,
                'from': "repoid",
                'color': color,
                'repoid': repoid,
                'run': (repoid, True, True,) # repoid, dbsync, pkgsync
            }
            parent = self.DataStore.append( None, (master,))

            for uri in data[repoid]:

                color = color_odd
                if 'packages' not in data[repoid][uri]:
                    color = color_even

                uri_master = {
                    'is_master': True,
                    'text': uri,
                    'from': "uri",
                    'color': color,
                    'repoid': repoid,
                    'run': (repoid, True, True,) # repoid, dbsync, pkgsync
                }
                uri_parent = self.DataStore.append( parent, (uri_master,))

                # db
                db_item = data[repoid][uri]['database']
                db_color = "#FFF7C2"
                if db_item['remote_revision'] == db_item['current_revision']:
                    db_color = "#E6FFCA"
                db_item['color'] = db_color
                db_item['from'] = "db"
                db_item['is_master'] = True
                db_item['repoid'] = repoid
                db_item['run'] = (repoid, True, True,) # repoid, dbsync, pkgsync

                self.DataStore.append( uri_parent, (db_item,))
                if 'packages' in data[repoid][uri]:

                    for action in data[repoid][uri]['packages']:

                        if data[repoid][uri]['packages'][action]:
                            pkgmaster = {
                                'is_master': True,
                                'text': action,
                                'from': "pkg_master",
                                'color': color,
                                'repoid': repoid,
                                'run': (repoid, False, True,)
                            }
                            pkg_parent = self.DataStore.append( uri_parent, (pkgmaster,))

                        for mypath, mysize in data[repoid][uri]['packages'][action]:
                            pkg_item = {
                                'from': "pkg",
                                'filename': os.path.basename(mypath),
                                'size': entropy.tools.bytes_into_human(mysize),
                                'color': color,
                                'repoid': repoid,
                                'run': (repoid, False, True,)
                            }
                            self.DataStore.append( pkg_parent, (pkg_item,))

        self.DataView.expand_all()


    def entropy_available_packages_data_view(self, packages_data, repoid, reload_func = None):

        if not isinstance(packages_data, dict):
            return

        if reload_func == None:
            def reload_func():
                self.on_repoManagerAvailablePackagesButton_clicked(None, repoid = repoid)

        self.clear_data_view()
        self.show_data_view_buttons_cat('available_packages')
        self.DataView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.DataView.set_rubber_banding(True)

        def my_data_text( column, cell, model, myiter, property ):
            obj = model.get_value( myiter, 0 )
            if obj:
                if property == "package":
                    is_cat = False
                    if 'is_cat' in obj:
                        is_cat = True
                    if is_cat:
                        mytxt = "<big><b>%s</b></big>" % (obj['name'],)
                        cell.set_property('markup', mytxt)
                    else:
                        self.entropy_package_obj_to_cell(obj, cell)
                elif property == "repoid":
                    cell.set_property('markup', "<small>%s</small>" % (cleanMarkupString(obj['repoid']),))
                cell.set_property('cell-background', obj['color'])

        def package_info_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            if model == None: return
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                if 'is_cat' in obj: continue
                self.retrieve_entropy_idpackage_data_and_show(obj['idpackage'], obj['repoid'])

        def remove_package_button_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            if model == None: return
            items = []
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                if 'is_cat' in obj: continue
                items.append((obj['idpackage'], obj['repoid'],))
            if items:
                self.remove_entropy_packages(items, reload_func = reload_func)

        def move_package_button_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            if model == None: return
            items = []
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                if 'is_cat' in obj: continue
                items.append((obj['idpackage'], obj['repoid'],))
            if items:
                self.move_entropy_packages(items, reload_func)


        h1 = self.DataViewButtons['available_packages']['package_info_button'].connect('clicked', package_info_clicked)
        h2 = self.DataViewButtons['available_packages']['remove_package_button'].connect('clicked', remove_package_button_clicked)
        h3 = self.DataViewButtons['available_packages']['move_package_button'].connect('clicked', move_package_button_clicked)
        self.DataViewButtons['available_packages']['handler_ids'].extend([h1, h2, h3])

        # glsa id
        self.create_text_column( self.DataView, _( "Package" ), 'package', size = 300, set_height = 60, cell_data_func = my_data_text, expand = True)

        # glsa title
        self.create_text_column( self.DataView, _( "Repository" ), 'repoid', size = 130, set_height = 60, cell_data_func = my_data_text)

        cats_data = {}
        for idpackage in packages_data['ordered_idpackages']:
            item = packages_data['data'].get(idpackage)
            if item == None: continue
            mycat = item['category']
            if mycat not in cats_data:
                cats_data[mycat] = []
            cats_data[mycat].append(item)

        colors = ["#CDEEFF", "#AFCBDA"]
        counter = 0
        cat_keys = sorted(cats_data.keys())

        for category in cat_keys:
            counter += 1
            mydict = {
                'is_cat': True,
                'name': category,
                'color': colors[0],
                'repoid': repoid,
            }
            parent = self.DataStore.append( None, (mydict,) )
            for item in cats_data[category]:
                counter += 1
                item['color'] = colors[counter%len(colors)]
                item['repoid'] = repoid
                self.DataStore.append( parent, (item,) )

        self.set_notebook_page(self.notebook_pages['data'])
        self.show_data_view()
        return False


    def categories_updates_data_view(self, data, categories, expand = False, reload_function = None):

        if reload_function == None:
            def reload_function():
                self.on_repoManagerCategoryUpdButton_clicked(None, categories = categories, expand = True)
                return False

        self.clear_data_view()
        self.show_data_view_buttons_cat('categories_updates')
        self.DataView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.DataView.set_rubber_banding(True)

        def my_data_text( column, cell, model, myiter, property ):
            obj = model.get_value( myiter, 0 )
            if obj:
                if 'is_cat' in obj:
                    txt = "<big><b>%s</b></big>" % (obj['name'],)
                    cell.set_property('markup', txt)
                else:
                    self.spm_package_obj_to_cell(obj, cell)
                cell.set_property('cell-background', obj['color'])

        def compile_button_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            atoms = []
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                if obj:
                    if 'available_atom' in obj:
                        if not obj['available_atom']:
                            continue
                        atom = obj['available_atom']
                    else:
                        atom = obj['atom']
                    atoms.append("="+atom)
            if atoms:
                self.on_compileAtom_clicked(None, atoms)

        def add_use_button_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            atoms = []
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                if 'key' in obj and 'slot' in obj:
                    atom_string = "%s:%s" % (obj['key'], obj['slot'],)
                    atoms.append(atom_string)
            if atoms:
                status = self.on_addUseAtom_clicked(None, atoms = atoms, load_view = False, parallel = False)
                if status:
                    gobject.idle_add(reload_function)

        def remove_use_button_clicked(widget):
            myiters, model = self.collect_data_view_iters()
            atoms = []
            for myiter in myiters:
                obj = model.get_value(myiter, 0)
                if 'key' in obj and 'slot' in obj:
                    atom_string = "%s:%s" % (obj['key'], obj['slot'],)
                    atoms.append(atom_string)
            if atoms:
                status = self.on_removeUseAtom_clicked(None, atoms = atoms, load_view = False, parallel = False)
                if status:
                    gobject.idle_add(reload_function)

        h1 = self.DataViewButtons['categories_updates']['compile_button'].connect('clicked', compile_button_clicked)
        h2 = self.DataViewButtons['categories_updates']['add_use_button'].connect('clicked', add_use_button_clicked)
        h3 = self.DataViewButtons['categories_updates']['remove_use_button'].connect('clicked', remove_use_button_clicked)
        self.DataViewButtons['categories_updates']['handler_ids'].extend([h1, h2, h3])

        # atom
        self.create_text_column( self.DataView, _( "Atom" ), 'atom', size = 220, cell_data_func = my_data_text, set_height = 150, expand = True)

        colors = ["#D2FFB9", "#B0D69B"]

        counter = 0
        for category in data:
            counter += 1
            master = {'is_cat': True, 'name': category, 'color': colors[counter%len(colors)]}
            parent = self.DataStore.append( None, (master,) )
            for atom in data[category]:
                counter += 1
                obj = data[category][atom].copy()
                obj['atom'] = atom
                obj['color'] = colors[counter%len(colors)]
                self.DataStore.append( parent, (obj,) )
        if expand:
            self.DataView.expand_all()

        self.set_notebook_page(self.notebook_pages['data'])
        self.show_data_view()
        return False

    def on_repoManagerQueueDown_clicked(self, widget):

        ( model, iterator ) = self.QueueView.get_selection().get_selected()
        if not iterator: return

        next_iterator = model.iter_next(iterator)
        if iterator and next_iterator:
            item1 = model.get_value(iterator, 0)
            item2 = model.get_value(next_iterator, 0)
            if item1 and item2:
                item1 = item1.copy()
                item2 = item2.copy()
                def task():
                    with self.BufferLock:
                        try:
                            status, msg = self.Service.Methods.swap_items_in_queue(item1['queue_id'], item2['queue_id'])
                            self.debug_print("on_repoManagerQueueDown_clicked", "%s, %s" % (status, msg,))
                            self.debug_print("on_repoManagerQueueDown_clicked", "%s, %s" % (item1, item2,))
                            if status:
                                self.QueueStore.swap(iterator, next_iterator)
                        except Exception as e:
                            self.service_status_message(e)
                            return
                    self.update_queue_view()
                t = ParallelTask(task)
                t.start()

    def on_repoManagerQueueUp_clicked(self, widget):

        ( model, next_iterator ) = self.QueueView.get_selection().get_selected()
        if not next_iterator: return

        path = model.get_path(next_iterator)[0]
        iterator = model.get_iter(path-1)

        if iterator and next_iterator:
            item1 = model.get_value(iterator, 0)
            item2 = model.get_value(next_iterator, 0)
            if item1 and item2:
                item1 = item1.copy()
                item2 = item2.copy()
                def task():
                    with self.BufferLock:
                        try:
                            status, msg = self.Service.Methods.swap_items_in_queue(item1['queue_id'], item2['queue_id'])
                            self.debug_print("on_repoManagerQueueUp_clicked", "%s, %s" % (status, msg,))
                            self.debug_print("on_repoManagerQueueUp_clicked", "%s, %s" % (item1, item2,))
                            if status:
                                self.QueueStore.swap(iterator, next_iterator)
                        except Exception as e:
                            self.service_status_message(e)
                            return
                    self.update_queue_view()
                t = ParallelTask(task)
                t.start()

    def on_repoManagerCategoryUpdButton_clicked(self, widget, categories = [], expand = False):

        def fake_callback(s):
            return s

        input_params = []
        if not categories:
            input_params += [
                ('categories', _('Categories, space separated'), fake_callback, False),
            ]
        data = {}
        data['categories'] = categories
        if input_params:
            mydata = self.Entropy.input_box(
                _('Insert categories'),
                input_params,
                cancel_button = True
            )
            if mydata == None: return
            data.update(mydata)
            if not categories:
                data['categories'] = data['categories'].split()

        if data['categories']:
            self.clear_data_store_and_view()
            self.run_spm_categories_updates(data['categories'], expand)

    def on_repoManagerCustomRunButton_clicked(self, widget):
        command = self.sm_ui.repoManagerCustomCmdEntry.get_text().strip()
        if not command: return
        self.run_run_custom_shell_command(command)

    def on_repoManagerInstalledPackages_clicked(self, widget, categories = [], world = False):

        def fake_callback_true(s):
            return True

        if world: categories = []
        input_params = []
        if not world:
            input_params += [
                ('categories', _('Categories, space separated'), fake_callback_true, False),
            ]
        data = {}
        data['categories'] = categories
        if input_params:
            mydata = self.Entropy.input_box(
                _('Insert categories (if you want)'),
                input_params,
                cancel_button = True
            )
            if mydata == None: return
            data.update(mydata)
            if not categories:
                data['categories'] = data['categories'].split()

        self.clear_data_store_and_view()
        self.run_get_spm_categories_installed(data['categories'], world)


    def on_repoManagerRunButton_clicked(self, widget):

        command = self.sm_ui.repoManagerRunEntry.get_text().strip()
        if not command: return
        command = command.split()
        cmd = command[0]

        avail_cmds = self.Service.get_available_client_commands()
        if cmd not in avail_cmds:
            okDialog(self.window, _("Invalid Command"), title = _("Custom command Error"))
            return

        cmd_data = avail_cmds.get(cmd)
        params = command[1:]
        mandatory_cmds = []
        for item in cmd_data['params']:
            if item[3]: mandatory_cmds.append(item)

        evalued_params = []
        for param in params:
            try:
                evalued_params.append(eval(param))
            except (NameError, SyntaxError):
                evalued_params.append(param)
            except TypeError:
                pass

        if len(evalued_params) < len(mandatory_cmds):
            okDialog(self.window, _("Not enough parameters"), title = _("Custom command Error"))
            return

        with self.BufferLock:
            try:
                cmd_data['call'](*evalued_params)
            except Exception as e:
                okDialog(self.window, "%s: %s" % (_("Error executing call"), e,), title = _("Custom command Error"))

    def on_repoManagerPauseQueueButton_toggled(self, widget):
        with self.BufferLock:
            try:
                do_pause = not self.queue_pause
                self.Service.Methods.pause_queue(do_pause)
                self.queue_pause = do_pause
            except Exception as e:
                self.service_status_message(e)
                return

    def on_repoManagerQueueView_row_activated(self, treeview, path, column):
        ( model, iterator ) = treeview.get_selection().get_selected()
        if model != None and iterator != None:
            obj = model.get_value( iterator, 0 )
            if obj:
                self.load_queue_info_menu(obj)

    def on_repoManagerOutputPauseButton_toggled(self, widget):
        if not self.output_pause:
            if isinstance(self.is_processing, dict):
                try:
                    self.paused_queue_id = self.is_processing['queue_id']
                except:
                    pass
        else:
            # back from pause, schedule refresh
            gobject.idle_add(self.update_output_view, True,
                self.paused_queue_id)
            self.paused_queue_id = None
        self.output_pause = not self.output_pause

    def on_repoManagerQueueRefreshButton_clicked(self, widget):
        self.Queue = {}
        self.do_update_queue_view()

    def on_repoManagerOutputCleanButton_clicked(self, widget):
        self.Output = None
        self.clear_console()

    def on_repoManagerCleanQueue_clicked(self, widget):
        clear_ids = set()
        for item in self.QueueStore:
            obj = item[0]
            if obj['from'] not in ("processed", "errored"):
                continue
            clear_ids.add(obj['queue_id'])
        if clear_ids: self.run_remove_queue_ids(clear_ids)

    def on_repoManagerClose_clicked(self, *args, **kwargs):
        self.QueueUpdater.kill()
        self.OutputUpdater.kill()
        self.PinboardUpdater.kill()
        self.destroy()

    def on_portageSync_clicked(self, widget):
        self.run_sync_spm()

    def on_removeAtom_clicked(self, widget, atoms = [], pretend = True, verbose = True, nocolor = True):

        def fake_callback(s):
            return s
        def fake_bool_cb(s):
            return True
        def fake_true_callback(s):
            return True

        input_params = []
        data = {}
        data['atoms'] = atoms
        data['pretend'] = pretend
        data['verbose'] = verbose
        data['nocolor'] = nocolor
        if not atoms:
            input_params.append(('atoms', _('Atoms, space separated'), fake_callback, False),)
        input_params += [
            ('pretend', ('checkbox', _('Pretend'),), fake_bool_cb, pretend,),
            ('verbose', ('checkbox', _('Verbose'),), fake_bool_cb, verbose,),
            ('nocolor', ('checkbox', _('No color'),), fake_bool_cb, nocolor,),
        ]
        mydata = self.Entropy.input_box(
            _('Insert packages removal parameters'),
            input_params,
            cancel_button = True
        )
        if mydata == None: return
        data.update(mydata)
        if not atoms:
            data['atoms'] = data['atoms'].split()

        if data['atoms']:
            self.run_spm_remove_atoms(data)


    def on_compileAtom_clicked(self, widget, atoms = [], pretend = False, oneshot = False, verbose = True, nocolor = True, fetchonly = False, buildonly = False, nodeps = False, custom_use = '', ldflags = '', cflags = ''):

        def fake_callback(s):
            return s
        def fake_bool_cb(s):
            return True
        def fake_true_callback(s):
            return True

        input_params = []
        data = {}
        data['atoms'] = atoms
        data['pretend'] = pretend
        data['oneshot'] = oneshot
        data['verbose'] = verbose
        data['nocolor'] = nocolor
        data['fetchonly'] = fetchonly
        data['buildonly'] = buildonly
        data['nodeps'] = nodeps
        data['custom_use'] = custom_use
        data['ldflags'] = ldflags
        data['cflags'] = cflags
        if not atoms:
            input_params.append(('atoms', _('Atoms, space separated'), fake_callback, False),)
        input_params += [
            ('pretend', ('checkbox', _('Pretend'),), fake_bool_cb, pretend,),
            ('oneshot', ('checkbox', _('Oneshot'),), fake_bool_cb, oneshot,),
            ('verbose', ('checkbox', _('Verbose'),), fake_bool_cb, verbose,),
            ('nocolor', ('checkbox', _('No color'),), fake_bool_cb, nocolor,),
            ('fetchonly', ('checkbox', _('Fetch only'),), fake_bool_cb, fetchonly,),
            ('buildonly', ('checkbox', _('Build only'),), fake_bool_cb, buildonly,),
            ('nodeps', ('checkbox', _('No dependencies'),), fake_bool_cb, nodeps,),
            ('custom_use', _('Custom USE flags'), fake_true_callback, False),
            ('ldflags', _('Custom LDFLAGS'), fake_true_callback, False),
            ('cflags', _('Custom CFLAGS'), fake_true_callback, False),
        ]
        mydata = self.Entropy.input_box(
            _('Insert compilation parameters'),
            input_params,
            cancel_button = True
        )
        if mydata == None: return
        data.update(mydata)
        if not atoms:
            data['atoms'] = data['atoms'].split()

        if data['atoms']:
            self.run_compile_atoms(data)

    def on_repoManagerSpmInfo_clicked(self, widget):
        self.run_spm_info()

    def on_addUseAtom_clicked(self, widget, atoms = [], use = [], load_view = True, parallel = True):
        data = self.handle_uses_for_atoms(atoms, use)
        if data == None: return False
        self.set_notebook_page(self.notebook_pages['data'])
        if data['atoms'] and data['use']:
            if parallel:
                def do_add():
                    self.run_enable_uses_for_atoms(data['atoms'], data['use'], load_view)
                    return False
                gobject.idle_add(do_add)
            else:
                return self.run_enable_uses_for_atoms(data['atoms'], data['use'], load_view)

    def on_removeUseAtom_clicked(self, widget, atoms = [], use = [], load_view = True, parallel = True):
        data = self.handle_uses_for_atoms(atoms, use)
        if data == None: return False
        self.set_notebook_page(self.notebook_pages['data'])
        if data['atoms'] and data['use']:
            if parallel:
                def do_remove():
                    self.run_disable_uses_for_atoms(data['atoms'], data['use'], load_view)
                    return False
                gobject.idle_add(do_remove)
            else:
                return self.run_disable_uses_for_atoms(data['atoms'], data['use'], load_view)

    def on_repoManagerPkgInfo_clicked(self, widget, atoms = [], clear = True):

        def fake_callback(s):
            return s

        input_params = []
        data = {}
        data['atoms'] = atoms
        if not atoms:
            input_params.append(('atoms', _('Atoms, space separated'), fake_callback, False),)
        if input_params:
            mydata = self.Entropy.input_box(
                _('Insert Package Information parameters'),
                input_params,
                cancel_button = True
            )
            if mydata == None: return
            data.update(mydata)
            if not atoms:
                data['atoms'] = data['atoms'].split()

        if data['atoms']:
            categories = []
            for atom in data['atoms']:
                categories.append(entropy.tools.dep_getkey(atom).split("/")[0])
            if clear: self.clear_data_store_and_view()
            self.run_get_spm_atoms_info(categories, data['atoms'], clear)

    def on_repoManagerRemoveButton_clicked(self, widget):
        model, myiter = self.QueueView.get_selection().get_selected()
        if myiter:
            obj = model.get_value( myiter, 0 )
            if obj and (obj['from'] != "processing"):
                self.run_remove_queue_ids([obj['queue_id']])

    def on_repoManagerStopButton_clicked(self, widget):
        model, myiter = self.QueueView.get_selection().get_selected()
        if myiter:
            obj = model.get_value( myiter, 0 )
            if obj and (obj['from'] == "processing"):
                self.run_kill_processing_queue_id(obj['queue_id'])

    def on_repoManagerQueueGetOutputButton_clicked(self, widget, queue_id = None, myfrom = None):

        def fake_callback_cb(s):
            return True

        model, myiter = self.QueueView.get_selection().get_selected()
        if myiter:
            obj = model.get_value( myiter, 0 )
            if obj:
                queue_id = obj['queue_id']
                myfrom = obj['from']

        if not queue_id: return

        input_params = [
            ('full', ("checkbox", _('Full output'),), fake_callback_cb, False),
        ]
        if myfrom == "processing":
            input_params.append(('autorefresh', ("checkbox", _('Auto refresh'),), fake_callback_cb, True))
        data = self.Entropy.input_box(
            _('Insert output parameters'),
            input_params,
            cancel_button = True
        )
        if data == None: return

        if 'autorefresh' in data:
            if data['autorefresh']:
                self.is_writing_output = True
                self.is_processing = {'queue_id': queue_id}

        self.set_notebook_page(self.notebook_pages['output'])
        if data.get('full'):
            gobject.idle_add(self.update_output_view, True, queue_id, 0)
        else:
            gobject.idle_add(self.update_output_view, True, queue_id)


    def on_repoManagerPinboardRefreshButton_clicked(self, widget):
        self.update_pinboard_view(force = True)

    def on_repoManagerPinboardAddButton_clicked(self, widget):

        def fake_callback(s):
            return s

        input_params = [
            ('note', _('Note'), fake_callback, False),
            ('extended_text', ("text", _('Extended note'),), fake_callback, False),
        ]
        data = self.Entropy.input_box(
            _('Insert your new pinboard item'),
            input_params,
            cancel_button = True
        )
        if data == None: return

        self.run_add_to_pinboard(data['note'], data['extended_text'])

    def collect_pinboard_view_iters(self):
        model, paths = self.PinboardView.get_selection().get_selected_rows()
        if not model:
            return [], model
        data = []
        for path in paths:
            myiter = model.get_iter(path)
            data.append(myiter)
        return data, model

    def on_repoManagerPinboardRemoveButton_clicked(self, widget):

        myiters, model = self.collect_pinboard_view_iters()
        if model == None: return
        remove_ids = []
        for myiter in myiters:
            obj = model.get_value( myiter, 0 )
            if obj:
                remove_ids.append(obj['pinboard_id'])

        if remove_ids:
            self.run_remove_from_pinboard(remove_ids)

    def on_repoManagerPinboardDoneButton_clicked(self, widget):
        self._set_pinboard_items_status(widget, True)

    def on_repoManagerPinboardNotDoneButton_clicked(self, widget):
        self._set_pinboard_items_status(widget, False)

    def _set_pinboard_items_status(self, widget, status):

        myiters, model = self.collect_pinboard_view_iters()
        if model == None: return
        done_ids = []
        for myiter in myiters:
            obj = model.get_value( myiter, 0 )
            if obj:
                done_ids.append(obj['pinboard_id'])

        def set_pinboard_status(done_ids, status):
            if done_ids:
                with self.BufferLock:
                    try:
                        status, queue_id = self.Service.Methods.set_pinboard_items_done(done_ids, status)
                    except Exception as e:
                        self.service_status_message(e)
                        return
                if status:
                    self.on_repoManagerPinboardRefreshButton_clicked(widget)

        set_pinboard_status(done_ids, status)

    def on_repoManagerPinboardView_row_activated(self, treeview, path, column):
        model = treeview.get_model()
        myiter = model.get_iter(path)
        obj = model.get_value(myiter, 0)
        if obj:
            my = SmPinboardMenu(self.window)
            my.load(obj.copy())

    def on_repoManagerSecurityUpdatesButton_clicked(self, widget):

        def fake_callback(s):
            return s

        input_params = [
            ('list_type', ('combo', (_('List type'), ['affected', 'new', 'all']),), fake_callback, False),
        ]
        data = self.Entropy.input_box(
            _('Choose what kind of list you want to see'),
            input_params,
            cancel_button = True
        )
        if data == None:
            return
        self.clear_data_store_and_view()

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.get_spm_glsa_data(data['list_type'][1])
            except Exception as e:
                self.service_status_message(e)
                return

        def task(queue_id, data):
            item = self.wait_queue_id_to_complete(queue_id)
            if item == None:
                return
            data = None
            try:
                status, data = item['result']
            except TypeError:
                status = False
            if not status:
                return
            gobject.idle_add(self.glsa_data_view, data)

        if status:
            t = ParallelTask(task, queue_id, data)
            t.start()
        else:
            self.service_status_message(queue_id)

    def on_repoManagerSwitchRepoButton_clicked(self, widget):

        # get current combo iter
        model = self.EntropyRepositoryStore
        myiter = self.EntropyRepositoryCombo.get_active_iter()
        repoid = model.get_value(myiter, 0)
        if not repoid:
            return

        with self.BufferLock:
            try:
                status, queue_id = self.Service.Methods.set_default_repository(repoid)
            except Exception as e:
                self.service_status_message(e)
                return

        def task():
            repo_info = self.get_available_repositories()
            if repo_info:
                gobject.idle_add(self.load_available_repositories,
                    repo_info)

        if status:
            t = ParallelTask(task)
            t.start()
        else:
            self.service_status_message(queue_id)

    def on_repoManagerAvailablePackagesButton_clicked(self, widget, repoid = None):

        def fake_callback(s):
            return s

        data = {}
        data['repoid'] = repoid
        avail_repos = list(self.EntropyRepositories['available'].keys())
        if not avail_repos: return
        input_params = []
        if not repoid:
            input_params.append(('repoid', ('combo', (_('Repository'), avail_repos),), fake_callback, False))

        if input_params:
            mydata = self.Entropy.input_box(
                _('Choose from which repository'),
                input_params,
                cancel_button = True
            )
            if mydata == None: return
            mydata['repoid'] = mydata['repoid'][1]
            data.update(mydata)

        self.clear_data_store_and_view()

        with self.BufferLock:
            try:
                status, repo_data = self.Service.Methods.get_available_entropy_packages(data['repoid'])
            except Exception as e:
                self.service_status_message(e)
                return

        def task(repo_data, data):
            def reload_func():
                self.on_repoManagerAvailablePackagesButton_clicked(widget,
                    repoid = data['repoid'])
            gobject.idle_add(self.entropy_available_packages_data_view,
                repo_data, data['repoid'], reload_func)

        if status:
            t = ParallelTask(task, repo_data, data)
            t.start()
        else:
            self.service_status_message(repo_data)

    def on_repoManagerPackageSearchButton_clicked(self, widget):

        def fake_callback(s):
            return s

        avail_repos = list(self.EntropyRepositories['available'].keys())
        if not avail_repos: return

        search_reference = {
            0: 'atom',
            1: 'needed',
            2: 'depends',
            3: 'tag',
            4: 'file',
            5: 'description',
            6: 'eclass',
        }
        search_types = [
            _("Atom"), _("Needed Libraries"), _("Reverse dependencies"), _("Tag"), _("File"), _("Description"), _("Eclass")
        ]
        input_params = [
            ('repoid', ('combo', (_('Repository'), avail_repos),), fake_callback, False),
            ('search_type', ('combo', (_('Search type'), search_types),), fake_callback, False),
            ('search_string', _('Search string'), fake_callback, False)
        ]
        data = self.Entropy.input_box(
            _('Entropy Search'),
            input_params,
            cancel_button = True
        )
        if data == None: return
        data['search_type'] = search_reference.get(data['search_type'][0])
        data['repoid'] = data['repoid'][1]
        self.clear_data_store_and_view()
        self.run_package_search(data['search_type'], data['search_string'], data['repoid'])

    def on_repoManagerEntropyDbUpdatesButton_clicked(self, widget):
        self.clear_data_store_and_view()
        self.run_entropy_database_updates_scan()

    def on_repoManagerDepTestButton_clicked(self, widget):
        self.run_entropy_deptest()

    def on_repoManagerLibTestButton_clicked(self, widget):
        self.run_entropy_libtest()

    def on_repoManagerSpmTreeupdatesButton_clicked(self, widget):

        avail_repos = list(self.EntropyRepositories['available'].keys())
        if not avail_repos: return

        def fake_callback_cb(s):
            return True

        input_params = [
            ('repoid', ('combo', (_('Repository'), avail_repos),), fake_callback_cb, False),
        ]

        data = self.Entropy.input_box(
            _('Choose the repository'),
            input_params,
            cancel_button = True
        )
        if data == None: return
        data['repoid'] = data['repoid'][1]

        self.run_entropy_treeupdates(data['repoid'])

    def on_repoManagerMirrorUpdatesButton_clicked(self, widget):

        avail_repos = list(self.EntropyRepositories['available'].keys())
        if not avail_repos: return

        def fake_callback_cb(s):
            return True

        input_params = []
        for repo in avail_repos:
            input_params.append((repo, ('checkbox', "%s: %s" % (_('Repository'), repo,),), fake_callback_cb, False))

        data = self.Entropy.input_box(
            _('Choose the repositories you want to scan'),
            input_params,
            cancel_button = True
        )
        if data == None: return
        repos = []
        for key in data:
            if data[key]:
                repos.append(key)
        if not repos: return

        self.clear_data_store_and_view()
        self.run_entropy_mirror_updates(repos)

    def on_repoManagerChecksumTestButton_clicked(self, widget):

        avail_repos = list(self.EntropyRepositories['available'].keys())
        if not avail_repos: return

        def fake_callback(s):
            return s

        input_params = [
            ('repoid', ('combo', (_('Repository'), avail_repos),), fake_callback, False),
            ('mode', ('combo', (_('Choose mode'), [_("Server check"), _("Mirrors check")]),), fake_callback, False),
        ]
        data = self.Entropy.input_box(
            _('Choose what kind of test you would like to run'),
            input_params,
            cancel_button = True
        )
        if data == None: return
        if data['mode'][0] == 0:
            mode = "local"
        else:
            mode = "remote"
        data['repoid'] = data['repoid'][1]
        self.run_entropy_checksum_test(data['repoid'], mode)

    def on_repoManagerStdinExecButton_clicked(self, widget):
        self.sm_ui.repoManagerStdinEntry.activate()

    def on_repoManagerStdinEntry_activate(self, widget, write_to_stdout = True, txt = ''):
        if not self.is_processing: return
        try: queue_id = self.is_processing.get('queue_id')
        except: return
        if not txt:
            txt = self.sm_ui.repoManagerStdinEntry.get_text()
        if not txt: return
        self.sm_ui.repoManagerStdinEntry.set_text('')
        self.run_write_to_running_command_pipe(queue_id, write_to_stdout, txt)

    def on_repoManagerNoticeBoardButton_clicked(self, widget, repoid = None):

        avail_repos = list(self.EntropyRepositories['available'].keys())
        if not avail_repos: return

        def fake_callback(s):
            return s

        input_params = []
        if not repoid:
            input_params += [
                ('repoid', ('combo', (_('Repository'), avail_repos),), fake_callback, False),
            ]
        if input_params:
            data = self.Entropy.input_box(
                _('Choose what notice board you want to see'),
                input_params,
                cancel_button = True
            )
            if data == None: return
            repoid = data['repoid'][1]

        if repoid in avail_repos:
            self.run_get_notice_board(repoid)

    def destroy(self):
        self.sm_ui.repositoryManager.destroy()

class SmPinboardMenu(MenuSkel):

    def __init__(self, window):

        self.window = window
        self.sm_ui = UI( const.GLADE_FILE, 'smPinboardInfo', 'entropy' )
        self.sm_ui.signal_autoconnect(self._getAllMethods())
        self.sm_ui.smPinboardInfo.set_transient_for(self.window)
        self.sm_ui.smPinboardInfo.add_events(gtk.gdk.BUTTON_PRESS_MASK)

    def on_smPinboardCloseButton_clicked(self, widget):
        self.sm_ui.smPinboardInfo.hide()

    def destroy(self):
        self.sm_ui.smPinboardInfo.destroy()

    def load(self, item):

        na = _("N/A")
        self.sm_ui.smPinboardId.set_text(item['pinboard_id'])
        self.sm_ui.smPinboardDate.set_text(item['ts'])
        self.sm_ui.smPinboardDone.set_text(item['done'])
        self.sm_ui.smPinboardNote.set_text(item['note'])
        mybuffer = gtk.TextBuffer()
        mybuffer.set_text(item['extended_text'])
        self.sm_ui.smPinboardExtendedNote.set_buffer(mybuffer)

        bold_items = [
            self.sm_ui.smPinboardIdLabel,
            self.sm_ui.smPinboardDateLabel,
            self.sm_ui.smPinboardDoneLabel,
            self.sm_ui.smPinboardNoteLabel,
            self.sm_ui.smPinboardExtendedNoteLabel
        ]
        small_items = [
            self.sm_ui.smPinboardId,
            self.sm_ui.smPinboardDate,
            self.sm_ui.smPinboardDone,
            self.sm_ui.smPinboardNote,
        ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<small><b>%s</b></small>" % (t,))
        for item in small_items:
            t = item.get_text()
            item.set_markup("<small>%s</small>" % (t,))

        self.sm_ui.smPinboardInfo.show_all()

class SmQueueMenu(MenuSkel):

    def __init__(self, window):

        self.window = window
        self.sm_ui = UI( const.GLADE_FILE, 'smQueueInfo', 'entropy' )
        self.sm_ui.signal_autoconnect(self._getAllMethods())
        self.sm_ui.smQueueInfo.set_transient_for(self.window)
        self.sm_ui.smQueueInfo.add_events(gtk.gdk.BUTTON_PRESS_MASK)

    def on_smQueueCloseButton_clicked(self, widget):
        self.sm_ui.smQueueInfo.hide()

    def destroy(self):
        self.sm_ui.smQueueInfo.destroy()

    def load(self, item):

        na = _("N/A")
        self.sm_ui.smQueueIdL.set_text(item['queue_id'])
        self.sm_ui.smCommandNameL.set_text(item['command_name'])
        self.sm_ui.smCommandDescL.set_text(item['command_desc'])
        args = "None"
        if isinstance(item['args'], list):
            args = ' '.join([x for x in item['args']])
        self.sm_ui.smCommandArgsL.set_text(args)
        self.sm_ui.smCallL.set_text(item['call'])
        self.sm_ui.smUserGroupL.set_text("%s / %s " % (item.get('user_id'), item.get('group_id'),))
        self.sm_ui.smQueuedAtL.set_text(item['queue_ts'])
        self.sm_ui.smProcessingAtL.set_text(item.get('processing_ts'))
        self.sm_ui.smCompletedAtL.set_text(item.get('completed_ts'))
        self.sm_ui.smErroredAtL.set_text(item.get('errored_ts'))
        self.sm_ui.smStdoutFileL.set_text(item['stdout'])
        self.sm_ui.smProcessResultL.set_text(item.get('result', ''))

        bold_items = [

            self.sm_ui.smQueueIdLabel,
            self.sm_ui.smCommandNameLabel,
            self.sm_ui.smCommandDescLabel,
            self.sm_ui.smCommandArgsLabel,
            self.sm_ui.smCallLabel,
            self.sm_ui.smUserGroupLabel,
            self.sm_ui.smQueuedAtLabel,
            self.sm_ui.smProcessingAtLabel,
            self.sm_ui.smCompletedAtLabel,
            self.sm_ui.smErroredAtLabel,
            self.sm_ui.smStdoutFileLabel,
            self.sm_ui.smProcessResultLabel

        ]
        small_items = [
            self.sm_ui.smQueueIdL,
            self.sm_ui.smCommandNameL,
            self.sm_ui.smCommandDescL,
            self.sm_ui.smCommandArgsL,
            self.sm_ui.smCallL,
            self.sm_ui.smUserGroupL,
            self.sm_ui.smQueuedAtL,
            self.sm_ui.smProcessingAtL,
            self.sm_ui.smCompletedAtL,
            self.sm_ui.smErroredAtL,
            self.sm_ui.smStdoutFileL,
            self.sm_ui.smProcessResultL
        ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<small><b>%s</b></small>" % (t,))
        for item in small_items:
            t = item.get_text()
            item.set_markup("<small>%s</small>" % (t,))

        self.sm_ui.smQueueInfo.show_all()