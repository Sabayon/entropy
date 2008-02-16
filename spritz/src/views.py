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

import gtk
import gobject
import logging
import glob
import ConfigParser
from misc import const
from etpgui.widgets import UI
from etpgui import *
from entropyConstants import *

from i18n import _

TOGGLE_WIDTH = 12

class SpritzCategoryView:
    def __init__( self, treeview):
        self.view = treeview
        self.model = self.setup_view()

    def setup_view( self ):
        """ Setup Category View  """
        model = gtk.TreeStore( gobject.TYPE_STRING,gobject.TYPE_STRING )
        self.view.set_model( model )
        cell1 = gtk.CellRendererText()
        column1= gtk.TreeViewColumn( _( "Categories" ), cell1, markup=0 )
        column1.set_resizable( True )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( 150 )

        self.view.append_column( column1 )
        self.view.set_headers_visible(False)
        return model

    def populate(self,data,tree=False):
        self.model.clear()
        if tree:
            data.populate(self.model)
        else:
            for el in data:
                self.model.append(None,[el,el])

class EntropyPackageView:
    def __init__( self, treeview, qview, ui, etpbase ):

        self.selection_width = 20
        self.loaded_widget = None
        self.loaded_reinstallable = None
        self.loaded_event = None
        self.event_click_pos = 0,0
        # default for installed packages
        self.pkg_install_ok = "package-installed-updated.png"
        self.pkg_install_updatable = "package-installed-outdated.png"
        self.pkg_install_new = "package-available.png"
        self.pkg_remove = "package-remove.png"
        self.pkg_purge = "package-purge.png"
        self.pkg_reinstall = "package-reinstall.png"
        self.pkg_install = "package-install.png"
        self.pkg_update = "package-upgrade.png"
        self.pkg_downgrade = "package-downgrade.png"
        self.pkg_undoinstall = "package-undoinstall.png"

        self.img_pkg_install_ok = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_install_ok,self.pkg_install_ok)
        self.img_pkg_install_updatable = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_install_updatable,self.pkg_install_updatable)
        self.img_pkg_update = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_update,self.pkg_update)
        self.img_pkg_downgrade = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_downgrade,self.pkg_downgrade)

        self.img_pkg_install_new = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_install_new,self.pkg_install_new)

        self.img_pkg_remove = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_remove,self.pkg_remove)
        self.img_pkg_undoremove = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_undoremove,self.pkg_remove)
        self.img_pkg_purge = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_purge,self.pkg_purge)
        self.img_pkg_undopurge = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_undopurge,self.pkg_purge)
        self.img_pkg_reinstall = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_reinstall,self.pkg_reinstall)
        self.img_pkg_undoreinstall = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_undoreinstall,self.pkg_reinstall)

        self.img_pkg_install = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_install,self.pkg_install)
        self.img_pkg_undoinstall = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_undoinstall,self.pkg_undoinstall)

        treeview.set_fixed_height_mode(True)
        self.view = treeview
        self.view.connect("button-release-event", self.load_menu)
        self.store = self.setupView()
        self.queue = qview.queue
        self.queueView = qview
        self.ui = ui
        self.etpbase = etpbase
        self.clearUpdates()

        # installed packages right click menu
        self.installed_menu_xml = gtk.glade.XML( const.GLADE_FILE, "packageInstalled",domain="yumex" )
        self.installed_menu = self.installed_menu_xml.get_widget( "packageInstalled" )
        self.installed_menu_xml.signal_autoconnect(self)

        self.installed_reinstall = self.installed_menu_xml.get_widget( "reinstall" )
        self.installed_undoreinstall = self.installed_menu_xml.get_widget( "undoreinstall" )
        self.installed_purge = self.installed_menu_xml.get_widget( "purge" )
        self.installed_undopurge = self.installed_menu_xml.get_widget( "undopurge" )
        self.installed_remove = self.installed_menu_xml.get_widget( "remove" )
        self.installed_undoremove = self.installed_menu_xml.get_widget( "undoremove" )
        self.installed_reinstall.set_image(self.img_pkg_reinstall)
        self.installed_undoreinstall.set_image(self.img_pkg_undoreinstall)
        self.installed_remove.set_image(self.img_pkg_remove)
        self.installed_undoremove.set_image(self.img_pkg_undoremove)
        self.installed_purge.set_image(self.img_pkg_purge)
        self.installed_undopurge.set_image(self.img_pkg_undopurge)

        # updates right click menu
        self.updates_menu_xml = gtk.glade.XML( const.GLADE_FILE, "packageUpdates",domain="yumex" )
        self.updates_menu = self.updates_menu_xml.get_widget( "packageUpdates" )
        self.updates_menu_xml.signal_autoconnect(self)
        self.updates_update = self.updates_menu_xml.get_widget( "update" )
        self.updates_undoupdate = self.updates_menu_xml.get_widget( "undoupdate" )
        self.updates_update.set_image(self.img_pkg_update)
        self.updates_undoupdate.set_image(self.img_pkg_downgrade)

        # install right click menu
        self.install_menu_xml = gtk.glade.XML( const.GLADE_FILE, "packageInstall",domain="yumex" )
        self.install_menu = self.install_menu_xml.get_widget( "packageInstall" )
        self.install_menu_xml.signal_autoconnect(self)
        self.install_install = self.install_menu_xml.get_widget( "install" )
        self.install_undoinstall = self.install_menu_xml.get_widget( "undoinstall" )
        self.install_install.set_image(self.img_pkg_install)
        self.updates_undoupdate.set_image(self.img_pkg_undoinstall)

    def reset_install_menu(self):
        self.install_install.show()
        self.install_undoinstall.hide()

    def hide_install_menu(self):
        self.install_install.hide()
        self.install_undoinstall.hide()

    def reset_updates_menu(self):
        self.updates_undoupdate.hide()
        self.updates_update.show()

    def hide_updates_menu(self):
        self.updates_undoupdate.hide()
        self.updates_update.hide()

    def reset_installed_packages_menu(self):
        self.installed_undoremove.hide()
        self.installed_undoreinstall.hide()
        self.installed_undopurge.hide()
        self.installed_remove.show()
        self.installed_reinstall.show()
        self.installed_purge.show()

    def hide_installed_packages_menu(self):
        self.installed_undoremove.hide()
        self.installed_undoreinstall.hide()
        self.installed_undopurge.hide()
        self.installed_remove.hide()
        self.installed_reinstall.hide()
        self.installed_purge.hide()

    def load_menu(self, widget, event):
        self.loaded_widget = widget
        self.loaded_event = event
        #if event.button != 3:
        #    return True

        if event.x < 10:
            return

        try:
            row, column, x, y = widget.get_path_at_pos(int(event.x),int(event.y))
        except TypeError:
            return
        self.event_click_pos = x,y
        if column.get_title() != "   S":
            return
        model, iter = widget.get_selection().get_selected()
        if iter:
            obj = model.get_value( iter, 0 )
            if obj.action in ["r"]: # installed packages listing
                self.run_installed_menu_stuff(obj)
            elif obj.action in ["u"]: # updatable packages listing
                self.run_updates_menu_stuff(obj)
            elif obj.action in ["i"]:
                self.run_install_menu_stuff(obj)

    def reposition_menu(self, menu):
        # devo tradurre x=0,y=20 in posizioni assolute
        abs_x, abs_y = self.loaded_event.get_root_coords()
        #print abs_x,abs_y
        #print self.loaded_event.x,self.loaded_event.y
        abs_x -= self.loaded_event.x
        event_y = self.loaded_event.y
        # FIXME: find a better way to properly position menu
        while event_y > self.selection_width+5:
            event_y -= self.selection_width+4
        abs_y += (self.selection_width-event_y)
        return int(abs_x),int(abs_y),True

    def run_install_menu_stuff(self, obj):
        do_show = True
        self.reset_install_menu()
        if obj.queued:
            self.hide_install_menu()
            self.install_undoinstall.show()
        self.install_menu.popup( None, None, self.reposition_menu, self.loaded_event.button, self.loaded_event.time )

    def run_updates_menu_stuff(self, obj):
        do_show = True
        self.reset_updates_menu()
        if obj.queued:
            self.hide_updates_menu()
            self.updates_undoupdate.show()
        self.updates_menu.popup( None, None, self.reposition_menu, self.loaded_event.button, self.loaded_event.time)

    def run_installed_menu_stuff(self, obj):
        do_show = True
        self.reset_installed_packages_menu()
        if obj.queued:
            self.hide_installed_packages_menu()
            if obj.queued == "r" and not obj.do_purge:
                self.installed_undoremove.show()
            elif obj.queued == "rr":
                self.installed_undoreinstall.show()
                self.set_loaded_reinstallable(obj)
            elif obj.queued == "r" and obj.do_purge:
                self.installed_undopurge.show()
        else:
            # is it a system package ?
            if obj.syspkg:
                self.installed_remove.hide()
                self.installed_purge.hide()

            if str(obj) not in self.etpbase.getPackages("reinstallable"):
                if obj.syspkg:
                    do_show = False
                self.installed_reinstall.hide()
            else:
                self.set_loaded_reinstallable(obj)
                if not self.loaded_reinstallable:
                    self.installed_reinstall.hide()
        if do_show: self.installed_menu.popup( None, None, self.reposition_menu, self.loaded_event.button, self.loaded_event.time )

    def set_loaded_reinstallable(self, obj):
        reinstallables = self.etpbase.getPackages("reinstallable")
        self.loaded_reinstallable = None
        for to_obj in reinstallables:
            if str(obj) == str(to_obj):
                self.loaded_reinstallable = to_obj
                break

    def on_remove_activate(self, widget, do_purge = False):
        busyCursor(self.ui.main)
        model, iter = self.loaded_widget.get_selection().get_selected()
        obj = self.store.get_value( iter, 0 )
        oldqueued = obj.queued
        oldpurge = obj.do_purge
        obj.queued = "r"
        if do_purge:
            obj.do_purge = True
        status, myaction = self.queue.add(obj)
        if status != 0:
            obj.queued = oldqueued
            obj.do_purge = oldpurge
        self.queueView.refresh()
        normalCursor(self.ui.main)

    def on_reinstall_activate(self, widget):
        busyCursor(self.ui.main)
        model, iter = self.loaded_widget.get_selection().get_selected()
        obj = self.store.get_value( iter, 0 )
        oldqueued = obj.queued
        obj.queued = "rr"
        oldqueued_reinstallable = self.loaded_reinstallable.queued
        self.loaded_reinstallable.queued = "rr"
        status, myaction = self.queue.add(self.loaded_reinstallable)
        if status != 0:
            obj.queued = oldqueued
            self.loaded_reinstallable.queued = oldqueued_reinstallable
        self.queueView.refresh()
        normalCursor(self.ui.main)

    def on_undoreinstall_activate(self, widget):
        busyCursor(self.ui.main)
        model, iter = self.loaded_widget.get_selection().get_selected()
        obj = self.store.get_value( iter, 0 )
        obj.queued = None
        self.remove_queued(self.loaded_reinstallable)
        self.queueView.refresh()
        normalCursor(self.ui.main)

    def on_undoremove_activate(self, widget):
        busyCursor(self.ui.main)
        model, iter = self.loaded_widget.get_selection().get_selected()
        obj = self.store.get_value( iter, 0 )
        self.remove_queued(obj)
        obj.do_purge = False
        self.queueView.refresh()
        normalCursor(self.ui.main)

    def remove_queued(self, obj):
        oldqueued = obj.queued
        obj.queued = None
        status, myaction = self.queue.remove(obj)
        if status != 0:
            obj.queued = oldqueued
        self.view.queue_draw()
        return status

    def on_purge_activate(self, widget):
        self.on_remove_activate(widget, True)
        self.view.queue_draw()

    def on_undopurge_activate(self, widget):
        self.on_undoremove_activate(widget)
        self.view.queue_draw()

    def on_update_activate(self, widget):
        self.on_install_update_activate(widget, "u")
        self.view.queue_draw()

    def on_undoupdate_activate(self, widget):
        self.on_undoinstall_undoupdate_activate(widget)
        self.view.queue_draw()

    def on_install_activate(self, widget):
        self.on_install_update_activate(widget, "i")
        self.view.queue_draw()

    def on_undoinstall_activate(self, widget):
        self.on_undoinstall_undoupdate_activate(widget)
        self.view.queue_draw()

    def on_install_update_activate(self, widget, action):
        busyCursor(self.ui.main)
        model, iter = self.loaded_widget.get_selection().get_selected()
        obj = self.store.get_value( iter, 0 )
        oldqueued = obj.queued
        obj.queued = action
        status, myaction = self.queue.add(obj)
        if status != 0:
            obj.queued = oldqueued
        self.queueView.refresh()
        normalCursor(self.ui.main)
        self.view.queue_draw()

    def on_undoinstall_undoupdate_activate(self, widget):
        busyCursor(self.ui.main)
        model, iter = self.loaded_widget.get_selection().get_selected()
        obj = self.store.get_value( iter, 0 )
        self.remove_queued(obj)
        self.queueView.refresh()
        normalCursor(self.ui.main)
        self.view.queue_draw()

    def setupView( self ):
        store = gtk.ListStore( gobject.TYPE_PYOBJECT, str )
        self.view.set_model( store )

        # Setup resent column
        cell1 = gtk.CellRendererPixbuf()    # new
        self.set_pixbuf_to_cell(cell1, self.pkg_install_ok )
        column1 = gtk.TreeViewColumn( "   S", cell1 )
        column1.set_cell_data_func( cell1, self.new_pixbuf )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( self.selection_width+20 )
        column1.set_sort_column_id( -1 )
        self.view.append_column( column1 )
        column1.set_clickable( False )

        self.create_text_column( _( "Package" ), 'name' , size=300)
        self.create_text_column( _( "Rev." ), 'revision' , size=40 )
        self.create_text_column( _( "Slot" ), 'slot' , size = 40 )
        self.create_text_column( _( "Repository" ), 'repoid', size = 100 )
        #self.create_text_column( _( "Size" ), 'intelligentsizeFmt', size=80 )
        #self.create_text_column( _( "Download" ), 'sizeFmt' , size=80 )
        self.view.set_search_column( 1 )
        self.view.set_enable_search(False)
        #store.set_sort_column_id(1, gtk.SORT_ASCENDING)# SLOOOW
        #self.view.set_reorderable( False )
        return store

    def set_pixbuf_to_cell(self, cell, filename):
        pixbuf = gtk.gdk.pixbuf_new_from_file(const.PIXMAPS_PATH+"/packages/"+filename)
        cell.set_property( 'pixbuf', pixbuf )

    def set_pixbuf_to_image(self, img, filename):
        img.set_from_file(const.PIXMAPS_PATH+"/packages/"+filename)

    def create_text_column( self, hdr, property, size, sortcol = None):
        """
        Create a TreeViewColumn with text and set
        the sorting properties and add it to the view
        """
        cell = gtk.CellRendererText()    # Size Column
        column = gtk.TreeViewColumn( hdr, cell )
        column.set_resizable( True )
        column.set_cell_data_func( cell, self.get_data_text, property )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( size )
        column.set_sort_column_id( -1 )
        self.view.append_column( column )
        return column

    def get_data_text( self, column, cell, model, iter, property ):
        obj = model.get_value( iter, 0 )
        if obj:
            cell.set_property( 'text', getattr( obj, property ) )
            cell.set_property('foreground',obj.color)

    def selectAll(self):
        list = [x[0] for x in self.store if not x[0].queued == x[0].action]
        if not list:
            return
        for obj in list:
            obj.queued = obj.action
        self.clearUpdates()
        self.updates['u'] = self.queue.packages['u'][:]
        self.updates['i'] = self.queue.packages['i'][:]
        self.updates['r'] = self.queue.packages['r'][:]
        status, myaction = self.queue.add(list)
        if status == 0:
            self.updates['u'] = [x for x in self.queue.packages['u'] if x not in self.updates['u']]
            self.updates['i'] = [x for x in self.queue.packages['i'] if x not in self.updates['i']]
            self.updates['r'] = [x for x in self.queue.packages['r'] if x not in self.updates['r']]
        else:
            for obj in list:
                obj.queued = None
        self.queueView.refresh()
        self.view.queue_draw()

    def clearUpdates(self):
        self.updates = {}
        self.updates['u'] = []
        self.updates['r'] = []
        self.updates['i'] = []

    def deselectAll(self):
        xlist = [x[0] for x in self.store if x[0].queued == x[0].action]
        xlist += [x for x in self.updates['u']+self.updates['i']+self.updates['r'] if x not in xlist]
        if not xlist:
            return
        for obj in xlist:
            obj.queued = None
        self.queue.remove(xlist)
        for obj in xlist:
            obj.set_select( False )
        self.clearUpdates()
        self.queueView.refresh()
        self.view.queue_draw()

    def new_pixbuf( self, column, cell, model, iter ):
        """ 
        Cell Data function for recent Column, shows pixmap
        if recent Value is True.
        """
        pkg = model.get_value( iter, 0 )
        if pkg:
            if not pkg.queued:
                if pkg.action == "r":
                    self.set_pixbuf_to_cell(cell, self.pkg_install_ok)
                elif pkg.action == "i":
                    self.set_pixbuf_to_cell(cell, self.pkg_install_new)
                else:
                    self.set_pixbuf_to_cell(cell, self.pkg_install_updatable)
            else:
                if pkg.queued == "r" and not pkg.do_purge:
                    self.set_pixbuf_to_cell(cell, self.pkg_remove)
                if pkg.queued == "r" and pkg.do_purge:
                    self.set_pixbuf_to_cell(cell, self.pkg_purge)
                elif pkg.queued == "rr":
                    self.set_pixbuf_to_cell(cell, self.pkg_reinstall)
                elif pkg.queued == "i":
                    self.set_pixbuf_to_cell(cell, self.pkg_install)
                elif pkg.queued == "u":
                    self.set_pixbuf_to_cell(cell, self.pkg_update)

        else:
            cell.set_property( 'visible', False )

class EntropyQueueView:
    """ Queue View Class"""
    def __init__( self, widget, queue ):
        self.view = widget
        self.model = self.setup_view()
        self.queue = queue

    def setup_view( self ):
        """ Create Notebook list for single page  """
        model = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_STRING )
        self.view.set_model( model )
        cell1 = gtk.CellRendererText()
        column1= gtk.TreeViewColumn( _( "Packages" ), cell1, markup=0 )
        column1.set_resizable( True )
        self.view.append_column( column1 )

        cell2 = gtk.CellRendererText()
        column2= gtk.TreeViewColumn( _( "Description" ), cell2, text=1 )
        column2.set_resizable( True )
        self.view.append_column( column2 )
        model.set_sort_column_id( 0, gtk.SORT_ASCENDING )
        self.view.get_selection().set_mode( gtk.SELECTION_MULTIPLE )
        return model

    def deleteSelected( self ):
        rmvlist = []
        model, paths = self.view.get_selection().get_selected_rows()
        for p in paths:
            row = model[p]
            if row.parent != None:
                rmvlist.append( row[0] )
        for pkg in self.getPkgsFromList( rmvlist ):
            pkg.queued = None
            pkg.set_select( not pkg.selected )
        f = lambda x: str( x ) not in rmvlist
        for action in ['u', 'i', 'r','rr']:
            list = self.queue.get(action)
            if list:
                self.queue.packages[action] = filter( f, list )
        self.refresh()

    def getPkgsFromList( self, rlist ):
        rclist = []
        f = lambda x: str( x ) in rlist
        for action in ['u', 'i', 'r','rr']:
            list = self.queue.packages[action]
            if list:
                rclist += filter( f, list )
        return rclist

    def refresh ( self ):
        """ Populate view with data from queue """
        self.model.clear()
        label = _( "<b>Packages To Reinstall</b>" )
        list = self.queue.packages['rr']
        if len( list ) > 0:
            self.populate_list( label, list )
        label = _( "<b>Packages To Update</b>" )
        list = self.queue.packages['u']
        if len( list ) > 0:
            self.populate_list( label, list )
        label = _( "<b>Packages To Install</b>" )
        list = self.queue.packages['i']
        if len( list ) > 0:
            self.populate_list( label, list )
        label = _( "<b>Packages To Remove</b>" )
        list = self.queue.packages['r']
        if len( list ) > 0:
            self.populate_list( label, list )
        self.view.expand_all()

    def populate_list( self, label, list ):
        parent = self.model.append( None, [label, ""] )
        for pkg in list:
            self.model.append( parent, [str( pkg ), pkg.description] )

class EntropyFilesView:
    """ Queue View Class"""
    def __init__( self, widget ):
        self.view = widget
        self.model = self.setup_view()

    def setup_view( self ):
        """ Create Notebook list for single page  """
        model = gtk.TreeStore( gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING )
        self.view.set_model( model )

        cell0 = gtk.CellRendererText()
        column0 = gtk.TreeViewColumn( "", cell0, markup = 0 )
        column0.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column0.set_fixed_width( 2 )
        self.view.append_column( column0 )

        cell1 = gtk.CellRendererText()
        column1 = gtk.TreeViewColumn( _( "Proposed" ), cell1, markup = 1 )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( 250 )
        column1.set_resizable( True )
        self.view.append_column( column1 )

        cell2 = gtk.CellRendererText()
        column2 = gtk.TreeViewColumn( _( "Destination" ), cell2, markup = 2 )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 300 )
        column2.set_resizable( True )
        self.view.append_column( column2 )

        cell3 = gtk.CellRendererText()
        column3 = gtk.TreeViewColumn( _( "Rev." ), cell3, text=3 )
        column3.set_resizable( True )
        column3.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column3.set_fixed_width( 30 )
        self.view.append_column( column3 )
        model.set_sort_column_id( 0, gtk.SORT_ASCENDING )
        self.view.get_selection().set_mode( gtk.SELECTION_SINGLE )
        return model

    def populate( self, scandata ):
        self.model.clear()
        keys = scandata.keys()
        keys.sort()
        for key in keys:
            self.model.append(None,[
                                        key,
                                        os.path.basename(scandata[key]['source']),
                                        scandata[key]['destination'],
                                        scandata[key]['revision']
                                    ]
            )

class CategoriesView:
    def __init__( self, treeview,qview):
        self.view = treeview
        self.model = self.setup_view()
        self.queue = qview.queue
        self.queueView = qview
        self.etpbase = None # it will se set later
        self.currentCategory = None
        self.icon_theme = gtk.icon_theme_get_default()


    def setup_view( self ):
        """ Setup Group View  """
        model = gtk.TreeStore(gobject.TYPE_BOOLEAN, # Installed
                              gobject.TYPE_STRING,  # Group Name
                              gobject.TYPE_STRING,  # Group Id
                              gobject.TYPE_BOOLEAN, # In queue
                              gobject.TYPE_BOOLEAN) # isCategory


        self.view.set_model( model )
        column = gtk.TreeViewColumn(None, None)
        # Selection checkbox
        selection = gtk.CellRendererToggle()    # Selection
        selection.set_property( 'activatable', True )
        column.pack_start(selection, False)
        column.set_cell_data_func( selection, self.setCheckbox )
        selection.connect( "toggled", self.on_toggled )
        self.view.append_column( column )

        column = gtk.TreeViewColumn(None, None)
        # Queue Status (install/remove group)
        state = gtk.CellRendererPixbuf()    # Queue Status
        state.set_property('stock-size', 1)
        column.pack_start(state, False)
        column.set_cell_data_func( state, self.queue_pixbuf )

        # category/group icons 
        icon = gtk.CellRendererPixbuf()
        icon.set_property('stock-size', 1)
        column.pack_start(icon, False)
        column.set_cell_data_func( icon, self.grp_pixbuf )

        category = gtk.CellRendererText()
        column.pack_start(category, False)
        column.add_attribute(category, 'markup', 1)

        self.view.append_column( column )
        self.view.set_headers_visible(False)
        return model

    def setCheckbox( self, column, cell, model, iter ):
        isCategory = model.get_value( iter, 4 )
        state = model.get_value( iter, 0 )
        if isCategory:
            cell.set_property( 'visible', False)
        else:
            cell.set_property( 'visible', True)
            cell.set_property('active',state)

    def on_toggled( self, widget, path ):
        """ Group selection handler """
        iter = self.model.get_iter( path )
        grpid = self.model.get_value( iter, 2 )
        inst = self.model.get_value( iter, 0 )
        action = self.queue.hasGroup(grpid)
        if action:
            self.queue.removeGroup(grpid,action)
            self._updatePackages(grpid,False,None)
            self.model.set_value( iter, 3,False )
        else:
            if inst:
                self.queue.addGroup(grpid,'r') # Add for remove
                self._updatePackages(grpid,True,'r')
            else:
                self.queue.addGroup(grpid,'i') # Add for install
                self._updatePackages(grpid,True,'i')
            self.model.set_value( iter, 3,True )
        self.model.set_value( iter, 0, not inst )


    def _updatePackages(self,id,add,action):
        grp = self.etpbase.comps.return_group(id)
        pkgs = self.etpbase._getByGroup(grp,['m','d'])
        # Add group packages to queue
        if add: 
            for po in pkgs:
                if not po.queued: 
                    if action == 'i' and po.available : # Install
                            po.queued = po.action
                            self.queue.add(po)
                            po.set_select( True )
                    elif action == 'r' and not po.available: # Remove
                            po.queued = po.action 
                            self.queue.add(po)
                            po.set_select( False )
        # Remove group packages from queue
        else:
            for po in pkgs:
                if po.queued:
                    po.queued = None
                    self.queue.remove(po)
                    po.set_select( not po.selected )
        self.queueView.refresh()

    def populate(self,data):
        self.model.clear()
        for cat in data:
            self.model.append(None,[None,cat,cat,False,True])

    def queue_pixbuf( self, column, cell, model, iter ):
        """ 
        Cell Data function for recent Column, shows pixmap
        if recent Value is True.
        """
        grpid = model.get_value( iter, 2 )
        queued = model.get_value( iter, 3 )
        action = self.queue.hasGroup(grpid)
        if action:            
            if action ==  'i':
                icon = 'network-server'
            else:
                icon = 'edit-delete'                
            cell.set_property( 'visible', True )
            cell.set_property( 'icon-name', icon )
        cell.set_property( 'visible', queued )

    def grp_pixbuf( self, column, cell, model, iter ):
        """ 
        Cell Data function for recent Column, shows pixmap
        if recent Value is True.
        """
        grpid = model.get_value( iter, 2 )
        pix = None
        fn = "/usr/share/pixmaps/comps/%s.png" % grpid
        if os.access(fn, os.R_OK):
            pix = self._get_pix(fn)
        if pix:
            cell.set_property( 'visible', True )
            cell.set_property( 'pixbuf', pix )
        else:
            cell.set_property( 'visible', False )


    def _get_pix(self, fn):
        imgsize = 24
        pix = gtk.gdk.pixbuf_new_from_file(fn)
        if pix.get_height() != imgsize or pix.get_width() != imgsize:
            pix = pix.scale_simple(imgsize, imgsize,
                                   gtk.gdk.INTERP_BILINEAR)
        return pix


class EntropyRepoView:
    """ 
    This class controls the repo TreeView
    """
    def __init__( self, widget, EquoConnection, ui):
        self.view = widget
        self.headers = [_('Repository'),_('Filename')]
        self.store = self.setup_view()
        self.Equo = EquoConnection
        self.ui = ui
        import dialogs
        self.okDialog = dialogs.okDialog

    def on_active_toggled( self, widget, path):
        """ Repo select/unselect handler """
        iter = self.store.get_iter( path )
        state = self.store.get_value(iter,0)
        repoid = self.store.get_value(iter,3)
        if repoid != etpConst['officialrepositoryid']:
            if state:
                self.store.set_value(iter,1, not state)
                self.Equo.disableRepository(repoid)
                initConfig_entropyConstants(etpSys['rootdir'])
            else:
                self.Equo.enableRepository(repoid)
                initConfig_entropyConstants(etpSys['rootdir'])
            self.okDialog(self.ui.main,_("You should press the %s button now") % (_("Regenerate Cache")))
            self.store.set_value(iter,0, not state)

    def on_update_toggled( self, widget, path):
        """ Repo select/unselect handler """
        iter = self.store.get_iter( path )
        state = self.store.get_value(iter,1)
        active = self.store.get_value(iter,0)
        if active:
            self.store.set_value(iter,1, not state)

    def setup_view( self ):
        """ Create models and columns for the Repo TextView  """
        store = gtk.ListStore( 'gboolean', 'gboolean', gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.view.set_model( store )

        # Setup Selection Column
        cell1 = gtk.CellRendererToggle()    # Selection
        cell1.set_property( 'activatable', True )
        column1 = gtk.TreeViewColumn( _("Active"), cell1 )
        column1.add_attribute( cell1, "active", 0 )
        column1.set_resizable( True )
        column1.set_sort_column_id( -1 )
        self.view.append_column( column1 )
        cell1.connect( "toggled", self.on_active_toggled )

        # Setup Selection Column
        cell2 = gtk.CellRendererToggle()    # Selection
        cell2.set_property( 'activatable', True )
        column2 = gtk.TreeViewColumn( _("Update"), cell2 )
        column2.add_attribute( cell2, "active", 1 )
        column2.set_resizable( True )
        column2.set_sort_column_id( -1 )
        self.view.append_column( column2 )
        cell2.connect( "toggled", self.on_update_toggled )

        # Setup revision column
        self.create_text_column( _('Revision'),2 )

        # Setup reponame & repofile column's
        self.create_text_column( _('Repository Identifier'),3 )
        self.create_text_column( _('Description'),4 )
        self.view.set_search_column( 1 )
        self.view.set_reorderable( False )
        return store

    def create_text_column( self, hdr,colno):
        cell = gtk.CellRendererText()    # Size Column
        column = gtk.TreeViewColumn( hdr, cell, text=colno )
        column.set_resizable( True )
        self.view.append_column( column )

    def populate(self):
        self.store.clear()
        """ Populate a repo liststore with data """
        first = 0
        for repo in etpRepositoriesOrder:
            repodata = etpRepositories[repo]
            self.store.append([1,1,repodata['dbrevision'],repo,repodata['description']])
            first = 1
        # excluded ones
        for repo in etpRepositoriesExcluded:
            repodata = etpRepositoriesExcluded[repo]
            self.store.append([0,0,repodata['dbrevision'],repo,repodata['description']])
            first = 1

    def new_pixbuf( self, column, cell, model, iter ):
        gpg = model.get_value( iter, 3 )
        if gpg:
            cell.set_property( 'visible', True )
        else:
            cell.set_property( 'visible',False)

    def get_selected( self ):
        selected = []
        for elem in self.store:
            state = elem[0]
            selection = elem[1]
            name = elem[3]
            if state and selection:
                selected.append( name )
        return selected

    def get_notselected( self ):
        notselected = []
        for elem in self.store:
            state = elem[0]
            name = elem[1]
            if not state:
                notselected.append( name )
        return notselected

    def deselect_all( self ):
        iterator = self.store.get_iter_first()
        while iterator != None:
            self.store.set_value( iterator, 0, False )
            iterator = self.store.iter_next( iterator )

    def select_all( self ):
        iterator = self.store.get_iter_first()
        while iterator != None:
            self.store.set_value( iterator, 0, True )
            iterator = self.store.iter_next( iterator )

    def get_repoid(self, iterdata):
        model, iter = iterdata
        return model.get_value( iter, 3 )

    def select_by_keys( self, keys):
        iterator = self.store.get_iter_first()
        while iterator != None:
            repoid = self.store.get_value( iterator, 1 )
            if repoid in keys:
                self.store.set_value( iterator, 0, True )
            else:
                self.store.set_value( iterator, 0, False)
            iterator = self.store.iter_next( iterator )

class EntropyRepositoryMirrorsView:
    """ 
    This class controls the repo TreeView
    """
    def __init__( self, widget):
        self.view = widget
        self.headers = [""]
        self.store = self.setup_view()

    def setup_view( self ):
        """ Create models and columns for the Repo TextView  """
        store = gtk.ListStore(str)
        self.view.set_model( store )

        # Setup Repository URL column
        self.create_text_column( "", 0 )

        # Setup reponame & repofile column's
        self.view.set_search_column( 1 )
        self.view.set_reorderable( False )
        return store

    def create_text_column( self, hdr, colno):
        cell = gtk.CellRendererText()    # Size Column
        column = gtk.TreeViewColumn( hdr, cell, text=colno )
        column.set_resizable( True )
        self.view.append_column( column )

    def populate(self):
        """ Populate a repo liststore with data """
        self.store.clear()

    def get_selected( self ):
        selected = []
        for elem in self.store:
            name = elem[0]
            if name:
                selected.append( name )
        return selected

    def get_all( self ):
        all = [x[0] for x in self.store]
        return all

    def add(self, url):
        self.store.append([str(url)])

    def remove_selected(self):
        urls = self.get_selected()
        self.remove(urls)

    def get_text(self, urldata):
        model, iter = urldata
        return model.get_value( iter, 0 )

    def remove(self, urldata):
        model, iter = urldata
        self.store.remove(iter)
