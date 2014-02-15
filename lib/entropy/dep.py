# -*- coding: utf-8 -*-
# Entropy miscellaneous tools module
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy dependency functions module}.
    This module contains Entropy package dependency manipulation functions.

"""
import re
from entropy.exceptions import InvalidAtom, EntropyException
from entropy.const import etpConst, const_cmp

# Imported from Gentoo portage_dep.py
# Copyright 1999-2010 Gentoo Foundation

# 2.1.1 A category name may contain any of the characters [A-Za-z0-9+_.-].
# It must not begin with a hyphen or a dot.
_cat = r'[\w+][\w+.-]*'

# 2.1.2 A package name may contain any of the characters [A-Za-z0-9+_-].
# It must not begin with a hyphen,
# and must not end in a hyphen followed by one or more digits.
_pkg = r'[\w+][\w+-]*?'

_v = r'(cvs\.)?(\d+)((\.\d+)*)([a-z]?)((_(pre|p|beta|alpha|rc)\d*)*)'
_rev = r'\d+'
_vr = _v + '(-r(' + _rev + '))?'

_cp = '(' + _cat + '/' + _pkg + '(-' + _vr + ')?)'
_cpv = '(' + _cp + '-' + _vr + ')'
_pv = '(?P<pn>' + _pkg + '(?P<pn_inval>-' + _vr + ')?)' + '-(?P<ver>' + _v + ')(-r(?P<rev>' + _rev + '))?'

ver_regexp = re.compile("^" + _vr + "$")
suffix_regexp = re.compile("^(alpha|beta|rc|pre|p)(\\d*)$")
suffix_value = {"pre": -2, "p": 0, "alpha": -4, "beta": -3, "rc": -1}
endversion_keys = ["pre", "p", "alpha", "beta", "rc"]

valid_category = re.compile("^\w[\w-]*")
invalid_atom_chars_regexp = re.compile("[()|@]")

def _ververify(myver):
    if myver.endswith("*"):
        m = ver_regexp.match(myver[:-1])
    else:
        m = ver_regexp.match(myver)
    if m:
        return True
    return False

_pv_re = re.compile('^' + _pv + '$', re.VERBOSE)
def _pkgsplit(mypkg):
    """
    @param mypkg: pv
    @return:
    1. None if input is invalid.
    2. (pn, ver, rev) if input is pv
    """
    m = _pv_re.match(mypkg)
    if m is None:
        return None

    if m.group('pn_inval') is not None:
        # package name appears to have a version-like suffix
        return None

    rev = m.group('rev')
    if rev is None:
        rev = '0'
    rev = 'r' + rev

    return  (m.group('pn'), m.group('ver'), rev)

def _generic_sorter(inputlist, cmp_func):

    inputs = inputlist[:]
    if len(inputs) < 2:
        return inputs
    max_idx = len(inputs)

    while True:
        changed = False
        for idx in range(max_idx):
            second_idx = idx+1
            if second_idx == max_idx:
                continue
            str_a = inputs[idx]
            str_b = inputs[second_idx]
            if cmp_func(str_a, str_b) < 0:
                inputs[idx] = str_b
                inputs[second_idx] = str_a
                changed = True
        if not changed:
            break

    return inputs

def isjustname(mypkg):
    """
    Checks to see if the depstring is only the package name (no version parts)

    Example usage:
        >>> isjustname('media-libs/test-3.0')
        False
        >>> isjustname('test')
        True
        >>> isjustname('media-libs/test')
        True

    @param mypkg: the package atom to check
    @param mypkg: string
    @rtype: int
    @return: if the package string is not just the package name
    """
    # must match, in case of "1.2.3-r1".
    rev = dep_get_spm_revision(mypkg)
    if rev == "r0":
        mypkg += "-r0"
    ver_rev = '-'.join(mypkg.split('-')[-2:])
    return not _ververify(ver_rev)

def catpkgsplit(mydata):
    """
    Takes a Category/Package-Version-Rev and returns a list of each.

    @param mydata: data to split
    @type mydata: string
    @rype: tuple
    @return:
        1.  If each exists, it returns (cat, pkgname, version, rev)
        2.  If cat is not specificed in mydata, cat will be "null"
        3.  if rev does not exist it will be '-r0'
    """

    # Categories may contain a-zA-z0-9+_- but cannot start with -
    mysplit = mydata.split("/")
    p_split = None
    if len(mysplit) == 1:
        retval = ("null",)
        p_split = _pkgsplit(mydata)
    elif len(mysplit) == 2:
        retval = (mysplit[0],)
        p_split = _pkgsplit(mysplit[1])
    if not p_split:
        return None
    retval += p_split
    return retval

def dep_getkey(mydep):
    """
    Return the category/package-name of a depstring.

    Example usage:
        >>> dep_getkey('media-libs/test-3.0')
        'media-libs/test'

    @param mydep: the depstring to retrieve the category/package-name of
    @type mydep: string
    @rtype: string
    @return: the package category/package-version
    """
    if not mydep:
        return mydep
    mydep = remove_tag(mydep)
    mydep = remove_usedeps(mydep)

    mydep = dep_getcpv(mydep)
    if mydep and (not isjustname(mydep)):
        mysplit = catpkgsplit(mydep)
        if not mysplit:
            return mydep
        return mysplit[0] + "/" + mysplit[1]

    return mydep

def dep_getcat(mydep):
    """
    Extract package category from dependency.
    """
    return dep_getkey(mydep).split("/")[0]

def remove_cat(mydep):
    """
    Drop category part from dependency, if any.
    """
    if "/" in mydep:
        return mydep.split("/", 1)[1]
    return mydep

def dep_getcpv(mydep):
    """
    Return the category-package-version with any operators/slot specifications stripped off

    Example usage:
        >>> dep_getcpv('>=media-libs/test-3.0')
        'media-libs/test-3.0'

    @param mydep: the depstring
    @type mydep: string
    @rtype: string
    @return: the depstring with the operator removed
    """
    if mydep and mydep[0] == "*":
        mydep = mydep[1:]
    if mydep and mydep[-1] == "*":
        mydep = mydep[:-1]
    if mydep and mydep[0] == "!":
        mydep = mydep[1:]
    if mydep[:2] in [">=", "<="]:
        mydep = mydep[2:]
    elif mydep[:1] in "=<>~":
        mydep = mydep[1:]
    colon = mydep.rfind(":")
    if colon != -1:
        mydep = mydep[:colon]

    return mydep

def dep_getslot(mydep):
    """
    # Imported from portage.dep
    # $Id: dep.py 11281 2008-07-30 06:12:19Z zmedico $

    Retrieve the slot on a depend.

    Example usage:
            >>> dep_getslot('app-misc/test:3')
            '3'

    @param mydep: the depstring to retrieve the slot of
    @type mydep: string
    @rtype: string
    @return: the slot
    """
    mydep = remove_tag(mydep)
    colon = mydep.find(":")
    if colon != -1:
        bracket = mydep.find("[", colon)
        if bracket == -1:
            return mydep[colon+1:]
        else:
            return mydep[colon+1:bracket]
    return None

def dep_getusedeps(depend):
    """
    # Imported from portage.dep
    # $Id: dep.py 11281 2008-07-30 06:12:19Z zmedico $

    Pull a listing of USE Dependencies out of a dep atom.

    Example usage:
            >>> dep_getusedeps('app-misc/test:3[foo,-bar]')
            ('foo', '-bar')

    @param depend: The depstring to process
    @type depend: String
    @rtype: List
    @return: List of use flags ( or [] if no flags exist )
    """
    use_list = []
    open_bracket = depend.find('[')
    # -1 = failure (think c++ string::npos)
    comma_separated = False
    bracket_count = 0
    while( open_bracket != -1 ):
        bracket_count += 1
        if bracket_count > 1:
            InvalidAtom("USE Dependency with more " + \
                "than one set of brackets: %s" % (depend,))
        close_bracket = depend.find(']', open_bracket )
        if close_bracket == -1:
            InvalidAtom("USE Dependency with no closing bracket: %s" % depend )
        use = depend[open_bracket + 1: close_bracket]
        # foo[1:1] may return '' instead of None, we don't want '' in the result
        if not use:
            InvalidAtom("USE Dependency with " + \
                "no use flag ([]): %s" % depend )
        if not comma_separated:
            comma_separated = "," in use

        if comma_separated and bracket_count > 1:
            InvalidAtom("USE Dependency contains a mixture of " + \
                "comma and bracket separators: %s" % depend )

        if comma_separated:
            for x in use.split(","):
                if x:
                    use_list.append(x)
                else:
                    InvalidAtom("USE Dependency with no use " + \
                            "flag next to comma: %s" % depend )
        else:
            use_list.append(use)

        # Find next use flag
        open_bracket = depend.find( '[', open_bracket+1 )

    return tuple(use_list)

def remove_usedeps(depend):
    """
    docstring_title

    @param depend: 
    @type depend: 
    @return: 
    @rtype: 
    """
    new_depend = ""
    skip = 0
    for char in depend:
        if char == "[":
            skip += 1
        elif char == "]":
            skip -= 1
            continue
        if skip == 0:
            new_depend += char

    return new_depend

def remove_slot(mydep):
    """
    # Imported from portage.dep
    # $Id: dep.py 11281 2008-07-30 06:12:19Z zmedico $

    Removes dep components from the right side of an atom:
            * slot
            * use
            * repo
    """
    colon = mydep.find(":")
    if colon != -1:
        mydep = mydep[:colon]
    else:
        bracket = mydep.find("[")
        if bracket != -1:
            mydep = mydep[:bracket]
    return mydep

def remove_tag_from_slot(slot):
    """
    Remove, if present, the tag part from SLOT string.
    Packages append the kernel tag to the slot, by comma separating it.
    """
    return slot[::-1].split(",", 1)[-1][::-1]

# input must be a valid package version or a full atom
def remove_revision(ver):
    """
    docstring_title

    @param ver: 
    @type ver: 
    @return: 
    @rtype: 
    """
    myver = ver.split("-")
    if myver[-1][0] == "r":
        return '-'.join(myver[:-1])
    return ver

def remove_tag(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    colon = mydep.rfind(etpConst['entropytagprefix'])
    if colon == -1:
        return mydep
    return mydep[:colon]

def remove_entropy_revision(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    dep = remove_package_operators(mydep)
    operators = mydep[:-len(dep)]
    colon = dep.rfind("~")
    if colon == -1:
        return mydep
    return operators+dep[:colon]

def dep_get_entropy_revision(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    #dep = remove_package_operators(mydep)
    colon = mydep.rfind("~")
    if colon != -1:
        myrev = mydep[colon+1:]
        try:
            myrev = int(myrev)
        except ValueError:
            return None
        return myrev
    return None

def dep_split_or_deps(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    dep = mydep.rstrip(etpConst['entropyordepquestion'])
    return dep.split(etpConst['entropyordepsep'])

dep_revmatch = re.compile('^r[0-9]')
def dep_get_spm_revision(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    myver = mydep.split("-")
    myrev = myver[-1]
    if dep_revmatch.match(myrev):
        return myrev
    else:
        return "r0"

def dep_get_match_in_repos(mydep):
    """
    docstring_title

    @param mydep: 
    @type mydep: 
    @return: 
    @rtype: 
    """
    colon = mydep.rfind(etpConst['entropyrepoprefix'])
    colon_offset = 1
    if colon == -1:
        # try with the alternate prefix
        colon = mydep.rfind(etpConst['entropyrepoprefix_alt'])
        colon_offset = 2
    if colon != -1:
        mydata = mydep[colon+colon_offset:]
        mydata = mydata.split(",")
        if not mydata:
            mydata = None
        return mydep[:colon], mydata
    else:
        return mydep, None

def dep_gettag(mydep):

    """
    Retrieve the slot on a depend.

    Example usage:
        >>> dep_gettag('app-misc/test#2.6.23-sabayon-r1')
        '2.6.23-sabayon-r1'

    """
    dep = mydep[:]
    dep = remove_entropy_revision(dep)
    colon = dep.rfind(etpConst['entropytagprefix'])
    if colon != -1:
        mydep = dep[colon+1:]
        rslt = remove_slot(mydep)
        return rslt
    return None

def remove_package_operators(atom):
    """
    docstring_title

    @param atom: 
    @type atom: 
    @return: 
    @rtype: 
    """
    return atom.lstrip("><=~")

def compare_versions(ver1, ver2):
    """
    docstring_title

    @param ver1: 
    @type ver1: 
    @param ver2: 
    @type ver2: 
    @return: 
    @rtype: 
    """
    if ver1 == ver2:
        return 0
    match1 = None
    match2 = None
    if ver1:
        match1 = ver_regexp.match(ver1)
    if ver2:
        match2 = ver_regexp.match(ver2)

    # checking that the versions are valid
    invalid = False
    invalid_rc = 0
    if not match1:
        invalid = True
    elif not match1.groups():
        invalid = True
    elif not match2:
        invalid_rc = 1
        invalid = True
    elif not match2.groups():
        invalid_rc = 1
        invalid = True
    if invalid:
        return invalid_rc

    # building lists of the version parts before the suffix
    # first part is simple
    list1 = [int(match1.group(2))]
    list2 = [int(match2.group(2))]

    # this part would greatly benefit from a fixed-length version pattern
    if len(match1.group(3)) or len(match2.group(3)):
        vlist1 = match1.group(3)[1:].split(".")
        vlist2 = match2.group(3)[1:].split(".")
        for i in range(0, max(len(vlist1), len(vlist2))):
            # Implcit .0 is given a value of -1, so that 1.0.0 > 1.0, since it
            # would be ambiguous if two versions that aren't literally equal
            # are given the same value (in sorting, for example).
            if len(vlist1) <= i or len(vlist1[i]) == 0:
                list1.append(-1)
                list2.append(int(vlist2[i]))
            elif len(vlist2) <= i or len(vlist2[i]) == 0:
                list1.append(int(vlist1[i]))
                list2.append(-1)
            # Let's make life easy and use integers unless we're forced to use floats
            elif (vlist1[i][0] != "0" and vlist2[i][0] != "0"):
                list1.append(int(vlist1[i]))
                list2.append(int(vlist2[i]))
            # now we have to use floats so 1.02 compares correctly against 1.1
            else:
                list1.append(float("0."+vlist1[i]))
                list2.append(float("0."+vlist2[i]))

    # and now the final letter
    if len(match1.group(5)):
        list1.append(ord(match1.group(5)))
    if len(match2.group(5)):
        list2.append(ord(match2.group(5)))

    for i in range(0, max(len(list1), len(list2))):
        if len(list1) <= i:
            return -1
        elif len(list2) <= i:
            return 1
        elif list1[i] != list2[i]:
            return list1[i] - list2[i]

    # main version is equal, so now compare the _suffix part
    list1 = match1.group(6).split("_")[1:]
    list2 = match2.group(6).split("_")[1:]

    for i in range(0, max(len(list1), len(list2))):
        if len(list1) <= i:
            s1 = ("p", "0")
        else:
            s1 = suffix_regexp.match(list1[i]).groups()
        if len(list2) <= i:
            s2 = ("p", "0")
        else:
            s2 = suffix_regexp.match(list2[i]).groups()
        if s1[0] != s2[0]:
            return suffix_value[s1[0]] - suffix_value[s2[0]]
        if s1[1] != s2[1]:
            # it's possible that the s(1|2)[1] == ''
            # in such a case, fudge it.
            try:
                r1 = int(s1[1])
            except ValueError:
                r1 = 0
            try:
                r2 = int(s2[1])
            except ValueError:
                r2 = 0
            return r1 - r2

    # the suffix part is equal to, so finally check the revision
    if match1.group(10):
        r1 = int(match1.group(10))
    else:
        r1 = 0
    if match2.group(10):
        r2 = int(match2.group(10))
    else:
        r2 = 0
    return r1 - r2

tag_regexp = re.compile("^([A-Za-z0-9+_.-]+)?$")
def is_valid_package_tag(tag):
    """
    Return whether string is a valid package tag.

    @param tag: package tag to test
    @type tag: string
    @return: True, if valid
    @rtype: bool
    """
    match = tag_regexp.match(tag)
    if not match:
        return False
    if not match.groups():
        return False
    return True

def entropy_compare_package_tags(tag_a, tag_b):
    """
    Compare two Entropy package tags using builtin cmp().

    @param tag_a: Entropy package tag
    @type tag_a: string
    @param tag_b: Entropy package tag
    @type tag_b: string
    return: negative number if tag_a < tag_b, positive number if tag_a > tag_b.
        zero if tag_a == tag_b.
    rtype: int
    """
    return const_cmp(tag_a, tag_b)

def sort_entropy_package_tags(tags):
    """
    Return a sorted list of Entropy package tags.

    @param tags: list of Entropy package tags
    @type tags: list
    @return: sorted list of Entropy package tags
    @rtype: list
    """
    return sorted(tags)

def entropy_compare_versions(ver_data, ver_data2):
    """
    @description: compare two lists composed by
        [version,tag,revision] and [version,tag,revision]
        if ver_data > ver_data2 --> positive number
        if ver_data == ver_data2 --> 0
        if ver_data < ver_data2 --> negative number
    @input package: ver_data[version,tag,rev] and ver_data2[version,tag,rev]
    @output: integer number
    """
    a_ver, a_tag, a_rev = ver_data
    b_ver, b_tag, b_rev = ver_data2

    # if both are tagged, check tag first
    rc = 0
    if a_tag and b_tag:
        rc = const_cmp(a_tag, b_tag)
    if rc == 0:
        rc = compare_versions(a_ver, b_ver)

    if rc == 0:
        # check tag
        tag_cmp = entropy_compare_package_tags(a_tag, b_tag)
        if tag_cmp < 0:
            return -1
        elif tag_cmp > 0:
            return 1
        else:
            # check rev
            if a_rev > b_rev:
                return 1
            elif a_rev < b_rev:
                return -1
            return 0

    return rc

def get_newer_version(versions):
    """
    Return a sorted list of versions

    @param versions: input version list
    @type versions: list
    @return: sorted version list
    @rtype: list
    """
    return _generic_sorter(versions, compare_versions)

def get_entropy_newer_version(versions):
    """
    Sort a list of entropy package versions.

    @param versions: list of package versions
    @type versions: list
    @return: sorted list
    @rtype: list
    """
    return _generic_sorter(versions, entropy_compare_versions)

sha1_re = re.compile(r"(.*)\.([a-f\d]{40})(.*)")
def get_entropy_package_sha1(package_name):
    """
    Extract the SHA1 checksum from a package file name.

    @param package_name: package file name
    @type package_name: string
    @return: the package SHA1 checksum, if any, or None
    @rtype: string or None
    """
    match = sha1_re.match(package_name)
    if match:
        groups = match.groups()
        if len(groups) != 3:
            return
        return groups[1]

def remove_entropy_package_sha1(package_name):
    """
    Remove the SHA1 checksum from a package file name.

    @param package_name: package file name
    @type package_name: string
    """
    match = sha1_re.match(package_name)
    if match:
        groups = match.groups()
        if len(groups) != 3:
            return package_name
        return groups[0]
    return package_name

def create_package_filename(category, name, version, package_tag,
                            ext = None, revision = None,
                            sha1 = None):
    """
    Create package filename string.

    @param category: package category
    @type category: string
    @param name: package name
    @type name: string
    @param version: package version
    @type version: string
    @param package_tag: package tag, if any, or None
    @type package_tag: string or None
    @keyword ext: alternative package file extension
    @type ext: string
    @keyword sha1: a SHA1 checksum to add to the file name
    @type sha1: string
    @return: package file name string
    @rtype: string
    """
    if package_tag:
        package_tag = "%s%s" % (etpConst['entropytagprefix'], package_tag,)
    else:
        package_tag = ''

    package_name = "%s:%s-%s" % (category, name, version,)
    package_name += package_tag
    if ext is None:
        ext = etpConst['packagesext']
    if sha1 is not None:
        package_name += ".%s" % (sha1,)
    if revision is not None:
        package_name += "~%d" % (revision,)
    package_name += ext
    return package_name

def create_package_relative_path(category, name, version, package_tag,
                                 ext = None, revision = None,
                                 sha1 = None):
    """
    Create package relative path, containing the filename string.

    The relative path contains a sub-directory part that is used to
    distribute files across different directories (to avoid hot spots).

    @param category: package category
    @type category: string
    @param name: package name
    @type name: string
    @param version: package version
    @type version: string
    @param package_tag: package tag, if any, or None
    @type package_tag: string or None
    @keyword ext: alternative package file extension
    @type ext: string
    @keyword sha1: a SHA1 checksum to add to the file name
    @type sha1: string
    @return: package file name string
    @rtype: string
    """
    return category + "/" + create_package_filename(
        category, name, version, package_tag, ext = ext,
        revision = revision, sha1 = sha1)

def strip_entropy_package_extension(pkg_path):
    """
    Strip entropy package file extension from package path pkg_path.

    @param pkg_path: package path
    @type pkg_path: string
    @return: stripped package path
    @rtype: string
    """
    return pkg_path.rstrip(etpConst['packagesext'])

def exploit_package_filename(package_name):
    """
    This is the inverse function of create_package_filename, and returns
    a tuple composed by category, name, version, package_tag (None if not set),
    SHA1 checksum (None if not set), and additional revision (as int).
    package_name should be a string like this:
        <category>:<name>-<version>[.<sha1>][~<revision>[#<tag>]][.tbz2]

    @param package_name: package file name
    @type package_name: string
    @return: tuple of strings/int composed by (category, name, version,
        package_tag, revision)
    @rtype: tuple
    @raise AttributeError: if package_name string passed is improperly formatted
    """
    pkg_str = strip_entropy_package_extension(package_name)
    pkg_str = pkg_str.replace(":", "/")
    pkg_str = strip_entropy_package_extension(pkg_str)
    etp_rev = dep_get_entropy_revision(pkg_str)
    pkg_str = remove_entropy_revision(pkg_str)
    etp_sha1 = get_entropy_package_sha1(pkg_str)
    pkg_str = remove_entropy_package_sha1(pkg_str)
    etp_tag = dep_gettag(pkg_str)
    pkg_str = remove_tag(pkg_str)
    split_data = catpkgsplit(pkg_str)
    if split_data is None:
        raise AttributeError("invalid package name passed: %s" % (
                package_name,))
    etp_cat, etp_name, ver, rev = split_data
    if rev != "r0":
        ver += "-" + rev
    return etp_cat, etp_name, ver, etp_tag, etp_sha1, etp_rev

def create_package_atom_string(category, name, version, package_tag):
    """
    Create Entropy package atom string.

    @param category: package category
    @type category: string
    @param name: package name
    @type name: string
    @param version: package version
    @type version: string
    @param package_tag: package tag, if any, or None
    @type package_tag: string or None
    @return: package atom string
    @rtype: string
    """
    if package_tag:
        package_tag = "%s%s" % (etpConst['entropytagprefix'], package_tag,)
    else:
        package_tag = ''
    package_name = "%s/%s-%s" % (category, name, version,)
    package_name += package_tag
    return package_name

class Dependency(object):

    """
    Helper class used to evaluate dependency string containing boolean
    expressions such as: (dep1 & dep2) | dep 3
    """

    def __init__(self, entropy_dep, entropy_repository_list):
        """
        Dependency constructor.

        @param entropy_dep: entropy package dependency
        @type entropy_dep: string
        @param entropy_repository_list: ordered list of EntropyRepositoryBase
            instances
        @type entropy_repository_list: list
        """
        self.__entropy_repository_list = entropy_repository_list
        self.__dep = entropy_dep

    def get(self):
        """
        Return encapsulated depdenency string

        @rtype: string
        """
        return self.__dep

    def __bool__(self):
        """
        Same as __nonzero__ but meant for Python 3.x support
        """
        for entropy_repository in self.__entropy_repository_list:
            pkg_id, res = entropy_repository.atomMatch(self.__dep)
            if res == 0:
                return True
        return False

    def __nonzero__(self):
        """
        Tries to match entropy_dep and returns True or False if dependency
        is matched.
        """
        for entropy_repository in self.__entropy_repository_list:
            pkg_id, res = entropy_repository.atomMatch(self.__dep)
            if res == 0:
                return True
        return False

    def evaluate(self):
        """
        Evaluate dependency trying to match dentropy_dep across all the
        available repositories and return package matches.
        """
        eval_data = set()
        for entropy_repository in self.__entropy_repository_list:
            repo_id = entropy_repository.repository_id()
            pkg_deps, res = entropy_repository.atomMatch(self.__dep,
                multiMatch = True)
            if res == 0:
                eval_data.update((x, repo_id) for x in pkg_deps)
        return eval_data

class DependencyStringParser(object):

    """
    Conditional dependency string parser. It is used by Entropy dependency
    matching logic to evaluate dependency conditions containing boolean
    operators. Example: "( app-foo/foo & foo-misc/foo ) | foo-misc/new-foo"

    Example usage (self is an EntropyRepositoryBase instance):
    >>> parser = DependencyStringParser("app-foo/foo & foo-misc/foo", self)
    >>> matched, outcome = parser.parse()
    >>> matched
    True
    >>> outcome
    ["app-foo/foo", "foo-misc/foo"]

    """
    LOGIC_AND = "&"
    LOGIC_OR = "|"

    class MalformedDependency(EntropyException):
        """
        Raised when dependency string is malformed.
        """

    def __init__(self, entropy_dep, entropy_repository_list,
        selected_matches = None):
        """
        DependencyStringParser constructor.

        @param entropy_dep: the dependency string to parse
        @type entropy_dep: string
        @param entropy_repository_list: ordered list of EntropyRepositoryBase
            based instances
        @type entropy_repository_list: list
        @keyword selected_matches: if given, it will be used in the decisional
            process of selecting conditional dependencies. Generally, a list
            of selected matches comes directly from user packages selection.
        @type selected_matches: set
        """
        self.__dep = entropy_dep
        self.__entropy_repository_list = entropy_repository_list
        self.__selected_matches = None
        if selected_matches:
            self.__selected_matches = frozenset(selected_matches)
        self.__dep_cache = {}
        self.__eval_cache = {}

    def __clear_cache(self):
        self.__dep_cache.clear()
        self.__eval_cache.clear()

    def __dependency(self, dep):
        """
        Helper function to make instantianting Dependency classes less annoying.
        """
        cached = self.__dep_cache.get(dep)
        if cached is not None:
            return cached
        obj = Dependency(dep, self.__entropy_repository_list)
        self.__dep_cache[dep] = obj
        return obj

    def __evaluate(self, dep):
        """
        Helper function to make instantianting Dependency classes and retrieving
        match results less annoying.
        """
        cached = self.__eval_cache.get(dep)
        if cached is not None:
            return cached
        obj = Dependency(dep, self.__entropy_repository_list).evaluate()
        self.__eval_cache[dep] = obj
        return obj

    def __split_subs(self, substring):
        deep_count = 0
        cur_str = ""
        subs = []
        for char in substring:
            if char == " ":
                continue
            elif char == "(" and deep_count == 0:
                if cur_str.strip():
                    subs.append(cur_str.strip())
                cur_str = char
                deep_count += 1
            elif char == "(":
                cur_str += char
                deep_count += 1
            elif char == self.LOGIC_OR and deep_count == 0:
                if cur_str.strip():
                    subs.append(cur_str.strip())
                subs.append(char)
                cur_str = ""
            elif char == self.LOGIC_AND and deep_count == 0:
                if cur_str.strip():
                    subs.append(cur_str.strip())
                subs.append(char)
                cur_str = ""
            elif char == ")":
                cur_str += char
                deep_count -= 1
                if deep_count == 0:
                    cur_str = cur_str.strip()
                    deps = self.__encode_sub(cur_str)
                    if len(deps) == 1:
                        subs.append(deps[0])
                    elif deps:
                        subs.append(deps)
                    else:
                        raise DependencyStringParser.MalformedDependency()
                    cur_str = ""
            else:
                cur_str += char

        if cur_str:
            subs.append(cur_str.strip())

        return subs

    def __evaluate_subs(self, iterable):

        if self.LOGIC_AND in iterable and self.LOGIC_OR in iterable:
            raise DependencyStringParser.MalformedDependency(
                "more than one operator in domain, not yet supported")

        if self.LOGIC_AND in iterable:
            iterable = [x for x in iterable if x != self.LOGIC_AND]

            outcomes = []
            for and_el in iterable:
                if isinstance(and_el, list):
                    outcome = self.__evaluate_subs(and_el)
                    if outcome:
                        outcomes.extend(outcome)
                    else:
                        return []
                elif self.__dependency(and_el):
                    outcomes.append(and_el)
                else:
                    return []
            return outcomes

        elif self.LOGIC_OR in iterable:
            iterable = [x for x in iterable if x != self.LOGIC_OR]

            if self.__selected_matches:
                # if there is something to prioritize
                for or_el in iterable:
                    if isinstance(or_el, list):
                        outcome = self.__evaluate_subs(or_el)
                        if outcome:
                            difference = set(outcome) - self.__selected_matches
                            if not difference:
                                # everything matched, so this should be taken
                                return outcome
                    else: # simple string
                        outcome = self.__evaluate(or_el)
                        if outcome:
                            difference = set(outcome) - self.__selected_matches
                            if len(outcome) != len(difference):
                                # ok cool, got it!
                                return [or_el]
            # no match using selected_matches priority list, fallback to
            # first available.
            for or_el in iterable:
                if isinstance(or_el, list):
                    outcome = self.__evaluate_subs(or_el)
                    if outcome:
                        return outcome
                elif self.__dependency(or_el):
                    return [or_el]
            return []

        # don't know what to do at the moment with this malformation
        return []

    def __encode_sub(self, dep):
        """
        Generate a list of lists and strings from a plain dependency match
        condition.
        """
        open_bracket = dep.find("(")
        closed_bracket = dep.rfind(")")

        try:
            substring = dep[open_bracket + 1:closed_bracket]
        except IndexError:
            raise DependencyStringParser.MalformedDependency()
        if not substring:
            raise DependencyStringParser.MalformedDependency()


        subs = self.__split_subs(substring)
        if not subs:
            raise DependencyStringParser.MalformedDependency()

        return subs

    def parse(self):
        """
        Execute the actual parsing and return the result.

        @return: tuple composed by boolean (matched? not matched?) and list
            of evaluated/matched dependencies.
        @rtype: tuple
        @raise MalformedDependency: if dependency string is malformed
        """
        self.__clear_cache()
        matched = False
        try:
            matched_deps = self.__evaluate_subs(
                self.__encode_sub("(" + self.__dep + ")"))
            if matched_deps:
                matched = True
        except DependencyStringParser.MalformedDependency:
            matched_deps = []
        return matched, matched_deps


def expand_dependencies(dependencies, entropy_repository_list,
    selected_matches = None):
    """
    Expand a list of dependencies resolving conditional ones.
    NOTE: it automatically handles dependencies metadata extended format:
        [(dep, type), ...]

    @param dependencies: list of raw package dependencies, as
        returned by EntropyRepositoryBase.retrieveDependencies{,List}()
    @type dependencies: iterable
    @param entropy_repository_list: ordered list of EntropyRepositoryBase instances
        used to execute the actual resolution
    @type entropy_repository_list: list
    @keyword selected_matches: list of preferred package matches used to
        evaluate or-dependencies.
    @type selected_matches: set
    @return: list (keeping the iterable order when possible) of expanded
        dependencies
    @rtype: list
    @raise AttributeError: if dependencies structure is unsupported (this
        function supports list of strings, or list of tuples of length 2)
    """
    pkg_deps = []
    for dep in dependencies:
        dep_type = None
        if isinstance(dep, tuple):
            if len(dep) == 2:
                dep, dep_type = dep
            elif len(dep) == 1:
                dep = dep[0]
            else:
                raise AttributeError("malformed input dependencies")

        if dep.startswith("("):
            _matched = False
            try:
                _matched, deps = DependencyStringParser(dep,
                    entropy_repository_list,
                    selected_matches = selected_matches).parse()
            except DependencyStringParser.MalformedDependency:
                # wtf! add as-is
                if dep_type is None:
                    pkg_deps.append(dep)
                else:
                    pkg_deps.append((dep, dep_type))
                continue
            if not _matched:
                # if not matched, hold the original
                # conditional dependency.
                deps = [dep]
            if dep_type is None:
                pkg_deps.extend(deps)
            else:
                pkg_deps.extend([(x, dep_type) for x in deps])

        elif dep_type is None:
            pkg_deps.append(dep)
        else:
            pkg_deps.append((dep, dep_type))

    return pkg_deps
