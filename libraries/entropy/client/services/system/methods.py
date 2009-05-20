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
from entropy.i18n import _

class BaseMixin:

    def __init__(self, SystemManagerClientInstance):
        self.Manager = SystemManagerClientInstance
        self.available_commands = {
            'get_available_commands': {
                'desc': _("Get a list of remotely available commands"),
                'params': [],
                'call': self.get_available_commands,
                'private': True,
            },
            'get_queue': {
                'desc': _("Get current queue content"),
                'params': [
                    ('extended',bool,_('Extended results'),False,)
                ],
                'call': self.get_queue,
                'private': True,
            },
            'get_queue_item_by_id': {
                'desc': _("Get queue item using its queue unique identifier"),
                'params': [('queue_id',int,_('Queue Identifier'),True,)],
                'call': self.get_queue_item_by_id,
                'private': True,
            },
            'get_queue_id_stdout': {
                'desc': _("Get queue stdout/stderr using its queue unique identifier"),
                'params': [('queue_id',int,_('Queue Identifier'),True,)],
                'call': self.get_queue_id_stdout,
                'private': True,
            },
            'get_queue_id_stdout': {
                'desc': _("Get queued command result using its queue unique identifier"),
                'params': [('queue_id',int,_('Queue Identifier'),True,)],
                'call': self.get_queue_id_result,
                'private': True,
            },
            'remove_queue_ids': {
                'desc': _("Remove queued commands using their queue unique identifiers"),
                'params': [('queue_ids',list,_('Queue Identifiers'),True,)],
                'call': self.remove_queue_ids,
                'private': True,
            },
            'pause_queue': {
                'desc': _("Toggle queue pause (True/False)"),
                'params': [('do_pause',bool,_('Pause or not'),True,)],
                'call': self.pause_queue,
                'private': True,
            },
            'kill_processing_queue_id': {
                'desc': _("Kill a running process through its queue id"),
                'params': [('queue_id',int,_('Queue Identifier'),True,)],
                'call': self.kill_processing_queue_id,
                'private': True,
            },
            'swap_items_in_queue': {
                'desc': _("Swap items in queue using their queue ids"),
                'params': [
                    ('queue_id1',int,_('Queue Identifier'),True,),
                    ('queue_id2',int,_('Queue Identifier'),True,)
                ],
                'call': self.swap_items_in_queue,
                'private': True,
            },
            'get_pinboard_data': {
                'desc': _("Get pinboard content"),
                'params': [],
                'call': self.get_pinboard_data,
                'private': True,
            },
            'add_to_pinboard': {
                'desc': _("Add item to pinboard"),
                'params': [
                    ('note',basestring,_('Note'),True,),
                    ('extended_text',basestring,_('Extended text'),True,)
                ],
                'call': self.add_to_pinboard,
                'private': True,
            },
            'remove_from_pinboard': {
                'desc': _("Remove item from pinboard"),
                'params': [('pinboard_ids',list,_('Pinboard identifiers'),True,)],
                'call': self.remove_from_pinboard,
                'private': True,
            },
            'set_pinboard_items_done': {
                'desc': _("Set pinboard items status (done/not done)"),
                'params': [
                    ('pinboard_ids',list,_('Pinboard identifiers'),True,),
                    ('done_status',bool,_('Done status'),True,),
                ],
                'call': self.set_pinboard_items_done,
                'private': True,
            },
            'write_to_running_command_pipe': {
                'desc': _("Write to a remote running command stdin"),
                'params': [
                    ('queue_id',int,_('Queue Identifier'),True,),
                    ('write_to_stdout',bool,_('Write to stdout?'),True,),
                    ('txt',basestring,_('Text'),True,),
                ],
                'call': self.write_to_running_command_pipe,
                'private': True,
            },
        }

    def get_available_commands(self):
        return self.Manager.do_cmd(False, "available_commands", [], {})

    def get_queue(self, extended = False):
        return self.Manager.do_cmd(True, "get_queue", [extended], {})

    def get_queue_item_by_id(self, queue_id):
        return self.Manager.do_cmd(True, "get_queue_item_by_id", [queue_id], {})

    def get_queue_id_stdout(self, queue_id, last_bytes = 0):
        return self.Manager.do_cmd(True, "get_queue_id_stdout", [queue_id, last_bytes], {})

    def get_queue_id_result(self, queue_id):
        return self.Manager.do_cmd(True, "get_queue_id_result", [queue_id], {})

    def remove_queue_ids(self, queue_ids):
        return self.Manager.do_cmd(True, "remove_queue_ids", [queue_ids], {})

    def pause_queue(self, do_queue):
        return self.Manager.do_cmd(True, "pause_queue", [do_queue], {})

    def kill_processing_queue_id(self, queue_id):
        return self.Manager.do_cmd(True, "kill_processing_queue_id", [queue_id], {})

    def swap_items_in_queue(self, queue_id1, queue_id2):
        return self.Manager.do_cmd(True, "swap_items_in_queue", [queue_id1,queue_id2], {})

    def get_pinboard_data(self):
        return self.Manager.do_cmd(True, "get_pinboard_data", [], {})

    def add_to_pinboard(self, note, extended_text):
        return self.Manager.do_cmd(True, "add_to_pinboard", [note,extended_text], {})

    def remove_from_pinboard(self, pinboard_ids):
        return self.Manager.do_cmd(True, "remove_from_pinboard", [pinboard_ids], {})

    def set_pinboard_items_done(self, pinboard_ids, done_status):
        return self.Manager.do_cmd(True, "set_pinboard_items_done", [pinboard_ids,done_status], {})

    def write_to_running_command_pipe(self, queue_id, write_to_stdout, txt):
        return self.Manager.do_cmd(True, "write_to_running_command_pipe", [queue_id, write_to_stdout, txt], {})


class Repository(BaseMixin):

    def __init__(self, *args, **kwargs):
        BaseMixin.__init__(self, *args, **kwargs)
        self.available_commands.update({
            'sync_spm': {
                'desc': _("Update Spm Repository (emerge --sync)"),
                'params': [],
                'call': self.sync_spm,
                'private': False,
            },
            'compile_atoms': {
                'desc': _("Compile specified atoms with specified parameters"),
                'params': [
                    ('atoms',list,_('Atoms'),True,),
                    ('pretend',bool,_('Pretend'),False,),
                    ('oneshot',bool,_('Oneshot'),False,),
                    ('verbose',bool,_('Verbose'),False,),
                    ('nocolor',bool,_('No color'),False,),
                    ('fetchonly',bool,_('Fetch only'),False,),
                    ('buildonly',bool,_('Build only'),False,),
                    ('nodeps',bool,_('No dependencies'),False,),
                    ('custom_use',basestring,_('Custom USE'),False,),
                    ('ldflags',basestring,_('Custom LDFLAGS'),False,),
                    ('cflags',basestring,_('Custom CFLAGS'),False,),
                ],
                'call': self.compile_atoms,
                'private': False,
            },
            'spm_remove_atoms': {
                'desc': _("Remove specified atoms with specified parameters"),
                'params': [
                    ('atoms',list,_('Atoms'),True,),
                    ('pretend',bool,_('Pretend'),False,),
                    ('verbose',bool,_('Verbose'),False,),
                    ('nocolor',bool,_('No color'),False,),
                ],
                'call': self.spm_remove_atoms,
                'private': False,
            },
            'get_spm_categories_updates': {
                'desc': _("Get SPM updates for the specified categories"),
                'params': [('categories',list,_('Categories'),True,)],
                'call': self.get_spm_categories_updates,
                'private': False,
            },
            'get_spm_categories_installed': {
                'desc': _("Get SPM installed packages for the specified categories"),
                'params': [('categories',list,_('Categories'),True,)],
                'call': self.get_spm_categories_installed,
                'private': False,
            },
            'enable_uses_for_atoms': {
                'desc': _("Enable USE flags for the specified atoms"),
                'params': [
                    ('atoms',list,_('Atoms'),True,),
                    ('useflags',list,_('USE flags'),True,)
                ],
                'call': self.enable_uses_for_atoms,
                'private': False,
            },
            'disable_uses_for_atoms': {
                'desc': _("Disable USE flags for the specified atoms"),
                'params': [
                    ('atoms',list,_('Atoms'),True,),
                    ('useflags',list,_('USE flags'),True,)
                ],
                'call': self.disable_uses_for_atoms,
                'private': False,
            },
            'get_spm_atoms_info': {
                'desc': _("Get info for the specified atoms"),
                'params': [('atoms',list,_('Atoms'),True,)],
                'call': self.get_spm_atoms_info,
                'private': False,
            },
            'run_spm_info': {
                'desc': _("Run SPM info command"),
                'params': [],
                'call': self.run_spm_info,
                'private': False,
            },
            'run_custom_shell_command': {
                'desc': _("Run custom shell command"),
                'params': [
                    ('command',basestring,_('Command'),True,)
                ],
                'call': self.run_custom_shell_command,
                'private': False,
            },
            'get_spm_glsa_data': {
                'desc': _("Get Spm security updates information"),
                'params': [
                    ('list_type',basestring,_('List type (affected,new,all)'),True,)
                ],
                'call': self.get_spm_glsa_data,
                'private': False,
            },
            'get_available_repositories': {
                'desc': _("Get information about available Entropy repositories"),
                'params': [],
                'call': self.get_available_repositories,
                'private': False,
            },
            'set_default_repository': {
                'desc': _("Set default Entropy Server repository"),
                'params': [
                    ('repoid',basestring,_('Repository Identifier'),True,)
                ],
                'call': self.set_default_repository,
                'private': False,
            },
            'get_available_entropy_packages': {
                'desc': _("Get available packages inside the specified repository"),
                'params': [
                    ('repoid',basestring,_('Repository Identifier'),True,)
                ],
                'call': self.get_available_entropy_packages,
                'private': False,
            },
            'get_entropy_idpackage_information': {
                'desc': _("Get idpackage metadata using its idpackage in the specified repository"),
                'params': [
                    ('idpackage',int,_('Package Identifier'),True,),
                    ('repoid',basestring,_('Repository Identifier'),True,)
                ],
                'call': self.get_entropy_idpackage_information,
                'private': False,
            },
            'remove_entropy_packages': {
                'desc': _("Remove the specified Entropy package matches (idpackage,repoid)"),
                'params': [
                    ('matched_atoms',list,_('Matched atoms'),True,)
                ],
                'call': self.remove_entropy_packages,
                'private': False,
            },
            'search_entropy_packages': {
                'desc': _("Search Entropy packages using a defined set of search types in the specified repository"),
                'params': [
                    ('search_type',basestring,_('Search type'),True,),
                    ('search_string',basestring,_('Search string'),True,),
                    ('repoid',basestring,_('Repository Identifier'),True,)
                ],
                'call': self.search_entropy_packages,
                'private': False,
            },
            'move_entropy_packages_to_repository': {
                'desc': _("Move or copy a package from a repository to another"),
                'params': [
                    ('idpackages',list,_('Package identifiers'),True,),
                    ('from_repo',basestring,_('From repository'),True,),
                    ('to_repo',basestring,_('To repository'),True,),
                    ('do_copy',bool,_('Copy instead of move?'),False,)
                ],
                'call': self.search_entropy_packages,
                'private': False,
            },
            'scan_entropy_packages_database_changes': {
                'desc': _("Scan Spm package changes and retrieve a list of action that should be run on the repositories"),
                'params': [],
                'call': self.scan_entropy_packages_database_changes,
                'private': False,
            },
            'run_entropy_database_updates': {
                'desc': _("Run Entropy database updates"),
                'params': [
                    ('to_add',list,_('Matches to add from Spm'),True,),
                    ('to_remove',list,_('Matches to remove from repository database'),True,),
                    ('to_inject',list,_('Matches to inject on repository database'),True,),
                ],
                'call': self.run_entropy_database_updates,
                'private': False,
            },
            'run_entropy_dependency_test': {
                'desc': _("Run Entropy dependency test"),
                'params': [],
                'call': self.run_entropy_dependency_test,
                'private': False,
            },
            'run_entropy_library_test': {
                'desc': _("Run Entropy library test"),
                'params': [],
                'call': self.run_entropy_library_test,
                'private': False,
            },
            'run_entropy_treeupdates': {
                'desc': _("Run Entropy tree updates"),
                'params': [
                    ('repoid',basestring,_('Repository Identifier'),True,),
                ],
                'call': self.run_entropy_treeupdates,
                'private': False,
            },
            'scan_entropy_mirror_updates': {
                'desc': _("Scan for Mirror updates and retrieve a list of action that should be run"),
                'params': [
                    ('repositories',list,_('list of repository identifiers'),True,),
                ],
                'call': self.scan_entropy_mirror_updates,
                'private': False,
            },
            'run_entropy_mirror_updates': {
                'desc': _("Run Mirror updates for the provided repositories and its data"),
                'params': [
                    ('repository_data',dict,_('composed repository data'),True,),
                ],
                'call': self.run_entropy_mirror_updates,
                'private': False,
            },
            'run_entropy_checksum_test': {
                'desc': _("Run Entropy packages digest verification test"),
                'params': [
                    ('repoid',basestring,_('Repository Identifier'),True,),
                    ('mode',basestring,_('Check mode'),False,),
                ],
                'call': self.run_entropy_mirror_updates,
                'private': False,
            },
            'get_notice_board': {
                'desc': _("Get repository notice board"),
                'params': [('repoid',basestring,_('Repository Identifier'),True,),],
                'call': self.get_notice_board,
                'private': False,
            },
            'remove_notice_board_entries': {
                'desc': _("Remove notice board entry"),
                'params': [
                    ('repoid',basestring,_('Repository Identifier'),True,),
                    ('entry_ids',list,_('Entry Identifiers'),True,),
                ],
                'call': self.remove_notice_board_entries,
                'private': False,
            },
            'add_notice_board_entry': {
                'desc': _("Add notice board entry"),
                'params': [
                    ('repoid',basestring,_('Repository Identifier'),True,),
                    ('title',basestring,_('Title'),True,),
                    ('notice_text',basestring,_('Text'),True,),
                    ('link',basestring,_('Notice link'),True,),
                ],
                'call': self.add_notice_board_entry,
                'private': False,
            },
        })

    def sync_spm(self):
        return self.Manager.do_cmd(True, "sync_spm", [], {})

    def compile_atoms(self, atoms, pretend = False, oneshot = False, verbose = True, nocolor = True, fetchonly = False, buildonly = False, nodeps = False, custom_use = '', ldflags = '', cflags = ''):
        return self.Manager.do_cmd(
            True,
            "compile_atoms",
            [atoms],
            {
                'pretend': pretend,
                'oneshot': oneshot,
                'verbose': verbose,
                'nocolor': nocolor,
                'fetchonly': fetchonly,
                'buildonly': buildonly,
                'nodeps': nodeps,
                'custom_use': custom_use,
                'ldflags': ldflags,
                'cflags': cflags,
            }
        )

    def spm_remove_atoms(self, atoms, pretend = True, verbose = True, nocolor = True):
        return self.Manager.do_cmd(
            True,
            "spm_remove_atoms",
            [atoms],
            {
                'pretend': pretend,
                'verbose': verbose,
                'nocolor': nocolor,
            }
        )

    def get_spm_categories_updates(self, categories):
        return self.Manager.do_cmd(True, "get_spm_categories_updates", [categories], {})

    def get_spm_categories_installed(self, categories):
        return self.Manager.do_cmd(True, "get_spm_categories_installed", [categories], {})

    def enable_uses_for_atoms(self, atoms, useflags):
        return self.Manager.do_cmd(True, "enable_uses_for_atoms", [atoms,useflags], {})

    def disable_uses_for_atoms(self, atoms, useflags):
        return self.Manager.do_cmd(True, "disable_uses_for_atoms", [atoms,useflags], {})

    def get_spm_atoms_info(self, atoms):
        return self.Manager.do_cmd(True, "get_spm_atoms_info", [atoms], {})

    def run_spm_info(self):
        return self.Manager.do_cmd(True, "run_spm_info", [], {})

    def run_custom_shell_command(self, command):
        return self.Manager.do_cmd(True, "run_custom_shell_command", [command], {})

    def get_spm_glsa_data(self, list_type = "affected"):
        return self.Manager.do_cmd(True, "get_spm_glsa_data", [list_type], {})

    def get_available_repositories(self):
        return self.Manager.do_cmd(True, "get_available_repositories", [], {})

    def set_default_repository(self, repoid):
        return self.Manager.do_cmd(True, "set_default_repository", [repoid], {})

    def get_available_entropy_packages(self, repoid):
        return self.Manager.do_cmd(True, "get_available_entropy_packages", [repoid], {})

    def get_entropy_idpackage_information(self, idpackage, repoid):
        return self.Manager.do_cmd(True, "get_entropy_idpackage_information", [idpackage,repoid], {})

    def remove_entropy_packages(self, matched_atoms):
        return self.Manager.do_cmd(True, "remove_entropy_packages", [matched_atoms], {})

    def search_entropy_packages(self, search_type, search_string, repoid):
        return self.Manager.do_cmd(True, "search_entropy_packages", [search_type,search_string,repoid], {})

    def move_entropy_packages_to_repository(self, idpackages, from_repo, to_repo, do_copy = False):
        return self.Manager.do_cmd(True, "move_entropy_packages_to_repository", [idpackages,from_repo,to_repo, do_copy], {})

    def scan_entropy_packages_database_changes(self):
        return self.Manager.do_cmd(True, "scan_entropy_packages_database_changes", [], {})

    def run_entropy_database_updates(self, to_add, to_remove, to_inject):
        return self.Manager.do_cmd(True, "run_entropy_database_updates", [to_add,to_remove,to_inject], {})

    def run_entropy_dependency_test(self):
        return self.Manager.do_cmd(True, "run_entropy_dependency_test", [], {})

    def run_entropy_library_test(self):
        return self.Manager.do_cmd(True, "run_entropy_library_test", [], {})

    def run_entropy_treeupdates(self, repoid):
        return self.Manager.do_cmd(True, "run_entropy_treeupdates", [repoid], {})

    def scan_entropy_mirror_updates(self, repositories):
        return self.Manager.do_cmd(True, "scan_entropy_mirror_updates", [repositories], {})

    def run_entropy_mirror_updates(self, repository_data):
        return self.Manager.do_cmd(True, "run_entropy_mirror_updates", [repository_data], {})

    def run_entropy_checksum_test(self, repoid, mode = "local"):
        return self.Manager.do_cmd(True, "run_entropy_checksum_test", [repoid, mode], {})

    def get_notice_board(self, repoid):
        return self.Manager.do_cmd(True, "get_notice_board", [repoid], {})

    def remove_notice_board_entries(self, repoid, entry_ids):
        return self.Manager.do_cmd(True, "remove_notice_board_entries", [repoid,entry_ids], {})

    def add_notice_board_entry(self, repoid, title, notice_text, link):
        return self.Manager.do_cmd(True, "add_notice_board_entry", [repoid,title,notice_text,link], {})
