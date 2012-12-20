#!/usr/bin/python

import sys
import os
import shlex
import signal
import argparse
import shutil
import tempfile
import subprocess
import errno
import fcntl
from threading import Lock

os.environ['ETP_GETTEXT_DOMAIN'] = "entropy-server"
# this application does not like interactivity
os.environ['ETP_NONITERACTIVE'] = "1"

# Entropy imports
sys.path.insert(0, '/usr/lib/entropy/lib')
sys.path.insert(0, '/usr/lib/entropy/server')
sys.path.insert(0, '/usr/lib/entropy/client')
sys.path.insert(0, '../lib')
sys.path.insert(0, '../server')
sys.path.insert(0, '../client')

# Entropy imports
from entropy.exceptions import PermissionDenied
from entropy.const import etpConst, const_convert_to_unicode, \
    const_get_stringtype, const_setup_perms
from entropy.output import print_info, print_error, print_warning, \
    purple, darkgreen, is_stdout_a_tty, getcolor
from entropy.exceptions import SPMError
from entropy.server.interfaces import Server

import entropy.tools
import entropy.dep

# Portage imports
os.environ['ACCEPT_PROPERTIES'] = "* -interactive"
os.environ['FEATURES'] = "split-log"
os.environ['CMAKE_NO_COLOR'] = "yes"

from _emerge.depgraph import backtrack_depgraph
from _emerge.actions import load_emerge_config
try:
    from _emerge.actions import validate_ebuild_environment
except ImportError:
    # older portage versions
    from _emerge.main import validate_ebuild_environment
try:
    from _emerge.post_emerge import post_emerge
except ImportError:
    # older portage versions
    from _emerge.main import post_emerge
from _emerge.create_depgraph_params import create_depgraph_params
from _emerge.main import parse_opts
from _emerge.stdout_spinner import stdout_spinner
from _emerge.Scheduler import Scheduler
from _emerge.clear_caches import clear_caches
from _emerge.unmerge import unmerge
from _emerge.Blocker import Blocker

import portage.versions
import portage.dep
import portage


def mkstemp():
    """
    Create temporary file into matter temporary directory.
    This is a tempfile.mkstemp() wrapper
    """
    tmp_dir = "/var/tmp/matter"
    if not os.path.isdir(tmp_dir):
        try:
            os.makedirs(tmp_dir)
        except OSError as err:
            # race condition
            if err.errno != errno.EEXIST:
                raise
        const_setup_perms(tmp_dir, etpConst['entropygid'],
            recursion = False)
    return tempfile.mkstemp(prefix="matter", dir=tmp_dir)


class EntropyResourceLock(object):
    """
    This class exposes a Lock-like interface for acquiring Entropy Server
    resources.
    """

    class NotAcquired(Exception):
        """ Raised when Entropy Resource Lock cannot be acquired """

    def __init__(self, entropy_server, blocking):
        """
        EntropyResourceLock constructor.

        @param entropy_server: Entropy Server instance
        @type entropy_server: entropy.server.interfaces.Server
        @param blocking: acquire lock in blocking mode?
        @type blocking: bool
        """
        self._entropy = entropy_server
        self._blocking = blocking
        self.__inside_with_stmt = 0

    def acquire(self):
        acquired = entropy.tools.acquire_entropy_locks(self._entropy,
            blocking = self._blocking)
        if not acquired:
            raise EntropyResourceLock.NotAcquired("unable to acquire lock")

    def release(self):
        entropy.tools.release_entropy_locks(self._entropy)

    def __enter__(self):
        """
        Acquire lock. Not thread-safe.
        """
        if self.__inside_with_stmt < 1:
            self.acquire()
        self.__inside_with_stmt += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Release lock. Not thread-safe.
        """
        self.__inside_with_stmt -= 1
        if self.__inside_with_stmt < 1:
            self.release()


class MatterResourceLock(object):
    """
    This class exposes a Lock-like interface for acquiring Matter lock file.
    """

    LOCK_FILE_PATH = "/var/tmp/.matter_resource.lock"

    class NotAcquired(Exception):
        """ Raised when Lock cannot be acquired """

    def __init__(self, blocking):
        """
        MatterResourceLock constructor.

        @param blocking: acquire lock in blocking mode?
        @type blocking: bool
        """
        self._blocking = blocking
        self.__inside_with_stmt = 0
        self.__lock_f = None
        self.__call_lock = Lock()

    def acquire(self):
        """
        Acquire the lock file.
        """
        file_path = MatterResourceLock.LOCK_FILE_PATH
        if self._blocking:
            flags = fcntl.LOCK_EX | fcntl.LOCK_NB
        else:
            flags = fcntl.LOCK_EX

        with self.__call_lock:
            if self.__lock_f is None:
                self.__lock_f = open(file_path, "wb")
                try:
                    fcntl.flock(self.__lock_f.fileno(), flags)
                except IOError as err:
                    if err.errno not in (errno.EACCES, errno.EAGAIN,):
                        # ouch, wtf?
                        raise
                    raise MatterResourceLock.NotAcquired(
                        "unable to acquire lock")

    def release(self):
        with self.__call_lock:
            if self.__lock_f is not None:
                fcntl.flock(self.__lock_f.fileno(), fcntl.LOCK_UN)
                self.__lock_f.close()
                self.__lock_f = None

    def __enter__(self):
        """
        Acquire lock. Not thread-safe.
        """
        if self.__inside_with_stmt < 1:
            self.acquire()
        self.__inside_with_stmt += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Release lock. Not thread-safe.
        """
        self.__inside_with_stmt -= 1
        if self.__inside_with_stmt < 1:
            self.release()


class GenericSpecFunctions(object):

    def ne_string(self, x):
        return x, 'raw_unicode_escape'

    def ne_list(self, x):
        return x

    def not_none(self, x):
        return x is not None

    def valid_integer(self, x):
        try:
            int(x)
        except (TypeError, ValueError,):
            return False
        return True

    def always_valid(self, *_args):
        return True

    def valid_path(self, x):
        return os.path.lexists(x)

    def valid_file(self, x):
        return os.path.isfile(x)

    def valid_dir(self, x):
        return os.path.isdir(x)

    def ve_string_open_file_read(self, x):
        try:
            open(x, "rb").close()
            return x
        except (IOError, OSError):
            return None

    def ve_string_stripper(self, x):
        return const_convert_to_unicode(x).strip()

    def ve_string_splitter(self, x):
        return const_convert_to_unicode(x).strip().split()

    def ve_integer_converter(self, x):
        return int(x)

    def valid_ascii(self, x):
        try:
            x = str(x)
            return x
        except (UnicodeDecodeError, UnicodeEncodeError,):
            return ''

    def valid_yes_no(self, x):
        return x in ("yes", "no")

    def valid_yes_no_inherit(self, x):
        return x in ("yes", "no", "inherit")

    def valid_path_string(self, x):
        try:
            os.path.split(x)
        except OSError:
            return False
        return True

    def valid_path_string_first_list_item(self, x):
        if not x:
            return False
        myx = x[0]
        try:
            os.path.split(myx)
        except OSError:
            return False
        return True

    def valid_comma_sep_list_list(self, input_str):
        parts = []
        for part in const_convert_to_unicode(input_str).split(","):
            part = part.strip()
            # do not filter out empty elements
            parts.append(part.split())
        return parts

    def valid_path_list(self, x):
        return [y.strip() for y in \
            const_convert_to_unicode(x).split(",") if \
                self.valid_path_string(y) and y.strip()]


class MatterSpec(GenericSpecFunctions):

    def vital_parameters(self):
        """
        Return a list of vital .spec file parameters

        @return: list of vital .spec file parameters
        @rtype: list
        """
        return ["packages", "repository"]

    def parser_data_path(self):
        """
        Return a dictionary containing parameter names as key and
        dict containing keys 've' and 'cb' which values are three
        callable functions that respectively do value extraction (ve),
        value verification (cb) and value modding (mod).

        @return: data path dictionary (see ChrootSpec code for more info)
        @rtype: dict
        """
        return {
            'dependencies': {
                'cb': self.valid_yes_no,
                've': self.ve_string_stripper,
                'default': "no",
            },
            'downgrade': {
                'cb': self.valid_yes_no,
                've': self.ve_string_stripper,
                'default': "no",
            },
            'keep-going': {
                'cb': self.valid_yes_no,
                've': self.ve_string_stripper,
                'default': "no",
            },
            'new-useflags': {
                'cb': self.valid_yes_no,
                've': self.ve_string_stripper,
                'default': "no",
            },
            'removed-useflags': {
                'cb': self.valid_yes_no,
                've': self.ve_string_stripper,
                'default': "no",
            },
            'rebuild': {
                'cb': self.valid_yes_no,
                've': self.ve_string_stripper,
                'default': "no",
            },
            'spm-repository-change': {
                'cb': self.valid_yes_no,
                've': self.ve_string_stripper,
                'default': "no",
            },
            'spm-repository-change-if-upstreamed': {
                'cb': self.valid_yes_no,
                've': self.ve_string_stripper,
                'default': "no",
            },
            'not-installed': {
                'cb': self.valid_yes_no,
                've': self.ve_string_stripper,
                'default': "no",
            },
            'pkgpre': {
                'cb': self.not_none,
                've': self.ve_string_open_file_read,
                'default': None,
            },
            'pkgpost': {
                'cb': self.not_none,
                've': self.ve_string_open_file_read,
                'default': None,
            },
            'buildfail': {
                'cb': self.not_none,
                've': self.ve_string_open_file_read,
                'default': None,
            },
            'packages': {
                'cb': self.always_valid,
                've': self.valid_comma_sep_list_list,
                'mod': lambda l_l: [x for x in l_l if x],
            },
            'repository': {
                'cb': self.ne_string,
                've': self.ve_string_stripper,
            },
            'stable': {
                'cb': self.valid_yes_no_inherit,
                've': self.ve_string_stripper,
                'default': "inherit",
            },
        }


class SpecPreprocessor:

    PREFIX = "%"
    class PreprocessorError(Exception):
        """ Error while preprocessing file """

    def __init__(self, spec_file_obj):
        self.__expanders = {}
        self.__builtin_expanders = {}
        self._spec_file_obj = spec_file_obj
        self._add_builtin_expanders()

    def add_expander(self, statement, expander_callback):
        """
        Add Preprocessor expander.

        @param statement: statement to expand
        @type statement: string
        @param expand_callback: one argument callback that is used to expand
            given line (line is raw format). Line is already pre-parsed and
            contains a valid preprocessor statement that callback can handle.
            Preprocessor callback should raise SpecPreprocessor.PreprocessorError
            if line is malformed.
        @type expander_callback: callable
        @raise KeyError: if expander is already available
        @return: a raw string (containing \n and whatever)
        @rtype: string
        """
        return self._add_expander(statement, expander_callback, builtin = False)

    def _add_expander(self, statement, expander_callback, builtin = False):
        obj = self.__expanders
        if builtin:
            obj = self.__builtin_expanders
        if statement in obj:
            raise KeyError("expander %s already provided" % (statement,))
        obj[SpecPreprocessor.PREFIX + statement] = \
            expander_callback

    def _add_builtin_expanders(self):
        # import statement
        self._add_expander("import", self._import_expander, builtin = True)

    def _import_expander(self, line):

        rest_line = line.split(" ", 1)[1].strip()
        if not rest_line:
            return line

        spec_f = self._spec_file_obj
        spec_f.seek(0)
        lines = ''
        try:
            for line in spec_f.readlines():
                # call recursively
                split_line = line.split(" ", 1)
                if split_line:
                    expander = self.__builtin_expanders.get(split_line[0])
                    if expander is not None:
                        try:
                            line = expander(line)
                        except RuntimeError as err:
                            raise SpecPreprocessor.PreprocessorError(
                                "invalid preprocessor line: %s" % (err,))
                lines += line
        finally:
            spec_f.seek(0)

        return lines

    def parse(self):

        content = []
        spec_f = self._spec_file_obj
        spec_f.seek(0)

        try:
            for line in spec_f.readlines():
                split_line = line.split(" ", 1)
                if split_line:
                    expander = self.__builtin_expanders.get(split_line[0])
                    if expander is not None:
                        line = expander(line)
                content.append(line)
        finally:
            spec_f.seek(0)

        final_content = []
        for line in content:
            split_line = line.split(" ", 1)
            if split_line:
                expander = self.__expanders.get(split_line[0])
                if expander is not None:
                    line = expander(line)
            final_content.append(line)

        final_content = (''.join(final_content)).split("\n")

        return final_content


class SpecParser:

    def __init__(self, file_object):

        self.file_object = file_object
        self._preprocessor = SpecPreprocessor(self.file_object)

        self.__plugin = MatterSpec()
        self.vital_parameters = self.__plugin.vital_parameters()
        self._parser_data_path = self.__plugin.parser_data_path()

    def _parse_line_statement(self, line_stmt):
        try:
            key, value = line_stmt.split(":", 1)
        except ValueError:
            return None, None
        key, value = key.strip(), value.strip()
        return key, value

    def parse(self):

        def _is_list_list(lst):
            for x in lst:
                if isinstance(x, list):
                    return True
            return False

        mydict = {}
        data = self._generic_parser()
        # compact lines properly
        old_key = None
        for line in data:
            key = None
            value = None
            v_key, v_value = self._parse_line_statement(line)
            check_dict = self._parser_data_path.get(v_key)
            if check_dict is not None:
                key, value = v_key, v_value
                old_key = key
            elif isinstance(old_key, const_get_stringtype()):
                key = old_key
                value = line.strip()
                if not value:
                    continue
            # gather again... key is changed
            check_dict = self._parser_data_path.get(key)
            if not isinstance(check_dict, dict):
                continue
            value = check_dict['ve'](value)
            if not check_dict['cb'](value):
                continue

            if key in mydict:

                if isinstance(value, const_get_stringtype()):
                    mydict[key] += " %s" % (value,)

                elif isinstance(value, list) and _is_list_list(value):
                    # support multi-line "," separators
                    # append the first element of value to the last
                    # element of mydict[key] if it's there.
                    first_el = value.pop(0)
                    if mydict[key] and first_el:
                        mydict[key][-1] += first_el
                    mydict[key] += value

                elif isinstance(value, list):
                    mydict[key] += value
                else:
                    continue
            else:
                mydict[key] = value
        self._validate_parse(mydict)
        self._extend_parse(mydict)
        self._mod_parse(mydict)
        return mydict.copy()

    def _extend_parse(self, mydata):
        """
        Extend parsed data with default values for statements with
        default option available.
        """
        for statement, opts in self._parser_data_path.items():
            if "default" in opts and (statement not in mydata):
                mydata[statement] = opts['default']

    def _mod_parse(self, mydata):
        """
        For parser data exposing a mod, execute the mod against
        the data itself.
        """
        for statement, opts in self._parser_data_path.items():
            if statement in mydata and "mod" in opts:
                mydata[statement] = opts['mod'](mydata[statement])

    def _validate_parse(self, mydata):
        for param in self.vital_parameters:
            if param not in mydata:
                raise ValueError(
                    "'%s' missing or invalid"
                    " '%s' parameter, it's vital. Your specification"
                    " file is incomplete!" % (self.file_object.name, param,)
                )

    def _generic_parser(self):
        data = []
        content = self._preprocessor.parse()
        # filter comments and white lines
        content = [x.strip().rsplit("#", 1)[0].strip() for x in content if \
            not x.startswith("#") and x.strip()]
        for line in content:
            if line in data:
                continue
            data.append(line)
        return data


class PackageBuilder(object):
    """
    Portage Package builder class
    """

    DEFAULT_PORTAGE_SYNC_CMD = "emerge --sync"
    PORTAGE_SYNC_CMD = shlex.split(os.getenv("MATTER_PORTAGE_SYNC_CMD",
        DEFAULT_PORTAGE_SYNC_CMD))

    DEFAULT_OVERLAYS_SYNC_CMD = "layman -S"
    OVERLAYS_SYNC_CMD = shlex.split(os.getenv("MATTER_OVERLAYS_SYNC_CMD",
        DEFAULT_OVERLAYS_SYNC_CMD))

    DEFAULT_PORTAGE_BUILD_ARGS = "--verbose --nospinner"
    PORTAGE_BUILD_ARGS = os.getenv("MATTER_PORTAGE_BUILD_ARGS",
        DEFAULT_PORTAGE_BUILD_ARGS).split()

    PORTAGE_BUILTIN_ARGS = ["--accept-properties=-interactive"]

    def __init__(self, entropy_server, emerge_config, packages, params,
        spec_number, tot_spec, pkg_number, tot_pkgs):
        self._entropy = entropy_server
        self._emerge_config = emerge_config
        self._packages = packages
        self._params = params
        self._spec_number = spec_number
        self._tot_spec = tot_spec
        self._pkg_number = pkg_number
        self._tot_pkgs = tot_pkgs
        self._built_packages = []
        self._not_found_packages = []
        self._not_installed_packages = []
        self._not_merged_packages = []

    @staticmethod
    def _build_standard_environment(repository=None):
        env = os.environ.copy()
        if repository is not None:
            env["MATTER_REPOSITORY_ID"] = repository
        return env

    @staticmethod
    def setup(executable_hook_f, cwd):

        # ignore exit status
        subprocess.call(["env-update"])

        hook_name = executable_hook_f.name
        if not hook_name.endswith("/"):
            # complete with current directory
            hook_name = os.path.join(cwd, hook_name)

        print_info("spawning pre hook: %s" % (hook_name,))
        return subprocess.call([hook_name],
            env = PackageBuilder._build_standard_environment())

    @staticmethod
    def teardown(executable_hook_f, cwd, exit_st):
        hook_name = executable_hook_f.name
        if not hook_name.endswith("/"):
            # complete with current directory
            hook_name = os.path.join(cwd, hook_name)

        print_info("spawning post hook: %s, passing exit status: %d" % (
            hook_name, exit_st,))
        env = PackageBuilder._build_standard_environment()
        env["MATTER_EXIT_STATUS"] = str(exit_st)
        return subprocess.call([hook_name], env = env)

    def _build_execution_header_output(self):
        """
        Return a string used as stdout/stderr header text.
        """
        my_str = "{%s of %s particles | %s of %s packages} " % (
            darkgreen(str(self._spec_number)),
            purple(str(self._tot_spec)),
            darkgreen(str(self._pkg_number)),
            purple(str(self._tot_pkgs)),)
        return my_str

    def get_built_packages(self):
        """
        Return the list of successfully built packages.
        """
        return self._built_packages

    def get_not_found_packages(self):
        """
        Return the list of packages that haven't been found in Portage.
        """
        return self._not_found_packages

    def get_not_installed_packages(self):
        """
        Return the list of packages that haven't been found on the System.
        """
        return self._not_installed_packages

    def get_not_merged_packages(self):
        """
        Return the list of packages that haven't been able to compile.
        """
        return self._not_merged_packages

    def run(self):
        """
        Execute Package building action.
        """
        header = self._build_execution_header_output()
        print_info(
            header + "spawning package build: %s" % (
                " ".join(self._packages),))

        std_env = PackageBuilder._build_standard_environment(
            repository=self._params["repository"])

        matter_package_names = " ".join(self._packages)
        std_env["MATTER_PACKAGE_NAMES"] = matter_package_names
        print_info("MATTER_PACKAGE_NAMES = %s" % (matter_package_names,))

        # run pkgpre, if any
        pkgpre = self._params["pkgpre"]
        if pkgpre is not None:
            print_info("spawning --pkgpre: %s" % (pkgpre,))
            tmp_fd, tmp_path = mkstemp()
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                with open(pkgpre, "rb") as pkgpre_f:
                    tmp_f.write(pkgpre_f.read())
            try:
                # now execute
                os.chmod(tmp_path, 0o700)
                exit_st = subprocess.call([tmp_path], env = std_env)
                if exit_st != 0:
                    return exit_st
            finally:
                os.remove(tmp_path)

        dirs_cleanup = []
        exit_st = self._run_builder(dirs_cleanup)

        print_info("builder terminated, exit status: %d" % (exit_st,))

        # cleanup temporary directories registered on the queue
        for tmp_dir in dirs_cleanup:
            self.__cleanup_dir(tmp_dir)

        # run pkgpost, if any
        pkgpost = self._params["pkgpost"]
        if pkgpost is not None:
            print_info("spawning --pkgpost: %s" % (pkgpost,))
            tmp_fd, tmp_path = mkstemp()
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                with open(pkgpost, "rb") as pkgpost_f:
                    tmp_f.write(pkgpost_f.read())
            try:
                # now execute
                os.chmod(tmp_path, 0o700)
                post_exit_st = subprocess.call([tmp_path, str(exit_st)],
                    env = std_env)
                if post_exit_st != 0:
                    return post_exit_st
            finally:
                os.remove(tmp_path)

        return exit_st

    def __cleanup_dir(self, tmp_dir):
        if os.path.isdir(tmp_dir) \
            and (not os.path.islink(tmp_dir)):
            shutil.rmtree(tmp_dir, True)

    def _pre_graph_filters(self, package, portdb, vardb):
        """
        Execute basic, pre-graph generation (dependencies calculation)
        filters against the package dependency to see if it's eligible
        for the graph.
        """
        allow_rebuild = self._params['rebuild'] == "yes"
        allow_not_installed = self._params['not-installed'] == "yes"
        allow_downgrade = self._params['downgrade'] == "yes"

        best_visible = portdb.xmatch("bestmatch-visible", package)
        if not best_visible:
            # package not found, return error
            print_error("cannot match: %s, ignoring this one" % (package,))
            self._not_found_packages.append(package)
            return None

        print_info("matched: %s for %s" % (best_visible, package,))
        # now determine what's the installed version.
        best_installed = portage.best(vardb.match(package))
        if (not best_installed) and (not allow_not_installed):
            # package not installed
            print_error("package not installed: %s, ignoring this one" % (
                package,))
            self._not_installed_packages.append(package)
            return None

        if (not best_installed) and allow_not_installed:
            print_warning(
                "package not installed: "
                "%s, but 'not-installed: yes' provided" % (package,))

        cmp_res = -1
        if best_installed:
            print_info("found installed: %s for %s" % (
                    best_installed, package,))
            # now compare
            # -1 if best_installed is older than best_visible
            # 1 if best_installed is newer than best_visible
            # 0 if they are equal
            cmp_res = portage.versions.pkgcmp(
                portage.versions.pkgsplit(best_installed),
                portage.versions.pkgsplit(best_visible))

        is_rebuild = cmp_res == 0

        if (cmp_res == 1) and (not allow_downgrade):
            # downgrade in action and downgrade not allowed, aborting!
            print_warning(
                "package: %s, would be downgraded, %s to %s, ignoring" % (
                    package, best_installed, best_visible,))
            return None

        if is_rebuild and (not allow_rebuild):
            # rebuild in action and rebuild not allowed, aborting!
            print_warning(
                "package: %s, would be rebuilt to %s, ignoring" % (
                    package, best_visible,))
            return None

        # at this point we can go ahead accepting package in queue
        print_info("package: %s [%s], accepted in queue" % (
                best_visible, package,))
        return best_visible

    def _post_graph_filters(self, graph, vardb, portdb):
        """
        Execute post-graph generation (dependencies calculation)
        filters against the package dependencies to see if they're
        eligible for building.
        """
        # list of _emerge.Package.Package objects
        package_queue = graph.altlist()

        # filter out blockers
        real_queue = [x for x in package_queue if not isinstance(
                x, Blocker)]
        # filter out broken or corrupted objects
        real_queue = [x for x in real_queue if x.cpv]

        # package_queue can also contain _emerge.Blocker.Blocker objects
        # not exposing .cpv field (but just .cp).
        dep_list = []
        for pobj in package_queue:
            if isinstance(pobj, Blocker):
                # blocker, list full atom
                dep_list.append("!" + pobj.atom)
                continue
            cpv = pobj.cpv
            repo = pobj.repo
            if repo:
                repo = "::" + repo
            if cpv:
                dep_list.append(cpv+repo)
            else:
                print_warning(
                    "attention, %s has broken cpv: '%s', ignoring" % (
                        pobj, cpv,))

        # calculate dependencies, if --dependencies is not enabled
        # because we have to validate it
        if (self._params['dependencies'] == "no") \
                and (len(package_queue) > 1):
            deps = "\n  ".join(dep_list)
            print_warning("dependencies pulled in:")
            print_warning(deps)
            print_warning("but 'dependencies: no' in config, aborting")
            return None

        # inspect use flags changes
        allow_new_useflags = self._params['new-useflags'] == "yes"
        allow_removed_useflags = \
            self._params['removed-useflags'] == "yes"

        use_flags_give_up = False
        if (not allow_new_useflags) or (not allow_removed_useflags):
            # checking for use flag changes
            for pkg in real_queue:
                # frozenset
                enabled_flags = pkg.use.enabled
                inst_atom = portage.best(vardb.match(pkg.slot_atom))
                if not inst_atom:
                    # new package, ignore check
                    continue
                installed_flags = frozenset(
                    vardb.aux_get(inst_atom, ["USE"])[0].split())

                new_flags = enabled_flags - installed_flags
                removed_flags = installed_flags - enabled_flags

                if (not allow_new_useflags) and new_flags:
                    print_warning(
                        "ouch: %s wants these new USE flags: %s" % (
                            pkg.cpv+"::"+pkg.repo,
                            " ".join(sorted(new_flags)),))
                    use_flags_give_up = True
                if (not allow_removed_useflags) and removed_flags:
                    print_warning(
                        "ouch: %s has these USE flags removed: %s" % (
                            pkg.cpv+"::"+pkg.repo,
                        " ".join(sorted(removed_flags)),))
                    use_flags_give_up = True

        if use_flags_give_up:
            print_warning("cannot continue due to unmet "
                          "USE flags constraint")
            return None

        allow_downgrade = self._params['downgrade'] == "yes"
        # check the whole queue against downgrade directive
        if not allow_downgrade:
            allow_downgrade_give_ups = []
            for pkg in real_queue:
                inst_atom = portage.best(vardb.match(pkg.slot_atom))
                cmp_res = -1
                if inst_atom:
                    # -1 if inst_atom is older than pkg.cpv
                    # 1 if inst_atom is newer than pkg.cpv
                    # 0 if they are equal
                    cmp_res = portage.versions.pkgcmp(
                        portage.versions.pkgsplit(inst_atom),
                        portage.versions.pkgsplit(pkg.cpv))
                if cmp_res > 0:
                    allow_downgrade_give_ups.append((inst_atom, pkg.cpv))

            if allow_downgrade_give_ups:
                print_warning(
                    "cannot continue due to package "
                    "downgrade not allowed for:")
                for inst_atom, avail_atom in allow_downgrade_give_ups:
                    print_warning("  installed: %s | wanted: %s" % (
                        inst_atom, avail_atom,))
                return None

        changing_repo_pkgs = []
        for pkg in real_queue:
            wanted_repo = pkg.repo
            inst_atom = portage.best(vardb.match(pkg.slot_atom))
            current_repo = vardb.aux_get(inst_atom, ["repository"])[0]
            if current_repo:
                if current_repo != wanted_repo:
                    changing_repo_pkgs.append(
                        (pkg.cpv, pkg.slot, current_repo, wanted_repo))

        if changing_repo_pkgs:
            print_warning("")
            print_warning(
                "Attention, packages are moving across SPM repositories:")
            for pkg_atom, pkg_slot, c_repo, w_repo in changing_repo_pkgs:
                print_warning("  %s:%s [%s->%s]" % (pkg_atom, pkg_slot,
                    c_repo, w_repo,))
            print_warning("")

        allow_spm_repo_change = self._params['spm-repository-change'] \
            == "yes"
        allow_spm_repo_change_if_ups = \
            self._params['spm-repository-change-if-upstreamed'] == "yes"

        if (not allow_spm_repo_change) and allow_spm_repo_change_if_ups:
            print_info("SPM repository change allowed if the original "
                       "repository does no longer contain "
                       "current packages.")

            # check if source repository still contains the package
            # in this case, set allow_spm_repo_change to True
            _allow = True
            for pkg_atom, pkg_slot, c_repo, w_repo in changing_repo_pkgs:
                pkg_key = portage.dep.dep_getkey("=%s" % (pkg_atom,))
                pkg_target = "%s:%s::%s" % (
                    pkg_key, pkg_slot, c_repo)
                pkg_match = portdb.xmatch("bestmatch-visible", pkg_target)
                if pkg_match:
                    # package still available in source repo
                    _allow = False
                    print_warning("  %s:%s, still in repo: %s" % (
                        pkg_atom, pkg_slot, c_repo,))
                    # do not break, print all the list
                    # break

            if _allow and changing_repo_pkgs:
                print_info(
                    "current packages are no longer in their "
                    "original repository, SPM repository change allowed.")
                allow_spm_repo_change = True

        if changing_repo_pkgs and (not allow_spm_repo_change):
            print_warning(
                "cannot continue due to unmet SPM repository "
                "change constraint")
            return None

        print_info("USE flags constraints are met for all "
                   "the queued packages")
        return dep_list, real_queue

    def _setup_keywords(self, settings):
        """
        Setup ACCEPT_KEYWORDS for package.
        """
        # setup stable keywords if needed
        force_stable_keywords = self._params["stable"] == "yes"
        inherit_keywords = self._params["stable"] == "inherit"

        settings.unlock()
        arch = settings["ARCH"][:]
        orig_key = "ACCEPT_KEYWORDS_MATTER"
        orig_keywords = settings.get(orig_key)

        if orig_keywords is None:
            orig_keywords = settings["ACCEPT_KEYWORDS"][:]
            settings[orig_key] = orig_keywords
            settings.backup_changes(orig_key)

        if force_stable_keywords:
            keywords = arch
        elif inherit_keywords:
            keywords = orig_keywords
        else:
            keywords = "%s ~%s" % (arch, arch)

        settings.unlock()
        settings["ACCEPT_KEYWORDS"] = keywords
        settings.backup_changes("ACCEPT_KEYWORDS")
        settings.lock()

    def _run_builder(self, dirs_cleanup_queue):
        """
        This method is called by _run and executes the whole package build
        logic, including constraints validation given by argv parameters.
        NOTE: negative errors indicate warnings that can be skipped.
        """
        if self._packages:
            first_package = self._packages[0]
        else:
            first_package = "_empty_"

        log_dir = tempfile.mkdtemp(prefix="matter_build.",
            suffix="." + first_package.replace("/", "_").lstrip("<>=~"))
        dirs_cleanup_queue.append(log_dir)

        emerge_settings, emerge_trees, mtimedb = self._emerge_config

        # Setup stable/unstable keywords, must be done on
        # emerge_settings bacause the reference is spread everywhere
        # in emerge_trees.
        # This is not thread-safe, but Portage isn't either, so
        # who cares!
        self._setup_keywords(emerge_settings)

        settings = portage.config(clone=emerge_settings)

        portdb = emerge_trees[settings["ROOT"]]["porttree"].dbapi
        if not portdb.frozen:
            portdb.freeze()
        vardb = emerge_trees[settings["ROOT"]]["vartree"].dbapi
        vardb.settings.unlock()
        vardb.settings["PORT_LOGDIR"] = log_dir
        vardb.settings.backup_changes("PORT_LOGDIR")
        vardb.settings.lock()

        # Load the most current variables from /etc/profile.env, which
        # has been re-generated by the env-update call in _run()
        settings.unlock()
        settings.reload()
        settings.regenerate()
        settings.lock()

        packages = []
        # execute basic, pre-graph generation filters against each
        # package dependency in self._packages.
        # This is just fast pruning of obvious obviousness.
        for package in self._packages:
            best_visible = self._pre_graph_filters(
                package, portdb, vardb)
            if best_visible is not None:
                packages.append((package, best_visible))

        if not packages:
            print_warning("No remaining packages in queue, aborting.")
            return 0

        # at this point we can go ahead building packages
        print_info("starting to build:")
        for package, best_visible in packages:
            print_info(": %s -> %s" % (
                    package, best_visible,))

        if not getcolor():
            portage.output.nocolor()

        # non interactive properties, this is not really required
        # accept-properties just sets os.environ...
        build_args = []
        build_args += PackageBuilder.PORTAGE_BUILD_ARGS
        build_args += PackageBuilder.PORTAGE_BUILTIN_ARGS
        build_args += ["=" + best_v for _x, best_v in packages]
        myaction, myopts, myfiles = parse_opts(build_args)

        if "--pretend" in myopts:
            print_warning("cannot use --pretend emerge argument, you idiot")
            del myopts["--pretend"]
        if "--ask" in myopts:
            print_warning("cannot use --ask emerge argument, you idiot")
            del myopts["--ask"]
        spinner = stdout_spinner()
        if "--quiet" in myopts:
            spinner.update = spinner.update_basic
        elif "--nospinner" in myopts:
            spinner.update = spinner.update_basic
        if settings.get("TERM") == "dumb" or not is_stdout_a_tty():
            spinner.update = spinner.update_basic

        print_info("emerge args: %s" % (" ".join(build_args),))

        params = create_depgraph_params(myopts, myaction)
        success, graph, favorites = backtrack_depgraph(settings,
            emerge_trees, myopts, params, myaction, myfiles, spinner)

        if not success:
            # print issues to stdout and give up
            print_warning("dependencies calculation failed, aborting")
            graph.display_problems()
            return 0
        print_info("dependency graph generated successfully")

        f_data = self._post_graph_filters(graph, vardb, portdb)
        if f_data is None:
            # post-graph filters not passed, giving up
            return 0
        dep_list, real_queue = f_data

        print_info("about to build the following packages:")
        for dep in dep_list:
            print_info("  %s" % (dep,))

        # re-calling action_build(), deps are re-calculated though
        validate_ebuild_environment(emerge_trees)
        mergetask = Scheduler(settings, emerge_trees, mtimedb,
            myopts, spinner, favorites=favorites,
            graph_config=graph.schedulerGraph())
        del graph
        clear_caches(emerge_trees)
        retval = mergetask.merge()

        not_merged = []
        real_queue_map = dict((pkg.cpv, pkg) for pkg in real_queue)
        failed_package = None
        if retval != 0:
            merge_list = mtimedb.get("resume", {}).get("mergelist")
            for _merge_type, _merge_root, merge_atom, _merge_act in merge_list:
                if failed_package is None:
                    # we consider the first encountered package the one
                    # that failed. It makes sense since packages are built
                    # serially as of today.
                    # Also, the package object must be available in our
                    # package queue, so grab it from there.
                    failed_package = real_queue_map.get(merge_atom)
                not_merged.append(merge_atom)
                self._not_merged_packages.append(merge_atom)

        for pkg in real_queue:
            cpv = pkg.cpv
            if not cpv:
                print_warning("package: %s, has broken cpv: '%s', ignoring" % (
                        pkg, cpv,))
            elif cpv not in not_merged:
                # add to build queue
                print_info("package: %s, successfully built" % (cpv,))
                self._built_packages.append(cpv)

        post_emerge(myaction, myopts, myfiles, settings["ROOT"],
            emerge_trees, mtimedb, retval)

        subprocess.call(["env-update"])

        if failed_package is not None:
            print_warning("failed package: %s::%s" % (failed_package.cpv,
                failed_package.repo,))

        if self._params['buildfail'] and (failed_package is not None):

            std_env = PackageBuilder._build_standard_environment(
                repository=self._params["repository"])
            std_env["MATTER_PACKAGE_NAMES"] = " ".join(self._packages)
            std_env["MATTER_PORTAGE_FAILED_PACKAGE_NAME"] = failed_package.cpv
            std_env["MATTER_PORTAGE_REPOSITORY"] = failed_package.repo
            # call pkgfail hook if defined
            std_env["MATTER_PORTAGE_BUILD_LOG_DIR"] = os.path.join(log_dir,
                "build")

            buildfail = self._params['buildfail']
            print_info("spawning buildfail: %s" % (buildfail,))
            tmp_fd, tmp_path = mkstemp()
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                with open(buildfail, "rb") as buildfail_f:
                    tmp_f.write(buildfail_f.read())
            try:
                # now execute
                os.chmod(tmp_path, 0o700)
                exit_st = subprocess.call([tmp_path], env = std_env)
                if exit_st != 0:
                    return exit_st
            finally:
                os.remove(tmp_path)

        print_info("portage spawned, return value: %d" % (retval,))
        return retval

    @staticmethod
    def post_build(emerge_config):
        """
        Execute Portage post-build tasks.
        """
        emerge_settings, emerge_trees, mtimedb = emerge_config
        if "yes" == emerge_settings.get("AUTOCLEAN"):
            print_info("executing post-build operations, please wait...")
            builtin_args = PackageBuilder.PORTAGE_BUILTIN_ARGS
            _action, opts, _files = parse_opts(
                PackageBuilder.PORTAGE_BUILD_ARGS + builtin_args)
            unmerge(emerge_trees[emerge_settings["ROOT"]]["root_config"],
                opts, "clean", [], mtimedb["ldpath"], autoclean=1)

    @staticmethod
    def sync():
        """
        Execute Portage and Overlays sync
        """
        sync_cmd = PackageBuilder.PORTAGE_SYNC_CMD
        std_env = PackageBuilder._build_standard_environment()
        exit_st = subprocess.call(sync_cmd, env = std_env)
        if exit_st != 0:
            return exit_st

        # overlays update
        overlay_cmd = PackageBuilder.OVERLAYS_SYNC_CMD
        return subprocess.call(overlay_cmd, env = std_env)

    @staticmethod
    def check_preserved_libraries(emerge_config):
        """
        Ask portage whether there are preserved libraries on the system.
        This usually indicates that Entropy packages should not be really
        committed.

        @param emerge_config: tuple returned by load_emerge_config(),
            -> (emerge_settings, emerge_trees, mtimedb)
        @type emerge_config: tuple
        @return: True, if preserved libraries are found
        @rtype: bool
        """
        emerge_settings, emerge_trees, _mtimedb = emerge_config
        vardb = emerge_trees[emerge_settings["ROOT"]]["vartree"].dbapi
        vardb._plib_registry.load()
        return vardb._plib_registry.hasEntries()

    @staticmethod
    def commit(entropy_server, repository, packages):
        """
        Commit packages to Entropy repository.
        """
        spm = entropy_server.Spm()
        spm_atoms = set()
        exit_st = 0

        print_info("committing packages: %s, to repository: %s" % (
            ", ".join(sorted(packages)), repository,))

        # if we get here, something has been compiled
        # successfully
        for package in packages:
            try:
                spm_atom = spm.match_installed_package(package)
                spm_atoms.add(spm_atom)
            except KeyError:
                exit_st = 1
                print_warning(
                    "cannot find installed package: %s" % (
                        package,))
                continue

        if not spm_atoms:
            return exit_st

        print_info("about to commit:")
        spm_packages = sorted(spm_atoms)

        for atom in spm_packages:
            item_txt = atom

            # this is a spm atom
            spm_key = portage.dep.dep_getkey("=%s" % (atom,))
            try:
                spm_slot = spm.get_installed_package_metadata(
                    atom, "SLOT")
                spm_repo = spm.get_installed_package_metadata(
                    atom, "repository")
            except KeyError:
                spm_slot = None
                spm_repo = None

            etp_repo = None
            if spm_repo is not None:
                pkg_id, repo_id = entropy_server.atom_match(spm_key,
                    match_slot = spm_slot)
                if repo_id != 1:
                    repo_db = entropy_server.open_repository(repo_id)
                    etp_repo = repo_db.retrieveSpmRepository(pkg_id)

                    if (etp_repo is not None) and (etp_repo != spm_repo):
                        item_txt += ' [%s {%s=>%s}]' % ("warning",
                            etp_repo, spm_repo,)

            print_info(item_txt)

        # always stuff new configuration files here
        # if --gentle was specified, the uncommitted stuff here belongs
        # to our packages.
        # if --gentle was NOT specified, we just don't give a shit
        # Due to bug #2480 -- sometimes (app-misc/tracker)
        # _check_config_file_updates() doesn't return all the files
        subprocess.call("echo -5 | etc-update", shell = True)
        uncommitted = entropy_server._check_config_file_updates()
        if uncommitted:
            # ouch, wtf? better aborting
            print_error("tried to commit configuration file changes and failed")
            return 1

        print_info("about to compress:")

        store_dir = entropy_server._get_local_store_directory(repository)
        package_paths = []
        for atom in spm_packages:
            print_info(atom)
            try:
                pkg_list = spm.generate_package(atom, store_dir)
            except OSError:
                entropy.tools.print_traceback()
                print_error("problem during package generation, aborting")
                return 1
            except SPMError:
                entropy.tools.print_traceback()
                print_error("problem during package generation (2), aborting")
                return 1
            package_paths.append(pkg_list)

        etp_pkg_files = [(pkg_list, False) for pkg_list in package_paths]
        # NOTE: any missing runtime dependency will be added
        # (beside those blacklisted), since this execution is not interactive
        package_ids = entropy_server.add_packages_to_repository(
            repository, etp_pkg_files, ask = False)
        if package_ids:
            # checking dependencies and print issues
            entropy_server.dependencies_test(repository)
        entropy_server.close_repositories()

        return exit_st

    @staticmethod
    def push(entropy_server, repository):
        """
        Push staged packages in repository to online Entropy mirrors.
        """
        exit_st = PackageBuilder._push_packages(entropy_server, repository)
        if exit_st != 0:
            return exit_st
        return PackageBuilder._push_repository(entropy_server, repository)

    @staticmethod
    def _push_packages(entropy_server, repository):
        """
        Upload newly built packages.
        """
        _mirrors_tainted, mirrors_errors, successfull_mirrors, \
            _broken_mirrors, _check_data = \
                entropy_server.Mirrors.sync_packages(
                    repository, ask = False, pretend = False)
        if mirrors_errors and not successfull_mirrors:
            return 1
        return 0

    @staticmethod
    def _push_repository(entropy_server, repository):
        """
        Update remote repository.
        """
        sts = entropy_server.Mirrors.sync_repository(repository)
        return sts


def matter_main(entropy_server, nsargs, cwd, specs):
    """
    Main application code run after all the resources setup.
    """
    exit_st = 0

    emerge_config = load_emerge_config()
    if not nsargs.disable_preserved_libs:
        preserved_libs = PackageBuilder.check_preserved_libraries(
            emerge_config)
        if preserved_libs:
            print_error(
                "preserved libraries are found on system, aborting.")
            raise SystemExit(7)

    if nsargs.gentle:
        # check if there is something to do
        to_be_added, _to_be_removed, _to_be_injected = \
            entropy_server.scan_package_changes()
        if to_be_added: # only check this, others we can ignore
            to_be_added = [x[0] for x in to_be_added]
            to_be_added.sort()
            print_error("--gentle specified, and unstaged packages found:")
            for name in to_be_added:
                print_warning("  " + name)
            raise SystemExit(5)

        # also check for uncommitted configuration files changed
        problems = entropy_server._check_config_file_updates()
        if problems:
            print_error(
                "some configuration files have to be merged manually")
            raise SystemExit(6)

    print_info("matter loaded, starting to scan particles, pid: %s" % (
        os.getpid(),))

    # setup
    if nsargs.pre:
        _rc = PackageBuilder.setup(nsargs.pre, cwd)
        if _rc != 0:
            exit_st = _rc

    if exit_st == 0:

        if nsargs.sync:
            _rc = PackageBuilder.sync()
            if _rc != 0:
                exit_st = _rc

        if exit_st == 0:
            completed = []
            not_found = []
            not_installed = []
            not_merged = []
            tainted_repositories = set()
            spec_count = 0
            tot_spec = len(specs)
            preserved_libs = False

            for spec in specs:

                spec_count += 1
                keep_going = spec["keep-going"] == "yes"
                local_completed = []

                tot_pkgs = len(spec['packages'])
                for pkg_count, packages in enumerate(spec['packages'], 1):

                    builder = PackageBuilder(entropy_server, emerge_config,
                        packages, spec, spec_count, tot_spec, pkg_count,
                        tot_pkgs)
                    _rc = builder.run()

                    not_found.extend(builder.get_not_found_packages())
                    not_installed.extend(
                        builder.get_not_installed_packages())
                    not_merged.extend(
                        builder.get_not_merged_packages())
                    preserved_libs = \
                        PackageBuilder.check_preserved_libraries(emerge_config)

                    if preserved_libs and not nsargs.disable_preserved_libs:
                        # abort, library breakages detected
                        exit_st = 1
                        print_error(
                            "preserved libraries detected, aborting")
                        break

                    # ignore _rc, we may have built pkgs even if _rc != 0
                    built_packages = builder.get_built_packages()
                    if built_packages:
                        print_info("built packages, in queue: %s" % (
                                " ".join(built_packages),))
                        local_completed.extend(
                            [x for x in built_packages \
                                 if x not in local_completed])
                        tainted_repositories.add(spec['repository'])

                    # make some room
                    print_info("")
                    if _rc < 0:
                        # ignore warning and go ahead
                        continue
                    else:
                        exit_st = _rc
                        if not keep_going:
                            break

                # call post-build cleanup operations,
                # run it unconditionally
                PackageBuilder.post_build(emerge_config)

                if preserved_libs and not nsargs.disable_preserved_libs:
                    # completely abort
                    break

                completed.extend([x for x in local_completed \
                    if x not in completed])
                # portage calls setcwd()
                os.chdir(cwd)

                if local_completed and nsargs.commit:
                    _rc = PackageBuilder.commit(
                        entropy_server,
                        spec['repository'], local_completed)
                    if exit_st == 0 and _rc != 0:
                        exit_st = _rc
                        if not keep_going:
                            break

            if tainted_repositories and nsargs.push and nsargs.commit:
                if preserved_libs and nsargs.disable_preserved_libs:
                    # cannot push anyway
                    print_warning("Preserved libraries detected, cannot push !")
                elif not preserved_libs:
                    for repository in tainted_repositories:
                        _rc = PackageBuilder.push(
                            entropy_server, repository)
                        if exit_st == 0 and _rc != 0:
                            exit_st = _rc

            # print summary
            print_info("")
            print_info("Summary")
            print_info("Packages built:\n  %s" % (
                "\n  ".join(sorted(completed)),))
            print_info("Packages not built:\n  %s" % (
                "\n  ".join(sorted(not_merged)),))
            print_info("Packages not found:\n  %s" % (
                "\n  ".join(sorted(not_found)),))
            print_info("Packages not installed:\n  %s" % (
                "\n  ".join(sorted(not_installed)),))
            print_info("Preserved libs: %s" % (
                preserved_libs,))
            print_info("")

    if nsargs.post:
        _rc = PackageBuilder.teardown(nsargs.post, cwd,
            exit_st)
        if exit_st == 0 and _rc != 0:
            exit_st = _rc

    raise SystemExit(exit_st)


def main():
    """
    Main App.
    """
    _env_vars_help = """\

Environment variables for Package Builder module:
%s       =  repository identifier
%s    =  alternative command used to sync Portage
                              default: %s
%s   =  alternative command used to sync Portage overlays
                              default: %s
%s  = custom emerge arguments
                              default: %s

Environment variables passed to --post executables:
%s        = exit status from previous execution phases, useful for detecting
                             execution errors.

Matter Resources Lock file you can use to detect if matter is running:
%s (--blocking switch makes it acquire in blocking mode)
""" % (
        purple("MATTER_REPOSITORY_ID"),
        purple("MATTER_PORTAGE_SYNC_CMD"),
        darkgreen(PackageBuilder.DEFAULT_PORTAGE_SYNC_CMD),
        purple("MATTER_OVERLAYS_SYNC_CMD"),
        darkgreen(PackageBuilder.DEFAULT_OVERLAYS_SYNC_CMD),
        purple("MATTER_PORTAGE_BUILD_ARGS"),
        darkgreen(PackageBuilder.DEFAULT_PORTAGE_BUILD_ARGS),
        purple("MATTER_EXIT_STATUS"),
        darkgreen(MatterResourceLock.LOCK_FILE_PATH),)

    parser = argparse.ArgumentParser(
        description='Automated Packages Builder',
        epilog=_env_vars_help,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # * instead of + in order to support --sync only tasks
    parser.add_argument("spec", nargs='+', metavar="<spec>", type=file,
        help="matter spec file")

    parser.add_argument("--blocking",
        help="when trying to acquire Entropy Server locks, block until success",
        action="store_true")

    parser.add_argument("--commit",
        help="commit built packages to repository",
        action="store_true")

    parser.add_argument("--community",
        help="enforce Community Repository mode on Entropy Server",
        action="store_true")

    parser.add_argument("--gentle",
        help="do not run if staged packages are present in Entropy repository",
        action="store_true")

    parser.add_argument("--pre", metavar="<exec>", type=file,
        help="executable to be called once for setup purposes",
        default=None)

    parser.add_argument("--post", metavar="<exec>", type=file,
        help="executable to be called once for teardown purposes",
        default=None)

    parser.add_argument("--push",
        help="push entropy package updates to online repository (only if --commit)",
        action="store_true")

    parser.add_argument("--sync",
        help="sync Portage tree, and attached overlays, before starting",
        action="store_true")

    parser.add_argument("--disable-preserved-libs",
        dest="disable_preserved_libs", default=False,
        help="disable prerserved libraries check",
        action="store_true")

    try:
        nsargs = parser.parse_args(sys.argv[1:])
    except IOError as err:
        if err.errno == errno.ENOENT:
            print_error(err.strerror + ": " + err.filename)
            raise SystemExit(1)
        raise

    if os.getuid() != 0:
        # root access required
        print_error("superuser access required")
        raise SystemExit(1)

    if nsargs.community:
        os.environ['ETP_COMMUNITY_MODE'] = "1"

    # parse spec files
    specs = []
    for spec_f in nsargs.spec:
        spec = SpecParser(spec_f)
        data = spec.parse()
        if data:
            specs.append(data)

    if not specs:
        print_error("invalid spec files provided")
        raise SystemExit(1)

    entropy_server = None
    exit_st = 0
    cwd = os.getcwd()

    try:
        try:
            entropy_server = Server()
        except PermissionDenied:
            # repository not available or not configured
            print_error("no valid server-side repositories configured")
            raise SystemExit(3)

        # validate repository entries of spec metadata
        avail_repos = entropy_server.repositories()
        for spec in specs:
            if spec["repository"] not in avail_repos:
                print_error("invalid repository %s" % (spec["repository"],))
                raise SystemExit(10)

        if nsargs.blocking:
            print_info("--blocking enabled, please wait for locks...")

        with EntropyResourceLock(entropy_server, nsargs.blocking):
            with MatterResourceLock(nsargs.blocking):
                matter_main(entropy_server, nsargs, cwd, specs)

    except EntropyResourceLock.NotAcquired:
        print_error("unable to acquire Entropy Resources lock")
        raise SystemExit(42)
    except MatterResourceLock.NotAcquired:
        print_error("unable to acquire Matter Resources lock")
        raise SystemExit(42)
    except KeyboardInterrupt:
        print_error("Keyboard Interrupt, pid: %s" % (os.getpid(),))
        raise SystemExit(100)
    finally:
        if entropy_server is not None:
            entropy_server.shutdown()

    print_warning("")
    print_warning("")
    print_warning("Tasks complete, exit status: %d" % (exit_st,))
    raise SystemExit(exit_st)


if __name__ == "__main__":
    main()
