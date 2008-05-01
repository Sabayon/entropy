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

import gtk
import gobject
import pango
from etpgui.widgets import UI
try:
    from iniparse.compat import ConfigParser,SafeConfigParser
except ImportError:
    from ConfigParser import ConfigParser,SafeConfigParser
from spritz_setup import const, cleanMarkupSting, SpritzConf, unicode2htmlentities
from i18n import _

class PkgInfoMenu:

    import entropyConstants
    def __init__(self, Entropy, pkg, window):
        self.pkg = pkg
        self.window = window
        self.Entropy = Entropy
        self.pkginfo_ui = UI( const.GLADE_FILE, 'pkgInfo', 'spritz' )
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

    def on_showContentButton_clicked( self, widget ):
        content = self.pkg.contentExt
        for x in content:
            self.contentModel.append(None,[x[0],x[1]])

    def on_closeInfo_clicked( self, widget ):
        self.pkginfo_ui.pkgInfo.hide()

    def on_pkgInfo_delete_event(self, widget, path):
        self.pkginfo_ui.pkgInfo.hide()
        return True

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
        self.configProtectView = self.pkginfo_ui.configProtectView
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


    def load(self):

        pkg = self.pkg
        dbconn = self.pkg.dbconn
        avail = False
        if dbconn:
            avail = dbconn.isIDPackageAvailable(pkg.matched_atom[0])
        if not avail:
            return
        if type(pkg.matched_atom[1]) is not int and pkg.matched_atom[1] not in self.Entropy.validRepositories:
            return

        # set package image
        pkg_pixmap = const.PIXMAPS_PATH+'/package-x-generic.png'
        heart_pixmap = const.PIXMAPS_PATH+'/heart.png'

        self.pkginfo_ui.pkgImage.set_from_file(pkg_pixmap)
        self.pkginfo_ui.vote1.set_from_file(heart_pixmap)
        self.pkginfo_ui.vote2.set_from_file(heart_pixmap)
        self.pkginfo_ui.vote3.set_from_file(heart_pixmap)
        self.pkginfo_ui.vote4.set_from_file(heart_pixmap)
        self.pkginfo_ui.vote5.set_from_file(heart_pixmap)

        self.pkginfo_ui.labelAtom.set_markup("<b>%s</b>" % (cleanMarkupSting(pkg.name),))
        self.pkginfo_ui.labelDescription.set_markup("<small>%s</small>" % (cleanMarkupSting(pkg.description),))

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
                        self.pkginfo_ui.useFlagsLabel,
                        self.pkginfo_ui.chostLabel,
                        self.pkginfo_ui.cflagsLabel,
                        self.pkginfo_ui.cxxflagsLabel,
                        self.pkginfo_ui.eclassesLabel,
                        self.pkginfo_ui.maskedLabel,
                        self.pkginfo_ui.messagesLabel,
                        self.pkginfo_ui.triggerLabel,
                        self.pkginfo_ui.configProtectLabel
        ]
        for item in bold_items:
            t = item.get_text()
            item.set_markup("<b>%s</b>" % (t,))

        repo = pkg.matched_atom[1]
        if repo == 0:
            self.pkginfo_ui.location.set_markup("%s" % (_("From your Operating System"),))
        else:
            self.pkginfo_ui.location.set_markup("%s" % (cleanMarkupSting(self.entropyConstants.etpRepositories[repo]['description']),))

        self.pkginfo_ui.version.set_markup( "%s" % (cleanMarkupSting(pkg.onlyver),) )
        tag = pkg.tag
        if not tag: tag = "None"
        self.pkginfo_ui.tag.set_markup( "%s" % (tag,) )
        self.pkginfo_ui.slot.set_markup( "%s" % (pkg.slot,) )
        self.pkginfo_ui.revision.set_markup( "%s" % (pkg.revision,) )
        self.pkginfo_ui.branch.set_markup( "%s" % (pkg.release,) )
        self.pkginfo_ui.eapi.set_markup( "%s" % (pkg.api,) )
        self.pkginfo_ui.homepage.set_markup( "%s" % (cleanMarkupSting(pkg.homepage),) )

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
        self.pkginfo_ui.useflags.set_markup( "%s" % (' '.join(pkg.useflags),) )
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
        # eclasses
        eclasses = ' '.join(pkg.eclasses)
        self.pkginfo_ui.eclasses.set_markup( "%s" % (eclasses,) )
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
        keywords = pkg.keywords
        for x in keywords:
            self.keywordsModel.append(None,[x])

        # dependencies view
        self.dependenciesModel.clear()
        self.dependenciesView.set_model( self.dependenciesModel )
        deps = pkg.dependencies
        conflicts = pkg.conflicts
        for x in deps:
            self.dependenciesModel.append(None,[cleanMarkupSting(x)])
        for x in conflicts:
            self.dependenciesModel.append(None,[cleanMarkupSting("!"+x)])

        # depends view
        self.dependsModel.clear()
        self.dependsView.set_model( self.dependsModel )
        depends = pkg.dependsFmt
        for x in depends:
            self.dependsModel.append(None,[cleanMarkupSting(x)])

        # needed view
        self.neededModel.clear()
        self.neededView.set_model( self.neededModel )
        neededs = pkg.needed
        for x in neededs:
            self.neededModel.append(None,[cleanMarkupSting(x)])

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

class ConfirmationDialog:
    def __init__( self, parent, pkgs, top_text = None, bottom_text = None, bottom_data = None, sub_text = None, cancel = True, simpleList = False, simpleDict = False ):

        self.xml = gtk.glade.XML( const.GLADE_FILE, 'confirmation',domain="spritz" )
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
                desc = cleanMarkupSting(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                level2 = model.append( level1, [mypkg+mydesc] )
        if install:
            label = "<b>%s</b>" % _("To be installed")
            level1 = model.append( None, [label] )
            for pkg in install:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupSting(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                level2 = model.append( level1, [mypkg+mydesc] )
        if update:
            label = "<b>%s</b>" % _("To be updated")
            level1 = model.append( None, [label] )
            for pkg in update:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupSting(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                level2 = model.append( level1, [mypkg+mydesc] )
        if remove:
            label = "<b>%s</b>" % _("To be removed")
            level1 = model.append( None, [label] )
            for pkg in remove:
                desc = pkg.description[:desc_len].rstrip()+"..."
                desc = cleanMarkupSting(desc)
                if not desc.strip():
                    desc = _("No description")
                mydesc = "\n<small><span foreground='#418C0F'>%s</span></small>" % (desc,)
                mypkg = "<span foreground='#FF0000'>%s</span>" % (str(pkg),)
                level2 = model.append( level1, [mypkg+mydesc] )

    def destroy( self ):
        return self.dialog.destroy()

class ConfimationDialog(ConfirmationDialog):
    pass

class ErrorDialog:
    def __init__( self, parent, title, text, longtext, modal ):
        self.xml = gtk.glade.XML( const.GLADE_FILE, "errDialog",domain="spritz" )
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
        self.xml = gtk.glade.XML( const.GLADE_FILE, "msg",domain="spritz" )
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
        self.xml = gtk.glade.XML( const.GLADE_FILE, "EntryDialog",domain="spritz" )
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

    def __init__(self, gfx,creditText,title="Spritz Package Manager"):

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

        mycredits = gtk.Label(text)
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
    dlg = EntryDialog( parent, title, text)
    if input_text:
        dlg.entry.set_text(input_text)
    rc = dlg.run()
    dlg.destroy()
    return rc

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

def questionDialog(parent, msg, message_format = _("Hey!")):
    dlg = gtk.MessageDialog(parent=parent,
                            type=gtk.MESSAGE_QUESTION,
                            buttons=gtk.BUTTONS_YES_NO, message_format = message_format)
    dlg.set_title( _("Spritz Question") )
    dlg.format_secondary_markup(cleanMarkupSting(msg))
    rc = dlg.run()
    dlg.destroy()
    if rc == gtk.RESPONSE_YES:
        return True
    else:
        return False

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


class LicenseDialog:
    def __init__( self, parent, licenses, entropy ):

        self.Entropy = entropy
        self.xml = gtk.glade.XML( const.GLADE_FILE, 'licenseWindow',domain="spritz" )
        self.xml_licread = gtk.glade.XML( const.GLADE_FILE, 'licenseReadWindow',domain="spritz" )
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

        self.view = self.xml.get_widget( "licenseView" )
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
            found = False
            for package in packages:
                repoid = package[1]
                dbconn = self.Entropy.openRepositoryDatabase(repoid)
                if dbconn.isLicensedataKeyAvailable(license_identifier):
                    license_text = dbconn.retrieveLicenseText(license_identifier)
                    found = True
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
