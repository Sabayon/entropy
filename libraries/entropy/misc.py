# -*- coding: utf-8 -*-
'''
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
'''

import os
import time
import urllib2
from entropyConstants import *

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
        self.Message = Message

    def smtp_send(self, sender, destinations, message):
        s = self.smtplib.SMTP(self.smtphost,self.smtpport)
        if self.smtpuser and self.smtppassword:
            s.login(self.smtpuser,self.smtppassword)
        s.sendmail(sender, destinations, message)
        s.quit()

    def send_text_email(self, sender_email, destination_emails, subject, content):

        # Create a text/plain message
        if isinstance(content,unicode):
            content = content.encode('utf-8')
        if isinstance(subject,unicode):
            subject = subject.encode('utf-8')

        msg = self.text(content)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ', '.join(destination_emails)
        return self.default_sender(sender_email, destination_emails, msg.as_string())

    def send_mime_email(self, sender_email, destination_emails, subject, content, files):

        outer = self.multipart()
        outer['Subject'] = subject
        outer['From'] = sender_email
        outer['To'] = ', '.join(destination_emails)
        outer.preamble = subject

        mymsg = self.text(content)
        outer.attach(mymsg)

        # attach files
        for myfile in files:
            if not (os.path.isfile(myfile) and os.access(myfile,os.R_OK)):
                continue

            ctype, encoding = self.mimetypes.guess_type(myfile)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)

            if maintype == 'image':
                fp = open(myfile, 'rb')
                msg = self.image(fp.read(), _subtype = subtype)
                fp.close()
            elif maintype == 'audio':
                fp = open(myfile, 'rb')
                msg = self.audio(fp.read(), _subtype = subtype)
                fp.close()
            else:
                fp = open(myfile, 'rb')
                msg = self.mimefile(maintype, subtype)
                msg.set_payload(fp.read())
                fp.close()
                self.encoders.encode_base64(msg)

            msg.add_header('Content-Disposition', 'attachment', filename = os.path.basename(myfile))
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
        self.__GeoIP = GeoIP
        # http://www.maxmind.com/download/geoip/database/GeoLiteCity.dat.gz
        if not (os.path.isfile(geoip_dbfile) and os.access(geoip_dbfile,os.R_OK)):
            raise AttributeError(
                "expecting a valid filepath for geoip_dbfile, got: %s" % (
                    repr(geoip_dbfile),
                )
            )
        self.__geoip_dbfile = geoip_dbfile

    def __get_geo_ip_generic(self):
        return self.__GeoIP.new(self.__GeoIP.GEOIP_MEMORY_CACHE)

    def __get_geo_ip_open(self):
        return self.__GeoIP.open(self.__geoip_dbfile, self.__GeoIP.GEOIP_STANDARD)

    def get_geoip_country_name_from_ip(self, ip_address):
        """
        @return: string or None
        @param1: ip address string
        """
        gi = self.__get_geo_ip_generic()
        return gi.country_name_by_addr(ip_address)

    def get_geoip_country_code_from_ip(self, ip_address):
        """
        @return: string or None
        @param1: ip address string
        """
        gi = self.__get_geo_ip_generic()
        return gi.country_code_by_addr(ip_address)

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
        go = self.__get_geo_ip_open()
        return go.record_by_addr(ip_address)

    def get_geoip_record_from_hostname(self, hostname):
        """
        @return: dict() or None
        @param1: hostname
        """
        go = self.__get_geo_ip_open()
        return go.record_by_name(hostname)


class rssFeed:

    import entropyTools
    def __init__(self, filename, title, description, maxentries = 100):

        self.__feed_title = title
        self.__feed_title = self.__feed_title.strip()
        self.__feed_description = description
        self.__feed_language = "en-EN"
        self.__feed_editor = etpConst['rss-managing-editor']
        self.__feed_copyright = "%s - (C) %s" % (
            etpConst['systemname'],
            self.entropyTools.getYear(),
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
            self.__link = etpConst['rss-website-url']
            f = open(self.__file,"w")
            f.write('')
            f.close()
        else:
            self.__rssdoc = self.xmldoc.getElementsByTagName("rss")[0]
            self.__channel = self.__rssdoc.getElementsByTagName("channel")[0]
            self.__title = self.__channel.getElementsByTagName("title")[0].firstChild.data.strip()
            self.__link = self.__channel.getElementsByTagName("link")[0].firstChild.data.strip()
            description = self.__channel.getElementsByTagName("description")[0].firstChild
            if hasattr(description,"data"):
                self.__description = description.data.strip()
            else:
                self.__description = ''
            try:
                self.__language = self.__channel.getElementsByTagName("language")[0].firstChild.data.strip()
            except IndexError:
                self.__language = 'en'
            try:
                self.__cright = self.__channel.getElementsByTagName("copyright")[0].firstChild.data.strip()
            except IndexError:
                self.__cright = ''
            try:
                self.__editor = self.__channel.getElementsByTagName("managingEditor")[0].firstChild.data.strip()
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
                self.__items[mycounter]['title'] = item.getElementsByTagName("title")[0].firstChild.data.strip()
                description = item.getElementsByTagName("description")[0].firstChild
                if description:
                    self.__items[mycounter]['description'] = description.data.strip()
                else:
                    self.__items[mycounter]['description'] = ""
                link = item.getElementsByTagName("link")[0].firstChild
                if link:
                    self.__items[mycounter]['link'] = link.data.strip()
                else:
                    self.__items[mycounter]['link'] = ""
                self.__items[mycounter]['guid'] = item.getElementsByTagName("guid")[0].firstChild.data.strip()
                self.__items[mycounter]['pubDate'] = item.getElementsByTagName("pubDate")[0].firstChild.data.strip()
                dcs = item.getElementsByTagName("dc:creator")
                if dcs:
                    self.__items[mycounter]['dc:creator'] = dcs[0].firstChild.data.strip()

    def addItem(self, title, link = '', description = '', pubDate = ''):
        self.__itemscounter += 1
        self.__items[self.__itemscounter] = {}
        self.__items[self.__itemscounter]['title'] = title
        if pubDate:
            self.__items[self.__itemscounter]['pubDate'] = pubDate
        else:
            self.__items[self.__itemscounter]['pubDate'] = time.strftime("%a, %d %b %Y %X +0000")
        self.__items[self.__itemscounter]['description'] = description
        self.__items[self.__itemscounter]['link'] = link
        if link:
            self.__items[self.__itemscounter]['guid'] = link
        else:
            myguid = etpConst['systemname'].lower()
            myguid = myguid.replace(" ","")
            self.__items[self.__itemscounter]['guid'] = myguid+"~"+description+str(self.__itemscounter)
        return self.__itemscounter

    def removeEntry(self, id):
        if id in self.__items:
            del self.__items[id]
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
        rss.setAttribute("version","2.0")
        rss.setAttribute("xmlns:atom","http://www.w3.org/2005/Atom")

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
        managingEditor = doc.createElement("managingEditor")
        ed_text = doc.createTextNode(unicode(self.__editor))
        managingEditor.appendChild(ed_text)
        channel.appendChild(managingEditor)

        keys = self.__items.keys()
        if reverse: keys.reverse()
        for key in keys:

            # sanity check, you never know
            if not self.__items.has_key(key):
                self.removeEntry(key)
                continue
            k_error = False
            for item in ['title','link','guid','description','pubDate']:
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
            item_title_text = doc.createTextNode(unicode(self.__items[key]['title']))
            item_title.appendChild(item_title_text)
            item.appendChild(item_title)
            # link
            item_link = doc.createElement("link")
            item_link_text = doc.createTextNode(unicode(self.__items[key]['link']))
            item_link.appendChild(item_link_text)
            item.appendChild(item_link)
            # guid
            item_guid = doc.createElement("guid")
            item_guid.setAttribute("isPermaLink","true")
            item_guid_text = doc.createTextNode(unicode(self.__items[key]['guid']))
            item_guid.appendChild(item_guid_text)
            item.appendChild(item_guid)
            # description
            item_desc = doc.createElement("description")
            item_desc_text = doc.createTextNode(unicode(self.__items[key]['description']))
            item_desc.appendChild(item_desc_text)
            item.appendChild(item_desc)
            # pubdate
            item_date = doc.createElement("pubDate")
            item_date_text = doc.createTextNode(unicode(self.__items[key]['pubDate']))
            item_date.appendChild(item_date_text)
            item.appendChild(item_date)

            # add item to channel
            channel.appendChild(item)

        # add channel to rss
        rss.appendChild(channel)
        doc.appendChild(rss)
        f = open(self.__file,"w")
        f.writelines(doc.toprettyxml(indent="    ").encode('utf-8'))
        f.flush()
        f.close()

class LogFile:

    def __init__(self, level = 0, filename = None, header = "[LOG]"):
        self.handler = self.default_handler
        self.level = level
        self.header = header
        self.logFile = None
        self.open(filename)
        self.__filename = filename

    def __del__(self):
        self.close()

    def close(self):
        try:
            self.logFile.close()
        except (IOError,OSError,):
            pass

    def get_fpath(self):
        return self.__filename

    def flush(self):
        self.logFile.flush()

    def fileno(self):
        return self.getFile()

    def isatty(self):
        return False

    def read(self, a):
        return ''

    def readline(self):
        return ''

    def readlines(self):
        return []

    def seek(self, a):
        return self.logFile.seek(a)

    def tell(self):
        return self.logFile.tell()

    def truncate(self):
        return self.logFile.truncate()

    def open (self, file = None):
        if isinstance(file,basestring):
            if os.access(file,os.W_OK) and os.path.isfile(file):
                self.logFile = open(file, "aw")
            else:
                self.logFile = open("/dev/null", "aw")
        elif hasattr(file,'write'):
            self.logFile = file
        else:
            self.logFile = sys.stderr

    def getFile (self):
        return self.logFile.fileno()

    def __call__(self, format, *args):
        self.handler (format % args)

    def default_handler (self, mystr):
        try:
            self.logFile.write ("* %s\n" % (mystr))
        except UnicodeEncodeError:
            self.logFile.write ("* %s\n" % (mystr.encode('utf-8'),))
        self.logFile.flush()

    def set_loglevel(self, level):
        self.level = level

    def log(self, messagetype, level, message):
        if self.level >= level and not etpUi['nolog']:
            self.handler("%s %s %s %s" % (self.getTimeDateHeader(),messagetype,self.header,message,))

    def write(self, s):
        self.handler(s)

    def writelines(self, lst):
        for s in lst:
            self.write(s)

    def getTimeDateHeader(self):
        return time.strftime('[%H:%M:%S %d/%m/%Y %Z]')

class Callable:
    def __init__(self, anycallable):
        self.__call__ = anycallable

class MultipartPostHandler(urllib2.BaseHandler):
    handler_order = urllib2.HTTPHandler.handler_order - 10 # needs to run first

    def http_request(self, request):

        import urllib
        doseq = 1

        data = request.get_data()
        if data is not None and type(data) != str:
            v_files = []
            v_vars = []
            try:
                 for(key, value) in data.items():
                     if type(value) == file:
                         v_files.append((key, value))
                     else:
                         v_vars.append((key, value))
            except TypeError:
                raise TypeError, "not a valid non-string sequence or mapping object"

            if len(v_files) == 0:
                data = urllib.urlencode(v_vars, doseq)
            else:
                boundary, data = self.multipart_encode(v_vars, v_files)

                contenttype = 'multipart/form-data; boundary=%s' % boundary
                '''
                if (request.has_header('Content-Type')
                   and request.get_header('Content-Type').find('multipart/form-data') != 0):
                    print "Replacing %s with %s" % (request.get_header('content-type'), 'multipart/form-data')
                '''
                request.add_unredirected_header('Content-Type', contenttype)
            request.add_data(data)
        return request

    def multipart_encode(vars, files, boundary = None, buf = None):

        from cStringIO import StringIO
        import mimetools, mimetypes

        if boundary is None:
            boundary = mimetools.choose_boundary()
        if buf is None:
            buf = StringIO()
        for(key, value) in vars:
            buf.write('--%s\r\n' % boundary)
            buf.write('Content-Disposition: form-data; name="%s"' % key)
            buf.write('\r\n\r\n' + value + '\r\n')
        for(key, fd) in files:
            file_size = os.fstat(fd.fileno())[stat.ST_SIZE]
            filename = fd.name.split('/')[-1]
            contenttype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            buf.write('--%s\r\n' % boundary)
            buf.write('Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (key, filename))
            buf.write('Content-Type: %s\r\n' % contenttype)
            # buffer += 'Content-Length: %s\r\n' % file_size
            fd.seek(0)
            buf.write('\r\n' + fd.read() + '\r\n')
        buf.write('--' + boundary + '--\r\n\r\n')
        buf = buf.getvalue()
        return boundary, buf
    multipart_encode = Callable(multipart_encode)

    https_request = http_request

