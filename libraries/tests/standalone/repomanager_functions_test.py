# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '../../')
sys.path.insert(0, '../../../sulfur/src')

import os
if os.getuid() != 0:
    raise SystemError("run this as root")

import signal
import unittest
import time
import socket

from entropy.const import etpUi, etpConst
from entropy.tools import print_traceback
from entropy.services.skel import SocketAuthenticator
from entropy.services.interfaces import SocketHost

from sulfur.dialogs import RepositoryManagerMenu

class FakeAuthenticator(SocketHost.BasicPamAuthenticator):
    """
    This class always returns valid login credentials
    """

    valid_auth_types = [ "plain", "shadow", "md5" ]

    def __get_user_data(self, user):

        import pwd
        try:
            udata = pwd.getpwnam(user)
        except KeyError:
            return None
        return udata

    def docmd_login(self, arguments):

        if not arguments or (len(arguments) != 3):
            return False, None, None, 'wrong arguments'

        user = arguments[0]
        auth_type = arguments[1]
        auth_string = arguments[2]

        # check auth type validity
        if auth_type not in FakeAuthenticator.valid_auth_types:
            return False, user, None, 'invalid auth type'

        udata = self.__get_user_data(user)
        if udata == None:
            return False, user, None, 'invalid user'

        uid = udata[2]

        if not uid:
            self.HostInterface.sessions[self.session]['admin'] = True
        else:
            self.HostInterface.sessions[self.session]['user'] = True

        return True, user, uid, "ok"

class MyRepositoryManager(RepositoryManagerMenu):

    def __init__(self, equo, parent):
        RepositoryManagerMenu.__init__(self, equo, parent)

    def service_status_message(self, e):
        if etpUi['debug']:
            print_traceback()

    def load(self):
        """ taken from real class """
        self.sm_ui.repositoryManager.show_all()
        self.hide_all_data_view_buttons()
        # spawn parallel tasks
        self.QueueUpdater.start()
        self.OutputUpdater.start()
        self.PinboardUpdater.start()
        # ui will be unlocked by the thread below
        self.ui_lock(True)
        self.EntropyRepositoryComboLoader.start()

        return True

    @staticmethod
    def init(entropy_client, host, port, username, password, ssl):
        import gobject
        import gtk
        import gtk.gdk
        repo = MyRepositoryManager(entropy_client, None)
        repo.connection_verification_callback(host, port, username,
            password, ssl)
        repo.load()
        # kill updaters, we don't need them
        repo.OutputUpdater.kill()
        repo.PinboardUpdater.kill()
        repo.QueueUpdater.set_delay(10)
        gobject.threads_init()
        gtk.gdk.threads_enter()

        def do_start():
            try:
                gtk.main()
            except KeyboardInterrupt:
                gtk.main_quit()
            gtk.gdk.threads_leave()

        gobject.timeout_add(1000, do_start)
        return repo

    def on_repoManagerClose_clicked(self, *args, **kwargs):
        """ taken from real class """
        self.QueueUpdater.kill()
        self.OutputUpdater.kill()
        self.PinboardUpdater.kill()
        self.destroy()
        raise SystemExit(0)


class RepomanTest(unittest.TestCase):

    def setUp(self):

        self.start_repoman_srv = True
        self.host = 'localhost'
        self.port = 1027
        self.ssl = False
        self.username = 'root'
        self.password = 'fakefakefake'
        # enable debug mode ?
        etpUi['debug'] = False

        # Server-side logging to stdout, if False, logs will be in socket.log
        # otherwise pushed to stdout
        self.stdout_logging = False

        self.repoman_srv_pid = None
        if self.start_repoman_srv:
            try:
                self.repoman_srv_pid = self.load_repoman_service()
            except AssertionError:
                self.kill_repoman_service()
                raise

        from entropy.client.interfaces import Client
        self.RepoMan = MyRepositoryManager.init(Client(), self.host,
            self.port, self.username, self.password, self.ssl)

    def wait_for_connection(self, i_want_conn_enabled = True):
        retries = 30
        while retries:
            retries -= 1
            time.sleep(1.0)
            try:
                sock = socket.create_connection((self.host, self.port),
                    timeout = 1.0)
            except socket.error as err:
                if not i_want_conn_enabled:
                    return True
                if err.errno == 111:
                    continue # retry
                raise
            sock.close()
            if i_want_conn_enabled:
                return True

        return False

    def load_repoman_service(self):

        from entropy.server.interfaces import Server
        # init with fake repository.
        server_intf = Server(fake_default_repo = True)

        pid = os.fork()
        if pid == 0:

            from entropy.services.system.executors import Base
            from entropy.services.system.commands import Repository
            from entropy.services.system.interfaces import Server as \
                ServiceServer

            # children
            srv = ServiceServer(
                    Server,
                    do_ssl = self.ssl,
                    sock_auth = (FakeAuthenticator, [], {}),
                    stdout_logging = self.stdout_logging,
                    external_cmd_classes = [Repository],
                    external_executor_cmd_classes = [(Base, [], {},)],
                    entropy_interface_kwargs = {
                        'community_repo': True,
                    }
                )
            srv.port = self.port
            try:
                srv.go()
            except (KeyboardInterrupt, SystemExit,):
                srv.killall()
                os._exit(0)

            srv.killall()
            os._exit(0)

        # ===> parent
        conn_status = self.wait_for_connection()
        self.assert_(conn_status)
        return pid

    def kill_repoman_service(self):
        if self.repoman_srv_pid:
            os.kill(self.repoman_srv_pid, signal.SIGTERM)
            os.kill(self.repoman_srv_pid, signal.SIGKILL)
            # get pid, avoid zombies
            os.waitpid(self.repoman_srv_pid, 0)

    def tearDown(self):
        """
        tearDown is run after each test
        """
        self.RepoMan.destroy()
        self.RepoMan.Service.kill_all_connections()
        self.kill_repoman_service()
        conn_status = self.wait_for_connection(i_want_conn_enabled = False)
        self.assert_(conn_status)
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def _test_glsa_data_exec(self, glsa_type):
        status, queue_id = self.RepoMan.Service.Methods.get_spm_glsa_data(
            glsa_type)
        self.assert_(status)
        self.assert_(queue_id)
        data = self.RepoMan.wait_queue_id_to_complete(queue_id)

    def test_queue(self):
        status, queue = self.RepoMan.Service.Methods.get_queue()
        self.assert_(status)
        self.assert_(isinstance(queue, dict))
        self.assert_("pause" in queue)
        self.assert_("processing_order" in queue)
        self.assert_("processing" in queue)
        self.assert_("errored_order" in queue)
        self.assert_("queue" in queue)
        self.assert_("queue_order" in queue)
        self.assert_("processed" in queue)

    def test_glsa_data_exec_all(self):
        self._test_glsa_data_exec("all")

    def test_glsa_data_exec_new(self):
        self._test_glsa_data_exec("new")

    def test_glsa_data_exec_affected(self):
        self._test_glsa_data_exec("affected")

    def test_available_repos(self):
        status, avail_repos = self.RepoMan.Service.Methods.get_available_repositories()
        self.assert_(status)
        self.assert_(avail_repos)
        self.assert_(isinstance(avail_repos, dict))
        for repo in avail_repos['available']:
            self._run_test_available_packages(repo)

    def _run_test_available_packages(self, repoid):
        status, repo_data = self.RepoMan.Service.Methods.get_available_entropy_packages(repoid)
        self.assert_(status)
        self.assert_(isinstance(repo_data, dict))
        self.assert_("ordered_idpackages" in repo_data)
        self.assert_("data" in repo_data)
        self.assert_(isinstance(repo_data["ordered_idpackages"], list))
        self.assert_(isinstance(repo_data["data"], dict))

if "__main__" == __name__:
    unittest.main()
