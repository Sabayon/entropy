PKGDIR = /usr/share/yumex

all: 
	@../tools/py-compile *.py 

clean:
	rm -fv *.pyc *.pyo *~ *.bak *.gladep
	rm -fv yumex/*.pyc yumex/*.pyo yumex/*~ 
	rm -fv yumgui/*.pyc yumgui/*.pyo yumgui/*~ 

install:
	mkdir -p $(DESTDIR)/usr/share/yumex
	mkdir -p $(DESTDIR)/usr/share/yumex
	install -m755 *.pyc $(DESTDIR)/$(PKGDIR)/.
	install -m755 *.py $(DESTDIR)/$(PKGDIR)/.
	install -m644 yumex.glade $(DESTDIR)/$(PKGDIR)/.
