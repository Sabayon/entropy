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

import time
import gtk
import gobject
import pango
from etpgui.widgets import UI
from spritz_setup import const, cleanMarkupString, SpritzConf, unicode2htmlentities
from entropy_i18n import _,_LOCALE
import packages
from entropyConstants import *

class PkgInfoMenu:

    def __init__(self, Entropy, pkg, window):

        self.pkg_pixmap = const.PIXMAPS_PATH+'/package-x-generic.png'
        self.ugc_small_pixmap = const.PIXMAPS_PATH+'/ugc.png'
        self.ugc_pixmap = const.PIXMAPS_PATH+'/ugc/icon.png'
        self.refresh_pixmap = const.PIXMAPS_PATH+'/ugc/refresh.png'

        self.pkg = pkg
        self.vote = 0
        self.window = window
        self.Entropy = Entropy
        self.repository = None
        self.pkgkey = None
        self.ugc_page_idx = 5
        self.switched_to_ugc_page = False
        self.pkginfo_ui = UI( const.GLADE_FILE, 'pkgInfo', 'entropy' )
        self.pkginfo_ui.signal_autoconnect(self._getAllMethods())
        self.pkginfo_ui.pkgInfo.set_transient_for(self.window)
        self.setupPkgPropertiesView()

    def _getAllMethods(self):
        result = {}
        allAttrNames = self.__dict__.keys() + self._getAllClassAttributes()
        for name in allAttrNames:
            value = getattr(self, name)
            if callable(value):
                result[name] = value
        return result

    def _getAllClassAttributes(self):
        nameSet = {}
        for currClass in self._getAllClasses():
            nameSet.update(currClass.__dict__)
        result = nameSet.keys()
        return result

    def _getAllClasses(self):
        result = [self.__class__]
        i = 0
        while i < len(result):
            currClass = result[i]
            result.extend(list(currClass.__bases__))
            i = i + 1
        return result

    def set_pixbuf_to_cell(self, cell, filepath):
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(const.PIXMAPS_PATH+"/"+filepath)
            cell.set_property( 'pixbuf', pixbuf )
        except gobject.GError:
            pass

    def on_showContentButton_clicked( self, widget ):
        content = self.pkg.contentExt
        for x in content:
            self.contentModel.append(None,[x[0],x[1]])

    def on_closeInfo_clicked(self, widget):
        self.pkginfo_ui.pkgInfo.hide()

    def on_pkgInfo_delete_event(self, widget, path):
        self.pkginfo_ui.pkgInfo.hide()
        return True

    def on_loadUgcButton_clicked(self, widget):
        print widget
        print "UGC"

    def on_infoBook_switch_page(self, widget, page, page_num):
        if (page_num == self.ugc_page_idx) and (not self.switched_to_ugc_page):
            self.switched_to_ugc_page = True
            self.on_loadUgcButton_clicked(widget)


    def on_star5_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 5)

    def on_star4_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 4)

    def on_star3_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 3)

    def on_star2_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 2)

    def on_star1_enter_notify_event(self, widget, event):
        self.star_enter(widget, event, 1)

    '''
    def on_star5_leave_notify_event(self, widget, event):
        self.star_leave(widget, event, 5)

    def on_star4_leave_notify_event(self, widget, event):
        self.star_leave(widget, event, 4)

    def on_star3_leave_notify_event(self, widget, event):
        self.star_leave(widget, event, 3)

    def on_star2_leave_notify_event(self, widget, event):
        self.star_leave(widget, event, 2)

    def on_star1_leave_notify_event(self, widget, event):
        self.star_leave(widget, event, 1)

    def star_leave(self, widget, event, number):
        return

    '''

    def on_starsEvent_leave_notify_event(self, widget, event):
        self.pkginfo_ui.pkgInfo.window.set_cursor(None)
        self.set_stars(self.vote)

    def on_starsEvent_enter_notify_event(self, widget, event):
        self.pkginfo_ui.pkgInfo.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.CROSSHAIR))

    def on_starEvent5_button_release_event(self, widget, event):
        self.vote_click(5)

    def on_starEvent4_button_release_event(self, widget, event):
        self.vote_click(4)

    def on_starEvent3_button_release_event(self, widget, event):
        self.vote_click(3)

    def on_starEvent2_button_release_event(self, widget, event):
        self.vote_click(2)

    def on_starEvent1_button_release_event(self, widget, event):
        self.vote_click(1)

    def vote_click(self, vote):
        if self.Entropy.UGC == None:
            return
        if not (self.repository and self.pkgkey):
            return
        if not self.Entropy.UGC.is_repository_eapi3_aware(self.repository):
            return
        status, err_msg = self.Entropy.UGC.add_vote(self.repository, self.pkgkey, vote)
        if status:
            self.set_stars_from_repository()
            msg = "<small><span foreground='#339101'>%s</span>: %s</small>" % (_("Vote registered successfully"),vote,)
        else:
            msg = "<small><span foreground='#FF0000'>%s</span>: %s</small>" % (_("Error registering vote"),err_msg,)

        self.pkginfo_ui.ugcMessageBox.set_markup(msg)

    def star_enter(self, widget, event, number):
        self.set_stars(number, hover = True)

    def setupPkgPropertiesView(self):

        # license view
        self.licenseView = self.pkginfo_ui.licenseView
        self.licenseModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "License name" ), cell, markup = 0 )
        self.licenseView.append_column( column )
        self.licenseView.set_model( self.licenseModel )

        # sources view
        self.sourcesView = self.pkginfo_ui.sourcesView
        self.sourcesModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Sources" ), cell, markup = 0 )
        self.sourcesView.append_column( column )
        self.sourcesView.set_model( self.sourcesModel )

        # mirrors view
        self.mirrorsReferenceView = self.pkginfo_ui.mirrorsReferenceView
        self.mirrorsReferenceModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Mirrors" ), cell, markup = 0 )
        self.mirrorsReferenceView.append_column( column )
        self.mirrorsReferenceView.set_model( self.mirrorsReferenceModel )

        # keywords view
        self.keywordsView = self.pkginfo_ui.keywordsView
        self.keywordsModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Keywords" ), cell, markup = 0 )
        self.keywordsView.append_column( column )
        self.keywordsView.set_model( self.keywordsModel )

        # useflags view
        self.useflagsView = self.pkginfo_ui.useflagsView
        self.useflagsModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "USE flags" ), cell, markup = 0 )
        self.useflagsView.append_column( column )
        self.useflagsView.set_model( self.useflagsModel )

        # eclasses view
        self.eclassesView = self.pkginfo_ui.eclassesView
        self.eclassesModel = gtk.ListStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Eclasses" ), cell, markup = 0 )
        self.eclassesView.append_column( column )
        self.eclassesView.set_model( self.eclassesModel )

        # dependencies view
        self.dependenciesView = self.pkginfo_ui.dependenciesView
        self.dependenciesModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Dependencies" ), cell, markup = 0 )
        self.dependenciesView.append_column( column )
        self.dependenciesView.set_model( self.dependenciesModel )

        # depends view
        self.dependsView = self.pkginfo_ui.dependsView
        self.dependsModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Depends" ), cell, markup = 0 )
        self.dependsView.append_column( column )
        self.dependsView.set_model( self.dependsModel )

        # needed view
        self.neededView = self.pkginfo_ui.neededView
        self.neededModel = gtk.TreeStore( gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Needed libraries" ), cell, markup = 0 )
        self.neededView.append_column( column )
        self.neededView.set_model( self.neededModel )

        # protect view
        self.configProtectView = self.pkginfo_ui.configProtectView1
        self.configProtectModel = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Protected item" ), cell, markup = 0 )
        self.configProtectView.append_column( column )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Type" ), cell, markup = 1 )
        self.configProtectView.append_column( column )
        self.configProtectView.set_model( self.configProtectModel )

        # content view
        self.contentView = self.pkginfo_ui.contentView
        self.contentModel = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_STRING )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "File" ), cell, markup = 0 )
        column.set_resizable( True )
        self.contentView.append_column( column )
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "Type" ), cell, markup = 1 )
        column.set_resizable( True )
        self.contentView.append_column( column )
        self.contentView.set_model( self.contentModel )

        # ugc view
        self.ugcView = self.pkginfo_ui.ugcView
        self.ugcModel = gtk.TreeStore( gobject.TYPE_PYOBJECT )

        '''
        # Setup resent column
        cell = gtk.CellRendererPixbuf()
        cell.set_property('height', 52)
        self.set_pixbuf_to_cell(cell, self.pkg_install_ok )
        column1 = gtk.TreeViewColumn( self.pkgcolumn_text, cell1 )
        column1.set_cell_data_func( cell1, self.new_pixbuf )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( self.selection_width+40 )
        column1.set_sort_column_id( -1 )
        self.view.append_column( column1 )
        column1.set_clickable( False )


        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _( "" ), cell )
        column.set_resizable( True )
        column.set_cell_data_func( cell, self.get_data_text, property )
        column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column.set_fixed_width( size )
        column.set_expand(expand)
        column.set_sort_column_id( -1 )
        self.view.append_column( column )
        '''


    def set_stars(self, count, hover = False):
        pix_path = const.PIXMAPS_PATH+'/star.png'
        if hover:
            pix_path = const.PIXMAPS_PATH+'/star_selected.png'
        pix_path_empty = const.PIXMAPS_PATH+'/star_empty.png'
        widgets = [
        self.pkginfo_ui.vote1,
        self.pkginfo_ui.vote2,
        self.pkginfo_ui.vote3,
        self.pkginfo_ui.vote4,
        self.pkginfo_ui.vote5
        ]
        if count > len(widgets):
            count = len(widgets)
        if count < 0: count = 0
        idx = -1
        while count > -1:
            w = widgets[count-1]
            w.set_from_file(pix_path)
            w.show()
            count -= 1
            idx += 1
        mycount = len(widgets) - idx
        while mycount:
            w = widgets[idx]
            w.set_from_file(pix_path_empty)
            w.show()
            mycount -= 1
            idx += 1

    def set_stars_from_repository(self):
        if not (self.repository and self.pkgkey):
            return
        vote = self.Entropy.UGC.UGCCache.get_package_vote(self.repository, self.pkgkey)
        if isinstance(vote,float):
            self.set_stars(int(vote))
            self.vote = int(vote)

    def load(self):

        pkg = self.pkg
        dbconn = self.pkg.dbconn
        avail = False
        if dbconn:
            avail = dbconn.isIDPackageAvailable(pkg.matched_atom[0])
        if not avail:
            return
        from_repo = True
        if isinstance(pkg.matched_atom[1],int): from_repo = False
        if from_repo and pkg.matched_atom[1] not in self.Entropy.validRepositories:
            return

        # set package image
        pkgatom = pkg.name
        self.vote = int(pkg.vote)
        self.repository = pkg.repoid
        self.pkgkey = self.Entropy.entropyTools.dep_getkey(pkgatom)
        self.set_stars_from_repository()
        self.pkginfo_ui.pkgImage.set_from_file(self.pkg_pixmap)
        self.pkginfo_ui.ugcSmallIcon.set_from_file(self.ugc_small_pixmap)
        self.pkginfo_ui.ugcIcon.set_from_file(self.ugc_pixmap)
        self.pkginfo_ui.refreshImage.set_from_file(self.refresh_pixmap)

        self.pkginfo_ui.labelAtom.set_markup("<b>%s</b>" % (cleanMarkupString(pkgatom),))
        self.pkginfo_ui.labelDescription.set_markup("<small>%s</small>" % (pkg.description,))
        self.pkginfo_ui.ugcDescriptionLabel.set_markup("<small>%s\n%s</small>" % (
                _("Share your opinion, your documents, your screenshots!"),
                _("Be part of our Community!")
            )
        )
        self.pkginfo_ui.ugcDownloaded.set_markup(
            "<small>%s: <b>%s</b></small>" % (_("Number of downloads"), pkg.downloads,)
        )

        bold_items = [  self.pkginfo_ui.locationLabel,
                        self.pkginfo_ui.homepageLabel,
                        self.pkginfo_ui.versionLabel,
                        self.pkginfo_ui.slotLabel,
                        self.pkginfo_ui.tagLabel,
                        self.pkginfo_ui.revisionLabel,
                        self.pkginfo_ui.branchLabel,
                        self.pkginfo_ui.eapiLabel,
                        self.pkginfo_ui.downloadLabel,
                        self.pkginfo_ui.checksumLabel,
                        self.pkginfo_ui.downSizeLabel,
                        self.pkginfo_ui.installSizeLabel,
                        self.pkginfo_ui.creationDateLabel,
                        self.pkginfo_ui.chostLabel,
                        self.pkginfo_ui.cflagsLabel,
                        self.pkginfo_ui.cxxflagsLabel,
                        self.pkginfo_ui.maskedLabel,
                        self.pkginfo_ui.messagesLabel,
                        self.pkginfo_ui.triggerLabel,
                        self.pkginfo_ui.configProtectLabel,
                        self.pkginfo_ui.ugcTitleLabel
        ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<b>%s</b>" % (t,))

        repo = pkg.matched_atom[1]
        if repo == 0:
            self.pkginfo_ui.location.set_markup("%s" % (_("From your Operating System"),))
        else:
            self.pkginfo_ui.location.set_markup("%s" % (cleanMarkupString(etpRepositories[repo]['description']),))

        self.pkginfo_ui.version.set_markup( "%s" % (cleanMarkupString(pkg.onlyver),) )
        tag = pkg.tag
        if not tag: tag = "None"
        self.pkginfo_ui.tag.set_markup( "%s" % (tag,) )
        self.pkginfo_ui.slot.set_markup( "%s" % (pkg.slot,) )
        self.pkginfo_ui.revision.set_markup( "%s" % (pkg.revision,) )
        self.pkginfo_ui.branch.set_markup( "%s" % (pkg.release,) )
        self.pkginfo_ui.eapi.set_markup( "%s" % (pkg.api,) )
        self.pkginfo_ui.homepage.set_markup( "%s" % (cleanMarkupString(pkg.homepage),) )

        # license view
        self.licenseModel.clear()
        self.licenseView.set_model( self.licenseModel )
        licenses = pkg.lic
        licenses = licenses.split()
        for x in licenses:
            self.licenseModel.append(None,[x])

        self.pkginfo_ui.download.set_markup( "%s" % (pkg.binurl,) )
        self.pkginfo_ui.checksum.set_markup( "%s" % (pkg.digest,) )
        self.pkginfo_ui.pkgsize.set_markup( "%s" % (pkg.sizeFmt,) )
        self.pkginfo_ui.instsize.set_markup( "%s" % (pkg.disksizeFmt,) )
        self.pkginfo_ui.creationdate.set_markup( "%s" % (pkg.epochFmt,) )
        # compile flags
        chost, cflags, cxxflags = pkg.compileflags
        self.pkginfo_ui.cflags.set_markup( "%s" % (cflags,) )
        self.pkginfo_ui.cxxflags.set_markup( "%s" % (cxxflags,) )
        self.pkginfo_ui.chost.set_markup( "%s" % (chost,) )
        # messages
        messages = pkg.messages
        mbuffer = gtk.TextBuffer()
        mbuffer.set_text('\n'.join(messages))
        self.pkginfo_ui.messagesTextView.set_buffer(mbuffer)
        # masked ?
        masked = 'False'
        idpackage_masked, idmasking_reason = dbconn.idpackageValidator(pkg.matched_atom[0])
        if idpackage_masked == -1:
            masked = 'True, %s' % (etpConst['packagemaskingreasons'][idmasking_reason],)
        self.pkginfo_ui.masked.set_markup( "%s" % (masked,) )

        # sources view
        self.sourcesModel.clear()
        self.sourcesView.set_model( self.sourcesModel )
        mirrors = set()
        sources = pkg.sources
        for x in sources:
            if x.startswith("mirror://"):
                mirrors.add(x.split("/")[2])
            self.sourcesModel.append(None,[x])

        # mirrors view
        self.mirrorsReferenceModel.clear()
        self.mirrorsReferenceView.set_model(self.mirrorsReferenceModel)
        for mirror in mirrors:
            mirrorinfo = dbconn.retrieveMirrorInfo(mirror)
            if mirrorinfo:
                # add parent
                parent = self.mirrorsReferenceModel.append(None,[mirror])
                for info in mirrorinfo:
                    self.mirrorsReferenceModel.append(parent,[info])

        # keywords view
        self.keywordsModel.clear()
        self.keywordsView.set_model( self.keywordsModel )
        for x in pkg.keywords:
            self.keywordsModel.append(None,[x])

        # useflags view
        self.useflagsModel.clear()
        self.useflagsView.set_model( self.useflagsModel )
        for x in pkg.useflags:
            self.useflagsModel.append([cleanMarkupString(x)])

        # eclasses view
        self.eclassesModel.clear()
        self.eclassesView.set_model( self.eclassesModel )
        for x in pkg.eclasses:
            self.eclassesModel.append([cleanMarkupString(x)])

        # dependencies view
        self.dependenciesModel.clear()
        self.dependenciesView.set_model( self.dependenciesModel )
        deps = pkg.dependencies
        conflicts = pkg.conflicts
        for x in deps:
            self.dependenciesModel.append(None,[cleanMarkupString(x)])
        for x in conflicts:
            self.dependenciesModel.append(None,[cleanMarkupString("!"+x)])

        # depends view
        self.dependsModel.clear()
        self.dependsView.set_model( self.dependsModel )
        depends = pkg.dependsFmt
        for x in depends:
            self.dependsModel.append(None,[cleanMarkupString(x)])

        # needed view
        self.neededModel.clear()
        self.neededView.set_model( self.neededModel )
        neededs = pkg.needed
        for x in neededs:
            self.neededModel.append(None,[cleanMarkupString(x)])

        # content view
        self.contentModel.clear()
        self.contentView.set_model( self.contentModel )

        # trigger
        trigger = pkg.trigger
        mtrigger = gtk.TextBuffer()
        mtrigger.set_text(trigger)
        self.pkginfo_ui.triggerTextView.set_buffer(mtrigger)

        # CONFIG_PROTECT Stuff
        protect = pkg.protect
        protect_mask = pkg.protect_mask
        for item in protect.split():
            self.configProtectModel.append(None,[item,'protect'])
        for item in protect_mask.split():
            self.configProtectModel.append(None,[item,'mask'])

        self.pkginfo_ui.pkgInfo.show()

class MaskedPackagesDialog:

    def __init__( self, Entropy, etpbase, parent, pkgs, top_text = None, sub_text = None ):
        self.Entropy = Entropy
        self.etpbase = etpbase
        self.xml = gtk.glade.XML( const.GLADE_FILE, 'maskdialog', domain="entropy" )
        self.dialog = self.xml.get_widget( "maskdialog" )
        self.dialog.set_transient_for( parent )
        self.action = self.xml.get_widget( "maskAction" )
        self.subaction = self.xml.get_widget( "maskSubtext" )
        self.cancelbutton = self.xml.get_widget( "cancelbutton" )
        self.okbutton = self.xml.get_widget( "okbutton" )
        self.enableButton = self.xml.get_widget( "enableButton" )
        self.enableButton.connect("clicked", self.enablePackage)
        self.enableAllButton = self.xml.get_widget( "enableAllButton" )
        self.enableAllButton.connect("clicked", self.enableAllPackages)
        self.propertiesButton = self.xml.get_widget( "propertiesButton" )
        self.propertiesButton.connect("clicked", self.openPackageProperties)
        self.docancel = True

        # setup text
        if top_text == None:
            top_text = _("These are the packages that must be enabled to satisfy your request")

        tit = "<b><span foreground='#0087C1' size='large'>%s</span></b>\n" % (_("Some packages are masked"),)
        tit += top_text
        self.action.set_markup( tit )
        if sub_text != None: self.subaction.set_markup( sub_text )

        self.pkgs = pkgs
        self.pkg = self.xml.get_widget( "maskPkg" )
        # fill
        self.model = self.setup_view( self.pkg )
        self.show_data( self.model, self.pkgs )
        self.pkg.expand_all()
        self.pkgcount = 0
        self.maxcount = len(self.pkgs)

    def get_obj(self):
        model, myiter = self.pkg.get_selection().get_selected()
        if myiter:
            return model.get_value( myiter, 0 )
        return None

    def openPackageProperties(self, widget):
        obj = self.get_obj()
        if not obj:
            return
        mymenu = PkgInfoMenu(self.Entropy, obj, self.dialog)
        mymenu.load()

    def enablePackage(self, widget, obj = None, do_refresh = True):
        if not obj:
            obj = self.get_obj()
        if not obj:
            return
        result = self.Entropy.unmask_match(obj.matched_atom, dry_run = True)
        if result:
            self.etpbase.unmaskingPackages.add(obj.matched_atom)
            self.pkgcount += 1
            if do_refresh:
                self.refresh()
        return result

    def enableAllPackages(self, widget):

        for parent in self.model:
            for child in parent.iterchildren():
                for obj in child:
                    if not obj:
                        continue
                    if obj.dummy_type != None:
                        continue
                    self.enablePackage(None,obj,False)
        self.refresh()

    def refresh(self):
        self.pkg.queue_draw()
        self.pkg.expand_all()

    def run( self ):
        self.dialog.show_all()
        self.okbutton.set_sensitive(False)
        return self.dialog.run()

    def setup_view( self, view ):

        model = gtk.TreeStore( gobject.TYPE_PYOBJECT )
        view.set_model( model )

        cell1 = gtk.CellRendererText()
        column1 = gtk.TreeViewColumn( _( "Masked package" ), cell1 )
        column1.set_cell_data_func( cell1, self.show_pkg )
        column1.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column1.set_fixed_width( 420 )
        column1.set_resizable( False )
        view.append_column( column1 )

        cell2 = gtk.CellRendererPixbuf()
        column2 = gtk.TreeViewColumn( _("Enabled"), cell2 )
        column2.set_cell_data_func( cell2, self.new_pixbuf )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 60 )
        column2.set_sort_column_id( -1 )
        view.append_column( column2 )
        column2.set_clickable( False )

        return model


    def set_pixbuf_to_cell(self, cell, do):
        if do:
            cell.set_property( 'stock-id', 'gtk-apply' )
        elif do == False:
            cell.set_property( 'stock-id', 'gtk-cancel' )
        else:
            cell.set_property( 'stock-id', None )

    def new_pixbuf( self, column, cell, model, iterator ):

        if self.pkgcount >= self.maxcount:
            self.okbutton.set_sensitive(True)

        obj = model.get_value( iterator, 0 )
        if obj.matched_atom in self.etpbase.unmaskingPackages:
            self.set_pixbuf_to_cell(cell, True)
        elif obj.dummy_type:
            self.set_pixbuf_to_cell(cell, None)
        else:
            self.set_pixbuf_to_cell(cell, False)
        self.set_line_status(obj, cell, stype = "cell-background")

    def show_pkg( self, column, cell, model, iterator ):
        obj = model.get_value( iterator, 0 )
        mydata = getattr( obj, 'namedesc' )
        cell.set_property('markup', mydata )
        self.set_line_status(obj, cell)

    def set_line_status(self, obj, cell, stype = "cell-background"):
        if obj.queued == "r":
            cell.set_property(stype,'#FFE2A3')
        elif obj.queued == "u":
            cell.set_property(stype,'#B7BEFF')
        elif obj.queued == "i":
            cell.set_property(stype,'#D895FF')
        elif obj.queued == "rr":
            cell.set_property(stype,'#B7BEFF')
        elif not obj.queued:
            cell.set_property(stype,None)

    def show_data( self, model, pkgs ):

        model.clear()
        self.pkg.set_model(None)
        self.pkg.set_model(model)

        desc_len = 80
        search_col = 0
        categories = {}

        for po in pkgs:
            mycat = po.cat
            if not categories.has_key(mycat):
                categories[mycat] = []
            categories[mycat].append(po)

        cats = categories.keys()
        cats.sort()
        for category in cats:
            cat_desc = _("No description")
            cat_desc_data = self.Entropy.get_category_description_data(category)
            if cat_desc_data.has_key(_LOCALE):
                cat_desc = cat_desc_data[_LOCALE]
            elif cat_desc_data.has_key('en'):
                cat_desc = cat_desc_data['en']
            cat_text = "<b><big>%s</big></b>\n<small>%s</small>" % (category,cleanMarkupString(cat_desc),)
            mydummy = packages.DummyEntropyPackage(
                    namedesc = cat_text,
                    dummy_type = SpritzConf.dummy_category,
                    onlyname = category
            )
            mydummy.color = '#9C7234'
            parent = model.append( None, (mydummy,) )
            for po in categories[category]:
                model.append( parent, (po,) )

        self.pkg.set_search_column( search_col )
        self.pkg.set_search_equal_func(self.atom_search)
        self.pkg.set_property('headers-visible',True)
        self.pkg.set_property('enable-search',True)

    def atom_search(self, model, column, key, iterator):
        obj = model.get_value( iterator, 0 )
        if obj:
            return not obj.onlyname.startswith(key)
        return True

    def destroy( self ):
        return self.dialog.destroy()

class ConfirmationDialog:

    def __init__( self, parent, pkgs, top_text = None, bottom_text = None, bottom_data = None, sub_text = None, cancel = True, simpleList = False, simpleDict = False ):

        self.xml = gtk.glade.XML( const.GLADE_FILE, 'confirmation', domain="entropy" )
        self.dialog = self.xml.get_widget( "confirmation" )
        self.dialog.set_transient_for( parent )
        self.action = self.xml.get_widget( "confAction" )
        self.subaction = self.xml.get_widget( "confSubtext" )
        self.bottomTitle = self.xml.get_widget( "bottomTitle" )
        self.bottomData = self.xml.get_widget( "bottomData" )
        self.cancelbutton = self.xml.get_widget( "cancelbutton2" )
        self.bottomtext = self.xml.get_widget( "bottomTitle" )
        self.lowerhbox = self.xml.get_widget( "hbox63" )

        self.dobottomtext = bottom_text
        self.dobottomdata = bottom_data
        self.docancel = cancel
        self.simpleList = simpleList
        self.simpleDict = simpleDict

        # setup text
        if top_text == None:
            top_text = _("Please confirm the actions above")

        if sub_text == None:
            sub_text = ""

        tit = "<span size='x-large'>%s</span>" % (top_text,)
        self.action.set_markup( tit )
        if bottom_text != None: self.bottomTitle.set_markup( bottom_text )
        if bottom_data != None: self.bottomData.set_text( bottom_data )
        if sub_text != None: self.subaction.set_text( sub_text )

        self.pkgs = pkgs
        self.pkg = self.xml.get_widget( "confPkg" )
        if self.simpleList:
            self.pkgModel = self.setup_simple_view( self.pkg )
            self.show_data_simple( self.pkgModel, pkgs )
        elif self.simpleDict:
            self.pkgModel = self.setup_simple_view( self.pkg )
            self.show_data_simpledict( self.pkgModel, pkgs )
        else:
            self.pkgModel = self.setup_view( self.pkg )
            self.show_data( self.pkgModel, pkgs )
        self.pkg.expand_all()

    def run( self ):
        self.dialog.show_all()
        if not self.docancel:
            self.cancelbutton.hide()
        if not self.dobottomtext:
            self.bottomtext.hide()
        if not self.dobottomdata:
            self.lowerhbox.hide()
        return self.dialog.run()

    def setup_view( self, view ):
        model = gtk.TreeStore( gobject.TYPE_STRING )
        model.set_sort_column_id( 0, gtk.SORT_ASCENDING )
        view.set_model( model )
        self.create_text_column( _( "Package" ), view, 0 )
        return model

    def setup_simple_view(self, view ):
        model = gtk.TreeStore( gobject.TYPE_STRING )
        view.set_model( model )
        self.create_text_column( _( "Package" ), view, 0 )
        return model

    def create_text_column( self, hdr, view, colno, min_width=0, max_width=0 ):
        cell = gtk.CellRendererText()    # Size Column
        column = gtk.TreeViewColumn( hdr, cell, markup=colno )
        column.set_resizable( True )
        if min_width:
            column.set_min_width( min_width )
        if max_width:
            column.set_max_width( max_width )
        view.append_column( column )

    def show_data_simpledict( self, model, pkgs ):
        model.clear()
        if pkgs.has_key("reinstall"):
            if pkgs['reinstall']:
                label = "<b>%s</b>" % _("To be reinstalled")
                parent = model.append( None, [label] )
                for pkg in pkgs['reinstall']:
                    model.append( parent, [pkg] )
        if pkgs.has_key("install"):
            if pkgs['install']:
                label = "<b>%s</b>" % _("To be installed")
                parent = model.append( None, [label] )
                for pkg in pkgs['install']:
                    model.append( parent, [pkg] )
        if pkgs.has_key("update"):
            if pkgs['update']:
                label = "<b>%s</b>" % _("To be updated")
                parent = model.append( None, [label] )
                for pkg in pkgs['update']:
                    model.append( parent, [pkg] )
        if pkgs.has_key("downgrade"):
            if pkgs['downgrade']:
                label = "<b>%s</b>" % _("To be downgraded")
                parent = model.append( None, [label] )
                for pkg in pkgs['downgrade']:
                    model.append( parent, [pkg] )
        if pkgs.has_key("remove"):
            if pkgs['remove']:
                label = "<b>%s</b>" % _("To be removed")
                parent = model.append( None, [label] )
                for pkg in pkgs['remove']:
                    model.append( parent, [pkg] )

    def show_data_simple( self, model, pkgs ):
        model.clear()
        for pkg in pkgs:
            model.append( None, [pkg] )

    def show_data( self, model, pkgs ):
        model.clear()
        desc_len = 80
        install = [x for x in pkgs if x.action == "i"]
        update = [x for x in pkgs if x.action == "u"]
        remove = [x for x in pkgs if x.action == "r"]
        reinstall = [x for x in pkgs if x.action == "rr"]
        if reinstall:
            label = "<b>%s</b>" % _("To be reinstalled")
            level1 = model.append( None, [label] )
            for pkg in reinstall:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if install:
            label = "<b>%s</b>" % _("To be installed")
            level1 = model.append( None, [label] )
            for pkg in install:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if update:
            label = "<b>%s</b>" % _("To be updated")
            level1 = model.append( None, [label] )
            for pkg in update:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                model.append( level1, [mypkg+mydesc] )
        if remove:
            label = "<b>%s</b>" % _("To be removed")
            level1 = model.append( None, [label] )
            for pkg in remove:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupString(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                model.append( level1, [mypkg+mydesc] )

    def destroy( self ):
        return self.dialog.destroy()

class ConfimationDialog(ConfirmationDialog):
    pass

class ErrorDialog:
    def __init__( self, parent, title, text, longtext, modal ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "errDialog",domain="entropy" )
        self.dialog = self.xml.get_widget( "errDialog" )
        self.parent = parent
        if parent:
            self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "errText" )
        self.longtext = self.xml.get_widget( "errTextView" )
        self.nameInput = self.xml.get_widget( "nameEntry" )
        self.mailInput = self.xml.get_widget( "mailEntry" )
        self.reportLabel = self.xml.get_widget( "reportLabel" )
        self.errorButton = self.xml.get_widget( "errorButton" )
        self.actionInput = self.xml.get_widget( "actionEntry" )
        self.reportTable = self.xml.get_widget( "reportTable" )
        self.style_err = gtk.TextTag( "error" )
        self.style_err.set_property( "style", pango.STYLE_ITALIC )
        self.style_err.set_property( "foreground", "red" )
        self.style_err.set_property( "family", "Monospace" )
        self.style_err.set_property( "size_points", 8 )
        self.longtext.get_buffer().get_tag_table().add( self.style_err )

        if modal:
            self.dialog.set_modal( True )
        if text != "":
            self.set_text( text )
        if longtext != "" and longtext != None:
            self.set_long_text( longtext )

    def set_text( self, text ):
        self.text.set_markup( text )

    def set_long_text( self, longtext ):
        mybuffer = self.longtext.get_buffer()
        start, end = mybuffer.get_bounds()
        mybuffer.insert_with_tags( end, longtext, self.style_err )

    def run( self, showreport = False ):
        self.dialog.show_all()
        if not showreport:
            self.hide_report_widgets()
        return self.dialog.run()

    def hide_report_widgets(self):
        self.reportTable.hide_all()
        self.errorButton.hide()
        self.reportLabel.hide()

    def get_entries( self ):
        mail = self.mailInput.get_text()
        name = self.nameInput.get_text()
        desc = self.actionInput.get_text()
        return name,mail,desc

    def destroy( self ):
        return self.dialog.destroy()

class infoDialog:
    def __init__( self, parent, title, text ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "msg",domain="entropy" )
        self.dialog = self.xml.get_widget( "msg" )
        self.parent = parent
        self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "msgText" )
        self.dialog.set_modal( True )
        self.set_text( text )

    def set_text( self, text ):
        self.text.set_markup( "<span size='large'>%s</span>" % text )

    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()

    def destroy( self ):
        return self.dialog.destroy()


class EntryDialog:
    def __init__( self, parent, title, text ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "EntryDialog",domain="entropy" )
        self.dialog = self.xml.get_widget( "EntryDialog" )
        self.parent = parent
        #self.dialog.set_transient_for( parent )
        #self.dialog.set_icon_name( 'gtk-dialog-error' )
        self.dialog.set_title( title )
        self.text = self.xml.get_widget( "inputLabel" )
        self.entry = self.xml.get_widget( "inputEntry" )
        self.dialog.set_modal( True )
        self.text.set_text( text )

    def run( self ):
        self.dialog.show_all()
        rc = self.dialog.run()
        if rc == gtk.RESPONSE_OK:
            return self.entry.get_text()
        else:
            return None

    def destroy( self ):
        return self.dialog.destroy()

class AboutDialog(gtk.Window):

    """ Class for a fancy "About" dialog.
        Mostly ripped from the one in gDesklets
    """

    def __init__(self, gfx, creditText, title = "Spritz Package Manager"):

        self.__is_stopped = True
        self.__scroller_values = ()


        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_resizable(False)
        self.set_title("%s %s" % (_("About"),title,))
        self.connect("button-press-event", self.__on_close)
        self.connect("key-press-event", self.__on_close)
        self.connect("delete-event", self.__on_close)
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.set_decorated(False)

        fixed = gtk.Fixed()
        self.add(fixed)

        img = gtk.Image()
        img.set_from_file(gfx)
        fixed.put(img, 0, 0)

        width, height = img.size_request()

        scroller = gtk.Fixed()
        scroller.set_size_request(width, height - 32)
        fixed.put(scroller, 0, 32)

        text = ""
        for header, body in creditText:
            text += "<b>" + header + "</b>\n\n"
            text += "\n".join(body)
            text += "\n\n\n\n"
        text = "<big>" + text.strip() + "</big>"

        mycredits = gtk.Label("<span foreground='#FFFFFF'>%s</span>" % (text,))
        mycredits.set_use_markup(True)
        mycredits.set_justify(gtk.JUSTIFY_CENTER)

        lbl_width, lbl_height = mycredits.size_request()
        scroller.put(mycredits, (width - lbl_width) / 2, height)

        self.__scroller = scroller
        self.__credits = mycredits

        self.__scroller_values = (height - 32, -lbl_height,
                                  (width - lbl_width) / 2)


    def __scroll(self, ycoord):

        begin, end, xcoord = self.__scroller_values
        self.__scroller.move(self.__credits, xcoord, ycoord)
        ycoord -= 1

        if (ycoord < end):
            ycoord = begin

        if (not self.__is_stopped):
            gobject.timeout_add(50, self.__scroll, ycoord)

        return False


    def __on_close(self, *args):

        self.__is_stopped = True
        self.hide()
        return True


    def show(self):

        if (not self.__is_stopped):
            return

        self.show_all()

        self.__is_stopped = False
        begin, end, xcoord = self.__scroller_values
        gobject.timeout_add(0, self.__scroll, begin)


def inputBox( parent, title, text, input_text = None):
    dlg = EntryDialog(parent, title, text)
    if input_text:
        dlg.entry.set_text(input_text)
    rc = dlg.run()
    dlg.destroy()
    return rc

def FileChooser(basedir = None, pattern = None):
    # open file selector
    dialog = gtk.FileChooserDialog(
        title = None,
        action = gtk.FILE_CHOOSER_ACTION_OPEN,
        buttons = (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK)
    )
    if not basedir:
        basedir = os.getenv('HOME')
        if not basedir:
            basedir = "/tmp"

    fn = None
    dialog.set_current_folder(basedir)
    if pattern:
        myfilter = gtk.FileFilter()
        myfilter.add_pattern(pattern)
        dialog.set_filter(myfilter)
    response = dialog.run()
    if response == gtk.RESPONSE_OK:
        fn = dialog.get_filename()
    dialog.destroy()
    return fn

def errorMessage( parent, title, text, longtext=None, modal= True, showreport = False ):
     dlg = ErrorDialog( parent, title, text, longtext, modal )
     rc = dlg.run(showreport)
     entries = dlg.get_entries()
     dlg.destroy()
     return rc, entries

def infoMessage( parent, title, text ):
    dlg = infoDialog( parent, title, text )
    rc = dlg.run()
    dlg.destroy()
    return not rc == gtk.RESPONSE_OK

def questionDialog(parent, msg, title = _("Spritz Question"), get_response = False):
    dlg = gtk.MessageDialog(
        parent=parent,
        type = gtk.MESSAGE_QUESTION,
        buttons = gtk.BUTTONS_YES_NO,
        message_format = _("Hey!")
    )
    dlg.set_title(title)
    dlg.format_secondary_markup(cleanMarkupString(msg))
    rc = dlg.run()
    dlg.destroy()
    if get_response:
        return rc
    if rc == gtk.RESPONSE_YES:
        return True
    return False

def choiceDialog(parent, msg, title, buttons):
    return MessageDialog(parent, title, msg, type = "custom", custom_buttons = buttons).getrc()

def inputDialog(parent, title, input_parameters, cancel):
    w = InputDialog(parent, title, input_parameters, cancel)
    return w.run()

def okDialog(parent, msg, title = None):
    dlg = gtk.MessageDialog(parent=parent,
                            type=gtk.MESSAGE_INFO,
                            buttons=gtk.BUTTONS_OK)
    dlg.set_markup(msg)
    if not title:
        title = _("Attention")
    dlg.set_title( title )
    dlg.run()
    dlg.destroy()



class InputDialog:

    parameters = {}
    button_pressed = False
    main_window = None
    parent = None
    def __init__(self, parent, title, input_parameters, cancel = True):

        mywin = gtk.Window()
        mywin.set_transient_for(parent)
        mywin.set_title(_("Please fill the following form"))
        myvbox = gtk.VBox()
        mylabel = gtk.Label()
        mylabel.set_markup(cleanMarkupString(title))
        myhbox = gtk.HBox()
        myvbox.pack_start(mylabel)
        mytable = gtk.Table(rows = len(input_parameters), columns = 2)
        self.identifiers_table = {}
        self.cb_table = {}
        self.entry_text_table = {}
        row_count = 0
        for input_id, input_text, input_cb, passworded in input_parameters:
            input_label = gtk.Label()
            input_label.set_markup(input_text)
            input_entry = gtk.Entry()
            if passworded: input_entry.set_visibility(False)
            self.identifiers_table[input_id] = input_entry
            self.entry_text_table[input_id] = input_text
            self.cb_table[input_entry] = input_cb
            mytable.attach(input_label, 0, 1, row_count, row_count+1)
            mytable.attach(input_entry, 1, 2, row_count, row_count+1)
            row_count += 1
        myvbox.pack_start(mytable)
        bbox = gtk.HButtonBox()
        bbox.set_layout(gtk.BUTTONBOX_END)
        bbox.set_spacing(10)
        myok = gtk.Button(stock = "gtk-ok")
        myok.connect('clicked', self.do_ok )
        bbox.pack_start(myok, padding = 10)
        if cancel:
            mycancel = gtk.Button(stock = "gtk-cancel")
            mycancel.connect('clicked', self.do_cancel )
            bbox.pack_start(mycancel)
        myvbox.pack_start(bbox)
        myvbox.set_spacing(10)
        myvbox.show()
        myhbox.pack_start(myvbox, padding = 10)
        myhbox.show()
        mywin.add(myhbox)
        self.main_window = mywin
        self.parent = parent
        mywin.set_keep_above(True)
        mywin.set_urgency_hint(True)
        mywin.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        mywin.set_default_size(350,-1)
        mywin.show_all()


    def do_ok(self, widget):
        # fill self.parameters
        for input_id in self.identifiers_table:
            myentry = self.identifiers_table.get(input_id)
            entry_txt = myentry.get_text()
            verify_cb = self.cb_table.get(myentry)
            valid = verify_cb(entry_txt)
            if not valid:
                okDialog(self.parent, "%s: %s" % (_("Invalid entry"),self.entry_text_table[input_id],) , title = _("Invalid entry"))
                self.parameters.clear()
                return
            self.parameters[input_id] = entry_txt
        self.button_pressed = True

    def do_cancel(self, widget):
        self.parameters = None
        self.button_pressed = True

    def run(self):
        import time
        while not self.button_pressed:
            time.sleep(0.05)
            while gtk.events_pending():
                gtk.main_iteration()
            continue
        self.main_window.destroy()
        return self.parameters

class MessageDialog:
    """
        courtesy of Anaconda :-) Copyright 1999-2005 Red Hat, Inc.
        Matt Wilson <msw@redhat.com>
        Michael Fulbright <msf@redhat.com>
    """

    def getrc(self):
        return self.rc

    def __init__ (self, parent, title, text, type = "ok", default=None, custom_buttons=None, custom_icon=None):
        self.rc = None
        docustom = 0
        if type == 'ok':
            buttons = gtk.BUTTONS_OK
            style = gtk.MESSAGE_INFO
        elif type == 'warning':
            buttons = gtk.BUTTONS_OK
            style = gtk.MESSAGE_WARNING
        elif type == 'okcancel':
            buttons = gtk.BUTTONS_OK_CANCEL
            style = gtk.MESSAGE_WARNING
        elif type == 'yesno':
            buttons = gtk.BUTTONS_YES_NO
            style = gtk.MESSAGE_QUESTION
        elif type == 'custom':
            docustom = 1
            buttons = gtk.BUTTONS_NONE
            style = gtk.MESSAGE_QUESTION

        if custom_icon == "warning":
            style = gtk.MESSAGE_WARNING
        elif custom_icon == "question":
            style = gtk.MESSAGE_QUESTION
        elif custom_icon == "error":
            style = gtk.MESSAGE_ERROR
        elif custom_icon == "info":
            style = gtk.MESSAGE_INFO

        dialog = gtk.MessageDialog(parent, 0, style, buttons, text)

        if docustom:
            rid=0
            for button in custom_buttons:
                if button == _("Cancel"):
                    tbutton = "gtk-cancel"
                else:
                    tbutton = button

                widget = dialog.add_button(tbutton, rid)
                rid = rid + 1

            defaultchoice = rid - 1
        else:
            if default == "no":
                defaultchoice = 0
            elif default == "yes" or default == "ok":
                defaultchoice = 1
            else:
                defaultchoice = 0

        dialog.set_title(title)
        dialog.format_secondary_markup(cleanMarkupString(text))
        dialog.set_position (gtk.WIN_POS_CENTER)
        dialog.set_default_response(defaultchoice)
        dialog.show_all ()

        rc = dialog.run()

        if rc == gtk.RESPONSE_OK or rc == gtk.RESPONSE_YES:
            self.rc = 1
        elif (rc == gtk.RESPONSE_CANCEL or rc == gtk.RESPONSE_NO
            or rc == gtk.RESPONSE_CLOSE):
            self.rc = 0
        elif rc == gtk.RESPONSE_DELETE_EVENT:
            self.rc = 0
        else:
            self.rc = rc
        dialog.destroy()



class LicenseDialog:
    def __init__( self, parent, licenses, entropy ):

        self.Entropy = entropy
        self.xml = gtk.glade.XML( const.GLADE_FILE, 'licenseWindow',domain="entropy" )
        self.xml_licread = gtk.glade.XML( const.GLADE_FILE, 'licenseReadWindow',domain="entropy" )
        self.dialog = self.xml.get_widget( "licenseWindow" )
        self.dialog.set_transient_for( parent )
        self.read_dialog = self.xml_licread.get_widget( "licenseReadWindow" )
        self.read_dialog.connect( 'delete-event', self.close_read_text_window )
        #self.read_dialog.set_transient_for( self.dialog )
        self.licenseView = self.xml_licread.get_widget( "licenseTextView" )
        self.okReadButton = self.xml_licread.get_widget( "okReadButton" )
        self.okReadButton.connect( "clicked", self.close_read_text )


        self.okButton = self.xml.get_widget( "confirmLicense" )
        self.stopButton = self.xml.get_widget( "discardLicense" )
        self.acceptLicense = self.xml.get_widget( "acceptLicense" )
        self.acceptLicense.connect( "clicked", self.accept_selected_license )
        self.readLicense = self.xml.get_widget( "readLicense" )
        self.readLicense.connect( "clicked", self.read_selected_license )

        self.view = self.xml.get_widget( "licenseView1" )
        self.model = self.setup_view()
        self.show_data( licenses )
        self.view.expand_all()
        self.licenses = licenses
        self.accepted = set()


    def close_read_text_window(self, widget, path):
        self.read_dialog.hide()
        return True

    def close_read_text(self, widget ):
        self.read_dialog.hide()

    def run( self ):
        self.dialog.show_all()
        return self.dialog.run()

    def destroy( self ):
        return self.dialog.destroy()

    def setup_view(self):
        model = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_PYOBJECT )
        self.view.set_model( model )
        self.create_text_column( _( "License" ), 0, size = 200 )

        cell2 = gtk.CellRendererPixbuf()    # new
        column2 = gtk.TreeViewColumn( _("Accepted"), cell2 )
        column2.set_cell_data_func( cell2, self.new_pixbuf )
        column2.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        column2.set_fixed_width( 20 )
        column2.set_sort_column_id( -1 )
        self.view.append_column( column2 )
        column2.set_clickable( False )

        return model

    def set_pixbuf_to_cell(self, cell, do):
        if do:
            cell.set_property( 'stock-id', 'gtk-apply' )
        elif do == False:
            cell.set_property( 'stock-id', 'gtk-cancel' )
        else:
            cell.set_property( 'stock-id', None )

    def new_pixbuf( self, column, cell, model, iterator ):
        license_identifier = model.get_value( iterator, 0 )
        chief = model.get_value( iterator, 1 )
        if (license_identifier in self.accepted) and chief:
            self.set_pixbuf_to_cell(cell, True)
        elif chief:
            self.set_pixbuf_to_cell(cell, False)
        elif chief == None:
            self.set_pixbuf_to_cell(cell, None)

    def create_text_column( self, hdr, colno, size = None ):
        cell = gtk.CellRendererText()    # Size Column
        column = gtk.TreeViewColumn( hdr, cell, markup=colno )
        if size != None:
            column.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
            column.set_fixed_width( size )
        column.set_resizable( False )
        self.view.append_column( column )

    def read_selected_license(self, widget):
        model, iterator = self.view.get_selection().get_selected()
        if model != None and iterator != None:
            license_identifier = model.get_value( iterator, 0 )
            if not self.licenses.has_key(license_identifier): # for security reasons
                return
            packages = self.licenses[license_identifier]
            license_text = ''
            for package in packages:
                repoid = package[1]
                dbconn = self.Entropy.openRepositoryDatabase(repoid)
                if dbconn.isLicensedataKeyAvailable(license_identifier):
                    license_text = dbconn.retrieveLicenseText(license_identifier)
                    break
            # prepare textview
            mybuffer = gtk.TextBuffer()
            mybuffer.set_text(unicode(license_text,'raw_unicode_escape'))
            self.licenseView.set_buffer(mybuffer)
            self.read_dialog.set_title(license_identifier+" license text")
            self.read_dialog.show_all()

    def accept_selected_license(self, widget):
        model, iterator = self.view.get_selection().get_selected()
        if model != None and iterator != None:
            license_identifier = model.get_value( iterator, 0 )
            chief = model.get_value( iterator, 1 )
            if chief:
                self.accepted.add(license_identifier)
                self.view.queue_draw()
                if len(self.accepted) == len(self.licenses):
                    self.okButton.set_sensitive(True)

    def show_data( self, licenses ):
        self.model.clear()
        for lic in licenses:
            parent = self.model.append( None, [lic,True] )
            packages = licenses[lic]
            for match in packages:
                dbconn = self.Entropy.openRepositoryDatabase(match[1])
                atom = dbconn.retrieveAtom(match[0])
                self.model.append( parent, [atom,None] )
