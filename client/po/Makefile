DESTDIR = 
INSTALL = /usr/bin/install -c
INSTALL_PROGRAM = ${INSTALL}
INSTALL_DATA = ${INSTALL} -m 644
INSTALLNLSDIR = $(DESTDIR)/usr/share/locale
top_srcdir = "."
MSGMERGE = intltool-update -x --gettext-package=$(NLSPACKAGE) --dist
NLSPACKAGE = entropy
CATALOGS = $(shell ls *.po)
FMTCATALOGS = $(patsubst %.po,%.mo,$(CATALOGS))
GLADEFILES = $(wildcard ../../magneto/src/magneto/gtk/*.glade)
PYFILES = $(wildcard ../../lib/entropy/db/*.py) \
	$(wildcard ../../lib/entropy/core/*.py) \
	$(wildcard ../../lib/entropy/core/settings/*.py) \
	$(wildcard ../../lib/entropy/core/settings/plugins/*.py) \
	$(wildcard ../../lib/entropy/core/settings/plugins/interfaces/*.py) \
	$(wildcard ../../lib/kswitch/*.py) \
	$(wildcard ../../lib/entropy/spm/*.py) \
	$(wildcard ../../lib/entropy/spm/plugins/*.py) \
	$(wildcard ../../lib/entropy/spm/plugins/portage_plugin/*.py) \
	$(wildcard ../../lib/entropy/spm/plugins/interfaces/portage_plugin/*.py) \
	$(wildcard ../../lib/entropy/spm/plugins/interfaces/*.py) \
	$(wildcard ../../lib/entropy/services/system/*.py) \
	$(wildcard ../../lib/entropy/services/ugc/*.py) \
	$(wildcard ../../lib/entropy/services/repository/*.py) \
	$(wildcard ../../lib/entropy/services/*.py) \
	$(wildcard ../../lib/entropy/client/services/ugc/*.py) \
	$(wildcard ../../lib/entropy/client/services/system/*.py) \
	$(wildcard ../../lib/entropy/client/services/*.py) \
	$(wildcard ../../lib/entropy/client/*.py) \
	$(wildcard ../../lib/entropy/client/interfaces/*.py) \
	$(wildcard ../../lib/entropy/client/interfaces/package/*.py) \
	$(wildcard ../../lib/entropy/client/interfaces/package/actions/*.py) \
	$(wildcard ../../lib/entropy/*.py) \
	$(wildcard ../../client/*.py) \
	$(wildcard ../../client/solo/*.py) \
	$(wildcard ../../client/solo/commands/*.py) \
	$(wildcard ../../magneto/src/magneto/kde/*.py) \
	$(wildcard ../../magneto/src/magneto/gtk/*.py) \
	$(wildcard ../../magneto/src/magneto/core/*.py) \
	../kernel-switcher

POTFILES = $(PYFILES) $(GLADEFILES)

all: $(NLSPACKAGE).pot $(FMTCATALOGS)

POTFILES.in:
	for file in $(POTFILES); do \
		echo "$${file#../}" ; \
	done > $@

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

install:	all
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
