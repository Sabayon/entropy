PKGNAME = entropy
SUBDIRS = doc
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
DESTDIR = 

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	mkdir -p $(DESTDIR)$(LIBDIR)/entropy/server
	mkdir -p $(DESTDIR)/etc/entropy
	mkdir -p $(DESTDIR)$(PREFIX)/sbin
	mkdir -p $(DESTDIR)$(BINDIR)

	install -m 644 ../conf/server.conf.example $(DESTDIR)/etc/entropy/

	install -m 755 *.py $(DESTDIR)/$(LIBDIR)/entropy/server/
	mv $(DESTDIR)/$(LIBDIR)/entropy/server/eit.py $(DESTDIR)$(BINDIR)/eit
	install -m 755 matter $(DESTDIR)$(PREFIX)/sbin

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
