# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,'.')
sys.path.insert(0,'../')
import unittest
from entropy.misc import Lifo

class MiscTest(unittest.TestCase):

    def setUp(self):
        self.__lifo = Lifo()
        self._lifo_item1 = set([1, 2, 3, 4])
        self._lifo_item2 = set([1, 2, 3, 4])
        self._lifo_item3 = dict(((None,x,) for x in xrange(0, 20)))
        self._lifo_item4 = u'èòàèòà'
        self._lifo_item5 = (1, 2, 3, 4,)
        self._lifo_item6 = '------'
        self._lifo_items = [self._lifo_item1, self._lifo_item2,
            self._lifo_item3, self._lifo_item4, self._lifo_item5,
            self._lifo_item6]

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def test_lifo_push_pop(self):

        # test push
        for item in self._lifo_items:
            self.__lifo.push(item)

        # is filled?
        self.assertEqual(self.__lifo.is_filled(), True)

        # pop
        myitems = self._lifo_items[:]
        myitems.reverse()
        for item in myitems:
            lifo_item = self.__lifo.pop()
            self.assertEqual(lifo_item, item)

        # is filled?
        self.assertEqual(self.__lifo.is_filled(), False)

        # refill
        for item in self._lifo_items:
            self.__lifo.push(item)

        # is filled?
        self.assertEqual(self.__lifo.is_filled(), True)

        # discard one
        self.__lifo.discard(self._lifo_item3)

        # remove and test
        myitems.remove(self._lifo_item3)
        for item in myitems:
            lifo_item = self.__lifo.pop()
            self.assertEqual(lifo_item, item)

        # is filled?
        self.assertEqual(self.__lifo.is_filled(), False)

if __name__ == '__main__':
    unittest.main()
