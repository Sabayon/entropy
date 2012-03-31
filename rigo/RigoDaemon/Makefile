SUBDIRS = dbus polkit
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
DESTDIR = 

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	install -d $(DESTDIR)$(LIBDIR)/rigo/RigoDaemon
	install -m 644 $(wildcard *.py) $(DESTDIR)$(LIBDIR)/rigo/RigoDaemon/
	install -m 755 app.py $(DESTDIR)$(LIBDIR)/rigo/RigoDaemon/
	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
