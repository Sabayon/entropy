PKGNAME = entropy
SUBDIRS = doc po
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

	cp eit $(DESTDIR)$(LIBDIR)/entropy/server/ -Ra
	install -m 755 eit.py $(DESTDIR)$(BINDIR)/eit
	install -m 755 matter.py $(DESTDIR)$(PREFIX)/sbin/matter
	install -m 755 antimatter $(DESTDIR)$(PREFIX)/sbin

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
