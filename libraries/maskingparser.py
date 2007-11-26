#!/usr/bin/python
'''
    # DESCRIPTION:
    # Parser of /etc/entropy/packages/* files

    Copyright (C) 2007 Fabio Erculiani

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

from entropyConstants import ETP_CONF_DIR, os

etpMaskFiles = {
    'keywords': ETP_CONF_DIR+"/packages/package.keywords", # keywords configuration files
}

'''
   This function parses files in etpMaskFiles and returns collected data to caller (dict)
'''
def parse():
    data = {}
    for item in etpMaskFiles:
        data[item] = eval(item+'_parser')()
    return data


'''
   parser of package.keywords file
'''
def keywords_parser():
    data = {
            'universal': set(),
            'packages': {},
            'repositories': {},
    }
    if os.path.isfile(etpMaskFiles['keywords']):
        f = open(etpMaskFiles['keywords'],"r")
        content = f.readlines()
        f.close()
        # filter comments and white lines
        content = [x.strip() for x in content if not x.startswith("#") and x.strip()]
        for line in content:
            keywordinfo = line.split()
            # skip wrong lines
            if len(keywordinfo) > 3:
                print ">> "+line+" << is invalid!!"
                continue
            if len(keywordinfo) == 1: # inversal keywording, check if it's not repo=
                # repo=?
                if keywordinfo[0].startswith("repo="):
                    print ">> "+line+" << is invalid!!"
                    continue
                # atom? is it worth it? it would take a little bit to parse uhm... >50 entries...!?
                kinfo = keywordinfo[0]
                if keywordinfo[0] == "**": keywordinfo[0] = "" # convert into entropy format
                data['universal'].add(keywordinfo[0])
                continue # needed?
            if len(keywordinfo) in (2,3): # inversal keywording, check if it's not repo=
                # repo=?
                if keywordinfo[0].startswith("repo="):
                    print ">> "+line+" << is invalid!!"
                    continue
                # add to repo?
                items = keywordinfo[1:]
                if keywordinfo[0] == "**": keywordinfo[0] = "" # convert into entropy format
                reponame = [x for x in items if x.startswith("repo=") and (len(x.split("=")) == 2)]
                if reponame:
                    reponame = reponame[0].split("=")[1]
                    if reponame not in data['repositories']:
                        data['repositories'][reponame] = {}
                    # repository unmask or package in repository unmask?
                    if keywordinfo[0] not in data['repositories'][reponame]:
                        data['repositories'][reponame][keywordinfo[0]] = set()
                    if len(items) == 1:
                        # repository unmask
                        data['repositories'][reponame][keywordinfo[0]].add('*')
                    else:
                        if "*" not in data['repositories'][reponame][keywordinfo[0]]:
                            item = [x for x in items if not x.startswith("repo=")]
                            data['repositories'][reponame][keywordinfo[0]].add(item[0])
                else:
                    # it's going to be a faulty line!!??
                    if len(items) == 2: # can't have two items and no repo=
                        print ">> "+line+" << is invalid!!"
                        continue
                    # add keyword to packages
                    if keywordinfo[0] not in data['packages']:
                        data['packages'][keywordinfo[0]] = set()
                    data['packages'][keywordinfo[0]].add(items[0])
    return data


