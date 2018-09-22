# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{System Kernel Switch Utility Library for Sabayon}.

"""

import os
import subprocess
import errno
import codecs
import collections

from entropy.const import etpConst, const_convert_to_unicode, \
    const_convert_to_rawstring
from entropy.exceptions import EntropyException, DependenciesNotRemovable
from entropy.i18n import _
from entropy.output import teal, purple, darkgreen, brown, print_info, \
    red, print_warning

import entropy.dep
import entropy.tools


KERNEL_BINARY_VIRTUAL = const_convert_to_unicode("virtual/linux-binary")
KERNEL_BINARY_LTS_VIRTUAL = const_convert_to_unicode("virtual/linux-binary-lts")
KERNEL_CATEGORY = const_convert_to_unicode("sys-kernel")
KERNELS_DIR = const_convert_to_rawstring("/etc/kernels")
RELEASE_LEVEL = const_convert_to_rawstring("RELEASE_LEVEL")


def _remove_tag_from_slot(slot):
    if not hasattr(entropy.dep, "remove_tag_from_slot"):
        # backward compatibility
        return slot[::-1].split(",", 1)[-1][::-1]
    return entropy.dep.remove_tag_from_slot(slot)


def _setup_kernel_symlink(target_tag):
    eselect_exec = "/usr/bin/eselect"
    if os.path.lexists(eselect_exec):
        subprocess.call((eselect_exec, "kernel", "set", target_tag))


def _guess_kernel_name(kernel_atom):
    """
    This method takes advantage of Entropy kernel package info files available
    at /etc/kernels/<pkg-name>-<pkg-ver>/ directory.
    This function tries to read uname -r from the RELEASE_LEVEL file.
    """
    namever = entropy.dep.remove_cat(kernel_atom)
    kernel_meta_file = os.path.join(KERNELS_DIR, namever, RELEASE_LEVEL)
    if os.path.isfile(kernel_meta_file):
        try:
            with open(kernel_meta_file, "r") as km_f:
                kernel_name = km_f.readline().strip()
                if kernel_name:
                    return kernel_name
        except (OSError, IOError):
            return None


def _guess_kernel_package_file(release_level):
    """
    This method takes advantage of Entropy kernel package info files available
    at /etc/kernels/<pkg-name>-<pkg-ver>/ directory looking for
    a RELEASE_LEVEL file whose content matches release_level (uname -r).
    """
    if not os.path.isdir(KERNELS_DIR):
        return None

    subs = collections.deque()
    for _curdir, subdirs, _files in os.walk(KERNELS_DIR):
        subs.extend(subdirs)
        break

    for sub in subs:
        sub_path = os.path.join(KERNELS_DIR, sub)
        try:
            dir_list = os.listdir(sub_path)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
            continue
        if RELEASE_LEVEL not in dir_list:
            continue

        level_path = os.path.join(
            sub_path, RELEASE_LEVEL)
        with codecs.open(
            level_path, "r", etpConst["conf_raw_encoding"]) as rel_f:
            rel_line = rel_f.readline().strip()

        if release_level == rel_line:
            return const_convert_to_unicode(level_path)


def _get_opengl_impl():
    eselect_exec = "/usr/bin/eselect"
    sts = 1
    out = "xorg-x11"
    if os.path.lexists(eselect_exec):
        sts, xout = entropy.tools.getstatusoutput("%s opengl show" % (
            eselect_exec,))
        if sts == 0:
            out = xout
    return out


def _set_opengl_impl(opengl):
    eselect_exec = "/usr/bin/eselect"
    if os.path.lexists(eselect_exec):
        args = (eselect_exec, "opengl", "set", opengl)
        subprocess.call(args)


def _show_kernel_warnings(kernel_atom):
    print_info("%s %s" % (purple(kernel_atom), teal(_("has been installed."))))
    print_warning("%s: %s" % (red(_("Attention")),
        brown(_("some external drivers cannot work across multiple kernels."))))
    print_warning(darkgreen(_("Please reboot your computer now !")))


class CannotFindRunningKernel(EntropyException):
    """
    Exception raised when the kernel switching code is unable
    to find the currently running kernel. This code path is
    triggered when switch_kernel() is called with from_running=True.
    """


class KernelSwitcher(object):

    """
    Helper class for operating system kernel upgrades.

    This class is process and thread safe with regards to the
    Installed Packages Repository.
    """

    def __init__(self, entropy_client):
        """
        KernelSwitcher constructor.

        @param entropy_client: an Entropy Client object instance
        @type entropy_client: entropy.client.interfaces.Client
        """
        self._entropy = entropy_client

    def _get_kernels(self):
        """
        Return a list of kernel package matches.
        """
        kernel_virtual_pkgs, _rc = self._entropy.atom_match(
            KERNEL_BINARY_VIRTUAL,
            multi_match=True, multi_repo=True)

        kernel_packages = []

        for pkg_id, repo_id in kernel_virtual_pkgs:
            repo = self._entropy.open_repository(repo_id)
            kernel_pkg_ids = repo.retrieveReverseDependencies(pkg_id)
            for kernel_pkg_id in kernel_pkg_ids:
                atom = repo.retrieveAtom(kernel_pkg_id)
                category = entropy.dep.dep_getcat(atom)
                if category == KERNEL_CATEGORY:
                    kernel_packages.append((atom, kernel_pkg_id, repo_id))

        return kernel_packages

    def _get_target_tag(self, kernel_match):
        """
        Get the package tag for the given kernel package match.

        @param kernel_match: an Entropy package match referencing
            a valid kernel package
        @type kernel_match: tuple
        """
        try:
            matches = self._entropy.get_reverse_queue(
                [kernel_match], recursive=False)
        except DependenciesNotRemovable:
            # wtf should not happen
            raise

        tags = set()
        for pkg_id, pkg_repo in matches:
            tag = self._entropy.open_repository(
                pkg_repo).retrieveTag(pkg_id)
            if tag:
                tags.add(tag)

        if tags:
            tags = sorted(tags, reverse = True)
            return tags.pop(0)

    def running_kernel_package(self):
        """
        Return the currently running kernel package by looking
        at uname() release.
        The release string is then used to search the corresponding
        kernel package file (typically called RELEASE_LEVEL) and
        match it against the installed packages files.
        The installed package identifier is then returned or
        CannotFindRunningKernel() exception is raised otherwise.

        This method is process and thread safe with regards to the Installed
        Packages Repository.

        @return: the installed package identifier
        @rtype: int
        @raise CannotFindRunningKernel: if the package is not found
        """
        try:
            uname_r = os.uname()[2]
        except OSError:
            uname_r = None
        except IndexError:
            uname_r = None

        pkg_file = None
        if uname_r is not None:
            pkg_file = _guess_kernel_package_file(uname_r)

        if pkg_file is not None:
            inst_repo = self._entropy.installed_repository()
            with inst_repo.shared():
                pkg_ids = list(inst_repo.searchBelongs(pkg_file))
            if pkg_ids:
                # if more than one, get the latest
                pkg_ids.sort(reverse=True)
                return pkg_ids[0]

        raise CannotFindRunningKernel(
            "Cannot find the currently running kernel")

    def prepared_switch(self, kernel_match, installer, from_running=False):
        """
        Return a PreparedSwitch object that can be used to execute the kernel
        switch process. API user should call, in order, pre(), run() and post().
        post() should only be called if run() returns zero exit status.

        This method is process and thread safe with regards to the Installed
        Packages Repository.
        """

        class PreparedSwitch(object):

            def __init__(self, switcher, entropy_client, kernel_match,
                         installer, from_running):
                self._switcher = switcher
                self._entropy = entropy_client
                self._kernel_match = kernel_match
                self._installer = installer
                self._from_running = from_running
                self._opengl = None
                self._matches = None
                self._target_tag = None

            def get_queue(self):
                """
                Return the install queue, this must be called after pre().
                """
                return self._matches

            def pre(self):
                # this can be None !
                self._target_tag = self._switcher._get_target_tag(
                    self._kernel_match)

                inst_repo = self._entropy.installed_repository()
                # try to look for the currently running kernel first if
                # --from-running is specified (use uname -r)
                latest_kernel = -1
                if self._from_running:
                    try:
                        latest_kernel = self._switcher.running_kernel_package()
                    except CannotFindRunningKernel:
                        raise

                # only pull in packages that are installed at this time.
                def _installed_pkgs_translator(inst_pkg_id):
                    if inst_pkg_id == latest_kernel:
                        # will be added later
                        return None
                    key, slot = inst_repo.retrieveKeySlot(inst_pkg_id)
                    target_slot = _remove_tag_from_slot(
                        slot) + "," + self._target_tag

                    pkg_id, pkg_repo = self._entropy.atom_match(key,
                        match_slot = target_slot)
                    if pkg_id == -1:
                        return None
                    return pkg_id, pkg_repo

                with inst_repo.shared():
                    if latest_kernel == -1:
                        latest_kernel, _k_rc = inst_repo.atomMatch(
                            KERNEL_BINARY_VIRTUAL)

                    installed_revdeps = []
                    if (latest_kernel != -1) and self._target_tag:
                        installed_revdeps = self._entropy.get_removal_queue(
                            [latest_kernel], recursive = False)

                    matches = map(_installed_pkgs_translator, installed_revdeps)

                matches = [x for x in matches if x is not None]
                matches.append(kernel_match)
                self._matches = matches

                self._opengl = _get_opengl_impl()

            def run(self):
                if self._matches is None:
                    raise TypeError("pre() not run")
                return self._installer(self._entropy, self._matches)

            def post(self):
                pkg_id, pkg_repo = self._kernel_match

                kernel_atom = self._entropy.open_repository(
                    pkg_repo).retrieveAtom(pkg_id)

                _set_opengl_impl(self._opengl)
                if self._target_tag:
                    # if target_tag is None, we are unable to set the symlink
                    _setup_kernel_symlink(self._target_tag)
                else:
                    # try to guess, sigh, for now
                    guessed_kernel_name = _guess_kernel_name(
                        kernel_atom)
                    if guessed_kernel_name:
                        _setup_kernel_symlink(guessed_kernel_name)
                _show_kernel_warnings(kernel_atom)

        return PreparedSwitch(self, self._entropy, kernel_match,
                              installer, from_running)

    def switch(self, kernel_match, installer, from_running=False):
        """
        Execute a kernel switch to the given kernel package.
        Caller is expected to acquire any relevant Entropy lock before
        calling this function.

        This method is process and thread safe with regards to the Installed
        Packages Repository.

        @param kernel_match: an Entropy package match referencing
            a valid kernel package
        @type kernel_match: tuple
        @param installer: a callable function that is expected to install
            the provided package matches (calculating dependencies, etc).
            This function must have the following signature:
            <int> exit_status callable(<Client> entropy_client,
                                       <list> package_matches).
            If you plan on implementing something like --pretend,
            make sure to return a non-zero status as well.
        @type installer: callable
        @keyword from_running: if True, determine the current kernel from the
            running system
        @type from_running: bool
        @return: the execution status, 0 means fine
        @rtype: int
        """
        switcher = self.prepared_switch(kernel_match, installer,
                                        from_running=from_running)
        switcher.pre()
        rc = switcher.run()
        if rc == 0:
            switcher.post()
        return rc

    def list(self):
        """
        Return a sorted (by atom) list of currently available
        kernels.

        This method is process and thread safe with regards to the Installed
        Packages Repository.

        @param entropy_client: an Entropy Client object instance
        @type entropy_client: entropy.client.interfaces.Client
        @return: a sorted list of Entropy package matches
        @rtype: list
        """
        matches = self._get_kernels()
        key_sorter = lambda x: x[0]
        result = [x[1:3] for x in sorted(matches, key=key_sorter)]
        return result
