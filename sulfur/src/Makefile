PKGDIR = /$(LIBDIR)/entropy/sulfur/sulfur

all:

clean:
	rm -fv sulfur/*.pyc sulfur/*.pyo sulfur/*~ sulfur/*.bak sulfur/*.gladep
	rm -fv sulfur/etpgui/*.pyc sulfur/etpgui/*.pyo sulfur/etpgui/*~ 

install:
	mkdir -p $(DESTDIR)/$(PKGDIR)/etpgui
	install -m755 *.py $(DESTDIR)/$(PKGDIR)/..
	install -m644 sulfur/*.py $(DESTDIR)/$(PKGDIR)/.
	install -m644 sulfur/*.glade $(DESTDIR)/$(PKGDIR)/.
	install -m644 sulfur/etpgui/*.py $(DESTDIR)/$(PKGDIR)/etpgui/.
