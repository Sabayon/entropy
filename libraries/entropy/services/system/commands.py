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

import os
from entropy.services.skel import SocketCommands
from entropy.const import etpConst

class Base(SocketCommands):

    import entropy.tools as entropyTools
    def __init__(self, HostInterface):

        import copy
        self.copy = copy
        SocketCommands.__init__(self, HostInterface, inst_name = "systemsrv")
        self.raw_commands = [
            'systemsrv:add_to_pinboard',
            'systemsrv:write_to_running_command_pipe'
        ]

        self.valid_commands = {
            'systemsrv:get_queue':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_queue,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get current queue",
                'syntax': "<SESSION_ID> systemsrv:get_queue",
                'from': unicode(self),
            },
            'systemsrv:get_queue_item_by_id':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_queue_item_by_id,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get current queue item through its queue id",
                'syntax': "<SESSION_ID> systemsrv:get_queue_item_by_id <queue_id>",
                'from': unicode(self),
            },
            'systemsrv:get_queue_id_stdout':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_queue_id_stdout,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get current queue item stdout/stderr output",
                'syntax': "<SESSION_ID> systemsrv:get_queue_id_stdout <queue_id> <how many bytes (from tail)>",
                'from': unicode(self),
            },
            'systemsrv:get_queue_id_result':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_queue_id_result,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get current queue item result output",
                'syntax': "<SESSION_ID> systemsrv:get_queue_id_result <queue_id>",
                'from': unicode(self),
            },
            'systemsrv:remove_queue_ids':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_remove_queue_ids,
                'args': ["myargs"],
                'as_user': False,
                'desc': "remove queue items using their queue ids",
                'syntax': "<SESSION_ID> systemsrv:remove_queue_ids <queue_id 1> <queue_id 2> <...>",
                'from': unicode(self),
            },
            'systemsrv:pause_queue':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_pause_queue,
                'args': ["myargs"],
                'as_user': False,
                'desc': "toggle queue pause (understood?)",
                'syntax': "<SESSION_ID> systemsrv:pause_queue <True/False>",
                'from': unicode(self),
            },
            'systemsrv:kill_processing_queue_id':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_kill_processing_queue_id,
                'args': ["myargs"],
                'as_user': False,
                'desc': "kill a running process using its queue id",
                'syntax': "<SESSION_ID> systemsrv:kill_processing_queue_id <queue_id>",
                'from': unicode(self),
            },
            'systemsrv:swap_items_in_queue':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_swap_items_in_queue,
                'args': ["myargs"],
                'as_user': False,
                'desc': "swap items in queue to change their order",
                'syntax': "<SESSION_ID> systemsrv:swap_items_in_queue <queue_id1> <queue_id1>",
                'from': unicode(self),
            },
            'systemsrv:get_pinboard_data':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_pinboard_data,
                'args': [],
                'as_user': False,
                'desc': "get pinboard content",
                'syntax': "<SESSION_ID> systemsrv:get_pinboard_data",
                'from': unicode(self),
            },
            'systemsrv:add_to_pinboard':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_add_to_pinboard,
                'args': ["myargs"],
                'as_user': False,
                'desc': "add item to pinboard",
                'syntax': "<SESSION_ID> systemsrv:add_to_pinboard <xml string containing pinboard note and extended text>",
                'from': unicode(self),
            },
            'systemsrv:remove_from_pinboard':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_remove_from_pinboard,
                'args': ["myargs"],
                'as_user': False,
                'desc': "remove item from pinboard",
                'syntax': "<SESSION_ID> systemsrv:remove_from_pinboard <pinboard identifier 1> <pinboard identifier 2> <...>",
                'from': unicode(self),
            },
            'systemsrv:set_pinboard_items_done':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_set_pinboard_items_done,
                'args': ["myargs"],
                'as_user': False,
                'desc': "set pinboard items status using their pinboard identifiers",
                'syntax': "<SESSION_ID> systemsrv:set_pinboard_items_done <pinboard identifier 1> <pinboard identifier 2> <...> <status (True/False)>",
                'from': unicode(self),
            },
            'systemsrv:write_to_running_command_pipe':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_write_to_running_command_pipe,
                'args': ["myargs"],
                'as_user': False,
                'desc': "write text to stdin of a running command",
                'syntax': "<SESSION_ID> systemsrv:write_to_running_command_pipe <queue_id> <write stdout (True/False)> <txt ...>",
                'from': unicode(self),
            },
        }

    def docmd_get_queue(self, myargs):

        myqueue = self.copy.deepcopy(self.HostInterface.ManagerQueue)

        extended = False
        if myargs:
            extended = myargs[0]

        if not extended:
            for key in self.HostInterface.done_queue_keys:
                for queue_id in myqueue.get(key):
                    item = myqueue[key].get(queue_id)
                    if not item.has_key('extended_result'):
                        continue
                    item['extended_result'] = None

        return True, myqueue

    def docmd_get_queue_item_by_id(self, myargs):

        if not myargs:
            return False,'wrong arguments'
        queue_id = myargs[0]
        try:
            queue_id = int(queue_id)
        except ValueError:
            return False,'wrong argument: queue_id'

        item, key = self.HostInterface.get_item_by_queue_id(queue_id, copy = True)
        if item == None:
            return False,'wrong queue id'

        return True,item

    def docmd_get_queue_id_stdout(self, myargs):

        if len(myargs) < 1:
            return False,'wrong arguments'
        queue_id = myargs[0]
        bytes_from_tail = myargs[1]

        try:
            queue_id = int(queue_id)
        except ValueError:
            return False,'wrong argument: queue_id'
        try:
            bytes_from_tail = int(bytes_from_tail)
        except ValueError:
            return False,'wrong argument: lines from tail'

        item, key = self.HostInterface.get_item_by_queue_id(queue_id, copy = True)
        if item == None:
            return False,'wrong queue id'

        file_path = item['stdout']
        if not (os.path.isfile(file_path) and os.access(file_path,os.R_OK)):
            text = ''
        else:
            f = open(file_path,"r")
            f.seek(0,2)
            tell_me = f.tell()
            if bytes_from_tail < 1:
                bytes_from_tail = tell_me
            if bytes_from_tail > tell_me:
                bytes_from_tail = tell_me
            f.seek(-1*bytes_from_tail,2)
            text = f.read()
            f.close()

        return True,text

    def docmd_get_queue_id_result(self, myargs):

        if not myargs:
            return False,'wrong arguments'
        queue_id = myargs[0]
        try:
            queue_id = int(queue_id)
        except ValueError:
            return False,'wrong argument: queue_id'

        item, key = self.HostInterface.get_item_by_queue_id(queue_id, copy = True)
        if item == None:
            return False,'wrong queue id'

        if key not in self.HostInterface.done_queue_keys:
            return False,'process not completed yet'

        if not item.has_key('result'):
            return False,'result not available'

        ext_result = None
        if item.has_key('extended_result'):
            ext_result = self.HostInterface.load_queue_ext_rc(queue_id)

        return True,(item['result'],ext_result,)

    def docmd_remove_queue_ids(self, myargs):

        if not myargs:
            return False,'wrong arguments'

        valid_queue_ids = set()
        for queue_id in myargs:
            item, key = self.HostInterface.get_item_by_queue_id(queue_id, copy = True)
            if (item != None) and (key in self.HostInterface.removable_queue_keys):
                valid_queue_ids.add(queue_id)

        if not valid_queue_ids:
            return False,'no valid queue ids'

        # remove
        self.HostInterface.remove_from_queue(valid_queue_ids)

        return True,'ok'

    def docmd_pause_queue(self, myargs):

        if not myargs:
            return False,'wrong arguments'

        do = myargs[0]
        if do:
            self.HostInterface.pause_queue()
        else:
            self.HostInterface.play_queue()

        return self.HostInterface.ManagerQueue['pause'],'ok'

    def docmd_kill_processing_queue_id(self, myargs):

        if not myargs:
            return False,'wrong arguments'

        queue_id = myargs[0]
        self.HostInterface.kill_processing_queue_id(queue_id)
        return True,'ok'

    def docmd_swap_items_in_queue(self, myargs):

        if len(myargs) < 2:
            return False,'wrong arguments'

        queue_id1 = myargs[0]
        queue_id2 = myargs[1]
        status = self.HostInterface.swap_items_in_queue(queue_id1,queue_id2)
        if status:
            return True,'ok'
        return False,'not done'

    def docmd_get_pinboard_data(self):
        data = self.HostInterface.get_pinboard_data()
        return True,data.copy()

    def docmd_add_to_pinboard(self, myargs):

        if not myargs:
            return False,'wrong arguments'

        xml_string = ' '.join(myargs)
        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)

        if not (mydict.has_key('note') and mydict.has_key('extended_text')):
            return None,'wrong dict arguments, xml must have 2 items with attr value -> note, extended_text'
        note = mydict.get('note')
        extended_text = mydict.get('extended_text')

        self.HostInterface.add_to_pinboard(note, extended_text)
        return True,'ok'

    def docmd_remove_from_pinboard(self, myargs):

        if not myargs:
            return False,'wrong arguments'

        for pinboard_id in myargs:
            try:
                pinboard_id = int(pinboard_id)
            except ValueError:
                continue
            self.HostInterface.remove_from_pinboard(pinboard_id)
        return True,'ok'

    def docmd_set_pinboard_items_done(self, myargs):

        if len(myargs) < 2:
            return False,'wrong arguments'

        status = myargs[-1]
        pinboard_ids = myargs[:-1]

        for pinboard_id in pinboard_ids:
            try:
                pinboard_id = int(pinboard_id)
            except ValueError:
                continue
            self.HostInterface.set_pinboard_item_status(pinboard_id, status)
        return True,'ok'

    def docmd_write_to_running_command_pipe(self, myargs):

        if len(myargs) < 2:
            return False, 'wrong arguments'

        try:
            queue_id = int(myargs[0])
        except ValueError:
            return False,'invalid queue id'

        try:
            write_stdout = bool(myargs[1])
        except ValueError:
            write_stdout = False

        txt = ' '.join(myargs[2:])+'\n'
        item, key = self.HostInterface.get_item_by_queue_id(queue_id, copy = True)
        if key not in self.HostInterface.processing_queue_keys:
            return False,'not running'
        mypipe = self.HostInterface.ManagerQueueStdInOut.get(queue_id)
        if mypipe == None:
            return False,'pipe not available'
        try:
            w_fd = mypipe[1]
        except (IndexError, ValueError,):
            return False,'pipe vanished'
        if not isinstance(w_fd,int):
            return False,'stdout fd not an int'

        if write_stdout:
            stdout = open(item['stdout'],"a+")
        try:
            os.write(w_fd,txt)
            if write_stdout:
                stdout.write(txt)
        except OSError, e:
            return False,'OSError: %s' % (e,)
        except IOError, e:
            return False,'IOError: %s' % (e,)
        finally:
            if write_stdout:
                stdout.flush()
                stdout.close()

        return True,'ok'

class Repository(SocketCommands):

    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    def __init__(self, HostInterface):

        SocketCommands.__init__(self, HostInterface, inst_name = "srvrepo")
        self.raw_commands = [
            'srvrepo:enable_uses_for_atoms',
            'srvrepo:disable_uses_for_atoms',
            'srvrepo:compile_atoms',
            'srvrepo:spm_remove_atoms',
            'srvrepo:run_custom_shell_command',
            'srvrepo:remove_entropy_packages',
            'srvrepo:search_entropy_packages',
            'srvrepo:run_entropy_database_updates',
            'srvrepo:run_entropy_mirror_updates',
            'srvrepo:add_notice_board_entry'
        ]
        self.valid_commands = {
            'srvrepo:sync_spm':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_sync_spm,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "spawn portage sync (emerge --sync)",
                'syntax': "<SESSION_ID> srvrepo:sync_spm",
                'from': unicode(self)
            },
            'srvrepo:compile_atoms':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_compile_atoms,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "compile specified atoms using Spm (Portage?)",
                'syntax': "<SESSION_ID> srvrepo:compile_atoms <xml string containing atoms and compile options>",
                'from': unicode(self)
            },
            'srvrepo:spm_remove_atoms':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_spm_remove_atoms,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "remove specified atoms using Spm (Portage?)",
                'syntax': "<SESSION_ID> srvrepo:spm_remove_atoms <xml string containing atoms and remove options>",
                'from': unicode(self)
            },
            'srvrepo:get_spm_categories_updates':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_spm_categories_updates,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "get SPM updates for the specified package categories",
                'syntax': "<SESSION_ID> srvrepo:get_spm_categories_updates <category 1> <category 2> <...>",
                'from': unicode(self)
            },
            'srvrepo:get_spm_categories_installed':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_spm_categories_installed,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "get SPM installed packages for the specified package categories",
                'syntax': "<SESSION_ID> srvrepo:get_spm_categories_installed <category 1> <category 2> <...>",
                'from': unicode(self)
            },
            'srvrepo:enable_uses_for_atoms':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_enable_uses_for_atoms,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "enable use flags for the specified atom",
                'syntax': "<SESSION_ID> srvrepo:enable_uses_for_atom <xml string containing atoms and use flags>",
                'from': unicode(self)
            },
            'srvrepo:disable_uses_for_atoms':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_disable_uses_for_atoms,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "enable use flags for the specified atom",
                'syntax': "<SESSION_ID> srvrepo:disable_uses_for_atom <xml string containing atoms and use flags>",
                'from': unicode(self)
            },
            'srvrepo:get_spm_atoms_info':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_spm_atoms_info,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "get info from SPM for the specified atoms",
                'syntax': "<SESSION_ID> srvrepo:get_spm_atoms_info <atom1> <atom2> <atom3>",
                'from': unicode(self)
            },
            'srvrepo:run_spm_info':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_run_spm_info,
                'args': ["cmd","authenticator"],
                'as_user': False,
                'desc': "run SPM info command",
                'syntax': "<SESSION_ID> srvrepo:run_spm_info",
                'from': unicode(self)
            },
            'srvrepo:run_custom_shell_command':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_run_custom_shell_command,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "run custom shell command",
                'syntax': "<SESSION_ID> srvrepo:run_custom_shell_command <shell command blah blah>",
                'from': unicode(self)
            },
            'srvrepo:get_spm_glsa_data':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_spm_glsa_data,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "get SPM security updates info",
                'syntax': "<SESSION_ID> srvrepo:get_spm_glsa_data <list_type string (affected,new,all)>",
                'from': unicode(self)
            },
            'srvrepo:get_available_repositories':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_available_repositories,
                'args': [],
                'as_user': False,
                'desc': "get information about available Entropy repositories",
                'syntax': "<SESSION_ID> srvrepo:get_available_repositories",
                'from': unicode(self)
            },
            'srvrepo:set_default_repository':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_set_default_repository,
                'args': ["myargs"],
                'as_user': False,
                'desc': "set a new default Entropy Server repository",
                'syntax': "<SESSION_ID> srvrepo:set_default_repository <repoid>",
                'from': unicode(self)
            },
            'srvrepo:get_available_entropy_packages':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_available_entropy_packages,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get available Entropy packages from the chosen repository id",
                'syntax': "<SESSION_ID> srvrepo:get_available_entropy_packages <repoid>",
                'from': unicode(self)
            },
            'srvrepo:get_entropy_idpackage_information':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_entropy_idpackage_information,
                'args': ["myargs"],
                'as_user': False,
                'desc': "get Entropy package metadata using its idpackage and repository id",
                'syntax': "<SESSION_ID> srvrepo:get_entropy_idpackage_information <idpackage> <repoid>",
                'from': unicode(self)
            },
            'srvrepo:remove_entropy_packages':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_remove_entropy_packages,
                'args': ["myargs"],
                'as_user': False,
                'desc': "remove Entropy packages using their match -> (idpackage,repo)",
                'syntax': "<SESSION_ID> srvrepo:remove_entropy_packages idpackage:repoid,idpackage,repoid,...",
                'from': unicode(self)
            },
            'srvrepo:search_entropy_packages':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_search_entropy_packages,
                'args': ["myargs"],
                'as_user': False,
                'desc': "search Entropy packages using a defined search type, search string inside the specified repository",
                'syntax': "<SESSION_ID> srvrepo:search_entropy_packages <repoid> <search_type> <search string...>",
                'from': unicode(self)
            },
            'srvrepo:move_entropy_packages_to_repository':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_move_entropy_packages_to_repository,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "move or copy Entropy packages from a repository to another",
                'syntax': "<SESSION_ID> srvrepo:move_entropy_packages_to_repository <from_repo> <to_repo> <do_copy (True: copy, False: move)> <idpackages...>",
                'from': unicode(self)
            },
            'srvrepo:scan_entropy_packages_database_changes':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_scan_entropy_packages_database_changes,
                'args': ["cmd","authenticator"],
                'as_user': False,
                'desc': "scan Spm package changes to retrieve a list of action that should be run on the repositories",
                'syntax': "<SESSION_ID> srvrepo:scan_entropy_packages_database_changes",
                'from': unicode(self)
            },
            'srvrepo:run_entropy_database_updates':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_run_entropy_database_updates,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "run Entropy database updates",
                'syntax': "<SESSION_ID> srvrepo:run_entropy_database_updates <to_add: atom:counter:repoid,atom:counter:repoid,...> <to_remove: idpackage:repoid,idpackage:repoid,...> <to_inject: idpackage:repoid,idpackage:repoid,...>",
                'from': unicode(self)
            },
            'srvrepo:run_entropy_dependency_test':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_run_entropy_dependency_test,
                'args': ["cmd","authenticator"],
                'as_user': False,
                'desc': "run Entropy dependency test",
                'syntax': "<SESSION_ID> srvrepo:run_entropy_dependency_test",
                'from': unicode(self)
            },
            'srvrepo:run_entropy_library_test':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_run_entropy_library_test,
                'args': ["cmd","authenticator"],
                'as_user': False,
                'desc': "run Entropy dependency test",
                'syntax': "<SESSION_ID> srvrepo:run_entropy_library_test",
                'from': unicode(self)
            },
            'srvrepo:run_entropy_treeupdates':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_run_entropy_treeupdates,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "run Entropy database treeupdates",
                'syntax': "<SESSION_ID> srvrepo:run_entropy_treeupdates <repoid>",
                'from': unicode(self)
            },
            'srvrepo:scan_entropy_mirror_updates':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_scan_entropy_mirror_updates,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "scan mirror updates for the specified repository identifiers",
                'syntax': "<SESSION_ID> srvrepo:scan_entropy_mirror_updates <repoid 1> <repoid 2> <...>",
                'from': unicode(self)
            },
            'srvrepo:run_entropy_mirror_updates':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_run_entropy_mirror_updates,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "run mirror updates for the provided repositories",
                'syntax': "<SESSION_ID> srvrepo:run_entropy_mirror_updates <xml data, properly formatted>",
                'from': unicode(self)
            },
            'srvrepo:run_entropy_checksum_test':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_run_entropy_checksum_test,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "run Entropy packages checksum verification tool",
                'syntax': "<SESSION_ID> srvrepo:run_entropy_checksum_test <repoid> <mode>",
                'from': unicode(self)
            },
            'srvrepo:get_notice_board':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_get_notice_board,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "get repository notice board",
                'syntax': "<SESSION_ID> srvrepo:get_notice_board <repoid>",
                'from': unicode(self)
            },
            'srvrepo:remove_notice_board_entries':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_remove_notice_board_entries,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "remove notice board entries",
                'syntax': "<SESSION_ID> srvrepo:remove_notice_board_entries <repoid> <entry_id1> <entry_id2> <...>",
                'from': unicode(self)
            },
            'srvrepo:add_notice_board_entry':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_add_notice_board_entry,
                'args': ["cmd","myargs","authenticator"],
                'as_user': False,
                'desc': "remove notice board entry",
                'syntax': "<SESSION_ID> srvrepo:add_notice_board_entry <xml formatted data>",
                'from': unicode(self)
            },
        }

    def docmd_sync_spm(self, cmd, myargs, authenticator):

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'sync_spm', [], {}, False, False, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_compile_atoms(self, cmd, myargs, authenticator):

        if not myargs:
            return False,'wrong arguments'

        xml_string = ' '.join(myargs)

        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)

        if not ( mydict.has_key('atoms') and mydict.has_key('pretend') and \
                 mydict.has_key('oneshot') and  mydict.has_key('verbose') and \
                 mydict.has_key('fetchonly') and  mydict.has_key('buildonly') and \
                 mydict.has_key('nodeps') and \
                 mydict.has_key('nocolor') and  mydict.has_key('custom_use') and \
                 mydict.has_key('ldflags') and  mydict.has_key('cflags') ):
            return None,'wrong dict arguments, xml must have 10 items with attr value' + \
                        ' -> atoms, pretend, oneshot, verbose, nocolor, fetchonly, ' + \
                        'buildonly, nodeps, custom_use, ldflags, cflags'

        atoms = mydict.get('atoms')
        if atoms: atoms = atoms.split()
        pretend = mydict.get('pretend')
        oneshot = mydict.get('oneshot')
        verbose = mydict.get('verbose')
        nocolor = mydict.get('nocolor')
        fetchonly = mydict.get('fetchonly')
        buildonly = mydict.get('buildonly')
        nodeps = mydict.get('nodeps')
        custom_use = mydict.get('custom_use')
        ldflags = mydict.get('ldflags')
        cflags = mydict.get('cflags')

        if pretend == "1": pretend = True
        else: pretend = False
        if oneshot == "1": oneshot = True
        else: oneshot = False
        if verbose == "1": verbose = True
        else: verbose = False
        if nocolor == "1": nocolor = True
        else: nocolor = False
        if fetchonly == "1": fetchonly = True
        else: fetchonly = False
        if buildonly == "1": buildonly = True
        else: buildonly = False
        if nodeps == "1": nodeps = True
        else: nodeps = False

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        add_dict = {
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

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs),
            uid, gid, 'compile_atoms', [atoms[:]], add_dict.copy(), False, False, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_spm_remove_atoms(self, cmd, myargs, authenticator):
        if not myargs:
            return False,'wrong arguments'

        xml_string = ' '.join(myargs)

        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)

        if not ( mydict.has_key('atoms') and mydict.has_key('pretend') and \
                 mydict.has_key('verbose') and mydict.has_key('nocolor') ):
            return None,'wrong dict arguments, xml must have 4 items with attr value -> atoms, pretend, verbose, nocolor'

        atoms = mydict.get('atoms')
        if atoms: atoms = atoms.split()
        pretend = mydict.get('pretend')
        verbose = mydict.get('verbose')
        nocolor = mydict.get('nocolor')

        if pretend == "1": pretend = True
        else: pretend = False
        if verbose == "1": verbose = True
        else: verbose = False
        if nocolor == "1": nocolor = True
        else: nocolor = False

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        add_dict = {
            'pretend': pretend,
            'verbose': verbose,
            'nocolor': nocolor,
        }

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'spm_remove_atoms', [atoms[:]], add_dict.copy(), False, False, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_get_spm_categories_updates(self, cmd, myargs, authenticator):
        if not myargs:
            return False,'wrong arguments'

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'get_spm_categories_updates', [myargs], {}, True, True, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_get_spm_categories_installed(self, cmd, myargs, authenticator):

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'get_spm_categories_installed', [myargs], {}, True, True, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_enable_uses_for_atoms(self, cmd, myargs, authenticator):
        if not myargs:
            return False,'wrong arguments'

        xml_string = ' '.join(myargs)
        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)
        if not (mydict.has_key('atoms') and mydict.has_key('useflags')):
            return None,'wrong dict arguments, xml must have 2 items with attr value -> atoms, useflags'

        atoms = mydict.get('atoms')
        useflags = mydict.get('useflags')
        if atoms: atoms = atoms.split()
        if useflags: useflags = useflags.split()

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'enable_uses_for_atoms', [atoms,useflags], {}, True, True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_disable_uses_for_atoms(self, cmd, myargs, authenticator):
        if not myargs:
            return False,'wrong arguments'

        xml_string = ' '.join(myargs)
        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)
        if not (mydict.has_key('atoms') and mydict.has_key('useflags')):
            return None,'wrong dict arguments, xml must have 2 items with attr value -> atoms, useflags'

        atoms = mydict.get('atoms')
        useflags = mydict.get('useflags')
        if atoms: atoms = atoms.split()
        if useflags: useflags = useflags.split()

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'disable_uses_for_atoms', [atoms,useflags], {}, True, True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_get_spm_atoms_info(self, cmd, myargs, authenticator):
        if not myargs:
            return False,'wrong arguments'

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'get_spm_atoms_info', [myargs], {}, True, True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_run_spm_info(self, cmd, authenticator):

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, '', uid, gid, 'run_spm_info', [], {}, True, False, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_run_custom_shell_command(self, cmd, myargs, authenticator):
        if not myargs:
            return False,'wrong arguments'

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')
        command = ' '.join(myargs)

        queue_id = self.HostInterface.add_to_queue(cmd, command, uid, gid, 'run_custom_shell_command', [command], {}, True, False, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_get_spm_glsa_data(self, cmd, myargs, authenticator):
        if not myargs:
            return False,'wrong arguments'

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'get_spm_glsa_data', [myargs[0]], {}, True, True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_get_available_repositories(self):
        data = {}
        data['available'] = self.HostInterface.Entropy.get_available_repositories()
        if etpConst['clientserverrepoid'] in data['available']:
            data['available'].pop(etpConst['clientserverrepoid'])
        data['community_mode'] = self.HostInterface.Entropy.community_repo
        data['current'] = self.HostInterface.Entropy.default_repository
        data['branches'] = etpConst['branches']
        data['branch'] = etpConst['branch']
        return True, data

    def docmd_set_default_repository(self, myargs):

        if not myargs:
            return False,'wrong arguments'
        repoid = myargs[0]
        if repoid not in self.HostInterface.Entropy.get_available_repositories():
            return False,'repository id not available'

        status = True
        msg = 'ok'
        try:
            self.HostInterface.Entropy.switch_default_repository(repoid, save = True, handle_uninitialized = False)
        except Exception, e:
            status = False
            msg = unicode(e)
        return status, msg

    def docmd_get_available_entropy_packages(self, myargs):

        if not myargs:
            return False,'wrong arguments'
        repoid = myargs[0]
        if repoid not in self.HostInterface.Entropy.get_available_repositories():
            return False,'repository id not available'

        dbconn = self.HostInterface.Entropy.open_server_repository(repo = repoid, just_reading = True, warnings = False, do_cache = False)
        idpackages = dbconn.listAllIdpackages(order_by = 'atom')
        package_data = []
        package_data = {
            'ordered_idpackages': idpackages,
            'data': {},
        }
        for idpackage in idpackages:

            data = self._get_entropy_pkginfo(dbconn, idpackage, repoid)
            if not data: continue
            package_data['data'][idpackage] = data.copy()
        dbconn.closeDB()
        return True,package_data

    def docmd_get_entropy_idpackage_information(self, myargs):

        if len(myargs) < 2:
            return False,'wrong arguments'
        idpackage = myargs[0]
        repoid = myargs[1]

        dbconn = self.HostInterface.Entropy.open_server_repository(repo = repoid, just_reading = True, warnings = False, do_cache = False)
        package_data = dbconn.getPackageData(idpackage, trigger_unicode = True)
        dbconn.closeDB()
        return True,package_data

    def docmd_remove_entropy_packages(self, myargs):
        if not myargs:
            return False,'wrong arguments'
        string = myargs[0].split(",")
        matched_atoms = []
        try:
            for item in string:
                mysplit = item.split(":")
                matched_atoms.append((int(mysplit[0]),mysplit[1],))
        except:
            return False,'cannot eval() string correctly'

        repo_data = {}
        for idpackage,repoid in matched_atoms:
            if not repo_data.has_key(repoid):
                repo_data[repoid] = []
            repo_data[repoid].append(idpackage)

        status = True
        msg = 'ok'
        try:
            for repoid in repo_data:
                self.HostInterface.Entropy.remove_packages(repo_data[repoid],repo = repoid)
        except Exception, e:
            status = False
            msg = unicode(e)

        return status, msg

    def docmd_move_entropy_packages_to_repository(self, cmd, myargs, authenticator):

        if len(myargs) < 4:
            return False,'wrong arguments'

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        from_repo = myargs[0]
        to_repo = myargs[1]
        do_copy = myargs[2]
        idpackages = myargs[3:]

        queue_id = self.HostInterface.add_to_queue(
            cmd, ' '.join([str(x) for x in myargs]),
            uid, gid, 'move_entropy_packages_to_repository',
            [from_repo,to_repo,idpackages,do_copy], {}, False, True,
            interactive = True
        )
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_scan_entropy_packages_database_changes(self, cmd, authenticator):

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, '', uid, gid, 'scan_entropy_packages_database_changes', [], {}, True, True, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_run_entropy_dependency_test(self, cmd, authenticator):

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, '', uid, gid, 'run_entropy_dependency_test', [], {}, True, True, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_run_entropy_library_test(self, cmd, authenticator):

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, '', uid, gid, 'run_entropy_library_test', [], {}, True, True, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_run_entropy_checksum_test(self, cmd, myargs, authenticator):
        if len(myargs) < 2:
            return False,'wrong arguments'
        repoid = myargs[0]
        mode = myargs[1]

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'run_entropy_checksum_test', [repoid,mode], {}, True, False, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_run_entropy_treeupdates(self, cmd, myargs, authenticator):

        if not myargs:
            return False,'wrong arguments'

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'run_entropy_treeupdates', [myargs[0]], {}, False, False, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_scan_entropy_mirror_updates(self, cmd, myargs, authenticator):

        if not myargs:
            return False,'wrong arguments'

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'scan_entropy_mirror_updates', [myargs], {}, True, True, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_run_entropy_mirror_updates(self, cmd, myargs, authenticator):

        if not myargs:
            return False,'wrong arguments'

        serialized_string = '\n'.join(myargs)
        try:
            mydict = self.dumpTools.unserialize_string(serialized_string)
        except Exception, e:
            return False,'cannot parse data: %s' % (e,)

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, '<raw data>', uid, gid, 'run_entropy_mirror_updates', [mydict], {}, False, False, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_run_entropy_database_updates(self, cmd, myargs, authenticator):

        to_add = {}
        to_remove = []
        to_inject = []
        to_add_string = ''
        to_remove_string = ''
        to_inject_string = ''
        if myargs:
            to_add_string = myargs[0].split(",")
        if len(myargs) > 1:
            to_remove_string = myargs[1].split(",")
        if len(myargs) > 2:
            to_inject_string = myargs[2].split(",")
        try:

            for item in to_add_string:
                atom, counter, repoid = item.split(":")
                if not to_add.has_key(repoid):
                    to_add[repoid] = []
                to_add[repoid].append(atom)

            for item in to_remove_string:
                idpackage, repoid = item.split(":")
                to_remove.append((idpackage, repoid,))

            for item in to_inject_string:
                idpackage, repoid = item.split(":")
                to_inject.append((idpackage, repoid,))

        except Exception, e:
            return False,'cannot run database updates properly: %s' % (e,)

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(
            cmd, ' '.join(myargs), uid, gid,
            'run_entropy_database_updates', [to_add,to_remove,to_inject],
            {}, False, True, interactive = True
        )
        if queue_id < 0: return False, queue_id
        return True, queue_id


    def docmd_search_entropy_packages(self, myargs):
        if len(myargs) < 3:
            return False,'wrong arguments'

        repoid = myargs[0]
        search_type = myargs[1]
        search_string = ' '.join(myargs[2:])
        avail_search_types = ['atom','needed','depends','tag','file','description']

        if search_type not in avail_search_types:
            return False, 'available search types: %s' % (avail_search_types,)

        search_results = {
            'ordered_idpackages': set(),
            'data': {},
        }

        dbconn = self.HostInterface.Entropy.open_server_repository(repo = repoid, just_reading = True, warnings = False, do_cache = False)

        if search_type == "atom":

            mysearchlist = search_string.split()
            for mystring in mysearchlist:
                results = dbconn.searchPackages(mystring)
                for atom, idpackage, branch in results:
                    data = self._get_entropy_pkginfo(dbconn, idpackage, repoid)
                    if not data: continue
                    search_results['ordered_idpackages'].add(idpackage)
                    search_results['data'][idpackage] = data.copy()

        elif search_type == "needed":

            mysearchlist = search_string.split()
            for mystring in mysearchlist:
                idpackages = dbconn.searchNeeded(mystring, like = True)
                for idpackage in idpackages:
                    search_results['ordered_idpackages'].add(idpackage)
                    search_results['data'][idpackage] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)

        elif search_type == "depends":

            mysearchlist = search_string.split()
            for mystring in mysearchlist:
                m_idpackage, m_result = dbconn.atomMatch(mystring)
                if m_idpackage == -1: continue
                idpackages = dbconn.retrieveDepends(m_idpackage)
                for idpackage in idpackages:
                    search_results['ordered_idpackages'].add(idpackage)
                    search_results['data'][idpackage] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)

        elif search_type == "tag":

            mysearchlist = search_string.split()
            for mystring in mysearchlist:
                idpackages = dbconn.searchTaggedPackages(mystring)
                for idpackage in idpackages:
                    search_results['ordered_idpackages'].add(idpackage)
                    search_results['data'][idpackage] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)

        elif search_type == "file":
            # belong

            like = False
            if search_string.find("*") != -1:
                search_string.replace("*","%")
                like = True
            idpackages = dbconn.searchBelongs(search_string, like)
            for idpackage in idpackages:
                search_results['ordered_idpackages'].add(idpackage)
                search_results['data'][idpackage] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)

        elif search_type == "description":

            results = dbconn.searchPackagesByDescription(search_string)
            for atom, idpackage in results:
                search_results['ordered_idpackages'].add(idpackage)
                search_results['data'][idpackage] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)

        elif search_type == "eclass":

            mysearchlist = search_string.split()
            for eclass in mysearchlist:
                idpackages = dbconn.searchEclassedPackages(eclass)
                for idpackage in idpackages:
                    search_results['ordered_idpackages'].add(idpackage)
                    search_results['data'][idpackage] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)


        dbconn.closeDB()
        return True, search_results

    def docmd_get_notice_board(self, cmd, myargs, authenticator):

        if not myargs:
            return False,'wrong arguments'
        repoid = myargs[0]

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(cmd, ' '.join(myargs), uid, gid, 'get_notice_board', [repoid], {}, True, True, interactive = True)
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_remove_notice_board_entries(self, cmd, myargs, authenticator):

        if len(myargs) < 2:
            return False,'wrong arguments'
        repoid = myargs[0]
        entry_ids = myargs[1:]

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(
            cmd, ' '.join([unicode(x) for x in myargs]), uid, gid,
            'remove_notice_board_entries', [repoid,entry_ids], {}, True, False, interactive = True
        )
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def docmd_add_notice_board_entry(self, cmd, myargs, authenticator):

        if not myargs:
            return False,'wrong arguments'

        xml_string = ' '.join(myargs)
        try:
            mydict = self.entropyTools.dict_from_xml(xml_string)
        except Exception, e:
            return None,"error: %s" % (e,)
        if not (mydict.has_key('repoid') and mydict.has_key('title') and \
                mydict.has_key('notice_text') and mydict.has_key('link')):
            return None,'wrong dict arguments, xml must have 4 items with attr value -> repoid, title, notice_text, link'

        repoid = mydict.get('repoid')
        title = mydict.get('title')
        notice_text = mydict.get('notice_text')
        link = mydict.get('link')

        status, userdata, err_str = authenticator.docmd_userdata()
        uid = userdata.get('uid')
        gid = userdata.get('gid')

        queue_id = self.HostInterface.add_to_queue(
            cmd, ' '.join(myargs), uid, gid,
            'add_notice_board_entry', [repoid,title,notice_text,link], {}, True, False, interactive = True
        )
        if queue_id < 0: return False, queue_id
        return True, queue_id

    def _get_entropy_pkginfo(self, dbconn, idpackage, repoid):
        data = {}
        try:
            data['atom'], data['name'], data['version'], data['versiontag'], \
            data['description'], data['category'], data['chost'], \
            data['cflags'], data['cxxflags'],data['homepage'], \
            data['license'], data['branch'], data['download'], \
            data['digest'], data['slot'], data['etpapi'], \
            data['datecreation'], data['size'], data['revision']  = dbconn.getBaseData(idpackage)
        except TypeError:
            return data
        data['injected'] = dbconn.isInjected(idpackage)
        data['repoid'] = repoid
        data['idpackage'] = idpackage
        return data
