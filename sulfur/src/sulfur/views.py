#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
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

import time
import gtk
import gobject
import os

from entropy.exceptions import RepositoryError, InvalidPackageSet
from entropy.const import etpConst, etpSys, initconfig_entropy_constants
from entropy.misc import ParallelTask
from entropy.i18n import _, _LOCALE
from entropy.db import dbapi2
from entropy.tools import convert_unix_time_to_datetime, dep_getkey, \
    print_traceback
from entropy.const import const_get_stringtype

from sulfur.setup import const, cleanMarkupString, SulfurConf
from sulfur.core import UI
from sulfur.widgets import CellRendererStars
from sulfur.package import DummyEntropyPackage
from sulfur.entropyapi import Equo
from sulfur.misc import busy_cursor, normal_cursor, STATUS_BAR_CONTEXT_IDS
from sulfur.dialogs import MaskedPackagesDialog, ConfirmationDialog, okDialog
from sulfur.event import SulfurSignals


class EntropyPackageViewModelInjector:

    def __init__(self, model, entropy, etpbase, dummy_cats):
        self.model = model
        self.entropy = entropy
        self.etpbase = etpbase
        self.dummy_cats = dummy_cats
        self.expand = True

    def pkgset_inject(self, packages):
        raise NotImplementedError

    def packages_inject(self, packages):
        raise NotImplementedError

    def inject(self, packages, pkgsets):
        if pkgsets:
            self.pkgset_inject(packages)
        else:
            self.dummy_cats.clear()
            self.packages_inject(packages)



class DefaultPackageViewModelInjector(EntropyPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        EntropyPackageViewModelInjector.__init__(self, *args, **kwargs)

    def pkgset_inject(self, packages):

        categories = {}
        cat_descs = {}
        for po in packages:
            for set_name in po.set_names:
                if set_name not in categories:
                    categories[set_name] = []
                cat_descs[set_name] = po.set_cat_namedesc
                if po not in categories[set_name]:
                    categories[set_name].append(po)

        cats = sorted(categories)
        orig_cat_desc = _("No description")
        for category in cats:

            cat_desc = orig_cat_desc
            cat_desc_data = self.entropy.get_category_description_data(category)
            if _LOCALE in cat_desc_data:
                cat_desc = cat_desc_data[_LOCALE]
            elif 'en' in cat_desc_data:
                cat_desc = cat_desc_data['en']
            elif cat_descs.get(category):
                cat_desc = cat_descs.get(category)

            cat_text = "<b><big>%s</big></b>\n<small>%s</small>" % (category, 
                cleanMarkupString(cat_desc),)
            mydummy = DummyEntropyPackage(namedesc = cat_text,
                dummy_type = SulfurConf.dummy_category, onlyname = category)
            mydummy.color = SulfurConf.color_package_category
            mydummy.is_pkgset_cat = True
            set_data = self.entropy.package_set_match(category)[0]
            if not set_data:
                continue

            set_from, set_name, set_deps = set_data
            mydummy.set_category = category
            mydummy.set_from.add(set_from)

            mydummy.set_matches, mydummy.set_installed_matches, \
                mydummy.set_install_incomplete, \
                mydummy.set_remove_incomplete = \
                    self.etpbase._pkg_get_pkgset_matches_installed_matches(
                        set_deps)

            mydummy.namedesc = "<b><big>%s</big></b>\n<small>%s</small>" % (
                category, cleanMarkupString(
                    self.etpbase._pkg_get_pkgset_set_from_desc(set_from)),
            )
            self.dummy_cats[category] = mydummy
            parent = self.model.append( None, (mydummy,) )
            for po in categories[category]:
                self.model.append( parent, (po,) )

    def packages_inject(self, packages):

        categories = {}
        cat_descs = {}

        for po in packages:
            try:
                mycat = po.cat
            except dbapi2.Error:
                continue
            if mycat not in categories:
                categories[mycat] = []
            categories[mycat].append(po)

        cats = sorted(categories)
        orig_cat_desc = _("No description")
        for category in cats:

            cat_desc = orig_cat_desc
            cat_desc_data = self.entropy.get_category_description_data(category)
            if _LOCALE in cat_desc_data:
                cat_desc = cat_desc_data[_LOCALE]
            elif 'en' in cat_desc_data:
                cat_desc = cat_desc_data['en']
            elif cat_descs.get(category):
                cat_desc = cat_descs.get(category)

            cat_text = "<b><big>%s</big></b>\n<small>%s</small>" % (category,
                cleanMarkupString(cat_desc),)
            mydummy = DummyEntropyPackage(namedesc = cat_text,
                dummy_type = SulfurConf.dummy_category, onlyname = category)
            mydummy.color = SulfurConf.color_package_category
            self.dummy_cats[category] = mydummy
            parent = self.model.append( None, (mydummy,) )
            for po in categories[category]:
                self.model.append( parent, (po,) )


class NameSortPackageViewModelInjector(DefaultPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        DefaultPackageViewModelInjector.__init__(self, *args, **kwargs)
        self.reverse = False

    def packages_inject(self, packages):

        categories = {}

        for po in packages:
            try:
                myinitial = po.onlyname.lower()[0]
            except dbapi2.Error:
                continue
            if myinitial not in categories:
                categories[myinitial] = []
            categories[myinitial].append(po)

        letters = sorted(categories, reverse = self.reverse)
        for letter in letters:
            for po in categories[letter]:
                self.model.append( None, (po,) )


class NameRevSortPackageViewModelInjector(NameSortPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        NameSortPackageViewModelInjector.__init__(self, *args, **kwargs)
        self.reverse = True

class DownloadSortPackageViewModelInjector(EntropyPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        EntropyPackageViewModelInjector.__init__(self, *args, **kwargs)

    def packages_inject(self, packages):

        def mycmp(obj_a, obj_b):
            eq = 0
            try:
                d1 = obj_a.downloads
                d2 = obj_b.downloads
            except dbapi2.Error:
                return 0
            if d1 == d2:
                return 0
            if d1 < d2:
                return 1
            return -1

        packages.sort(mycmp)
        for po in packages:
            self.model.append( None, (po,) )

class VoteSortPackageViewModelInjector(EntropyPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        EntropyPackageViewModelInjector.__init__(self, *args, **kwargs)
        self.reverse = False

    def packages_inject(self, packages):


        def mycmp(obj_a, obj_b):
            eq = 0
            try:
                d1 = obj_a.votefloat
                d2 = obj_b.votefloat
            except dbapi2.Error:
                return 0
            if d1 == d2:
                return 0
            if d1 < d2:
                return 1
            return -1

        packages.sort(mycmp, reverse = self.reverse)
        for po in packages:
                self.model.append( None, (po,) )

class VoteRevSortPackageViewModelInjector(VoteSortPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        VoteSortPackageViewModelInjector.__init__(self, *args, **kwargs)
        self.reverse = True

class RepoSortPackageViewModelInjector(EntropyPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        EntropyPackageViewModelInjector.__init__(self, *args, **kwargs)

    def packages_inject(self, packages):

        def mycmp(obj_a, obj_b):
            eq = 0
            try:
                d1 = obj_a.repoid
                d2 = obj_b.repoid
            except dbapi2.Error:
                return 0
            if d1 == d2:
                return 0
            if d1 < d2:
                return 1
            return -1

        packages.sort(mycmp)
        for po in packages:
            self.model.append( None, (po,) )

class DateSortPackageViewModelInjector(EntropyPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        EntropyPackageViewModelInjector.__init__(self, *args, **kwargs)

    def packages_inject(self, packages):

        def mycmp(obj_a, obj_b):
            eq = 0
            try:
                d1 = obj_a.epoch
                d2 = obj_b.epoch
            except dbapi2.Error:
                return 0
            if d1 == d2:
                return 0
            if d1 < d2:
                return 1
            return -1

        packages.sort(mycmp)
        for po in packages:
            self.model.append( None, (po,) )

class DateGroupedSortPackageViewModelInjector(EntropyPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        EntropyPackageViewModelInjector.__init__(self, *args, **kwargs)

    def packages_inject(self, packages):

        dates = {}
        for po in packages:
            try:
                date = float(po.epoch)
            except (TypeError, AttributeError, ValueError,):
                date = None
            if date is not None:
                dateobj = convert_unix_time_to_datetime(date)
                date = (dateobj.year, dateobj.month, dateobj.day,)
            dates_obj = dates.setdefault(date, [])
            dates_obj.append(po)

        date_refs = sorted(dates, reverse = True)

        not_avail_txt = _("Not available")
        for date in date_refs:

            date_desc = not_avail_txt
            if date is not None:
                date_desc = "%s-%s-%s" % date

            date_text = "<b><big>%s</big></b>\n<small>%s</small>" % (
                cleanMarkupString(date_desc),
                _("entered the repository"),
            )
            mydummy = DummyEntropyPackage(namedesc = date_text,
                dummy_type = SulfurConf.dummy_category, onlyname = date)
            mydummy.color = SulfurConf.color_package_category
            self.dummy_cats[date] = mydummy
            parent = self.model.append( None, (mydummy,) )
            for po in dates[date]:
                self.model.append( parent, (po,) )

class LicenseSortPackageViewModelInjector(EntropyPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        EntropyPackageViewModelInjector.__init__(self, *args, **kwargs)

    def packages_inject(self, packages):

        licenses = {}
        for po in packages:
            try:
                lic = po.lic
            except (TypeError, AttributeError, ValueError,):
                lic = None
            if lic is not None:
                if not lic.strip():
                    lic = _("Not available")
                lic_obj = licenses.setdefault(lic, [])
                lic_obj.append(po)

        for lic in sorted(licenses):

            lic_text = "<b><big>%s</big></b>\n<small>%s</small>" % (
                cleanMarkupString(lic),
                _("license"),
            )
            mydummy = DummyEntropyPackage(namedesc = lic_text,
                dummy_type = SulfurConf.dummy_category, onlyname = lic)
            mydummy.color = SulfurConf.color_package_category
            self.dummy_cats[lic] = mydummy
            parent = self.model.append( None, (mydummy,) )
            for po in licenses[lic]:
                self.model.append( parent, (po,) )

class GroupSortPackageViewModelInjector(EntropyPackageViewModelInjector):

    def __init__(self, *args, **kwargs):
        EntropyPackageViewModelInjector.__init__(self, *args, **kwargs)
        self.expand = False

    def packages_inject(self, packages):

        groups = self.entropy.get_package_groups()
        group_data = dict((tuple(val['categories']), key,) for key, val \
            in list(groups.items()))

        nocat = _("No category")
        groups['no_category'] = {
            'name': nocat,
            'description': _("Applications without a group"),
            'categories': [],
        }

        metadata = {}
        no_category = []
        for po in packages:
            try:
                cat = po.cat
            except dbapi2.Error:
                continue
            found = False
            for cats in group_data:
                if cat in cats:
                    obj = metadata.setdefault(group_data[cats], [])
                    obj.append(po)
                    found = True
                    break
            if not found:
                no_category.append(po)

        # "No category" must go at the very bottom
        cats = sorted(metadata)
        if no_category:
            metadata['no_category'] = no_category
            cats.append('no_category')

        for cat in cats:

            if not metadata[cat]:
                continue

            cat_text = "<b><big>%s</big></b>\n<small>%s</small>" % (
                cleanMarkupString(groups[cat]['name']),
                groups[cat]['description'],
            )
            mydummy = DummyEntropyPackage(namedesc = cat_text,
                dummy_type = SulfurConf.dummy_category, onlyname = cat)
            mydummy.is_group = True
            mydummy.color = SulfurConf.color_package_category
            self.dummy_cats[cat] = mydummy
            parent = self.model.append( None, (mydummy,) )
            for po in metadata[cat]:
                self.model.append( parent, (po,) )

class EntropyPackageView:

    ROW_HEIGHT = 35

    def __init__( self, treeview, qview, ui, etpbase, main_window,
        application = None ):

        self.Equo = Equo()
        self.Sulfur = application
        self.pkgcolumn_text = _("Selection")
        self.pkgcolumn_text_rating = _("Rating")
        self.stars_col_size = 100
        self.selection_width = 34
        self.show_reinstall = True
        self.show_purge = True
        self.show_mask = True
        self.loaded_widget = None
        self.selected_objs = []
        self.last_row = None
        self.loaded_reinstallables = []
        self.loaded_event = None
        self.do_refresh_view = False
        self.main_window = main_window
        self.empty_mode = False
        self.event_click_pos = 0, 0
        # default for installed packages
        self.pkg_install_ok = "package-installed-updated.png"
        self.pkg_install_updatable = "package-installed-outdated.png"
        self.pkg_install_new = "package-available.png"
        self.pkg_remove = "package-remove.png"
        self.pkg_purge = "package-purge.png"
        self.pkg_reinstall = "package-reinstall.png"
        self.pkg_install = "package-install.png"
        self.pkg_update = "package-upgrade.png"
        self.pkg_downgrade = "package-downgrade.png"
        self.pkg_undoinstall = "package-undoinstall.png"

        self.img_pkg_install_ok = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_install_ok, self.pkg_install_ok)
        self.img_pkg_install_updatable = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_install_updatable, self.pkg_install_updatable)
        self.img_pkg_update = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_update, self.pkg_update)
        self.img_pkg_downgrade = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_downgrade, self.pkg_downgrade)

        self.img_pkg_install_new = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_install_new, self.pkg_install_new)

        self.img_pkg_remove = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_remove, self.pkg_remove)
        self.img_pkg_undoremove = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_undoremove, self.pkg_remove)
        self.img_pkg_purge = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_purge, self.pkg_purge)
        self.img_pkg_undopurge = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_undopurge, self.pkg_purge)
        self.img_pkg_reinstall = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_reinstall, self.pkg_reinstall)
        self.img_pkg_undoreinstall = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_undoreinstall, self.pkg_reinstall)

        self.img_pkg_install = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_install, self.pkg_install)
        self.img_pkg_undoinstall = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_undoinstall, self.pkg_undoinstall)

        self.img_pkgset_install = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkgset_install, self.pkg_install_ok)
        self.img_pkgset_undoinstall = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkgset_undoinstall, self.pkg_undoinstall)
        self.img_pkgset_remove = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkgset_remove, self.pkg_remove)
        self.img_pkgset_undoremove = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkgset_undoremove, self.pkg_remove)
        self.img_pkg_updateinstall = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_updateinstall, self.pkg_update)
        self.img_pkg_undoupdateinstall = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_undoupdateinstall, self.pkg_downgrade)

        self.img_pkg_update_remove = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_update_remove, self.pkg_remove)
        self.img_pkg_update_undoremove = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_update_undoremove, self.pkg_remove)
        self.img_pkg_update_purge = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_update_purge, self.pkg_purge)
        self.img_pkg_update_undopurge = gtk.Image()
        self.set_pixbuf_to_image(self.img_pkg_update_undopurge, self.pkg_purge)

        treeview.set_fixed_height_mode(True)
        self.view_expanded = True
        self.view = treeview
        self.view.connect("button-press-event", self.on_view_button_press)
        self.view.connect("enter-notify-event", self.treeview_enter_notify)
        self.view.connect("leave-notify-event", self.treeview_leave_notify)
        self.store = self.setupView()
        self.dummyCats = {}
        self.__install_statuses = {}
        self.queue = qview.queue
        self.queueView = qview
        self.ui = ui
        self.etpbase = etpbase
        self.clear_updates()

        # installed packages right click menu
        self.installed_menu_xml = gtk.glade.XML( const.GLADE_FILE, "packageInstalled", domain="entropy" )
        self.installed_menu = self.installed_menu_xml.get_widget( "packageInstalled" )
        self.installed_menu_xml.signal_autoconnect(self)

        self.installed_reinstall = self.installed_menu_xml.get_widget( "reinstall" )
        self.installed_undoreinstall = self.installed_menu_xml.get_widget( "undoreinstall" )
        self.installed_purge = self.installed_menu_xml.get_widget( "purge" )
        self.installed_undopurge = self.installed_menu_xml.get_widget( "undopurge" )
        self.installed_remove = self.installed_menu_xml.get_widget( "remove" )
        self.installed_undoremove = self.installed_menu_xml.get_widget( "undoremove" )
        self.installed_unmask = self.installed_menu_xml.get_widget( "unmask" )
        self.installed_mask = self.installed_menu_xml.get_widget( "mask" )
        self.installed_update = self.installed_menu_xml.get_widget( "updateinstall" )
        self.installed_undoupdate = self.installed_menu_xml.get_widget( "undoupdateinstall" )

        self.installed_reinstall.set_image(self.img_pkg_reinstall)
        self.installed_undoreinstall.set_image(self.img_pkg_undoreinstall)
        self.installed_remove.set_image(self.img_pkg_remove)
        self.installed_undoremove.set_image(self.img_pkg_undoremove)
        self.installed_purge.set_image(self.img_pkg_purge)
        self.installed_undopurge.set_image(self.img_pkg_undopurge)
        self.installed_update.set_image(self.img_pkg_updateinstall)
        self.installed_undoupdate.set_image(self.img_pkg_undoupdateinstall)

        # updates right click menu
        self.updates_menu_xml = gtk.glade.XML( const.GLADE_FILE, "packageUpdates", domain="entropy" )
        self.updates_menu = self.updates_menu_xml.get_widget( "packageUpdates" )
        self.updates_menu_xml.signal_autoconnect(self)

        self.updates_update = self.updates_menu_xml.get_widget( "update" )
        self.updates_undoupdate = self.updates_menu_xml.get_widget( "undoupdate" )
        self.updates_remove = self.updates_menu_xml.get_widget( "updateRemove" )
        self.updates_undoremove = self.updates_menu_xml.get_widget( "updateUndoRemove" )
        self.updates_purge = self.updates_menu_xml.get_widget( "updatePurge" )
        self.updates_undopurge = self.updates_menu_xml.get_widget( "updateUndoPurge" )
        self.updates_mask = self.updates_menu_xml.get_widget( "updateMask" )

        self.updates_remove.set_image(self.img_pkg_update_remove)
        self.updates_undoremove.set_image(self.img_pkg_update_undoremove)
        self.updates_purge.set_image(self.img_pkg_update_purge)
        self.updates_undopurge.set_image(self.img_pkg_update_undopurge)

        self.updates_update.set_image(self.img_pkg_update)
        self.updates_undoupdate.set_image(self.img_pkg_downgrade)

        # install right click menu
        self.install_menu_xml = gtk.glade.XML( const.GLADE_FILE, "packageInstall", domain="entropy" )
        self.install_menu = self.install_menu_xml.get_widget( "packageInstall" )
        self.install_menu_xml.signal_autoconnect(self)
        self.install_install = self.install_menu_xml.get_widget( "install" )
        self.install_undoinstall = self.install_menu_xml.get_widget( "undoinstall" )
        self.install_mask = self.install_menu_xml.get_widget( "maskinstall" )
        self.install_install.set_image(self.img_pkg_install)
        self.install_undoinstall.set_image(self.img_pkg_undoinstall)

        # package set right click menu
        self.pkgset_menu_xml = gtk.glade.XML( const.GLADE_FILE, "packageSet", domain="entropy" )
        self.pkgset_menu = self.pkgset_menu_xml.get_widget( "packageSet" )
        self.pkgset_menu_xml.signal_autoconnect(self)

        self.pkgset_install = self.pkgset_menu_xml.get_widget( "pkgsetInstall" )
        self.pkgset_undoinstall = self.pkgset_menu_xml.get_widget( "pkgsetUndoinstall" )
        self.pkgset_remove = self.pkgset_menu_xml.get_widget( "pkgsetRemove" )
        self.pkgset_undoremove = self.pkgset_menu_xml.get_widget( "pkgsetUndoremove" )
        self.pkgset_install.set_image(self.img_pkgset_install)
        self.pkgset_undoinstall.set_image(self.img_pkgset_undoinstall)
        self.pkgset_remove.set_image(self.img_pkgset_remove)
        self.pkgset_undoremove.set_image(self.img_pkgset_undoremove)

        self.model_injector_rotation = {
            'package': [NameSortPackageViewModelInjector,
                NameRevSortPackageViewModelInjector,
                DownloadSortPackageViewModelInjector,
                DefaultPackageViewModelInjector,
                DateGroupedSortPackageViewModelInjector,
                LicenseSortPackageViewModelInjector],
            'vote': [VoteSortPackageViewModelInjector,
                VoteRevSortPackageViewModelInjector],
            'repository': [RepoSortPackageViewModelInjector],
        }

        # set default model injector
        self.change_model_injector(DefaultPackageViewModelInjector)

        self.ugc_update_event_handler_id = \
            SulfurSignals.connect('ugc_data_update', self.__update_ugc_event)

    def __update_ugc_event(self, event):
        self.view.queue_draw()

    def change_model_injector(self, injector):
        if not issubclass(injector, EntropyPackageViewModelInjector):
            raise AttributeError("wrong sorter")
        self.__current_model_injector_class = injector
        self.Injector = injector(self.store, self.Equo, self.etpbase,
            self.dummyCats)

    def treeview_enter_notify(self, widget, event):
        self.main_window.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.CROSSHAIR))

    def treeview_leave_notify(self, widget, event):
        self.main_window.window.set_cursor(None)

    def reset_install_menu(self):
        self.install_install.show()
        self.install_undoinstall.hide()
        self.install_mask.hide()

    def hide_install_menu(self):
        self.install_install.hide()
        self.install_undoinstall.hide()
        self.install_mask.hide()

    def reset_updates_menu(self):
        self.updates_undoupdate.hide()
        self.updates_update.show()
        self.updates_remove.hide()
        self.updates_undoremove.hide()
        self.updates_purge.hide()
        self.updates_undopurge.hide()
        self.updates_mask.hide()

    def reset_set_menu(self):
        self.pkgset_install.hide()
        self.pkgset_undoinstall.hide()
        self.pkgset_remove.hide()
        self.pkgset_undoremove.hide()

    def hide_updates_menu(self):
        self.updates_undoupdate.hide()
        self.updates_update.hide()
        self.updates_remove.hide()
        self.updates_undoremove.hide()
        self.updates_purge.hide()
        self.updates_undopurge.hide()
        self.updates_mask.hide()

    def reset_installed_packages_menu(self):
        self.installed_unmask.hide()
        self.installed_undoremove.hide()
        self.installed_undoreinstall.hide()
        self.installed_undopurge.hide()
        self.installed_remove.show()
        self.installed_reinstall.hide()
        self.installed_mask.hide()
        if self.show_reinstall:
            self.installed_reinstall.show()
        self.installed_purge.hide()
        if self.show_purge:
            self.installed_purge.show()
        self.installed_update.hide()
        self.installed_undoupdate.hide()

    def hide_installed_packages_menu(self):
        self.installed_unmask.hide()
        self.installed_undoremove.hide()
        self.installed_undoreinstall.hide()
        self.installed_undopurge.hide()
        self.installed_remove.hide()
        self.installed_reinstall.hide()
        self.installed_purge.hide()
        self.installed_mask.hide()
        self.installed_update.hide()
        self.installed_undoupdate.hide()

    def collect_view_iters(self, widget = None):
        if widget == None:
            widget = self.view
        model, paths = widget.get_selection().get_selected_rows()
        if not model:
            return [], model
        data = []
        for path in paths:
            myiter = model.get_iter(path)
            data.append(myiter)
        return data, model

    def collect_selected_items(self, widget = None):
        myiters, model = self.collect_view_iters(widget)
        if model == None:
            return []

        items = []
        for myiter in myiters:
            obj = model.get_value(myiter, 0)
            items.append(obj)
        return items

    def collect_selected_children_items(self, widget = None):
        iters, model = self.collect_view_iters(widget = widget)
        items = []
        for myiter in iters:
            if not model.iter_has_child(myiter):
                continue
            myiter = model.iter_children(myiter)
            while myiter:
                obj = model.get_value(myiter, 0)
                items.append(obj)
                myiter = model.iter_next(myiter)

        return items

    def on_view_button_press(self, widget, event):

        try:
            row, column, x, y = widget.get_path_at_pos(int(event.x), int(event.y))
        except TypeError:
            return True

        objs = self.collect_selected_items(widget)
        col_title = column.get_title()
        if (col_title == self.pkgcolumn_text_rating) and len(objs) < 2:
            self.load_menu(widget, event, objs = objs)
            self.last_row = row
            return False

        if (col_title == self.pkgcolumn_text) and objs:
            if (len(objs) == 1) and (row != self.last_row):
                self.last_row = row
                return False
            did_something = self.load_menu(widget, event, objs = objs)
            self.last_row = row
            return did_something

    def load_menu(self, widget, event, objs = None):

        self.loaded_widget = widget
        self.loaded_event = event
        del self.loaded_reinstallables[:]

        if objs == None:
            objs = self.collect_selected_items(widget)

        event_x = event.x
        if event_x < 10:
            return False

        try:
            row, column, x, y = widget.get_path_at_pos(int(event_x), int(event.y))
        except TypeError:
            return False

        self.event_click_pos = x, y
        if column.get_title() == self.pkgcolumn_text:

            #if event.button != 3:
            #    return False

            # filter dummy objs
            objs = [obj for obj in objs if (not isinstance(obj, DummyEntropyPackage)) or obj.set_category]
            if objs:

                objs_len = len(objs)
                set_categories = [obj for obj in objs if obj.set_category]
                pkgsets = [obj for obj in objs if (obj.pkgset and obj.action in ("i", "r"))]
                installed_objs = [obj for obj in objs if obj.action in ("r", "rr")]
                updatable_objs = [obj for obj in objs if obj.action == "u"]
                installable_objs = [obj for obj in objs if obj.action == "i"]

                if len(set_categories) == objs_len:
                    self.run_set_menu_stuff(set_categories)
                elif len(pkgsets) == objs_len:
                    pfx_len = len(etpConst['packagesetprefix'])
                    new_objs = [self.dummyCats.get(obj.name[pfx_len:]) for obj in objs if self.dummyCats.get(obj.name[pfx_len:])]
                    self.run_set_menu_stuff(new_objs)
                elif len(installed_objs) == objs_len: # installed packages listing
                    self.run_installed_menu_stuff(installed_objs)
                elif len(updatable_objs) == objs_len: # updatable packages listing
                    self.run_updates_menu_stuff(updatable_objs)
                elif len(installable_objs) == objs_len:
                    self.run_install_menu_stuff(installable_objs)

                return True

        elif len(objs) == 1:
            obj = objs[0]
            distance = 0
            for col in self.view.get_columns()[0:2]:
                distance += col.get_width()
            if (event_x > distance) and (event_x < (distance+self.stars_col_size)):
                vote = int((event_x - distance)/self.stars_col_size*5)+1
                # this is required to fix idiotic GTK behaviour
                self.delayed_vote_submit(widget, vote)
                return True

        return False

    def delayed_vote_submit(self, widget, vote):

        def go(widget, vote):
            objs = self.collect_selected_items(widget)
            if len(objs) == 1:
                obj = objs[0]
                obj.voted = float(vote)
                # submit vote
                self.spawn_vote_submit(obj)
            return False

        gobject.timeout_add(1000, go, widget, vote)

    def reposition_menu(self, menu):
        # devo tradurre x=0,y=20 in posizioni assolute
        abs_x, abs_y = self.loaded_event.get_root_coords()
        abs_x -= self.loaded_event.x
        event_y = self.loaded_event.y
        # FIXME: find a better way to properly position menu
        while event_y > self.selection_width+5:
            event_y -= self.selection_width+5
        abs_y += (self.selection_width-event_y)
        return int(abs_x), int(abs_y), True

    def run_install_menu_stuff(self, objs):
        self.reset_install_menu()

        self.selected_objs = objs
        objs_len = len(objs)
        queued = [x for x in objs if x.queued]
        not_queued = [x for x in objs if not x.queued]

        do_show = True
        if len(queued) == objs_len:
            self.hide_install_menu()
            self.install_undoinstall.show()
        elif len(not_queued) != objs_len:
            do_show = False
        else:
            user_unmasked = [x for x in objs if x.user_unmasked]
            if len(user_unmasked) == objs_len:
                self.install_mask.show()

        if do_show:
            self.install_menu.popup( None, None, None, self.loaded_event.button, self.loaded_event.time )

    def run_updates_menu_stuff(self, objs):
        self.reset_updates_menu()

        objs_len = len(objs)
        self.selected_objs = objs

        do_show = True
        while True:
            queued_u = [x for x in objs if x.queued == "u"]
            if len(queued_u) == objs_len:
                self.updates_update.hide()
                self.updates_undoupdate.show()
                break
            queued_r_p = [x for x in objs if x.queued == "r" and x.do_purge]
            if len(queued_r_p) == objs_len:
                self.updates_update.hide()
                self.updates_undopurge.show()
                break
            queued_r_no_p = [x for x in objs if x.queued == "r" and not x.do_purge]
            if len(queued_r_no_p) == objs_len:
                self.updates_update.hide()
                self.updates_undoremove.show()
                break
            installed_m = [x for x in objs if x.installed_match]
            if len(installed_m) == objs_len:
                self.updates_remove.show()
                self.updates_purge.show()
            updatables = [x for x in objs if not x.queued]
            if len(updatables) != objs_len:
                do_show = False
                break
            user_unmasked = [x for x in objs if x.user_unmasked]
            if len(user_unmasked) == objs_len:
                self.updates_mask.show()
                break
            break

        if do_show:
            self.updates_menu.popup( None, None, None, self.loaded_event.button, self.loaded_event.time)

    def run_set_menu_stuff(self, objs):
        self.reset_set_menu()

        not_queued = [x for x in objs if not x.queued]
        installs = [x for x in objs if x.queued == "i"]
        undorms = [x for x in objs if x.queued == "r"]
        objs_len = len(objs)

        self.selected_objs = objs
        do_show = True
        if len(not_queued) == objs_len:
            # show install + remove
            # hide undo install + undo remove
            self.pkgset_install.show()
            self.pkgset_remove.show()
        elif len(installs) == objs_len:
            # show undo install
            self.pkgset_undoinstall.show()
        elif len(undorms) == objs_len:
            # show undo remove
            self.pkgset_undoremove.show()
        else:
            do_show = False

        if do_show:
            self.pkgset_menu.popup( None, None, None, self.loaded_event.button, self.loaded_event.time)


    def run_installed_menu_stuff(self, objs):
        do_show = True

        objs_len = len(objs)
        masked = [x for x in objs if x.masked]
        queued = [x for x in objs if x.queued]

        self.reset_installed_packages_menu()
        self.selected_objs = objs

        if len(masked) == objs_len:
            masked = [x for x in masked if x.maskstat]
            if len(masked) == objs_len:
                self.installed_unmask.show()

        if len(queued) == objs_len:

            self.hide_installed_packages_menu()

            queued_r = [x for x in objs if (x.queued == "r" and not x.do_purge)]
            queued_rr = [x for x in objs if (x.queued == "rr" and not x.do_purge)]
            queued_r_purge = [x for x in objs if (x.queued == "r" and x.do_purge)]
            queued_updatable = [x for x in objs if x.install_status == 2]

            if len(queued_r) == objs_len:
                self.installed_undoremove.show()
            elif len(queued_rr) == objs_len:
                self.installed_undoreinstall.show()
                self.set_loaded_reinstallable(objs)
            elif len(queued_r_purge) == objs_len:
                self.installed_undopurge.show()
            elif len(queued_updatable) == objs_len:
                self.installed_undoupdate.show()

        else:

            syspkgs = [x for x in objs if x.syspkg]
            queued_updatable = [x for x in objs if x.install_status == 2]

            # is it a system package ?
            if syspkgs:
                self.installed_remove.hide()
                self.installed_purge.hide()

            reinstallables = self.get_reinstallables(objs)
            if len(reinstallables) != objs_len:
                self.installed_reinstall.hide()
            else:
                self.loaded_reinstallables = reinstallables
                if not reinstallables:
                    self.installed_reinstall.hide()

            if syspkgs:
                self.installed_remove.hide()
                self.installed_purge.hide()

            if len(queued_updatable) == objs_len:
                self.installed_update.show()

            if self.show_mask:
                user_unmasked = [x for x in objs if x.user_unmasked]
                if len(user_unmasked) == objs_len:
                    self.installed_mask.show()

        if do_show:
            #self.installed_menu.popup( None, None, self.reposition_menu, self.loaded_event.button, self.loaded_event.time )
            self.installed_menu.popup( None, None, None, self.loaded_event.button, self.loaded_event.time )

    def get_reinstallables(self, objs):
        reinstallables = self.etpbase.get_raw_groups("reinstallable")
        r_dict = dict(((x.matched_atom, x,) for x in objs))
        # this has been added to support reinstallables on
        # the "Queue/installation" tab, when objects from available
        # group are selected
        r2_dict = dict(((x.installed_match, x,) for x in objs))
        r_dict.update(r2_dict)
        found = []
        for to_obj in reinstallables:
            t_match = to_obj.installed_match
            r_obj = r_dict.get(t_match)
            if r_obj is not None:
                found.append(to_obj)
        return found

    def set_loaded_reinstallable(self, objs):
        self.loaded_reinstallables = self.get_reinstallables(objs)

    def on_unmask_activate(self, widget):
        busy_cursor(self.main_window)
        objs = self.selected_objs
        oldmask = self.etpbase.unmaskingPackages.copy()
        mydialog = MaskedPackagesDialog(self.Equo, self.etpbase, self.ui.main, objs)
        result = mydialog.run()
        if result != -5:
            self.etpbase.unmaskingPackages = oldmask.copy()
        mydialog.destroy()
        normal_cursor(self.main_window)

    def do_remove(self, action, do_purge):

        busy_cursor(self.main_window)
        new_objs = []
        just_show_objs = []

        for obj in self.selected_objs:
            if obj.installed_match:
                iobj, new = self.etpbase.get_package_item(obj.installed_match)
                new_objs.append(iobj)
                just_show_objs.append(obj)
            else:
                new_objs.append(obj)

        q_cache = {}
        for obj in just_show_objs+new_objs:
            q_cache[obj.matched_atom] = (obj.queued, obj.do_purge,)
            obj.queued = action
            if action:
                obj.do_purge = do_purge

        if action:
            status = self.add_to_queue(new_objs, action)
        else:
            status = self.remove_queued(new_objs)
        if status != 0:
            for obj in just_show_objs+new_objs:
                queued, do_purge = q_cache[obj.matched_atom]
                obj.queued = queued
                obj.do_purge = do_purge

        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    def on_remove_activate(self, widget, do_purge = False):
        return self.do_remove("r", do_purge)

    def on_undoremove_activate(self, widget):
        return self.do_remove(None, None)

    def do_reinstall(self, action):

        busy_cursor(self.main_window)

        q_cache = {}
        for obj in self.selected_objs+self.loaded_reinstallables:
            q_cache[obj.matched_atom] = obj.queued
            obj.queued = action

        if action:
            status, myaction = self.queue.add(self.loaded_reinstallables)
        else:
            status, myaction = self.queue.remove(self.loaded_reinstallables)

        if status != 0:
            for obj in self.selected_objs+self.loaded_reinstallables:
                obj.queued = q_cache.get(obj.matched_atom)

        self.queueView.refresh()
        normal_cursor(self.main_window)

    def on_reinstall_activate(self, widget):
        self.do_reinstall("rr")

    def on_undoreinstall_activate(self, widget):
        self.do_reinstall(None)

    def remove_queued(self, objs):

        if not isinstance(objs, list):
            objs = [objs]

        q_cache = {}
        for obj in objs:
            q_cache[obj.matched_atom] = obj.queued
            obj.queued = None

        status, myaction = self.queue.remove(objs)
        if status != 0:
            for obj in objs:
                obj.queued = q_cache.get(obj.matched_atom)
        else:
            # queued tab content is tainted
            if "queued" in self.etpbase._packages:
                del self.etpbase._packages["queued"]
            # if we remove packages from the queued view
            # we need to completely remove them from the list
            if self.Sulfur != None:
                if self.Sulfur.lastPkgPB == "queued":
                    self.etpbase.populate_single_group("queued", force = True)
                    self.Sulfur.show_packages()
            # disable user selection
            for obj in objs:
                obj.selected_by_user = False

        self.view.queue_draw()

        return status

    def add_to_queue(self, objs, action):

        q_cache = {}
        for obj in objs:
            q_cache[obj.matched_atom] = obj.queued
            obj.queued = action

        status, myaction = self.queue.add(objs)
        if status != 0:
            for obj in objs:
                obj.queued = q_cache.get(obj.matched_atom)
        else:
            # queued tab content is tainted
            if "queued" in self.etpbase._packages:
                del self.etpbase._packages["queued"]
            # enable user selection
            for obj in objs:
                obj.selected_by_user = True

        return status

    def add_to_package_mask(self, objs):
        confirmDialog = ConfirmationDialog( self.ui.main,
            objs,
            top_text = _("These are the packages that would be disabled"),
            bottom_text = _("Once confirmed, these packages will be considered masked."),
            simpleList = True
        )
        result = confirmDialog.run()
        confirmDialog.destroy()
        if result != -5: return
        for obj in objs: self.Equo.mask_match(obj.matched_atom)
        # clear cache
        self.clear()
        self.etpbase.clear_groups()
        self.etpbase.clear_cache()
        if self.Sulfur != None:
            self.Sulfur.show_packages()

    def on_pkgsetUndoinstall_activate(self, widget):
        return self.on_pkgset_install_undoinstall_activate(widget, install = False)

    def on_pkgsetInstall_activate(self, widget):
        return self.on_pkgset_install_undoinstall_activate(widget)

    def _get_pkgset_data(self, items, add = True, remove_action = False):

        pkgsets = set()
        realpkgs = set()
        if remove_action:
            for item in items:
                for mid, mrep in item.set_installed_matches:
                    if mrep == None:
                        pkgsets.add(mid)
                    elif mid != -1:
                        realpkgs.add((mid, mrep,))
        else:
            for item in items:
                for mid, mrep in item.set_matches:
                    if mrep == None:
                        pkgsets.add(mid)
                    else:
                        realpkgs.add((mid, mrep,))

        # check for set depends :-)
        selected_sets = set()
        if not add:
            sets_categories = [x.set_category for x in items]
            selected_sets = [self.dummyCats.get(x) for x in self.dummyCats if x not in sets_categories]
            selected_sets = set([x.set_category for x in selected_sets])
            selected_sets = set(["%s%s" % (etpConst['packagesetprefix'], x,) for x in selected_sets])
        pkgsets.update(selected_sets)

        exp_atoms = set()
        broken_sets = set()
        for pkgset in pkgsets:
            try:
                exp_atoms |= self.Equo.package_set_expand(pkgset)
            except InvalidPackageSet:
                # this package set is broken or doesn't exist
                # we can exclude it from our data collection
                broken_sets.add(pkgset)
                continue

        # remove broken sets
        pkgsets.difference_update(broken_sets)

        exp_matches = set()
        if remove_action:
            for exp_atom in exp_atoms:
                exp_match = self.Equo.clientDbconn.atomMatch(exp_atom)
                if exp_match[0] == -1: continue
                exp_matches.add(exp_match)
        else:
            for exp_atom in exp_atoms:
                exp_match = self.Equo.atom_match(exp_atom)
                if exp_match[0] == -1: continue
                exp_matches.add(exp_match)

        exp_matches |= realpkgs

        objs = []
        for match in exp_matches:
            try:
                yp, new = self.etpbase.get_package_item(match)
            except RepositoryError:
                return
            if add and yp.queued != None:
                continue
            objs.append(yp)

        set_objs = []
        for pkgset in pkgsets:
            yp, new = self.etpbase.get_package_item(pkgset)
            set_objs.append(yp)

        return pkgsets, exp_matches, objs, set_objs, exp_atoms

    def on_pkgset_install_undoinstall_activate(self, widget, install = True):

        busy_cursor(self.main_window)
        try:
            pkgsets, exp_matches, objs, set_objs, exp_atoms = \
                self._get_pkgset_data(self.selected_objs, add = install)
        except InvalidPackageSet:
            okDialog(self.ui.main,
                _("Package Set has broken dependencies, Sets not found"))
            return

        if not objs+set_objs:
            return

        install_incomplete = [x for x in self.selected_objs if x.set_install_incomplete]
        remove_incomplete = [x for x in self.selected_objs if x.set_remove_incomplete]
        if (install and install_incomplete) or ((not install) and remove_incomplete):
            okDialog(self.ui.main,
                _("There are incomplete package sets, continue at your own risk"))

        q_cache = {}
        for obj in objs+set_objs:
            q_cache[obj.matched_atom] = obj.queued
            if install:
                obj.queued = obj.action
            else:
                obj.queued = None

        if install:
            status, myaction = self.queue.add(objs)
        else:
            status, myaction = self.queue.remove(objs)

        if status != 0:
            for obj in objs+set_objs:
                obj.queued = q_cache.get(obj.matched_atom)
        else:
            c_action = "i"
            if not install:
                c_action = None

            pkgset_pfx_len = len(etpConst['packagesetprefix'])

            # also disable/enable item if it's a dep of any other set
            for item in self.selected_objs:

                if item.set_category: myset = "%s%s" % (
                    etpConst['packagesetprefix'], item.set_category,)
                else: myset = item.matched_atom

                yp, new = self.etpbase.get_package_item(myset)
                yp.queued = c_action

                for pkgset in pkgsets:
                    dummy_obj = self.dummyCats.get(pkgset[pkgset_pfx_len:])
                    if not dummy_obj: continue
                    dummy_obj.queued = c_action
                item.queued = c_action

        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    def on_pkgset_remove_undoremove_activate(self, widget, remove = True):

        busy_cursor(self.main_window)
        pkgsets, exp_matches, objs, set_objs, exp_atoms = \
            self._get_pkgset_data(self.selected_objs, add = remove,
                remove_action = True)
        if not objs+set_objs: return

        repo_objs = []
        for idpackage, rid in exp_matches:
            key, slot = self.Equo.clientDbconn.retrieveKeySlot(idpackage)
            if not self.Equo.validate_package_removal(idpackage):
                continue
            mymatch = self.Equo.atom_match(key, matchSlot = slot)
            if mymatch[0] == -1: continue
            yp, new = self.etpbase.get_package_item(mymatch)
            repo_objs.append(yp)

        q_cache = {}
        joint_objs = objs+set_objs+repo_objs

        for obj in joint_objs:
            q_cache[obj.matched_atom] = obj.queued
            if remove:
                obj.queued = "r"
            else:
                obj.queued = None

        if remove:
            status, myaction = self.queue.add(objs)
        else:
            status, myaction = self.queue.remove(objs)

        if status != 0:
            for obj in joint_objs:
                obj.queued = q_cache.get(obj.matched_atom)
        else:
            c_action = "r"
            if not remove:
                c_action = None

            pkgset_pfx_len = len(etpConst['packagesetprefix'])
            for item in self.selected_objs:
                # also disable/enable item if it's a dep of any other set
                if item.set_category: myset = "%s%s" % (
                    etpConst['packagesetprefix'], item.set_category,)
                else: myset = item.matched_atom

                yp, new = self.etpbase.get_package_item(myset)
                yp.queued = c_action

                for pkgset in pkgsets:
                    dummy_obj = self.dummyCats.get(pkgset[pkgset_pfx_len:])
                    if not dummy_obj: continue
                    dummy_obj.queued = c_action
                item.queued = c_action


        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    def on_pkgsetRemove_activate(self, widget):
        return self.on_pkgset_remove_undoremove_activate(widget)

    def on_pkgsetUndoremove_activate(self, widget):
        return self.on_pkgset_remove_undoremove_activate(widget, remove = False)

    def on_purge_activate(self, widget):
        self.on_remove_activate(widget, True)
        self.view.queue_draw()

    def on_undopurge_activate(self, widget):
        self.on_undoremove_activate(widget)
        self.view.queue_draw()

    def on_update_activate(self, widget):
        self.on_install_update_activate(widget, "u")
        self.view.queue_draw()

    def on_undoupdate_activate(self, widget):
        self.on_undoinstall_undoupdate_activate(widget)
        self.view.queue_draw()

    def on_install_activate(self, widget):
        self.on_install_update_activate(widget, "i")
        self.view.queue_draw()

    def on_undoinstall_activate(self, widget):
        self.on_undoinstall_undoupdate_activate(widget)
        self.view.queue_draw()

    def on_install_update_activate(self, widget, action):
        busy_cursor(self.main_window)
        if self.selected_objs:
            self.add_to_queue(self.selected_objs, action)
        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    def on_undoinstall_undoupdate_activate(self, widget):
        busy_cursor(self.main_window)
        self.remove_queued(self.selected_objs)
        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    def on_updateinstall_activate(self, widget):
        """
        Triggered from the Installed packages view for those which have
        updates available.
        """
        # need to translate installed objects into updates
        selected_objs = self.get_installed_pkg_objs_for_selected()

        busy_cursor(self.main_window)
        if selected_objs:
            status = self.add_to_queue(selected_objs, "u")
            if status == 0:
                # also update original objects
                for obj in self.selected_objs:
                    obj.queued = "u"
        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    def on_undoupdateinstall_activate(self, widget):
        """
        Triggered from the Installed packages view for those which have
        updates available.
        """
        busy_cursor(self.main_window)
        # need to translate installed objects into updates
        selected_objs = self.get_installed_pkg_objs_for_selected()
        self.remove_queued(selected_objs)
        self.remove_queued(self.selected_objs)
        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    # installed packages mask action
    def on_mask_activate(self, widget):

        objs = []
        for x in self.selected_objs:
            key, slot = x.keyslot
            m = self.Equo.atom_match(key, matchSlot = slot)
            if m[0] != -1: objs.append(m)

        busy_cursor(self.main_window)
        if objs:
            self.add_to_package_mask(objs)
        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    # updatable packages mask action
    def on_updateMask_activate(self, widget):
        busy_cursor(self.main_window)
        if self.selected_objs:
            self.add_to_package_mask(self.selected_objs)
        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    # available packages mask action
    def on_maskinstall_activate(self, widget):
        busy_cursor(self.main_window)
        if self.selected_objs:
            self.add_to_package_mask(self.selected_objs)
        self.queueView.refresh()
        normal_cursor(self.main_window)
        self.view.queue_draw()

    def __do_change_sorting_by_column(self, options):
        busy_cursor(self.main_window)
        current = self.__current_model_injector_class
        new = options[0]
        if current in options:
            try:
                new = options[options.index(current)+1]
            except IndexError:
                new = options[0] # make explicit

        if new == self.__current_model_injector_class:
            return
        self.change_model_injector(new)
        if self.Sulfur != None:
            sorter = self.Sulfur.ui.pkgSorter
            for sort_name, sort_class in list(self.Sulfur.avail_pkg_sorters.items()):
                if sort_class == new:
                    sort_id = self.Sulfur.pkg_sorters_id_inverse.get(sort_name)
                    sorter.set_active(sort_id)
                    break
            self.Sulfur.show_packages()
        normal_cursor(self.main_window)

    def on_package_column_clicked(self, widget):
        options = self.model_injector_rotation['package']
        self.__do_change_sorting_by_column(options)

    def on_vote_column_clicked(self, widget):
        options = self.model_injector_rotation['vote']
        self.__do_change_sorting_by_column(options)

    def on_repository_column_clicked(self, widget):
        options = self.model_injector_rotation['repository']
        self.__do_change_sorting_by_column(options)

    def on_selection_column_clicked(self, widget):
        if self.view_expanded:
            self.expand()
        else:
            self.collapse()

    def expand(self):
        self.view.expand_all()
        self.view_expanded = True

    def collapse(self):
        self.view.collapse_all()
        self.view_expanded = True

    def setupView(self):

        store = gtk.TreeStore( gobject.TYPE_PYOBJECT )
        self.view.get_selection().set_mode( gtk.SELECTION_MULTIPLE )
        self.view.set_model( store )

        myheight = EntropyPackageView.ROW_HEIGHT
        # selection pixmap
        cell1 = gtk.CellRendererPixbuf()
        cell1.set_property('height', myheight)
        self.set_pixbuf_to_cell(cell1, self.pkg_install_ok )
        column1 = gtk.TreeViewColumn( self.pkgcolumn_text, cell1 )
        column1.set_cell_data_func( cell1, self.new_pixbuf )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( self.selection_width+40 )
        column1.set_sort_column_id( -1 )
        column1.set_clickable(True)
        column1.connect("clicked", self.on_selection_column_clicked)
        self.view.append_column( column1 )
        column1.set_clickable( True )

        self.create_text_column( _( "Application" ), 'namedesc', size = 300,
            expand = True, set_height = myheight, clickable = True,
            click_cb = self.on_package_column_clicked)

        # vote event box
        cell2 = CellRendererStars()
        cell2.set_property('height', myheight)
        column2 = gtk.TreeViewColumn( self.pkgcolumn_text_rating, cell2 )
        column2.set_resizable( True )
        column2.set_cell_data_func( cell2, self.get_stars_rating )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( self.stars_col_size )
        column2.set_expand(False)
        column2.set_sort_column_id( -1 )
        column2.set_clickable(True)
        column2.connect("clicked", self.on_vote_column_clicked)
        self.view.append_column( column2 )

        self.create_text_column( _( "Repository" ), 'repoid', size = 130,
            set_height = myheight, clickable = True,
            click_cb = self.on_repository_column_clicked)

        return store

    def get_stars_rating( self, column, cell, model, myiter ):
        obj = model.get_value( myiter, 0 )
        if not obj: return

        if obj.color:
            self.set_line_status(obj, cell)

        try:
            voted = obj.voted
        except:
            return
        try:
            mydata = obj.vote
        except:
            return
        cell.value = float(mydata)
        cell.value_voted = float(voted)

    def spawn_vote_submit(self, obj):

        if self.Equo.UGC == None:
            obj.voted = 0.0
            return
        repository = obj.repoid
        if not self.Equo.UGC.is_repository_eapi3_aware(repository):
            obj.voted = 0.0
            return
        atom = obj.name
        key = dep_getkey(atom)

        self.queueView.refresh()
        self.view.queue_draw()

        t = ParallelTask(self.vote_submit_thread, repository, key, obj)
        t.start()


    def vote_submit_thread(self, repository, key, obj):
        status, err_msg = self.Equo.UGC.add_vote(repository, key, int(obj.voted))

        if status:
            color = SulfurConf.color_good
            txt1 = _("Vote registered successfully")
            txt2 = str(int(obj.voted))
        else:
            color = SulfurConf.color_error
            txt1 = _("Error registering vote")
            txt2 = err_msg

        msg = "<span foreground='%s'><b>%s</b></span>: %s" % (
                color, txt1, txt2,)

        def do_refresh(msg):
            self.ui.status.push(STATUS_BAR_CONTEXT_IDS['UGC'],
                "%s: %s" % (txt1, txt2,))
            self.ui.UGCMessageLabel.show()
            self.ui.UGCMessageLabel.set_markup(msg)
            return False
        def remove_ugc_sts():
            self.ui.status.pop(STATUS_BAR_CONTEXT_IDS['UGC'])
            self.ui.UGCMessageLabel.set_markup("")
            self.ui.UGCMessageLabel.hide()
            return False

        gobject.timeout_add(0, do_refresh, msg)
        gobject.timeout_add(20*1000, remove_ugc_sts)
        t = ParallelTask(self.refresh_vote_info, obj)
        t.start()

    def refresh_vote_info(self, obj):
        time.sleep(5)
        obj.voted = 0.0
        def do_refresh():
            try:
                self.queueView.refresh()
            except self.Equo.dbapi2.ProgrammingError:
                pass
            self.view.queue_draw()
            return False
        gobject.timeout_add(0, do_refresh)

    def clear(self):
        self.__install_statuses.clear()
        self.store.clear()

    def set_filtering_string(self, filter_string, run_it = True):
        if not hasattr(self.ui, "pkgFilter"):
            return False
        self.ui.pkgFilter.set_text(filter_string)
        if run_it:
            self.ui.pkgFilter.activate()
        return True

    def get_installed_pkg_objs_for_selected(self):
        selected_objs = []
        for inst_obj in self.selected_objs:
            key, slot = inst_obj.keyslot
            m_tup = self.Equo.atom_match(key, matchSlot = slot)
            if m_tup[0] != -1:
                ep, new = self.etpbase.get_package_item(m_tup)
                if new:
                    raise ValueError("trying to load new package objects when" \
                        " shouldn't be allowed")
                selected_objs.append(ep)
        return selected_objs

    def populate(self, pkgs, widget = None, empty = False, pkgsets = False):

        self.dummyCats.clear()
        self.clear()
        search_col = 0

        if widget == None:
            widget = self.ui.viewPkg

        widget.set_model(None)
        widget.set_model(self.store)
        self.empty_mode = empty

        if not pkgs:
            widget.set_property('headers-visible', False)
            widget.set_property('enable-search', False)
            empty_item = self.etpbase._pkg_get_empty_search_item()
            self.store.append(None, (empty_item,))

        elif empty:
            widget.set_property('headers-visible', False)
            widget.set_property('enable-search', False)
            for po in pkgs:
                self.store.append(None, (po,))

        else:
            # current injectors fills the model
            self.Injector.inject(pkgs, pkgsets)

            widget.set_search_column(search_col)
            widget.set_search_equal_func(self.atom_search)
            widget.set_property('headers-visible', True)
            widget.set_property('enable-search', True)

        if self.Injector.expand:
            widget.expand_all()
            self.view_expanded = True
        else:
            widget.collapse_all()
            self.view_expanded = False


        # scroll back to top if possible
        if hasattr(self.ui, "swPkg"):
            self.ui.swPkg.set_placement(gtk.CORNER_TOP_LEFT)


    def atom_search(self, model, column, key, iterator):
        obj = model.get_value( iterator, 0 )
        if obj:
            try:
                return not obj.onlyname.startswith(key)
            except self.Equo.dbapi2.ProgrammingError:
                pass
        return True

    def set_pixbuf_to_cell(self, cell, filename):
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(
                const.PIXMAPS_PATH+"/packages/"+filename)
            cell.set_property( 'pixbuf', pixbuf )
        except gobject.GError:
            pass

    def set_pixbuf_to_image(self, img, filename):
        try:
            img.set_from_file(const.PIXMAPS_PATH+"/packages/"+filename)
        except gobject.GError:
            pass

    def create_text_column( self, hdr, property, size, sortcol = None,
            expand = False, set_height = 0, clickable = False, click_cb = None):
        """
        Create a TreeViewColumn with text and set
        the sorting properties and add it to the view
        """
        cell = gtk.CellRendererText()    # Size Column
        if set_height:
            cell.set_property('height', set_height)
        column = gtk.TreeViewColumn( hdr, cell )
        column.set_resizable( True )
        column.set_cell_data_func( cell, self.get_data_text, property )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( size )
        column.set_expand(expand)
        column.set_sort_column_id( -1 )
        column.set_clickable(clickable)
        if hasattr(click_cb, '__call__'):
            column.connect("clicked", click_cb)
        self.view.append_column( column )
        return column

    def get_data_text( self, column, cell, model, myiter, property ):
        obj = model.get_value( myiter, 0 )
        if obj:
            if self.empty_mode:
                w, h = self.view.get_size_request()
                cell.set_fixed_size(w, h)

            try:
                mydata = getattr( obj, property )
                cell.set_property('markup', mydata)
            except self.Equo.dbapi2.ProgrammingError:
                self.do_refresh_view = True
            if obj.color:
                self.set_line_status(obj, cell)
                cell.set_property('foreground', obj.color)

    def new_pixbuf( self, column, cell, model, myiter ):
        """ 
        Cell Data function for recent Column, shows pixmap
        if recent Value is True.
        """
        pkg = model.get_value( myiter, 0 )
        if pkg:

            self.set_line_status(pkg, cell)

            if pkg.dummy_type == SulfurConf.dummy_empty:
                cell.set_property( 'stock-id', 'gtk-apply' )
                return

            if pkg.dummy_type == SulfurConf.dummy_category:
                cell.set_property( 'icon-name', 'package-x-generic' )
                return

            # check if package is broken
            if pkg.broken:
                self.set_pixbuf_to_cell(cell, self.pkg_purge) # X icon
                return

            if not pkg.queued:

                if pkg.action in ["r", "rr"]:

                    # grab install status to determine what pixmap showing
                    # for installed packages, this could be slow, but let'see
                    inst_status = self.__install_statuses.get(pkg.matched_atom)
                    if inst_status is None:
                        try:
                            inst_status = pkg.install_status
                        except self.Equo.dbapi2.ProgrammingError:
                            inst_status = 0
                        self.__install_statuses[pkg.matched_atom] = inst_status

                    if inst_status is 2:
                        self.set_pixbuf_to_cell(cell, self.pkg_install_updatable)
                    else:
                        self.set_pixbuf_to_cell(cell, self.pkg_install_ok)

                elif pkg.action == "i":
                    self.set_pixbuf_to_cell(cell, self.pkg_install_new)
                elif pkg.action == "d":
                    self.set_pixbuf_to_cell(cell, self.pkg_downgrade)
                else:
                    self.set_pixbuf_to_cell(cell, self.pkg_install_updatable)

            else:

                if pkg.queued == "r" and not pkg.do_purge:
                    self.set_pixbuf_to_cell(cell, self.pkg_remove)
                if pkg.queued == "r" and pkg.do_purge:
                    self.set_pixbuf_to_cell(cell, self.pkg_purge)
                elif pkg.queued == "rr":
                    self.set_pixbuf_to_cell(cell, self.pkg_reinstall)
                elif pkg.queued == "i":
                    self.set_pixbuf_to_cell(cell, self.pkg_install)
                elif pkg.queued == "u":
                    self.set_pixbuf_to_cell(cell, self.pkg_update)
                elif pkg.queued == "d":
                    self.set_pixbuf_to_cell(cell, self.pkg_downgrade)

        else:
            cell.set_property( 'visible', False )

    def set_line_status(self, obj, cell, stype = "cell-background"):
        if obj.queued == "r":
            cell.set_property(stype, '#FFE2A3')
        elif obj.queued == "u":
            cell.set_property(stype, '#B7BEFF')
        elif obj.queued == "d":
            cell.set_property(stype, '#A7D0FF')
        elif obj.queued == "i":
            cell.set_property(stype, '#E9C8FF')
        elif obj.queued == "rr":
            cell.set_property(stype, '#B7BEFF')
        elif not obj.queued:
            cell.set_property(stype, None)

    def select_all(self):

        mylist = []
        for parent in self.store:
            for child in parent.iterchildren():
                mylist += [x for x in child if x.queued != x.action]

        if not mylist:
            return

        for obj in mylist:
            obj.queued = obj.action

        self.clear_updates()
        self.updates['u'] = self.queue.packages['u'][:]
        self.updates['i'] = self.queue.packages['i'][:]
        self.updates['r'] = self.queue.packages['r'][:]
        self.updates['d'] = self.queue.packages['d'][:]
        status, myaction = self.queue.add(mylist)
        if status == 0:
            self.updates['u'] = [x for x in self.queue.packages['u'] if x not \
                in self.updates['u']]
            self.updates['i'] = [x for x in self.queue.packages['i'] if x not \
                in self.updates['i']]
            self.updates['r'] = [x for x in self.queue.packages['r'] if x not \
                in self.updates['r']]
            self.updates['d'] = [x for x in self.queue.packages['d'] if x not \
                in self.updates['d']]
        else:
            for obj in mylist:
                obj.queued = None
        self.queueView.refresh()
        self.view.queue_draw()

    def clear_updates(self):
        self.updates = {}
        self.updates['u'] = []
        self.updates['r'] = []
        self.updates['d'] = []
        self.updates['i'] = []

    def deselect_all(self):

        xlist = []
        for parent in self.store:
            for child in parent.iterchildren():
                xlist += [x for x in child if x.queued == x.action]

        for key in self.updates:
            xlist += [x for x in self.updates[key] if x not in xlist]
        if not xlist:
            return
        for obj in xlist:
            obj.queued = None
        self.queue.remove(xlist)
        self.clear_updates()
        self.queueView.refresh()
        self.view.queue_draw()

class EntropyQueueView:

    def __init__( self, widget, queue ):
        self.view = widget
        self.setup_view()
        self.queue = queue
        self.Equo = Equo()
        self.ugc_update_event_handler_id = \
            SulfurSignals.connect('ugc_data_update', self.__ugc_refresh)

    def setup_view( self ):

        cell1 = gtk.CellRendererText()
        column1 = gtk.TreeViewColumn( _( "Applications" ), cell1, markup=0 )
        column1.set_resizable( True )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_expand(True)
        column1.set_fixed_width( 300 )
        column1.set_cell_data_func( cell1, self.get_data_text )
        self.view.append_column( column1 )
        column1.set_sort_column_id( -1 )

    def get_data_text( self, column, cell, model, iter ):
        namedesc = model.get_value( iter, 0 )
        cell.set_property('markup', namedesc)

    def set_line_status(self, obj, cell, stype = "cell-background"):
        if obj.queued == "r":
            cell.set_property(stype, '#FFE2A3')
        elif obj.queued == "u":
            cell.set_property(stype, '#B7BEFF')
        elif obj.queued == "i":
            cell.set_property(stype, '#D895FF')
        elif obj.queued == "rr":
            cell.set_property(stype, '#B7BEFF')
        elif obj.queued == "d":
            cell.set_property(stype, '#A7D0FF')
        elif not obj.queued:
            cell.set_property(stype, None)

    def __ugc_refresh(self, event):
        try:
            # this is atomic
            self.refresh()
        except:
            pass

    def refresh(self):

        model = gtk.TreeStore(gobject.TYPE_STRING)

        label = "<b>%s</b>" % (_( "Applications to remove" ),)
        mylist = self.queue.packages['r']
        if mylist:
            self.populate_list( model, label, mylist )

        label = "<b>%s</b>" % (_( "Applications to downgrade" ),)
        mylist = self.queue.packages['d']
        if mylist:
            self.populate_list( label, mylist )

        label = "<b>%s</b>" % (_( "Applications to install" ),)
        mylist = self.queue.packages['i']
        if mylist:
            self.populate_list( model, label, mylist )

        label = "<b>%s</b>" % (_( "Applications to update" ),)
        mylist = self.queue.packages['u']
        if mylist:
            self.populate_list( model, label, mylist )

        label = "<b>%s</b>" % (_( "Applications to reinstall" ),)
        mylist = self.queue.packages['rr']
        if mylist:
            self.populate_list( model, label, mylist )

        self.view.set_model(model)
        search_col = 0
        self.view.set_search_column( search_col )
        self.view.set_search_equal_func(self.atom_search)
        self.view.set_property('headers-visible', True)
        self.view.set_property('enable-search', True)

        self.view.expand_all()

    def atom_search(self, model, column, key, iterator):
        namedesc = model.get_value( iterator, 0 )
        return not (namedesc.find(key) != -1)

    def populate_list( self, model, label, mylist ):

        categories = {}
        for po in mylist:
            mycat = po.cat
            if mycat not in categories:
                categories[mycat] = []
            categories[mycat].append(po)

        cats = sorted(categories.keys())
        grandfather = model.append( None, (label,) )
        for category in cats:
            cat_desc = _("No description")
            cat_desc_data = self.Equo.get_category_description_data(category)
            if _LOCALE in cat_desc_data:
                cat_desc = cat_desc_data[_LOCALE]
            elif 'en' in cat_desc_data:
                cat_desc = cat_desc_data['en']
            cat_text = "<b><big>%s</big></b>\n<small>%s</small>" % (category,
                cleanMarkupString(cat_desc),)
            mydummy = DummyEntropyPackage(
                    namedesc = cat_text,
                    dummy_type = SulfurConf.dummy_category,
                    onlyname = category
            )
            mydummy.color = SulfurConf.color_package_category
            parent = model.append( grandfather, (mydummy.namedesc,) )
            for po in categories[category]:
                model.append( parent, (po.namedesc,) )


class EntropyFilesView:

    def __init__(self, widget, show_widget):
        self.view = widget
        self.model = self.setup_view()
        self.show_widget = show_widget

    def setup_view(self):

        model = gtk.TreeStore( gobject.TYPE_INT, gobject.TYPE_STRING,
            gobject.TYPE_STRING, gobject.TYPE_STRING )
        self.view.set_model( model )

        cell0 = gtk.CellRendererText()
        column0 = gtk.TreeViewColumn( "", cell0, markup = 0 )
        column0.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column0.set_fixed_width( 2 )
        self.view.append_column( column0 )

        cell1 = gtk.CellRendererText()
        column1 = gtk.TreeViewColumn( _( "Proposed" ), cell1, markup = 1 )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( 200 )
        column1.set_resizable( True )
        self.view.append_column( column1 )

        cell2 = gtk.CellRendererText()
        column2 = gtk.TreeViewColumn( _( "Destination" ), cell2, markup = 2 )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 200 )
        column2.set_resizable( True )
        self.view.append_column( column2 )

        cell3 = gtk.CellRendererText()
        column3 = gtk.TreeViewColumn( _( "Rev." ), cell3, text=3 )
        column3.set_resizable( True )
        column3.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column3.set_fixed_width( 30 )
        self.view.append_column( column3 )
        model.set_sort_column_id( 0, gtk.SORT_ASCENDING )
        self.view.get_selection().set_mode( gtk.SELECTION_SINGLE )
        return model

    def is_filled(self):
        first = self.model.get_iter_first()
        if not first:
            return False
        return True

    def populate(self, scandata):
        self.model.clear()
        keys = sorted(scandata.keys())
        for key in keys:
            self.model.append(None, [key,
                    os.path.basename(scandata[key]['source']),
                    scandata[key]['destination'],
                    scandata[key]['revision']
                ]
            )
        if keys:
            self.show_widget.show()

class EntropyAdvisoriesView:

    def __init__( self, widget, ui, etpbase ):
        self.view = widget
        self.model = self.setup_view()
        self.etpbase = etpbase
        self.ui = ui
        self._xcache = {}

    def setup_view( self ):
        model = gtk.ListStore(
                                gobject.TYPE_PYOBJECT,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING
        )
        self.view.set_model( model )

        # Setup resent column
        cell0 = gtk.CellRendererPixbuf()
        self.set_icon_to_cell(cell0, 'gtk-apply' )
        column0 = gtk.TreeViewColumn( _("Status"), cell0 )
        column0.set_cell_data_func( cell0, self.new_icon )
        column0.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column0.set_fixed_width( 50 )
        self.view.append_column( column0 )

        cell1 = gtk.CellRendererText()
        column1 = gtk.TreeViewColumn( _("Security id."), cell1, markup = 1 )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( 80 )
        column1.set_resizable( True )
        column1.set_cell_data_func( cell1, self.get_data_text )
        self.view.append_column( column1 )

        cell2 = gtk.CellRendererText()
        column2 = gtk.TreeViewColumn( _( "Application name" ), cell2, markup = 2 )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 210 )
        column2.set_resizable( True )
        column2.set_cell_data_func( cell2, self.get_data_text )
        self.view.append_column( column2 )

        cell3 = gtk.CellRendererText()
        column3 = gtk.TreeViewColumn( _( "Description" ), cell3, markup = 3 )
        column3.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column3.set_fixed_width( 190 )
        column3.set_resizable( True )
        column3.set_cell_data_func( cell3, self.get_data_text )
        self.view.append_column( column3 )

        self.view.connect("button-release-event", self.set_advisory_id)
        self.view.get_selection().set_mode( gtk.SELECTION_SINGLE )
        model.set_sort_column_id( 1, gtk.SORT_ASCENDING )

        return model

    def set_advisory_id(self, widget, event):

        model, myiter = widget.get_selection().get_selected()
        if myiter:
            key, affected, data = model.get_value( myiter, 0 )
            if key != None:
                self.enable_properties_menu((key, affected, data))
                return
        self.enable_properties_menu(None)

    def enable_properties_menu(self, data):
        self.etpbase.selected_advisory_item = None
        do = False
        if data:
            do = True
            self.etpbase.selected_advisory_item = data
        self.ui.advInfoButton.set_sensitive(do)

    def set_icon_to_cell(self, cell, icon):
        cell.set_property( 'icon-name', icon )

    def new_icon( self, column, cell, model, myiter ):
        key, affected, data = model.get_value( myiter, 0 )
        if key == None:
            affected = False
        if affected:
            self.set_icon_to_cell(cell, 'gtk-cancel')
        else:
            self.set_icon_to_cell(cell, 'gtk-apply')

    def get_data_text( self, column, cell, model, myiter ):
        key, affected, data = model.get_value( myiter, 0 )
        if key == None:
            affected = False
        if affected:
            cell.set_property('background', SulfurConf.color_background_error)
            cell.set_property('foreground',
                SulfurConf.color_error_on_color_background)
        else:
            cell.set_property('background', SulfurConf.color_background_good)
            cell.set_property('foreground',
                SulfurConf.color_good_on_color_background)

    def atom_search(self, model, column, key, iterator):
        obj = model.get_value( iterator, 2 )
        if isinstance(obj, const_get_stringtype()):
            if obj.find(key) != -1:
                return False
        return True

    def populate(self, security_interface, adv_metadata, show,
        use_cache = False):

        self.model.clear()
        self.enable_properties_menu(None)

        only_affected = False
        only_unaffected = False
        do_all = False
        if show == "affected":
            only_affected = True
        elif show == "applied":
            only_unaffected = True
        else:
            do_all = True

        model_data = None
        if use_cache and (show in self._xcache):
            model_data = self._xcache[show]

        if model_data is None:
            identifiers = {}
            model_data = []

            for key in adv_metadata:
                affected = security_interface.is_affected(key)
                if do_all:
                    identifiers[key] = affected
                elif only_affected and not affected:
                    continue
                elif only_unaffected and affected:
                    continue
                identifiers[key] = affected

            for key in identifiers:
                if not adv_metadata[key]['affected']:
                    continue
                affected_data = adv_metadata[key]['affected']
                if not affected_data:
                    continue
                for a_key in affected_data:
                    model_data.append(
                        (key, identifiers[key], adv_metadata[key], a_key))

        # cache item
        self._xcache[show] = model_data[:]

        if not model_data:
            self.model.append(
                [
                    (None, None, None),
                    "---------",
                    "<b>%s</b>" % (_("No advisories"),),
                    "<small>%s</small>" % (_("There are no items to show"),)
                ]
            )

        else:
            for key, adv_affected, adv_meta, a_key in model_data:
                self.model.append(
                    [
                        (key, adv_affected, adv_meta,),
                        key, "<b>%s</b>" % (a_key,),
                        "<small>%s</small>" % (
                            cleanMarkupString(adv_meta['title']),
                        )
                    ]
                )

        self.view.set_search_column(2)
        self.view.set_search_equal_func(self.atom_search)
        self.view.set_property('headers-visible', True)
        self.view.set_property('enable-search', True)


class EntropyRepoView:

    def __init__( self, widget, ui, application):
        self.view = widget
        self.headers = [_('Repository'), _('Filename')]
        self.store = self.setup_view()
        self.Equo = Equo()
        self.ui = ui
        self.okDialog = okDialog
        self.Sulfur = application

    def on_active_toggled( self, widget, path):
        self.view.set_sensitive(False)
        try:
            myiter = self.store.get_iter( path )
            state = self.store.get_value(myiter, 0)
            repoid = self.store.get_value(myiter, 3)
            if repoid != self.Equo.SystemSettings['repositories']['default_repository']:
                self.store.set_value(myiter, 0, not state)
                self.Sulfur.gtk_loop()
                if state:
                    self.store.set_value(myiter, 1, not state)
                    self.Equo.disable_repository(repoid)
                    initconfig_entropy_constants(etpSys['rootdir'])
                else:
                    self.Equo.enable_repository(repoid)
                    initconfig_entropy_constants(etpSys['rootdir'])
                self.Sulfur.reset_cache_status()
                self.Sulfur.show_packages(back_to_page = "repos")
        finally:
            self.view.set_sensitive(True)

    def on_update_toggled( self, widget, path):
        """ Repo select/unselect handler """
        self.view.set_sensitive(False)
        try:
            myiter = self.store.get_iter( path )
            state = self.store.get_value(myiter, 1)
            active = self.store.get_value(myiter, 0)
            if active:
                self.store.set_value(myiter, 1, not state)
        finally:
            self.view.set_sensitive(True)

    def setup_view( self ):

        store = gtk.ListStore( 'gboolean', 'gboolean', gobject.TYPE_STRING,
            gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.view.set_model( store )

        # Setup Selection Column
        cell1 = gtk.CellRendererToggle()    # Selection
        cell1.set_property( 'activatable', True )
        column1 = gtk.TreeViewColumn( _("Active"), cell1 )
        column1.add_attribute( cell1, "active", 0 )
        column1.set_resizable( True )
        column1.set_sort_column_id( -1 )
        self.view.append_column( column1 )
        cell1.connect( "toggled", self.on_active_toggled )

        # Setup Selection Column
        cell2 = gtk.CellRendererToggle()    # Selection
        cell2.set_property( 'activatable', True )
        column2 = gtk.TreeViewColumn( _("Update"), cell2 )
        column2.add_attribute( cell2, "active", 1 )
        column2.set_resizable( True )
        column2.set_sort_column_id( -1 )
        self.view.append_column( column2 )
        cell2.connect( "toggled", self.on_update_toggled )

        # Setup revision column
        self.create_text_column( _('Revision'), 2 )

        # Setup reponame & repofile column's
        self.create_text_column( _('Repository Identifier'), 3 )
        self.create_text_column( _('Description'), 4 )
        self.view.set_search_column( 1 )
        self.view.set_reorderable( False )
        return store

    def create_text_column( self, hdr, colno):
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( hdr, cell, text=colno )
        column.set_resizable( True )
        self.view.append_column( column )

    def populate(self):

        self.store.clear()
        for repo in self.Equo.SystemSettings['repositories']['order']:
            repodata = self.Equo.SystemSettings['repositories']['available'][repo]
            self.store.append([1, 1, repodata['dbrevision'], repo,
                repodata['description']])
        # excluded ones
        repo_excluded = self.Equo.SystemSettings['repositories']['excluded']
        for repo in repo_excluded:
            repodata = repo_excluded[repo]
            self.store.append([0, 0, repodata['dbrevision'], repo,
                repodata['description']])

    def new_pixbuf( self, column, cell, model, myiter ):
        gpg = model.get_value( myiter, 3 )
        if gpg:
            cell.set_property( 'visible', True )
        else:
            cell.set_property( 'visible', False)

    def get_selected( self ):
        selected = []
        for elem in self.store:
            state = elem[0]
            selection = elem[1]
            name = elem[3]
            if state and selection:
                selected.append( name )
        return selected

    def get_notselected( self ):
        notselected = []
        for elem in self.store:
            state = elem[0]
            name = elem[1]
            if not state:
                notselected.append( name )
        return notselected

    def deselect_all( self ):
        iterator = self.store.get_iter_first()
        while iterator != None:
            self.store.set_value( iterator, 0, False )
            iterator = self.store.iter_next( iterator )

    def select_all( self ):
        iterator = self.store.get_iter_first()
        while iterator != None:
            self.store.set_value( iterator, 0, True )
            iterator = self.store.iter_next( iterator )

    def get_repoid(self, iterdata):
        model, myiter = iterdata
        return model.get_value( myiter, 3 )

    def select_by_keys( self, keys):
        iterator = self.store.get_iter_first()
        while iterator != None:
            repoid = self.store.get_value( iterator, 1 )
            if repoid in keys:
                self.store.set_value( iterator, 0, True )
            else:
                self.store.set_value( iterator, 0, False)
            iterator = self.store.iter_next( iterator )

class EntropyRepositoryMirrorsView:

    def __init__( self, widget):
        self.view = widget
        self.headers = [""]
        self.store = self.setup_view()

    def setup_view( self ):

        store = gtk.ListStore(str)
        self.view.set_model( store )

        # Setup Repository URL column
        self.create_text_column( "", 0 )

        # Setup reponame & repofile column's
        self.view.set_search_column( 1 )
        self.view.set_reorderable( False )
        return store

    def create_text_column( self, hdr, colno):
        cell = gtk.CellRendererText()    # Size Column
        column = gtk.TreeViewColumn( hdr, cell, text=colno )
        column.set_resizable( True )
        self.view.append_column( column )

    def populate(self):
        self.store.clear()

    def get_selected( self ):
        selected = []
        for elem in self.store:
            name = elem[0]
            if name:
                selected.append( name )
        return selected

    def get_all( self ):
        return [x[0] for x in self.store]

    def add(self, url):
        self.store.append([str(url)])

    def remove_selected(self):
        urls = self.get_selected()
        self.remove(urls)

    def get_text(self, urldata):
        model, myiter = urldata
        return model.get_value( myiter, 0 )

    def remove(self, urldata):
        model, myiter = urldata
        self.store.remove(myiter)
