PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
DESTDIR = 

all:

install:
	install -d $(DESTDIR)$(PREFIX)/share/polkit-1/actions
	install -m 644 org.sabayon.RigoDaemon.policy $(DESTDIR)$(PREFIX)/share/polkit-1/actions/

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
