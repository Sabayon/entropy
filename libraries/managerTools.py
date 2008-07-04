#!/usr/bin/python
'''
    # DESCRIPTION:
    # enzyme helper classes

    Copyright (C) http://excess.org/urwid
    Thanks to Urwid developers, stuff taken from here too:
        http://excess.org/urwid/browser/urwid/trunk/dialog.py?format=txt

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''
import urwid
from entropyConstants import *
from entropy_i18n import _

class ManagerSettings:

    def __init__(self):
        self.Widgets = None
        self.process_spawned = False
        self.menu_enabled = False
        self.last_rc = None
        self.output_buffer = ''
        self.screen = None
        self.mainFrame = None
        self.mainBody = None
        self.menuBar = None
        self.statusBar = None
        self.programWidget = None
        self.outputWidget = None
        self.output = None
        self.output_row = 1
        self.max_x, self.max_y = 0,0
        self.welcome_text = _("(CTRL+E Menu | CTRL+X Exit)")
        self.inFocus = 0
        self.focusOptions = [0,1]
        self.focusInfo = {
            0: "Application",
            1: "Terminal"
        }
        self.auth_data = {}
        self.menu_keys_calls = {}


class PasswordEdit(urwid.Edit):

    def __init__(self, *args, **kwargs):
        urwid.Edit.__init__(self, *args, **kwargs)
        self._clean_edit_text = ''

    def set_edit_text(self, text):
        """Set the edit text for this widget."""
        self.highlight = None
        self._clean_edit_text = text
        text = '*'*len(text)
        self.edit_text = text
        if self.edit_pos > len(text):
            self.edit_pos = len(text)
        self._invalidate()

    def insert_text(self, text):
        """Insert text at the cursor position and update cursor."""
        p = self.edit_pos
        self.set_edit_text( self._clean_edit_text[:p] + text + 
                self._clean_edit_text[p:] )
        self.set_edit_pos( self.edit_pos + len(text))

    def get_edit_text(self):
        return self._clean_edit_text

class SimpleWidgets:

    class QuestionWidget(urwid.WidgetWrap):
        """
        Creates a BoxWidget that displays a message

        Attributes:

        b_pressed -- Contains the label of the last button pressed or None if no
                    button has been pressed.
        edit_text -- After a button is pressed, this contains the text the user
                    has entered in the edit field
        """

        b_pressed = None
        edit_text = None
        _edit_widget = None
        _mode = None

        def __init__(self, msg, buttons, attr, width, height, body):
            """
            msg -- content of the message widget, one of:
                    plain string -- string is displayed
                    (attr, markup2) -- markup2 is given attribute attr
                    [markupA, markupB, ... ] -- list items joined together
            buttons -- a list of strings with the button labels
            attr -- a tuple (background, button, active_button) of attributes
            width -- width of the message widget
            height -- height of the message widget
            body -- widget displayed beneath the message widget
            """

            self._blank = urwid.Text("")
            #Text widget containing the message:
            msg_widget = urwid.Padding(urwid.Text(msg), 'center', width - 4)

            #GridFlow widget containing all the buttons:
            button_widgets = []

            for button in buttons:
                button_widgets.append(urwid.AttrWrap(urwid.Button(button, self._action), attr[1], attr[2]))

            button_grid = urwid.GridFlow(button_widgets, 12, 2, 1, 'center')

            #Combine message widget and button widget:
            widget_list = [msg_widget, self._blank, button_grid]
            self._combined = urwid.AttrWrap(urwid.Filler(urwid.Pile(widget_list, 2)), attr[0])

            #Place the dialog widget on top of body:
            overlay = urwid.Overlay(self._combined, body, 'center', width, 'middle', height)

            urwid.WidgetWrap.__init__(self, overlay)

        def _action(self, button):
            """
            Function called when a button is pressed.
            Should not be called manually.
            """

            self.b_pressed = button.get_label()
            if self._edit_widget:
                self.edit_text = self._edit_widget.get_edit_text()

    class MenuWidget(urwid.WidgetWrap):

        class SelText(urwid.Text):
            """
            A selectable text widget. See urwid.Text.
            """

            def selectable(self):
                return True

            def keypress(self, size, key):
                """
                Don't handle any keys.
                """
                return key

        """
        Creates a popup menu on top of another BoxWidget.

        Attributes:

        selected -- Contains the item the user has selected by pressing <RETURN>,
                    or None if nothing has been selected.
        """

        selected = None

        def __init__(self, menu_list, attr, pos, body):
            """
            menu_list -- a list of strings with the menu entries
            attr -- a tuple (background, active_item) of attributes
            pos -- a tuple (x, y), position of the menu widget
            body -- widget displayed beneath the message widget
            """

            content = [urwid.AttrWrap(self.SelText(" " + w), None, attr[1])
                    for w in menu_list]

            #Calculate width and height of the menu widget:
            height = len(menu_list)
            width = 0
            for entry in menu_list:
                if len(entry) > width:
                    width = len(entry)

            #Create the ListBox widget and put it on top of body:
            self._listbox = urwid.AttrWrap(urwid.ListBox(content), attr[0])
            overlay = urwid.Overlay(self._listbox, body, ('fixed left', pos[0]),
                                    width + 2, ('fixed top', pos[1]), height)

            urwid.WidgetWrap.__init__(self, overlay)


        def keypress(self, size, key):
            """
            <RETURN> key selects an item, other keys will be passed to
            the ListBox widget.
            """

            if key == "enter":
                (widget, foo) = self._listbox.get_focus()
                (text, foo) = widget.get_text()
                self.selected = text[1:] #Get rid of the leading space...
            else:
                return self._listbox.keypress(size, key)

    class InputDialogWidget(urwid.WidgetWrap):

        b_pressed = None
        def __init__(self, title, input_parameters, attr, width, body, cancel = True):

            self.labels = {
                _('Ok'): 'ok',
                _('Cancel'): 'cancel',
            }
            height = 6
            self.button_values = ['ok','cancel']
            self.input_text_is_valid = False
            self.input_data = {}
            self.edit_widgets = []
            self.input_parameters = input_parameters[:]
            self.identifiers = {}
            self.do_cancel = cancel
            for identifier,widget_text,callback, password in self.input_parameters:
                if password:
                    myw = PasswordEdit(caption = widget_text+": ")
                else:
                    myw = urwid.Edit(caption = widget_text+": ")
                self.identifiers[identifier] = (myw,callback,widget_text,)
                self.edit_widgets.append(myw)
                height += 1

            # blank line
            self._blank = urwid.Text("")
            self._title = urwid.Text(title)
            # buttons
            button_widgets = []
            button_widgets.append(urwid.AttrWrap(urwid.Button(_('Ok'), self._action), attr[1], attr[2]))
            if self.do_cancel:
                button_widgets.append(urwid.AttrWrap(urwid.Button(_('Cancel'), self._action), attr[1], attr[2]))
            # button grid
            button_grid = urwid.GridFlow(button_widgets, 12, 2, 1, 'center')

            #Combine message widget and button widget:
            widget_list = [self._title,self._blank]
            widget_list += self.edit_widgets
            widget_list += [self._blank, button_grid]

            self._combined = urwid.Filler(urwid.Pile(widget_list, 2))
            self._combined = urwid.Padding(self._combined, 'center', width - 4)
            self._combined = urwid.AttrWrap(self._combined, attr[0])

            #Place the dialog widget on top of body:
            overlay = urwid.Overlay(self._combined, body, 'center', width+4, 'middle', height+1)
            urwid.WidgetWrap.__init__(self, overlay)

        def _action(self, button):
            """
            Function called when a button is pressed.
            Should not be called manually.
            """

            got_valid = True
            b_pressed = button.get_label()
            self.b_pressed = None
            # update input_data
            for identifier in self.identifiers:
                self.input_data[identifier] = None
                myw, cb, widget_text = self.identifiers[identifier]
                result = myw.get_edit_text()
                valid = cb(result)
                if valid:
                    self.input_data[identifier] = result
                else:
                    got_valid = False
            self.input_text_is_valid = got_valid
            self.b_pressed = self.labels.get(b_pressed)

    def __init__(self, interface):
        self.Manager = interface.Manager
        self.Interface = interface

    def Dialog(self, message, options):
        return self.QuestionWidget(message, options, ('menu', 'bg', 'bgf'), 30, 5, self.Manager.mainFrame)

    def InputDialog(self, title, input_parameters, show_cancel = True):
        return self.InputDialogWidget(title, input_parameters, ('menu', 'bg', 'bgf'), 40, self.Manager.mainFrame, cancel = show_cancel)

    def Menu(self, options, position):
        return self.MenuWidget(options, ('menu', 'menuf'), position, self.Manager.mainFrame)

