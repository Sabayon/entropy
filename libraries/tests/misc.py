# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
from entropy.const import const_convert_to_unicode
from entropy.misc import Lifo, TimeScheduled, ParallelTask, EmailSender

class MiscTest(unittest.TestCase):

    def setUp(self):
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()
        self.__lifo = Lifo()
        self._lifo_item1 = set([1, 2, 3, 4])
        self._lifo_item2 = set([1, 2, 3, 4])
        self._lifo_item3 = dict(((None, x,) for x in range(0, 20)))
        self._lifo_item4 = const_convert_to_unicode('èòàèòà', 'utf-8')
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
        # test if it raises ValueError exception
        self.assertRaises(ValueError, self.__lifo.pop)


    def test_timesched(self):

        self.t_sched_run = False
        def do_t():
            self.t_sched_run = True

        t = TimeScheduled(0.1, do_t)
        t.set_delay_before(True)
        t.start()
        t.kill()
        t.join()
        self.assert_(self.t_sched_run)

    def test_parallel_task(self):

        self.t_sched_run = False
        def do_t():
            import time
            time.sleep(1)
            self.t_sched_run = True
            #print "parallel done"

        t = ParallelTask(do_t)
        t.start()
        #print "joining"
        t.join()
        #print "joined"
        self.assert_(self.t_sched_run)

    def test_email_sender(self):

        mail_sender = 'test@test.com'
        mail_recipients = ['test@test123.com']
        mail_sub = 'hello'
        mail_msg = 'stfu\nstfu\n'

        def def_send(sender, dest, message):
            self.assertEqual(mail_sender, sender)
            self.assertEqual(mail_recipients, dest)
            self.assert_(message.endswith(mail_msg))

        sender = EmailSender()
        sender.default_sender = def_send
        sender.send_text_email(mail_sender, mail_recipients, mail_sub, mail_msg)

if __name__ == '__main__':
    unittest.main()
