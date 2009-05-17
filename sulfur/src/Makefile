PKGDIR = /$(LIBDIR)/entropy/spritz

all:

clean:
	rm -fv *.pyc *.pyo *~ *.bak *.gladep
	rm -fv etpgui/*.pyc etpgui/*.pyo etpgui/*~ 

install:
	mkdir -p $(DESTDIR)/$(LIBDIR)/entropy/spritz
	install -m755 *.py $(DESTDIR)/$(PKGDIR)/.
	install -m644 sulfur.glade $(DESTDIR)/$(PKGDIR)/.
