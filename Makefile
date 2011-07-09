PKGNAME = entropy
PYTHON = python2
SUBDIRS = magneto misc/po sulfur
SERVER_INSPKGS = reagent.py activator.py server_reagent.py server_activator.py server_query.py
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
DESTDIR = 

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done

entropy-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/libraries
	mkdir -p $(DESTDIR)$(PREFIX)/sbin
	mkdir -p $(DESTDIR)$(BINDIR)
	mkdir -p $(DESTDIR)/etc/entropy
	mkdir -p $(DESTDIR)/etc/env.d
	mkdir -p $(DESTDIR)/etc/init.d
	mkdir -p $(DESTDIR)/etc/logrotate.d
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/services

	cp libraries/entropy $(DESTDIR)/$(LIBDIR)/entropy/libraries/ -Ra
	install -m 755 misc/entropy.sh $(DESTDIR)$(PREFIX)/sbin/
	install -m 755 services/repository_services $(DESTDIR)/etc/init.d/
	install -m 755 services/smartapp_wrapper $(DESTDIR)/$(LIBDIR)/entropy/services/
	install -m 755 misc/entropy_hwgen.sh $(DESTDIR)$(BINDIR)/
	install -m 644 misc/entropy.logrotate $(DESTDIR)/etc/logrotate.d/entropy

	install -m 644 conf/entropy.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fsdirs.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fsdirsmask.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fsldpaths.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/brokensyms.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fssymlinks.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/brokenlibsmask.conf $(DESTDIR)/etc/entropy/

	install -m 644 conf/repositories.conf.example $(DESTDIR)/etc/entropy/
	install -m 644 conf/entropy.conf $(DESTDIR)/etc/entropy/
	cp conf/packages $(DESTDIR)/etc/entropy/ -Ra
	install -m 644 misc/05entropy.envd $(DESTDIR)/etc/env.d/05entropy

	install -m 644 docs/COPYING $(DESTDIR)/$(LIBDIR)/entropy/

entropy-server-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/server
	mkdir -p $(DESTDIR)/etc/entropy
	mkdir -p $(DESTDIR)$(PREFIX)/sbin
	mkdir -p $(DESTDIR)$(PREFIX)/share/man/man1
	mkdir -p $(DESTDIR)$(PREFIX)/sbin

	install -m 644 conf/server.conf.example $(DESTDIR)/etc/entropy/

	install -m 755 server/*.py $(DESTDIR)/$(LIBDIR)/entropy/server/
	install -m 755 server/*.py $(DESTDIR)/$(LIBDIR)/entropy/server/
	install -m 755 server/eit $(DESTDIR)$(PREFIX)/sbin
	ln -sf /$(LIBDIR)/entropy/server/reagent.py $(DESTDIR)$(PREFIX)/sbin/reagent
	ln -sf /$(LIBDIR)/entropy/server/activator.py $(DESTDIR)$(PREFIX)/sbin/activator

	# copy man pages
	install -m 644 docs/man/man1/reagent.1 $(DESTDIR)$(PREFIX)/share/man/man1/
	install -m 644 docs/man/man1/activator.1 $(DESTDIR)$(PREFIX)/share/man/man1/

equo-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/client
	mkdir -p $(DESTDIR)/etc/portage
	mkdir -p $(DESTDIR)/etc/entropy
	mkdir -p $(DESTDIR)$(BINDIR)
	mkdir -p $(DESTDIR)$(PREFIX)/share/man/man1

	# copying portage bashrc
	install -m 644 conf/bashrc.entropy $(DESTDIR)/etc/portage/bashrc.entropy
	install -m 644 conf/client.conf $(DESTDIR)/etc/entropy/

	install -m 644 client/*.py $(DESTDIR)/$(LIBDIR)/entropy/client/
	install -m 644 client/revision $(DESTDIR)/$(LIBDIR)/entropy/client/
	install -m 755 client/equo.py $(DESTDIR)/$(LIBDIR)/entropy/client/
	install -m 755 services/kernel-switcher $(DESTDIR)$(BINDIR)/

	ln -sf /$(LIBDIR)/entropy/client/equo.py $(DESTDIR)$(BINDIR)/equo

	# copy man page
	install -m 644 docs/man/man1/equo.1 $(DESTDIR)$(PREFIX)/share/man/man1/

	# copy zsh completion
	mkdir -p $(DESTDIR)$(PREFIX)/share/zsh/site-functions
	install -m 644 conf/_equo $(DESTDIR)$(PREFIX)/share/zsh/site-functions/


updates-daemon-install:

	mkdir -p $(DESTDIR)/etc/dbus-1/system.d/
	mkdir -p $(DESTDIR)$(PREFIX)/sbin/
	mkdir -p $(DESTDIR)$(PREFIX)/libexec/
	mkdir -p $(DESTDIR)$(PREFIX)/share/dbus-1/system-services/
	mkdir -p $(DESTDIR)$(PREFIX)/share/dbus-1/interfaces/
	install -m 744 services/client-updates-daemon $(DESTDIR)$(PREFIX)/sbin/
	install -m 744 services/entropy-updates-service $(DESTDIR)$(PREFIX)/libexec/
	install -m 644 misc/dbus/system.d/org.entropy.Client.conf $(DESTDIR)/etc/dbus-1/system.d/
	install -m 644 misc/dbus/system-services/org.entropy.Client.service $(DESTDIR)$(PREFIX)/share/dbus-1/system-services/
	install -m 644 misc/dbus/interfaces/org.entropy.Client.xml $(DESTDIR)$(PREFIX)/share/dbus-1/interfaces/

install: all entropy-install entropy-server-install equo-install updates-daemon-install
	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done
