#!/usr/bin/python -tt
# -*- coding: iso-8859-1 -*-
#    Yum Exteder (yumex) - A GUI for yum
#    Copyright (C) 2006 Tim Lauridsen < tim<AT>yum-extender<DOT>org > 
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

from i18n import _
from spritz_setup import cleanMarkupSting

class SpritzQueue:

    def __init__(self):
        self.packages = {}
        self.groups = {}
        self.before = []
        self.keyslotFilter = set()
        self._keyslotFilter = set()
        self.clear()
        self.Entropy = None
        self.etpbase = None
        self.pkgView = None
        self.queueView = None
        import dialogs
        self.dialogs = dialogs


    def connect_objects(self, EquoConnection, etpbase, pkgView, ui):
        self.Entropy = EquoConnection
        self.etpbase = etpbase
        self.pkgView = pkgView
        self.ui = ui

    def clear( self ):
        self.packages.clear()
        self.packages['i'] = []
        self.packages['u'] = []
        self.packages['r'] = []
        self.packages['rr'] = []
        self.groups.clear()
        self.groups['i'] = []
        self.groups['r'] = []
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
                dbconn = self.Entropy.openRepositoryDatabase(match[1])
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
        valid = self.Entropy.validatePackageRemoval(pkg.matched_atom[0])
        if not valid:
            pkg.queued = None
        return valid

    def elaborateReinsert(self, to_be_reinserted, idpackages_queued, accept_reinsert):

        new_proposed_idpackages_queue = [x for x in idpackages_queued if x not in to_be_reinserted]

        # atoms
        atoms = []
        newdepends = set()
        # get depends tree
        if new_proposed_idpackages_queue:
            depends_tree, status = self.Entropy.generate_depends_tree(new_proposed_idpackages_queue)
            if status == 0:
                for key in depends_tree:
                    newdepends |= depends_tree[key]

        for idpackage in to_be_reinserted:
            if idpackage not in newdepends:
                mystring = "<span foreground='#FF0000'>%s</span>\n<small><span foreground='#418C0F'>%s</span></small>" % (
                    self.Entropy.clientDbconn.retrieveAtom(idpackage),
                    cleanMarkupSting(self.Entropy.clientDbconn.retrieveDescription(idpackage)),
                )
                atoms.append(mystring)
        atoms.sort()


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

    def remove(self, pkgs, accept = False, accept_reinsert = False):

        if type(pkgs) is not list:
            pkgs = [pkgs]

        action = [pkgs[0].action]
        if action[0] in ("u","i","rr"): # update/install

            action = ["u","i","rr"]

            xlist = [x.matched_atom for x in self.packages['u']+self.packages['i']+self.packages['rr'] if x not in pkgs]
            self.before = self.packages['u'][:]+self.packages['i'][:]+self.packages['rr'][:]
            for pkg in self.before:
                pkg.queued = None
            del self.packages['u'][:]
            del self.packages['i'][:]
            del self.packages['rr'][:]

            mybefore = set([x.keyslot for x in self.before])
            self.keyslotFilter -= mybefore

            if xlist:
                status = self.elaborateInstall(xlist,action,False,accept)
                del self.before[:]
                return status,0

            del self.before[:]
            return 0,0

        else:

            xlist = [x.matched_atom[0] for x in self.packages[action[0]] if x not in pkgs]
            toberemoved_idpackages = [x.matched_atom[0] for x in pkgs]
            mydepends = set()
            for pkg in pkgs:
                mydepends |= self.Entropy.clientDbconn.retrieveDepends(pkg.matched_atom[0])
            # what are in queue?
            mylist = set(xlist)
            mylist -= mydepends
            if mylist:
                xlist = self.elaborateReinsert(mylist, xlist, accept_reinsert)

            self.before = self.packages[action[0]][:]
            # clean, will be refilled
            for pkg in self.before:
                pkg.queued = None
            del self.packages[action[0]][:]

            if xlist:

                status = self.elaborateRemoval(xlist,False,accept)
                if status == -10:
                    del self.packages[action[0]][:]
                    self.packages[action[0]] = self.before[:]

                del self.before[:]
                return status,1

            del self.before[:]
            return 0,1

    def add(self, pkgs, accept = False):

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
            tmpqueue = [x for x in pkgs if x not in self.packages['u']+self.packages['i']+self.packages['rr']]
            xlist = [x.matched_atom for x in self.packages['u']+self.packages['i']+self.packages['rr']+tmpqueue]
            xlist = list(set(xlist))
            status = self.elaborateInstall(xlist,action,False,accept)
            if status == 0:
                self.keyslotFilter |= self._keyslotFilter
            return status,0

        else: # remove

            mypkgs = []
            for pkg in pkgs:
                status = self.checkSystemPackage(pkg)
                if status:
                    mypkgs.append(pkg)
            pkgs = mypkgs

            if not pkgs:
                return -2,1

            tmpqueue = [x for x in pkgs if x not in self.packages['r']]
            xlist = [x.matched_atom[0] for x in self.packages['r']+tmpqueue]
            status = self.elaborateRemoval(xlist,False, accept)
            return status,1

    def elaborateInstall(self, xlist, actions, deep_deps, accept):
        (runQueue, removalQueue, status) = self.Entropy.retrieveInstallQueue(xlist,False,deep_deps)
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
                self.etpbase.getRawPackages('updates')
                self.etpbase.getRawPackages('available')
                self.etpbase.getRawPackages('reinstallable')
                for matched_atom in runQueue:
                    dep_pkg = self.etpbase.getPackageItem(matched_atom,True)
                    if not dep_pkg:
                        continue
                    if (dep_pkg not in self.packages[actions[0]] + \
                            self.packages[actions[1]] + \
                            self.packages[actions[2]]) and \
                            (dep_pkg not in install_todo):
                                install_todo.append(dep_pkg)

            if removalQueue:
                self.etpbase.getRawPackages('installed')
                for idpackage in removalQueue:
                    mymatch = (idpackage,0)
                    rem_pkg = self.etpbase.getPackageItem(mymatch,True)
                    if not rem_pkg:
                        continue
                    if rem_pkg not in remove_todo:
                        remove_todo.append(rem_pkg)

            if install_todo or remove_todo:
                ok = True

                items_before = [x for x in install_todo+remove_todo if x not in self.before]

                if (len(items_before) > 1) and not accept:
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
                    size = self.Entropy.entropyTools.bytesIntoHuman(size)
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
                    for rem_pkg in remove_todo:
                        rem_pkg.queued = rem_pkg.action
                        if rem_pkg not in self.packages['r']:
                            self.packages['r'].append(rem_pkg)
                    for dep_pkg in install_todo:
                        dep_pkg.queued = dep_pkg.action
                        if dep_pkg not in self.packages[dep_pkg.action]:
                            self.packages[dep_pkg.action].append(dep_pkg)
                else:
                    return -10

        return status

    def elaborateRemoval(self, mylist, nodeps, accept):
        if nodeps:
            return 0
        removalQueue = self.Entropy.retrieveRemovalQueue(mylist)
        if removalQueue:
            todo = []
            self.etpbase.getRawPackages('installed')
            for idpackage in removalQueue:
                mymatch = (idpackage,0)
                rem_pkg = self.etpbase.getPackageItem(mymatch,True)
                if not rem_pkg:
                    continue
                if rem_pkg not in self.packages[rem_pkg.action] and (rem_pkg not in todo):
                    todo.append(rem_pkg)

            if todo:
                ok = True
                items_before = [x for x in todo if x not in self.before]
                if (len(items_before) > 1) and not accept:
                    ok = False
                    size = 0
                    for x in todo:
                        size += x.disksize
                    if size > 0:
                        bottom_text = _("Freed space")
                    else:
                        size = abs(size)
                        bottom_text = _("Needed space")
                    size = self.Entropy.entropyTools.bytesIntoHuman(size)
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
                        rem_pkg.queued = rem_pkg.action
                        if rem_pkg not in self.packages[rem_pkg.action]:
                            self.packages[rem_pkg.action].append(rem_pkg)
                else:
                    return -10

        return 0
