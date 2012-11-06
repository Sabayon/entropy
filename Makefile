PKGNAME = entropy
PYTHON = python2
SUBDIRS = lib client server magneto
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
VARDIR = /var
DESTDIR = 

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done

install: all
	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done
