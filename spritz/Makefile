SUBDIRS = src po src/yumgui 
PYFILES = $(wildcard *.py)
PKGNAME = yumex
VERSION=$(shell awk '/Version:/ { print $$2 }' ${PKGNAME}.spec)
PYTHON=python
SRCDIR=src
MISCDIR=misc
PIXDIR=gfx
ALLDIRS=src po src/yumgui gfx misc tools

all: subdirs
	
subdirs:
	for d in $(SUBDIRS); do make -C $$d; [ $$? = 0 ] || exit 1 ; done

clean:
	@rm -fv *~ *.tar.gz *.list *.lang
	for d in $(SUBDIRS); do make -C $$d clean ; done

install:
	mkdir -p $(DESTDIR)/usr/lib/entropy/spritz
	mkdir -p $(DESTDIR)/usr/share/pixmaps/spritz
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/etc
	mkdir -p $(DESTDIR)/etc/pam.d
	mkdir -p $(DESTDIR)/etc/security/console.apps
	install -m644 COPYING $(DESTDIR)/usr/lib/entropy/spritz/.
	install -m755 $(MISCDIR)/yumex $(DESTDIR)/usr/lib/entropy/spritz/.
	install -m644 $(PIXDIR)/*.png $(DESTDIR)/usr/share/pixmaps/spritz/.
	install -m644 $(MISCDIR)/spritz.pam $(DESTDIR)/etc/pam.d/spritz
	chmod +x $(DESTDIR)/usr/lib/entropy/spritz
	install -m644 $(MISCDIR)/spritz.desktop $(DESTDIR)/usr/share/applications/.
	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done


FORCE:
    
