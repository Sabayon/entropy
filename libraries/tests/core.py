# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'client')
sys.path.insert(0, '../../client')
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
from entropy.core import EntropyPluginStore, Singleton
import tests._misc as _misc

class CoreTest(unittest.TestCase):

    def setUp(self):
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def test_plugin_store(self):

        store = EntropyPluginStore()
        plug_object = object()
        plug_id = "plug"

        store.add_plugin(plug_id, plug_object)
        self.assertEqual(store.get_plugins(), {plug_id: plug_object})

        store.remove_plugin(plug_id)
        self.assertEqual(store.get_plugins(), {})

        store.add_plugin(plug_id, plug_object)
        self.assertEqual(store.get_plugins(), {plug_id: plug_object})
        store.drop_plugins()
        self.assertEqual(store.get_plugins(), {})

    def test_core_singleton(self):
        class myself(Singleton):
            def init_singleton(self):
                pass

        obj = myself()
        obj2 = myself()
        self.assert_(obj is obj2)


if __name__ == '__main__':
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        from entropy.const import etpUi
        etpUi['debug'] = True
    unittest.main()
