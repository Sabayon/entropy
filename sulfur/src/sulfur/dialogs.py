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

import threading
import time, gtk, gobject, pango, pty, sys
from entropy.i18n import _, _LOCALE
from entropy.exceptions import *
from entropy.const import *
from entropy.misc import TimeScheduled, ParallelTask
from entropy.output import print_generic
import entropy.tools as entropyTools

from sulfur.event import SulfurSignals
from sulfur.core import UI
from sulfur.misc import busy_cursor, normal_cursor
from sulfur.setup import const, cleanMarkupString, SulfurConf, \
    unicode2htmlentities, fakeoutfile, fakeinfile

class MenuSkel:

    def _getAllMethods(self):
        result = {}
        allAttrNames = list(self.__dict__.keys()) + self._getAllClassAttributes()
        for name in allAttrNames:
            value = getattr(self, name)
            if hasattr(value, '__call__'):
                result[name] = value
        return result

    def _getAllClassAttributes(self):
        nameSet = {}
        for currClass in self._getAllClasses():
            nameSet.update(currClass.__dict__)
        result = list(nameSet.keys())
        return result

    def _getAllClasses(self):
        result = [self.__class__]
        i = 0
        while i < len(result):
            currClass = result[i]
            result.extend(list(currClass.__bases__))
            i = i + 1
        return result

class AddRepositoryWindow(MenuSkel):

    def __init__(self, application, window, entropy):

        from sulfur.views import EntropyRepositoryMirrorsView
        self.addrepo_ui = UI( const.GLADE_FILE, 'addRepoWin', 'entropy' )
        self.addrepo_ui.signal_autoconnect(self._getAllMethods())
        self.repoMirrorsView = EntropyRepositoryMirrorsView(
            self.addrepo_ui.mirrorsView)
        self.addrepo_ui.addRepoWin.set_transient_for(window)
        self.Equo = entropy
        self.Sulfur = application
        self.window = window
        self.addrepo_ui.repoSubmit.show()
        self.addrepo_ui.repoSubmitEdit.hide()
        self.addrepo_ui.repoInsert.show()
        self.addrepo_ui.repoidEntry.set_editable(True)
        self.addrepo_ui.repodbcformatEntry.set_active(0)
        self.addrepo_ui.repoidEntry.set_text("")
        self.addrepo_ui.repoDescEntry.set_text("")
        self.addrepo_ui.repodbEntry.set_text("")
        self.repoMirrorsView.populate()

    def load(self):
        self.addrepo_ui.addRepoWin.show()

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
            dbc_format_entry = self.addrepo_ui.repodbcformatEntry
            if repodata['dbcformat'] == dbc_format_entry.get_active_text():
                break
            idx += 1
        self.addrepo_ui.repodbEntry.set_text(repodata['plain_database'])

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

    def _validate_repo_submit(self, repodata, edit = False):
        errors = []
        if not repodata['repoid']:
            errors.append(_('No Repository Identifier'))

        if repodata['repoid'] and repodata['repoid'] in self.Equo.SystemSettings['repositories']['available']:
            if not edit:
                errors.append(_('Duplicated Repository Identifier'))

        if not repodata['description']:
            repodata['description'] = "No description"

        if not repodata['plain_packages']:
            errors.append(_("No download mirrors"))

        if not repodata['plain_database'] or not \
            (repodata['plain_database'].startswith("http://") or \
            repodata['plain_database'].startswith("ftp://") or \
            repodata['plain_database'].startswith("file://")):

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

    def on_mirrorDown_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        # get text
        if urldata[1] != None:
            next = urldata[0].iter_next(urldata[1])
            if next:
                self.repoMirrorsView.store.swap(urldata[1], next)

    def on_mirrorUp_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        # get text
        if urldata[1] != None:
            path = urldata[0].get_path(urldata[1])[0]
            if path > 0:
                # get next iter
                prev = urldata[0].get_iter(path-1)
                self.repoMirrorsView.store.swap(urldata[1], prev)

    def on_repoMirrorEdit_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        # get text
        if urldata[1] != None:
            text = self.repoMirrorsView.get_text(urldata)
            self.repoMirrorsView.remove(urldata)
            text = inputBox(self.addrepo_ui.addRepoWin, _("Insert URL"),
                _("Enter a download mirror, HTTP or FTP")+"   ",
                input_text = text)
            # call liststore and tell to add
            self.repoMirrorsView.add(text)

    def on_repoMirrorRemove_clicked( self, widget ):
        selection = self.repoMirrorsView.view.get_selection()
        urldata = selection.get_selected()
        if urldata[1] != None:
            self.repoMirrorsView.remove(urldata)

    def on_repoMirrorAdd_clicked( self, widget ):
        text = inputBox(self.addrepo_ui.addRepoWin, _("Insert URL"),
            _("Enter a download mirror, HTTP or FTP")+"   ")
        # call liststore and tell to add
        if text:
            # validate url
            if not (text.startswith("http://") or text.startswith("ftp://") or \
                text.startswith("file://")):
                okDialog( self.addrepo_ui.addRepoWin,
                    _("You must enter either a HTTP or a FTP url.") )
            else:
                self.repoMirrorsView.add(text)

    def on_repoInsert_clicked( self, widget ):
        text = inputBox(self.addrepo_ui.addRepoWin, _("Insert Repository"),
            _("Insert Repository identification string")+"   ")
        if text:
            if (text.startswith("repository|")) and (len(text.split("|")) == 5):
                current_branch = self.Equo.SystemSettings['repositories']['branch']
                current_product = self.Equo.SystemSettings['repositories']['product']
                repoid, repodata = \
                    self.Equo.SystemSettings._analyze_client_repo_string(text,
                        current_branch, current_product)
                self._load_repo_data(repodata)
            else:
                okDialog( self.addrepo_ui.addRepoWin,
                    _("This Repository identification string is malformed") )

    def on_repoCancel_clicked( self, widget ):
        self.addrepo_ui.addRepoWin.hide()
        self.addrepo_ui.addRepoWin.destroy()

    def on_repoSubmit_clicked( self, widget ):
        repodata = self._get_repo_data()
        # validate
        errors = self._validate_repo_submit(repodata)
        if not errors:
            self.Equo.add_repository(repodata)
            self.Sulfur.reset_cache_status()
            self.Sulfur.setup_repoView()
            self.addrepo_ui.addRepoWin.hide()
        else:
            msg = "%s: %s" % (_("Wrong entries, errors"), ', '.join(errors),)
            okDialog( self.addrepo_ui.addRepoWin, msg )

    def on_repoSubmitEdit_clicked( self, widget ):
        repodata = self._get_repo_data()
        errors = self._validate_repo_submit(repodata, edit = True)
        if errors:
            msg = "%s: %s" % (_("Wrong entries, errors"), ', '.join(errors),)
            okDialog( self.addrepo_ui.addRepoWin, msg )
            return True
        else:
            disable = False
            repo_excluded = self.Equo.SystemSettings['repositories']['excluded']
            if repodata['repoid'] in repo_excluded:
                disable = True
            self.Equo.remove_repository(repodata['repoid'], disable = disable)
            if not disable:
                self.Equo.add_repository(repodata)
            self.Sulfur.reset_cache_status()

            self.Sulfur.setup_repoView()
            self.addrepo_ui.addRepoWin.hide()


class NoticeBoardWindow(MenuSkel):

    def __init__( self, window, entropy ):

        self.Entropy = entropy
        self.window = window

        self.nb_ui = UI( const.GLADE_FILE, 'noticeBoardWindow', 'entropy' )
        self.nb_ui.signal_autoconnect(self._getAllMethods())
        self.nb_ui.noticeBoardWindow.set_transient_for(self.window)

        mytxt = "<big><b>%s</b></big>\n<small>%s</small>" % (
            _("Repositories Notice Board"),
            _("Here below you will find a list of important news directly issued by your applications maintainers.\n" \
                "Double click on each item to retrieve detailed info."),
        )
        self.nb_ui.noticeBoardLabel.set_markup(mytxt)
        self.view = self.nb_ui.noticeView
        self.model = self.setup_view()

    def load(self, repoids):
        self.repoids = repoids
        self.show_data()
        self.view.expand_all()
        self.nb_ui.noticeBoardStfu.set_active(
            self.Entropy.are_noticeboards_marked_as_read())
        self.nb_ui.noticeBoardWindow.show()

    def setup_view(self):
        model = gtk.TreeStore( gobject.TYPE_PYOBJECT )
        self.view.set_model( model )

        self.create_text_column( _( "Notice" ), size = 200, expand = True,
            set_height = 40 )

        # Create read status pixmap
        cell = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn( _("Status"), cell )
        column.set_cell_data_func( cell, self.status_pixbuf )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( 40 )
        self.view.append_column( column )

        return model

    def text_data_func( self, column, cell, model, iterator ):
        obj = model.get_value(iterator, 0)
        if obj:
            if 'is_repo' in obj:
                cell.set_property('markup', "<big><b>%s</b></big>\n<small>%s</small>" % (cleanMarkupString(obj['name']), cleanMarkupString(obj['desc']),))
            else:
                mytxt = '<b><u>%s</u></b>\n<small><b>%s</b>: %s</small>' % (
                    cleanMarkupString(obj['pubDate']),
                    _("Title"),
                    cleanMarkupString(obj['title']),
                )
                cell.set_property('markup', mytxt)
            cell.set_property('cell-background', obj['color'])

    def status_pixbuf( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 ) or {}
        if obj.get('is_repo'):
            cell.set_property('stock-id', None)
        elif obj['read']:
            cell.set_property('stock-id', 'gtk-apply')
        else:
            cell.set_property('stock-id', 'gtk-cancel')
        cell.set_property('cell-background', obj['color'])

    def create_text_column( self, hdr, size = None, expand = False, set_height = 0 ):
        cell = gtk.CellRendererText()
        if set_height: cell.set_property('height', set_height)
        column = gtk.TreeViewColumn( hdr, cell )
        column.set_cell_data_func( cell, self.text_data_func )
        if size != None:
            column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
            column.set_fixed_width( size )
        column.set_resizable( False )
        column.set_expand( expand )
        self.view.append_column( column )

    def on_noticeBoardStfu_toggled(self, widget):
        for repoid in self.repoids:
            if widget.get_active():
                self.Entropy.mark_noticeboard_items_as_read(repoid)
            else:
                self.Entropy.unmark_noticeboard_items_as_read(repoid)

    def on_noticeBoardWindow_delete_event(self, *myargs):

        # store noticeboard items read status back to hd
        for mod_obj in self.model:
            for children in mod_obj.iterchildren():
                for obj in children:
                    if not obj:
                        continue
                    self.Entropy.set_noticeboard_item_read_status(
                        obj['repoid'], obj['id'], obj['read'])

        self.model.clear()
        self.nb_ui.noticeBoardWindow.destroy()
        del self.nb_ui

    def on_closeNoticeBoardButton_clicked(self, widget):
        self.on_noticeBoardWindow_delete_event(widget)

    def on_noticeView_row_activated(self, widget, iterator, path):
        ( model, iterator ) = widget.get_selection().get_selected()
        if model != None and iterator != None:
            obj = model.get_value(iterator, 0)
            if 'is_repo' not in obj:
                my = RmNoticeBoardMenu(self.nb_ui.noticeBoardWindow)
                my.load(obj)

    def show_data(self):
        self.model.clear()
        colors = ["#CDEEFF", "#AFCBDA"]
        avail_repos = self.Entropy.SystemSettings['repositories']['available']
        for repoid in self.repoids:
            counter = 0
            master_dict = {
                'is_repo': True,
                'name': repoid,
                'desc': avail_repos[repoid].get('description'),
                'path': self.repoids[repoid],
                'color': colors[0],
                'read': False,
                'repoid': repoid,
            }
            parent = self.model.append( None, (master_dict,) )
            items = self.Entropy.get_noticeboard(repoid).copy()
            read_items = self.Entropy.get_noticeboard_item_read_status(repoid)
            for key in sorted(items):
                counter += 1
                mydict = items[key].copy()
                mydict['color'] = colors[counter%len(colors)]
                mydict['id'] = key
                mydict['read'] = key in read_items
                mydict['repoid'] = repoid
                self.model.append( parent, (mydict,) )

class RemoteConnectionMenu(MenuSkel):

    import entropy.dump as dumpTools
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
        data = self.Entropy.inputBox(
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
        obj = self.dumpTools.loadobj(self.store_path)
        if not obj: return []
        return obj

    def remove_connection_data_item(self, item):
        if item in self.connection_data:
            self.connection_data.remove(item)

    def store_connection_data_item(self, item):
        self.connection_data.append(item)

    def store_connection_data(self):
        self.dumpTools.dumpobj(self.store_path, self.connection_data)

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
            entropyTools.bytes_into_human(obj['size']),
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
                entropyTools.print_traceback()
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
        entropyTools.print_traceback()
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

        rc = self.Entropy.askQuestion(_("Are you sure you want to remove the selected packages ? (For EVA!)"))
        if rc != _("Yes"):
            return

        rc = self.Entropy.askQuestion(_("This is your last chance, are you really really really sure?"))
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
            mydata = self.Entropy.inputBox(
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
        data = self.Entropy.inputBox(
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
            data = self.Entropy.inputBox(
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
            mydata = self.Entropy.inputBox(
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

                data = self.Entropy.inputBox(
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
                mydata = self.Entropy.inputBox(
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
            mydata = self.Entropy.inputBox(
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
            cat = entropyTools.dep_getkey(spm_atom).split("/")[0]
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
                                'size': entropyTools.bytes_into_human(mysize),
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
            mydata = self.Entropy.inputBox(
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
            mydata = self.Entropy.inputBox(
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
        mydata = self.Entropy.inputBox(
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
        mydata = self.Entropy.inputBox(
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
            mydata = self.Entropy.inputBox(
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
                categories.append(entropyTools.dep_getkey(atom).split("/")[0])
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
        data = self.Entropy.inputBox(
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
        data = self.Entropy.inputBox(
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
        data = self.Entropy.inputBox(
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
            mydata = self.Entropy.inputBox(
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
        data = self.Entropy.inputBox(
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

        data = self.Entropy.inputBox(
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

        data = self.Entropy.inputBox(
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
        data = self.Entropy.inputBox(
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
            data = self.Entropy.inputBox(
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


class RmNoticeBoardMenu(MenuSkel):

    def __init__(self, window):

        self.window = window
        self.rm_ui = UI( const.GLADE_FILE, 'rmNoticeBoardInfo', 'entropy' )
        self.rm_ui.signal_autoconnect(self._getAllMethods())
        self.rm_ui.rmNoticeBoardInfo.set_transient_for(self.window)
        self.rm_ui.rmNoticeBoardInfo.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.url = None
        self.item = None
        gtk.link_button_set_uri_hook(self.load_url, data=self.url)

    def load_url(self, widget, url, extra):
        import subprocess
        f = open("/dev/null", "w")
        subprocess.call(['xdg-open', url], stdout = f, stderr = f)
        f.close()

    def on_rmNoticeBoardCloseButton_clicked(self, widget):
        self.rm_ui.rmNoticeBoardInfo.hide()
        self.rm_ui.rmNoticeBoardInfo.destroy()

    def on_rmNoticeBoardMarkRead_clicked(self, widget):
        if self.item:
            self.item['read'] = True

    def destroy(self):
        self.rm_ui.rmNoticeBoardInfo.destroy()

    def load(self, item):

        na = _("N/A")
        self.rm_ui.rmNoticeBoardIdLabel.set_text(item['id'])
        self.rm_ui.rmNoticeBoardDateLabel.set_text(cleanMarkupString(item['pubDate']))
        self.rm_ui.rmNoticeBoardTitleLabel.set_text(cleanMarkupString(item['title']))
        self.rm_ui.rmNoticeBoardLinkLabel.set_label(item['link'])
        self.rm_ui.rmNoticeBoardLinkLabel.set_uri(item['link'])
        self.url = item['link']
        self.rm_ui.rmNoticeBoardTextLabel.set_text(cleanMarkupString(item['description']))

        bold_items = [
            self.rm_ui.rmNoticeBoardId,
            self.rm_ui.rmNoticeBoardDate,
            self.rm_ui.rmNoticeBoardTitle,
            self.rm_ui.rmNoticeBoardLink
        ]
        small_items = [
            self.rm_ui.rmNoticeBoardIdLabel,
            self.rm_ui.rmNoticeBoardDateLabel,
            self.rm_ui.rmNoticeBoardTitleLabel,
        ]
        for xitem in bold_items:
            t = xitem.get_text()
            xitem.set_markup("<span foreground='%s'><small><b>%s</b></small></span>" % (SulfurConf.color_title, t,))
        for xitem in small_items:
            t = xitem.get_text()
            xitem.set_markup("<span foreground='%s'><small>%s</small></span>" % (SulfurConf.color_pkgsubtitle, t,))
        t = self.rm_ui.rmNoticeBoardTextLabel.get_text()
        self.rm_ui.rmNoticeBoardTextLabel.set_markup("<span foreground='%s'><small>%s</small></span>" % (SulfurConf.color_subdesc, t,))
        self.rm_ui.rmNoticeBoardInfo.show_all()
        self.item = item

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

class PkgInfoMenu(MenuSkel):

    def __init__(self, Entropy, pkg, window):

        self.pkg_pixmap = const.pkg_pixmap
        self.ugc_small_pixmap = const.ugc_small_pixmap
        self.ugc_pixmap = const.ugc_pixmap
        self.refresh_pixmap = const.refresh_pixmap
        self.star_normal_pixmap = const.star_normal_pixmap
        self.star_selected_pixmap = const.star_selected_pixmap
        self.star_empty_pixmap = const.star_empty_pixmap

        self.ugc_update_event_handler_id = None
        self.loading_pix = gtk.image_new_from_file(const.loading_pix)
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
        if self.window:
            self.pkginfo_ui.pkgInfo.set_transient_for(self.window)
        self.pkginfo_ui.pkgInfo.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        # noeeees! otherwise voting won't work
        #self.pkginfo_ui.pkgInfo.connect('button-press-event', self.on_button_press)
        self.setupPkgPropertiesView()

        self.ugc_tab_clicked_signal_handler_id = \
            SulfurSignals.connect('pkg_properties__ugc_tab_clicked',
                self._ugc_tab_clicked)

    def set_pixbuf_to_cell(self, cell, path):
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(path)
            cell.set_property( 'pixbuf', pixbuf )
        except gobject.GError:
            pass

    def ugc_pixbuf( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 )
        if isinstance(obj, dict):
            if 'preview_path' in obj:
                self.set_pixbuf_to_cell(cell, obj['preview_path'])
            else:
                self.set_pixbuf_to_cell(cell, obj['image_path'])
            self.set_colors_to_cell(cell, obj)

    def ugc_content( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 )
        if isinstance(obj, dict):
            self.set_colors_to_cell(cell, obj)

            if 'is_cat' in obj:
                cell.set_property('markup', "<b>%s</b>\n<small>%s</small>" % (obj['parent_desc'], _("Expand to browse"),))
            else:
                title = _("N/A")
                if obj['title']:
                    title = const_convert_to_unicode(obj['title'])
                description = _("N/A")
                if obj['description']:
                    description = obj['description']
                if obj['iddoctype'] in (etpConst['ugc_doctypes']['comments'], etpConst['ugc_doctypes']['bbcode_doc'],):
                    myddata = obj['ddata']
                    if not isinstance(obj['ddata'], const_get_stringtype()):
                        myddata = myddata.tostring()
                    description = const_convert_to_unicode(myddata)
                    if len(description) > 100:
                        description = description[:100].strip()+"..."
                mytxt = "<small><b>%s</b>: %s, %s: %s\n<b>%s</b>: %s, <i>%s</i>\n<b>%s</b>: %s\n<b>%s</b>: <i>%s</i>\n<b>%s</b>: %s</small>" % (
                    _("Identifier"),
                    obj['iddoc'],
                    _("Size"),
                    entropyTools.bytes_into_human(obj['size']),
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
                cell.set_property('markup', mytxt)

    def set_colors_to_cell(self, cell, obj):
        odd = 0
        if 'counter' in obj:
            odd = obj['counter']%2
        if 'background' in obj:
            cell.set_property('cell-background', obj['background'][odd])
        else:
            cell.set_property('cell-background', None)
        try:
            if 'foreground' in obj:
                cell.set_property('foreground', obj['foreground'])
            else:
                cell.set_property('foreground', None)
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
            self.contentModel.append(None, [x[0], x[1]])

    def disconnect_event_signals(self):
        # disconnect signals
        if self.ugc_update_event_handler_id is not None:
            SulfurSignals.disconnect(self.ugc_update_event_handler_id)
        if self.ugc_tab_clicked_signal_handler_id is not None:
            SulfurSignals.disconnect(self.ugc_tab_clicked_signal_handler_id)

    def on_closeInfo_clicked(self, widget):
        self.disconnect_event_signals()
        self.reset_ugc_data()
        self.pkginfo_ui.pkgInfo.hide()

    def on_pkgInfo_delete_event(self, widget, path):
        self.disconnect_event_signals()
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
        if not isinstance(obj, dict): return
        if 'is_cat' in obj: return
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
        if not isinstance(obj, dict): return
        if 'is_cat' in obj: return
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

            try:
                docs_data, err_msg = self.Entropy.UGC.get_docs(self.repository,
                    self.pkgkey)
            except TimeoutError:
                dialog_title = _("Timeout Error")
                err_msg = _("Connection timed out, sorry!")
                docs_data = None
                okDialog(self.window, err_msg, title = dialog_title)

            if not isinstance(docs_data, (list, tuple)):
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
            if mydict['iddoctype'] not in newdata:
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
                if 'store_url' not in mydoc:
                    continue
                if not mydoc['store_url']:
                    continue
                store_path = self.Entropy.UGC.UGCCache.get_stored_document(mydoc['iddoc'], self.repository, mydoc['store_url'])
                if store_path == None:
                    self.Entropy.UGC.UGCCache.store_document(mydoc['iddoc'], self.repository, mydoc['store_url'])
                    store_path = self.Entropy.UGC.UGCCache.get_stored_document(mydoc['iddoc'], self.repository, mydoc['store_url'])
                if (store_path != None) and os.access(store_path, os.R_OK):
                    try:
                        preview_path = store_path+".preview"
                        if not os.path.isfile(preview_path) and (os.stat(store_path)[6] < 1024000):
                            # resize pix
                            img = gtk.Image()
                            img.set_from_file(store_path)
                            img_buf = img.get_pixbuf()
                            w, h = img_buf.get_width(), img_buf.get_height()
                            new_w = 64.0
                            new_h = new_w*h/w
                            img_buf = img_buf.scale_simple(int(new_w), int(new_h), gtk.gdk.INTERP_BILINEAR)
                            img_buf.save(preview_path, "png")
                            del img, img_buf
                        if os.path.isfile(preview_path):
                            mydoc['preview_path'] = preview_path
                    except:
                        continue

    def populate_ugc_view(self):

        if self.ugc_data == None: return

        spawn_fetch = False
        doc_types = list(self.ugc_data.keys())
        doc_type_image_map = {
            1: const.ugc_text_pix,
            2: const.ugc_text_pix,
            3: const.ugc_image_pix,
            4: const.ugc_generic_pix,
            5: const.ugc_video_pix,
        }
        doc_type_background_map = {
            1: ('#67AB6F', '#599360'),
            2: ('#67AB6F', '#599360'),
            3: ('#AB8158', '#CA9968'),
            4: ('#BBD5B0', '#99AE90'),
            5: ('#A5C0D5', '#8EA5B7'),
        }
        doc_type_foreground_map = {
            1: '#FFFFFF',
            2: '#FFFFFF',
            3: '#FFFFFF',
            4: '#FFFFFF',
            5: '#FFFFFF',
        }
        counter = 1
        for doc_type in doc_types:
            spawn_fetch = True
            image_path = doc_type_image_map.get(int(doc_type))
            cat_dict = {
                'is_cat': True,
                'image_path': image_path,
                'parent_desc': "%s (%s)" % (etpConst['ugc_doctypes_description'].get(int(doc_type)), len(self.ugc_data[doc_type]),),
                'foreground': doc_type_foreground_map.get(int(doc_type)),
                'background': doc_type_background_map.get(int(doc_type)),
            }
            parent = self.ugcModel.append( None, (cat_dict,) )
            docs_dates = {}
            for mydoc in self.ugc_data[doc_type]:
                ts = mydoc['ts']
                if ts not in docs_dates:
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
            gobject.idle_add(self.spawn_docs_fetch)

        #search_col = 0
        #self.view.set_search_column( search_col )
        #self.view.set_search_equal_func(self.atom_search)
        self.ugcView.set_property('headers-visible', True)
        self.ugcView.set_property('enable-search', True)
        self.ugcView.show_all()

    def on_infoBook_switch_page(self, widget, page, page_num):
        if (page_num == self.ugc_page_idx) and (not self.switched_to_ugc_page):
            SulfurSignals.emit('pkg_properties__ugc_tab_clicked')

    def _ugc_tab_clicked(self, event):
        self.switched_to_ugc_page = True
        self.on_loadUgcButton_clicked(None, force = False)

    def on_showChangeLogButton_clicked(self, widget):
        if not self.changelog:
            return
        mybuffer = gtk.TextBuffer()
        mybuffer.set_text(self.changelog)
        xml_clread = gtk.glade.XML( const.GLADE_FILE, 'textReadWindow', domain="entropy" )
        read_dialog = xml_clread.get_widget( "textReadWindow" )
        okReadButton = xml_clread.get_widget( "okReadButton" )
        self.changelog_read_dialog = read_dialog
        okReadButton.connect( 'clicked', self.destroy_changelog_read_dialog )
        clView = xml_clread.get_widget( "readTextView" )
        clView.set_buffer(mybuffer)
        read_dialog.set_title(_("Package ChangeLog"))
        read_dialog.set_transient_for(self.pkginfo_ui.pkgInfo)
        read_dialog.show()

    def destroy_changelog_read_dialog(self, widget):
        self.changelog_read_dialog.destroy()

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
        normal_cursor(self.pkginfo_ui.pkgInfo)
        self.set_stars(self.vote)

    def on_starsEvent_enter_notify_event(self, widget, event):
        busy_cursor(self.pkginfo_ui.pkgInfo, cur = gtk.gdk.Cursor(gtk.gdk.CROSSHAIR))

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
            msg = "<small><span foreground='%s'>%s</span>: %s</small>" % (SulfurConf.color_good, _("Vote registered successfully"), vote,)
        else:
            msg = "<small><span foreground='%s'>%s</span>: %s</small>" % (SulfurConf.color_error, _("Error registering vote"), err_msg,)

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

        self.ugcView.set_property('headers-visible', True)
        self.ugcView.set_property('enable-search', True)

    def __update_ugc_event(self, event):
        self.set_stars_from_repository()
        self.set_download_numbers_from_repository()

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
        vote = self.pkg.voteint
        self.set_stars(vote)
        self.vote = vote

    def set_download_numbers_from_repository(self):
        self.pkginfo_ui.ugcDownloaded.set_markup(
            "<small>%s: <b>%s</b></small>" % (_("Number of downloads"),
                self.pkg.downloads,)
        )

    def load(self, remote = False):

        pkg = self.pkg
        dbconn = self.pkg.dbconn
        avail = False
        if dbconn:
            avail = dbconn.isIdpackageAvailable(pkg.matched_atom[0])
        if not avail:
            return
        from_repo = True
        if isinstance(pkg.matched_atom[1], int): from_repo = False
        if from_repo and (pkg.matched_atom[1] not in self.Entropy.validRepositories) and (not remote):
            return

        # set package image
        pkgatom = pkg.name
        self.vote = int(pkg.vote)
        self.repository = pkg.repoid
        self.pkgkey = entropyTools.dep_getkey(pkgatom)
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
        self.set_download_numbers_from_repository()

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
                        self.pkginfo_ui.ugcTitleLabel,
                        self.pkginfo_ui.changeLogLabel
        ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<b>%s</b>" % (t,))

        repo = pkg.matched_atom[1]
        avail_repos = self.Entropy.SystemSettings['repositories']['available']
        if repo == 0:
            repo = pkg.repoid

        if remote:
            self.pkginfo_ui.location.set_markup("%s: %s" % (_("Remotely"), pkg.repoid,))
        else:
            self.pkginfo_ui.location.set_markup("%s" % (cleanMarkupString(avail_repos[repo]['description']),))

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
            self.licenseModel.append(None, [x])

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
        masked = _("No")
        idpackage_masked, idmasking_reason = dbconn.idpackageValidator(pkg.matched_atom[0])
        if idpackage_masked == -1:
            masked = '%s, %s' % (_("Yes"), self.Entropy.SystemSettings['pkg_masking_reasons'][idmasking_reason],)
        self.pkginfo_ui.masked.set_markup( "%s" % (masked,) )

        # package changelog
        self.changelog = pkg.changelog
        if not self.changelog:
            self.pkginfo_ui.showChangeLogButtonAlign.hide()
            self.pkginfo_ui.changeLogLabel.hide()
            self.changelog = None

        # sources view
        self.sourcesModel.clear()
        self.sourcesView.set_model( self.sourcesModel )
        mirrors = set()
        sources = pkg.sources
        for x in sources:
            if x.startswith("mirror://"):
                mirrors.add(x.split("/")[2])
            self.sourcesModel.append(None, [x])

        # mirrors view
        self.mirrorsReferenceModel.clear()
        self.mirrorsReferenceView.set_model(self.mirrorsReferenceModel)
        for mirror in mirrors:
            mirrorinfo = dbconn.retrieveMirrorInfo(mirror)
            if mirrorinfo:
                # add parent
                parent = self.mirrorsReferenceModel.append(None, [mirror])
                for info in mirrorinfo:
                    self.mirrorsReferenceModel.append(parent, [info])

        # keywords view
        self.keywordsModel.clear()
        self.keywordsView.set_model( self.keywordsModel )
        for x in pkg.keywords:
            self.keywordsModel.append(None, [x])

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
            self.dependenciesModel.append(None, [cleanMarkupString(x)])
        for x in conflicts:
            self.dependenciesModel.append(None, [cleanMarkupString("!"+x)])

        # depends view
        self.dependsModel.clear()
        self.dependsView.set_model( self.dependsModel )
        depends = pkg.dependsFmt
        for x in depends:
            self.dependsModel.append(None, [cleanMarkupString(x)])

        # needed view
        self.neededModel.clear()
        self.neededView.set_model( self.neededModel )
        neededs = pkg.needed
        for x in neededs:
            self.neededModel.append(None, [cleanMarkupString(x)])

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
            self.configProtectModel.append(None, [item, 'protect'])
        for item in protect_mask.split():
            self.configProtectModel.append(None, [item, 'mask'])

        # connect events
        self.ugc_update_event_handler_id = \
            SulfurSignals.connect('ugc_data_update', self.__update_ugc_event)

        self.pkginfo_ui.pkgInfo.show()

class SecurityAdvisoryMenu(MenuSkel):

    def __init__(self, window):

        self.window = window
        self.advinfo_ui = UI( const.GLADE_FILE, 'advInfo', 'entropy' )
        self.advinfo_ui.signal_autoconnect(self._getAllMethods())
        self.advinfo_ui.advInfo.set_transient_for(self.window)
        self.advinfo_ui.advInfo.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.setupAdvPropertiesView()

    def setupAdvPropertiesView(self):

        # affected view
        self.affectedView = self.advinfo_ui.affectedView
        self.affectedModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Package" ), cell, markup = 0 )
        self.affectedView.append_column( column )
        self.affectedView.set_model( self.affectedModel )

        # bugs view
        self.bugsView = self.advinfo_ui.bugsView
        self.bugsModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Bug" ), cell, markup = 0 )
        self.bugsView.append_column( column )
        self.bugsView.set_model( self.bugsModel )

        # references view
        self.referencesView = self.advinfo_ui.referencesView
        self.referencesModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Reference" ), cell, markup = 0 )
        self.referencesView.append_column( column )
        self.referencesView.set_model( self.referencesModel )

    def load(self, item):

        key, affected, data = item

        adv_pixmap = const.PIXMAPS_PATH+'/button-glsa.png'
        self.advinfo_ui.advImage.set_from_file(adv_pixmap)

        glsa_idtext = "<b>GLSA</b>#<span foreground='%s' weight='bold'>%s</span>" % (SulfurConf.color_title, key,)
        self.advinfo_ui.labelIdentifier.set_markup(glsa_idtext)

        bold_items = [
                        self.advinfo_ui.descriptionLabel,
                        self.advinfo_ui.backgroundLabel,
                        self.advinfo_ui.impactLabel,
                        self.advinfo_ui.affectedLabel,
                        self.advinfo_ui.bugsLabel,
                        self.advinfo_ui.referencesLabel,
                        self.advinfo_ui.revisedLabel,
                        self.advinfo_ui.announcedLabel,
                        self.advinfo_ui.synopsisLabel,
                        self.advinfo_ui.workaroundLabel,
                        self.advinfo_ui.resolutionLabel
                     ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<b>%s</b>" % (t,))

        # packages
        if 'packages' in data:
            packages_data = data['packages']
        else:
            packages_data = data['affected']
        glsa_packages = '\n'.join([x for x in packages_data])
        glsa_packages = "<span weight='bold' size='large'>%s</span>" % (glsa_packages,)
        self.advinfo_ui.labelPackages.set_markup(glsa_packages)

        # title
        myurl = ''
        if 'url' in data:
            myurl = data['url']

        self.advinfo_ui.labelTitle.set_markup( "<small>%s</small>" % (data['title'],))
        self.advinfo_ui.advLink.set_uri(myurl)
        self.advinfo_ui.advLink.set_label(myurl)

        # description
        desc_text = ' '.join([x.strip() for x in data['description'].split("\n")]).strip()
        if 'description_items' in data:
            if data['description_items']:
                for item in data['description_items']:
                    desc_text += '\n\t%s %s' % ("<span foreground='%s'>(*)</span>" % (SulfurConf.color_title,), item,)
        desc_text = desc_text.replace('!;\\n', '')
        b = gtk.TextBuffer()
        b.set_text(desc_text)
        self.advinfo_ui.descriptionTextLabel.set_buffer(b)

        # background
        back_text = ' '.join([x.strip() for x in data['background'].split("\n")]).strip()
        back_text = back_text.replace('!;\\n', '')
        b = gtk.TextBuffer()
        b.set_text(back_text)
        self.advinfo_ui.backgroundTextLabel.set_buffer(b)

        # impact
        impact_text = ' '.join([x.strip() for x in data['impact'].split("\n")]).strip()
        impact_text = impact_text.replace('!;\\n', '')
        b = gtk.TextBuffer()
        b.set_text(back_text)
        self.advinfo_ui.impactTextLabel.set_buffer(b)

        t = self.advinfo_ui.impactLabel.get_text()
        t = "<b>%s</b>" % (t,)
        t += " [<span foreground='darkgreen'>%s</span>:<span foreground='%s'>%s</span>|<span foreground='%s'>%s</span>:<span foreground='%s'>%s</span>]" % (
                    _("impact"),
                    SulfurConf.color_title2,
                    data['impacttype'],
                    SulfurConf.color_subdesc,
                    _("access"),
                    SulfurConf.color_pkgsubtitle,
                    data['access'],
        )
        self.advinfo_ui.impactLabel.set_markup(t)

        # affected packages
        self.affectedModel.clear()
        self.affectedView.set_model( self.affectedModel )
        for key in packages_data:
            affected_data = packages_data[key][0]
            vul_atoms = affected_data['vul_atoms']
            unaff_atoms = affected_data['unaff_atoms']
            parent = self.affectedModel.append(None, [key])
            if vul_atoms:
                myparent = self.affectedModel.append(parent, [_('Vulnerables')])
                for atom in vul_atoms:
                    self.affectedModel.append(myparent, [cleanMarkupString(atom)])
            if unaff_atoms:
                myparent = self.affectedModel.append(parent, [_('Unaffected')])
                for atom in unaff_atoms:
                    self.affectedModel.append(myparent, [cleanMarkupString(atom)])

        # bugs
        self.bugsModel.clear()
        self.bugsView.set_model( self.bugsModel )
        for bug in data['bugs']:
            self.bugsModel.append([cleanMarkupString(bug)])

        self.referencesModel.clear()
        self.referencesView.set_model( self.referencesModel )
        for reference in data['references']:
            self.referencesModel.append([cleanMarkupString(reference)])

        # announcedTextLabel
        self.advinfo_ui.announcedTextLabel.set_markup(data['announced'])
        # revisedTextLabel
        self.advinfo_ui.revisedTextLabel.set_markup(data['revised'])

        # synopsis
        synopsis_text = ' '.join([x.strip() for x in data['synopsis'].split("\n")]).strip()
        b = gtk.TextBuffer()
        b.set_text(synopsis_text)
        self.advinfo_ui.synopsisTextLabel.set_buffer(b)

        # workaround
        workaround_text = ' '.join([x.strip() for x in data['workaround'].split("\n")]).strip()
        workaround_text = workaround_text.replace('!;\\n', '')
        b = gtk.TextBuffer()
        b.set_text(workaround_text)
        self.advinfo_ui.workaroundTextLabel.set_buffer(b)

        # resolution

        if isinstance(data['resolution'], list):
            resolution_text = []
            for resolution in data['resolution']:
                resolution_text.append(' '.join([x.strip() for x in resolution.split("\n")]).strip())
            resolution_text = '\n'.join(resolution_text)
        else:
            resolution_text = data['resolution'].replace('!;\\n', '')
            resolution_text = '\n'.join([x for x in resolution_text.strip().split("\n")])

        b = gtk.TextBuffer()
        b.set_text(resolution_text)
        self.advinfo_ui.resolutionTextLabel.set_buffer(b)

        self.advinfo_ui.advInfo.show()

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
            self.subprocess.call(['xdg-open', self.ugc_data['store_url']])

    def load(self):

        pix_path = self.ugc_data['image_path']
        if 'preview_path' in self.ugc_data:
            if os.path.isfile(self.ugc_data['preview_path']) and os.access(self.ugc_data['preview_path'], os.R_OK):
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
        self.ugcinfo_ui.titleContent.set_markup("%s" % (const_convert_to_unicode(self.ugc_data['title']),))
        self.ugcinfo_ui.descriptionContent.set_markup("%s" % (const_convert_to_unicode(self.ugc_data['description']),))
        self.ugcinfo_ui.authorContent.set_markup("<i>%s</i>" % (const_convert_to_unicode(self.ugc_data['username']),))
        self.ugcinfo_ui.dateContent.set_markup("<u>%s</u>" % (self.ugc_data['ts'],))
        self.ugcinfo_ui.keywordsContent.set_markup("%s" % (const_convert_to_unicode(', '.join(self.ugc_data['keywords'])),))
        self.ugcinfo_ui.sizeContent.set_markup("%s" % (entropyTools.bytes_into_human(self.ugc_data['size']),))

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
            ###
            # we need to properly handle raw data coming from ddata dict key
            ###
            if const_isunicode(self.ugc_data['ddata']):
                buf_text = self.ugc_data['ddata']
            elif const_israwstring(self.ugc_data['ddata']):
                buf_text = const_convert_to_unicode(self.ugc_data['ddata'])
            else: # mysql shitty type?
                buf_text = const_convert_to_unicode(self.ugc_data['ddata'].tostring())
            mybuf.set_text(buf_text)
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
        self.text_types = (etpConst['ugc_doctypes']['comments'], etpConst['ugc_doctypes']['bbcode_doc'],)
        self.file_selected = None

    def on_closeAdd_clicked(self, widget, path = None):
        self.ugcadd_ui.ugcAdd.hide()
        return True

    def on_ugcAddTypeCombo_changed(self, widget):
        myiter = widget.get_active_iter()
        idx = self.store.get_value( myiter, 0 )
        if idx in self.text_types:
            txt = "%s %s" % (_("Write your"), etpConst['ugc_doctypes_description_singular'][idx],) # write your <document type>
            self.setup_text_insert()
        else:
            txt = "%s %s" % (_("Select your"), etpConst['ugc_doctypes_description_singular'][idx],) # select your <document type>
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
        if rc != _("Yes"):
            return False

        self.show_loading()

        old_show_progress = self.Entropy.UGC.show_progress
        self.Entropy.UGC.show_progress = True
        bck_updateProgress = self.Entropy.updateProgress
        self.Entropy.updateProgress = self.do_label_update_progress
        try:
            t = ParallelTask(self.do_send_document_autosense, doc_type, doc_path, title, description, keywords_text)
            t.start()
            while True:
                if not t.isAlive(): break
                while gtk.events_pending():
                    gtk.main_iteration()
                time.sleep(0.06)
            rslt, data = t.get_rc()
        finally:
            self.Entropy.UGC.show_progress = old_show_progress
            self.Entropy.updateProgress = bck_updateProgress


        self.hide_loading()
        if not rslt:
            txt = "<small><span foreground='%s'><b>%s</b></span>: %s | %s</small>" % (SulfurConf.color_error, _("UGC Error"), rslt, data,)
            self.ugcadd_ui.ugcAddStatusLabel.set_markup(txt)
            return False
        else:
            okDialog(self.ugcadd_ui.ugcAdd, _("Document added successfully. Thank you"), title = _("Success!"))
            self.on_closeAdd_clicked(None, None)
            self.refresh_cb()
            return True

    def do_label_update_progress(self, *myargs, **mykwargs):

        count = mykwargs.get("count")
        percent = mykwargs.get("percent")
        text = myargs[0].encode('utf-8')

        count_str = ""
        if count:
            if len(count) > 1:
                if percent:
                    count_str = " ("+str(round((float(count[0])/count[1])*100, 1))+"%) "
                else:
                    count_str = " (%s/%s) " % (str(count[0]), str(count[1]),)

        txt = count_str+text
        gtk.gdk.threads_enter()
        self.ugcadd_ui.ugcAddStatusLabel.set_markup(cleanMarkupString(txt))
        gtk.gdk.threads_leave()

    def do_send_document_autosense(self, doc_type, doc_path, title, description, keywords_text):
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
        except Exception as e:
            rslt = False
            data = e
        return rslt, data

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
        self.ugcadd_ui.ugcAddTitleEntry.set_max_length(255)
        self.ugcadd_ui.ugcAddInsertLabel.set_markup(txt)

    def setup_file_insert(self, txt = _("Select your file")):
        self.ugcadd_ui.ugcAddFileChooser.show()
        self.ugcadd_ui.ugcAddFrame.hide()
        self.ugcadd_ui.ugcAddDescLabel.show()
        self.ugcadd_ui.ugcAddDescEntry.show()
        self.ugcadd_ui.ugcAddTitleEntry.set_max_length(60)
        self.ugcadd_ui.ugcAddInsertLabel.set_markup(txt)

    def load(self):

        self.ugcadd_ui.ugcAddImage.set_from_file(self.pix_path)
        self.ugcadd_ui.labelAddKey.set_markup("<b>%s</b>" % (self.pkgkey,))
        self.ugcadd_ui.labelAddRepo.set_markup("<small>%s: <b>%s</b></small>" % (_("On repository"), self.repository,))

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


class MaskedPackagesDialog(MenuSkel):


    def __init__( self, Entropy, etpbase, parent, pkgs, top_text = None, sub_text = None ):

        self.Entropy = Entropy
        self.etpbase = etpbase
        self.parent = parent
        self.docancel = True
        self.mp_ui = UI( const.GLADE_FILE, 'packageMaskWindow', 'entropy' )
        self.mp_ui.signal_autoconnect(self._getAllMethods())
        self.window = self.mp_ui.packageMaskWindow
        self.mp_ui.packageMaskWindow.set_transient_for(self.parent)
        self.cancelbutton = self.mp_ui.maskDialogCancelButton
        self.okbutton = self.mp_ui.maskDialogOkButton
        self.enableButton = self.mp_ui.maskDialogEnableButton
        self.enableAllButton = self.mp_ui.maskDialogEnableAllButton
        self.propertiesButton = self.mp_ui.maskDialogPropertiesButton
        self.action = self.mp_ui.maskDialogAction
        self.subaction = self.mp_ui.maskDialogSubtext
        self.pkg = self.mp_ui.maskDialogPkg
        self.button_pressed = False
        # backward compat
        self.ok_button_reply = -5
        self.cancel_button_reply = -6
        self.rc = self.cancel_button_reply

        self.okbutton.connect("clicked", self.do_ok)
        self.cancelbutton.connect("clicked", self.do_cancel)
        self.enableButton.connect("clicked", self.enablePackage)
        self.enableAllButton.connect("clicked", self.enableAllPackages)
        self.propertiesButton.connect("clicked", self.openPackageProperties)

        # setup text
        if top_text == None:
            top_text = _("These are the packages that must be enabled to satisfy your request")

        tit = "<b><span foreground='%s' size='large'>%s</span></b>\n" % (SulfurConf.color_title, _("Some packages are masked"),)
        tit += top_text
        self.action.set_markup( tit )
        if sub_text != None: self.subaction.set_markup( sub_text )

        self.pkgs = pkgs
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
        mymenu = PkgInfoMenu(self.Entropy, obj, self.window)
        mymenu.load()

    def enablePackage(self, widget, obj = None, do_refresh = True):
        if not obj:
            obj = self.get_obj()
        if not obj: return
        if obj.matched_atom == (0, 0): return
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
                    self.enablePackage(None, obj, False)
        self.refresh()

    def refresh(self):
        self.pkg.queue_draw()
        self.pkg.expand_all()

    def do_cancel(self, widget):
        self.button_pressed = True

    def do_ok(self, widget):
        self.rc = self.ok_button_reply
        self.button_pressed = True

    def on_packageMaskWindow_destroy_event(self, *args, **kwargs):
        self.button_pressed = True

    def on_packageMaskWindow_delete_event(self, *args, **kwargs):
        self.button_pressed = True

    def run( self ):

        self.window.show_all()
        self.okbutton.set_sensitive(False)

        while not self.button_pressed:
            time.sleep(0.05)
            while gtk.events_pending():
                gtk.main_iteration()
            continue

        self.window.destroy()

        return self.rc

    def setup_view( self, view ):

        model = gtk.TreeStore( gobject.TYPE_PYOBJECT )
        view.set_model( model )

        cell1 = gtk.CellRendererText()
        column1 = gtk.TreeViewColumn( _( "Masked package" ), cell1 )
        column1.set_cell_data_func( cell1, self.show_pkg )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( 410 )
        column1.set_resizable( True )
        view.append_column( column1 )

        cell2 = gtk.CellRendererPixbuf()
        column2 = gtk.TreeViewColumn( _("Enabled"), cell2 )
        column2.set_cell_data_func( cell2, self.new_pixbuf )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 40 )
        column2.set_sort_column_id( -1 )
        view.append_column( column2 )
        column2.set_clickable( False )

        return model


    def set_pixbuf_to_cell(self, cell, do):
        if do:
            cell.set_property( 'stock-id', 'gtk-apply' )
        elif (not do) and isinstance(do, bool):
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
        mydata = obj.namedesc
        cell.set_property('markup', mydata )
        self.set_line_status(obj, cell)

    def set_line_status(self, obj, cell, stype = "cell-background"):
        if obj.queued == "r":
            cell.set_property(stype, '#FFE2A3')
        elif obj.queued == "u":
            cell.set_property(stype, '#B7BEFF')
        elif obj.queued == "i":
            cell.set_property(stype, '#D895FF')
        elif obj.queued == "rr":
            cell.set_property(stype, '#B7BEFF')
        elif obj.queued == "d":
            cell.set_property(stype, '#A7D0FF')
        elif not obj.queued:
            cell.set_property(stype, None)

    def show_data( self, model, pkgs ):

        model.clear()
        self.pkg.set_model(None)
        self.pkg.set_model(model)

        desc_len = 80
        search_col = 0
        categories = {}

        for po in pkgs:
            mycat = po.cat
            if mycat not in categories:
                categories[mycat] = []
            categories[mycat].append(po)

        from sulfur.package import DummyEntropyPackage

        cats = sorted(categories.keys())
        for category in cats:
            cat_desc = _("No description")
            cat_desc_data = self.Entropy.get_category_description_data(category)
            if _LOCALE in cat_desc_data:
                cat_desc = cat_desc_data[_LOCALE]
            elif 'en' in cat_desc_data:
                cat_desc = cat_desc_data['en']
            cat_text = "<b><big>%s</big></b>\n<small>%s</small>" % (category, cleanMarkupString(cat_desc),)
            mydummy = DummyEntropyPackage(
                    namedesc = cat_text,
                    dummy_type = SulfurConf.dummy_category,
                    onlyname = category
            )
            mydummy.color = SulfurConf.color_package_category
            parent = model.append( None, (mydummy,) )
            for po in categories[category]:
                model.append( parent, (po,) )

        self.pkg.set_search_column( search_col )
        self.pkg.set_search_equal_func(self.atom_search)
        self.pkg.set_property('headers-visible', True)
        self.pkg.set_property('enable-search', True)

    def atom_search(self, model, column, key, iterator):
        obj = model.get_value( iterator, 0 )
        if obj:
            return not obj.onlyname.startswith(key)
        return True

    def destroy( self ):
        return self.window.destroy()

class TextReadDialog(MenuSkel):


    def __init__(self, title, text, read_only = True, rw_save_path = None):

        self.rw_save_path = rw_save_path
        self.txt_buffer = text
        if not isinstance(text, gtk.TextBuffer):
            self.txt_buffer = gtk.TextBuffer()
            self.txt_buffer.set_text(text)
        if not read_only and (rw_save_path == None):
            raise AttributeError("rw_save_path must be vaild if not read_only")

        xml_read = gtk.glade.XML(const.GLADE_FILE, 'textReadWindow',
            domain="entropy")
        self.__read_dialog = xml_read.get_widget( "textReadWindow" )
        ok_read = xml_read.get_widget( "okReadButton" )
        ok_read.connect( 'clicked', self.ok_button )
        ok_save = xml_read.get_widget("okSaveButton")
        ok_cancel = xml_read.get_widget("okCancelButton")
        self.txt_view = xml_read.get_widget( "readTextView" )
        self.txt_view.set_buffer(self.txt_buffer)
        self.__read_dialog.set_title(title)
        self.__read_dialog.show_all()
        self.done_reading = False

        ok_save.hide()
        ok_cancel.hide()
        if not read_only:
            self.txt_view.set_editable(True)
            self.txt_view.set_cursor_visible(True)
            ok_read.hide()
            ok_save.connect( 'clicked', self.ok_save_button )
            ok_cancel.connect( 'clicked', self.ok_cancel_button )
            ok_save.show()
            ok_cancel.show()

    def get_content(self):
        start = self.txt_buffer.get_start_iter()
        end = self.txt_buffer.get_end_iter()
        return self.txt_buffer.get_text(start, end)

    def ok_save_button(self, widget):
        source_f = open(self.rw_save_path+".etp_tmp", "w")
        cont = self.get_content()
        source_f.write(cont)
        source_f.flush()
        source_f.close()
        os.rename(self.rw_save_path+".etp_tmp", self.rw_save_path)
        self.ok_button(widget)

    def ok_cancel_button(self, widget):
        self.ok_button(widget)

    def ok_button(self, widget):
        self.done_reading = True
        self.__read_dialog.destroy()

    def run( self ):
        """ you don't have to run this if you're looking for non-blocking d. """
        while not self.done_reading:
            time.sleep(0.1)
            while gtk.events_pending():
                gtk.main_iteration()
            continue



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
        self.okbutton = self.xml.get_widget( "okbutton2" )
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

        tit = "<b>%s</b>" % (top_text,)
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
        self.create_text_column( _( "Item" ), view, 0 )
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
        if "downgrade" in pkgs:
            if pkgs['downgrade']:
                label = "<b>%s</b>" % _("To be downgraded")
                parent = model.append( None, [label] )
                for pkg in pkgs['downgrade']:
                    model.append( parent, [pkg] )
        if "remove" in pkgs:
            if pkgs['remove']:
                label = "<b>%s</b>" % _("To be removed")
                parent = model.append( None, [label] )
                for pkg in pkgs['remove']:
                    model.append( parent, [pkg] )
        if "reinstall" in pkgs:
            if pkgs['reinstall']:
                label = "<b>%s</b>" % _("To be reinstalled")
                parent = model.append( None, [label] )
                for pkg in pkgs['reinstall']:
                    model.append( parent, [pkg] )
        if "install" in pkgs:
            if pkgs['install']:
                label = "<b>%s</b>" % _("To be installed")
                parent = model.append( None, [label] )
                for pkg in pkgs['install']:
                    model.append( parent, [pkg] )
        if "update" in pkgs:
            if pkgs['update']:
                label = "<b>%s</b>" % _("To be updated")
                parent = model.append( None, [label] )
                for pkg in pkgs['update']:
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
        downgrade = [x for x in pkgs if x.action == "d"]
        if remove:
            label = "<b>%s</b>" % _("To be removed")
            level1 = model.append( None, [label] )
            for pkg in remove:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='%s'>%s</span></small>" % (SulfurConf.color_pkgdesc, desc,)
                mypkg = "<span foreground='%s'>%s</span>" % (SulfurConf.color_remove, str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if downgrade:
            label = "<b>%s</b>" % _("To be downgraded")
            level1 = model.append( None, [label] )
            for pkg in downgrade:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='%s'>%s</span></small>" % (SulfurConf.color_pkgdesc, desc,)
                mypkg = "<span foreground='%s'>%s</span>" % (SulfurConf.color_downgrade, str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if reinstall:
            label = "<b>%s</b>" % _("To be reinstalled")
            level1 = model.append( None, [label] )
            for pkg in reinstall:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='%s'>%s</span></small>" % (SulfurConf.color_pkgdesc, desc,)
                mypkg = "<span foreground='%s'>%s</span>" % (SulfurConf.color_reinstall, str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if install:
            label = "<b>%s</b>" % _("To be installed")
            level1 = model.append( None, [label] )
            for pkg in install:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='%s'>%s</span></small>" % (SulfurConf.color_pkgdesc, desc,)
                mypkg = "<span foreground='%s'>%s</span>" % (SulfurConf.color_install, str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if update:
            label = "<b>%s</b>" % _("To be updated")
            level1 = model.append( None, [label] )
            for pkg in update:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='%s'>%s</span></small>" % (SulfurConf.color_pkgdesc, desc,)
                mypkg = "<span foreground='%s'>%s</span>" % (SulfurConf.color_update, str(pkg),)
                model.append( level1, [mypkg+mydesc] )

    def destroy( self ):
        return self.dialog.destroy()

class ErrorDialog:

    def __init__( self, parent, title, text, longtext, modal ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "errDialog", domain="entropy" )
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
        self.style_err.set_property( "foreground", "#760000" )
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
        return name, mail, desc

    def destroy( self ):
        return self.dialog.destroy()

class infoDialog:
    def __init__( self, parent, title, text ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "msg", domain="entropy" )
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
        self.xml = gtk.glade.XML( const.GLADE_FILE, "EntryDialog", domain="entropy" )
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

    def __init__(self, gfx, creditText, title = "Sulfur Project"):

        self.__is_stopped = True
        self.__scroller_values = ()


        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_resizable(False)
        self.set_title("%s %s" % (_("About"), title,))
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
        gobject.idle_add(self.__scroll, begin)


def inputBox( parent, title, text, input_text = None):
    dlg = EntryDialog(parent, title, text)
    if input_text:
        dlg.entry.set_text(input_text)
    rc = dlg.run()
    dlg.destroy()
    return rc

def FileChooser(basedir = None, pattern = None, action = gtk.FILE_CHOOSER_ACTION_OPEN, buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK)):
    # open file selector
    chooser_title = _("Sulfur file chooser")
    dialog = gtk.FileChooserDialog(
        title = chooser_title,
        action = action,
        buttons = buttons
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

def questionDialog(parent, msg, title = _("Sulfur Question"), get_response = False):
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
        self.callback_parent_window = mywin
        # avoids to taint the returning elements
        # when running nested
        self.parameters = self.parameters.copy()

        mywin.set_title(_("Please fill the following form"))
        myvbox = gtk.VBox()
        mylabel = gtk.Label()
        mylabel.set_markup(cleanMarkupString(title))
        myhbox = gtk.HBox()
        myvbox.pack_start(mylabel, expand = False, fill = False)
        mytable = gtk.Table(rows = len(input_parameters), columns = 2)
        self.identifiers_table = {}
        self.cb_table = {}
        self.entry_text_table = {}
        row_count = 0
        for input_id, input_text, input_cb, passworded in input_parameters:

            if isinstance(input_text, tuple):

                input_type, text = input_text
                combo_options = []
                if isinstance(text, tuple):
                    text, combo_options = text

                input_label = gtk.Label()
                input_label.set_line_wrap(True)
                input_label.set_alignment(0.0, 0.5)
                input_label.set_markup(text)

                if input_type == "checkbox":

                    input_widget = gtk.CheckButton(text)
                    input_widget.set_alignment(0.0, 0.5)
                    input_widget.set_active(passworded)

                elif input_type == "combo":

                    input_widget = gtk.combo_box_new_text()
                    for opt in combo_options:
                        input_widget.append_text(opt)
                    if combo_options:
                        input_widget.set_active(0)
                    mytable.attach(input_label, 0, 1, row_count, row_count+1)

                elif input_type == "list":

                    myhbox_l = gtk.HBox()
                    input_widget = gtk.ListStore(gobject.TYPE_STRING)
                    view = gtk.TreeView()
                    cell = gtk.CellRendererText()
                    column = gtk.TreeViewColumn( text, cell, markup = 0 )
                    column.set_resizable( True )
                    column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
                    column.set_expand(True)
                    view.append_column( column )
                    view.set_model(input_widget)
                    for opt in combo_options:
                        input_widget.append((opt,))
                    myhbox_l.pack_start(view, expand = True, fill = True)

                    myvbox_l = gtk.VBox()
                    add_button = gtk.Button()
                    add_image = gtk.Image()
                    add_image.set_from_stock("gtk-add", gtk.ICON_SIZE_BUTTON)
                    add_button.add(add_image)
                    rm_button = gtk.Button()
                    rm_image = gtk.Image()
                    rm_image.set_from_stock("gtk-remove", gtk.ICON_SIZE_BUTTON)
                    rm_button.add(rm_image)
                    myvbox_l.pack_start(add_button, expand = False, fill = False)
                    myvbox_l.pack_start(rm_button, expand = False, fill = False)

                    def on_add_button(widget):
                        mydata = inputDialog(mywin, _("Add atom"),
                            [('atom', _('Atom'), input_cb, False)], True)
                        if mydata == None:
                            return
                        atom = mydata.get('atom')
                        input_widget.append((atom,))

                    def on_remove_button(widget):
                        model, iterator = view.get_selection().get_selected()
                        if iterator == None:
                            return
                        model.remove(iterator)

                    add_button.connect("clicked", on_add_button)
                    rm_button.connect("clicked", on_remove_button)

                    myhbox_l.pack_start(myvbox_l, expand = False, fill = False)
                    mytable.attach(myhbox_l, 0, 2, row_count, row_count+1)

                elif input_type == "filled_text":

                    input_widget = gtk.Entry()
                    input_widget.set_text(combo_options)
                    if passworded:
                        input_widget.set_visibility(False)
                    mytable.attach(input_label, 0, 1, row_count, row_count+1)

                elif input_type == "text":

                    def rescroll_output(adj, scroll):
                        adj.set_value(adj.upper-adj.page_size)
                        scroll.set_vadjustment(adj)

                    scrolled_win = gtk.ScrolledWindow()
                    scrolled_win.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
                    scrolled_win.set_placement(gtk.CORNER_BOTTOM_LEFT)
                    # textview
                    input_widget = gtk.TextBuffer()
                    output_scroll_vadj = scrolled_win.get_vadjustment()
                    output_scroll_vadj.connect('changed', lambda a, s=scrolled_win: rescroll_output(a, s))

                    my_tv = gtk.TextView()
                    my_tv.set_buffer(input_widget)
                    my_tv.set_wrap_mode(gtk.WRAP_WORD)
                    my_tv.set_editable(True)
                    my_tv.set_accepts_tab(True)
                    scrolled_win.add_with_viewport(my_tv)
                    mytable.attach(input_label, 0, 1, row_count, row_count+1)
                    mytable.attach(scrolled_win, 1, 2, row_count, row_count+1)

                else:
                    continue

                self.entry_text_table[input_id] = text
                self.identifiers_table[input_id] = input_widget

                if input_type in ["list", "text", "combo", "filled_text"]:
                    def my_input_cb(s):
                        return s
                    self.cb_table[input_widget] = my_input_cb
                elif input_type == "checkbox":
                    def my_input_cb(s):
                        return True
                    self.cb_table[input_widget] = my_input_cb


                if input_type not in ["text", "list"]:
                    mytable.attach(input_widget, 1, 2, row_count, row_count+1)


            else:

                input_label = gtk.Label()
                input_label.set_line_wrap(True)
                input_label.set_alignment(0.0, 0.5)
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
        myvbox.pack_start(bbox, expand = False, fill = False)
        myvbox.set_spacing(10)
        myvbox.show()
        myhbox.pack_start(myvbox, padding = 10)
        myhbox.show()
        mywin.add(myhbox)
        self.main_window = mywin
        self.parent = parent
        mywin.set_keep_above(True)
        mywin.set_urgency_hint(True)
        if parent == None:
            mywin.set_position(gtk.WIN_POS_CENTER)
        else:
            mywin.set_transient_for(parent)
            mywin.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        mywin.set_default_size(350, -1)
        mywin.show_all()


    def do_ok(self, widget):
        # fill self.parameters
        for input_id in self.identifiers_table:
            mywidget = self.identifiers_table.get(input_id)
            if isinstance(mywidget, gtk.Entry):
                content = mywidget.get_text()
            elif isinstance(mywidget, gtk.CheckButton):
                content = mywidget.get_active()
            elif isinstance(mywidget, gtk.ComboBox):
                content = mywidget.get_active(), mywidget.get_active_text()
            elif isinstance(mywidget, gtk.TextBuffer):
                content = mywidget.get_text(mywidget.get_start_iter(), mywidget.get_end_iter(), True)
            elif isinstance(mywidget, (gtk.ListStore, gtk.TreeStore)):
                myiter = mywidget.get_iter_first()
                content = []
                while myiter:
                    content.append(mywidget.get_value(myiter, 0))
                    myiter = mywidget.iter_next(myiter)
            else:
                continue
            verify_cb = self.cb_table.get(mywidget)
            valid = verify_cb(content)
            if not valid:
                okDialog(self.callback_parent_window, "%s: %s" % (
                    _("Invalid entry"),
                    self.entry_text_table[input_id],),
                    title = _("Invalid entry"))
                self.parameters.clear()
                return
            self.parameters[input_id] = content
        self.button_pressed = True

    def do_cancel(self, widget):
        self.parameters = None
        self.button_pressed = True

    def run(self):
        self.parameters.clear()
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
    def __init__( self, application, entropy, licenses ):

        self.parent = application.ui.main
        self.Sulfur = application
        self.Entropy = entropy
        self.xml = gtk.glade.XML( const.GLADE_FILE, 'licenseWindow',
            domain = "entropy" )
        self.xml_licread = gtk.glade.XML( const.GLADE_FILE, 'textReadWindow',
            domain = "entropy" )
        self.dialog = self.xml.get_widget( "licenseWindow" )
        self.dialog.set_transient_for( self.parent )
        self.read_dialog = self.xml_licread.get_widget( "textReadWindow" )
        self.read_dialog.connect( 'delete-event', self.close_read_text_window )
        #self.read_dialog.set_transient_for( self.dialog )
        self.licenseView = self.xml_licread.get_widget( "readTextView" )
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
        self.dialog.show()
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
        elif (not do) and isinstance(do, bool):
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

            if model.iter_depth(iterator):
                # we need to get its parent
                iterator = model.get_iter_root()

            license_identifier = model.get_value( iterator, 0 )
            # for security reasons
            if license_identifier not in self.licenses:
                return

            packages = self.licenses[license_identifier]
            license_text = ''
            for package in packages:
                repoid = package[1]
                dbconn = self.Entropy.open_repository(repoid)
                if dbconn.isLicensedataKeyAvailable(license_identifier):
                    license_text = dbconn.retrieveLicenseText(license_identifier)
                    break

            # prepare textview
            mybuffer = gtk.TextBuffer()
            try:
                utf_lic_text = license_text.decode('utf-8')
            except UnicodeDecodeError: # old license text stored, will be rm'ed
                utf_lic_text = const_convert_to_unicode(license_text)
            mybuffer.set_text(utf_lic_text)
            self.licenseView.set_buffer(mybuffer)
            txt = "[%s] %s" % (license_identifier, _("license text"),)
            self.read_dialog.set_title(txt)
            self.read_dialog.show()

    def accept_selected_license(self, widget):
        model, iterator = self.view.get_selection().get_selected()
        if model != None and iterator != None:

            if model.iter_depth(iterator):
                # we need to get its parent
                iterator = model.get_iter_root()

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
            parent = self.model.append( None, [lic, True] )
            packages = licenses[lic]
            for match in packages:
                dbconn = self.Entropy.open_repository(match[1])
                atom = dbconn.retrieveAtom(match[0])
                self.model.append( parent, [atom, None] )

class WaitWindow(MenuSkel):

    def __init__(self, window):

        self.wait_ui = UI( const.GLADE_FILE, 'waitWindow', 'entropy' )
        self.wait_ui.signal_autoconnect(self._getAllMethods())
        self.wait_ui.waitWindow.set_transient_for(window)
        self.window = window

    def show(self):
        self.window.set_sensitive(False)
        self.wait_ui.waitWindow.show_all()
        self.wait_ui.waitWindow.queue_draw()
        self.window.queue_draw()
        while gtk.events_pending():
           gtk.main_iteration()

    def hide(self):
        self.wait_ui.waitWindow.hide()
        self.window.set_sensitive(True)


class ExceptionDialog:

    def __init__(self):
        pass

    def show(self, errmsg = None):

        if errmsg is None:
            errmsg = entropyTools.get_traceback()
        conntest = entropyTools.get_remote_data(etpConst['distro_website_url'])
        rc, (name, mail, description) = errorMessage(
            None,
            _( "Exception caught" ),
            _( "Sulfur crashed! An unexpected error occured." ),
            errmsg,
            showreport = conntest
        )
        if rc == -1:

            from entropy.client.interfaces.qa import UGCErrorReportInterface
            try:
                error = UGCErrorReportInterface()
            except (IncorrectParameter, OnlineMirrorError,):
                error = None

            result = None
            if error is not None:
                error.prepare(errmsg, name, mail, description = description)
                result = error.submit()
            if result:
                okDialog(None, _("Your report has been submitted successfully! Thanks a lot."))
            else:
                okDialog(None, _("Cannot submit your report. Not connected to Internet?"))
        raise SystemExit(1)
