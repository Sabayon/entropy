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

from entropyConstants import *
from serverConstants import *
from outputTools import *
import entropyTools
import socket
import ftplib

class handlerFTP:

    # this must be run before calling the other functions
    def __init__(self, ftpuri):

        # import FTP modules
        socket.setdefaulttimeout(60)

        self.ftpuri = ftpuri

        self.ftphost = entropyTools.extractFTPHostFromUri(self.ftpuri)

        self.ftpuser = ftpuri.split("ftp://")[len(ftpuri.split("ftp://"))-1].split(":")[0]
        if (self.ftpuser == ""):
            self.ftpuser = "anonymous@"
            self.ftppassword = "anonymous"
        else:
            self.ftppassword = ftpuri.split("@")[:len(ftpuri.split("@"))-1]
            if len(self.ftppassword) > 1:
                self.ftppassword = '@'.join(self.ftppassword)
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
        if self.ftpdir == "":
            self.ftpdir = "/"

        count = 10
        while 1:
            count -= 1
            try:
                self.ftpconn = ftplib.FTP(self.ftphost)
                break
            except:
                if not count:
                    raise
                continue

        self.ftpconn.login(self.ftpuser,self.ftppassword)
        # change to our dir
        self.ftpconn.cwd(self.ftpdir)
        self.currentdir = self.ftpdir

    # this can be used in case of exceptions
    def reconnectHost(self):
        # import FTP modules
        socket.setdefaulttimeout(60)
        counter = 10
        while 1:
            counter -= 1
            try:
                self.ftpconn = ftplib.FTP(self.ftphost)
                break
            except:
                if not counter:
                    raise
                continue
        self.ftpconn.login(self.ftpuser,self.ftppassword)
        # save curr dir
        #cur = self.currentdir
        #self.setCWD(self.ftpdir)
        self.setCWD(self.currentdir)

    def getHost(self):
        return self.ftphost

    def getPort(self):
        return self.ftpport

    def getDir(self):
        return self.ftpdir

    def getCWD(self):
        pwd = self.ftpconn.pwd()
        return pwd

    def setCWD(self,dir):
        self.ftpconn.cwd(dir)
        self.currentdir = self.getCWD()

    def setPASV(self,bool):
        self.ftpconn.set_pasv(bool)

    def setChmod(self,chmodvalue,file):
        return self.ftpconn.voidcmd("SITE CHMOD "+str(chmodvalue)+" "+str(file))

    def getFileMtime(self,path):
        rc = self.ftpconn.sendcmd("mdtm "+path)
        return rc.split()[len(rc.split())-1]

    def spawnCommand(self,cmd):
        return self.ftpconn.sendcmd(cmd)

    # list files and directory of a FTP
    # @returns a list
    def listDir(self):
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

    def mkdir(self,directory):
        # FIXME: add rc
        self.ftpconn.mkd(directory)

    # this function also supports callback, because storbinary doesn't
    def advancedStorBinary(self, cmd, fp, callback=None):
        ''' Store a file in binary mode. Our version supports a callback function'''
        self.ftpconn.voidcmd('TYPE I')
        conn = self.ftpconn.transfercmd(cmd)
        while 1:
            buf = fp.readline()
            if not buf: break
            conn.sendall(buf)
            if callback: callback(buf)
        conn.close()

        # that's another workaround
        #return "226"
        try:
            rc = self.ftpconn.voidresp()
        except:
            self.reconnectHost()
            return "226"
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

        for i in range(10): # ten tries
            filename = file.split("/")[len(file.split("/"))-1]
            try:
                f = open(file,"r")
                # get file size
                self.myFileSize = round(float(os.stat(file)[6])/1024,1)
                self.mykByteCount = 0

                if self.isFileAvailable(filename+".tmp"):
                    self.deleteFile(filename+".tmp")

                if (ascii):
                    rc = self.ftpconn.storlines("STOR "+filename+".tmp",f)
                else:
                    rc = self.advancedStorBinary("STOR "+filename+".tmp", f, callback = uploadFileAndUpdateProgress )

                # now we can rename the file with its original name
                self.renameFile(filename+".tmp",filename)
                f.close()

                if rc.find("226") != -1: # upload complete
                    return True
                else:
                    return False

            except Exception, e: # connection reset by peer
                import traceback
                traceback.print_exc()
                print_warning("")
                print_warning(red("  Upload issue: ")+bold(str(e))+red(", retrying... #"+str(i+1)))
                self.reconnectHost() # reconnect
                if self.isFileAvailable(filename):
                    self.deleteFile(filename)
                if self.isFileAvailable(filename+".tmp"):
                    self.deleteFile(filename+".tmp")
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

        item = filepath.split("/")[len(filepath.split("/"))-1]
        # look if the file exist
        if self.isFileAvailable(item):
            self.mykByteCount = 0
            # get the file size
            self.myFileSize = self.getFileSizeCompat(item)
            if (self.myFileSize):
                self.myFileSize = round(float(int(self.myFileSize))/1024,1)
                if (self.myFileSize == 0):
                    self.myFileSize = 1
            else:
                self.myFileSize = 0
            if (not ascii):
                f = open(downloaddir+"/"+item,"wb")
                rc = self.ftpconn.retrbinary('RETR '+item, downloadFileStoreAndUpdateProgress, 1024)
            else:
                f = open(downloaddir+"/"+item,"w")
                rc = self.ftpconn.retrlines('RETR '+item, f.write)
            f.flush()
            f.close()
            if rc.find("226") != -1: # upload complete
                return True
            else:
                return False
        else:
            return None

    # also used to move files
    def renameFile(self,fromfile,tofile):
        rc = self.ftpconn.rename(fromfile,tofile)

    # not supported by dreamhost.com
    def getFileSize(self,file):
        return self.ftpconn.size(file)

    def getFileSizeCompat(self,file):
        data = self.getRoughList()
        for item in data:
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

    def closeConnection(self):
        self.ftpconn.quit()
