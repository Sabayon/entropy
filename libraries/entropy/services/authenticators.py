# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Services Authenticators Interface}.

"""

from entropy.const import const_get_stringtype
from entropy.services.skel import Authenticator
from entropy.services.auth_interfaces import phpBB3Auth
from entropy.services.skel import SocketAuthenticator
from entropy.exceptions import *

# Authenticator that can be used by SocketHostInterface based instances
class phpBB3(phpBB3Auth, SocketAuthenticator):

    import entropy.tools as entropyTools
    def __init__(self, HostInterface, *args, **kwargs):
        SocketAuthenticator.__init__(self, HostInterface)
        phpBB3Auth.__init__(self)
        self.set_connection_data(kwargs)
        self.connect()

    def set_session(self, session):
        self.session = session
        session_data = self.HostInterface.sessions.get(self.session)
        if not session_data:
            return
        auth_id = session_data['auth_uid']
        if auth_id:
            self.logged_in = True
            # fill login_data with fake information
            self.login_data = {'username': self.FAKE_USERNAME, 'password': 'look elsewhere, this is not a password', 'user_id': auth_id}
            ip_address = session_data.get('ip_address')
            if ip_address and self.do_update_session_table:
                self._update_session_table(auth_id, ip_address)

    def docmd_login(self, arguments):

        # filter n00bs
        if not arguments or (len(arguments) != 2):
            return False, None, None, 'wrong arguments'

        ip_address = None
        session_data = self.HostInterface.sessions.get(self.session)
        if session_data:
            ip_address = session_data.get('ip_address')
        user = arguments[0]
        password = arguments[1]

        if ip_address:
            if self._is_ip_banned(ip_address):
                return False, user, None, "banned IP"

        login_data = {'username': user, 'password': password}
        self.set_login_data(login_data)
        rc = False
        try:
            rc = self.login()
        except PermissionDenied as e:
            return rc, user, None, e.value

        if rc:
            uid = self.get_user_id()
            is_admin = self.is_administrator()
            is_dev = self.is_developer()
            is_mod = self.is_moderator()
            is_user = self.is_user()
            self.HostInterface.sessions[self.session]['admin'] = is_admin
            self.HostInterface.sessions[self.session]['developer'] = is_dev
            self.HostInterface.sessions[self.session]['moderator'] = is_mod
            self.HostInterface.sessions[self.session]['user'] = is_user
            if ip_address and uid and self.do_update_session_table:
                self._update_session_table(uid, ip_address)
            return True, user, uid, "ok"
        return rc, user, None, "login failed"

    # if we get here it means we are logged in
    def docmd_userdata(self):
        data = self.get_user_data()
        return True, data, 'ok'

    def docmd_logout(self, myargs):

        # filter n00bs
        if (len(myargs) < 1) or (len(myargs) > 1):
            return False, None, 'wrong arguments'

        user = myargs[0]
        # filter n00bs
        if not user or not isinstance(user, const_get_stringtype()):
            return False, None, "wrong user"

        if not self.is_logged_in():
            return False, user, "already logged out"

        return True, user, "ok"

    def set_exc_permissions(self, *args, **kwargs):
        pass

    def hide_login_data(self, args):
        myargs = args[:]
        myargs[-1] = 'hidden'
        return myargs

    def terminate_instance(self):
        self.disconnect()
