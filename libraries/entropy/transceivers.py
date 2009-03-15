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
from __future__ import with_statement
import os
import urllib2
import time
from entropy.const import etpConst
from entropy.output import TextInterface, darkblue, darkred, purple, blue, brown, darkgreen, red, bold
from entropy.exceptions import *
from entropy.i18n import _
from entropy.misc import TimeScheduled, ParallelTask


class urlFetcher:

    def __init__(self, url, path_to_save, checksum = True,
            show_speed = True, resume = True,
            abort_check_func = None, disallow_redirect = False,
            thread_stop_func = None, speed_limit = etpConst['downloadspeedlimit'],
            OutputInterface = None):

        self.progress = None
        import entropy.tools as entropyTools
        import socket
        self.entropyTools, self.socket = entropyTools, socket
        self.__th_id = 0
        self.__resume = resume
        self.__url = self.__encode_url(url)
        self.__path_to_save = path_to_save
        self.__checksum = checksum
        self.__show_speed = show_speed
        self.__abort_check_func = abort_check_func
        self.__thread_stop_func = thread_stop_func
        self.__disallow_redirect = disallow_redirect
        self.__speedlimit = speed_limit # kbytes/sec

        # important to have this here too
        self.__datatransfer = 0
        self.__resumed = False

        uname = os.uname()
        self.user_agent = "Entropy/%s (compatible; %s; %s: %s %s %s)" % (
            etpConst['entropyversion'],
            "Entropy",
            os.path.basename(self.__url),
            uname[0],
            uname[4],
            uname[2],
        )
        self.__extra_header_data = {}
        self.__Output = OutputInterface
        if self.__Output == None:
            self.__Output = TextInterface()
        elif not hasattr(self.__Output,'updateProgress'):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        elif not callable(self.__Output.updateProgress):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

    def _init_vars(self):

        self.__resumed = False
        self.__buffersize = 8192
        self.__status = None
        self.__remotefile = None
        self.__downloadedsize = 0
        self.__average = 0
        self.__remotesize = 0
        self.__oldaverage = 0.0
        # transfer status data
        self.__startingposition = 0
        self.__datatransfer = 0
        self.__time_remaining = "(infinite)"
        self.__time_remaining_secs = 0
        self.__elapsed = 0.0
        self.__updatestep = 0.2
        self.__transferpollingtime = float(1)/4
        self.__setup_resume_support()
        self._setup_proxy()

    def __setup_resume_support(self):
        # resume support
        if os.path.isfile(self.__path_to_save) and os.access(self.__path_to_save,os.W_OK) and self.__resume:
            self.localfile = open(self.__path_to_save,"awb")
            self.localfile.seek(0,2)
            self.__startingposition = int(self.localfile.tell())
            self.__resumed = True
        else:
            if os.path.lexists(self.__path_to_save) and not self.entropyTools.is_valid_path(self.__path_to_save):
                try:
                    os.remove(self.__path_to_save)
                except OSError: # I won't stop you here
                    pass
            self.localfile = open(self.__path_to_save,"wb")

    def _setup_proxy(self):
        # setup proxy, doing here because config is dynamic
        mydict = {}
        if etpConst['proxy']['ftp']:
            mydict['ftp'] = etpConst['proxy']['ftp']
        if etpConst['proxy']['http']:
            mydict['http'] = etpConst['proxy']['http']
        if mydict:
            mydict['username'] = etpConst['proxy']['username']
            mydict['password'] = etpConst['proxy']['password']
            self.entropyTools.add_proxy_opener(urllib2, mydict)
        else:
            # unset
            urllib2._opener = None

    def __encode_url(self, url):
        import urllib
        url = os.path.join(os.path.dirname(url),urllib.quote(os.path.basename(url)))
        return url

    def set_id(self, th_id):
        self.__th_id = th_id

    def download(self):

        self._init_vars()
        self.speedUpdater = TimeScheduled(
            self.__transferpollingtime,
            self.__update_speed,
        )
        self.speedUpdater.start()
        # set timeout
        self.socket.setdefaulttimeout(20)

        if self.__url.startswith("http://"):
            headers = { 'User-Agent' : self.user_agent }
            req = urllib2.Request(self.__url, self.__extra_header_data, headers)
        else:
            req = self.__url

        u_agent_error = False
        while 1:
            # get file size if available
            try:
                self.__remotefile = urllib2.urlopen(req)
            except KeyboardInterrupt:
                self.__close()
                raise
            except urllib2.HTTPError, e:
                if (e.code == 405) and not u_agent_error:
                    # server doesn't like our user agent
                    req = self.__url
                    u_agent_error = True
                    continue
                self.__close()
                self.__status = "-3"
                return self.__status
            except:
                self.__close()
                self.__status = "-3"
                return self.__status
            break

        try:
            self.__remotesize = int(self.__remotefile.headers.get("content-length"))
            self.__remotefile.close()
        except KeyboardInterrupt:
            self.__close()
            raise
        except:
            pass

        # handle user stupidity
        try:
            request = self.__url
            if ((self.__startingposition > 0) and (self.__remotesize > 0)) and (self.__startingposition < self.__remotesize):
                try:
                    request = urllib2.Request(
                        self.__url,
                        headers = {
                            "Range" : "bytes=" + str(self.__startingposition) + "-" + str(self.__remotesize)
                        }
                    )
                except KeyboardInterrupt:
                    self.__close()
                    raise
                except:
                    pass
            elif (self.__startingposition == self.__remotesize):
                self.__close()
                return self.__prepare_return()
            else:
                self.localfile = open(self.__path_to_save,"wb")
            self.__remotefile = urllib2.urlopen(request)
        except KeyboardInterrupt:
            self.__close()
            raise
        except:
            self.__close()
            self.__status = "-3"
            return self.__status

        if self.__remotesize > 0:
            self.__remotesize = float(int(self.__remotesize))/1024

        if self.__disallow_redirect and (self.__url != self.__remotefile.geturl()):
            self.__close()
            self.__status = "-3"
            return self.__status

        while 1:
            try:
                rsx = self.__remotefile.read(self.__buffersize)
                if rsx == '': break
                if self.__abort_check_func != None:
                    self.__abort_check_func()
                if self.__thread_stop_func != None:
                    self.__thread_stop_func()
            except KeyboardInterrupt:
                self.__close()
                raise
            except self.socket.timeout:
                self.__close()
                self.__status = "-4"
                return self.__status
            except:
                # python 2.4 timeouts go here
                self.__close()
                self.__status = "-3"
                return self.__status
            self.__commit(rsx)
            if self.__show_speed:
                self.handle_statistics(self.__th_id, self.__downloadedsize,
                    self.__remotesize, self.__average, self.__oldaverage,
                    self.__updatestep, self.__show_speed, self.__datatransfer,
                    self.__time_remaining, self.__time_remaining_secs
                )
                self.updateProgress()
                self.__oldaverage = self.__average
            if self.__speedlimit:
                while self.__datatransfer > self.__speedlimit*1024:
                    time.sleep(0.1)
                    if self.__show_speed:
                        self.updateProgress()
                        self.__oldaverage = self.__average

        # kill thread
        self.__close()
        return self.__prepare_return()


    def __prepare_return(self):
        if self.__checksum:
            self.__status = self.entropyTools.md5sum(self.__path_to_save)
            return self.__status
        self.__status = "-2"
        return self.__status

    def __commit(self, mybuffer):
        # writing file buffer
        self.localfile.write(mybuffer)
        # update progress info
        self.__downloadedsize = self.localfile.tell()
        kbytecount = float(self.__downloadedsize)/1024
        self.__average = int((kbytecount/self.__remotesize)*100)

    def __close(self):
        try:
            self.localfile.flush()
            self.localfile.close()
        except:
            pass
        try:
            self.__remotefile.close()
        except:
            pass
        self.speedUpdater.kill()
        self.socket.setdefaulttimeout(2)

    def __update_speed(self):
        self.__elapsed += self.__transferpollingtime
        # we have the diff size
        self.__datatransfer = (self.__downloadedsize-self.__startingposition) / self.__elapsed
        try:
            self.__time_remaining_secs = int(round((int(round(self.__remotesize*1024,0))-int(round(self.__downloadedsize,0)))/self.__datatransfer,0))
            self.__time_remaining = self.entropyTools.convertSecondsToFancyOutput(self.__time_remaining_secs)
        except:
            self.__time_remaining = "(%s)" % (_("infinite"),)

    def get_transfer_rate(self):
        return self.__datatransfer

    def is_resumed(self):
        return self.__resumed

    def handle_statistics(self, th_id, downloaded_size, total_size,
            average, old_average, update_step, show_speed, data_transfer,
            time_remaining, time_remaining_secs):
        pass

    def updateProgress(self):

        mytxt = _("[F]")
        eta_txt = _("ETA")
        sec_txt = _("sec") # as in XX kb/sec

        currentText = darkred("    %s: " % (mytxt,)) + \
            darkgreen(str(round(float(self.__downloadedsize)/1024,1))) + "/" + \
            red(str(round(self.__remotesize,1))) + " kB"
        # create progress bar
        barsize = 10
        bartext = "["
        curbarsize = 1
        if self.__average > self.__oldaverage+self.__updatestep:
            averagesize = (self.__average*barsize)/100
            while averagesize > 0:
                curbarsize += 1
                bartext += "="
                averagesize -= 1
            bartext += ">"
            diffbarsize = barsize-curbarsize
            while diffbarsize > 0:
                bartext += " "
                diffbarsize -= 1
            if self.__show_speed:
                bartext += "] => %s" % (self.entropyTools.bytesIntoHuman(self.__datatransfer),)
                bartext += "/%s : %s: %s" % (sec_txt,eta_txt,self.__time_remaining,)
            else:
                bartext += "]"
            average = str(self.__average)
            if len(average) < 2:
                average = " "+average
            currentText += " <->  "+average+"% "+bartext
            self.__Output.updateProgress(currentText, back = True)

class MultipleUrlFetcher:

    import entropy.tools as entropyTools
    def __init__(self, url_path_list, checksum = True,
            show_speed = True, resume = True,
            abort_check_func = None, disallow_redirect = False,
            OutputInterface = None, urlFetcherClass = None):
        """
            @param url_path_list list [(url,path_to_save,),...]
            @param checksum bool return checksum data
            @param show_speed bool show transfer speed on the output
            @param resume bool enable resume support
            @param abort_check_func callable function that could
                raise exception and stop transfer
            @param disallow_redirect bool disable automatic HTTP redirect
            @param OutputInterface TextInterface instance used to
                print instance output through a common interface
            @param urlFetcherClass, urlFetcher instance/interface used
        """
        self.__url_path_list = url_path_list
        self.__resume = resume
        self.__checksum = checksum
        self.__show_speed = show_speed
        self.__abort_check_func = abort_check_func
        self.__disallow_redirect = disallow_redirect

        # important to have a declaration here
        self.__data_transfer = 0
        self.__average = 0
        self.__old_average = 0
        self.__time_remaining_sec = 0

        self.__Output = OutputInterface
        if self.__Output == None:
            self.__Output = TextInterface()
        elif not hasattr(self.__Output,'updateProgress'):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        elif not callable(self.__Output.updateProgress):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.urlFetcher = urlFetcherClass
        if self.urlFetcher == None:
            self.urlFetcher = urlFetcher


    def __handle_threads_stop(self):
        if self.__stop_threads:
            raise InterruptError

    def _init_vars(self):
        self.__progress_data = {}
        self.__thread_pool = {}
        self.__download_statuses = {}
        self.__show_progress = False
        self.__stop_threads = False
        self.__first_refreshes = 50
        self.__data_transfer = 0
        self.__average = 0
        self.__old_average = 0
        self.__time_remaining_sec = 0

    def download(self):
        self._init_vars()

        th_id = 0
        speed_limit = 0
        dsl = etpConst['downloadspeedlimit']
        if isinstance(dsl,int) and self.__url_path_list:
            speed_limit = dsl/len(self.__url_path_list)

        for url, path_to_save in self.__url_path_list:
            th_id += 1
            downloader = self.urlFetcher(url, path_to_save,
                checksum = self.__checksum, show_speed = self.__show_speed,
                resume = self.__resume, abort_check_func = self.__abort_check_func,
                disallow_redirect = self.__disallow_redirect,
                thread_stop_func = self.__handle_threads_stop,
                speed_limit = speed_limit,
                OutputInterface = self.__Output
            )
            downloader.set_id(th_id)
            downloader.updateProgress = self.updateProgress
            downloader.handle_statistics = self.handle_statistics

            def do_download(ds, th_id, downloader):
                ds[th_id] = downloader.download()

            t = ParallelTask(do_download, self.__download_statuses, th_id, downloader)
            self.__thread_pool[th_id] = t
            t.start()
        self.show_download_files_info()
        self.__show_progress = True
        while len(self.__url_path_list) != len(self.__download_statuses):
            try:
                time.sleep(0.5)
            except (SystemExit, KeyboardInterrupt,):
                self.__stop_threads = True
                raise

        return self.__download_statuses

    def get_data_transfer(self):
        return self.__data_transfer

    def get_average(self):
        return self.__average

    def get_seconds_remaining(self):
        return self.__time_remaining_sec

    def show_download_files_info(self):
        count = 0
        pl = self.__url_path_list[:]
        self.__Output.updateProgress(
            "%s: %s %s" % (
                darkblue(_("Aggregated download")),
                darkred(str(len(pl))),
                darkblue(_("items")),
            ),
            importance = 0,
            type = "info",
            header = purple("  ## ")
        )
        for url, save_path in pl:
            count += 1
            fname = os.path.basename(url)
            uri = self.entropyTools.spliturl(url)[1]
            self.__Output.updateProgress(
                "[%s] %s => %s" % (
                    darkblue(str(count)),
                    darkgreen(uri),
                    blue(fname),
                ),
                importance = 0,
                type = "info",
                header = brown("   # ")
            )

    def handle_statistics(self, th_id, downloaded_size, total_size,
            average, old_average, update_step, show_speed, data_transfer,
            time_remaining, time_remaining_secs):
        data = {
            'th_id': th_id,
            'downloaded_size': downloaded_size,
            'total_size': total_size,
            'average': average,
            'old_average': old_average,
            'update_step': update_step,
            'show_speed': show_speed,
            'data_transfer': data_transfer,
            'time_remaining': time_remaining,
            'time_remaining_secs': time_remaining_secs,
        }
        self.__progress_data[th_id] = data

    def updateProgress(self):

        eta_txt = _("ETA")
        sec_txt = _("sec") # as in XX kb/sec
        downloaded_size = 0
        total_size = 0
        time_remaining = 0
        data_transfer = 0
        update_step = 0
        average = 100
        pd = self.__progress_data.copy()
        pdlen = len(pd)

        # calculation
        for th_id in sorted(pd):
            data = pd.get(th_id)
            downloaded_size += data.get('downloaded_size',0)
            total_size += data.get('total_size',0)
            data_transfer += data.get('data_transfer',0)
            tr = data.get('time_remaining_secs',0)
            if tr > 0: time_remaining += tr
            update_step += data.get('update_step',0)

        # total_size is in kbytes
        # downloaded_size is in bytes
        if total_size > 0:
            average = int(float(downloaded_size/1024)/total_size * 100)
        self.__data_transfer = data_transfer
        self.__average = average
        update_step = update_step/pdlen
        self.__time_remaining_sec = time_remaining
        time_remaining = self.entropyTools.convertSecondsToFancyOutput(time_remaining)

        if ((average > self.__old_average+update_step) or \
            (self.__first_refreshes > 0)) and self.__show_progress:

            self.__first_refreshes -= 1
            currentText = darkgreen(str(round(float(downloaded_size)/1024,1))) + "/" + \
                red(str(round(total_size,1))) + " kB"
            # create progress bar
            barsize = 10
            bartext = "["
            curbarsize = 1
            averagesize = (average*barsize)/100
            while averagesize > 0:
                curbarsize += 1
                bartext += "="
                averagesize -= 1
            bartext += ">"
            diffbarsize = barsize-curbarsize
            while diffbarsize > 0:
                bartext += " "
                diffbarsize -= 1
            if self.__show_speed:
                bartext += "] => %s" % (self.entropyTools.bytesIntoHuman(data_transfer),)
                bartext += "/%s : %s: %s" % (sec_txt,eta_txt,time_remaining,)
            else:
                bartext += "]"
            myavg = str(average)
            if len(myavg) < 2:
                myavg = " "+myavg
            currentText += " <->  "+myavg+"% "+bartext+" "
            self.__Output.updateProgress(currentText, back = True)

        self.__old_average = average


class FtpInterface:

    # this must be run before calling the other functions
    def __init__(self, ftpuri, OutputInterface, verbose = True):

        if not hasattr(OutputInterface,'updateProgress'):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (OutputInterface,mytxt,))
        elif not callable(OutputInterface.updateProgress):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (OutputInterface,mytxt,))

        import socket, ftplib
        import entropy.tools as entropyTools
        self.socket, self.ftplib, self.entropyTools = socket, ftplib, entropyTools
        self.Entropy = OutputInterface
        self.__verbose = verbose
        self.__init_vars()
        self.socket.setdefaulttimeout(60)
        self.__ftpuri = ftpuri
        self.__speed_updater = None
        self.__currentdir = '.'
        self.__ftphost = self.entropyTools.extract_ftp_host_from_uri(self.__ftpuri)
        self.__ftpuser, self.__ftppassword, self.__ftpport, self.__ftpdir = self.entropyTools.extract_ftp_data(ftpuri)

        count = 10
        while 1:
            count -= 1
            try:
                self.__ftpconn = self.ftplib.FTP(self.__ftphost)
                break
            except (self.socket.gaierror,), e:
                raise ConnectionError('ConnectionError: %s' % (e,))
            except (self.socket.error,), e:
                if not count:
                    raise ConnectionError('ConnectionError: %s' % (e,))
                continue
            except:
                if not count: raise
                continue

        if self.__verbose:
            mytxt = _("connecting with user")
            self.Entropy.updateProgress(
                "[ftp:%s] %s: %s" % (darkgreen(self.__ftphost),mytxt,blue(self.__ftpuser),),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        try:
            self.__ftpconn.login(self.__ftpuser,self.__ftppassword)
        except self.ftplib.error_perm, e:
            raise FtpError('FtpError: %s' % (e,))
        if self.__verbose:
            mytxt = _("switching to")
            self.Entropy.updateProgress(
                "[ftp:%s] %s: %s" % (darkgreen(self.__ftphost),mytxt,blue(self.__ftpdir),),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        self.set_cwd(self.__ftpdir, dodir = True)

    def __init_vars(self):
        self.__oldprogress = 0.0
        self.__filesize = 0
        self.__filekbcount = 0
        self.__transfersize = 0
        self.__startingposition = 0
        self.__elapsed = 0.0
        self.__time_remaining_secs = 0
        self.__time_remaining = "(%s)" % (_("infinite"),)
        self.__transferpollingtime = float(1)/4

    def set_basedir(self):
        return self.set_cwd(self.__ftpdir)

    # this can be used in case of exceptions
    def reconnect_host(self):
        # import FTP modules
        self.socket.setdefaulttimeout(60)
        counter = 10
        while 1:
            counter -= 1
            try:
                self.__ftpconn = self.ftplib.FTP(self.__ftphost)
                break
            except:
                if not counter:
                    raise
                continue
        if self.__verbose:
            mytxt = _("reconnecting with user")
            self.Entropy.updateProgress(
                "[ftp:%s] %s: %s" % (darkgreen(self.__ftphost),mytxt,blue(self.__ftpuser),),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        self.__ftpconn.login(self.__ftpuser,self.__ftppassword)
        if self.__verbose:
            mytxt = _("switching to")
            self.Entropy.updateProgress(
                "[ftp:%s] %s: %s" % (darkgreen(self.__ftphost),mytxt,blue(self.__ftpdir),),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        self.set_cwd(self.__currentdir)

    def get_host(self):
        return self.__ftphost

    def get_port(self):
        return self.__ftpport

    def get_dir(self):
        return self.__ftpdir

    def get_cwd(self):
        pwd = self.__ftpconn.pwd()
        return pwd

    def set_cwd(self, mydir, dodir = False):
        try:
            return self._set_cwd(mydir, dodir)
        except self.ftplib.error_perm, e:
            raise FtpError('FtpError: %s' % (e,))

    def _set_cwd(self, mydir, dodir = False):
        if self.__verbose:
            mytxt = _("switching to")
            self.Entropy.updateProgress(
                "[ftp:%s] %s: %s" % (darkgreen(self.__ftphost),mytxt,blue(mydir),),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        try:
            self.__ftpconn.cwd(mydir)
        except self.ftplib.error_perm, e:
            if e[0][:3] == '550' and dodir:
                self.recursive_mkdir(mydir)
                self.__ftpconn.cwd(mydir)
            else:
                raise
        self.__currentdir = self.get_cwd()

    def set_pasv(self,bool):
        self.__ftpconn.set_pasv(bool)

    def set_chmod(self,chmodvalue,file):
        return self.__ftpconn.voidcmd("SITE CHMOD "+str(chmodvalue)+" "+str(file))

    def get_file_mtime(self,path):
        rc = self.__ftpconn.sendcmd("mdtm "+path)
        return rc.split()[-1]

    def send_cmd(self,cmd):
        return self.__ftpconn.sendcmd(cmd)

    def list_dir(self):
        return [x.split("/")[-1] for x in self.__ftpconn.nlst()]

    def is_file_available(self, filename):
        xx = []
        def cb(x):
            if x == filename: xx.append(x)
        self.__ftpconn.retrlines('NLST',cb)
        if xx: return True
        return False

    def delete_file(self,file):
        rc = self.__ftpconn.delete(file)
        if rc.startswith("250"):
            return True
        return False

    def recursive_mkdir(self, mypath):
        mydirs = [x for x in mypath.split("/") if x]
        mycurpath = ""
        for mydir in mydirs:
            mycurpath = os.path.join(mycurpath,mydir)
            if not self.is_file_available(mycurpath):
                try:
                    self.mkdir(mycurpath)
                except self.ftplib.error_perm, e:
                    if e[0].lower().find("permission denied") != -1:
                        raise
                    elif e[0][:3] != '550':
                        raise

    def mkdir(self,directory):
        return self.__ftpconn.mkd(directory)

    def upload_file(self, file, ascii = False):

        # this function also supports callback, because storbinary doesn't
        def advanced_stor(cmd, fp, callback=None):
            ''' Store a file in binary mode. Our version supports a callback function'''
            self.__ftpconn.voidcmd('TYPE I')
            conn = self.__ftpconn.transfercmd(cmd)
            while 1:
                buf = fp.readline()
                if not buf: break
                conn.sendall(buf)
                if callback: callback(buf)
            conn.close()

            # that's another workaround
            #return "226"
            try:
                rc = self.__ftpconn.voidresp()
            except:
                self.reconnect_host()
                return "226"
            return rc

        def up_file_up_progress(buf):
            self.updateProgress(len(buf))

        tries = 0
        while tries < 10:

            tries += 1
            filename = os.path.basename(file)
            self.__init_vars()
            self.__start_speed_counter()
            try:

                with open(file,"r") as f:

                    self.__filesize = round(float(self.entropyTools.get_file_size(file))/1024,1)
                    self.__filekbcount = 0

                    if self.is_file_available(filename+".tmp"):
                        self.delete_file(filename+".tmp")

                    if ascii:
                        rc = self.__ftpconn.storlines("STOR "+filename+".tmp",f)
                    else:
                        rc = advanced_stor("STOR "+filename+".tmp", f, callback = up_file_up_progress)

                    # now we can rename the file with its original name
                    self.rename_file(filename+".tmp",filename)

                if rc.find("226") != -1: # upload complete
                    return True
                return False

            except Exception, e: # connection reset by peer

                self.entropyTools.print_traceback()
                mytxt = red("%s: %s, %s... #%s") % (
                    _("Upload issue"),
                    e,
                    _("retrying"),
                    tries+1,
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = "  "
                    )
                self.reconnect_host() # reconnect
                if self.is_file_available(filename):
                    self.delete_file(filename)
                if self.is_file_available(filename+".tmp"):
                    self.delete_file(filename+".tmp")

            finally:
                self.__stop_speed_counter()

    def download_file(self, filename, downloaddir, ascii = False):

        def df_up(buf):
            # writing file buffer
            f.write(buf)
            # update progress
            self.__filekbcount += float(len(buf))/1024
            # create text
            cnt = round(self.__filekbcount,1)
            mytxt = _("Download status")
            currentText = brown("    <-> %s: " % (mytxt,)) + darkgreen(str(cnt)) + "/" + \
                red(str(self.__filesize)) + " kB"
            self.Entropy.updateProgress(
                currentText,
                importance = 0,
                type = "info",
                back = True,
                count = (cnt, self.__filesize),
                percent = True
            )

        tries = 10
        while tries:
            tries -= 1

            self.__init_vars()
            self.__start_speed_counter()
            try:

                # look if the file exist
                if self.is_file_available(filename):
                    self.__filekbcount = 0
                    # get the file size
                    self.__filesize = self.get_file_size_compat(filename)
                    if (self.__filesize):
                        self.__filesize = round(float(int(self.__filesize))/1024,1)
                        if (self.__filesize == 0):
                            self.__filesize = 1
                    else:
                        self.__filesize = 0
                    if not ascii:
                        f = open(downloaddir+"/"+filename,"wb")
                        rc = self.__ftpconn.retrbinary('RETR '+filename, df_up, 1024)
                    else:
                        f = open(downloaddir+"/"+filename,"w")
                        rc = self.__ftpconn.retrlines('RETR '+filename, f.write)
                    f.flush()
                    f.close()
                    if rc.find("226") != -1: # upload complete
                        return True
                    return False

            except Exception, e: # connection reset by peer

                self.entropyTools.print_traceback()
                mytxt = red("%s: %s, %s... #%s") % (
                    _("Download issue"),
                    e,
                    _("retrying"),
                    tries+1,
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = "  "
                    )
                self.reconnect_host() # reconnect

            finally:
                self.__stop_speed_counter()

    # also used to move files
    def rename_file(self, fromfile, tofile):
        rc = self.__ftpconn.rename(fromfile,tofile)
        return rc

    def get_file_size(self, filename):
        return self.__ftpconn.size(filename)

    def get_file_size_compat(self, filename):
        try:
            data = [x.split() for x in self.__ftpconn.sendcmd("stat %s" % (filename,)).split("\n")]
        except self.ftplib.error_temp:
            return ""
        for item in data:
            if item[-1] == filename:
                return item[4]
        return ""

    def get_raw_list(self):
        mybuffer = []
        def bufferizer(buf):
            mybuffer.append(buf)
        self.__ftpconn.dir(bufferizer)
        return mybuffer

    def close(self):
        try:
            self.__ftpconn.quit()
        except (EOFError,AttributeError,self.socket.timeout,self.ftplib.error_reply,):
            # AttributeError is raised when socket gets trashed
            # EOFError is raised when the connection breaks
            # timeout, who cares!
            pass

    def __start_speed_counter(self):
        self.__speed_updater = TimeScheduled(
            self.__transferpollingtime,
            self.__update_speed,
        )
        self.__speed_updater.start()

    def __stop_speed_counter(self):
        if self.__speed_updater != None:
            self.__speed_updater.kill()

    def __update_speed(self):
        self.__elapsed += self.__transferpollingtime
        # we have the diff size
        self.__datatransfer = (self.__transfersize-self.__startingposition) / self.__elapsed
        try:
            self.__time_remaining_secs = int(round((int(round(self.__filesize*1024,0))-int(round(self.__transfersize,0)))/self.__datatransfer,0))
            self.__time_remaining = self.entropyTools.convertSecondsToFancyOutput(self.__time_remaining_secs)
        except:
            self.__time_remaining = "(%s)" % (_("infinite"),)

    def updateProgress(self, buf_len):
        # get the buffer size
        self.__filekbcount += float(buf_len)/1024
        self.__transfersize += buf_len
        # create percentage
        myUploadPercentage = 100.0
        if self.__filesize >= 1:
            myUploadPercentage = round((round(self.__filekbcount,1)/self.__filesize)*100,1)
        currentprogress = myUploadPercentage
        myUploadSize = round(self.__filekbcount,1)
        if (currentprogress > self.__oldprogress+1.0) and \
            (myUploadPercentage < 100.1) and \
            (myUploadSize <= self.__filesize):

            myUploadPercentage = str(myUploadPercentage)+"%"
            # create text
            mytxt = _("Transfer status")
            currentText = brown("    <-> %s: " % (mytxt,)) + \
                darkgreen(str(myUploadSize)) + "/" + red(str(self.__filesize)) + " kB " + \
                brown("[") + str(myUploadPercentage) + brown("]") + " " + self.__time_remaining + \
                " " + self.entropyTools.bytesIntoHuman(self.__datatransfer) + "/"+_("sec")
            # WARN: re-enabled updateProgress, this may cause slowdowns
            # print_info(currentText, back = True)
            self.Entropy.updateProgress(currentText, back = True)
            self.__oldprogress = currentprogress


class FtpServerHandler:

    import entropy.tools as entropyTools
    def __init__(self, ftp_interface, entropy_interface, uris, files_to_upload,
        download = False, remove = False, ftp_basedir = None, local_basedir = None,
        critical_files = [], use_handlers = False, handlers_data = {}, repo = None):

        self.FtpInterface = ftp_interface
        self.Entropy = entropy_interface
        if not isinstance(uris,list):
            raise InvalidDataType("InvalidDataType: %s" % (_("uris must be a list instance"),))
        if not isinstance(files_to_upload,(list,dict)):
            raise InvalidDataType("InvalidDataType: %s" % (
                    _("files_to_upload must be a list or dict instance"),
                )
            )
        self.uris = uris
        if isinstance(files_to_upload,list):
            self.myfiles = files_to_upload[:]
        else:
            self.myfiles = sorted([x for x in files_to_upload])
        self.download = download
        self.remove = remove
        self.repo = repo
        if self.repo == None:
            self.repo = self.Entropy.default_repository
        self.use_handlers = use_handlers
        if self.remove:
            self.download = False
            self.use_handlers = False
        if not ftp_basedir:
            # default to database directory
            my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
            self.ftp_basedir = unicode(my_path)
        else:
            self.ftp_basedir = unicode(ftp_basedir)
        if not local_basedir:
            # default to database directory
            self.local_basedir = os.path.dirname(self.Entropy.get_local_database_file(self.repo))
        else:
            self.local_basedir = unicode(local_basedir)
        self.critical_files = critical_files
        self.handlers_data = handlers_data.copy()

    def handler_verify_upload(self, local_filepath, uri, counter, maxcount, tries):

        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)

        self.Entropy.updateProgress(
            "[%s|#%s|(%s/%s)] %s: %s" % (
                blue(crippled_uri),
                darkgreen(str(tries)),
                blue(str(counter)),
                bold(str(maxcount)),
                darkgreen(_("verifying upload (if supported)")),
                blue(os.path.basename(local_filepath)),
            ),
            importance = 0,
            type = "info",
            header = red(" @@ "),
            back = True
        )

        checksum = self.Entropy.get_remote_package_checksum(
            self.repo,
            os.path.basename(local_filepath),
            self.handlers_data['branch']
        )
        if checksum == None:
            self.Entropy.updateProgress(
                "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                    blue(crippled_uri),
                    darkgreen(str(tries)),
                    blue(str(counter)),
                    bold(str(maxcount)),
                    blue(_("digest verification")),
                    os.path.basename(local_filepath),
                    darkred(_("not supported")),
                ),
                importance = 0,
                type = "info",
                header = red(" @@ ")
            )
            return True
        elif isinstance(checksum,bool) and not checksum:
            self.Entropy.updateProgress(
                "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                    blue(crippled_uri),
                    darkgreen(str(tries)),
                    blue(str(counter)),
                    bold(str(maxcount)),
                    blue(_("digest verification")),
                    os.path.basename(local_filepath),
                    bold(_("file not found")),
                ),
                importance = 0,
                type = "warning",
                header = brown(" @@ ")
            )
            return False
        elif len(checksum) == 32:
            # valid? checking
            ckres = self.entropyTools.compare_md5(local_filepath,checksum)
            if ckres:
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        darkgreen(_("so far, so good!")),
                    ),
                    importance = 0,
                    type = "info",
                    header = red(" @@ ")
                )
                return True
            else:
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        darkred(_("invalid checksum")),
                    ),
                    importance = 0,
                    type = "warning",
                    header = brown(" @@ ")
                )
                return False
        else:
            self.Entropy.updateProgress(
                "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                    blue(crippled_uri),
                    darkgreen(str(tries)),
                    blue(str(counter)),
                    bold(str(maxcount)),
                    blue(_("digest verification")),
                    os.path.basename(local_filepath),
                    darkred(_("unknown data returned")),
                ),
                importance = 0,
                type = "warning",
                header = brown(" @@ ")
            )
            return True

    def go(self):

        broken_uris = set()
        fine_uris = set()
        errors = False
        action = 'upload'
        if self.download:
            action = 'download'
        elif self.remove:
            action = 'remove'

        for uri in self.uris:

            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
            self.Entropy.updateProgress(
                "[%s|%s] %s..." % (
                    blue(crippled_uri),
                    brown(action),
                    blue(_("connecting to mirror")),
                ),
                importance = 0,
                type = "info",
                header = blue(" @@ ")
            )
            try:
                ftp = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.print_traceback()
                return True,fine_uris,broken_uris # issues
            my_path = os.path.join(self.Entropy.get_remote_database_relative_path(self.repo),etpConst['branch'])
            self.Entropy.updateProgress(
                "[%s|%s] %s %s..." % (
                    blue(crippled_uri),
                    brown(action),
                    blue(_("changing directory to")),
                    darkgreen(my_path),
                ),
                importance = 0,
                type = "info",
                header = blue(" @@ ")
            )

            ftp.set_cwd(self.ftp_basedir, dodir = True)
            maxcount = len(self.myfiles)
            counter = 0

            for mypath in self.myfiles:

                ftp.set_basedir()
                ftp.set_cwd(self.ftp_basedir, dodir = True)

                mycwd = None
                if isinstance(mypath,tuple):
                    if len(mypath) < 2: continue
                    mycwd = mypath[0]
                    mypath = mypath[1]
                    ftp.set_cwd(mycwd, dodir = True)

                syncer = ftp.upload_file
                myargs = [mypath]
                if self.download:
                    syncer = ftp.download_file
                    myargs = [os.path.basename(mypath),self.local_basedir]
                elif self.remove:
                    syncer = ftp.delete_file

                counter += 1
                tries = 0
                done = False
                lastrc = None
                while tries < 5:
                    tries += 1
                    self.Entropy.updateProgress(
                        "[%s|#%s|(%s/%s)] %s: %s" % (
                            blue(crippled_uri),
                            darkgreen(str(tries)),
                            blue(str(counter)),
                            bold(str(maxcount)),
                            blue(action+"ing"),
                            red(os.path.basename(mypath)),
                        ),
                        importance = 0,
                        type = "info",
                        header = red(" @@ ")
                    )
                    rc = syncer(*myargs)
                    if rc and self.use_handlers and not self.download:
                        rc = self.handler_verify_upload(mypath, uri, counter, maxcount, tries)
                    if rc:
                        self.Entropy.updateProgress(
                            "[%s|#%s|(%s/%s)] %s %s: %s" % (
                                        blue(crippled_uri),
                                        darkgreen(str(tries)),
                                        blue(str(counter)),
                                        bold(str(maxcount)),
                                        blue(action),
                                        _("successful"),
                                        red(os.path.basename(mypath)),
                            ),
                            importance = 0,
                            type = "info",
                            header = darkgreen(" @@ ")
                        )
                        done = True
                        break
                    else:
                        self.Entropy.updateProgress(
                            "[%s|#%s|(%s/%s)] %s %s: %s" % (
                                        blue(crippled_uri),
                                        darkgreen(str(tries)),
                                        blue(str(counter)),
                                        bold(str(maxcount)),
                                        blue(action),
                                        brown(_("failed, retrying")),
                                        red(os.path.basename(mypath)),
                                ),
                            importance = 0,
                            type = "warning",
                            header = brown(" @@ ")
                        )
                        lastrc = rc
                        continue

                if not done:

                    self.Entropy.updateProgress(
                        "[%s|(%s/%s)] %s %s: %s - %s: %s" % (
                                blue(crippled_uri),
                                blue(str(counter)),
                                bold(str(maxcount)),
                                blue(action),
                                darkred("failed, giving up"),
                                red(os.path.basename(mypath)),
                                _("error"),
                                lastrc,
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )

                    if mypath not in self.critical_files:
                        self.Entropy.updateProgress(
                            "[%s|(%s/%s)] %s: %s, %s..." % (
                                blue(crippled_uri),
                                blue(str(counter)),
                                bold(str(maxcount)),
                                blue(_("not critical")),
                                os.path.basename(mypath),
                                blue(_("continuing")),
                            ),
                            importance = 1,
                            type = "warning",
                            header = brown(" @@ ")
                        )
                        continue

                    ftp.close()
                    errors = True
                    broken_uris.add((uri,lastrc))
                    # next mirror
                    break

            # close connection
            ftp.close()
            fine_uris.add(uri)

        return errors,fine_uris,broken_uris