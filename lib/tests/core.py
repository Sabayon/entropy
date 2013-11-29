# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'client')
sys.path.insert(0, '../../client')
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
from entropy.core import EntropyPluginStore, Singleton
from entropy.core.settings.base import SystemSettings
import tests._misc as _misc

class CoreTest(unittest.TestCase):

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

    def test_plugin_updatable_config_files(self):
        sys_set = SystemSettings()
        files = sys_set.get_updatable_configuration_files(None)
        self.assertTrue(isinstance(files, set))
        self.assertTrue(files) # not empty

    def test_core_singleton(self):
        class myself(Singleton):
            def init_singleton(self):
                pass

        obj = myself()
        obj2 = myself()
        self.assertTrue(obj is obj2)


if __name__ == '__main__':
    unittest.main()
    raise SystemExit(0)
