#!/usr/bin/python
'''
    # DESCRIPTION:
    # load/save a data to file by dumping its structure

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

import sys
import commands
sys.path.append('../libraries')
from xml.dom import minidom
from entropyConstants import *

'''
   @description: dump object to file
   @input: name of the object, object
   @output: status code
'''
def dumpobj(name,object):
    doc = minidom.Document()
    structure = doc.createElement("structure")
    doc.appendChild(structure)
    data = doc.createElement("data")
    structure.appendChild(data)
    text = doc.createTextNode(unicode(object))
    data.appendChild(text)
    # etpConst['dumpstoragedir']
    try:
	if not os.path.isdir(etpConst['dumpstoragedir']):
	    os.makedirs(etpConst['dumpstoragedir'])
        f = open(etpConst['dumpstoragedir']+"/"+name+".dmp","w") #FIXME add check
        f.writelines(doc.toprettyxml(indent="  "))
        f.flush()
        f.close()
    except:
        raise IOError,"can't write to file"


'''
   @description: load object from a file
   @input: name of the object
   @output: object or, if error -1
'''
def loadobj(name):
    dmpfile = etpConst['dumpstoragedir']+"/"+name+".dmp"
    if os.path.isfile(dmpfile):
	try:
	    xmldoc = minidom.parse(dmpfile)
	    structure = xmldoc.firstChild
	    data = structure.childNodes[1]
	    x = eval(data.firstChild.data.strip())
	    return x
	except:
	    os.remove(dmpfile)
	    raise SyntaxError,"cannot load object"