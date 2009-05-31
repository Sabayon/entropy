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
import shutil
from entropy.services.skel import SocketCommands
from entropy.const import etpConst
from entropy.services.ugc.interfaces import Server
from entropy.misc import EmailSender

class UGC(SocketCommands):

    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    def __init__(self, HostInterface, connection_data, store_path, store_url):

        SocketCommands.__init__(self, HostInterface, inst_name = "ugc-commands")
        self.connection_data = connection_data.copy()
        self.store_path = store_path
        self.store_url = store_url
        self.DOC_TYPES = etpConst['ugc_doctypes'].copy()
        self.SUPPORTED_DOCFILE_TYPES = [
            self.DOC_TYPES['image'],
            self.DOC_TYPES['generic_file'],
            self.DOC_TYPES['youtube_video'],
        ]
        self.raw_commands = [
            'ugc:add_comment', 'ugc:edit_comment',
            'ugc:register_stream','ugc:do_download_stats',
            'ugc:report_error'
        ]

        self.valid_commands = {
            'ugc:get_comments':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_comments,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get the comments of the provided package key",
                'syntax': "<SESSION_ID> ugc:get_comments app-foo/foo",
                'from': unicode(self), # from what class
            },
            'ugc:get_comments_by_identifiers':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_comments_by_identifiers,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get the comments belonging to the provided identifiers",
                'syntax': "<SESSION_ID> ugc:get_comments_by_identifiers <identifier1> <identifier2> <identifier3>",
                'from': unicode(self), # from what class
            },
            'ugc:get_documents_by_identifiers':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_documents_by_identifiers,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get the documents belonging to the provided identifiers",
                'syntax': "<SESSION_ID> ugc:get_documents_by_identifiers <identifier1> <identifier2> <identifier3>",
                'from': unicode(self), # from what class
            },
            'ugc:get_vote':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_vote,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get the vote of the provided package key",
                'syntax': "<SESSION_ID> ugc:get_vote app-foo/foo",
                'from': unicode(self), # from what class
            },
            'ugc:get_downloads':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_downloads,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get the number of downloads of the provided package key",
                'syntax': "<SESSION_ID> ugc:get_downloads app-foo/foo",
                'from': unicode(self), # from what class
            },
            'ugc:get_textdocs':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_textdocs,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get the text documents belonging to the provided package key",
                'syntax': "<SESSION_ID> ugc:get_textdocs app-foo/foo",
                'from': unicode(self), # from what class
            },
            'ugc:get_textdocs_by_identifiers':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_textdocs_by_identifiers,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get the text documents belonging to the provided identifiers",
                'syntax': "<SESSION_ID> ugc:get_textdocs_by_identifiers <identifier1> <identifier2> <identifier3>",
                'from': unicode(self), # from what class
            },
            'ugc:get_alldocs':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_alldocs,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get the all the documents belonging to the provided package key",
                'syntax': "<SESSION_ID> ugc:get_alldocs app-foo/foo",
                'from': unicode(self), # from what class
            },
            'ugc:get_allvotes':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_allvotes,
                'args': [],
                'as_user': False,
                'desc': "get vote information for every available package key",
                'syntax': "<SESSION_ID> ugc:get_allvotes",
                'from': unicode(self), # from what class
            },
            'ugc:get_alldownloads':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_get_alldownloads,
                'args': [],
                'as_user': False,
                'desc': "get download information for every available package key",
                'syntax': "<SESSION_ID> ugc:get_alldownloads",
                'from': unicode(self), # from what class
            },
            'ugc:do_vote':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_do_vote,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "vote the specified application (from 0 to 5)",
                'syntax': "<SESSION_ID> ugc:do_vote app-foo/foo <0..5>",
                'from': unicode(self), # from what class
            },
            'ugc:do_downloads':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_do_downloads,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "inform the system of downloaded applications",
                'syntax': "<SESSION_ID> ugc:do_downloads app-foo/foo1 app-foo/foo2 <...>",
                'from': unicode(self), # from what class
            },
            'ugc:add_comment':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_add_comment,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "insert a comment related to a package key",
                'syntax': "<SESSION_ID> ugc:add_comment app-foo/foo <valid xml formatted data>",
                'from': unicode(self), # from what class
            },
            'ugc:remove_comment':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_remove_comment,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "remove a comment (you need its iddoc and mod/admin privs)",
                'syntax': "<SESSION_ID> ugc:remove_comment <iddoc>",
                'from': unicode(self), # from what class
            },
            'ugc:edit_comment':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_edit_comment,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "edit a comment related to a package key (you need its iddoc, mod/admin privs or being the author)",
                'syntax': "<SESSION_ID> ugc:edit_comment <iddoc> <valid xml formatted data>",
                'from': unicode(self), # from what class
            },
            'ugc:register_stream':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_register_stream,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "register an uploaded file (through stream cmd) to the relative place (image, file, videos)",
                'syntax': "<SESSION_ID> ugc:register_stream app-foo/foo <valid xml formatted data>",
                'from': unicode(self), # from what class
            },
            'ugc:remove_image':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_remove_image,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "remove an image (you need its iddoc and mod/admin privs)",
                'syntax': "<SESSION_ID> ugc:remove_image <iddoc>",
                'from': unicode(self), # from what class
            },
            'ugc:remove_file':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_remove_file,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "remove a file (you need its iddoc and mod/admin privs)",
                'syntax': "<SESSION_ID> ugc:remove_file <iddoc>",
                'from': unicode(self), # from what class
            },
            'ugc:remove_youtube_video':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_remove_youtube_video,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "remove a youtube video (you need its iddoc and mod/admin privs)",
                'syntax': "<SESSION_ID> ugc:remove_youtube_video <iddoc>",
                'from': unicode(self), # from what class
            },
            'ugc:do_download_stats':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_do_download_stats,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "send information regarding downloads and distribution used",
                'syntax': "<SESSION_ID> ugc:do_download_stats <valid xml formatted data>",
                'from': unicode(self), # from what class
            },
            'ugc:report_error':    {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_do_report_error,
                'args': ["authenticator","myargs"],
                'as_user': False,
                'desc': "submit an Entropy Error Report",
                'syntax': "<SESSION_ID> ugc:report_error <valid xml formatted data>",
                'from': unicode(self), # from what class
            },
        }

    def _load_ugc_interface(self):
        return Server(self.connection_data, self.store_path, self.store_url)

    def _get_userid(self, authenticator):
        session_data = self.HostInterface.sessions.get(authenticator.session)
        if not session_data:
            return False
        elif not session_data.has_key('auth_uid'):
            return False
        return session_data['auth_uid']

    def _get_username(self, authenticator):
        return authenticator.get_username()

    def _get_session_file(self, authenticator):
        session_data = self.HostInterface.sessions.get(authenticator.session)
        if not session_data:
            return False
        elif not session_data.has_key('stream_path'):
            return False
        elif not session_data['stream_path']:
            return False
        mypath = session_data['stream_path']
        if not (os.path.isfile(mypath) and os.access(mypath,os.R_OK)):
            return False
        return mypath

    def _get_session_ip_address(self, authenticator):
        session_data = self.HostInterface.sessions.get(authenticator.session)
        if not session_data:
            return None
        elif not session_data.has_key('ip_address'):
            return None
        return session_data['ip_address']

    def docmd_register_stream(self, authenticator, myargs):

        if len(myargs) < 3:
            return None,'wrong arguments'
        pkgkey = myargs[0]

        xml_string = ' '.join(myargs[1:])
        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)
        if not (mydict.has_key('doc_type') \
                and mydict.has_key('title') \
                and mydict.has_key('description') \
                and mydict.has_key('keywords') \
                and mydict.has_key('file_name') ):
            return None,'wrong dict arguments, xml must have 5 items with attr value -> doc_type, title, description, keywords, file_name'
        doc_type = mydict.get('doc_type')
        title = mydict.get('title')
        description = mydict.get('description')
        keywords = mydict.get('keywords')
        file_name = mydict.get('file_name')
        real_filename = mydict.get('real_filename')

        try:
            doc_type = int(doc_type)
        except (ValueError,):
            return None,'wrong arguments (doc_type)'
        if doc_type not in self.SUPPORTED_DOCFILE_TYPES:
            return None,'unsupported doc type (SUPPORTED_DOCFILE_TYPES)'

        if not title: title = 'No title'
        if not description: description = 'No description'
        if not keywords: keywords = ''

        userid = self._get_userid(authenticator)
        if userid == None:
            return False,'no session userid available'
        elif isinstance(userid,bool) and not userid:
            return False,'no session data available'
        username = self._get_username(authenticator)

        # get file path
        stream_path = self._get_session_file(authenticator)
        if not stream_path:
            return False,'no stream path available'
        orig_stream_path = os.path.dirname(stream_path)
        new_stream_path = orig_stream_path

        scount = -1
        while os.path.lexists(new_stream_path):
            scount += 1
            b_name = os.path.basename(stream_path)
            b_name = "%s.%s" % (scount,b_name,)
            new_stream_path = os.path.join(os.path.dirname(orig_stream_path),b_name)
            if scount > 1000000:
                return False,'while loop interrupted while looking for new_stream_path'
        shutil.move(stream_path,new_stream_path)
        stream_path = new_stream_path

        ugc = self._load_ugc_interface()

        rslt = None, 'invalid doc type'
        if doc_type == self.DOC_TYPES['image']:
            rslt = ugc.insert_image(pkgkey, userid, username, stream_path, file_name, title, description, keywords)
        elif doc_type == self.DOC_TYPES['generic_file']:
            rslt = ugc.insert_file(pkgkey, userid, username, stream_path, file_name, title, description, keywords)
        elif doc_type == self.DOC_TYPES['youtube_video']:
            rslt = ugc.insert_youtube_video(pkgkey, userid, username, stream_path, real_filename, title, description, keywords)
        return rslt

    def docmd_add_comment(self, authenticator, myargs):

        if len(myargs) < 2:
            return None,'wrong arguments'
        pkgkey = myargs[0]
        xml_string = ' '.join(myargs[1:])
        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)
        if not (mydict.has_key('comment') and mydict.has_key('title') and mydict.has_key('keywords')):
            return None,'wrong dict arguments, xml must have 3 items with attr value -> comment, title, keywords'
        comment = mydict.get('comment')
        title = mydict.get('title')
        keywords = mydict.get('keywords')

        userid = self._get_userid(authenticator)
        if userid == None:
            return False,'no session userid available'
        elif isinstance(userid,bool) and not userid:
            return False,'no session data available'
        username = self._get_username(authenticator)

        ugc = self._load_ugc_interface()
        status, iddoc = ugc.insert_comment(pkgkey, userid, username, comment, title, keywords)
        if not status:
            t = 'unable to add comment'
            if isinstance(iddoc,basestring):
                t = iddoc
            return False,t
        return iddoc,'ok'

    def docmd_remove_comment(self, authenticator, myargs):

        if not myargs:
            return None,'wrong arguments'
        try:
            iddoc = int(myargs[0])
        except (ValueError,):
            return False,'not a valid iddoc'

        userid = self._get_userid(authenticator)
        if userid == None:
            return False,'no session userid available'
        elif isinstance(userid,bool) and not userid:
            return False,'no session data available'

        ugc = self._load_ugc_interface()
        iddoc_userid = ugc.get_iddoc_userid(iddoc)
        if iddoc_userid == None:
            return False,'document not available'

        # check if admin/mod or author
        if authenticator.is_user() and (userid != iddoc_userid):
            return False,'permission denied'

        ugc = self._load_ugc_interface()
        status, iddoc = ugc.remove_comment(iddoc)
        if not status:
            return False,'document not removed or not available'

        return iddoc,'ok'

    def docmd_edit_comment(self, authenticator, myargs):

        if len(myargs) < 2:
            return None,'wrong arguments'
        try:
            iddoc = int(myargs[0])
        except (ValueError,):
            return False,'not a valid iddoc'

        xml_string = ' '.join(myargs[1:])
        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)
        if not (mydict.has_key('comment') and mydict.has_key('title') and mydict.has_key('keywords')):
            return None,'wrong dict arguments, xml must have two item with attr value -> comment, title'
        new_comment = mydict.get('comment')
        new_title = mydict.get('title')
        new_keywords = mydict.get('keywords')

        userid = self._get_userid(authenticator)
        if userid == None:
            return False,'no session userid available'
        elif isinstance(userid,bool) and not userid:
            return False,'no session data available'

        ugc = self._load_ugc_interface()
        iddoc_userid = ugc.get_iddoc_userid(iddoc)
        if iddoc_userid == None:
            return False,'document not available'

        # check if admin/mod or author
        if authenticator.is_user() and (userid != iddoc_userid):
            return False,'permission denied'

        status, iddoc = ugc.edit_comment(iddoc, new_comment, new_title, new_keywords)
        if not status:
            return False,'document not removed or not available'

        return iddoc,'ok'

    def docmd_remove_image(self, authenticator, myargs):

        if not myargs:
            return None,'wrong arguments'
        try:
            iddoc = int(myargs[0])
        except (ValueError,):
            return False,'not a valid iddoc'

        userid = self._get_userid(authenticator)
        if userid == None:
            return False,'no session userid available'
        elif isinstance(userid,bool) and not userid:
            return False,'no session data available'

        ugc = self._load_ugc_interface()
        iddoc_userid = ugc.get_iddoc_userid(iddoc)
        if iddoc_userid == None:
            return False,'document not available'

        # check if admin/mod or author
        if authenticator.is_user() and (userid != iddoc_userid):
            return False,'permission denied'

        ugc = self._load_ugc_interface()
        status, iddoc = ugc.delete_image(iddoc)
        if not status:
            return False,'document not removed or not available'

        return iddoc,'ok'

    def docmd_remove_file(self, authenticator, myargs):

        if not myargs:
            return None,'wrong arguments'
        try:
            iddoc = int(myargs[0])
        except (ValueError,):
            return False,'not a valid iddoc'

        userid = self._get_userid(authenticator)
        if userid == None:
            return False,'no session userid available'
        elif isinstance(userid,bool) and not userid:
            return False,'no session data available'

        ugc = self._load_ugc_interface()
        iddoc_userid = ugc.get_iddoc_userid(iddoc)
        if iddoc_userid == None:
            return False,'document not available'

        # check if admin/mod or author
        if authenticator.is_user() and (userid != iddoc_userid):
            return False,'permission denied'

        ugc = self._load_ugc_interface()
        status, iddoc = ugc.delete_file(iddoc)
        if not status:
            return False,'document not removed or not available'

        return iddoc,'ok'

    def docmd_remove_youtube_video(self, authenticator, myargs):

        if not myargs:
            return None,'wrong arguments'
        try:
            iddoc = int(myargs[0])
        except (ValueError,):
            return False,'not a valid iddoc'

        userid = self._get_userid(authenticator)
        if userid == None:
            return False,'no session userid available'
        elif isinstance(userid,bool) and not userid:
            return False,'no session data available'

        ugc = self._load_ugc_interface()
        iddoc_userid = ugc.get_iddoc_userid(iddoc)
        if iddoc_userid == None:
            return False,'document not available'

        # check if admin/mod or author
        if authenticator.is_user() and (userid != iddoc_userid):
            return False,'permission denied'

        ugc = self._load_ugc_interface()
        status, iddoc = ugc.remove_youtube_video(iddoc)
        if not status:
            return False,'document not removed or not available'

        return iddoc,'ok'

    def docmd_do_vote(self, authenticator, myargs):

        if len(myargs) < 2:
            return None,'wrong arguments'
        pkgkey = myargs[0]
        vote = myargs[1]

        userid = self._get_userid(authenticator)
        if userid == None:
            return False,'no session userid available'
        elif isinstance(userid,bool) and not userid:
            return userid,'no session data available'

        ugc = self._load_ugc_interface()
        voted = ugc.do_vote(pkgkey, userid, vote)
        if not voted:
            return voted,'already voted'
        return voted,'ok'

    def docmd_do_downloads(self, authenticator, myargs):

        if not myargs:
            return None,'wrong arguments'

        ip_addr = self._get_session_ip_address(authenticator)
        ugc = self._load_ugc_interface()
        done = ugc.do_downloads(myargs, ip_addr = ip_addr)
        if not done:
            return done,'download not stored'
        return done,'ok'

    def docmd_do_download_stats(self, authenticator, myargs):

        if not myargs:
            return None,'wrong arguments'

        xml_string = ' '.join(myargs)
        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)
        if not (mydict.has_key('branch') and \
            mydict.has_key('release_string') and \
            mydict.has_key('pkgkeys')):
            return None,'wrong dict arguments, xml must have 3 items with attr value -> branch, release_string, pkgkeys'

        branch = mydict.get('branch')
        release_string = mydict.get('release_string')
        hw_hash = mydict.get('hw_hash')
        pkgkeys = mydict.get('pkgkeys').split()
        ip_addr = self._get_session_ip_address(authenticator)

        ugc = self._load_ugc_interface()
        done = ugc.do_download_stats(branch, release_string, hw_hash, pkgkeys,
            ip_addr)
        if not done:
            return done,'stats not stored'
        return done,'ok'

    def _get_generic_doctypes(self, pkgkey, doctypes):
        ugc = self._load_ugc_interface()
        metadata = ugc.get_ugc_metadata_doctypes(pkgkey, doctypes)
        if not metadata:
            return None
        return metadata

    def _get_generic_doctypes_by_identifiers(self, identifiers, doctypes):
        ugc = self._load_ugc_interface()
        metadata = ugc.get_ugc_metadata_doctypes_by_identifiers(identifiers, doctypes)
        if not metadata:
            return None
        return metadata

    def _get_generic_documents_by_identifiers(self, identifiers):
        ugc = self._load_ugc_interface()
        metadata = ugc.get_ugc_metadata_by_identifiers(identifiers)
        if not metadata:
            return None
        return metadata

    def docmd_get_comments(self, myargs):

        if not myargs:
            return None,'wrong arguments'
        pkgkey = myargs[0]

        metadata = self._get_generic_doctypes(pkgkey, [self.DOC_TYPES['comments']])
        if metadata == None:
            return None,'no metadata available'

        return metadata,'ok'

    def docmd_get_comments_by_identifiers(self, myargs):

        if not myargs:
            return None,'wrong arguments'

        identifiers = []
        for myarg in myargs:
            try:
                identifiers.append(int(myarg))
            except ValueError:
                pass

        if not identifiers:
            return None,'wrong arguments'

        metadata = self._get_generic_doctypes_by_identifiers(identifiers, [self.DOC_TYPES['comments']])
        if metadata == None:
            return None,'no metadata available'

        return metadata,'ok'

    def docmd_get_documents_by_identifiers(self, myargs):

        if not myargs:
            return None,'wrong arguments'

        identifiers = []
        for myarg in myargs:
            try:
                identifiers.append(int(myarg))
            except ValueError:
                pass

        if not identifiers:
            return None,'wrong arguments'

        metadata = self._get_generic_documents_by_identifiers(identifiers)
        if metadata == None:
            return None,'no metadata available'

        return metadata,'ok'

    def docmd_get_allvotes(self):
        ugc = self._load_ugc_interface()
        metadata = ugc.get_ugc_allvotes()
        if not metadata:
            return None,'no metadata available'
        return metadata,'ok'

    def docmd_get_alldownloads(self):
        ugc = self._load_ugc_interface()
        metadata = ugc.get_ugc_alldownloads()
        if not metadata:
            return None,'no metadata available'
        return metadata,'ok'

    def docmd_get_vote(self, myargs):

        if not myargs:
            return None,'wrong arguments'
        pkgkey = myargs[0]

        ugc = self._load_ugc_interface()
        vote = ugc.get_ugc_vote(pkgkey)
        return vote,'ok'

    def docmd_get_downloads(self, myargs):

        if not myargs:
            return None,'wrong arguments'
        pkgkey = myargs[0]

        ugc = self._load_ugc_interface()
        downloads = ugc.get_ugc_downloads(pkgkey)
        return downloads,'ok'

    def docmd_get_textdocs(self, myargs):

        if not myargs:
            return None,'wrong arguments'
        pkgkey = myargs[0]

        metadata = self._get_generic_doctypes(pkgkey, [self.DOC_TYPES['comments'],self.DOC_TYPES['bbcode_doc']])
        if metadata == None:
            return None,'no metadata available'

        return metadata,'ok'

    def docmd_get_textdocs_by_identifiers(self, myargs):

        if not myargs:
            return None,'wrong arguments'

        identifiers = []
        for myarg in myargs:
            try:
                identifiers.append(int(myarg))
            except ValueError:
                pass

        if not identifiers:
            return None,'wrong arguments'

        metadata = self._get_generic_doctypes_by_identifiers(identifiers, [self.DOC_TYPES['comments'],self.DOC_TYPES['bbcode_doc']])
        if metadata == None:
            return None,'no metadata available'

        return metadata,'ok'

    def docmd_get_alldocs(self, myargs):

        if not myargs:
            return None,'wrong arguments'
        pkgkey = myargs[0]

        metadata = self._get_generic_doctypes(pkgkey, [self.DOC_TYPES[x] for x in self.DOC_TYPES])
        if metadata == None:
            return None,'no metadata available'

        return metadata,'ok'

    def docmd_do_report_error(self, authenticator, myargs):

        if not myargs:
            return None, 'wrong arguments'

        xml_string = ' '.join(myargs)
        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None, "error: %s" % (e,)

        subject = 'Entropy Error Reporting Handler'
        destination_email = 'entropy.errors@sabayon.org'
        sender_email = mydict.get('email', 'anonymous@sabayon.org')
        keys_to_file = ['errordata', 'processes', 'lspci', 'dmesg', 'locale']

        # call it over
        mail_txt = ''
        for key in sorted(mydict):
            if key in keys_to_file:
                continue
            mail_txt += u'%s: %s\n' % (key, mydict.get(key),)

        from datetime import datetime
        import time
        import tempfile
        date = datetime.fromtimestamp(time.time())

        # add ip address
        ip_addr = self._get_session_ip_address(authenticator)
        mail_txt += u'ip_address: %s\n' % (ip_addr,)
        mail_txt += u'date: %s\n' % (date,)

        files = []
        rm_paths = []
        for key in keys_to_file:
            if key not in mydict:
                continue
            fd, path = tempfile.mkstemp(suffix = "__%s.txt" % (key,))
            try:
                f_path = open(path, "w")
                f_path.write(mydict.get(key,''))
                f_path.flush()
                f_path.close()
            except IOError:
                continue
            files.append(path)
            rm_paths.append(path)

        sender = EmailSender()
        sender.send_mime_email(sender_email, [destination_email], subject,
            mail_txt, files)
        del sender

        for rm_path in rm_paths:
            os.remove(rm_path)

        return True,'ok'
