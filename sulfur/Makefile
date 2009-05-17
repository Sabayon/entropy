SUBDIRS = src src/etpgui 
PYFILES = $(wildcard *.py)
PKGNAME = sulfur
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
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/sulfur/misc
	mkdir -p $(DESTDIR)/usr/share/pixmaps/sulfur/packages
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/usr/share/mimelnk/application
	mkdir -p $(DESTDIR)/usr/share/mime/packages
	mkdir -p $(DESTDIR)/usr/share/autostart
	mkdir -p $(DESTDIR)/etc/xdg/autostart
	mkdir -p $(DESTDIR)/etc/gconf/schemas	
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/etc
	mkdir -p $(DESTDIR)/etc/pam.d

	install -m755 $(MISCDIR)/entropy-repo-manager $(DESTDIR)/usr/bin/.
	install -m755 $(MISCDIR)/sulfur $(DESTDIR)/usr/bin/.
	install -m755 $(MISCDIR)/sulfur-uri-handler $(DESTDIR)/usr/bin/.
	install -m644 $(MISCDIR)/entropy-handler.schemas $(DESTDIR)/etc/gconf/schemas/.
	install -m644 $(PIXDIR)/*.png $(DESTDIR)/usr/share/pixmaps/sulfur/.
	install -m644 $(PIXDIR)/packages/*.png $(DESTDIR)/usr/share/pixmaps/sulfur/packages/.
	install -m644 $(MISCDIR)/kde_x-sulfur.desktop $(DESTDIR)/usr/share/mimelnk/application/.
	install -m644 $(MISCDIR)/entropy-mimetypes.xml $(DESTDIR)/usr/share/mime/packages/.
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/usr/share/applications/.
	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` LIBDIR=$(LIBDIR) -C $$d install; [ $$? = 0 ] || exit 1; done


FORCE:
    
