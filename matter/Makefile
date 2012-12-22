SUBDIRS = 
PREFIX = /usr
LIBDIR = $(PREFIX)/lib
SBINDIR = $(PREFIX)/sbin
DESTDIR = 

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	mkdir -p $(DESTDIR)$(LIBDIR)/matter
	mkdir -p $(DESTDIR)$(SBINDIR)

	cp -R matter $(DESTDIR)$(LIBDIR)/matter/
	install -m 755 matter.py $(DESTDIR)$(SBINDIR)/matter
	install -m 755 antimatter.py $(DESTDIR)$(SBINDIR)/antimatter

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done