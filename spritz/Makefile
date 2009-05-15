SUBDIRS = src src/etpgui 
PYFILES = $(wildcard *.py)
PKGNAME = spritz
PYTHON = python2
SRCDIR = src
MISCDIR = misc
PIXDIR = gfx
ALLDIRS = src src/etpgui gfx misc

all: subdirs
	
subdirs:
	for d in $(SUBDIRS); do make -C $$d; [ $$? = 0 ] || exit 1 ; done

clean:
	@rm -fv *~ *.tar.gz *.list *.lang
	for d in $(SUBDIRS); do make -C $$d clean ; done

install:
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/spritz
	mkdir -p $(DESTDIR)/usr/share/pixmaps/spritz/packages
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/usr/share/mimelnk/application
	mkdir -p $(DESTDIR)/usr/share/mime/packages
	mkdir -p $(DESTDIR)/usr/share/autostart
	mkdir -p $(DESTDIR)/etc/xdg/autostart
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/etc
	mkdir -p $(DESTDIR)/etc/pam.d
	install -m644 COPYING $(DESTDIR)/$(LIBDIR)/entropy/spritz/.
	install -m755 $(MISCDIR)/entropy-repo-manager $(DESTDIR)/usr/bin/.
	install -m755 $(MISCDIR)/spritz $(DESTDIR)/usr/bin/.
	install -m755 $(MISCDIR)/spritz-uri-handler $(DESTDIR)/usr/bin/.
	install -m644 $(PIXDIR)/*.png $(DESTDIR)/usr/share/pixmaps/spritz/.
	install -m644 $(PIXDIR)/packages/*.png $(DESTDIR)/usr/share/pixmaps/spritz/packages/.
	install -m644 $(MISCDIR)/spritz.pam $(DESTDIR)/etc/pam.d/spritz
	install -m644 $(MISCDIR)/kde_x-spritz.desktop $(DESTDIR)/usr/share/mimelnk/application/.
	install -m644 $(MISCDIR)/entropy-mimetypes.xml $(DESTDIR)/usr/share/mime/packages/.
	chmod +x $(DESTDIR)/usr/bin/spritz
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/usr/share/applications/.
	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` LIBDIR=$(LIBDIR) -C $$d install; [ $$? = 0 ] || exit 1; done


FORCE:
    
