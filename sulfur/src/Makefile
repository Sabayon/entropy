PKGDIR = /$(LIBDIR)/entropy/sulfur/sulfur

all:

clean:
	rm -fv sulfur/*.pyc sulfur/*.pyo sulfur/*~ sulfur/*.bak sulfur/*.gladep

install:
	mkdir -p $(DESTDIR)/$(PKGDIR)
	install -m755 *.py $(DESTDIR)/$(PKGDIR)/..
	install -m644 sulfur/*.py $(DESTDIR)/$(PKGDIR)/.
	install -m644 sulfur/*.glade $(DESTDIR)/$(PKGDIR)/.
