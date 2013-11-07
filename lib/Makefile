PKGNAME = entropy
SUBDIRS = kswitch
PREFIX = /usr
VARDIR = /var
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
TMPFILESDIR = /usr/lib/tmpfiles.d
DESTDIR = 

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	install -d $(DESTDIR)/$(LIBDIR)/entropy/lib
	install -d $(DESTDIR)$(PREFIX)/sbin
	install -d $(DESTDIR)$(BINDIR)
	install -d -m 775 $(DESTDIR)/etc/entropy
	install -d $(DESTDIR)/etc/env.d
	install -d $(DESTDIR)/etc/init.d
	install -d $(DESTDIR)/etc/logrotate.d
	install -d $(DESTDIR)/$(LIBDIR)/entropy/services
	install -d $(DESTDIR)/$(TMPFILESDIR)

	# Empty directories that should be created and kept
	install -d -m 775 $(DESTDIR)$(VARDIR)/tmp/entropy
	touch $(DESTDIR)$(VARDIR)/tmp/entropy/.keep

	install -d -m 775 $(DESTDIR)$(VARDIR)/lib/entropy
	touch $(DESTDIR)$(VARDIR)/lib/entropy/.keep

	install -d -m 775 $(DESTDIR)/$(VARDIR)/lib/entropy/client/packages
	touch $(DESTDIR)/$(VARDIR)/lib/entropy/client/packages/.keep

	install -d -m 775 $(DESTDIR)/$(VARDIR)/log/entropy
	touch $(DESTDIR)/$(VARDIR)/log/entropy/.keep

	chmod +x entropy/spm/plugins/interfaces/portage_plugin/env_sourcer.sh
	cp -Ra entropy $(DESTDIR)/$(LIBDIR)/entropy/lib/

	ln -sf lib $(DESTDIR)/$(LIBDIR)/entropy/libraries
	install -m 755 ../misc/entropy.sh $(DESTDIR)$(PREFIX)/sbin/
	install -m 755 ../misc/entropy_hwgen.sh $(DESTDIR)$(BINDIR)/
	install -m 644 ../misc/entropy.logrotate $(DESTDIR)/etc/logrotate.d/entropy

	install -m 644 ../conf/entropy.conf $(DESTDIR)/etc/entropy/
	install -m 644 ../conf/fsdirs.conf $(DESTDIR)/etc/entropy/
	install -m 644 ../conf/fsdirsmask.conf $(DESTDIR)/etc/entropy/
	install -m 644 ../conf/fsldpaths.conf $(DESTDIR)/etc/entropy/
	install -m 644 ../conf/brokensyms.conf $(DESTDIR)/etc/entropy/
	install -m 644 ../conf/fssymlinks.conf $(DESTDIR)/etc/entropy/
	install -m 644 ../conf/brokenlibsmask.conf $(DESTDIR)/etc/entropy/
	install -m 644 ../conf/brokenlinksmask.conf $(DESTDIR)/etc/entropy/

	install -m 644 ../conf/repositories.conf.example $(DESTDIR)/etc/entropy/
	cp ../conf/repositories.conf.d $(DESTDIR)/etc/entropy/ -Ra
	install -m 644 ../conf/entropy.conf $(DESTDIR)/etc/entropy/
	cp ../conf/packages $(DESTDIR)/etc/entropy/ -Ra
	install -m 644 ../misc/05entropy.envd $(DESTDIR)/etc/env.d/05entropy

	install -m 644 ../docs/COPYING $(DESTDIR)/$(LIBDIR)/entropy/

	install -m 644 ../conf/entropy-tmpfiles.d.conf $(DESTDIR)/$(TMPFILESDIR)/entropy.conf

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
