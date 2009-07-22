INSTALL= /usr/bin/install -c
INSTALL_PROGRAM= ${INSTALL}
INSTALL_DATA= ${INSTALL} -m 644
INSTALLNLSDIR=$(DESTDIR)/usr/share/locale
top_srcdir = "."


MSGMERGE = intltool-update -x --gettext-package=$(NLSPACKAGE) --dist

NLSPACKAGE = entropy

CATALOGS = $(shell ls *.po)
FMTCATALOGS = $(patsubst %.po,%.mo,$(CATALOGS))

GLADEFILES = $(wildcard ../../sulfur/src/sulfur/*.glade) $(wildcard ../../magneto/src/magneto/gtk/*.glade)
PYFILES  = $(wildcard ../../libraries/entropy/services/system/*.py) $(wildcard ../../libraries/entropy/services/ugc/*.py) $(wildcard ../../libraries/entropy/services/repository/*.py) $(wildcard ../../libraries/entropy/services/*.py) $(wildcard ../../libraries/entropy/server/*.py) $(wildcard ../../libraries/entropy/server/interfaces/*.py) $(wildcard ../../libraries/entropy/client/services/ugc/*.py) $(wildcard ../../libraries/entropy/client/services/system/*.py) $(wildcard ../../libraries/entropy/client/services/*.py) $(wildcard ../../libraries/entropy/client/*.py) $(wildcard ../../libraries/entropy/client/interfaces/*.py) $(wildcard ../../libraries/entropy/*.py) $(wildcard ../../libraries/*.py) $(wildcard ../../client/*.py) $(wildcard ../../server/*.py) $(wildcard ../../sulfur/src/*.py) $(wildcard ../../sulfur/src/sulfur/*.py) $(wildcard ../../magneto/src/magneto/kde/*.py) $(wildcard ../../magneto/src/magneto/gtk/*.py)
POTFILES  = $(PYFILES) $(GLADEFILES)

all: $(NLSPACKAGE).pot $(FMTCATALOGS)

POTFILES.in:
	for file in $(POTFILES); do \
		echo "$${file#../}" ; \
	done > $@

$(NLSPACKAGE).pot: $(POTFILES) POTFILES.in
	intltool-update --gettext-package=$(NLSPACKAGE) --pot

update-po: Makefile $(NLSPACKAGE).pot refresh-po

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
	mkdir -p $(PREFIX)/$(INSTALLNLSDIR)
	for n in $(CATALOGS); do \
	    l=`basename $$n .po`; \
	    mo=$$l.mo; \
	    if [ ! -f $$mo ]; then continue; fi; \
	    $(INSTALL) -m 755 -d /$(PREFIX)/$(INSTALLNLSDIR)/$$l; \
	    $(INSTALL) -m 755 -d /$(PREFIX)/$(INSTALLNLSDIR)/$$l/LC_MESSAGES; \
	    $(INSTALL) -m 644 $$mo \
		/$(PREFIX)/$(INSTALLNLSDIR)/$$l/LC_MESSAGES/$(NLSPACKAGE).mo; \
	done

%.mo: %.po
	msgfmt -o $@ $<
