# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework miscellaneous module}.

    This module contains miscellaneous classes, not directly
    related with the "Entropy metaphor".

"""
import os
import sys
import time
import tempfile
if sys.hexversion >= 0x3000000:
    import urllib.request, urllib.error, urllib.parse
    UrllibBaseHandler = urllib.request.BaseHandler
else:
    import urllib
    import urllib2
    UrllibBaseHandler = urllib2.BaseHandler
import logging
import threading
from collections import deque
from entropy.const import etpConst, const_isunicode, \
    const_isfileobj, const_convert_log_level

import entropy.tools


class Lifo(object):

    """

    This class can be used to build LIFO buffers, also commonly
    known as "stacks". I{Lifo} allows you to store and retrieve
    Python objects from its stack, in a very smart way.
    This implementation is much faster than the one provided
    by Python (queue module) and more sofisticated.

    Sample code:

        >>> # load Lifo
        >>> from entropy.misc import Lifo
        >>> stack = Lifo()
        >>> item1 = set([1,2,3])
        >>> item2 = ["a","b", "c"]
        >>> item3 = None
        >>> item4 = 1
        >>> stack.push(item4)
        >>> stack.push(item3)
        >>> stack.push(item2)
        >>> stack.push(item1)
        >>> stack.is_filled()
        True
        # discarding all the item matching int(1) in the stack
        >>> stack.discard(1)
        >>> item3 is stack.pop()
        True
        >>> item2 is stack.pop()
        True
        >>> item1 is stack.pop()
        True
        >>> stack.pop()
        ValueError exception (stack is empty)
        >>> stack.is_filled()
        False
        >>> del stack

    """

    def __init__(self):
        """ Lifo class constructor """
        object.__init__(self)
        self.__buf = deque()

    def __nonzero__(self):
        """
        Return if stack is empty.
        """
        return len(self.__buf) != 0

    def __len__(self):
        """
        Return stack size.
        """
        return len(self.__buf)

    def push(self, item):
        """
        Push an object into the stack.

        @param item: any Python object
        @type item: Python object
        @return: None
        @rtype: None
        """
        self.__buf.append(item)

    def insert(self, item):
        """
        Insert item at the bottom of the stack.

        @param item: any Python object
        @type item: Python object
        @return: None
        @rtype: None
        """
        self.__buf.appendleft(item)

    def clear(self):
        """
        Clear the stack.

        @return: None
        @rtype: None
        """
        self.__buf.clear()

    def is_filled(self):
        """
        Tell whether Lifo contains data that can be popped out.

        @return: fill status
        @rtype: bool
        """
        if self.__buf:
            return True
        return False

    def discard(self, entry):
        """
        Remove given object from stack. Any matching object,
        through identity and == comparison will be removed.

        @param entry: object in stack
        @type entry: any Python object
        @return: None
        @rtype: None
        """
        indexes = []
        while True:
            try:
                self.__buf.remove(entry)
            except ValueError:
                break

    def pop(self):
        """
        Pop the uppermost item of the stack out of it.

        @return: object stored in the stack
        @rtype: any Python object
        @raise ValueError: if stack is empty
        """
        try:
            return self.__buf.pop()
        except IndexError:
            raise ValueError("Lifo is empty")


class TimeScheduled(threading.Thread):

    """
    Multithreading class that wraps Python threading.Thread.
    Specifically, this class implements the timed function execution
    concept. It means that you can run timed functions (say every N
    seconds) and control its execution through another (main?) thread.

    It is possible to set arbitrary, variable, delays and decide if to delay
    before or after the execution of the function provided at construction
    time.
    Timed function can be stopped by calling TimeScheduled.kill() method.
    You may find the example below more exhaustive:

        >>> from entropy.misc import TimeScheduled
        >>> time_sched = TimeSheduled(5, print, "hello world", 123)
        >>> time_sched.start()
        hello world 123 # every 5 seconds
        hello world 123 # every 5 seconds
        hello world 123 # every 5 seconds
        >>> time_sched.kill()

    """

    def __init__(self, delay, *args, **kwargs):
        """
        TimeScheduled constructor.

        @param delay: delay in seconds between a function call and another.
        @type delay: float
        @param *args: function as first magic arg and its arguments
        @keyword *kwargs: keyword arguments of the function passed
        @return: None
        @rtype: None
        """
        threading.Thread.__init__(self)
        self.__f = args[0]
        self.__delay = delay
        self.__args = args[1:][:]
        self.__kwargs = kwargs.copy()
        # never enable this by default
        # otherwise kill() and thread
        # check will hang until
        # time.sleep() is done
        self.__accurate = False
        self.__delay_before = False
        self.__alive = 0
        self.__paused = False
        self.__paused_delay = 2

    def pause(self, pause):
        """
        Pause current internal timer countdown.

        @param pause: True to pause timer
        @type pause: bool
        """
        self.__paused = pause

    def set_delay(self, delay):
        """
        Change current delay in seconds.

        @param delay: new delay
        @type delay: float
        @return: None
        @rtype: None
        """
        self.__delay = delay

    def set_delay_before(self, delay_before):
        """
        Set whether delay before the execution of the function or not.

        @param delay_before: delay before boolean
        @type delay_before: bool
        @return: None
        @rtype: None
        """
        self.__delay_before = bool(delay_before)

    def set_accuracy(self, accuracy):
        """
        Set whether delay function must be accurate or not.

        @param accuracy: accuracy boolean
        @type accuracy: bool
        @return: None
        @rtype: None
        """
        self.__accurate = bool(accuracy)

    def run(self):
        """
        This method is called automatically when start() is called.
        Don't call this directly!!!
        """
        self.__alive = 1
        while self.__alive:

            if self.__delay_before:
                do_break = self.__do_delay()
                if do_break:
                    break

            if self.__f == None:
                break
            try:
                self.__f(*self.__args, **self.__kwargs)
            except KeyboardInterrupt:
                break

            if not self.__delay_before:
                do_break = self.__do_delay()
                if do_break:
                    break


    def __do_delay(self):

        """ Executes the delay """
        while self.__paused:
            if time == None:
                return True
            time.sleep(self.__paused_delay)

        if not self.__accurate:

            if float == None:
                return True
            mydelay = float(self.__delay)
            t_frac = 0.3
            while mydelay > 0.0:
                if not self.__alive:
                    return True
                if time == None:
                    return True # shut down?
                time.sleep(t_frac)
                mydelay -= t_frac

        else:

            if time == None:
                return True # shut down?
            time.sleep(self.__delay)

        return False

    def kill(self):
        """ Stop the execution of the timed function """
        self.__alive = 0

class ParallelTask(threading.Thread):

    """
    Multithreading class that wraps Python threading.Thread.
    Specifically, this class makes possible to easily execute a function
    on a separate thread.

    Python threads can't be stopped, paused or more generically arbitrarily
    controlled.

        >>> from entropy.misc import ParallelTask
        >>> parallel = ParallelTask(print, "hello world", 123)
        >>> parallel.start()
        hello world 123
        >>> parallel.kill()

    """

    def __init__(self, *args, **kwargs):
        """
        ParallelTask constructor

        Provide a function and its arguments as arguments of this constructor.
        """
        threading.Thread.__init__(self)
        self.__function = args[0]
        self.__args = args[1:][:]
        self.__kwargs = kwargs.copy()
        self.__rc = None

    def run(self):
        """
        This method is called automatically when start() is called.
        Don't call this directly!!!
        """
        self.__rc = self.__function(*self.__args, **self.__kwargs)

    def get_function(self):
        """
        Return the function passed to constructor that is going to be executed.

        @return: parallel function
        @rtype: Python callable object
        """
        return self.__function

    def get_rc(self):
        """
        Return result of the last parallel function call passed to constructor.

        @return: parallel function result
        @rtype: Python object
        """
        return self.__rc


class MasterSlaveLock(object):

    DEBUG = False

    def __init__(self):
        self.__locks = {}
        self.__ms_action_lock = threading.Lock()
        self.__locks_dict_lock = threading.Lock()
        self.__master_locked = False
        self.__master_is_locking = False
        self.__spin_count = 0

    @staticmethod
    def log(*args):
        txt = ' '.join([str(x) for x in args])
        sys.stdout.write(txt + "\n")
        sys.stdout.flush()

    def slave_acquire(self, key, timeout = None):
        if MasterSlaveLock.DEBUG:
            MasterSlaveLock.log("calling slave_acquire", key)
        with self.__locks_dict_lock:
            lock = self.__locks.setdefault(key, threading.Lock())

        # setup "else" case variables here to reduce transaction length below.
        acquired = False
        timeout_secs = 1
        if timeout is not None:
            timeout_secs = int(timeout)
            if timeout_secs < 1:
                # guard value
                timeout_secs = 1

        with self.__ms_action_lock:
            if self.__master_locked or self.__master_is_locking:
                # master locked us, give up
                return False
            elif lock.locked() and not self.__master_locked:
                # slave locked, we're fine
                # NOTE: it can happen to allow one more acquire() on the lock
                # while master is locking, this is fine, the case is handled
                # in master_acquire().
                self.__spin_count += 1
                if MasterSlaveLock.DEBUG:
                    MasterSlaveLock.log("DEBUG: new spin count (++1)",
                        self.__spin_count)
                return True
            else:
                # if lock is not locked, first time slave gets here
                # spin_count here must be 0.

                while timeout_secs > 0:
                    # non blocking if timeout is not None
                    # blocking otherwise.
                    acquired = lock.acquire(timeout is None)
                    if timeout is None:
                        # if we get here, lock is acquired when in blocking mode
                        acquired = True
                        break
                    if not acquired:
                        timeout_secs -= 1
                        time.sleep(1)
                        continue
                    break
                if acquired:
                    self.__spin_count += 1
                    if MasterSlaveLock.DEBUG:
                        MasterSlaveLock.log("DEBUG: new spin count (++2)",
                            self.__spin_count)
                    return True
                else: # otherwise, give up.
                    return False

    def slave_release(self, key):
        if MasterSlaveLock.DEBUG:
            MasterSlaveLock.log("calling slave_release", key)
        with self.__locks_dict_lock:
            lock = self.__locks.setdefault(key, threading.Lock())

        with self.__ms_action_lock:
            if (self.__spin_count - 1) < 1:
                # release only if master did not acquire
                if self.__master_locked:
                    # don't do anything, don't release the lock!
                    pass
                elif self.__master_is_locking:
                    # if master is locking, release the lock
                    # even if master already acquired it.
                    # This race condition will be handled by master.
                    lock.release()
                # otherwise do nothing
            self.__spin_count -= 1
            if MasterSlaveLock.DEBUG:
                MasterSlaveLock.log("DEBUG: new spin count (--)",
                    self.__spin_count)

    def master_acquire(self, key):
        # Acquire the lock, then wait for every slave to release before
        # returning
        if MasterSlaveLock.DEBUG:
            MasterSlaveLock.log("calling master_acquire", key)
        with self.__locks_dict_lock:
            lock = self.__locks.setdefault(key, threading.Lock())

        self.__master_is_locking = True
        while True:
            acquired = lock.acquire(False) # non blocking, wait indefinitely
            if not acquired:
                if MasterSlaveLock.DEBUG:
                    MasterSlaveLock.log(
                        "still waiting for master_acquire, lock acquire", key)
                time.sleep(1.0)
                continue
            break

        # from now on, new requests from slaves won't accepted, since
        # the acquisition and the enable of master_locked are not atomic
        # we'll have to wait until all the slave requests are flushed out.
        # this is done below, in the while loop.
        self.__master_locked = True
        # -- race condition here, handled below --
        self.__master_is_locking = False
        # now make sure we still hold the lock, unsing a non-blocking acquire
        # if it fails, it's because we are still holding the lock
        # if it succeeds, it means that the last slave released a lock.
        lock.acquire(False)

        # wait for slaves to terminate before returning
        while self.__spin_count > 0:
            time.sleep(0.4)
            if MasterSlaveLock.DEBUG:
                MasterSlaveLock.log(
                    "waiting for slaves to terminate, slaves:",
                        self.__spin_count)

    def master_release(self, key):
        # This can only happen when no slave is holding the lock
        # and master locked.
        if MasterSlaveLock.DEBUG:
            MasterSlaveLock.log("calling master_release", key)
        # must be available, otherwise KeyError is raised
        with self.__locks_dict_lock:
            self.__locks[key].release()
        self.__master_locked = False


class EmailSender:

    """
    This class implements a very simple e-mail (through SMTP) sender.
    It is used by the User Generated Content interface and something more.

    You can swap the sender function at runtime, by redefining
    EmailSender.default_sender. By default, default_sender is set to
    EmailSender.smtp_send.

    Sample code:

        >>> sender = EmailSender()
        >>> sender.send_text_email("me@test.com", ["him@test.com"], "hello!",
            "this is the content")
        ...
        >>> sender = EmailSender()
        >>> sender.send_mime_email("me@test.com", ["him@test.com"], "hello!",
            "this is the content", ["/path/to/file1", "/path/to/file2"])

    """

    def __init__(self):

        """ EmailSender constructor """

        import smtplib
        self.smtplib = smtplib
        from email.mime.audio import MIMEAudio
        from email.mime.image import MIMEImage
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email import encoders
        from email.message import Message
        import mimetypes
        self.smtpuser = None
        self.smtppassword = None
        self.smtphost = 'localhost'
        self.smtpport = 25
        self.text = MIMEText
        self.mimefile = MIMEBase
        self.audio = MIMEAudio
        self.image = MIMEImage
        self.multipart = MIMEMultipart
        self.default_sender = self.smtp_send
        self.mimetypes = mimetypes
        self.encoders = encoders
        self.message = Message

    def smtp_send(self, sender, destinations, message):
        """
        This is the default method for sending emails.
        It uses Python's smtplib module.
        You should not use this function directly.

        @param sender: sender email address
        @type sender: string
        @param destinations: list of recipients
        @type destinations: list of string
        @param message: message to send
        @type message: string

        @return: None
        @rtype: None
        """
        s_srv = self.smtplib.SMTP(self.smtphost, self.smtpport)
        if self.smtpuser and self.smtppassword:
            s_srv.login(self.smtpuser, self.smtppassword)
        s_srv.sendmail(sender, destinations, message)
        s_srv.quit()

    def send_text_email(self, sender_email, destination_emails, subject,
        content):
        """
        This method exposes an easy way to send textual emails.

        @param sender_email: sender email address
        @type sender_email: string
        @param destination_emails: list of recipients
        @type destination_emails: list
        @param subject: email subject
        @type subject: string
        @param content: email content
        @type content: string

        @return: None
        @rtype: None
        """
        # Create a text/plain message
        if sys.hexversion < 0x3000000:
            if const_isunicode(content):
                content = content.encode('utf-8')
            if const_isunicode(subject):
                subject = subject.encode('utf-8')
        else:
            if not const_isunicode(content):
                raise AttributeError("content must be unicode (str)")
            if not const_isunicode(subject):
                raise AttributeError("subject must be unicode (str)")

        msg = self.text(content)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ', '.join(destination_emails)
        return self.default_sender(sender_email, destination_emails,
            msg.as_string())

    def send_mime_email(self, sender_email, destination_emails, subject,
            content, files):
        """
        This method exposes an easy way to send complex emails (with
        attachments).

        @param sender_email: sender email address
        @type sender_email: string
        @param destination_emails: list of recipients
        @type destination_emails: list of string
        @param subject: email subject
        @type subject: string
        @param content: email content
        @type content: string
        @param files: list of valid file paths
        @type files: list

        @return: None
        @rtype: None
        """
        outer = self.multipart()
        outer['Subject'] = subject
        outer['From'] = sender_email
        outer['To'] = ', '.join(destination_emails)
        outer.preamble = subject

        mymsg = self.text(content)
        outer.attach(mymsg)

        # attach files
        for myfile in files:
            if not (os.path.isfile(myfile) and os.access(myfile, os.R_OK)):
                continue

            ctype, encoding = self.mimetypes.guess_type(myfile)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)

            if maintype == 'image':
                img_f = open(myfile, 'rb')
                msg = self.image(img_f.read(), _subtype = subtype)
                img_f.close()
            elif maintype == 'audio':
                audio_f = open(myfile, 'rb')
                msg = self.audio(audio_f.read(), _subtype = subtype)
                audio_f.close()
            else:
                gen_f = open(myfile, 'rb')
                msg = self.mimefile(maintype, subtype)
                msg.set_payload(gen_f.read())
                gen_f.close()
                self.encoders.encode_base64(msg)

            msg.add_header('Content-Disposition', 'attachment',
                filename = os.path.basename(myfile))
            outer.attach(msg)

        composed = outer.as_string()
        return self.default_sender(sender_email, destination_emails, composed)

class EntropyGeoIP:

    """
    Entropy geo-tagging interface containing useful methods to ease
    metadata management and transformation.
    It's a wrapper over GeoIP at the moment dev-python/geoip-python
    required.

    Sample code:

        >>> geo = EntropyGeoIp("mygeoipdb.dat")
        >>> geo.get_geoip_record_from_ip("123.123.123.123")
        { dict() metadata }

    """

    def __init__(self, geoip_dbfile):

        """
        EntropyGeoIP constructor.

        @param geoip_dbfile: valid GeoIP (Maxmind) database file (.dat) path
            (download from:
            http://www.maxmind.com/download/geoip/database/GeoLiteCity.dat.gz)
        @type geoip_dbfile: string
        """

        import GeoIP
        self.__geoip = GeoIP
        # http://www.maxmind.com/download/geoip/database/GeoLiteCity.dat.gz
        if not (os.path.isfile(geoip_dbfile) and \
            os.access(geoip_dbfile, os.R_OK)):
            raise AttributeError(
                "expecting a valid filepath for geoip_dbfile, got: %s" % (
                    repr(geoip_dbfile),
                )
            )
        self.__geoip_dbfile = geoip_dbfile

    def __get_geo_ip_generic(self):
        """ Private method """
        return self.__geoip.new(self.__geoip.GEOIP_MEMORY_CACHE)

    def __get_geo_ip_open(self):
        """ Private method """
        return self.__geoip.open(self.__geoip_dbfile,
            self.__geoip.GEOIP_STANDARD)

    def get_geoip_country_name_from_ip(self, ip_address):
        """
        Get country name from IP address.

        @param ip_address: ip address string
        @type ip_address: string
        @return: country name or None
        @rtype: string or None
        """
        gi_a = self.__get_geo_ip_generic()
        return gi_a.country_name_by_addr(ip_address)

    def get_geoip_country_code_from_ip(self, ip_address):
        """
        Get country code from IP address.

        @param ip_address: ip address string
        @type ip_address: string
        @return: country code or None
        @rtype: string or None
        """
        gi_a = self.__get_geo_ip_generic()
        return gi_a.country_code_by_addr(ip_address)

    def get_geoip_record_from_ip(self, ip_address):
        """
        Get GeoIP record from IP address.

        @param ip_address: ip address string
        @type ip_address: string
        @return: GeoIP record data
        @rtype: dict
        """
        go_a = self.__get_geo_ip_open()
        return go_a.record_by_addr(ip_address)

    def get_geoip_record_from_hostname(self, hostname):
        """
        Get GeoIP record from hostname.

        @param hostname: ip address string
        @type hostname: string
        @return: GeoIP record data
        @rtype: dict
        """
        go_a = self.__get_geo_ip_open()
        return go_a.record_by_name(hostname)


class RSS:

    """

    This is a base class for handling RSS (XML) files through Python's
    xml.dom.minidom module. It produces 100% W3C-complaint code.

    This class is meant to be used inside the Entropy world, it's not meant
    for other tasks outside this codebase.

    """

    def __init__(self, filename, title, description, maxentries = 100):

        """
        RSS constructor

        @param filename: RSS file path (a new file will be created if not found)
        @type filename: string
        @param title: RSS feed title (used for new RSS files)
        @type title: string
        @param description: RSS feed description (used for new RSS files)
        @type description: string
        @keyword maxentries: max RSS feed entries
        @type maxentries: int
        """

        from entropy.core.settings.base import SystemSettings
        self.__system_settings = SystemSettings()
        self.__feed_title = title
        self.__feed_title = self.__feed_title.strip()
        self.__feed_description = description
        self.__feed_language = "en-EN"
        self.__srv_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        srv_settings = self.__system_settings.get(self.__srv_settings_plugin_id)
        if srv_settings is None:
            self.__feed_editor = "N/A"
        else:
            self.__feed_editor = srv_settings['server']['rss']['editor']
        self.__feed_copyright = "%s - (C) %s" % (
            self.__system_settings['system']['name'],
            entropy.tools.get_year(),
        )

        self.__file = filename
        self.__items = {}
        self.__itemscounter = 0
        self.__maxentries = maxentries
        from xml.dom import minidom
        self.minidom = minidom

        # sanity check
        broken = False
        if os.path.isfile(self.__file):
            try:
                self.xmldoc = self.minidom.parse(self.__file)
            except:
                broken = True

        if not os.path.isfile(self.__file) or broken:

            self.__title = self.__feed_title
            self.__description = self.__feed_description
            self.__language = self.__feed_language
            self.__cright = self.__feed_copyright
            self.__editor = self.__feed_editor
            sys_set = self.__system_settings.get(self.__srv_settings_plugin_id)
            if sys_set is None:
                self.__link = etpConst['rss-website-url']
            else:
                srv_set = sys_set['server']
                self.__link = srv_set['rss']['website_url']

        else:

            self.__rssdoc = self.xmldoc.getElementsByTagName("rss")[0]
            self.__channel = self.__rssdoc.getElementsByTagName("channel")[0]
            title_obj = self.__channel.getElementsByTagName("title")[0]
            self.__title = title_obj.firstChild.data.strip()
            link_obj = self.__channel.getElementsByTagName("link")[0]
            self.__link = link_obj.firstChild.data.strip()
            desc_obj = self.__channel.getElementsByTagName("description")[0]
            description = desc_obj.firstChild
            if hasattr(description, "data"):
                self.__description = description.data.strip()
            else:
                self.__description = ''
            try:
                lang_obj = self.__channel.getElementsByTagName("language")[0]
                self.__language = lang_obj.firstChild.data.strip()
            except IndexError:
                self.__language = 'en'
            try:
                cright_obj = self.__channel.getElementsByTagName("copyright")[0]
                self.__cright = cright_obj.firstChild.data.strip()
            except IndexError:
                self.__cright = ''
            try:
                e_obj = self.__channel.getElementsByTagName("managingEditor")[0]
                self.__editor = e_obj.firstChild.data.strip()
            except IndexError:
                self.__editor = ''
            entries = self.__channel.getElementsByTagName("item")
            self.__itemscounter = len(entries)
            if self.__itemscounter > self.__maxentries:
                self.__itemscounter = self.__maxentries
            mycounter = self.__itemscounter
            for item in entries:
                if mycounter == 0: # max entries reached
                    break
                mycounter -= 1
                self.__items[mycounter] = {}
                title_obj = item.getElementsByTagName("title")[0]
                self.__items[mycounter]['title'] = \
                    title_obj.firstChild.data.strip()
                desc_obj = item.getElementsByTagName("description")
                description = None
                if desc_obj:
                    description = desc_obj[0].firstChild
                if description:
                    self.__items[mycounter]['description'] = \
                        description.data.strip()
                else:
                    self.__items[mycounter]['description'] = ""

                link = item.getElementsByTagName("link")[0].firstChild
                if link:
                    self.__items[mycounter]['link'] = link.data.strip()
                else:
                    self.__items[mycounter]['link'] = ""

                guid_obj = item.getElementsByTagName("guid")[0]
                self.__items[mycounter]['guid'] = \
                    guid_obj.firstChild.data.strip()
                pub_date_obj = item.getElementsByTagName("pubDate")[0]
                self.__items[mycounter]['pubDate'] = \
                    pub_date_obj.firstChild.data.strip()
                dcs = item.getElementsByTagName("dc:creator")
                if dcs:
                    self.__items[mycounter]['dc:creator'] = \
                        dcs[0].firstChild.data.strip()


    def add_item(self, title, link = '', description = '', pubDate = ''):
        """
        Add new entry to RSS feed.

        @param title: entry title
        @type title: string
        @keyword link: entry link
        @type link: string
        @keyword description: entry description
        @type description: string
        @keyword pubDate: entry publication date
        @type pubDate: string
        """

        self.__itemscounter += 1
        self.__items[self.__itemscounter] = {}
        self.__items[self.__itemscounter]['title'] = title
        if pubDate:
            self.__items[self.__itemscounter]['pubDate'] = pubDate
        else:
            self.__items[self.__itemscounter]['pubDate'] = \
                time.strftime("%a, %d %b %Y %X +0000")
        self.__items[self.__itemscounter]['description'] = description
        self.__items[self.__itemscounter]['link'] = link
        if link:
            self.__items[self.__itemscounter]['guid'] = link
        else:
            myguid = self.__system_settings['system']['name'].lower()
            myguid = myguid.replace(" ", "")
            self.__items[self.__itemscounter]['guid'] = myguid+"~" + \
                description + str(self.__itemscounter)
        return self.__itemscounter

    def remove_entry(self, key):
        """
        Remove entry from RSS feed through its index number.

        @param key: entry index number.
        @type key: int
        @return: new entry count
        @rtype: int
        """
        if key in self.__items:
            del self.__items[key]
            self.__itemscounter -= 1
        return self.__itemscounter

    def get_entries(self):
        """
        Get entries and their total number.

        @return: tuple composed by items (list of dict) and total items count
        @rtype: tuple
        """
        return self.__items, self.__itemscounter

    def write_changes(self, reverse = True):
        """
        Writes changes to file.

        @keyword reverse: write entries in reverse order.
        @type reverse: bool
        @return: None
        @rtype: None
        """

        # filter entries to fit in maxentries
        if self.__itemscounter > self.__maxentries:
            tobefiltered = self.__itemscounter - self.__maxentries
            for index in range(tobefiltered):
                try:
                    del self.__items[index]
                except KeyError:
                    pass

        doc = self.minidom.Document()

        rss = doc.createElement("rss")
        rss.setAttribute("version", "2.0")
        rss.setAttribute("xmlns:atom", "http://www.w3.org/2005/Atom")

        channel = doc.createElement("channel")

        # title
        title = doc.createElement("title")
        title_text = doc.createTextNode(self.__title)
        title.appendChild(title_text)
        channel.appendChild(title)
        # link
        link = doc.createElement("link")
        link_text = doc.createTextNode(self.__link)
        link.appendChild(link_text)
        channel.appendChild(link)
        # description
        description = doc.createElement("description")
        desc_text = doc.createTextNode(self.__description)
        description.appendChild(desc_text)
        channel.appendChild(description)
        # language
        language = doc.createElement("language")
        lang_text = doc.createTextNode(self.__language)
        language.appendChild(lang_text)
        channel.appendChild(language)
        # copyright
        cright = doc.createElement("copyright")
        cr_text = doc.createTextNode(self.__cright)
        cright.appendChild(cr_text)
        channel.appendChild(cright)
        # managingEditor
        managing_editor = doc.createElement("managingEditor")
        ed_text = doc.createTextNode(self.__editor)
        managing_editor.appendChild(ed_text)
        channel.appendChild(managing_editor)

        keys = list(self.__items.keys())
        if reverse:
            keys.reverse()
        for key in keys:

            # sanity check, you never know
            if key not in self.__items:
                self.remove_entry(key)
                continue
            k_error = False
            for item in ('title', 'link', 'guid', 'description', 'pubDate',):
                if item not in self.__items[key]:
                    k_error = True
                    break
            if k_error:
                self.remove_entry(key)
                continue

            # item
            item = doc.createElement("item")
            # title
            item_title = doc.createElement("title")
            item_title_text = doc.createTextNode(
                self.__items[key]['title'])
            item_title.appendChild(item_title_text)
            item.appendChild(item_title)
            # link
            item_link = doc.createElement("link")
            item_link_text = doc.createTextNode(
                self.__items[key]['link'])
            item_link.appendChild(item_link_text)
            item.appendChild(item_link)
            # guid
            item_guid = doc.createElement("guid")
            item_guid.setAttribute("isPermaLink", "true")
            item_guid_text = doc.createTextNode(
                self.__items[key]['guid'])
            item_guid.appendChild(item_guid_text)
            item.appendChild(item_guid)
            # description
            item_desc = doc.createElement("description")
            item_desc_text = doc.createTextNode(
                self.__items[key]['description'])
            item_desc.appendChild(item_desc_text)
            item.appendChild(item_desc)
            # pubdate
            item_date = doc.createElement("pubDate")
            item_date_text = doc.createTextNode(
                self.__items[key]['pubDate'])
            item_date.appendChild(item_date_text)
            item.appendChild(item_date)

            # add item to channel
            channel.appendChild(item)

        # add channel to rss
        rss.appendChild(channel)
        doc.appendChild(rss)
        rss_f = open(self.__file, "w")
        rss_f.writelines(doc.toprettyxml(indent="    ").encode('utf-8'))
        rss_f.flush()
        rss_f.close()


class FastRSS:

    """

    This is a fast class for handling RSS files through Python's
    xml.dom.minidom module. It produces 100% W3C-complaint code.
    Any functionality exposed works in O(1) time (apart from commit()
    which is O(n)).
    """

    BASE_TITLE = "No title"
    BASE_DESCRIPTION = "No description"
    BASE_EDITOR = "No editor"
    BASE_URL = etpConst['distro_website_url']
    MAX_ENTRIES = -1
    LANGUAGE = "en-EN"

    def __init__(self, rss_file_path):
        """
        RSS constructor

        @param rss_file_path: RSS file path (a new file will be created
            if not found)
        @type rss_file_path: string
        """
        from entropy.core.settings.base import SystemSettings
        self.__system_settings = SystemSettings()
        self.__feed_title = FastRSS.BASE_TITLE
        self.__feed_description = FastRSS.BASE_DESCRIPTION
        self.__feed_language = FastRSS.LANGUAGE
        self.__feed_editor = FastRSS.BASE_EDITOR
        self.__system_name = self.__system_settings['system']['name']
        self.__feed_year = entropy.tools.get_year()
        self.__title_changed = False
        self.__link_updated = False
        self.__description_updated = False
        self.__language_updated = False
        self.__year_updated = False
        self.__editor_updated = False
        self.__doc = None

        self.__file = rss_file_path
        self.__items = []
        self.__itemscounter = 0
        self.__maxentries = FastRSS.MAX_ENTRIES
        self.__link = FastRSS.BASE_URL

        from xml.dom import minidom
        self.__minidom = minidom

        self.__newly_created = not (os.path.isfile(self.__file) and \
            os.access(self.__file, os.R_OK | os.F_OK))

    def is_new(self):
        """
        Return whether the file has been newly created or not

        @return: True, if rss is new
        @rtype: bool
        """
        return self.__newly_created

    def set_title(self, title):
        """
        Set feed title

        @param title: rss feed title
        @type title: string
        @return: this instance, for chaining
        """
        self.__title_changed = True
        self.__feed_title = title
        return self

    def set_language(self, language):
        """
        Set feed language

        @param title: rss language
        @type title: string
        @return: this instance, for chaining
        """
        self.__language_updated = True
        self.__feed_language = language
        return self

    def set_description(self, description):
        """
        Set feed description

        @param description: rss feed description
        @type description: string
        @return: this instance, for chaining
        """
        self.__description_updated = True
        self.__feed_description = description
        return self

    def set_max_entries(self, max_entries):
        """
        Set the maximum amount of rss feed entries, -1 for infinity

        @param description: rss feed max entries value
        @type description: int
        @return: this instance, for chaining
        """
        self.__maxentries = max_entries
        return self

    def set_editor(self, editor):
        """
        Set rss feed editor name

        @param editor: rss feed editor name
        @type editor: string
        @return: this instance, for chaining
        """
        self.__editor_updated = True
        self.__feed_editor = editor
        return self

    def set_url(self, url):
        """
        Set rss feed url name

        @param url: rss feed url
        @type url: string
        @return: this instance, for chaining
        """
        self.__link_updated = True
        self.__link = url
        return self

    def set_year(self, year):
        """
        Set rss feed copyright year

        @param url: rss feed copyright year
        @type url: string
        @return: this instance, for chaining
        """
        self.__year_updated = True
        self.__feed_year = year
        return self

    def append(self, title, link, description, pub_date):
        """
        Add new entry

        @param title: entry title
        @type title: string
        @param link: entry link
        @type link: string
        @param description: entry description
        @type description: string
        @param pubDate: entry publication date
        @type pubDate: string
        """
        meta = {
            "title": title,
            "pubDate": pub_date or time.strftime("%a, %d %b %Y %X +0000"),
            "description": description or "",
            "link": link or "",
            "guid": link or "",
        }
        self.__items.append(meta)

    def get(self):
        """
        Return xml.minidom Document object.

        @return: the Document object
        @rtype: xml.dom.Document object
        """
        if self.__doc is not None:
            return self.__doc

        is_new = self.is_new()

        feed_copyright = "%s - (C) %s" % (
            self.__system_name, self.__feed_year,
        )

        if not is_new:
            doc = self.__minidom.parse(self.__file)
            rss = doc.getElementsByTagName("rss")[0]
            channel = doc.getElementsByTagName("channel")[0]

            titles = doc.getElementsByTagName("title")
            if not titles:
                title = doc.createElement("title")
                title.appendChild(doc.createTextNode(self.__feed_title))
                channel.appendChild(title)
            else:
                title = titles[0]

            links = doc.getElementsByTagName("link")
            if not links:
                link = doc.createElement("link")
                link.appendChild(doc.createTextNode(self.__link))
                channel.appendChild(link)
            else:
                link = links[0]

            descriptions = doc.getElementsByTagName("description")
            if not descriptions:
                description = doc.createElement("description")
                description.appendChild(doc.createTextNode(
                    self.__feed_description))
                channel.appendChild(description)
            else:
                description = descriptions[0]

            languages = doc.getElementsByTagName("language")
            if not languages:
                language = doc.createElement("language")
                language.appendChild(doc.createTextNode(self.__feed_language))
                channel.appendChild(language)
            else:
                language = languages[0]

            crights = doc.getElementsByTagName("copyright")
            if not crights:
                cright = doc.createElement("copyright")
                cright.appendChild(doc.createTextNode(feed_copyright))
                channel.appendChild(cright)
            else:
                cright = crights[0]

            editors = doc.getElementsByTagName("managingEditor")
            if not editors:
                editor = doc.createElement("managingEditor")
                editor.appendChild(doc.createTextNode(self.__feed_editor))
                channel.appendChild(editor)
            else:
                editor = editors[0]

            # update title
            if self.__title_changed:
                title.removeChild(title.firstChild)
                title.appendChild(doc.createTextNode(self.__feed_title))
                self.__title_changed = False

            # update link
            if self.__link_updated:
                link.removeChild(link.firstChild)
                link.appendChild(doc.createTextNode(self.__link))
                self.__link_updated = False

            # update description
            if self.__description_updated:
                description.removeChild(description.firstChild)
                description.appendChild(doc.createTextNode(
                    self.__feed_description))
                self.__description_updated = False
            # update language
            if self.__language_updated:
                language.removeChild(language.firstChild)
                language.appendChild(doc.createTextNode(self.__feed_language))
                self.__language_updated = False
            # update copyright
            if self.__year_updated:
                cright.removeChild(cright.firstChild)
                cright.appendChild(doc.createTextNode(feed_copyright))
                self.__year_updated = False
            # update managingEditor, if required
            if self.__editor_updated:
                editor.removeChild(editor.firstChild)
                editor.appendChild(doc.createTextNode(self.__feed_editor))
                self.__editor_updated = False
        else:
            doc = self.__minidom.Document()
            rss = doc.createElement("rss")
            rss.setAttribute("version", "2.0")
            rss.setAttribute("xmlns:atom", "http://www.w3.org/2005/Atom")
            channel = doc.createElement("channel")
            # title
            title = doc.createElement("title")
            title.appendChild(doc.createTextNode(self.__feed_title))
            channel.appendChild(title)
            # link
            link = doc.createElement("link")
            link.appendChild(doc.createTextNode(self.__link))
            channel.appendChild(link)
            # description
            description = doc.createElement("description")
            description.appendChild(doc.createTextNode(self.__feed_description))
            channel.appendChild(description)
            # language
            language = doc.createElement("language")
            language.appendChild(doc.createTextNode(self.__feed_language))
            channel.appendChild(language)
            # copyright
            cright = doc.createElement("copyright")
            cright.appendChild(doc.createTextNode(feed_copyright))
            channel.appendChild(cright)
            # managingEditor
            editor = doc.createElement("managingEditor")
            editor.appendChild(doc.createTextNode(self.__feed_editor))
            channel.appendChild(editor)

        rss.appendChild(channel)
        doc.appendChild(rss)
        self.__doc = doc
        return doc

    def commit(self):
        """
        Commit changes to file
        """
        doc = self.get()
        channel = doc.getElementsByTagName("channel")[0]

        # append new items at the bottom
        while self.__items:
            meta = self.__items.pop(0)
            item = doc.createElement("item")

            for key in meta.keys():
                obj = doc.createElement(key)
                obj.appendChild(doc.createTextNode(meta[key]))
                item.appendChild(obj)

            channel.appendChild(item)

        if self.__maxentries > 0:
            # drop older ones, from the top
            how_many = len(channel.childNodes)
            to_remove = how_many - self.__maxentries
            while to_remove > 0:
                child_nodes = channel.childNodes
                if not child_nodes:
                    break
                node = child_nodes[0]
                channel.removeChild(node)
                node.unlink()
                to_remove -= 1

        tmp_fd, tmp_path = tempfile.mkstemp(prefix="entropy.misc.FastRSS.",
            dir = os.path.dirname(self.__file))
        with os.fdopen(tmp_fd, "wb") as rss_f:
            rss_f.writelines(doc.toprettyxml(indent="    ").encode("UTF-8"))
            rss_f.flush()
        os.rename(tmp_path, self.__file)


class LogFile:

    """ Entropy simple logging interface, works as file object """

    LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL
    }
    LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s"
    DATE_FORMAT = "[%H:%M:%S %d/%m/%Y %Z]"

    def __init__(self, level = None, filename = None, header = "[LOG]"):
        """
        LogFile constructor.

        @keyword level: any valid Entropy log level id (0, 1, 2).
            0: error logging, 1: normal logging, 2: debug logging
        @type level: int
        @keyword filename: log file path
        @type filename: string
        @keyword header: log line header
        @type header: string
        """
        if level is not None:
            logger_level = const_convert_log_level(level)
        else:
            logger_level = logging.INFO
        self.__filename = filename
        self.__header = header

        self.__logger = logging.getLogger(os.path.basename(self.__filename))
        self.__level = LogFile.LEVELS.get(logger_level)
        self.__logger.setLevel(logging.DEBUG)

        if self.__filename is not None:
            try:
                self.__handler = logging.FileHandler(self.__filename)
            except (IOError, OSError):
                self.__handler = logging.StreamHandler()
        else:
            self.__handler = logging.StreamHandler()
        if self.__level is not None:
            self.__handler.setLevel(self.__level)
        self.__handler.setFormatter(logging.Formatter(LogFile.LOG_FORMAT,
            LogFile.DATE_FORMAT))
        self.__logger.addHandler(self.__handler)

    def __enter__(self):
        """
        Just return self, configuration is done in __init__
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Make sure any resource is closed.
        """
        self.flush()
        self.close()

    def fileno(self):
        return self.__handler.stream.fileno()

    def flush(self):
        """ Flush log buffer """
        if hasattr(self.__handler, 'flush'):
            self.__handler.flush()

    def __del__(self):
        self.close()

    def close(self):
        """ Close log file """
        if self.__handler is not None:
            if hasattr(self.__handler, 'close'):
                self.__handler.close()
            self.__logger.removeHandler(self.__handler)
            self.__handler = None
            self.__logger = None

    def _handler(self, mystr):
        """
        Default log file writer. This can be reimplemented.

        @param mystr: log string to write
        @type mystr: string
        @param level: logging level
        @type level: string
        """
        self.__get_logger()
        try:
            self.__get_logger()(mystr)
        except UnicodeEncodeError:
            self.__get_logger()(mystr.encode('utf-8'))

    def log(self, messagetype, level, message):
        """
        This is the effective function that LogFile consumers should use.

        @param messagetype: message type (or tag)
        @type messagetype: string
        @param level: minimum logging threshold which should trigger the
            effective write
        @type level: int
        @param message: log message
        @type message: string
        """
        self._handler("%s %s %s" % (messagetype, self.__header, message,))

    def write(self, mystr):
        """
        File object method, write log message to file using the default
        handler set (LogFile.default_handler is the default).

        @param mystr: log string to write
        @type mystr: string
        """
        self._handler(mystr)

    def writelines(self, lst):
        """
        File object method, write log message strings to file using the default
        handler set (LogFile.default_handler is the default).

        @param lst: list of strings to write
        @type lst: list
        """
        for line in lst:
            self.write(line)

    def __get_logger(self):
        logger_map = {
            logging.INFO: self.__logger.info,
            logging.WARNING: self.__logger.warning,
            logging.DEBUG: self.__logger.debug,
            logging.ERROR: self.__logger.error,
            logging.CRITICAL: self.__logger.error,
            logging.NOTSET: self.__logger.info,
        }
        return logger_map.get(self.__level, self.__logger.info)


class Callable:
    """
    Fake class wrapping any callable object into a callable class.
    """
    def __init__(self, anycallable):
        """
        Callable constructor.

        @param anycallable: any callable object
        @type callable: callable
        """
        self.__call__ = anycallable

class MultipartPostHandler(UrllibBaseHandler):

    """
    Custom urllib2 opener used in the Entropy codebase.
    """

    # needs to run first
    if sys.hexversion >= 0x3000000:
        handler_order = urllib.request.HTTPHandler.handler_order - 10
    else:
        handler_order = urllib2.HTTPHandler.handler_order - 10

    def __init__(self):
        """
        MultipartPostHandler constructor.
        """
        pass

    def http_request(self, request):

        """
        Entropy codebase internal method. Not for re-use.

        @param request: urllib2 HTTP request object
        """

        doseq = 1

        data = request.get_data()
        if data is not None and not isinstance(data, str):
            v_files = []
            v_vars = []
            try:
                for (key, value) in list(data.items()):
                    if const_isfileobj(value):
                        v_files.append((key, value))
                    else:
                        v_vars.append((key, value))
            except TypeError:
                raise TypeError("not a valid non-string sequence" \
                        " or mapping object")

            if len(v_files) == 0:
                if sys.hexversion >= 0x3000000:
                    data = urllib.parse.urlencode(v_vars, doseq)
                else:
                    data = urllib.urlencode(v_vars, doseq)
            else:
                boundary, data = self.multipart_encode(v_vars, v_files)
                contenttype = 'multipart/form-data; boundary=%s' % boundary
                request.add_unredirected_header('Content-Type', contenttype)

            request.add_data(data)
        return request

    def multipart_encode(self, myvars, files, boundary = None, buf = None):

        """
        Does the effective multipart mime encoding. Entropy codebase internal
        method. Not for re-use.
        """

        from io import StringIO
        import mimetools, mimetypes
        #import stat

        if boundary is None:
            boundary = mimetools.choose_boundary()
        if buf is None:
            buf = StringIO()
        for(key, value) in myvars:
            buf.write('--%s\r\n' % boundary)
            buf.write('Content-Disposition: form-data; name="%s"' % key)
            buf.write('\r\n\r\n' + value + '\r\n')
        for(key, fdesc) in files:
            #file_size = os.fstat(fdesc.fileno())[stat.ST_SIZE]
            filename = fdesc.name.split('/')[-1]
            contenttype = mimetypes.guess_type(filename)[0] or \
                'application/octet-stream'
            buf.write('--%s\r\n' % boundary)
            buf.write('Content-Disposition: form-data; name="%s"; ' \
                'filename="%s"\r\n' % (key, filename))
            buf.write('Content-Type: %s\r\n' % contenttype)
            # buffer += 'Content-Length: %s\r\n' % file_size
            fdesc.seek(0)
            buf.write('\r\n' + fdesc.read() + '\r\n')
        buf.write('--' + boundary + '--\r\n\r\n')
        buf = buf.getvalue()
        return boundary, buf

    multipart_encode = Callable(multipart_encode)

    https_request = http_request

