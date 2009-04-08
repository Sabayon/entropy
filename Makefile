PKGNAME = entropy
PYTHON = python2
SUBDIRS = client conf docs entropy-notification-applet handlers libraries misc/po misc server spritz
SERVER_INSPKGS = reagent.py activator.py server_reagent.py server_activator.py entropy-system-daemon entropy-repository-daemon server_query.py

all:
	for d in $(SUBDIRS); do make -C $$d; done

clean:
	for d in $(SUBDIRS); do make -C $$d clean; done
	cd pylzma && $(PYTHON) setup.py clean --all

pylzma:
	cd pylzma && $(PYTHON) setup.py build

entropy-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/libraries
	mkdir -p $(DESTDIR)/usr/sbin
	mkdir -p $(DESTDIR)/etc/entropy
	mkdir -p $(DESTDIR)/etc/env.d
	cp libraries $(DESTDIR)/$(LIBDIR)/entropy/ -Ra
	install -m 755 server/entropy-system-daemon $(DESTDIR)/usr/sbin/
	install -m 755 misc/entropy.sh $(DESTDIR)/usr/sbin/

	install -m 644 conf/entropy.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fsdirs.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/fsdirsmask.conf $(DESTDIR)/etc/entropy/
	install -m 644 conf/repositories.conf.example $(DESTDIR)/etc/entropy/
	install -m 644 conf/socket* $(DESTDIR)/etc/entropy/
	install -m 644 conf/entropy.conf $(DESTDIR)/etc/entropy/
	cp conf/packages $(DESTDIR)/etc/entropy/ -Ra
	install -m 644 misc/05entropy.envd $(DESTDIR)/etc/env.d/05entropy

	make DESTDIR="$(DESTDIR)" -C misc/po install

entropy-server-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/server
	mkdir -p $(DESTDIR)/etc/entropy
	mkdir -p $(DESTDIR)/usr/sbin
	install -m 644 conf/server.conf.example $(DESTDIR)/etc/entropy/

	install -m 755 server/reagent.py $(DESTDIR)/$(LIBDIR)/entropy/server/
	install -m 755 server/activator.py $(DESTDIR)/$(LIBDIR)/entropy/server/
	ln -sf ../lib/entropy/server/reagent.py $(DESTDIR)/usr/sbin/reagent
	ln -sf ../lib/entropy/server/activator.py $(DESTDIR)/usr/sbin/activator

equo-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/client
	mkdir -p $(DESTDIR)/etc/portage
	mkdir -p $(DESTDIR)/etc/entropy
	mkdir -p $(DESTDIR)/usr/bin

	# copying portage bashrc
	install -m 644 conf/bashrc.entropy $(DESTDIR)/etc/portage/bashrc.entropy
	install -m 644 conf/client.conf $(DESTDIR)/etc/entropy/

	install -m 644 client/*.py $(DESTDIR)/$(LIBDIR)/entropy/client/
	install -m 644 client/entropy-system-test-client $(DESTDIR)/$(LIBDIR)/entropy/client/
	install -m 755 client/equo.py $(DESTDIR)/$(LIBDIR)/entropy/client/

	ln -sf ../lib/entropy/client/equo.py $(DESTDIR)/usr/bin/equo


notification-applet-install:

	make DESTDIR="$(DESTDIR)" -C entropy-notification-applet install

spritz-install:

	make DESTDIR="$(DESTDIR)" -C spritz install

pylzma-install:

	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/libraries/pylzma/
	cd pylzma && $(PYTHON) setup.py install --root="$(DESTDIR)" --install-lib="$(LIBDIR)/entropy/libraries/pylzma/"

pycompile-all:

	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)/usr/', force = True, quiet = True)"

install: entropy-install entropy-server-install equo-install notification-applet-install spritz-install pycompile-all
