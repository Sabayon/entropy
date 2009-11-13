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

if sys.hexversion >= 0x3000000:
    import urllib.request as urlmod
    import urllib.error as urlmod_error
else:
    import urllib2 as urlmod
    import urllib2 as urlmod_error

import time
from entropy.const import etpConst, const_isfileobj, const_isnumber
from entropy.output import TextInterface, darkblue, darkred, purple, blue, \
    brown, darkgreen, red, bold
from entropy.exceptions import *
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
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        elif not hasattr(self.__Output.updateProgress, '__call__'):
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
        # set timeout
        self.socket.setdefaulttimeout(20)

        if self.__url.startswith("http://"):
            headers = { 'User-Agent' : self.user_agent }
            req = urlmod.Request(self.__url, headers = headers)
        else:
            req = self.__url

        u_agent_error = False
        while True:
            # get file size if available
            try:
                self.__remotefile = urlmod.urlopen(req)
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

            self.__remotefile = urlmod.urlopen(request)
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
        self.socket.setdefaulttimeout(2)

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
            tx_round = int(round(x_delta/self.__datatransfer, 0))
            self.__time_remaining_secs = tx_round
            self.__time_remaining = \
                self.entropyTools.convert_seconds_to_fancy_output(
                    self.__time_remaining_secs)
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

    def updateProgress(self):

        mytxt = _("[F]")
        eta_txt = _("ETA")
        sec_txt = _("sec") # as in XX kb/sec

        currentText = darkred("    %s: " % (mytxt,)) + \
            darkgreen(str(round(float(self.__downloadedsize)/1024, 1))) + "/" + \
            red(str(round(self.__remotesize, 1))) + " kB"
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
                bartext += "] => %s" % (self.entropyTools.bytes_into_human(self.__datatransfer),)
                bartext += "/%s : %s: %s" % (sec_txt, eta_txt, self.__time_remaining,)
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
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        elif not hasattr(self.__Output.updateProgress, '__call__'):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

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
            downloaded_size += data.get('downloaded_size', 0)
            total_size += data.get('total_size', 0)
            data_transfer += data.get('data_transfer', 0)
            tr = data.get('time_remaining_secs', 0)
            if tr > 0: time_remaining += tr
            update_step += data.get('update_step', 0)

        # total_size is in kbytes
        # downloaded_size is in bytes
        if total_size > 0:
            average = int(float(downloaded_size/1024)/total_size * 100)
        self.__data_transfer = data_transfer
        self.__average = average
        update_step = update_step/pdlen
        self.__time_remaining_sec = time_remaining
        time_remaining = self.entropyTools.convert_seconds_to_fancy_output(time_remaining)

        if ((average > self.__old_average+update_step) or \
            (self.__first_refreshes > 0)) and self.__show_progress:

            self.__first_refreshes -= 1
            currentText = darkgreen(str(round(float(downloaded_size)/1024, 1))) + "/" + \
                red(str(round(total_size, 1))) + " kB"
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
                bartext += "] => %s" % (self.entropyTools.bytes_into_human(data_transfer),)
                bartext += "/%s : %s: %s" % (sec_txt, eta_txt, time_remaining,)
            else:
                bartext += "]"
            myavg = str(average)
            if len(myavg) < 2:
                myavg = " "+myavg
            currentText += " <->  "+myavg+"% "+bartext+" "
            self.__Output.updateProgress(currentText, back = True)

        self.__old_average = average


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

    def __init__(self, uri):
        """
        EntropyTransceiver constructor, just pass the friggin URI(tm).

        @param uri: URI to handle
        @type uri: string
        """
        self._uri = uri
        self._speed_limit = 0
        self._verbose = False

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
                return handler(self._uri)

        raise UriHandlerNotFound(
            "no URI handler available for %s" % (self._uri,))


class EntropyUriHandler(object):
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

        @param uri: URI to handle
        @type uri: string
        """
        self._uri = uri
        self._verbose = False
        self._silent = False

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

    def get_uri(self):
        """
        Return copy of previously stored URI.

        @return: stored URI
        @rtype: string
        """
        return self._uri[:]

    def set_speed_limit(self, speed_limit):
        """
        Set download/upload speed limit in kb/sec form.

        @param speed_limit: speed limit in kb/sec form.
        @type speed_limit: int
        """
        raise NotImplementedError()

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

    def download(self, uri, save_path):
        """
        Download URI and save it to save_path.

        @param uri: URI to handle
        @type uri: string
        @param save_path: complete path where to store file from uri.
            If directory doesn't exist, it will be created with default
            Entropy permissions.
        @type save_path: string
        """
        raise NotImplementedError()

    def upload(self, load_path, uri):
        """
        Upload URI from load_path location to uri.

        @param load_path: URI to handle
        @type load_path: string
        @param uri: URI to handle
        @type uri: string
        """
        raise NotImplementedError()

    def rename(self, uri_old, uri_new):
        """
        Rename URI old to URI new.

        @param uri_old: URI to handle
        @type uri_old: string
        @param uri_new: URI to create
        @type uri_new: string
        """
        raise NotImplementedError()

    def get_md5(self, uri):
        """
        Return MD5 checksum of file at URI.

        @param uri: URI to handle
        @type uri: string
        @return: MD5 checksum in hexdigest form
        @rtype: string
        """
        raise NotImplementedError()

    def list_content(self, uri):
        """
        List content of directory referenced at URI.

        @param uri: URI to handle
        @type uri: string
        @return: content
        @rtype: list
        """
        raise NotImplementedError()

    def list_content_metadata(self, uri):
        """
        List content of directory referenced at URI with metadata like
        permissions, owner, size.

        @param uri: URI to handle
        @type uri: string
        @return: content
        @rtype: list
        """
        raise NotImplementedError()

    def is_uri_available(self, uri):
        """
        Given a URI (which can point to dir or file), determine whether it's
        available or not.

        @param uri: URI to handle
        @type uri: string
        @return: availability
        @rtype: bool
        """
        raise NotImplementedError()

    def makedirs(self, uri):
        """
        Given a URI, recursively create all the missing directories.

        @param uri: URI to handle
        @type uri: string
        """
        raise NotImplementedError()

    def keep_alive(self):
        """
        Send a keep-alive ping to handler.
        """
        raise NotImplementedError()

    def close(self):
        """
        Called when requesting to close connection completely.
        """
        raise NotImplementedError()


class FtpInterface:

    def __init__(self, ftpuri, OutputInterface, verbose = True,
        speed_limit = None):

        if not hasattr(OutputInterface, 'updateProgress'):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise AttributeError("AttributeError: %s, (! %s !)" % (
                OutputInterface, mytxt,))
        elif not hasattr(OutputInterface.updateProgress, '__call__'):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise AttributeError("AttributeError: %s, (! %s !)" % (
                OutputInterface, mytxt,))

        import socket, ftplib
        import entropy.tools as entropyTools
        self.socket, self.ftplib, self.entropyTools = socket, ftplib, entropyTools
        self.Entropy = OutputInterface
        self.__verbose = verbose
        self._init_vars()
        self.socket.setdefaulttimeout(60)
        self.__ftpuri = ftpuri
        self.__speed_limit = speed_limit
        self.__currentdir = '.'
        self.__ftphost = self.entropyTools.extract_ftp_host_from_uri(self.__ftpuri)
        self.__ftpuser, self.__ftppassword, self.__ftpport, self.__ftpdir = \
            self.entropyTools.extract_ftp_data(ftpuri)

        count = 10
        while True:
            count -= 1
            try:
                self.__ftpconn = self.ftplib.FTP()
                self.__ftpconn.connect(self.__ftphost, self.__ftpport)
                break
            except (self.socket.gaierror,) as e:
                raise ConnectionError('ConnectionError: %s' % (e,))
            except (self.socket.error,) as e:
                if not count:
                    raise ConnectionError('ConnectionError: %s' % (e,))
                continue
            except:
                if not count: raise
                continue

        if self.__verbose:
            mytxt = _("connecting with user")
            self.Entropy.updateProgress(
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
            raise FtpError('FtpError: %s' % (e,))
        if self.__verbose:
            mytxt = _("switching to")
            self.Entropy.updateProgress(
                "[ftp:%s] %s: %s" % (
                    darkgreen(self.__ftphost), mytxt, blue(self.__ftpdir),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        self.set_cwd(self.__ftpdir, dodir = True)

    def _init_vars(self):
        self.__oldprogress = 0.0
        self.__filesize = 0
        self.__filekbcount = 0
        self.__transfersize = 0
        self.__startingposition = 0
        self.__elapsed = 0.0
        self.__time_remaining_secs = 0
        self.__time_remaining = "(%s)" % (_("infinite"),)
        self.__starttime = time.time()

    def set_basedir(self):
        return self.set_cwd(self.__ftpdir)

    # this can be used in case of exceptions
    def reconnect_host(self):
        # import FTP modules
        self.socket.setdefaulttimeout(60)
        counter = 10
        while True:
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
                "[ftp:%s] %s: %s" % (
                    darkgreen(self.__ftphost), mytxt, blue(self.__ftpuser),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        self.__ftpconn.login(self.__ftpuser, self.__ftppassword)
        if self.__verbose:
            mytxt = _("switching to")
            self.Entropy.updateProgress(
                "[ftp:%s] %s: %s" % (
                    darkgreen(self.__ftphost), mytxt, blue(self.__ftpdir),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        self.set_cwd(self.__currentdir)

    def _get_host(self):
        return self.__ftphost

    def _get_port(self):
        return self.__ftpport

    def _get_dir(self):
        return self.__ftpdir

    def _get_cwd(self):
        pwd = self.__ftpconn.pwd()
        return pwd

    def set_cwd(self, mydir, dodir = False):
        try:
            return self._set_cwd(mydir, dodir)
        except self.ftplib.error_perm as e:
            raise FtpError('FtpError: %s' % (e,))

    def _set_cwd(self, mydir, dodir = False):
        if self.__verbose:
            mytxt = _("switching to")
            self.Entropy.updateProgress(
                "[ftp:%s] %s: %s" % (darkgreen(self.__ftphost), mytxt, blue(mydir),),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        try:
            self.__ftpconn.cwd(mydir)
        except self.ftplib.error_perm as e:
            if e[0][:3] == '550' and dodir:
                self._recursive_mkdir(mydir)
                self.__ftpconn.cwd(mydir)
            else:
                raise
        self.__currentdir = self.get_cwd()

    def _set_pasv(self, bool):
        self.__ftpconn.set_pasv(bool)

    def _set_chmod(self, chmodvalue, filename):
        return self.__ftpconn.voidcmd("SITE CHMOD " + str(chmodvalue) + " " + \
            str(filename))

    def _get_file_mtime(self, path):
        rc = self.__ftpconn.sendcmd("mdtm " + path)
        return rc.split()[-1]

    def _send_cmd(self, cmd):
        return self.__ftpconn.sendcmd(cmd)

    def list_dir(self):
        return [os.path.basename(x) for x in self.__ftpconn.nlst()]

    def is_file_available(self, filename):
        xx = []
        def cb(x):
            if x == filename: xx.append(x)
        self.__ftpconn.retrlines('NLST', cb)
        if xx: return True
        return False

    def delete_file(self, file):
        try:
            rc = self.__ftpconn.delete(file)
        except self.ftplib.error_perm as e:
            if e[0][:3] == '550':
                return True
            return False # not found
        if rc.startswith("250"):
            return True
        return False

    def _recursive_mkdir(self, mypath):
        mydirs = [x for x in mypath.split("/") if x]
        mycurpath = ""
        for mydir in mydirs:
            mycurpath = os.path.join(mycurpath, mydir)
            if not self.is_file_available(mycurpath):
                try:
                    self.mkdir(mycurpath)
                except self.ftplib.error_perm as e:
                    if e[0].lower().find("permission denied") != -1:
                        raise
                    elif e[0][:3] != '550':
                        raise

    def mkdir(self, directory):
        return self.__ftpconn.mkd(directory)

    def upload_file(self, file_path):

        # this function also supports callback, because storbinary doesn't
        def advanced_stor(cmd, fp):
            self.__ftpconn.voidcmd('TYPE I')
            conn = self.__ftpconn.transfercmd(cmd)
            while True:
                buf = fp.readline()
                if not buf:
                    break
                conn.sendall(buf)
                self._commit_buffer_update(len(buf))
                self._update_speed()
                self.updateProgress()
                self._speed_limit_loop()
            conn.close()

            # that's another workaround
            #return "226"
            try:
                rc = self.__ftpconn.voidresp()
            except:
                self.reconnect_host()
                return "226"

            return rc

        tries = 0
        while tries < 10:

            tries += 1
            filename = os.path.basename(file_path)
            self._init_vars()
            try:

                with open(file_path, "r") as f:

                    file_size = self.entropyTools.get_file_size(file_path)
                    self.__filesize = round(float(file_size)/ 1024, 1)
                    self.__filekbcount = 0

                    # delete old one, if exists
                    self.delete_file(filename+".tmp")
                    rc = advanced_stor("STOR "+filename+".tmp", f)

                    # now we can rename the file with its original name
                    self.rename_file(filename+".tmp", filename)

                if rc.find("226") != -1: # upload complete
                    return True
                return False

            except Exception as e: # connection reset by peer

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
                self.delete_file(filename)
                self.delete_file(filename+".tmp")

    def download_file(self, file_path, downloaddir):

        def df_up(buf):
            # writing file buffer
            f.write(buf)
            self._commit_buffer_update(len(buf))
            self._update_speed()
            self.updateProgress()
            self._speed_limit_loop()

        tries = 10
        while tries:
            tries -= 1

            self._init_vars()
            try:

                self.__filekbcount = 0
                # get the file size
                self.__filesize = self._get_file_size_compat(file_path)
                if (self.__filesize):
                    self.__filesize = round(float(int(self.__filesize))/1024, 1)
                    if (self.__filesize == 0):
                        self.__filesize = 1
                elif not self.is_file_available(file_path):
                    return False
                else:
                    self.__filesize = 0

                f = open(os.path.join(downloaddir, file_path), "wb")
                rc = self.__ftpconn.retrbinary('RETR ' + file_path, df_up, 1024)
                f.flush()
                f.close()
                if rc.find("226") != -1: # upload complete
                    return True
                return False

            except Exception as e: # connection reset by peer

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

    # also used to move files
    def rename_file(self, fromfile, tofile):
        rc = self.__ftpconn.rename(fromfile, tofile)
        return rc

    def get_file_md5(self, filename):
        # PROFTPD with mod_md5 supports it!
        try:
            rc_data = self.__ftpconn.sendcmd("SITE MD5 %s" % (filename,))
        except self.ftplib.error_perm:
            return None # not supported
        try:
            return rc_data.split("\n")[0].split("\t")[0].split("-")[1]
        except (IndexError, TypeError,): # wrong output
            return None

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

    def get_raw_list(self):
        mybuffer = []
        def bufferizer(buf):
            mybuffer.append(buf)
        self.__ftpconn.dir(bufferizer)
        return mybuffer

    def close(self):
        try:
            self.__ftpconn.quit()
        except (EOFError, AttributeError, self.socket.timeout, self.ftplib.error_reply,):
            # AttributeError is raised when socket gets trashed
            # EOFError is raised when the connection breaks
            # timeout, who cares!
            pass

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
                self.entropyTools.convert_seconds_to_fancy_output(
                    self.__time_remaining_secs)
        except (ValueError, TypeError,):
            self.__time_remaining = "(%s)" % (_("infinite"),)

    def _speed_limit_loop(self):
        if self.__speed_limit:
            while self.__datatransfer > self.__speed_limit * 1024:
                time.sleep(0.1)
                self._update_speed()
                self.updateProgress()

    def _commit_buffer_update(self, buf_len):
        # get the buffer size
        self.__filekbcount += float(buf_len)/1024
        self.__transfersize += buf_len

    def updateProgress(self):

        # create percentage
        upload_percent = 100.0
        if self.__filesize >= 1:
            kbcount_round = round(self.__filekbcount, 1)
            upload_percent = round((kbcount_round / self.__filesize) * 100, 1)

        currentprogress = upload_percent
        upload_size = round(self.__filekbcount, 1)

        if (currentprogress > self.__oldprogress + 0.5) and \
            (upload_percent < 100.1) and \
            (upload_size <= self.__filesize):

            upload_percent = str(upload_percent)+"%"
            # create text
            mytxt = _("Transfer status")
            current_txt = brown("    <-> %s: " % (mytxt,)) + \
                darkgreen(str(upload_size)) + "/" + \
                red(str(self.__filesize)) + " kB " + \
                brown("[") + str(upload_percent) + brown("]") + \
                " " + self.__time_remaining + " " + \
                self.entropyTools.bytes_into_human(self.__datatransfer) + \
                "/" + _("sec")

            self.Entropy.updateProgress(current_txt, back = True)
            self.__oldprogress = currentprogress
