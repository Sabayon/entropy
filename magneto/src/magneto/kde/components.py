"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
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
        self.__launch_pm_button = QPushButton(_("Launch Application Browser"))
        self.__button_hbox.addWidget(self.__launch_pm_button)
        self.__button_hbox.addWidget(self.__close_button)

        self.__vbox.addLayout(self.__button_hbox)

        self.setLayout(self.__vbox)

        # set window settings
        self.resize(400, 200)
        self.setWindowTitle(_("Application updates"))

        self.connect(self.__close_button, SIGNAL("clicked()"), self.on_close)
        self.connect(self.__launch_pm_button, SIGNAL("clicked()"), self.on_pm)

    def closeEvent(self, event):
        """
        We don't want to kill the window, since the whole app will close
        otherwise.
        """
        event.ignore()
        self.on_close()

    def on_pm(self):
        self.__controller.launch_package_manager()

    def on_close(self):
        self.__controller.trigger_notice_window()

    def populate(self, pkg_data, critical_txt):
        self.__list_model.setStringList(pkg_data)
        self.__critical_label.setText(critical_txt)
        self.__list_view.update()
