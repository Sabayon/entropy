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

from entropyConstants import ETP_CONF_DIR, etpConst, etpCache, os

etpMaskFiles = {
    'keywords': ETP_CONF_DIR+"/packages/package.keywords", # keywording configuration files
    'unmask': ETP_CONF_DIR+"/packages/package.unmask", # unmasking configuration files
    'mask': ETP_CONF_DIR+"/packages/package.mask", # masking configuration files
}

etpMtimeFiles = {
    'keywords_mtime': etpConst['dumpstoragedir']+"/keywords.mtime", # keywording configuration files mtime
    'unmask_mtime': etpConst['dumpstoragedir']+"/unmask.mtime", # unmasking configuration files mtime
    'mask_mtime': etpConst['dumpstoragedir']+"/mask.mtime", # masking configuration files mtime
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
    
    __validateEntropyCache(etpMaskFiles['keywords'],etpMtimeFiles['keywords_mtime'])
    
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


def unmask_parser():
    __validateEntropyCache(etpMaskFiles['unmask'],etpMtimeFiles['unmask_mtime'])
    
    data = set()
    if os.path.isfile(etpMaskFiles['unmask']):
        f = open(etpMaskFiles['unmask'],"r")
        content = f.readlines()
        f.close()
        # filter comments and white lines
        content = [x.strip() for x in content if not x.startswith("#") and x.strip()]
        for line in content:
            # FIXME: need validation? probably not since atomMatch handles it all
            # and doesn't care about badly formatted atoms
            data.add(line)
    return data

def mask_parser():
    __validateEntropyCache(etpMaskFiles['mask'],etpMtimeFiles['mask_mtime'])
    
    data = set()
    if os.path.isfile(etpMaskFiles['mask']):
        f = open(etpMaskFiles['mask'],"r")
        content = f.readlines()
        f.close()
        # filter comments and white lines
        content = [x.strip() for x in content if not x.startswith("#") and x.strip()]
        for line in content:
            # FIXME: need validation? probably not since atomMatch handles it all
            # and doesn't care about badly formatted atoms
            data.add(line)
    return data

'''
   internal functions
'''

def __removeRepoCache():
    if os.path.isdir(etpConst['dumpstoragedir']):
        content = os.listdir(etpConst['dumpstoragedir'])
        for file in content:
            if file.startswith(etpCache['dbMatch']+etpConst['dbnamerepoprefix']) and file.endswith(".dmp"):
                os.remove(etpConst['dumpstoragedir']+"/"+file)
    else:
        os.makedirs(etpConst['dumpstoragedir'])

def __saveFileMtime(toread,tosaveinto):
    
    if not os.path.isfile(toread):
        currmtime = 0.0
    else:
        currmtime = os.path.getmtime(toread)
    
    if not os.path.isdir(etpConst['dumpstoragedir']):
        os.makedirs(etpConst['dumpstoragedir'])
    
    f = open(tosaveinto,"w")
    f.write(str(currmtime))
    f.flush()
    f.close()
    

def __validateEntropyCache(maskfile,mtimefile):
    # handle on-disk cache validation
    # in this case, repositories cache
    # if package.keywords is changed, we must destroy cache
    if not os.path.isfile(mtimefile):
        # we can't know if package.keywords has been updated
        # remove repositories caches
        __removeRepoCache()
        __saveFileMtime(maskfile,mtimefile)
    else:
        # check mtime
        try:
            f = open(mtimefile,"r")
            mtime = float(f.readline().strip())
            # compare with current mtime
            try:
                currmtime = os.path.getmtime(maskfile)
            except OSError:
                currmtime = 0.0
            if mtime != currmtime:
                __removeRepoCache()
                __saveFileMtime(maskfile,mtimefile)
        except:
            __removeRepoCache()
            __saveFileMtime(maskfile,mtimefile)
