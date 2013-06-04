#!/usr/bin/python

import argparse
import cgi
import functools
import sys
import os
import re
import time

os.environ["ETP_GETTEXT_DOMAIN"] = "entropy-server"

# Entropy imports
sys.path.insert(0, "/usr/lib/entropy/lib")
sys.path.insert(0, "/usr/lib/entropy/server")
sys.path.insert(0, "/usr/lib/entropy/client")
sys.path.insert(0, "../lib")
sys.path.insert(0, "../server")
sys.path.insert(0, "../client")


# Entropy imports
from entropy.output import print_info, print_error, print_warning, \
    print_generic, is_stdout_a_tty, nocolor, darkgreen, teal, \
    purple, brown

# Portage imports
os.environ["ACCEPT_PROPERTIES"] = "* -interactive"
os.environ["FEATURES"] = "split-log"
os.environ["CMAKE_NO_COLOR"] = "yes"

from _emerge.actions import load_emerge_config
import portage
import portage.dep
import portage.versions


class AntiMatterPackage(object):
    """
    This object describes a potentially available update and
    exposes an API for easy retrieval of the update information.
    """

    def __init__(self, vardb, portdb, installed, available, status):
        """
        Constructor.

        @param vardb: Portage vardb object.
        @type vardb: opaque
        @param portdb: Portage portdb object.
        @type portdb: opaque
        @param installed: Atom object of the installed package.
        @type installed: portage.dep.Atom
        @param available: Atom object of the available package.
        @type available: portage.dep.Atom
        @param status: 1 for upgrade, -1 for downgrade, 0 for rebuild
        @type status: int
        """
        self._vardb = vardb
        self._portdb = portdb
        self._installed = installed
        self._available = available
        self._status = status

    def key(self):
        """
        Return the package key:slot string.
        """
        return self.target().cp

    def slot(self):
        """
        Return the package slot.
        """
        return self.target().slot

    def keyslot(self):
        """
        Return the package key:slot string.
        """
        target = self.target()
        return "%s:%s" % (target.cp, target.slot)

    def installed(self):
        """
        Return the installed package Atom object.
        """
        return self._installed

    def available(self):
        """
        Return the available package Atom object or None.
        """
        return self._available

    def target(self):
        """
        Automatically return the right object between available()
        and installed(). In particular, if available() is None,
        installed() is returned.
        """
        if self._available:
            return self._available
        return self._installed

    def dropped_upstream(self):
        """
        Return whether the package has been dropped upstream
        and no more updated versions are available for update.
        """
        return self._available is None

    def upgrade(self):
        """
        Return whether the package would be upgraded.
        """
        return self._status == 1

    def downgrade(self):
        """
        Return whether the package would be downgraded.
        """
        return self._status == -1


class BaseAntiMatterResult(object):
    """
    Base class for implementing AntiMatter result
    objects. Subclasses must implement the notify()
    method.
    """

    def __init__(self, result, nsargs):
        """
        Constructor.

        @param result: list of AntiMatterPackage objects
        @type result: list
        @param nsargs: ArgumentParser namespace object
        @type nsargs: argparse.Namespace
        """
        self._result = result
        self._nsargs = nsargs

    def notify(self):
        """
        Notify the result of an AntiMatter run using
        the list of AntiMatterPackage objects passed
        to the constructor.
        """
        raise NotImplementedError()


class StdoutAntiMatterResult(BaseAntiMatterResult):
    """
    BaseAntiMatterResult subclass that prints the results
    to stdout.
    """

    def __init__(self, result, nsargs):
        """
        Constructor.

        @param result: list of AntiMatterPackage objects
        @type result: list
        @param nsargs: ArgumentParser namespace object
        @type nsargs: argparse.Namespace
        """
        super(StdoutAntiMatterResult, self).__init__(
            result, nsargs)

    def notify(self):
        """
        Overridden from BaseAntiMatterResult
        """
        for package in self._result:

            if self._nsargs.extended:
                cp = package.key()
                slot = package.slot()

                from_ver = "x"
                inst = package.installed()
                if inst is not None:
                    from_ver = inst.version

                to_ver = "x"
                avail = package.available()
                if avail is not None:
                    to_ver = avail.version

                name = "%s:%s  [%s->%s]" % (
                    darkgreen(cp),
                    brown(slot),
                    teal(from_ver),
                    purple(to_ver))

            elif self._nsargs.verbose:
                name = package.target()
            else:
                name = package.keyslot()

            if self._nsargs.quiet:
                print_generic(name)
            else:
                print_info(name)


class HtmlAntiMatterResult(BaseAntiMatterResult):
    """
    BaseAntiMatterResult subclass that prints the results
    to stdout in HTML format.
    """

    def __init__(self, result, nsargs):
        """
        Constructor.

        @param result: list of AntiMatterPackage objects
        @type result: list
        @param nsargs: ArgumentParser namespace object
        @type nsargs: argparse.Namespace
        """
        super(HtmlAntiMatterResult, self).__init__(
            result, nsargs)

    def notify(self):
        """
        Overridden from BaseAntiMatterResult
        """
        txt = "<h3>" + str(len(self._result)) + " packages are %s</h3>"
        if self._nsargs.extinguished:
            txt = txt % ("extinguished",)
        elif self._nsargs.upgrade:
            txt = txt % ("upgradable",)
        elif self._nsargs.downgrade:
            txt = txt % ("downgradable",)
        elif self._nsargs.new:
            txt = txt % ("new",)
        elif self._nsargs.not_installed:
            txt = txt % ("not installed",)
        print_generic(txt)

        print_generic("<ul class='result'>")
        for package in self._result:

            if self._nsargs.extended:
                cp = package.key()
                slot = package.slot()

                from_ver = "x"
                inst = package.installed()
                if inst is not None:
                    from_ver = cgi.escape(inst.version)

                to_ver = "x"
                avail = package.available()
                if avail is not None:
                    to_ver = cgi.escape(avail.version)

                name = """\
  <li>
  <span class='rt'>%s:%s</span>
  &nbsp;&nbsp;
  [<span class='rd'>
    <span class='frompkg'>%s</span>
    %s
    <span class='topkg'>%s</span>
  </span>]
  </li>""" % (
                    cgi.escape(cp),
                    cgi.escape(slot),
                    cgi.escape(from_ver),
                    cgi.escape("->"),
                    cgi.escape(to_ver))

            elif self._nsargs.verbose:
                name = "<li class='rt'>%s</li>" % (
                    cgi.escape(package.target()),)
            else:
                name = "<li class='rt'>%s</li>" % (
                    cgi.escape(package.keyslot()),)

            print_generic(name)

        print_generic("</ul>")


class AntiMatter(object):
    """
    AntiMatter is a package update scanner that uses
    Portage and Entropy to determine
    """

    def __init__(self, nsargs):
        """
        Constructor.

        @param nsargs: argparse's parsed arguments.
        @param entropy_obj: an Entropy instance or None
        """
        self._nsargs = nsargs

    def _get_dbs(self):
        """
        Return a tuple containing (vardb, portdb)
        """
        emerge_config = load_emerge_config()
        emerge_settings, emerge_trees, _mtimedb = emerge_config
        settings = portage.config(clone=emerge_settings)

        portdb = emerge_trees[settings["ROOT"]]["porttree"].dbapi
        if not portdb.frozen:
            portdb.freeze()
        vardb = emerge_trees[settings["ROOT"]]["vartree"].dbapi

        return vardb, portdb

    def _new_scan(self):
        """
        Internal scan method, executes the actual scan and retuns
        a raw list of AntiMatterPackage objects.
        """
        vardb, portdb = self._get_dbs()
        new_days_old_secs = self._nsargs.new_days_old * 3600 * 24
        not_installed = self._nsargs.not_installed
        result = []

        cp_all = portdb.cp_all()
        cp_all.sort()
        root = portdb.porttree_root
        for count, package in enumerate(cp_all):

            count_str = "[%s of %s]" % (
                count, len(cp_all),)

            if self._nsargs.verbose:
                print_warning("%s :: %s" % (count_str, package),
                              back=True)

            if not not_installed:
                cp_dir = os.path.join(root, package)
                try:
                    mtime = os.path.getmtime(cp_dir)
                except (OSError, IOError):
                    mtime = 0.0

                if abs(time.time() - mtime) >= new_days_old_secs:
                    # not new enough
                    continue

            best_installed = portage.best(vardb.match(package))
            if best_installed:
                # package key is already installed, ignore
                continue

            best_visible = portage.best(portdb.match(package))
            if not best_visible:
                # wtf? package masked?
                continue

            try:
                slot, repo = portdb.aux_get(
                    best_visible, ["SLOT", "repository"])
            except KeyError:
                # portage is scrappy
                continue

            atom = portage.dep.Atom(
                "=%s:%s::%s" % (best_visible, slot, repo),
                allow_wildcard=True,
                allow_repo=True)

            pkg = AntiMatterPackage(
                vardb, portdb, None, atom, 1)
            result.append(pkg)

        if cp_all and self._nsargs.verbose:
            print_generic("")

        return result

    def _scan(self):
        """
        Internal scan method, executes the actual scan and retuns
        a raw list of AntiMatterPackage objects.
        """
        vardb, portdb = self._get_dbs()
        result = []

        vardb.lock()
        try:
            cpv_all = vardb.cpv_all()
            cpv_all.sort()
            for count, package in enumerate(cpv_all):

                count_str = "[%s of %s]" % (
                    count, len(cpv_all),)

                try:
                    slot, repo = vardb.aux_get(
                        package, ["SLOT", "repository"])
                except KeyError:
                    # package vanished, can still
                    # happen even if locked?
                    continue

                atom = portage.dep.Atom(
                    "=%s:%s::%s" % (package, slot, repo),
                    allow_wildcard=True,
                    allow_repo=True)

                if self._nsargs.verbose:
                    print_warning("%s :: %s" % (count_str, atom),
                                  back=True)

                key_slot = "%s:%s" % (atom.cp, atom.slot)

                best_visible = portage.best(portdb.match(key_slot))

                if not best_visible:
                    # dropped upstream
                    pkg = AntiMatterPackage(
                        vardb, portdb, atom, None, -1)
                    result.append(pkg)
                    if self._nsargs.verbose:
                        print_error(
                            "  %s no longer upstream or masked" % (key_slot,))
                    continue

                cmp_res = portage.versions.pkgcmp(
                    portage.versions.pkgsplit(best_visible),
                    portage.versions.pkgsplit(package))

                pkg = AntiMatterPackage(
                    vardb, portdb, atom,
                    best_visible, cmp_res)
                result.append(pkg)
        finally:
            vardb.unlock()


        if cpv_all and self._nsargs.verbose:
            print_generic("")

        return result

    def scan(self):
        """
        Execute a scan of the system and return a BaseAntiMatterResult
        object.
        """
        if self._nsargs.new or self._nsargs.not_installed:
            result = self._new_scan()
        else:
            result = self._scan()
        # apply filtering basing on arguments
        if self._nsargs.extinguished:
            result = [x for x in result if x.dropped_upstream()]
        elif self._nsargs.upgrade:
            result = [x for x in result if x.upgrade()]
        elif self._nsargs.downgrade:
            result = [x for x in result if x.downgrade()]
        elif self._nsargs.not_installed:
            result = [x for x in result if not x.installed()]

        def _regex_filter(regex, x):
            target = x.target()
            operator = target.operator
            target_str = target[len(operator):]
            return regex.match(target_str)

        for regex in self._nsargs.filters:
            result = list(filter(
                    functools.partial(_regex_filter, regex),
                    result))

        klass = StdoutAntiMatterResult
        if self._nsargs.html:
            klass = HtmlAntiMatterResult

        return klass(result, self._nsargs)


if __name__ == "__main__":

    # disable color if standard output is not a TTY
    if not is_stdout_a_tty():
        nocolor()

    parser = argparse.ArgumentParser(
        description="Automated package updates scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--verbose", "-v", action="store_true",
                        default=False, help="verbose output")
    parser.add_argument("--extended", "-x", action="store_true",
                        default=False, help="extended output")
    parser.add_argument("--quiet", "-q", action="store_true",
                        default=False, help="quiet output")
    parser.add_argument("--html", "-t", action="store_true",
                        default=False, help="prints in html format")

    parser.add_argument("--filter", "-f", dest="filters",
                        action="append", default=[],
                        help="filter package atoms using the given "
                        "regular expressions. They will be applied in "
                        "the given order, against the full package atom "
                        "string (which includes version, slot, repo: "
                        " app-foo/bar-1.2.3:slot::repo).")

    mg_group = parser.add_mutually_exclusive_group(required=True)
    mg_group.add_argument("--extinguished", "-e", action="store_true",
                          default=False,
                          help="list dead packages only (those which "
                          "upstream dropped)")
    mg_group.add_argument("--upgrade", "-u", action="store_true",
                          default=False,
                          help="list packages that would be upgraded")
    mg_group.add_argument("--downgrade", "-d", action="store_true",
                          default=False,
                          help="list packages that would be downgraded")
    mg_group.add_argument("--new", "-n", action="store_true",
                          default=False,
                          help="list packages that have been recently "
                          "added")
    mg_group.add_argument("--not-installed", "-i", action="store_true",
                          default=False,
                          help="list packages that haven't been installed")

    nsargs = None
    try:
        nsargs = parser.parse_args(sys.argv[1:])
        nsargs.filters = [re.compile(x) for x in nsargs.filters]
        # still hardcoded, but candidate for argparse argument
        # used in the calculation of new packages.
        nsargs.new_days_old = 14
    except re.error as err:
        print_error("Error, invalid regexp: %s" % (err,))
        raise SystemExit(1)

    try:
        antimatter = AntiMatter(nsargs)
        antimatter.scan().notify()
    except KeyboardInterrupt:
        print_error("Interrupted.")
        raise SystemExit(1)

    raise SystemExit(0)
