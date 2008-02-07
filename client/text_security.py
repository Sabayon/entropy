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
    for opt in options:
        if opt == "--affected":
            only_affected = True
        elif opt == "--unaffected":
            only_unaffected = True

    if options[0] == "update":
        rc = Equo.Security.fetch_advisories()
    elif options[0] == "list":
        rc = list_advisories(only_affected = only_affected, only_unaffected = only_unaffected)
    else:
        rc = -10

    return rc


def list_advisories(only_affected = False, only_unaffected = False):
    if (not only_affected and not only_unaffected) or (only_affected and only_unaffected):
        adv_metadata = Equo.Security.get_advisories_metadata()
    elif only_affected:
        adv_metadata = Equo.Security.get_vulnerabilities()
    else:
        adv_metadata = Equo.Security.get_fixed_vulnerabilities()
    if not adv_metadata:
        print_info(brown(" :: ")+darkgreen("No advisories available. Try running the 'update' tool."))
        return 0
    adv_keys = adv_metadata.keys()
    adv_keys.sort()
    for key in adv_keys:
        affected = Equo.Security.is_affected(key)
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


