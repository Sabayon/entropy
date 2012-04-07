# -*- coding: utf-8 -*-
"""
Copyright (C) 2012 Fabio Erculiani

Authors:
  Fabio Erculiani

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; version 3.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""
import os
from gi.repository import GLib, Polkit, GObject

from entropy.const import const_debug_write

class AuthenticationController(object):

    """
    This class handles User authentication required
    for privileged activies, like Repository updates
    and Application management.
    """

    def __init__(self):
        self._mainloop = GLib.MainLoop()

    def authenticate(self, pid, action_id, authentication_callback):
        """
        Authenticate current User asking Administrator
        passwords.
        authentication_callback is the function that
        is called after the authentication procedure,
        providing one boolean argument describing the
        process result: True for authenticated, False
        for not authenticated.
        This method must be called from the MainLoop.
        """
        def _polkit_auth_callback(authority, res, loop):
            authenticated = False
            try:
                result = authority.check_authorization_finish(res)
                if result.get_is_authorized():
                    authenticated = True
                elif result.get_is_challenge():
                    authenticated = True
            except GObject.GError as err:
                const_debug_write(
                    __name__,
                    "_polkit_auth_callback: error: %s" % (err,))
            finally:
                authentication_callback(authenticated)

        # authenticated_sem will be released in the callback
        authority = Polkit.Authority.get()
        subject = Polkit.UnixProcess.new(pid)
        authority.check_authorization(
                subject,
                action_id,
                None,
                Polkit.CheckAuthorizationFlags.ALLOW_USER_INTERACTION,
                None, # Gio.Cancellable()
                _polkit_auth_callback,
                self._mainloop)

    def authenticate_sync(self, pid, action_id):
        """
        Authenticate current User asking Administrator
        passwords.
        Return True if authenticated, False if not.
        """
        authority = Polkit.Authority.get()
        subject = Polkit.UnixProcess.new(pid)
        result = authority.check_authorization_sync(
                subject,
                action_id,
                None,
                Polkit.CheckAuthorizationFlags.ALLOW_USER_INTERACTION,
                None)

        authenticated = False
        try:
            if result.get_is_authorized():
                authenticated = True
            elif result.get_is_challenge():
                authenticated = True
        except GObject.GError as err:
            const_debug_write(
                __name__,
                "_polkit_auth_callback: error: %s" % (err,))
        return authenticated
