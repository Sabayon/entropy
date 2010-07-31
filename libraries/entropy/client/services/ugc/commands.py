# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Client Services UGC Base Commands}.

"""

import os
from entropy.exceptions import SSLError
from entropy.const import etpConst, const_get_stringtype, const_debug_write, \
    const_convert_to_rawstring
from entropy.output import darkblue, bold, blue, darkgreen, darkred, brown
from entropy.i18n import _
from entropy.core.settings.base import SystemSettings
import entropy.tools
import entropy.dump

class Base:

    def __init__(self, OutputInterface, Service):

        if not hasattr(OutputInterface, 'output'):
            raise AttributeError(
                "OutputInterface does not have an output method")
        elif not hasattr(OutputInterface.output, '__call__'):
            raise AttributeError(
                "OutputInterface does not have an output method")

        from entropy.services.ugc.interfaces import Client as Cl
        if not isinstance(Service, Cl):
            raise AttributeError(
                "entropy.services.ugc.interfaces.Client needed")

        import socket, zlib, struct
        self.socket, self.zlib, self.struct = socket, zlib, struct
        self.Output = OutputInterface
        self.Service = Service
        self.output_header = ''
        self._settings = SystemSettings()
        self.standard_answers_map = {
            'all_fine': 0,
            'not_supported_remotely': 1,
            'service_temp_not_avail': 2,
            'command_failed': 3,
            'wrong_answer': 4,
        }


    def handle_standard_answer(self, data, repository = None, arch = None,
        product = None):

        do_skip = False
        answer_id = self.standard_answers_map['all_fine']

        # elaborate answer
        if data == None:
            mytxt = _("feature not supported remotely")
            self.Output.output(
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
                level = "error",
                header = self.output_header
            )
            do_skip = True
            answer_id = self.standard_answers_map['not_supported_remotely']
        elif not data:
            mytxt = _("service temporarily not available")
            self.Output.output(
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
                level = "error",
                header = self.output_header
            )
            do_skip = True
            answer_id = self.standard_answers_map['service_temp_not_avail']
        elif data == self.Service.answers['no']:
            # command failed
            mytxt = _("command failed")
            self.Output.output(
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
                level = "error",
                header = self.output_header
            )
            do_skip = True
            answer_id = self.standard_answers_map['command_failed']
        elif data != self.Service.answers['ok']:
            mytxt = _("received wrong answer")

            # do not spam terminal
            if isinstance(data, const_get_stringtype()):
                if len(data) > 10:
                    data = data[:10] + "[...]"

            self.Output.output(
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
                level = "error",
                header = self.output_header
            )
            do_skip = True
            answer_id = self.standard_answers_map['wrong_answer']

        return do_skip, answer_id

    def get_result(self, session):
        # get the information
        cmd = "%s rc" % (session,)
        self.Service.transmit(cmd)
        try:
            data = self.Service.receive()
            return data
        except Exception:
            entropy.tools.print_traceback()
            return None

    def convert_stream_to_object(self, data, gzipped, repository = None,
        arch = None, product = None):

        # unstream object
        error = False
        try:
            data = self.Service.stream_to_object(data, gzipped)
        except (EOFError, IOError, self.zlib.error, entropy.dump.pickle.UnpicklingError,):
            const_debug_write(__name__, entropy.tools.get_traceback())
            mytxt = _("cannot convert stream into object")
            self.Output.output(
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
                level = "error",
                header = self.output_header
            )
            data = None
            error = True
        return data, error

    def retrieve_command_answer(self, cmd, session_id, repository = None,
        arch = None, product = None, compression = False):

        tries = 3
        lasterr = None
        while True:

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

            skip, answer_id = self.handle_standard_answer(data, repository,
                arch, product)
            if skip:
                if tries <= 0:
                    const_debug_write(__name__,
                        darkred("skipping command, NOT reconnecting"))
                else:
                    const_debug_write(__name__,
                        darkred("skipping command, reconnect+retry!"))
                const_debug_write(__name__, str(answer_id))
                # reconnect host and retry
                self.Service.reconnect_socket()
                continue

            data = self.get_result(session_id)
            if data == None:
                lasterr = None
                continue
            elif not data:
                lasterr = False
                continue

            objdata, error = self.convert_stream_to_object(data, compression,
                repository, arch, product)
            if not error:
                return objdata

    def do_generic_handler(self, cmd, session_id, tries = 10, compression = False):

        self.Service.check_socket_connection()

        while True:
            try:
                result = self.retrieve_command_answer(cmd, session_id,
                    compression = compression)
                if result == None:
                    return False, 'command not supported' # untranslated on purpose
                return result
            except (self.socket.error, self.struct.error,):
                self.Service.reconnect_socket()
                tries -= 1
                if tries < 1:
                    raise

    def set_gzip_compression(self, session, do):
        self.Service.check_socket_connection()
        cmd = "%s %s %s %s zlib" % (
            const_convert_to_rawstring(session),
            const_convert_to_rawstring('session_config'),
            const_convert_to_rawstring('compression'), 
            const_convert_to_rawstring(do),
        )
        self.Service.transmit(cmd)
        data = self.Service.receive()
        if data == self.Service.answers['ok']:
            return True
        return False

    def service_login(self, username, password, session_id):

        cmd = "%s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('login'),
            const_convert_to_rawstring(username),
            const_convert_to_rawstring(password),
        )
        return self.do_generic_handler(cmd, session_id)

    def service_logout(self, username, session_id):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('logout'),
            const_convert_to_rawstring(username),
        )
        return self.do_generic_handler(cmd, session_id)

    def get_logged_user_data(self, session_id):

        cmd = "%s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('user_data'),
        )
        return self.do_generic_handler(cmd, session_id)

    def is_user(self, session_id):

        cmd = "%s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('is_user'),
        )
        return self.do_generic_handler(cmd, session_id)

    def is_developer(self, session_id):

        cmd = "%s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('is_developer'),
        )
        return self.do_generic_handler(cmd, session_id)

    def is_moderator(self, session_id):

        cmd = "%s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('is_moderator'),
        )
        return self.do_generic_handler(cmd, session_id)

    def is_administrator(self, session_id):

        cmd = "%s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('is_administrator'),
        )
        return self.do_generic_handler(cmd, session_id)

    def available_commands(self, session_id):

        cmd = "%s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('available_commands'),
        )
        return self.do_generic_handler(cmd, session_id)


class Client(Base):

    def __init__(self, EntropyInterface, ServiceInterface):
        Base.__init__(self, EntropyInterface, ServiceInterface)

    def differential_packages_comparison(self, session_id, idpackages,
        repository, arch, product):

        myidlist = const_convert_to_rawstring(
            ' '.join([str(x) for x in idpackages]))
        cmd = "%s %s %s %s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('repository_server:dbdiff'),
            const_convert_to_rawstring(repository),
            const_convert_to_rawstring(arch),
            const_convert_to_rawstring(product),
            const_convert_to_rawstring(
                self._settings['repositories']['branch']),
            myidlist,
        )

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        data = self.do_generic_handler(cmd, session_id, tries = 5,
            compression = compression)

        # disable compression
        self.set_gzip_compression(session_id, False)

        return data

    def get_repository_treeupdates(self, session_id, repository, arch, product):

        cmd = "%s %s %s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('repository_server:treeupdates'),
            const_convert_to_rawstring(repository),
            const_convert_to_rawstring(arch),
            const_convert_to_rawstring(product),
            const_convert_to_rawstring(
                self._settings['repositories']['branch']),
        )
        return self.do_generic_handler(cmd, session_id, tries = 5)

    def get_package_sets(self, session_id, repository, arch, product):

        cmd = "%s %s %s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('repository_server:get_package_sets'),
            const_convert_to_rawstring(repository),
            const_convert_to_rawstring(arch),
            const_convert_to_rawstring(product),
            const_convert_to_rawstring(
                self._settings['repositories']['branch']),
        )
        return self.do_generic_handler(cmd, session_id, tries = 5)

    def get_repository_metadata(self, session_id, repository, arch, product):

        cmd = "%s %s %s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring(
                'repository_server:get_repository_metadata'),
            const_convert_to_rawstring(repository),
            const_convert_to_rawstring(arch),
            const_convert_to_rawstring(product),
            const_convert_to_rawstring(
                self._settings['repositories']['branch']),
        )
        return self.do_generic_handler(cmd, session_id, tries = 5)

    def get_strict_package_information(self, session_id, idpackages,
        repository, arch, product):

        cmd = "%s %s %s %s %s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('repository_server:pkginfo_strict'),
            True,
            const_convert_to_rawstring(repository),
            const_convert_to_rawstring(arch),
            const_convert_to_rawstring(product),
            const_convert_to_rawstring(
                self._settings['repositories']['branch']),
            const_convert_to_rawstring(' '.join([str(x) for x in idpackages])),
        )

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        data = self.do_generic_handler(cmd, session_id, compression = compression)

        # disable compression
        self.set_gzip_compression(session_id, False)

        return data

    def ugc_do_download_stats(self, session_id, package_names):

        sub_lists = entropy.tools.split_indexable_into_chunks(
            package_names, 100)

        last_srv_rc_data = None
        for pkgkeys in sub_lists:

            release_string = '--N/A--'
            rel_file = etpConst['systemreleasefile']
            if os.path.isfile(rel_file) and os.access(rel_file, os.R_OK):
                with open(rel_file, "r") as f:
                    release_string = f.read(512)

            hw_hash = self._settings['hw_hash']
            if not hw_hash:
                hw_hash = ''

            mydict = {
                'branch': self._settings['repositories']['branch'],
                'release_string': release_string,
                'hw_hash': hw_hash,
                'pkgkeys': ' '.join(pkgkeys),
            }
            xml_string = entropy.tools.xml_from_dict(mydict)

            cmd = "%s %s %s" % (
                const_convert_to_rawstring(session_id),
                const_convert_to_rawstring('ugc:do_download_stats'),
                const_convert_to_rawstring(xml_string),
            )
            last_srv_rc_data = self.do_generic_handler(cmd, session_id)
            if not isinstance(last_srv_rc_data, tuple):
                return last_srv_rc_data
            elif last_srv_rc_data[0] != True:
                return last_srv_rc_data
        return last_srv_rc_data

    def ugc_get_downloads(self, session_id, pkgkey):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:get_downloads'),
            pkgkey,
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_alldownloads(self, session_id):

        cmd = "%s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:get_alldownloads'),
        )

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        rc = self.do_generic_handler(cmd, session_id, compression = compression)

        # disable compression
        self.set_gzip_compression(session_id, False)

        return rc

    def ugc_do_vote(self, session_id, pkgkey, vote):

        cmd = "%s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:do_vote'),
            const_convert_to_rawstring(pkgkey),
            const_convert_to_rawstring(vote),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_vote(self, session_id, pkgkey):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:get_vote'),
            const_convert_to_rawstring(pkgkey),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_allvotes(self, session_id):

        cmd = "%s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:get_allvotes'),
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
        xml_string = entropy.tools.xml_from_dict(mydict)

        cmd = "%s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:add_comment'),
            const_convert_to_rawstring(pkgkey),
            const_convert_to_rawstring(xml_string),
        )

        return self.do_generic_handler(cmd, session_id)

    def ugc_edit_comment(self, session_id, iddoc, new_comment, new_title, new_keywords):

        mydict = {
            'comment': new_comment,
            'title': new_title,
            'keywords': new_keywords,
        }
        xml_string = entropy.tools.xml_from_dict(mydict)

        cmd = "%s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:edit_comment'),
            const_convert_to_rawstring(iddoc),
            const_convert_to_rawstring(xml_string),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_remove_comment(self, session_id, iddoc):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:remove_comment'),
            const_convert_to_rawstring(iddoc),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_remove_image(self, session_id, iddoc):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:remove_image'),
            const_convert_to_rawstring(iddoc),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_remove_file(self, session_id, iddoc):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:remove_file'),
            const_convert_to_rawstring(iddoc),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_remove_youtube_video(self, session_id, iddoc):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:remove_youtube_video'),
            const_convert_to_rawstring(iddoc),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_docs(self, session_id, pkgkey):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:get_alldocs'),
            const_convert_to_rawstring(pkgkey),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_textdocs(self, session_id, pkgkey):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:get_textdocs'),
            const_convert_to_rawstring(pkgkey),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_textdocs_by_identifiers(self, session_id, identifiers):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:get_textdocs_by_identifiers'),
            const_convert_to_rawstring(' '.join([str(x) for x in identifiers])),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_get_documents_by_identifiers(self, session_id, identifiers):

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:get_documents_by_identifiers'),
            const_convert_to_rawstring(' '.join([str(x) for x in identifiers])),
        )
        return self.do_generic_handler(cmd, session_id)

    def ugc_send_file_stream(self, session_id, file_path):

        if not (os.path.isfile(file_path) and os.access(file_path, os.R_OK)):
            return False, False, 'cannot read file_path'

        import zlib
        # enable stream
        cmd = "%s %s %s on" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('session_config'),
            const_convert_to_rawstring('stream'),
        )
        status, msg = self.do_generic_handler(cmd, session_id)
        if not status:
            return False, status, msg

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        # start streamer
        stream_status = True
        stream_msg = 'ok'
        f = open(file_path, "rb")
        chunk = f.read(8192)
        base_path = os.path.basename(file_path)
        transferred = len(chunk)
        max_size = entropy.tools.get_file_size(file_path)
        while chunk:

            if (not self.Service.quiet) or self.Service.show_progress:
                self.Output.output(
                    "%s, %s: %s" % (
                        blue(_("User Generated Content")),
                        darkgreen(_("sending file")),
                        darkred(base_path),
                    ),
                    importance = 1,
                    level = "info",
                    header = brown(" @@ "),
                    back = True,
                    count = (transferred, max_size,),
                    percent = True
                )

            chunk = zlib.compress(chunk, 7) # compression level 1-9
            cmd = "%s %s %s" % (
                const_convert_to_rawstring(session_id),
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
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('session_config'),
            const_convert_to_rawstring('stream'),
        )
        status, msg = self.do_generic_handler(cmd, session_id)
        if not status:
            return False, status, msg

        return True, stream_status, stream_msg

    def ugc_send_file(self, session_id, pkgkey, file_path, doc_type, title,
        description, keywords):

        status, rem_status, err_msg = self.ugc_send_file_stream(session_id, file_path)
        if not (status and rem_status):
            return False, err_msg

        mydict = {
            'doc_type': str(doc_type),
            'title': title,
            'description': description,
            'keywords': keywords,
            'file_name': os.path.join(pkgkey, os.path.basename(file_path)),
            'real_filename': os.path.basename(file_path),
        }
        xml_string = entropy.tools.xml_from_dict(mydict)

        cmd = "%s %s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:register_stream'),
            pkgkey,
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def report_error(self, session_id, error_data):

        import zlib
        xml_string = entropy.tools.xml_from_dict_extended(error_data)
        xml_comp_string = zlib.compress(xml_string)

        cmd = "%s %s %s" % (
            const_convert_to_rawstring(session_id),
            const_convert_to_rawstring('ugc:report_error'),
            const_convert_to_rawstring(xml_comp_string),
        )

        return self.do_generic_handler(cmd, session_id)
