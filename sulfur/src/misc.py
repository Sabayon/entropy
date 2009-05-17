#!/usr/bin/python2 -O
# -*- coding: iso-8859-1 -*-
#    Sulfur (Entropy Interface)
#    Copyright: (C) 2007-2009 Fabio Erculiani < lxnay<AT>sabayonlinux<DOT>org >
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from entropy.i18n import _
from sulfur_setup import cleanMarkupString, SulfurConf

class Queue:

    def __init__(self, SulfurApplication):
        self.packages = {}
        self.before = []
        self.keyslotFilter = set()
        self._keyslotFilter = set()
        self.clear()
        self.Entropy = None
        self.etpbase = None
        self.pkgView = None
        self.queueView = None
        self.Sulfur = SulfurApplication
        import dialogs
        self.dialogs = dialogs


    def connect_objects(self, equo_conn, etpbase, pkgView, ui):
        self.Entropy = equo_conn
        self.etpbase = etpbase
        self.pkgView = pkgView
        self.ui = ui

    def clear( self ):
        self.packages.clear()
        self.packages['i'] = []
        self.packages['u'] = []
        self.packages['r'] = []
        self.packages['rr'] = []
        del self.before[:]
        self.keyslotFilter.clear()

    def get( self, action = None ):
        if action == None:
            return self.packages
        else:
            return self.packages[action]

    def total(self):
        size = 0
        for key in self.packages:
            size += len(self.packages[key])
        return size

    def keySlotFiltering(self, queue):

        blocked = []
        for pkg in queue:
            match = pkg.matched_atom
            if type(match[1]) is int: # installed package
                dbconn = self.Entropy.clientDbconn
            else:
                dbconn = self.Entropy.open_repository(match[1])
            keyslot = dbconn.retrieveKeySlot(match[0])
            if keyslot in self.keyslotFilter:
                blocked.append(pkg)
            else:
                self._keyslotFilter.add(keyslot)

        return blocked

    def showKeySlotErrorMessage(self, blocked):

        confirmDialog = self.dialogs.ConfirmationDialog( self.ui.main,
                    list(blocked),
                    top_text = _("Attention"),
                    sub_text = _("There are packages that can't be installed at the same time, thus are blocking your request:"),
                    bottom_text = "",
                    cancel = False
        )
        confirmDialog.run()
        confirmDialog.destroy()

    def checkSystemPackage(self, pkg):
        # check if it's a system package
        valid = self.Entropy.validate_package_removal(pkg.matched_atom[0])
        if not valid:
            pkg.queued = None
        return valid

    def elaborateReinsert(self, to_be_reinserted, idpackages_queued, accept_reinsert):

        new_proposed_idpackages_queue = [x for x in idpackages_queued if x not in to_be_reinserted]
        if not new_proposed_idpackages_queue:
            return idpackages_queued

        # atoms
        atoms = []
        newdepends = set()
        # get depends tree
        if new_proposed_idpackages_queue:
            newdepends = self.Entropy.get_removal_queue(new_proposed_idpackages_queue)

        for idpackage in to_be_reinserted:
            if idpackage not in newdepends:
                mystring = "<span foreground='%s'>%s</span>\n<small><span foreground='%s'>%s</span></small>" % (
                    SulfurConf.color_title,
                    self.Entropy.clientDbconn.retrieveAtom(idpackage),
                    SulfurConf.color_pkgsubtitle,
                    cleanMarkupString(self.Entropy.clientDbconn.retrieveDescription(idpackage)),
                )
                atoms.append(mystring)
        atoms = sorted(atoms)


        ok = True
        if not accept_reinsert and atoms:
            ok = False
            confirmDialog = self.dialogs.ConfirmationDialog( self.ui.main,
                atoms,
                top_text = _("These are the needed packages"),
                sub_text = _("These packages must be removed from the removal queue because they depend on your last selection. Do you agree?"),
                bottom_text = '',
                bottom_data = '',
                simpleList = True
            )
            result = confirmDialog.run()
            if result == -5: # ok
                ok = True
            confirmDialog.destroy()

        if ok:
            return new_proposed_idpackages_queue
        return idpackages_queued

    def elaborateUndoremove(self, matches_to_be_removed, proposed_matches):

        def flatten(d):
            mynew = set()
            [mynew.update(d[x]) for x in d]
            return mynew

        dep_tree, st = self.Entropy.get_required_packages(proposed_matches[:])
        if st != 0: return proposed_matches, False # wtf?
        if 0 in dep_tree: dep_tree.pop(0)
        new_deptree = flatten(dep_tree)

        crying_items = [x for x in matches_to_be_removed if x in new_deptree]
        if not crying_items:
            return proposed_matches, False

        # we need to get a list of packages that must be "undo-removed"
        crying_items = []
        for match in proposed_matches:
            match_tree, rc = self.Entropy.generate_dependency_tree(match, flat = True)
            if rc != 0: return proposed_matches, False # wtf?
            mm = [x for x in matches_to_be_removed if x in match_tree]
            if mm: crying_items.append(match)

        # just to make sure...
        if not crying_items: return proposed_matches, False

        atoms = []
        for idpackage, repoid in crying_items:
            dbconn = self.Entropy.open_repository(repoid)
            mystring = "<span foreground='%s'>%s</span>\n<small><span foreground='%s'>%s</span></small>" % (
                SulfurConf.color_title,
                dbconn.retrieveAtom(idpackage),
                SulfurConf.color_pkgsubtitle,
                cleanMarkupString(dbconn.retrieveDescription(idpackage)),
            )
            atoms.append(mystring)
        atoms = sorted(atoms)

        ok = False
        confirmDialog = self.dialogs.ConfirmationDialog( self.ui.main,
            atoms,
            top_text = _("These packages must be excluded"),
            sub_text = _("These packages must be removed from the queue because they depend on your last selection. Do you agree?"),
            bottom_text = '',
            bottom_data = '',
            simpleList = True
        )
        result = confirmDialog.run()
        if result == -5: # ok
            ok = True
        confirmDialog.destroy()

        if not ok: return proposed_matches, True

        return [x for x in proposed_matches if x not in crying_items], False

    def remove(self, pkgs, accept = False, accept_reinsert = False, always_ask = False):

        self.Sulfur.show_wait_window()

        try:
            if type(pkgs) is not list:
                pkgs = [pkgs]

            action = [pkgs[0].action]
            if action[0] in ("u","i","rr"): # update/install

                action = ["u","i","rr"]
                pkgs_matches = [x.matched_atom for x in pkgs]
                myq = [x.matched_atom for x in self.packages['u']+self.packages['i']+self.packages['rr']]
                xlist = [x for x in myq if x not in pkgs_matches]

                xlist, abort = self.elaborateUndoremove(pkgs_matches, xlist)
                if abort: return -10,0

                self.before = self.packages['u'][:]+self.packages['i'][:]+self.packages['rr'][:]
                for pkg in self.before: pkg.queued = None
                del self.packages['u'][:]
                del self.packages['i'][:]
                del self.packages['rr'][:]

                mybefore = set([x.keyslot for x in self.before])
                self.keyslotFilter -= mybefore

                if xlist:
                    status = self.elaborateInstall(xlist,action,False,accept,always_ask)
                    del self.before[:]
                    return status,0

                del self.before[:]
                return 0,0

            else:

                xlist = [x.matched_atom[0] for x in self.packages[action[0]] if x not in pkgs]
                #toberemoved_idpackages = [x.matched_atom[0] for x in pkgs]
                mydepends = set(self.Entropy.get_removal_queue([x.matched_atom[0] for x in pkgs]))
                mydependencies = set()
                myQA = self.Entropy.QA()
                for pkg in pkgs:
                    mydeps = myQA._get_deep_dependency_list(self.Entropy.clientDbconn, pkg.matched_atom[0])
                    mydependencies |= set([x for x in mydeps if x in xlist])
                # what are in queue?
                mylist = set(xlist)
                mylist -= mydepends
                mylist |= mydependencies
                if mylist:
                    xlist = self.elaborateReinsert(mylist, xlist, accept_reinsert)

                self.before = self.packages[action[0]][:]
                # clean, will be refilled
                for pkg in self.before:
                    pkg.queued = None
                del self.packages[action[0]][:]

                if xlist:

                    status = self.elaborateRemoval(xlist,False,accept,always_ask)
                    if status == -10:
                        del self.packages[action[0]][:]
                        self.packages[action[0]] = self.before[:]

                    del self.before[:]
                    return status,1

                del self.before[:]
                return 0,1
        finally:
            self.Sulfur.hide_wait_window()

    def add(self, pkgs, accept = False, always_ask = False):

        self.Sulfur.show_wait_window()

        try:
            if type(pkgs) is not list:
                pkgs = [pkgs]

            action = [pkgs[0].queued]

            if action[0] in ("u","i","rr"): # update/install

                self._keyslotFilter.clear()
                blocked = self.keySlotFiltering(pkgs)
                if blocked:
                    self.showKeySlotErrorMessage(blocked)
                    return 1,0

                action = ["u","i","rr"]
                myq = [x.matched_atom for x in self.packages['u']+self.packages['i']+self.packages['rr']]
                xlist = myq+[x.matched_atom for x in pkgs if x.matched_atom not in myq]
                status = self.elaborateInstall(xlist,action,False,accept,always_ask)
                if status == 0:
                    self.keyslotFilter |= self._keyslotFilter
                return status,0

            else: # remove

                def myfilter(pkg):
                    if not self.checkSystemPackage(pkg):
                        return False
                    return True

                pkgs = filter(myfilter,pkgs)
                if not pkgs: return -2,1
                myq = [x.matched_atom[0] for x in self.packages['r']]
                pkgs = [x.matched_atom[0] for x in pkgs if x.matched_atom[0] not in myq]+myq
                status = self.elaborateRemoval(pkgs,False,accept,always_ask)
                return status,1

        finally:
            self.Sulfur.hide_wait_window()

    def elaborateMaskedPackages(self, matches):

        matchfilter = set()
        masks = {}
        for match in matches:
            mymasks = self.Entropy.get_masked_packages_tree(match, atoms = False, flat = True, matchfilter = matchfilter)
            masks.update(mymasks)
        # run dialog if found some
        if not masks:
            return 0

        # filter already masked
        mymasks = {}
        for match in masks:
            if match not in self.etpbase.unmaskingPackages:
                mymasks[match] = masks[match]
        if not mymasks:
            return 0

        pkgs = []
        self.etpbase.getRawPackages('masked')
        for match in masks:
            pkg, new = self.etpbase.getPackageItem(match)
            pkgs.append(pkg)

        self.Sulfur.hide_wait_window()
        # save old
        oldmask = self.etpbase.unmaskingPackages.copy()
        maskDialog = self.dialogs.MaskedPackagesDialog(self.Entropy, self.etpbase, self.ui.main, pkgs)
        result = maskDialog.run()
        if result == -5: # ok
            result = 0
        else:
            # discard changes
            self.etpbase.unmaskingPackages = oldmask.copy()
        maskDialog.destroy()
        self.Sulfur.show_wait_window()

        return result

    def elaborateInstall(self, xlist, actions, deep_deps, accept, always_ask = False):

        status = self.elaborateMaskedPackages(xlist)
        if status != 0:
            return status

        (runQueue, removalQueue, status) = self.Entropy.get_install_queue(xlist,False,deep_deps, quiet = True)
        if status == -2: # dependencies not found
            confirmDialog = self.dialogs.ConfirmationDialog( self.ui.main,
                        runQueue,
                        top_text = _("Attention"),
                        sub_text = _("Some dependencies couldn't be found. It can either be because they are masked or because they aren't in any active repository."),
                        bottom_text = "",
                        cancel = False,
                        simpleList = True
            )
            confirmDialog.run()
            confirmDialog.destroy()
            return -10
        elif status == 0:
            # runQueue
            remove_todo = []
            install_todo = []
            if runQueue:
                icache = set([x.matched_atom for x in self.packages[actions[0]]+self.packages[actions[1]]+self.packages[actions[2]]])
                my_icache = set()

                # load packages in cache
                self.etpbase.getRawPackages('installed')
                self.etpbase.getRawPackages('available')
                self.etpbase.getRawPackages('reinstallable')
                self.etpbase.getRawPackages('updates')
                self.etpbase.getRawPackages('masked')

                for matched_atom in runQueue:
                    if matched_atom in my_icache:
                        continue
                    my_icache.add(matched_atom)
                    if matched_atom in icache:
                        continue
                    dep_pkg, new = self.etpbase.getPackageItem(matched_atom)
                    if not dep_pkg:
                        continue
                    install_todo.append(dep_pkg)

            if removalQueue:
                my_rcache = set()
                rcache = set([x.matched_atom[0] for x in self.packages['r']])
                for idpackage in removalQueue:
                    if idpackage in my_rcache:
                        continue
                    my_rcache.add(idpackage)
                    if idpackage in rcache:
                        continue
                    mymatch = (idpackage,0)
                    rem_pkg, new = self.etpbase.getPackageItem(mymatch)
                    if not rem_pkg:
                        continue
                    remove_todo.append(rem_pkg)

            if install_todo or remove_todo:
                ok = True

                mybefore = [x.matched_atom for x in self.before]
                items_before = [x for x in install_todo+remove_todo if x.matched_atom not in mybefore]

                if ((len(items_before) > 1) and (not accept)) or (always_ask):

                    ok = False
                    size = 0
                    for x in install_todo:
                        size += x.disksize
                    for x in remove_todo:
                        size -= x.disksize
                    if size > 0:
                        bottom_text = _("Needed disk space")
                    else:
                        size = abs(size)
                        bottom_text = _("Freed disk space")
                    size = self.Entropy.entropyTools.bytes_into_human(size)
                    confirmDialog = self.dialogs.ConfirmationDialog( self.ui.main,
                        install_todo+remove_todo,
                        top_text = _("These are the packages that would be installed/updated"),
                        bottom_text = bottom_text,
                        bottom_data = size
                    )
                    result = confirmDialog.run()
                    if result == -5: # ok
                        ok = True
                    confirmDialog.destroy()

                if ok:

                    mycache = {
                        'r': [x.matched_atom for x in self.packages['r']],
                        'u': [x.matched_atom for x in self.packages['u']],
                        'rr': [x.matched_atom for x in self.packages['rr']],
                        'i': [x.matched_atom for x in self.packages['i']],
                    }

                    for rem_pkg in remove_todo:
                        rem_pkg.queued = rem_pkg.action
                        if rem_pkg.matched_atom not in mycache['r']:
                            self.packages['r'].append(rem_pkg)
                    for dep_pkg in install_todo:
                        dep_pkg.queued = dep_pkg.action
                        if dep_pkg.matched_atom not in mycache[dep_pkg.action]:
                            self.packages[dep_pkg.action].append(dep_pkg)
                else:
                    return -10

        return status

    def elaborateRemoval(self, mylist, nodeps, accept, always_ask = False):
        if nodeps:
            return 0

        def r_cache_map(x):
            return x.matched_atom[0]

        r_cache = set(map(r_cache_map,self.packages['r']))
        removalQueue = self.Entropy.get_removal_queue(mylist)

        if removalQueue:
            todo = []
            my_rcache = set()
            self.etpbase.getRawPackages('installed')
            for idpackage in removalQueue:
                if idpackage in my_rcache:
                    continue
                my_rcache.add(idpackage)
                if idpackage in r_cache:
                    continue
                rem_pkg, new = self.etpbase.getPackageItem((idpackage,0))
                if not rem_pkg:
                    continue
                todo.append(rem_pkg)
            del r_cache, my_rcache

            if todo:
                ok = True
                items_before = [x for x in todo if x not in self.before]
                if ((len(items_before) > 1) and (not accept)) or (always_ask):
                    ok = False
                    size = 0
                    for x in todo:
                        size += x.disksize
                    if size > 0:
                        bottom_text = _("Freed space")
                    else:
                        size = abs(size)
                        bottom_text = _("Needed space")
                    size = self.Entropy.entropyTools.bytes_into_human(size)
                    confirmDialog = self.dialogs.ConfirmationDialog(
                        self.ui.main,
                        todo,
                        top_text = _("These are the packages that would be removed"),
                        bottom_text = bottom_text,
                        bottom_data = size
                    )
                    result = confirmDialog.run()
                    if result == -5: # ok
                        ok = True
                    confirmDialog.destroy()

                if ok:
                    for rem_pkg in todo:
                        if rem_pkg not in self.packages[rem_pkg.action]:
                            rem_pkg.queued = rem_pkg.action
                            self.packages[rem_pkg.action].append(rem_pkg)
                else:
                    return -10

        return 0
