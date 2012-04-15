SUBDIRS = data po
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
RIGODIR = $(LIBDIR)/rigo
DESTDIR =

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	install -d $(DESTDIR)$(BINDIR)/
	install -d $(DESTDIR)$(RIGODIR)/rigo/ \
		$(DESTDIR)$(RIGODIR)/rigo/controllers \
		$(DESTDIR)$(RIGODIR)/rigo/models \
		$(DESTDIR)$(RIGODIR)/rigo/ui/gtk3/controllers \
		$(DESTDIR)$(RIGODIR)/rigo/ui/gtk3/models \
		$(DESTDIR)$(RIGODIR)/rigo/ui/gtk3/widgets \

	install -m 644 $(wildcard rigo/*.py) $(DESTDIR)$(RIGODIR)/rigo/
	install -m 644 $(wildcard rigo/models/*.py) \
		$(DESTDIR)$(RIGODIR)/rigo/models/
	install -m 644 $(wildcard rigo/controllers/*.py) \
		$(DESTDIR)$(RIGODIR)/rigo/controllers/
	install -m 644 $(wildcard rigo/ui/*.py) \
		$(DESTDIR)$(RIGODIR)/rigo/ui/
	install -m 644 $(wildcard rigo/ui/gtk3/*.py) \
		$(DESTDIR)$(RIGODIR)/rigo/ui/gtk3/

	install -m 644 $(wildcard rigo/ui/gtk3/models/*.py) \
		$(DESTDIR)$(RIGODIR)/rigo/ui/gtk3/models/
	install -m 644 $(wildcard rigo/ui/gtk3/controllers/*.py) \
		$(DESTDIR)$(RIGODIR)/rigo/ui/gtk3/controllers/
	install -m 644 $(wildcard rigo/ui/gtk3/widgets/*.py) \
		$(DESTDIR)$(RIGODIR)/rigo/ui/gtk3/widgets/

	install -m 755 rigo_app.py $(DESTDIR)$(BINDIR)/rigo
	install -d $(DESTDIR)/usr/share/applications
	install -d $(DESTDIR)/usr/share/mime/packages
	install -m 644 data/desktop/rigo.desktop $(DESTDIR)/usr/share/applications/
	install -m 644 data/desktop/rigo-mimetypes.xml $(DESTDIR)/usr/share/mime/packages/

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
