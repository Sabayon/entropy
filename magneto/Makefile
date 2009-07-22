PKGNAME = magneto
SRCDIR = src
MISCDIR = misc
PIXDIR = gfx
ALLDIRS = src gfx misc

magneto-core-install:

	mkdir -p $(DESTDIR)/usr/share/pixmaps/magneto
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/core
	install -m644 src/magneto/*.py $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/.
	install -m644 src/magneto/core/*.py $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/core/.
	install -m644 $(PIXDIR)/magneto/*.png $(DESTDIR)/usr/share/pixmaps/magneto/.
	install -m644 $(PIXDIR)/magneto.png $(DESTDIR)/usr/share/pixmaps/.

magneto-loader-install:

	mkdir -p $(DESTDIR)/etc/xdg/autostart
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/usr/share/autostart
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/usr/share/autostart/.
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/etc/xdg/autostart/.
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/usr/share/applications/.
	install -m755 src/magneto.py $(DESTDIR)/$(LIBDIR)/entropy/magneto/.
	install -m755 $(MISCDIR)/magneto $(DESTDIR)/usr/bin/.

magneto-gtk-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk
	install -m644 src/magneto/gtk/*.py $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk/.
	install -m644 src/magneto/gtk/*.glade $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/gtk/.

magneto-kde-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/kde
	mkdir -p $(DESTDIR)/usr/share/apps/magneto
	# deprecated, kept for compat
	mkdir -p $(DESTDIR)/usr/kde/4.2/share/apps/magneto
	install -m644 src/magneto/kde/*.py $(DESTDIR)/$(LIBDIR)/entropy/magneto/magneto/kde/.
	# install Magneto notification service
	install -m644 $(MISCDIR)/magneto.notifyrc $(DESTDIR)/usr/share/apps/magneto/.
	# deprecated, kept for compat
	install -m644 $(MISCDIR)/magneto.notifyrc $(DESTDIR)/usr/kde/4.2/share/apps/magneto/.


install: magneto-core-install magneto-loader-install magneto-gtk-install magneto-kde-install









