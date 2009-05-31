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
from entropy.exceptions import *
from entropy.const import etpConst
from entropy.output import darkblue, bold, blue, darkgreen, darkred, brown
from entropy.i18n import _
from entropy.core import SystemSettings

class Base:

    def __init__(self, OutputInterface, Service):

        if not hasattr(OutputInterface,'updateProgress'):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (OutputInterface,mytxt,))
        elif not callable(OutputInterface.updateProgress):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (OutputInterface,mytxt,))

        from entropy.services.ugc.interfaces import Client as Cl
        if not isinstance(Service, (Cl,)):
                mytxt = _("A valid entropy.services.ugc.interfaces.Client based instance is needed")
                raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (Service,mytxt,))

        import socket, zlib, struct
        import entropy.tools as entropyTools
        import entropy.dump as dumpTools
        self.entropyTools, self.socket, self.zlib, self.struct, self.dumpTools = entropyTools, socket, zlib, struct, dumpTools
        self.Output = OutputInterface
        self.Service = Service
        self.output_header = ''
        self.SystemSettings = SystemSettings()

    def handle_standard_answer(self, data, repository = None, arch = None, product = None):
        do_skip = False
        # elaborate answer
        if data == None:
            mytxt = _("feature not supported remotely")
            self.Output.updateProgress(
                "[%s:%s|%s:%s|%s:%s] %s" % (
                        darkblue(_("repo")),
                        bold(str(repository)),
                        darkred(_("arch")),
                        bold(str(arch)),
                        darkgreen(_("product")),
                        bold(str(product)),
                        blue(mytxt),
                ),
                importance = 1,
                type = "error",
                header = self.output_header
            )
            do_skip = True
        elif not data:
            mytxt = _("service temporarily not available")
            self.Output.updateProgress(
                "[%s:%s|%s:%s|%s:%s] %s" % (
                        darkblue(_("repo")),
                        bold(str(repository)),
                        darkred(_("arch")),
                        bold(str(arch)),
                        darkgreen(_("product")),
                        bold(str(product)),
                        blue(mytxt),
                ),
                importance = 1,
                type = "error",
                header = self.output_header
            )
            do_skip = True
        elif data == self.Service.answers['no']:
            # command failed
            mytxt = _("command failed")
            self.Output.updateProgress(
                "[%s:%s|%s:%s|%s:%s] %s" % (
                        darkblue(_("repo")),
                        bold(str(repository)),
                        darkred(_("arch")),
                        bold(str(arch)),
                        darkgreen(_("product")),
                        bold(str(product)),
                        blue(mytxt),
                ),
                importance = 1,
                type = "error",
                header = self.output_header
            )
        elif data != self.Service.answers['ok']:
            mytxt = _("received wrong answer")
            self.Output.updateProgress(
                "[%s:%s|%s:%s|%s:%s] %s: %s" % (
                        darkblue(_("repo")),
                        bold(str(repository)),
                        darkred(_("arch")),
                        bold(str(arch)),
                        darkgreen(_("product")),
                        bold(str(product)),
                        blue(mytxt),
                        repr(data),
                ),
                importance = 1,
                type = "error",
                header = self.output_header
            )
            do_skip = True
        return do_skip

    def get_result(self, session):
        # get the information
        cmd = "%s rc" % (session,)
        self.Service.transmit(cmd)
        try:
            data = self.Service.receive()
            return data
        except:
            self.entropyTools.print_traceback()
            return None

    def convert_stream_to_object(self, data, gzipped, repository = None, arch = None, product = None):

        # unstream object
        error = False
        try:
            data = self.Service.stream_to_object(data, gzipped)
        except (EOFError,IOError,self.zlib.error,self.dumpTools.pickle.UnpicklingError,):
            mytxt = _("cannot convert stream into object")
            self.Output.updateProgress(
                "[%s:%s|%s:%s|%s:%s] %s" % (
                        darkblue(_("repo")),
                        bold(unicode(repository)),
                        darkred(_("arch")),
                        bold(unicode(arch)),
                        darkgreen(_("product")),
                        bold(unicode(product)),
                        blue(mytxt),
                ),
                importance = 1,
                type = "error",
                header = self.output_header
            )
            data = None
            error = True
        return data, error

    def retrieve_command_answer(self, cmd, session_id, repository = None, arch = None, product = None, compression = False):

        tries = 3
        lasterr = None
        while 1:

            if tries <= 0:
                return lasterr
            tries -= 1

            try:
                # send command
                self.Service.transmit(cmd)
            except (SSLError,):
                return None
            # receive answer
            data = self.Service.receive()

            skip = self.handle_standard_answer(data, repository, arch, product)
            if skip:
                continue

            data = self.get_result(session_id)
            if data == None:
                lasterr = None
                continue
            elif not data:
                lasterr = False
                continue

            objdata, error = self.convert_stream_to_object(data, compression, repository, arch, product)
            if not error:
                return objdata

    def do_generic_handler(self, cmd, session_id, tries = 10, compression = False):

        self.Service.check_socket_connection()

        while 1:
            try:
                result = self.retrieve_command_answer(cmd, session_id, compression = compression)
                if result == None:
                    return False,'command not supported' # untranslated on purpose
                return result
            except (self.socket.error,self.struct.error,):
                self.Service.reconnect_socket()
                tries -= 1
                if tries < 1:
                    raise

    def set_gzip_compression(self, session, do):
        self.Service.check_socket_connection()
        cmd = "%s %s %s %s zlib" % (session, 'session_config', 'compression', do,)
        self.Service.transmit(cmd)
        data = self.Service.receive()
        if data == self.Service.answers['ok']:
            return True
        return False

    def service_login(self, username, password, session_id):

        cmd = "%s %s %s %s" % (
            session_id,
            'login',
            username,
            password,
        )
        return self.do_generic_handler(cmd, session_id)

    def service_logout(self, username, session_id):

        cmd = "%s %s %s" % (
            session_id,
            'logout',
            username,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_logged_user_data(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'user_data',
        )
        return self.do_generic_handler(cmd, session_id)

    def is_user(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'is_user',
        )
        return self.do_generic_handler(cmd, session_id)

    def is_developer(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'is_developer',
        )
        return self.do_generic_handler(cmd, session_id)

    def is_moderator(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'is_moderator',
        )
        return self.do_generic_handler(cmd, session_id)

    def is_administrator(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'is_administrator',
        )
        return self.do_generic_handler(cmd, session_id)

    def available_commands(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'available_commands',
        )
        return self.do_generic_handler(cmd, session_id)


class Client(Base):

    def __init__(self, EntropyInterface, ServiceInterface):
        Base.__init__(self, EntropyInterface, ServiceInterface)

    def differential_packages_comparison(self, session_id, idpackages, repository, arch, product):

        myidlist = ' '.join([str(x) for x in idpackages])
        cmd = "%s %s %s %s %s %s %s" % (
            session_id,
            'repository_server:dbdiff',
            repository,
            arch,
            product,
            self.SystemSettings['repositories']['branch'],
            myidlist,
        )

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        data = self.do_generic_handler(cmd, session_id, tries = 5, compression = compression)

        # disable compression
        self.set_gzip_compression(session_id, False)

        return data

    def get_repository_treeupdates(self, session_id, repository, arch, product):

        cmd = "%s %s %s %s %s %s" % (
            session_id,
            'repository_server:treeupdates',
            repository,
            arch,
            product,
            self.SystemSettings['repositories']['branch'],
        )
        return self.do_generic_handler(cmd, session_id, tries = 5)

    def get_package_sets(self, session_id, repository, arch, product):

        cmd = "%s %s %s %s %s %s" % (
            session_id,
            'repository_server:get_package_sets',
            repository,
            arch,
            product,
            self.SystemSettings['repositories']['branch'],
        )
        return self.do_generic_handler(cmd, session_id, tries = 5)

    def get_repository_metadata(self, session_id, repository, arch, product):

        cmd = "%s %s %s %s %s %s" % (
            session_id,
            'repository_server:get_repository_metadata',
            repository,
            arch,
            product,
            self.SystemSettings['repositories']['branch'],
        )
        return self.do_generic_handler(cmd, session_id, tries = 5)

    def get_package_information(self, session_id, idpackages, repository, arch, product):

        cmd = "%s %s %s %s %s %s %s %s" % (
            session_id,
            'repository_server:pkginfo',
            True,
            repository,
            arch,
            product,
            self.SystemSettings['repositories']['branch'],
            ' '.join([str(x) for x in idpackages]),
        )

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        data = self.do_generic_handler(cmd, session_id, compression = compression)

        # disable compression
        self.set_gzip_compression(session_id, False)

        return data

    def get_strict_package_information(self, session_id, idpackages, repository, arch, product):

        cmd = "%s %s %s %s %s %s %s %s" % (
            session_id,
            'repository_server:pkginfo_strict',
            True,
            repository,
            arch,
            product,
            self.SystemSettings['repositories']['branch'],
            ' '.join([str(x) for x in idpackages]),
        )

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        data = self.do_generic_handler(cmd, session_id, compression = compression)

        # disable compression
        self.set_gzip_compression(session_id, False)

        return data

    def ugc_do_downloads(self, session_id, pkgkeys):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:do_downloads',
            ' '.join(pkgkeys),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_do_download_stats(self, session_id, pkgkeys):

        release_string = '--N/A--'
        rel_file = etpConst['systemreleasefile']
        if os.path.isfile(rel_file) and os.access(rel_file,os.R_OK):
            with open(rel_file,"r") as f:
                release_string = f.read(512)

        hw_hash = self.SystemSettings['hw_hash']
        if not hw_hash:
            hw_hash = ''

        mydict = {
            'branch': self.SystemSettings['repositories']['branch'],
            'release_string': release_string,
            'hw_hash': hw_hash,
            'pkgkeys': ' '.join(pkgkeys),
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s" % (
            session_id,
            'ugc:do_download_stats',
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_downloads(self, session_id, pkgkey):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:get_downloads',
            pkgkey,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_alldownloads(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'ugc:get_alldownloads',
        )

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        rc = self.do_generic_handler(cmd, session_id, compression = compression)

        # disable compression
        self.set_gzip_compression(session_id, False)

        return rc

    def ugc_do_vote(self, session_id, pkgkey, vote):

        cmd = "%s %s %s %s" % (
            session_id,
            'ugc:do_vote',
            pkgkey,
            vote,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_vote(self, session_id, pkgkey):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:get_vote',
            pkgkey,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_allvotes(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'ugc:get_allvotes',
        )

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        rc = self.do_generic_handler(cmd, session_id, compression = compression)

        # disable compression
        self.set_gzip_compression(session_id, False)

        return rc

    def ugc_add_comment(self, session_id, pkgkey, comment, title, keywords):

        mydict = {
            'comment': comment,
            'title': title,
            'keywords': keywords,
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s %s" % (
            session_id,
            'ugc:add_comment',
            pkgkey,
            xml_string,
        )

        return self.do_generic_handler(cmd, session_id)

    def ugc_edit_comment(self, session_id, iddoc, new_comment, new_title, new_keywords):

        mydict = {
            'comment': new_comment,
            'title': new_title,
            'keywords': new_keywords,
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s %s" % (
            session_id,
            'ugc:edit_comment',
            iddoc,
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_remove_comment(self, session_id, iddoc):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:remove_comment',
            iddoc,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_remove_image(self, session_id, iddoc):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:remove_image',
            iddoc,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_remove_file(self, session_id, iddoc):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:remove_file',
            iddoc,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_remove_youtube_video(self, session_id, iddoc):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:remove_youtube_video',
            iddoc,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_docs(self, session_id, pkgkey):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:get_alldocs',
            pkgkey,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_textdocs(self, session_id, pkgkey):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:get_textdocs',
            pkgkey,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_textdocs_by_identifiers(self, session_id, identifiers):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:get_textdocs_by_identifiers',
            ' '.join([str(x) for x in identifiers]),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_documents_by_identifiers(self, session_id, identifiers):

        cmd = "%s %s %s" % (
            session_id,
            'ugc:get_documents_by_identifiers',
            ' '.join([str(x) for x in identifiers]),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_send_file_stream(self, session_id, file_path):

        if not (os.path.isfile(file_path) and os.access(file_path,os.R_OK)):
            return False,False,'cannot read file_path'

        import zlib
        # enable stream
        cmd = "%s %s %s on" % (
            session_id,
            'session_config',
            'stream',
        )
        status, msg = self.do_generic_handler(cmd, session_id)
        if not status:
            return False,status,msg

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        # start streamer
        stream_status = True
        stream_msg = 'ok'
        f = open(file_path,"rb")
        chunk = f.read(8192)
        base_path = os.path.basename(file_path)
        transferred = len(chunk)
        max_size = self.entropyTools.get_file_size(file_path)
        while chunk:

            if (not self.Service.quiet) or self.Service.show_progress:
                self.Output.updateProgress(
                    "%s, %s: %s" % (
                        blue(_("User Generated Content")),
                        darkgreen(_("sending file")),
                        darkred(base_path),
                    ),
                    importance = 1,
                    type = "info",
                    header = brown(" @@ "),
                    back = True,
                    count = (transferred,max_size,),
                    percent = True
                )

            chunk = zlib.compress(chunk, 7) # compression level 1-9
            cmd = "%s %s %s" % (
                session_id,
                'stream',
                chunk,
            )
            status, msg = self.do_generic_handler(cmd, session_id, compression = compression)
            if not status:
                stream_status = status
                stream_msg = msg
                break
            chunk = f.read(8192)
            transferred += len(chunk)

        f.close()

        # disable compression
        self.set_gzip_compression(session_id, False)

        # disable config
        cmd = "%s %s %s off" % (
            session_id,
            'session_config',
            'stream',
        )
        status, msg = self.do_generic_handler(cmd, session_id)
        if not status:
            return False,status,msg

        return True,stream_status,stream_msg

    def ugc_send_file(self, session_id, pkgkey, file_path, doc_type, title, description, keywords):

        status, rem_status, err_msg = self.ugc_send_file_stream(session_id, file_path)
        if not (status and rem_status):
            return False,err_msg

        mydict = {
            'doc_type': str(doc_type),
            'title': title,
            'description': description,
            'keywords': keywords,
            'file_name': os.path.join(pkgkey,os.path.basename(file_path)),
            'real_filename': os.path.basename(file_path),
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s %s" % (
            session_id,
            'ugc:register_stream',
            pkgkey,
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def report_error(self, session_id, error_data):

        xml_string = self.entropyTools.xml_from_dict(error_data)

        cmd = "%s %s %s" % (
            session_id,
            'ugc:report_error',
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)
