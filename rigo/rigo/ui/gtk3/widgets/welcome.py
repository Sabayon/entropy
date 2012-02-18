import os

from gi.repository import Gtk

from rigo.paths import DATA_DIR

from entropy.i18n import _


class WelcomeBox(Gtk.VBox):

    def __init__(self):
        Gtk.VBox.__init__(self)
        self._image_path = os.path.join(DATA_DIR, "ui/gtk3/art/rigo.png")

    def render(self):
        image = Gtk.Image.new_from_file(self._image_path)
        label = Gtk.Label()
        label.set_markup(_("<i>Browse <b>Applications</b> with ease</i>"))
        self.pack_start(image, False, False, 0)
        self.pack_start(label, False, False, 0)
        label.show()
        image.show()
