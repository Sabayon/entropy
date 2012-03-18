import os
from threading import Semaphore
from gi.repository import GLib, Polkit, GObject

class AuthenticationController(object):

    """
    This class handles User authentication required
    for privileged activies, like Repository updates
    and Application management.
    """

    def __init__(self, mainloop):
        self._authenticated = False
        self._authenticated_sem = Semaphore(1)
        self._mainloop = mainloop

    def authenticate(self, action_id, authentication_callback):
        """
        Authenticate current User asking Administrator
        passwords.
        authentication_callback is the function that
        is called after the authentication procedure,
        providing one boolean argument describing the
        process result: True for authenticated, False
        for not authenticated.
        This method must be called from the MainLoop.
        If authentication has been already
        """
        self._authenticated_sem.acquire()
        if self._authenticated:
            try:
                authentication_callback(True)
            finally:
                self._authenticated_sem.release()
            return

        def _polkit_auth_callback(authority, res, loop):
            authenticated = False
            try:
                result = authority.check_authorization_finish(res)
                if result.get_is_authorized():
                    authenticated = True
                elif result.get_is_challenge():
                    authenticated = True
            except GObject.GError as err:
                raise err
            finally:
                self._authenticated = authenticated
                self._authenticated_sem.release()
                authentication_callback(authenticated)

        # authenticated_sem will be released in the callback
        authority = Polkit.Authority.get()
        subject = Polkit.UnixProcess.new(os.getppid())
        authority.check_authorization(
                subject,
                action_id,
                None,
                Polkit.CheckAuthorizationFlags.ALLOW_USER_INTERACTION,
                None, # Gio.Cancellable()
                _polkit_auth_callback,
                self._mainloop)

def callback(result):
    print "Auth status", result

mainloop = GLib.MainLoop()
ctrl = AuthenticationController(mainloop)
GLib.idle_add(ctrl.authenticate, "org.sabayon.RigoDaemon.update", callback)
mainloop.run()
