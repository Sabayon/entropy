# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
from entropy.const import etpConst
from entropy.output import red, darkred, blue, brown, darkgreen, darkblue, \
    bold, purple, green, print_error, print_warning, print_info
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
    for opt in options:
        if opt == "--affected":
            only_affected = True
        elif opt == "--unaffected":
            only_unaffected = True
        elif opt == "--fetch":
            fetch = True
        elif opt == "--force":
            force = True

    from entropy.client.interfaces import Client
    entropy_client = Client()
    try:

        if options[0] == "update":
            security_intf = entropy_client.Security()
            er_txt = darkred(_("You must be either root or in this group:")) + \
                " " +  etpConst['sysgroup']
            if not entropy.tools.is_user_in_entropy_group():
                print_error(er_txt)
                return 1
            rc = security_intf.sync(force = force)

        elif options[0] == "list":
            security_intf = entropy_client.Security()
            rc = list_advisories(security_intf, only_affected = only_affected,
                only_unaffected = only_unaffected)

        elif options[0] == "install":
            security_intf = entropy_client.Security()
            rc = install_packages(entropy_client, security_intf, fetch = fetch)

        elif options[0] == "info":
            security_intf = entropy_client.Security()
            rc = show_advisories_info(security_intf, options[1:])
        else:
            rc = -10
    finally:
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

    # print advisory code
    print_info(blue(" @@ ")+red("%s " % (_("GLSA Identifier"),))+bold(key) + \
        red(" | ")+blue(advisory_data['url']))

    # title
    print_info("\t"+darkgreen("%s:\t\t" % (_("Title"),)) + \
        darkred(advisory_data['title']))

    # description
    description = advisory_data['description'].split("\n")
    desc_text = "\t"+darkgreen("%s:\t" % (_("Description"),) )
    for x in description:
        print_info(desc_text+x.strip())
        desc_text = "\t\t\t"

    for item in advisory_data['description_items']:
        desc_text = "\t\t\t %s " % (darkred("(*)"),)
        count = 8
        mystr = []
        for word in item.split():
            count -= 1
            mystr.append(word)
            if count < 1:
                print_info(desc_text+' '.join(mystr))
                desc_text = "\t\t\t   "
                mystr = []
                count = 8
        if count < 8:
            print_info(desc_text+' '.join(mystr))

    # background
    if advisory_data['background']:
        background = advisory_data['background'].split("\n")
        bg_text = "\t"+darkgreen("%s:\t" % (_("Background"),))
        for x in background:
            print_info(bg_text+purple(x.strip()))
            bg_text = "\t\t\t"

    # access
    if advisory_data['access']:
        print_info("\t"+darkgreen("%s:\t" % (_("Exploitable"),)) + \
            bold(advisory_data['access']))

    # impact
    if advisory_data['impact']:
        impact = advisory_data['impact'].split("\n")
        imp_text = "\t"+darkgreen("%s:\t\t" % (_("Impact"),))
        for x in impact:
            print_info(imp_text+brown(x.strip()))
            imp_text = "\t\t\t"

    # impact type
    if advisory_data['impacttype']:
        print_info("\t"+darkgreen("%s:\t" % (_("Impact type"),)) + \
            bold(advisory_data['impacttype']))

    # revised
    if advisory_data['revised']:
        print_info("\t"+darkgreen("%s:\t" % (_("Revised"),)) + \
            brown(advisory_data['revised']))

    # announced
    if advisory_data['announced']:
        print_info("\t"+darkgreen("%s:\t" % (_("Announced"),)) + \
            brown(advisory_data['announced']))

    # synopsis
    synopsis = advisory_data['synopsis'].split("\n")
    syn_text = "\t"+darkgreen("%s:\t" % (_("Synopsis"),))
    for x in synopsis:
        print_info(syn_text+x.strip())
        syn_text = "\t\t\t"

    # references
    if advisory_data['references']:
        print_info("\t"+darkgreen("%s:" % (_("References"),)))
        for reference in advisory_data['references']:
            print_info("\t\t\t"+darkblue(reference))

    # gentoo bugs
    if advisory_data['bugs']:
        print_info("\t"+darkgreen("%s:" % (_("Upstream bugs"),)))
        for bug in advisory_data['bugs']:
            print_info("\t\t\t"+darkblue(bug))

    # affected
    if advisory_data['affected']:
        print_info("\t"+darkgreen("%s:" % (_("Affected"),)))
        for key in advisory_data['affected']:
            print_info("\t\t\t"+darkred(key))
            affected_data = advisory_data['affected'][key][0]
            vul_vers = affected_data['vul_vers']
            unaff_vers = affected_data['unaff_vers']
            if vul_vers:
                print_info("\t\t\t  "+brown("%s: " % (
                    _("vulnerable versions"),))+", ".join(vul_vers))
            if unaff_vers:
                print_info("\t\t\t  "+brown("%s: " % (
                    _("unaffected versions"),))+", ".join(unaff_vers))

    # workaround
    if advisory_data['workaround']:
        print_info("\t"+darkgreen("%s:\t" % (_("Workaround"),)) + \
            darkred(advisory_data['workaround']))

    # resolution
    if advisory_data['resolution']:
        res_text = "\t"+darkgreen("%s:\t" % (_("Resolution"),))
        resolutions = advisory_data['resolution']
        for resolution in resolutions:
            for x in resolution.split("\n"):
                print_info(res_text+x.strip())
                res_text = "\t\t\t"

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
