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
import sys,os
import ConfigParser

from i18n import _


class YumexCategoryView:
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
    

class YumexPackageView:
    def __init__( self, treeview,qview ):
        self.view = treeview
        self.headers = [_( "Package" ), _( "Ver" ), _( "Summary" ), _( "Repo" ), _( "Architecture" ), _( "Size" )]
        self.store = self.setupView()
        self.queue = qview.queue
        self.queueView = qview
        
    def setupView( self ):
        store = gtk.ListStore( gobject.TYPE_PYOBJECT,str)
        self.view.set_model( store )
        # Setup selection column
        cell1 = gtk.CellRendererToggle()    # Selection
        cell1.set_property( 'activatable', True )
        column1 = gtk.TreeViewColumn( "", cell1 )
        column1.set_cell_data_func( cell1, self.get_data_bool, 'selected' )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( 20 )
        column1.set_sort_column_id( -1 )            
        self.view.append_column( column1 )
        cell1.connect( "toggled", self.on_toggled )            
        column1.set_clickable( True )
        # Setup resent column
        cell2 = gtk.CellRendererPixbuf()    # new
        cell2.set_property( 'stock-id', gtk.STOCK_ADD )
        column2 = gtk.TreeViewColumn( "", cell2 )
        column2.set_cell_data_func( cell2, self.new_pixbuf )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 20 )
        column2.set_sort_column_id( -1 )            
        self.view.append_column( column2 )
        column2.set_clickable( True )

        self.create_text_column( _( "Package" ), 'name' , size=240)
        self.create_text_column( _( "Arch." ), 'arch' , size = 50 )
        self.create_text_column( _( "Ver." ), 'ver', size = 100 )
        self.create_text_column( _( "Summary" ), 'summaryFirst', size=400 )
        self.create_text_column( _( "Repo." ), 'repoid' , size=100 )
        self.create_text_column( _( "Size." ), 'sizeFmt' , size=100 )
        self.view.set_search_column( 1 )
        self.view.set_enable_search(True)
        #store.set_sort_column_id(1, gtk.SORT_ASCENDING)
        self.view.set_reorderable( False )
        return store
   
    def create_text_column( self, hdr, property, size,sortcol = None):
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
        
    def get_data_text( self, column, cell, model, iter,property ):
        obj = model.get_value( iter, 0 )
        if obj:
            cell.set_property( 'text', getattr( obj, property ) )
            cell.set_property('foreground',obj.color)

    def get_data_bool( self, column, cell, model, iter, property ):
        obj = model.get_value( iter, 0 )
        cell.set_property( "visible", True )
        if obj:
            cell.set_property( "active", getattr( obj, property ) )
    
    def on_toggled( self, widget, path ):
        """ Package selection handler """
        iter = self.store.get_iter( path )
        obj = self.store.get_value( iter, 0 )
        self.togglePackage(obj)
        self.queueView.refresh()
        
    def togglePackage(self,obj):
        if obj.queued == obj.action:
            obj.queued = None
            self.queue.remove(obj)
        else:
           obj.queued = obj.action      
           self.queue.add(obj)
        obj.set_select( not obj.selected )
        
                
    def selectAll(self):
        for el in self.store:
            obj = el[0]
            if not obj.queued == obj.action:
                obj.queued = obj.action      
                self.queue.add(obj)
                obj.set_select( not obj.selected )
        self.queueView.refresh()
        self.view.queue_draw() 

    def deselectAll(self):
        for el in self.store:
            obj = el[0]
            if obj.queued == obj.action:
                obj.queued = None
                self.queue.remove(obj)
                obj.set_select( not obj.selected )
        self.queueView.refresh()
        self.view.queue_draw() 

    def new_pixbuf( self, column, cell, model, iter ):
        """ 
        Cell Data function for recent Column, shows pixmap
        if recent Value is True.
        """
        pkg = model.get_value( iter, 0 )
        if pkg:
            action = pkg.queued
            if action:            
                if action in ( 'u', 'i' ):
                    icon = 'network-server'
                else:
                    icon = 'edit-delete'
                cell.set_property( 'visible', True )
                cell.set_property( 'icon-name', icon )
            else:
                cell.set_property( 'visible', pkg.recent )
                cell.set_property( 'icon-name', 'document-new' )
        else:
            cell.set_property( 'visible', False )
            

    def get_selected( self, package=True ):
        """ Get selected packages in current packageList """
        selected = []
        for row in self.store:
            col = row[0]
            if col:
                pkg = row[0][0]
                if pkg.selected:
                    selected.append( pkg )
        return selected

        
class YumexQueueView:
    """ Queue View Class"""
    def __init__( self, widget,queue ):
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
        column2= gtk.TreeViewColumn( _( "Summary" ), cell2, text=1 )
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
        for action in ['u', 'i', 'r']:
            list = self.queue.get(action)
            if list:
                self.queue.packages[action] = filter( f, list )
        self.refresh()


    def getPkgsFromList( self, rlist ):
        rclist = []
        f = lambda x: str( x ) in rlist
        for action in ['u', 'i', 'r']:
            list = self.queue.packages[action]
            if list:
                rclist += filter( f, list )
        return rclist
        
    def refresh ( self ):
        """ Populate view with data from queue """
        self.model.clear()
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
            self.model.append( parent, [str( pkg ), pkg.summaryFirst] )
            

class YumexCompsView:
    def __init__( self, treeview,qview):
        self.view = treeview
        self.model = self.setup_view()
        self.queue = qview.queue
        self.queueView = qview
        self.yumbase = None # it will se set later 
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
        grp = self.yumbase.comps.return_group(id)
        pkgs = self.yumbase._getByGroup(grp,['m','d'])
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
        for cat,grps in data:
            cName,cId = cat
            node = self.model.append(None,[None,cName,cId,False,True])          
            for grp in grps:
                (gName,gId,gInst) = grp
                self.model.append(node,[gInst,gName,gId,False,False])
            
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
        
        
class YumexRepoView:
    """ 
    This class controls the repo TreeView
    """
    def __init__( self, widget):
        self.view = widget
        self.headers = [_('Repository'),_('Filename')]
        self.store = self.setup_view()
    
    
    def on_toggled( self, widget, path):
        """ Repo select/unselect handler """
        iter = self.store.get_iter( path )
        state = self.store.get_value(iter,0)
        self.store.set_value(iter,0, not state)
                     
    def setup_view( self ):
        """ Create models and columns for the Repo TextView  """
        store = gtk.ListStore( 'gboolean', gobject.TYPE_STRING,gobject.TYPE_STRING,'gboolean')
        self.view.set_model( store )
        # Setup Selection Column
        cell1 = gtk.CellRendererToggle()    # Selection
        cell1.set_property( 'activatable', True )
        column1 = gtk.TreeViewColumn( "    ", cell1 )
        column1.add_attribute( cell1, "active", 0 )
        column1.set_resizable( True )
        column1.set_sort_column_id( -1 )            
        self.view.append_column( column1 )
        cell1.connect( "toggled", self.on_toggled )     
        # Setup resent column
        cell2 = gtk.CellRendererPixbuf()    # gpgcheck
        cell2.set_property( 'stock-id', gtk.STOCK_DIALOG_AUTHENTICATION )
        column2 = gtk.TreeViewColumn( "", cell2 )
        column2.set_cell_data_func( cell2, self.new_pixbuf )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 20 )
        column2.set_sort_column_id( -1 )            
        self.view.append_column( column2 )
        column2.set_clickable( True )
               
        # Setup reponame & repofile column's
        self.create_text_column( _('Repository'),1 )
        self.create_text_column( _('Name'),2 )
        self.view.set_search_column( 1 )
        self.view.set_reorderable( False )
        return store
    
    def create_text_column( self, hdr,colno):
        cell = gtk.CellRendererText()    # Size Column
        column = gtk.TreeViewColumn( hdr, cell, text=colno )
        column.set_resizable( True )
        self.view.append_column( column )        

    def populate( self, data ):
        """ Populate a repo liststore with data """
        self.store.clear()
        for state,id,name,gpg in data:
            self.store.append([state,id,name,gpg])           

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
            name = elem[1]
            if state:
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
            

    def select_by_keys( self, keys):
        self.store 
        iterator = self.store.get_iter_first()
        while iterator != None:    
            repoid = self.store.get_value( iterator, 1 )
            if repoid in keys:
                self.store.set_value( iterator, 0, True )
            else:
                self.store.set_value( iterator, 0, False)
            iterator = self.store.iter_next( iterator )
        
class YumexPluginView:
    def __init__( self, widget ):
        self.view = widget
        self.model = self.setup_view()
        self.plugins = self.load()
        self.populate_view()
    
    def on_toggled( self, cell, path, model ):
        newstate = not model[path][0]
        model[path][0] = newstate
        conf = model[path][2]
        if newstate:
            val = '1'
        else:
            val = '0'
        conf.set( 'main', 'enabled', val )
        return

    def setup_view( self ):
        """ Create Notebook list for single page  """
        model = gtk.ListStore( 'gboolean', gobject.TYPE_STRING, gobject.TYPE_PYOBJECT )
        self.view.set_model( model )
        # Setup Selection Column
        cell1 = gtk.CellRendererToggle()    # Selection
        cell1.set_property( 'activatable', True )
        column1 = gtk.TreeViewColumn( "    ", cell1 )
        column1.add_attribute( cell1, "active", 0 )
        column1.set_resizable( True )
        self.view.append_column( column1 )
        cell1.connect( "toggled", self.on_toggled, model )             
        cell2 = gtk.CellRendererText()
        column2= gtk.TreeViewColumn( _( "Plugin" ), cell2, text=1 )
        column2.set_resizable( True )
        self.view.append_column( column2 )
        return model
    
    def populate_view( self ):
        self.model.clear()
        keys = self.plugins.keys()
        for key in keys:
            if conf.has_section('main'):
                conf = self.plugins[key]
                state = conf.get( 'main', 'enabled' ) == '1'
                el = [state, key, conf]
                self.model.append( el )
        
    def dump( self ):
        for row in self.model:
            print "--> %s is %s" % ( row[1], row[0] )
            
    def load( self ):
        """ Create a dict with parsers to available plugings"""
        dict = {}
        for modulefile in glob.glob( '/etc/yum/pluginconf.d/*.conf' ):
            dir, modname = os.path.split( modulefile )
            modname = modname.split( '.conf' )[0]
            try:
                parser = ConfigParser.ConfigParser()
                parser.read( modulefile )
                dict[modname] = parser
            except:
                print "Error loading : %s" % modulefile
                
        return dict
        
            
    def save( self ):
        """ Write plugins configs back to disk """
        for row in self.model:
            fp = open( "/etc/yum/pluginconf.d/%s.conf" % row[1], "wt" )
            row[2].write( fp )
            fp.close()
