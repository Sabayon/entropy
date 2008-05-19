SUBDIRS = src src/etpgui src/applet 
PYFILES = $(wildcard *.py)
PKGNAME = spritz
VERSION=$(shell awk '/Version:/ { print $$2 }' ${PKGNAME}.spec)
PYTHON=python
SRCDIR=src
MISCDIR=misc
PIXDIR=gfx
ALLDIRS=src src/etpgui gfx misc tools src/applet

all: subdirs
	
subdirs:
	for d in $(SUBDIRS); do make -C $$d; [ $$? = 0 ] || exit 1 ; done

clean:
	@rm -fv *~ *.tar.gz *.list *.lang
	for d in $(SUBDIRS); do make -C $$d clean ; done

install:
	mkdir -p $(DESTDIR)/usr/lib/entropy/spritz
	mkdir -p $(DESTDIR)/usr/share/pixmaps/spritz/packages
	mkdir -p $(DESTDIR)/usr/share/pixmaps/spritz/applet
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/usr/share/autostart
	mkdir -p $(DESTDIR)/etc/xdg/autostart
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/etc
	mkdir -p $(DESTDIR)/etc/pam.d
	install -m644 COPYING $(DESTDIR)/usr/lib/entropy/spritz/.
	install -m755 $(MISCDIR)/spritz $(DESTDIR)/usr/bin/.
	install -m755 $(MISCDIR)/etp-applet-gui $(DESTDIR)/usr/bin/.
	install -m644 $(PIXDIR)/*.png $(DESTDIR)/usr/share/pixmaps/spritz/.
	install -m644 $(PIXDIR)/packages/*.png $(DESTDIR)/usr/share/pixmaps/spritz/packages/.
	install -m644 $(PIXDIR)/applet/*.png $(DESTDIR)/usr/share/pixmaps/spritz/applet/.
	install -m644 $(PIXDIR)/entropy-applet.png $(DESTDIR)/usr/share/pixmaps/.
	install -m644 $(MISCDIR)/spritz.pam $(DESTDIR)/etc/pam.d/spritz
	chmod +x $(DESTDIR)/usr/bin/spritz
	chmod +x $(DESTDIR)/usr/bin/etp-applet-gui
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/usr/share/applications/.
	install -m644 $(MISCDIR)/etp-applet.desktop $(DESTDIR)/usr/share/autostart/.
	install -m644 $(MISCDIR)/etp-applet.desktop $(DESTDIR)/etc/xdg/autostart/.
	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done


FORCE:
    
