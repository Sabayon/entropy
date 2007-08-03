SUBDIRS = src po src/yumgui 
PYFILES = $(wildcard *.py)
PKGNAME = yumex
VERSION=$(shell awk '/Version:/ { print $$2 }' ${PKGNAME}.spec)
PYTHON=python
SRCDIR=src
MISCDIR=misc
PIXDIR=gfx

all: subdirs
	
subdirs:
	for d in $(SUBDIRS); do make -C $$d; [ $$? = 0 ] || exit 1 ; done

clean:
	@rm -fv *~ *.tar.gz *.list *.lang
	for d in $(SUBDIRS); do make -C $$d clean ; done

install:
	mkdir -p $(DESTDIR)/usr/share/yumex
	mkdir -p $(DESTDIR)/usr/share/pixmaps/yumex
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/etc
	mkdir -p $(DESTDIR)/etc/pam.d
	mkdir -p $(DESTDIR)/etc/security/console.apps
	install -m644 COPYING $(DESTDIR)/usr/share/yumex/.
	install -m755 $(MISCDIR)/yumex $(DESTDIR)/usr/share/yumex/.
	install -m644 $(PIXDIR)/*.png $(DESTDIR)/usr/share/pixmaps/yumex/.
	install -m644 $(MISCDIR)/yumex.profiles.conf $(DESTDIR)/etc/.
	install -m644 $(MISCDIR)/yumex.pam $(DESTDIR)/etc/pam.d/yumex
	install -m600 $(MISCDIR)/yumex.conf.default $(DESTDIR)/etc/yumex.conf
	install -m644 $(MISCDIR)/yumex.pam $(DESTDIR)/etc/pam.d/yumex
	install -m644 $(MISCDIR)/yumex.console.app $(DESTDIR)/etc/security/console.apps/yumex
	ln -s consolehelper $(DESTDIR)/usr/bin/yumex
	chmod +x $(DESTDIR)/usr/share/yumex/yumex
	install -m644 $(MISCDIR)/yumex.desktop $(DESTDIR)/usr/share/applications/.
	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done


archive:

	rm -rf ${PKGNAME}-${VERSION}.tar.gz
	rm -rf /tmp/${PKGNAME}-$(VERSION) /tmp/${PKGNAME}
	@dir=$$PWD; cd /tmp; cp -a "$$dir" ${PKGNAME}
	@mv /tmp/${PKGNAME} /tmp/${PKGNAME}-$(VERSION)
	@dir=$$PWD; cd /tmp; tar cvzf "$$dir/${PKGNAME}-$(VERSION).tar.gz" ${PKGNAME}-$(VERSION)
	@rm -rf /tmp/${PKGNAME}-$(VERSION)	
	@cp ${PKGNAME}-$(VERSION).tar.gz $(shell rpm -E '%_sourcedir')
	@rm -rf ${PKGNAME}-${VERSION}.tar.gz
	@echo "The archive is in ${PKGNAME}-$(VERSION).tar.gz"

rpm-centos5: 
	rpmbuild -ba -D "dist .centos5" yumex.spec	

rpm-fc6: 
	rpmbuild -ba -D "dist .fc6" yumex.spec	

rpm-fc7: 
	rpmbuild -ba -D "dist .fc7" yumex.spec	

changelog:
	@svn2cl -r HEAD:66 --group-by-day --strip-prefix=trunk/yumex --authors=authors.xml --break-before-msg -f ChangeLog
	
upload:
	
release:
	@svn commit -m "bumped version to $(VERSION)"
	@$(MAKE) changelog
	@svn commit -m "updated ChangeLog"
	
