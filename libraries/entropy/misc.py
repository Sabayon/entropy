# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework miscellaneous module}.

    This module contains miscellaneous classes, not directly
    related with the "Entropy metaphor".

"""
from __future__ import with_statement
import os
import sys
import time
import urllib2
import threading
from entropy.const import etpConst, etpUi
from entropy.core import SystemSettings

class Lifo:

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
        self.__buf = {}

    def push(self, item):
        """
        Push an object into the stack.

        @param item: any Python object
        @type item: Python object
        @return: None
        @rtype: None
        """
        try:
            idx = max(self.__buf)+1
        except ValueError:
            idx = 0
        self.__buf[idx] = item

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
        for key, buf_entry in self.__buf.items():
            # identity is generally faster, so try
            # this first
            if self.__buf is None: # shutting down py
                break
            if entry is buf_entry:
                self.__buf.pop(key)
                continue
            if entry == buf_entry:
                self.__buf.pop(key)
                continue

    def pop(self):
        """
        Pop the uppermost item of the stack out of it.

        @return: object stored in the stack
        @rtype: any Python object
        @raise ValueError: if stack is empty
        """
        try:
            idx = max(self.__buf)
        except (ValueError, TypeError,):
            raise ValueError("Lifo is empty")
        try:
            return self.__buf.pop(idx)
        except (KeyError, TypeError,):
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
            self.__f(*self.__args, **self.__kwargs)

            if not self.__delay_before:
                do_break = self.__do_delay()
                if do_break:
                    break


    def __do_delay(self):

        """ Executes the delay """

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
        if isinstance(content, unicode):
            content = content.encode('utf-8')
        if isinstance(subject, unicode):
            subject = subject.encode('utf-8')

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

    # this is a relative import to avoid circular deps
    import entropy.tools as entropyTools
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
            self.entropyTools.get_year(),
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
            rss_f = open(self.__file, "w")
            rss_f.write('')
            rss_f.flush()
            rss_f.close()

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
        title_text = doc.createTextNode(unicode(self.__title))
        title.appendChild(title_text)
        channel.appendChild(title)
        # link
        link = doc.createElement("link")
        link_text = doc.createTextNode(unicode(self.__link))
        link.appendChild(link_text)
        channel.appendChild(link)
        # description
        description = doc.createElement("description")
        desc_text = doc.createTextNode(unicode(self.__description))
        description.appendChild(desc_text)
        channel.appendChild(description)
        # language
        language = doc.createElement("language")
        lang_text = doc.createTextNode(unicode(self.__language))
        language.appendChild(lang_text)
        channel.appendChild(language)
        # copyright
        cright = doc.createElement("copyright")
        cr_text = doc.createTextNode(unicode(self.__cright))
        cright.appendChild(cr_text)
        channel.appendChild(cright)
        # managingEditor
        managing_editor = doc.createElement("managingEditor")
        ed_text = doc.createTextNode(unicode(self.__editor))
        managing_editor.appendChild(ed_text)
        channel.appendChild(managing_editor)

        keys = self.__items.keys()
        if reverse:
            keys.reverse()
        for key in keys:

            # sanity check, you never know
            if not self.__items.has_key(key):
                self.remove_entry(key)
                continue
            k_error = False
            for item in ('title', 'link', 'guid', 'description', 'pubDate',):
                if not self.__items[key].has_key(item):
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
                unicode(self.__items[key]['title']))
            item_title.appendChild(item_title_text)
            item.appendChild(item_title)
            # link
            item_link = doc.createElement("link")
            item_link_text = doc.createTextNode(
                unicode(self.__items[key]['link']))
            item_link.appendChild(item_link_text)
            item.appendChild(item_link)
            # guid
            item_guid = doc.createElement("guid")
            item_guid.setAttribute("isPermaLink", "true")
            item_guid_text = doc.createTextNode(
                unicode(self.__items[key]['guid']))
            item_guid.appendChild(item_guid_text)
            item.appendChild(item_guid)
            # description
            item_desc = doc.createElement("description")
            item_desc_text = doc.createTextNode(
                unicode(self.__items[key]['description']))
            item_desc.appendChild(item_desc_text)
            item.appendChild(item_desc)
            # pubdate
            item_date = doc.createElement("pubDate")
            item_date_text = doc.createTextNode(
                unicode(self.__items[key]['pubDate']))
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

class LogFile:

    """ Entropy simple logging interface, works as file object """

    def __init__(self, level = 0, filename = None, header = "[LOG]"):
        """
        LogFile constructor.

        @keyword level: log level threshold which will trigger effective write
            on log file
        @type level: int
        @keyword filename: log file path
        @type filename: string
        @keyword header: log line header
        @type header: string
        """
        self.handler = self.default_handler
        self.level = level
        self.header = header
        self._logfile = None
        self.open(filename)
        self.__filename = filename

    def __del__(self):
        self.close()

    def close(self):
        """ Close log file """
        try:
            self._logfile.close()
        except (IOError, OSError,):
            pass

    def get_fpath(self):
        """ Get log file path """
        return self.__filename

    def flush(self):
        """ Flush log file buffer to disk """
        self._logfile.flush()

    def fileno(self):
        """
        Get log file descriptor number

        @return: file descriptor number
        @rtype: int
        """
        return self.__get_file()

    def isatty(self):
        """
        Return whether LogFile works like a tty

        @return: is a tty?
        @rtype: bool
        """
        return False

    def read(self, *args):
        """
        Fake method (exposed for file object compatibility)

        @return: empty string
        @rtype: string
        """
        return ''

    def readline(self):
        """
        Fake method (exposed for file object compatibility)

        @return: empty string
        @rtype: string
        """
        return ''

    def readlines(self):
        """
        Fake method (exposed for file object compatibility)

        @return: empty list
        @rtype: list
        """
        return []

    def seek(self, offset):
        """
        File object method, move file object cursor at offset

        @return: new file object position
        @rtype: int
        """
        return self._logfile.seek(offset)

    def tell(self):
        """
        File object method, tell file object position

        @return: file object position
        @rtype: int
        """
        return self._logfile.tell()

    def truncate(self):
        """
        File object method, truncate file buffer.
        """
        return self._logfile.truncate()

    def open(self, file_path = None):
        """
        Open log file, if possible, otherwise redirect to /dev/null or stderr.

        @keyword file_path: path to file
        @type file_path: string
        """
        if isinstance(file_path, basestring):
            if not os.access(file_path, os.F_OK) and os.access(
                os.path.dirname(file_path), os.W_OK):
                self._logfile = open(file_path, "aw")
            else:
                if os.access(file_path, os.W_OK | os.F_OK):
                    self._logfile = open(file_path, "aw")
                else:
                    self._logfile = open("/dev/null", "aw")
        elif hasattr(file_path, 'write'):
            self._logfile = file_path
        else:
            self._logfile = sys.stderr

    def __get_file(self):
        return self._logfile.fileno()

    def __call__(self, format, *args):
        self.handler (format % args)

    def default_handler(self, mystr):
        """
        Default log file writer. This can be reimplemented.

        @param mystr: log string to write
        @type mystr: string
        """
        try:
            self._logfile.write ("* %s\n" % (mystr))
        except UnicodeEncodeError:
            self._logfile.write ("* %s\n" % (mystr.encode('utf-8'),))
        self._logfile.flush()

    def set_loglevel(self, level):
        """
        Change logging threshold.

        @param level: new logging threshold
        @type level: int
        """
        self.level = level

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
        if self.level >= level and not etpUi['nolog']:
            self.handler("%s %s %s %s" % (self.__get_header(),
                messagetype, self.header, message,))

    def write(self, mystr):
        """
        File object method, write log message to file using the default
        handler set (LogFile.default_handler is the default).

        @param mystr: log string to write
        @type mystr: string
        """
        self.handler(mystr)

    def writelines(self, lst):
        """
        File object method, write log message strings to file using the default
        handler set (LogFile.default_handler is the default).

        @param lst: list of strings to write
        @type lst: list
        """
        for line in lst:
            self.write(line)

    def __get_header(self):
        return time.strftime('[%H:%M:%S %d/%m/%Y %Z]')

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

class MultipartPostHandler(urllib2.BaseHandler):

    """
    Custom urllib2 opener used in the Entropy codebase.
    """

    handler_order = urllib2.HTTPHandler.handler_order - 10 # needs to run first

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

        import urllib
        doseq = 1

        data = request.get_data()
        if data is not None and type(data) != str:
            v_files = []
            v_vars = []
            try:
                for (key, value) in data.items():
                    if type(value) == file:
                        v_files.append((key, value))
                    else:
                        v_vars.append((key, value))
            except TypeError:
                raise TypeError, "not a valid non-string sequence" \
                        " or mapping object"

            if len(v_files) == 0:
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

        from cStringIO import StringIO
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

