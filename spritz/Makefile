SUBDIRS = src po src/yumgui 
PYFILES = $(wildcard *.py)
PKGNAME = yumex
VERSION=$(shell awk '/Version:/ { print $$2 }' ${PKGNAME}.spec)
PYTHON=python
SRCDIR=src
MISCDIR=misc
PIXDIR=gfx
ALLDIRS=src po src/yumgui gfx misc tools

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
	@rm -rf ${PKGNAME}-${VERSION}.tar.gz
	@git-archive --format=tar --prefix=$(PKGNAME)-$(VERSION)/ HEAD | gzip -9v >${PKGNAME}-$(VERSION).tar.gz
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
	@git log --pretty --numstat --summary | tools/git2cl > ChangeLog.git
	@cat ChangeLog.git ChangeLog.svn > ChangeLog
	@rm ChangeLog.git
	
upload: FORCE
	@scp ~/rpmbuild/SOURCES/${PKGNAME}-${VERSION}.tar.gz yum-extender.org:public_html/dnl/yumex/source/.
    
	
release:
	@git commit -a -m "bumped version to $(VERSION)"
	@$(MAKE) changelog
	@git commit -a -m "updated ChangeLog"
	@git push
	@git tag ${PKGNAME}-${VERSION} -m "Added ${PKGNAME}-${VERSION} release tag"
	@git push --tags origin

FORCE:
    
