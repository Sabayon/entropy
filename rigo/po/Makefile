DESTDIR =
INSTALL = /usr/bin/install -c
INSTALL_PROGRAM = ${INSTALL}
INSTALL_DATA = ${INSTALL} -m 644
INSTALLNLSDIR = $(DESTDIR)/usr/share/locale
MSGMERGE = intltool-update -x --gettext-package=$(NLSPACKAGE) --dist
NLSPACKAGE = rigo
CATALOGS = $(shell ls *.po)
FMTCATALOGS = $(patsubst %.po,%.mo,$(CATALOGS))
GTKBFILES = ../data/ui/gtk3/rigo.ui
PYFILES =  $(wildcard ../RigoDaemon/*.py) $(wildcard ../rigo/*.py) \
	$(wildcard ../rigo/models/*.py) \
	$(wildcard ../rigo/controllers/*.py) \
	$(wildcard ../rigo/ui/*.py) $(wildcard ../rigo/ui/gtk3/*.py) \
	$(wildcard ../rigo/ui/gtk3/controllers/*.py) \
	$(wildcard ../rigo/ui/gtk3/models/*.py) \
	$(wildcard ../rigo/ui/gtk3/widgets/*.py) ../rigo_app.py
POTFILES = $(PYFILES) $(GTKBFILES)

all: $(NLSPACKAGE).pot $(FMTCATALOGS)

POTFILES.in:
	for file in $(PYFILES); do \
		echo "$${file#../}" ; \
	done > $@
	for file in $(GTKBFILES); do \
		echo "[type: gettext/glade]$${file#../}" ; \
	done >> $@

$(NLSPACKAGE).pot: $(POTFILES) POTFILES.in
	intltool-update --gettext-package=$(NLSPACKAGE) --pot

transifex-pull:
	tx pull -a -f

transifex-push:
	tx push -s

validate:
	catalogs='$(CATALOGS)'; \
	for cat in $$catalogs; do \
		lang=`basename $$cat .po`; \
		msgfmt -c $$lang.po -o /dev/null || exit 1; \
	done

update-po: Makefile $(NLSPACKAGE).pot transifex-pull

refresh-po: Makefile POTFILES.in
	catalogs='$(CATALOGS)'; \
	for cat in $$catalogs; do \
		lang=`basename $$cat .po`; \
		cp $$lang.po $$lang.old.po; \
		if $(MSGMERGE) $$lang ; then \
			rm -f $$lang.old.po ; \
			echo "$(MSGMERGE) of $$lang succeeded" ; \
		else \
			echo "$(MSGMERGE) of $$lang failed" ; \
			mv $$lang.old.po $$lang.po ; \
		fi \
	done

report:
	@for cat in *.po ; do \
		echo -n "$$cat: "; \
		msgfmt --statistics -o /dev/null $$cat; \
	done

clean:
	@rm -fv *mo *~ .depend *.autosave

distclean: clean
	rm -f *mo .depend Makefile $(NLSPACKAGE).pot POTFILES.in

depend:

install: all
	mkdir -p $(INSTALLNLSDIR)
	for n in $(CATALOGS); do \
	    l=`basename $$n .po`; \
	    mo=$$l.mo; \
	    if [ ! -f $$mo ]; then continue; fi; \
	    $(INSTALL) -m 755 -d $(INSTALLNLSDIR)/$$l; \
	    $(INSTALL) -m 755 -d $(INSTALLNLSDIR)/$$l/LC_MESSAGES; \
	    $(INSTALL) -m 644 $$mo \
		$(INSTALLNLSDIR)/$$l/LC_MESSAGES/$(NLSPACKAGE).mo; \
	done

%.mo: %.po
	msgfmt -o $@ $<
