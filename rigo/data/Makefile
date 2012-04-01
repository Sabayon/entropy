PREFIX = /usr
DESTDIR =

all:


install:
	install -d $(DESTDIR)$(PREFIX)/share/rigo/icons
	install -m 644 $(wildcard icons/*) \
		$(DESTDIR)$(PREFIX)/share/rigo/icons/

	install -d $(DESTDIR)$(PREFIX)/share/rigo/ui/gtk3/art \
		$(DESTDIR)$(PREFIX)/share/rigo/ui/gtk3/css
	install -m 644 $(wildcard ui/gtk3/art/*) \
		$(DESTDIR)$(PREFIX)/share/rigo/ui/gtk3/art/
	install -m 644 $(wildcard ui/gtk3/css/*) \
		$(DESTDIR)$(PREFIX)/share/rigo/ui/gtk3/css/
	install -m 644 ui/gtk3/rigo.ui \
		$(DESTDIR)$(PREFIX)/share/rigo/ui/gtk3/

clean:
