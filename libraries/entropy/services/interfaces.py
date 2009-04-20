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
import os
import shutil
import time
from entropy.const import etpConst, ETP_LOGLEVEL_NORMAL, ETP_LOGPRI_INFO, \
    const_setup_perms
from entropy.exceptions import *
from entropy.services.skel import SocketAuthenticator, SocketCommands
from entropy.i18n import _
from entropy.output import blue, red, darkgreen

class SocketHost:

    import socket
    import SocketServer
    from threading import Thread

    class BasicPamAuthenticator(SocketAuthenticator):

        import entropy.tools as entropyTools

        def __init__(self, HostInterface, *args, **kwargs):
            self.valid_auth_types = [ "plain", "shadow", "md5" ]
            SocketAuthenticator.__init__(self, HostInterface)

        def docmd_login(self, arguments):

            # filter n00bs
            if not arguments or (len(arguments) != 3):
                return False,None,None,'wrong arguments'

            user = arguments[0]
            auth_type = arguments[1]
            auth_string = arguments[2]

            # check auth type validity
            if auth_type not in self.valid_auth_types:
                return False,user,None,'invalid auth type'

            udata = self.__get_user_data(user)
            if udata == None:
                return False,user,None,'invalid user'

            uid = udata[2]
            # check if user is in the Entropy group
            if not self.entropyTools.is_user_in_entropy_group(uid):
                return False,user,uid,'user not in %s group' % (etpConst['sysgroup'],)

            # now validate password
            valid = self.__validate_auth(user,auth_type,auth_string)
            if not valid:
                return False,user,uid,'auth failed'

            if not uid:
                self.HostInterface.sessions[self.session]['admin'] = True
            else:
                self.HostInterface.sessions[self.session]['user'] = True
            return True,user,uid,"ok"

        # it we get here is because user is logged in
        def docmd_userdata(self):

            auth_uid = self.HostInterface.sessions[self.session]['auth_uid']
            mydata = {}
            udata = self.__get_uid_data(auth_uid)
            if udata:
                mydata['username'] = udata[0]
                mydata['uid'] = udata[2]
                mydata['gid'] = udata[3]
                mydata['references'] = udata[4]
                mydata['home'] = udata[5]
                mydata['shell'] = udata[6]
            return True,mydata,'ok'

        def __get_uid_data(self, user_id):
            import pwd
            # check user validty
            try:
                udata = pwd.getpwuid(user_id)
            except KeyError:
                return None
            return udata

        def __get_user_data(self, user):
            import pwd
            # check user validty
            try:
                udata = pwd.getpwnam(user)
            except KeyError:
                return None
            return udata

        def __validate_auth(self, user, auth_type, auth_string):
            valid = False
            if auth_type == "plain":
                valid = self.__do_auth(user, auth_string)
            elif auth_type == "shadow":
                valid = self.__do_auth(user, auth_string, auth_type = "shadow")
            elif auth_type == "md5":
                valid = self.__do_auth(user, auth_string, auth_type = "md5")
            return valid

        def __do_auth(self, user, password, auth_type = None):
            import spwd

            try:
                enc_pass = spwd.getspnam(user)[1]
            except KeyError:
                return False

            if auth_type == None: # plain
                import crypt
                generated_pass = crypt.crypt(str(password), enc_pass)
            elif auth_type == "shadow":
                generated_pass = password
            elif auth_type == "md5": # md5
                import hashlib
                m = hashlib.md5()
                m.update(enc_pass)
                enc_pass = m.hexdigest()
                generated_pass = str(password)
            else: # haha, fuck!
                generated_pass = None

            if generated_pass == enc_pass:
                return True
            return False

        def docmd_logout(self, myargs):

            # filter n00bs
            if (len(myargs) < 1) or (len(myargs) > 1):
                return False,None,'wrong arguments'

            user = myargs[0]
            # filter n00bs
            if not user or not isinstance(user,basestring):
                return False,None,"wrong user"

            return True,user,"ok"

        def set_exc_permissions(self, uid, gid):
            if gid != None:
                os.setgid(gid)
            if uid != None:
                os.setuid(uid)

        def hide_login_data(self, args):
            myargs = args[:]
            myargs[-1] = 'hidden'
            return myargs

        def terminate_instance(self):
            pass

    class HostServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):

        class ConnWrapper:
            '''
            Base class for implementing the rest of the wrappers in this module.
            Operates by taking a connection argument which is used when 'self' doesn't
            provide the functionality being requested.
            '''
            def __init__(self, connection) :
                self.connection = connection

            def __getattr__(self, function) :
                return getattr(self.connection, function)

        import entropy.tools as entropyTools
        import socket as socket_mod
        import select
        import SocketServer
        # This means the main server will not do the equivalent of a
        # pthread_join() on the new threads.  With this set, Ctrl-C will
        # kill the server reliably.
        daemon_threads = True

        # By setting this we allow the server to re-bind to the address by
        # setting SO_REUSEADDR, meaning you don't have to wait for
        # timeouts when you kill the server and the sockets don't get
        # closed down correctly.
        allow_reuse_address = True

        def __init__(self, server_address, RequestHandlerClass, processor, HostInterface, authorized_clients_only = False):

            self.alive = True
            self.socket = self.socket_mod
            self.processor = processor
            self.server_address = server_address
            self.HostInterface = HostInterface
            self.SSL = self.HostInterface.SSL
            self.real_sock = None
            self.ssl_authorized_clients_only = authorized_clients_only

            if self.SSL:
                self.SocketServer.BaseServer.__init__(self, server_address, RequestHandlerClass)
                self.load_ssl_context()
                self.make_ssl_connection_alive()
            else:
                try:
                    self.SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
                except self.socket_mod.error, e:
                    if e[0] == 13:
                        raise ConnectionError('ConnectionError: %s' % (_("Cannot bind the service"),))
                    raise

        def load_ssl_context(self):
            # setup an SSL context.
            self.context = self.SSL['m'].Context(self.SSL['m'].SSLv23_METHOD)
            self.context.set_verify(self.SSL['m'].VERIFY_PEER, self.verify_ssl_cb) # ask for a certificate
            self.context.set_options(self.SSL['m'].OP_NO_SSLv2)
            # load up certificate stuff.
            self.context.use_privatekey_file(self.SSL['key'])
            self.context.use_certificate_file(self.SSL['cert'])
            self.context.load_verify_locations(self.SSL['ca_cert'])
            self.context.load_client_ca(self.SSL['ca_cert'])
            self.HostInterface.updateProgress('SSL context loaded, key: %s - cert: %s, CA cert: %s, CA pkey: %s' % (
                    self.SSL['key'],
                    self.SSL['cert'],
                    self.SSL['ca_cert'],
                    self.SSL['ca_pkey']
                )
            )

        def make_ssl_connection_alive(self):
            self.real_sock = self.socket_mod.socket(self.address_family, self.socket_type)
            self.socket = self.ConnWrapper(self.SSL['m'].Connection(self.context, self.real_sock))
            self.server_bind()
            self.server_activate()

        # this function should do the authentication checking to see that
        # the client is who they say they are.
        def verify_ssl_cb(self, conn, cert, errnum, depth, ok) :
            return ok

        def verify_request(self, request, client_address):

            self.do_ssl = self.HostInterface.SSL
            if self.do_ssl: self.do_ssl = True
            else: self.do_ssl = False

            allowed = self.ip_blacklist_check(client_address[0])
            if allowed: allowed = self.ip_max_connections_check(client_address[0])
            if not allowed:
                self.HostInterface.updateProgress(
                    '[from: %s | SSL: %s] connection refused, ip blacklisted or maximum connections per IP reached' % (
                        client_address,
                        self.do_ssl,
                    )
                )
                return False

            allowed = self.max_connections_check(request)
            if not allowed:
                self.HostInterface.updateProgress(
                    '[from: %s | SSL: %s] connection refused (max connections reached: %s)' % (
                        client_address,
                        self.do_ssl,
                        self.HostInterface.max_connections,
                    )
                )
                return False

            ### let's go!
            self.HostInterface.connections += 1
            self.HostInterface.updateProgress(
                '[from: %s | SSL: %s] connection established (%s of %s max connections)' % (
                    client_address,
                    self.do_ssl,
                    self.HostInterface.connections,
                    self.HostInterface.max_connections,
                )
            )
            return True

        def ip_blacklist_check(self, client_addr):
            if client_addr in self.HostInterface.ip_blacklist:
                return False
            return True

        def ip_max_connections_check(self, ip_address):
            max_conn_per_ip = self.HostInterface.max_connections_per_host
            max_conn_per_ip_barrier = self.HostInterface.max_connections_per_host_barrier
            per_host_connections = self.HostInterface.per_host_connections
            conn_data = per_host_connections.get(ip_address)
            if conn_data == None:
                per_host_connections[ip_address] = 1
            else:
                conn_data += 1
                per_host_connections[ip_address] += 1
                if conn_data > max_conn_per_ip:
                    self.HostInterface.updateProgress(
                        '[from: %s] ------- :EEK: !! connection closed too many simultaneous connections from host (current: %s | limit: %s) -------' % (
                            ip_address,
                            conn_data,
                            max_conn_per_ip,
                        )
                    )
                    return False
                elif conn_data > max_conn_per_ip_barrier:
                    times = [5,6,7,8]
                    self.HostInterface.updateProgress(
                        '[from: %s] ------- :EEEK: !! connection warning simultaneous connection barrier reached from host (current: %s | soft limit: %s) -------' % (
                            ip_address,
                            conn_data,
                            max_conn_per_ip_barrier,
                        )
                    )
                    rnd_num = self.entropyTools.get_random_number()
                    time.sleep(times[abs(hash(rnd_num))%len(times)])

            return True

        def max_connections_check(self, request):
            current = self.HostInterface.connections
            maximum = self.HostInterface.max_connections
            if current >= maximum:
                try:
                    self.HostInterface.transmit(
                        request,
                        self.HostInterface.answers['mcr']
                    )
                except:
                    pass
                return False
            else:
                return True

        def serve_forever(self):
            while self.alive:
                #r,w,e = self.select.select([self.socket], [], [], 1)
                #if r:
                self.handle_request()

        # taken from SocketServer.py
        def finish_request(self, request, client_address):
            """Finish one request by instantiating RequestHandlerClass."""
            self.RequestHandlerClass(request, client_address, self)

            self.HostInterface.updateProgress(
                '[from: %s] connection closed (%s of %s max connections)' % (
                    client_address,
                    self.HostInterface.connections - 1,
                    self.HostInterface.max_connections,
                )
            )
            per_host_connections = self.HostInterface.per_host_connections
            conn_data = per_host_connections.get(client_address[0])
            if conn_data != None:
                if conn_data < 1:
                    del per_host_connections[client_address[0]]
                else:
                    per_host_connections[client_address[0]] -= 1

        def close_request(self, request):
            if self.HostInterface.connections > 0:
                self.HostInterface.connections -= 1

    class RequestHandler(SocketServer.BaseRequestHandler):

        import SocketServer
        import select
        import socket
        import entropy.tools as entropyTools
        import gc
        timed_out = False

        def __init__(self, request, client_address, server):

            # pre-init attribues
            self.server = None
            self.request = None
            self.client_address = None
            self.SocketServer.BaseRequestHandler.__init__(self, request,
                client_address, server)

        def data_receiver(self):

            if self.timed_out:
                return True
            self.timed_out = True
            try:
                ready_to_read, ready_to_write, in_error = self.select.select(
                    [self.request], [], [], self.default_timeout)
            except KeyboardInterrupt:
                self.timed_out = True
                return True

            if len(ready_to_read) == 1 and ready_to_read[0] == self.request:

                self.timed_out = False

                try:

                    data = self.request.recv(1024)
                    if self.ssl:
                        while self.request.pending():
                            data += self.request.recv(1024)

                    if self.data_counter == None:
                        if data == '': # client wants to close
                            return True
                        elif data == self.server.processor.HostInterface.answers['noop']:
                            return False
                        elif len(data) < len(self.myeos):
                            self.server.processor.HostInterface.updateProgress(
                                'interrupted: %s, reason: %s - from client: %s - data: "%s" - counter: %s' % (
                                    self.server.server_address,
                                    "malformed EOS",
                                    self.client_address,
                                    repr(data),
                                    self.data_counter,
                                )
                            )
                            self.buffered_data = ''
                            return True
                        mystrlen = data.split(self.myeos)[0]
                        self.data_counter = int(mystrlen)
                        data = data[len(mystrlen)+1:]
                        self.data_counter -= len(data)
                        self.buffered_data += data

                    # command length exceeds our command length limit
                    if self.data_counter > self.max_command_length:
                        raise InterruptError('InterruptError: command too long: %s, limit: %s' % (self.data_counter,self.max_command_length,))

                    while self.data_counter > 0:
                        if self.ssl:
                            x = ''
                            while self.request.pending():
                                x += self.request.recv(1024)
                        else:
                            x = self.request.recv(1024)
                        xlen = len(x)
                        self.data_counter -= xlen
                        self.buffered_data += x
                        if not xlen:
                            break

                    self.data_counter = None
                except ValueError:
                    #self.entropyTools.print_traceback()
                    self.server.processor.HostInterface.updateProgress(
                        'interrupted: %s, reason: %s - from client: %s' % (
                            self.server.server_address,
                            "malformed transmission",
                            self.client_address,
                        )
                    )
                    return True
                except self.socket.timeout, e:
                    self.server.processor.HostInterface.updateProgress(
                        'interrupted: %s, reason: %s - from client: %s' % (
                            self.server.server_address,
                            e,
                            self.client_address,
                        )
                    )
                    return True
                except self.socket.sslerror, e:
                    self.server.processor.HostInterface.updateProgress(
                        'interrupted: %s, SSL socket error reason: %s - from client: %s' % (
                            self.server.server_address,
                            e,
                            self.client_address,
                        )
                    )
                    return True
                except (self.ssl_exceptions['WantReadError'], self.ssl_exceptions['WantX509LookupError'],):
                    return False
                except self.ssl_exceptions['ZeroReturnError']:
                    return True
                except self.ssl_exceptions['Error'], e:
                    self.server.processor.HostInterface.updateProgress(
                        'interrupted: SSL Error, reason: %s - from client: %s' % (
                            e,
                            self.client_address,
                        )
                    )
                    return True
                except InterruptError, e:
                    self.server.processor.HostInterface.updateProgress(
                        'interrupted: Command Error, reason: %s - from client: %s' % (
                            e,
                            self.client_address,
                        )
                    )
                    return True

                if not self.buffered_data:
                    return True

                cmd = self.server.processor.process(self.buffered_data, self.request, self.client_address)
                if cmd == 'close':
                    # send KAPUTT signal JA!
                    self.server.processor.transmit(self.server.processor.HostInterface.answers['cl'])
                    return True
                self.buffered_data = ''
                return False

        def fork_lock_acquire(self):
            if hasattr(self.server.processor.HostInterface,'ForkLock'):
                x = getattr(self.server.processor.HostInterface,'ForkLock')
                if hasattr(x,'acquire') and hasattr(x,'release') and hasattr(x,'locked'):
                    x.acquire()

        def fork_lock_release(self):
            if hasattr(self.server.processor.HostInterface,'ForkLock'):
                x = getattr(self.server.processor.HostInterface,'ForkLock')
                if hasattr(x,'acquire') and hasattr(x,'release') and hasattr(x,'locked'):
                    if x.locked(): x.release()

        def handle(self):
            # not using spawnFunction because it causes some mess
            # forking this way avoids having memory leaks
            if self.server.processor.HostInterface.fork_requests:
                self.fork_lock_acquire()
                try:
                    my_timeout = self.server.processor.HostInterface.fork_request_timeout_seconds
                    pid = os.fork()
                    seconds = 0
                    if pid > 0: # parent here
                        # pid killer after timeout
                        passed_away = False
                        while 1:
                            time.sleep(1)
                            seconds += 1
                            try:
                                dead = os.waitpid(pid, os.WNOHANG)[0]
                            except OSError, e:
                                if e.errno != 10: raise
                                dead = True
                            if passed_away:
                                break
                            if dead: break
                            if seconds > my_timeout:
                                self.server.processor.HostInterface.updateProgress(
                                    'interrupted: forked request timeout: %s,%s from client: %s' % (
                                        seconds,
                                        dead,
                                        self.client_address,
                                    )
                                )
                                if not dead:
                                    import signal
                                    os.kill(pid,signal.SIGKILL)
                                    passed_away = True # in this way, the process table should be clean
                                    continue
                                break
                    else:
                        self.do_handle()
                        os._exit(0)
                finally:
                    self.fork_lock_release()
            else:
                self.do_handle()
            #self.entropyTools.spawn_function(self.do_handle)

        def do_handle(self):

            self.default_timeout = self.server.processor.HostInterface.timeout
            self.ssl = self.server.processor.HostInterface.SSL
            self.ssl_exceptions = self.server.processor.HostInterface.SSL_exceptions
            self.myeos = self.server.processor.HostInterface.answers['eos']
            self.max_command_length = self.server.processor.HostInterface.max_command_length

            while 1:

                try:
                    dobreak = self.data_receiver()
                    if dobreak: break
                except Exception, e:
                    self.server.processor.HostInterface.updateProgress(
                        'interrupted: Unhandled exception: %s, error: %s - from client: %s' % (
                            Exception,
                            e,
                            self.client_address,
                        )
                    )
                    # print exception
                    tb = self.entropyTools.get_traceback()
                    print tb
                    self.server.processor.HostInterface.socketLog.write(tb)
                    break

            self.request.close()

        def setup(self):
            self.data_counter = None
            self.buffered_data = ''


    class CommandProcessor:

        import entropy.tools as entropyTools
        import socket
        import gc

        def __init__(self, HostInterface):
            self.HostInterface = HostInterface
            self.channel = None

        def handle_termination_commands(self, data):
            if data.strip() in self.HostInterface.termination_commands:
                self.HostInterface.updateProgress('close: %s' % (self.client_address,))
                self.transmit(self.HostInterface.answers['cl'])
                return "close"

            if not data.strip():
                return "ignore"

        def handle_command_string(self, string):
            # validate command
            args = string.strip().split()
            session = args[0]
            if (session in self.HostInterface.initialization_commands) or \
                (session in self.HostInterface.no_session_commands) or \
                len(args) < 2:
                    cmd = args[0]
                    session = None
            else:
                cmd = args[1]
                args = args[1:] # remove session

            stream_enabled = False
            if (session != None) and self.HostInterface.sessions.has_key(session):
                stream_enabled = self.HostInterface.sessions[session].get('stream_mode')

            if stream_enabled and (cmd not in self.HostInterface.config_commands):
                session_len = 0
                if session: session_len = len(session)+1
                return cmd,[string[session_len+len(cmd)+1:]],session
            else:
                myargs = []
                if len(args) > 1:
                    myargs = args[1:]

                return cmd,myargs,session

        def handle_end_answer(self, cmd, whoops, valid_cmd):
            if not valid_cmd:
                self.transmit(self.HostInterface.answers['no'])
            elif whoops:
                self.transmit(self.HostInterface.answers['er'])
            elif cmd not in self.HostInterface.no_acked_commands:
                self.transmit(self.HostInterface.answers['ok'])

        def validate_command(self, cmd, args, session):

            # answer to invalid commands
            if (cmd not in self.HostInterface.valid_commands):
                return False,"not a valid command"

            if session == None:
                if cmd not in self.HostInterface.no_session_commands:
                    return False,"need a valid session"
            elif session not in self.HostInterface.sessions:
                return False,"session is not alive"

            # check if command needs authentication
            if session != None:
                auth = self.HostInterface.valid_commands[cmd]['auth']
                if auth:
                    # are we?
                    authed = self.HostInterface.sessions[session]['auth_uid']
                    if authed == None:
                        # nope
                        return False,"not authenticated"

            # keep session alive
            if session != None:
                self.HostInterface.set_session_running(session)
                self.HostInterface.update_session_time(session)

            return True,"all good"

        def load_authenticator(self):
            f, args, kwargs = self.HostInterface.AuthenticatorInst
            myinst = f(*args,**kwargs)
            return myinst

        def load_service_interface(self, session):

            uid = None
            if session != None:
                uid = self.HostInterface.sessions[session]['auth_uid']

            intf = self.HostInterface.EntropyInstantiation[0]
            args = self.HostInterface.EntropyInstantiation[1]
            kwds = self.HostInterface.EntropyInstantiation[2]
            return intf(*args, **kwds)

        def process(self, data, channel, client_address):

            self.channel = channel
            self.client_address = client_address

            term = self.handle_termination_commands(data)
            if term:
                del authenticator
                return term

            cmd, args, session = self.handle_command_string(data)
            valid_cmd, reason = self.validate_command(cmd, args, session)

            # decide if we need to load authenticator or Entropy
            authenticator = None
            cmd_data = self.HostInterface.valid_commands.get(cmd)
            if not isinstance(cmd_data,dict):
                self.HostInterface.updateProgress(
                    '[from: %s] command error: invalid command: %s' % (
                        self.client_address,
                        cmd,
                    )
                )
                return "close"
            elif (("authenticator" in cmd_data['args']) or (cmd in self.HostInterface.login_pass_commands)):
                try:
                    authenticator = self.load_authenticator()
                except ConnectionError, e:
                    self.HostInterface.updateProgress(
                        '[from: %s] authenticator error: cannot load: %s' % (
                            self.client_address,
                            e,
                        )
                    )
                    tb = self.entropyTools.get_traceback()
                    print tb
                    self.HostInterface.socketLog.write(tb)
                    return "close"
                except Exception, e:
                    self.HostInterface.updateProgress(
                        '[from: %s] authenticator error: cannot load: %s - unknown error' % (
                            self.client_address,
                            e,
                        )
                    )
                    tb = self.entropyTools.get_traceback()
                    print tb
                    self.HostInterface.socketLog.write(tb)
                    return "close"

            p_args = args
            if (cmd in self.HostInterface.login_pass_commands) and authenticator != None:
                p_args = authenticator.hide_login_data(p_args)
            elif cmd in self.HostInterface.raw_commands:
                p_args = ['raw data']
            self.HostInterface.updateProgress(
                '[from: %s] command validation :: called %s: length: %s, args: %s, session: %s, valid: %s, reason: %s' % (
                    self.client_address,
                    cmd,
                    len(data),
                    p_args,
                    session,
                    valid_cmd,
                    reason,
                )
            )

            whoops = False
            if valid_cmd:

                if authenticator != None:
                    # now set session
                    authenticator.set_session(session)

                Entropy = None
                if "Entropy" in cmd_data['args']:
                    Entropy = self.load_service_interface(session)
                try:
                    self.run_task(cmd, args, session, Entropy, authenticator)
                except self.socket.timeout:
                    self.HostInterface.updateProgress(
                        '[from: %s] command error: timeout, closing connection' % (
                            self.client_address,
                        )
                    )
                    # close connection
                    del authenticator
                    del Entropy
                    return "close"
                except self.socket.error, e:
                    self.HostInterface.updateProgress(
                        '[from: %s] command error: socket error: %s' % (
                            self.client_address,
                            e,
                        )
                    )
                    # close connection
                    del authenticator
                    del Entropy
                    return "close"
                except self.HostInterface.SSL_exceptions['SysCallError'], e:
                    self.HostInterface.updateProgress(
                        '[from: %s] command error: SSL SysCallError: %s' % (
                            self.client_address,
                            e,
                        )
                    )
                    # close connection
                    del authenticator
                    del Entropy
                    return "close"
                except Exception, e:
                    # write to self.HostInterface.socketLog
                    tb = self.entropyTools.get_traceback()
                    print tb
                    self.HostInterface.socketLog.write(tb)
                    # store error
                    self.HostInterface.updateProgress(
                        '[from: %s] command error: %s, type: %s' % (
                            self.client_address,
                            e,
                            type(e),
                        )
                    )
                    if session != None:
                        self.HostInterface.store_rc(str(e),session)
                    whoops = True

                del Entropy

            if session != None:
                self.HostInterface.update_session_time(session)
                self.HostInterface.unset_session_running(session)
            rcmd = None
            try:
                self.handle_end_answer(cmd, whoops, valid_cmd)
            except (self.socket.error, self.socket.timeout,self.HostInterface.SSL_exceptions['SysCallError'],):
                rcmd = "close"

            if authenticator != None:
                authenticator.terminate_instance()
            del authenticator
            if not self.HostInterface.fork_requests:
                self.gc.collect()
            return rcmd

        def transmit(self, data):
            self.HostInterface.transmit(self.channel, data)

        def run_task(self, cmd, args, session, Entropy, authenticator):

            p_args = args
            if cmd in self.HostInterface.login_pass_commands:
                p_args = authenticator.hide_login_data(p_args)
            elif cmd in self.HostInterface.raw_commands:
                p_args = ['raw data']
            self.HostInterface.updateProgress(
                '[from: %s] run_task :: called %s: args: %s, session: %s' % (
                    self.client_address,
                    cmd,
                    p_args,
                    session,
                )
            )

            myargs = args
            mykwargs = {}
            if cmd not in self.HostInterface.raw_commands:
                myargs, mykwargs = self._get_args_kwargs(args)

            rc = self.spawn_function(cmd, myargs, mykwargs, session, Entropy, authenticator)
            if session != None and self.HostInterface.sessions.has_key(session):
                self.HostInterface.store_rc(rc, session)
            return rc

        def _get_args_kwargs(self, args):
            myargs = []
            mykwargs = {}

            def is_int(x):
                try:
                    int(x)
                except ValueError:
                    return False
                return True

            for arg in args:
                if (arg.find("=") != -1) and not arg.startswith("="):
                    x = arg.split("=")
                    a = x[0]
                    b = ''.join(x[1:])
                    if (b in ("True","False",)) or is_int(b):
                        mykwargs[a] = eval(b)
                    else:
                        myargs.append(arg)
                else:
                    if (arg in ("True","False",)) or is_int(arg):
                        myargs.append(eval(arg))
                    else:
                        myargs.append(arg)
            return myargs, mykwargs

        def spawn_function(self, cmd, myargs, mykwargs, session, Entropy, authenticator):

            p_args = myargs
            if cmd in self.HostInterface.login_pass_commands:
                p_args = authenticator.hide_login_data(p_args)
            elif cmd in self.HostInterface.raw_commands:
                p_args = ['raw data']
            self.HostInterface.updateProgress(
                '[from: %s] called %s: args: %s, kwargs: %s' % (
                    self.client_address,
                    cmd,
                    p_args,
                    mykwargs,
                )
            )
            return self.do_spawn(cmd, myargs, mykwargs, session, Entropy, authenticator)

        def do_spawn(self, cmd, myargs, mykwargs, session, Entropy, authenticator):

            cmd_data = self.HostInterface.valid_commands.get(cmd)
            do_fork = cmd_data['as_user']
            f = cmd_data['cb']
            func_args = []
            for arg in cmd_data['args']:
                try:
                    func_args.append(eval(arg))
                except (NameError, SyntaxError):
                    func_args.append(str(arg))

            if do_fork:
                myfargs = func_args[:]
                myfargs.extend(myargs)
                return self.fork_task(f, session, authenticator, *myfargs, **mykwargs)
            else:
                return f(*func_args)

        def fork_task(self, f, session, authenticator, *args, **kwargs):
            gid = None
            uid = None
            if session != None:
                logged_in = self.HostInterface.sessions[session]['auth_uid']
                if logged_in != None:
                    uid = logged_in
                    gid = etpConst['entropygid']
            return self.entropyTools.spawn_function(self._do_fork, f, authenticator, uid, gid, *args, **kwargs)

        def _do_fork(self, f, authenticator, uid, gid, *args, **kwargs):
            authenticator.set_exc_permissions(uid,gid)
            rc = f(*args,**kwargs)
            return rc

    class BuiltInCommands(SocketCommands):

        import entropy.dump as dumpTools
        import zlib

        def __init__(self, HostInterface):

            SocketCommands.__init__(self, HostInterface, inst_name = "builtin")

            self.valid_commands = {
                'begin':    {
                                'auth': False, # does it need authentication ?
                                'built_in': True, # is it built-in ?
                                'cb': self.docmd_begin, # function to call
                                'args': ["self.transmit", "self.client_address"], # arguments to be passed before *args and **kwards, in SocketHostInterface.do_spawn()
                                'as_user': False, # do I have to fork the process and run it as logged user?
                                                  # needs auth = True
                                'desc': "instantiate a session", # description
                                'syntax': "begin", # syntax
                                'from': unicode(self), # from what class
                            },
                'end':      {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_end,
                                'args': ["self.transmit", "session"],
                                'as_user': False,
                                'desc': "end a session",
                                'syntax': "<SESSION_ID> end",
                                'from': unicode(self),
                            },
                'session_config':      {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_session_config,
                                'args': ["session","myargs"],
                                'as_user': False,
                                'desc': "set session configuration options",
                                'syntax': "<SESSION_ID> session_config <option> [parameters]",
                                'from': unicode(self),
                            },
                'rc':       {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_rc,
                                'args': ["self.transmit","session"],
                                'as_user': False,
                                'desc': "get data returned by the last valid command (streamed python object)",
                                'syntax': "<SESSION_ID> rc",
                                'from': unicode(self),
                            },
                'hello':    {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_hello,
                                'args': ["self.transmit"],
                                'as_user': False,
                                'desc': "get server status",
                                'syntax': "hello",
                                'from': unicode(self),
                            },
                'alive':    {
                                'auth': True,
                                'built_in': True,
                                'cb': self.docmd_alive,
                                'args': ["self.transmit","self.client_address","myargs"],
                                'as_user': False,
                                'desc': "check if a session is still alive",
                                'syntax': "alive <SESSION_ID>",
                                'from': unicode(self),
                            },
                'login':    {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_login,
                                'args': ["self.transmit", "authenticator", "session", "self.client_address", "myargs"],
                                'as_user': False,
                                'desc': "login on the running server (allows running extra commands)",
                                'syntax': "<SESSION_ID> login <authenticator parameters, default: <user> <auth_type> <password> >",
                                'from': unicode(self),
                            },
                'user_data':    {
                                'auth': True,
                                'built_in': True,
                                'cb': self.docmd_userdata,
                                'args': ["self.transmit", "authenticator", "session"],
                                'as_user': False,
                                'desc': "get general user information, user must be logged in",
                                'syntax': "<SESSION_ID> user_data",
                                'from': unicode(self),
                            },
                'logout':   {
                                'auth': True,
                                'built_in': True,
                                'cb': self.docmd_logout,
                                'args': ["self.transmit", "authenticator", "session", "self.client_address", "myargs"],
                                'as_user': False,
                                'desc': "logout on the running server",
                                'syntax': "<SESSION_ID> logout <USER>",
                                'from': unicode(self),
                            },
                'help':   {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_help,
                                'args': ["self.transmit"],
                                'as_user': False,
                                'desc': "this output",
                                'syntax': "help",
                                'from': unicode(self),
                            },
                'available_commands':   {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_available_commands,
                                'args': ["self.HostInterface"],
                                'as_user': False,
                                'desc': "get info about available commands (you must retrieve this using the 'rc' command)",
                                'syntax': "available_commands",
                                'from': unicode(self),
                            },
                'stream':   {
                                'auth': True,
                                'built_in': True,
                                'cb': self.docmd_stream,
                                'args': ["session", "myargs"],
                                'as_user': False,
                                'desc': "send a chunk of data to be saved on the session temp file path (will be removed on session expiration)",
                                'syntax': "<SESSION_ID> stream <chunk of byte-string to write to file>",
                                'from': unicode(self),
                            },
            }

            self.no_acked_commands = ["rc", "begin", "end", "hello", "alive", "login", "logout","help"]
            self.termination_commands = ["quit","close"]
            self.initialization_commands = ["begin"]
            self.login_pass_commands = ["login"]
            self.no_session_commands = ["begin","hello","alive","help"]
            self.raw_commands = ["stream"]
            self.config_commands = ["session_config"]

        def docmd_session_config(self, session, myargs):

            if not myargs:
                return False,"not enough parameters"

            option = myargs[0]
            myopts = myargs[1:]

            if option == "compression":
                docomp = True
                do_zlib = False
                if "zlib" in myopts:
                    do_zlib = True
                if myopts:
                    if isinstance(myopts[0],bool):
                        docomp = myopts[0]
                    else:
                        try:
                            docomp = eval(myopts[0])
                        except (NameError, TypeError,):
                            pass
                if docomp and do_zlib:
                    docomp = "zlib"
                elif docomp and not do_zlib:
                    docomp = "gzip"
                else:
                    docomp = None
                self.HostInterface.sessions[session]['compression'] = docomp
                return True,"compression now: %s" % (docomp,)
            elif option == "stream":
                dostream = True
                if "off" in myopts:
                    dostream = False
                self.HostInterface.sessions[session]['stream_mode'] = dostream
                return True,'stream mode: %s' % (dostream,)
            else:
                return False,"invalid config option"

        def docmd_available_commands(self, host_interface):

            def copy_obj(obj):
                if isinstance(obj,set) or isinstance(obj,dict):
                    return obj.copy()
                elif isinstance(obj,list) or isinstance(obj,tuple):
                    return obj[:]
                return obj

            def can_be_streamed(obj):
                if isinstance(obj,(bool,basestring,int,float,list,tuple,set,dict,)):
                    return True
                return False

            mydata = {}
            mydata['disabled_commands'] = copy_obj(host_interface.disabled_commands)
            valid_cmds = copy_obj(host_interface.valid_commands)
            mydata['valid_commands'] = {}
            for cmd in valid_cmds:
                mydict = {}
                for item in valid_cmds[cmd]:
                    param = valid_cmds[cmd][item]
                    if not can_be_streamed(param):
                        continue
                    mydict[item] = param
                mydata['valid_commands'][cmd] = mydict.copy()

            return mydata

        def docmd_stream(self, session, myargs):

            if not self.HostInterface.sessions[session]['stream_mode']:
                return False,'not in stream mode'
            if not myargs:
                return False,'no stream sent'

            compression = self.HostInterface.sessions[session]['compression']

            stream = myargs[0]
            stream_path = self.HostInterface.sessions[session]['stream_path']
            stream_dir = os.path.dirname(stream_path)
            if not os.path.isdir(os.path.dirname(stream_path)):
                try:
                    os.makedirs(stream_dir)
                    if etpConst['entropygid'] != None:
                        const_setup_perms(stream_dir,etpConst['entropygid'])
                except OSError:
                    return False,'cannot initialize stream directory'

            f = open(stream_path,'abw')
            if compression:
                stream = self.zlib.decompress(stream)
            f.write(stream)
            f.flush()
            f.close()

            return True,'ok'

        def docmd_login(self, transmitter, authenticator, session, client_address, myargs):

            # is already auth'd?
            auth_uid = self.HostInterface.sessions[session]['auth_uid']
            if auth_uid != None:
                return False,"already authenticated"

            status, user, uid, reason = authenticator.docmd_login(myargs)
            if status:
                self.HostInterface.updateProgress(
                    '[from: %s] user %s logged in successfully, session: %s' % (
                        client_address,
                        user,
                        session,
                    )
                )
                self.HostInterface.sessions[session]['auth_uid'] = uid
                transmitter(self.HostInterface.answers['ok'])
                return True,reason
            elif user == None:
                self.HostInterface.updateProgress(
                    '[from: %s] user -not specified- login failed, session: %s, reason: %s' % (
                        client_address,
                        session,
                        reason,
                    )
                )
                transmitter(self.HostInterface.answers['no'])
                return False,reason
            else:
                self.HostInterface.updateProgress(
                    '[from: %s] user %s login failed, session: %s, reason: %s' % (
                        client_address,
                        user,
                        session,
                        reason,
                    )
                )
                transmitter(self.HostInterface.answers['no'])
                return False,reason

        def docmd_userdata(self, transmitter, authenticator, session):

            auth_uid = self.HostInterface.sessions[session]['auth_uid']
            if auth_uid == None:
                return False,None,"not authenticated"

            return authenticator.docmd_userdata()

        def docmd_logout(self, transmitter, authenticator, session, client_address, myargs):
            status, user, reason = authenticator.docmd_logout(myargs)
            if status:
                self.HostInterface.updateProgress(
                    '[from: %s] user %s logged out successfully, session: %s, args: %s ' % (
                        client_address,
                        user,
                        session,
                        myargs,
                    )
                )
                self.HostInterface.sessions[session]['auth_uid'] = None
                transmitter(self.HostInterface.answers['ok'])
                return True,reason
            elif user == None:
                self.HostInterface.updateProgress(
                    '[from: %s] user -not specified- logout failed, session: %s, args: %s, reason: %s' % (
                        client_address,
                        session,
                        myargs,
                        reason,
                    )
                )
                transmitter(self.HostInterface.answers['no'])
                return False,reason
            else:
                self.HostInterface.updateProgress(
                    '[from: %s] user %s logout failed, session: %s, args: %s, reason: %s' % (
                        client_address,
                        user,
                        session,
                        myargs,
                        reason,
                    )
                )
                transmitter(self.HostInterface.answers['no'])
                return False,reason

        def docmd_alive(self, transmitter, client_address, myargs):
            cmd = self.HostInterface.answers['no']
            alive = False
            if myargs:
                session_data = self.HostInterface.sessions.get(myargs[0])
                if session_data != None:
                    if client_address[0] == session_data.get('ip_address'):
                        cmd = self.HostInterface.answers['ok']
                        alive = True
            transmitter(cmd)
            return alive

        def docmd_hello(self, transmitter):
            from entropy.tools import getstatusoutput
            from entropy.core import SystemSettings
            sys_settings = SystemSettings()
            uname = os.uname()
            kern_string = uname[2]
            running_host = uname[1]
            running_arch = uname[4]
            load_stats = getstatusoutput('uptime')[1].split("\n")[0]
            text = "Entropy Server %s, connections: %s ~ running on: %s ~ host: %s ~ arch: %s, kernel: %s, stats: %s\n" % (
                    etpConst['entropyversion'],
                    self.HostInterface.connections,
                    sys_settings['system']['name'],
                    running_host,
                    running_arch,
                    kern_string,
                    load_stats
                    )
            transmitter(text)

        def docmd_help(self, transmitter):
            text = '\nEntropy Socket Interface Help Menu\n' + \
                   'Available Commands:\n\n'
            valid_cmds = sorted(self.HostInterface.valid_commands.keys())
            for cmd in valid_cmds:
                if self.HostInterface.valid_commands[cmd].has_key('desc'):
                    desc = self.HostInterface.valid_commands[cmd]['desc']
                else:
                    desc = 'no description available'

                if self.HostInterface.valid_commands[cmd].has_key('syntax'):
                    syntax = self.HostInterface.valid_commands[cmd]['syntax']
                else:
                    syntax = 'no syntax available'
                if self.HostInterface.valid_commands[cmd].has_key('from'):
                    myfrom = self.HostInterface.valid_commands[cmd]['from']
                else:
                    myfrom = 'N/A'
                text += "[%s] %s\n   %s: %s\n   %s: %s\n" % (
                    myfrom,
                    blue(cmd),
                    red("description"),
                    desc.strip(),
                    darkgreen("syntax"),
                    syntax,
                )
            transmitter(text)

        def docmd_end(self, transmitter, session):
            rc = self.HostInterface.destroy_session(session)
            cmd = self.HostInterface.answers['no']
            if rc: cmd = self.HostInterface.answers['ok']
            transmitter(cmd)
            return rc

        def docmd_begin(self, transmitter, client_address):
            session = self.HostInterface.get_new_session(client_address[0])
            transmitter(session)
            return session

        def docmd_rc(self, transmitter, session):
            rc = self.HostInterface.get_rc(session)
            comp = self.HostInterface.sessions[session]['compression']
            myserialized = self.dumpTools.serialize_string(rc)
            if comp == "zlib": # new shiny zlib
                myserialized = self.zlib.compress(myserialized, 7) # compression level 1-9
            elif comp == "gzip": # old and burried
                import gzip
                try:
                    import cStringIO as stringio
                except ImportError:
                    import StringIO as stringio
                f = stringio.StringIO()
                self.dumpTools.serialize(rc, f)
                myf = stringio.StringIO()
                mygz = gzip.GzipFile(
                    mode = 'wb',
                    fileobj = myf
                )
                f.seek(0)
                chunk = f.read(8192)
                while chunk:
                    mygz.write(chunk)
                    chunk = f.read(8192)
                mygz.flush()
                mygz.close()
                myserialized = myf.getvalue()
                f.close()
                myf.close()


            transmitter(myserialized)

            return rc

    def __init__(self, service_interface, *args, **kwds):

        import gc
        self.gc = gc
        import threading
        self.threading = threading
        import entropy.tools as entropyTools
        from entropy.misc import TimeScheduled
        self.TimeScheduled = TimeScheduled
        self.entropyTools = entropyTools
        self.Server = None
        self.Gc = None
        self.PythonGarbageCollector = None
        self.AuthenticatorInst = None

        self.args = args
        self.kwds = kwds
        from entropy.misc import LogFile
        self.socketLog = LogFile(
            level = etpConst['socketloglevel'],
            filename = etpConst['socketlogfile'],
            header = "[Socket]"
        )

        # settings
        from entropy.core import SystemSettings
        import copy
        """
        SystemSettings is a singleton, and we just need to read
        socket configuration. we don't want to mess other instances
        so we pay attention to not use it more than what is needed.
        """
        sys_settings = SystemSettings()
        self.__socket_settings = copy.deepcopy(sys_settings['socket_service'])

        self.SessionsLock = self.threading.Lock()
        self.fork_requests = True # used by the command processor
        self.fork_request_timeout_seconds = self.__socket_settings['forked_requests_timeout']
        self.stdout_logging = True
        self.timeout = self.__socket_settings['timeout']
        self.hostname = self.__socket_settings['hostname']
        self.session_ttl = self.__socket_settings['session_ttl']
        if self.hostname == "*": self.hostname = ''
        self.port = self.__socket_settings['port']
        self.threads = self.__socket_settings['threads'] # maximum number of allowed sessions
        self.max_connections = self.__socket_settings['max_connections']
        self.max_connections_per_host = self.__socket_settings['max_connections_per_host']
        self.max_connections_per_host_barrier = self.__socket_settings['max_connections_per_host_barrier']
        self.max_command_length = self.__socket_settings['max_command_length']
        self.disabled_commands = self.__socket_settings['disabled_cmds']
        self.ip_blacklist = self.__socket_settings['ip_blacklist']
        self.answers = self.__socket_settings['answers']
        self.connections = 0
        self.per_host_connections = {}
        self.sessions = {}
        self.__output = None
        self.SSL = {}
        self.SSL_exceptions = {}
        self.SSL_exceptions['WantReadError'] = None
        self.SSL_exceptions['WantWriteError'] = None
        self.SSL_exceptions['WantX509LookupError'] = None
        self.SSL_exceptions['ZeroReturnError'] = None
        self.SSL_exceptions['SysCallError'] = None
        self.SSL_exceptions['Error'] = []
        self.last_print = ''
        self.valid_commands = {}
        self.no_acked_commands = []
        self.raw_commands = []
        self.config_commands = []
        self.termination_commands = []
        self.initialization_commands = []
        self.login_pass_commands = []
        self.no_session_commands = []
        self.command_classes = [self.BuiltInCommands]
        self.command_instances = []
        self.EntropyInstantiation = (service_interface, self.args, self.kwds)

        self.setup_external_command_classes()
        self.start_local_output_interface()
        self.setup_authenticator()
        self.setup_hostname()
        self.setup_commands()
        self.disable_commands()
        self.start_session_garbage_collector()
        self.setup_ssl()
        self.start_python_garbage_collector()

    def killall(self):
        if hasattr(self,'socketLog'):
            self.socketLog.close()
        if self.Server != None:
            self.Server.alive = False
        if self.Gc != None:
            self.Gc.kill()
        if self.PythonGarbageCollector != None:
            self.PythonGarbageCollector.kill()

    def append_eos(self, data):
        return str(len(data)) + \
            self.answers['eos'] + \
                data

    def setup_ssl(self):

        do_ssl = False
        if self.kwds.has_key('ssl'):
            do_ssl = self.kwds.pop('ssl')

        if not do_ssl:
            return

        try:
            from OpenSSL import SSL, crypto
        except ImportError, e:
            self.updateProgress('Unable to load OpenSSL, error: %s' % (repr(e),))
            return
        self.SSL_exceptions['WantReadError'] = SSL.WantReadError
        self.SSL_exceptions['Error'] = SSL.Error
        self.SSL_exceptions['WantWriteError'] = SSL.WantWriteError
        self.SSL_exceptions['WantX509LookupError'] = SSL.WantX509LookupError
        self.SSL_exceptions['ZeroReturnError'] = SSL.ZeroReturnError
        self.SSL_exceptions['SysCallError'] = SSL.SysCallError
        self.SSL['m'] = SSL
        self.SSL['crypto'] = crypto
        self.SSL['key'] = self.__socket_settings['ssl_key']
        self.SSL['cert'] = self.__socket_settings['ssl_cert']
        self.SSL['ca_cert'] = self.__socket_settings['ssl_ca_cert']
        self.SSL['ca_pkey'] = self.__socket_settings['ssl_ca_pkey']
        # change port
        self.port = self.__socket_settings['ssl_port']
        self.SSL['not_before'] = 0
        self.SSL['not_after'] = 60*60*24*365*5 # 5 years
        self.SSL['serial'] = 0
        self.SSL['digest'] = 'md5'

        if not (os.path.isfile(self.SSL['ca_cert']) and \
            os.path.isfile(self.SSL['ca_pkey']) and \
            os.path.isfile(self.SSL['key']) and \
            os.path.isfile(self.SSL['cert'])):
                self.create_ca_server_certs(
                    self.SSL['serial'],
                    self.SSL['digest'],
                    self.SSL['not_before'],
                    self.SSL['not_after'],
                    self.SSL['ca_pkey'],
                    self.SSL['ca_cert'],
                    self.SSL['key'],
                    self.SSL['cert']
                )
                os.chmod(self.SSL['ca_cert'],0644)
                try:
                    os.chown(self.SSL['ca_cert'],-1,0)
                except OSError:
                    pass
                os.chmod(self.SSL['ca_pkey'],0600)
                try:
                    os.chown(self.SSL['ca_pkey'],-1,0)
                except OSError:
                    pass

        os.chmod(self.SSL['key'],0600)
        try:
            os.chown(self.SSL['key'],-1,0)
        except OSError:
            pass
        os.chmod(self.SSL['cert'],0644)
        try:
            os.chown(self.SSL['cert'],-1,0)
        except OSError:
            pass

    def create_ca_server_certs(self, serial, digest, not_before, not_after, ca_pkey_dest, ca_cert_dest, server_key, server_cert):

        mycn = 'Entropy Repository Service'
        cakey = self.create_ssl_key_pair(self.SSL['crypto'].TYPE_RSA, 1024)
        careq = self.create_ssl_certificate_request(cakey, digest, CN = mycn)
        cert = self.SSL['crypto'].X509()
        cert.set_serial_number(serial)
        cert.gmtime_adj_notBefore(not_before)
        cert.gmtime_adj_notAfter(not_after)
        cert.set_issuer(careq.get_subject())
        cert.set_subject(careq.get_subject())
        cert.sign(cakey, digest)

        # now create server key + cert
        s_pkey = self.create_ssl_key_pair(self.SSL['crypto'].TYPE_RSA, 1024)
        s_req = self.create_ssl_certificate_request(s_pkey, digest, CN = mycn)
        s_cert = self.SSL['crypto'].X509()
        s_cert.set_serial_number(serial+1)
        s_cert.gmtime_adj_notBefore(not_before)
        s_cert.gmtime_adj_notAfter(not_after)
        s_cert.set_issuer(cert.get_subject())
        s_cert.set_subject(s_req.get_subject())
        s_cert.set_pubkey(s_req.get_pubkey())
        s_cert.sign(cakey, digest)

        # write CA
        if os.path.isfile(ca_pkey_dest):
            shutil.move(ca_pkey_dest,ca_pkey_dest+".moved")
        f = open(ca_pkey_dest,"w")
        f.write(self.SSL['crypto'].dump_privatekey(self.SSL['crypto'].FILETYPE_PEM, cakey))
        f.flush()
        f.close()
        if os.path.isfile(ca_cert_dest):
            shutil.move(ca_cert_dest,ca_cert_dest+".moved")
        f = open(ca_cert_dest,"w")
        f.write(self.SSL['crypto'].dump_certificate(self.SSL['crypto'].FILETYPE_PEM, cert))
        f.flush()
        f.close()

        if os.path.isfile(server_key):
            shutil.move(server_key,server_key+".moved")
        # write server
        f = open(server_key,"w")
        f.write(self.SSL['crypto'].dump_privatekey(self.SSL['crypto'].FILETYPE_PEM, s_pkey))
        f.flush()
        f.close()
        if os.path.isfile(server_cert):
            shutil.move(server_cert,server_cert+".moved")
        f = open(server_cert,"w")
        f.write(self.SSL['crypto'].dump_certificate(self.SSL['crypto'].FILETYPE_PEM, s_cert))
        f.flush()
        f.close()

    def create_ssl_key_pair(self, keytype, bits):
        pkey = self.SSL['crypto'].PKey()
        pkey.generate_key(keytype, bits)
        return pkey

    def create_ssl_certificate_request(self, pkey, digest, **name):
        req = self.SSL['crypto'].X509Req()
        subj = req.get_subject()
        for (key,value) in name.items():
            setattr(subj, key, value)
        req.set_pubkey(pkey)
        req.sign(pkey, digest)
        return req

    def setup_external_command_classes(self):

        if self.kwds.has_key('external_cmd_classes'):
            ext_commands = self.kwds.pop('external_cmd_classes')
            if not isinstance(ext_commands,list):
                raise InvalidDataType("InvalidDataType: external_cmd_classes must be a list")
            self.command_classes += ext_commands

    def setup_commands(self):

        identifiers = set()
        for myclass in self.command_classes:

            myargs = []
            mykwargs = {}
            if isinstance(myclass,tuple) or isinstance(myclass,list):
                if len(myclass) > 2:
                    mykwargs = myclass[2]
                if len(myclass) > 1:
                    myargs = myclass[1]
                myclass = myclass[0]

            myinst = myclass(self, *myargs, **mykwargs)
            if str(myinst) in identifiers:
                raise PermissionDenied("PermissionDenied: another command instance is owning this name")
            identifiers.add(str(myinst))
            self.command_instances.append(myinst)
            # now register
            myinst.register(    self.valid_commands,
                                self.no_acked_commands,
                                self.termination_commands,
                                self.initialization_commands,
                                self.login_pass_commands,
                                self.no_session_commands,
                                self.raw_commands,
                                self.config_commands
                            )

    def disable_commands(self):
        for cmd in self.disabled_commands:

            if cmd in self.valid_commands:
                self.valid_commands.pop(cmd)

            if cmd in self.no_acked_commands:
                self.no_acked_commands.remove(cmd)

            if cmd in self.termination_commands:
                self.termination_commands.remove(cmd)

            if cmd in self.initialization_commands:
                self.initialization_commands.remove(cmd)

            if cmd in self.login_pass_commands:
                self.login_pass_commands.remove(cmd)

            if cmd in self.no_session_commands:
                self.no_session_commands.remove(cmd)

            if cmd in self.raw_commands:
                self.raw_commands.remove(cmd)

            if cmd in self.config_commands:
                self.config_commands.remove(cmd)

    def start_local_output_interface(self):
        if self.kwds.has_key('sock_output'):
            outputIntf = self.kwds.pop('sock_output')
            self.__output = outputIntf

    def setup_authenticator(self):

        # lock, if perhaps some implementations need it
        self.AuthenticatorLock = self.threading.Lock()
        auth_inst = (self.BasicPamAuthenticator, [self], {},) # authentication class, args, keywords
        # external authenticator
        if self.kwds.has_key('sock_auth'):
            authIntf = self.kwds.pop('sock_auth')
            if type(authIntf) is tuple:
                if len(authIntf) == 3:
                    auth_inst = authIntf[:]
                else:
                    raise IncorrectParameter("IncorrectParameter: wront authentication interface specified")
            else:
                raise IncorrectParameter("IncorrectParameter: wront authentication interface specified")
            # initialize authenticator
        self.AuthenticatorInst = (auth_inst[0],[self]+auth_inst[1],auth_inst[2],)

    def start_python_garbage_collector(self):
        self.PythonGarbageCollector = self.TimeScheduled(3600, self.python_garbage_collect)
        self.PythonGarbageCollector.set_accuracy(False)
        self.PythonGarbageCollector.start()

    def start_session_garbage_collector(self):
        self.Gc = self.TimeScheduled(5, self.gc_clean)
        self.Gc.start()

    def python_garbage_collect(self):
        self.gc.collect()
        self.gc.collect()
        self.gc.collect()

    def gc_clean(self):
        if not self.sessions:
            return

        with self.SessionsLock:
            for session_id in self.sessions.keys():
                sess_time = self.sessions[session_id]['t']
                is_running = self.sessions[session_id]['running']
                auth_uid = self.sessions[session_id]['auth_uid'] # is kept alive?
                if (is_running) or (auth_uid == -1):
                    if auth_uid == -1:
                        self.updateProgress('not killing session %s, since it is kept alive by auth_uid=-1' % (session_id,) )
                    continue
                cur_time = time.time()
                ttl = self.session_ttl
                check_time = sess_time + ttl
                if cur_time > check_time:
                    self.updateProgress('killing session %s, ttl: %ss: no activity' % (session_id,ttl,) )
                    self._destroy_session(session_id)

    def setup_hostname(self):
        if self.hostname:
            try:
                self.hostname = self.get_ip_address(self.hostname)
            except IOError: # it isn't a device name
                pass

    def get_ip_address(self, ifname):
        import fcntl
        import struct
        mysock = self.socket.socket ( self.socket.AF_INET, self.socket.SOCK_STREAM )
        return self.socket.inet_ntoa(fcntl.ioctl(mysock.fileno(), 0x8915, struct.pack('256s', ifname[:15]))[20:24])

    def get_md5_hash(self):
        import hashlib
        m = hashlib.md5()
        m.update(os.urandom(2))
        return m.hexdigest()

    def get_new_session(self, ip_address = None):
        with self.SessionsLock:
            if len(self.sessions) > self.threads:
                # fuck!
                return "0"
            rng = self.get_md5_hash()
            while rng in self.sessions:
                rng = self.get_md5_hash()
            self.sessions[rng] = {}
            self.sessions[rng]['running'] = False
            self.sessions[rng]['auth_uid'] = None
            self.sessions[rng]['admin'] = False
            self.sessions[rng]['moderator'] = False
            self.sessions[rng]['user'] = False
            self.sessions[rng]['developer'] = False
            self.sessions[rng]['compression'] = None
            self.sessions[rng]['stream_mode'] = False
            try:
                self.sessions[rng]['stream_path'] = self.entropyTools.get_random_temp_file()
            except (IOError,OSError,):
                self.sessions[rng]['stream_path'] = ''
            self.sessions[rng]['t'] = time.time()
            self.sessions[rng]['ip_address'] = ip_address
            return rng

    def update_session_time(self, session):
        with self.SessionsLock:
            if self.sessions.has_key(session):
                self.sessions[session]['t'] = time.time()
                self.updateProgress('session time updated for %s' % (session,) )

    def set_session_running(self, session):
        with self.SessionsLock:
            if self.sessions.has_key(session):
                self.sessions[session]['running'] = True

    def unset_session_running(self, session):
        with self.SessionsLock:
            if self.sessions.has_key(session):
                self.sessions[session]['running'] = False

    def destroy_session(self, session):
        with self.SessionsLock:
            self._destroy_session(session)

    def _destroy_session(self, session):
        if self.sessions.has_key(session):
            stream_path = self.sessions[session]['stream_path']
            del self.sessions[session]
            if os.path.isfile(stream_path) and os.access(stream_path,os.W_OK) and not os.path.islink(stream_path):
                try: os.remove(stream_path)
                except OSError: pass
            return True
        return False

    def go(self):
        self.socket.setdefaulttimeout(self.timeout)
        while 1:
            try:
                self.Server = self.HostServer(
                                                (self.hostname, self.port),
                                                self.RequestHandler,
                                                self.CommandProcessor(self),
                                                self
                                            )
                break
            except self.socket.error, e:
                if e[0] == 98:
                    # Address already in use
                    self.updateProgress('address already in use (%s, port: %s), waiting 5 seconds...' % (self.hostname,self.port,))
                    time.sleep(5)
                    continue
                else:
                    raise
        self.updateProgress('server connected, listening on: %s, port: %s, timeout: %s' % (self.hostname,self.port,self.timeout,))
        self.Server.serve_forever()
        self.Gc.kill()

    def store_rc(self, rc, session):
        with self.SessionsLock:
            if session in self.sessions:
                if type(rc) in (list,tuple,):
                    rc_item = rc[:]
                elif type(rc) in (set,frozenset,dict,):
                    rc_item = rc.copy()
                else:
                    rc_item = rc
                self.sessions[session]['rc'] = rc_item

    def get_rc(self, session):
        with self.SessionsLock:
            if session in self.sessions:
                return self.sessions[session].get('rc')

    def transmit(self, channel, data):
        if self.SSL:
            mydata = self.append_eos(data)
            encode_done = False
            while 1:
                try:
                    sent = channel.send(mydata)
                    if sent == len(mydata):
                        break
                    mydata = mydata[sent:]
                except (self.SSL_exceptions['WantWriteError'],self.SSL_exceptions['WantReadError']):
                    time.sleep(0.2)
                    continue
                except UnicodeEncodeError:
                    if encode_done:
                        raise
                    mydata = mydata.encode('utf-8')
                    encode_done = True
                    continue
        else:
            channel.sendall(self.append_eos(data))

    def updateProgress(self, *args, **kwargs):
        message = args[0]
        if message != self.last_print:
            self.socketLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,str(args[0]))
            if self.__output != None and self.stdout_logging:
                self.__output.updateProgress(*args,**kwargs)
            self.last_print = message
