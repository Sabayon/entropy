# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Services System Management Interface}.

"""
import time
import os
import random
import subprocess
from entropy.services.interfaces import SocketHost
from entropy.const import etpConst, const_setup_perms
from entropy.output import TextInterface
from entropy.misc import ParallelTask

class TaskExecutor:

    def __init__(self, SystemInterface, Entropy):
        import entropy.tools as entropyTools
        self.entropyTools = entropyTools
        self.Entropy = Entropy
        self.SystemInterface = SystemInterface
        self.available_commands = {}
        self.task_result = None

    def register(self, available_commands):
        self.available_commands.update(available_commands)

    def execute_task(self, command_data):

        import signal
        queue_id = command_data['queue_id']
        args = command_data['args']
        kwargs = command_data['kwargs']
        data = self.available_commands.get(command_data['call'])

        if data == None:
            return False, 'no command'
        elif len(args)+1 < data['args']:
            return False, 'not enough args'

        args.insert(0, queue_id)
        self.task_result = None
        t = ParallelTask(data['func'], *args, **kwargs)
        t.start()
        killed = False
        while True:
            if not t.isAlive(): break
            time.sleep(2)
            live_item, key = self.SystemInterface.get_item_by_queue_id(queue_id)
            if isinstance(live_item, dict) and (key == "processing") and (not killed):
                if live_item['kill'] and (live_item['processing_pid'] != None):
                    os.kill(live_item['processing_pid'], signal.SIGKILL)
                    killed = True
        if killed:
            return False, 'killed by user'
        return True, t.get_rc()

class Server(SocketHost):

    class FakeServiceInterface:
        def __init__(self, *args, **kwargs):
            pass

    class BuiltInSystemManagerExecutorCommands:

        def __init__(self, SystemManagerExecutorInstance, *args, **kwargs):
            self.SystemManagerExecutor = SystemManagerExecutorInstance
            self.available_commands = {
                'hello_world': {
                    'func': self.hello_world,
                    'args': 0,
                }
            }

        def hello_world(self):
            rc = subprocess.call('echo hello world', shell = True)
            return True, rc


    queue_file = 'system_manager_queue'
    pinboard_file = "system_manager_pinboard"
    queue_ext_rc_dir = "system_manager_rc"
    STDOUT_STORAGE_DIR = os.path.join(etpConst['dumpstoragedir'], 'system_manager_stdout')
    def __init__(self, EntropyInterface, do_ssl = False, stdout_logging = True, entropy_interface_kwargs = {}, **kwargs):

        self.queue_loaded = False
        from entropy.misc import TimeScheduled
        self.TimeScheduled = TimeScheduled

        import entropy.tools as entropyTools
        import entropy.dump as dumpTools
        import threading
        self.entropyTools, self.dumpTools, self.threading = entropyTools, dumpTools, threading
        from datetime import datetime
        self.datetime = datetime
        import copy
        self.copy = copy
        from entropy.services.system.commands import Base
        self.setup_stdout_storage_dir()

        if 'external_cmd_classes' not in kwargs:
            kwargs['external_cmd_classes'] = []
        kwargs['external_cmd_classes'].insert(0, Base)

        self.Entropy = EntropyInterface(**entropy_interface_kwargs)
        self.Text = TextInterface()
        self.SystemExecutor = TaskExecutor(self, self.Entropy)

        self.ExecutorCommandClasses = [(self.BuiltInSystemManagerExecutorCommands, [], {},)]
        self.ExecutorCommandInstances = []
        if 'external_executor_cmd_classes' in kwargs:
            self.ExecutorCommandClasses += kwargs.pop('external_executor_cmd_classes')
        self.handle_executor_command_classes_initialization()

        self.QueueProcessor = None
        self.QueueLock = self.threading.Lock()
        self.PinboardLock = self.threading.Lock()
        self.ForkLock = self.threading.Lock()
        self.do_ssl = do_ssl

        self.PinboardData = {}
        self.load_pinboard()

        self.done_queue_keys = ['processed', 'errored']
        self.removable_queue_keys = ['processed', 'errored', 'queue']
        self.processing_queue_keys = ['processing']
        self.dict_queue_keys = ['queue', 'processing', 'processed', 'errored']
        self.ManagerQueueStdInOut = {}
        self.ManagerQueue = {
            'queue': {},
            'queue_order': [],
            'processing': {},
            'processing_order': [],
            'processed': {},
            'processed_order': [],
            'errored' : {},
            'errored_order': [],
            'pause': True
        }
        self.load_queue()
        self.queue_loaded = True
        if self.ManagerQueue['processing'] or self.ManagerQueue['processing_order']:
            self.ManagerQueue['processing'].clear()
            del self.ManagerQueue['processing_order'][:]
            self.store_queue()

        SocketHost.__init__(
            self,
            self.FakeServiceInterface,
            sock_output = self.Text,
            ssl = do_ssl,
            **kwargs
        )
        self.stdout_logging = stdout_logging
        # no way, we MUST fork requests, otherwise weird things will happen when more than
        # one user is connected
        # self.fork_requests = False
        self.load_queue_processor()
        # here we can put anything that must be loaded before the queue processor execution
        self.play_queue()

    def __del__(self):
        if hasattr(self, 'queue_loaded'):
            if self.queue_loaded:
                self.store_queue()

    def handle_executor_command_classes_initialization(self):
        for myclass, args, kwargs in self.ExecutorCommandClasses:
            myintf = myclass(self.SystemExecutor, *args,**kwargs)
            if hasattr(myintf, 'available_commands'):
                self.SystemExecutor.register(myintf.available_commands)
                self.ExecutorCommandInstances.append(myintf)
            else:
                del myintf

    def setup_stdout_storage_dir(self):
        if os.path.isfile(self.STDOUT_STORAGE_DIR) or os.path.islink(self.STDOUT_STORAGE_DIR):
            os.remove(self.STDOUT_STORAGE_DIR)
        if not os.path.isdir(self.STDOUT_STORAGE_DIR):
            os.makedirs(self.STDOUT_STORAGE_DIR, 0o775)
            if etpConst['entropygid'] != None:
                const_setup_perms(self.STDOUT_STORAGE_DIR, etpConst['entropygid'])

    def load_pinboard(self):
        obj = self.get_stored_pinboard()
        if isinstance(obj, dict):
            self.PinboardData = obj
            return True
        return False

    def get_stored_pinboard(self):
        return self.dumpTools.loadobj(self.pinboard_file)

    def store_pinboard(self):
        self.dumpTools.dumpobj(self.pinboard_file, self.PinboardData)

    def add_to_pinboard(self, note, extended_text):
        with self.PinboardLock:
            mydata = {
                'note': note,
                'extended_text': extended_text,
                'ts': self.get_ts(),
                'done': False,
            }
            pinboard_id = self.get_pinboard_id()
            self.PinboardData[pinboard_id] = mydata
            self.store_pinboard()

    def remove_from_pinboard(self, pinboard_id):
        with self.PinboardLock:
            if pinboard_id in self.PinboardData:
                self.PinboardData.pop(pinboard_id)
                self.store_pinboard()
                return True
            return False

    def set_pinboard_item_status(self, pinboard_id, status):
        with self.PinboardLock:
            if pinboard_id in self.PinboardData:
                self.PinboardData[pinboard_id]['done'] = status
                self.store_pinboard()
                return True
            return False

    def get_pinboard_id(self):
        numbers = list(self.PinboardData.keys())
        if numbers:
            number = max(numbers)+1
        else:
            number = 1
        return number

    def get_pinboard_data(self):
        with self.PinboardLock:
            return self.PinboardData.copy()

    def load_queue_processor(self):
        self.QueueProcessor = self.TimeScheduled(2, self.queue_processor)
        self.QueueProcessor.start()

    def get_stored_queue(self):
        return self.dumpTools.loadobj(self.queue_file)

    def load_queue(self):
        obj = self.get_stored_queue()
        if isinstance(obj, dict):
            self.ManagerQueue = obj
            return True
        return False

    def store_queue(self):
        self.dumpTools.dumpobj(self.queue_file, self.ManagerQueue)

    def load_queue_ext_rc(self, queue_id):
        return self.dumpTools.loadobj(os.path.join(self.queue_ext_rc_dir, str(queue_id)))

    def store_queue_ext_rc(self, queue_id, rc):
        return self.dumpTools.dumpobj(os.path.join(self.queue_ext_rc_dir, str(queue_id)), rc)

    def remove_queue_ext_rc(self, queue_id):
        return self.dumpTools.removeobj(os.path.join(self.queue_ext_rc_dir, str(queue_id)))

    def get_ts(self):
        return self.datetime.fromtimestamp(time.time())

    def swap_items_in_queue(self, queue_id1, queue_id2):
        self.load_queue()
        item1, key1 = self._get_item_by_queue_id(queue_id1)
        item2, key2 = self._get_item_by_queue_id(queue_id2)
        if key1 != key2:
            return False
        t_item = item1.copy()
        item1.clear()
        item1.update(item2)
        item2.clear()
        item2.update(t_item)
        # fix the _order
        queue_id1_idx = self.ManagerQueue[key1+"_order"].index(queue_id1)
        queue_id2_idx = self.ManagerQueue[key2+"_order"].index(queue_id2)
        self.ManagerQueue[key1+"_order"][queue_id1_idx] = queue_id2
        self.ManagerQueue[key2+"_order"][queue_id2_idx] = queue_id1
        self.store_queue()
        return True


    def add_to_queue(self, command_name, command_text, user_id, group_id, function, args, kwargs, do_parallel, extended_result, interactive = False):

        if function not in self.SystemExecutor.available_commands:
            return -1

        self.load_queue()
        queue_id = self.generate_unique_queue_id()
        if interactive:
            self.ManagerQueueStdInOut[queue_id] = os.pipe()
        myqueue_dict = {
            'queue_id': queue_id,
            'command_name': command_name,
            'command_desc': self.valid_commands[command_name]['desc'],
            'command_text': command_text,
            'call': function,
            'args': self.copy.deepcopy(args),
            'kwargs': self.copy.deepcopy(kwargs),
            'user_id': user_id,
            'group_id': group_id,
            'stdout': self.assign_unique_stdout_file(queue_id),
            'queue_ts': "%s" % (self.get_ts(),),
            'kill': False,
            'processing_pid': None,
            'do_parallel': do_parallel,
            'interactive': False,
        }
        if extended_result:
            myqueue_dict['extended_result'] = None
        self.ManagerQueue['queue'][queue_id] = myqueue_dict
        self.ManagerQueue['queue_order'].append(queue_id)
        self.store_queue()
        return queue_id

    def remove_from_queue(self, queue_ids):
        self.load_queue()
        removed = False
        for key in self.ManagerQueue:
            if key not in self.dict_queue_keys:
                continue
            for queue_id in queue_ids:
                item = None
                try:
                    item = self.ManagerQueue[key].pop(queue_id)
                except KeyError:
                    continue
                if item:
                    self.flush_item(item, queue_id)
                    if queue_id in self.ManagerQueue[key+"_order"]:
                        self.ManagerQueue[key+"_order"].remove(queue_id)
                removed = True
                self.remove_queue_ext_rc(queue_id)
        if removed: self.store_queue()
        return removed

    def kill_processing_queue_id(self, queue_id):
        self.load_queue()
        item, key = self._get_item_by_queue_id(queue_id)
        if key in self.processing_queue_keys:
            item['kill'] = True
        self.store_queue()

    def pause_queue(self):
        self.load_queue()
        self.ManagerQueue['pause'] = True
        self.store_queue()

    def play_queue(self):
        self.load_queue()
        self.ManagerQueue['pause'] = False
        self.store_queue()

    def flush_item(self, item, queue_id):
        if not isinstance(item, dict):
            return False
        if 'stdout' in item:
            stdout = item['stdout']
            if (os.path.isfile(stdout) and os.access(stdout, os.W_OK)):
                os.remove(stdout)
        if 'interactive' in item:
            if item['interactive'] and (queue_id in self.ManagerQueueStdInOut):
                stdin, stdout = self.ManagerQueueStdInOut.pop(queue_id)
                os.close(stdin)
                os.close(stdout)
        return True

    def assign_unique_stdout_file(self, queue_id):
        stdout = os.path.join(self.STDOUT_STORAGE_DIR, "%d.%s" % (queue_id, "stdout",))
        if os.path.isfile(stdout):
            os.remove(stdout)
        count = 0
        orig_stdout = stdout
        while os.path.lexists(stdout):
            count += 1
            stdout = "%s.%d" % (orig_stdout, count,)
        return stdout

    def generate_unique_queue_id(self):
        current_ids = set()
        for key in self.ManagerQueue:
            if not key.endswith("_order"):
                continue
            current_ids |= set(self.ManagerQueue[key])
        while True:
            try:
                queue_id = abs(hash(os.urandom(1)))
            except NotImplementedError:
                random.seed()
                queue_id = random.randint(1000000000000000000, 9999999999999999999)
            if queue_id not in current_ids:
                return queue_id

    def get_item_by_queue_id(self, queue_id, copy = False):
        self.load_queue()
        item, key = self._get_item_by_queue_id(queue_id)
        if copy: item = self._queue_copy_obj(item)
        return item, key

    def _get_item_by_queue_id(self, queue_id):
        for key in self.dict_queue_keys:
            item = self.ManagerQueue[key].get(queue_id)
            if item != None:
                return item, key
        return None, None

    def _pop_item_from_queue(self):
        try:
            if self.ManagerQueue['queue_order']:
                queue_id = self.ManagerQueue['queue_order'].pop(0)
                return self.ManagerQueue['queue'].pop(queue_id), queue_id
        except (IndexError, KeyError,):
            self.entropyTools.print_traceback()
        return None, None

    def _queue_copy_obj(self, obj):
        if isinstance(obj, (dict, set, frozenset)):
            return obj.copy()
        elif isinstance(obj, (list, tuple)):
            return obj[:]
        return obj

    def queue_processor(self, fork_data = None):

        try:
            self._queue_processor(fork_data)
        except:
            if self.QueueLock.locked() and not fork_data:
                self.QueueLock.release()
            raise

    def _queue_processor(self, fork_data):

        # queue processing is stopped until there's a process running
        if self.ForkLock.locked(): return

        with self.ForkLock:
            with self.QueueLock:

                if fork_data:
                    command_data, queue_id = self._queue_copy_obj(fork_data)
                else:
                    self.load_queue()
                    if self.ManagerQueue['pause']: return
                    if not self.ManagerQueue['queue_order']: return
                    command_data, queue_id = self._pop_item_from_queue()
                    if not command_data: return
                    command_data = self._queue_copy_obj(command_data)
                    command_data['processing_ts'] = "%s" % (self.get_ts(),)
                    self.ManagerQueue['processing'][queue_id] = command_data
                    self.ManagerQueue['processing_order'].append(queue_id)
                    self.store_queue()

        self.remove_queue_ext_rc(queue_id)
        try:
            if command_data.get('do_parallel') and not fork_data:
                t = ParallelTask(self.queue_processor, fork_data = (command_data, queue_id,))
                t.start()
                return
            done, result = self.SystemExecutor.execute_task(command_data)
        except Exception as e:
            if self.QueueLock.locked(): self.QueueLock.release()
            self.entropyTools.print_traceback()
            done = False
            result = (False, str(e),)

        if 'extended_result' in command_data and done:
            try:
                command_data['result'], extended_result = self._queue_copy_obj(result)
                self.store_queue_ext_rc(queue_id, extended_result)
            except TypeError:
                done = False
                command_data['result'] = 'wrong tuple split from queue processor (1)'
                self.store_queue_ext_rc(queue_id, None)
        else:
            command_data['result'] = self._queue_copy_obj(result)

        with self.ForkLock:
            with self.QueueLock:

                self.load_queue()

                if not done:
                    try:
                        self.ManagerQueue['processing'].pop(queue_id)
                    except KeyError:
                        pass
                    if queue_id in self.ManagerQueue['processing_order']:
                        self.ManagerQueue['processing_order'].remove(queue_id)
                    command_data['errored_ts'] = "%s" % (self.get_ts(),)
                    self.ManagerQueue['errored'][queue_id] = command_data
                    self.ManagerQueue['errored_order'].append(queue_id)
                    self.store_queue()
                    return

                try:
                    done, cmd_result = result
                except TypeError:
                    done = False
                    command_data['result'] = 'wrong tuple split from queue processor (2)'

                if not done:
                    try:
                        self.ManagerQueue['processing'].pop(queue_id)
                    except KeyError:
                        pass
                    if queue_id in self.ManagerQueue['processing_order']:
                        self.ManagerQueue['processing_order'].remove(queue_id)
                    command_data['errored_ts'] = "%s" % (self.get_ts(),)
                    self.ManagerQueue['errored'][queue_id] = command_data
                    self.ManagerQueue['errored_order'].append(queue_id)
                    self.store_queue()
                    return

                try:
                    self.ManagerQueue['processing'].pop(queue_id)
                except KeyError:
                    pass
                if queue_id in self.ManagerQueue['processing_order']:
                    self.ManagerQueue['processing_order'].remove(queue_id)
                command_data['processed_ts'] = "%s" % (self.get_ts(),)
                self.ManagerQueue['processed'][queue_id] = command_data
                self.ManagerQueue['processed_order'].append(queue_id)
                self.store_queue()


    def killall(self):
        SocketHost.killall(self)
        if self.QueueProcessor != None:
            self.QueueProcessor.kill()
