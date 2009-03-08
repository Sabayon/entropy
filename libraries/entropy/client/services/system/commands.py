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

from entropy.client.services.ugc.commands import Base


class Client(Base):

    import entropyTools
    def __init__(self, *args, **kwargs):
        Base.__init__(self, *args, **kwargs)

    def service_login(self, username, password, session_id):

        cmd = "%s %s %s %s %s" % (
            session_id,
            'login',
            username,
            'plain',
            password,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_queue(self, session_id, extended):

        cmd = "%s %s %s" % (
            session_id,
            'systemsrv:get_queue',
            extended,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_queue_item_by_id(self, session_id, queue_id):

        cmd = "%s %s %d" % (
            session_id,
            'systemsrv:get_queue_item_by_id',
            queue_id,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_queue_id_stdout(self, session_id, queue_id, last_bytes):

        cmd = "%s %s %d %d" % (
            session_id,
            'systemsrv:get_queue_id_stdout',
            queue_id,
            last_bytes,
        )

        # enable zlib compression
        compression = self.set_gzip_compression(session_id, True)

        rc = self.do_generic_handler(cmd, session_id, compression = compression)

        # disable compression
        self.set_gzip_compression(session_id, False)

        return rc

    def get_queue_id_result(self, session_id, queue_id):

        cmd = "%s %s %d" % (
            session_id,
            'systemsrv:get_queue_id_result',
            queue_id,
        )
        return self.do_generic_handler(cmd, session_id)

    def remove_queue_ids(self, session_id, queue_ids):

        cmd = "%s %s %s" % (
            session_id,
            'systemsrv:remove_queue_ids',
            ' '.join([str(x) for x in queue_ids]),
        )
        return self.do_generic_handler(cmd, session_id)

    def pause_queue(self, session_id, do_pause):

        cmd = "%s %s %s" % (
            session_id,
            'systemsrv:pause_queue',
            do_pause,
        )
        return self.do_generic_handler(cmd, session_id)

    def kill_processing_queue_id(self, session_id, queue_id):

        cmd = "%s %s %s" % (
            session_id,
            'systemsrv:kill_processing_queue_id',
            queue_id,
        )
        return self.do_generic_handler(cmd, session_id)

    def swap_items_in_queue(self, session_id, queue_id1, queue_id2):

        cmd = "%s %s %d %d" % (
            session_id,
            'systemsrv:swap_items_in_queue',
            queue_id1,
            queue_id2,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_pinboard_data(self, session_id):
        cmd = "%s %s" % (
            session_id,
            'systemsrv:get_pinboard_data',
        )
        return self.do_generic_handler(cmd, session_id)

    def add_to_pinboard(self, session_id, note, extended_text):

        mydict = {
            'note': note,
            'extended_text': extended_text,
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s" % (
            session_id,
            'systemsrv:add_to_pinboard',
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def remove_from_pinboard(self, session_id, pinboard_ids):

        cmd = "%s %s %s" % (
            session_id,
            'systemsrv:remove_from_pinboard',
            ' '.join([str(x) for x in pinboard_ids]),
        )
        return self.do_generic_handler(cmd, session_id)

    def set_pinboard_items_done(self, session_id, pinboard_ids, status):
        cmd = "%s %s %s %s" % (
            session_id,
            'systemsrv:set_pinboard_items_done',
            ' '.join([str(x) for x in pinboard_ids]),
            status,
        )
        return self.do_generic_handler(cmd, session_id)

    def write_to_running_command_pipe(self, session_id, queue_id, write_to_stdout, txt):
        cmd = "%s %s %s %s %s" % (
            session_id,
            'systemsrv:write_to_running_command_pipe',
            queue_id,
            write_to_stdout,
            txt,
        )
        return self.do_generic_handler(cmd, session_id)

class Repository(Client):

    import dumpTools

    def sync_spm(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'srvrepo:sync_spm',
        )
        return self.do_generic_handler(cmd, session_id)

    def compile_atoms(self, session_id, atoms, pretend = False, oneshot = False,
            verbose = False, nocolor = True, fetchonly = False, buildonly = False,
            nodeps = False, custom_use = '', ldflags = '', cflags = ''):

        s_pretend = "0"
        s_oneshot = "0"
        s_verbose = "0"
        s_nocolor = "0"
        s_fetchonly = "0"
        s_buildonly = "0"
        s_nodeps = "0"
        if pretend: s_pretend = "1"
        if oneshot: s_oneshot = "1"
        if verbose: s_verbose = "1"
        if nocolor: s_nocolor = "1"
        if fetchonly: s_fetchonly = "1"
        if buildonly: s_buildonly = "1"
        if nodeps: s_nodeps = "1"
        mydict = {
            'atoms': ' '.join(atoms),
            'pretend': s_pretend,
            'oneshot': s_oneshot,
            'verbose': s_verbose,
            'nocolor': s_nocolor,
            'fetchonly': s_fetchonly,
            'buildonly': s_buildonly,
            'nodeps': s_nodeps,
            'custom_use': custom_use,
            'ldflags': ldflags,
            'cflags': cflags,
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:compile_atoms',
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def spm_remove_atoms(self, session_id, atoms, pretend = False, verbose = False, nocolor = True):

        s_pretend = "0"
        s_verbose = "0"
        s_nocolor = "0"
        if pretend: s_pretend = "1"
        if verbose: s_verbose = "1"
        if nocolor: s_nocolor = "1"
        mydict = {
            'atoms': ' '.join(atoms),
            'pretend': s_pretend,
            'verbose': s_verbose,
            'nocolor': s_nocolor,
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:spm_remove_atoms',
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_spm_categories_updates(self, session_id, categories):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:get_spm_categories_updates',
            ' '.join(categories),
        )
        return self.do_generic_handler(cmd, session_id)

    def get_spm_categories_installed(self, session_id, categories):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:get_spm_categories_installed',
            ' '.join(categories),
        )
        return self.do_generic_handler(cmd, session_id)

    def enable_uses_for_atoms(self, session_id, atoms, useflags):

        mydict = {
            'atoms': ' '.join(atoms),
            'useflags': ' '.join(useflags),
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:enable_uses_for_atoms',
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def disable_uses_for_atoms(self, session_id, atoms, useflags):

        mydict = {
            'atoms': ' '.join(atoms),
            'useflags': ' '.join(useflags),
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:disable_uses_for_atoms',
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_spm_atoms_info(self, session_id, atoms):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:get_spm_atoms_info',
            ' '.join(atoms),
        )
        return self.do_generic_handler(cmd, session_id)

    def run_spm_info(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'srvrepo:run_spm_info',
        )
        return self.do_generic_handler(cmd, session_id)

    def run_custom_shell_command(self, session_id, command):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:run_custom_shell_command',
            command,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_spm_glsa_data(self, session_id, list_type):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:get_spm_glsa_data',
            list_type,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_available_repositories(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'srvrepo:get_available_repositories',
        )
        return self.do_generic_handler(cmd, session_id)

    def set_default_repository(self, session_id, repoid):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:set_default_repository',
            repoid,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_available_entropy_packages(self, session_id, repoid):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:get_available_entropy_packages',
            repoid,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_entropy_idpackage_information(self, session_id, idpackage, repoid):

        cmd = "%s %s %d %s" % (
            session_id,
            'srvrepo:get_entropy_idpackage_information',
            idpackage,
            repoid,
        )
        return self.do_generic_handler(cmd, session_id)

    def remove_entropy_packages(self, session_id, matched_atoms):
        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:remove_entropy_packages',
            ','.join(["%s:%s" % (str(x[0]),str(x[1]),) for x in matched_atoms]), # 1:repoid,2:repoid
        )
        return self.do_generic_handler(cmd, session_id)

    def search_entropy_packages(self, session_id, search_type, search_string, repoid):

        cmd = "%s %s %s %s %s" % (
            session_id,
            'srvrepo:search_entropy_packages',
            repoid,
            search_type,
            search_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def move_entropy_packages_to_repository(self, session_id, idpackages, from_repo, to_repo, do_copy):

        cmd = "%s %s %s %s %s %s" % (
            session_id,
            'srvrepo:move_entropy_packages_to_repository',
            from_repo,
            to_repo,
            do_copy,
            ' '.join([str(x) for x in idpackages]),
        )
        return self.do_generic_handler(cmd, session_id)

    def scan_entropy_packages_database_changes(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'srvrepo:scan_entropy_packages_database_changes',
        )
        return self.do_generic_handler(cmd, session_id)

    def run_entropy_database_updates(self, session_id, to_add, to_remove, to_inject):

        cmd = "%s %s %s %s %s" % (
            session_id,
            'srvrepo:run_entropy_database_updates',
            ','.join(["%s:%s:%s" % (str(x[0]),str(x[1]),str(x[2]),) for x in to_add]),
            ','.join(["%s:%s" % (str(x[0]),str(x[1]),) for x in to_remove]),
            ','.join(["%s:%s" % (str(x[0]),str(x[1]),) for x in to_inject]),
        )
        return self.do_generic_handler(cmd, session_id)

    def run_entropy_dependency_test(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'srvrepo:run_entropy_dependency_test',
        )
        return self.do_generic_handler(cmd, session_id)

    def run_entropy_library_test(self, session_id):

        cmd = "%s %s" % (
            session_id,
            'srvrepo:run_entropy_library_test',
        )
        return self.do_generic_handler(cmd, session_id)

    def run_entropy_treeupdates(self, session_id, repoid):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:run_entropy_treeupdates',
            repoid,
        )
        return self.do_generic_handler(cmd, session_id)

    def scan_entropy_mirror_updates(self, session_id, repositories):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:scan_entropy_mirror_updates',
            ' '.join(repositories),
        )
        return self.do_generic_handler(cmd, session_id)

    def run_entropy_mirror_updates(self, session_id, repository_data):

        serialized_string = self.dumpTools.serialize_string(repository_data)
        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:run_entropy_mirror_updates',
            serialized_string,
        )
        return self.do_generic_handler(cmd, session_id)

    def run_entropy_checksum_test(self, session_id, repoid, mode):

        cmd = "%s %s %s %s" % (
            session_id,
            'srvrepo:run_entropy_checksum_test',
            repoid,
            mode,
        )
        return self.do_generic_handler(cmd, session_id)

    def get_notice_board(self, session_id, repoid):

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:get_notice_board',
            repoid,
        )
        return self.do_generic_handler(cmd, session_id)

    def remove_notice_board_entries(self, session_id, repoid, entry_ids):

        cmd = "%s %s %s %s" % (
            session_id,
            'srvrepo:remove_notice_board_entries',
            repoid,
             ' '.join([str(x) for x in entry_ids]),
        )
        return self.do_generic_handler(cmd, session_id)

    def add_notice_board_entry(self, session_id, repoid, title, notice_text, link):

        mydict = {
            'repoid': repoid,
            'title': title,
            'notice_text': notice_text,
            'link': link,
        }
        xml_string = self.entropyTools.xml_from_dict(mydict)

        cmd = "%s %s %s" % (
            session_id,
            'srvrepo:add_notice_board_entry',
            xml_string,
        )
        return self.do_generic_handler(cmd, session_id)
