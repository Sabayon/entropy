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

from entropy.const import etpConst, const_convert_to_unicode, \
    const_convert_to_rawstring
from entropy.exceptions import EntropyException, DependenciesNotRemovable
from entropy.i18n import _
from entropy.output import teal, purple, darkgreen, brown, print_info, \
    red, print_warning

import entropy.dep
import entropy.tools


KERNEL_BINARY_VIRTUAL = const_convert_to_unicode("virtual/linux-binary")
KERNELS_DIR = const_convert_to_rawstring("/etc/kernels")
RELEASE_LEVEL = const_convert_to_rawstring("RELEASE_LEVEL")


def _get_kernels(entropy_client):
    matches, x_rc = entropy_client.atom_match(KERNEL_BINARY_VIRTUAL,
        multi_match = True, multi_repo = True)
    return matches, x_rc


def _remove_tag_from_slot(slot):
    if not hasattr(entropy.dep, "remove_tag_from_slot"):
        # backward compatibility
        return slot[::-1].split(",", 1)[-1][::-1]
    return entropy.dep.remove_tag_from_slot(slot)


def _get_target_tag(entropy_client, kernel_match):
    try:
        matches = entropy_client.get_reverse_queue([kernel_match],
            recursive = False)
    except DependenciesNotRemovable:
        # wtf should not happen
        raise
    tags = set()
    for pkg_id, pkg_repo in matches:
        tag = entropy_client.open_repository(pkg_repo).retrieveTag(pkg_id)
        if tag:
            tags.add(tag)

    if tags:
        tags = sorted(tags, reverse = True)
        return tags.pop(0)


def _setup_kernel_symlink(target_tag):
    eselect_exec = "/usr/bin/eselect"
    if os.access(eselect_exec, os.X_OK):
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

    subs = []
    for _curdir, subs, _files in os.walk(KERNELS_DIR):
        subs.extend(subs)

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
    if os.access(eselect_exec, os.X_OK):
        sts, xout = entropy.tools.getstatusoutput("%s opengl show" % (
            eselect_exec,))
        if sts == 0:
            out = xout
    return out


def _set_opengl_impl(opengl):
    eselect_exec = "/usr/bin/eselect"
    if os.access(eselect_exec, os.X_OK):
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


def switch_kernel(entropy_client, kernel_match, installer,
                  from_running=False):
    """
    Execute a kernel switch to the given kernel package.
    Caller is expected to acquire any relevant Entropy lock before
    calling this function.

    @param entropy_client: an Entropy Client object instance
    @type entropy_client: entropy.client.interfaces.Client
    @param kernel_match: an Entropy package match referencing
        a valid kernel package
    @type kernel_match: tuple
    @param installer: a callable function that is expected to install
        the provided package matches (calculating dependencies, etc).
        This function must have the following signature:
        <int> exit_status callable(<list> package_matches).
        If you plan on implementing something like --pretend,
        make sure to return a non-zero status as well.
    @type installer: callable
    @keyword from_running: if True, determine the current kernel from the
        running system
    @type from_running: bool
    @return: the execution status, 0 means fine
    @rtype: int
    """
    pkg_id, pkg_repo = kernel_match
    kernel_atom = entropy_client.open_repository(
        pkg_repo).retrieveAtom(pkg_id)
    # this can be None !
    target_tag = _get_target_tag(entropy_client, kernel_match)

    inst_repo = entropy_client.installed_repository()
    # try to look for the currently running kernel first if
    # --from-running is specified (use uname -r)
    latest_kernel = -1
    if from_running:
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
            _pkg_ids = list(inst_repo.searchBelongs(pkg_file))
            # if more than one, get the latest
            _pkg_ids.sort(reverse=True)
            if _pkg_ids:
                latest_kernel = _pkg_ids[0]
        if latest_kernel == -1:
            raise CannotFindRunningKernel(
                "Cannot find the currently running kernel")

    if latest_kernel == -1:
        latest_kernel, _k_rc = inst_repo.atomMatch(
            KERNEL_BINARY_VIRTUAL)
    installed_revdeps = []
    if (latest_kernel != -1) and target_tag:
        installed_revdeps = entropy_client.get_removal_queue(
            [latest_kernel], recursive = False)

    # only pull in packages that are installed at this time.
    def _installed_pkgs_translator(inst_pkg_id):
        if inst_pkg_id == latest_kernel:
            # will be added later
            return None
        key, slot = inst_repo.retrieveKeySlot(inst_pkg_id)
        target_slot = _remove_tag_from_slot(slot) + "," + target_tag

        pkg_id, pkg_repo = entropy_client.atom_match(key,
            match_slot = target_slot)
        if pkg_id == -1:
            return None
        return pkg_id, pkg_repo

    matches = map(_installed_pkgs_translator, installed_revdeps)
    matches = [x for x in matches if x is not None]
    matches.append(kernel_match)

    opengl = _get_opengl_impl()
    rc = installer(matches)
    if rc == 0:
        _set_opengl_impl(opengl)
        if target_tag:
            # if target_tag is None, we are unable to set the symlink
            _setup_kernel_symlink(target_tag)
        else:
            # try to guess, sigh, for now
            guessed_kernel_name = _guess_kernel_name(kernel_atom)
            if guessed_kernel_name:
                _setup_kernel_symlink(guessed_kernel_name)
        _show_kernel_warnings(kernel_atom)

    return rc


def list_kernels(entropy_client):
    """
    Return a sorted (by atom) list of currently available
    kernels.

    @param entropy_client: an Entropy Client object instance
    @type entropy_client: entropy.client.interfaces.Client
    @return: a sorted list of Entropy package matches
    @rtype: list
    """
    matches, _rc = _get_kernels(entropy_client)
    key_sorter = lambda x: \
        entropy_client.open_repository(x[1]).retrieveAtom(x[0])
    return sorted(matches, key=key_sorter)
