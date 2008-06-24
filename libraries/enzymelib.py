#!/usr/bin/python
'''
    # DESCRIPTION:
    # enzyme helper classes

    Copyright (C) http://excess.org/urwid

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
        self.welcome_text = _("%s Repository Manager %s") % (etpConst['systemname'],etpConst['entropyversion'],)
        self.inFocus = 0
        self.focusOptions = [0,1]
        self.focusInfo = {
            0: "Application",
            1: "Terminal"
        }
        self.menu_keys_calls = {}

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

    def __init__(self, interface):
        self.Manager = interface.Manager
        self.Interface = interface

    def Dialog(self, message, options):
        return self.QuestionWidget(message, options,('menu', 'bg', 'bgf'), 30, 5, self.Manager.mainFrame)
