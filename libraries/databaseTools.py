#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy Database Interface

    Copyright (C) 2007 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

# Never do "import portage" here, please use entropyTools binding
# EXIT STATUSES: 300-399

from entropyConstants import *
import entropyTools
from outputTools import *
from pysqlite2 import dbapi2 as sqlite
import os
import sys
import string

# Logging initialization
import logTools
dbLog = logTools.LogFile(level = etpConst['databaseloglevel'],filename = etpConst['databaselogfile'], header = "[DBase]")


def database(options):

    import activatorTools
    import reagentTools
    import mirrorTools

    databaseRequestNoAsk = False
    _options = []
    for opt in options:
	if opt.startswith("--noask"):
	    databaseRequestNoAsk = True
	else:
	    _options.append(opt)
    options = _options

    if len(options) == 0:
	print_error(yellow(" * ")+red("Not enough parameters"))
	sys.exit(301)

    if (options[0] == "--initialize"):
	
	# do some check, print some warnings
	print_info(green(" * ")+red("Initializing Entropy database..."), back = True)
        # database file: etpConst['etpdatabasefilepath']
	revisionsMatch = {}
        if os.path.isfile(etpConst['etpdatabasefilepath']):
	    try:
		dbconn = etpDatabase(readOnly = True, noUpload = True)
		idpackages = dbconn.listAllIdpackages()
		for idpackage in idpackages:
		    package = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
		    branch = dbconn.retrieveBranch(idpackage)
		    revision = dbconn.retrieveRevision(idpackage)
		    revisionsMatch[package] = [branch,revision]
		dbconn.closeDB()
	    except:
		pass
	    print_info(red(" * ")+bold("WARNING")+red(": database file already exists. Overwriting."))
	    rc = entropyTools.askquestion("\n     Do you want to continue ?")
	    if rc == "No":
	        sys.exit(0)
	    os.remove(etpConst['etpdatabasefilepath'])

	revisionsMatch = {u'm4-1.4.10.tbz2': [u'unstable', 0], u'gst-plugins-esd-0.10.6.tbz2': [u'unstable', 0], u'toolame-02l-r2.tbz2': [u'unstable', 1], u'myspell-fr-20060316.tbz2': [u'unstable', 1], u'ebdftopcf-2.tbz2': [u'unstable', 1], u'dvdauthor-0.6.14.tbz2': [u'unstable', 1], u'pgpdump-0.24.tbz2': [u'unstable', 1], u'aspell-ro-0.50.2.tbz2': [u'unstable', 1], u'torcs-1.3.0.tbz2': [u'unstable', 1], u'sabayonlive-tools-1.6.1.tbz2': [u'unstable', 0], u'alsa-plugins-1.0.14.tbz2': [u'unstable', 0], u'libcaca-0.99_beta11.tbz2': [u'unstable', 1], u'kverbos-3.5.7.tbz2': [u'unstable', 1], u'kate-plugins-3.5.7.tbz2': [u'unstable', 1], u'slmodem-2.9.11_pre20070505-t2.6.22_sabayon.tbz2': [u'unstable', 0], u'aspell-es-0.50.2.tbz2': [u'unstable', 1], u'dmapi-2.2.8.tbz2': [u'unstable', 0], u'amsn-0.97_rc1.tbz2': [u'unstable', 0], u'xf86-video-chips-1.1.1.tbz2': [u'unstable', 1], u'linux-wlan-ng-utils-0.2.2.tbz2': [u'unstable', 1], u'irssi-0.8.12_rc1.tbz2': [u'unstable', 0], u'fribidi-0.10.7.tbz2': [u'unstable', 1], u'kteatime-3.5.7.tbz2': [u'unstable', 1], u'aspell-cy-0.50.3.tbz2': [u'unstable', 1], u'celementtree-1.0.5-r1.tbz2': [u'unstable', 0], u'extutils-parsexs-2.18.tbz2': [u'unstable', 1], u'sdl-mixer-1.2.8.tbz2': [u'unstable', 0], u'synce-libsynce-0.9.1.tbz2': [u'unstable', 1], u'gdm-2.18.4.tbz2': [u'unstable', 0], u'safe-browsing-helpers-1.0.1.tbz2': [u'unstable', 1], u'xkbutils-1.0.1.tbz2': [u'unstable', 1], u'at-spi-1.18.1-r1.tbz2': [u'unstable', 0], u'xf86-video-tdfx-1.3.0.tbz2': [u'unstable', 1], u'gst-plugins-good-0.10.6.tbz2': [u'unstable', 0], u'neon-0.26.3.tbz2': [u'unstable', 0], u'uw-mailutils-2004g.tbz2': [u'unstable', 1], u'klatin-3.5.7.tbz2': [u'unstable', 1], u'transcode-1.0.4_rc6.tbz2': [u'unstable', 0], u'ksokoban-3.5.7.tbz2': [u'unstable', 1], u'log4j-1.2.14-r1.tbz2': [u'unstable', 1], u'sauerbraten-2007.08.19.tbz2': [u'unstable', 0], u'genkernel-3.4.9_pre2.tbz2': [u'unstable', 0], u'kturtle-3.5.7.tbz2': [u'unstable', 1], u'XML-XQL-0.68.tbz2': [u'unstable', 1], u'googleearth-4.tbz2': [u'unstable', 1], u'konsolekalendar-3.5.7.tbz2': [u'unstable', 1], u'gob-2.0.14.tbz2': [u'unstable', 1], u'gnome-panel-2.18.3.tbz2': [u'unstable', 0], u'lxml-1.3.4.tbz2': [u'unstable', 0], u'binutils-config-1.9-r4.tbz2': [u'unstable', 0], u'ktalkd-3.5.7.tbz2': [u'unstable', 1], u'libdvdnav-0.1.10.tbz2': [u'unstable', 1], u'dos2unix-3.1-r2.tbz2': [u'unstable', 0], u'aspell-el-0.50.3.tbz2': [u'unstable', 1], u'font-adobe-75dpi-1.0.0.tbz2': [u'unstable', 1], u'glade-sharp-2.10.0.tbz2': [u'unstable', 2], u'Heap-0.80.tbz2': [u'unstable', 0], u'xf86-input-citron-2.2.1.tbz2': [u'unstable', 0], u'Time-Local-1.17.tbz2': [u'unstable', 1], u'font-bitstream-75dpi-1.0.0.tbz2': [u'unstable', 1], u'gawk-3.1.5-r5.tbz2': [u'unstable', 0], u'aspell-0.60.5.tbz2': [u'unstable', 1], u'kdepim-meta-3.5.7.tbz2': [u'unstable', 1], u'system-tools-backends-2.2.1-r2.tbz2': [u'unstable', 1], u'ipw2200-firmware-3.0.tbz2': [u'unstable', 3], u'pwlib-1.10.7.tbz2': [u'unstable', 1], u'kpovmodeler-3.5.7.tbz2': [u'unstable', 1], u'tor-0.1.2.17.tbz2': [u'unstable', 0], u'speech-tools-1.2.96_beta.tbz2': [u'unstable', 1], u'Text-WrapI18N-0.06.tbz2': [u'unstable', 1], u'libintl-perl-1.16.tbz2': [u'unstable', 1], u'commons-lang-2.3.tbz2': [u'unstable', 0], u'font-bh-lucidatypewriter-100dpi-1.0.0.tbz2': [u'unstable', 1], u'vim-core-7.1.087.tbz2': [u'unstable', 0], u'renamedlg-audio-3.5.7.tbz2': [u'unstable', 1], u'nautilus-cd-burner-2.18.2.tbz2': [u'unstable', 0], u'libvisual-plugins-0.2.0.tbz2': [u'unstable', 1], u'python-fchksum-1.7.1.tbz2': [u'unstable', 1], u'docbook-xml-dtd-4.5.tbz2': [u'unstable', 2], u'kaudiocreator-3.5.7.tbz2': [u'unstable', 1], u'IO-stringy-2.110.tbz2': [u'unstable', 1], u'kamera-3.5.7.tbz2': [u'unstable', 1], u'libgphoto2-2.3.1-r5.tbz2': [u'unstable', 0], u'perl-Sys-Syslog-0.18.tbz2': [u'unstable', 1], u'module-init-tools-3.2.2-r3.tbz2': [u'unstable', 1], u'kpercentage-3.5.7.tbz2': [u'unstable', 1], u'kmahjongg-3.5.7.tbz2': [u'unstable', 1], u'dialog-1.1.20070704.tbz2': [u'unstable', 0], u'xf86-video-sis-0.9.3.tbz2': [u'unstable', 1], u'virtualbox-bin-1.5.0.tbz2': [u'unstable', 0], u'gnome-mount-0.6.tbz2': [u'unstable', 1], u'obexftp-0.22_rc7.tbz2': [u'unstable', 0], u'xf86-video-cirrus-1.1.0.tbz2': [u'unstable', 1], u'opencdk-0.6.4.tbz2': [u'unstable', 0], u'man-1.6e-r3.tbz2': [u'unstable', 1], u'gspcav1-20070508-t2.6.22_sabayon.tbz2': [u'unstable', 1], u'flightgear-0.9.10.tbz2': [u'unstable', 1], u'privoxy-3.0.6.tbz2': [u'unstable', 1], u'recode-3.6-r2.tbz2': [u'unstable', 1], u'xalan-serializer-2.7.0.tbz2': [u'unstable', 0], u'kasteroids-3.5.7.tbz2': [u'unstable', 1], u'emul-linux-x86-sdl-10.1.tbz2': [u'unstable', 1], u'unshield-0.5-r1.tbz2': [u'unstable', 1], u'madwifi-ng-tools-0.9.3.2.tbz2': [u'unstable', 0], u'glitz-0.5.6.tbz2': [u'unstable', 1], u'art-sharp-2.16.0.tbz2': [u'unstable', 1], u'hal-0.5.9.1-r7.tbz2': [u'unstable', 1], u'libxml-1.8.17-r2.tbz2': [u'unstable', 1], u'libdc1394-1.2.1.tbz2': [u'unstable', 1], u'dbus-qt3-old-0.70.tbz2': [u'unstable', 1], u'extutils-depends-0.205.tbz2': [u'unstable', 1], u'gst-plugins-libpng-0.10.6.tbz2': [u'unstable', 0], u'eel-2.18.3.tbz2': [u'unstable', 0], u'compositeproto-0.4.tbz2': [u'unstable', 0], u'bsh-2.0_beta4-r3.tbz2': [u'unstable', 0], u'xf86-video-ark-0.6.0.tbz2': [u'unstable', 1], u'libstdc++-3.3.tbz2': [u'unstable', 1], u'libaal-1.0.5.tbz2': [u'unstable', 1], u'kruler-3.5.7.tbz2': [u'unstable', 1], u'hping-2.0.0_rc3-r1.tbz2': [u'unstable', 1], u'xterm-229.tbz2': [u'unstable', 0], u'gpm-1.20.1-r6.tbz2': [u'unstable', 0], u'kimagemapeditor-3.5.7.tbz2': [u'unstable', 1], u'xf86-input-aiptek-1.0.1.tbz2': [u'unstable', 1], u'perl-Storable-2.16.tbz2': [u'unstable', 1], u'apr-util-0.9.12-r1.tbz2': [u'unstable', 1], u'gjdoc-0.7.8.tbz2': [u'unstable', 1], u'smartmontools-5.37.tbz2': [u'unstable', 1], u'secondlife-bin-1.18.0.6.tbz2': [u'unstable', 1], u'perl-5.8.8-r2.tbz2': [u'unstable', 1], u'gconf-editor-2.18.2.tbz2': [u'unstable', 0], u'kdewebdev-meta-3.5.7.tbz2': [u'unstable', 1], u'ccrtp-1.5.1.tbz2': [u'unstable', 0], u'webapp-config-1.50.16-r2.tbz2': [u'unstable', 0], u'kontact-3.5.7-r1.tbz2': [u'unstable', 0], u'aspell-pt-0.50.2.tbz2': [u'unstable', 1], u'libX11-1.1.3.tbz2': [u'unstable', 0], u'kdemultimedia-kioslaves-3.5.7.tbz2': [u'unstable', 1], u'xclip-0.08-r2.tbz2': [u'unstable', 0], u'ikvm-bin-0.34.0.2.tbz2': [u'unstable', 0], u'kview-3.5.7.tbz2': [u'unstable', 1], u'sabayon-2.18.1.tbz2': [u'unstable', 1], u'gst-plugins-v4l2-0.10.6.tbz2': [u'unstable', 0], u'cracklib-2.8.10.tbz2': [u'unstable', 1], u'XML-Simple-2.18.tbz2': [u'unstable', 0], u'libassuan-1.0.2-r1.tbz2': [u'unstable', 0], u'sqlite-2.8.16-r4.tbz2': [u'unstable', 1], u'aspell-bg-0.50.0.tbz2': [u'unstable', 1], u'itk-3.3-r1.tbz2': [u'unstable', 1], u'ttf-bitstream-vera-1.10-r3.tbz2': [u'unstable', 1], u'XML-RegExp-0.03-r1.tbz2': [u'unstable', 1], u'groff-1.18.1.1.tbz2': [u'unstable', 1], u'compiz-settings-0.07.tbz2': [u'unstable', 1], u'pth-2.0.7.tbz2': [u'unstable', 1], u'kbounce-3.5.7.tbz2': [u'unstable', 1], u'airtraf-1.1.tbz2': [u'unstable', 1], u'xf86dgaproto-2.0.3.tbz2': [u'unstable', 0], u'pygtk-2.10.6.tbz2': [u'unstable', 0], u'potrace-1.7.tbz2': [u'unstable', 1], u'mimelib-3.5.7.tbz2': [u'unstable', 1], u'libXcomposite-0.4.0.tbz2': [u'unstable', 0], u'kdeprint-3.5.7.tbz2': [u'unstable', 1], u'raptor-1.4.15.tbz2': [u'unstable', 1], u'kblackbox-3.5.7.tbz2': [u'unstable', 1], u'elementtree-1.2.6-r2.tbz2': [u'unstable', 0], u'xf86-video-i740-1.1.0.tbz2': [u'unstable', 1], u'DBD-Pg-1.49.tbz2': [u'unstable', 1], u'xvid4conf-1.12.tbz2': [u'unstable', 1], u'libsynaptics-0.14.6c.tbz2': [u'unstable', 1], u'man-pages-ro-0.2.tbz2': [u'unstable', 1], u'Socket6-0.19.tbz2': [u'unstable', 1], u'xf86-video-vesa-1.3.0.tbz2': [u'unstable', 1], u'gtkglext-1.2.0.tbz2': [u'unstable', 1], u'sun-jaf-1.1.tbz2': [u'unstable', 1], u'jdk-1.6.0.tbz2': [u'unstable', 1], u'Scalar-List-Utils-1.19.tbz2': [u'unstable', 1], u'libgtop-2.14.9.tbz2': [u'unstable', 0], u'xcalc-1.0.2.tbz2': [u'unstable', 0], u'libxml-perl-0.08.tbz2': [u'unstable', 1], u'aspell-hr-0.51.0.tbz2': [u'unstable', 1], u'grub-0.97-r12.tbz2': [u'unstable', 0], u'virtinst-0.300.0.tbz2': [u'unstable', 0], u'mpfr-2.2.1_p5.tbz2': [u'unstable', 1], u'freetype-2.3.5-r1.tbz2': [u'unstable', 0], u'gnome-system-tools-2.18.0.tbz2': [u'unstable', 1], u'libXTrap-1.0.0.tbz2': [u'unstable', 1], u'ktron-3.5.7.tbz2': [u'unstable', 1], u'libdmx-1.0.2.tbz2': [u'unstable', 1], u'kaboodle-3.5.7.tbz2': [u'unstable', 1], u'font-bh-ttf-1.0.0.tbz2': [u'unstable', 1], u'libpqxx-2.6.9.tbz2': [u'unstable', 0], u'pycairo-1.4.0.tbz2': [u'unstable', 1], u'font-mutt-misc-1.0.0.tbz2': [u'unstable', 1], u'Pod-Escapes-1.04.tbz2': [u'unstable', 1], u'kbattleship-3.5.7.tbz2': [u'unstable', 1], u'xplc-0.3.13-r1.tbz2': [u'unstable', 1], u're2c-0.12.0.tbz2': [u'unstable', 0], u'faad2-2.0-r13.tbz2': [u'unstable', 1], u'chkrootkit-0.47.tbz2': [u'unstable', 1], u'bluez-firmware-1.2.tbz2': [u'unstable', 1], u'XML-Writer-0.603.tbz2': [u'unstable', 0], u'libkcal-3.5.7-r1.tbz2': [u'unstable', 0], u'liboil-0.3.12.tbz2': [u'unstable', 0], u'fltk-1.1.7-r2.tbz2': [u'unstable', 0], u'bcm43xx-firmware-4319-r1.tbz2': [u'unstable', 1], u'multipath-tools-0.4.7-r2.tbz2': [u'unstable', 0], u'kcoloredit-3.5.7.tbz2': [u'unstable', 1], u'evolution-data-server-1.10.3.1.tbz2': [u'unstable', 0], u'savage-bin-2.00e.tbz2': [u'unstable', 1], u'lm_sensors-2.10.4.tbz2': [u'unstable', 0], u'netkit-talk-0.17-r4.tbz2': [u'unstable', 1], u'gentoo-syntax-20070506.tbz2': [u'unstable', 0], u'realplayer-10.0.9.tbz2': [u'unstable', 0], u'klettres-3.5.7.tbz2': [u'unstable', 1], u'pcsc-lite-1.4.4.tbz2': [u'unstable', 0], u'DB_File-1.815.tbz2': [u'unstable', 1], u'plotutils-2.4.1-r4.tbz2': [u'unstable', 0], u'pam_userdb-0.99.8.1.tbz2': [u'unstable', 0], u'iproute2-2.6.22.20070710.tbz2': [u'unstable', 0], u'aspell-fr-0.60.tbz2': [u'unstable', 0], u'perl-ldap-0.34.tbz2': [u'unstable', 1], u'xinput-1.2.tbz2': [u'unstable', 1], u'gnome-power-manager-2.18.3.tbz2': [u'unstable', 1], u'tetex-3.0_p1-r4.tbz2': [u'unstable', 0], u'flex-2.5.33-r3.tbz2': [u'unstable', 0], u'pycrash-0.4_pre3.tbz2': [u'unstable', 1], u'libkholidays-3.5.7.tbz2': [u'unstable', 1], u'gtk-engines-qt-0.7_p20070327-r2.tbz2': [u'unstable', 1], u'module-rebuild-0.5.tbz2': [u'unstable', 1], u'xalan-2.7.0-r4.tbz2': [u'unstable', 0], u'opengl-7.0.tbz2': [u'unstable', 1], u'xdpyinfo-1.0.2.tbz2': [u'unstable', 1], u'gtk2-gladexml-1.006.tbz2': [u'unstable', 1], u'hugin-0.6.1.tbz2': [u'unstable', 1], u'dev86-0.16.17-r3.tbz2': [u'unstable', 0], u'pam_krb5-20030601-r1.tbz2': [u'unstable', 1], u'man-pages-fr-2.39.0.tbz2': [u'unstable', 1], u'pam_require-0.6.tbz2': [u'unstable', 1], u'layman-1.0.99.tbz2': [u'unstable', 1], u'hspell-1.0-r1.tbz2': [u'unstable', 1], u'faac-1.25.tbz2': [u'unstable', 1], u'kmousetool-3.5.7.tbz2': [u'unstable', 1], u'intltool-0.35.5.tbz2': [u'unstable', 1], u'commons-logging-1.1-r2.tbz2': [u'unstable', 1], u'recordproto-1.13.2.tbz2': [u'unstable', 1], u'libbonoboui-2.18.0.tbz2': [u'unstable', 1], u'xf86-input-palmax-1.1.0.tbz2': [u'unstable', 1], u'libdvdplay-1.0.1.tbz2': [u'unstable', 1], u'kolf-3.5.7.tbz2': [u'unstable', 1], u'ftp-0.17-r6.tbz2': [u'unstable', 1], u'kodo-3.5.7.tbz2': [u'unstable', 1], u'mdadm-2.6.3.tbz2': [u'unstable', 0], u'PyQt-3.17.3.tbz2': [u'unstable', 0], u'bluez-libs-3.18.tbz2': [u'unstable', 0], u'orbit-2.14.8-r3.tbz2': [u'unstable', 2], u'poppler-0.5.4-r2.tbz2': [u'unstable', 0], u'libmtp-0.2.1.tbz2': [u'unstable', 0], u'kalarm-3.5.7.tbz2': [u'unstable', 1], u'akode-2.0.2.tbz2': [u'unstable', 1], u'tcp-wrappers-7.6-r8.tbz2': [u'unstable', 1], u'fontcacheproto-0.1.2.tbz2': [u'unstable', 1], u'pam_ssh-1.92.tbz2': [u'unstable', 1], u'bigreqsproto-1.0.2.tbz2': [u'unstable', 1], u'kdeaccessibility-iconthemes-3.5.7.tbz2': [u'unstable', 1], u'font-xfree86-type1-1.0.0.tbz2': [u'unstable', 1], u'XML-LibXML-1.63.tbz2': [u'unstable', 1], u'dasher-4.4.2.tbz2': [u'unstable', 0], u'esearch-0.7.1-r4.tbz2': [u'unstable', 1], u'a2ps-4.13c-r5.tbz2': [u'unstable', 1], u'ksplash-engine-moodin-0.4.2.tbz2': [u'unstable', 1], u'xf86-video-nv-2.1.3.tbz2': [u'unstable', 0], u'm2crypto-0.18.tbz2': [u'unstable', 0], u'scrollkeeper-0.3.14-r2.tbz2': [u'unstable', 1], u'xsane-0.994.tbz2': [u'unstable', 1], u'acx-firmware-20060207.tbz2': [u'unstable', 1], u'ctypes-1.0.2.tbz2': [u'unstable', 0], u'jdk-1.4.2.tbz2': [u'unstable', 1], u'kdict-3.5.7.tbz2': [u'unstable', 1], u'konsole-3.5.7.tbz2': [u'unstable', 1], u'kmid-3.5.7.tbz2': [u'unstable', 1], u'MailTools-1.77.tbz2': [u'unstable', 0], u'kmyfirewall-1.0.1-r1.tbz2': [u'unstable', 1], u'bison-2.3.tbz2': [u'unstable', 1], u'libxslt-1.1.20-r1.tbz2': [u'unstable', 0], u'xlsfonts-1.0.2.tbz2': [u'unstable', 1], u'Louie-1.1.tbz2': [u'unstable', 1], u'libkexiv2-0.1.5.tbz2': [u'unstable', 0], u'synaptics-0.14.6.tbz2': [u'unstable', 1], u'xmag-1.0.2.tbz2': [u'unstable', 0], u'xf86-input-dmc-1.1.1.tbz2': [u'unstable', 0], u'font-schumacher-misc-1.0.0.tbz2': [u'unstable', 1], u'amd64codecs-20061203.tbz2': [u'unstable', 1], u'ksirtet-3.5.7.tbz2': [u'unstable', 1], u'iwlwifi-ucode-2.14.3.tbz2': [u'unstable', 1], u'pam_ssh_agent-0.2-r1.tbz2': [u'unstable', 1], u'IP-Country-2.23.tbz2': [u'unstable', 1], u'ktux-3.5.7.tbz2': [u'unstable', 1], u'kdebase-startkde-3.5.7.tbz2': [u'unstable', 1], u'emul-linux-x86-soundlibs-10.0-r1.tbz2': [u'unstable', 1], u'mjpegtools-1.9.0_rc2.tbz2': [u'unstable', 1], u'libXxf86dga-1.0.2.tbz2': [u'unstable', 0], u'sip-4.7.tbz2': [u'unstable', 0], u'kaffeine-0.8.5.tbz2': [u'unstable', 0], u'aspell-it-2.2.20050523.tbz2': [u'unstable', 1], u'Digest-SHA-5.45.tbz2': [u'unstable', 0], u'libSM-1.0.3.tbz2': [u'unstable', 0], u'pstoedit-3.44.tbz2': [u'unstable', 0], u'glut-3.7.1.tbz2': [u'unstable', 1], u'klickety-3.5.7.tbz2': [u'unstable', 1], u'xf86-video-voodoo-1.1.1.tbz2': [u'unstable', 1], u'ncurses-5.6-r2.tbz2': [u'unstable', 0], u'tcpdump-3.9.7-r1.tbz2': [u'unstable', 0], u'915resolution-0.5.3-r1.tbz2': [u'unstable', 0], u'iptraf-3.0.0-r4.tbz2': [u'unstable', 0], u'ruby-1.8.6_p36-r4.tbz2': [u'unstable', 0], u'plib-1.8.4-r1.tbz2': [u'unstable', 1], u'gnome-light-2.18.3.tbz2': [u'unstable', 0], u'kmilo-3.5.7.tbz2': [u'unstable', 1], u'kdeaddons-kfile-plugins-3.5.6-r1.tbz2': [u'unstable', 1], u'fontsproto-2.0.2.tbz2': [u'unstable', 1], u'grep-2.5.1a-r1.tbz2': [u'unstable', 1], u'kghostview-3.5.7.tbz2': [u'unstable', 1], u'kwin4-3.5.7.tbz2': [u'unstable', 1], u'khelpcenter-3.5.7.tbz2': [u'unstable', 1], u'linux-headers-2.6.22-r2.tbz2': [u'unstable', 0], u'liblockfile-1.06-r2.tbz2': [u'unstable', 1], u'perl-MIME-Base64-3.07.tbz2': [u'unstable', 1], u'libdvb-0.5.5.1-r3.tbz2': [u'unstable', 1], u'vino-2.18.1.tbz2': [u'unstable', 0], u'gst-plugins-raw1394-0.10.6.tbz2': [u'unstable', 0], u'libxkbfile-1.0.4.tbz2': [u'unstable', 1], u'ksystraycmd-3.5.5.tbz2': [u'unstable', 1], u'kdepasswd-3.5.7-r1.tbz2': [u'unstable', 0], u'docbook-xsl-stylesheets-1.73.2.tbz2': [u'unstable', 0], u'gst-plugins-faac-0.10.5.tbz2': [u'unstable', 0], u'kdetoys-meta-3.5.7.tbz2': [u'unstable', 1], u'aspell-vi-0.01.1.1.tbz2': [u'unstable', 1], u'python-ldap-2.3.1.tbz2': [u'unstable', 0], u'networkmanager-openvpn-0.3.3.tbz2': [u'unstable', 0], u'kdeedu-applnk-3.5.7.tbz2': [u'unstable', 1], u'gst-plugins-cdio-0.10.6.tbz2': [u'unstable', 0], u'gnokii-0.6.18-r1.tbz2': [u'unstable', 0], u'Digest-MD4-1.5.tbz2': [u'unstable', 1], u'Test-Number-Delta-1.03.tbz2': [u'unstable', 0], u'libdvbpsi-0.1.5.tbz2': [u'unstable', 1], u'kerry-0.2.1.tbz2': [u'unstable', 1], u'libid3tag-0.15.1b.tbz2': [u'unstable', 1], u'dcoprss-3.5.7.tbz2': [u'unstable', 1], u'iwlwifi4965-ucode-4.44.15.tbz2': [u'unstable', 1], u'kdeaddons-docs-konq-plugins-3.5.7.tbz2': [u'unstable', 1], u'gnome-nettool-2.18.0.tbz2': [u'unstable', 1], u'unix2dos-2.2.tbz2': [u'unstable', 1], u'libICE-1.0.4.tbz2': [u'unstable', 0], u'startup-notification-0.9.tbz2': [u'unstable', 0], u'netkit-rsh-0.17-r8.tbz2': [u'unstable', 1], u'aspell-sk-0.52.0.tbz2': [u'unstable', 1], u'nmap-4.20.tbz2': [u'unstable', 1], u'flac-1.1.4.tbz2': [u'unstable', 0], u'libgail-gnome-1.18.0.tbz2': [u'unstable', 1], u'corefonts-1-r4.tbz2': [u'unstable', 0], u'gst-python-0.10.8.tbz2': [u'unstable', 0], u'SGMLSpm-1.03-r5.tbz2': [u'unstable', 1], u'libical-0.26.7.tbz2': [u'unstable', 0], u'libgnomeuimm-2.18.0.tbz2': [u'unstable', 1], u'egenix-mx-base-3.0.0.tbz2': [u'unstable', 0], u'khexedit-3.5.7.tbz2': [u'unstable', 1], u'ksayit-3.5.7.tbz2': [u'unstable', 1], u'xlsatoms-1.0.1.tbz2': [u'unstable', 1], u'ladspa-cmt-1.15.tbz2': [u'unstable', 1], u'cdrdao-1.2.2.tbz2': [u'unstable', 1], u'iptables-1.3.8-r2.tbz2': [u'unstable', 0], u'freealut-1.1.0.tbz2': [u'unstable', 1], u'kdeartwork-styles-3.5.7.tbz2': [u'unstable', 1], u'libvisual-plugins-0.4.0-r1.tbz2': [u'unstable', 0], u'compizconfig-python-0.5.2.tbz2': [u'unstable', 1], u'superkaramba-3.5.7.tbz2': [u'unstable', 1], u'dhcdbd-3.0.tbz2': [u'unstable', 0], u'kdf-3.5.7.tbz2': [u'unstable', 1], u'libmpeg2-0.4.1.tbz2': [u'unstable', 1], u'liboobs-2.18.1.tbz2': [u'unstable', 1], u'font-bitstream-type1-1.0.0.tbz2': [u'unstable', 1], u'gnome-netstatus-2.12.1.tbz2': [u'unstable', 1], u'xf86-input-elographics-1.1.0.tbz2': [u'unstable', 1], u'mono-1.2.5-r1.tbz2': [u'unstable', 0], u'qca-tls-1.0-r3.tbz2': [u'unstable', 1], u'kgoldrunner-3.5.7.tbz2': [u'unstable', 1], u'unifdef-1.20.tbz2': [u'unstable', 1], u'samba-3.0.25c-r1.tbz2': [u'unstable', 0], u'bluez-hcidump-1.40.tbz2': [u'unstable', 0], u'MIME-Lite-3.01.tbz2': [u'unstable', 1], u'xmessage-1.0.2.tbz2': [u'unstable', 0], u'yakuake-2.8_beta1.tbz2': [u'unstable', 0], u'dvd+rw-tools-7.0.tbz2': [u'unstable', 1], u'pygame-1.7.1.tbz2': [u'unstable', 1], u'evolution-webcal-2.10.0.tbz2': [u'unstable', 0], u'yasm-0.6.1.tbz2': [u'unstable', 0], u'Text-Shellwords-1.08.tbz2': [u'unstable', 1], u'mpeg2vidcodec-12-r1.tbz2': [u'unstable', 1], u'konversation-1.0.1-r3.tbz2': [u'unstable', 0], u'libpcre-7.2.tbz2': [u'unstable', 0], u'rman-3.2.tbz2': [u'unstable', 1], u'libpthread-stubs-0.1.tbz2': [u'unstable', 0], u'Time-HiRes-1.97.07.tbz2': [u'unstable', 1], u'kmenuedit-3.5.7.tbz2': [u'unstable', 1], u'aspell-af-0.50.0.tbz2': [u'unstable', 1], u'gtkmm-2.10.10.tbz2': [u'unstable', 0], u'docbook-xml-dtd-4.2-r2.tbz2': [u'unstable', 1], u'gimp-2.4.0_rc2.tbz2': [u'unstable', 0], u'gnome-python-extras-2.14.2-r1.tbz2': [u'unstable', 1], u'poppler-data-0.1.tbz2': [u'unstable', 1], u'libpano12-2.8.4.tbz2': [u'unstable', 1], u'musepack-tools-1.15v.tbz2': [u'unstable', 1], u'kappfinder-3.5.7.tbz2': [u'unstable', 1], u'qt-4.3.1.tbz2': [u'unstable', 0], u'pciutils-2.2.6-r1.tbz2': [u'unstable', 0], u'aspell-en-6.0.0.tbz2': [u'unstable', 1], u'libcompizconfig-0.5.2.tbz2': [u'unstable', 1], u'splashutils-1.5.2.tbz2': [u'unstable', 0], u'kdebase-meta-3.5.7.tbz2': [u'unstable', 1], u'gst-plugins-shout2-0.10.6.tbz2': [u'unstable', 0], u'doxygen-1.5.3.tbz2': [u'unstable', 0], u'xf86-input-digitaledge-1.1.0.tbz2': [u'unstable', 1], u'psmisc-22.5-r2.tbz2': [u'unstable', 0], u'kdeartwork-sounds-3.5.6.tbz2': [u'unstable', 1], u'docbook-sgml-dtd-3.1-r3.tbz2': [u'unstable', 1], u'openmotif-2.2.3-r9.tbz2': [u'unstable', 1], u'xf86-input-penmount-1.2.1.tbz2': [u'unstable', 0], u'knock-0.5.tbz2': [u'unstable', 1], u'texinfo-4.8-r5.tbz2': [u'unstable', 1], u'xf86-input-acecad-1.2.1.tbz2': [u'unstable', 0], u'tcl-8.4.15.tbz2': [u'unstable', 0], u'compiz-bcop-0.5.2.tbz2': [u'unstable', 1], u'win32codecs-20061022-r1.tbz2': [u'unstable', 1], u'mftrace-1.2.9.tbz2': [u'unstable', 0], u'motif-config-0.10.tbz2': [u'unstable', 1], u'appres-1.0.1.tbz2': [u'unstable', 1], u'check-0.9.5.tbz2': [u'unstable', 1], u'fonttosfnt-1.0.3.tbz2': [u'unstable', 1], u'docbook-dsssl-stylesheets-1.79.tbz2': [u'unstable', 1], u'libxkbui-1.0.2.tbz2': [u'unstable', 1], u'commons-lang-2.0-r2.tbz2': [u'unstable', 1], u'gst-plugins-jpeg-0.10.6.tbz2': [u'unstable', 0], u'beecrypt-4.1.2-r2.tbz2': [u'unstable', 1], u'desktop-file-utils-0.14.tbz2': [u'unstable', 0], u'perl-File-Spec-3.25.tbz2': [u'unstable', 0], u'musicbrainz-2.1.4.tbz2': [u'unstable', 1], u'libraw1394-1.2.1.tbz2': [u'unstable', 1], u'yaml-0.65.tbz2': [u'unstable', 0], u'gst-plugins-farsight-0.12.2.tbz2': [u'unstable', 0], u'Net-Daemon-0.43.tbz2': [u'unstable', 0], u'gksu-2.0.0.tbz2': [u'unstable', 1], u'mit-krb5-1.5.3-r1.tbz2': [u'unstable', 0], u'dosfstools-2.11-r3.tbz2': [u'unstable', 0], u'xproto-7.0.10.tbz2': [u'unstable', 1], u'Event-1.09.tbz2': [u'unstable', 0], u'pe-format-0.tbz2': [u'unstable', 1], u'tomboy-0.6.3.tbz2': [u'unstable', 0], u'libXaw-1.0.4.tbz2': [u'unstable', 0], u'kaddressbook-3.5.7.tbz2': [u'unstable', 1], u'gsmlib-1.11_pre041028.tbz2': [u'unstable', 1], u'font-bh-type1-1.0.0.tbz2': [u'unstable', 1], u'vcdimager-0.7.23.tbz2': [u'unstable', 1], u'gentoolkit-0.2.4_pre6.tbz2': [u'unstable', 0], u'DBI-1.58.tbz2': [u'unstable', 0], u'pam_passwdqc-1.0.4.tbz2': [u'unstable', 0], u'xmodmap-1.0.3.tbz2': [u'unstable', 0], u'libfame-0.9.1-r1.tbz2': [u'unstable', 0], u'enchant-1.2.5.tbz2': [u'unstable', 1], u'cvs-1.12.12-r4.tbz2': [u'unstable', 1], u'expat-2.0.1.tbz2': [u'unstable', 0], u'cronbase-0.3.2.tbz2': [u'unstable', 1], u'font-bitstream-100dpi-1.0.0.tbz2': [u'unstable', 1], u'urw-fonts-2.3.6.tbz2': [u'unstable', 0], u'xwd-1.0.1.tbz2': [u'unstable', 1], u'gtk2-ex-formfactory-0.65-r1.tbz2': [u'unstable', 1], u'libgadu-1.7.1.tbz2': [u'unstable', 0], u'juk-3.5.7.tbz2': [u'unstable', 1], u'gst-plugins-ugly-0.10.6.tbz2': [u'unstable', 0], u'Compress-Raw-Zlib-2.005.tbz2': [u'unstable', 0], u'boost-1.34.1.tbz2': [u'unstable', 0], u'dbus-1.0.2-r2.tbz2': [u'unstable', 1], u'kipi-plugins-0.1.4-r1.tbz2': [u'unstable', 0], u'compiz-fusion-plugins-main-0.5.2.tbz2': [u'unstable', 1], u'gst-plugins-annodex-0.10.6.tbz2': [u'unstable', 0], u'IO-Zlib-1.05.tbz2': [u'unstable', 1], u'gconf-2.18.0.1.tbz2': [u'unstable', 1], u'libdvdcss-1.2.9-r1.tbz2': [u'unstable', 1], u'aspell-nl-0.50.2.tbz2': [u'unstable', 1], u'xlsclients-1.0.1.tbz2': [u'unstable', 1], u'SOAP-Lite-0.69.tbz2': [u'unstable', 0], u'exiv2-0.15.tbz2': [u'unstable', 0], u'aspell-cs-0.60.20040614.tbz2': [u'unstable', 0], u'kjots-3.5.7.tbz2': [u'unstable', 1], u'eselect-esd-20060719.tbz2': [u'unstable', 1], u'read-edid-1.4.1-r1.tbz2': [u'unstable', 0], u'kdelirc-3.5.7.tbz2': [u'unstable', 1], u'gtksourceview-sharp-0.10-r1.tbz2': [u'unstable', 1], u'xsm-1.0.1.tbz2': [u'unstable', 1], u'ktimer-3.5.7.tbz2': [u'unstable', 1], u'artsplugin-xine-3.5.7.tbz2': [u'unstable', 1], u'jhead-2.7.tbz2': [u'unstable', 0], u'Xaw3d-1.5-r1.tbz2': [u'unstable', 1], u'flac123-0.0.11.tbz2': [u'unstable', 0], u'vpnc-0.5.1.tbz2': [u'unstable', 0], u'xf86-input-ur98-1.1.0.tbz2': [u'unstable', 1], u'sdl-ttf-2.0.9.tbz2': [u'unstable', 0], u'ksplashml-3.5.7.tbz2': [u'unstable', 1], u'cpuburn-1.4.tbz2': [u'unstable', 1], u'XML-Twig-3.29.tbz2': [u'unstable', 0], u'gdbm-1.8.3-r3.tbz2': [u'unstable', 1], u'tango-icon-theme-extras-0.1.0-r1.tbz2': [u'unstable', 1], u'gnome-mime-data-2.18.0.tbz2': [u'unstable', 1], u'fast-user-switch-applet-2.18.0.tbz2': [u'unstable', 1], u'kstars-3.5.7.tbz2': [u'unstable', 1], u'amor-3.5.7.tbz2': [u'unstable', 1], u'networkmanager-0.6.5_p20070823-r1.tbz2': [u'unstable', 0], u'nspluginwrapper-0.9.91.5.tbz2': [u'unstable', 0], u'mkfontscale-1.0.3.tbz2': [u'unstable', 1], u'randrproto-1.2.1.tbz2': [u'unstable', 1], u'TermReadKey-2.30.tbz2': [u'unstable', 1], u'fpconst-0.7.3.tbz2': [u'unstable', 1], u'xclock-1.0.3.tbz2': [u'unstable', 0], u'gift-0.11.8.1-r1.tbz2': [u'unstable', 0], u'kreversi-3.5.7.tbz2': [u'unstable', 1], u'krfb-3.5.7.tbz2': [u'unstable', 1], u'htdig-3.2.0_beta6-r2.tbz2': [u'unstable', 1], u'eyeD3-0.6.14.tbz2': [u'unstable', 0], u'kode-3.5.6.tbz2': [u'unstable', 1], u'libgnomecups-0.2.2.tbz2': [u'unstable', 1], u'docbook-sgml-dtd-4.0-r3.tbz2': [u'unstable', 1], u'xprop-1.0.3.tbz2': [u'unstable', 0], u'XML-Filter-BufferText-1.01.tbz2': [u'unstable', 1], u'videoproto-2.2.2.tbz2': [u'unstable', 1], u'linux-sabayon-2.6.22.tbz2': [u'unstable', 1], u'libXevie-1.0.2.tbz2': [u'unstable', 1], u'eselect-vi-1.1.5.tbz2': [u'unstable', 0], u'nss-mdns-0.10.tbz2': [u'unstable', 0], u'gnome-volume-manager-2.17.0.tbz2': [u'unstable', 1], u'eject-2.1.5-r1.tbz2': [u'unstable', 1], u'aircrack-ng-0.9.1.tbz2': [u'unstable', 0], u'XML-DOM-1.44.tbz2': [u'unstable', 1], u'rcs-5.7-r3.tbz2': [u'unstable', 1], u'glade-3.2.2.tbz2': [u'unstable', 0], u'crypto++-5.5.1.tbz2': [u'unstable', 0], u'kdcop-3.5.7.tbz2': [u'unstable', 1], u'docbook-sgml-dtd-3.0-r3.tbz2': [u'unstable', 1], u'sabayon-sources-2.6.22.tbz2': [u'unstable', 1], u'font-bh-lucidatypewriter-75dpi-1.0.0.tbz2': [u'unstable', 1], u'qscintilla-2.1.tbz2': [u'unstable', 0], u'mirrorselect-1.2.tbz2': [u'unstable', 1], u'kismet-2007.01.1b.tbz2': [u'unstable', 1], u'pptpclient-1.7.1-r1.tbz2': [u'unstable', 1], u'jasper-1.900.1-r1.tbz2': [u'unstable', 0], u'libmodplug-0.8.4-r2.tbz2': [u'unstable', 1], u'man-pages-zh_CN-1.5.tbz2': [u'unstable', 1], u'util-linux-2.13-r1.tbz2': [u'unstable', 1], u'libwww-5.4.0-r7.tbz2': [u'unstable', 1], u'libidn-1.0.tbz2': [u'unstable', 1], u'fontforge-20070831.tbz2': [u'unstable', 0], u'foomatic-db-engine-3.0.20070508.tbz2': [u'unstable', 0], u'gst-plugins-v4l-0.10.14.tbz2': [u'unstable', 0], u'emerald-0.5.2.tbz2': [u'unstable', 1], u'gtk-doc-1.8-r2.tbz2': [u'unstable', 0], u'ntp-4.2.4_p3.tbz2': [u'unstable', 0], u'libvirt-0.3.2.tbz2': [u'unstable', 0], u'libsexy-0.1.11.tbz2': [u'unstable', 1], u'xplsprinters-1.0.1.tbz2': [u'unstable', 1], u'hfsutils-3.2.6-r5.tbz2': [u'unstable', 1], u'gst-plugins-base-0.10.14.tbz2': [u'unstable', 0], u'man-pages-pl-20070628.tbz2': [u'unstable', 0], u'gnome-backgrounds-2.18.3.tbz2': [u'unstable', 0], u'totem-2.18.3.tbz2': [u'unstable', 0], u'gtk-engines-2.10.2.tbz2': [u'unstable', 0], u'xft-7.0.tbz2': [u'unstable', 1], u'gedit-2.18.2.tbz2': [u'unstable', 0], u'gtk+-1.2.10-r12.tbz2': [u'unstable', 1], u'libkcddb-3.5.7.tbz2': [u'unstable', 1], u'openoffice-2.2.1.tbz2': [u'unstable', 0], u'Params-Validate-0.88.tbz2': [u'unstable', 1], u'kcontrol-3.5.7-r90.tbz2': [u'unstable', 1], u'cabextract-1.2.tbz2': [u'unstable', 1], u'rsync-2.6.9-r3.tbz2': [u'unstable', 0], u'kdialog-3.5.5.tbz2': [u'unstable', 1], u'pyorbit-2.14.3.tbz2': [u'unstable', 0], u'procps-3.2.7.tbz2': [u'unstable', 1], u'mailx-support-20060102-r1.tbz2': [u'unstable', 1], u'xset-1.0.3.tbz2': [u'unstable', 0], u'myspell-de-20060316.tbz2': [u'unstable', 1], u'tls-1.5.0-r1.tbz2': [u'unstable', 0], u'build-docbook-catalog-1.2.tbz2': [u'unstable', 1], u'xf86-input-joystick-1.2.3.tbz2': [u'unstable', 0], u'spamassassin-3.2.3.tbz2': [u'unstable', 0], u'screen-4.0.3.tbz2': [u'unstable', 1], u'libnet-1.21.tbz2': [u'unstable', 0], u'korn-3.5.7.tbz2': [u'unstable', 1], u'gtkhtml-3.6.2.tbz2': [u'unstable', 1], u'kbstateapplet-3.5.7.tbz2': [u'unstable', 1], u'mkfontdir-1.0.3.tbz2': [u'unstable', 1], u'xf86-video-trident-1.2.3.tbz2': [u'unstable', 1], u'kwin-3.5.7.tbz2': [u'unstable', 1], u'xdm-1.1.6.tbz2': [u'unstable', 0], u'xf86-input-jamstudio-1.1.0.tbz2': [u'unstable', 1], u'ntfsprogs-1.13.1-r1.tbz2': [u'unstable', 0], u'aspell-gl-0.50.0.tbz2': [u'unstable', 1], u'kcron-3.5.7.tbz2': [u'unstable', 1], u'blackdown-jdk-1.4.2.03-r16.tbz2': [u'unstable', 0], u'mplayer-1.0_rc1_p20070824.tbz2': [u'unstable', 0], u'ktouch-3.5.7.tbz2': [u'unstable', 1], u'kcminit-3.5.6.tbz2': [u'unstable', 1], u'gettext-0.16.1-r1.tbz2': [u'unstable', 0], u'fbgrab-1.0.tbz2': [u'unstable', 1], u'xorg-cf-files-1.0.2.tbz2': [u'unstable', 1], u'gtkglarea-1.99.0.tbz2': [u'unstable', 1], u'usbutils-0.72-r4.tbz2': [u'unstable', 1], u'xf86-input-magellan-1.1.1.tbz2': [u'unstable', 0], u'dhcpcd-3.1.5.tbz2': [u'unstable', 0], u'madplay-0.15.2b-r1.tbz2': [u'unstable', 1], u'servletapi-2.4-r5.tbz2': [u'unstable', 1], u'confuse-2.5.tbz2': [u'unstable', 1], u'miro-0.9.9.1.tbz2': [u'unstable', 0], u'nas-1.8b.tbz2': [u'unstable', 1], u'virtualbox-modules-1.5.0-t2.6.22_sabayon.tbz2': [u'unstable', 0], u'glibc-2.6.1.tbz2': [u'unstable', 0], u'gecko-sharp-0.12.tbz2': [u'unstable', 0], u'desktop-acceleration-helpers-3.0-r7.tbz2': [u'unstable', 0], u'apr-util-1.2.10.tbz2': [u'unstable', 0], u'accel-manager-1.3.5.tbz2': [u'unstable', 1], u'gnu-gs-fonts-std-8.11.tbz2': [u'unstable', 1], u'xml-commons-resolver-1.2.tbz2': [u'unstable', 1], u'damageproto-1.1.0.tbz2': [u'unstable', 1], u'ndiswrapper-1.48_rc2-t2.6.22_sabayon.tbz2': [u'unstable', 0], u'kxsldbg-3.5.7.tbz2': [u'unstable', 1], u'kfilereplace-3.5.7.tbz2': [u'unstable', 1], u'arts-3.5.5-r1.tbz2': [u'unstable', 1], u'suspend2-userui-0.7.1.tbz2': [u'unstable', 0], u'bluez-utils-3.18.tbz2': [u'unstable', 0], u'eselect-timidity-20061203.tbz2': [u'unstable', 1], u'udept-0.5.99.0.2.95-r1.tbz2': [u'unstable', 1], u'pylirc-0.0.5.tbz2': [u'unstable', 1], u'xdriinfo-1.0.2.tbz2': [u'unstable', 0], u'sound-juicer-2.16.4.tbz2': [u'unstable', 0], u'radeontool-1.5-r3.tbz2': [u'unstable', 1], u'gocr-0.44.tbz2': [u'unstable', 0], u'gst-plugins-theora-0.10.14.tbz2': [u'unstable', 0], u'device-mapper-1.02.22.tbz2': [u'unstable', 1], u'db-3.2.9-r11.tbz2': [u'unstable', 1], u'foomatic-db-ppds-20070508.tbz2': [u'unstable', 0], u'knotes-3.5.7.tbz2': [u'unstable', 1], u'scons-0.97.tbz2': [u'unstable', 0], u'pymad-0.6.tbz2': [u'unstable', 0], u'emerald-themes-0.5.2.tbz2': [u'unstable', 1], u'Graph-0.81.tbz2': [u'unstable', 0], u'libmng-1.0.9-r1.tbz2': [u'unstable', 1], u'cogito-0.18.2.tbz2': [u'unstable', 1], u'kbackgammon-3.5.7.tbz2': [u'unstable', 1], u'File-Temp-0.18.tbz2': [u'unstable', 0], u'kfloppy-3.5.7.tbz2': [u'unstable', 1], u'nautilus-2.18.3.tbz2': [u'unstable', 1], u'aspell-et-0.1.21.1.tbz2': [u'unstable', 1], u'kmix-3.5.7.tbz2': [u'unstable', 1], u'libifp-1.0.0.2.tbz2': [u'unstable', 1], u'kdebase-kioslaves-3.5.7-r1.tbz2': [u'unstable', 0], u'font-adobe-utopia-type1-1.0.1.tbz2': [u'unstable', 1], u'xf86-video-vga-4.1.0.tbz2': [u'unstable', 1], u'kreadconfig-3.5.6.tbz2': [u'unstable', 1], u'Event-RPC-0.90.tbz2': [u'unstable', 1], u'gnome-desktop-2.18.3.tbz2': [u'unstable', 0], u'rar-3.7.0.tbz2': [u'unstable', 0], u'kdm-3.5.7-r11.tbz2': [u'unstable', 1], u'metisse-0.4.0_rc4-r2.tbz2': [u'unstable', 0], u'openssl-0.9.8e-r2.tbz2': [u'unstable', 0], u'beagle-0.2.17.tbz2': [u'unstable', 1], u'pkgconfig-0.22.tbz2': [u'unstable', 1], u'openexr-1.4.0a.tbz2': [u'unstable', 1], u'mozilla-firefox-2.0.0.6.tbz2': [u'unstable', 0], u'db-4.5.20_p2.tbz2': [u'unstable', 1], u'dnsmasq-2.40.tbz2': [u'unstable', 0], u'polyester-1.0.2.tbz2': [u'unstable', 0], u'portaudio-18.1-r6.tbz2': [u'unstable', 1], u'aspell-de-0.60_pre20030222.tbz2': [u'unstable', 1], u'dangerdeep-0.3.0.tbz2': [u'unstable', 1], u'xf86-input-fpit-1.1.0-r1.tbz2': [u'unstable', 1], u'libxmlpp-2.13.1.tbz2': [u'unstable', 1], u'Test-Simple-0.70.tbz2': [u'unstable', 1], u'libdrm-2.3.0.tbz2': [u'unstable', 1], u'opensp-1.5.2-r1.tbz2': [u'unstable', 1], u'gst-plugins-alsa-0.10.14.tbz2': [u'unstable', 0], u'sdparm-1.01.tbz2': [u'unstable', 1], u'PodParser-1.35.tbz2': [u'unstable', 1], u'karm-3.5.7.tbz2': [u'unstable', 1], u'katomic-3.5.7.tbz2': [u'unstable', 1], u'pam_keyring-0.0.8.tbz2': [u'unstable', 1], u'alsa-utils-1.0.14.tbz2': [u'unstable', 0], u'mailbase-1.tbz2': [u'unstable', 1], u'kpager-3.5.7.tbz2': [u'unstable', 1], u'perl-DB_File-1.815.tbz2': [u'unstable', 1], u'font-util-1.0.1.tbz2': [u'unstable', 1], u'font-misc-misc-1.0.0.tbz2': [u'unstable', 1], u'xf86-input-mutouch-1.1.0.tbz2': [u'unstable', 1], u'xerces-2.9.0.tbz2': [u'unstable', 0], u'kfind-3.5.7.tbz2': [u'unstable', 1], u'kfax-3.5.7.tbz2': [u'unstable', 1], u'klines-3.5.7.tbz2': [u'unstable', 1], u'klipper-3.5.7.tbz2': [u'unstable', 1], u'korganizer-3.5.7-r1.tbz2': [u'unstable', 0], u'pam-0.99.8.1.tbz2': [u'unstable', 0], u'fox-1.6.27.tbz2': [u'unstable', 0], u'xf86-video-tseng-1.1.1.tbz2': [u'unstable', 1], u'pppconfig-2.3.17-r1.tbz2': [u'unstable', 0], u'timidity++-2.13.2-r5.tbz2': [u'unstable', 0], u'klaptopdaemon-3.5.7-r1.tbz2': [u'unstable', 0], u'nopaste-1992.tbz2': [u'unstable', 1], u'libkpgp-3.5.4.tbz2': [u'unstable', 1], u'afatech9005-firmware-2.tbz2': [u'unstable', 2], u'aspell-da-1.6.0.tbz2': [u'unstable', 1], u'fftw-2.1.5-r3.tbz2': [u'unstable', 0], u'dosbox-0.72.tbz2': [u'unstable', 0], u'knewsticker-3.5.7.tbz2': [u'unstable', 1], u'automake-1.5.tbz2': [u'unstable', 1], u'kbruch-3.5.7.tbz2': [u'unstable', 1], u'eselect-1.0.10.tbz2': [u'unstable', 0], u'ogmtools-1.5.tbz2': [u'unstable', 1], u'lightscribe-1.4.136.1.tbz2': [u'unstable', 1], u'evince-0.8.3.tbz2': [u'unstable', 0], u'avalon-logkit-2.1-r1.tbz2': [u'unstable', 0], u't1utils-1.32.tbz2': [u'unstable', 1], u'man-pages-nl-0.13.3.tbz2': [u'unstable', 1], u'kstart-3.5.6.tbz2': [u'unstable', 1], u'clamav-0.91.2.tbz2': [u'unstable', 0], u'diffutils-2.8.7-r2.tbz2': [u'unstable', 0], u'ftgl-2.1.2-r1.tbz2': [u'unstable', 1], u'openal-0.0.8-r2.tbz2': [u'unstable', 0], u'ed-0.8.tbz2': [u'unstable', 0], u'autoconf-2.61-r1.tbz2': [u'unstable', 0], u'cups-1.2.12.tbz2': [u'unstable', 0], u'javacup-0.11a_beta20060608.tbz2': [u'unstable', 0], u'libvncserver-0.9.1.tbz2': [u'unstable', 0], u'gnu-netcat-0.7.1-r1.tbz2': [u'unstable', 0], u'Cairo-1.04.1.tbz2': [u'unstable', 0], u'libkdcraw-0.1.1.tbz2': [u'unstable', 0], u'indent-2.2.9-r4.tbz2': [u'unstable', 0], u'libpq-8.2.4.tbz2': [u'unstable', 0], u'pmount-0.9.16.tbz2': [u'unstable', 0], u'glut-1.0.tbz2': [u'unstable', 1], u'kdebase-data-3.5.7.tbz2': [u'unstable', 1], u'Net-SSLeay-1.30.tbz2': [u'unstable', 1], u'control-center-2.18.1.tbz2': [u'unstable', 1], u'libXfixes-4.0.3.tbz2': [u'unstable', 1], u'man-pages-ru-0.98.tbz2': [u'unstable', 1], u'portato-0.8.5.tbz2': [u'unstable', 0], u'gnome-games-2.18.2.1.tbz2': [u'unstable', 0], u'libXpm-3.5.7.tbz2': [u'unstable', 0], u'db-1.85-r3.tbz2': [u'unstable', 1], u'tango-icon-theme-0.8.0.tbz2': [u'unstable', 1], u'tftp-hpa-0.48.tbz2': [u'unstable', 1], u'xf86vidmodeproto-2.2.2.tbz2': [u'unstable', 1], u'kpilot-3.5.5.tbz2': [u'unstable', 1], u'libsamplerate-0.1.2-r1.tbz2': [u'unstable', 1], u'hdparm-7.7.tbz2': [u'unstable', 0], u'gst-plugins-gconf-0.10.6.tbz2': [u'unstable', 0], u'myspell-es-20060316.tbz2': [u'unstable', 1], u'ksmiletris-3.5.7.tbz2': [u'unstable', 1], u'XML-Handler-YAWriter-0.23-r1.tbz2': [u'unstable', 1], u'unzip-5.52-r1.tbz2': [u'unstable', 1], u'gnome-doc-utils-0.10.3.tbz2': [u'unstable', 1], u'emul-linux-x86-gtklibs-11.0.tbz2': [u'unstable', 0], u'libXext-1.0.3.tbz2': [u'unstable', 1], u'netselect-0.3-r1.tbz2': [u'unstable', 1], u'zenity-2.18.2.tbz2': [u'unstable', 0], u'XML-XSLT-0.48.tbz2': [u'unstable', 1], u'glibmm-2.12.10.tbz2': [u'unstable', 0], u'nxclient-3.0.0-r3.tbz2': [u'unstable', 0], u'db-4.2.52_p4-r2.tbz2': [u'unstable', 1], u'gst-plugins-speex-0.10.6.tbz2': [u'unstable', 0], u'libgdiplus-1.2.5.tbz2': [u'unstable', 0], u'GD-2.35-r1.tbz2': [u'unstable', 0], u'xcursorgen-1.0.2.tbz2': [u'unstable', 0], u'xf86-video-s3-0.5.0.tbz2': [u'unstable', 1], u'util-macros-1.1.5.tbz2': [u'unstable', 1], u'font-adobe-utopia-75dpi-1.0.1.tbz2': [u'unstable', 1], u'baekmuk-fonts-2.2-r2.tbz2': [u'unstable', 1], u'kscd-3.5.7.tbz2': [u'unstable', 1], u'k3b-1.0.3.tbz2': [u'unstable', 0], u'acpid-1.0.6.tbz2': [u'unstable', 0], u'libXdmcp-1.0.2.tbz2': [u'unstable', 1], u'twisted-2.5.0.tbz2': [u'unstable', 1], u'emul-linux-x86-qtlibs-10.0-r1.tbz2': [u'unstable', 1], u'ksvg-3.5.7.tbz2': [u'unstable', 1], u'artsplugin-akode-3.5.7.tbz2': [u'unstable', 1], u'libsvg-0.1.4.tbz2': [u'unstable', 1], u'evolution-sharp-0.12.4.tbz2': [u'unstable', 0], u'File-Which-0.05.tbz2': [u'unstable', 1], u'pygtkglext-1.1.0.tbz2': [u'unstable', 1], u'xwininfo-1.0.3.tbz2': [u'unstable', 0], u'libgssglue-0.1.tbz2': [u'unstable', 0], u'sabayon-version-3.4-r2.tbz2': [u'unstable', 0], u'gtkhtml-2.6.3.tbz2': [u'unstable', 1], u'vorbis-tools-1.1.1-r5.tbz2': [u'unstable', 0], u'configobj-4.4.0-r1.tbz2': [u'unstable', 0], u'amarok-1.4.7.tbz2': [u'unstable', 0], u'rdesktop-1.5.0-r3.tbz2': [u'unstable', 0], u'gsm-1.0.12.tbz2': [u'unstable', 0], u'xf86-input-microtouch-1.1.1.tbz2': [u'unstable', 0], u'aspell-he-1.0.0.tbz2': [u'unstable', 0], u'knewsticker-scripts-3.5.7.tbz2': [u'unstable', 1], u'jack-3.1.1.tbz2': [u'unstable', 1], u'perl-PodParser-1.35.tbz2': [u'unstable', 1], u'pilot-link-0.11.8-r1.tbz2': [u'unstable', 1], u'libofa-0.9.3.tbz2': [u'unstable', 1], u'aspell-sr-0.60.tbz2': [u'unstable', 1], u'libkdeedu-3.5.7.tbz2': [u'unstable', 1], u'kdepim-kresources-3.5.7-r1.tbz2': [u'unstable', 0], u'p7zip-4.51.tbz2': [u'unstable', 0], u'emul-linux-x86-compat-1.0-r3.tbz2': [u'unstable', 1], u'SVG-2.33.tbz2': [u'unstable', 1], u'ark-3.5.7.tbz2': [u'unstable', 1], u'lacie-lightscribe-labeler-1.0.6.tbz2': [u'unstable', 1], u'kworldclock-3.5.7.tbz2': [u'unstable', 0], u'File-Find-Rule-0.30.tbz2': [u'unstable', 1], u'amule-2.2.0_pre20070920.tbz2': [u'unstable', 0], u'libstdc++-v3-3.3.6.tbz2': [u'unstable', 1], u'sudo-1.6.8_p12-r1.tbz2': [u'unstable', 1], u'font-cursor-misc-1.0.0.tbz2': [u'unstable', 1], u'libXp-1.0.0.tbz2': [u'unstable', 1], u'Compress-Zlib-2.005.tbz2': [u'unstable', 0], u'python-2.5.1-r2.tbz2': [u'unstable', 0], u'whois-4.7.22.tbz2': [u'unstable', 0], u'Error-0.17.008.tbz2': [u'unstable', 1], u'orca-2.18.1.tbz2': [u'unstable', 0], u'globespan-adsl-0.12.tbz2': [u'unstable', 0], u'vlc-0.8.6c.tbz2': [u'unstable', 0], u'klinkstatus-3.5.7.tbz2': [u'unstable', 1], u'libavc1394-0.5.3.tbz2': [u'unstable', 1], u'xfsprogs-2.9.3.tbz2': [u'unstable', 0], u'ca-certificates-20070303-r1.tbz2': [u'unstable', 0], u'trapproto-3.4.3.tbz2': [u'unstable', 1], u'kuser-3.5.7.tbz2': [u'unstable', 1], u'xorg-server-1.4-r2.tbz2': [u'unstable', 0], u'gst-plugins-flac-0.10.6.tbz2': [u'unstable', 0], u'skim-1.4.5.tbz2': [u'unstable', 1], u'libmcs-0.5.0.tbz2': [u'unstable', 0], u'pyvorbis-1.4-r2.tbz2': [u'unstable', 0], u'pessulus-2.16.2.tbz2': [u'unstable', 0], u'swt-3.3.tbz2': [u'unstable', 0], u'itcl-3.3-r1.tbz2': [u'unstable', 1], u'kpat-3.5.7.tbz2': [u'unstable', 1], u'junit-3.8.2-r1.tbz2': [u'unstable', 0], u'snack-2.2.10-r1.tbz2': [u'unstable', 0], u'aspell-eo-0.50.2.tbz2': [u'unstable', 1], u'myspell-nl-20060316.tbz2': [u'unstable', 1], u'fping-2.4_beta2-r1.tbz2': [u'unstable', 1], u'gnome-spell-1.0.7-r1.tbz2': [u'unstable', 1], u'gperf-3.0.3.tbz2': [u'unstable', 0], u'kcharselect-3.5.7.tbz2': [u'unstable', 1], u'myspell-ru-20060316.tbz2': [u'unstable', 1], u'perl-cleaner-1.04.3.tbz2': [u'unstable', 1], u'wine-0.9.45.tbz2': [u'unstable', 0], u'pixman-0.9.5.tbz2': [u'unstable', 0], u'vim-7.1.087.tbz2': [u'unstable', 0], u'autopano-sift-2.4.tbz2': [u'unstable', 1], u'hunspell-1.1.9.tbz2': [u'unstable', 0], u'md5deep-1.13.tbz2': [u'unstable', 0], u'libmix-2.05.tbz2': [u'unstable', 1], u'ufed-0.40-r6.tbz2': [u'unstable', 1], u'fox-wrapper-2.tbz2': [u'unstable', 1], u'gpgme-0.3.14-r1.tbz2': [u'unstable', 1], u'libsdl-1.2.12.tbz2': [u'unstable', 0], u'xcb-proto-1.0.tbz2': [u'unstable', 0], u'shash-0.2.6-r1.tbz2': [u'unstable', 1], u'ardour-2.0.5.tbz2': [u'unstable', 0], u'glade-2.12.1.tbz2': [u'unstable', 1], u'shadow-4.0.18.1-r1.tbz2': [u'unstable', 0], u'boehm-gc-7.0-r1.tbz2': [u'unstable', 0], u'font-bitstream-speedo-1.0.0.tbz2': [u'unstable', 1], u'perl-Digest-MD5-2.36.tbz2': [u'unstable', 1], u'mktemp-1.5.tbz2': [u'unstable', 1], u'setserial-2.17-r3.tbz2': [u'unstable', 1], u'kdesu-3.5.7.tbz2': [u'unstable', 1], u'kpf-3.5.7.tbz2': [u'unstable', 1], u'fluxbox-1.0_rc3_p5059.tbz2': [u'unstable', 0], u'pam_dotfile-0.7-r1.tbz2': [u'unstable', 1], u'kdeaccessibility-meta-3.5.7.tbz2': [u'unstable', 1], u'libsmbios-0.13.10.tbz2': [u'unstable', 0], u'man-pages-da-0.1.1.tbz2': [u'unstable', 1], u'libgnomeprint-2.18.1.tbz2': [u'unstable', 0], u'compiz-fusion-0.5.2.tbz2': [u'unstable', 1], u'zlib-1.2.3-r1.tbz2': [u'unstable', 1], u'dssi-0.9.1.tbz2': [u'unstable', 1], u'kmldonkey-0.10.1-r1.tbz2': [u'unstable', 0], u'picasa-2.2.2820.5.tbz2': [u'unstable', 1], u'kalzium-3.5.7.tbz2': [u'unstable', 1], u'kdnssd-3.5.7.tbz2': [u'unstable', 1], u'popt-1.10.7.tbz2': [u'unstable', 1], u'udftools-1.0.0b-r7.tbz2': [u'unstable', 0], u'XML-SAX-0.16.tbz2': [u'unstable', 0], u'libglademm-2.6.4.tbz2': [u'unstable', 0], u'cyrus-sasl-2.1.22-r2.tbz2': [u'unstable', 1], u'gcalctool-5.9.14.tbz2': [u'unstable', 1], u'lvm2-2.02.27.tbz2': [u'unstable', 0], u'foomatic-filters-3.0.20070501.tbz2': [u'unstable', 0], u'extutils-pkgconfig-1.07.tbz2': [u'unstable', 1], u'xtrap-1.0.2.tbz2': [u'unstable', 1], u'ctags-5.6-r3.tbz2': [u'unstable', 0], u'crystal-1.0.2.tbz2': [u'unstable', 1], u'ppp-2.4.4-r13.tbz2': [u'unstable', 0], u'perl-Time-Local-1.17.tbz2': [u'unstable', 1], u'librpcsecgss-0.16.tbz2': [u'unstable', 0], u'docbook-xml-dtd-4.4-r1.tbz2': [u'unstable', 1], u'HTML-Tagset-3.10.tbz2': [u'unstable', 1], u'mandvd-2.4-r2.tbz2': [u'unstable', 1], u'curl-7.17.0_pre20070828.tbz2': [u'unstable', 0], u'pango-1.16.5.tbz2': [u'unstable', 0], u'lilo-22.8-r1.tbz2': [u'unstable', 0], u'Archive-Tar-1.32.tbz2': [u'unstable', 0], u'vamps-0.99.2.tbz2': [u'unstable', 1], u'java-config-wrapper-0.14.tbz2': [u'unstable', 0], u'xvinfo-1.0.2.tbz2': [u'unstable', 0], u'gnome-python-2.18.2.tbz2': [u'unstable', 0], u'libmal-0.31.tbz2': [u'unstable', 1], u'python-updater-0.2.tbz2': [u'unstable', 0], u'wireshark-0.99.6-r1.tbz2': [u'unstable', 0], u'konqueror-akregator-3.5.7.tbz2': [u'unstable', 1], u'subtitleripper-0.3.4-r2.tbz2': [u'unstable', 1], u'xsetroot-1.0.2.tbz2': [u'unstable', 0], u'xlogo-1.0.1.tbz2': [u'unstable', 1], u'xf86-input-keyboard-1.2.2.tbz2': [u'unstable', 0], u'kdenetwork-kfile-plugins-3.5.7.tbz2': [u'unstable', 1], u'xf86-video-mga-1.4.7.tbz2': [u'unstable', 0], u'fifteenapplet-3.5.7.tbz2': [u'unstable', 1], u'net-tools-1.60-r13.tbz2': [u'unstable', 1], u'libnet-1.1.2.1-r1.tbz2': [u'unstable', 1], u'ksim-3.5.7.tbz2': [u'unstable', 1], u'cdrtools-2.01.01_alpha34.tbz2': [u'unstable', 0], u'opal-2.2.8.tbz2': [u'unstable', 1], u'ftpbase-0.01.tbz2': [u'unstable', 0], u'libXvMC-1.0.4.tbz2': [u'unstable', 1], u'kmoon-3.5.7.tbz2': [u'unstable', 1], u'keduca-3.5.7.tbz2': [u'unstable', 1], u'gparted-0.3.3.tbz2': [u'unstable', 1], u'busybox-1.7.0.tbz2': [u'unstable', 0], u'gnome-pilot-2.0.15.tbz2': [u'unstable', 1], u'tvtime-1.0.2-r1.tbz2': [u'unstable', 1], u'noatun-plugins-3.5.7.tbz2': [u'unstable', 1], u'cairomm-1.2.4.tbz2': [u'unstable', 1], u'kdebase-pam-7.tbz2': [u'unstable', 0], u'dpkg-1.13.25.tbz2': [u'unstable', 1], u'imlib2-1.4.0.tbz2': [u'unstable', 0], u'iceauth-1.0.2.tbz2': [u'unstable', 0], u'gnome-pilot-conduits-2.0.15.tbz2': [u'unstable', 1], u'sabayonlinux-artwork-3.40-r3.tbz2': [u'unstable', 1], u'aspell-ga-0.50.4.tbz2': [u'unstable', 1], u'DateTime-TimeZone-0.66.02.tbz2': [u'unstable', 0], u'gnome-session-2.18.3.tbz2': [u'unstable', 0], u'keyboard-configuration-helpers-2.2.tbz2': [u'unstable', 1], u'subversion-1.4.4-r4.tbz2': [u'unstable', 0], u'wv-1.2.3-r1.tbz2': [u'unstable', 1], u'gst-plugins-fluendo-mpegdemux-0.10.4.tbz2': [u'unstable', 1], u'tiff-3.8.2-r2.tbz2': [u'unstable', 1], u'gst-plugins-mpeg2dec-0.10.6.tbz2': [u'unstable', 0], u'ksync-3.5.6.tbz2': [u'unstable', 1], u'poppler-bindings-0.5.4.tbz2': [u'unstable', 1], u'xf86-video-savage-2.1.3.tbz2': [u'unstable', 0], u'nspr-4.6.7.tbz2': [u'unstable', 0], u'rp-l2tp-0.4-r1.tbz2': [u'unstable', 1], u'ladspa-sdk-1.12-r2.tbz2': [u'unstable', 1], u'libXrender-0.9.4.tbz2': [u'unstable', 0], u'metacity-2.18.5.tbz2': [u'unstable', 0], u'xkbcomp-1.0.3.tbz2': [u'unstable', 1], u'gentoolkit-dev-0.2.6.6.tbz2': [u'unstable', 0], u'kmailcvt-3.5.5.tbz2': [u'unstable', 1], u'yelp-2.18.1.tbz2': [u'unstable', 1], u'kdesktop-3.5.7-r10.tbz2': [u'unstable', 1], u'jack-audio-connection-kit-0.103.0.tbz2': [u'unstable', 0], u'foomatic-db-20070508.tbz2': [u'unstable', 0], u'kanagram-3.5.7.tbz2': [u'unstable', 1], u'resolvconf-gentoo-1.4.tbz2': [u'unstable', 0], u'tcsh-6.15-r2.tbz2': [u'unstable', 0], u'myspell-gl-20060316.tbz2': [u'unstable', 1], u'gconf-sharp-2.16.0.tbz2': [u'unstable', 1], u'acl-2.2.44.tbz2': [u'unstable', 0], u'perl-tk-804.027.tbz2': [u'unstable', 1], u'gmime-2.2.3.tbz2': [u'unstable', 1], u'vbetool-0.7.tbz2': [u'unstable', 1], u'docbook-sgml-dtd-4.4.tbz2': [u'unstable', 1], u'eselect-opengl-1.0.5.tbz2': [u'unstable', 1], u'kandy-3.5.7.tbz2': [u'unstable', 1], u'xload-1.0.2.tbz2': [u'unstable', 1], u'gail-1.18.0.tbz2': [u'unstable', 1], u'bridge-utils-1.2.tbz2': [u'unstable', 1], u'johntheripper-1.7.2-r2.tbz2': [u'unstable', 0], u'libgcrypt-1.2.4.tbz2': [u'unstable', 1], u'mesa-7.0.1.tbz2': [u'unstable', 0], u'lsof-4.78-r1.tbz2': [u'unstable', 0], u'artsplugin-audiofile-3.5.4.tbz2': [u'unstable', 1], u'atlantikdesigner-3.5.7.tbz2': [u'unstable', 1], u'libXxf86vm-1.0.1.tbz2': [u'unstable', 1], u'openldap-2.3.38.tbz2': [u'unstable', 0], u'ethtool-6.tbz2': [u'unstable', 0], u'compizconfig-backend-kconfig-0.5.2.tbz2': [u'unstable', 1], u'DateManip-5.44.tbz2': [u'unstable', 1], u'pyid3lib-0.5.1-r1.tbz2': [u'unstable', 0], u'lzo-1.08-r1.tbz2': [u'unstable', 1], u'zd1211-firmware-1.3.tbz2': [u'unstable', 1], u'docbook-sgml-utils-0.6.14.tbz2': [u'unstable', 1], u'pyogg-1.3-r1.tbz2': [u'unstable', 1], u'gucharmap-1.10.0.tbz2': [u'unstable', 1], u'sqlite-3.4.1.tbz2': [u'unstable', 0], u'qca-1.0-r2.tbz2': [u'unstable', 1], u'gcc-4.2.0.tbz2': [u'unstable', 0], u'libgnomekbd-2.18.2.tbz2': [u'unstable', 0], u'perl-Test-Simple-0.70.tbz2': [u'unstable', 1], u'dvd-slideshow-0.8.0.tbz2': [u'unstable', 1], u'noatun-3.5.7.tbz2': [u'unstable', 1], u'libkonq-3.5.7.tbz2': [u'unstable', 1], u'make-3.81.tbz2': [u'unstable', 1], u'kvm-36-t2.6.22_sabayon.tbz2': [u'unstable', 0], u'xf86-video-openchrome-9999.tbz2': [u'unstable', 1], u'gccmakedep-1.0.2.tbz2': [u'unstable', 1], u'IO-Socket-SSL-1.07.tbz2': [u'unstable', 0], u'fixesproto-4.0.tbz2': [u'unstable', 1], u'ucl-1.03.tbz2': [u'unstable', 1], u'normalize-0.7.7.tbz2': [u'unstable', 1], u'xf86-input-elo2300-1.1.1.tbz2': [u'unstable', 0], u'gtk-theme-switch-2.0.0_rc2-r2.tbz2': [u'unstable', 1], u'eyesapplet-3.5.7.tbz2': [u'unstable', 1], u'strace-4.5.16.tbz2': [u'unstable', 0], u'gst-plugins-neon-0.10.5.tbz2': [u'unstable', 0], u'expect-5.43.0.tbz2': [u'unstable', 1], u'fortune-mod-1.99.1-r2.tbz2': [u'unstable', 1], u'kdvi-3.5.7.tbz2': [u'unstable', 1], u'libbtctl-0.8.2.tbz2': [u'unstable', 1], u'atk-1.18.0.tbz2': [u'unstable', 1], u'chrpath-0.13.tbz2': [u'unstable', 1], u'font-sun-misc-1.0.0.tbz2': [u'unstable', 1], u'reiserfsprogs-3.6.19-r2.tbz2': [u'unstable', 0], u'xcb-util-0.2.tbz2': [u'unstable', 0], u'gtk-sharp-2.10.0.tbz2': [u'unstable', 3], u'file-roller-2.18.4.tbz2': [u'unstable', 0], u'coreutils-6.9-r1.tbz2': [u'unstable', 0], u'MIME-tools-5.420.tbz2': [u'unstable', 1], u'sdl-sound-1.0.1-r2.tbz2': [u'unstable', 1], u'mime-types-7.tbz2': [u'unstable', 1], u'festival-1.96_beta.tbz2': [u'unstable', 1], u'pygobject-2.12.3.tbz2': [u'unstable', 1], u'renamedlg-images-3.5.7.tbz2': [u'unstable', 1], u'dynamite-0.1.tbz2': [u'unstable', 1], u'Locale-gettext-1.05.tbz2': [u'unstable', 1], u'elfutils-0.127.tbz2': [u'unstable', 0], u'Storable-2.16.tbz2': [u'unstable', 1], u'libshout-2.2.2.tbz2': [u'unstable', 1], u'printproto-1.0.3.tbz2': [u'unstable', 1], u'gwenview-1.4.1.tbz2': [u'unstable', 1], u'xbitmaps-1.0.1.tbz2': [u'unstable', 1], u'jython-2.1-r11.tbz2': [u'unstable', 0], u'kvoctrain-3.5.7.tbz2': [u'unstable', 1], u'avahi-0.6.21.tbz2': [u'unstable', 0], u'libsndfile-1.0.17.tbz2': [u'unstable', 1], u'libwww-perl-5.805.tbz2': [u'unstable', 1], u'GD-SVG-0.28.tbz2': [u'unstable', 0], u'wxGTK-2.6.3.3.tbz2': [u'unstable', 1], u'xdelta-3.0-r1.tbz2': [u'unstable', 0], u'xorg-docs-1.4-r1.tbz2': [u'unstable', 0], u'Test-Harness-2.64.tbz2': [u'unstable', 1], u'ksynaptics-0.3.3.tbz2': [u'unstable', 1], u'libkpimidentities-3.5.7.tbz2': [u'unstable', 1], u'pyxml-0.8.4-r1.tbz2': [u'unstable', 0], u'gtk-vnc-0.1.0.tbz2': [u'unstable', 0], u'Crypt-SSLeay-0.55.tbz2': [u'unstable', 0], u'emul-linux-x86-baselibs-10.2.tbz2': [u'unstable', 1], u'kgpg-3.5.7.tbz2': [u'unstable', 1], u'baselayout-1.12.10-r4.tbz2': [u'unstable', 0], u'linuxwacom-0.7.4_p3.tbz2': [u'unstable', 1], u'libXv-1.0.3.tbz2': [u'unstable', 1], u'libopensync-0.22.tbz2': [u'unstable', 1], u'kig-3.5.7.tbz2': [u'unstable', 1], u'icon-slicer-0.3.tbz2': [u'unstable', 1], u'kdeartwork-wallpapers-3.5.6.tbz2': [u'unstable', 1], u'gnome-sharp-2.16.0.tbz2': [u'unstable', 1], u'mplayerplug-in-3.45.tbz2': [u'unstable', 0], u'bcm43xx-fwcutter-006.tbz2': [u'unstable', 1], u'pysqlite-2.3.5.tbz2': [u'unstable', 1], u'ksnake-3.5.7.tbz2': [u'unstable', 1], u'meanwhile-1.0.2.tbz2': [u'unstable', 1], u'libpng-1.2.19.tbz2': [u'unstable', 0], u'resourceproto-1.0.2.tbz2': [u'unstable', 1], u'numeric-24.2-r6.tbz2': [u'unstable', 0], u'xf86-input-mouse-1.2.2.tbz2': [u'unstable', 0], u'imlib-1.9.15-r1.tbz2': [u'unstable', 1], u'kpersonalizer-3.5.7.tbz2': [u'unstable', 1], u'Net-DBus-0.33.4.tbz2': [u'unstable', 1], u'Net-DNS-0.61.tbz2': [u'unstable', 0], u'smpeg-0.4.4-r9.tbz2': [u'unstable', 1], u'openobex-1.3.tbz2': [u'unstable', 1], u'wxGTK-2.8.4.0.tbz2': [u'unstable', 1], u'xrandr-1.2.2.tbz2': [u'unstable', 0], u'jre-1.4.2.tbz2': [u'unstable', 1], u'java-config-2.0.33-r1.tbz2': [u'unstable', 1], u'ksnapshot-3.5.7.tbz2': [u'unstable', 1], u'gnome-media-2.18.0-r1.tbz2': [u'unstable', 0], u'myspell-it-20060316.tbz2': [u'unstable', 1], u'glade-sharp-1.0.10.tbz2': [u'unstable', 1], u'XML-XPath-1.13.tbz2': [u'unstable', 1], u'gst-plugins-gnomevfs-0.10.14.tbz2': [u'unstable', 0], u'libkdegames-3.5.7.tbz2': [u'unstable', 1], u'pythondialog-2.7.tbz2': [u'unstable', 1], u'myspell-en-20060316.tbz2': [u'unstable', 1], u'id3-py-1.2.tbz2': [u'unstable', 1], u'kttsd-3.5.7.tbz2': [u'unstable', 1], u'skype-1.4.0.99.tbz2': [u'unstable', 0], u'speedtouch-1.3.1-r3.tbz2': [u'unstable', 1], u'Net-IP-1.25-r1.tbz2': [u'unstable', 1], u'dvdrip-0.98.8.tbz2': [u'unstable', 0], u'net-snmp-5.4.1-r1.tbz2': [u'unstable', 0], u'iso-codes-0.58.tbz2': [u'unstable', 1], u'kdeartwork-emoticons-3.5.4.tbz2': [u'unstable', 1], u'squashfs-tools-3.2_p2.tbz2': [u'unstable', 0], u'xrdb-1.0.4.tbz2': [u'unstable', 0], u'zip-2.32.tbz2': [u'unstable', 1], u'hwdata-gentoo-0.3.tbz2': [u'unstable', 1], u'xf86-input-hyperpen-1.1.0.tbz2': [u'unstable', 1], u'libXrandr-1.2.2.tbz2': [u'unstable', 0], u'Event-ExecFlow-0.63.tbz2': [u'unstable', 1], u'libwnck-2.18.3.tbz2': [u'unstable', 0], u'gnome-python-desktop-2.18.0.tbz2': [u'unstable', 1], u'xf86-input-tek4957-1.1.0.tbz2': [u'unstable', 1], u'gst-plugins-a52dec-0.10.6.tbz2': [u'unstable', 0], u'bin86-0.16.17.tbz2': [u'unstable', 1], u'gnome-icon-theme-2.18.0.tbz2': [u'unstable', 1], u'kdegames-meta-3.5.7.tbz2': [u'unstable', 1], u'libvisual-0.4.0.tbz2': [u'unstable', 1], u'timidity-eawpatches-12-r5.tbz2': [u'unstable', 1], u'docbook-sgml-dtd-4.1-r3.tbz2': [u'unstable', 1], u'xf86-video-siliconmotion-1.5.1.tbz2': [u'unstable', 1], u'kweather-3.5.7.tbz2': [u'unstable', 1], u'libgnomeui-2.18.1.tbz2': [u'unstable', 1], u'libgnomeprintui-2.18.0.tbz2': [u'unstable', 1], u'gmp-4.2.1-r1.tbz2': [u'unstable', 1], u'atlantik-3.5.7.tbz2': [u'unstable', 1], u'xf86miscproto-0.9.2.tbz2': [u'unstable', 1], u'libsvg-cairo-0.1.6.tbz2': [u'unstable', 1], u'gnome-main-menu-9999.tbz2': [u'unstable', 1], u'dbus-python-0.82.2.tbz2': [u'unstable', 0], u'yacc-1.9.1-r3.tbz2': [u'unstable', 1], u'URI-1.35.tbz2': [u'unstable', 1], u'javatoolkit-0.2.0-r1.tbz2': [u'unstable', 1], u'm17n-lib-1.3.4.tbz2': [u'unstable', 1], u'cddb-py-1.4.tbz2': [u'unstable', 1], u'kmail-3.5.7-r2.tbz2': [u'unstable', 0], u'man-pages-cs-0.16-r1.tbz2': [u'unstable', 1], u'xf86driproto-2.0.3.tbz2': [u'unstable', 1], u'gzip-1.3.12.tbz2': [u'unstable', 1], u'gle-3.1.0-r1.tbz2': [u'unstable', 1], u'giflib-4.1.4.tbz2': [u'unstable', 1], u'automake-1.9.6-r2.tbz2': [u'unstable', 1], u'libatomic_ops-1.2-r1.tbz2': [u'unstable', 0], u'aspell-ca-0.60.20040130.tbz2': [u'unstable', 0], u'kenolaba-3.5.7.tbz2': [u'unstable', 1], u'libuninameslist-20060907.tbz2': [u'unstable', 0], u'openvpn-2.0.7-r2.tbz2': [u'unstable', 1], u'dejavu-2.19.tbz2': [u'unstable', 0], u'x11vnc-0.9.2-r1.tbz2': [u'unstable', 0], u'knetworkmanager-0.2_pre20070702-r1.tbz2': [u'unstable', 1], u'kate-3.5.7-r1.tbz2': [u'unstable', 0], u'Number-Compare-0.01.tbz2': [u'unstable', 1], u'kdeartwork-kworldclock-3.5.7.tbz2': [u'unstable', 1], u'foomatic-filters-ppds-20070501.tbz2': [u'unstable', 0], u'libiconv-0.tbz2': [u'unstable', 1], u'audacity-1.3.3.tbz2': [u'unstable', 1], u'jdk-1.5.0.tbz2': [u'unstable', 1], u'ortp-0.7.1-r1.tbz2': [u'unstable', 1], u'mhash-0.9.9-r1.tbz2': [u'unstable', 0], u'inputproto-1.4.2.1.tbz2': [u'unstable', 0], u'xf86-video-dummy-0.2.0.tbz2': [u'unstable', 1], u'bzip2-1.0.4.tbz2': [u'unstable', 1], u'kdeedu-meta-3.5.7.tbz2': [u'unstable', 1], u'kicker-applets-3.5.7.tbz2': [u'unstable', 1], u'libkpimexchange-3.5.7.tbz2': [u'unstable', 1], u'gst-plugins-libvisual-0.10.14.tbz2': [u'unstable', 0], u'cowsay-3.03-r1.tbz2': [u'unstable', 0], u'ktuberling-3.5.7.tbz2': [u'unstable', 1], u'libieee1284-0.2.10.tbz2': [u'unstable', 0], u'commoncpp2-1.5.7.tbz2': [u'unstable', 0], u'aspell-ru-0.99.1.tbz2': [u'unstable', 1], u'libvisual-0.2.0.tbz2': [u'unstable', 1], u'eog-2.18.2.tbz2': [u'unstable', 0], u'libXdamage-1.1.1.tbz2': [u'unstable', 1], u'kpoker-3.5.7.tbz2': [u'unstable', 1], u'sdl-net-1.2.7.tbz2': [u'unstable', 0], u'libXft-2.1.12-r90.tbz2': [u'unstable', 1], u'graphviz-2.12.tbz2': [u'unstable', 1], u'quanta-3.5.7.tbz2': [u'unstable', 1], u'kiten-3.5.7.tbz2': [u'unstable', 1], u'warsow-0.3.2.tbz2': [u'unstable', 0], u'gtk-sharp-1.0.10.tbz2': [u'unstable', 1], u'parted-1.8.8.tbz2': [u'unstable', 0], u'gnome-speech-0.4.16.tbz2': [u'unstable', 0], u'gst-plugins-cdparanoia-0.10.14.tbz2': [u'unstable', 0], u'xineramaproto-1.1.2.tbz2': [u'unstable', 1], u'binutils-2.18.tbz2': [u'unstable', 0], u'deskbar-applet-2.18.1.tbz2': [u'unstable', 1], u'orange-0.3.tbz2': [u'unstable', 1], u'xfontsel-1.0.2.tbz2': [u'unstable', 1], u'emul-linux-x86-java-1.6.0.02.tbz2': [u'unstable', 0], u'rgb-1.0.1.tbz2': [u'unstable', 1], u'nm-applet-0.6.5-r1.tbz2': [u'unstable', 1], u'xinit-1.0.5-r1.tbz2': [u'unstable', 0], u'distcc-2.18.3-r10.tbz2': [u'unstable', 1], u'kbproto-1.0.3.tbz2': [u'unstable', 1], u'fusion-icon-9999.tbz2': [u'unstable', 1], u'PlRPC-0.2020-r1.tbz2': [u'unstable', 0], u'aspell-br-0.50.2.tbz2': [u'unstable', 1], u'gst-plugins-ffmpeg-0.10.2.tbz2': [u'unstable', 1], u'xf86-video-nsc-2.8.3.tbz2': [u'unstable', 0], u'automake-wrapper-3-r1.tbz2': [u'unstable', 1], u'font-bh-75dpi-1.0.0.tbz2': [u'unstable', 1], u'Crypt-SmbHash-0.12.tbz2': [u'unstable', 1], u'kdelibs-3.5.7-r10.tbz2': [u'unstable', 1], u'setxkbmap-1.0.4.tbz2': [u'unstable', 0], u'ksmserver-3.5.7.tbz2': [u'unstable', 1], u'kedit-3.5.7.tbz2': [u'unstable', 1], u'scim-1.4.7.tbz2': [u'unstable', 0], u'wget-1.10.2.tbz2': [u'unstable', 1], u'ntfs3g-1.826.tbz2': [u'unstable', 0], u'xgamma-1.0.2.tbz2': [u'unstable', 0], u'kjumpingcube-3.5.7.tbz2': [u'unstable', 1], u'mmpython-0.4.10.tbz2': [u'unstable', 1], u'libol-0.3.18.tbz2': [u'unstable', 1], u'netpbm-10.39.0.tbz2': [u'unstable', 0], u'openssh-4.7_p1-r1.tbz2': [u'unstable', 0], u'urlgrabber-3.0.0.tbz2': [u'unstable', 1], u'pam_ldap-183.tbz2': [u'unstable', 1], u'laptop-mode-tools-1.34.tbz2': [u'unstable', 0], u'apr-1.2.11.tbz2': [u'unstable', 2], u'kmouth-3.5.7.tbz2': [u'unstable', 1], u'pyparted-1.8.9.tbz2': [u'unstable', 0], u'keychain-2.6.8.tbz2': [u'unstable', 1], u'scim-m17n-0.2.2.tbz2': [u'unstable', 1], u'libgnome-2.18.0.tbz2': [u'unstable', 1], u'ipod-sharp-0.6.3.tbz2': [u'unstable', 0], u'xf86-video-cyrix-1.1.0.tbz2': [u'unstable', 1], u'c-ares-1.4.0.tbz2': [u'unstable', 0], u'aspell-is-0.51.1.0.tbz2': [u'unstable', 1], u'gscanbus-0.7.1.tbz2': [u'unstable', 1], u'dmxproto-2.2.2.tbz2': [u'unstable', 1], u'lame-3.97-r1.tbz2': [u'unstable', 0], u'ocrad-0.15.tbz2': [u'unstable', 1], u'libpixman-0.1.6.tbz2': [u'unstable', 1], u'enblend-3.0.tbz2': [u'unstable', 0], u'azureus-2.5.0.4-r1.tbz2': [u'unstable', 1], u'libdts-0.0.2-r5.tbz2': [u'unstable', 1], u'klamav-0.41.tbz2': [u'unstable', 1], u'eselect-emacs-1.2.tbz2': [u'unstable', 0], u'aspell-pl-6.0.20061121.0.tbz2': [u'unstable', 0], u'libXtst-1.0.3.tbz2': [u'unstable', 0], u'gnome-cups-manager-0.31-r2.tbz2': [u'unstable', 1], u'libXres-1.0.3.tbz2': [u'unstable', 1], u'gnome-applets-2.18.0-r2.tbz2': [u'unstable', 0], u'xf86-input-void-1.1.1.tbz2': [u'unstable', 0], u'liblazy-0.1.tbz2': [u'unstable', 1], u'setuptools-0.6_rc6.tbz2': [u'unstable', 0], u'nano-2.0.6.tbz2': [u'unstable', 0], u'evieext-1.0.2.tbz2': [u'unstable', 1], u'ktorrent-2.2.2.tbz2': [u'unstable', 0], u'gtk2-perl-1.145.tbz2': [u'unstable', 0], u'lcms-1.17.tbz2': [u'unstable', 0], u'pcmcia-2.6.13.tbz2': [u'unstable', 1], u'nvidia-settings-1.0.20070621.tbz2': [u'unstable', 0], u'kftpgrabber-0.8.1-r1.tbz2': [u'unstable', 0], u'font-adobe-100dpi-1.0.0.tbz2': [u'unstable', 1], u'librsvg-2.16.1-r2.tbz2': [u'unstable', 0], u'xf86-video-vmware-10.15.0.tbz2': [u'unstable', 1], u'emul-linux-x86-medialibs-10.2.tbz2': [u'unstable', 1], u'man-pages-ja-20070515.tbz2': [u'unstable', 0], u'powersave-0.14.0.tbz2': [u'unstable', 0], u'gst-plugins-xvideo-0.10.14.tbz2': [u'unstable', 0], u'rescan-scsi-bus-1.25.tbz2': [u'unstable', 0], u'kxkb-3.5.7.tbz2': [u'unstable', 1], u'aspell-uk-1.4.0.0.tbz2': [u'unstable', 0], u'kgamma-3.5.7.tbz2': [u'unstable', 1], u'init-0.tbz2': [u'unstable', 1], u'pam_pwdfile-0.99.tbz2': [u'unstable', 1], u'gnomevfs-sharp-2.16.0.tbz2': [u'unstable', 1], u'texi2html-1.76.tbz2': [u'unstable', 1], u'reswrap-3.2.0.tbz2': [u'unstable', 1], u'bluez-bluefw-1.0.tbz2': [u'unstable', 1], u'debianutils-2.23.1.tbz2': [u'unstable', 0], u'kdeartwork-kwin-styles-3.5.7.tbz2': [u'unstable', 1], u'glproto-1.4.8.tbz2': [u'unstable', 3], u'libcdio-0.78.2.tbz2': [u'unstable', 1], u'sane-backends-1.0.18-r4.tbz2': [u'unstable', 0], u'git-1.5.3.tbz2': [u'unstable', 0], u'alsa-firmware-1.0.14.tbz2': [u'unstable', 0], u'avalon-logkit-1.2-r2.tbz2': [u'unstable', 1], u'kdegraphics-meta-3.5.7.tbz2': [u'unstable', 1], u'xf86-video-tga-1.1.0.tbz2': [u'unstable', 1], u'libwpd-0.8.10.tbz2': [u'unstable', 0], u'soappy-0.12.0.tbz2': [u'unstable', 1], u'rhythmbox-0.10.1.tbz2': [u'unstable', 0], u'portage-utils-0.1.28.tbz2': [u'unstable', 0], u'libvorbis-1.2.0.tbz2': [u'unstable', 0], u'xextproto-7.0.2.tbz2': [u'unstable', 1], u'module-build-0.28.08.tbz2': [u'unstable', 0], u'secpolicy-3.5.6.tbz2': [u'unstable', 1], u'unionfs-utils-0.1.tbz2': [u'unstable', 1], u'jre-1.6.0.tbz2': [u'unstable', 1], u'ktip-3.5.7.tbz2': [u'unstable', 1], u'xinetd-2.3.14.tbz2': [u'unstable', 0], u'bind-tools-9.4.1_p1.tbz2': [u'unstable', 0], u'xfs-1.0.4.tbz2': [u'unstable', 1], u'kwalletmanager-3.5.7.tbz2': [u'unstable', 1], u'kitchensync-3.5.7.tbz2': [u'unstable', 1], u'kmines-3.5.7.tbz2': [u'unstable', 1], u'xf86-video-v4l-0.1.1.tbz2': [u'unstable', 1], u'xscreensaver-5.03.tbz2': [u'unstable', 0], u'encodings-1.0.2.tbz2': [u'unstable', 1], u'xev-1.0.2.tbz2': [u'unstable', 1], u'portmap-6.0.tbz2': [u'unstable', 0], u'kochi-substitute-20030809-r3.tbz2': [u'unstable', 1], u'icon-naming-utils-0.8.2-r1.tbz2': [u'unstable', 0], u'raidutils-0.0.6-r2.tbz2': [u'unstable', 1], u'wesnoth-1.2.6.tbz2': [u'unstable', 0], u'docbook-xml-simple-dtd-4.1.2.4-r2.tbz2': [u'unstable', 1], u'xfsdump-2.2.45.tbz2': [u'unstable', 0], u'Geography-Countries-1.4.tbz2': [u'unstable', 1], u'xrefresh-1.0.2.tbz2': [u'unstable', 1], u'gtkspell-2.0.11-r1.tbz2': [u'unstable', 1], u'xhost-1.0.2.tbz2': [u'unstable', 0], u'STLport-5.1.2.tbz2': [u'unstable', 1], u'gsf-sharp-0.8.tbz2': [u'unstable', 1], u'perl-File-Temp-0.18.tbz2': [u'unstable', 0], u'libXxf86misc-1.0.1.tbz2': [u'unstable', 1], u'libgpg-error-1.5.tbz2': [u'unstable', 1], u'sablotron-1.0.3.tbz2': [u'unstable', 1], u'automake-1.6.3.tbz2': [u'unstable', 1], u'fuse-2.7.0.tbz2': [u'unstable', 0], u'dd-rescue-1.12.tbz2': [u'unstable', 1], u'libgpod-0.5.2.tbz2': [u'unstable', 0], u'ffmpeg-0.4.9_p20070616-r1.tbz2': [u'unstable', 0], u'gnome-mag-0.14.6.tbz2': [u'unstable', 0], u'xcmiscproto-1.1.2.tbz2': [u'unstable', 1], u'IO-Compress-Base-2.005.tbz2': [u'unstable', 0], u'kdemultimedia-kappfinder-data-3.5.7.tbz2': [u'unstable', 1], u'myspell-ga-20060316.tbz2': [u'unstable', 1], u'pinentry-0.7.3.tbz2': [u'unstable', 0], u'readline-5.2_p7.tbz2': [u'unstable', 0], u'less-406.tbz2': [u'unstable', 0], u'konqueror-3.5.7-r2.tbz2': [u'unstable', 0], u'jre-1.5.0.tbz2': [u'unstable', 1], u'ktnef-3.5.7.tbz2': [u'unstable', 1], u'man-pages-es-1.55-r1.tbz2': [u'unstable', 1], u'djvu-3.5.19-r1.tbz2': [u'unstable', 0], u'xeyes-1.0.1.tbz2': [u'unstable', 1], u'gdb-6.6-r2.tbz2': [u'unstable', 1], u'sdl-image-1.2.6.tbz2': [u'unstable', 0], u'sun-javamail-1.4.tbz2': [u'unstable', 1], u'kde-meta-3.5.7.tbz2': [u'unstable', 1], u'compiz-fusion-plugins-extra-0.5.2.tbz2': [u'unstable', 1], u'timezone-data-2007g.tbz2': [u'unstable', 0], u'compizconfig-backend-gconf-0.5.2.tbz2': [u'unstable', 1], u'linux-atm-2.4.1-r2.tbz2': [u'unstable', 1], u'libart_lgpl-2.3.19-r1.tbz2': [u'unstable', 1], u'libsoup-2.2.100.tbz2': [u'unstable', 1], u'kdeadmin-meta-3.5.7.tbz2': [u'unstable', 1], u'gnome-common-2.12.0.tbz2': [u'unstable', 1], u'lisa-3.5.7.tbz2': [u'unstable', 1], u'perl-Time-HiRes-1.97.07.tbz2': [u'unstable', 1], u'libXau-1.0.3.tbz2': [u'unstable', 1], u'monodoc-1.2.5.tbz2': [u'unstable', 0], u'ekiga-2.0.9.tbz2': [u'unstable', 0], u'jfsutils-1.1.12.tbz2': [u'unstable', 0], u'gst-plugins-sidplay-0.10.6.tbz2': [u'unstable', 0], u'pyrex-0.9.5.1a.tbz2': [u'unstable', 1], u'prism54-firmware-1.0.4.3.tbz2': [u'unstable', 1], u'librss-3.5.6.tbz2': [u'unstable', 1], u'libXt-1.0.5.tbz2': [u'unstable', 1], u'automake-1.10.tbz2': [u'unstable', 1], u'xjavac-20041208-r5.tbz2': [u'unstable', 0], u'bdftopcf-1.0.0.tbz2': [u'unstable', 1], u'telnet-bsd-1.2-r1.tbz2': [u'unstable', 1], u'gst-plugins-faad-0.10.5.tbz2': [u'unstable', 0], u'findutils-4.3.8-r1.tbz2': [u'unstable', 0], u'pycrypto-2.0.1-r6.tbz2': [u'unstable', 1], u'libgksu-2.0.5.tbz2': [u'unstable', 1], u'xf86-input-evdev-1.1.5-r1.tbz2': [u'unstable', 1], u'rp-pppoe-3.8-r1.tbz2': [u'unstable', 1], u'smplayer-0.5.59.tbz2': [u'unstable', 0], u'pax-utils-0.1.16.tbz2': [u'unstable', 0], u'libFS-1.0.0.tbz2': [u'unstable', 1], u'ant-core-1.7.0.tbz2': [u'unstable', 1], u't1lib-5.0.2.tbz2': [u'unstable', 1], u'libpaper-1.1.21.tbz2': [u'unstable', 1], u'ipw3945d-1.7.22-r10.tbz2': [u'unstable', 1], u'gnome-menus-2.18.3.tbz2': [u'unstable', 0], u'libiec61883-1.1.0.tbz2': [u'unstable', 1], u'kontact-specialdates-3.5.7.tbz2': [u'unstable', 1], u'slang-1.4.9-r2.tbz2': [u'unstable', 1], u'gst-plugins-musepack-0.10.5.tbz2': [u'unstable', 0], u'liblo-0.23.tbz2': [u'unstable', 1], u'kdeartwork-meta-3.5.7.tbz2': [u'unstable', 1], u'libnjb-2.2.5-r1.tbz2': [u'unstable', 0], u'xine-lib-1.1.8.tbz2': [u'unstable', 0], u'madwifi-ng-0.9.4-t2.6.22_sabayon.tbz2': [u'unstable', 1], u'gnome-vfsmm-2.18.0.tbz2': [u'unstable', 1], u'bio2jack-0.7.tbz2': [u'unstable', 1], u'gnome2-user-docs-2.18.2.tbz2': [u'unstable', 0], u'libksba-1.0.2.tbz2': [u'unstable', 0], u'openh323-1.18.0-r1.tbz2': [u'unstable', 1], u'networkmanager-vpnc-0.7.0.tbz2': [u'unstable', 1], u'wvdial-1.60.tbz2': [u'unstable', 0], u'gst-plugins-lame-0.10.6.tbz2': [u'unstable', 0], u'glib-perl-1.144.tbz2': [u'unstable', 1], u'kdepim-wizards-3.5.7.tbz2': [u'unstable', 1], u'HTML-Tree-3.23.tbz2': [u'unstable', 1], u'boost-build-1.34.1.tbz2': [u'unstable', 0], u'autoconf-2.13.tbz2': [u'unstable', 1], u'bcel-5.2.tbz2': [u'unstable', 1], u'Convert-ASN1-0.21.tbz2': [u'unstable', 1], u'docbook-xml-dtd-4.1.2-r6.tbz2': [u'unstable', 1], u'kscreensaver-3.5.7.tbz2': [u'unstable', 1], u'libdv-1.0.0-r2.tbz2': [u'unstable', 1], u'linuxtv-dvb-headers-3.1.tbz2': [u'unstable', 1], u'gpgme-1.1.5.tbz2': [u'unstable', 1], u'portatosourceview-2.16.1.tbz2': [u'unstable', 1], u'xf86-input-summa-1.1.0.tbz2': [u'unstable', 1], u'etcproposals-1.3.tbz2': [u'unstable', 1], u'libintl-0.tbz2': [u'unstable', 1], u'compiz-0.5.2.tbz2': [u'unstable', 1], u'cmake-2.4.7-r1.tbz2': [u'unstable', 0], u'libotf-0.9.6.tbz2': [u'unstable', 0], u'kdemultimedia-arts-3.5.7.tbz2': [u'unstable', 1], u'AnyEvent-2.5.3.tbz2': [u'unstable', 0], u'xf86-video-apm-1.1.1.tbz2': [u'unstable', 1], u'emul-linux-x86-xlibs-10.1.tbz2': [u'unstable', 0], u'icu-3.6-r1.tbz2': [u'unstable', 0], u'openjade-1.3.2-r1.tbz2': [u'unstable', 1], u'khangman-3.5.7.tbz2': [u'unstable', 1], u'soundkonverter-0.3.4.tbz2': [u'unstable', 0], u'iwidgets-4.0.1-r1.tbz2': [u'unstable', 0], u'gimp-print-4.2.7.tbz2': [u'unstable', 1], u'xv-3.10a-r14.tbz2': [u'unstable', 0], u'xf86-input-spaceorb-1.1.1.tbz2': [u'unstable', 0], u'evilred-0.2.tbz2': [u'unstable', 1], u'pommed-1.8.tbz2': [u'unstable', 0], u'xf86-video-i810-2.1.1.tbz2': [u'unstable', 0], u'lsdvd-0.16.tbz2': [u'unstable', 1], u'krdc-3.5.7.tbz2': [u'unstable', 1], u'xf86-input-magictouch-1.0.0.5.tbz2': [u'unstable', 1], u'libdaemon-0.12.tbz2': [u'unstable', 1], u'xf86-input-dynapro-1.1.1.tbz2': [u'unstable', 0], u'sun-jms-1.1-r2.tbz2': [u'unstable', 1], u'libcroco-0.6.1.tbz2': [u'unstable', 1], u'libmovtar-0.1.3-r1.tbz2': [u'unstable', 1], u'libgda-1.2.4.tbz2': [u'unstable', 1], u'x264-svn-20070325.tbz2': [u'unstable', 1], u'luit-1.0.2.tbz2': [u'unstable', 1], u'gd-2.0.35.tbz2': [u'unstable', 0], u'psutils-1.17.tbz2': [u'unstable', 1], u'zopeinterface-3.0.1-r1.tbz2': [u'unstable', 1], u'certmanager-3.5.7-r1.tbz2': [u'unstable', 0], u'perl-libnet-1.21.tbz2': [u'unstable', 0], u'gtkhtml-sharp-2.16.0.tbz2': [u'unstable', 1], u'libfontenc-1.0.4.tbz2': [u'unstable', 1], u'synce-librapi2-0.9.1.tbz2': [u'unstable', 1], u'Archive-Zip-1.20.tbz2': [u'unstable', 0], u'notification-daemon-0.3.7.tbz2': [u'unstable', 1], u'm17n-db-1.3.4.tbz2': [u'unstable', 1], u'libgnomemm-2.0.1.tbz2': [u'unstable', 1], u'tar-1.18-r2.tbz2': [u'unstable', 0], u'kommander-3.5.7.tbz2': [u'unstable', 1], u'Text-Iconv-1.4.tbz2': [u'unstable', 1], u'libnotify-0.4.4.tbz2': [u'unstable', 1], u'kdenetwork-filesharing-3.5.7.tbz2': [u'unstable', 1], u'docbook-xml-dtd-4.3-r1.tbz2': [u'unstable', 1], u'ssmtp-2.61-r2.tbz2': [u'unstable', 1], u'edb-1.0.5.007.tbz2': [u'unstable', 1], u'et131x-1.2.3-r1-t2.6.22_sabayon.tbz2': [u'unstable', 1], u'bsf-2.4.0-r1.tbz2': [u'unstable', 0], u'aspell-sv-0.51.0.tbz2': [u'unstable', 1], u'ddcxinfo-knoppix-bin-0.6.tbz2': [u'unstable', 1], u'alsa-headers-1.0.14.tbz2': [u'unstable', 0], u'font-ibm-type1-1.0.0.tbz2': [u'unstable', 1], u'attr-2.4.38.tbz2': [u'unstable', 0], u'Parse-Yapp-1.05-r1.tbz2': [u'unstable', 1], u'libquicktime-1.0.0.tbz2': [u'unstable', 1], u'esound-0.2.38-r1.tbz2': [u'unstable', 0], u'ccsm-0.5.2.tbz2': [u'unstable', 1], u'vixie-cron-4.1-r10.tbz2': [u'unstable', 1], u'rt73-firmware-1.8.tbz2': [u'unstable', 1], u'bc-1.06.95.tbz2': [u'unstable', 1], u'libkdenetwork-3.5.7.tbz2': [u'unstable', 1], u'equo-9999-r3.tbz2': [u'unstable', 0], u'pigment-0.1.5.tbz2': [u'unstable', 1], u'mutagen-1.12.tbz2': [u'unstable', 0], u'gst-plugins-dv-0.10.6.tbz2': [u'unstable', 0], u'man-pages-2.64.tbz2': [u'unstable', 0], u'libertas-firmware-5.220.10.tbz2': [u'unstable', 1], u'alsa-tools-1.0.14.tbz2': [u'unstable', 0], u'xf86-video-ati-6.6.3.tbz2': [u'unstable', 1], u'libgnomemm-2.18.0.tbz2': [u'unstable', 1], u'Text-Glob-0.08.tbz2': [u'unstable', 0], u'glew-1.3.5.tbz2': [u'unstable', 0], u'konquest-3.5.7.tbz2': [u'unstable', 1], u'sessreg-1.0.3.tbz2': [u'unstable', 0], u'libmp4v2-1.5.0.1.tbz2': [u'unstable', 1], u'twisted-web-0.7.0.tbz2': [u'unstable', 1], u'dmidecode-2.9.tbz2': [u'unstable', 1], u'networkstatus-3.5.7.tbz2': [u'unstable', 1], u'kmplot-3.5.7.tbz2': [u'unstable', 1], u'alacarte-0.11.3-r1.tbz2': [u'unstable', 0], u'tcmplex-panteltje-0.4.7.tbz2': [u'unstable', 1], u'kmag-3.5.7.tbz2': [u'unstable', 1], u'mono-tools-1.2.4.tbz2': [u'unstable', 0], u'libXinerama-1.0.2.tbz2': [u'unstable', 1], u'rt61-firmware-1.2.tbz2': [u'unstable', 1], u'kopete-3.5.7-r1.tbz2': [u'unstable', 0], u'ifplugd-0.28-r8.tbz2': [u'unstable', 1], u'gtkhtml-3.12.3.tbz2': [u'unstable', 1], u'docbook-xml-simple-dtd-1.0-r1.tbz2': [u'unstable', 1], u'taglib-1.4-r1.tbz2': [u'unstable', 1], u'kdemultimedia-kfile-plugins-3.5.7.tbz2': [u'unstable', 1], u'pyopengl-2.0.1.09-r1.tbz2': [u'unstable', 1], u'libnl-1.0_pre6.tbz2': [u'unstable', 1], u'xf86-video-fbdev-0.3.1.tbz2': [u'unstable', 1], u'freetype-1.3.1-r5.tbz2': [u'unstable', 1], u'sg3_utils-1.24.tbz2': [u'unstable', 0], u'ncompress-4.2.4.2.tbz2': [u'unstable', 0], u'aalib-1.4_rc5.tbz2': [u'unstable', 1], u'autotrace-0.31.1-r2.tbz2': [u'unstable', 0], u'libtheora-1.0_alpha7-r1.tbz2': [u'unstable', 0], u'xdg-utils-1.0.2.tbz2': [u'unstable', 0], u'pyopenssl-0.6-r1.tbz2': [u'unstable', 1], u'Coherence-0.2.1.tbz2': [u'unstable', 1], u'newt-0.52.2.tbz2': [u'unstable', 1], u'airsnort-0.2.7e.tbz2': [u'unstable', 1], u'xf86-video-neomagic-1.1.1.tbz2': [u'unstable', 1], u'font-adobe-utopia-100dpi-1.0.1.tbz2': [u'unstable', 1], u'xsetpointer-1.0.1.tbz2': [u'unstable', 1], u'sandbox-1.2.18.1.tbz2': [u'unstable', 1], u'kiconedit-3.5.7.tbz2': [u'unstable', 1], u'po4a-0.32-r1.tbz2': [u'unstable', 0], u'apr-0.9.12.tbz2': [u'unstable', 1], u'evolution-2.10.3.tbz2': [u'unstable', 0], u'id3lib-3.8.3-r6.tbz2': [u'unstable', 0], u'file-4.21-r1.tbz2': [u'unstable', 0], u'kwordquiz-3.5.7.tbz2': [u'unstable', 1], u'gnome-screensaver-2.18.2-r1.tbz2': [u'unstable', 0], u'e2fsprogs-1.40.2-r10.tbz2': [u'unstable', 1], u'cpufrequtils-002-r3.tbz2': [u'unstable', 0], u'elisa-0.1.6-r1.tbz2': [u'unstable', 1], u'libIDL-0.8.8.tbz2': [u'unstable', 1], u'libxcb-1.0.tbz2': [u'unstable', 0], u'chillispot-1.1.0.tbz2': [u'unstable', 0], u'konq-plugins-3.5.7.tbz2': [u'unstable', 1], u'filezilla-3.0.0.tbz2': [u'unstable', 0], u'aspell-fi-0.7.0.tbz2': [u'unstable', 1], u'pwgen-2.05.tbz2': [u'unstable', 1], u'knode-3.5.7.tbz2': [u'unstable', 1], u'jbigkit-1.6-r1.tbz2': [u'unstable', 1], u'nasm-0.98.39-r3.tbz2': [u'unstable', 1], u'sharutils-4.6.3.tbz2': [u'unstable', 1], u'perl-Scalar-List-Utils-1.19.tbz2': [u'unstable', 1], u'libutempter-1.1.5.tbz2': [u'unstable', 1], u'ubuntulooks-0.9.12.tbz2': [u'unstable', 1], u'kdeaddons-meta-3.5.7.tbz2': [u'unstable', 1], u'xf86bigfontproto-1.1.2.tbz2': [u'unstable', 1], u'libbonobo-2.18.0.tbz2': [u'unstable', 1], u'kviewshell-3.5.7.tbz2': [u'unstable', 1], u'kdnssd-avahi-0.1.2.tbz2': [u'unstable', 1], u'gnupg-2.0.6.tbz2': [u'unstable', 0], u'libgsf-1.14.6.tbz2': [u'unstable', 0], u'scrnsaverproto-1.1.0.tbz2': [u'unstable', 1], u'gst-plugins-ximagesrc-0.10.6.tbz2': [u'unstable', 0], u'gst-plugins-mad-0.10.6.tbz2': [u'unstable', 0], u'kdeartwork-icewm-themes-3.5.7.tbz2': [u'unstable', 1], u'mc-4.6.1-r4.tbz2': [u'unstable', 0], u'wpa_supplicant-0.5.8.tbz2': [u'unstable', 0], u'Class-Singleton-1.03.tbz2': [u'unstable', 1], u'libao-pulse-0.9.3.tbz2': [u'unstable', 1], u'libmcrypt-2.5.8.tbz2': [u'unstable', 0], u'drkonqi-3.5.7.tbz2': [u'unstable', 1], u'imake-1.0.2.tbz2': [u'unstable', 1], u'gst-plugins-x-0.10.14.tbz2': [u'unstable', 0], u'kdenetwork-meta-3.5.7.tbz2': [u'unstable', 1], u'libglademm-2.0.1.tbz2': [u'unstable', 1], u'manencode-1.0.tbz2': [u'unstable', 0], u'kdeartwork-kscreensaver-3.5.7.tbz2': [u'unstable', 1], u'kdegraphics-kfile-plugins-3.5.7.tbz2': [u'unstable', 1], u'wvstreams-4.4.tbz2': [u'unstable', 0], u'gamin-0.1.9.tbz2': [u'unstable', 0], u'libmad-0.15.1b-r4.tbz2': [u'unstable', 0], u'culmus-0.101-r1.tbz2': [u'unstable', 1], u'audiofile-0.2.6-r3.tbz2': [u'unstable', 1], u'Digest-SHA1-2.11.tbz2': [u'unstable', 1], u'libglade-2.6.1.tbz2': [u'unstable', 0], u'digikam-0.9.2.tbz2': [u'unstable', 0], u'HTML-Parser-3.56.tbz2': [u'unstable', 1], u'ncftp-3.2.0.tbz2': [u'unstable', 1], u'nvidia-drivers-100.14.19-r10-t2.6.22_sabayon.tbz2': [u'unstable', 0], u'hplip-2.7.7-r2.tbz2': [u'unstable', 0], u'xf86-video-glint-1.1.1.tbz2': [u'unstable', 1], u'man-pages-it-2.43.tbz2': [u'unstable', 1], u'mt-st-0.9b.tbz2': [u'unstable', 1], u'XML-SAX-Writer-0.50.tbz2': [u'unstable', 1], u'libxklavier-3.2.tbz2': [u'unstable', 0], u'openslp-1.2.1-r1.tbz2': [u'unstable', 0], u'lzo-2.02-r1.tbz2': [u'unstable', 3], u'xine-ui-0.99.5.tbz2': [u'unstable', 0], u'bash-3.2_p17-r1.tbz2': [u'unstable', 0], u'qt-3.3.8-r3.tbz2': [u'unstable', 0], u'Sys-Syslog-0.18.tbz2': [u'unstable', 1], u'eselect-oodict-20061117.tbz2': [u'unstable', 1], u'font-screen-cyrillic-1.0.1.tbz2': [u'unstable', 1], u'automake-1.7.9-r1.tbz2': [u'unstable', 1], u'DateTime-0.39.tbz2': [u'unstable', 0], u'libtar-1.2.11-r1.tbz2': [u'unstable', 1], u'hwinfo-13.28.tbz2': [u'unstable', 0], u'IO-Compress-Zlib-2.005.tbz2': [u'unstable', 0], u'gpu-detector-1.9.9.tbz2': [u'unstable', 1], u'enscript-1.6.4-r3.tbz2': [u'unstable', 1], u'wine-doors-0.1.tbz2': [u'unstable', 1], u'swig-1.3.31.tbz2': [u'unstable', 1], u'libXScrnSaver-1.1.2.tbz2': [u'unstable', 1], u'java-config-1.3.7.tbz2': [u'unstable', 1], u'nexuiz-2.3.tbz2': [u'unstable', 1], u'font-sony-misc-1.0.0.tbz2': [u'unstable', 1], u'sgml-common-0.6.3-r5.tbz2': [u'unstable', 1], u'libsigc++-2.0.17.tbz2': [u'unstable', 3], u'gstreamer-0.10.14.tbz2': [u'unstable', 0], u'lightscribe-simplelabeler-1.4.128.1.tbz2': [u'unstable', 1], u'netkit-fingerd-0.17-r3.tbz2': [u'unstable', 1], u'libkmime-3.5.7.tbz2': [u'unstable', 1], u'xf86-video-sisusb-0.8.1.tbz2': [u'unstable', 1], u'kregexpeditor-3.5.7.tbz2': [u'unstable', 1], u'libgnomecanvasmm-2.16.0.tbz2': [u'unstable', 1], u'inkscape-0.45.1.tbz2': [u'unstable', 1], u'wireless-tools-29_pre22.tbz2': [u'unstable', 0], u'syslog-ng-2.0.5.tbz2': [u'unstable', 0], u'gnome-keyring-manager-2.18.0.tbz2': [u'unstable', 1], u'libtool-1.5.24.tbz2': [u'unstable', 0], u'DBD-SQLite-1.13.tbz2': [u'unstable', 1], u'ksysguard-3.5.7.tbz2': [u'unstable', 1], u'xf86dga-1.0.2.tbz2': [u'unstable', 1], u'libkscan-3.5.7.tbz2': [u'unstable', 1], u'digest-base-1.15.tbz2': [u'unstable', 1], u'simgear-0.3.10.tbz2': [u'unstable', 1], u'gtk+-2.10.14.tbz2': [u'unstable', 0], u'portage-2.1.3.9.tbz2': [u'unstable', 1], u'Text-CharWidth-0.04.tbz2': [u'unstable', 1], u'libtasn1-1.1.tbz2': [u'unstable', 0], u'xtrans-1.0.4.tbz2': [u'unstable', 0], u'mailx-8.1.2.20050715-r1.tbz2': [u'unstable', 1], u'language-configuration-helpers-1.2.0.tbz2': [u'unstable', 1], u'xloadimage-4.1-r5.tbz2': [u'unstable', 0], u'tk-8.4.15.tbz2': [u'unstable', 0], u'murrine-0.10.tbz2': [u'unstable', 1], u'commons-cli-1.0-r5.tbz2': [u'unstable', 1], u'mbrola-3.0.1h-r4.tbz2': [u'unstable', 1], u'libXmu-1.0.3.tbz2': [u'unstable', 1], u'ettercap-0.7.3-r2.tbz2': [u'unstable', 1], u'kfouleggs-3.5.7.tbz2': [u'unstable', 1], u'nucleo-0.6-r2.tbz2': [u'unstable', 1], u'virt-manager-0.5.0.tbz2': [u'unstable', 0], u'dcraw-8.73.tbz2': [u'unstable', 0], u'kbd-1.13-r1.tbz2': [u'unstable', 0], u'gst-plugins-ogg-0.10.14.tbz2': [u'unstable', 0], u'xvkbd-2.8.tbz2': [u'unstable', 1], u'patch-2.5.9-r1.tbz2': [u'unstable', 1], u'pidgin-2.1.1.tbz2': [u'unstable', 0], u'which-2.16.tbz2': [u'unstable', 1], u'libXi-1.1.3.tbz2': [u'unstable', 0], u'kppp-3.5.7.tbz2': [u'unstable', 1], u'servletapi-2.3-r3.tbz2': [u'unstable', 1], u'jakarta-regexp-1.3-r4.tbz2': [u'unstable', 1], u'kdeutils-meta-3.5.7.tbz2': [u'unstable', 1], u'gnome-terminal-2.18.1.tbz2': [u'unstable', 0], u'cryptsetup-luks-1.0.4-r3.tbz2': [u'unstable', 1], u'libipoddevice-0.5.3.tbz2': [u'unstable', 0], u'f-spot-0.4.0.tbz2': [u'unstable', 0], u'libreadline-java-0.8.0-r2.tbz2': [u'unstable', 1], u'kmrml-3.5.7.tbz2': [u'unstable', 1], u'liblrdf-0.4.0.tbz2': [u'unstable', 1], u'XML-LibXML-Common-0.13.tbz2': [u'unstable', 1], u'traceroute-2.0.8-r2.tbz2': [u'unstable', 0], u'libao-0.8.6-r3.tbz2': [u'unstable', 1], u'libkipi-0.1.5.tbz2': [u'unstable', 1], u'truecrypt-4.3a-t2.6.22_sabayon.tbz2': [u'unstable', 0], u'xf86-video-s3virge-1.9.1.tbz2': [u'unstable', 1], u'automake-1.8.5-r3.tbz2': [u'unstable', 1], u'nevow-0.9.0.tbz2': [u'unstable', 1], u'a52dec-0.7.4-r5.tbz2': [u'unstable', 1], u'povray-3.6.1-r2.tbz2': [u'unstable', 1], u'automake-1.4_p6.tbz2': [u'unstable', 1], u'libpcap-0.9.7.tbz2': [u'unstable', 0], u'kpowersave-0.6.2.tbz2': [u'unstable', 0], u'xdialog-2.3.1.tbz2': [u'unstable', 1], u'font-alias-1.0.1.tbz2': [u'unstable', 1], u'gnome-system-monitor-2.18.2.tbz2': [u'unstable', 0], u'ghostscript-esp-8.15.4.tbz2': [u'unstable', 1], u'sysvinit-2.86-r9.tbz2': [u'unstable', 0], u'manslide-1.7.1.tbz2': [u'unstable', 0], u'ipw3945-ucode-1.14.2.tbz2': [u'unstable', 1], u'swh-plugins-0.4.15.tbz2': [u'unstable', 0], u'ruby-config-0.3.2.tbz2': [u'unstable', 1], u'cpio-2.9.tbz2': [u'unstable', 0], u'scanssh-2.1.tbz2': [u'unstable', 1], u'kolourpaint-3.5.7.tbz2': [u'unstable', 1], u'libevent-1.3d.tbz2': [u'unstable', 0], u'pulseaudio-0.9.6-r1.tbz2': [u'unstable', 0], u'ExtUtils-CBuilder-0.19.tbz2': [u'unstable', 0], u'libexif-0.6.16.tbz2': [u'unstable', 0], u'help2man-1.36.4.tbz2': [u'unstable', 1], u'IO-Socket-INET6-2.51.tbz2': [u'unstable', 1], u'libcap-1.10-r10.tbz2': [u'unstable', 1], u'lirc-0.8.2-r1.tbz2': [u'unstable', 0], u'wxpython-2.6.3.3.tbz2': [u'unstable', 1], u'linux-wlan-ng-firmware-0.2.2.tbz2': [u'unstable', 1], u'libksieve-3.5.7.tbz2': [u'unstable', 1], u'xauth-1.0.2.tbz2': [u'unstable', 1], u'krec-3.5.7.tbz2': [u'unstable', 1], u'hal-info-20070618.tbz2': [u'unstable', 1], u'hotplug-base-20040401.tbz2': [u'unstable', 1], u'ksame-3.5.7.tbz2': [u'unstable', 1], u'ttmkfdir-3.0.9-r3.tbz2': [u'unstable', 1], u'xorg-x11-7.3.tbz2': [u'unstable', 0], u'sysfsutils-2.1.0.tbz2': [u'unstable', 1], u'Digest-HMAC-1.01-r1.tbz2': [u'unstable', 1], u'glu-7.0.tbz2': [u'unstable', 1], u'gtkmm-2.2.12.tbz2': [u'unstable', 1], u'IO-String-1.08.tbz2': [u'unstable', 1], u'shared-mime-info-0.22.tbz2': [u'unstable', 0], u'kspaceduel-3.5.7.tbz2': [u'unstable', 1], u'urt-3.1b-r1.tbz2': [u'unstable', 1], u'xwud-1.0.1.tbz2': [u'unstable', 1], u'cdparanoia-3.9.8-r5.tbz2': [u'unstable', 1], u'libmpeg3-1.7.tbz2': [u'unstable', 0], u'gnutls-2.0.0.tbz2': [u'unstable', 0], u'kdepim-kioslaves-3.5.7-r1.tbz2': [u'unstable', 0], u'ksig-3.5.7.tbz2': [u'unstable', 1], u'gnome-utils-2.18.1.tbz2': [u'unstable', 1], u'kicker-3.5.7-r13.tbz2': [u'unstable', 0], u'mozilla-launcher-1.56.tbz2': [u'unstable', 1], u'kcalc-3.5.7.tbz2': [u'unstable', 1], u'libsidplay-1.36.59.tbz2': [u'unstable', 0], u'kget-3.5.7.tbz2': [u'unstable', 1], u'pykde-3.16.0-r1.tbz2': [u'unstable', 0], u'scim-qtimm-0.9.4-r1.tbz2': [u'unstable', 0], u'dbus-glib-0.74.tbz2': [u'unstable', 0], u'prism54-usb-firmware-1.0.4.3.tbz2': [u'unstable', 1], u'links-2.1_pre28-r1.tbz2': [u'unstable', 0], u'alsa-lib-1.0.14a-r1.tbz2': [u'unstable', 0], u'sun-jdk-1.5.0.12.tbz2': [u'unstable', 0], u'kooka-3.5.7.tbz2': [u'unstable', 1], u'sox-13.0.0.tbz2': [u'unstable', 1], u'libgnomecanvas-2.14.0.tbz2': [u'unstable', 1], u'libnfsidmap-0.20.tbz2': [u'unstable', 0], u'xf86-video-i128-1.2.1.tbz2': [u'unstable', 1], u'libsigc++-1.2.5.tbz2': [u'unstable', 1], u'kaddressbook-plugins-3.5.7.tbz2': [u'unstable', 1], u'bug-buddy-2.18.1.tbz2': [u'unstable', 1], u'makedepend-1.0.1.tbz2': [u'unstable', 1], u'gst-plugins-vorbis-0.10.14.tbz2': [u'unstable', 0], u'hddtemp-0.3_beta15-r3.tbz2': [u'unstable', 0], u'twolame-0.3.10.tbz2': [u'unstable', 1], u'DateTime-Locale-0.34.tbz2': [u'unstable', 1], u'autoconf-wrapper-4-r3.tbz2': [u'unstable', 1], u'libXprintUtil-1.0.1.tbz2': [u'unstable', 1], u'mpg123-0.65.tbz2': [u'unstable', 1], u'libmikmod-3.1.11-r4.tbz2': [u'unstable', 1], u'kdeadmin-kfile-plugins-3.5.7.tbz2': [u'unstable', 1], u'font-winitzki-cyrillic-1.0.0.tbz2': [u'unstable', 1], u'libsoundtouch-1.3.1-r1.tbz2': [u'unstable', 1], u'khotkeys-3.5.7.tbz2': [u'unstable', 1], u'man-pages-de-0.5.tbz2': [u'unstable', 1], u'libwmf-0.2.8.4.tbz2': [u'unstable', 1], u'libmpcdec-1.2.6.tbz2': [u'unstable', 0], u'xf86rushproto-1.1.2.tbz2': [u'unstable', 1], u'libprojectm-0.99-r1.tbz2': [u'unstable', 1], u'consolekit-0.2.1.tbz2': [u'unstable', 1], u'glib-1.2.10-r5.tbz2': [u'unstable', 1], u'rpm2targz-9.0-r6.tbz2': [u'unstable', 0], u'kdeartwork-iconthemes-3.5.7.tbz2': [u'unstable', 1], u'xf86-video-rendition-4.1.3.tbz2': [u'unstable', 1], u'xf86-input-calcomp-1.1.1.tbz2': [u'unstable', 0], u'kwifimanager-3.5.7.tbz2': [u'unstable', 1], u'sdl-gfx-2.0.16.tbz2': [u'unstable', 1], u'knetattach-3.5.7.tbz2': [u'unstable', 1], u'libXcursor-1.1.9.tbz2': [u'unstable', 0], u'twm-1.0.3.tbz2': [u'unstable', 1], u'ksirc-3.5.7.tbz2': [u'unstable', 1], u'evolution-exchange-2.10.3.tbz2': [u'unstable', 0], u'nfs-utils-1.1.0-r1.tbz2': [u'unstable', 0], u'gst-plugins-oss-0.10.6.tbz2': [u'unstable', 0], u'nss-3.11.7.tbz2': [u'unstable', 0], u'jpeg-6b-r8.tbz2': [u'unstable', 1], u'Time-modules-2006.0814.tbz2': [u'unstable', 1], u'arphicfonts-0.1.20060928.tbz2': [u'unstable', 1], u'com_err-1.40.2.tbz2': [u'unstable', 1], u'renderproto-0.9.3.tbz2': [u'unstable', 0], u'libusb-0.1.12-r1.tbz2': [u'unstable', 1], u'libkdepim-3.5.7-r1.tbz2': [u'unstable', 0], u'sed-4.1.5.tbz2': [u'unstable', 1], u'tsclient-0.148.tbz2': [u'unstable', 1], u'PyQt4-4.3.tbz2': [u'unstable', 0], u'kcheckpass-3.5.7.tbz2': [u'unstable', 0], u'db-4.3.29-r2.tbz2': [u'unstable', 1], u'cksfv-1.3.9.tbz2': [u'unstable', 1], u'speex-1.2_beta2.tbz2': [u'unstable', 0], u'libkexif-0.2.5.tbz2': [u'unstable', 1], u'glib-2.12.13.tbz2': [u'unstable', 0], u'ss-1.40.2.tbz2': [u'unstable', 1], u'pcmciautils-014-r1.tbz2': [u'unstable', 1], u'gnome2-vfs-perl-1.061.tbz2': [u'unstable', 1], u'xf86-input-vmmouse-12.4.2.tbz2': [u'unstable', 0], u'libXfont-1.3.1.tbz2': [u'unstable', 0], u'mingetty-1.07-r1.tbz2': [u'unstable', 1], u'libjingle-0.3.11.tbz2': [u'unstable', 0], u'live-2007.02.20.tbz2': [u'unstable', 1], u'klibc-1.5.tbz2': [u'unstable', 0], u'eventlog-0.2.5.tbz2': [u'unstable', 0], u'bcprov-1.37.tbz2': [u'unstable', 0], u'Unicode-String-2.09.tbz2': [u'unstable', 1], u'udev-115-r1.tbz2': [u'unstable', 1], u'gnome-vfs-2.18.1.tbz2': [u'unstable', 1], u'gst-plugins-pango-0.10.14.tbz2': [u'unstable', 0], u'kpdf-3.5.7-r2.tbz2': [u'unstable', 0], u'gst-plugins-dvdread-0.10.6.tbz2': [u'unstable', 0], u'pam_console-0.99.7.0.2.7-r1.tbz2': [u'unstable', 0], u'gnuconfig-20070724.tbz2': [u'unstable', 0], u'lilo-config-3.5.7.tbz2': [u'unstable', 1], u'libgnomecanvasmm-2.0.1.tbz2': [u'unstable', 1], u'Tie-IxHash-1.21-r1.tbz2': [u'unstable', 1], u'nsplugins-3.5.7.tbz2': [u'unstable', 1], u'imagemagick-6.3.5.tbz2': [u'unstable', 1], u'gconfmm-2.18.0.tbz2': [u'unstable', 1], u'gtksourceview-1.8.5.tbz2': [u'unstable', 1], u'libcddb-1.3.0.tbz2': [u'unstable', 1], u'fftw-3.1.2.tbz2': [u'unstable', 2], u'gtkhtml-3.14.3-r1.tbz2': [u'unstable', 0], u'cairo-1.4.10.tbz2': [u'unstable', 0], u'wv2-0.2.3.tbz2': [u'unstable', 1], u'myspell-eo-20060316.tbz2': [u'unstable', 1], u'kdemultimedia-meta-3.5.7.tbz2': [u'unstable', 1], u'atmel-firmware-1.3.tbz2': [u'unstable', 1], u'libxml2-2.6.29.tbz2': [u'unstable', 0], u'pvr-firmware-20070217.tbz2': [u'unstable', 1], u'kgeography-3.5.7.tbz2': [u'unstable', 1], u'blinken-3.5.7.tbz2': [u'unstable', 1], u'perl-Test-Harness-2.64.tbz2': [u'unstable', 1], u'blackdown-jre-1.4.2.03-r14.tbz2': [u'unstable', 0], u'libperl-5.8.8-r1.tbz2': [u'unstable', 1], u'gnome-keyring-0.8.1.tbz2': [u'unstable', 1], u'lynx-2.8.6-r2.tbz2': [u'unstable', 0], u'hicolor-icon-theme-0.10.tbz2': [u'unstable', 1], u'xkbprint-1.0.1.tbz2': [u'unstable', 1], u'xf86-video-imstt-1.1.0.tbz2': [u'unstable', 1], u'hotplug-20040923-r2.tbz2': [u'unstable', 1], u'docbook2X-0.8.8.tbz2': [u'unstable', 0], u'libdvdread-0.9.7.tbz2': [u'unstable', 1], u'k9copy-1.1.3.tbz2': [u'unstable', 0], u'proftpd-1.3.1_rc3.tbz2': [u'unstable', 0], u'loudmouth-1.2.3.tbz2': [u'unstable', 0], u'netscape-flash-9.0.48.0-r1.tbz2': [u'unstable', 0], u'xml-commons-external-1.3.04.tbz2': [u'unstable', 1], u'gok-1.2.5.tbz2': [u'unstable', 0], u'dhcp-3.1.0.tbz2': [u'unstable', 0], u'imaging-1.1.6.tbz2': [u'unstable', 1], u'gcc-config-1.4.0-r2.tbz2': [u'unstable', 0], u'vte-0.16.8.tbz2': [u'unstable', 0], u'iputils-20070202.tbz2': [u'unstable', 1], u'xvid-1.1.3.tbz2': [u'unstable', 0], u'sysinfo-1.8.2.tbz2': [u'unstable', 1], u'liblbxutil-1.0.1.tbz2': [u'unstable', 1], u'gtkglarea-1.2.3-r1.tbz2': [u'unstable', 1], u'nuvola-1.0-r1.tbz2': [u'unstable', 1], u'mesa-progs-7.0.1.tbz2': [u'unstable', 0], u'notify-python-0.1.1.tbz2': [u'unstable', 0], u'dietlibc-0.31_pre20070612.tbz2': [u'unstable', 0], u'perl-digest-base-1.15.tbz2': [u'unstable', 1], u'font-bh-100dpi-1.0.0.tbz2': [u'unstable', 1], u'gtkhtml-3.2.5.tbz2': [u'unstable', 1], u'net6-1.3.5.tbz2': [u'unstable', 0], u'kde-i18n-3.5.7.tbz2': [u'unstable', 1], u'libbinio-1.4.tbz2': [u'unstable', 1], u'kdebluetooth-1.0_beta6.tbz2': [u'unstable', 0], u'File-Spec-3.25.tbz2': [u'unstable', 0], u'tunepimp-0.5.3.tbz2': [u'unstable', 1], u'XML-Parser-2.34-r1.tbz2': [u'unstable', 0], u'gnome-themes-2.18.1.tbz2': [u'unstable', 1], u'aspell-sl-0.50.0.tbz2': [u'unstable', 1], u'get-live-help-0.1.9.tbz2': [u'unstable', 0], u'vte-sharp-2.16.0.tbz2': [u'unstable', 1], u'kshisen-3.5.7.tbz2': [u'unstable', 1], u'hashalot-0.3-r2.tbz2': [u'unstable', 1], u'lskat-3.5.7.tbz2': [u'unstable', 1], u'xkeyboard-config-0.9.tbz2': [u'unstable', 0], u'pwdb-0.62.tbz2': [u'unstable', 1], u'antlr-2.7.7.tbz2': [u'unstable', 1], u'libogg-1.1.3.tbz2': [u'unstable', 1], u'libdnet-1.11-r1.tbz2': [u'unstable', 0], u'kdebugdialog-3.5.6.tbz2': [u'unstable', 1], u'XML-NamespaceSupport-1.09.tbz2': [u'unstable', 1], u'sun-jdk-1.6.0.02.tbz2': [u'unstable', 0], u'libXfontcache-1.0.4.tbz2': [u'unstable', 1], u'ghostscript-0.tbz2': [u'unstable', 1], u'fontconfig-2.4.2.tbz2': [u'unstable', 1], u'tsocks-1.8_beta5-r2.tbz2': [u'unstable', 1], u'akregator-3.5.7-r1.tbz2': [u'unstable', 0]}

	# initialize the database
        dbconn = etpDatabase(readOnly = False, noUpload = True)
	dbconn.initializeDatabase()
	
	# sync packages directory
	activatorTools.packages(["sync","--ask"])
	
	# now fill the database
	pkgbranches = os.listdir(etpConst['packagesbindir'])
	pkgbranches = [x for x in pkgbranches if os.path.isdir(etpConst['packagesbindir']+"/"+x)]
	#print revisionsMatch
	for mybranch in pkgbranches:
	
	    pkglist = os.listdir(etpConst['packagesbindir']+"/"+mybranch)
	
	    # filter .md5
	    _pkglist = []
	    for i in pkglist:
	        if not i.endswith(etpConst['packageshashfileext']):
		    _pkglist.append(i)
	    pkglist = _pkglist
	    if (not pkglist):
		continue

	    print_info(green(" * ")+red("Reinitializing Entropy database for branch ")+bold(mybranch)+red(" using Packages in the repository ..."))
	    currCounter = 0
	    atomsnumber = len(pkglist)
	    import reagentTools
	    
	    for pkg in pkglist:
		
	        print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+red("Analyzing: ")+bold(pkg), back = True)
	        currCounter += 1
	        print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+green("(")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(" ..."), back = True)
		
	        etpData = reagentTools.extractPkgData(etpConst['packagesbindir']+"/"+mybranch+"/"+pkg, mybranch)
	        # remove disgregated package
		revisionAvail = revisionsMatch.get(os.path.basename(etpData['download']),None)
		addRevision = 0
		if (revisionAvail):
		    if mybranch == revisionAvail[0]:
			addRevision = revisionAvail[1]+1
	        # fill the db entry
	        idpk, revision, etpDataUpdated, accepted = dbconn.addPackage(etpData, revision = addRevision, wantedBranch = mybranch)
		
		print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+green("(")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(". Revision: ")+blue(str(addRevision)))
	    
	    dbconn.commitChanges()
	
	# regen dependstable
        reagentTools.dependsTableInitialize(dbconn, False)
	
	dbconn.closeDB()
	print_info(green(" * ")+red("Entropy database has been reinitialized using binary packages available"))

    # used by reagent
    elif (options[0] == "search"):
	mykeywords = options[1:]
	if (len(mykeywords) == 0):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(302)
	if (not os.path.isfile(etpConst['etpdatabasefilepath'])):
	    print_error(yellow(" * ")+red("Entropy Datbase does not exist"))
	    sys.exit(303)
	# search tool
	print_info(green(" * ")+red("Searching ..."))
	# open read only
	dbconn = etpDatabase(True)
	foundCounter = 0
	for mykeyword in mykeywords:
	    results = dbconn.searchPackages(mykeyword)
	    
	    for result in results:
		foundCounter += 1
		print 
		print_info(green(" * ")+bold(dbconn.retrieveCategory(result[1])+"/"+dbconn.retrieveName(result[1])))   # package atom
		
		print_info(red("\t Atom: ")+blue(result[0]))
		print_info(red("\t Name: ")+blue(dbconn.retrieveName(result[1])))
		print_info(red("\t Version: ")+blue(dbconn.retrieveVersion(result[1])))
		tag = dbconn.retrieveVersionTag(result[1])
		if (tag):
		    print_info(red("\t Tag: ")+blue(tag))
		
		description = dbconn.retrieveDescription(result[1])
		if (description):
		    print_info(red("\t Description: ")+description)
		
		flags = dbconn.retrieveCompileFlags(result[1])
		print_info(red("\t CHOST: ")+blue(flags[0]))
		print_info(red("\t CFLAGS: ")+darkred(flags[1]))
		print_info(red("\t CXXFLAGS: ")+darkred(flags[2]))
		
		website = dbconn.retrieveHomepage(result[1])
		if (website):
		    print_info(red("\t Website: ")+website)
		
		flags = string.join(dbconn.retrieveUseflags(result[1])," ")
		if (flags):
		    print_info(red("\t USE Flags: ")+blue(flags))
		
		print_info(red("\t License: ")+bold(dbconn.retrieveLicense(result[1])))
		keywords = string.join(dbconn.retrieveKeywords(result[1])," ")
		binkeywords = string.join(dbconn.retrieveBinKeywords(result[1])," ")
		print_info(red("\t Source keywords: ")+darkblue(keywords))
		print_info(red("\t Binary keywords: ")+green(binkeywords))
		print_info(red("\t Package branch: ")+dbconn.retrieveBranch(result[1]))
		print_info(red("\t Download relative URL: ")+dbconn.retrieveDownloadURL(result[1]))
		print_info(red("\t Package Checksum: ")+green(dbconn.retrieveDigest(result[1])))
		
		sources = dbconn.retrieveSources(result[1])
		if (sources):
		    print_info(red("\t Sources"))
		    for source in sources:
			print_info(darkred("\t    # Source package: ")+yellow(source))
		
		slot = dbconn.retrieveSlot(result[1])
		if (slot):
		    print_info(red("\t Slot: ")+yellow(slot))
		else:
		    print_info(red("\t Slot: ")+yellow("Not set"))
		
		'''
		mirrornames = []
		for x in sources:
		    if x.startswith("mirror://"):
		        mirrorname = x.split("/")[2]
		        mirrornames.append(mirrorname)
		for mirror in mirrornames:
		    mirrorlinks = dbconn.retrieveMirrorInfo(mirror)
		    print_info(red("\t mirror://"+mirror+" = ")+str(string.join(mirrorlinks," "))) # I don't need to print mirrorlinks
		'''
		
		dependencies = dbconn.retrieveDependencies(result[1])
		if (dependencies):
		    print_info(red("\t Dependencies"))
		    for dep in dependencies:
			print_info(darkred("\t    # Depends on: ")+dep)
		#print_info(red("\t Blah: ")+result[20]) --> it's a dup of [21]
		
		conflicts = dbconn.retrieveConflicts(result[1])
		if (conflicts):
		    print_info(red("\t Conflicts with"))
		    for conflict in conflicts:
			print_info(darkred("\t    # Conflict: ")+conflict)
		
		api = dbconn.retrieveApi(result[1])
		print_info(red("\t Entry API: ")+green(str(api)))
		
		date = dbconn.retrieveDateCreation(result[1])
		print_info(red("\t Package Creation date: ")+str(entropyTools.convertUnixTimeToHumanTime(float(date))))
		
		revision = dbconn.retrieveRevision(result[1])
		print_info(red("\t Entry revision: ")+str(revision))
		#print result
		
	dbconn.closeDB()
	if (foundCounter == 0):
	    print_warning(red(" * ")+red("Nothing found."))
	else:
	    print

    elif (options[0] == "create-empty-database"):
	mypath = options[1:]
	if len(mypath) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(303)
	if (os.path.dirname(mypath[0]) != '') and (not os.path.isdir(os.path.dirname(mypath[0]))):
	    print_error(green(" * ")+red("Supplied directory does not exist."))
	    sys.exit(304)
	print_info(green(" * ")+red("Initializing an empty database file with Entropy structure ..."),back = True)
	connection = sqlite.connect(mypath[0])
	cursor = connection.cursor()
	for sql in etpSQLInitDestroyAll.split(";"):
	    if sql:
	        cursor.execute(sql+";")
	del sql
	for sql in etpSQLInit.split(";"):
	    if sql:
		cursor.execute(sql+";")
	connection.commit()
	cursor.close()
	connection.close()
	print_info(green(" * ")+red("Entropy database file ")+bold(mypath[0])+red(" successfully initialized."))

    elif (options[0] == "stabilize") or (options[0] == "unstabilize"): # FIXME: adapt to the new branches structure

	if options[0] == "stabilize":
	    stable = True
	else:
	    stable = False
	
	if (stable):
	    print_info(green(" * ")+red("Collecting packages that would be marked stable ..."), back = True)
	else:
	    print_info(green(" * ")+red("Collecting packages that would be marked unstable ..."), back = True)
	
	myatoms = options[1:]
	if len(myatoms) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(303)
	# is world?
	if myatoms[0] == "world":
	    # open db in read only
	    dbconn = etpDatabase(readOnly = True)
	    if (stable):
	        pkglist = dbconn.listUnstablePackages()
	    else:
		pkglist = dbconn.listStablePackages()
	    # This is the list of all the packages available in Entropy
	    dbconn.closeDB()
	else:
	    pkglist = []
	    for atom in myatoms:
		# validate atom
		dbconn = etpDatabase(readOnly = True)
		if (stable):
		    pkg = dbconn.searchPackagesInBranch(atom,"unstable")
		else:
		    pkg = dbconn.searchPackagesInBranch(atom,"stable")
		for x in pkg:
		    pkglist.append(x[0])
	
	# filter dups
	pkglist = list(set(pkglist))
	# check if atoms were found
	if len(pkglist) == 0:
	    print
	    print_error(yellow(" * ")+red("No packages found."))
	    sys.exit(303)
	
	# show what would be done
	if (stable):
	    print_info(green(" * ")+red("These are the packages that would be marked stable:"))
	else:
	    print_info(green(" * ")+red("These are the packages that would be marked unstable:"))

	for pkg in pkglist:
	    print_info(red("\t (*) ")+bold(pkg))
	
	# ask to continue
	rc = entropyTools.askquestion("     Would you like to continue ?")
	if rc == "No":
	    sys.exit(0)
	
	# now mark them as stable
	print_info(green(" * ")+red("Marking selected packages ..."))

	# open db
	dbconn = etpDatabase(readOnly = False, noUpload = True)
	import re
	for pkg in pkglist:
	    print_info(green(" * ")+red("Marking package: ")+bold(pkg)+red(" ..."), back = True)
	    rc, action = dbconn.stabilizePackage(pkg,stable)
	    # @rc: True if updated, False if not
	    # @action: action taken: "stable" for stabilized package, "unstable" for unstabilized package
	    if (rc):
		
		print_info(green(" * ")+red("Package: ")+bold(pkg)+red(" needs to be marked ")+bold(action), back = True)
		
		# change download database parameter name
		download = dbconn.retrievePackageVar(pkg, "download", branch = action)
		# change action with the opposite:
		if action == "stable":
		    # move to unstable
		    oppositeAction = "unstable"
		else:
		    oppositeAction = "stable"
		
		oldpkgfilename = os.path.basename(download)
		download = re.subn("-"+oppositeAction,"-"+action, download)
		
		if download[1]: # if the name has been converted
		
		    newpkgfilename = os.path.basename(download[0])
		
		    # change download parameter in the database entry
		    dbconn.writePackageParameter(pkg, "download", download[0], action)
		
		    print_info(green("   * ")+yellow("Updating local package name"))
		
		    # change filename locally
		    if os.path.isfile(etpConst['packagesbindir']+"/"+oldpkgfilename):
		        os.rename(etpConst['packagesbindir']+"/"+oldpkgfilename,etpConst['packagesbindir']+"/"+newpkgfilename)
		
		    print_info(green("   * ")+yellow("Updating local package checksum"))
		
		    # update md5
		    if os.path.isfile(etpConst['packagesbindir']+"/"+oldpkgfilename+etpConst['packageshashfileext']):
			
		        f = open(etpConst['packagesbindir']+"/"+oldpkgfilename+etpConst['packageshashfileext'])
		        oldMd5 = f.readline().strip()
		        f.close()
		        newMd5 = re.subn(oldpkgfilename, newpkgfilename, oldMd5)
		        if newMd5[1]:
			    f = open(etpConst['packagesbindir']+"/"+newpkgfilename+etpConst['packageshashfileext'],"w")
			    f.write(newMd5[0]+"\n")
			    f.flush()
			    f.close()
		        # remove old
		        os.remove(etpConst['packagesbindir']+"/"+oldpkgfilename+etpConst['packageshashfileext'])
			
		    else: # old md5 does not exist
			
			entropyTools.createHashFile(etpConst['packagesbindir']+"/"+newpkgfilename)
			
		
		    print_info(green("   * ")+yellow("Updating remote package information"))
		
		    # change filename remotely
		    ftp = mirrorTools.handlerFTP(uri)
		    ftp.setCWD(etpConst['binaryurirelativepath'])
		    if (ftp.isFileAvailable(etpConst['packagesbindir']+"/"+oldpkgfilename)):
			# rename tbz2
			ftp.renameFile(oldpkgfilename,newpkgfilename)
			# remove old .md5
			ftp.deleteFile(oldpkgfilename+etpConst['packageshashfileext'])
			# upload new .md5 if found
			if os.path.isfile(etpConst['packagesbindir']+"/"+newpkgfilename+etpConst['packageshashfileext']):
			    ftp.uploadFile(etpConst['packagesbindir']+"/"+newpkgfilename+etpConst['packageshashfileext'],ascii = True)
		

	dbconn.commitChanges()
	print_info(green(" * ")+red("All the selected packages have been marked as requested. Have fun."))
	dbconn.closeDB()

    elif (options[0] == "remove"):

	print_info(green(" * ")+red("Scanning packages that would be removed ..."), back = True)
	
	myopts = options[1:]
	_myopts = []
	branch = ''
	for opt in myopts:
	    if (opt.startswith("--branch=")) and (len(opt.split("=")) == 2):
		
		try:
		    branch = opt.split("=")[1]
		    idx = etpConst['branches'].index(branch)
		    etpConst['branch'] = branch
		except:
		    pass
	    else:
		_myopts.append(opt)
	myopts = _myopts
	
	if len(myopts) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(303)

	pkglist = []
	dbconn = etpDatabase(readOnly = True)
	
	for atom in myopts:
	    pkg = dbconn.atomMatch(atom)
	    if pkg[0] != -1:
	        pkglist.append(pkg[0])

	# filter dups
	pkglist = list(set(pkglist))
	# check if atoms were found
	if len(pkglist) == 0:
	    print
	    dbconn.closeDB()
	    print_error(yellow(" * ")+red("No packages found."))
	    sys.exit(303)
	
	print_info(green(" * ")+red("These are the packages that would be removed from the database:"))

	for pkg in pkglist:
	    pkgatom = dbconn.retrieveAtom(pkg)
	    branch = dbconn.retrieveBranch(pkg)
	    print_info(red("\t (*) ")+bold(pkgatom)+blue(" [")+red(branch)+blue("]"))

	dbconn.closeDB()

	# ask to continue
	rc = entropyTools.askquestion("     Would you like to continue ?")
	if rc == "No":
	    sys.exit(0)
	
	# now mark them as stable
	print_info(green(" * ")+red("Removing selected packages ..."))

	# open db
	dbconn = etpDatabase(readOnly = False, noUpload = True)
	for pkg in pkglist:
	    pkgatom = dbconn.retrieveAtom(pkg)
	    print_info(green(" * ")+red("Removing package: ")+bold(pkgatom)+red(" ..."), back = True)
	    dbconn.removePackage(pkg)
	dbconn.commitChanges()
	print_info(green(" * ")+red("All the selected packages have been removed as requested. To remove online binary packages, just run Activator."))
	dbconn.closeDB()

    # used by reagent
    elif (options[0] == "statistics"):
	print_info(green(" [LOCAL DB STATISTIC]\t\t")+red("Information"))
	# fetch total packages
	dbconn = etpDatabase(readOnly = True)
	totalpkgs = len(dbconn.listAllPackages())
	totalstablepkgs = len(dbconn.listStablePackages())
	totalunstablepkgs = len(dbconn.listUnstablePackages())
	print_info(green(" Total Installed Packages\t\t")+red(str(totalpkgs)))
	print_info(green(" Total Stable Packages\t\t")+red(str(totalstablepkgs)))
	print_info(green(" Total Unstable Packages\t\t")+red(str(totalunstablepkgs)))
	activatorTools.syncRemoteDatabases(justStats = True)
	dbconn.closeDB()

    # used by reagent
    # FIXME: complete this with some automated magic
    elif (options[0] == "md5check"):

	print_info(green(" * ")+red("Integrity verification of the selected packages:"))

	mypackages = options[1:]
	dbconn = etpDatabase(readOnly = True)
	
	# statistic vars
	pkgMatch = 0
	pkgNotMatch = 0
	pkgDownloadedSuccessfully = 0
	pkgDownloadedError = 0
	worldSelected = False
	
	if (len(mypackages) == 0):
	    # check world
	    # create packages list
	    worldSelected = True
	    pkgs2check = dbconn.listAllPackages()
	elif (mypackages[0] == "world"):
	    # check world
	    # create packages list
	    worldSelected = True
	    pkgs2check = dbconn.listAllPackages()
	else:
	    # catch the names
	    pkgs2check = []
	    for pkg in mypackages:
		results = dbconn.searchPackages(pkg)
		for i in results:
		    pkgs2check.append(i)

	if (not worldSelected):
	    print_info(red("   This is the list of the packages that would be checked:"))
	else:
	    print_info(red("   All the packages in the Entropy Packages repository will be checked."))
	
	toBeDownloaded = []
	availList = []
	for pkginfo in pkgs2check:
	
	    pkgatom = pkginfo[0]
	    idpackage = pkginfo[1]
	    pkgbranch = pkginfo[2]
	    pkgfile = dbconn.retrieveDownloadURL(idpackage)
	    pkgfile = os.path.basename(pkgfile)
	    if (os.path.isfile(etpConst['packagesbindir']+"/"+pkgbranch+"/"+pkgfile)):
		if (not worldSelected): print_info(green("   - [PKG AVAILABLE] ")+red(pkgatom)+" -> "+bold(pkgfile))
		availList.append(idpackage)
	    elif (os.path.isfile(etpConst['packagessuploaddir']+"/"+pkgbranch+"/"+pkgfile)):
		if (not worldSelected): print_info(green("   - [RUN ACTIVATOR] ")+darkred(pkgatom)+" -> "+bold(pkgfile))
	    else:
		if (not worldSelected): print_info(green("   - [MUST DOWNLOAD] ")+yellow(pkgatom)+" -> "+bold(pkgfile))
		toBeDownloaded.append([idpackage,pkgfile,pkgbranch])
	
	if (not databaseRequestNoAsk):
	    rc = entropyTools.askquestion("     Would you like to continue ?")
	    if rc == "No":
	        sys.exit(0)

	notDownloadedPackages = []
	if (toBeDownloaded != []):
	    print_info(red("   Starting to download missing files..."))
	    for uri in etpConst['activatoruploaduris']:
		
		if (notDownloadedPackages != []):
		    print_info(red("   Trying to search missing or broken files on another mirror ..."))
		    toBeDownloaded = notDownloadedPackages
		    notDownloadedPackages = []
		
		for pkg in toBeDownloaded:
		    rc = activatorTools.downloadPackageFromMirror(uri,pkg[1],pkg[2])
		    if (rc is None):
			notDownloadedPackages.append([pkg[1],pkg[2]])
		    if (rc == False):
			notDownloadedPackages.append([pkg[1],pkg[2]])
		    if (rc == True):
			pkgDownloadedSuccessfully += 1
			availList.append(pkg[0])
		
		if (notDownloadedPackages == []):
		    print_info(red("   All the binary packages have been downloaded successfully."))
		    break
	
	    if (notDownloadedPackages != []):
		print_warning(red("   These are the packages that cannot be found online:"))
		for i in notDownloadedPackages:
		    pkgDownloadedError += 1
		    print_warning(red("    * ")+yellow(i[0])+" in "+blue(i[1]))
		print_warning(red("   They won't be checked."))
	
	brokenPkgsList = []
	totalcounter = str(len(availList))
	currentcounter = 0
	for pkg in availList:
	    currentcounter += 1
	    pkgfile = dbconn.retrieveDownloadURL(pkg)
	    pkgbranch = dbconn.retrieveBranch(pkg)
	    pkgfile = os.path.basename(pkgfile)
	    print_info("  ("+red(str(currentcounter))+"/"+blue(totalcounter)+") "+red("Checking hash of ")+yellow(pkgfile)+red(" in branch: ")+blue(pkgbranch)+red(" ..."), back = True)
	    storedmd5 = dbconn.retrieveDigest(pkg)
	    result = entropyTools.compareMd5(etpConst['packagesbindir']+"/"+pkgbranch+"/"+pkgfile,storedmd5)
	    if (result):
		# match !
		pkgMatch += 1
		#print_info(red("   Package ")+yellow(pkg)+green(" is healthy. Checksum: ")+yellow(storedmd5), back = True)
	    else:
		pkgNotMatch += 1
		print_error(red("   Package ")+yellow(pkgfile)+red(" in branch: ")+blue(pkgbranch)+red(" is _NOT_ healthy !!!! Stored checksum: ")+yellow(storedmd5))
		brokenPkgsList.append([pkgfile,pkgbranch])

	dbconn.closeDB()

	if (brokenPkgsList != []):
	    print_info(blue(" *  This is the list of the BROKEN packages: "))
	    for bp in brokenPkgsList:
		print_info(red("    * Package file: ")+bold(bp[0])+red(" in branch: ")+blue(bp[1]))

	# print stats
	print_info(blue(" *  Statistics: "))
	print_info(yellow("     Number of checked packages:\t\t")+str(pkgMatch+pkgNotMatch))
	print_info(green("     Number of healthy packages:\t\t")+str(pkgMatch))
	print_info(red("     Number of broken packages:\t\t")+str(pkgNotMatch))
	if (pkgDownloadedSuccessfully > 0) or (pkgDownloadedError > 0):
	    print_info(green("     Number of downloaded packages:\t\t")+str(pkgDownloadedSuccessfully+pkgDownloadedError))
	    print_info(green("     Number of happy downloads:\t\t")+str(pkgDownloadedSuccessfully))
	    print_info(red("     Number of failed downloads:\t\t")+str(pkgDownloadedError))


############
# Functions and Classes
#####################################################################################

# this class simply describes the current database status
class databaseStatus:

    def __init__(self):
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus.__init__ called.")
	
	self.databaseBumped = False
	self.databaseInfoCached = False
	self.databaseLock = False
	#self.database
	self.databaseDownloadLock = False
	self.databaseAlreadyTainted = False
	
	if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile']):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: database tainted.")
	    self.databaseAlreadyTainted = True

    def isDatabaseAlreadyBumped(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: already bumped? "+str(self.databaseBumped))
	return self.databaseBumped

    def isDatabaseAlreadyTainted(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: tainted? "+str(self.databaseAlreadyTainted))
	return self.databaseAlreadyTainted

    def setDatabaseTaint(self,bool):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: setting database taint to: "+str(bool))
	self.databaseAlreadyTainted = bool

    def setDatabaseBump(self,bool):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: setting database bump to: "+str(bool))
	self.databaseBumped = bool

    def setDatabaseLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: Locking database (upload)")
	self.databaseLock = True

    def unsetDatabaseLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: Unlocking database (upload)")
	self.databaseLock = False

    def getDatabaseLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: getting database lock info (upload), status: "+str(self.databaseLock))
	return self.databaseLock

    def setDatabaseDownloadLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: Locking database (download)")
	self.databaseDownloadLock = True

    def unsetDatabaseDownloadLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: Unlocking database (download)")
	self.databaseDownloadLock = False

    def getDatabaseDownloadLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: getting database lock info (download), status: "+str(self.databaseDownloadLock))
	return self.databaseDownloadLock

class etpDatabase:

    def __init__(self, readOnly = False, noUpload = False, dbFile = etpConst['etpdatabasefilepath'], clientDatabase = False, xcache = True):
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase.__init__ called.")
	
	self.readOnly = readOnly
	self.noUpload = noUpload
	self.packagesRemoved = False
	self.packagesAdded = False
	self.clientDatabase = clientDatabase
	self.xcache = xcache
	
	# caching dictionaries
	self.databaseCache = {}
	self.matchCache = {} # dependencies resolving
	
	if (self.clientDatabase):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: database opened by Entropy client, file: "+str(dbFile))
	    # if the database is opened readonly, we don't need to lock the online status
	    self.connection = sqlite.connect(dbFile)
	    self.cursor = self.connection.cursor()
	    # set the table read only
	    return
	
	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: database opened readonly, file: "+str(dbFile))
	    # if the database is opened readonly, we don't need to lock the online status
	    self.connection = sqlite.connect(dbFile)
	    self.cursor = self.connection.cursor()
	    # set the table read only
	    return
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: database opened in read/write mode, file: "+str(dbFile))

	import mirrorTools
	import activatorTools

	# check if the database is locked locally
	if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"etpDatabase: database already locked")
	    print_info(red(" * ")+red("Entropy database is already locked by you :-)"))
	else:
	    # check if the database is locked REMOTELY
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"etpDatabase: starting to lock and sync database")
	    print_info(red(" * ")+red(" Locking and Syncing Entropy database ..."), back = True)
	    for uri in etpConst['activatoruploaduris']:
		dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: connecting to "+uri)
	        ftp = mirrorTools.handlerFTP(uri)
	        ftp.setCWD(etpConst['etpurirelativepath'])
	        if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])) and (not os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])):
		    import time
		    print_info(red(" * ")+bold("WARNING")+red(": online database is already locked. Waiting up to 2 minutes..."), back = True)
		    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"etpDatabase: online database already locked. Waiting 2 minutes")
		    unlocked = False
		    for x in range(120):
		        time.sleep(1)
		        if (not ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
			    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"etpDatabase: online database has been unlocked !")
			    print_info(red(" * ")+bold("HOORAY")+red(": online database has been unlocked. Locking back and syncing..."))
			    unlocked = True
			    break
		    if (unlocked):
		        break

		    dbLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"etpDatabase: online database has not been unlocked in time. Giving up.")
		    # time over
		    print_info(red(" * ")+bold("ERROR")+red(": online database has not been unlocked. Giving up. Who the hell is working on it? Damn, it's so frustrating for me. I'm a piece of python code with a soul dude!"))
		    # FIXME show the lock status

		    print_info(yellow(" * ")+green("Mirrors status table:"))
		    dbstatus = activatorTools.getMirrorsLock()
		    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: showing mirrors status table:")
		    for db in dbstatus:
		        if (db[1]):
	        	    db[1] = red("Locked")
	    	        else:
	        	    db[1] = green("Unlocked")
	    	        if (db[2]):
	        	    db[2] = red("Locked")
	                else:
	        	    db[2] = green("Unlocked")
			dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"   "+entropyTools.extractFTPHostFromUri(db[0])+": DATABASE: "+db[1]+" | DOWNLOAD: "+db[2])
	    	        print_info(bold("\t"+entropyTools.extractFTPHostFromUri(db[0])+": ")+red("[")+yellow("DATABASE: ")+db[1]+red("] [")+yellow("DOWNLOAD: ")+db[2]+red("]"))
	    
	            ftp.closeConnection()
	            sys.exit(320)

	    # if we arrive here, it is because all the mirrors are unlocked so... damn, LOCK!
	    activatorTools.lockDatabases(True)

	    # ok done... now sync the new db, if needed
	    activatorTools.syncRemoteDatabases(self.noUpload)
	
	self.connection = sqlite.connect(dbFile,timeout=300.0)
	self.cursor = self.connection.cursor()

    def closeDB(self):
	
	# if the class is opened readOnly, close and forget
	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"closeDB: closing database opened in readonly.")
	    #self.connection.rollback()
	    self.cursor.close()
	    self.connection.close()
	    return

	# if it's equo that's calling the function, just save changes and quit
	if (self.clientDatabase):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"closeDB: closing database opened by Entropy Client.")
	    self.commitChanges()
	    self.cursor.close()
	    self.connection.close()
	    return

	# Cleanups if at least one package has been removed
	# Please NOTE: the client database does not need it
	if (self.packagesRemoved):
	    self.cleanupUseflags()
	    self.cleanupSources()
	    self.cleanupDependencies()

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"closeDB: closing database opened in read/write.")
	
	# FIXME verify all this shit, for now it works...
	if (entropyTools.dbStatus.isDatabaseAlreadyTainted()) and (not entropyTools.dbStatus.isDatabaseAlreadyBumped()):
	    # bump revision, setting DatabaseBump causes the session to just bump once
	    entropyTools.dbStatus.setDatabaseBump(True)
	    self.revisionBump()
	
	if (not entropyTools.dbStatus.isDatabaseAlreadyTainted()):
	    # we can unlock it, no changes were made
	    import activatorTools
	    activatorTools.lockDatabases(False)
	else:
	    print_info(yellow(" * ")+green("Mirrors have not been unlocked. Run activator."))
	
	self.cursor.close()
	self.connection.close()

    def commitChanges(self):
	if (not self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"commitChanges: writing changes to database.")
	    try:
	        self.connection.commit()
	    except:
		pass
	    self.taintDatabase()
	else:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"commitChanges: discarding changes to database (opened readonly).")
	    self.discardChanges() # is it ok?

    def taintDatabase(self):
	if (self.clientDatabase): # if it's equo to open it, this should be avoided
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"taintDatabase: called by Entropy client, won't do anything.")
	    return
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"taintDatabase: called.")
	# taint the database status
	f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'],"w")
	f.write(etpConst['currentarch']+" database tainted\n")
	f.flush()
	f.close()
	entropyTools.dbStatus.setDatabaseTaint(True)

    def untaintDatabase(self):
	if (self.clientDatabase): # if it's equo to open it, this should be avoided
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"untaintDatabase: called by Entropy client, won't do anything.")
	    return
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"untaintDatabase: called.")
	entropyTools.dbStatus.setDatabaseTaint(False)
	# untaint the database status
	entropyTools.spawnCommand("rm -f "+etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'])

    def revisionBump(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"revisionBump: called.")
	if (not os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaserevisionfile'])):
	    revision = 0
	else:
	    f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaserevisionfile'],"r")
	    revision = int(f.readline().strip())
	    revision += 1
	    f.close()
	f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaserevisionfile'],"w")
	f.write(str(revision)+"\n")
	f.flush()
	f.close()

    def isDatabaseTainted(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isDatabaseTainted: called.")
	if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile']):
	    return True
	return False

    def discardChanges(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"discardChanges: called.")
	self.connection.rollback()

    # never use this unless you know what you're doing
    def initializeDatabase(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"initializeDatabase: called.")
	for sql in etpSQLInitDestroyAll.split(";"):
	    if sql:
	        self.cursor.execute(sql+";")
	del sql
	for sql in etpSQLInit.split(";"):
	    if sql:
		self.cursor.execute(sql+";")
	self.commitChanges()

    # this function manages the submitted package
    # if it does not exist, it fires up addPackage
    # otherwise it fires up updatePackage
    def handlePackage(self, etpData, forcedRevision = -1, forcedBranch = False):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlePackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

        # prepare versiontag
	versiontag = ""
	if (etpData['versiontag']):
	    versiontag = "-"+etpData['versiontag']

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlePackage: called.")
	if (not self.isPackageAvailable(etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag)):
	    if (forcedRevision < 0):
		forcedRevision = 0
	    if (forcedBranch):
	        idpk, revision, etpDataUpdated, accepted = self.addPackage(etpData, revision = forcedRevision, wantedBranch = etpData['branch'])
	    else:
		idpk, revision, etpDataUpdated, accepted = self.addPackage(etpData, revision = forcedRevision)
	else:
	    idpk, revision, etpDataUpdated, accepted = self.updatePackage(etpData, forcedRevision) # branch and revision info will be overwritten
	return idpk, revision, etpDataUpdated, accepted


    # FIXME: default add an unstable package ~~ use indexes
    def addPackage(self, etpData, revision = 0, wantedBranch = "unstable"):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackage: called.")
	
	# if a similar package, in the same branch exists, mark for removal
	searchsimilar = self.searchSimilarPackages(etpData['category']+"/"+etpData['name'], branch = wantedBranch)
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"addPackage: here is the list of similar packages (that will be removed) found for "+etpData['category']+"/"+etpData['name']+": "+str(searchsimilar))
	removelist = []
	for oldpkg in searchsimilar:
	    # get the package slot
	    idpackage = oldpkg[1]
	    slot = self.retrieveSlot(idpackage)
	    if (etpData['slot'] == slot):
		# remove!
		removelist.append(idpackage)
	
	for pkg in removelist:
	    self.removePackage(pkg)
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackage: inserting: ")
	for ln in etpData:
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"\t "+ln+": "+str(etpData[ln]))

	# create new category if it doesn't exist
	catid = self.isCategoryAvailable(etpData['category'])
	if (catid == -1):
	    # create category
	    catid = self.addCategory(etpData['category'])

	# create new license if it doesn't exist
	licid = self.isLicenseAvailable(etpData['license'])
	if (licid == -1):
	    # create category
	    licid = self.addLicense(etpData['license'])

	# look for configured versiontag
	versiontag = ""
	if (etpData['versiontag']):
	    versiontag = "-"+etpData['versiontag']

	# baseinfo
	self.cursor.execute(
		'INSERT into baseinfo VALUES '
		'(NULL,?,?,?,?,?,?,?,?,?,?)'
		, (	etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag,
			catid,
			etpData['name'],
			etpData['version'],
			etpData['versiontag'],
			revision,
			wantedBranch,
			etpData['slot'],
			licid,
			etpData['etpapi'],
			)
	)
	self.connection.commit()
	idpackage = self.cursor.lastrowid

	# create new idflag if it doesn't exist
	idflags = self.areCompileFlagsAvailable(etpData['chost'],etpData['cflags'],etpData['cxxflags'])
	if (idflags == -1):
	    # create category
	    idflags = self.addCompileFlags(etpData['chost'],etpData['cflags'],etpData['cxxflags'])

	# extrainfo
	self.cursor.execute(
		'INSERT into extrainfo VALUES '
		'(?,?,?,?,?,?,?,?)'
		, (	idpackage,
			etpData['description'],
			etpData['homepage'],
			etpData['download'],
			etpData['size'],
			idflags,
			etpData['digest'],
			etpData['datecreation'],
			)
	)

	# content, a list
	for file in etpData['content']:
	    self.cursor.execute(
		'INSERT into content VALUES '
		'(?,?)'
		, (	idpackage,
			file,
			)
	    )
	
	# counter, if != -1
	try:
	    if etpData['counter'] != -1:
	        self.cursor.execute(
	        'INSERT into counters VALUES '
	        '(?,?)'
	        , (	etpData['counter'],
		    idpackage,
		    )
	        )
	except:
	    pass # FIXME: temp woraround, add check for clientDbconn
	
	# on disk size
	try:
	    self.cursor.execute(
	    'INSERT into sizes VALUES '
	    '(?,?)'
	    , (	idpackage,
		etpData['disksize'],
		)
	    )
	except:
	    # create sizes table, temp hack
	    self.createSizesTable()
	    self.cursor.execute(
	    'INSERT into sizes VALUES '
	    '(?,?)'
	    , (	idpackage,
		etpData['disksize'],
		)
	    )
	
	# dependencies, a list
	for dep in etpData['dependencies']:
	
	    iddep = self.isDependencyAvailable(dep)
	    if (iddep == -1):
	        # create category
	        iddep = self.addDependency(dep)
	
	    self.cursor.execute(
		'INSERT into dependencies VALUES '
		'(?,?)'
		, (	idpackage,
			iddep,
			)
	    )

	# provide
	for atom in etpData['provide']:
	    self.cursor.execute(
		'INSERT into provide VALUES '
		'(?,?)'
		, (	idpackage,
			atom,
			)
	    )
	
	# is it a system package?
	if etpData['systempackage']:
	    self.cursor.execute(
		'INSERT into systempackages VALUES '
		'(?)'
		, (	idpackage,
			)
	    )

	# create new protect if it doesn't exist
	idprotect = self.isProtectAvailable(etpData['config_protect'])
	if (idprotect == -1):
	    # create category
	    idprotect = self.addProtect(etpData['config_protect'])
	# fill configprotect
	self.cursor.execute(
		'INSERT into configprotect VALUES '
		'(?,?)'
		, (	idpackage,
			idprotect,
			)
	)
	    
	idprotect = self.isProtectAvailable(etpData['config_protect_mask'])
	if (idprotect == -1):
	    # create category
	    idprotect = self.addProtect(etpData['config_protect_mask'])
	# fill configprotect
	self.cursor.execute(
		'INSERT into configprotectmask VALUES '
		'(?,?)'
		, (	idpackage,
			idprotect,
			)
	)

	# conflicts, a list
	for conflict in etpData['conflicts']:
	    self.cursor.execute(
		'INSERT into conflicts VALUES '
		'(?,?)'
		, (	idpackage,
			conflict,
			)
	    )

	# mirrorlinks, always update the table
	for mirrordata in etpData['mirrorlinks']:
	    mirrorname = mirrordata[0]
	    mirrorlist = mirrordata[1]
	    # remove old
	    self.removeMirrorEntries(mirrorname)
	    # add new
	    self.addMirrors(mirrorname,mirrorlist)

	# sources, a list
	for source in etpData['sources']:
	    
	    idsource = self.isSourceAvailable(source)
	    if (idsource == -1):
	        # create category
	        idsource = self.addSource(source)
	    
	    self.cursor.execute(
		'INSERT into sources VALUES '
		'(?,?)'
		, (	idpackage,
			idsource,
			)
	    )

	# useflags, a list
	for flag in etpData['useflags']:
	    
	    iduseflag = self.isUseflagAvailable(flag)
	    if (iduseflag == -1):
	        # create category
	        iduseflag = self.addUseflag(flag)
	    
	    self.cursor.execute(
		'INSERT into useflags VALUES '
		'(?,?)'
		, (	idpackage,
			iduseflag,
			)
	    )

	# create new keyword if it doesn't exist
	for key in etpData['keywords']:

	    idkeyword = self.isKeywordAvailable(key)
	    if (idkeyword == -1):
	        # create category
	        idkeyword = self.addKeyword(key)

	    self.cursor.execute(
		'INSERT into keywords VALUES '
		'(?,?)'
		, (	idpackage,
			idkeyword,
			)
	    )

	for key in etpData['binkeywords']:

	    idbinkeyword = self.isKeywordAvailable(key)
	    if (idbinkeyword == -1):
	        # create category
	        idbinkeyword = self.addKeyword(key)

	    self.cursor.execute(
		'INSERT into binkeywords VALUES '
		'(?,?)'
		, (	idpackage,
			idbinkeyword,
			)
	    )

	self.packagesAdded = True
	self.commitChanges()
	
	return idpackage, revision, etpData, True

    # Update already available atom in db
    # returns True,revision if the package has been updated
    # returns False,revision if not
    def updatePackage(self, etpData, forcedRevision = -1):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: called.")

        # prepare versiontag
	versiontag = ""
	if (etpData['versiontag']):
	    versiontag = "-"+etpData['versiontag']
	# build atom string
	pkgatom = etpData['category'] + "/" + etpData['name'] + "-" + etpData['version']+versiontag

	# if client opened the database, before starting the update, remove previous entries - same atom, all branches
	if (self.clientDatabase):
	    
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: client request. Removing duplicated entries.")
	    atomInfos = self.searchPackages(pkgatom)
	    for atomInfo in atomInfos:
		idpackage = atomInfo[1]
		self.removePackage(idpackage)
	    
	    if (forcedRevision < 0):
		forcedRevision = 0 # FIXME: this shouldn't happen
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: removal complete. Now spawning addPackage.")
	    x,y,z,accepted = self.addPackage(etpData, revision = forcedRevision, wantedBranch = etpData['branch'])
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: returned back from addPackage.")
	    return x,y,z,accepted
	    
	else:
	    # update package in etpData['branch']
	    # get its package revision
	    idpackage = self.getIDPackage(pkgatom,etpData['branch'])
	    if (forcedRevision == -1):
	        if (idpackage != -1):
	            curRevision = self.retrieveRevision(idpackage)
	        else:
	            curRevision = 0
	    else:
		curRevision = forcedRevision

	    if (idpackage != -1): # remove old package in branch
	        self.removePackage(idpackage)
		if (forcedRevision == -1):
		    curRevision += 1
	    
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: current revision set to "+str(curRevision))

	    # add the new one
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: complete. Now spawning addPackage.")
	    x,y,z,accepted = self.addPackage(etpData, revision = curRevision, wantedBranch = etpData['branch'])
	    return x,y,z,accepted
	

    def removePackage(self,idpackage):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removePackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

	key = self.retrieveAtom(idpackage)
	branch = self.retrieveBranch(idpackage)

	# clean package cache
	xcached = self.databaseCache.get(int(idpackage), None)
	if xcached:
	    try:
	        del self.databaseCache[int(idpackage)]
	    except:
		pass
	self.matchCache = {} # dependencies handling cache

	idpackage = str(idpackage)
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"removePackage: trying to remove (if exists) -> "+idpackage+":"+str(key)+" | branch: "+branch)
	# baseinfo
	self.cursor.execute('DELETE FROM baseinfo WHERE idpackage = '+idpackage)
	# extrainfo
	self.cursor.execute('DELETE FROM extrainfo WHERE idpackage = '+idpackage)
	# content
	self.cursor.execute('DELETE FROM content WHERE idpackage = '+idpackage)
	# dependencies
	self.cursor.execute('DELETE FROM dependencies WHERE idpackage = '+idpackage)
	# provide
	self.cursor.execute('DELETE FROM provide WHERE idpackage = '+idpackage)
	# conflicts
	self.cursor.execute('DELETE FROM conflicts WHERE idpackage = '+idpackage)
	# protect
	self.cursor.execute('DELETE FROM configprotect WHERE idpackage = '+idpackage)
	# protect_mask
	self.cursor.execute('DELETE FROM configprotectmask WHERE idpackage = '+idpackage)
	# sources
	self.cursor.execute('DELETE FROM sources WHERE idpackage = '+idpackage)
	# useflags
	self.cursor.execute('DELETE FROM useflags WHERE idpackage = '+idpackage)
	# keywords
	self.cursor.execute('DELETE FROM keywords WHERE idpackage = '+idpackage)
	# binkeywords
	self.cursor.execute('DELETE FROM binkeywords WHERE idpackage = '+idpackage)
	# systempackage
	self.cursor.execute('DELETE FROM systempackages WHERE idpackage = '+idpackage)
	try:
	    # cpunter
	    self.cursor.execute('DELETE FROM counters WHERE idpackage = '+idpackage)
	except:
	    pass
	try:
	    # on disk sizes
	    self.cursor.execute('DELETE FROM sizes WHERE idpackage = '+idpackage)
	except:
	    pass
	
	# Remove from installedtable if exists
	self.removePackageFromInstalledTable(idpackage)
	# Remove from dependstable if exists
	self.removePackageFromDependsTable(idpackage)
	# need a final cleanup
	self.packagesRemoved = True
	
	self.commitChanges()

    def removeMirrorEntries(self,mirrorname):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removeMirrors: removing entries for mirror -> "+str(mirrorname))
	self.cursor.execute('DELETE FROM mirrorlinks WHERE mirrorname = "'+mirrorname+'"')
	self.commitChanges()

    def addMirrors(self,mirrorname,mirrorlist):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addMirrors: adding Mirror list for "+str(mirrorname)+" -> "+str(mirrorlist))
	for x in mirrorlist:
	    self.cursor.execute(
		'INSERT into mirrorlinks VALUES '
		'(?,?)', (mirrorname,x,)
	    )
	self.commitChanges()

    def addCategory(self,category):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addCategory: adding Package Category -> "+str(category))
	self.cursor.execute(
		'INSERT into categories VALUES '
		'(NULL,?)', (category,)
	)
	# get info about inserted value and return
	cat = self.isCategoryAvailable(category)
	if cat != -1:
	    self.commitChanges()
	    return cat
	raise Exception, "I tried to insert a category but then, fetching it returned -1. There's something broken."

    def addProtect(self,protect):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addProtect: adding CONFIG_PROTECT/CONFIG_PROTECT_MASK -> "+str(protect))
	self.cursor.execute(
		'INSERT into configprotectreference VALUES '
		'(NULL,?)', (protect,)
	)
	# get info about inserted value and return
	prt = self.isProtectAvailable(protect)
	if prt != -1:
	    return prt
	raise Exception, "I tried to insert a protect but then, fetching it returned -1. There's something broken."

    def addSource(self,source):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addSource: adding Package Source -> "+str(source))
	self.cursor.execute(
		'INSERT into sourcesreference VALUES '
		'(NULL,?)', (source,)
	)
	# get info about inserted value and return
	src = self.isSourceAvailable(source)
	if src != -1:
	    return src
	raise Exception, "I tried to insert a source but then, fetching it returned -1. There's something broken."

    def addDependency(self,dependency):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addDependency: adding Package Dependency -> "+str(dependency))
	self.cursor.execute(
		'INSERT into dependenciesreference VALUES '
		'(NULL,?)', (dependency,)
	)
	# get info about inserted value and return
	dep = self.isDependencyAvailable(dependency)
	if dep != -1:
	    return dep
	raise Exception, "I tried to insert a dependency but then, fetching it returned -1. There's something broken."

    def addKeyword(self,keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addKeyword: adding Keyword -> "+str(keyword))
	self.cursor.execute(
		'INSERT into keywordsreference VALUES '
		'(NULL,?)', (keyword,)
	)
	# get info about inserted value and return
	key = self.isKeywordAvailable(keyword)
	if key != -1:
	    return key
	raise Exception, "I tried to insert a keyword but then, fetching it returned -1. There's something broken."

    def addUseflag(self,useflag):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addUseflag: adding Keyword -> "+str(useflag))
	self.cursor.execute(
		'INSERT into useflagsreference VALUES '
		'(NULL,?)', (useflag,)
	)
	# get info about inserted value and return
	use = self.isUseflagAvailable(useflag)
	if use != -1:
	    return use
	raise Exception, "I tried to insert a useflag but then, fetching it returned -1. There's something broken."

    def addLicense(self,license):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addLicense: adding License -> "+str(license))
	self.cursor.execute(
		'INSERT into licenses VALUES '
		'(NULL,?)', (license,)
	)
	# get info about inserted value and return
	lic = self.isLicenseAvailable(license)
	if lic != -1:
	    return lic
	raise Exception, "I tried to insert a license but then, fetching it returned -1. There's something broken."

    #addCompileFlags(etpData['chost'],etpData['cflags'],etpData['cxxflags'])
    def addCompileFlags(self,chost,cflags,cxxflags):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addCompileFlags: adding Flags -> "+chost+"|"+cflags+"|"+cxxflags)
	self.cursor.execute(
		'INSERT into flags VALUES '
		'(NULL,?,?,?)', (chost,cflags,cxxflags,)
	)
	# get info about inserted value and return
	idflag = self.areCompileFlagsAvailable(chost,cflags,cxxflags)
	if idflag != -1:
	    return idflag
	raise Exception, "I tried to insert a flag tuple but then, fetching it returned -1. There's something broken."

    def setDigest(self, idpackage, digest):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"setChecksum: setting new digest for idpackage: "+str(idpackage)+" -> "+str(digest))
	self.cursor.execute('UPDATE extrainfo SET digest = "'+str(digest)+'" WHERE idpackage = "'+str(idpackage)+'"')

    def cleanupUseflags(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupUseflags: called.")
	self.cursor.execute('SELECT idflag FROM useflagsreference')
	idflags = set([])
	for row in self.cursor:
	    idflags.add(row[0])
	# now parse them into useflags table
	orphanedFlags = idflags.copy()
	for idflag in idflags:
	    self.cursor.execute('SELECT idflag FROM useflags WHERE idflag = '+str(idflag))
	    for row in self.cursor:
		orphanedFlags.remove(row[0])
		break
	# now we have orphans that can be removed safely
	for idoflag in orphanedFlags:
	    self.cursor.execute('DELETE FROM useflagsreference WHERE idflag = '+str(idoflag))
	for row in self.cursor:
	    x = row # really necessary ?

    def cleanupSources(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupSources: called.")
	self.cursor.execute('SELECT idsource FROM sourcesreference')
	idsources = set([])
	for row in self.cursor:
	    idsources.add(row[0])
	# now parse them into useflags table
	orphanedSources = idsources.copy()
	for idsource in idsources:
	    self.cursor.execute('SELECT idsource FROM sources WHERE idsource = '+str(idsource))
	    for row in self.cursor:
		orphanedSources.remove(row[0])
		break
	# now we have orphans that can be removed safely
	for idosrc in orphanedSources:
	    self.cursor.execute('DELETE FROM sourcesreference WHERE idsource = '+str(idosrc))
	for row in self.cursor:
	    x = row # really necessary ?

    def cleanupDependencies(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupDependencies: called.")
	self.cursor.execute('SELECT iddependency FROM dependenciesreference')
	iddeps = set([])
	for row in self.cursor:
	    iddeps.add(row[0])
	# now parse them into useflags table
	orphanedDeps = iddeps.copy()
	for iddep in iddeps:
	    self.cursor.execute('SELECT iddependency FROM dependencies WHERE iddependency = '+str(iddep))
	    for row in self.cursor:
		orphanedDeps.remove(row[0])
		break
	# now we have orphans that can be removed safely
	for idodep in orphanedDeps:
	    self.cursor.execute('DELETE FROM dependenciesreference WHERE iddependency = '+str(idodep))
	for row in self.cursor:
	    x = row # really necessary ?

    # WARNING: this function must be kept in sync with Entropy database schema
    # returns True if equal
    # returns False if not
    # FIXME: this must be fixed to work with branches
    def comparePackagesData(self, etpData, pkgAtomToQuery, branchToQuery = "unstable"):
	
	# fill content - get idpackage
	idpackage = self.getIDPackage(pkgAtomToQuery,branchToQuery)
	# get data
	myEtpData = self.getPackageData(idpackage)
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"comparePackagesData: called for "+str(etpData['name'])+" and "+str(myEtpData['name'])+" | branch: "+branchToQuery)
	
	for i in etpData:
	    if etpData[i] != myEtpData[i]:
		dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"comparePackagesData: they don't match")
		return False
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"comparePackagesData: they match")
	return True
    
    def getIDPackage(self, atom, branch = "unstable"):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDPackage: retrieving package ID for "+atom+" | branch: "+branch)
	self.cursor.execute('SELECT "IDPACKAGE" FROM baseinfo WHERE atom = "'+atom+'" AND branch = "'+branch+'"')
	idpackage = -1
	for row in self.cursor:
	    idpackage = int(row[0])
	    break
	return idpackage

    def getIDPackageFromFileInBranch(self, file, branch = "unstable"):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDPackageFromFile: retrieving package ID for file "+file+" | branch: "+branch)
	self.cursor.execute('SELECT idpackage FROM content WHERE file = "'+file+'"')
	idpackages = []
	for row in self.cursor:
	    idpackages.append(row[0])
	result = []
	for pkg in idpackages:
	    self.cursor.execute('SELECT idpackage FROM baseinfo WHERE idpackage = "'+str(pkg)+'" and branch = "'+branch+'"')
	    for row in self.cursor:
		result.append(row[0])
	return result

    def getIDPackagesFromFile(self, file):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDPackageFromFile: retrieving package ID for file "+file)
	self.cursor.execute('SELECT idpackage FROM content WHERE file = "'+file+'"')
	idpackages = []
	for row in self.cursor:
	    idpackages.append(row[0])
	return idpackages

    def getIDCategory(self, category):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDCategory: retrieving category ID for "+str(category))
	self.cursor.execute('SELECT "idcategory" FROM categories WHERE category = "'+str(category)+'"')
	idcat = -1
	for row in self.cursor:
	    idcat = int(row[0])
	    break
	return idcat

    def getIDPackageFromBinaryPackage(self,packageName):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDPackageFromBinaryPackage: retrieving package ID for "+atom+" | branch: "+branch)
	self.cursor.execute('SELECT "IDPACKAGE" FROM baseinfo WHERE download = "'+etpConst['binaryurirelativepath']+packageName+'"')
	idpackage = -1
	for row in self.cursor:
	    idpackage = int(row[0])
	    break
	return idpackage

    def getPackageData(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageData: retrieving etpData for package ID for "+str(idpackage))
	data = {}
	
	data['name'] = self.retrieveName(idpackage)
	data['version'] = self.retrieveVersion(idpackage)
	data['versiontag'] = self.retrieveVersionTag(idpackage)
	data['description'] = self.retrieveDescription(idpackage)
	data['category'] = self.retrieveCategory(idpackage)
	
	flags = self.retrieveCompileFlags(idpackage)
	data['chost'] = flags[0]
	data['cflags'] = flags[1]
	data['cxxflags'] = flags[2]
	
	data['homepage'] = self.retrieveHomepage(idpackage)
	data['useflags'] = self.retrieveUseflags(idpackage)
	data['license'] = self.retrieveLicense(idpackage)
	
	data['keywords'] = self.retrieveKeywords(idpackage)
	data['binkeywords'] = self.retrieveBinKeywords(idpackage)
	
	data['branch'] = self.retrieveBranch(idpackage)
	data['download'] = self.retrieveDownloadURL(idpackage)
	data['digest'] = self.retrieveDigest(idpackage)
	data['sources'] = self.retrieveSources(idpackage)
	data['counter'] = self.retrieveCounter(idpackage)
	
	if (self.isSystemPackage(idpackage)):
	    data['systempackage'] = 'xxx'
	else:
	    data['systempackage'] = ''
	
	data['config_protect'] = self.retrieveProtect(idpackage)
	data['config_protect_mask'] = self.retrieveProtectMask(idpackage)
	
	mirrornames = []
	for x in data['sources']:
	    if x.startswith("mirror://"):
		mirrorname = x.split("/")[2]
		mirrornames.append(mirrorname)
	data['mirrorlinks'] = []
	for mirror in mirrornames:
	    mirrorlinks = self.retrieveMirrorInfo(mirror)
	    data['mirrorlinks'].append([mirror,mirrorlinks])
	
	data['slot'] = self.retrieveSlot(idpackage)
	data['content'] = self.retrieveContent(idpackage)
	
	data['dependencies'] = self.retrieveDependencies(idpackage)
	data['provide'] = self.retrieveProvide(idpackage)
	data['conflicts'] = self.retrieveConflicts(idpackage)
	
	data['etpapi'] = self.retrieveApi(idpackage)
	data['datecreation'] = self.retrieveDateCreation(idpackage)
	data['size'] = self.retrieveSize(idpackage)
	data['disksize'] = self.retrieveOnDiskSize(idpackage)
	return data

    def retrieveAtom(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveAtom: retrieving Atom for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveAtom',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "atom" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	atom = ''
	for row in self.cursor:
	    atom = row[0]
	    break
	
	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveAtom'] = atom
	return atom

    def retrieveBranch(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveBranch: retrieving Branch for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveBranch',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "branch" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	br = ''
	for row in self.cursor:
	    br = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveBranch'] = br
	return br

    def retrieveDownloadURL(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDownloadURL: retrieving download URL for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveDownloadURL',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "download" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	download = ''
	for row in self.cursor:
	    download = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveDownloadURL'] = download
	return download

    def retrieveDescription(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDescription: retrieving description for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveDescription',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "description" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	description = ''
	for row in self.cursor:
	    description = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveDescription'] = description
	return description

    def retrieveHomepage(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveHomepage: retrieving Homepage for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveHomepage',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "homepage" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	home = ''
	for row in self.cursor:
	    home = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveHomepage'] = home
	return home

    def retrieveCounter(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCounter: retrieving Counter for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveCounter',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	counter = -1
	try:
	    self.cursor.execute('SELECT "counter" FROM counters WHERE idpackage = "'+str(idpackage)+'"')
	    for row in self.cursor:
	        counter = row[0]
	        break
	except:
	    pass

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveCounter'] = counter
	return counter

    # in bytes
    def retrieveSize(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSize: retrieving Size for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveSize',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "size" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	size = 'N/A'
	for row in self.cursor:
	    size = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveSize'] = size
	return size

    # in bytes
    def retrieveOnDiskSize(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveOnDiskSize: retrieving On Disk Size for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveOnDiskSize',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	try:
	    self.cursor.execute('SELECT size FROM sizes WHERE idpackage = "'+str(idpackage)+'"')
	except:
	    # table does not exist?
	    return 0
	size = 0
	for row in self.cursor:
	    size = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveOnDiskSize'] = size
	return size

    def retrieveDigest(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDigest: retrieving Digest for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveDigest',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "digest" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	digest = ''
	for row in self.cursor:
	    digest = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveDigest'] = digest
	return digest

    def retrieveName(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveName: retrieving Name for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveName',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "name" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	name = ''
	for row in self.cursor:
	    name = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveName'] = name
	return name

    def retrieveVersion(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveVersion: retrieving Version for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveVersion',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "version" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = ''
	for row in self.cursor:
	    ver = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveVersion'] = ver
	return ver

    def retrieveRevision(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveRevision: retrieving Revision for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveRevision',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "revision" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	rev = ''
	for row in self.cursor:
	    rev = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveRevision'] = rev
	return rev

    def retrieveDateCreation(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDateCreation: retrieving Creation Date for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveDateCreation',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "datecreation" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	date = 'N/A'
	for row in self.cursor:
	    date = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveDateCreation'] = date
	return date

    def retrieveApi(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveApi: retrieving Database API for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveApi',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "etpapi" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	api = -1
	for row in self.cursor:
	    api = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveApi'] = api
	return api

    def retrieveUseflags(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveUseflags: retrieving USE flags for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveUseflags',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "idflag" FROM useflags WHERE idpackage = "'+str(idpackage)+'"')
	idflgs = []
	for row in self.cursor:
	    idflgs.append(row[0])
	flags = []
	for idflg in idflgs:
	    self.cursor.execute('SELECT "flagname" FROM useflagsreference WHERE idflag = "'+str(idflg)+'"')
	    for row in self.cursor:
	        flags.append(row[0])

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveUseflags'] = flags
	return flags

    def retrieveConflicts(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveConflicts: retrieving Conflicts for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveConflicts',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "conflict" FROM conflicts WHERE idpackage = "'+str(idpackage)+'"')
	confl = []
	for row in self.cursor:
	    confl.append(row[0])

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveConflicts'] = confl
	return confl

    def retrieveProvide(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveProvide: retrieving Provide for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveProvide',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "atom" FROM provide WHERE idpackage = "'+str(idpackage)+'"')
	provide = []
	for row in self.cursor:
	    provide.append(row[0])
	
	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveProvide'] = provide
	return provide

    def retrieveDependencies(self, idpackage):
	self.cursor.execute('SELECT iddependency FROM dependencies WHERE idpackage = "'+str(idpackage)+'"')
	
	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveDependencies',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}
	
	iddeps = []
	for row in self.cursor:
	    iddeps.append(row[0])
	deps = []
	for iddep in iddeps:
	    self.cursor.execute('SELECT dependency FROM dependenciesreference WHERE iddependency = "'+str(iddep)+'"')
	    for row in self.cursor:
		deps.append(row[0])
	
	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveDependencies'] = deps
	return deps

    def retrieveIdDependencies(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDependencies: retrieving Dependencies for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveIdDependencies',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT iddependency FROM dependencies WHERE idpackage = "'+str(idpackage)+'"')
	iddeps = []
	for row in self.cursor:
	    iddeps.append(row[0])

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveIdDependencies'] = iddeps
	return iddeps

    def retrieveBinKeywords(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveBinKeywords: retrieving Binary Keywords for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveBinKeywords',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "idkeyword" FROM binkeywords WHERE idpackage = "'+str(idpackage)+'"')
	idkws = []
	for row in self.cursor:
	    idkws.append(row[0])
	kw = []
	for idkw in idkws:
	    self.cursor.execute('SELECT "keywordname" FROM keywordsreference WHERE idkeyword = "'+str(idkw)+'"')
	    for row in self.cursor:
	        kw.append(row[0])

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveBinKeywords'] = kw
	return kw

    def retrieveKeywords(self, idpackage):

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveKeywords',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveKeywords: retrieving Keywords for package ID "+str(idpackage))
	self.cursor.execute('SELECT "idkeyword" FROM keywords WHERE idpackage = "'+str(idpackage)+'"')
	idkws = []
	for row in self.cursor:
	    idkws.append(row[0])
	kw = []
	for idkw in idkws:
	    self.cursor.execute('SELECT "keywordname" FROM keywordsreference WHERE idkeyword = "'+str(idkw)+'"')
	    for row in self.cursor:
	        kw.append(row[0])

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveKeywords'] = kw
	return kw

    def retrieveProtect(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveProtect: retrieving CONFIG_PROTECT for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveProtect',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "idprotect" FROM configprotect WHERE idpackage = "'+str(idpackage)+'"')
	idprotect = -1
	for row in self.cursor:
	    idprotect = row[0]
	    break
	protect = ''
	if idprotect == -1:
	    return protect
	self.cursor.execute('SELECT "protect" FROM configprotectreference WHERE idprotect = "'+str(idprotect)+'"')
	for row in self.cursor:
	    protect = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveProtect'] = protect
	return protect

    def retrieveProtectMask(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveProtectMask: retrieving CONFIG_PROTECT_MASK for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveProtectMask',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "idprotect" FROM configprotectmask WHERE idpackage = "'+str(idpackage)+'"')
	idprotect = -1
	for row in self.cursor:
	    idprotect = row[0]
	    break
	protect = ''
	if idprotect == -1:
	    return protect
	self.cursor.execute('SELECT "protect" FROM configprotectreference WHERE idprotect = "'+str(idprotect)+'"')
	for row in self.cursor:
	    protect = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveProtectMask'] = protect
	return protect

    def retrieveSources(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSources: retrieving Sources for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveSources',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT idsource FROM sources WHERE idpackage = "'+str(idpackage)+'"')
	idsources = []
	for row in self.cursor:
	    idsources.append(row[0])
	sources = []
	for idsource in idsources:
	    self.cursor.execute('SELECT source FROM sourcesreference WHERE idsource = "'+str(idsource)+'"')
	    for row in self.cursor:
		sources.append(row[0])

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveSources'] = sources
	return sources

    def retrieveContent(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveContent: retrieving Content for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveContent',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "file" FROM content WHERE idpackage = "'+str(idpackage)+'"')
	fl = []
	for row in self.cursor:
	    fl.append(row[0])

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveContent'] = fl
	return fl

    def retrieveSlot(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSlot: retrieving Slot for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveSlot',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "slot" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = ''
	for row in self.cursor:
	    ver = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveSlot'] = ver
	return ver
    
    def retrieveVersionTag(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveVersionTag: retrieving Version TAG for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveVersionTag',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "versiontag" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = ''
	for row in self.cursor:
	    ver = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveVersionTag'] = ver
	return ver
    
    def retrieveMirrorInfo(self, mirrorname):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveMirrorInfo: retrieving Mirror info for mirror name "+str(mirrorname))

	self.cursor.execute('SELECT "mirrorlink" FROM mirrorlinks WHERE mirrorname = "'+str(mirrorname)+'"')
	mirrorlist = []
	for row in self.cursor:
	    mirrorlist.append(row[0])

	return mirrorlist

    def retrieveCategory(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCategory: retrieving Category for package ID for "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveCategory',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "idcategory" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	cat = ''
	for row in self.cursor:
	    cat = row[0]
	    break
	# now get the category name
	self.cursor.execute('SELECT "category" FROM categories WHERE idcategory = '+str(cat))
	cat = -1
	for row in self.cursor:
	    cat = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveCategory'] = cat
	return cat

    def retrieveLicense(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveLicense: retrieving License for package ID for "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveLicense',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "idlicense" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	lic = -1
	for row in self.cursor:
	    lic = row[0]
	    break
	# now get the license name
	self.cursor.execute('SELECT "license" FROM licenses WHERE idlicense = '+str(lic))
	licname = ''
	for row in self.cursor:
	    licname = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveLicense'] = licname
	return licname

    def retrieveCompileFlags(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCompileFlags: retrieving CHOST,CFLAGS,CXXFLAGS for package ID for "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('retrieveCompileFlags',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	self.cursor.execute('SELECT "idflags" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	idflag = -1
	for row in self.cursor:
	    idflag = row[0]
	    break
	# now get the flags
	self.cursor.execute('SELECT chost,cflags,cxxflags FROM flags WHERE idflags = '+str(idflag))
	flags = ["N/A","N/A","N/A"]
	for row in self.cursor:
	    flags = row
	    break

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['retrieveCompileFlags'] = flags
	return flags

    def retrieveDepends(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDepends: called for idpackage "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('searchDepends',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	# sanity check on the table
	sanity = self.isDependsTableSane() #FIXME: perhaps running this only on a client database?
	if (not sanity):
	    return -2 # table does not exist or is broken, please regenerate and re-run

	iddeps = []
	self.cursor.execute('SELECT iddependency FROM dependstable WHERE idpackage = "'+str(idpackage)+'"')
	for row in self.cursor:
	    iddeps.append(row[0])
	result = []
	for iddep in iddeps:
	    #print iddep
	    self.cursor.execute('SELECT idpackage FROM dependencies WHERE iddependency = "'+str(iddep)+'"')
	    for row in self.cursor:
	        result.append(row[0])

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['searchDepends'] = result

	return result

    # You must provide the full atom to this function
    # WARNING: this function does not support branches !!!
    def isPackageAvailable(self,pkgkey):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isPackageAvailable: called.")
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	result = []
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = "'+pkgkey+'"')
	for row in self.cursor:
	    result.append(row)
	if result == []:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isPackageAvailable: "+pkgkey+" not available.")
	    return False
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isPackageAvailable: "+pkgkey+" available.")
	return True

    def isIDPackageAvailable(self,idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isIDPackageAvailable: called.")
	result = []
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	for row in self.cursor:
	    result.append(row[0])
	if result == []:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isIDPackageAvailable: "+str(idpackage)+" not available.")
	    return False
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isIDPackageAvailable: "+str(idpackage)+" available.")
	return True

    # This version is more specific and supports branches
    def isSpecificPackageAvailable(self, pkgkey, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSpecificPackageAvailable: called.")
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	result = []
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = "'+pkgkey+'" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row[0])
	if result == []:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isSpecificPackageAvailable: "+pkgkey+" | branch: "+branch+" -> not found.")
	    return False
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSpecificPackageAvailable: "+pkgkey+" | branch: "+branch+" -> found !")
	return True

    def isCategoryAvailable(self,category):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCategoryAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isCategoryAvailable: "+category+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCategoryAvailable: "+category+" available.")
	return result

    def isProtectAvailable(self,protect):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isProtectAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idprotect FROM configprotectreference WHERE protect = "'+protect+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isProtectAvailable: "+protect+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isProtectAvailable: "+protect+" available.")
	return result

    def isSourceAvailable(self,source):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSourceAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idsource FROM sourcesreference WHERE source = "'+source+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isSourceAvailable: "+source+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSourceAvailable: "+source+" available.")
	return result

    def isDependencyAvailable(self,dependency):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isDependencyAvailable: called.")
	result = -1
	self.cursor.execute('SELECT iddependency FROM dependenciesreference WHERE dependency = "'+dependency+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isDependencyAvailable: "+dependency+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isDependencyAvailable: "+dependency+" available.")
	return result

    def isKeywordAvailable(self,keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isKeywordAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idkeyword FROM keywordsreference WHERE keywordname = "'+keyword+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isKeywordAvailable: "+keyword+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isKeywordAvailable: "+keyword+" available.")
	return result

    def isUseflagAvailable(self,useflag):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isUseflagAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idflag FROM useflagsreference WHERE flagname = "'+useflag+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isUseflagAvailable: "+useflag+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isUseflagAvailable: "+useflag+" available.")
	return result

    def isCounterAvailable(self,counter):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCounterAvailable: called.")
	result = False
	self.cursor.execute('SELECT counter FROM counters WHERE counter = "'+str(counter)+'"')
	for row in self.cursor:
	    result = True
	if (result):
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isCounterAvailable: "+str(counter)+" not available.")
	else:
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCounterAvailable: "+str(counter)+" available.")
	return result

    def isLicenseAvailable(self,license):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isLicenseAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idlicense FROM licenses WHERE license = "'+license+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isLicenseAvailable: "+license+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isLicenseAvailable: "+license+" available.")
	return result

    def isSystemPackage(self,idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSystemPackage: called.")

	''' caching '''
	if (self.xcache):
	    cached = self.databaseCache.get(int(idpackage), None)
	    if cached:
	        rslt = self.databaseCache[int(idpackage)].get('isSystemPackage',None)
	        if rslt:
		    return rslt
	    else:
	        self.databaseCache[int(idpackage)] = {}

	result = -1
	self.cursor.execute('SELECT idpackage FROM systempackages WHERE idpackage = "'+str(idpackage)+'"')
	for row in self.cursor:
	    result = row[0]
	    break
	rslt = False
	if result != -1:
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSystemPackage: package is in system.")
	    rslt = True
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSystemPackage: package is NOT in system.")

	''' caching '''
	if (self.xcache):
	    self.databaseCache[int(idpackage)]['isSystemPackage'] = rslt
	
	return rslt

    def areCompileFlagsAvailable(self,chost,cflags,cxxflags):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"areCompileFlagsAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idflags FROM flags WHERE chost = "'+chost+'" AND cflags = "'+cflags+'" AND cxxflags = "'+cxxflags+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"areCompileFlagsAvailable: flags tuple "+chost+"|"+cflags+"|"+cxxflags+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"areCompileFlagsAvailable: flags tuple "+chost+"|"+cflags+"|"+cxxflags+" available.")
	return result

    def searchBelongs(self, file, like = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchBelongs: called for "+file)
	result = []
	if (like):
	    self.cursor.execute('SELECT idpackage FROM content WHERE file LIKE "'+file+'"')
	else:
	    self.cursor.execute('SELECT idpackage FROM content WHERE file = "'+file+'"')
	for row in self.cursor:
	    result.append(row[0])
	return result

    def searchPackages(self, keyword, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackages: called for "+keyword)
	result = []
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo WHERE atom LIKE "%'+keyword+'%"')
	else:
	    self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo WHERE LOWER(atom) LIKE "%'+string.lower(keyword)+'%"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchProvide(self, keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchProvide: called for "+keyword)

	idpackage = []
	self.cursor.execute('SELECT idpackage FROM provide WHERE atom = "'+keyword+'"')
	for row in self.cursor:
	    idpackage = row[0]
	    break
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	result = []
	for row in self.cursor:
	    result = row
	    break

	return result

    def searchProvideInBranch(self, keyword, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchProvideInBranch: called for "+keyword+" and branch: "+branch)
	idpackage = []
	self.cursor.execute('SELECT idpackage FROM provide WHERE atom = "'+keyword+'"')
	for row in self.cursor:
	    idpackage = row[0]
	    break
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	result = []
	for row in self.cursor:
	    data = row
	    idpackage = data[1]
	    pkgbranch = self.retrieveBranch(idpackage)
	    if (branch == pkgbranch):
		result.append(data)
		break
	return result

    def searchPackagesInBranch(self, keyword, branch, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranch: called.")
	result = []
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE atom LIKE "%'+keyword+'%" AND branch = "'+branch+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(atom) LIKE "%'+string.lower(keyword)+'%" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesByDescription(self, keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByDescription: called for "+keyword)
	idpkgs = []
	self.cursor.execute('SELECT idpackage FROM extrainfo WHERE LOWER(description) LIKE "%'+string.lower(keyword)+'%"')
	for row in self.cursor:
	    idpkgs.append(row[0])
	result = []
	for idpk in idpkgs:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idpackage = "'+str(idpk)+'"')
	    for row in self.cursor:
	        result.append(row)
	return result

    def searchPackagesByName(self, keyword, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByName: called for "+keyword)
	result = []
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+keyword+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(keyword)+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesByNameAndCategory(self, name, category, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByNameAndCategory: called for name: "+name+" and category: "+category)
	result = []
	# get category id
	idcat = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	for row in self.cursor:
	    idcat = row[0]
	    break
	if idcat == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"searchPackagesByNameAndCategory: Category "+category+" not available.")
	    return result
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" AND idcategory ='+str(idcat))
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(name)+'" AND idcategory ='+str(idcat))
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranchByName(self, keyword, branch, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranchByName: called for "+keyword)
	result = []
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+keyword+'" AND branch = "'+branch+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(keyword)+'" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranchByNameAndCategory(self, name, category, branch, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranchByNameAndCategory: called for "+name+" and category "+category)
	result = []
	# get category id
	idcat = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	for row in self.cursor:
	    idcat = row[0]
	    break
	if idcat == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"searchPackagesInBranchByNameAndCategory: Category "+category+" not available.")
	    return result
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(name)+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranchByNameAndVersionAndCategory(self, name, version, category, branch, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranchByNameAndVersionAndCategoryAndTag: called for "+name+" and version "+version+" and category "+category+" | branch "+branch)
	result = []
	# get category id
	idcat = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	for row in self.cursor:
	    idcat = row[0]
	    break
	if idcat == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"searchPackagesInBranchByNameAndVersionAndCategoryAndTag: Category "+category+" not available.")
	    return result
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" AND version = "'+version+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(name)+'" AND version = "'+version+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    # this function search packages with the same pkgcat/pkgname
    # you must provide something like: media-sound/amarok
    # optionally, you can add version too.
    def searchSimilarPackages(self, atom, branch = "unstable"):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchSimilarPackages: called for "+atom+" | branch: "+branch)
	category = atom.split("/")[0]
	name = atom.split("/")[1]
	# get category id
	idcategory = self.getIDCategory(category)
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idcategory = "'+str(idcategory)+'" AND LOWER(name) = "'+string.lower(name)+'" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def listAllPackages(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllPackages: called.")
	self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo')
	result = []
	for row in self.cursor:
	    result.append(row)
	return result

    def listAllCounters(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllCounters: called.")
	self.cursor.execute('SELECT counter,idpackage FROM counters')
	result = []
	for row in self.cursor:
	    result.append(row)
	return result

    def listAllIdpackages(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllIdpackages: called.")
	self.cursor.execute('SELECT idpackage FROM baseinfo')
	result = []
	for row in self.cursor:
	    result.append(row[0])
	return result

    def listAllDependencies(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllDependencies: called.")
	self.cursor.execute('SELECT * FROM dependenciesreference')
	result = []
	for row in self.cursor:
	    result.append(row)
	return result

    def listIdpackageDependencies(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listIdpackageDependencies: called.")
	self.cursor.execute('SELECT iddependency FROM dependencies where idpackage = "'+str(idpackage)+'"')
	iddeps = []
	for row in self.cursor:
	    iddeps.append(row[0])
	result = []
	for iddep in iddeps:
	    self.cursor.execute('SELECT iddependency,dependency FROM dependenciesreference where iddependency = "'+str(iddep)+'"')
	    for row in self.cursor:
	        result.append(row)
	return result

    ### DEPRECATED
    def listAllPackagesTbz2(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllPackagesTbz2: called.")
        result = []
        pkglist = self.listAllPackages()
        for pkg in pkglist:
	    idpackage = pkg[1]
	    url = self.retrieveDownloadURL(idpackage)
	    if url:
		result.append(url)
        # filter dups?
	if (result):
            result = list(set(result))
	    result.sort()
	return result

    def listBranchPackagesTbz2(self, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listBranchPackagesTbz2: called with "+str(branch))
        result = []
        pkglist = self.listBranchPackages(branch)
        for pkg in pkglist:
	    idpackage = pkg[1]
	    url = self.retrieveDownloadURL(idpackage)
	    if url:
		result.append(os.path.basename(url))
        # filter dups?
	if (result):
            result = list(set(result))
	    result.sort()
	return result

    def listBranchPackages(self, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listBranchPackages: called with "+str(branch))
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE branch = "'+str(branch)+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    # FIXME: remove this, we don't just have stable/unstable branches
    def searchStablePackages(self,atom):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchStablePackages: called for "+atom)
	category = atom.split("/")[0]
	name = atom.split("/")[1]
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE category = "'+category+'" AND name = "'+name+'" AND branch = "stable"')
	for row in self.cursor:
	    result.append(row)
	return result

    # FIXME: also remove this
    def searchUnstablePackages(self,atom):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchUnstablePackages: called for "+atom)
	category = atom.split("/")[0]
	name = atom.split("/")[1]
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE category = "'+category+'" AND name = "'+name+'" AND branch = "stable"')
	for row in self.cursor:
	    result.append(row)
	return result

    def stabilizePackage(self,atom,stable = True):

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: called for "+atom+" | branch stable? -> "+str(stable))

	action = "unstable"
	removeaction = "stable"
	if (stable):
	    action = "stable"
	    removeaction = "unstable"
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: add action: "+action+" | remove action: "+removeaction)
	
	if (self.isSpecificPackageAvailable(atom, removeaction)):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: there's something old that needs to be removed.")
	    idpackage = self.getIDPackage(atom, branch = removeaction)
	    
	    pkgname = self.retrieveName(idpackage)
	    # get its pkgcat
	    category = self.retrieveCategory(idpackage)
	    # search packages with similar pkgcat/name marked as stable
	    slot = self.retrieveSlot(idpackage)
	    
	    # we need to get rid of them
	    results = self.searchStablePackages(category+"/"+pkgname)
	    
	    removelist = []
	    for result in results:
		myidpackage = result[1]
		# have a look if the slot matches
		#print result
		myslot = self.retrieveSlot(myidpackage)
		if (myslot == slot):
		    removelist.append(result[1])
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: removelist: "+str(removelist))
	    for pkg in removelist:
		self.removePackage(pkg)
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: updating "+atom+" setting branch: "+action)
	    
	    self.cursor.execute('UPDATE baseinfo SET branch = "'+action+'" WHERE idpackage = "'+idpackage+'"')
	    self.commitChanges()
	    
	    return True,action
	return False,action

########################################################
####
##   Client Database API / but also used by server part
#

    def addPackageToInstalledTable(self, idpackage, repositoryName):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackageToInstalledTable: called for "+str(idpackage)+" and repository "+str(repositoryName))
	self.cursor.execute(
		'INSERT into installedtable VALUES '
		'(?,?)'
		, (	idpackage,
			repositoryName,
			)
	)
	self.commitChanges()

    def retrievePackageFromInstalledTable(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrievePackageFromInstalledTable: called. ")
	result = 'Not available'
	try:
	    self.cursor.execute('SELECT repositoryname FROM installedtable WHERE idpackage = "'+str(idpackage)+'"')
	    for row in self.cursor:
	        result = row[0]
	        break
	except:
	    pass
	return result

    def removePackageFromInstalledTable(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removePackageFromInstalledTable: called for "+str(idpackage))
	try:
	    self.cursor.execute('DELETE FROM installedtable WHERE idpackage = '+str(idpackage))
	    self.commitChanges()
	except:
	    self.createInstalledTable()

    def removePackageFromDependsTable(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removePackageFromDependsTable: called for "+str(idpackage))
	try:
	    self.cursor.execute('DELETE FROM dependstable WHERE idpackage = '+str(idpackage))
	    self.commitChanges()
	    return 0
	except:
	    return 1 # need reinit

    def removeDependencyFromDependsTable(self, iddependency):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removeDependencyFromDependsTable: called for "+str(iddependency))
	try:
	    self.cursor.execute('DELETE FROM dependstable WHERE iddependency = '+str(iddependency))
	    self.commitChanges()
	    return 0
	except:
	    return 1 # need reinit

    # temporary/compat functions
    def createDependsTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createDependsTable: called.")
	self.cursor.execute('DROP TABLE IF EXISTS dependstable;')
	self.cursor.execute('CREATE TABLE dependstable ( iddependency INTEGER PRIMARY KEY, idpackage INTEGER );')
	# this will be removed when dependstable is refilled properly
	self.cursor.execute(
		'INSERT into dependstable VALUES '
		'(?,?)'
		, (	-1,
			-1,
			)
	)
	self.commitChanges()

    def sanitizeDependsTable(self):
	self.cursor.execute('DELETE FROM dependstable where iddependency = -1')
	self.commitChanges()

    def isDependsTableSane(self):
	sane = True
	try:
	    self.cursor.execute('SELECT iddependency FROM dependstable WHERE iddependency = -1')
	except:
	    return False # table does not exist, please regenerate and re-run
	for row in self.cursor:
	    sane = False
	    break
	return sane

    def createSizesTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createSizesTable: called.")
	self.cursor.execute('DROP TABLE IF EXISTS sizes;')
	self.cursor.execute('CREATE TABLE sizes ( idpackage INTEGER, size INTEGER );')
	self.commitChanges()

    def createInstalledTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createInstalledTable: called.")
	self.cursor.execute('DROP TABLE IF EXISTS installedtable;')
	self.cursor.execute('CREATE TABLE installedtable ( idpackage INTEGER, repositoryname VARCHAR );')
	self.commitChanges()

    def addDependRelationToDependsTable(self, iddependency, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addDependRelationToDependsTable: called for iddependency "+str(iddependency)+" and idpackage "+str(idpackage))
	self.cursor.execute(
		'INSERT into dependstable VALUES '
		'(?,?)'
		, (	iddependency,
			idpackage,
			)
	)
	self.commitChanges()


########################################################
####
##   Dependency handling functions
#

    '''
       @description: matches the user chosen package name+ver, if possibile, in a single repository
       @input atom: string
       @input dbconn: database connection
       @output: the package id, if found, otherwise -1 plus the status, 0 = ok, 1 = not found, 2 = need more info, 3 = cannot use direction without specifying version
    '''
    def atomMatch(self, atom, caseSensitive = True):
    
        if (self.xcache):
            cached = self.matchCache.get(atom)
            if cached:
	        return cached['result']
    
        # check for direction
        strippedAtom = entropyTools.dep_getcpv(atom)
        if atom.endswith("*"):
	    strippedAtom += "*"
        direction = atom[0:len(atom)-len(strippedAtom)]
        #print direction

        #print strippedAtom
        #print isspecific(strippedAtom)
        #print direction
    
        justname = entropyTools.isjustname(strippedAtom)
        #print justname
        pkgversion = ''
        if (not justname):
	    # strip tag
            if strippedAtom.split("-")[len(strippedAtom.split("-"))-1].startswith("t"):
                strippedAtom = string.join(strippedAtom.split("-t")[:len(strippedAtom.split("-t"))-1],"-t")
	    # get version
	    data = entropyTools.catpkgsplit(strippedAtom)
	    if data == None:
	        return -1,3 # atom is badly formatted
	    pkgversion = data[2]+"-"+data[3]
	    pkgtag = ''
	    if atom.split("-")[len(atom.split("-"))-1].startswith("t"):
	        pkgtag = atom.split("-")[len(atom.split("-"))-1]
	        #print "TAG: "+pkgtag
	    #print data
	    #print pkgversion
	    #print pkgtag
	

        pkgkey = entropyTools.dep_getkey(strippedAtom)
        if len(pkgkey.split("/")) == 2:
            pkgname = pkgkey.split("/")[1]
            pkgcat = pkgkey.split("/")[0]
        else:
            pkgname = pkgkey.split("/")[0]
	    pkgcat = "null"

        #print dep_getkey(strippedAtom)
    
        myBranchIndex = etpConst['branches'].index(etpConst['branch'])
    
        # IDs found in the database that match our search
        foundIDs = []
    
        for idx in range(myBranchIndex+1)[::-1]: # reverse order
	    #print "Searching into -> "+etpConst['branches'][idx]
	    # search into the less stable, if found, break, otherwise continue
	    results = self.searchPackagesInBranchByName(pkgname, etpConst['branches'][idx], caseSensitive)
	
	    # if it's a PROVIDE, search with searchProvide
	    if (not results):
	        results = self.searchProvideInBranch(pkgkey,etpConst['branches'][idx])
	
	    # now validate
	    if (not results):
	        #print "results is empty"
	        continue # search into a stabler branch
	
	    elif (len(results) > 1):
	
	        #print "results > 1"
	        # if it's because category differs, it's a problem
	        foundCat = ""
	        cats = []
	        for result in results:
		    idpackage = result[1]
		    cat = self.retrieveCategory(idpackage)
		    cats.append(cat)
		    if (cat == pkgcat):
		        foundCat = cat
		        break
	        # if categories are the same...
	        if (not foundCat) and (len(cats) > 0):
		    cats = entropyTools.filterDuplicatedEntries(cats)
		    if len(cats) == 1:
		        foundCat = cats[0]
	        if (not foundCat) and (pkgcat == "null"):
		    # got the issue
		    # gosh, return and complain
		    self.matchCache[atom] = {}
		    self.matchCache[atom]['result'] = -1,2
		    return -1,2
	
	        # I can use foundCat
	        pkgcat = foundCat
	    
	        # we need to search using the category
	        results = self.searchPackagesInBranchByNameAndCategory(pkgname,pkgcat,etpConst['branches'][idx], caseSensitive)
	        # validate again
	        if (not results):
		    continue  # search into a stabler branch
	
	        # if we get here, we have found the needed IDs
	        foundIDs = results
	        break

	    else:
	        #print "results == 1"
	        foundIDs.append(results[0])
	        break

        if (foundIDs):
	    # now we have to handle direction
	    if (direction) or (direction == '' and not justname) or (direction == '' and not justname and strippedAtom.endswith("*")):
	        # check if direction is used with justname, in this case, return an error
	        if (justname):
		    #print "justname"
		    self.matchCache[atom] = {}
		    self.matchCache[atom]['result'] = -1,3
		    return -1,3 # error, cannot use directions when not specifying version
	    
	        if (direction == "~") or (direction == "=") or (direction == '' and not justname) or (direction == '' and not justname and strippedAtom.endswith("*")): # any revision within the version specified OR the specified version
		
		    if (direction == '' and not justname):
		        direction = "="
		
		    #print direction+" direction"
		    # remove revision (-r0 if none)
		    if (direction == "="):
		        if (pkgversion.split("-")[len(pkgversion.split("-"))-1] == "r0"):
		            pkgversion = string.join(pkgversion.split("-")[:len(pkgversion.split("-"))-1],"-")
		    if (direction == "~"):
		        pkgversion = string.join(pkgversion.split("-")[:len(pkgversion.split("-"))-1],"-")
		
		    #print pkgversion
		    dbpkginfo = []
		    for list in foundIDs:
		        idpackage = list[1]
		        dbver = self.retrieveVersion(idpackage)
		        if (direction == "~"):
		            if dbver.startswith(pkgversion):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        else:
			    dbtag = self.retrieveVersionTag(idpackage)
			    #print pkgversion
			    # media-libs/test-1.2* support
			    if pkgversion.endswith("*"):
			        testpkgver = pkgversion[:len(pkgversion)-1]
			        #print testpkgver
			        combodb = dbver+dbtag
			        combopkg = testpkgver+pkgtag
			        #print combodb
			        #print combopkg
			        if combodb.startswith(combopkg):
				    dbpkginfo.append([idpackage,dbver])
			    else:
		                if (dbver+dbtag == pkgversion+pkgtag):
			            # found
			            dbpkginfo.append([idpackage,dbver])
		
		    if (not dbpkginfo):
		        # no version available
		        if (direction == "~"): # if the atom with the same version (any rev) is not found, fallback to the first available
			    for list in foundIDs:
			        idpackage = list[1]
			        dbver = self.retrieveVersion(idpackage)
			        dbpkginfo.append([idpackage,dbver])
		
		    if (not dbpkginfo):
		        self.matchCache[atom] = {}
		        self.matchCache[atom]['result'] = -1,1
		        return -1,1
		
		    versions = []
		    for x in dbpkginfo:
		        versions.append(x[1])
		    # who is newer ?
		    versionlist = entropyTools.getNewerVersion(versions)
		    newerPackage = dbpkginfo[versions.index(versionlist[0])]
		
	            # now look if there's another package with the same category, name, version, but different tag
	            newerPkgName = self.retrieveName(newerPackage[0])
	            newerPkgCategory = self.retrieveCategory(newerPackage[0])
	            newerPkgVersion = self.retrieveVersion(newerPackage[0])
		    newerPkgBranch = self.retrieveBranch(newerPackage[0])
	            similarPackages = self.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch, caseSensitive)
		
		    #print newerPackage
		    #print similarPackages
	            if (len(similarPackages) > 1):
		        # gosh, there are packages with the same name, version, category
		        # we need to parse version tag
		        versionTags = []
		        for pkg in similarPackages:
		            versionTags.append(self.retrieveVersionTag(pkg[1]))
		        versiontaglist = entropyTools.getNewerVersionTag(versionTags)
		        newerPackage = similarPackages[versionTags.index(versiontaglist[0])]
		
		    #print newerPackage
		    #print newerPackage[1]
		    self.matchCache[atom] = {}
		    self.matchCache[atom]['result'] = newerPackage[0],0
		    return newerPackage[0],0
	
	        elif (direction.find(">") != -1) or (direction.find("<") != -1): # FIXME: add slot scopes
		
		    #print direction+" direction"
		    # remove revision (-r0 if none)
		    if pkgversion.split("-")[len(pkgversion.split("-"))-1] == "r0":
		        # remove
		        pkgversion = string.join(pkgversion.split("-")[:len(pkgversion.split("-"))-1],"-")

		    dbpkginfo = []
		    for list in foundIDs:
		        idpackage = list[1]
		        dbver = self.retrieveVersion(idpackage)
		        cmp = entropyTools.compareVersions(pkgversion,dbver)
		        if direction == ">": # the --deep mode should really act on this
		            if (cmp < 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        elif direction == "<":
		            if (cmp > 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        elif direction == ">=": # the --deep mode should really act on this
		            if (cmp <= 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        elif direction == "<=":
		            if (cmp >= 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		
		    if (not dbpkginfo):
		        # this version is not available
		        self.matchCache[atom] = {}
		        self.matchCache[atom]['result'] = -1,1
		        return -1,1
		
		    versions = []
		    for x in dbpkginfo:
		        versions.append(x[1])
		    # who is newer ?
		    versionlist = entropyTools.getNewerVersion(versions) ## FIXME: this is already running in --deep mode, maybe adding a function that is more gentle with pulling dependencies?
		    newerPackage = dbpkginfo[versions.index(versionlist[0])]
		
	            # now look if there's another package with the same category, name, version, but different tag
	            newerPkgName = self.retrieveName(newerPackage[0])
	            newerPkgCategory = self.retrieveCategory(newerPackage[0])
	            newerPkgVersion = self.retrieveVersion(newerPackage[0])
		    newerPkgBranch = self.retrieveBranch(newerPackage[0])
	            similarPackages = self.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch)
		
		    #print newerPackage
		    #print similarPackages
	            if (len(similarPackages) > 1):
		        # gosh, there are packages with the same name, version, category
		        # we need to parse version tag
		        versionTags = []
		        for pkg in similarPackages:
		            versionTags.append(self.retrieveVersionTag(pkg[1]))
		        versiontaglist = entropyTools.getNewerVersionTag(versionTags)
		        newerPackage = similarPackages[versionTags.index(versiontaglist[0])]
		
		    #print newerPackage
		    #print newerPackage[1]
		    self.matchCache[atom] = {}
		    self.matchCache[atom]['result'] = newerPackage[0],0
		    return newerPackage[0],0

	        else:
		    self.matchCache[atom] = {}
		    self.matchCache[atom]['result'] = -1,1
		    return -1,1
		
	    else:
	    
	        # not set, just get the newer version
	        versionIDs = []
	        for list in foundIDs:
		    versionIDs.append(self.retrieveVersion(list[1]))
	    
	        versionlist = entropyTools.getNewerVersion(versionIDs)
	        newerPackage = foundIDs[versionIDs.index(versionlist[0])]
	    
	        # now look if there's another package with the same category, name, version, tag
	        newerPkgName = self.retrieveName(newerPackage[1])
	        newerPkgCategory = self.retrieveCategory(newerPackage[1])
	        newerPkgVersion = self.retrieveVersion(newerPackage[1])
	        newerPkgBranch = self.retrieveBranch(newerPackage[1])
	        similarPackages = self.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch)
	    
	        if (len(similarPackages) > 1):
		    # gosh, there are packages with the same name, version, category
		    # we need to parse version tag
		    versionTags = []
		    for pkg in similarPackages:
		        versionTags.append(self.retrieveVersionTag(pkg[1]))
		    versiontaglist = entropyTools.getNewerVersionTag(versionTags)
		    newerPackage = similarPackages[versionTags.index(versiontaglist[0])]
	    
		self.matchCache[atom] = {}
		self.matchCache[atom]['result'] = newerPackage[1],0
	        return newerPackage[1],0

        else:
	    # package not found in any branch
	    self.matchCache[atom] = {}
	    self.matchCache[atom]['result'] = -1,1
	    return -1,1
	