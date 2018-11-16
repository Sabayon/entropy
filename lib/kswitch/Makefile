PREFIX ?= /usr
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib
PYTHON_SITEDIR ?= $(LIBDIR)
DESTDIR ?= 

all:


install:
	install -d $(DESTDIR)/$(PYTHON_SITEDIR)/entropy/lib/kswitch
	install -m 644 *.py $(DESTDIR)/$(PYTHON_SITEDIR)/entropy/lib/kswitch/

clean:
