SUBDIRS = dbus polkit
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
PYTHON_SITEDIR = $(LIBDIR)
LIBEXECDIR = $(PREFIX)/libexec
DESTDIR = 

all:
	for d in $(SUBDIRS); do $(MAKE) -C $$d; done

install:
	install -d $(DESTDIR)$(LIBEXECDIR)
	install -d $(DESTDIR)$(PYTHON_SITEDIR)/rigo/RigoDaemon
	install -m 644 $(wildcard *.py) $(DESTDIR)$(PYTHON_SITEDIR)/rigo/RigoDaemon/
	install -m 755 app/RigoDaemon_app.py $(DESTDIR)$(LIBEXECDIR)/
	for d in $(SUBDIRS); do $(MAKE) -C $$d install; done

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
