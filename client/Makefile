PKGNAME = entropy
SUBDIRS = doc po
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
DESTDIR = 

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	install -d $(DESTDIR)/$(LIBDIR)/entropy/client/solo/commands
	install -d -m 775 $(DESTDIR)/etc/entropy
	install -d $(DESTDIR)$(BINDIR)
	install -d $(DESTDIR)$(PREFIX)/share/man/man1

	# copying portage bashrc
	install -m 644 ../conf/client.conf $(DESTDIR)/etc/entropy/

	install -m 644 solo/*.py $(DESTDIR)/$(LIBDIR)/entropy/client/solo/
	install -m 644 solo/commands/*.py $(DESTDIR)/$(LIBDIR)/entropy/client/solo/commands/
	install -m 644 revision $(DESTDIR)/$(LIBDIR)/entropy/client/
	install -m 755 equo.py $(DESTDIR)/$(BINDIR)/equo
	install -m 755 kernel-switcher $(DESTDIR)/$(BINDIR)/

	# copy zsh completion
	install -d $(DESTDIR)$(PREFIX)/share/zsh/site-functions
	install -m 644 equo-completion.zsh $(DESTDIR)$(PREFIX)/share/zsh/site-functions/_equo

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
