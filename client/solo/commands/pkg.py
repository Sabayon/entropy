# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import functools
import os
import sys
import argparse
import tempfile
import shutil

from entropy.const import etpConst, const_setup_directory, \
    const_convert_to_unicode, const_convert_to_rawstring
from entropy.i18n import _
from entropy.output import darkgreen, teal, brown, purple, darkred, blue

import entropy.tools
import entropy.dep

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand


class SoloPkg(SoloCommand):
    """
    Main Solo Smart command.
    """

    NAME = "pkg"
    ALIASES = ["smart"]
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Execute advanced tasks on Entropy packages and the running system.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._nsargs = None
        self._commands = {}
        self._savedir = etpConst['entropyunpackdir']
        self._ask = False

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloPkg.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloPkg.NAME))

        subparsers = parser.add_subparsers(
            title="action",
            description=_("execute advanced tasks on packages"),
            help=_("available commands"))

        def _add_ask_to_parser(p):
            p.add_argument(
                "--ask", "-a", action="store_true",
                default=self._ask,
                help=_("ask before making any changes"))

        def _argparse_easygoing_valid_entropy_path(string):
            if os.path.isfile(string) and os.path.exists(string):
                return string
            # see bug 3873, requires raw string
            msg = "%s: %s" % (
                _("not a valid Entropy package file"),
                string)
            msg = const_convert_to_rawstring(
                msg, from_enctype="utf-8")
            raise argparse.ArgumentTypeError(msg)

        quickpkg_parser = subparsers.add_parser(
            "quickpkg", help=_("generate packages from "
                               "the installed system"))
        quickpkg_parser.add_argument(
            "packages", nargs='+', metavar="<package>",
            help=_("installed package name"))
        quickpkg_parser.add_argument(
            "--savedir", metavar="<path>",
            type=self._argparse_is_valid_directory,
            default=self._savedir,
            help=_("destination directory "
                   "where to save generated packages"))
        _add_ask_to_parser(quickpkg_parser)
        quickpkg_parser.set_defaults(func=self._quickpkg)
        _commands["quickpkg"] = {}

        inflate_parser = subparsers.add_parser(
            "inflate", help=_("transform SPM package files "
                              "into Entropy ones"))
        inflate_parser.add_argument(
            "files", nargs='+', metavar="<file>",
            type=_argparse_easygoing_valid_entropy_path,
            help=_("SPM package file path"))
        inflate_parser.add_argument(
            "--savedir", metavar="<path>",
            type=self._argparse_is_valid_directory,
            default=self._savedir,
            help=_("destination directory "
                   "where to save generated packages"))
        _add_ask_to_parser(inflate_parser)
        inflate_parser.set_defaults(func=self._inflate)
        _commands["inflate"] = {}

        deflate_parser = subparsers.add_parser(
            "deflate", help=_("transform Entropy package files "
                              "into SPM ones"))
        deflate_parser.add_argument(
            "files", nargs='+', metavar="<file>",
            type=self._argparse_is_valid_entropy_package,
            help=_("Entropy package file path"))
        deflate_parser.add_argument(
            "--savedir", metavar="<path>",
            type=self._argparse_is_valid_directory,
            default=self._savedir,
            help=_("destination directory "
                   "where to save generated packages"))
        _add_ask_to_parser(deflate_parser)
        deflate_parser.set_defaults(func=self._deflate)
        _commands["deflate"] = {}

        extract_parser = subparsers.add_parser(
            "extract", help=_("extract Entropy metadata "
                              "from Entropy packages"))
        extract_parser.add_argument(
            "files", nargs='+', metavar="<file>",
            type=_argparse_easygoing_valid_entropy_path,
            help=_("Entropy package file path"))
        extract_parser.add_argument(
            "--savedir", metavar="<path>",
            type=self._argparse_is_valid_directory,
            default=self._savedir,
            help=_("destination directory "
                   "where to save generated packages"))
        _add_ask_to_parser(extract_parser)
        extract_parser.set_defaults(func=self._extract)
        _commands["extract"] = {}

        self._commands = _commands
        return parser

    def parse(self):
        """
        Parse command
        """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return functools.partial(self.print_help, parser), []

        self._nsargs = nsargs
        return self._call_locked, [nsargs.func]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        return self._hierarchical_bashcomp(last_arg, [], self._commands)

    def _scan_packages(self, entropy_client, packages, installed=False):
        """
        Scan the list of package names filtering out unmatched
        entries.
        """
        found_pkgs = []
        for package in packages:
            if installed:
                repo = entropy_client.installed_repository()
                repo_id = repo.repository_id()
                package_id, _pkg_rc = repo.atomMatch(package)
            else:
                package_id, repo_id = entropy_client.atom_match(package)
            if package_id == -1:
                mytxt = "!!! %s: %s %s." % (
                    purple(_("Warning")),
                    teal(const_convert_to_unicode(package)),
                    purple(_("is not available")),
                )
                entropy_client.output(
                    "!!!", level="warning", importance=1)
                entropy_client.output(
                    mytxt, level="warning", importance=1)
                entropy_client.output(
                    "!!!", level="warning", importance=1)
                continue
            found_pkgs.append((package_id, repo_id))
        return found_pkgs

    def _quickpkg(self, entropy_client):
        """
        Solo Pkg Quickpkg command.
        """
        packages = self._nsargs.packages
        ask = self._ask
        savedir = self._nsargs.savedir
        if not os.path.isdir(savedir) and not os.path.exists(savedir):
            # this is validated by the parser
            # but not in case of no --savedir provided
            const_setup_directory(savedir)
        if not os.path.exists(savedir):
            entropy_client.output(
                "%s: %s" % (
                    brown(_("broken directory path")),
                    savedir,), level="error", importance=1)
            return 1

        entropy_repository = entropy_client.installed_repository()

        pkg_matches = self._scan_packages(entropy_client, packages,
                                          installed=True)
        if not pkg_matches:
            return 1

        entropy_client.output(
            "%s:" % (
                brown(_("This is the list of packages "
                        "that would be considered")),
                ))

        for pkg in pkg_matches:
            pkg_id, pkg_repo = pkg
            repo = entropy_client.open_repository(pkg_repo)
            atom = repo.retrieveAtom(pkg_id)
            entropy_client.output(
                "[%s] %s" % (
                    brown(pkg_repo),
                    darkgreen(atom),),
                header="  ")

        if ask:
            q_rc = entropy_client.ask_question(
                _("Would you like to continue ?"))
            if q_rc == _("No"):
                return 0

        for pkg in pkg_matches:

            pkg_id, pkg_repo = pkg
            repo = entropy_client.open_repository(pkg_repo)
            atom = repo.retrieveAtom(pkg_id)
            entropy_client.output(
                "%s: %s" % (
                    teal(_("generating package")),
                    purple(atom),),
                header=brown(" @@ "), back=True)

            pkg_data = repo.getPackageData(pkg_id)
            file_path = entropy_client.generate_package(
                pkg_data, save_directory=savedir)
            if file_path is None:
                entropy_client.output(
                    "%s: %s" % (
                        darkred(_("package file creation error")),
                        blue(atom),),
                    level="error", importance=1)
                return 3

            entropy_client.output(
                "[%s] %s: %s" % (
                    darkgreen(atom),
                    teal(_("package generated")),
                    purple(file_path),),
                header=brown(" ## "))

        return 0

    def _inflate(self, entropy_client):
        """
        Solo Pkg Inflate command.
        """
        files = self._nsargs.files
        ask = self._ask
        savedir = self._nsargs.savedir
        if not os.path.isdir(savedir) and not os.path.exists(savedir):
            # this is validated by the parser
            # but not in case of no --savedir provided
            const_setup_directory(savedir)
        if not os.path.exists(savedir):
            entropy_client.output(
                "%s: %s" % (
                    brown(_("broken directory path")),
                    savedir,), level="error", importance=1)
            return 1

        spm = entropy_client.Spm()

        for _file in files:
            entropy_client.output(
                "%s: %s" % (
                    teal(_("working on package file")),
                    purple(_file)),
                header=darkred(" @@ "),
                back=True)
            file_name = os.path.basename(_file)
            package_path = os.path.join(savedir, file_name)
            if os.path.realpath(_file) != os.path.realpath(package_path):
                # make a copy first
                shutil.copy2(_file, package_path)

            pkg_data = spm.extract_package_metadata(package_path)
            entropy_client.output(
                "%s: %s" % (
                    teal(_("package file extraction complete")),
                    purple(package_path)),
                header=darkred(" @@ "),
                back=True)

            # append development revision number
            # and create final package file name
            pkg_data['revision'] = etpConst['spmetprev']
            download_dirpath = entropy.tools.create_package_dirpath(
                pkg_data['branch'], nonfree=False, restricted=False)
            download_name = entropy.dep.create_package_filename(
                pkg_data['category'], pkg_data['name'],
                pkg_data['version'], pkg_data['versiontag'],
                ext=etpConst['packagesext'],
                revision=pkg_data['revision'])
            pkg_data['download'] = download_dirpath + "/" + download_name

            # migrate to the proper format
            final_path = os.path.join(savedir, download_name)
            if package_path != final_path:
                shutil.move(package_path, final_path)
            package_path = final_path

            tmp_fd, tmp_path = tempfile.mkstemp(
                prefix="equo.smart.inflate.",
                dir=savedir)
            os.close(tmp_fd)

            # attach entropy metadata to package file
            repo = entropy_client.open_generic_repository(tmp_path)
            repo.initializeRepository()
            package_id = repo.addPackage(
                pkg_data, revision=pkg_data['revision'])
            repo.commit()
            repo.close()

            entropy_client.output(
                "%s: %s" % (
                    teal(_("package metadata generation complete")),
                    purple(package_path)),
                header=darkred(" @@ "),
                back=True)

            entropy.tools.aggregate_entropy_metadata(
                package_path, tmp_path)
            os.remove(tmp_path)

            entropy_client.output(
                "%s: %s" % (
                    teal(_("package file generated at")),
                    purple(package_path)),
                header=darkred(" @@ "))

        return 0

    def _deflate(self, entropy_client):
        """
        Solo Pkg Deflate command.
        """
        files = self._nsargs.files
        ask = self._ask
        savedir = self._nsargs.savedir
        if not os.path.isdir(savedir) and not os.path.exists(savedir):
            # this is validated by the parser
            # but not in case of no --savedir provided
            const_setup_directory(savedir)
        if not os.path.exists(savedir):
            entropy_client.output(
                "%s: %s" % (
                    brown(_("broken directory path")),
                    savedir,), level="error", importance=1)
            return 1

        for _file in files:
            entropy_client.output(
                "%s: %s" % (
                    teal(_("working on package file")),
                    purple(_file)),
                header=darkred(" @@ "),
                back=True)

            file_name = os.path.basename(_file)
            package_path = os.path.join(savedir, file_name)
            ext_rc = entropy.tools.remove_entropy_metadata(
                _file, package_path)
            if not ext_rc:
                entropy_client.output(
                    "%s: %s" % (
                        teal(_("error during metadata extraction")),
                        purple(_file)),
                    header=darkred(" @@ "),
                    level="error", importance=1)
                return 1

            entropy_client.output(
                "%s: %s" % (
                    teal(_("package file generated")),
                    purple(package_path)),
                header=darkred(" @@ "))

        return 0

    def _extract(self, entropy_client):
        """
        Solo Pkg Extract command.
        """
        files = self._nsargs.files
        ask = self._ask
        savedir = self._nsargs.savedir
        if not os.path.isdir(savedir) and not os.path.exists(savedir):
            # this is validated by the parser
            # but not in case of no --savedir provided
            const_setup_directory(savedir)
        if not os.path.exists(savedir):
            entropy_client.output(
                "%s: %s" % (
                    brown(_("broken directory path")),
                    savedir,), level="error", importance=1)
            return 1

        for _file in files:
            entropy_client.output(
                "%s: %s" % (
                    teal(_("working on package file")),
                    purple(_file)),
                header=darkred(" @@ "),
                back=True)

            file_name = os.path.basename(_file)
            package_path = os.path.join(
                savedir, file_name + ".db")
            ext_rc = entropy.tools.dump_entropy_metadata(
                _file, package_path)
            if not ext_rc:
                entropy_client.output(
                    "%s: %s" % (
                        teal(_("error during metadata extraction")),
                        purple(_file)),
                    header=darkred(" @@ "),
                    level="error", importance=1)
                return 1

            entropy_client.output(
                "%s: %s" % (
                    teal(_("metadata file generated")),
                    purple(package_path)),
                header=darkred(" @@ "))

        return 0

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloPkg,
        SoloPkg.NAME,
        _("execute advanced tasks on packages"))
    )
