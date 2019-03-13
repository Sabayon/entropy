SUBDIRS = data po
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
PYTHON_SITEDIR = $(LIBDIR)
RIGO_PYDIR = $(PYTHON_SITEDIR)/_entropy
DESTDIR =

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	install -d $(DESTDIR)$(BINDIR)/
	install -d $(DESTDIR)$(RIGO_PYDIR)/rigo/ \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/controllers \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/models \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/ui/gtk3/controllers \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/ui/gtk3/models \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/ui/gtk3/widgets \

	install -m 644 $(wildcard rigo/*.py) $(DESTDIR)$(RIGO_PYDIR)/rigo/
	install -m 644 $(wildcard rigo/models/*.py) \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/models/
	install -m 644 $(wildcard rigo/controllers/*.py) \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/controllers/
	install -m 644 $(wildcard rigo/ui/*.py) \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/ui/
	install -m 644 $(wildcard rigo/ui/gtk3/*.py) \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/ui/gtk3/

	install -m 644 $(wildcard rigo/ui/gtk3/models/*.py) \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/ui/gtk3/models/
	install -m 644 $(wildcard rigo/ui/gtk3/controllers/*.py) \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/ui/gtk3/controllers/
	install -m 644 $(wildcard rigo/ui/gtk3/widgets/*.py) \
		$(DESTDIR)$(RIGO_PYDIR)/rigo/ui/gtk3/widgets/

	install -m 755 rigo_app.py $(DESTDIR)$(BINDIR)/rigo
	install -d $(DESTDIR)/usr/share/applications
	install -d $(DESTDIR)/usr/share/mime/packages
	install -m 644 data/desktop/rigo.desktop $(DESTDIR)/usr/share/applications/
	install -m 644 data/desktop/rigo-mimetypes.xml $(DESTDIR)/usr/share/mime/packages/

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
