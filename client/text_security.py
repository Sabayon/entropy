#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo security tools

    Copyright (C) 2007-2008 Fabio Erculiani

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
from entropyConstants import *
from outputTools import *
from entropy import EquoInterface
Equo = EquoInterface()

def security(options):

    rc = 0
    if len(options) < 1:
        return -10

    only_affected = False
    only_unaffected = False
    fetch = False
    for opt in options:
        if opt == "--affected":
            only_affected = True
        elif opt == "--unaffected":
            only_unaffected = True
        elif opt == "--fetch":
            fetch = True

    if options[0] == "update":
        securityConn = Equo.Security()
        rc = securityConn.fetch_advisories()
    elif options[0] == "list":
        rc = list_advisories(only_affected = only_affected, only_unaffected = only_unaffected)
    elif options[0] == "install":
        rc = install_packages(fetch = fetch)
    elif options[0] == "info":
        rc = show_advisories_info(options[1:])
    else:
        rc = -10

    return rc

def show_advisories_info(advisories):
    if not advisories:
        print_error(brown(" :: ")+darkgreen("No advisories provided."))
        return 1

    securityConn = Equo.Security()
    adv_metadata = securityConn.get_advisories_metadata()
    for advisory in advisories:
        if advisory not in adv_metadata:
            print_warning(brown(" :: ")+darkred("Advisory ")+blue(advisory)+darkred(" does not exist."))
            continue
        print_advisory_information(adv_metadata[advisory], key = advisory)

    return 0

def print_advisory_information(advisory_data, key):

    # print advisory code
    glsa_url = "http://www.gentoo.org/security/en/glsa/%s" % (advisory_data['filename'],)
    print_info(blue(" @@ ")+red("GLSA Identifier ")+bold(key)+red(" | ")+blue(glsa_url))

    # title
    print_info("\t"+darkgreen("Title:\t\t")+darkred(advisory_data['title']))

    # description
    description = advisory_data['description'].split("\n")
    desc_text = "\t"+darkgreen("Description:\t")
    for x in description:
        print_info(desc_text+x.strip())
        desc_text = "\t\t\t"

    # background
    if advisory_data['background']:
        background = advisory_data['background'].split("\n")
        bg_text = "\t"+darkgreen("Background:\t")
        for x in background:
            print_info(bg_text+purple(x.strip()))
            bg_text = "\t\t\t"

    # access
    if advisory_data['access']:
        print_info("\t"+darkgreen("Exploitable:\t")+bold(advisory_data['access']))

    # impact
    if advisory_data['impact']:
        impact = advisory_data['impact'].split("\n")
        imp_text = "\t"+darkgreen("Impact:\t\t")
        for x in impact:
            print_info(imp_text+brown(x.strip()))
            imp_text = "\t\t\t"

    # impact type
    if advisory_data['impacttype']:
        print_info("\t"+darkgreen("Impact type:\t")+bold(advisory_data['impacttype']))

    # revised
    if advisory_data['revised']:
        print_info("\t"+darkgreen("Revised:\t")+brown(advisory_data['revised']))

    # announced
    if advisory_data['announced']:
        print_info("\t"+darkgreen("Announced:\t")+brown(advisory_data['announced']))

    # synopsis
    synopsis = advisory_data['synopsis'].split("\n")
    syn_text = "\t"+darkgreen("Synopsis:\t")
    for x in synopsis:
        print_info(syn_text+x.strip())
        syn_text = "\t\t\t"

    # references
    if advisory_data['references']:
        print_info("\t"+darkgreen("References:"))
        for reference in advisory_data['references']:
            print_info("\t\t\t"+darkblue(reference))

    # gentoo bugs
    if advisory_data['bugs']:
        print_info("\t"+darkgreen("Gentoo bugs:"))
        for bug in advisory_data['bugs']:
            bug = "https://bugs.gentoo.org/show_bug.cgi?id=%s" % (bug,)
            print_info("\t\t\t"+darkblue(bug))

    # affected
    if advisory_data['affected']:
        print_info("\t"+darkgreen("Affected:"))
        for key in advisory_data['affected']:
            print_info("\t\t\t"+darkred(key))
            affected_data = advisory_data['affected'][key][0]
            vul_vers = affected_data['vul_vers']
            unaff_vers = affected_data['unaff_vers']
            if vul_vers:
                print_info("\t\t\t  "+brown("vulnerable versions: ")+", ".join(vul_vers))
            if unaff_vers:
                print_info("\t\t\t  "+brown("unaffected versions: ")+", ".join(unaff_vers))
            #print affected_data

    # workaround
    if advisory_data['workaround']:
        print_info("\t"+darkgreen("Workaround:\t")+darkred(advisory_data['workaround']))

    # resolution
    if advisory_data['resolution']:
        res_text = "\t"+darkgreen("Resolution:\t")
        resolutions = advisory_data['resolution']
        for resolution in resolutions:
            for x in resolution.split("\n"):
                print_info(res_text+x.strip())
                res_text = "\t\t\t"

{'background': u''}


def list_advisories(only_affected = False, only_unaffected = False):
    securityConn = Equo.Security()
    if (not only_affected and not only_unaffected) or (only_affected and only_unaffected):
        adv_metadata = securityConn.get_advisories_metadata()
    elif only_affected:
        adv_metadata = securityConn.get_vulnerabilities()
    else:
        adv_metadata = securityConn.get_fixed_vulnerabilities()
    if not adv_metadata:
        print_info(brown(" :: ")+darkgreen("No advisories available or applicable."))
        return 0
    adv_keys = adv_metadata.keys()
    adv_keys.sort()
    for key in adv_keys:
        affected = securityConn.is_affected(key)
        if only_affected and not affected:
            continue
        if only_unaffected and affected:
            continue
        if affected:
            affection_string = red("A")
        else:
            affection_string = green("N")
        if adv_metadata[key]['affected']:
            affected_data = adv_metadata[key]['affected'].keys()
            if affected_data:
                for a_key in affected_data:
                    vulnerables = ', '.join(adv_metadata[key]['affected'][a_key][0]['vul_vers'])
                    description = "[GLSA:%s:%s][%s] %s: %s" % (
                                        darkgreen(key),
                                        affection_string,
                                        brown(vulnerables),
                                        darkred(a_key),
                                        blue(adv_metadata[key]['title'])
                    )
                    print_info(description)
    return 0

def install_packages(fetch = False):

    cr = Equo.entropyTools.applicationLockCheck("install", gentle = True)
    if (cr):
        print_warning(red("Running with ")+bold("--pretend")+red("..."))
        etpUi['pretend'] = True
    import text_ui

    securityConn = Equo.Security()
    print_info(red(" @@ ")+blue("Calculating security updates..."))
    affected_atoms = securityConn.get_affected_atoms()
    # match in client database
    valid_matches = set()
    for atom in affected_atoms:
        match = Equo.clientDbconn.atomMatch(atom)
        if match[0] == -1:
            continue
        # get key + slot
        key, slot = Equo.clientDbconn.retrieveKeySlot(match[0])
        # match in repos
        match = Equo.atomMatch(key, matchSlot = slot)
        if match[0] != -1:
            valid_matches.add(match)

    if not valid_matches:
        print_info(red(" @@ ")+blue("All the available updates have been already installed."))
        return 0

    rc, stat = text_ui.installPackages(atomsdata = valid_matches, onlyfetch = fetch)
    return rc
