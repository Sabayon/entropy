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
import pango

# Use iniparse if it exist, else use Python ConfigParser
try:
    from iniparse.compat import ConfigParser,SafeConfigParser
except:
    from ConfigParser import ConfigParser,SafeConfigParser


from misc import const,cleanMarkupSting,YumexConf
from views import YumexPluginView
from i18n import _

class Preferences:
    def __init__( self):
        self.xml = gtk.glade.XML( const.GLADE_FILE, root="pref",domain="yumex")
        self.conf = self.read_yumex_conf()
        self.setup_gui()
        gtk.main()
                     
    def read_yumex_conf( self,configfile='/etc/yumex.conf', sec='yumex' ):
        conf = YumexConf()
        parser = ConfigParser()    
        parser.read( configfile )
        conf.populate( parser, sec )
        return conf
    

    def setup_gui( self ):
        self.win = self.xml.get_widget( 'pref' )
        self.win.connect( "destroy", self.quit )
        self.win.connect( "delete_event", self.quit )
        self.bOK = self.xml.get_widget( "prefOK" )
        self.bOK.connect( "clicked", self.click, "OK" )
        self.bCancel = self.xml.get_widget( "prefCancel" )
        self.bCancel.connect( "clicked", self.click, "CANCEL" )

        self.fontConsole = self.xml.get_widget( "fontConsole" )
        self.fontConsole.set_font_name( self.conf.font_console )
        self.colorConsole = self.xml.get_widget( "colorConsole" )

        color = gtk.gdk.color_parse( self.conf.color_console )
        self.colorConsole.set_color( color )

        self.fontPkgDesc = self.xml.get_widget( "fontPkgDesc" )
        self.fontPkgDesc.set_font_name( self.conf.font_pkgdesc )
        
        self.colorPkgDesc = self.xml.get_widget( "colorPkgDesc" )
        color = gtk.gdk.color_parse( self.conf.color_pkgdesc )
        self.colorPkgDesc.set_color( color )
        
        self.autoRefresh = self.xml.get_widget( "prefAutoRefresh" )
        self.autoRefresh.set_active( self.conf.autorefresh )
        self.debugMode = self.xml.get_widget( "prefDebug" )
        self.debugMode.set_active( self.conf.debug )
        self.excList = self.xml.get_widget( "excView" )
        self.excBuffer = self.excList.get_buffer()
        self.get_excludes()
        self.pluginView = YumexPluginView( self.xml.get_widget( "prefPluginView" ) )
        self.repoExclude = self.xml.get_widget( "prefRepoExclude" )
        ex = ",".join(self.conf.repo_exclude)
        self.repoExclude.set_text(ex)
        self.proxy = self.xml.get_widget( "prefProxy" )
        self.proxy.connect( "toggled", self.on_proxy )
        self.proxySrv = self.xml.get_widget( "prefProxySrv" )
        self.proxyBox = self.xml.get_widget( "prefProxyBox" )
        proxy = self.conf.proxy
        if proxy:
            self.proxyBox.show_all()
            self.proxy.set_active( True )
            self.proxySrv.set_text( proxy )
        else:
            self.proxyBox.hide_all()
            self.proxy.set_active( False )
            self.proxySrv.set_text( "" )
            
        self.win.show() 

    def get_excludes( self ):
        for ex in self.conf.exclude:
            self.addline( ex )
                    
    def set_excludes( self ):
        self.conf.exclude = self.get_lines()
        
    def get_lines( self ):
        start = self.excBuffer.get_start_iter()
        end = self.excBuffer.get_end_iter()
        txt = self.excBuffer.get_text( start, end )
        return txt.split( '\n' )
            
    def addline( self, txt ):
        end = self.excBuffer.get_end_iter()
        self.excBuffer.insert( end, "%s\n" % txt )
        
        
    def on_proxy( self, widget ):        
        if self.proxy.get_active():
            self.proxyBox.show_all()
        else:
            self.proxyBox.hide_all()
            
        
        
    
    def update_conf( self ):
        self.conf.autorefresh = self.autoRefresh.get_active() 
        self.conf.debug = self.debugMode.get_active()
        #self.conf.nolauncher = self.noLauncher.get_active() 
        self.conf.font_console = self.fontConsole.get_font_name()
        self.conf.font_pkgdesc = self.fontPkgDesc.get_font_name()
        self.conf.color_console = gtk.color_selection_palette_to_string( [self.colorConsole.get_color()] )
        self.conf.color_pkgdesc = gtk.color_selection_palette_to_string( [self.colorPkgDesc.get_color()] )
        ex = self.repoExclude.get_text()
        self.conf.repo_exclude = ex.split(',')
        self.set_excludes()
        if self.proxy.get_active():
            proxy = self.proxySrv.get_text()
            self.conf.proxy = proxy
        else:
            self.conf.proxy = ""
            

        
    def save( self ):       
        self.conf.write( open( '/etc/yumex.conf', "wt" ) )
        self.pluginView.save()

    def quit( self, w=None, event=None ):
        self.win.hide()
        self.win.destroy()
        gtk.main_quit()

    def click( self, button, key ):
        if key == "OK":
            self.update_conf()
            self.save()
            self.quit()
        elif key == "CANCEL":
            self.quit()
        elif key == "PROXY":
            self.proxyState = self.useProxy.get_active()
            if self.proxyState:
                self.boxProxy.show()     
            else:
                self.boxProxy.hide()     
            
    def font_click( self, button, event, key ):
        if event.button == 3: # Right Click
            if key == "FONT_CONSOLE":
                self.fontConsole.get_text()
                fd = FontDialog( "Select Console Font", self.fontConsole.get_text() )
                fd.run()
                if fd.font:
                    pangoFont = pango.FontDescription( fd.font )
                    self.fontConsole.modify_font( pangoFont )                    
                    self.fontConsole.set_text( fd.font )
                fd.destroy()
            elif key == "FONT_PKGDESC":
                fd = FontDialog( "Select Console Font", self.fontPkgDesc.get_text() )
                fd.run()
                if fd.font:
                    pangoFont = pango.FontDescription( fd.font )
                    self.fontPkgDesc.modify_font( pangoFont )                    
                    self.fontPkgDesc.set_text( fd.font )
                fd.destroy()


class ConfimationDialog:
    def __init__( self, parent, pkgs, size ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, 'confirmation',domain="yumex" )
        self.dialog = self.xml.get_widget( "confirmation" )
        self.dialog.set_transient_for( parent )
        self.action = self.xml.get_widget( "confAction" )
        tit = "<span size='x-large'>%s</span>" % _("Packages to Process")
        self.action.set_markup( tit )
        self.pkg = self.xml.get_widget( "confPkg" )
        self.pkgModel = self.setup_view( self.pkg )
        self.show_data( self.pkgModel, pkgs )
        self.size = self.xml.get_widget( "confSize" )
        self.size.set_text( str( size ) )
        self.pkg.expand_all()

    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()
             
    def setup_view( self, view ):
        model = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING )
        view.set_model( model )
        self.create_text_column( _( "Name" ), view, 0 )
        self.create_text_column( _( "Arch" ), view, 1 )
        self.create_text_column( _( "Ver" ), view, 2 )
        self.create_text_column( _( "Repository" ), view, 3 )
        self.create_text_column( _( "Size" ), view, 4 )
        return model

    def create_text_column( self, hdr, view, colno, min_width=0 ):
         cell = gtk.CellRendererText()    # Size Column
         column = gtk.TreeViewColumn( hdr, cell, markup=colno )
         column.set_resizable( True )
         if not min_width == 0:
             column.set_min_width( min_width )
         view.append_column( column )        
             
             
    def show_data( self, model, pkglist ):
        model.clear()       
        for sub, lvl1 in pkglist:
            label = "<b>%s</b>" % sub
            level1 = model.append( None, [label, "", "", "", ""] )
            for name, arch, ver, repo, size, replaces in lvl1:
                level2 = model.append( level1, [name, arch, ver, repo, size] )
                for r in replaces:
                    level3 = model.append( level2, [ r, "", "", "", ""] )

    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()

    def destroy( self ):
        return self.dialog.destroy()
        
class ErrorDialog:
    def __init__( self, parent, title, text, longtext, modal ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "errDialog",domain="yumex" )
        self.dialog = self.xml.get_widget( "errDialog" )
        self.parent = parent
        if parent:
            self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "errText" )
        self.longtext = self.xml.get_widget( "errTextView" )
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
        buffer = self.longtext.get_buffer()
        start, end = buffer.get_bounds()
        buffer.insert_with_tags( end, longtext, self.style_err )
        
    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()

    def destroy( self ):
        return self.dialog.destroy()  

class infoDialog:
    def __init__( self, parent, title, text ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "msg",domain="yumex" )
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
        self.xml = gtk.glade.XML( const.GLADE_FILE, "EntryDialog",domain="yumex" )
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

    def __init__(self, gfx,creditText,title="Yum Extender"):

        self.__is_stopped = True
        self.__scroller_values = ()
  

        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_resizable(False)
        self.set_title(_("About %s") % title)
        self.connect("button-press-event", self.__on_close)
        self.connect("key-press-event", self.__on_close)
        self.connect("delete-event", self.__on_close)
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)

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

        credits = gtk.Label(text)
        credits.set_use_markup(True)
        credits.set_justify(gtk.JUSTIFY_CENTER)

        lbl_width, lbl_height = credits.size_request()
        scroller.put(credits, (width - lbl_width) / 2, height)

        self.__scroller = scroller
        self.__credits = credits

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


                 
def inputBox( parent, title, text):
    dlg = EntryDialog( parent, title, text)
    rc = dlg.run()
    dlg.destroy()
    return rc

def errorMessage( parent, title, text, longtext=None, modal= True ):
     dlg = ErrorDialog( parent, title, text, longtext, modal )
     dlg.run()
     dlg.destroy()

def infoMessage( parent, title, text ):
    dlg = infoDialog( parent, title, text )
    rc = dlg.run()
    dlg.destroy()
    return not rc == gtk.RESPONSE_OK

def questionDialog(parent, msg):
    dlg = gtk.MessageDialog(parent=parent,
                            type=gtk.MESSAGE_QUESTION,
                            buttons=gtk.BUTTONS_YES_NO)
    dlg.set_markup(cleanMarkupSting(msg))
    rc = dlg.run()
    dlg.destroy()
    if rc == gtk.RESPONSE_YES:
        return True
    else:
        return False
        
def okDialog(parent, msg):
    dlg = gtk.MessageDialog(parent=parent,
                            type=gtk.MESSAGE_INFO,
                            buttons=gtk.BUTTONS_OK)
    dlg.set_markup(cleanMarkupSting(msg))
    rc = dlg.run()
    dlg.destroy()
    
