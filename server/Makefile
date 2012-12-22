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
	mkdir -p $(DESTDIR)$(BINDIR)

	install -m 644 ../conf/server.conf.example $(DESTDIR)/etc/entropy/

	cp -R eit $(DESTDIR)$(LIBDIR)/entropy/server/
	install -m 755 eit.py $(DESTDIR)$(BINDIR)/eit

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
