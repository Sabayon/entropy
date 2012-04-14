PKGNAME = entropy
PYTHON = python2
SUBDIRS = server magneto misc/po sulfur
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

	install -d $(DESTDIR)/$(LIBDIR)/entropy/lib
	install -d $(DESTDIR)$(PREFIX)/sbin
	install -d $(DESTDIR)$(BINDIR)
	install -d $(DESTDIR)/etc/entropy
	install -d $(DESTDIR)/etc/env.d
	install -d $(DESTDIR)/etc/init.d
	install -d $(DESTDIR)/etc/logrotate.d
	install -d $(DESTDIR)/$(LIBDIR)/entropy/services

	cp lib/entropy $(DESTDIR)/$(LIBDIR)/entropy/lib/ -Ra
	ln -sf lib $(DESTDIR)/$(LIBDIR)/entropy/libraries
	install -m 755 misc/entropy.sh $(DESTDIR)$(PREFIX)/sbin/
	install -m 755 services/repository_services $(DESTDIR)/etc/init.d/
	install -m 755 misc/entropy_hwgen.sh $(DESTDIR)$(BINDIR)/
	install -m 644 misc/entropy.logrotate $(DESTDIR)/etc/logrotate.d/entropy

	install -m 644 conf/entropy.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fsdirs.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fsdirsmask.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fsldpaths.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/brokensyms.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fssymlinks.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/brokenlibsmask.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/brokenlinksmask.conf $(DESTDIR)/etc/entropy/

	install -m 644 conf/repositories.conf.example $(DESTDIR)/etc/entropy/
	cp conf/repositories.conf.d $(DESTDIR)/etc/entropy/ -Ra
	install -m 644 conf/entropy.conf $(DESTDIR)/etc/entropy/
	cp conf/packages $(DESTDIR)/etc/entropy/ -Ra
	install -m 644 misc/05entropy.envd $(DESTDIR)/etc/env.d/05entropy

	install -m 644 docs/COPYING $(DESTDIR)/$(LIBDIR)/entropy/

equo-install:

	install -d $(DESTDIR)/$(LIBDIR)/entropy/client
	install -d $(DESTDIR)/etc/portage
	install -d $(DESTDIR)/etc/entropy
	install -d $(DESTDIR)$(BINDIR)
	install -d $(DESTDIR)$(PREFIX)/share/man/man1

	# copying portage bashrc
	install -m 644 conf/bashrc.entropy $(DESTDIR)/etc/portage/bashrc.entropy
	install -m 644 conf/client.conf $(DESTDIR)/etc/entropy/

	install -m 644 client/*.py $(DESTDIR)/$(LIBDIR)/entropy/client/
	install -m 644 client/revision $(DESTDIR)/$(LIBDIR)/entropy/client/
	install -m 755 client/equo.py $(DESTDIR)/$(BINDIR)/equo
	install -m 755 services/kernel-switcher $(DESTDIR)$(BINDIR)/

	# copy man page
	install -m 644 docs/man/man1/equo.1 $(DESTDIR)$(PREFIX)/share/man/man1/

	# copy zsh completion
	install -d $(DESTDIR)$(PREFIX)/share/zsh/site-functions
	install -m 644 conf/_equo $(DESTDIR)$(PREFIX)/share/zsh/site-functions/


install: all entropy-install equo-install
	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done
