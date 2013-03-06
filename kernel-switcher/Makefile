SUBDIRS = 
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
DESTDIR = 

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	install -d $(DESTDIR)/$(LIBDIR)/entropy/kernel-switcher
	install -d $(DESTDIR)$(BINDIR)

	install -m 644 kswitch.py $(DESTDIR)/$(LIBDIR)/entropy/kernel-switcher/
	install -m 755 kernel-switcher $(DESTDIR)/$(BINDIR)/.

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
