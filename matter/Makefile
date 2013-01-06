SUBDIRS = 
PREFIX = /usr
LIBDIR = $(PREFIX)/lib
SBINDIR = $(PREFIX)/sbin
DESTDIR = 
MATTERDIR = $(DESTDIR)$(LIBDIR)/matter

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	mkdir -p $(MATTERDIR)/matter
	mkdir -p $(MATTERDIR)/matter/binpms
	mkdir -p $(DESTDIR)$(SBINDIR)

	install -m 644 matter/*.py $(MATTERDIR)/matter/
	install -m 644 matter/binpms/__init__.py \
		$(MATTERDIR)/matter/binpms/

	install -m 755 matter_app.py $(DESTDIR)$(SBINDIR)/matter
	install -m 755 antimatter.py $(DESTDIR)$(SBINDIR)/antimatter

	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

base-install:
	mkdir -p $(MATTERDIR)/matter/binpms

	install -m 644 matter/binpms/base.py \
		$(MATTERDIR)/matter/binpms/

entropysrv-install:
	mkdir -p $(MATTERDIR)/matter/binpms

	install -m 644 matter/binpms/entropysrv.py \
		$(MATTERDIR)/matter/binpms/

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
