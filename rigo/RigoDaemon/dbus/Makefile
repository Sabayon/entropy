PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
LIBEXECDIR = $(PREFIX)/libexec
DESTDIR = 

all:

install:
	install -d $(DESTDIR)$(LIBEXECDIR)
	install -d $(DESTDIR)/etc/dbus-1/system.d
	install -m 644 org.sabayon.Rigo.conf $(DESTDIR)/etc/dbus-1/system.d/

	install -d $(DESTDIR)$(PREFIX)/share/dbus-1/interfaces
	install -m 644 org.sabayon.Rigo.xml $(DESTDIR)$(PREFIX)/share/dbus-1/interfaces/

	install -m 755 RigoDaemon $(DESTDIR)$(LIBEXECDIR)/

	install -d $(DESTDIR)$(PREFIX)/share/dbus-1/system-services
	install -m 644 org.sabayon.Rigo.service $(DESTDIR)$(PREFIX)/share/dbus-1/system-services/

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
