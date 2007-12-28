#!/usr/bin/python -tt
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# Authors:
#    Tim Lauridsen <tla@rasmil.dk>

import gtk.glade
import pango
import yumgui
import gobject
import types

class TextViewConsole:
    '''  Encapsulate a gtk.TextView'''
    def __init__(self,textview,default_style=None,font=None,color=None):
        self.textview = textview
        self.buffer = self.textview.get_buffer()
        self.endMark = self.buffer.create_mark( "End", self.buffer.get_end_iter(), False )
        self.startMark = self.buffer.create_mark( "Start", self.buffer.get_start_iter(), False )
        #setup styles.
        self.style_banner = gtk.TextTag( "banner" )
        self.style_banner.set_property( "foreground", "saddle brown" )
        self.style_banner.set_property( "family", "Monospace" )
        self.style_banner.set_property( "size_points", 8 )
        
            
        self.style_ps1 = gtk.TextTag( "ps1" )
        self.style_ps1.set_property( "editable", False )
        if color:
            self.style_ps1.set_property( "foreground", color )
        else:
            self.style_ps1.set_property( "foreground", "DarkOrchid4" )
        if font:
            self.style_ps1.set_property( "font", font)
        else:
            self.style_ps1.set_property( "family", "Monospace" )
            self.style_ps1.set_property( "size_points", 8 )

        self.style_ps2 = gtk.TextTag( "ps2" )
        self.style_ps2.set_property( "foreground", "DarkOliveGreen" )
        self.style_ps2.set_property( "editable", False )
        self.style_ps2.set_property( "font", "courier" )

        self.style_out = gtk.TextTag( "stdout" )
        self.style_out.set_property( "foreground", "midnight blue" )
        self.style_out.set_property( "family", "Monospace" )
        self.style_out.set_property( "size_points", 8)


        self.style_err = gtk.TextTag( "stderr" ) 
        self.style_err.set_property( "style", pango.STYLE_ITALIC )
        self.style_err.set_property( "foreground", "red" )
        if font:
            self.style_err.set_property( "font", font)
        else:
            self.style_err.set_property( "family", "Monospace" )
            self.style_err.set_property( "size_points", 8 )

        self.buffer.get_tag_table().add( self.style_banner )
        self.buffer.get_tag_table().add( self.style_ps1 )
        self.buffer.get_tag_table().add( self.style_ps2 )
        self.buffer.get_tag_table().add( self.style_out )
        self.buffer.get_tag_table().add( self.style_err )
        
        if default_style:
            self.default_style=default_style
        else:
            self.default_style=self.style_ps1
    
    def changeStyle(self,color,font,style=None):
        if not style:
            self.default_style.set_property( "foreground", color )
            self.default_style.set_property( "font", font )
        else:
            style.set_property( "foreground", color )
            style.set_property( "font", font )
    
    def write_line( self, txt, style=None):
        """ write a line to button of textview and scoll to end
        @param txt: Text to write to textview
        @param style: Predefinded pango style to use. 
        """
        #txt = gobject.markup_escape_text(txt)
        txt = self._toUTF(txt)
        start, end = self.buffer.get_bounds()
        if style == None:
            self.buffer.insert_with_tags( end, txt, self.default_style )
        else:
            self.buffer.insert_with_tags( end, txt, style )
        self.textview.scroll_to_iter( self.buffer.get_end_iter(), 0.0 )

    def _toUTF( self, txt ):
        rc=""
        if isinstance(txt,types.UnicodeType):
            return txt
        else:
            try:
                rc = unicode( txt, 'utf-8' )
            except UnicodeDecodeError, e:
                rc = unicode( txt, 'iso-8859-1' )
            return rc
            

    def clear(self):
        self.buffer.set_text('')
        
    def goTop(self):
        self.textview.scroll_to_iter( self.buffer.get_start_iter(), 0.0 )
        
    

#        
# These classes come from the article
# http://www.linuxjournal.com/article/4702
#
# They have been modified a little to support domain
#       
        
class UI(gtk.glade.XML):
    """Base class for UIs loaded from glade."""
    
    def __init__(self, filename, rootname,domain=None):
        """Initialize a new instance.
        `filename' is the name of the .glade file containing the UI hierarchy.
        `rootname' is the name of the topmost widget to be loaded.
        `gladeDir' is the name of the directory, relative to the Python
        path, in which to search for `filename'."""
        if domain:
            gtk.glade.XML.__init__(self, filename, rootname, domain)
        else:
            gtk.glade.XML.__init__(self, filename, rootname)
        self.filename = filename
        self.root = self.get_widget(rootname)

    def __getattr__(self, name):
        """Look up an as-yet undefined attribute, assuming it's a widget."""
        result = self.get_widget(name)
        if result is None:
            raise AttributeError("Can't find widget %s in %s.\n" %
                                 (`name`, `self.filename`))
        
        # Cache the widget to speed up future lookups.  If multiple
        # widgets in a hierarchy have the same name, the lookup
        # behavior is non-deterministic just as for libglade.
        setattr(self, name, result)
        return result

class Controller:
    """Base class for all controllers of glade-derived UIs."""
    def __init__(self, ui):
        """Initialize a new instance.
        `ui' is the user interface to be controlled."""
        self.ui = ui
        self.ui.signal_autoconnect(self._getAllMethods())

    def _getAllMethods(self):
        """Get a dictionary of all methods in self's class hierarchy."""
        result = {}

        # Find all callable instance/class attributes.  This will miss
        # attributes which are "interpreted" via __getattr__.  By
        # convention such attributes should be listed in
        # self.__methods__.
        allAttrNames = self.__dict__.keys() + self._getAllClassAttributes()
        for name in allAttrNames:
            value = getattr(self, name)
            if callable(value):
                result[name] = value
        return result

    def _getAllClassAttributes(self):
        """Get a list of all attribute names in self's class hierarchy."""
        nameSet = {}
        for currClass in self._getAllClasses():
            nameSet.update(currClass.__dict__)
        result = nameSet.keys()
        return result

    def _getAllClasses(self):
        """Get all classes in self's heritage."""
        result = [self.__class__]
        i = 0
        while i < len(result):
            currClass = result[i]
            result.extend(list(currClass.__bases__))
            i = i + 1
        return result


