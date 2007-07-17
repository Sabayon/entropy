#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy Mirrors interface

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

# Never do "import portage" here, please use entropyTools binding
# EXIT STATUSES: 700-799

from entropyConstants import *
from outputTools import *
import entropyTools
import string
import os
import ftplib
import time

# Logging initialization
import logTools
mirrorLog = logTools.LogFile(level=etpConst['mirrorsloglevel'],filename = etpConst['mirrorslogfile'], header = "[Mirrors]")
# example: mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"testFuncton: called.")


class handlerFTP:

    # ftp://linuxsabayon:asdasd@silk.dreamhost.com/sabayon.org
    # this must be run before calling the other functions
    def __init__(self, ftpuri):

	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.__init__: called.")

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

	self.ftpconn = ftplib.FTP(self.ftphost)
	self.ftpconn.login(self.ftpuser,self.ftppassword)
	# change to our dir
	#print self.ftpdir
	self.ftpconn.cwd(self.ftpdir)
	self.currentdir = self.ftpdir

    def my_storbinary(self, cmd, fp, callback=None):   # patched for callback
        '''Store a file in line mode.'''
        self.ftpconn.voidcmd('TYPE I')
	CRLF = ftplib.CRLF
        conn = self.ftpconn.transfercmd(cmd)
        while 1:
            buf = fp.readline()
            if not buf: break
            if buf[-2:] != CRLF:
                if buf[-1] in CRLF: buf = buf[:-1]
                buf = buf + CRLF
            conn.sendall(buf)
            if callback: callback(buf)                 # patched for callback
        conn.close()
        return self.ftpconn.voidresp()
	#FTP.storbinary = my_storbinary  # use the patched version

    # this can be used in case of exceptions
    def reconnectHost(self):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.reconnectHost: called.")
	#try:
	#    self.closeFTPConnection()
	#except:
	#    pass
	self.ftpconn = ftplib.FTP(self.ftphost)
	self.ftpconn.login(self.ftpuser,self.ftppassword)
	# save curr dir
	#cur = self.currentdir
	#self.setCWD(self.ftpdir)
	self.setCWD(self.currentdir)

    def getFTPHost(self):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.getFTPHost: called -> "+self.ftphost)
	return self.ftphost

    def getFTPPort(self):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.getFTPPort: called -> "+self.ftpport)
	return self.ftpport

    def getFTPDir(self):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.getFTPPort: called -> "+self.ftpdir)
	return self.ftpdir

    def getCWD(self):
	pwd = self.ftpconn.pwd()
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.getCWD: called -> "+pwd)
	return pwd

    def setCWD(self,dir):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.setCWD: called -> "+dir)
	self.ftpconn.cwd(dir)
	self.currentdir = self.getCWD()

    def setPASV(self,bool):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.setPASV: called -> "+str(bool))
	self.ftpconn.set_pasv(bool)

    def getFileMtime(self,path):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.getFileMtime: called for -> "+path)
	rc = self.ftpconn.sendcmd("mdtm "+path)
	return rc.split()[len(rc.split())-1]

    def spawnFTPCommand(self,cmd):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.spawnFTPCommand: called, command -> "+cmd)
	rc = self.ftpconn.sendcmd(cmd)
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.spawnFTPCommand: called, rc -> "+str(rc))
	return rc

    # list files and directory of a FTP
    # @returns a list
    def listFTPdir(self):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.listFTPdir: called.")
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
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.isFileAvailable: called for -> "+filename)
	# directory is: self.ftpdir
	try:
	    rc = self.ftpconn.nlst()
	    _rc = []
	    for i in rc:
		_rc.append(i.split("/")[len(i.split("/"))-1])
	    rc = _rc
	    for i in rc:
		if i == filename:
		    mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.isFileAvailable: result -> True")
		    return True
	    mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGPRI_WARNING,"handlerFTP.isFileAvailable: result -> False (no exception)")
	    return False
	except:
	    mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGPRI_ERROR,"handlerFTP.isFileAvailable: result -> False (exception occured!!!)")
	    return False

    def deleteFile(self,file):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.deleteFile: called for -> "+str(file))
	try:
	    rc = self.ftpconn.delete(file)
	    if rc.startswith("250"):
		mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.deleteFile: result -> True")
		return True
	    else:
		mirrorLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"handlerFTP.deleteFile: result -> False (no exception)")
		return False
	except:
	    mirrorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"handlerFTP.deleteFile: result -> False (exception occured!!!)")
	    return False

    # this function also supports callback, because storbinary doesn't
    def advancedStorBinary(self, cmd, fp, callback=None, blocksize=8192):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.advancedStorBinary: called with -> "+str(cmd))
	''' Store a file in binary mode. Our version supports a callback function'''
        self.ftpconn.voidcmd('TYPE I')
        conn = self.ftpconn.transfercmd(cmd)
        while 1:
            buf = fp.readline()
            if not buf: break
            conn.sendall(buf)
            if callback: callback(buf)
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.advancedStorBinary: before conn.close()")
        conn.close()
	time.sleep(3)
	rc = self.ftpconn.voidresp()
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.advancedStorBinary: after conn.close()")
	return rc

    def uploadFile(self,file,ascii = False):
	
	def uploadFileAndUpdateProgress(buf):
	    # get the buffer size
	    self.mykByteCount += float(len(buf))/1024
	    # create percentage
	    myUploadPercentage = round((round(self.mykByteCount,1)/self.myFileSize)*100,1)
	    myUploadSize = round(self.mykByteCount,1)
	    if (myUploadPercentage < 100.1) and (myUploadSize <= self.myFileSize):
	        myUploadPercentage = str(myUploadPercentage)+"%"
		
	        # create text
	        currentText = yellow("    <-> Upload status: ")+green(str(myUploadSize))+"/"+red(str(self.myFileSize))+" kB "+yellow("[")+str(myUploadPercentage)+yellow("]")
	        # print !
	        print_info(currentText,back = True)
	
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"handlerFTP.uploadFile: called for -> "+str(file)+" to "+str(self.getCWD())+", mode, ascii?: "+str(ascii))
	
	for i in range(10): # ten tries
	
	    mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.uploadFile: try #"+str(i+1))
	
	    try:
	    
	        f = open(file,"r")
	        filename = file.split("/")[len(file.split("/"))-1]
		
	        # get file size
	        self.myFileSize = round(float(os.stat(file)[6])/1024,1)
	        self.mykByteCount = 0
		
	        if self.isFileAvailable(filename+".tmp"):
	            self.deleteFile(filename+".tmp")
		
	        if (ascii):
		    rc = self.ftpconn.storlines("STOR "+filename+".tmp",f)
	        else:
		    rc = self.my_storbinary("STOR "+filename+".tmp", f, callback = uploadFileAndUpdateProgress )
		
	        # now we can rename the file with its original name
	        self.renameFile(filename+".tmp",filename)
	        mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.uploadFile: after self.renameFile()")
	    
	        f.close()
	    
	        if rc.find("226") != -1: # upload complete
		    mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.uploadFile: upload complete.")
		    return True
	        else:
		    mirrorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"handlerFTP.uploadFile: upload failed !!.")
		    return False
	    
	    except Exception, e: # connection reset by peer
		mirrorLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"handlerFTP.uploadFile: Caught Exception: "+str(e)+" upload issues, retrying...")
		print_info(red("Upload issue, retrying... #"+str(i+1)))
		self.reconnectHost() # reconnect
		mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.uploadFile: after reconnectHost()")
		if self.isFileAvailable(filename):
		    self.deleteFile(filename)
		if self.isFileAvailable(filename+".tmp"):
		    self.deleteFile(filename+".tmp")
		mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.uploadFile: after file deletion")
		pass
		
    def downloadFile(self,filepath,downloaddir,ascii = False):

        def downloadFileStoreAndUpdateProgress(buf):
	    # writing file buffer
	    f.write(buf)
	    # update progress
	    self.mykByteCount += float(len(buf))/1024
	    # create text
	    currentText = yellow("    <-> Download status: ")+green(str(round(self.mykByteCount,1)))+"/"+red(str(self.myFileSize))+" kB"
	    # print !
	    print_info(currentText,back = True)

	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"handlerFTP.downloadFile: called for -> "+str(filepath)+" | download directory: "+str(downloaddir)+" | ascii? "+str(ascii))

	file = filepath.split("/")[len(filepath.split("/"))-1]
	# look if the file exist
	if self.isFileAvailable(file):
	    self.mykByteCount = 0
	    # get the file size
	    self.myFileSize = self.getFileSizeCompat(file)
	    if (self.myFileSize):
	        self.myFileSize = round(float(int(self.myFileSize))/1024,1)
		if (self.myFileSize == 0):
		    self.myFileSize = 1
	    else:
		self.myFileSize = 0
	    if (not ascii):
	        f = open(downloaddir+"/"+file,"wb")
	        rc = self.ftpconn.retrbinary('RETR '+file, downloadFileStoreAndUpdateProgress, 1024)
	    else:
	        f = open(downloaddir+"/"+file,"w")
	        rc = self.ftpconn.retrlines('RETR '+file, f.write)
	    f.flush()
	    f.close()
	    if rc.find("226") != -1: # upload complete
		mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.downloadFile: download success.")
		return True
	    else:
		mirrorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"handlerFTP.downloadFile: download issues !!.")
		return False
	else:
	    mirrorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"handlerFTP.downloadFile: file '"+file+"' not available !!.")
	    return None

    # also used to move files
    def renameFile(self,fromfile,tofile):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.renameFile: rename file from '"+fromfile+"' to '"+tofile+"'.")
	rc = self.ftpconn.rename(fromfile,tofile)
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.renameFile: return output: '"+str(rc)+"'")

    # not supported by dreamhost.com
    def getFileSize(self,file):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.getFileSize: called for -> "+file)
	return self.ftpconn.size(file)
    
    def getFileSizeCompat(self,file):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.getFileSizeCompat: called for -> "+file)
	list = self.getRoughList()
	for item in list:
	    if item.find(file) != -1:
		# extact the size
		return item.split()[4]
	return ""

    def bufferizer(self,buf):
	self.FTPbuffer.append(buf)

    def getRoughList(self):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.getRoughList: called.")
	self.FTPbuffer = []
	self.ftpconn.dir(self.bufferizer)
	return self.FTPbuffer

    def closeFTPConnection(self):
	mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlerFTP.closeFTPConnection: called.")
	self.ftpconn.quit()
