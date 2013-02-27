PKGNAME = magneto
SRCDIR = src
MISCDIR = misc
PIXDIR = data/pixmaps
ICONDIR = data/icons
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
DESTDIR =

all:

magneto-core-install:
	mkdir -p $(DESTDIR)$(PREFIX)/share/pixmaps/magneto
	mkdir -p $(DESTDIR)$(PREFIX)/share/magneto/icons
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/core
	install -m644 src/magneto/*.py \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/.
	install -m644 src/magneto/core/*.py \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/core/.
	install -m644 $(PIXDIR)/* $(DESTDIR)$(PREFIX)/share/pixmaps/magneto/.
	install -m644 $(ICONDIR)/* $(DESTDIR)$(PREFIX)/share/magneto/icons/.

magneto-loader-install:
	mkdir -p $(DESTDIR)/etc/xdg/autostart
	mkdir -p $(DESTDIR)$(BINDIR)
	mkdir -p $(DESTDIR)$(PREFIX)/share/applications
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/etc/xdg/autostart/.
	install -m644 $(MISCDIR)/*.desktop \
		$(DESTDIR)$(PREFIX)/share/applications/.
	install -m755 src/magneto_app.py \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto.py
	install -m755 $(MISCDIR)/magneto $(DESTDIR)$(BINDIR)/.

magneto-gtk-install:
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk
	install -m644 src/magneto/gtk/*.py \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk/.
	install -m644 src/magneto/gtk/*.glade \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk/.

magneto-gtk3-install:
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk3
	install -m644 src/magneto/gtk3/*.py \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk3/.
	install -m644 src/magneto/gtk3/*.ui \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk3/.

magneto-kde-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/kde
	mkdir -p $(DESTDIR)$(PREFIX)/share/apps/magneto
	install -m644 src/magneto/kde/*.py \
		$(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/kde/.
	# install Magneto notification service
	install -m644 $(MISCDIR)/magneto.notifyrc \
		$(DESTDIR)$(PREFIX)/share/apps/magneto/.


install: magneto-core-install magneto-loader-install \
		magneto-gtk-install magneto-gtk3-install \
		magneto-kde-install
