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
	mkdir -p $(DESTDIR)$(LIBDIR)/matter
	mkdir -p $(DESTDIR)/etc/entropy
	mkdir -p $(DESTDIR)$(PREFIX)/sbin
	mkdir -p $(DESTDIR)$(BINDIR)

	install -m 644 ../conf/server.conf.example $(DESTDIR)/etc/entropy/

	cp eit $(DESTDIR)$(LIBDIR)/entropy/server/ -R
	install -m 755 eit.py $(DESTDIR)$(BINDIR)/eit
	cp matter $(DESTDIR)$(LIBDIR)/matter/ -R
	install -m 755 matter.py $(DESTDIR)$(PREFIX)/sbin/matter
	install -m 755 antimatter.py $(DESTDIR)$(PREFIX)/sbin/antimatter

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
