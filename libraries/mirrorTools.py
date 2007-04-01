#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy Mirrors interface

    Copyright (C) 2007 Fabio Erculiani

    This program is free software; you can entropyTools.redistribute it and/or modify
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

# Never do "import portage" here, please use entropyTools binding
# EXIT STATUSES: 700-799

from entropyConstants import *
import entropyTools
import string

class handlerFTP:

    # ftp://linuxsabayon:asdasd@silk.dreamhost.com/sabayon.org
    # this must be run before calling the other functions
    def __init__(self, ftpuri):
	
	from ftplib import FTP
	
	self.ftpuri = ftpuri
	
	self.ftphost = entropyTools.extractFTPHostFromUri(self.ftpuri)
	
	self.ftpuser = ftpuri.split("ftp://")[len(ftpuri.split("ftp://"))-1].split(":")[0]
	if (self.ftpuser == ""):
	    self.ftpuser = "anonymous@"
	    self.ftppassword = "anonymous"
	else:
	    self.ftppassword = ftpuri.split("@")[:len(ftpuri.split("@"))-1]
	    if len(self.ftppassword) > 1:
		import string
		self.ftppassword = string.join(self.ftppassword,"@")
		self.ftppassword = self.ftppassword.split(":")[len(self.ftppassword.split(":"))-1]
		if (self.ftppassword == ""):
		    self.ftppassword = "anonymous"
	    else:
		self.ftppassword = self.ftppassword[0]
		self.ftppassword = self.ftppassword.split(":")[len(self.ftppassword.split(":"))-1]
		if (self.ftppassword == ""):
		    self.ftppassword = "anonymous"
	
	self.ftpport = ftpuri.split(":")[len(ftpuri.split(":"))-1]
	try:
	    self.ftpport = int(self.ftpport)
	except:
	    self.ftpport = 21
	
	self.ftpdir = ftpuri.split("ftp://")[len(ftpuri.split("ftp://"))-1]
	self.ftpdir = self.ftpdir.split("/")[len(self.ftpdir.split("/"))-1]
	self.ftpdir = self.ftpdir.split(":")[0]
	if self.ftpdir.endswith("/"):
	    self.ftpdir = self.ftpdir[:len(self.ftpdir)-1]

	self.ftpconn = FTP(self.ftphost)
	self.ftpconn.login(self.ftpuser,self.ftppassword)
	# change to our dir
	self.ftpconn.cwd(self.ftpdir)
	self.currentdir = self.ftpdir


    # this can be used in case of exceptions
    def reconnectHost(self):
	self.ftpconn = FTP(self.ftphost)
	self.ftpconn.login(self.ftpuser,self.ftppassword)
	self.ftpconn.cwd(self.currentdir)

    def getFTPHost(self):
	return self.ftphost

    def getFTPPort(self):
	return self.ftpport

    def getFTPDir(self):
	return self.ftpdir

    def getCWD(self):
	return self.ftpconn.pwd()

    def setCWD(self,dir):
	self.ftpconn.cwd(dir)
	self.currentdir = dir

    def getFileMtime(self,path):
	rc = self.ftpconn.sendcmd("mdtm "+path)
	return rc.split()[len(rc.split())-1]

    def spawnFTPCommand(self,cmd):
	rc = self.ftpconn.sendcmd(cmd)
	return rc

    # list files and directory of a FTP
    # @returns a list
    def listFTPdir(self):
	# directory is: self.ftpdir
	try:
	    rc = self.ftpconn.nlst()
	    _rc = []
	    for i in rc:
		_rc.append(i.split("/")[len(i.split("/"))-1])
	    rc = _rc
	except:
	    return []
	return rc

    # list if the file is available
    # @returns True or False
    def isFileAvailable(self,filename):
	# directory is: self.ftpdir
	try:
	    rc = self.ftpconn.nlst()
	    _rc = []
	    for i in rc:
		_rc.append(i.split("/")[len(i.split("/"))-1])
	    rc = _rc
	    for i in rc:
		if i == filename:
		    return True
	    return False
	except:
	    return False

    def deleteFile(self,file):
	try:
	    rc = self.ftpconn.delete(file)
	    if rc.startswith("250"):
		return True
	    else:
		return False
	except:
	    return False

    def uploadFile(self,file,ascii = False):
	for i in range(10): # ten tries
	    f = open(file)
	    filename = file.split("/")[len(file.split("/"))-1]
	    try:
		if (ascii):
		    rc = self.ftpconn.storlines("STOR "+filename+".tmp",f)
		else:
		    rc = self.ftpconn.storbinary("STOR "+filename+".tmp",f)
		# now we can rename the file with its original name
		self.renameFile(filename+".tmp",filename)
	        return rc
	    except socket.error: # connection reset by peer
		entropyTools.print_info(entropyTools.red("Upload issue, retrying..."))
		self.reconnectHost() # reconnect
		self.deleteFile(filename)
		self.deleteFile(filename+".tmp")
		f.close()
		continue

    def downloadFile(self,filepath,downloaddir,ascii = False):
	file = filepath.split("/")[len(filepath.split("/"))-1]
	if (not ascii):
	    f = open(downloaddir+"/"+file,"wb")
	    rc = self.ftpconn.retrbinary('RETR '+file,f.write)
	else:
	    f = open(downloaddir+"/"+file,"w")
	    rc = self.ftpconn.retrlines('RETR '+file,f.write)
	f.flush()
	f.close()
	return rc

    # also used to move files
    # FIXME: beautify !
    def renameFile(self,fromfile,tofile):
	self.ftpconn.rename(fromfile,tofile)

    # not supported by dreamhost.com
    def getFileSize(self,file):
	return self.ftpconn.size(file)
    
    def getFileSizeCompat(self,file):
	list = getRoughList()
	for item in list:
	    if item.find(file) != -1:
		# extact the size
		return item.split()[4]
	return ""

    def bufferizer(self,buf):
	self.FTPbuffer.append(buf)

    def getRoughList(self):
	self.FTPbuffer = []
	self.ftpconn.dir(self.bufferizer)
	return self.FTPbuffer

    def closeFTPConnection(self):
	self.ftpconn.quit()
