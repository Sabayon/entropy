# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '../../')
sys.path.insert(0, '../../../sulfur/src')

import unittest
import gobject, gtk, gtk.gdk

from entropy.const import etpUi
from entropy.client.interfaces import Client
from sulfur.dialogs import RepositoryManagerMenu

host = 'localhost'
port = 1027
ssl = "--ssl" in sys.argv
if ssl:
    sys.argv.remove("--ssl")
username = 'root'
password = 'rootpass'

class MyRepositoryManager(RepositoryManagerMenu):

    def __init__(self, equo, parent):
        RepositoryManagerMenu.__init__(self, equo, parent)

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

# enable debug mode
etpUi['debug'] = True
CLIENT = Client()
REPOMAN = MyRepositoryManager.init(CLIENT, host,
    port, username, password, ssl)

class RepomanTest(unittest.TestCase):

    def setUp(self):
        self.RepoMan = REPOMAN

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def test_glsa_data_exec(self):
        status, queue_id = self.RepoMan.Service.Methods.get_spm_glsa_data("all")
        self.assert_(status)
        self.assert_(queue_id)
        data = self.RepoMan.wait_queue_id_to_complete(queue_id)

if "__main__" == __name__:
    unittest.main()
