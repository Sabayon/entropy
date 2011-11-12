EITVER = 1.0
PREFIX = /usr
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib
DESTDIR = 

all:
	if [ ! -d man ]; then mkdir man; fi
	for man_name in mansrc/*.1.txt; do \
		a2x --attribute="eitversion=$(EITVER)" --format=manpage \
		-D man/ $$man_name; \
	done

update-doc:
	./generate

install:
	mkdir -p $(DESTDIR)$(PREFIX)/share/man/man1
	install -m 644 man/* $(DESTDIR)$(PREFIX)/share/man/man1/

clean:
