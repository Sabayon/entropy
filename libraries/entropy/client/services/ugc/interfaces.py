# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Client Services UGC Base Interfaces}.

"""

from __future__ import with_statement
import os
from entropy.core import Singleton
from entropy.exceptions import *
from entropy.const import etpConst, etpCache, const_setup_file, const_setup_perms
from entropy.i18n import _

class Client:

    ssl_connection = True
    def __init__(self, EquoInstance, quiet = True, show_progress = False):

        from entropy.client.interfaces import Client as Cl
        if not isinstance(EquoInstance,Cl):
            mytxt = _("A valid Client based instance is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        import socket, threading
        self.socket, self.threading = socket, threading
        import struct
        self.struct = struct
        self.Entropy = EquoInstance
        self.store = AuthStore()
        self.quiet = quiet
        self.show_progress = show_progress
        self.UGCCache = Cache(self)
        self.TxLocks = {}

    def connect_to_service(self, repository, timeout = None):
        if repository not in self.Entropy.SystemSettings['repositories']['available']:
            raise RepositoryError("RepositoryError: %s" % (_('repository is not available'),))

        try:
            url = self.Entropy.SystemSettings['repositories']['available'][repository]['plain_database'].split("/")[2]
            port = self.Entropy.SystemSettings['repositories']['available'][repository]['service_port']
            if self.ssl_connection: port = self.Entropy.SystemSettings['repositories']['available'][repository]['ssl_service_port']
        except (IndexError,KeyError,):
            raise RepositoryError("RepositoryError: %s" % (_('repository metadata is malformed'),))

        from entropy.services.ugc.interfaces import Client
        from entropy.client.services.ugc.commands import Client as CommandsClient
        args = [self.Entropy, CommandsClient]
        kwargs = {
            'ssl': self.ssl_connection,
            'quiet': self.quiet,
            'show_progress': self.show_progress
        }
        if timeout != None: kwargs['socket_timeout'] = timeout
        srv = Client(*args,**kwargs)
        srv.connect(url, port)
        return srv

    def get_service_connection(self, repository, check = True, timeout = None):
        if check:
            if not self.is_repository_eapi3_aware(repository):
                return None
        try:
            srv = self.connect_to_service(repository, timeout = timeout)
        except (RepositoryError,ConnectionError,):
            return None
        except (self.socket.error,self.struct.error,):
            return None
        return srv

    def is_repository_eapi3_aware(self, repository):

        aware = self.UGCCache._get_live_cache_item(repository, 'is_repository_eapi3_aware')
        if aware != None:
            return aware

        srv = self.get_service_connection(repository, check = False, timeout = 3)
        if srv == None:
            aware = False
        else:
            session = srv.open_session()
            if session != None:
                srv.close_session(session)
                srv.disconnect()
                aware = True
            else:
                aware = False

        self.UGCCache._set_live_cache_item(repository, 'is_repository_eapi3_aware', aware)
        return aware

    def read_login(self, repository):
        return self.store.read_login(repository)

    def remove_login(self, repository):
        return self.store.remove_login(repository)

    def do_login(self, repository, force = False):

        login_data = self.read_login(repository)
        if (login_data != None) and not force:
            return True,_('ok')

        aware = self.is_repository_eapi3_aware(repository)
        if not aware:
            return False,_('repository does not support EAPI3')

        def fake_callback(*args,**kwargs):
            return True

        attempts = 3
        while attempts:

            # use input box to read login
            input_params = [
                ('username',_('Username'),fake_callback,False),
                ('password',_('Password'),fake_callback,True)
            ]
            login_data = self.Entropy.inputBox(
                "%s %s %s" % (_('Please login against'),repository,_('repository'),),
                input_params,
                cancel_button = True
            )
            if not login_data:
                return False,_('login abort')

            # now verify
            srv = self.get_service_connection(repository)
            if srv == None:
                return False,_('connection issues')
            session = srv.open_session()
            login_status, login_msg = srv.CmdInterface.service_login(login_data['username'], login_data['password'], session)
            if not login_status:
                srv.close_session(session)
                srv.disconnect()
                self.Entropy.askQuestion("%s: %s" % (_("Access denied. Login failed"),login_msg,), responses = ["Ok"])
                attempts -= 1
                continue

            # login accepted, store it?
            srv.close_session(session)
            srv.disconnect()
            rc = self.Entropy.askQuestion(_("Login successful. Do you want to save these credentials ?"))
            save = False
            if rc == "Yes": save = True
            self.store.store_login(login_data['username'], login_data['password'], repository, save = save)
            return True,_('ok')


    def login(self, repository, force = False):

        if not self.TxLocks.has_key(repository):
            self.TxLocks[repository] = self.threading.Lock()

        with self.TxLocks[repository]:
            return self.do_login(repository, force = force)


    def logout(self, repository):
        return self.store.remove_login(repository)

    def do_cmd(self, repository, login_required, func, args, kwargs):

        if not self.TxLocks.has_key(repository):
            self.TxLocks[repository] = self.threading.Lock()

        with self.TxLocks[repository]:

            if login_required:
                status, err_msg = self.do_login(repository)
                if not status:
                    return False,err_msg

            srv = self.get_service_connection(repository)
            if srv == None:
                return False,'no connection'
            session = srv.open_session()
            if session == None:
                return False,'no session'
            args.insert(0,session)

            if login_required:
                stored_pass = False
                while 1:
                    # login
                    login_data = self.read_login(repository)
                    if login_data == None:
                        status, msg = self.login(repository)
                        if not status: return status, msg
                        username, password = self.read_login(repository)
                    else:
                        stored_pass = True
                        username, password = login_data
                    logged, error = srv.CmdInterface.service_login(username, password, session)
                    if not logged:
                        if stored_pass:
                            stored_pass = False
                            self.remove_login(repository)
                            continue
                        srv.close_session(session)
                        srv.disconnect()
                        return logged, error
                    break

            try:
                cmd_func = getattr(srv.CmdInterface, func)
            except AttributeError:
                return False, 'local function not available'
            rslt = cmd_func(*args,**kwargs)
            try:
                srv.close_session(session)
                srv.disconnect()
            except ConnectionError:
                return False, 'no connection'

            return rslt

    def get_comments(self, repository, pkgkey):
        return self.do_cmd(repository, False, "ugc_get_textdocs", [pkgkey], {})

    def get_comments_by_identifiers(self, repository, identifiers):
        return self.do_cmd(repository, False, "ugc_get_textdocs_by_identifiers", [identifiers], {})

    def get_documents_by_identifiers(self, repository, identifiers):
        return self.do_cmd(repository, False, "ugc_get_documents_by_identifiers", [identifiers], {})

    def add_comment(self, repository, pkgkey, comment, title, keywords):
        self.UGCCache.clear_alldocs_cache(repository)
        return self.do_cmd(repository, True, "ugc_add_comment", [pkgkey, comment, title, keywords], {})

    def edit_comment(self, repository, iddoc, new_comment, new_title, new_keywords):
        self.UGCCache.clear_alldocs_cache(repository)
        return self.do_cmd(repository, True, "ugc_edit_comment", [iddoc, new_comment, new_title, new_keywords], {})

    def remove_comment(self, repository, iddoc):
        self.UGCCache.clear_alldocs_cache(repository)
        return self.do_cmd(repository, True, "ugc_remove_comment", [iddoc], {})

    def add_vote(self, repository, pkgkey, vote):
        data = self.do_cmd(repository, True, "ugc_do_vote", [pkgkey, vote], {})
        if isinstance(data,tuple): voted, add_err_msg = data
        else: return False,'wrong server answer'
        if voted: self.get_vote(repository, pkgkey)
        return voted, add_err_msg

    def get_vote(self, repository, pkgkey):
        vote, err_msg = self.do_cmd(repository, False, "ugc_get_vote", [pkgkey], {})
        if isinstance(vote,float):
            mydict = {pkgkey: vote}
            self.UGCCache.update_vote_cache(repository, mydict)
        return vote, err_msg

    def get_all_votes(self, repository):
        votes_dict, err_msg = self.do_cmd(repository, False, "ugc_get_allvotes", [], {})
        if isinstance(votes_dict,dict):
            self.UGCCache.update_vote_cache(repository, votes_dict)
        return votes_dict, err_msg

    def add_downloads(self, repository, pkgkeys):
        return self.do_cmd(repository, False, "ugc_do_downloads", [pkgkeys], {})

    def get_downloads(self, repository, pkgkey):
        data = self.do_cmd(repository, False, "ugc_get_downloads", [pkgkey], {})
        if isinstance(data,tuple): downloads, err_msg = data
        else: return False,'wrong server answer'
        if downloads:
            mydict = {pkgkey: downloads}
            self.UGCCache.update_downloads_cache(repository, mydict)
        return downloads, err_msg

    def get_all_downloads(self, repository):
        down_dict, err_msg = self.do_cmd(repository, False, "ugc_get_alldownloads", [], {})
        if isinstance(down_dict,dict):
            self.UGCCache.update_downloads_cache(repository, down_dict)
        return down_dict, err_msg

    def add_download_stats(self, repository, pkgkeys):
        return self.do_cmd(repository, False, "ugc_do_download_stats", [pkgkeys], {})

    def send_file(self, repository, pkgkey, file_path, title, description, keywords):
        self.UGCCache.clear_alldocs_cache(repository)
        return self.do_cmd(repository, True, "ugc_send_file", [pkgkey, file_path, etpConst['ugc_doctypes']['generic_file'], title, description, keywords], {})

    def remove_file(self, repository, iddoc):
        self.UGCCache.clear_alldocs_cache(repository)
        return self.do_cmd(repository, True, "ugc_remove_file", [iddoc], {})

    def send_image(self, repository, pkgkey, image_path, title, description, keywords):
        self.UGCCache.clear_alldocs_cache(repository)
        return self.do_cmd(repository, True, "ugc_send_file", [pkgkey, image_path, etpConst['ugc_doctypes']['image'], title, description, keywords], {})

    def remove_image(self, repository, iddoc):
        self.UGCCache.clear_alldocs_cache(repository)
        return self.do_cmd(repository, True, "ugc_remove_image", [iddoc], {})

    def send_youtube_video(self, repository, pkgkey, video_path, title, description, keywords):
        self.UGCCache.clear_alldocs_cache(repository)
        return self.do_cmd(repository, True, "ugc_send_file", [pkgkey, video_path, etpConst['ugc_doctypes']['youtube_video'], title, description, keywords], {})

    def remove_youtube_video(self, repository, iddoc):
        self.UGCCache.clear_alldocs_cache(repository)
        return self.do_cmd(repository, True, "ugc_remove_youtube_video", [iddoc], {})

    def get_docs(self, repository, pkgkey):
        data = self.do_cmd(repository, False, "ugc_get_docs", [pkgkey], {})
        if isinstance(data,tuple): docs_data, err_msg = data
        else: return False,'wrong server answer'
        if err_msg == 'ok':
            self.UGCCache.update_alldocs_cache(pkgkey, repository, docs_data)
        return docs_data, err_msg

    def send_document_autosense(self, repository, pkgkey, ugc_type, data, title, description, keywords):
        if ugc_type == etpConst['ugc_doctypes']['generic_file']:
            return self.send_file(repository, pkgkey, data, title, description, keywords)
        elif ugc_type == etpConst['ugc_doctypes']['image']:
            return self.send_image(repository, pkgkey, data, title, description, keywords)
        elif ugc_type == etpConst['ugc_doctypes']['youtube_video']:
            return self.send_youtube_video(repository, pkgkey, data, title, description, keywords)
        elif ugc_type == etpConst['ugc_doctypes']['comments']:
            return self.add_comment(repository, pkgkey, description, title, keywords)
        return None,'type not supported locally'

    def remove_document_autosense(self, repository, iddoc, ugc_type):
        if ugc_type == etpConst['ugc_doctypes']['generic_file']:
            return self.remove_file(repository, iddoc)
        elif ugc_type == etpConst['ugc_doctypes']['image']:
            return self.remove_image(repository, iddoc)
        elif ugc_type == etpConst['ugc_doctypes']['youtube_video']:
            return self.remove_youtube_video(repository, iddoc)
        elif ugc_type == etpConst['ugc_doctypes']['comments']:
            return self.remove_comment(repository, iddoc)
        return None,'type not supported locally'

    def report_error(self, repository, error_data):
        return self.do_cmd(repository, False, "report_error", [error_data], {})


class AuthStore(Singleton):

    access_file = etpConst['ugc_accessfile']
    def init_singleton(self):

        from xml.dom import minidom
        from xml.parsers import expat
        self.expat = expat
        self.minidom = minidom
        self.setup_store_paths()
        try:
            self.setup_permissions()
        except IOError:
            pass
        self.store = {}
        try:
            self.xmldoc = self.minidom.parse(self.access_file)
        except (self.expat.ExpatError,IOError,):
            self.xmldoc = None
        if self.xmldoc != None:
            try:
                self.parse_document()
            except self.expat.ExpatError:
                self.xmldoc = None
                self.store = {}

    def setup_store_paths(self):
        myhome = os.getenv("HOME")
        if myhome != None:
            if os.path.isdir(myhome) and os.access(myhome,os.W_OK):
                self.access_file = os.path.join(myhome,".config/entropy",
                    os.path.basename(self.access_file))
        self.access_dir = os.path.dirname(self.access_file)

    def setup_permissions(self):
        if not os.path.isdir(self.access_dir):
            os.makedirs(self.access_dir)
        if not os.path.isfile(self.access_file):
            f = open(self.access_file, "w")
            f.close()
        gid = etpConst['entropygid']
        if gid is None:
            gid = 0

        try:
            const_setup_file(self.access_dir, gid, 0700)
        except OSError:
            pass
        try:
            const_setup_file(self.access_file, gid, 0600)
        except OSError:
            pass

    def parse_document(self):
        self.store.clear()
        store = self.xmldoc.getElementsByTagName("store")[0]
        repositories = store.getElementsByTagName("repository")
        for repository in repositories:
            repoid = repository.getAttribute("id")
            if not repoid: continue
            username = repository.getElementsByTagName("username")[0].firstChild.data.strip()
            password = repository.getElementsByTagName("password")[0].firstChild.data.strip()
            self.store[repoid] = {'username': username, 'password': password}

    def store_login(self, username, password, repository, save = True):
        self.store[repository] = {'username': username, 'password': password}
        if save:
            self.save_store()

    def save_store(self):

        self.xmldoc = self.minidom.Document()
        store = self.xmldoc.createElement("store")

        for repository in self.store:
            repo = self.xmldoc.createElement("repository")
            repo.setAttribute('id',repository)
            # username
            username = self.xmldoc.createElement("username")
            username_value = self.xmldoc.createTextNode(self.store[repository]['username'])
            username.appendChild(username_value)
            repo.appendChild(username)
            # password
            password = self.xmldoc.createElement("password")
            password_value = self.xmldoc.createTextNode(self.store[repository]['password'])
            password.appendChild(password_value)
            repo.appendChild(password)
            store.appendChild(repo)

        self.xmldoc.appendChild(store)
        f = open(self.access_file,"w")
        f.writelines(self.xmldoc.toprettyxml(indent="    "))
        f.flush()
        f.close()
        self.setup_permissions()
        self.parse_document()

    def remove_login(self, repository, save = True):
        if repository in self.store:
            del self.store[repository]
            if save:
                self.save_store()

    def read_login(self, repository):
        if repository in self.store:
            return self.store[repository]['username'],self.store[repository]['password']

class Cache:

    def __init__(self, UGCClientInstance):

        if not isinstance(UGCClientInstance,Client):
            mytxt = _("A valid UGC Client interface based instance is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        import threading
        import entropy.dump as dumpTools
        self.CacheLock = threading.Lock()
        self.dumpTools = dumpTools
        self.Service = UGCClientInstance
        self.xcache = {}

    def _get_live_cache_item(self, repository, item):
        if repository not in self.xcache:
            return None
        return self.xcache[repository].get(item)

    def _set_live_cache_item(self, repository, item, obj):
        if repository not in self.xcache:
            self.xcache[repository] = {}
        if type(obj) in (list,tuple,):
            my_obj = obj[:]
        elif type(obj) in (set,frozenset,dict,):
            my_obj = obj.copy()
        else:
            my_obj = obj
        self.xcache[repository][item] = my_obj

    def _clear_live_cache_item(self, repository, item):
        if not self.xcache.has_key(repository):
            return
        if not self.xcache[repository].has_key(item):
            return
        del self.xcache[repository][item]

    def _get_store_cache_file(self, iddoc, repository, doc_url):
        return "%s/%s/iddoc_%s/%s" % (etpCache['ugc_docs'], repository, iddoc, doc_url,)

    def _get_vote_cache_file(self, repository):
        return self._get_vote_cache_dir(repository)

    def _get_downloads_cache_file(self, repository):
        return self._get_downloads_cache_dir(repository)

    def _get_alldocs_cache_file(self, pkgkey, repository):
        return self._get_alldocs_cache_dir(repository)+"/"+pkgkey

    def _get_alldocs_cache_dir(self, repository):
        return etpCache['ugc_docs']+"/"+repository

    def _get_downloads_cache_dir(self, repository):
        return etpCache['ugc_downloads']+"/"+repository

    def _get_vote_cache_dir(self, repository):
        return etpCache['ugc_votes']+"/"+repository

    def _get_vote_cache_key(self, repository):
        return 'get_vote_cache_'+repository

    def _get_downloads_cache_key(self, repository):
        return 'get_downloads_cache_'+repository

    def _get_alldocs_cache_key(self, repository):
        return 'get_package_alldocs_cache_'+repository

    def store_document(self, iddoc, repository, doc_url):
        cache_file = os.path.join(etpConst['dumpstoragedir'],self._get_store_cache_file(iddoc, repository, doc_url))
        cache_dir = os.path.dirname(cache_file)

        try:
            if not os.path.isdir(cache_dir):
                os.makedirs(cache_dir,0775)
                if etpConst['entropygid'] != None:
                    const_setup_perms(cache_dir,etpConst['entropygid'])
        except OSError:
            raise PermissionDenied("PermissionDenied: %s %s" % (_("Cannot setup cache directory"),cache_dir,))
        if not os.access(cache_dir,os.W_OK):
            raise PermissionDenied("PermissionDenied: %s %s" % (_("Cannot write to cache directory"),cache_dir,))

        if os.path.isfile(cache_file) or os.path.islink(cache_file):
            try:
                os.remove(cache_file)
            except OSError:
                raise PermissionDenied("PermissionDenied: %s %s" % (_("Cannot remove cache file"),cache_file,))

        fetcher = self.Service.Entropy.urlFetcher(doc_url, cache_file, resume = False)
        rc = fetcher.download()
        if rc in ("-1","-2","-3","-4"): return None
        if not os.path.isfile(cache_file): return None

        try:
            os.chmod(cache_file,0664)
            if etpConst['entropygid'] != None:
                os.chown(cache_file,-1,etpConst['entropygid'])
        except OSError:
            raise PermissionDenied("PermissionDenied: %s %s" % (_("Cannot write to cache file"),cache_file,))

        del fetcher
        return cache_file

    def get_stored_document(self, iddoc, repository, doc_url):
        cache_file = os.path.join(etpConst['dumpstoragedir'],self._get_store_cache_file(iddoc, repository, doc_url))
        if os.path.isfile(cache_file) and os.access(cache_file,os.R_OK):
            return cache_file

    def update_vote_cache(self, repository, vote_dict):
        cached = self.get_vote_cache(repository)
        if cached == None:
            cached = vote_dict.copy()
        else:
            cached.update(vote_dict)
        self.save_vote_cache(repository,cached)

    def update_downloads_cache(self, repository, down_dict):
        cached = self.get_downloads_cache(repository)
        if cached == None:
            cached = down_dict.copy()
        else:
            cached.update(down_dict)
        self.save_downloads_cache(repository,cached)

    def update_alldocs_cache(self, pkgkey, repository, alldocs_dict):
        self.save_alldocs_cache(pkgkey, repository, alldocs_dict)

    def clear_alldocs_cache(self, repository):
        with self.CacheLock:
            self.Service.Entropy.clear_dump_cache(self._get_alldocs_cache_dir(repository))
            self._clear_live_cache_item(repository, self._get_alldocs_cache_key(repository))

    def clear_downloads_cache(self, repository):
        with self.CacheLock:
            self.Service.Entropy.clear_dump_cache(self._get_alldocs_cache_dir(repository))
            self._clear_live_cache_item(repository, self._get_downloads_cache_key(repository))

    def clear_vote_cache(self, repository):
        with self.CacheLock:
            self.Service.Entropy.clear_dump_cache(self._get_vote_cache_dir(repository))
            self._clear_live_cache_item(repository, self._get_vote_cache_key(repository))

    def clear_cache(self, repository):
        self.clear_alldocs_cache(repository)
        self.clear_downloads_cache(repository)
        self.clear_vote_cache(repository)
        self.xcache.clear()

    def get_vote_cache(self, repository):
        cache_key = self._get_vote_cache_key(repository)
        cached = self._get_live_cache_item(repository, cache_key)
        if cached != None:
            return cached
        with self.CacheLock:
            cache_file = self._get_vote_cache_file(repository)
            try:
                data = self.dumpTools.loadobj(cache_file)
                if data != None:
                    self._set_live_cache_item(repository, cache_key, data)
            except (IOError,EOFError,OSError):
                data = None
        return data

    def get_downloads_cache(self, repository):
        cache_key = self._get_downloads_cache_key(repository)
        cached = self._get_live_cache_item(repository, cache_key)
        if cached != None:
            return cached
        with self.CacheLock:
            cache_file = self._get_downloads_cache_file(repository)
            try:
                data = self.dumpTools.loadobj(cache_file)
                if data != None:
                    self._set_live_cache_item(repository, cache_key, data)
            except (IOError,EOFError,OSError):
                data = None
        return data

    def get_alldocs_cache(self, pkgkey, repository):
        cache_key = self._get_alldocs_cache_key(repository)
        cached = self._get_live_cache_item(repository, cache_key)
        if isinstance(cached,dict):
            if cached.has_key(pkgkey): return cached[pkgkey]
        else:
            cached = {}
        with self.CacheLock:
            cache_file = self._get_alldocs_cache_file(pkgkey, repository)
            try:
                data = self.dumpTools.loadobj(cache_file)
                if data != None:
                    cached[pkgkey] = data
                    self._set_live_cache_item(repository, cache_key, cached)
            except (IOError,EOFError,OSError):
                data = None
        return data

    def save_vote_cache(self, repository, vote_dict):
        with self.CacheLock:
            self._clear_live_cache_item(repository, self._get_vote_cache_key(repository))
            self.dumpTools.dumpobj(self._get_vote_cache_file(repository), vote_dict)

    def save_downloads_cache(self, repository, down_dict):
        with self.CacheLock:
            self._clear_live_cache_item(repository, self._get_downloads_cache_key(repository))
            self.dumpTools.dumpobj(self._get_downloads_cache_file(repository), down_dict)

    def save_alldocs_cache(self, pkgkey, repository, alldocs_dict):
        with self.CacheLock:
            self._clear_live_cache_item(repository, self._get_alldocs_cache_key(repository))
            self.dumpTools.dumpobj(self._get_alldocs_cache_file(pkgkey, repository), alldocs_dict)

    def get_package_vote(self, repository, pkgkey):
        cache = self.get_vote_cache(repository)
        if not cache:
            return 0.0
        elif not isinstance(cache,dict):
            return 0.0
        elif not cache.has_key(pkgkey):
            return 0.0
        return cache[pkgkey]

    def get_package_downloads(self, repository, pkgkey):
        cache = self.get_downloads_cache(repository)
        if not cache:
            return 0
        elif not isinstance(cache,dict):
            return 0
        elif not cache.has_key(pkgkey):
            return 0
        try:
            return int(cache[pkgkey])
        except ValueError:
            return 0
