SUBDIRS = src
PYFILES = $(wildcard *.py)
PKGNAME = entropy-notification-applet
VERSION=$(shell awk '/Version:/ { print $$2 }' ${PKGNAME}.spec)
PYTHON=python
SRCDIR=src
MISCDIR=misc
PIXDIR=gfx
ALLDIRS=src gfx misc

all: subdirs
	
subdirs:
	for d in $(SUBDIRS); do make -C $$d; [ $$? = 0 ] || exit 1 ; done

clean:
	@rm -fv *~ *.tar.gz *.list *.lang
	for d in $(SUBDIRS); do make -C $$d clean ; done

install:
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/spritz/applet
	mkdir -p $(DESTDIR)/usr/share/pixmaps/spritz/applet
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/usr/share/autostart
	mkdir -p $(DESTDIR)/etc/xdg/autostart
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/etc
	install -m644 COPYING $(DESTDIR)/$(LIBDIR)/entropy/spritz/applet/.
	install -m755 $(MISCDIR)/etp-applet-gui $(DESTDIR)/usr/bin/.
	install -m644 $(PIXDIR)/applet/*.png $(DESTDIR)/usr/share/pixmaps/spritz/applet/.
	install -m644 $(PIXDIR)/entropy-applet.png $(DESTDIR)/usr/share/pixmaps/.
	chmod +x $(DESTDIR)/usr/bin/etp-applet-gui
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/usr/share/applications/.
	install -m644 $(MISCDIR)/etp-applet.desktop $(DESTDIR)/usr/share/autostart/.
	install -m644 $(MISCDIR)/etp-applet.desktop $(DESTDIR)/etc/xdg/autostart/.
	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done

FORCE:
    
