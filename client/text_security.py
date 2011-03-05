# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import os
from entropy.const import etpConst, etpUi
from entropy.output import red, darkred, blue, brown, darkgreen, darkblue, \
    bold, purple, green, teal, print_error, print_warning, print_info, \
    print_generic
from text_tools import print_table
from entropy.i18n import _
import entropy.tools

def security(options):

    rc = 0
    if not options:
        return -10

    only_affected = False
    only_unaffected = False
    fetch = False
    force = False
    mtime = False
    reinstall = False
    assimilate = False
    for opt in options:
        if opt == "--affected":
            only_affected = True
        elif opt == "--unaffected":
            only_unaffected = True
        elif opt == "--fetch":
            fetch = True
        elif opt == "--force":
            force = True
        elif opt == "--mtime":
            mtime = True
        elif opt == "--reinstall":
            reinstall = True
        elif opt == "--assimilate":
            assimilate = True

    cmd = options[0]
    from entropy.client.interfaces import Client
    entropy_client = None
    try:
        entropy_client = Client()

        if cmd == "update":
            security_intf = entropy_client.Security()
            er_txt = darkred(_("You must be either root or in this group:")) + \
                " " +  etpConst['sysgroup']
            if not entropy.tools.is_user_in_entropy_group():
                print_error(er_txt)
                return 1
            rc = security_intf.sync(force = force)

        elif cmd == "list":
            security_intf = entropy_client.Security()
            rc = list_advisories(security_intf, only_affected = only_affected,
                only_unaffected = only_unaffected)

        elif cmd == "oscheck":
            if not entropy.tools.is_root():
                er_txt = darkred(_("You must be an administrator."))
                print_error(er_txt)
                return 1
            rc = oscheck(entropy_client, mtime_only = mtime,
                reinstall = reinstall, assimilate = assimilate)

        elif cmd == "install":

            acquired = False
            try:
                acquired = entropy.tools.acquire_entropy_locks(entropy_client)
                if not acquired:
                    print_error(darkgreen(
                        _("Another Entropy is currently running.")))
                    return 1

                security_intf = entropy_client.Security()
                rc = install_packages(entropy_client, security_intf,
                    fetch = fetch)
            finally:
                if acquired:
                    entropy.tools.release_entropy_locks(entropy_client)

        elif cmd == "info":
            security_intf = entropy_client.Security()
            rc = show_advisories_info(security_intf, options[1:])
        else:
            rc = -10
    finally:
        if entropy_client is not None:
            entropy_client.shutdown()

    return rc

def show_advisories_info(security_intf, advisories):
    if not advisories:
        print_error(brown(" :: ")+darkgreen("%s." % (
            _("No advisories provided"),)))
        return 1

    adv_metadata = security_intf.get_advisories_metadata()
    for advisory in advisories:
        if advisory not in adv_metadata:
            print_warning(brown(" :: ") + darkred("%s " % (_("Advisory"),)) + \
                blue(advisory) + darkred(" %s." % (_("does not exist"),)))
            continue
        print_advisory_information(adv_metadata[advisory], key = advisory)

    return 0

def print_advisory_information(advisory_data, key):

    toc = []

    # print advisory code
    toc.append(blue(" @@ ")+red("%s " % (_("GLSA Identifier"),))+bold(key) + \
        red(" | ")+blue(advisory_data['url']))

    # title
    toc.append((darkgreen("    %s:" % (_("Title"),)),
        darkred(advisory_data['title'])))

    # description
    description = advisory_data['description'].split("\n")
    desc_text = darkgreen("    %s:" % (_("Description"),) )
    for x in description:
        toc.append((desc_text, x.strip()))
        desc_text = " "

    for item in advisory_data['description_items']:
        desc_text = " %s " % (darkred("(*)"),)
        count = 8
        mystr = []
        for word in item.split():
            count -= 1
            mystr.append(word)
            if count < 1:
                toc.append((" ", desc_text+' '.join(mystr)))
                desc_text = "   "
                mystr = []
                count = 8
        if count < 8:
            toc.append((" ", desc_text+' '.join(mystr)))

    # background
    if advisory_data['background']:
        background = advisory_data['background'].split("\n")
        bg_text = darkgreen("    %s:" % (_("Background"),))
        for x in background:
            toc.append((bg_text, purple(x.strip())))
            bg_text = " "

    # access
    if advisory_data['access']:
        toc.append((darkgreen("    %s:" % (_("Exploitable"),)),
            bold(advisory_data['access'])))

    # impact
    if advisory_data['impact']:
        impact = advisory_data['impact'].split("\n")
        imp_text = darkgreen("    %s:" % (_("Impact"),))
        for x in impact:
            toc.append((imp_text, brown(x.strip())))
            imp_text = " "

    # impact type
    if advisory_data['impacttype']:
        toc.append((darkgreen("    %s:" % (_("Impact type"),)),
            bold(advisory_data['impacttype'])))

    # revised
    if advisory_data['revised']:
        toc.append((darkgreen("    %s:" % (_("Revised"),)),
            brown(advisory_data['revised'])))

    # announced
    if advisory_data['announced']:
        toc.append((darkgreen("    %s:" % (_("Announced"),)),
            brown(advisory_data['announced'])))

    # synopsis
    synopsis = advisory_data['synopsis'].split("\n")
    syn_text = darkgreen("    %s:" % (_("Synopsis"),))
    for x in synopsis:
        toc.append((syn_text, x.strip()))
        syn_text = " "

    # references
    if advisory_data['references']:
        toc.append(darkgreen("    %s:" % (_("References"),)))
        for reference in advisory_data['references']:
            toc.append((" ", darkblue(reference)))

    # gentoo bugs
    if advisory_data['bugs']:
        toc.append(darkgreen("    %s:" % (_("Upstream bugs"),)))
        for bug in advisory_data['bugs']:
            toc.append((" ", darkblue(bug)))

    # affected
    if advisory_data['affected']:
        toc.append(darkgreen("    %s:" % (_("Affected"),)))
        for key in advisory_data['affected']:
            toc.append((" ", darkred(key)))
            affected_data = advisory_data['affected'][key][0]
            vul_vers = affected_data['vul_vers']
            unaff_vers = affected_data['unaff_vers']
            if vul_vers:
                toc.append((" ", brown("%s: " % (
                    _("vulnerable versions"),))+", ".join(vul_vers)))
            if unaff_vers:
                toc.append((" ", brown("%s: " % (
                    _("unaffected versions"),))+", ".join(unaff_vers)))

    # workaround
    workaround = advisory_data['workaround'].split("\n")
    if advisory_data['workaround']:
        work_text = darkgreen("    %s:" % (_("Workaround"),))
        for x in workaround:
            toc.append((work_text, darkred(x.strip())))
            work_text = " "

    # resolution
    if advisory_data['resolution']:
        res_text = darkgreen("    %s:" % (_("Resolution"),))
        resolutions = advisory_data['resolution']
        for resolution in resolutions:
            for x in resolution.split("\n"):
                toc.append((res_text, x.strip()))
                res_text = " "

    print_table(toc, cell_spacing = 3)

def list_advisories(security_intf, only_affected = False,
    only_unaffected = False):

    if (not only_affected and not only_unaffected) or \
        (only_affected and only_unaffected):
        adv_metadata = security_intf.get_advisories_metadata()

    elif only_affected:
        adv_metadata = security_intf.get_vulnerabilities()

    else:
        adv_metadata = security_intf.get_fixed_vulnerabilities()

    if not adv_metadata:
        print_info(brown(" :: ")+darkgreen("%s." % (
            _("No advisories available or applicable"),)))
        return 0

    adv_keys = sorted(adv_metadata.keys())
    for key in adv_keys:
        affected = security_intf.is_affected(key)
        if only_affected and not affected:
            continue
        if only_unaffected and affected:
            continue
        if affected:
            affection_string = red("A")
        else:
            affection_string = green("N")
        if adv_metadata[key]['affected']:
            affected_data = list(adv_metadata[key]['affected'].keys())
            if affected_data:
                for a_key in affected_data:
                    k_data = adv_metadata[key]['affected'][a_key]
                    vulnerables = ', '.join(k_data[0]['vul_vers'])
                    description = "[GLSA:%s:%s][%s] %s: %s" % (
                        darkgreen(key),
                        affection_string,
                        brown(vulnerables),
                        darkred(a_key),
                        blue(adv_metadata[key]['title']))
                    print_info(description)
    return 0

def oscheck(entropy_client, mtime_only = False, reinstall = False,
    assimilate = False):

    import text_ui

    installed_repo = entropy_client.installed_repository()
    if installed_repo is None:
        if not etpUi['quiet']:
            print_info(red(" @@ ")+blue("%s." % (
                _("Installed packages repository is not available"),)))
        return 1

    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue("%s..." % (_("Checking system files"),)))
    pkg_ids = installed_repo.listAllPackageIds()
    total = len(pkg_ids)
    count = 0
    faulty_pkg_ids = []

    for pkg_id in pkg_ids:
        count += 1
        pkg_atom = installed_repo.retrieveAtom(pkg_id)
        sts_txt = "%s%s/%s%s %s" % (blue("["), darkgreen(str(count)),
            purple(str(total)), blue("]"), brown(pkg_atom))

        if not etpUi['quiet']:
            print_info(blue("@@") + " " + sts_txt, back = True)
        cont_s = installed_repo.retrieveContentSafety(pkg_id)
        if not cont_s:
            if (not etpUi['quiet']) and etpUi['verbose']:
                atom_txt = " %s: " % (brown(pkg_atom),)
                print_info(red("@@") + atom_txt + _("no checksum information"))
            # if pkg provides content!
            continue

        paths_tainted = []
        paths_unavailable = []
        for path, safety_data in cont_s.items():
            tainted = False
            mtime = None
            sha256 = None

            if not os.path.lexists(path):
                # file does not exist
                # NOTE: current behaviour is to ignore file not available
                # this might change in future.
                paths_unavailable.append(path)
                continue

            elif not mtime_only:
                # verify sha256
                sha256 = entropy.tools.sha256(path)
                tainted = sha256 != safety_data['sha256']
                if tainted:
                    cont_s[path]['sha256'] = sha256
            else:
                # verify mtime
                mtime = os.path.getmtime(path)
                tainted = mtime != safety_data['mtime']
                if tainted:
                    cont_s[path]['mtime'] = mtime

            if assimilate:
                if mtime is None:
                    cont_s[path]['mtime'] = os.path.getmtime(path)
                elif sha256 is None:
                    cont_s[path]['sha256'] = entropy.tools.sha256(path)

            if tainted:
                paths_tainted.append(path)

        if paths_tainted:
            faulty_pkg_ids.append(pkg_id)
            paths_tainted.sort()
            if not etpUi['quiet']:
                atom_txt = " %s: " % (teal(pkg_atom),)
                print_info(red("@@") + atom_txt + _("altered files") + ":")
            for path in paths_tainted:
                if etpUi['quiet']:
                    print_generic(path)
                else:
                    txt = " %s" % (purple(path),)
                    print_info(txt)
            if assimilate:
                if not etpUi['quiet']:
                    print_info(blue("@@") + " " + sts_txt + ", " + \
                        teal(_("assimilated new hashes and mtime")),)
                installed_repo.setContentSafety(pkg_id, cont_s)

        if paths_unavailable:
            paths_unavailable.sort()
            if (not etpUi['quiet']) and etpUi['verbose']:
                for path in paths_unavailable:
                    txt = " %s [%s]" % (teal(path), purple(_("unavailable")))
                    print_info(txt)

    if not faulty_pkg_ids:
        if not etpUi['quiet']:
            print_info(red(" @@ ") + darkgreen(_("No altered files found")))
        return 0

    rc = 0
    if faulty_pkg_ids:
        rc = 10
    valid_matches = set()

    if reinstall and faulty_pkg_ids:
        for pkg_id in faulty_pkg_ids:
            key, slot = installed_repo.retrieveKeySlot(pkg_id)
            match = entropy_client.atom_match(key, match_slot = slot)
            if match[0] != -1:
                valid_matches.add(match)

        if valid_matches:
            rc, stat = text_ui.install_packages(entropy_client,
                atomsdata = valid_matches)

    if not etpUi['quiet']:
        print_warning(red(" @@ ") + \
            purple(_("Altered files have been found")))
        if reinstall and (rc == 0) and valid_matches:
            print_warning(red(" @@ ") + \
                purple(_("Packages have been reinstalled successfully")))

    return rc

def install_packages(entropy_client, security_intf, fetch = False):

    import text_ui
    print_info(red(" @@ ")+blue("%s..." % (_("Calculating security updates"),)))
    affected_atoms = security_intf.get_affected_packages()
    # match in client database
    valid_matches = set()
    for atom in affected_atoms:
        match = entropy_client.installed_repository().atomMatch(atom)
        if match[0] == -1:
            continue
        # get key + slot
        key, slot = entropy_client.installed_repository().retrieveKeySlot(match[0])
        # match in repos
        match = entropy_client.atom_match(key, match_slot = slot)
        if match[0] != -1:
            valid_matches.add(match)

    if not valid_matches:
        print_info(red(" @@ ")+blue("%s." % (
            _("All the available updates have been already installed"),)))
        return 0

    rc, stat = text_ui.install_packages(entropy_client,
        atomsdata = valid_matches, onlyfetch = fetch)
    return rc
