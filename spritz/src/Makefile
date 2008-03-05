PKGDIR = /usr/lib/entropy/spritz

all:
	@../tools/py-compile *.py 

clean:
	rm -fv *.pyc *.pyo *~ *.bak *.gladep
	rm -fv etpgui/*.pyc etpgui/*.pyo etpgui/*~ 
	rm -fv applet/*.pyc etpgui/*.pyo applet/*~ 

install:
	mkdir -p $(DESTDIR)/usr/lib/entropy/spritz
	install -m755 *.py $(DESTDIR)/$(PKGDIR)/.
	install -m644 spritz.glade $(DESTDIR)/$(PKGDIR)/.
