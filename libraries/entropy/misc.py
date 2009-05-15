# -*- coding: utf-8 -*-
"""
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
"""
# pylink ok - doc
from __future__ import with_statement
import os
import sys
import time
import urllib2
import threading
from entropy.const import etpConst, etpUi
from entropy.core import SystemSettings

class Lifo:

    def __init__(self):
        self.__buf = {}

    def push(self, item):
        try:
            idx = max(self.__buf)+1
        except ValueError:
            idx = 0
        self.__buf[idx] = item

    def clear(self):
        self.__buf.clear()

    def is_filled(self):
        if self.__buf:
            return True
        return False

    def discard(self, entry):
        for key, buf_entry in self.__buf.items():
            # identity is generally faster, so try
            # this first
            if entry is buf_entry:
                self.__buf.pop(key)
                continue
            if entry == buf_entry:
                self.__buf.pop(key)
                continue

    def pop(self):
        try:
            idx = max(self.__buf)
        except ValueError:
            return None
        return self.__buf.pop(idx)

class TimeScheduled(threading.Thread):

    def __init__(self, delay, *args, **kwargs):
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
        self.__delay = delay

    def set_delay_before(self, bool_do):
        self.__delay_before = bool(bool_do)

    def set_accuracy(self, bool_do):
        self.__accurate = bool(bool_do)

    def run(self):
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
        self.__alive = 0

class ParallelTask(threading.Thread):

    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self)
        self.__function = args[0]
        self.__args = args[1:][:]
        self.__kwargs = kwargs.copy()
        self.__rc = None

    def run(self):
        self.__rc = self.__function(*self.__args, **self.__kwargs)

    def get_function(self):
        return self.__function

    def get_rc(self):
        return self.__rc

class EmailSender:

    def __init__(self):
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
        s_srv = self.smtplib.SMTP(self.smtphost, self.smtpport)
        if self.smtpuser and self.smtppassword:
            s_srv.login(self.smtpuser, self.smtppassword)
        s_srv.sendmail(sender, destinations, message)
        s_srv.quit()

    def send_text_email(self, sender_email, destination_emails, subject,
        content):

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
        Entropy geo-tagging interface containing useful
        methods to ease metadata management and transfor-
        mation.
        It's a wrapper over GeoIP at the moment
        dev-python/geoip-python required
    """

    def __init__(self, geoip_dbfile):

        """
        @param1: valid GeoIP (Maxmind) database file (.dat)
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
        return self.__geoip.new(self.__geoip.GEOIP_MEMORY_CACHE)

    def __get_geo_ip_open(self):
        return self.__geoip.open(self.__geoip_dbfile,
            self.__geoip.GEOIP_STANDARD)

    def get_geoip_country_name_from_ip(self, ip_address):
        """
        @return: string or None
        @param1: ip address string
        """
        gi_a = self.__get_geo_ip_generic()
        return gi_a.country_name_by_addr(ip_address)

    def get_geoip_country_code_from_ip(self, ip_address):
        """
        @return: string or None
        @param1: ip address string
        """
        gi_a = self.__get_geo_ip_generic()
        return gi_a.country_code_by_addr(ip_address)

    def get_geoip_record_from_ip(self, ip_address):
        """
        @return: dict() or None
        @param1: ip address string
        dict data:
            {
                'city': 'Treviso',
                'region': '20',
                'area_code': 0,
                'longitude': 12.244999885559082,
                'country_code3': 'ITA',
                'latitude': 45.666698455810547,
                'postal_code': None,
                'dma_code': 0,
                'country_code': 'IT',
                'country_name': 'Italy'
            }
        """
        go_a = self.__get_geo_ip_open()
        return go_a.record_by_addr(ip_address)

    def get_geoip_record_from_hostname(self, hostname):
        """
        @return: dict() or None
        @param1: hostname
        """
        go_a = self.__get_geo_ip_open()
        return go_a.record_by_name(hostname)


class rssFeed:

    # this is a relative import to avoid circular deps
    import tools as entropyTools
    def __init__(self, filename, title, description, maxentries = 100):

        self.__system_settings = SystemSettings()
        self.__feed_title = title
        self.__feed_title = self.__feed_title.strip()
        self.__feed_description = description
        self.__feed_language = "en-EN"
        self.__srv_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        self.__feed_editor = self.__system_settings[self.__srv_settings_plugin_id]['server']['rss']['editor']
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
            self.__link = self.__system_settings[self.__srv_settings_plugin_id]['server']['rss']['website_url']
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
                desc_obj = item.getElementsByTagName("description")[0]
                description = desc_obj.firstChild
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

    def addItem(self, title, link = '', description = '', pubDate = ''):
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

    def removeEntry(self, key):
        if key in self.__items:
            del self.__items[key]
            self.__itemscounter -= 1
        return self.__itemscounter

    def getEntries(self):
        return self.__items, self.__itemscounter

    def writeChanges(self, reverse = True):

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
                self.removeEntry(key)
                continue
            k_error = False
            for item in ('title', 'link', 'guid', 'description', 'pubDate',):
                if not self.__items[key].has_key(item):
                    k_error = True
                    break
            if k_error:
                self.removeEntry(key)
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

    def __init__(self, level = 0, filename = None, header = "[LOG]"):
        self.handler = self.default_handler
        self.level = level
        self.header = header
        self.__logfile = None
        self.open(filename)
        self.__filename = filename

    def __del__(self):
        self.close()

    def close(self):
        try:
            self.__logfile.close()
        except (IOError, OSError,):
            pass

    def get_fpath(self):
        return self.__filename

    def flush(self):
        self.__logfile.flush()

    def fileno(self):
        return self.__get_file()

    def isatty(self):
        return False

    def read(self, *args):
        return ''

    def readline(self):
        return ''

    def readlines(self):
        return []

    def seek(self, offset):
        return self.__logfile.seek(offset)

    def tell(self):
        return self.__logfile.tell()

    def truncate(self):
        return self.__logfile.truncate()

    def open(self, file_path = None):

        if isinstance(file_path, basestring):
            if not os.access(file_path, os.F_OK) and os.access(
                os.path.dirname(file_path), os.W_OK):
                self.__logfile = open(file_path, "aw")
            else:
                if os.access(file_path, os.W_OK | os.F_OK):
                    self.__logfile = open(file_path, "aw")
                else:
                    self.__logfile = open("/dev/null", "aw")
        elif hasattr(file_path, 'write'):
            self.__logfile = file_path
        else:
            self.__logfile = sys.stderr

    def __get_file(self):
        return self.__logfile.fileno()

    def __call__(self, format, *args):
        self.handler (format % args)

    def default_handler (self, mystr):
        try:
            self.__logfile.write ("* %s\n" % (mystr))
        except UnicodeEncodeError:
            self.__logfile.write ("* %s\n" % (mystr.encode('utf-8'),))
        self.__logfile.flush()

    def set_loglevel(self, level):
        self.level = level

    def log(self, messagetype, level, message):
        if self.level >= level and not etpUi['nolog']:
            self.handler("%s %s %s %s" % (self.__get_header(),
                messagetype, self.header, message,))

    def write(self, line):
        self.handler(line)

    def writelines(self, lst):
        for line in lst:
            self.write(line)

    def __get_header(self):
        return time.strftime('[%H:%M:%S %d/%m/%Y %Z]')

class Callable:
    def __init__(self, anycallable):
        self.__call__ = anycallable

class MultipartPostHandler(urllib2.BaseHandler):

    handler_order = urllib2.HTTPHandler.handler_order - 10 # needs to run first

    def __init__(self):
        pass

    def http_request(self, request):

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

