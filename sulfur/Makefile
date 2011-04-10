SUBDIRS = src 
PYFILES = $(wildcard *.py)
PKGNAME = sulfur
PYTHON = python2
SRCDIR = src
MISCDIR = misc
PIXDIR = gfx
PREFIX = /usr
LIBDIR = $(PREFIX)/lib
BINDIR = $(PREFIX)/bin
DESTDIR = 

all: subdirs
	
subdirs:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; [ $$? = 0 ] || exit 1 ; done

clean:
	@rm -fv *~ *.tar.gz *.list *.lang
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean ; done

install:
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/sulfur/sulfur/misc
	mkdir -p $(DESTDIR)/usr/share/pixmaps/sulfur/packages
	mkdir -p $(DESTDIR)/usr/share/pixmaps/sulfur/gfx
	mkdir -p $(DESTDIR)/usr/share/pixmaps/sulfur/ugc
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/usr/share/mimelnk/application
	mkdir -p $(DESTDIR)/usr/share/mime/packages
	mkdir -p $(DESTDIR)/usr/share/autostart
	mkdir -p $(DESTDIR)/etc/xdg/autostart
	mkdir -p $(DESTDIR)/etc/gconf/schemas	
	mkdir -p $(DESTDIR)$(BINDIR)
	mkdir -p $(DESTDIR)/etc
	mkdir -p $(DESTDIR)/etc/pam.d

	install -m755 $(MISCDIR)/sulfur $(DESTDIR)$(BINDIR)/.
	install -m755 $(MISCDIR)/sulfur-uri-handler $(DESTDIR)$(BINDIR)/.
	install -m644 $(MISCDIR)/entropy-handler.schemas $(DESTDIR)/etc/gconf/schemas/.
	install -m644 $(PIXDIR)/*.png $(DESTDIR)/usr/share/pixmaps/sulfur/.
	install -m644 $(PIXDIR)/*.gif $(DESTDIR)/usr/share/pixmaps/sulfur/.
	install -m644 $(PIXDIR)/packages/*.png $(DESTDIR)/usr/share/pixmaps/sulfur/packages/.
	install -m644 $(PIXDIR)/ugc/*.png $(DESTDIR)/usr/share/pixmaps/sulfur/ugc/.
	install -m644 $(MISCDIR)/kde_x-sulfur.desktop $(DESTDIR)/usr/share/mimelnk/application/.
	install -m644 $(MISCDIR)/entropy-mimetypes.xml $(DESTDIR)/usr/share/mime/packages/.
	install -m644 $(MISCDIR)/*.desktop $(DESTDIR)/usr/share/applications/.
	for d in $(SUBDIRS); do $(MAKE) DESTDIR=`cd $(DESTDIR); pwd` LIBDIR=$(LIBDIR) -C $$d install; [ $$? = 0 ] || exit 1; done


FORCE:
    
