# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Transceivers Fetchers submodule}.

"""
import os
import sys
import time

if sys.hexversion >= 0x3000000:
    import urllib.request as urlmod
    import urllib.error as urlmod_error
else:
    import urllib2 as urlmod
    import urllib2 as urlmod_error

from entropy.tools import print_traceback, get_file_size, \
    convert_seconds_to_fancy_output, bytes_into_human, spliturl
from entropy.const import etpConst, const_isfileobj
from entropy.output import TextInterface, darkblue, darkred, purple, blue, \
    brown, darkgreen, red

from entropy.i18n import _
from entropy.misc import ParallelTask
from entropy.core.settings.base import SystemSettings


class UrlFetcher:

    def __init__(self, url, path_to_save, checksum = True,
            show_speed = True, resume = True,
            abort_check_func = None, disallow_redirect = False,
            thread_stop_func = None, speed_limit = None,
            OutputInterface = None):

        self.__system_settings = SystemSettings()
        if speed_limit == None:
            speed_limit = \
                self.__system_settings['repositories']['transfer_limit']

        self.progress = None
        import entropy.tools as entropyTools
        import socket
        self.entropyTools, self.socket = entropyTools, socket
        self.__timeout = \
            self.__system_settings['repositories']['timeout']
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
        self.__existed_before = False
        self.localfile = None

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
        self.__Output = OutputInterface
        if self.__Output == None:
            self.__Output = TextInterface()
        elif not hasattr(self.__Output, 'updateProgress'):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise AttributeError(mytxt)
        elif not hasattr(self.__Output.updateProgress, '__call__'):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise AttributeError(mytxt)

    def _init_vars(self):
        self.__resumed = False
        self.__buffersize = 8192
        self.__status = None
        self.__remotefile = None
        self.__downloadedsize = 0
        self.__average = 0
        self.__remotesize = 0
        self.__oldaverage = 0.0
        self.__last_output_time = time.time()
        # transfer status data
        self.__startingposition = 0
        self.__datatransfer = 0
        self.__time_remaining = "(infinite)"
        self.__time_remaining_secs = 0
        self.__elapsed = 0.0
        self.__updatestep = 0.2
        self.__starttime = time.time()
        self.__existed_before = False
        if os.path.lexists(self.__path_to_save):
            self.__existed_before = True
        self.__setup_resume_support()
        self._setup_proxy()

    def __setup_resume_support(self):
        # if client uses this instance more than
        # once, make sure we close previously opened
        # files.
        if const_isfileobj(self.localfile):
            try:
                self.localfile.flush()
                self.localfile.close()
            except (IOError, OSError,):
                pass

        # resume support
        if os.path.isfile(self.__path_to_save) and \
            os.access(self.__path_to_save, os.W_OK) and self.__resume:

            self.localfile = open(self.__path_to_save, "ab")
            self.localfile.seek(0, os.SEEK_END)
            self.__startingposition = int(self.localfile.tell())
            self.__resumed = True
            return

        self.localfile = open(self.__path_to_save, "wb")

    def _setup_proxy(self):
        # setup proxy, doing here because config is dynamic
        mydict = {}
        proxy_data = self.__system_settings['system']['proxy']
        if proxy_data['ftp']:
            mydict['ftp'] = proxy_data['ftp']
        if proxy_data['http']:
            mydict['http'] = proxy_data['http']
        if mydict:
            mydict['username'] = proxy_data['username']
            mydict['password'] = proxy_data['password']
            self.entropyTools.add_proxy_opener(urlmod, mydict)
        else:
            # unset
            urlmod._opener = None

    def __encode_url(self, url):
        if sys.hexversion >= 0x3000000:
            import urllib.parse as encurl
        else:
            import urllib as encurl
        url = os.path.join(os.path.dirname(url),
            encurl.quote(os.path.basename(url)))
        return url

    def set_id(self, th_id):
        self.__th_id = th_id

    def download(self):

        self._init_vars()

        if self.__url.startswith("http://"):
            headers = { 'User-Agent' : self.user_agent }
            req = urlmod.Request(self.__url, headers = headers)
        else:
            req = self.__url

        u_agent_error = False
        while True:
            # get file size if available
            try:
                self.__remotefile = urlmod.urlopen(req, None, self.__timeout)
            except KeyboardInterrupt:
                self.__close(False)
                raise
            except urlmod_error.HTTPError as e:
                if (e.code == 405) and not u_agent_error:
                    # server doesn't like our user agent
                    req = self.__url
                    u_agent_error = True
                    continue
                self.__close(True)
                self.__status = "-3"
                return self.__status

            except urlmod_error.URLError as err: # timeout error
                self.__close(True)
                self.__status = "-3"
                return self.__status

            except:
                print_traceback()
                raise
            break

        try:
            self.__remotesize = int(self.__remotefile.headers.get(
                "content-length"))
            self.__remotefile.close()
        except KeyboardInterrupt:
            self.__close(False)
            raise
        except:
            pass

        # handle user stupidity
        try:
            request = self.__url
            if ((self.__startingposition > 0) and (self.__remotesize > 0)) \
                and (self.__startingposition < self.__remotesize):

                try:
                    request = urlmod.Request(
                        self.__url,
                        headers = {
                            "Range" : "bytes=" + \
                                str(self.__startingposition) + "-" + \
                                str(self.__remotesize)
                        }
                    )
                except KeyboardInterrupt:
                    self.__close(False)
                    raise
                except:
                    pass
            elif (self.__startingposition == self.__remotesize):
                # all fine then!
                self.__close(False)
                return self.__prepare_return()

            self.__remotefile = urlmod.urlopen(request, None, self.__timeout)
        except KeyboardInterrupt:
            self.__close(False)
            raise
        except:
            self.__close(True)
            self.__status = "-3"
            return self.__status

        if self.__remotesize > 0:
            self.__remotesize = float(int(self.__remotesize))/1024

        if self.__disallow_redirect and \
            (self.__url != self.__remotefile.geturl()):

            self.__close(True)
            self.__status = "-3"
            return self.__status

        while True:
            try:
                rsx = self.__remotefile.read(self.__buffersize)
                if not rsx:
                    break
                if self.__abort_check_func != None:
                    self.__abort_check_func()
                if self.__thread_stop_func != None:
                    self.__thread_stop_func()
            except KeyboardInterrupt:
                self.__close(False)
                raise
            except self.socket.timeout:
                self.__close(False)
                self.__status = "-4"
                return self.__status
            except:
                # python 2.4 timeouts go here
                self.__close(True)
                self.__status = "-3"
                return self.__status

            self._commit(rsx)
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
                    self._update_speed()
                    if self.__show_speed:
                        self.updateProgress()
                        self.__oldaverage = self.__average

        self._push_progress_to_output()
        # kill thread
        self.__close(False)
        return self.__prepare_return()


    def __prepare_return(self):
        if self.__checksum:
            self.__status = self.entropyTools.md5sum(self.__path_to_save)
            return self.__status
        self.__status = "-2"
        return self.__status

    def _commit(self, mybuffer):
        # writing file buffer
        self.localfile.write(mybuffer)
        # update progress info
        self.__downloadedsize = self.localfile.tell()
        kbytecount = float(self.__downloadedsize)/1024
        average = int((kbytecount/self.__remotesize)*100)
        if average > 100:
            average = 100
        self.__average = average
        self._update_speed()

    def __close(self, errored):
        self._update_speed()
        try:
            if const_isfileobj(self.localfile):
                self.localfile.flush()
                self.localfile.close()
        except IOError:
            pass
        if (not self.__existed_before) and errored:
            try:
                os.remove(self.__path_to_save)
            except OSError:
                pass
        try:
            self.__remotefile.close()
        except:
            pass

    def _update_speed(self):
        cur_time = time.time()
        self.__elapsed = cur_time - self.__starttime
        # we have the diff size
        x_delta = self.__downloadedsize - self.__startingposition
        self.__datatransfer = x_delta / self.__elapsed
        if self.__datatransfer < 0:
            self.__datatransfer = 0
        try:
            rounded_remote = int(round(self.__remotesize*1024, 0))
            rounded_downloaded = int(round(self.__downloadedsize, 0))
            x_delta = rounded_remote - rounded_downloaded
            tx_round = 0
            if self.__datatransfer > 0:
                tx_round = int(round(x_delta/self.__datatransfer, 0))
            self.__time_remaining_secs = tx_round
            self.__time_remaining = \
                convert_seconds_to_fancy_output(self.__time_remaining_secs)
        except (ValueError, TypeError,):
            self.__time_remaining = "(%s)" % (_("infinite"),)

    def get_transfer_rate(self):
        return self.__datatransfer

    def is_resumed(self):
        return self.__resumed

    def handle_statistics(self, th_id, downloaded_size, total_size,
            average, old_average, update_step, show_speed, data_transfer,
            time_remaining, time_remaining_secs):
        return

    def _push_progress_to_output(self):

        mytxt = _("[F]")
        eta_txt = _("ETA")
        sec_txt = _("sec") # as in XX kb/sec

        current_txt = darkred("    %s: " % (mytxt,)) + \
            darkgreen(str(round(float(self.__downloadedsize)/1024, 1))) + "/" \
            + red(str(round(self.__remotesize, 1))) + " kB"
        # create progress bar
        barsize = 10
        bartext = "["
        curbarsize = 1

        averagesize = (self.__average*barsize)/100
        while averagesize > 0:
            curbarsize += 1
            bartext += "="
            averagesize -= 1
        bartext += ">"
        diffbarsize = barsize - curbarsize
        while diffbarsize > 0:
            bartext += " "
            diffbarsize -= 1
        if self.__show_speed:
            bartext += "] => %s" % (bytes_into_human(self.__datatransfer),)
            bartext += "/%s : %s: %s" % (sec_txt, eta_txt,
                self.__time_remaining,)
        else:
            bartext += "]"
        average = str(self.__average)
        if len(average) < 2:
            average = " "+average
        current_txt += " <->  "+average+"% "+bartext
        self.__Output.updateProgress(current_txt, back = True)

    def updateProgress(self):
        """
        Main fetch progress callback. You can reimplement this to refresh
        your output devices.
        """
        update_time_delta = 0.5
        cur_t = time.time()
        if cur_t > (self.__last_output_time + update_time_delta):
            self.__last_output_time = cur_t
            self._push_progress_to_output()


class MultipleUrlFetcher:

    import entropy.tools as entropyTools
    def __init__(self, url_path_list, checksum = True,
            show_speed = True, resume = True,
            abort_check_func = None, disallow_redirect = False,
            OutputInterface = None, UrlFetcherClass = None):
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
            @param UrlFetcherClass, urlFetcher instance/interface used
        """
        self.__system_settings = SystemSettings()
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
        elif not hasattr(self.__Output, 'updateProgress'):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise AttributeError("IncorrectParameter: %s" % (mytxt,))
        elif not hasattr(self.__Output.updateProgress, '__call__'):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise AttributeError("IncorrectParameter: %s" % (mytxt,))

        self.__url_fetcher = UrlFetcherClass
        if self.__url_fetcher == None:
            self.__url_fetcher = UrlFetcher


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
        self.__progress_update_t = time.time()
        self.__startup_time = time.time()

    def download(self):
        self._init_vars()

        th_id = 0
        speed_limit = 0
        dsl = self.__system_settings['repositories']['transfer_limit']
        if isinstance(dsl, int) and self.__url_path_list:
            speed_limit = dsl/len(self.__url_path_list)

        class MyFetcher(self.__url_fetcher):

            def __init__(self, klass, multiple, *args, **kwargs):
                klass.__init__(self, *args, **kwargs)
                self.__multiple_fetcher = multiple

            def updateProgress(self):
                return self.__multiple_fetcher.updateProgress()

            def _push_progress_to_output(self):
                return

            def handle_statistics(self, *args, **kwargs):
                return self.__multiple_fetcher.handle_statistics(*args,
                    **kwargs)

        for url, path_to_save in self.__url_path_list:
            th_id += 1
            downloader = MyFetcher(self.__url_fetcher, self, url, path_to_save,
                checksum = self.__checksum, show_speed = self.__show_speed,
                resume = self.__resume,
                abort_check_func = self.__abort_check_func,
                disallow_redirect = self.__disallow_redirect,
                thread_stop_func = self.__handle_threads_stop,
                speed_limit = speed_limit,
                OutputInterface = self.__Output
            )
            downloader.set_id(th_id)

            def do_download(ds, th_id, downloader):
                ds[th_id] = downloader.download()

            t = ParallelTask(do_download, self.__download_statuses, th_id,
                downloader)
            self.__thread_pool[th_id] = t
            t.start()

        self._push_progress_to_output(force = True)
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
            uri = spliturl(url)[1]
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

    def _push_progress_to_output(self, force = False):

        downloaded_size = 0
        total_size = 0
        time_remaining = 0
        update_step = 0
        pd = self.__progress_data.copy()
        pdlen = len(pd)

        # calculation
        for th_id in sorted(pd):
            data = pd.get(th_id)
            downloaded_size += data.get('downloaded_size', 0)
            total_size += data.get('total_size', 0)
            # data_transfer from Python threading bullshit is not reliable
            # with multiple threads and causes inaccurate informations to be
            # printed
            # data_transfer += data.get('data_transfer', 0)
            tr = data.get('time_remaining_secs', 0)
            if tr > 0: time_remaining += tr
            update_step += data.get('update_step', 0)

        elapsed_t = time.time() - self.__startup_time
        if elapsed_t < 0.1:
            elapsed_t = 0.1
        data_transfer = downloaded_size / elapsed_t
        self.__data_transfer = data_transfer

        average = 100
        # total_size is in kbytes
        # downloaded_size is in bytes
        if total_size > 0:
            average = int(float(downloaded_size/1024)/total_size * 100)

        self.__average = average
        if pdlen > 0:
            update_step = update_step/pdlen
        else:
            update_step = 0
        time_remaining = convert_seconds_to_fancy_output(time_remaining)
        self.__time_remaining_sec = time_remaining

        update_time_delta = 0.5
        cur_t = time.time()
        if ((cur_t > (self.__progress_update_t + update_time_delta)) \
            or force or (self.__first_refreshes > 0)) and self.__show_progress:

            self.__first_refreshes -= 1
            self.__progress_update_t = cur_t

            eta_txt = _("ETA")
            sec_txt = _("sec") # as in XX kb/sec
            down_size_txt = str(round(float(downloaded_size)/1024, 1))
            total_size_txt = str(round(total_size, 1))
            current_txt = darkgreen(down_size_txt) + "/" + red(total_size_txt)
            current_txt += " kB"
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
                bartext += "] => %s" % (bytes_into_human(data_transfer),)
                bartext += "/%s : %s: %s" % (sec_txt, eta_txt, time_remaining,)
            else:
                bartext += "]"
            myavg = str(average)
            if len(myavg) < 2:
                myavg = " "+myavg
            current_txt += " <->  "+myavg+"% "+bartext+" "
            self.__Output.updateProgress(current_txt, back = True)

        self.__old_average = average

    def updateProgress(self):
        return self._push_progress_to_output()