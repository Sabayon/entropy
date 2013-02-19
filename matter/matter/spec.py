# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

"""
import os
import shlex

from matter.utils import convert_to_unicode, get_stringtype


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
        return convert_to_unicode(x).strip()

    def ve_string_splitter(self, x):
        return convert_to_unicode(x).strip().split()

    def ve_integer_converter(self, x):
        return int(x)

    def ve_string_shlex_splitter(self, x):
        return list(shlex.split(x))

    def valid_ascii(self, x):
        try:
            x = str(x)
            return x
        except (UnicodeDecodeError, UnicodeEncodeError,):
            return ""

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
        for part in convert_to_unicode(input_str).split(","):
            part = part.strip()
            # do not filter out empty elements
            parts.append(part.split())
        return parts

    def valid_path_list(self, x):
        return [y.strip() for y in \
            convert_to_unicode(x).split(",") if \
                self.valid_path_string(y) and y.strip()]


class MatterSpecParser(object):
    """
    Base class for implementing external .spec parsers
    that can be used to extend the list of supported statements.
    """

    def vital_parameters(self):
        """
        Return a list of vital parameters.
        """
        raise NotImplementedError()

    def data(self):
        """
        Return a dictionary containing parameter names as key and
        dict containing keys 've' and 'cb' which values are three
        callable functions that respectively do value extraction (ve),
        value verification (cb) and value modding (mod).

        @return: data path dictionary (see ChrootSpec code for more info)
        @rtype: dict
        """
        raise NotImplementedError()


class MatterSpec(MatterSpecParser):

    _external_parsers = []

    def __init__(self):
        """
        MatterSpec constructor.
        """
        self._funcs = GenericSpecFunctions()

    @classmethod
    def register_parser(cls, parser):
        """
        Register an external parser object.

        @param parser: a MatterSpecParser subclass
        @type parser: MatterSpecParser
        """
        MatterSpec._external_parsers.append(parser)

    def vital_parameters(self):
        """
        Return a list of vital .spec file parameters

        @return: list of vital .spec file parameters
        @rtype: list
        """
        vital = set(["packages", "repository"])
        for parser in MatterSpec._external_parsers:
            vital |= set(parser.vital_parameters())
        return sorted(vital)

    def data(self):
        """
        Return a dictionary containing parameter names as key and
        dict containing keys 've' and 'cb' which values are three
        callable functions that respectively do value extraction (ve),
        value verification (cb) and value modding (mod).

        @return: data path dictionary (see ChrootSpec code for more info)
        @rtype: dict
        """
        data = {
            "build-args": {
                "cb": self._funcs.ne_string,
                "ve": self._funcs.ve_string_shlex_splitter,
                "default": ["--verbose", "--nospinner"],
                "desc": "Portage build arguments (default is --verbose\n "
                "--nospinner)",
            },
            "build-only": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Only build the packages without merging them\n "
                "into the system.",
            },
            "dependencies": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Allow dependencies to be pulled in? (yes/no)",
            },
            "downgrade": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Allow package downgrades? (yes/no)",
            },
            "keep-going": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Make possible to continue if one \n\t"
                "or more packages fail to build? (yes/no)",
            },
            "new-useflags": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Allow new USE flags? (yes/no)",
            },
            "removed-useflags": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Allow removed USE flags? (yes/no)",
            },
            "rebuild": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Allow package rebuilds? (yes/no)",
            },
            "spm-repository-change": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Allow Source Package Manager (Portage) \n\t"
                "repository change? (yes/no)",
            },
            "spm-repository-change-if-upstreamed": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "In case of Source Package Manager \n\trepository "
                "changes, allow execution if the original repository "
                "\n\tdoes not contain the package anymore? (yes/no)",
            },
            "not-installed": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Allow compiling packages even if they "
                "are not \n\tactually installed on the System? (yes/no)",
            },
            "soft-blocker": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "yes",
                "desc": "Allow soft-blockers in the merge queue?\n "
                "Packages will be unmerged if yes. (yes/no)",
            },
            "unmerge": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "yes",
                "desc": "Allow package unmerges due to Portage\n "
                "soft-blockers resolution. (yes/no)",
            },
            "pkgpre": {
                "cb": self._funcs.not_none,
                "ve": self._funcs.ve_string_open_file_read,
                "default": None,
                "desc": "Package pre execution script hook path, "
                "executed \n\tfor each package (also see example files)",
            },
            "pkgpost": {
                "cb": self._funcs.not_none,
                "ve": self._funcs.ve_string_open_file_read,
                "default": None,
                "desc": "Package build post execution script hook path, "
                "executed \n\tfor each package (also see example files)",
            },
            "buildfail": {
                "cb": self._funcs.not_none,
                "ve": self._funcs.ve_string_open_file_read,
                "default": None,
                "desc": "Package build failure execution script hook "
                "path, \n\texecuted for each failing package (also see "
                "example files)",
            },
            "packages": {
                "cb": self._funcs.always_valid,
                "ve": self._funcs.valid_comma_sep_list_list,
                "mod": lambda l_l: [x for x in l_l if x],
                "desc": "List of packages to scrape, separated by "
                "comma. \n\tIf you want to let Portage consider a group "
                "of packages, \n\tjust separate them with spaces/tabs but "
                "no commas",
            },
            "repository": {
                "cb": self._funcs.ne_string,
                "ve": self._funcs.ve_string_stripper,
                "desc": "Binary Package Manager repository in where "
                "newly built \n\tpackages will be put and pushed to",
            },
            "stable": {
                "cb": self._funcs.valid_yes_no_inherit,
                "ve": self._funcs.ve_string_stripper,
                "default": "inherit",
                "desc": "Only accept Portage stable packages (no "
                "unstable keywords)",
            },
        }
        for parser in MatterSpec._external_parsers:
            parser_data = parser.data()
            common_keys = set(data.keys()) & set(parser_data.keys())
            if common_keys:
                raise ValueError("Parser %s duplicates support for %s" % (
                        parser, " ".join(sorted(common_keys)),))
            data.update(parser_data)
        return data


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
        lines = ""
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

        final_content = ("".join(final_content)).split("\n")

        return final_content


class SpecParser:

    def __init__(self, file_object):

        self.file_object = file_object
        self._preprocessor = SpecPreprocessor(self.file_object)

        self.__parser = MatterSpec()
        self.vital_parameters = self.__parser.vital_parameters()
        self._data = self.__parser.data()

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
            check_dict = self._data.get(v_key)
            if check_dict is not None:
                key, value = v_key, v_value
                old_key = key
            elif isinstance(old_key, get_stringtype()):
                key = old_key
                value = line.strip()
                if not value:
                    continue
            # gather again... key is changed
            check_dict = self._data.get(key)
            if not isinstance(check_dict, dict):
                continue
            value = check_dict["ve"](value)
            if not check_dict["cb"](value):
                continue

            if key in mydict:

                if isinstance(value, get_stringtype()):
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
        data = mydict.copy()
        # add file name if possible
        data["__name__"] = self.file_object.name
        return data

    def _extend_parse(self, mydata):
        """
        Extend parsed data with default values for statements with
        default option available.
        """
        for statement, opts in self._data.items():
            if "default" in opts and (statement not in mydata):
                mydata[statement] = opts["default"]

    def _mod_parse(self, mydata):
        """
        For parser data exposing a mod, execute the mod against
        the data itself.
        """
        for statement, opts in self._data.items():
            if statement in mydata and "mod" in opts:
                mydata[statement] = opts["mod"](mydata[statement])

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
