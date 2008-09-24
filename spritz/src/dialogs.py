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

import time
import gtk
import gobject
import pango
from etpgui.widgets import UI
from etpgui import CURRENT_CURSOR, busyCursor, normalCursor
from spritz_setup import const, cleanMarkupString, SpritzConf, unicode2htmlentities
from entropy_i18n import _,_LOCALE
import packages
import exceptionTools
from entropyConstants import *


class MenuSkel:

    def _getAllMethods(self):
        result = {}
        allAttrNames = self.__dict__.keys() + self._getAllClassAttributes()
        for name in allAttrNames:
            value = getattr(self, name)
            if callable(value):
                result[name] = value
        return result

    def _getAllClassAttributes(self):
        nameSet = {}
        for currClass in self._getAllClasses():
            nameSet.update(currClass.__dict__)
        result = nameSet.keys()
        return result

    def _getAllClasses(self):
        result = [self.__class__]
        i = 0
        while i < len(result):
            currClass = result[i]
            result.extend(list(currClass.__bases__))
            i = i + 1
        return result

class RemoteConnectionMenu(MenuSkel):

    def __init__( self, verification_callback, window ):

        # hostname, port, username, password, ssl will be passed as parameters
        self.verification_callback = verification_callback
        self.window = window
        self.cm_ui = UI( const.GLADE_FILE, 'remoteConnManager', 'entropy' )
        self.cm_ui.signal_autoconnect(self._getAllMethods())
        self.cm_ui.remoteConnManager.set_transient_for(self.window)
        self.cm_ui.remoteConnManager.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.button_pressed = False
        self.loaded = False
        self.parameters = None

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

    def __init__(self, Entropy, window):
        self.Entropy = Entropy
        self.window = window
        self.sm_ui = UI( const.GLADE_FILE, 'repositoryManager', 'entropy' )
        self.sm_ui.signal_autoconnect(self._getAllMethods())
        self.sm_ui.repositoryManager.set_transient_for(self.window)
        self.sm_ui.repositoryManager.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.setup_queue_view()
        self.is_processing = None
        self.Queue = {}
        self.Output = None
        self.output_pause = False
        self.queue_pause = False
        self.QueueUpdater = self.Entropy.entropyTools.TimeScheduled(self.update_queue_view, 5)
        self.OutputUpdater = self.Entropy.entropyTools.TimeScheduled(self.update_output_view, 4)
        self.ssl_mode = True
        self.OutputBuffer = gtk.TextBuffer()
        self.sm_ui.repoOutputView.set_buffer(self.OutputBuffer)
        self.sm_ui.repoManagerOutputScroll.set_placement(gtk.CORNER_BOTTOM_LEFT)
        self.output_scroll_vadj = self.sm_ui.repoManagerOutputScroll.get_vadjustment()
        self.output_scroll_vadj.connect('changed', lambda a, s=self.sm_ui.repoManagerOutputScroll: self.rescroll_output(a,s))
        self.notebook_pages = {
            'queue': 0,
            'commands': 1,
            'data': 2,
            'output': 3
        }
        self.channel_call = False

        from entropy import SystemManagerClientInterface, \
            SystemManagerRepositoryClientCommands, \
            SystemManagerRepositoryMethodsInterface
        self.Service = SystemManagerClientInterface(
            self.Entropy,
            MethodsInterface = SystemManagerRepositoryMethodsInterface,
            ClientCommandsInterface = SystemManagerRepositoryClientCommands
        )
        self.CommandsStore = None
        self.setup_commands_view()
        self.fill_commands_view(self.Service.get_available_client_commands())

    def set_notebook_page(self, page):
        self.sm_ui.repoManagerNotebook.set_current_page(page)

    def rescroll_output(self, adj, scroll):
        adj.set_value(adj.upper-adj.page_size)
        scroll.set_vadjustment(adj)

    def setup_commands_view(self):

        # setup commands view
        self.CommandsView = self.sm_ui.repoManagerCommandsView
        self.CommandsStore = gtk.ListStore( gobject.TYPE_PYOBJECT )
        self.CommandsView.set_model( self.CommandsStore )

        # command col
        self.create_text_column( self.CommandsView, _( "Command" ), 'commands:command', size = 200, set_height = 40)
        # desc col
        self.create_text_column( self.CommandsView, _( "Description" ), 'commands:desc', size = 200, expand = True, set_height = 40)

    def fill_commands_view(self, data):
        self.CommandsStore.clear()
        keys = sorted(data.keys())
        for key in keys:
            if data[key]['private']: continue
            item = data[key].copy()
            item['key'] = key
            params = ' | '.join([cleanMarkupString(unicode(x)) for x in item['params']])
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
        self.QueueStore = gtk.ListStore( gobject.TYPE_PYOBJECT )
        self.QueueView.set_model( self.QueueStore )

        # selection pixmap
        cell = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn( _("Status"), cell )
        column.set_cell_data_func( cell, self.queue_pixbuf )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 60 )
        column.set_sort_column_id( -1 )
        self.QueueView.append_column( column )
        column.set_clickable( False )

        # command col
        self.create_text_column( self.QueueView, _( "Command" ), 'queue:command_name', size = 180)
        # description col
        self.create_text_column( self.QueueView, _( "Parameters" ), 'queue:command_text', size = 200, expand = True)
        # date col
        self.create_text_column( self.QueueView, _( "Date" ), 'queue:ts', size = 120)

    def create_text_column( self, view, hdr, property, size, sortcol = None, expand = False, set_height = 0):
        cell = gtk.CellRendererText()
        if set_height: cell.set_property('height', set_height)
        column = gtk.TreeViewColumn( hdr, cell )
        column.set_resizable( True )
        column.set_cell_data_func( cell, self.get_data_text, property )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( size )
        column.set_expand(expand)
        column.set_sort_column_id( -1 )
        view.append_column( column )
        return column

    def set_pixbuf_to_cell(self, cell, filename):
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
            cell.set_property( 'pixbuf', pixbuf )
        except gobject.GError:
            pass

    def queue_pixbuf( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 )
        if obj:
            st = self.get_status_from_queue_item(obj.copy())
            if st != None:
                cell.set_property('stock-id',st)

    def get_status_from_queue_item(self, item):
        if item.has_key('errored_ts'):
            return "gtk-cancel"
        elif item.has_key('processed_ts'):
            return "gtk-apply"
        elif item.has_key('processing_ts'):
            return "gtk-refresh"
        elif item.has_key('queue_ts'):
            return "gtk-up"
        return "gtk-apply"

    def get_ts_from_queue_item(self, item):
        if item.has_key('errored_ts'):
            return item['errored_ts']
        elif item.has_key('processed_ts'):
            return item['processed_ts']
        elif item.has_key('processing_ts'):
            return item['processing_ts']
        elif item.has_key('queue_ts'):
            return item['queue_ts']
        return None

    def get_data_text( self, column, cell, model, myiter, property ):
        obj = model.get_value( myiter, 0 )
        if obj:
            if property == "queue:ts":
                cell.set_property('markup',self.get_ts_from_queue_item(obj))
            elif property == "queue:command_text":
                cell.set_property('markup',obj['command_text'])
            elif property == "queue:command_name":
                cell.set_property('markup',obj['command_name'])
            elif property == "commands:command":
                cell.set_property('markup',obj['key'])
            elif property == "commands:desc":
                cell.set_property('markup',obj['myinfo'])

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
        session = srv.open_session()
        if session == None:
            return False, _("Unable to create a remote session. Try again later.")
        try:
            logged, error = self.Service.login(srv, session)
            if not logged:
                return False, _("Login failed. Please retry.")
        except Exception, e:
            return False, "%s: %s" % (_("Connection Error"),e,)
        srv.close_session(session)
        srv.disconnect()
        return True, None

    def load(self):

        my = RemoteConnectionMenu(self.connection_verification_callback, self.window)
        my.load()
        login_data = my.run()
        if not login_data:
            return False

        bold_items = []
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<b>%s</b>" % (t,))

        self.sm_ui.repositoryManager.show_all()

        # spawn parallel tasks
        self.QueueUpdater.start()
        self.OutputUpdater.start()

        return True

    def wait_channel_call(self):
        while self.channel_call:
            time.sleep(0.5)
        self.channel_call = True

    def update_queue_view(self):
        self.wait_channel_call()

        try:
            status, queue = self.Service.Methods.get_queue()
        except:
            self.channel_call = False
            return
        self.channel_call = False
        if not status: return
        if queue == self.Queue: return

        gtk.gdk.threads_enter()
        self.fill_queue_view(queue)
        gtk.gdk.threads_leave()
        self.Queue = queue.copy()

    def fill_queue_view(self, queue):
        self.QueueStore.clear()
        keys = queue.keys()

        if "processing" in keys:
            for item in queue['processing']:
                self.is_processing = item.copy()
                item = item.copy()
                item['from'] = "processing"
                self.QueueStore.append((item,))
            if not queue['processing']:
                self.is_processing = None
        else:
            self.is_processing = None

        if "processed" in keys:
            for item in queue['processed']:
                item = item.copy()
                item['from'] = "processed"
                self.QueueStore.append((item,))

        if "queue" in keys:
            for item in queue['queue']:
                item = item.copy()
                item['from'] = "queue"
                self.QueueStore.append((item,))
        if "errored" in keys:
            for item in queue['errored']:
                item = item.copy()
                item['from'] = "errored"
                self.QueueStore.append((item,))

        self.QueueView.queue_draw()

    def update_output_view(self):

        if self.output_pause:
            return
        n_bytes = 4000
        if self.is_processing == None:
            return
        obj = self.is_processing.copy()
        if not obj.has_key('queue_id'):
            return
        self.wait_channel_call()
        status, stdout = self.Service.Methods.get_queue_id_stdout(obj['queue_id'], n_bytes)
        self.channel_call = False
        if not status:
            return
        stdout = stdout[-1*n_bytes:]
        if stdout == self.Output:
            return
        self.Output = stdout
        self.OutputBuffer.set_text(stdout)
        gtk.gdk.threads_enter()
        self.sm_ui.repoOutputView.queue_draw()
        while gtk.events_pending():
            gtk.main_iteration()
        gtk.gdk.threads_leave()

    def load_queue_info_menu(self, obj):
        my = SmQueueMenu(self.window)
        my.load(obj)

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
                self.wait_channel_call()
                status, msg = self.Service.Methods.swap_items_in_queue(item1['queue_id'],item2['queue_id'])
                self.channel_call = False
                if status: self.QueueStore.swap(iterator,next_iterator)
                self.update_queue_view()

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
                self.wait_channel_call()
                status, msg = self.Service.Methods.swap_items_in_queue(item1['queue_id'],item2['queue_id'])
                self.channel_call = False
                if status: self.QueueStore.swap(iterator,next_iterator)
                self.update_queue_view()

    def on_repoManagerRunButton_clicked(self, widget):

        command = self.sm_ui.remoManagerRunEntry.get_text().strip()
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

        try:
            cmd_data['call'](*evalued_params)
        except Exception, e:
            okDialog(self.window, "%s: %s" % (_("Error executing call"),e,), title = _("Custom command Error"))

    def on_repoManagerPauseQueueButton_toggled(self, widget):
        self.wait_channel_call()
        do_pause = not self.queue_pause
        self.Service.Methods.pause_queue(do_pause)
        self.queue_pause = do_pause
        self.channel_call = False

    def on_repoManagerQueueView_row_activated(self, treeview, path, column):
        ( model, iterator ) = treeview.get_selection().get_selected()
        if model != None and iterator != None:
            obj = model.get_value( iterator, 0 )
            if obj:
                self.load_queue_info_menu(obj)

    def on_repoManagerOutputPauseButton_toggled(self, widget):
        self.output_pause = not self.output_pause

    def on_repoManagerQueueRefreshButton_clicked(self, widget):
        self.Queue = None
        self.update_queue_view()

    def on_repoManagerOutputCleanButton_clicked(self, widget):
        self.Output = None
        self.OutputBuffer.set_text('')
        self.sm_ui.repoOutputView.queue_draw()

    def on_repoManagerCleanQueue_clicked(self, widget):
        clear_ids = set()
        for item in self.QueueStore:
            obj = item[0]
            if obj['from'] not in ("processed","errored"):
                continue
            clear_ids.add(obj['queue_id'])
        self.wait_channel_call()
        for queue_id in clear_ids:
            self.Service.Methods.remove_queue_id(queue_id)
        self.channel_call = False

    def on_repoManagerClose_clicked(self, *args, **kwargs):
        self.QueueUpdater.kill()
        self.OutputUpdater.kill()
        self.destroy()

    def on_portageSync_clicked(self, widget):
        self.set_notebook_page(self.notebook_pages['output'])
        self.wait_channel_call()
        self.Service.Methods.sync_spm()
        self.channel_call = False

    def on_compileAtom_clicked(self, widget):
        def fake_callback(s):
            return s
        def fake_bool_cb(s):
            return True
        input_params = [
            ('atom',_('Atom'),fake_callback,False),
            ('pretend',('checkbox',_('Pretend'),),fake_bool_cb,False,),
        ]
        data = self.Entropy.inputBox(
            _('Insert compilation parameters'),
            input_params,
            cancel_button = True
        )
        if data == None: return
        self.set_notebook_page(self.notebook_pages['output'])
        self.Service.Methods.compile_atom(data['atom'])

    def on_repoManagerRemoveButton_clicked(self, widget):
        model, myiter = self.QueueView.get_selection().get_selected()
        if myiter:
            obj = model.get_value( myiter, 0 )
            if obj and (obj['from'] != "processing"):
                self.wait_channel_call()
                self.Service.Methods.remove_queue_id(obj['queue_id'])
                self.channel_call = False

    def on_repoManagerStopButton_clicked(self, widget):
        model, myiter = self.QueueView.get_selection().get_selected()
        if myiter:
            obj = model.get_value( myiter, 0 )
            if obj and (obj['from'] == "processing"):
                self.wait_channel_call()
                self.Service.Methods.kill_processing_queue_id(obj['queue_id'])
                self.channel_call = False

    def destroy(self):
        self.sm_ui.repositoryManager.destroy()

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
        self.sm_ui.smQueueIdL.set_text(unicode(item['queue_id']))
        self.sm_ui.smCommandNameL.set_text(item['command_name'])
        self.sm_ui.smCommandDescL.set_text(item['command_desc'])
        args = "None"
        if isinstance(item['args'],list):
            args = ' '.join([unicode(x) for x in item['args']])
        self.sm_ui.smCommandArgsL.set_text(args)
        self.sm_ui.smCallL.set_text(item['call'])
        self.sm_ui.smUserGroupL.set_text("%s / %s " % (item.get('user_id'),item.get('group_id'),))
        self.sm_ui.smQueuedAtL.set_text(unicode(item['queue_ts']))
        self.sm_ui.smProcessingAtL.set_text(unicode(item.get('processing_ts')))
        self.sm_ui.smCompletedAtL.set_text(unicode(item.get('completed_ts')))
        self.sm_ui.smErroredAtL.set_text(unicode(item.get('errored_ts')))
        self.sm_ui.smStdoutFileL.set_text(unicode(item['stdout']))
        self.sm_ui.smProcessResultL.set_text(unicode(item.get('result')))

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

class PkgInfoMenu(MenuSkel):

    def __init__(self, Entropy, pkg, window):

        self.pkg_pixmap = const.pkg_pixmap
        self.ugc_small_pixmap = const.ugc_small_pixmap
        self.ugc_pixmap = const.ugc_pixmap
        self.refresh_pixmap = const.refresh_pixmap
        self.star_normal_pixmap = const.star_normal_pixmap
        self.star_selected_pixmap = const.star_selected_pixmap
        self.star_empty_pixmap = const.star_empty_pixmap

        self.loading_pix = gtk.image_new_from_file(const.loading_pix)
        self.ugc_preview_fetcher = None
        self.ugc_data = None
        self.ugc_status_message = None
        self.pkg = pkg
        self.vote = 0
        self.window = window
        self.Entropy = Entropy
        self.repository = None
        self.pkgkey = None
        self.ugc_page_idx = 5
        self.switched_to_ugc_page = False
        self.pkginfo_ui = UI( const.GLADE_FILE, 'pkgInfo', 'entropy' )
        self.pkginfo_ui.signal_autoconnect(self._getAllMethods())
        self.pkginfo_ui.pkgInfo.set_transient_for(self.window)
        self.pkginfo_ui.pkgInfo.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        # noeeees! otherwise voting won't work
        #self.pkginfo_ui.pkgInfo.connect('button-press-event', self.on_button_press)
        self.setupPkgPropertiesView()

    def set_pixbuf_to_cell(self, cell, path):
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(path)
            cell.set_property( 'pixbuf', pixbuf )
        except gobject.GError:
            pass

    def ugc_pixbuf( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 )
        if isinstance(obj,dict):
            if obj.has_key('preview_path'):
                self.set_pixbuf_to_cell(cell,obj['preview_path'])
            else:
                self.set_pixbuf_to_cell(cell,obj['image_path'])
            self.set_colors_to_cell(cell, obj)

    def ugc_content( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 )
        if isinstance(obj,dict):
            self.set_colors_to_cell(cell,obj)

            if obj.has_key('is_cat'):
                cell.set_property('markup',"<b>%s</b>\n<small>%s</small>" % (obj['parent_desc'],_("Expand to browse"),))
            else:
                title = _("N/A")
                if obj['title']:
                    title = unicode(obj['title'],'raw_unicode_escape')
                description = _("N/A")
                if obj['description']:
                    description = obj['description']
                if obj['iddoctype'] in (etpConst['ugc_doctypes']['comments'], etpConst['ugc_doctypes']['bbcode_doc'],):
                    description = unicode(obj['ddata'].tostring(),'raw_unicode_escape')
                    if len(description) > 100:
                        description = description[:100].strip()+"..."
                mytxt = "<small><b>%s</b>: %s, %s: %s\n<b>%s</b>: %s, <i>%s</i>\n<b>%s</b>: %s\n<b>%s</b>: <i>%s</i>\n<b>%s</b>: %s</small>" % (
                    _("Identifier"),
                    obj['iddoc'],
                    _("Size"),
                    self.Entropy.entropyTools.bytesIntoHuman(obj['size']),
                    _("Author"),
                    obj['username'],
                    obj['ts'],
                    _("Title"),
                    title,
                    _("Description"),
                    description,
                    _("Keywords"),
                    ', '.join(obj['keywords']),
                )
                cell.set_property('markup',mytxt)

    def set_colors_to_cell(self, cell, obj):
        odd = 0
        if obj.has_key('counter'):
            odd = obj['counter']%2
        if obj.has_key('background'):
            cell.set_property('cell-background',obj['background'][odd])
        else:
            cell.set_property('cell-background',None)
        try:
            if obj.has_key('foreground'):
                cell.set_property('foreground',obj['foreground'])
            else:
                cell.set_property('foreground',None)
        except TypeError:
            pass


    def on_button_press(self, widget, event):
        self.pkginfo_ui.pkgInfo.begin_move_drag(
                        event.button,
                        int(event.x_root),
                        int(event.y_root),
                        event.time)

    def on_showContentButton_clicked( self, widget ):
        content = self.pkg.contentExt
        for x in content:
            self.contentModel.append(None,[x[0],x[1]])

    def on_closeInfo_clicked(self, widget):
        self.reset_ugc_data()
        self.pkginfo_ui.pkgInfo.hide()

    def on_pkgInfo_delete_event(self, widget, path):
        self.reset_ugc_data()
        self.pkginfo_ui.pkgInfo.hide()
        return True

    def on_loadUgcButton_clicked(self, widget, force = True):
        self.spawn_ugc_load(force = force)

    def on_ugcRemoveButton_released(self, widget):
        if self.Entropy.UGC == None: return
        if self.repository == None: return
        model, myiter = self.ugcView.get_selection().get_selected()
        if myiter == None: return
        obj = model.get_value( myiter, 0 )
        if not isinstance(obj,dict): return
        if obj.has_key('is_cat'): return
        self.show_loading()
        self.Entropy.UGC.remove_document_autosense(self.repository, int(obj['iddoc']), obj['iddoctype'])
        self.hide_loading()
        self.reset_ugc_data()
        self.spawn_ugc_load(force = True)
        self.refresh_ugc_view()

    def on_ugc_doubleclick(self, widget, path, view):
        self.on_ugcShowButton_clicked(widget)

    def on_ugcShowButton_clicked(self, widget):
        if self.Entropy.UGC == None: return
        if self.repository == None: return
        model, myiter = self.ugcView.get_selection().get_selected()
        if myiter == None: return
        obj = model.get_value( myiter, 0 )
        if not isinstance(obj,dict): return
        if obj.has_key('is_cat'): return
        my = UGCInfoMenu(self.Entropy, obj, self.repository, self.pkginfo_ui.pkgInfo)
        my.load()

    def on_ugcAddButton_clicked(self, widget):
        if self.Entropy.UGC == None: return
        if self.repository == None: return
        if self.pkgkey == None: return
        my = UGCAddMenu(self.Entropy, self.pkgkey, self.repository, self.pkginfo_ui.pkgInfo, self.refresh_view_cb)
        my.load()

    def refresh_view_cb(self):
        self.spawn_ugc_load(force = True)

    def reset_ugc_data(self):
        del self.ugc_data
        self.ugc_data = None
        if self.ugc_preview_fetcher != None:
            self.ugc_preview_fetcher.kill()

    def show_loading(self):
        self.pkginfo_ui.ugcButtonBox.hide()
        self.pkginfo_ui.loadUgcButton.set_sensitive(False)
        self.pkginfo_ui.scrolledView.hide()
        self.pkginfo_ui.ugcView.hide()
        self.pkginfo_ui.ugcLoadingEvent.show_all()
        self.pkginfo_ui.ugcLoadingEvent.add(self.loading_pix)
        self.pkginfo_ui.ugcLoadingEvent.show_all()
        self.pkginfo_ui.pkgInfo.queue_draw()

    def hide_loading(self):
        self.pkginfo_ui.ugcLoadingEvent.remove(self.loading_pix)
        self.pkginfo_ui.scrolledView.show()
        self.pkginfo_ui.ugcView.show()
        self.pkginfo_ui.ugcLoadingEvent.hide()
        self.pkginfo_ui.loadUgcButton.set_sensitive(True)
        self.pkginfo_ui.ugcButtonBox.show_all()

    def spawn_ugc_load(self, force = False):

        if (self.ugc_data != None) and (not force):
            return
        if self.Entropy.UGC == None:
            return
        if not (self.pkgkey and self.repository):
            return

        self.show_loading()

        docs_cache = None
        if not force:
            docs_cache = self.Entropy.UGC.UGCCache.get_alldocs_cache(self.pkgkey, self.repository)
        if docs_cache == None:
            docs_data, err_msg = self.Entropy.UGC.get_docs(self.repository, self.pkgkey)
            if not isinstance(docs_data,tuple):
                self.ugc_data = {}
            else:
                self.ugc_data = self.digest_remote_docs_data(docs_data)
            self.ugc_status_message = err_msg
        else:
            self.ugc_data = self.digest_remote_docs_data(docs_cache)

        self.refresh_ugc_view()
        self.hide_loading()

    def digest_remote_docs_data(self, data):
        newdata = {}
        for mydict in data:
            if not mydict:
                continue
            if not newdata.has_key(mydict['iddoctype']):
                newdata[mydict['iddoctype']] = []
            newdata[mydict['iddoctype']].append(mydict)
        return newdata

    def refresh_ugc_view(self):
        self.ugcModel.clear()
        if self.ugc_data == None: return
        self.populate_ugc_view()
        #self.ugcView.expand_all()

    def spawn_docs_fetch(self):
        if self.ugc_data == None: return
        if self.repository == None: return

        for doc_type in self.ugc_data:
            if int(doc_type) not in (etpConst['ugc_doctypes']['image'],):
                continue
            for mydoc in self.ugc_data[doc_type]:
                if not mydoc.has_key('store_url'):
                    continue
                if not mydoc['store_url']:
                    continue
                store_path = self.Entropy.UGC.UGCCache.get_stored_document(mydoc['iddoc'], self.repository, mydoc['store_url'])
                if store_path == None:
                    self.Entropy.UGC.UGCCache.store_document(mydoc['iddoc'], self.repository, mydoc['store_url'])
                    store_path = self.Entropy.UGC.UGCCache.get_stored_document(mydoc['iddoc'], self.repository, mydoc['store_url'])
                if (store_path != None) and os.access(store_path,os.R_OK):
                    try:
                        preview_path = store_path+".preview"
                        if not os.path.isfile(preview_path) and (os.stat(store_path)[6] < 1024000):
                            # resize pix
                            img = gtk.Image()
                            img.set_from_file(store_path)
                            img_buf = img.get_pixbuf()
                            w, h = img_buf.get_width(),img_buf.get_height()
                            new_w = 64.0
                            new_h = new_w*h/w
                            img_buf = img_buf.scale_simple(int(new_w),int(new_h),gtk.gdk.INTERP_BILINEAR)
                            img_buf.save(preview_path, "png")
                            del img, img_buf
                        if os.path.isfile(preview_path):
                            mydoc['preview_path'] = preview_path
                    except:
                        continue

    def populate_ugc_view(self):

        if self.ugc_data == None: return

        spawn_fetch = False
        doc_types = self.ugc_data.keys()
        doc_type_image_map = {
            1: const.ugc_text_pix,
            2: const.ugc_text_pix,
            3: const.ugc_image_pix,
            4: const.ugc_generic_pix,
            5: const.ugc_video_pix,
        }
        doc_type_background_map = {
            1:('#67AB6F','#599360'),
            2:('#67AB6F','#599360'),
            3:('#AB8158','#CA9968'),
            4:('#BBD5B0','#99AE90'),
            5:('#A5C0D5','#8EA5B7'),
        }
        doc_type_foreground_map = {
            1:'#FFFFFF',
            2:'#FFFFFF',
            3:'#FFFFFF',
            4:'#FFFFFF',
            5:'#FFFFFF',
        }
        counter = 1
        for doc_type in doc_types:
            spawn_fetch = True
            image_path = doc_type_image_map.get(int(doc_type))
            cat_dict = {
                'is_cat': True,
                'image_path': image_path,
                'parent_desc': "%s (%s)" % (etpConst['ugc_doctypes_description'].get(int(doc_type)),len(self.ugc_data[doc_type]),),
                'foreground': doc_type_foreground_map.get(int(doc_type)),
                'background': doc_type_background_map.get(int(doc_type)),
            }
            parent = self.ugcModel.append( None, (cat_dict,) )
            docs_dates = {}
            for mydoc in self.ugc_data[doc_type]:
                ts = mydoc['ts']
                if not docs_dates.has_key(ts):
                    docs_dates[ts] = []
                docs_dates[ts].append(mydoc)
            sorted_dates = sorted(docs_dates.keys())
            for ts in sorted_dates:
                for mydoc in docs_dates[ts]:
                    mydoc['image_path'] = const.ugc_pixmap_small
                    mydoc['foreground'] = doc_type_foreground_map.get(int(doc_type))
                    mydoc['background'] = doc_type_background_map.get(int(doc_type))
                    mydoc['counter'] = counter
                    self.ugcModel.append( parent, (mydoc,) )
                    counter += 1

        if spawn_fetch:
            self.ugc_preview_fetcher = self.Entropy.entropyTools.parallelTask(self.spawn_docs_fetch)
            self.ugc_preview_fetcher.parallel_wait()
            self.ugc_preview_fetcher.start()

        #search_col = 0
        #self.view.set_search_column( search_col )
        #self.view.set_search_equal_func(self.atom_search)
        self.ugcView.set_property('headers-visible',True)
        self.ugcView.set_property('enable-search',True)
        self.ugcView.show_all()

    def on_infoBook_switch_page(self, widget, page, page_num):
        if (page_num == self.ugc_page_idx) and (not self.switched_to_ugc_page):
            self.switched_to_ugc_page = True
            self.on_loadUgcButton_clicked(widget, force = False)

    def on_star5_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 5)

    def on_star4_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 4)

    def on_star3_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 3)

    def on_star2_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 2)

    def on_star1_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 1)

    def on_starsEvent_leave_notify_event(self, widget, event):
        normalCursor(self.pkginfo_ui.pkgInfo)
        self.set_stars(self.vote)

    def on_starsEvent_enter_notify_event(self, widget, event):
        busyCursor(self.pkginfo_ui.pkgInfo, cur = gtk.gdk.Cursor(gtk.gdk.CROSSHAIR))

    def on_starEvent5_button_release_event(self, widget, event):
        self.vote_click(5)

    def on_starEvent4_button_release_event(self, widget, event):
        self.vote_click(4)

    def on_starEvent3_button_release_event(self, widget, event):
        self.vote_click(3)

    def on_starEvent2_button_release_event(self, widget, event):
        self.vote_click(2)

    def on_starEvent1_button_release_event(self, widget, event):
        self.vote_click(1)

    def vote_click(self, vote):
        if self.Entropy.UGC == None:
            return
        if not (self.repository and self.pkgkey):
            return
        if not self.Entropy.UGC.is_repository_eapi3_aware(self.repository):
            return
        status, err_msg = self.Entropy.UGC.add_vote(self.repository, self.pkgkey, vote)
        if status:
            self.set_stars_from_repository()
            msg = "<small><span foreground='#339101'>%s</span>: %s</small>" % (_("Vote registered successfully"),vote,)
        else:
            msg = "<small><span foreground='#FF0000'>%s</span>: %s</small>" % (_("Error registering vote"),err_msg,)

        self.pkginfo_ui.ugcMessageBox.set_markup(msg)

    def star_enter(self, widget, event, number):
        self.set_stars(number, hover = True)

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

        # useflags view
        self.useflagsView = self.pkginfo_ui.useflagsView
        self.useflagsModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "USE flags" ), cell, markup = 0 )
        self.useflagsView.append_column( column )
        self.useflagsView.set_model( self.useflagsModel )

        # eclasses view
        self.eclassesView = self.pkginfo_ui.eclassesView
        self.eclassesModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Eclasses" ), cell, markup = 0 )
        self.eclassesView.append_column( column )
        self.eclassesView.set_model( self.eclassesModel )

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
        self.configProtectView = self.pkginfo_ui.configProtectView1
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

        # ugc view
        self.ugcView = self.pkginfo_ui.ugcView
        self.ugcModel = gtk.TreeStore( gobject.TYPE_PYOBJECT )

        # Setup image column
        cell = gtk.CellRendererPixbuf()
        cell.set_property('height', 78)
        column = gtk.TreeViewColumn( _("Type"), cell ) # Document Type
        column.set_cell_data_func( cell, self.ugc_pixbuf )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 120 )
        column.set_sort_column_id( -1 )
        self.ugcView.append_column( column )

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Content" ), cell )
        column.set_resizable( True )
        column.set_cell_data_func( cell, self.ugc_content )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 350 )
        column.set_expand(True)
        column.set_sort_column_id( -1 )
        self.ugcView.append_column( column )
        self.ugcView.set_model( self.ugcModel )

        self.ugcView.set_property('headers-visible',True)
        self.ugcView.set_property('enable-search',True)


    def set_stars(self, count, hover = False):
        pix_path = self.star_normal_pixmap
        if hover: pix_path = self.star_selected_pixmap
        pix_path_empty = self.star_empty_pixmap

        widgets = [
        self.pkginfo_ui.vote1,
        self.pkginfo_ui.vote2,
        self.pkginfo_ui.vote3,
        self.pkginfo_ui.vote4,
        self.pkginfo_ui.vote5
        ]
        if count > len(widgets):
            count = len(widgets)
        if count < 0: count = 0
        idx = -1
        while count > -1:
            w = widgets[count-1]
            w.set_from_file(pix_path)
            w.show()
            count -= 1
            idx += 1
        mycount = len(widgets) - idx
        while mycount:
            w = widgets[idx]
            w.set_from_file(pix_path_empty)
            w.show()
            mycount -= 1
            idx += 1

    def set_stars_from_repository(self):
        if not (self.repository and self.pkgkey):
            return
        vote = self.Entropy.UGC.UGCCache.get_package_vote(self.repository, self.pkgkey)
        if isinstance(vote,float):
            self.set_stars(int(vote))
            self.vote = int(vote)

    def load(self):

        pkg = self.pkg
        dbconn = self.pkg.dbconn
        avail = False
        if dbconn:
            avail = dbconn.isIDPackageAvailable(pkg.matched_atom[0])
        if not avail:
            return
        from_repo = True
        if isinstance(pkg.matched_atom[1],int): from_repo = False
        if from_repo and pkg.matched_atom[1] not in self.Entropy.validRepositories:
            return

        # set package image
        pkgatom = pkg.name
        self.vote = int(pkg.vote)
        self.repository = pkg.repoid
        self.pkgkey = self.Entropy.entropyTools.dep_getkey(pkgatom)
        self.set_stars_from_repository()
        self.pkginfo_ui.pkgImage.set_from_file(self.pkg_pixmap)
        self.pkginfo_ui.ugcSmallIcon.set_from_file(self.ugc_small_pixmap)
        self.pkginfo_ui.ugcIcon.set_from_file(self.ugc_pixmap)
        self.pkginfo_ui.refreshImage.set_from_file(self.refresh_pixmap)

        self.pkginfo_ui.labelAtom.set_markup("<b>%s</b>" % (cleanMarkupString(pkgatom),))
        self.pkginfo_ui.labelDescription.set_markup("<small>%s</small>" % (pkg.description,))
        self.pkginfo_ui.ugcDescriptionLabel.set_markup("<small>%s\n%s</small>" % (
                _("Share your opinion, your documents, your screenshots!"),
                _("Be part of our Community!")
            )
        )
        self.pkginfo_ui.ugcDownloaded.set_markup(
            "<small>%s: <b>%s</b></small>" % (_("Number of downloads"), pkg.downloads,)
        )

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
                        self.pkginfo_ui.chostLabel,
                        self.pkginfo_ui.cflagsLabel,
                        self.pkginfo_ui.cxxflagsLabel,
                        self.pkginfo_ui.maskedLabel,
                        self.pkginfo_ui.messagesLabel,
                        self.pkginfo_ui.triggerLabel,
                        self.pkginfo_ui.configProtectLabel,
                        self.pkginfo_ui.ugcTitleLabel
        ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<b>%s</b>" % (t,))

        repo = pkg.matched_atom[1]
        if repo == 0:
            self.pkginfo_ui.location.set_markup("%s" % (_("From your Operating System"),))
        else:
            self.pkginfo_ui.location.set_markup("%s" % (cleanMarkupString(etpRepositories[repo]['description']),))

        self.pkginfo_ui.version.set_markup( "%s" % (cleanMarkupString(pkg.onlyver),) )
        tag = pkg.tag
        if not tag: tag = "None"
        self.pkginfo_ui.tag.set_markup( "%s" % (tag,) )
        self.pkginfo_ui.slot.set_markup( "%s" % (pkg.slot,) )
        self.pkginfo_ui.revision.set_markup( "%s" % (pkg.revision,) )
        self.pkginfo_ui.branch.set_markup( "%s" % (pkg.release,) )
        self.pkginfo_ui.eapi.set_markup( "%s" % (pkg.api,) )
        self.pkginfo_ui.homepage.set_markup( "%s" % (cleanMarkupString(pkg.homepage),) )

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
        for x in pkg.keywords:
            self.keywordsModel.append(None,[x])

        # useflags view
        self.useflagsModel.clear()
        self.useflagsView.set_model( self.useflagsModel )
        for x in pkg.useflags:
            self.useflagsModel.append([cleanMarkupString(x)])

        # eclasses view
        self.eclassesModel.clear()
        self.eclassesView.set_model( self.eclassesModel )
        for x in pkg.eclasses:
            self.eclassesModel.append([cleanMarkupString(x)])

        # dependencies view
        self.dependenciesModel.clear()
        self.dependenciesView.set_model( self.dependenciesModel )
        deps = pkg.dependencies
        conflicts = pkg.conflicts
        for x in deps:
            self.dependenciesModel.append(None,[cleanMarkupString(x)])
        for x in conflicts:
            self.dependenciesModel.append(None,[cleanMarkupString("!"+x)])

        # depends view
        self.dependsModel.clear()
        self.dependsView.set_model( self.dependsModel )
        depends = pkg.dependsFmt
        for x in depends:
            self.dependsModel.append(None,[cleanMarkupString(x)])

        # needed view
        self.neededModel.clear()
        self.neededView.set_model( self.neededModel )
        neededs = pkg.needed
        for x in neededs:
            self.neededModel.append(None,[cleanMarkupString(x)])

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

class UGCInfoMenu(MenuSkel):

    def __init__(self, Entropy, obj, repository, window):

        import subprocess
        self.subprocess = subprocess
        self.repository = repository
        self.window = window
        self.Entropy = Entropy
        self.ugc_data = obj.copy()
        self.ugcinfo_ui = UI( const.GLADE_FILE, 'ugcInfo', 'entropy' )
        self.ugcinfo_ui.signal_autoconnect(self._getAllMethods())
        self.ugcinfo_ui.ugcInfo.set_transient_for(self.window)
        self.ugcinfo_ui.ugcInfo.add_events(gtk.gdk.BUTTON_PRESS_MASK)

    def on_closeInfo_clicked(self, widget, path = None):
        self.ugcinfo_ui.ugcInfo.hide()
        return True

    def on_getButton_clicked(self, widget):
        if self.ugc_data['store_url'] != None:
            self.subprocess.call(['xdg-open',self.ugc_data['store_url']])

    def load(self):

        pix_path = self.ugc_data['image_path']
        if self.ugc_data.has_key('preview_path'):
            if os.path.isfile(self.ugc_data['preview_path']) and os.access(self.ugc_data['preview_path'],os.R_OK):
                pix_path = self.ugc_data['preview_path']
        self.ugcinfo_ui.ugcImage.set_from_file(pix_path)
        self.ugcinfo_ui.labelKey.set_markup("<b>%s</b>" % (self.ugc_data['pkgkey'],))
        doc_type_desc = etpConst['ugc_doctypes_description_singular'].get(int(self.ugc_data['iddoctype']))
        self.ugcinfo_ui.labelTypedesc.set_markup("<small>[<b>%s</b>:%d] <i>%s</i></small>" % (
                _("Id"),
                int(self.ugc_data['iddoc']),
                doc_type_desc,
            )
        )
        self.ugcinfo_ui.titleContent.set_markup("%s" % (unicode(self.ugc_data['title'],'raw_unicode_escape'),))
        self.ugcinfo_ui.descriptionContent.set_markup("%s" % (unicode(self.ugc_data['description'],'raw_unicode_escape'),))
        self.ugcinfo_ui.authorContent.set_markup("<i>%s</i>" % (unicode(self.ugc_data['username'],'raw_unicode_escape'),))
        self.ugcinfo_ui.dateContent.set_markup("<u>%s</u>" % (self.ugc_data['ts'],))
        self.ugcinfo_ui.keywordsContent.set_markup("%s" % (unicode(', '.join(self.ugc_data['keywords']),'raw_unicode_escape'),))
        self.ugcinfo_ui.sizeContent.set_markup("%s" % (self.Entropy.entropyTools.bytesIntoHuman(self.ugc_data['size']),))

        bold_items = [
            self.ugcinfo_ui.titleLabel,
            self.ugcinfo_ui.descLabel,
            self.ugcinfo_ui.authorLabel,
            self.ugcinfo_ui.dateLabel,
            self.ugcinfo_ui.keywordsLabel,
            self.ugcinfo_ui.sizeLabel
        ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<b>%s</b>" % (t,))

        small_items = bold_items
        small_items += [
            self.ugcinfo_ui.titleContent,
            self.ugcinfo_ui.descriptionContent,
            self.ugcinfo_ui.authorContent,
            self.ugcinfo_ui.dateContent,
            self.ugcinfo_ui.keywordsContent,
            self.ugcinfo_ui.sizeContent
        ]
        for item in small_items:
            t = item.get_label()
            item.set_markup("<small>%s</small>" % (t,))

        if self.ugc_data['iddoctype'] in (etpConst['ugc_doctypes']['comments'], etpConst['ugc_doctypes']['bbcode_doc'],):
            self.ugcinfo_ui.ugcTable.remove(self.ugcinfo_ui.descLabel)
            self.ugcinfo_ui.ugcTable.remove(self.ugcinfo_ui.descriptionContent)
            self.ugcinfo_ui.buttonBox.hide()
            mybuf = gtk.TextBuffer()
            mybuf.set_text(unicode(self.ugc_data['ddata'].tostring(),'raw_unicode_escape'))
            self.ugcinfo_ui.textContent.set_buffer(mybuf)
        else:
            self.ugcinfo_ui.textFrame.hide()

        self.ugcinfo_ui.ugcInfo.show()


class UGCAddMenu(MenuSkel):

    def __init__(self, Entropy, pkgkey, repository, window, refresh_cb):

        self.loading_pix = gtk.image_new_from_file(const.loading_pix)
        self.repository = repository
        self.pix_path = const.ugc_pixmap
        self.pkgkey = pkgkey
        self.window = window
        self.Entropy = Entropy
        self.ugcadd_ui = UI( const.GLADE_FILE, 'ugcAdd', 'entropy' )
        self.ugcadd_ui.signal_autoconnect(self._getAllMethods())
        self.ugcadd_ui.ugcAdd.set_transient_for(self.window)
        self.ugcadd_ui.ugcAdd.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.store = None
        self.refresh_cb = refresh_cb
        self.text_types = (etpConst['ugc_doctypes']['comments'],etpConst['ugc_doctypes']['bbcode_doc'],)
        self.file_selected = None

    def on_closeAdd_clicked(self, widget, path = None):
        self.ugcadd_ui.ugcAdd.hide()
        return True

    def on_ugcAddTypeCombo_changed(self, widget):
        myiter = widget.get_active_iter()
        idx = self.store.get_value( myiter, 0 )
        if idx in self.text_types:
            txt = "%s %s" % (_("Write your"),etpConst['ugc_doctypes_description_singular'][idx],) # write your <document type>
            self.setup_text_insert()
        else:
            txt = "%s %s" % (_("Select your"),etpConst['ugc_doctypes_description_singular'][idx],) # select your <document type>
            self.setup_file_insert(txt)

    def on_ugcAddFileChooser_file_set(self, widget):
        self.file_selected = widget.get_filename()

    def on_submitButton_clicked(self, widget):
        dialog_title = _("Submit issue")
        myiter = self.ugcadd_ui.ugcAddTypeCombo.get_active_iter()
        doc_type = self.store.get_value( myiter, 0 )
        title = self.ugcadd_ui.ugcAddTitleEntry.get_text()
        description = self.ugcadd_ui.ugcAddDescEntry.get_text()
        keywords_text = self.ugcadd_ui.ugcAddKeywordsEntry.get_text()
        doc_path = None
        if doc_type in self.text_types:
            mybuf = self.ugcadd_ui.ugcAddTextView.get_buffer()
            start_iter = mybuf.get_start_iter()
            end_iter = mybuf.get_end_iter()
            description = mybuf.get_text(start_iter, end_iter)
            if not description:
                okDialog(self.window, _("Empty Document"), title = dialog_title)
                return False
        else:
            if not description:
                okDialog(self.window, _("Invalid Description"), title = dialog_title)
                return False
            doc_path = self.file_selected

        # checking
        if doc_type == None:
            okDialog(self.window, _("Invalid Document Type"), title = dialog_title)
            return False
        if not title:
            okDialog(self.window, _("Invalid Title"), title = dialog_title)
            return False

        # confirm ?
        rc = self.Entropy.askQuestion(_("Do you confirm your submission?"))
        if rc != "Yes":
            return False

        self.show_loading()
        try:
            rslt, data = self.Entropy.UGC.send_document_autosense(
                self.repository,
                str(self.pkgkey),
                doc_type,
                doc_path,
                title,
                description,
                keywords_text
            )
        except Exception, e:
            rslt = False
            data = e
        self.hide_loading()
        if not rslt:
            txt = "<small><span foreground='#FF0000'><b>%s</b></span>: %s | %s</small>" % (_("UGC Error"),rslt,data,)
            self.ugcadd_ui.ugcAddStatusLabel.set_markup(txt)
            return False
        else:
            okDialog(self.window, _("Document added successfully. Thank you"), title = _("Success!"))
            self.on_closeAdd_clicked(None,None)
            self.refresh_cb()
            return True

    def show_loading(self):
        self.ugcadd_ui.ugcAddButtonBox.hide()
        self.ugcadd_ui.closeAdd.set_sensitive(False)
        self.ugcadd_ui.ugcAddLoadingEvent.show_all()
        self.ugcadd_ui.ugcAddLoadingEvent.add(self.loading_pix)
        self.ugcadd_ui.ugcAddLoadingEvent.show_all()
        self.ugcadd_ui.ugcAdd.queue_draw()

    def hide_loading(self):
        self.ugcadd_ui.ugcAddButtonBox.show()
        self.ugcadd_ui.closeAdd.set_sensitive(True)
        self.ugcadd_ui.ugcAddLoadingEvent.remove(self.loading_pix)
        self.ugcadd_ui.ugcAddLoadingEvent.hide()
        self.ugcadd_ui.ugcAdd.queue_draw()

    def setup_text_insert(self, txt = _("Write your document")):
        self.ugcadd_ui.ugcAddFileChooser.hide()
        self.ugcadd_ui.ugcAddFrame.show()
        self.ugcadd_ui.ugcAddDescLabel.hide()
        self.ugcadd_ui.ugcAddDescEntry.hide()
        self.ugcadd_ui.ugcAddInsertLabel.set_markup(txt)

    def setup_file_insert(self, txt = _("Select your file")):
        self.ugcadd_ui.ugcAddFileChooser.show()
        self.ugcadd_ui.ugcAddFrame.hide()
        self.ugcadd_ui.ugcAddDescLabel.show()
        self.ugcadd_ui.ugcAddDescEntry.show()
        self.ugcadd_ui.ugcAddInsertLabel.set_markup(txt)

    def load(self):

        self.ugcadd_ui.ugcAddImage.set_from_file(self.pix_path)
        self.ugcadd_ui.labelAddKey.set_markup("<b>%s</b>" % (self.pkgkey,))
        self.ugcadd_ui.labelAddRepo.set_markup("<small>%s: <b>%s</b></small>" % (_("On repository"),self.repository,))

        # add types to combo
        doc_types_list = sorted(etpConst['ugc_doctypes_description_singular'].keys())
        self.store = gtk.ListStore( gobject.TYPE_INT, gobject.TYPE_STRING )
        self.ugcadd_ui.ugcAddTypeCombo.set_model(self.store)
        cell = gtk.CellRendererText()
        self.ugcadd_ui.ugcAddTypeCombo.pack_start(cell, True)
        self.ugcadd_ui.ugcAddTypeCombo.add_attribute(cell, 'text', 1)
        for idx in doc_types_list:
            # disable bbcode for now
            if idx == etpConst['ugc_doctypes']['bbcode_doc']:
                continue
            self.store.append( (idx, etpConst['ugc_doctypes_description_singular'][idx],) )
        self.ugcadd_ui.ugcAddTypeCombo.set_active(0)

        # hide file chooser
        self.setup_text_insert()

        bold_items = [
            self.ugcadd_ui.ugcAddTitleLabel,
            self.ugcadd_ui.ugcAddDescLabel,
            self.ugcadd_ui.ugcAddTypeLabel,
            self.ugcadd_ui.ugcAddKeywordsLabel
        ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<b>%s</b>" % (t,))

        self.ugcadd_ui.ugcAdd.show()


class MaskedPackagesDialog:

    def __init__( self, Entropy, etpbase, parent, pkgs, top_text = None, sub_text = None ):
        self.Entropy = Entropy
        self.etpbase = etpbase
        self.xml = gtk.glade.XML( const.GLADE_FILE, 'maskdialog', domain="entropy" )
        self.dialog = self.xml.get_widget( "maskdialog" )
        self.dialog.set_transient_for( parent )
        self.action = self.xml.get_widget( "maskAction" )
        self.subaction = self.xml.get_widget( "maskSubtext" )
        self.cancelbutton = self.xml.get_widget( "cancelbutton" )
        self.okbutton = self.xml.get_widget( "okbutton" )
        self.enableButton = self.xml.get_widget( "enableButton" )
        self.enableButton.connect("clicked", self.enablePackage)
        self.enableAllButton = self.xml.get_widget( "enableAllButton" )
        self.enableAllButton.connect("clicked", self.enableAllPackages)
        self.propertiesButton = self.xml.get_widget( "propertiesButton" )
        self.propertiesButton.connect("clicked", self.openPackageProperties)
        self.docancel = True

        # setup text
        if top_text == None:
            top_text = _("These are the packages that must be enabled to satisfy your request")

        tit = "<b><span foreground='#0087C1' size='large'>%s</span></b>\n" % (_("Some packages are masked"),)
        tit += top_text
        self.action.set_markup( tit )
        if sub_text != None: self.subaction.set_markup( sub_text )

        self.pkgs = pkgs
        self.pkg = self.xml.get_widget( "maskPkg" )
        # fill
        self.model = self.setup_view( self.pkg )
        self.show_data( self.model, self.pkgs )
        self.pkg.expand_all()
        self.pkgcount = 0
        self.maxcount = len(self.pkgs)

    def get_obj(self):
        model, myiter = self.pkg.get_selection().get_selected()
        if myiter:
            return model.get_value( myiter, 0 )
        return None

    def openPackageProperties(self, widget):
        obj = self.get_obj()
        if not obj:
            return
        mymenu = PkgInfoMenu(self.Entropy, obj, self.dialog)
        mymenu.load()

    def enablePackage(self, widget, obj = None, do_refresh = True):
        if not obj:
            obj = self.get_obj()
        if not obj:
            return
        result = self.Entropy.unmask_match(obj.matched_atom, dry_run = True)
        if result:
            self.etpbase.unmaskingPackages.add(obj.matched_atom)
            self.pkgcount += 1
            if do_refresh:
                self.refresh()
        return result

    def enableAllPackages(self, widget):

        for parent in self.model:
            for child in parent.iterchildren():
                for obj in child:
                    if not obj:
                        continue
                    if obj.dummy_type != None:
                        continue
                    self.enablePackage(None,obj,False)
        self.refresh()

    def refresh(self):
        self.pkg.queue_draw()
        self.pkg.expand_all()

    def run( self ):
        self.dialog.show_all()
        self.okbutton.set_sensitive(False)
        return self.dialog.run()

    def setup_view( self, view ):

        model = gtk.TreeStore( gobject.TYPE_PYOBJECT )
        view.set_model( model )

        cell1 = gtk.CellRendererText()
        column1 = gtk.TreeViewColumn( _( "Masked package" ), cell1 )
        column1.set_cell_data_func( cell1, self.show_pkg )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( 420 )
        column1.set_resizable( False )
        view.append_column( column1 )

        cell2 = gtk.CellRendererPixbuf()
        column2 = gtk.TreeViewColumn( _("Enabled"), cell2 )
        column2.set_cell_data_func( cell2, self.new_pixbuf )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 60 )
        column2.set_sort_column_id( -1 )
        view.append_column( column2 )
        column2.set_clickable( False )

        return model


    def set_pixbuf_to_cell(self, cell, do):
        if do:
            cell.set_property( 'stock-id', 'gtk-apply' )
        elif do == False:
            cell.set_property( 'stock-id', 'gtk-cancel' )
        else:
            cell.set_property( 'stock-id', None )

    def new_pixbuf( self, column, cell, model, iterator ):

        if self.pkgcount >= self.maxcount:
            self.okbutton.set_sensitive(True)

        obj = model.get_value( iterator, 0 )
        if obj.matched_atom in self.etpbase.unmaskingPackages:
            self.set_pixbuf_to_cell(cell, True)
        elif obj.dummy_type:
            self.set_pixbuf_to_cell(cell, None)
        else:
            self.set_pixbuf_to_cell(cell, False)
        self.set_line_status(obj, cell, stype = "cell-background")

    def show_pkg( self, column, cell, model, iterator ):
        obj = model.get_value( iterator, 0 )
        mydata = getattr( obj, 'namedesc' )
        cell.set_property('markup', mydata )
        self.set_line_status(obj, cell)

    def set_line_status(self, obj, cell, stype = "cell-background"):
        if obj.queued == "r":
            cell.set_property(stype,'#FFE2A3')
        elif obj.queued == "u":
            cell.set_property(stype,'#B7BEFF')
        elif obj.queued == "i":
            cell.set_property(stype,'#D895FF')
        elif obj.queued == "rr":
            cell.set_property(stype,'#B7BEFF')
        elif not obj.queued:
            cell.set_property(stype,None)

    def show_data( self, model, pkgs ):

        model.clear()
        self.pkg.set_model(None)
        self.pkg.set_model(model)

        desc_len = 80
        search_col = 0
        categories = {}

        for po in pkgs:
            mycat = po.cat
            if not categories.has_key(mycat):
                categories[mycat] = []
            categories[mycat].append(po)

        cats = categories.keys()
        cats.sort()
        for category in cats:
            cat_desc = _("No description")
            cat_desc_data = self.Entropy.get_category_description_data(category)
            if cat_desc_data.has_key(_LOCALE):
                cat_desc = cat_desc_data[_LOCALE]
            elif cat_desc_data.has_key('en'):
                cat_desc = cat_desc_data['en']
            cat_text = "<b><big>%s</big></b>\n<small>%s</small>" % (category,cleanMarkupString(cat_desc),)
            mydummy = packages.DummyEntropyPackage(
                    namedesc = cat_text,
                    dummy_type = SpritzConf.dummy_category,
                    onlyname = category
            )
            mydummy.color = '#9C7234'
            parent = model.append( None, (mydummy,) )
            for po in categories[category]:
                model.append( parent, (po,) )

        self.pkg.set_search_column( search_col )
        self.pkg.set_search_equal_func(self.atom_search)
        self.pkg.set_property('headers-visible',True)
        self.pkg.set_property('enable-search',True)

    def atom_search(self, model, column, key, iterator):
        obj = model.get_value( iterator, 0 )
        if obj:
            return not obj.onlyname.startswith(key)
        return True

    def destroy( self ):
        return self.dialog.destroy()

class ConfirmationDialog:

    def __init__( self, parent, pkgs, top_text = None, bottom_text = None, bottom_data = None, sub_text = None, cancel = True, simpleList = False, simpleDict = False ):

        self.xml = gtk.glade.XML( const.GLADE_FILE, 'confirmation', domain="entropy" )
        self.dialog = self.xml.get_widget( "confirmation" )
        self.dialog.set_transient_for( parent )
        self.action = self.xml.get_widget( "confAction" )
        self.subaction = self.xml.get_widget( "confSubtext" )
        self.bottomTitle = self.xml.get_widget( "bottomTitle" )
        self.bottomData = self.xml.get_widget( "bottomData" )
        self.cancelbutton = self.xml.get_widget( "cancelbutton2" )
        self.bottomtext = self.xml.get_widget( "bottomTitle" )
        self.lowerhbox = self.xml.get_widget( "hbox63" )

        self.dobottomtext = bottom_text
        self.dobottomdata = bottom_data
        self.docancel = cancel
        self.simpleList = simpleList
        self.simpleDict = simpleDict

        # setup text
        if top_text == None:
            top_text = _("Please confirm the actions above")

        if sub_text == None:
            sub_text = ""

        tit = "<span size='x-large'>%s</span>" % (top_text,)
        self.action.set_markup( tit )
        if bottom_text != None: self.bottomTitle.set_markup( bottom_text )
        if bottom_data != None: self.bottomData.set_text( bottom_data )
        if sub_text != None: self.subaction.set_text( sub_text )

        self.pkgs = pkgs
        self.pkg = self.xml.get_widget( "confPkg" )
        if self.simpleList:
            self.pkgModel = self.setup_simple_view( self.pkg )
            self.show_data_simple( self.pkgModel, pkgs )
        elif self.simpleDict:
            self.pkgModel = self.setup_simple_view( self.pkg )
            self.show_data_simpledict( self.pkgModel, pkgs )
        else:
            self.pkgModel = self.setup_view( self.pkg )
            self.show_data( self.pkgModel, pkgs )
        self.pkg.expand_all()

    def run( self ):
        self.dialog.show_all()
        if not self.docancel:
            self.cancelbutton.hide()
        if not self.dobottomtext:
            self.bottomtext.hide()
        if not self.dobottomdata:
            self.lowerhbox.hide()
        return self.dialog.run()

    def setup_view( self, view ):
        model = gtk.TreeStore( gobject.TYPE_STRING )
        model.set_sort_column_id( 0, gtk.SORT_ASCENDING )
        view.set_model( model )
        self.create_text_column( _( "Package" ), view, 0 )
        return model

    def setup_simple_view(self, view ):
        model = gtk.TreeStore( gobject.TYPE_STRING )
        view.set_model( model )
        self.create_text_column( _( "Package" ), view, 0 )
        return model

    def create_text_column( self, hdr, view, colno, min_width=0, max_width=0 ):
        cell = gtk.CellRendererText()    # Size Column
        column = gtk.TreeViewColumn( hdr, cell, markup=colno )
        column.set_resizable( True )
        if min_width:
            column.set_min_width( min_width )
        if max_width:
            column.set_max_width( max_width )
        view.append_column( column )

    def show_data_simpledict( self, model, pkgs ):
        model.clear()
        if pkgs.has_key("reinstall"):
            if pkgs['reinstall']:
                label = "<b>%s</b>" % _("To be reinstalled")
                parent = model.append( None, [label] )
                for pkg in pkgs['reinstall']:
                    model.append( parent, [pkg] )
        if pkgs.has_key("install"):
            if pkgs['install']:
                label = "<b>%s</b>" % _("To be installed")
                parent = model.append( None, [label] )
                for pkg in pkgs['install']:
                    model.append( parent, [pkg] )
        if pkgs.has_key("update"):
            if pkgs['update']:
                label = "<b>%s</b>" % _("To be updated")
                parent = model.append( None, [label] )
                for pkg in pkgs['update']:
                    model.append( parent, [pkg] )
        if pkgs.has_key("downgrade"):
            if pkgs['downgrade']:
                label = "<b>%s</b>" % _("To be downgraded")
                parent = model.append( None, [label] )
                for pkg in pkgs['downgrade']:
                    model.append( parent, [pkg] )
        if pkgs.has_key("remove"):
            if pkgs['remove']:
                label = "<b>%s</b>" % _("To be removed")
                parent = model.append( None, [label] )
                for pkg in pkgs['remove']:
                    model.append( parent, [pkg] )

    def show_data_simple( self, model, pkgs ):
        model.clear()
        for pkg in pkgs:
            model.append( None, [pkg] )

    def show_data( self, model, pkgs ):
        model.clear()
        desc_len = 80
        install = [x for x in pkgs if x.action == "i"]
        update = [x for x in pkgs if x.action == "u"]
        remove = [x for x in pkgs if x.action == "r"]
        reinstall = [x for x in pkgs if x.action == "rr"]
        if reinstall:
            label = "<b>%s</b>" % _("To be reinstalled")
            level1 = model.append( None, [label] )
            for pkg in reinstall:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if install:
            label = "<b>%s</b>" % _("To be installed")
            level1 = model.append( None, [label] )
            for pkg in install:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if update:
            label = "<b>%s</b>" % _("To be updated")
            level1 = model.append( None, [label] )
            for pkg in update:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if remove:
            label = "<b>%s</b>" % _("To be removed")
            level1 = model.append( None, [label] )
            for pkg in remove:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                model.append( level1, [mypkg+mydesc] )

    def destroy( self ):
        return self.dialog.destroy()

class ErrorDialog:
    def __init__( self, parent, title, text, longtext, modal ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "errDialog",domain="entropy" )
        self.dialog = self.xml.get_widget( "errDialog" )
        self.parent = parent
        if parent:
            self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "errText" )
        self.longtext = self.xml.get_widget( "errTextView" )
        self.nameInput = self.xml.get_widget( "nameEntry" )
        self.mailInput = self.xml.get_widget( "mailEntry" )
        self.reportLabel = self.xml.get_widget( "reportLabel" )
        self.errorButton = self.xml.get_widget( "errorButton" )
        self.actionInput = self.xml.get_widget( "actionEntry" )
        self.reportTable = self.xml.get_widget( "reportTable" )
        self.style_err = gtk.TextTag( "error" )
        self.style_err.set_property( "style", pango.STYLE_ITALIC )
        self.style_err.set_property( "foreground", "red" )
        self.style_err.set_property( "family", "Monospace" )
        self.style_err.set_property( "size_points", 8 )
        self.longtext.get_buffer().get_tag_table().add( self.style_err )

        if modal:
            self.dialog.set_modal( True )
        if text != "":
            self.set_text( text )
        if longtext != "" and longtext != None:
            self.set_long_text( longtext )

    def set_text( self, text ):
        self.text.set_markup( text )

    def set_long_text( self, longtext ):
        mybuffer = self.longtext.get_buffer()
        start, end = mybuffer.get_bounds()
        mybuffer.insert_with_tags( end, longtext, self.style_err )

    def run( self, showreport = False ):
        self.dialog.show_all()
        if not showreport:
            self.hide_report_widgets()
        return self.dialog.run()

    def hide_report_widgets(self):
        self.reportTable.hide_all()
        self.errorButton.hide()
        self.reportLabel.hide()

    def get_entries( self ):
        mail = self.mailInput.get_text()
        name = self.nameInput.get_text()
        desc = self.actionInput.get_text()
        return name,mail,desc

    def destroy( self ):
        return self.dialog.destroy()

class infoDialog:
    def __init__( self, parent, title, text ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "msg",domain="entropy" )
        self.dialog = self.xml.get_widget( "msg" )
        self.parent = parent
        self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "msgText" )
        self.dialog.set_modal( True )
        self.set_text( text )

    def set_text( self, text ):
        self.text.set_markup( "<span size='large'>%s</span>" % text )

    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()

    def destroy( self ):
        return self.dialog.destroy()


class EntryDialog:
    def __init__( self, parent, title, text ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "EntryDialog",domain="entropy" )
        self.dialog = self.xml.get_widget( "EntryDialog" )
        self.parent = parent
        #self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "inputLabel" )
        self.entry = self.xml.get_widget( "inputEntry" )
        self.dialog.set_modal( True )
        self.text.set_text( text )

    def run( self ):
        self.dialog.show_all()
        rc = self.dialog.run()
        if rc == gtk.RESPONSE_OK:
            return self.entry.get_text()
        else:
            return None

    def destroy( self ):
        return self.dialog.destroy()

class AboutDialog(gtk.Window):

    """ Class for a fancy "About" dialog.
        Mostly ripped from the one in gDesklets
    """

    def __init__(self, gfx, creditText, title = "Spritz Package Manager"):

        self.__is_stopped = True
        self.__scroller_values = ()


        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_resizable(False)
        self.set_title("%s %s" % (_("About"),title,))
        self.connect("button-press-event", self.__on_close)
        self.connect("key-press-event", self.__on_close)
        self.connect("delete-event", self.__on_close)
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.set_decorated(False)

        fixed = gtk.Fixed()
        self.add(fixed)

        img = gtk.Image()
        img.set_from_file(gfx)
        fixed.put(img, 0, 0)

        width, height = img.size_request()

        scroller = gtk.Fixed()
        scroller.set_size_request(width, height - 32)
        fixed.put(scroller, 0, 32)

        text = ""
        for header, body in creditText:
            text += "<b>" + header + "</b>\n\n"
            text += "\n".join(body)
            text += "\n\n\n\n"
        text = "<big>" + text.strip() + "</big>"

        mycredits = gtk.Label("<span foreground='#FFFFFF'>%s</span>" % (text,))
        mycredits.set_use_markup(True)
        mycredits.set_justify(gtk.JUSTIFY_CENTER)

        lbl_width, lbl_height = mycredits.size_request()
        scroller.put(mycredits, (width - lbl_width) / 2, height)

        self.__scroller = scroller
        self.__credits = mycredits

        self.__scroller_values = (height - 32, -lbl_height,
                                  (width - lbl_width) / 2)


    def __scroll(self, ycoord):

        begin, end, xcoord = self.__scroller_values
        self.__scroller.move(self.__credits, xcoord, ycoord)
        ycoord -= 1

        if (ycoord < end):
            ycoord = begin

        if (not self.__is_stopped):
            gobject.timeout_add(50, self.__scroll, ycoord)

        return False


    def __on_close(self, *args):

        self.__is_stopped = True
        self.hide()
        return True


    def show(self):

        if (not self.__is_stopped):
            return

        self.show_all()

        self.__is_stopped = False
        begin, end, xcoord = self.__scroller_values
        gobject.timeout_add(0, self.__scroll, begin)


def inputBox( parent, title, text, input_text = None):
    dlg = EntryDialog(parent, title, text)
    if input_text:
        dlg.entry.set_text(input_text)
    rc = dlg.run()
    dlg.destroy()
    return rc

def FileChooser(basedir = None, pattern = None):
    # open file selector
    dialog = gtk.FileChooserDialog(
        title = None,
        action = gtk.FILE_CHOOSER_ACTION_OPEN,
        buttons = (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK)
    )
    if not basedir:
        basedir = os.getenv('HOME')
        if not basedir:
            basedir = "/tmp"

    fn = None
    dialog.set_current_folder(basedir)
    if pattern:
        myfilter = gtk.FileFilter()
        myfilter.add_pattern(pattern)
        dialog.set_filter(myfilter)
    response = dialog.run()
    if response == gtk.RESPONSE_OK:
        fn = dialog.get_filename()
    dialog.destroy()
    return fn

def errorMessage( parent, title, text, longtext=None, modal= True, showreport = False ):
     dlg = ErrorDialog( parent, title, text, longtext, modal )
     rc = dlg.run(showreport)
     entries = dlg.get_entries()
     dlg.destroy()
     return rc, entries

def infoMessage( parent, title, text ):
    dlg = infoDialog( parent, title, text )
    rc = dlg.run()
    dlg.destroy()
    return not rc == gtk.RESPONSE_OK

def questionDialog(parent, msg, title = _("Spritz Question"), get_response = False):
    dlg = gtk.MessageDialog(
        parent=parent,
        type = gtk.MESSAGE_QUESTION,
        buttons = gtk.BUTTONS_YES_NO,
        message_format = _("Hey!")
    )
    dlg.set_title(title)
    dlg.format_secondary_markup(cleanMarkupString(msg))
    rc = dlg.run()
    dlg.destroy()
    if get_response:
        return rc
    if rc == gtk.RESPONSE_YES:
        return True
    return False

def choiceDialog(parent, msg, title, buttons):
    return MessageDialog(parent, title, msg, type = "custom", custom_buttons = buttons).getrc()

def inputDialog(parent, title, input_parameters, cancel):
    w = InputDialog(parent, title, input_parameters, cancel)
    return w.run()

def okDialog(parent, msg, title = None):
    dlg = gtk.MessageDialog(parent=parent,
                            type=gtk.MESSAGE_INFO,
                            buttons=gtk.BUTTONS_OK)
    dlg.set_markup(msg)
    if not title:
        title = _("Attention")
    dlg.set_title( title )
    dlg.run()
    dlg.destroy()



class InputDialog:

    parameters = {}
    button_pressed = False
    main_window = None
    parent = None
    def __init__(self, parent, title, input_parameters, cancel = True):

        mywin = gtk.Window()
        mywin.set_transient_for(parent)
        mywin.set_title(_("Please fill the following form"))
        myvbox = gtk.VBox()
        mylabel = gtk.Label()
        mylabel.set_markup(cleanMarkupString(title))
        myhbox = gtk.HBox()
        myvbox.pack_start(mylabel)
        mytable = gtk.Table(rows = len(input_parameters), columns = 2)
        self.identifiers_table = {}
        self.cb_table = {}
        self.entry_text_table = {}
        row_count = 0
        for input_id, input_text, input_cb, passworded in input_parameters:

            if isinstance(input_text,tuple):

                input_type, text = input_text
                combo_options = []
                if isinstance(text,tuple):
                    text, combo_options = text

                input_label = gtk.Label()
                input_label.set_line_wrap(True)
                input_label.set_alignment(0.0,0.5)
                input_label.set_markup(text)

                if input_type == "checkbox":
                    input_widget = gtk.CheckButton(text)
                    input_widget.set_alignment(0.0,0.5)
                    input_widget.set_active(passworded)
                elif input_type == "combo":
                    input_widget = gtk.combo_box_new_text()
                    for opt in combo_options:
                        input_widget.append_text(opt)
                    if combo_options:
                        input_widget.set_active(0)
                    mytable.attach(input_label, 0, 1, row_count, row_count+1)
                else:
                    continue

                self.entry_text_table[input_id] = text
                self.identifiers_table[input_id] = input_widget
                self.cb_table[input_widget] = input_cb
                mytable.attach(input_widget, 1, 2, row_count, row_count+1)


            else:

                input_label = gtk.Label()
                input_label.set_line_wrap(True)
                input_label.set_alignment(0.0,0.5)
                input_label.set_markup(input_text)
                self.entry_text_table[input_id] = input_text
                mytable.attach(input_label, 0, 1, row_count, row_count+1)
                input_entry = gtk.Entry()
                if passworded: input_entry.set_visibility(False)

                self.identifiers_table[input_id] = input_entry
                self.cb_table[input_entry] = input_cb
                mytable.attach(input_entry, 1, 2, row_count, row_count+1)

            row_count += 1
        myvbox.pack_start(mytable)
        bbox = gtk.HButtonBox()
        bbox.set_layout(gtk.BUTTONBOX_END)
        bbox.set_spacing(10)
        myok = gtk.Button(stock = "gtk-ok")
        myok.connect('clicked', self.do_ok )
        bbox.pack_start(myok, padding = 10)
        if cancel:
            mycancel = gtk.Button(stock = "gtk-cancel")
            mycancel.connect('clicked', self.do_cancel )
            bbox.pack_start(mycancel)
        myvbox.pack_start(bbox)
        myvbox.set_spacing(10)
        myvbox.show()
        myhbox.pack_start(myvbox, padding = 10)
        myhbox.show()
        mywin.add(myhbox)
        self.main_window = mywin
        self.parent = parent
        mywin.set_keep_above(True)
        mywin.set_urgency_hint(True)
        mywin.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        mywin.set_default_size(350,-1)
        mywin.show_all()


    def do_ok(self, widget):
        # fill self.parameters
        for input_id in self.identifiers_table:
            mywidget = self.identifiers_table.get(input_id)
            if isinstance(mywidget,gtk.Entry):
                content = mywidget.get_text()
            elif isinstance(mywidget,gtk.CheckButton):
                content = mywidget.get_active()
            elif isinstance(mywidget,gtk.ComboBox):
                content = mywidget.get_active(),mywidget.get_active_text()
            else:
                continue
            verify_cb = self.cb_table.get(mywidget)
            valid = verify_cb(content)
            if not valid:
                okDialog(self.parent, "%s: %s" % (_("Invalid entry"),self.entry_text_table[input_id],) , title = _("Invalid entry"))
                self.parameters.clear()
                return
            self.parameters[input_id] = content
        self.button_pressed = True

    def do_cancel(self, widget):
        self.parameters = None
        self.button_pressed = True

    def run(self):
        while not self.button_pressed:
            time.sleep(0.05)
            while gtk.events_pending():
                gtk.main_iteration()
            continue
        self.main_window.destroy()
        return self.parameters

class MessageDialog:
    """
        courtesy of Anaconda :-) Copyright 1999-2005 Red Hat, Inc.
        Matt Wilson <msw@redhat.com>
        Michael Fulbright <msf@redhat.com>
    """

    def getrc(self):
        return self.rc

    def __init__ (self, parent, title, text, type = "ok", default=None, custom_buttons=None, custom_icon=None):
        self.rc = None
        docustom = 0
        if type == 'ok':
            buttons = gtk.BUTTONS_OK
            style = gtk.MESSAGE_INFO
        elif type == 'warning':
            buttons = gtk.BUTTONS_OK
            style = gtk.MESSAGE_WARNING
        elif type == 'okcancel':
            buttons = gtk.BUTTONS_OK_CANCEL
            style = gtk.MESSAGE_WARNING
        elif type == 'yesno':
            buttons = gtk.BUTTONS_YES_NO
            style = gtk.MESSAGE_QUESTION
        elif type == 'custom':
            docustom = 1
            buttons = gtk.BUTTONS_NONE
            style = gtk.MESSAGE_QUESTION

        if custom_icon == "warning":
            style = gtk.MESSAGE_WARNING
        elif custom_icon == "question":
            style = gtk.MESSAGE_QUESTION
        elif custom_icon == "error":
            style = gtk.MESSAGE_ERROR
        elif custom_icon == "info":
            style = gtk.MESSAGE_INFO

        dialog = gtk.MessageDialog(parent, 0, style, buttons, text)

        if docustom:
            rid=0
            for button in custom_buttons:
                if button == _("Cancel"):
                    tbutton = "gtk-cancel"
                else:
                    tbutton = button

                widget = dialog.add_button(tbutton, rid)
                rid = rid + 1

            defaultchoice = rid - 1
        else:
            if default == "no":
                defaultchoice = 0
            elif default == "yes" or default == "ok":
                defaultchoice = 1
            else:
                defaultchoice = 0

        dialog.set_title(title)
        #dialog.format_secondary_markup(cleanMarkupString(text))
        dialog.set_position (gtk.WIN_POS_CENTER)
        dialog.set_default_response(defaultchoice)
        dialog.show_all ()

        rc = dialog.run()

        if rc == gtk.RESPONSE_OK or rc == gtk.RESPONSE_YES:
            self.rc = 1
        elif (rc == gtk.RESPONSE_CANCEL or rc == gtk.RESPONSE_NO
            or rc == gtk.RESPONSE_CLOSE):
            self.rc = 0
        elif rc == gtk.RESPONSE_DELETE_EVENT:
            self.rc = 0
        else:
            self.rc = rc
        dialog.destroy()



class LicenseDialog:
    def __init__( self, parent, licenses, entropy ):

        self.Entropy = entropy
        self.xml = gtk.glade.XML( const.GLADE_FILE, 'licenseWindow',domain="entropy" )
        self.xml_licread = gtk.glade.XML( const.GLADE_FILE, 'licenseReadWindow',domain="entropy" )
        self.dialog = self.xml.get_widget( "licenseWindow" )
        self.dialog.set_transient_for( parent )
        self.read_dialog = self.xml_licread.get_widget( "licenseReadWindow" )
        self.read_dialog.connect( 'delete-event', self.close_read_text_window )
        #self.read_dialog.set_transient_for( self.dialog )
        self.licenseView = self.xml_licread.get_widget( "licenseTextView" )
        self.okReadButton = self.xml_licread.get_widget( "okReadButton" )
        self.okReadButton.connect( "clicked", self.close_read_text )


        self.okButton = self.xml.get_widget( "confirmLicense" )
        self.stopButton = self.xml.get_widget( "discardLicense" )
        self.acceptLicense = self.xml.get_widget( "acceptLicense" )
        self.acceptLicense.connect( "clicked", self.accept_selected_license )
        self.readLicense = self.xml.get_widget( "readLicense" )
        self.readLicense.connect( "clicked", self.read_selected_license )

        self.view = self.xml.get_widget( "licenseView1" )
        self.model = self.setup_view()
        self.show_data( licenses )
        self.view.expand_all()
        self.licenses = licenses
        self.accepted = set()


    def close_read_text_window(self, widget, path):
        self.read_dialog.hide()
        return True

    def close_read_text(self, widget ):
        self.read_dialog.hide()

    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()

    def destroy( self ):
        return self.dialog.destroy()

    def setup_view(self):
        model = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_PYOBJECT )
        self.view.set_model( model )
        self.create_text_column( _( "License" ), 0, size = 200 )

        cell2 = gtk.CellRendererPixbuf()    # new
        column2 = gtk.TreeViewColumn( _("Accepted"), cell2 )
        column2.set_cell_data_func( cell2, self.new_pixbuf )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 20 )
        column2.set_sort_column_id( -1 )
        self.view.append_column( column2 )
        column2.set_clickable( False )

        return model

    def set_pixbuf_to_cell(self, cell, do):
        if do:
            cell.set_property( 'stock-id', 'gtk-apply' )
        elif do == False:
            cell.set_property( 'stock-id', 'gtk-cancel' )
        else:
            cell.set_property( 'stock-id', None )

    def new_pixbuf( self, column, cell, model, iterator ):
        license_identifier = model.get_value( iterator, 0 )
        chief = model.get_value( iterator, 1 )
        if (license_identifier in self.accepted) and chief:
            self.set_pixbuf_to_cell(cell, True)
        elif chief:
            self.set_pixbuf_to_cell(cell, False)
        elif chief == None:
            self.set_pixbuf_to_cell(cell, None)

    def create_text_column( self, hdr, colno, size = None ):
        cell = gtk.CellRendererText()    # Size Column
        column = gtk.TreeViewColumn( hdr, cell, markup=colno )
        if size != None:
            column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
            column.set_fixed_width( size )
        column.set_resizable( False )
        self.view.append_column( column )

    def read_selected_license(self, widget):
        model, iterator = self.view.get_selection().get_selected()
        if model != None and iterator != None:
            license_identifier = model.get_value( iterator, 0 )
            if not self.licenses.has_key(license_identifier): # for security reasons
                return
            packages = self.licenses[license_identifier]
            license_text = ''
            for package in packages:
                repoid = package[1]
                dbconn = self.Entropy.openRepositoryDatabase(repoid)
                if dbconn.isLicensedataKeyAvailable(license_identifier):
                    license_text = dbconn.retrieveLicenseText(license_identifier)
                    break
            # prepare textview
            mybuffer = gtk.TextBuffer()
            mybuffer.set_text(unicode(license_text,'raw_unicode_escape'))
            self.licenseView.set_buffer(mybuffer)
            self.read_dialog.set_title(license_identifier+" license text")
            self.read_dialog.show_all()

    def accept_selected_license(self, widget):
        model, iterator = self.view.get_selection().get_selected()
        if model != None and iterator != None:
            license_identifier = model.get_value( iterator, 0 )
            chief = model.get_value( iterator, 1 )
            if chief:
                self.accepted.add(license_identifier)
                self.view.queue_draw()
                if len(self.accepted) == len(self.licenses):
                    self.okButton.set_sensitive(True)

    def show_data( self, licenses ):
        self.model.clear()
        for lic in licenses:
            parent = self.model.append( None, [lic,True] )
            packages = licenses[lic]
            for match in packages:
                dbconn = self.Entropy.openRepositoryDatabase(match[1])
                atom = dbconn.retrieveAtom(match[0])
                self.model.append( parent, [atom,None] )
