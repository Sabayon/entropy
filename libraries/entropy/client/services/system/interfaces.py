# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

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
from __future__ import with_statement
import time
from entropy.exceptions import *
from entropy.i18n import _
from entropy.misc import TimeScheduled
from entropy.i18n import _

class Client:

    ssl_connection = True
    def __init__(self, OutputInterface, MethodsInterface = None, ClientCommandsInterface = None, quiet = True, show_progress = False, do_cache_connection = False, do_cache_session = False):

        if not hasattr(OutputInterface,'updateProgress'):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (OutputInterface,mytxt,))
        elif not callable(OutputInterface.updateProgress):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (OutputInterface,mytxt,))

        from entropy.client.services.system.commands import Client as ClientCommands
        if ClientCommandsInterface != None:
            if not issubclass(ClientCommandsInterface, ClientCommands):
                mytxt = _("A valid entropy.client.services.system.commands.Client class/subclass is needed")
                raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
            self.ClientCommandsInterface = ClientCommandsInterface
        else:
            self.ClientCommandsInterface = ClientCommands

        from entropy.client.services.system.methods import Base as BaseMethods
        if MethodsInterface != None:
            if not issubclass(MethodsInterface, BaseMethods):
                mytxt = _("A valid entropy.client.services.system.methods.BaseMethods class/subclass is needed")
                raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
            self.MethodsInterface = MethodsInterface
        else:
            self.MethodsInterface = BaseMethods

        import socket, struct
        import entropy.tools as entropyTools
        self.socket, self.struct, self.entropyTools = socket, struct, entropyTools
        from datetime import datetime
        self.datetime = datetime
        import threading
        self.threading = threading
        self.Output = OutputInterface
        self.hostname = None
        self.hostport = None
        self.username = None
        self.password = None
        self.quiet = quiet
        self.do_cache_connection = do_cache_connection
        self.show_progress = show_progress
        self.ClientCommandsInterface = ClientCommandsInterface
        self.Methods = self.MethodsInterface(self)
        self.session_cache = {}
        self.SessionCacheLock = self.threading.Lock()
        self.connection_cache = {}
        self.CacheLock = self.threading.Lock()
        self.shutdown = False
        self.connection_killer = None

        # XXX actually session cache doesn't work when the connection is closed and re-opened
        # when the server is spawning requests under a child process (fork_requests = True)
        # this should be fixed by pushing the cache to disk but triggers a possible security issue
        # since sessions and their password are stored in memory and kept alive there until those
        # expires
        self.do_cache_session = do_cache_session
        if self.do_cache_connection:
            self.connection_killer = TimeScheduled(2, self.connection_killer_handler)
            self.connection_killer.start()

    def __del__(self):
        if hasattr(self,'shutdown'):
            self.shutdown = True
        if hasattr(self,'connection_killer'):
            if self.connection_killer != None:
                self.connection_killer.kill()

    def _validate_credentials(self):
        if not isinstance(self.hostname,basestring):
            raise IncorrectParameter("IncorrectParameter: hostname: %s. %s" % (_('not a string'),_('Please use setup_connection() properly'),))
        if not isinstance(self.username,basestring):
            raise IncorrectParameter("IncorrectParameter: username: %s. %s" % (_('not a string'),_('Please use setup_connection() properly'),))
        if not isinstance(self.password,basestring):
            raise IncorrectParameter("IncorrectParameter: password: %s. %s" % (_('not a string'),_('Please use setup_connection() properly'),))
        if not isinstance(self.hostport,int):
            raise IncorrectParameter("IncorrectParameter: port: %s. %s" % (_('not an int'),_('Please use setup_connection() properly'),))
        if not isinstance(self.ssl_connection,bool):
            raise IncorrectParameter("IncorrectParameter: ssl_connection: %s. %s" % (_('not a bool'),_('Please use setup_connection() properly'),))

    def get_session_cache(self, cmd_tuple):
        if self.do_cache_session:
            with self.SessionCacheLock:
                return self.session_cache.get(cmd_tuple)

    def set_session_cache(self, cmd_tuple, session_id):
        if self.do_cache_session:
            with self.SessionCacheLock:
                self.session_cache[cmd_tuple] = session_id

    def remove_session_cache(self, cmd_tuple):
        if self.do_cache_session:
            with self.SessionCacheLock:
                del self.session_cache[cmd_tuple]

    def get_connection_cache_key(self):
        return hash((self.hostname, self.hostport, self.username, self.password, self.ssl_connection,))

    def get_connection_cache(self):
        if self.do_cache_connection:
            key = self.get_connection_cache_key()
            srv = self.connection_cache.get(key)
            # FIXME: if you enable cache connection, you should also consider to clear the socket buffer
            #  srv.sock_conn
            #  srv.real_sock_conn
            return srv

    def cache_connection(self, srv):
        if self.do_cache_connection:
            key = self.get_connection_cache_key()
            self.connection_cache[key] = {
                'conn': srv,
                'ts': self.get_ts(),
            }

    def update_connection_ts(self):
        if self.do_cache_connection:
            key = self.get_connection_cache_key()
            if key not in self.connection_cache:
                return
            self.connection_cache[key]['ts'] = self.get_ts()

    def kill_all_connections(self):
        if self.do_cache_connection:
            self.CacheLock.acquire()
            try:
                keys = self.connection_cache.keys()
                for key in keys:
                    data = self.connection_cache.pop(key)
                    data['conn'].disconnect()
            finally:
                self.CacheLock.release()

    def connection_killer_handler(self):

        if not self.do_cache_connection: return
        if self.shutdown: return
        if not self.connection_cache: return

        keys = self.connection_cache.keys()
        for key in keys:
            curr_ts = self.get_ts()
            ts = self.connection_cache[key]['ts']
            delta = curr_ts - ts
            if delta.seconds < 60:
                continue
            self.CacheLock.acquire()
            try:
                data = self.connection_cache.pop(key)
            finally:
                self.CacheLock.release()
            srv = data['conn']
            srv.disconnect()

    def get_ts(self):
        return self.datetime.fromtimestamp(time.time())

    def setup_connection(self, hostname, port, username, password, ssl):
        self.hostname = hostname
        self.hostport = port
        self.username = username
        self.password = password
        self.ssl_connection = ssl
        self._validate_credentials()

    def connect_to_service(self, timeout = None):
        self._validate_credentials()
        args = [self.Output, self.ClientCommandsInterface]
        kwargs = {
            'ssl': self.ssl_connection,
            'quiet': self.quiet,
            'show_progress': self.show_progress
        }
        if timeout != None: kwargs['socket_timeout'] = timeout
        from entropy.services.ugc.interfaces import Client
        srv = Client(*args,**kwargs)
        srv.connect(self.hostname, self.hostport)
        return srv

    def get_service_connection(self, timeout = None):
        try:
            srv = self.connect_to_service(timeout = timeout)
        except (ConnectionError,self.socket.error,self.struct.error,):
            return None
        return srv

    def logout(self, srv, session_id):
        self._validate_credentials()
        return srv.CmdInterface.service_logout(self.username, session_id)

    def login(self, srv, session_id):
        self._validate_credentials()
        return srv.CmdInterface.service_login(self.username, self.password, session_id)

    # eval(func) must have session as first param
    def do_cmd(self, login_required, func, args, kwargs):

        with self.CacheLock:

            srv = self.get_connection_cache()
            if srv == None:
                srv = self.get_service_connection(timeout = 10)
                if srv != None: self.cache_connection(srv)
            else:
                srv = srv['conn']

            if srv == None:
                return False, 'no connection'

            cmd_tuple = (login_required, func,)
            new_session = False
            session = self.get_session_cache(cmd_tuple)
            if session == None:
                new_session = True
                session = srv.open_session()
                if session == None:
                    return False, 'no session'
            else:
                if not srv.is_session_alive(session):
                    new_session = True
                    session = srv.open_session()
                    if session == None:
                        return False, 'no session'
            self.set_session_cache(cmd_tuple, session)

            self.update_connection_ts()
            args.insert(0,session)

            if login_required and new_session:
                logged, error = self.login(srv, session)
                if not logged:
                    srv.close_session(session)
                    self.remove_session_cache(cmd_tuple)
                    if not self.do_cache_connection:
                        srv.disconnect()
                    return False, error

            rslt = eval("srv.CmdInterface.%s" % (func,))(*args,**kwargs)
            if not self.do_cache_session:
                if login_required:
                    self.logout(srv, session)
                srv.close_session(session)
            if not self.do_cache_connection:
                srv.disconnect()
            return rslt

    def get_available_client_commands(self):
        return self.Methods.available_commands.copy()