#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy feeds handling functions

    Copyright (C) 2007 Fabio Erculiani

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

from entropyConstants import *
from xml.dom import minidom
import time, datetime

feed_title = etpConst['systemname']+" Online Repository Status"
feed_description = "Keep you updated on what's going on in the Official "+etpConst['systemname']+" Repository."
feed_language = "en-EN"
feed_editor = etpConst['rss-managing-editor']
feed_copyright = etpConst['systemname']+" (C) 2007-2009"

class rssFeed:
    
    def __init__(self, filename, maxentries = 100):
        
        self.file = filename
        self.items = {}
        self.itemscounter = 0
        self.maxentries = maxentries
        
        # sanity check
        broken = False
        if os.path.isfile(self.file):
            try:
                self.xmldoc = minidom.parse(self.file)
            except:
                #print "DEBUG: RSS broken, recreating in 5 seconds."
                #time.sleep(5)
                broken = True
        
        if not os.path.isfile(self.file) or broken:
            self.title = feed_title
            self.description = feed_description
            self.language = feed_language
            self.copyright = feed_copyright
            self.editor = feed_editor
            self.link = etpConst['rss-website-url']
            f = open(self.file,"w")
            f.write('')
            f.close()
        else:
            # parse file
            self.rssdoc = self.xmldoc.getElementsByTagName("rss")[0]
            self.channel = self.rssdoc.getElementsByTagName("channel")[0]
            self.title = self.channel.getElementsByTagName("title")[0].firstChild.data
            self.link = self.channel.getElementsByTagName("link")[0].firstChild.data
            self.description = self.channel.getElementsByTagName("description")[0].firstChild.data
            self.language = self.channel.getElementsByTagName("language")[0].firstChild.data
            self.copyright = self.channel.getElementsByTagName("copyright")[0].firstChild.data
            self.editor = self.channel.getElementsByTagName("managingEditor")[0].firstChild.data
            entries = self.channel.getElementsByTagName("item")
            self.itemscounter = len(entries)
            if self.itemscounter > self.maxentries:
                self.itemscounter = self.maxentries
            mycounter = self.itemscounter
            for item in entries:
                if mycounter == 0: # max entries reached
                    break
                mycounter -= 1
                self.items[mycounter] = {}
                self.items[mycounter]['title'] = item.getElementsByTagName("title")[0].firstChild.data
                description = item.getElementsByTagName("description")[0].firstChild
                if description:
                    self.items[mycounter]['description'] = description.data
                else:
                    self.items[mycounter]['description'] = ""
                link = item.getElementsByTagName("link")[0].firstChild
                if link:
                    self.items[mycounter]['link'] = link.data
                else:
                    self.items[mycounter]['link'] = ""
                self.items[mycounter]['guid'] = item.getElementsByTagName("guid")[0].firstChild.data
                self.items[mycounter]['pubDate'] = item.getElementsByTagName("pubDate")[0].firstChild.data

    def addItem(self, title, link = '', description = ''):
        self.itemscounter += 1
        self.items[self.itemscounter] = {}
        self.items[self.itemscounter]['title'] = title
        self.items[self.itemscounter]['pubDate'] = time.strftime("%a, %d %b %Y %X +0000")
        self.items[self.itemscounter]['description'] = description
        self.items[self.itemscounter]['link'] = link
        if link:
            self.items[self.itemscounter]['guid'] = link
        else:
            self.items[self.itemscounter]['guid'] = "sabayonlinux.org~"+description+str(self.itemscounter)
        return self.itemscounter
    
    def removeEntry(self, id):
        del self.items[id]
        self.itemscounter -= 1
        return len(self.itemscounter)
    
    def getEntries(self):
        return self.items, self.itemscounter

    def writeChanges(self):
        
        # filter entries to fit in maxentries
        if self.itemscounter > self.maxentries:
            tobefiltered = self.itemscounter - self.maxentries
            for index in range(tobefiltered):
                del self.items[index]
        
        doc = minidom.Document()
        
        rss = doc.createElement("rss")
        rss.setAttribute("version","2.0")
        rss.setAttribute("xmlns:atom","http://www.w3.org/2005/Atom")
        
        channel = doc.createElement("channel")
        
        # title
        title = doc.createElement("title")
        title_text = doc.createTextNode(unicode(self.title))
        title.appendChild(title_text)
        channel.appendChild(title)
        # link
        link = doc.createElement("link")
        link_text = doc.createTextNode(unicode(self.link))
        link.appendChild(link_text)
        channel.appendChild(link)
        # description
        description = doc.createElement("description")
        desc_text = doc.createTextNode(unicode(self.description))
        description.appendChild(desc_text)
        channel.appendChild(description)
        # language
        language = doc.createElement("language")
        lang_text = doc.createTextNode(unicode(self.language))
        language.appendChild(lang_text)
        channel.appendChild(language)
        # copyright
        copyright = doc.createElement("copyright")
        cr_text = doc.createTextNode(unicode(self.copyright))
        copyright.appendChild(cr_text)
        channel.appendChild(copyright)
        # managingEditor
        managingEditor = doc.createElement("managingEditor")
        ed_text = doc.createTextNode(unicode(self.editor))
        managingEditor.appendChild(ed_text)
        channel.appendChild(managingEditor)

        keys = self.items.keys()
        keys.reverse()
        for key in keys:
            # item
            item = doc.createElement("item")
            # title
            item_title = doc.createElement("title")
            item_title_text = doc.createTextNode(unicode(self.items[key]['title']))
            item_title.appendChild(item_title_text)
            item.appendChild(item_title)
            # link
            item_link = doc.createElement("link")
            item_link_text = doc.createTextNode(unicode(self.items[key]['link']))
            item_link.appendChild(item_link_text)
            item.appendChild(item_link)
            # guid
            item_guid = doc.createElement("guid")
            item_guid.setAttribute("isPermaLink","true")
            item_guid_text = doc.createTextNode(unicode(self.items[key]['guid']))
            item_guid.appendChild(item_guid_text)
            item.appendChild(item_guid)
            # description
            item_desc = doc.createElement("description")
            item_desc_text = doc.createTextNode(unicode(self.items[key]['description']))
            item_desc.appendChild(item_desc_text)
            item.appendChild(item_desc)
            # pubdate
            item_date = doc.createElement("pubDate")
            item_date_text = doc.createTextNode(unicode(self.items[key]['pubDate']))
            item_date.appendChild(item_date_text)
            item.appendChild(item_date)

            # add item to channel
            channel.appendChild(item)

        # add channel to rss
        rss.appendChild(channel)
        doc.appendChild(rss)
        f = open(self.file,"w")
        f.writelines(doc.toprettyxml(indent="    "))
        f.flush()
        f.close()

