# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy base transceivers module}.

"""
import os
import sys
import time
import signal
import tempfile

if sys.hexversion >= 0x3000000:
    import urllib.request as urlmod
    import urllib.error as urlmod_error
else:
    import urllib2 as urlmod
    import urllib2 as urlmod_error

from entropy.tools import print_traceback, get_file_size, \
    convert_seconds_to_fancy_output, bytes_into_human, spliturl
from entropy.const import etpConst, const_isfileobj, const_isnumber
from entropy.output import TextInterface, darkblue, darkred, purple, blue, \
    brown, darkgreen, red, bold

from entropy.i18n import _
from entropy.misc import ParallelTask, Lifo
from entropy.core.settings.base import SystemSettings

from entropy.exceptions import UriHandlerNotFound, ConnectionError, \
    TransceiverError

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
            raise AttributeError("IncorrectParameter: %s" % (mytxt,))
        elif not hasattr(self.__Output.updateProgress, '__call__'):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise AttributeError("IncorrectParameter: %s" % (mytxt,))

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
                self.entropyTools.print_traceback()
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
        self.__average = int((kbytecount/self.__remotesize)*100)
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

            t = ParallelTask(do_download, self.__download_statuses, th_id, downloader)
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


class EntropyTransceiver(TextInterface):

    _URI_HANDLERS = []

    """
    Base class for Entropy transceivers. This provides a common API across
    all the available URI handlers.

    # FIXME: allow to provide other OutputInterfaces

    How to use this class:
      Let's consider that we have a valid EntropyUriHandler for ftp:// protocol
      already installed via "add_uri_handler".

      >> txc = EntropyTransceiver("ftp://myuser:mypwd@myhost")
      >> txc.set_speed_limit(150) # set speed limit to 150kb/sec
      >> handler = txc.swallow()
      >> handler.download("ftp://myuser:mypwd@myhost/myfile.txt", "/tmp")
         # download 

    """

    @staticmethod
    def add_uri_handler(entropy_uri_handler_class):
        """
        Add custom URI handler to EntropyTransceiver class.

        @param entropy_uri_handler_class: EntropyUriHandler based class
        @type entropy_uri_handler_class; EntropyUriHandler instance
        """
        if not issubclass(entropy_uri_handler_class, EntropyUriHandler):
            raise AttributeError("EntropyUriHandler based class expected")
        EntropyTransceiver._URI_HANDLERS.append(entropy_uri_handler_class)

    @staticmethod
    def remove_uri_handler(entropy_uri_handler_class):
        """
        Remove custom URI handler to EntropyTransceiver class.

        @param entropy_uri_handler_class: EntropyUriHandler based instance
        @type entropy_uri_handler_class; EntropyUriHandler instance
        @raise ValueError: if provided EntropyUriHandler is not in storage.
        """
        if not issubclass(entropy_uri_handler_class, EntropyUriHandler):
            raise AttributeError("EntropyUriHandler based class expected")
        EntropyTransceiver._URI_HANDLERS.remove(entropy_uri_handler_class)

    @staticmethod
    def get_uri_handlers():
        """
        Return a copy of the internal list of URI handler instances.

        @return: URI handlers instances list
        @rtype: list
        """
        return EntropyTransceiver._URI_HANDLERS[:]

    @staticmethod
    def get_uri_name(uri):
        """
        Given an URI, extract and return the URI name (hostname).

        @param uri: URI to handle
        @type uri: string
        @return: URI name
        @rtype: string
        @raise UriHandlerNotFound: if no URI handlers can deal with given URI
            string
        """
        handlers = EntropyTransceiver.get_uri_handlers()
        for handler in handlers:
            if handler.approve_uri(uri):
                return handler.get_uri_name(uri)

        raise UriHandlerNotFound(
            "no URI handler available for %s" % (uri,))

    @staticmethod
    def hide_sensible_data(uri):
        """
        Given an URI, hide sensible data from string and return it back.

        @param uri: URI to handle
        @type uri: string
        @return: URI cleaned
        @rtype: string
        @raise UriHandlerNotFound: if no URI handlers can deal with given URI
            string
        """
        handlers = EntropyTransceiver.get_uri_handlers()
        for handler in handlers:
            if handler.approve_uri(uri):
                return handler.hide_sensible_data(uri)

        raise UriHandlerNotFound(
            "no URI handler available for %s" % (uri,))

    def __init__(self, uri):
        """
        EntropyTransceiver constructor, just pass the friggin URI(tm).

        @param uri: URI to handle
        @type uri: string
        """
        self._uri = uri
        self._speed_limit = 0
        self._verbose = False
        self._timeout = None
        self._silent = None
        self._output_interface = None
        self.__with_stack = Lifo()

    def __enter__(self):
        """
        Support for "with" statement, this method will execute swallow() and
        return a valid EntropyUriHandler instance.
        """
        handler = self.swallow()
        self.__with_stack.push(handler)
        return handler

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Support for "with" statement, this method will automagically close the
        previously created EntropyUriHandler instance connection.
        """
        handler = self.__with_stack.pop() # if this fails, it's not a good sign
        handler.close()

    def set_output_interface(self, output_interface):
        """
        Provide alternative Entropy output interface (must be based on
        entropy.output.TextInterface)

        @param output_interface: new entropy.output.TextInterface instance to
            use
        @type output_interface: entropy.output.TextInterface based instance
        @raise AttributeError: if argument passed is not correct
        """
        if not isinstance(output_interface, TextInterface):
            raise AttributeError(
                "expected a valid TextInterface based instance")
        self._output_interface = output_interface

    def set_speed_limit(self, speed_limit):
        """
        Set download/upload speed limit in kb/sec form.
        Zero value will be considered as "disable speed limiter".

        @param speed_limit: speed limit in kb/sec form.
        @type speed_limit: int
        @raise AttributeError: if speed_limit is not an integer
        """
        if not const_isnumber(speed_limit):
            raise AttributeError("expected a valid number")
        self._speed_limit = speed_limit

    def set_timeout(self, timeout):
        """
        Set transceiver tx/rx timeout value in seconds.

        @param timeout: timeout in seconds
        @type timeout: int
        """
        if not const_isnumber(timeout):
            raise AttributeError("not a number")
        self._timeout = timeout

    def set_silent(self, silent):
        """
        Disable transceivers verbosity.

        @param verbosity: verbosity value
        @type verbosity: bool
        """
        self._silent = silent

    def set_verbosity(self, verbosity):
        """
        Set transceiver verbosity.

        @param verbosity: verbosity value
        @type verbosity: bool
        """
        if not isinstance(verbosity, bool):
            raise AttributeError("expected a valid bool")
        self._verbose = verbosity

    def swallow(self):
        """
        Given the URI at the constructor, this method returns the first valid
        URI handler instance found that can be used to do required action.

        @raise entropy.exceptions.UriHandlerNotFound: when URI handler for given
            URI is not available.
        """
        handlers = EntropyTransceiver.get_uri_handlers()
        for handler in handlers:
            if handler.approve_uri(self._uri):
                handler_instance = handler(self._uri)
                if self._output_interface is not None:
                    handler_instance.set_output_interface(
                        self._output_interface)
                if const_isnumber(self._speed_limit):
                    handler_instance.set_speed_limit(self._speed_limit)
                handler_instance.set_verbosity(self._verbose)
                handler_instance.set_silent(self._silent)
                if const_isnumber(self._timeout):
                    handler_instance.set_timeout(self._timeout)
                return handler_instance

        raise UriHandlerNotFound(
            "no URI handler available for %s" % (self._uri,))


class EntropyUriHandler(TextInterface):
    """
    Base class for EntropyTransceiver URI handler interfaces. This provides
    a common API for implementing custom URI handlers.

    To add your URI handler to EntropyTransceiver, do the following:
    >>> EntropyTransceiver.add_uri_handler(my_entropy_transceiver_based_instance)
    "add_uri_handler" is a EntropyTransceiver static method.
    """
    def __init__(self, uri):
        """
        EntropyUriHandler constructor.
        When constructor is called, instance should perform a connection and
        permissions check and raise entropy.exceptions.ConnectionError in case
        of issues.

        @param uri: URI to handle
        @type uri: string
        """
        self._uri = uri
        self._speed_limit = 0
        self._verbose = False
        self._silent = False
        self._timeout = None

    def __enter__(self):
        """
        Support for "with" statement, this will trigger UriHandler connection
        setup.
        """
        raise NotImplementedError()

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Support for "with" statement, this will trigger UriHandler connection
        hang up.
        """
        raise NotImplementedError()

    @staticmethod
    def approve_uri(uri):
        """
        Approve given URI by returning True or False depending if this
        class is able to handle it.

        @param uri: URI to handle
        @type uri: string
        @return: True, if URI can be handled by this class
        @rtype: bool
        """
        raise NotImplementedError()

    @staticmethod
    def get_uri_name(uri):
        """
        Given a valid URI (meaning that implementation can handle the provided
        URI), it extracts and returns the URI name (hostname).

        @param uri: URI to handle
        @type uri: string
        @return: URI name
        @rtype: string
        """
        raise NotImplementedError()

    @staticmethod
    def hide_sensible_data(uri):
        """
        Given an URI, hide sensible data from string and return it back.

        @param uri: URI to handle
        @type uri: string
        @return: URI cleaned
        @rtype: string
        """
        raise NotImplementedError()

    def get_uri(self):
        """
        Return copy of previously stored URI.

        @return: stored URI
        @rtype: string
        """
        return self._uri[:]

    def set_output_interface(self, output_interface):
        """
        Provide alternative Entropy output interface (must be based on
        entropy.output.TextInterface)

        @param output_interface: new entropy.output.TextInterface instance to
            use
        @type output_interface: entropy.output.TextInterface based instance
        @raise AttributeError: if argument passed is not correct
        """
        if not isinstance(output_interface, TextInterface):
            raise AttributeError(
                "expected a valid TextInterface based instance")
        self.updateProgress = output_interface.updateProgress
        self.askQuestion = output_interface.askQuestion

    def set_speed_limit(self, speed_limit):
        """
        Set download/upload speed limit in kb/sec form.

        @param speed_limit: speed limit in kb/sec form.
        @type speed_limit: int
        """
        if not const_isnumber(speed_limit):
            raise AttributeError("not a number")
        self._speed_limit = speed_limit

    def set_timeout(self, timeout):
        """
        Set transceiver tx/rx timeout value in seconds.

        @param timeout: timeout in seconds
        @type timeout: int
        """
        if not const_isnumber(timeout):
            raise AttributeError("not a number")
        self._timeout = timeout

    def set_silent(self, silent):
        """
        Disable transceiver verbosity.

        @param verbosity: verbosity value
        @type verbosity: bool
        """
        self._silent = silent

    def set_verbosity(self, verbosity):
        """
        Set transceiver verbosity.

        @param verbosity: verbosity value
        @type verbosity: bool
        """
        self._verbose = verbosity

    def download(self, remote_path, save_path):
        """
        Download URI and save it to save_path.

        @param remote_path: remote path to handle
        @type remote_path: string
        @param save_path: complete path where to store file from uri.
            If directory doesn't exist, it will be created with default
            Entropy permissions.
        @type save_path: string
        @return: execution status, True if done
        @rtype: bool
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def upload(self, load_path, remote_path):
        """
        Upload URI from load_path location to uri.

        @param load_path: remote path to handle
        @type load_path: string
        @param remote_path: remote path to handle ("directory"/"file name" !)
        @type remote_path: string
        @return: execution status, True if done
        @rtype: bool
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def rename(self, remote_path_old, remote_path_new):
        """
        Rename URI old to URI new.

        @param remote_path_old: remote path to handle
        @type remote_path_old: string
        @param remote_path_new: remote path to create
        @type remote_path_new: string
        @return: execution status, True if done
        @rtype: bool
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def delete(self, remote_path):
        """
        Remove the remote path (must be a file).

        @param remote_path_old: remote path to remove (only file allowed)
        @type remote_path_old: string
        @return: True, if operation went successful
        @rtype: bool
        @return: execution status, True if done
        @rtype: bool
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def get_md5(self, remote_path):
        """
        Return MD5 checksum of file at URI.

        @param remote_path: remote path to handle
        @type remote_path: string
        @return: MD5 checksum in hexdigest form
        @rtype: string or None (if not supported)
        """
        raise NotImplementedError()

    def list_content(self, remote_path):
        """
        List content of directory referenced at URI.

        @param remote_path: remote path to handle
        @type remote_path: string
        @return: content
        @rtype: list
        @raise ValueError: if remote_path does not exist
        """
        raise NotImplementedError()

    def list_content_metadata(self, remote_path):
        """
        List content of directory referenced at URI with metadata in this form:
        [(name, size, owner, group, permissions<drwxr-xr-x>,), ...]
        permissions, owner, group, size, name.

        @param remote_path: remote path to handle
        @type remote_path: string
        @return: content
        @rtype: list
        @raise ValueError: if remote_path does not exist
        """
        raise NotImplementedError()

    def is_path_available(self, remote_path):
        """
        Given a remote path (which can point to dir or file), determine whether
        it's available or not.

        @param remote_path: URI to handle
        @type remote_path: string
        @return: availability
        @rtype: bool
        """
        raise NotImplementedError()

    def is_dir(self, remote_path):
        """
        Given a remote path (which can point to dir or file), determine whether
        it's a directory.

        @param remote_path: URI to handle
        @type remote_path: string
        @return: True, if remote_path is a directory
        @rtype: bool
        """
        raise NotImplementedError()

    def is_file(self, remote_path):
        """
        Given a remote path (which can point to dir or file), determine whether
        it's a file.

        @param remote_path: URI to handle
        @type remote_path: string
        @return: True, if remote_path is a file
        @rtype: bool
        """
        raise NotImplementedError()

    def makedirs(self, remote_path):
        """
        Given a remote path, recursively create all the missing directories.

        @param remote_path: URI to handle
        @type remote_path: string
        """
        raise NotImplementedError()

    def keep_alive(self):
        """
        Send a keep-alive ping to handler.
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def close(self):
        """
        Called when requesting to close connection completely.
        """
        raise NotImplementedError()


class EntropyFtpUriHandler(EntropyUriHandler):

    """
    EntropyUriHandler based FTP transceiver plugin.
    """

    _DEFAULT_TIMEOUT = 60

    @staticmethod
    def approve_uri(uri):
        if uri.startswith("ftp://"):
            return True
        return False

    @staticmethod
    def get_uri_name(uri):
        myuri = spliturl(uri)[1]
        # remove username:pass@
        myuri = myuri.split("@")[-1]
        return myuri

    @staticmethod
    def hide_sensible_data(uri):
        ftppassword = uri.split("@")[:-1]
        if not ftppassword:
            return uri
        ftppassword = '@'.join(ftppassword)
        ftppassword = ftppassword.split(":")[-1]
        if not ftppassword:
            return uri
        newuri = uri.replace(ftppassword, "xxxxxxxx")
        return newuri

    def __init__(self, uri):
        EntropyUriHandler.__init__(self, uri)

        import socket, ftplib
        self.socket, self.ftplib = socket, ftplib
        self.__connected = False
        self.__ftpconn = None
        self.__currentdir = '.'
        self.__ftphost = EntropyFtpUriHandler.get_uri_name(self._uri)
        self.__ftpuser, self.__ftppassword, self.__ftpport, self.__ftpdir = \
            self.__extract_ftp_data(self._uri)

        self._init_vars()

        # as documentation suggests
        # test out connection first
        self._connect()
        self._disconnect()

    def __enter__(self):
        pass # self.__connect_if_not()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __extract_ftp_data(self, ftpuri):
        ftpuser = ftpuri.split("ftp://")[-1].split(":")[0]
        if (not ftpuser):
            ftpuser = "anonymous@"
            ftppassword = "anonymous"
        else:
            ftppassword = ftpuri.split("@")[:-1]
            if len(ftppassword) > 1:
                ftppassword = '@'.join(ftppassword)
                ftppassword = ftppassword.split(":")[-1]
                if (not ftppassword):
                    ftppassword = "anonymous"
            else:
                ftppassword = ftppassword[0]
                ftppassword = ftppassword.split(":")[-1]
                if not ftppassword:
                    ftppassword = "anonymous"

        ftpport = ftpuri.split(":")[-1]
        try:
            ftpport = int(ftpport)
        except ValueError:
            ftpport = 21

        ftpdir = '/'
        if ftpuri.count("/") > 2:
            if ftpuri.startswith("ftp://"):
                ftpdir = ftpuri[6:]
            ftpdir = "/" + ftpdir.split("/", 1)[-1]
            ftpdir = ftpdir.split(":")[0]
            if not ftpdir:
                ftpdir = '/'
            elif ftpdir.endswith("/") and (ftpdir != "/"):
                ftpdir = ftpdir[:-1]

        return ftpuser, ftppassword, ftpport, ftpdir

    def __connect_if_not(self):
        """
        Handy internal method.
        """
        if not self.__connected:
            self._connect()
        try:
            self.keep_alive()
        except ConnectionError:
            self._connect()

    def _connect(self):
        """
        Connect to FTP host.
        """
        timeout = self._timeout
        if timeout is None:
            # default timeout set to 60 seconds
            timeout = EntropyFtpUriHandler._DEFAULT_TIMEOUT

        count = 10
        while True:
            count -= 1
            try:
                self.__ftpconn = self.ftplib.FTP()
                self.__ftpconn.connect(self.__ftphost, self.__ftpport, timeout)
                break
            except (self.socket.gaierror,) as e:
                raise ConnectionError('ConnectionError: %s' % (e,))
            except (self.socket.error,) as e:
                if not count:
                    raise ConnectionError('ConnectionError: %s' % (e,))
            except:
                if not count:
                    raise

        if self._verbose:
            mytxt = _("connecting with user")
            self.updateProgress(
                "[ftp:%s] %s: %s" % (
                    darkgreen(self.__ftphost), mytxt, blue(self.__ftpuser),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        try:
            self.__ftpconn.login(self.__ftpuser, self.__ftppassword)
        except self.ftplib.error_perm as e:
            raise ConnectionError('ConnectionError: %s' % (e,))

        if self._verbose:
            mytxt = _("switching to")
            self.updateProgress(
                "[ftp:%s] %s: %s" % (
                    darkgreen(self.__ftphost), mytxt, blue(self.__ftpdir),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        # create dirs if they don't exist
        self._set_cwd(self.__ftpdir, dodir = True)
        self.__connected = True

    def _disconnect(self):
        if self.__ftpconn is not None:
            # try to disconnect
            try:
                self.__ftpconn.quit()
            except (EOFError, self.socket, self.socket.timeout,
                self.ftplib.error_reply,):
                # AttributeError is raised when socket gets trashed
                # EOFError is raised when the connection breaks
                # timeout, who cares!
                pass
            self.__ftpconn = None
        self.__connected = False

    def _reconnect(self):
        self._disconnect()
        self._connect()

    def _init_vars(self):
        self.__oldprogress_t = time.time()
        self.__datatransfer = 0
        self.__filesize = 0
        self.__filekbcount = 0
        self.__transfersize = 0
        self.__startingposition = 0
        self.__elapsed = 0.0
        self.__time_remaining_secs = 0
        self.__time_remaining = "(%s)" % (_("infinite"),)
        self.__starttime = time.time()

    def _get_cwd(self):
        return self.__ftpconn.pwd()

    def _set_cwd(self, mydir, dodir = False):
        try:
            return self.__set_cwd(mydir, dodir)
        except self.ftplib.error_perm as e:
            raise TransceiverError('TransceiverError: %s' % (e,))

    def __set_cwd(self, mydir, dodir = False):
        if self._verbose:
            mytxt = _("switching to")
            self.updateProgress(
                "[ftp:%s] %s: %s" % (darkgreen(self.__ftphost),
                    mytxt, blue(mydir),),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        try:
            self.__ftpconn.cwd(mydir)
        except self.ftplib.error_perm as e:
            if e[0][:3] == '550' and dodir:
                self.makedirs(mydir)
                self.__ftpconn.cwd(mydir)
            else:
                raise
        self.__currentdir = self._get_cwd()

    def _set_pasv(self, pasv):
        self.__ftpconn.set_pasv(pasv)

    def _set_chmod(self, chmodvalue, filename):
        return self.__ftpconn.voidcmd("SITE CHMOD " + str(chmodvalue) + " " + \
            str(filename))

    def _get_file_mtime(self, path):
        rc = self.__ftpconn.sendcmd("mdtm " + path)
        return rc.split()[-1]

    def _send_cmd(self, cmd):
        return self.__ftpconn.sendcmd(cmd)

    def _update_speed(self):
        current_time = time.time()
        self.__elapsed = current_time - self.__starttime
        # we have the diff size
        pos_diff = self.__transfersize - self.__startingposition
        self.__datatransfer = pos_diff / self.__elapsed
        if self.__datatransfer < 0:
            self.__datatransfer = 0
        try:
            round_fsize = int(round(self.__filesize*1024, 0))
            round_rsize = int(round(self.__transfersize, 0))
            self.__time_remaining_secs = int(round((round_fsize - \
                round_rsize)/self.__datatransfer, 0))
            self.__time_remaining = \
                convert_seconds_to_fancy_output(self.__time_remaining_secs)
        except (ValueError, TypeError,):
            self.__time_remaining = "(%s)" % (_("infinite"),)

    def _speed_limit_loop(self):
        if self._speed_limit:
            while self.__datatransfer > self._speed_limit * 1024:
                time.sleep(0.1)
                self._update_speed()
                self._update_progress()

    def _commit_buffer_update(self, buf_len):
        # get the buffer size
        self.__filekbcount += float(buf_len)/1024
        self.__transfersize += buf_len

    def _update_progress(self, force = False):

        upload_percent = 100.0
        upload_size = round(self.__filekbcount, 1)

        if self.__filesize >= 1:
            kbcount_round = round(self.__filekbcount, 1)
            upload_percent = round((kbcount_round / self.__filesize) * 100, 1)

        delta_secs = 0.5
        cur_t = time.time()
        if (cur_t > (self.__oldprogress_t + delta_secs)) or force:

            upload_percent = str(upload_percent)+"%"
            # create text
            mytxt = _("Transfer status")
            current_txt = brown("    <-> %s: " % (mytxt,)) + \
                darkgreen(str(upload_size)) + "/" + \
                red(str(self.__filesize)) + " kB " + \
                brown("[") + str(upload_percent) + brown("]") + \
                " " + self.__time_remaining + " " + \
                bytes_into_human(self.__datatransfer) + \
                "/" + _("sec")

            self.updateProgress(current_txt, back = True)
            self.__oldprogress_t = cur_t

    def _get_file_size(self, filename):
        return self.__ftpconn.size(filename)

    def _get_file_size_compat(self, filename):
        try:
            sc = self.__ftpconn.sendcmd
            data = [x.split() for x in sc("stat %s" % (filename,)).split("\n")]
        except self.ftplib.error_temp:
            return ""
        for item in data:
            if item[-1] == filename:
                return item[4]
        return ""

    def _mkdir(self, directory):
        return self.__ftpconn.mkd(directory)

    def download(self, remote_path, save_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)
        tmp_save_path = save_path + ".dtmp"

        def writer(buf):
            # writing file buffer
            f.write(buf)
            self._commit_buffer_update(len(buf))
            self._update_speed()
            self._update_progress()
            self._speed_limit_loop()

        tries = 10
        while tries:
            tries -= 1

            self._init_vars()
            try:

                self.__filekbcount = 0
                # get the file size
                self.__filesize = self._get_file_size_compat(path)
                if (self.__filesize):
                    self.__filesize = round(float(int(self.__filesize))/1024, 1)
                    if (self.__filesize == 0):
                        self.__filesize = 1
                elif not self.is_path_available(path):
                    return False
                else:
                    self.__filesize = 0

                with open(tmp_save_path, "wb") as f:
                    rc = self.__ftpconn.retrbinary('RETR ' + path, writer, 8192)
                    f.flush()
                self._update_progress(force = True)

                done = rc.find("226") != -1
                if done:
                    # download complete, atomic mv
                    os.rename(tmp_save_path, save_path)

                return done

            except Exception as e: # connection reset by peer

                print_traceback()
                mytxt = red("%s: %s, %s... #%s") % (
                    _("Download issue"),
                    e,
                    _("retrying"),
                    tries+1,
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = "  "
                    )
                self._reconnect() # reconnect

    def upload(self, load_path, remote_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        tmp_path = path + ".dtmp"
        tries = 0

        def updater(buf):
            self._commit_buffer_update(len(buf))
            self._update_speed()
            self._update_progress()
            self._speed_limit_loop()

        while tries < 10:

            tries += 1
            self._init_vars()

            try:

                file_size = get_file_size(load_path)
                self.__filesize = round(float(file_size)/ 1024, 1)
                self.__filekbcount = 0

                with open(load_path, "r") as f:
                    rc = self.__ftpconn.storbinary("STOR " + tmp_path, f,
                        8192, updater)

                self._update_progress(force = True)
                # now we can rename the file with its original name
                self.rename(tmp_path, path)

                done = rc.find("226") != -1
                return done

            except Exception as e: # connection reset by peer

                print_traceback()
                mytxt = red("%s: %s, %s... #%s") % (
                    _("Upload issue"),
                    e,
                    _("retrying"),
                    tries+1,
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = "  "
                    )
                self._reconnect() # reconnect
                self.delete(tmp_path)
                self.delete(path)

    def rename(self, remote_path_old, remote_path_new):

        self.__connect_if_not()

        old = os.path.join(self.__ftpdir, remote_path_old)
        new = os.path.join(self.__ftpdir, remote_path_new)
        try:
            rc = self.__ftpconn.rename(old, new)
        except self.ftplib.error_perm as err:
            # if err[0][:3] in ('553',):
            # workaround for some servers
            # try to delete old file first, and then call rename again
            self.delete(remote_path_new)
            rc = self.__ftpconn.rename(old, new)

        done = rc.find("250") != -1
        return done

    def delete(self, remote_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        done = False
        try:
            rc = self.__ftpconn.delete(path)
            if rc.startswith("250"):
                done = True
        except self.ftplib.error_perm as err:
            if err[0][:3] == '550':
                done = True
            # otherwise not found

        return done

    def get_md5(self, remote_path):
        # PROFTPD with mod_md5 supports it!
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        try:
            rc_data = self.__ftpconn.sendcmd("SITE MD5 %s" % (path,))
        except self.ftplib.error_perm:
            return None # not supported

        try:
            return rc_data.split("\n")[0].split("\t")[0].split("-")[1]
        except (IndexError, TypeError,): # wrong output
            return None

    def list_content(self, remote_path):
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)
        try:
            return [os.path.basename(x) for x in self.__ftpconn.nlst(path)]
        except self.ftplib.error_temp:
            raise ValueError("No such file or directory")

    def list_content_metadata(self, remote_path):
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        mybuffer = []
        def bufferizer(buf):
            mybuffer.append(buf)

        try:
            self.__ftpconn.dir(path, bufferizer)
        except self.ftplib.error_temp:
            raise ValueError("No such file or directory")

        data = []
        for item in mybuffer:
            item = item.split()
            name, size, owner, group, perms = item[8], item[4], item[2], \
                item[3], item[0]
            data.append((name, size, owner, group, perms,))

        return data

    def is_dir(self, remote_path):

        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)

        cwd = self._get_cwd()
        data = True
        try:
            self.__set_cwd(path)
        except self.ftplib.error_perm:
            data = False
        finally:
            self.__set_cwd(cwd)

        return data

    def is_file(self, remote_path):

        if self.is_dir(remote_path):
            return False
        return self.is_path_available(remote_path)

    def _is_path_available(self, full_path):

        path, fn = os.path.split(full_path)
        content = []
        def cb(x):
            y = os.path.basename(x)
            if y == fn:
                content.append(y)

        try:
            self.__ftpconn.retrlines('NLST %s' % (path,), cb)
        except self.ftplib.error_temp as err:
            if not str(err).startswith("450"):
                raise # wtf?
            # path does not exist if FTP error 450 is raised

        if content:
            return True
        return False

    def is_path_available(self, remote_path):
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)
        return self._is_path_available(path)

    def makedirs(self, remote_path):
        self.__connect_if_not()
        path = os.path.join(self.__ftpdir, remote_path)
        mydirs = [x for x in path.split("/") if x]

        mycurpath = ""
        for mydir in mydirs:
            mycurpath = os.path.join(mycurpath, mydir)
            if not self._is_path_available(mycurpath):
                try:
                    self._mkdir(mycurpath)
                except self.ftplib.error_perm as e:
                    if e[0].lower().find("permission denied") != -1:
                        raise
                    elif e[0][:3] != '550':
                        raise

    def keep_alive(self):
        """
        Send a keep-alive ping to handler.
        """
        if not self.__connected:
            raise ConnectionError("keep_alive when not connected")
        try:
            self.__ftpconn.sendcmd("NOOP")
        except (self.ftplib.error_temp, self.ftplib.error_reply,):
            raise ConnectionError("cannot execute keep_alive")

    def close(self):
        """ just call our disconnect method """
        self._disconnect()
EntropyTransceiver.add_uri_handler(EntropyFtpUriHandler)


class EntropySshUriHandler(EntropyUriHandler):

    """
    EntropyUriHandler based SSH (with pubkey) transceiver plugin.
    """

    _DEFAULT_TIMEOUT = 60
    _DEFAULT_PORT = 22
    _TXC_CMD = "/usr/bin/scp"
    _SSH_CMD = "/usr/bin/ssh"

    @staticmethod
    def approve_uri(uri):
        if uri.startswith("ssh://"):
            return True
        return False

    @staticmethod
    def get_uri_name(uri):
        myuri = uri.split("/")[2:][0]
        myuri = myuri.split("@")[-1]
        return myuri

    @staticmethod
    def hide_sensible_data(uri):
        return uri

    def __init__(self, uri):
        EntropyUriHandler.__init__(self, uri)

        import socket, subprocess, pty
        self._socket, self._subprocess = socket, subprocess
        self._pty = pty
        self.__host = EntropySshUriHandler.get_uri_name(self._uri)
        self.__user, self.__port, self.__dir = self.__extract_scp_data(
            self._uri)

        # as documentation suggests
        # test out connection first
        self.__test_connection()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __test_connection(self):
        try:
            self._socket.create_connection((self.__host, self.__port), 5)
        except self._socket.error:
            raise ConnectionError("cannot connect to %s on port %s" % (
                self.__host, self.__port,))

    def __extract_scp_data(self, uri):

        no_ssh_split = uri.split("ssh://")[-1]
        user = no_ssh_split.split("@")[0].split(":")[0]

        port = uri.split(":")[-1]
        try:
            port = int(port)
        except ValueError:
            port = EntropySshUriHandler._DEFAULT_PORT

        sdir = '/'
        if uri.count("/") > 2:
            if uri.startswith("ssh://"):
                sdir = uri[6:]
            sdir = "/" + sdir.split("/", 1)[-1]
            sdir = sdir.split(":")[0]
            if not sdir:
                sdir = '/'
            elif sdir.endswith("/") and (sdir != "/"):
                sdir = sdir[:-1]

        return user, port, sdir

    def _parse_progress_line(self, line):

        line_data = line.strip().split()
        if len(line_data) < 5:
            # mmh... not possible to properly parse data
            self.updateProgress(line, back = True)
            return

        percent = line_data[1]
        tx_speed = line_data[3]
        tx_size = line_data[2]
        eta = line_data[4]

        # create text
        mytxt = _("Transfer status")
        current_txt = brown("    <-> %s: " % (mytxt,)) + \
            darkgreen(tx_size) + " " + \
            brown("[") + str(percent) + brown("]") + \
            " " + eta + " " + tx_speed

        self.updateProgress(current_txt, back = True)

    def _update_progress(self, std_r):
        read_buf = ""
        try:
            char = std_r.read(1)
            while char:
                if (char == "\r") and read_buf:
                    self._parse_progress_line(read_buf)
                    read_buf = ""
                elif (char != "\r"):
                    read_buf += char
                char = std_r.read(1)
        except IOError:
            return

    def _fork_cmd(self, args):

        pid, fd = self._pty.fork()

        if pid == 0:
            proc = self._subprocess.Popen(args)
            os._exit(proc.wait())
        elif pid == -1:
            raise ConnectionError("cannot forkpty()")
        else:
            dead = False
            return_code = 1
            std_r = os.fdopen(fd, "r")
            while not dead:

                try:
                    dead, return_code = os.waitpid(pid, os.WNOHANG)
                except OSError as e:
                    if e.errno != 10:
                        raise
                    dead = True

                time.sleep(0.5)
                self._update_progress(std_r)
            std_r.close()

            return return_code

    def _exec_cmd(self, args):

        fd, tmp_path = tempfile.mkstemp()
        fd_err, tmp_path_err = tempfile.mkstemp()
        os.close(fd)
        os.close(fd_err)

        with open(tmp_path, "wb") as std_f:
            with open(tmp_path_err, "wb") as std_f_err:
                proc = self._subprocess.Popen(args, stdout = std_f,
                    stderr = std_f_err)
                exec_rc = proc.wait()

        std_f = open(tmp_path, "rb")
        output = std_f.read()
        std_f.close()
        std_f = open(tmp_path_err, "rb")
        error = std_f.read()
        std_f.close()

        os.remove(tmp_path)
        os.remove(tmp_path_err)
        return exec_rc, output, error

    def _setup_common_args(self, remote_path):
        args = []
        if self._speed_limit:
            args += ["-l", str(self._speed_limit*8)] # scp wants kbits/sec
        remote_ptr = os.path.join(self.__dir, remote_path)
        remote_str = ""
        if self.__user:
            remote_str += self.__user + "@"
        remote_str += self.__host + ":" + remote_ptr

        return args, remote_str

    def download(self, remote_path, save_path):
        args = [EntropySshUriHandler._TXC_CMD]
        c_args, remote_str = self._setup_common_args(remote_path)
        args.extend(c_args)
        args += ["-B", "-P", str(self.__port), remote_str, save_path]
        return self._fork_cmd(args) == 0

    def upload(self, load_path, remote_path):
        args = [EntropySshUriHandler._TXC_CMD]
        c_args, remote_str = self._setup_common_args(remote_path)
        args.extend(c_args)
        args += ["-B", "-P", str(self.__port), load_path, remote_str]
        return self._fork_cmd(args) == 0

    def _setup_fs_args(self):
        args = [EntropySshUriHandler._SSH_CMD]
        remote_str = ""
        if self.__user:
            remote_str += self.__user + "@"
        remote_str += self.__host
        return args, remote_str

    def rename(self, remote_path_old, remote_path_new):
        args, remote_str = self._setup_fs_args()
        remote_ptr_old = os.path.join(self.__dir, remote_path_old)
        remote_ptr_new = os.path.join(self.__dir, remote_path_new)
        args += [remote_str, "mv", remote_ptr_old, remote_ptr_new]
        return self._exec_cmd(args)[0] == 0

    def delete(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "rm", remote_ptr]
        return self._exec_cmd(args)[0] == 0

    def get_md5(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "md5sum", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        if exec_rc:
            return None
        return output.strip().split()[0]

    def list_content(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "ls", "-1", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        if exec_rc:
            return []
        return [x for x in output.split("\n") if x]

    def list_content_metadata(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "ls", "-1lA", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        if exec_rc:
            return []

        data = []
        for item in output.split("\n"):
            item = item.strip().split()
            if len(item) < 5:
                continue
            perms, owner, group, size, name = item[0], item[2], item[3], \
                item[4], item[-1]
            data.append((name, size, owner, group, perms,))
        return data

    def is_dir(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "test", "-d", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        return exec_rc == 0

    def is_file(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "test", "-f", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        return exec_rc == 0

    def is_path_available(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "stat", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        return exec_rc == 0

    def makedirs(self, remote_path):
        args, remote_str = self._setup_fs_args()
        remote_ptr = os.path.join(self.__dir, remote_path)
        args += [remote_str, "mkdir", "-p", remote_ptr]
        exec_rc, output, error = self._exec_cmd(args)
        return exec_rc == 0

    def keep_alive(self):
        return

    def close(self):
        return

EntropyTransceiver.add_uri_handler(EntropySshUriHandler)
