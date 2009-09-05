"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) UI components module}

"""

# System imports
import os

# Qt imports
from PyQt4.QtCore import SIGNAL
from PyQt4.QtGui import QPixmap, QHBoxLayout, QListView, QLabel, QWidget, \
    QStringListModel, QVBoxLayout, QPushButton, QIcon

# Entropy imports
from entropy.i18n import _

# Magneto imports
from magneto.core.config import PIXMAPS_PATH, ICON_PATH

class AppletIconPixbuf:

    def __init__(self):
        self.images = {}

    def add_file(self, name, filename):

        if not self.images.has_key(name):
            self.images[name] = []

        filename = os.path.join(PIXMAPS_PATH, filename)
        if not os.access(filename, os.R_OK):
            raise AttributeError("Cannot open image file %s" % filename)

        pixmap = QPixmap(filename)
        self.add(name, pixmap)

    def add(self, name, pixbuf):
        self.images[name].append(pixbuf)

    def best_match(self, name, size):
        best = None

        for image in self.images[name]:
            if not best:
                best = image
                continue
            if abs(size - image.height) < abs(size - best.height):
                best = image

        return best


class AppletNoticeWindow(QWidget):

    def __init__(self, controller):

        QWidget.__init__(self)
        self.__controller = controller

        self.__pkglist = []

        # setup widgets
        self.__vbox_up = QVBoxLayout()
        self.__critical_label = QLabel()
        self.__critical_label.setWordWrap(True)
        self.__list_model = QStringListModel()
        self.__list_view = QListView()
        self.__list_view.setModel(self.__list_model)
        self.__vbox_up.addWidget(self.__critical_label)
        self.__vbox_up.addWidget(self.__list_view)

        # bottom buttons
        self.__vbox = QVBoxLayout()
        self.__vbox.addLayout(self.__vbox_up)

        self.__button_hbox = QHBoxLayout()
        self.__close_button = QPushButton(_("Close"))
        self.__launch_pm_button = QPushButton(_("Launch Sulfur"))
        self.__button_hbox.addWidget(self.__launch_pm_button)
        self.__button_hbox.addWidget(self.__close_button)

        self.__vbox.addLayout(self.__button_hbox)

        self.setLayout(self.__vbox)

        # set window settings
        self.resize(400, 200)
        self.setWindowTitle(_("Application updates"))

        # set window icon
        if os.access(ICON_PATH, os.R_OK) and os.path.isfile(ICON_PATH):
            self.__window_icon = QIcon(ICON_PATH)
            self.setWindowIcon(self.__window_icon)

        self.connect(self.__close_button, SIGNAL("clicked()"), self.on_close)
        self.connect(self.__launch_pm_button, SIGNAL("clicked()"), self.on_sulfur)

    def closeEvent(self, event):
        """
        We don't want to kill the window, since the whole app will close
        otherwise.
        """
        event.ignore()
        self.on_close()

    def on_sulfur(self):
        self.__controller.launch_package_manager()

    def on_close(self):
        self.__controller.trigger_notice_window()

    def populate(self, pkg_data, critical_txt):
        self.__list_model.setStringList(pkg_data)
        self.__critical_label.setText(critical_txt)
        self.__list_view.update()


