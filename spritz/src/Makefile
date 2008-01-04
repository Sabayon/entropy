PKGDIR = /usr/lib/entropy/spritz

all:
	@../tools/py-compile *.py 

clean:
	rm -fv *.pyc *.pyo *~ *.bak *.gladep
	rm -fv yumex/*.pyc yumex/*.pyo etpgui/*~ 
	rm -fv etpgui/*.pyc etpgui/*.pyo etpgui/*~ 

install:
	mkdir -p $(DESTDIR)/usr/lib/entropy/spritz
	mkdir -p $(DESTDIR)/usr/lib/entropy/spritz
	install -m755 *.pyc $(DESTDIR)/$(PKGDIR)/.
	install -m755 *.py $(DESTDIR)/$(PKGDIR)/.
	install -m644 spritz.glade $(DESTDIR)/$(PKGDIR)/.
