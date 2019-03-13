PKGNAME = magneto
SRCDIR = src
MISCDIR = misc
PIXDIR = data/pixmaps
ICONDIR = data/icons
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
PYTHON_SITEDIR = $(LIBDIR)
DESTDIR =

all:

magneto-core-install:
	mkdir -p $(DESTDIR)$(PREFIX)/share/pixmaps/magneto
	mkdir -p $(DESTDIR)$(PREFIX)/share/magneto/icons
	mkdir -p $(DESTDIR)/$(PYTHON_SITEDIR)/_entropy/magneto/core
	install -m644 src/magneto/*.py \
		$(DESTDIR)/$(PYTHON_SITEDIR)/_entropy/magneto/.
	install -m644 src/magneto/core/*.py \
		$(DESTDIR)/$(PYTHON_SITEDIR)/_entropy/magneto/core/.
	install -m644 $(PIXDIR)/* $(DESTDIR)$(PREFIX)/share/pixmaps/magneto/.
	install -m644 $(ICONDIR)/* $(DESTDIR)$(PREFIX)/share/magneto/icons/.

magneto-loader-install:
	mkdir -p $(DESTDIR)/etc/xdg/autostart
	mkdir -p $(DESTDIR)$(BINDIR)
	mkdir -p $(DESTDIR)$(PREFIX)/share/applications
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/etc/xdg/autostart/.
	install -m644 $(MISCDIR)/*.desktop \
		$(DESTDIR)$(PREFIX)/share/applications/.
	install -m755 src/magneto_app.py \
		$(DESTDIR)$(BINDIR)/magneto

magneto-gtk-install:
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk
	mkdir -p $(DESTDIR)/$(PYTHON_SITEDIR)/_entropy/magneto/gtk
	install -m644 src/magneto/gtk/*.py \
		$(DESTDIR)/$(PYTHON_SITEDIR)/_entropy/magneto/gtk/.
	install -m644 src/magneto/gtk/*.glade \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk/.

magneto-gtk3-install:
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk3
	mkdir -p $(DESTDIR)/$(PYTHON_SITEDIR)/_entropy/magneto/gtk3
	install -m644 src/magneto/gtk3/*.py \
		$(DESTDIR)/$(PYTHON_SITEDIR)/_entropy/magneto/gtk3/.
	install -m644 src/magneto/gtk3/*.ui \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk3/.

magneto-kde-install:

	mkdir -p $(DESTDIR)/$(PYTHON_SITEDIR)/_entropy/magneto/qt5
	mkdir -p $(DESTDIR)$(PREFIX)/share/apps/magneto
	install -m644 src/magneto/qt5/*.py \
		$(DESTDIR)/$(PYTHON_SITEDIR)/_entropy/magneto/qt5/.
	# install Magneto notification service
	install -m644 $(MISCDIR)/magneto.notifyrc \
		$(DESTDIR)$(PREFIX)/share/apps/magneto/.


install: magneto-core-install magneto-loader-install \
		magneto-gtk-install magneto-gtk3-install \
		magneto-kde-install
