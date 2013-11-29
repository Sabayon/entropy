# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import os
import unittest
import tempfile
import json
from entropy.const import const_convert_to_unicode
from entropy.misc import Lifo, TimeScheduled, ParallelTask, EmailSender, \
    FastRSS, FlockFile

class MiscTest(unittest.TestCase):

    def setUp(self):
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

    """
    XXX: causes random lock ups
    def test_timesched(self):

        self.t_sched_run = False
        def do_t():
            self.t_sched_run = True

        t = TimeScheduled(5, do_t)
        t.start()
        t.kill()
        t.join()
        self.assertTrue(self.t_sched_run)
    """

    def test_parallel_task(self):

        self.t_sched_run = False
        def do_t():
            import time
            time.sleep(1)
            self.t_sched_run = True

        t = ParallelTask(do_t)
        t.start()
        t.join()
        self.assertTrue(self.t_sched_run)

    def test_flock_file(self):
        tmp_fd, tmp_path = None, None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(prefix="entropy.misc.test")
            mf = FlockFile(tmp_path, fd = tmp_fd)
            mf.acquire_exclusive()
            mf.demote()
            mf.promote()
            mf.release()
            mf.acquire_shared()
            mf.release()
            mf.close()
        finally:
            if tmp_fd is not None:
                self.assertRaises(OSError, os.close, tmp_fd)
            if tmp_path is not None:
                os.remove(tmp_path)

    def test_email_sender(self):

        mail_sender = 'test@test.com'
        mail_recipients = ['test@test123.com']
        mail_sub = 'hello'
        mail_msg = 'stfu\nstfu\n'

        def def_send(sender, dest, message):
            self.assertEqual(mail_sender, sender)
            self.assertEqual(mail_recipients, dest)
            self.assertTrue(message.endswith(mail_msg))

        sender = EmailSender()
        sender.default_sender = def_send
        sender.send_text_email(mail_sender, mail_recipients, mail_sub, mail_msg)

    def test_fast_rss(self):
        tmp_fd, tmp_path = tempfile.mkstemp()
        os.close(tmp_fd) # who cares
        os.remove(tmp_path)

        fast_rss = FastRSS(tmp_path)
        self.assertTrue(fast_rss.is_new())
        fast_rss.set_title("title").set_editor("editor").set_description(
            "description").set_url("http://url").set_year("2011")
        fast_rss.append("title1", "link1", "description1", "1")
        fast_rss.append("title", "link", "description", "0")
        fast_rss.append("title2", "link2", "description2", "2")
        fast_rss.commit()

        expected_outcome = """
<?xml version="1.0" ?>
  <rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>title</title>
    <link>http://url</link>
    <description>description</description>
    <language>en-EN</language>
    <copyright>Sabayon Linux - (C) 2011</copyright>
    <managingEditor>editor</managingEditor>
    <item>
      <description>description1</description>
      <guid>link1</guid>
      <link>link1</link>
      <pubDate>1</pubDate>
      <title>title1</title>
    </item>
    <item>
      <description>description</description>
      <guid>link</guid>
      <link>link</link><pubDate>0</pubDate>
      <title>title</title>
    </item>
    <item>
      <description>description2</description>
      <guid>link2</guid>
      <link>link2</link>
      <pubDate>2</pubDate>
      <title>title2</title>
    </item>
  </channel>
</rss>"""
        with open(tmp_path, "r") as tmp_f:
            self.assertEqual(
                expected_outcome.replace(" ", "").replace("\n", ""),
                tmp_f.read().replace(" ", "").replace("\n", ""))

        # make sure metadata doesn't get screwed
        fast_rss = FastRSS(tmp_path)
        self.assertFalse(fast_rss.is_new())
        fast_rss.commit()
        with open(tmp_path, "r") as tmp_f:
            self.assertEqual(
                expected_outcome.replace(" ", "").replace("\n", ""),
                tmp_f.read().replace(" ", "").replace("\n", ""))

        os.remove(tmp_path)

    def test_fast_rss_json_payload(self):
        tmp_fd, tmp_path = tempfile.mkstemp()
        os.close(tmp_fd) # who cares
        os.remove(tmp_path)

        fast_rss = FastRSS(tmp_path)
        self.assertTrue(fast_rss.is_new())
        fast_rss.set_title("title").set_editor("editor").set_description(
            "description").set_url("http://url").set_year("2011")

        desc_data = {
            "name": "hello.world",
            "security": False,
            "number": 123,
            "float": 123.0,
            "list": [1,2,3],
        }
        fast_rss.append("title1", "link1", json.dumps(desc_data), "1")
        fast_rss.commit()

        doc = fast_rss.get()
        channel = doc.getElementsByTagName("channel").item(0)
        item = channel.getElementsByTagName("item").item(0)
        desc = item.getElementsByTagName("description").item(0)
        json_data = desc.firstChild.data.strip()
        desc_data_out = json.loads(json_data)
        self.assertEqual(desc_data, desc_data_out)
        del doc

        # test append
        fast_rss = FastRSS(tmp_path)
        self.assertFalse(fast_rss.is_new())
        fast_rss.append("title2", "link2", json.dumps(desc_data), "2")
        fast_rss.commit()
        doc = fast_rss.get()
        channel = doc.getElementsByTagName("channel").item(0)
        items = channel.getElementsByTagName("item")
        self.assertEqual(len(items), 2)
        for item in items:
            desc = item.getElementsByTagName("description").item(0)
            json_data = desc.firstChild.data.strip()
            desc_data_out = json.loads(json_data)
            self.assertEqual(desc_data, desc_data_out)

        os.remove(tmp_path)


if __name__ == '__main__':
    unittest.main()
    raise SystemExit(0)
