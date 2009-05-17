PYTHON=python
PACKAGE = $(shell basename `pwd`)
PYFILES = $(wildcard *.py)
PKGDIR = /$(LIBDIR)/entropy/spritz/etpgui

all: 

clean:
	rm -f *.pyc *.pyo *~

install:
	mkdir -p $(DESTDIR)/$(PKGDIR)
	for p in $(PYFILES) ; do \
		install -m 755 $$p $(DESTDIR)/$(PKGDIR)/$$p; \
	done
