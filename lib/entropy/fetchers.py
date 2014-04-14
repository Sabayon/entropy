# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Transceivers Fetchers submodule}.

"""
import os
import errno
import sys
import time
try:
    import httplib
except ImportError:
    # python 3.x
    import http.client as httplib
import hashlib
import socket
import pty
import subprocess
import threading
import contextlib

from entropy.const import const_is_python3, const_file_readable

if const_is_python3():
    import urllib.request as urlmod
    import urllib.error as urlmod_error
else:
    import urllib2 as urlmod
    import urllib2 as urlmod_error

from entropy.exceptions import InterruptError
from entropy.tools import print_traceback, \
    convert_seconds_to_fancy_output, bytes_into_human, spliturl, \
    add_proxy_opener, md5sum
from entropy.const import etpConst, const_isfileobj, const_debug_write
from entropy.output import TextInterface, darkblue, darkred, purple, blue, \
    brown, darkgreen, red

from entropy.i18n import _, ngettext
from entropy.misc import ParallelTask
from entropy.core.settings.base import SystemSettings


class UrlFetcher(TextInterface):

    """
    Entropy single URL fetcher. It supports what Python's urllib2 supports,
    plus resuming, proxies and custom user agents. No external tools
    dependencies are required (including wget).
    """

    # this dict must be kept in sync with
    # the __supported_uris variable below
    # until plugins support is implemented
    _supported_differential_download = {
        'file': False,
        'http': False,
        'https': False,
        'ftp': False,
        'ftps': False,
        'rsync': True,
        'ssh': True,
    }

    GENERIC_FETCH_ERROR = "-3"
    TIMEOUT_FETCH_ERROR = "-4"
    GENERIC_FETCH_WARN = "-2"

    def __init__(self, url, path_to_save, checksum = True,
                 show_speed = True, resume = True,
                 abort_check_func = None, disallow_redirect = False,
                 thread_stop_func = None, speed_limit = None,
                 timeout = None, download_context_func = None,
                 pre_download_hook = None, post_download_hook = None):
        """
        Entropy URL downloader constructor.

        @param url: download URL (do not URL-encode it!)
        @type url: string
        @param path_to_save: file path where to save downloaded data
        @type path_to_save: string
        @keyword checksum: return md5 hash instead of status code
        @type checksum: bool
        @keyword show_speed: show download speed
        @type show_speed: bool
        @keyword resume: enable resume support
        @type resume: bool
        @keyword abort_check_func: callback used to stop download, it has to
            raise an exception that has to be caught by provider application.
            This exception will be considered an "abort" request.
        @type abort_check_func: callable
        @keyword disallow_redirect: disallow automatic HTTP redirects
        @type disallow_redirect: bool
        @keyword thread_stop_func: callback used to stop download, it has to
            raise an exception that has to be caught by provider application.
            This exception will be considered a "stop" request.
        @type thread_stop_func: callable
        @keyword speed_limit: speed limit in kb/sec
        @type speed_limit: int
        @keyword timeout: custom request timeout value (in seconds), if None
            the value is read from Entropy configuration files.
        @type timeout: int
        @keyword download_context_func: if not None, it must be a function
            exposing a context manager and taking a path (the download path)
            as argument. This can be used to implement locking on files to be
            downloaded.
        @type download_context_func: callable
        @keyword pre_download_hook: hook called before starting the download
            process, inside the download_context_func context. This can be
            used to verify if the download is actually needed or just return.
            If the returned value is not None, the download method will return
            that value. The function takes a path (the download path) and the
            download id as arguments.
        @type pre_download_hook: callable
        @keyword post_download_hook: hook called after the download is complete,
            inside the download_context_func context. This can be used to verify
            the integrity of the downloaded data.
            The function takes a path (the download path) and the download
            status and the download id as arguments.
        @type post_download_hook: callable
        """
        self.__supported_uris = {
            'file': self._urllib_download,
            'http': self._urllib_download,
            'https': self._urllib_download,
            'ftp': self._urllib_download,
            'ftps': self._urllib_download,
            'rsync': self._rsync_download,
            'ssh': self._rsync_download,
        }

        self.__system_settings = SystemSettings()
        if speed_limit == None:
            speed_limit = \
                self.__system_settings['repositories']['transfer_limit']

        if timeout is None:
            self.__timeout = \
                self.__system_settings['repositories']['timeout']
        else:
            self.__timeout = timeout
        self.__th_id = 0

        if download_context_func is None:
            @contextlib.contextmanager
            def download_context_func(path):
                yield

        self.__download_context_func = download_context_func
        self.__pre_download_hook = pre_download_hook
        self.__post_download_hook = post_download_hook

        self.__resume = resume
        self.__url = url
        self.__path_to_save = path_to_save
        self.__checksum = checksum
        self.__show_speed = show_speed
        self.__abort_check_func = abort_check_func
        self.__thread_stop_func = thread_stop_func
        self.__disallow_redirect = disallow_redirect
        self.__speedlimit = speed_limit # kbytes/sec

        self._init_vars()
        self.__init_urllib()

    @staticmethod
    def _get_url_protocol(url):
        return url.split(":")[0]

    def __init_urllib(self):
        # this will be moved away soon anyway
        self.__localfile = None

    def _init_vars(self):
        self.__use_md5_checksum = False
        self.__md5_checksum = hashlib.new("md5")
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
        self.__last_update_time = self.__starttime
        self.__last_downloadedsize = 0
        self.__existed_before = False
        if os.path.lexists(self.__path_to_save):
            self.__existed_before = True

    def __setup_urllib_resume_support(self):

        # resume support
        if const_file_readable(self.__path_to_save) and self.__resume:
            self.__urllib_open_local_file("ab")
            self.__localfile.seek(0, os.SEEK_END)
            self.__startingposition = int(self.__localfile.tell())
            self.__last_downloadedsize = self.__startingposition
        else:
            self.__urllib_open_local_file("wb")

    def __urllib_open_local_file(self, mode):
        # if client uses this instance more than
        # once, make sure we close previously opened
        # files.
        if const_isfileobj(self.__localfile):
            try:
                if hasattr(self.__localfile, 'flush'):
                    self.__localfile.flush()
                self.__localfile.close()
            except (IOError, OSError,):
                pass
        self.__localfile = open(self.__path_to_save, mode)
        if mode.startswith("a"):
            self.__resumed = True
        else:
            self.__resumed = False

    def __encode_url(self, url):
        if const_is_python3():
            import urllib.parse as encurl
        else:
            import urllib as encurl
        url = os.path.join(os.path.dirname(url),
            encurl.quote(os.path.basename(url)))
        return url

    def __prepare_return(self):
        if self.__checksum:
            if self.__use_md5_checksum:
                self.__status = self.__md5_checksum.hexdigest()
            else:
                # for rsync, we don't have control on the data flow, so
                # we cannot calculate the md5 on the way
                self.__status = md5sum(self.__path_to_save)
            return self.__status
        self.__status = UrlFetcher.GENERIC_FETCH_WARN
        return self.__status

    def __fork_cmd(self, args, environ, update_output_callback):

        def _line_reader(std_r):
            read_buf = ""
            try:
                char = std_r.read(1)
                while char:
                    if (char == "\r") and read_buf:
                        update_output_callback(read_buf)
                        read_buf = ""
                    elif (char != "\r"):
                        read_buf += char
                    char = std_r.read(1)
            except IOError:
                return

        try:
            pid, fd = pty.fork()
        except OSError as err:
            const_debug_write(__name__,
                "__fork_cmd(%s): status: %s" % (args, err,))
            # out of pty devices
            return 1

        if pid == 0:
            proc = subprocess.Popen(args, env = environ)
            rc = proc.wait()
            os._exit(rc)
        elif pid == -1:
            raise SystemError("cannot forkpty()")
        else:
            dead = False
            return_code = 1
            srd_r = None
            try:
                std_r = os.fdopen(fd, "r")
                while not dead:

                    try:
                        dead, return_code = os.waitpid(pid, os.WNOHANG)
                    except OSError as e:
                        if e.errno != errno.ECHILD:
                            raise
                        dead = True

                    # wait a bit
                    time.sleep(0.2)
                    _line_reader(std_r)

                    if self.__abort_check_func != None:
                        self.__abort_check_func()
                    if self.__thread_stop_func != None:
                        self.__thread_stop_func()
            finally:
                if std_r is not None:
                    std_r.close()
            return return_code

    @staticmethod
    def supports_differential_download(url):
        """
        Return whether the current protocol handler for given URL supports
        differential download. It's up to UrlFetcher users to implement
        the logic to provide a previously downloaded file to "path_to_save"
        location (argument passed to UrlFetcher constructor).

        @param url: download URL
        @type url: string
        @return: differential download support status
        @rtype: bool
        """
        protocol = UrlFetcher._get_url_protocol(url)
        return UrlFetcher._supported_differential_download.get(protocol, False)

    def set_id(self, th_id):
        """
        Set instance id (usually the thread identifier).
        @param th_id: id to set
        @type th_id: int
        """
        self.__th_id = th_id

    def download(self):
        """
        Start downloading URL given at construction time.

        @return: download status, which can be either one of:
            UrlFetcher.GENERIC_FETCH_ERROR means error.
            UrlFetcher.TIMEOUT_FETCH_ERROR means timeout error.
            UrlFetcher.GENERIC_FETCH_WARN means warning,
                downloaded fine but unable to calculate the md5 hash.
        Otherwise returns md5 hash.
        @rtype: string
        @todo: improve return data
        """
        protocol = UrlFetcher._get_url_protocol(self.__url)
        downloader = self.__supported_uris.get(protocol)
        const_debug_write(
            __name__,
            "UrlFetcher.download(%s), save: %s, checksum: %s, resume: %s, "
            "show speed: %s, abort func: %s, thread stop func: %s, "
            "disallow redir: %s, speed limit: %s, timeout: %s, "
            "download context method: %s, pre download hook: %s, "
            "post download hook: %s" % (
                self.__url, self.__path_to_save, self.__checksum,
                self.__resume, self.__show_speed, self.__abort_check_func,
                self.__thread_stop_func, self.__disallow_redirect,
                self.__speedlimit, self.__timeout,
                self.__download_context_func,
                self.__pre_download_hook, self.__post_download_hook)
        )
        if downloader is None:
            # return error, protocol not supported
            self._update_speed()
            self.__status = UrlFetcher.GENERIC_FETCH_ERROR
            return self.__status

        self._init_vars()
        with self.__download_context_func(self.__path_to_save):

            if self.__pre_download_hook:
                status = self.__pre_download_hook(
                    self.__path_to_save, self.__th_id)
                if status is not None:
                    return status

            status = downloader()
            if self.__show_speed:
                self.update()

            if self.__post_download_hook:
                self.__post_download_hook(
                    self.__path_to_save, status, self.__th_id)

            return status

    def _setup_rsync_args(self):
        protocol = UrlFetcher._get_url_protocol(self.__url)
        url = self.__url
        _rsync_exec = "/usr/bin/rsync"
        _default_ssh_port = 22

        list_args, args = None, None
        if protocol == "rsync":
            args = (_rsync_exec, "--no-motd", "--compress", "--progress",
                "--stats", "--inplace", "--timeout=%d" % (self.__timeout,))
            if self.__speedlimit:
                args += ("--bwlimit=%d" % (self.__speedlimit,),)
            if not self.__resume:
                args += ("--whole-file",)
            else:
                args += ("--partial",)
            args += (url, self.__path_to_save,)
            # args to rsync to get remote file size
            list_args = (_rsync_exec, "--no-motd", "--list-only", url)

        elif protocol == "ssh":

            def _extract_ssh_port_url(url):
                start_t = url.find("<")
                if start_t == -1:
                    return _default_ssh_port, url

                start_t += 1
                end_t = start_t - 1
                try:
                    for x in url[start_t:]:
                        end_t += 1
                        if x == ">":
                            break
                except IndexError:
                    return _default_ssh_port, url

                try:
                    port = int(url[start_t:end_t])
                    url = url[:start_t-1] + url[end_t+1:]
                except ValueError:
                    port = _default_ssh_port
                return port, url

            # SUPPORTED URL form: ssh://username@host<PORT>:/path
            # strip ssh:// from url
            url = url.lstrip("ssh://")
            # get port
            port, url = _extract_ssh_port_url(url)
            args = (_rsync_exec, "--no-motd", "--compress", "--progress",
                "--stats", "--inplace", "--timeout=%d" % (self.__timeout,),
                "-e", "ssh -p %s" % (port,))
            if self.__speedlimit:
                args += ("--bwlimit=%d" % (self.__speedlimit,),)
            if not self.__resume:
                args += ("--whole-file",)
            else:
                args += ("--partial",)
            args += (url, self.__path_to_save,)
            # args to rsync to get remote file size
            list_args = (_rsync_exec, "--no-motd", "--list-only", "-e",
                "ssh -p %s" % (port,), url)

        return list_args, args

    def _rsync_download(self):
        """
        rsync based downloader. It uses rsync executable.
        """
        list_args, args = self._setup_rsync_args()
        # rsync executable environment
        rsync_environ = {}

        # setup proxy support
        proxy_data = self.__system_settings['system']['proxy']
        if proxy_data['rsync']:
            rsync_environ['RSYNC_PROXY'] = proxy_data['rsync']

        def rsync_stats_extractor(output_line):
            const_debug_write(__name__,
                "rsync_stats_extractor(%s): %s" % (self.__th_id, output_line,))
            data = output_line.split()
            if len(data) != 4:
                # it's just garbage here
                self._update_speed()
                return

            bytes_read, pct, speed_kbsec, eta = data
            try:
                bytes_read = int(bytes_read)
            except ValueError:
                bytes_read = 0
            try:
                average = int(pct.strip("%"))
            except ValueError:
                average = 0

            # update progress info
            # _rsync_commit
            self.__downloadedsize = bytes_read
            if average > 100:
                average = 100
            self.__average = average
            self._update_speed()

            if self.__show_speed:
                self.handle_statistics(self.__th_id, self.__downloadedsize,
                    self.__remotesize, self.__average, self.__oldaverage,
                    self.__updatestep, self.__show_speed, self.__datatransfer,
                    self.__time_remaining, self.__time_remaining_secs
                )
                self.update()
                self.__oldaverage = self.__average

        def rsync_list_extractor(output_line):
            data = output_line.split()
            if len(data) == 5:
                try:
                    # perms, size, date, time, file name
                    self.__remotesize = float(data[1])/1000
                except ValueError:
                    pass

        const_debug_write(__name__,
            "spawning rsync fetch(%s): %s, %s, %s" % (
                self.__th_id, list_args, rsync_environ, rsync_list_extractor,))
        sts = self.__fork_cmd(list_args, rsync_environ, rsync_list_extractor)
        const_debug_write(__name__,
            "spawned rsync fetch(%s): status: %s" % (self.__th_id, sts,))
        if sts != 0:
            self.__rsync_close(True)
            self.__status = UrlFetcher.GENERIC_FETCH_ERROR
            return self.__status

        const_debug_write(__name__,
            "spawning rsync fetch(%s): %s, %s, %s" % (
                self.__th_id, args, rsync_environ, rsync_stats_extractor,))
        sts = self.__fork_cmd(args, rsync_environ, rsync_stats_extractor)
        const_debug_write(__name__,
            "spawned rsync fetch(%s): status: %s" % (self.__th_id, sts,))
        if sts != 0:
            self.__rsync_close(True)
            self.__status = UrlFetcher.GENERIC_FETCH_ERROR
            return self.__status

        # kill thread
        self.__rsync_close(False)
        return self.__prepare_return()

    def __rsync_close(self, errored):
        if (not self.__existed_before) and errored:
            try:
                os.remove(self.__path_to_save)
            except OSError:
                pass

    def _setup_urllib_proxy(self):
        """
        Setup urllib proxy data
        """
        mydict = {}
        proxy_data = self.__system_settings['system']['proxy']
        if proxy_data['ftp']:
            mydict['ftp'] = proxy_data['ftp']
        if proxy_data['http']:
            mydict['http'] = proxy_data['http']
        if mydict:
            mydict['username'] = proxy_data['username']
            mydict['password'] = proxy_data['password']
            add_proxy_opener(urlmod, mydict)
        else:
            # unset
            urlmod._opener = None

    def _urllib_download(self):
        """
        urrlib2 based downloader. This is the default for HTTP and FTP urls.
        """
        self._setup_urllib_proxy()
        self.__setup_urllib_resume_support()
        # we're going to feed the md5 digestor on the way.
        self.__use_md5_checksum = True
        url = self.__encode_url(self.__url)
        url_protocol = UrlFetcher._get_url_protocol(self.__url)
        uname = os.uname()
        user_agent = "Entropy/%s (compatible; %s; %s: %s %s %s)" % (
            etpConst['entropyversion'],
            "Entropy",
            os.path.basename(url),
            uname[0],
            uname[4],
            uname[2],
        )

        if url_protocol in ("http", "https"):
            headers = {'User-Agent': user_agent,}
            req = urlmod.Request(url, headers = headers)
        else:
            req = url

        u_agent_error = False
        do_return = False
        while True:

            # get file size if available
            try:
                self.__remotefile = urlmod.urlopen(req, None, self.__timeout)
            except KeyboardInterrupt:
                self.__urllib_close(False)
                raise
            except httplib.InvalidURL:
                # malformed url!
                self.__urllib_close(True)
                self.__status = UrlFetcher.GENERIC_FETCH_ERROR
                do_return = True

            except urlmod_error.HTTPError as e:
                if (e.code == 405) and not u_agent_error:
                    # server doesn't like our user agent
                    req = url
                    u_agent_error = True
                    continue
                self.__urllib_close(True)
                self.__status = UrlFetcher.GENERIC_FETCH_ERROR
                do_return = True

            except urlmod_error.URLError as err: # timeout error
                self.__urllib_close(True)
                self.__status = UrlFetcher.GENERIC_FETCH_ERROR
                do_return = True

            except httplib.BadStatusLine:
                # obviously, something to cope with
                self.__urllib_close(True)
                self.__status = UrlFetcher.GENERIC_FETCH_ERROR
                do_return = True

            except socket.timeout:
                # arghv!!
                self.__urllib_close(True)
                self.__status = UrlFetcher.TIMEOUT_FETCH_ERROR
                do_return = True

            except socket.error:
                # connection reset by peer?
                self.__urllib_close(True)
                self.__status = UrlFetcher.GENERIC_FETCH_ERROR
                do_return = True

            except ValueError: # malformed, unsupported URL? raised by urllib
                self.__urllib_close(True)
                self.__status = UrlFetcher.GENERIC_FETCH_ERROR
                do_return = True

            except Exception:
                print_traceback()
                raise
            break

        if do_return:
            return self.__status

        try:
            self.__remotesize = int(self.__remotefile.headers.get(
                "content-length", -1))
        except KeyboardInterrupt:
            self.__urllib_close(False)
            raise
        except ValueError:
            pass

        try:
            # i don't remember why this is needed
            # the whole code here is crap and written at
            # scriptkiddie age, but still, it works (kinda).
            request = url
            if ((self.__startingposition > 0) and (self.__remotesize > 0)) \
                and (self.__startingposition < self.__remotesize):

                headers = {
                    "Range" : "bytes=" + \
                        str(self.__startingposition) + "-" + \
                        str(self.__remotesize)
                }
                if url_protocol in ("http", "https"):
                    headers['User-Agent'] = user_agent

                try:
                    request = urlmod.Request(
                        url,
                        headers = headers)
                except KeyboardInterrupt:
                    self.__urllib_close(False)
                    raise
                except:
                    pass

                # this will be replaced, close...
                try:
                    self.__remotefile.close()
                except:
                    pass
                self.__remotefile = urlmod.urlopen(
                    request, None, self.__timeout)

            elif self.__startingposition == self.__remotesize:
                # all fine then!
                self.__urllib_close(False)
                return self.__prepare_return()
            elif (self.__startingposition > self.__remotesize) and \
                self.__resumed:
                # there is something wrong
                # downloaded more than the advertised size
                # the HTTP server is broken or something else happened
                # locally and file cannot be trusted (resumed)
                self.__urllib_open_local_file("wb")

        except KeyboardInterrupt:
            self.__urllib_close(False)
            raise
        except:
            self.__urllib_close(True)
            self.__status = UrlFetcher.GENERIC_FETCH_ERROR
            return self.__status

        if self.__remotesize > 0:
            self.__remotesize = float(int(self.__remotesize))/1000
        else:
            # this means we were not able to get Content-Length
            self.__remotesize = 0

        if url_protocol not in ("file", "ftp", "ftps"):
            if self.__disallow_redirect and \
                (url != self.__remotefile.geturl()):

                self.__urllib_close(True)
                self.__status = UrlFetcher.GENERIC_FETCH_ERROR
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
                self.__urllib_close(False)
                raise

            except socket.timeout:
                self.__urllib_close(False)
                self.__status = UrlFetcher.TIMEOUT_FETCH_ERROR
                return self.__status

            except socket.error:
                # connection reset by peer?
                self.__urllib_close(False)
                self.__status = UrlFetcher.GENERIC_FETCH_ERROR
                return self.__status

            except Exception:
                # python 2.4 timeouts go here
                self.__urllib_close(True)
                self.__status = UrlFetcher.GENERIC_FETCH_ERROR
                return self.__status

            self.__urllib_commit(rsx)
            if self.__show_speed:
                self.handle_statistics(self.__th_id, self.__downloadedsize,
                    self.__remotesize, self.__average, self.__oldaverage,
                    self.__updatestep, self.__show_speed, self.__datatransfer,
                    self.__time_remaining, self.__time_remaining_secs
                )
                self.update()
                self.__oldaverage = self.__average
            if self.__speedlimit:
                while self.__datatransfer > self.__speedlimit*1000:
                    time.sleep(0.1)
                    self._update_speed()
                    if self.__show_speed:
                        self.update()
                        self.__oldaverage = self.__average

        # kill thread
        self.__urllib_close(False)
        return self.__prepare_return()

    def __urllib_commit(self, mybuffer):
        # writing file buffer
        self.__localfile.write(mybuffer)
        self.__md5_checksum.update(mybuffer)
        # update progress info
        self.__downloadedsize = self.__localfile.tell()
        kbytecount = float(self.__downloadedsize)/1000
        # avoid race condition with test and eval not being atomic
        # this will always work
        try:
            average = int((kbytecount/self.__remotesize)*100)
        except ZeroDivisionError:
            average = 0
        if average > 100:
            average = 100
        self.__average = average
        self._update_speed()

    def __urllib_close(self, errored):
        self._update_speed()
        try:
            if const_isfileobj(self.__localfile):
                if hasattr(self.__localfile, 'flush'):
                    self.__localfile.flush()
                self.__localfile.close()
        except IOError:
            pass
        if (not self.__existed_before) and errored:
            try:
                os.remove(self.__path_to_save)
            except OSError:
                pass

        if self.__remotefile is not None:
            try:
                self.__remotefile.close()
            except socket.error:
                pass

    def _update_speed(self):
        cur_time = time.time()
        self.__elapsed = cur_time - self.__starttime
        last_elapsed = cur_time - self.__last_update_time
        # we have the diff size
        x_delta = self.__downloadedsize - self.__startingposition
        x_delta_now = self.__downloadedsize - self.__last_downloadedsize

        el_factor = self.__elapsed
        if self.__elapsed > 1:
            el_factor = 1

        if (last_elapsed > 0) and (self.__elapsed > 0):
            self.__datatransfer = 0.5 * self.__datatransfer + \
                0.5 * (el_factor * x_delta / self.__elapsed + \
                    (1-el_factor) * x_delta_now / last_elapsed)
        else:
            self.__datatransfer = 0.0

        self.__last_update_time = cur_time
        self.__last_downloadedsize = self.__downloadedsize

        if self.__datatransfer < 0:
            self.__datatransfer = 0.0

        rounded_remote = int(round(self.__remotesize * 1000, 0))
        rounded_downloaded = int(round(self.__downloadedsize, 0))
        x_delta = rounded_remote - rounded_downloaded
        if self.__datatransfer > 0:
            tx_round = round(x_delta/self.__datatransfer, 0)
            self.__time_remaining_secs = int(tx_round)

        if self.__time_remaining_secs < 0:
            self.__time_remaining = "(%s)" % (_("infinite"),)
        else:
            self.__time_remaining = \
                convert_seconds_to_fancy_output(self.__time_remaining_secs)

    def get_transfer_rate(self):
        """
        Return transfer rate, in kb/sec.

        @return: transfer rate
        @rtype: int
        """
        return self.__datatransfer

    def get_average(self):
        """
        Get current download percentage.

        @return: download percentage
        @rtype: float
        """
        return self.__average

    def get_seconds_remaining(self):
        """
        Return remaining seconds to download completion.

        @return: remaining download seconds
        @rtype: int
        """
        return self.__time_remaining_secs

    def is_resumed(self):
        """
        Return whether given download has been resumed.
        """
        return self.__resumed

    def handle_statistics(self, th_id, downloaded_size, total_size,
            average, old_average, update_step, show_speed, data_transfer,
            time_remaining, time_remaining_secs):
        """
        Reimplement this callback to gather information about data currently
        downloaded.

        @param th_id: instance identifier
        @type th_id: int
        @param downloaded_size: size downloaded up to now, in bytes
        @type downloaded_size: int
        @param total_size: total download size, in bytes
        @type total_size: int
        @param average: percentage of file downloaded up to now
        @type average: float
        @param old_average: old percentage of file downloaded
        @type: float
        @param update_step: currently configured update average delta
        @type update_step: int
        @param show_speed: if download speed should be shown for given instance
        @type show_speed: bool
        @param data_transfer: current data transfer, in kb/sec
        @type data_transfer: int
        @param time_remaining: currently hypothesized remaining download time,
            in string format (showing hours, minutes, seconds).
        @type time_remaining: string
        @param time_remaining_secs: currently hypothesized remaining download time,
            in seconds.
        @type time_remaining_secs: int
        """
        return

    def _push_progress_to_output(self):

        mytxt = _("[F]")
        eta_txt = _("ETA")
        sec_txt = _("sec") # as in XX kb/sec

        current_txt = darkred("    %s: " % (mytxt,)) + \
            darkgreen(str(round(float(self.__downloadedsize)/1000, 1))) + "/" \
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
        TextInterface.output(current_txt, back = True)

    def update(self):
        """
        Main fetch progress callback. You can reimplement this to refresh
        your output devices.
        """
        update_time_delta = 0.5
        cur_t = time.time()
        if cur_t > (self.__last_output_time + update_time_delta):
            self.__last_output_time = cur_t
            self._push_progress_to_output()


class MultipleUrlFetcher(TextInterface):

    def __init__(self, url_path_list, checksum = True,
                 show_speed = True, resume = True,
                 abort_check_func = None, disallow_redirect = False,
                 url_fetcher_class = None, timeout = None,
                 download_context_func = None,
                 pre_download_hook = None, post_download_hook = None):
        """
        @param url_path_list: list of tuples composed by url and
            path to save, for eg. [(url,path_to_save,),...]
        @type url_path_list: list
        @keyword checksum: return md5 hash instead of status code
        @type checksum: bool
        @keyword show_speed: show download speed
        @type show_speed: bool
        @keyword resume: enable resume support
        @type resume: bool
        @keyword abort_check_func: callback used to stop download, it has to
            raise an exception that has to be caught by provider application.
            This exception will be considered an "abort" request.
        @type abort_check_func: callable
        @keyword disallow_redirect: disallow automatic HTTP redirects
        @type disallow_redirect: bool
        @keyword thread_stop_func: callback used to stop download, it has to
            raise an exception that has to be caught by provider application.
            This exception will be considered a "stop" request.
        @type thread_stop_func: callable
        @param url_fetcher_class: UrlFetcher based class to use
        @type url_fetcher_class: subclass of UrlFetcher
        @keyword timeout: custom request timeout value (in seconds), if None
            the value is read from Entropy configuration files.
        @type timeout: int
        @keyword download_context_func: if not None, it must be a function
            exposing a context manager and taking a path (the download path)
            as argument. This can be used to implement locking on files to be
            downloaded.
        @type download_context_func: callable
        @keyword pre_download_hook: hook called before starting the download
            process, inside the download_context_func context. This can be
            used to verify if the download is actually needed or just return.
            If the returned value is not None, the download method will return
            that value. The function takes a path (the download path) and the
            download id as arguments.
        @type pre_download_hook: callable
        @keyword post_download_hook: hook called after the download is complete,
            inside the download_context_func context. This can be used to verify
            the integrity of the downloaded data.
            The function takes a path (the download path) and the download
            status and the download id as arguments.
        @type post_download_hook: callable
        """
        self._progress_data = {}
        self._url_path_list = url_path_list

        self.__system_settings = SystemSettings()
        self.__resume = resume
        self.__checksum = checksum
        self.__show_speed = show_speed
        self.__abort_check_func = abort_check_func
        self.__disallow_redirect = disallow_redirect
        self.__timeout = timeout
        self.__download_context_func = download_context_func
        self.__pre_download_hook = pre_download_hook
        self.__post_download_hook = post_download_hook

        # important to have a declaration here
        self.__data_transfer = 0
        self.__average = 0
        self.__old_average = 0
        self.__time_remaining_secs = 0

        self.__url_fetcher = url_fetcher_class
        if self.__url_fetcher == None:
            self.__url_fetcher = UrlFetcher

    def __handle_threads_stop(self):
        if self.__stop_threads:
            raise InterruptError("interrupted")

    def _init_vars(self):
        self._progress_data.clear()
        self._progress_data_lock = threading.Lock()
        self.__thread_pool = {}
        self.__download_statuses = {}
        self.__show_progress = False
        self.__stop_threads = False
        self.__first_refreshes = 50
        self.__data_transfer = 0
        self.__average = 0
        self.__old_average = 0
        self.__time_remaining_secs = 0
        self.__progress_update_t = time.time()
        self.__startup_time = time.time()

    @staticmethod
    def supports_differential_download(url):
        """
        Return whether the current protocol handler for given URL supports
        differential download. It's up to UrlFetcher users to implement
        the logic to provide a previously downloaded file to "path_to_save"
        location (argument passed to UrlFetcher constructor).

        @param url: download URL
        @type url: string
        @return: differential download support status
        @rtype: bool
        """
        return UrlFetcher.supports_differential_download(url)

    def download(self):
        """
        Start downloading URL given at construction time.

        @return: dict containing UrlFetcher.get_id() as key
            and download status as value, which can be either one of:
            UrlFetcher.GENERIC_FETCH_ERROR means error.
            UrlFetcher.TIMEOUT_FETCH_ERROR means timeout error.
            UrlFetcher.GENERIC_FETCH_WARN means warning,
                downloaded fine but unable to calculate the md5 hash.
        @rtype: dict
        """
        self._init_vars()

        speed_limit = 0
        dsl = self.__system_settings['repositories']['transfer_limit']
        if isinstance(dsl, int) and self._url_path_list:
            speed_limit = dsl/len(self._url_path_list)

        class MyFetcher(self.__url_fetcher):

            def __init__(self, klass, multiple, *args, **kwargs):
                klass.__init__(self, *args, **kwargs)
                self.__multiple_fetcher = multiple

            def update(self):
                return self.__multiple_fetcher.update()

            def _push_progress_to_output(self, *args):
                return

            def handle_statistics(self, *args, **kwargs):
                return self.__multiple_fetcher.handle_statistics(*args,
                    **kwargs)

        th_id = 0
        for url, path_to_save in self._url_path_list:
            th_id += 1
            downloader = MyFetcher(
                self.__url_fetcher, self, url, path_to_save,
                checksum = self.__checksum, show_speed = self.__show_speed,
                resume = self.__resume,
                abort_check_func = self.__abort_check_func,
                disallow_redirect = self.__disallow_redirect,
                thread_stop_func = self.__handle_threads_stop,
                speed_limit = speed_limit,
                timeout = self.__timeout,
                download_context_func = self.__download_context_func,
                pre_download_hook = self.__pre_download_hook,
                post_download_hook = self.__post_download_hook
            )
            downloader.set_id(th_id)

            def do_download(ds, dth_id, downloader):
                ds[dth_id] = downloader.download()

            t = ParallelTask(do_download, self.__download_statuses, th_id,
                downloader)
            t.name = "UrlFetcher{%s}" % (url,)
            t.daemon = True
            self.__thread_pool[th_id] = t
            t.start()

        self._push_progress_to_output(force = True)
        self.__show_download_files_info()
        self.__show_progress = True

        # wait until all the threads are done
        # do not block the main thread
        # but rather use timeout and check
        try:
            while True:
                _all_joined = True
                for th_id, th in self.__thread_pool.items():
                    th.join(0.3)
                    if th.is_alive():
                        # timeout then
                        _all_joined = False
                if _all_joined:
                    break
        except (SystemExit, KeyboardInterrupt):
            self.__stop_threads = True
            raise

        if len(self._url_path_list) != len(self.__download_statuses):
            # there has been an error (exception)
            # complete download_statuses with error info
            for th_id, th in self.__thread_pool.items():
                if th_id not in self.__download_statuses:
                    self.__download_statuses[th_id] = \
                        UrlFetcher.GENERIC_FETCH_ERROR

        return self.__download_statuses

    def get_transfer_rate(self):
        """
        Return transfer rate, in kb/sec.

        @return: transfer rate
        @rtype: int
        """
        return self.__data_transfer

    def get_average(self):
        """
        Get current download percentage.

        @return: download percentage
        @rtype: float
        """
        return self.__average

    def get_seconds_remaining(self):
        """
        Return remaining seconds to download completion.

        @return: remaining download seconds
        @rtype: int
        """
        return self.__time_remaining_secs

    def __show_download_files_info(self):
        count = 0
        pl = self._url_path_list[:]
        TextInterface.output(
            "%s: %s %s" % (
                darkblue(_("Aggregated download")),
                darkred(str(len(pl))),
                darkblue(ngettext("item", "items", len(pl))),
            ),
            importance = 0,
            level = "info",
            header = purple("  ## ")
        )
        for url, save_path in pl:
            count += 1
            fname = os.path.basename(url)
            uri = spliturl(url)[1]
            TextInterface.output(
                "[%s] %s => %s" % (
                    darkblue(str(count)),
                    darkgreen(uri),
                    blue(fname),
                ),
                importance = 0,
                level = "info",
                header = brown("   # ")
            )

    def handle_statistics(self, th_id, downloaded_size, total_size,
            average, old_average, update_step, show_speed, data_transfer,
            time_remaining, time_remaining_secs):
        """
        Reimplement this callback to gather information about data currently
        downloaded.

        @param th_id: instance identifier
        @type th_id: int
        @param downloaded_size: size downloaded up to now, in bytes
        @type downloaded_size: int
        @param total_size: total download size, in bytes
        @type total_size: int
        @param average: percentage of file downloaded up to now
        @type average: float
        @param old_average: old percentage of file downloaded
        @type: float
        @param update_step: currently configured update average delta
        @type update_step: int
        @param show_speed: if download speed should be shown for given instance
        @type show_speed: bool
        @param data_transfer: current data transfer, in kb/sec
        @type data_transfer: int
        @param time_remaining: currently hypothesized remaining download time,
            in string format (showing hours, minutes, seconds).
        @type time_remaining: string
        @param time_remaining_secs: currently hypothesized remaining download time,
            in seconds.
        @type time_remaining_secs: int
        """
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
        with self._progress_data_lock:
            self._progress_data[th_id] = data

    def _compute_progress_stats(self):
        """
        Compute the progress statistics by reading individual ones.
        """
        downloaded_size = 0
        total_size = 0
        time_remaining = 0

        with self._progress_data_lock:
            all_started = len(self._progress_data) == len(self._url_path_list)
            for th_id, data in self._progress_data.items():
                downloaded_size += data.get('downloaded_size', 0)
                total_size += data.get('total_size', 0)
                # data_transfer from Python threading bullshit is not reliable
                # with multiple threads and causes inaccurate informations to be
                # printed
                # data_transfer += data.get('data_transfer', 0)
                tr = data.get('time_remaining_secs', 0)
                if tr > 0:
                    time_remaining += tr

        elapsed_t = time.time() - self.__startup_time
        if elapsed_t < 0.1:
            elapsed_t = 0.1
        data_transfer = int(downloaded_size / elapsed_t)

        average = 0
        # total_size is in kbytes
        # downloaded_size is in bytes
        if total_size > 0 and all_started:
            average = int(float(downloaded_size / 1000) / total_size * 100)

        time_remaining_str = convert_seconds_to_fancy_output(time_remaining)
        if not all_started:
            time_remaining_str = "~%s" % (time_remaining_str,)

        return {
            "downloaded_size": downloaded_size,
            "total_size": total_size,
            "time_remaining": time_remaining,
            "time_remaining_str": time_remaining_str,
            "all_started": all_started,
            "data_transfer": data_transfer,
            "average": average,
            }

    def _push_progress_to_output(self, force = False):

        stats = self._compute_progress_stats()
        downloaded_size = stats["downloaded_size"]
        total_size = stats["total_size"]
        time_remaining = stats["time_remaining"]
        data_transfer = stats["data_transfer"]
        average = stats["average"]
        time_remaining_str = stats["time_remaining_str"]

        self.__data_transfer = data_transfer
        self.__average = average
        self.__time_remaining_secs = time_remaining

        update_time_delta = 0.5
        cur_t = time.time()
        if ((cur_t > (self.__progress_update_t + update_time_delta)) \
            or force or (self.__first_refreshes > 0)) and self.__show_progress:

            self.__first_refreshes -= 1
            self.__progress_update_t = cur_t

            eta_txt = _("ETA")
            sec_txt = _("sec") # as in XX kb/sec
            down_size_txt = str(round(float(downloaded_size) / 1000, 1))
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
                bartext += "/%s : %s: %s" % (
                    sec_txt, eta_txt, time_remaining_str,)
            else:
                bartext += "]"
            myavg = str(average)
            if len(myavg) < 2:
                myavg = " "+myavg
            current_txt += " <->  "+myavg+"% "+bartext+" "
            TextInterface.output(current_txt, back = True)

        self.__old_average = average

    def update(self):
        """
        Main fetch progress callback. You can reimplement this to refresh
        your output devices.
        """
        return self._push_progress_to_output()
