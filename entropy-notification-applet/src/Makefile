PYTHON=python
PACKAGE = $(shell basename `pwd`)
PYFILES = $(wildcard *.py)
PKGDIR = /$(LIBDIR)/entropy/spritz/applet

all: 
	echo "Nothing to do"

clean:
	rm -f *.pyc *.pyo *~

install:
	mkdir -p $(DESTDIR)/$(PKGDIR)
	for p in $(PYFILES) ; do \
		install -m 755 $$p $(DESTDIR)/$(PKGDIR)/$$p; \
	done
	install -m 644 *.glade $(DESTDIR)/$(PKGDIR)
