SUBDIRS = 
PREFIX = /usr
LIBDIR = $(PREFIX)/lib
PYTHON_SITEDIR = $(LIBDIR)
SBINDIR = $(PREFIX)/sbin
DESTDIR = 
MATTER_PYDIR = $(DESTDIR)$(PYTHON_SITEDIR)/_entropy

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	mkdir -p $(MATTER_PYDIR)/matter
	mkdir -p $(MATTER_PYDIR)/matter/binpms
	mkdir -p $(DESTDIR)$(SBINDIR)

	install -m 644 matter/*.py $(MATTER_PYDIR)/matter/
	install -m 644 matter/binpms/__init__.py \
		$(MATTER_PYDIR)/matter/binpms/

	install -m 755 matter_app.py $(DESTDIR)$(SBINDIR)/matter
	install -m 755 antimatter.py $(DESTDIR)$(SBINDIR)/antimatter

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

base-install:
	mkdir -p $(MATTER_PYDIR)/matter/binpms

	install -m 644 matter/binpms/base.py \
		$(MATTER_PYDIR)/matter/binpms/

entropysrv-install:
	mkdir -p $(MATTER_PYDIR)/matter/binpms

	install -m 644 matter/binpms/entropysrv.py \
		$(MATTER_PYDIR)/matter/binpms/

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
