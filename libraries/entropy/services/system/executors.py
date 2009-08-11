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
import sys
import subprocess
from entropy.const import etpConst
from entropy.output import blue, red
from entropy.i18n import _

class Base:

    import entropy.tools as entropyTools
    def __init__(self, SystemManagerExecutorInstance, *args, **kwargs):

        try:
            import cPickle as pickle
        except ImportError:
            import pickle
        self.pickle = pickle

        self.SystemManagerExecutor = SystemManagerExecutorInstance
        self.args = args
        self.kwargs = kwargs
        self.available_commands = {
            'sync_spm': {
                'func': self.sync_portage,
                'args': 1,
            },
            'compile_atoms': {
                'func': self.compile_atoms,
                'args': 2,
            },
            'spm_remove_atoms': {
                'func': self.spm_remove_atoms,
                'args': 2,
            },
            'get_spm_categories_updates': {
                'func': self.get_spm_categories_updates,
                'args': 2,
            },
            'get_spm_categories_installed': {
                'func': self.get_spm_categories_installed,
                'args': 2,
            },
            'enable_uses_for_atoms': {
                'func': self.enable_uses_for_atoms,
                'args': 3,
            },
            'disable_uses_for_atoms': {
                'func': self.disable_uses_for_atoms,
                'args': 3,
            },
            'get_spm_atoms_info': {
                'func': self.get_spm_atoms_info,
                'args': 2,
            },
            'run_spm_info': {
                'func': self.run_spm_info,
                'args': 1,
            },
            'run_custom_shell_command': {
                'func': self.run_custom_shell_command,
                'args': 1,
            },
            'get_spm_glsa_data': {
                'func': self.get_spm_glsa_data,
                'args': 1,
            },
            'move_entropy_packages_to_repository': {
                'func': self.move_entropy_packages_to_repository,
                'args': 5,
            },
            'scan_entropy_packages_database_changes': {
                'func': self.scan_entropy_packages_database_changes,
                'args': 1,
            },
            'run_entropy_database_updates': {
                'func': self.run_entropy_database_updates,
                'args': 4,
            },
            'run_entropy_dependency_test': {
                'func': self.run_entropy_dependency_test,
                'args': 1,
            },
            'run_entropy_library_test': {
                'func': self.run_entropy_library_test,
                'args': 1,
            },
            'run_entropy_treeupdates': {
                'func': self.run_entropy_treeupdates,
                'args': 2,
            },
            'scan_entropy_mirror_updates': {
                'func': self.scan_entropy_mirror_updates,
                'args': 2,
            },
            'run_entropy_mirror_updates': {
                'func': self.run_entropy_mirror_updates,
                'args': 2,
            },
            'run_entropy_checksum_test': {
                'func': self.run_entropy_checksum_test,
                'args': 3,
            },
            'get_notice_board': {
                'func': self.get_notice_board,
                'args': 2,
            },
            'remove_notice_board_entries': {
                'func': self.remove_notice_board_entries,
                'args': 3,
            },
            'add_notice_board_entry': {
                'func': self.add_notice_board_entry,
                'args': 5,
            },
        }

    def _set_processing_pid(self, queue_id, process_pid):
        with self.SystemManagerExecutor.SystemInterface.QueueLock:
            self.SystemManagerExecutor.SystemInterface.load_queue()
            live_item, key = self.SystemManagerExecutor.SystemInterface._get_item_by_queue_id(queue_id)
            if isinstance(live_item,dict):
                live_item['processing_pid'] = process_pid
                # _get_item_by_queue_id
                self.SystemManagerExecutor.SystemInterface.store_queue()

    def sync_portage(self, queue_id):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        cmd = ["emerge", "--sync"]
        try:
            p = subprocess.Popen(cmd, stdout = stdout_err, stderr = stdout_err, stdin = self._get_stdin(queue_id))
            self._set_processing_pid(queue_id, p.pid)
            rc = p.wait()
        finally:
            stdout_err.write("\n### Done ###\n")
            stdout_err.flush()
            stdout_err.close()
        return True,rc

    def compile_atoms(  self,
                        queue_id, atoms,
                        pretend = False, oneshot = False,
                        verbose = True, nocolor = True,
                        fetchonly = False, buildonly = False,
                        nodeps = False, custom_use = '', ldflags = '', cflags = ''
        ):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        cmd = [etpConst['spm']['env_update_cmd'],"&&"]
        cmd += etpConst['spm']['source_profile']+["&&"]
        if custom_use:
            cmd += ['export USE="']+custom_use.strip().split()+['"','&&']
        if ldflags:
            cmd += ['export LDFLAGS="']+custom_use.strip().split()+['"','&&']
        if cflags:
            cmd += ['export CFLAGS="']+custom_use.strip().split()+['"','&&']
        cmd += [etpConst['spm']['exec']]+atoms
        if pretend:
            cmd.append(etpConst['spm']['pretend_cmd'])
        if verbose:
            cmd.append(etpConst['spm']['verbose_cmd'])
        if oneshot:
            cmd.append(etpConst['spm']['oneshot_cmd'])
        if nocolor:
            cmd.append(etpConst['spm']['nocolor_cmd'])
        if fetchonly:
            cmd.append(etpConst['spm']['fetchonly_cmd'])
        if buildonly:
            cmd.append(etpConst['spm']['buildonly_cmd'])
        if nodeps:
            cmd.append(etpConst['spm']['nodeps_cmd'])

        stdout_err.write("Preparing to spawn parameter: '%s'. Good luck mate!\n" % (' '.join(cmd),))
        stdout_err.flush()

        try:
            p = subprocess.Popen(' '.join(cmd), stdout = stdout_err, stderr = stdout_err, stdin = self._get_stdin(queue_id), shell = True)
            self._set_processing_pid(queue_id, p.pid)
            rc = p.wait()
        finally:
            stdout_err.write("\n### Done ###\n")
            stdout_err.flush()
            stdout_err.close()
        return True,rc

    def spm_remove_atoms(self, queue_id, atoms, pretend = True, verbose = True, nocolor = True):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        cmd = [etpConst['spm']['env_update_cmd'],"&&"]
        cmd += etpConst['spm']['source_profile']+["&&"]
        cmd += [etpConst['spm']['exec'],etpConst['spm']['remove_cmd']]+atoms
        if pretend:
            cmd.append(etpConst['spm']['pretend_cmd'])
        if verbose:
            cmd.append(etpConst['spm']['verbose_cmd'])
        if nocolor:
            cmd.append(etpConst['spm']['nocolor_cmd'])

        stdout_err.write("Preparing to spawn parameter: '%s'. Good luck mate!\n" % (' '.join(cmd),))
        stdout_err.flush()

        try:
            p = subprocess.Popen(' '.join(cmd), stdout = stdout_err, stderr = stdout_err, stdin = self._get_stdin(queue_id), shell = True)
            self._set_processing_pid(queue_id, p.pid)
            rc = p.wait()
        finally:
            stdout_err.write("\n### Done ###\n")
            stdout_err.flush()
            stdout_err.close()
        return True,rc

    def enable_uses_for_atoms(self, queue_id, atoms, useflags):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        use_data = {}
        spm = self.SystemManagerExecutor.SystemInterface.Entropy.Spm()
        for atom in atoms:
            try:
                status = spm.enable_package_useflags(atom, useflags)
            except:
                continue
            if status:
                use_data[atom] = {}
                matched_atom = spm.get_best_atom(atom)
                use_data[atom] = spm.get_package_useflags(matched_atom)

        return True, use_data

    def disable_uses_for_atoms(self, queue_id, atoms, useflags):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        use_data = {}
        spm = self.SystemManagerExecutor.SystemInterface.Entropy.Spm()
        for atom in atoms:
            try:
                status = spm.disable_package_useflags(atom, useflags)
            except:
                continue
            if status:
                use_data[atom] = {}
                matched_atom = spm.get_best_atom(atom)
                use_data[atom] = spm.get_package_useflags(matched_atom)

        return True, use_data

    def get_spm_atoms_info(self, queue_id, atoms):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        atoms_data = {}
        spm = self.SystemManagerExecutor.SystemInterface.Entropy.Spm()
        for atom in atoms:

            try:
                key = self.entropyTools.dep_getkey(atom)
                category = key.split("/")[0]
            except:
                continue
            matched_atom = spm.get_best_atom(atom)
            if not matched_atom: continue

            if not atoms_data.has_key(category):
                atoms_data[category] = {}

            atoms_data[category][matched_atom] = self._get_spm_pkginfo(matched_atom)

        return True, atoms_data

    def get_spm_categories_updates(self, queue_id, categories):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        spm = self.SystemManagerExecutor.SystemInterface.Entropy.Spm()
        packages = spm.get_available_packages(categories)
        package_data = {}
        for package in packages:
            try:
                key = self.entropyTools.dep_getkey(package)
                category = key.split("/")[0]
            except:
                continue
            if not package_data.has_key(category):
                package_data[category] = {}
            package_data[category][package] = self._get_spm_pkginfo(package)

        return True, package_data

    def get_spm_categories_installed(self, queue_id, categories):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        spm = self.SystemManagerExecutor.SystemInterface.Entropy.Spm()
        packages, pkg_len = spm.get_installed_packages(categories = categories)
        package_data = {}
        for package in packages:
            try:
                key = self.entropyTools.dep_getkey(package)
                category = key.split("/")[0]
            except:
                continue
            if not package_data.has_key(category):
                package_data[category] = {}
            package_data[category][package] = self._get_spm_pkginfo(package, from_installed = True)

        return True, package_data

    def run_spm_info(self, queue_id):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        cmd = [etpConst['spm']['exec'],etpConst['spm']['info_cmd']]

        stdout_err.write("Preparing to spawn parameter: '%s'. Good luck mate!\n" % (' '.join(cmd),))
        stdout_err.flush()

        try:
            p = subprocess.Popen(cmd, stdout = stdout_err, stderr = stdout_err, stdin = self._get_stdin(queue_id))
            self._set_processing_pid(queue_id, p.pid)
            rc = p.wait()
        finally:
            stdout_err.write("\n### Done ###\n")
            stdout_err.flush()
            stdout_err.close()
        return True,rc

    def run_custom_shell_command(self, queue_id, command):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        cmd = [etpConst['spm']['env_update_cmd'],"&&"]
        cmd += etpConst['spm']['source_profile']+[";"]
        cmd += command.split()

        cmd = ' '.join(cmd)
        stdout_err.write("Preparing to spawn parameter: '%s'. Good luck mate!\n" % (cmd,))
        stdout_err.flush()

        try:
            p = subprocess.Popen(cmd, stdout = stdout_err, stderr = stdout_err, stdin = self._get_stdin(queue_id), shell = True)
            self._set_processing_pid(queue_id, p.pid)
            rc = p.wait()
        finally:
            stdout_err.write("\n### Done ###\n")
            stdout_err.flush()
            stdout_err.close()
        return True,rc

    def move_entropy_packages_to_repository(self, queue_id, from_repo, to_repo, idpackages, do_copy):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        # run
        matches = []
        for idpackage in idpackages:
            matches.append((idpackage,from_repo,))

        stdout_err = open(queue_data['stdout'],"a+")

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:
                switched = self.SystemManagerExecutor.SystemInterface.Entropy.move_packages(
                    matches, to_repo,
                    from_repo = from_repo,
                    ask = False,
                    do_copy = do_copy
                )
                return switched
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        switched = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()

        rc = 1
        if len(switched) == len(idpackages):
            rc = 0
        return True,rc

    def scan_entropy_packages_database_changes(self, queue_id):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")
        Entropy = self.SystemManagerExecutor.SystemInterface.Entropy

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:

                for repoid in Entropy.get_available_repositories():
                    self.run_entropy_treeupdates(queue_id, repoid)

                stdout_err.write("\n"+_("Calculating updates...").encode('utf-8')+"\n")
                stdout_err.flush()

                to_add, to_remove, to_inject = Entropy.scan_package_changes()
                mydict = { 'add': to_add, 'remove': to_remove, 'inject': to_inject }

                # setup add data
                mydict['add_data'] = {}
                for portage_atom, portage_counter in to_add:
                    mydict['add_data'][(portage_atom, portage_counter,)] = self._get_spm_pkginfo(portage_atom,from_installed = True)

                mydict['remove_data'] = {}
                for idpackage, repoid in to_remove:
                    dbconn = Entropy.open_server_repository(repo = repoid, just_reading = True, warnings = False, do_cache = False)
                    mydict['remove_data'][(idpackage, repoid,)] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)
                    dbconn.closeDB()

                mydict['inject_data'] = {}
                for idpackage, repoid in to_inject:
                    dbconn = Entropy.open_server_repository(repo = repoid, just_reading = True, warnings = False, do_cache = False)
                    mydict['inject_data'][(idpackage, repoid,)] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)
                    dbconn.closeDB()

                return True,mydict

            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        data = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return data

    def run_entropy_database_updates(self, queue_id, to_add, to_remove, to_inject):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")
        Entropy = self.SystemManagerExecutor.SystemInterface.Entropy

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:

                atoms_removed = []
                matches_injected = set()

                if to_inject: Entropy.updateProgress(_("Running package injection"))

                # run inject
                for idpackage, repoid in to_inject:
                    matches_injected.add((idpackage,repoid,))
                    Entropy.transform_package_into_injected(idpackage, repo = repoid)

                if to_remove: Entropy.updateProgress(_("Running package removal"))

                # run remove
                remdata = {}
                for idpackage,repoid in to_remove:
                    dbconn = Entropy.open_server_repository(repo = repoid, just_reading = True, warnings = False, do_cache = False)
                    atoms_removed.append(dbconn.retrieveAtom(idpackage))
                    dbconn.closeDB()
                    if not remdata.has_key(repoid):
                        remdata[repoid] = set()
                    remdata[repoid].add(idpackage)
                for repoid in remdata:
                    Entropy.remove_packages(remdata[repoid], repo = repoid)

                mydict = {
                    'added_data': {},
                    'remove_data': atoms_removed,
                    'inject_data': {}
                }

                if to_add:
                    problems = Entropy.check_config_file_updates()
                    if problems:
                        return False,mydict
                    Entropy.updateProgress(_("Running package quickpkg"))

                # run quickpkg
                for repoid in to_add:
                    store_dir = Entropy.get_local_store_directory(repo = repoid)
                    for atom in to_add[repoid]:
                        Entropy.quickpkg(atom,store_dir)

                # inject new into db
                avail_repos = Entropy.get_available_repositories()
                if etpConst['clientserverrepoid'] in avail_repos:
                    avail_repos.pop(etpConst['clientserverrepoid'])
                matches_added = set()
                for repoid in avail_repos:
                    store_dir = Entropy.get_local_store_directory(repo = repoid)
                    package_files = os.listdir(store_dir)
                    if not package_files: continue
                    package_files = [(os.path.join(store_dir,x),False) for x in package_files]

                    Entropy.updateProgress( "[%s|%s] %s" % (
                            repoid,
                            Entropy.SystemSettings['repositories']['branch'],
                            _("Adding packages"),
                        )
                    )
                    for package_file, inject in package_files:
                        Entropy.updateProgress("    %s" % (package_file,))

                    idpackages = Entropy.add_packages_to_repository(package_files, ask = False, repo = repoid)
                    matches_added |= set([(x,repoid,) for x in idpackages])


                Entropy.dependencies_test()

                for idpackage, repoid in matches_added:
                    dbconn = Entropy.open_server_repository(repo = repoid, just_reading = True, warnings = False, do_cache = False)
                    mydict['added_data'][(idpackage, repoid,)] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)
                    dbconn.closeDB()
                for idpackage, repoid in matches_injected:
                    dbconn = Entropy.open_server_repository(repo = repoid, just_reading = True, warnings = False, do_cache = False)
                    mydict['inject_data'][(idpackage, repoid,)] = self._get_entropy_pkginfo(dbconn, idpackage, repoid)
                    dbconn.closeDB()
                return True, mydict

            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        data = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return data

    def run_entropy_dependency_test(self, queue_id):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:
                deps_not_matched = self.SystemManagerExecutor.SystemInterface.Entropy.dependencies_test()
                return True,deps_not_matched
            except Exception, e:
                self.entropyTools.print_traceback()
                return False,unicode(e)
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        data = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return data

    def run_entropy_library_test(self, queue_id):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:
                return self.SystemManagerExecutor.SystemInterface.Entropy.test_shared_objects()
            except Exception, e:
                self.entropyTools.print_traceback()
                return False,unicode(e)
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        status, result = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()

        mystatus = False
        if status == 0: mystatus = True
        if not result: result = set()
        return mystatus,result

    def run_entropy_checksum_test(self, queue_id, repoid, mode):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:
                if mode == "local":
                    data = self.SystemManagerExecutor.SystemInterface.Entropy.verify_local_packages([], ask = False, repo = repoid)
                else:
                    data = self.SystemManagerExecutor.SystemInterface.Entropy.verify_remote_packages([], ask = False, repo = repoid)
                return True, data
            except Exception, e:
                self.entropyTools.print_traceback()
                return False,unicode(e)
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        mydata = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return mydata

    def run_entropy_treeupdates(self, queue_id, repoid):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:
                sys.stdout.write(_("Opening database to let it run treeupdates. If you won't see anything below, it's just fine.").encode('utf-8')+"\n")
                dbconn = self.SystemManagerExecutor.SystemInterface.Entropy.open_server_repository(
                    repo = repoid, do_cache = False,
                    read_only = True
                )
                dbconn.closeDB()
            except Exception, e:
                self.entropyTools.print_traceback()
                return False,unicode(e)
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return True, 0

    def scan_entropy_mirror_updates(self, queue_id, repositories):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")
        import socket
        Entropy = self.SystemManagerExecutor.SystemInterface.Entropy

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:

                sys.stdout.write(_("Scanning").encode('utf-8')+"\n")
                repo_data = {}
                for repoid in repositories:

                    repo_data[repoid] = {}

                    for uri in Entropy.get_remote_mirrors(repoid):

                        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)

                        repo_data[repoid][crippled_uri] = {}
                        repo_data[repoid][crippled_uri]['packages'] = {}

                        try:
                            upload_queue, download_queue, removal_queue, \
                                fine_queue, remote_packages_data = Entropy.MirrorsService.calculate_packages_to_sync(
                                    uri, Entropy.SystemSettings['repositories']['branch'],
                                    repoid)
                        except socket.error:
                            self.entropyTools.print_traceback(f = stdout_err)
                            stdout_err.write("\n"+_("Socket error, continuing...").encode('utf-8')+"\n")
                            continue

                        if (upload_queue or download_queue or removal_queue):
                            upload, download, removal, copy, metainfo = Entropy.MirrorsService.expand_queues(
                                upload_queue,
                                download_queue,
                                removal_queue,
                                remote_packages_data,
                                Entropy.SystemSettings['repositories']['branch'],
                                repoid
                            )
                            if len(upload)+len(download)+len(removal)+len(copy):
                                repo_data[repoid][crippled_uri]['packages'] = {
                                    'upload': upload,
                                    'download': download,
                                    'removal': removal,
                                    'copy': copy,
                                }

                        # now the db
                        current_revision = Entropy.get_local_database_revision(repoid)
                        remote_revision = Entropy.get_remote_database_revision(repoid)
                        download_latest, upload_queue = Entropy.MirrorsService.calculate_database_sync_queues(repoid)

                        repo_data[repoid][crippled_uri]['database'] = {
                            'current_revision': current_revision,
                            'remote_revision': remote_revision,
                            'download_latest': download_latest,
                            'upload_queue': [(self.entropyTools.extract_ftp_host_from_uri(x[0]),x[1],) for x in upload_queue]
                        }

                return True, repo_data

            except Exception, e:
                self.entropyTools.print_traceback()
                return False,unicode(e)
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        data = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return data

    def run_entropy_mirror_updates(self, queue_id, repository_data):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")
        Entropy = self.SystemManagerExecutor.SystemInterface.Entropy

        def sync_remote_databases(repoid, pretend):

            rdb_status = Entropy.MirrorsService.get_remote_databases_status()
            Entropy.updateProgress(
                "%s:" % (_("Remote Entropy Database Repository Status"),),
                header = " * "
            )
            for myuri, myrev in rdb_status:
                Entropy.updateProgress("\t %s:\t %s" % (_("Host"),self.entropyTools.extract_ftp_host_from_uri(myuri),))
                Entropy.updateProgress("\t  * %s: %s" % (_("Database revision"),myrev,))
            local_revision = Entropy.get_local_database_revision(repoid)
            Entropy.updateProgress("\t  * %s: %s" % (_("Database local revision currently at"),local_revision,))
            if pretend:
                return 0,set(),set()

            errors, fine_uris, broken_uris = Entropy.MirrorsService.sync_databases(no_upload = False)
            remote_status = Entropy.MirrorsService.get_remote_databases_status(repoid)
            Entropy.updateProgress(" * %s: " % (_("Remote Entropy Database Repository Status"),))
            for myuri, myrev in remote_status:
                Entropy.updateProgress("\t %s:\t%s" % (_("Host"),Entropy.entropyTools.extract_ftp_host_from_uri(myuri),))
                Entropy.updateProgress("\t  * %s: %s" % (_("Database revision"),myrev,) )

            return errors, fine_uris, broken_uris


        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:

                repo_data = {}
                sys_settings_srv_plugin_id = \
                    etpConst['system_settings_plugins_ids']['server_plugin']
                for repoid in repository_data:

                    # avoid __default__
                    if repoid == etpConst['clientserverrepoid']: continue

                    successfull_mirrors = set()
                    mirrors_errors = False
                    mirrors_tainted = False
                    broken_mirrors = set()
                    check_data = []

                    repo_data[repoid] = {
                        'mirrors_tainted': mirrors_tainted,
                        'mirrors_errors': mirrors_errors,
                        'successfull_mirrors': successfull_mirrors.copy(),
                        'broken_mirrors': broken_mirrors.copy(),
                        'check_data': check_data,
                        'db_errors': 0,
                        'db_fine': set(),
                        'db_broken': set(),
                    }

                    if repository_data[repoid]['pkg']:

                        mirrors_tainted, mirrors_errors, \
                        successfull_mirrors, broken_mirrors, \
                        check_data = Entropy.MirrorsService.sync_packages(
                            ask = False, pretend = repository_data[repoid]['pretend'],
                            packages_check = repository_data[repoid]['pkg_check'], repo = repoid)

                        repo_data[repoid]['mirrors_tainted'] = mirrors_tainted
                        repo_data[repoid]['mirrors_errors'] = mirrors_errors
                        repo_data[repoid]['successfull_mirrors'] = successfull_mirrors
                        repo_data[repoid]['broken_mirrors'] = broken_mirrors
                        repo_data[repoid]['check_data'] = check_data

                        if (not successfull_mirrors) and (not repository_data[repoid]['pretend']): continue

                    if (not mirrors_errors) and repository_data[repoid]['db']:

                        if mirrors_tainted and Entropy.SystemSettings[sys_settings_srv_plugin_id]['server']['rss']['enabled']:
                            commit_msg = repository_data[repoid]['commit_msg']
                            if not commit_msg: commit_msg = "Autodriven update"
                            Entropy.rssMessages['commitmessage'] = commit_msg

                        errors, fine, broken = sync_remote_databases(repoid, repository_data[repoid]['pretend'])
                        repo_data[repoid]['db_errors'] = errors
                        repo_data[repoid]['db_fine'] = fine.copy()
                        repo_data[repoid]['db_broken'] = broken.copy()
                        if errors: continue
                        Entropy.MirrorsService.lock_mirrors(lock = False, repo = repoid)
                        Entropy.MirrorsService.tidy_mirrors(
                            repo = repoid, ask = False,
                            pretend = repository_data[repoid]['pretend']
                        )

                return True, repo_data

            except Exception, e:
                self.entropyTools.print_traceback()
                return False,unicode(e)
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        data = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return data

    def get_spm_glsa_data(self, queue_id, list_type):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        data = {}
        spm = self.SystemManagerExecutor.SystemInterface.Entropy.Spm()
        glsa_ids = spm.list_glsa_packages(list_type)
        if not glsa_ids: return False,data
        for myid in glsa_ids:
            data[myid] = spm.get_glsa_id_information(myid)
        return True,data

    def get_notice_board(self, queue_id, repoid):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:
                data = self.SystemManagerExecutor.SystemInterface.Entropy.MirrorsService.read_notice_board(repo = repoid)
                if data == None:
                    return False,None
                return True,data
            except Exception, e:
                self.entropyTools.print_traceback()
                return False,unicode(e)
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        mydata = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return mydata

    def remove_notice_board_entries(self, queue_id, repoid, entry_ids):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:
                for entry_id in entry_ids:
                    data = self.SystemManagerExecutor.SystemInterface.Entropy.MirrorsService.remove_from_notice_board(entry_id, repo = repoid)
                self.SystemManagerExecutor.SystemInterface.Entropy.MirrorsService.upload_notice_board(repo = repoid)
                return True,data
            except Exception, e:
                self.entropyTools.print_traceback()
                return False,unicode(e)
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        mydata = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return mydata

    def add_notice_board_entry(self, queue_id, repoid, title, notice_text, link):

        queue_data, key = self.SystemManagerExecutor.SystemInterface.get_item_by_queue_id(queue_id, copy = True)
        if queue_data == None:
            return False,'no item in queue'

        stdout_err = open(queue_data['stdout'],"a+")

        def myfunc():
            sys.stdout = stdout_err
            sys.stderr = stdout_err
            mystdin = self._get_stdin(queue_id)
            if mystdin: sys.stdin = os.fdopen(mystdin, 'rb')
            try:
                data = self.SystemManagerExecutor.SystemInterface.Entropy.MirrorsService.update_notice_board(title, notice_text, link = link, repo = repoid)
                return True,data
            except Exception, e:
                self.entropyTools.print_traceback()
                return False,unicode(e)
            finally:
                sys.stdout.write("\n### Done ###\n")
                sys.stdout.flush()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                sys.stdin = sys.__stdin__

        def write_pid(pid):
            self._set_processing_pid(queue_id, pid)

        mydata = self.entropyTools.spawn_function(myfunc, write_pid_func = write_pid)
        stdout_err.flush()
        stdout_err.close()
        return mydata

    def _get_stdin(self, queue_id):
        mystdin = None
        std_data = self.SystemManagerExecutor.SystemInterface.ManagerQueueStdInOut.get(queue_id)
        if std_data != None: mystdin = std_data[0]
        return mystdin

    def _file_updateProgress(self, f, *myargs, **mykwargs):

        f.flush()
        back = mykwargs.get("back")
        count = mykwargs.get("count")
        header = mykwargs.get("header")
        percent = mykwargs.get("percent")
        text = myargs[0].encode('utf-8')
        if not header: header = ''

        count_str = ""
        if count:
            if len(count) > 1:
                if percent:
                    count_str = " ("+str(round((float(count[0])/count[1])*100,1))+"%) "
                else:
                    count_str = " (%s/%s) " % (red(str(count[0])),blue(str(count[1])),)

        def is_last_newline(f):
            try:
                f.seek(-1,os.SEEK_END)
                last = f.read(1)
                if last == "\n":
                    return True
            except IOError:
                pass
            return False

        if back:
            self.entropyTools.seek_till_newline(f)
            txt = header+count_str+text
        else:
            if not is_last_newline(f): f.write("\n")
            txt = header+count_str+text+"\n"
        f.write(txt)

        f.flush()

    # !!! duplicate
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

    def _get_spm_pkginfo(self, matched_atom, from_installed = False):
        data = {}
        data['atom'] = matched_atom
        data['key'] = self.entropyTools.dep_getkey(matched_atom)
        spm = self.SystemManagerExecutor.SystemInterface.Entropy.Spm()
        try:
            if from_installed:
                data['slot'] = spm.get_installed_package_slot(matched_atom)
                portage_matched_atom = spm.get_best_atom("%s:%s" % (data['key'],data['slot'],))
                # get installed package description
                data['available_atom'] = portage_matched_atom
                if portage_matched_atom:
                    data['use'] = spm.get_package_useflags(portage_matched_atom)
                else:
                    # get use flags of the installed package
                    data['use'] = spm.get_installed_package_useflags(matched_atom)
                data['description'] = spm.get_installed_package_description(matched_atom)
            else:
                data['slot'] = spm.get_package_slot(matched_atom)
                data['use'] = spm.get_package_useflags(matched_atom)
                data['installed_atom'] = spm.get_installed_atom("%s:%s" % (data['key'],data['slot'],))
                data['description'] = spm.get_package_description(matched_atom)
        except KeyError:
            pass

        return data