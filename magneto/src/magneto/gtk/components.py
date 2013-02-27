"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) GTK components}

"""

# System imports
import os

# GTK imports
import gobject
import gtk.glade
gtk.glade.bindtextdomain('entropy', "/usr/share/locale")
import gtk
from entropy.i18n import _


class GladeWindow:

    def __init__(self, filename, window_name):

        path = filename
        if not os.path.isfile(filename):
            path = "/usr/lib/entropy/magneto/magneto/gtk/%s" % (filename,)
        if not os.path.isfile(path):
            path = "magneto/gtk/%s" % (filename,)

        self.filename = path
        self.xml = gtk.glade.XML(self.filename, window_name, domain = "entropy")
        self.window = self.xml.get_widget(window_name)

    def get_widget(self, widget):
        return self.xml.get_widget(widget)


class AppletNoticeWindow(GladeWindow):

    def __init__(self, controller):
        GladeWindow.__init__(self, "magneto.glade", "notice_window_2")

        self.__controller = controller
        self.window.connect('delete_event', self.on_close)

        self.package_list = self.get_widget('update_clist')
        self.package_list.append_column(
            gtk.TreeViewColumn(
                _("Application"), gtk.CellRendererText(), text=0))
        self.package_list.append_column(
            gtk.TreeViewColumn(_("Latest version"),
                               gtk.CellRendererText(), text=1))
        self.package_list.get_selection().set_mode(gtk.SELECTION_NONE)

        self.notebook = self.get_widget('notice_notebook')
        self.critical_tab = None
        self.critical_tab_contents = None

        self.package_list_model = gtk.ListStore(gobject.TYPE_STRING,
            gobject.TYPE_STRING)
        self.package_list.set_model(self.package_list_model)

        self.xml.signal_autoconnect (
            {
            "on_launch_pm_clicked": self.on_pm,
            "on_close_clicked": self.on_close,
            })

        message_label = gtk.Label()
        message_label.set_line_wrap(True)
        self.message_label = message_label


    def hide(self):
        self.window.hide()

    def show(self):
        self.window.show()

    def on_pm(self, button):
        self.__controller.launch_package_manager()

    def on_close(self, *args):
        self.__controller.trigger_notice_window()
        return True

    def __set_critical(self, text):

        if not self.critical_tab_contents:

            vb = gtk.VBox()
            vb.add(self.message_label)
            tab_label = gtk.Label(_("Critical Information"))

            tab_label.show()
            self.message_label.show()
            vb.show()

            self.critical_tab = self.notebook.prepend_page(vb, tab_label)
            self.critical_tab_contents = vb

            self.notebook.set_current_page(
                self.notebook.page_num(self.critical_tab_contents))

            self.message_label.set_markup(text)

        else:

            self.message_label.set_markup(text)

    def __remove_critical(self):
        if not self.critical_tab_contents:
            return
        self.notebook.remove_page(
            self.notebook.page_num(self.critical_tab_contents))

    def populate(self, pkg_data, critical_txt):
        self.package_list_model.clear()
        for name, avail in pkg_data:
            self.package_list_model.append((name, avail,))

        if critical_txt:
            self.__set_critical(critical_txt)
        else:
            self.__remove_critical()
