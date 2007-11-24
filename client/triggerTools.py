#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo general purpose triggering scripts for pre/post install and remove 

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

import os
from commands import getoutput
from outputTools import *
from entropyConstants import *
import entropyTools
# Logging initialization
import logTools
equoLog = logTools.LogFile(level = etpConst['equologlevel'],filename = etpConst['equologfile'], header = "[Equo]")

'''
   @ description: Gentoo toolchain variables
'''
MODULEDB_DIR="/var/lib/module-rebuild/"
INITSERVICES_DIR="/var/lib/init.d/"

'''
   @description: pkgdata parser that collects post-install scripts that would be run
'''
def postinstall(pkgdata):
    
    functions = set()

    if pkgdata['trigger']:
        functions.add('call_ext_postinstall')

    # fonts configuration
    if pkgdata['category'] == "media-fonts":
	functions.add("fontconfig")

    # opengl configuration
    if (pkgdata['category'] == "x11-drivers") and (pkgdata['name'].startswith("nvidia-") or pkgdata['name'].startswith("ati-")):
	functions.add("openglsetup")

    # gcc configuration
    if pkgdata['category']+"/"+pkgdata['name'] == "sys-devel/gcc":
	functions.add("gccswitch")

    # binutils configuration
    if pkgdata['category']+"/"+pkgdata['name'] == "sys-devel/binutils":
	functions.add("binutilsswitch")

    # python configuration
    if pkgdata['category']+"/"+pkgdata['name'] == "dev-lang/python":
	functions.add("pythoninst")

    if pkgdata['category']+"/"+pkgdata['name'] == "dev-db/sqlite":
	functions.add('sqliteinst')

    # kde package ?
    if "kde" in pkgdata['eclasses']:
	functions.add("kbuildsycoca")

    # update mime
    if "fdo-mime" in pkgdata['eclasses']:
	functions.add('mimeupdate')
	functions.add('mimedesktopupdate')

    # update gconf db and icon cache
    if "gnome2" in pkgdata['eclasses']:
	functions.add('iconscache')
	functions.add('gconfinstallschemas')
	functions.add('gconfreload')

    if pkgdata['name'] == "pygobject":
	functions.add('pygtksetup')

    # load linker paths
    ldpaths = entropyTools.collectLinkerPaths()

    # prepare content
    for x in pkgdata['content']:
	if x.startswith("/usr/share/icons") and x.endswith("index.theme"):
	    functions.add('iconscache')
	if x.startswith("/usr/share/mime"):
	    functions.add('mimeupdate')
	if x.startswith("/usr/share/applications"):
	    functions.add('mimedesktopupdate')
	if x.startswith("/usr/share/omf"):
	    functions.add('scrollkeeper')
	if x.startswith("/etc/gconf/schemas"):
	    functions.add('gconfreload')
	if x.startswith('/lib/modules/'):
	    functions.add('kernelmod')
	if x.startswith('/boot/kernel-'):
	    functions.add('addbootablekernel')
	if x.startswith('/usr/src/'):
	    functions.add('createkernelsym')
	if x.startswith('/usr/share/java-config-2/vm/'):
	    functions.add('add_java_config_2')
        if x.startswith('/etc/env.d/'):
            functions.add('env_update')
        if x == '/bin/su':
            functions.add("susetuid")
        for path in ldpaths:
            if x.startswith(path) and (x.find(".so") != -1):
	        functions.add('run_ldconfig')
	#if x.startswith("/etc/init.d/"): do it externally
	#    functions.add('initadd')

    return functions

'''
   @description: pkgdata parser that collects pre-install scripts that would be run
'''
def preinstall(pkgdata):
    
    functions = set()
    
    if pkgdata['trigger']:
        functions.add('call_ext_preinstall')
    
    for x in pkgdata['content']:
	if x.startswith("/etc/init.d/"):
	    functions.add('initinform')
	if x.startswith("/boot"):
	    functions.add('mountboot')

    return functions

'''
   @description: pkgdata parser that collects post-remove scripts that would be run
'''
def postremove(pkgdata):
    
    functions = set()

    if pkgdata['trigger']:
        functions.add('call_ext_postremove')

    # opengl configuration
    if (pkgdata['category'] == "x11-drivers") and (pkgdata['name'].startswith("nvidia-") or pkgdata['name'].startswith("ati-")):
	functions.add("openglsetup_xorg")

    # kde package ?
    if "kde" in pkgdata['eclasses']:
	functions.add("kbuildsycoca")

    if pkgdata['name'] == "pygtk":
	functions.add('pygtkremove')

    if pkgdata['category']+"/"+pkgdata['name'] == "dev-db/sqlite":
	functions.add('sqliteinst')

    # python configuration
    if pkgdata['category']+"/"+pkgdata['name'] == "dev-lang/python":
	functions.add("pythoninst")

    # fonts configuration
    if pkgdata['category'] == "media-fonts":
	functions.add("fontconfig")

    # load linker paths
    ldpaths = entropyTools.collectLinkerPaths()

    for x in pkgdata['removecontent']:
	if x.startswith("/usr/share/icons") and x.endswith("index.theme"):
	    functions.add('iconscache')
	if x.startswith("/usr/share/mime"):
	    functions.add('mimeupdate')
	if x.startswith("/usr/share/applications"):
	    functions.add('mimedesktopupdate')
	if x.startswith("/usr/share/omf"):
	    functions.add('scrollkeeper')
	if x.startswith("/etc/gconf/schemas"):
	    functions.add('gconfreload')
	if x.startswith('/boot/kernel-'):
	    functions.add('removebootablekernel')
	if x.startswith('/etc/init.d/'):
	    functions.add('removeinit')
        if x.endswith('.py'):
            functions.add('cleanpy')
        if x.startswith('/etc/env.d/'):
            functions.add('env_update')
        for path in ldpaths:
            if x.startswith(path) and (x.find(".so") != -1):
	        functions.add('run_ldconfig')

    return functions

'''
   @description: pkgdata parser that collects pre-remove scripts that would be run
'''
def preremove(pkgdata):
    
    functions = set()

    if pkgdata['trigger']:
        functions.add('call_ext_preremove')

    for x in pkgdata['removecontent']:
	if x.startswith("/etc/init.d/"):
	    functions.add('initdisable')
	if x.startswith("/boot"):
	    functions.add('mountboot')

    return functions

########################################################
####
##   External triggers support functions
#

def call_ext_preinstall(pkgdata):
    rc = call_ext_generic(pkgdata,'preinstall')
    return rc

def call_ext_postinstall(pkgdata):
    rc = call_ext_generic(pkgdata,'postinstall')
    return rc

def call_ext_preremove(pkgdata):
    rc = call_ext_generic(pkgdata,'preremove')
    return rc

def call_ext_postremove(pkgdata):
    rc = call_ext_generic(pkgdata,'postremove')
    return rc

def call_ext_generic(pkgdata, stage):

    triggerfile = etpConst['entropyunpackdir']+"/trigger-"+str(entropyTools.getRandomNumber())
    while os.path.isfile(triggerfile):
        triggerfile = etpConst['entropyunpackdir']+"/trigger-"+str(entropyTools.getRandomNumber())
    f = open(triggerfile,"w")
    for x in pkgdata['trigger']:
        f.write(x)
    f.close()
    
    execfile(triggerfile)
    
    os.remove(triggerfile)
    return my_ext_status

########################################################
####
##   Public functions
#

def fontconfig(pkgdata):
    fontdirs = set()
    for xdir in pkgdata['content']:
	if xdir.startswith("/usr/share/fonts"):
	    origdir = xdir[16:]
	    if origdir:
		if origdir.startswith("/"):
		    origdir = origdir.split("/")[1]
		    if os.path.isdir(xdir[:16]+"/"+origdir):
		        fontdirs.add(xdir[:16]+"/"+origdir)
    if (fontdirs):
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring fonts directory...")
	print_info(red("   ##")+brown(" Configuring fonts directory..."))
    for fontdir in fontdirs:
	setup_font_dir(fontdir)
	setup_font_cache(fontdir)

def gccswitch(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring GCC Profile...")
    print_info(red("   ##")+brown(" Configuring GCC Profile..."))
    # get gcc profile
    pkgsplit = entropyTools.catpkgsplit(pkgdata['category']+"/"+pkgdata['name']+"-"+pkgdata['version'])
    profile = pkgdata['chost']+"-"+pkgsplit[2]
    set_gcc_profile(profile)

def iconscache(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating icons cache...")
    print_info(red("   ##")+brown(" Updating icons cache..."))
    for file in pkgdata['content']:
	if file.startswith("/usr/share/icons") and file.endswith("index.theme"):
	    cachedir = os.path.dirname(file)
	    generate_icons_cache(cachedir)

def mimeupdate(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating shared mime info database...")
    print_info(red("   ##")+brown(" Updating shared mime info database..."))
    update_mime_db()

def mimedesktopupdate(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating desktop mime database...")
    print_info(red("   ##")+brown(" Updating desktop mime database..."))
    update_mime_desktop_db()

def scrollkeeper(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating scrollkeeper database...")
    print_info(red("   ##")+brown(" Updating scrollkeeper database..."))
    update_scrollkeeper_db()

def gconfreload(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Reloading GConf2 database...")
    print_info(red("   ##")+brown(" Reloading GConf2 database..."))
    reload_gconf_db()

def binutilsswitch(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring Binutils Profile...")
    print_info(red("   ##")+brown(" Configuring Binutils Profile..."))
    # get binutils profile
    pkgsplit = entropyTools.catpkgsplit(pkgdata['category']+"/"+pkgdata['name']+"-"+pkgdata['version'])
    profile = pkgdata['chost']+"-"+pkgsplit[2]
    set_binutils_profile(profile)

def kernelmod(pkgdata):
    if pkgdata['category'] != "sys-kernel":
        equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating moduledb...")
        print_info(red("   ##")+brown(" Updating moduledb..."))
        item = 'a:1:'+pkgdata['category']+"/"+pkgdata['name']+"-"+pkgdata['version']
        update_moduledb(item)
    print_info(red("   ##")+brown(" Running depmod..."))
    # get kernel modules dir name
    name = ''
    for file in pkgdata['content']:
        if file.startswith("/lib/modules/"):
            name = file.split("/")[3]
            break
    run_depmod(name)

def pythoninst(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring Python...")
    print_info(red("   ##")+brown(" Configuring Python..."))
    python_update_symlink()

def sqliteinst(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring SQLite...")
    print_info(red("   ##")+brown(" Configuring SQLite..."))
    sqlite_update_symlink()

def initdisable(pkgdata):
    for file in pkgdata['removecontent']:
	if file.startswith("/etc/init.d/") and os.path.isfile(file):
	    # running?
	    running = os.path.isfile(INITSERVICES_DIR+'/started/'+os.path.basename(file))
	    scheduled = not os.system('rc-update show | grep '+os.path.basename(file)+'&> /dev/null')
	    initdeactivate(file, running, scheduled)

def initinform(pkgdata):
    for file in pkgdata['content']:
	if file.startswith("/etc/init.d/") and not os.path.isfile(file):
            equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] A new service will be installed: "+file)
	    print_info(red("   ##")+brown(" A new service will be installed: ")+file)

def removeinit(pkgdata):
    for file in pkgdata['removecontent']:
	if file.startswith("/etc/init.d/") and os.path.isfile(file):
            equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Removing boot service: "+os.path.basename(file))
	    print_info(red("   ##")+brown(" Removing boot service: ")+os.path.basename(file))
	    try:
		os.system('rc-update del '+os.path.basename(file)+' &> /dev/null')
	    except:
		pass

def openglsetup(pkgdata):
    opengl = "xorg-x11"
    if pkgdata['name'] == "nvidia-drivers":
	opengl = "nvidia"
    elif pkgdata['name'] == "ati-drivers":
	opengl = "ati"
    # is there eselect ?
    eselect = os.system("eselect opengl &> /dev/null")
    if eselect == 0:
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Reconfiguring OpenGL to "+opengl+" ...")
	print_info(red("   ##")+brown(" Reconfiguring OpenGL..."))
	os.system("eselect opengl set --use-old "+opengl)
    else:
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Eselect NOT found, cannot run OpenGL trigger")
	print_info(red("   ##")+brown(" Eselect NOT found, cannot run OpenGL trigger"))

def openglsetup_xorg(pkgdata):
    eselect = os.system("eselect opengl &> /dev/null")
    if eselect == 0:
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Reconfiguring OpenGL to fallback xorg-x11 ...")
	print_info(red("   ##")+brown(" Reconfiguring OpenGL..."))
	os.system("eselect opengl set xorg-x11")
    else:
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Eselect NOT found, cannot run OpenGL trigger")
	print_info(red("   ##")+brown(" Eselect NOT found, cannot run OpenGL trigger"))

# FIXME: this only supports grub (no lilo support)
def addbootablekernel(pkgdata):
    kernels = [x for x in pkgdata['content'] if x.startswith("/boot/kernel-")]
    for kernel in kernels:
	initramfs = "/boot/initramfs-"+kernel[13:]
	if initramfs not in pkgdata['content']:
	    initramfs = ''
	# configure GRUB
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring GRUB bootloader. Adding the new kernel...")
	print_info(red("   ##")+brown(" Configuring GRUB bootloader. Adding the new kernel..."))
	configure_boot_grub(kernel,initramfs)
	

# FIXME: this only supports grub (no lilo support)
def removebootablekernel(pkgdata):
    kernels = [x for x in pkgdata['content'] if x.startswith("/boot/kernel-")]
    for kernel in kernels:
	initramfs = "/boot/initramfs-"+kernel[13:]
	if initramfs not in pkgdata['content']:
	    initramfs = ''
	# configure GRUB
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring GRUB bootloader. Removing the selected kernel...")
	print_info(red("   ##")+brown(" Configuring GRUB bootloader. Removing the selected kernel..."))
	remove_boot_grub(kernel,initramfs)

def mountboot(pkgdata):
    # is in fstab?
    if os.path.isfile("/etc/fstab"):
        f = open("/etc/fstab","r")
	fstab = f.readlines()
        fstab = entropyTools.listToUtf8(fstab)
	f.close()
	for line in fstab:
	    fsline = line.split()
	    if len(fsline) > 1:
		if fsline[1] == "/boot":
                    if not os.path.ismount("/boot"):
                        # trigger mount /boot
                        rc = os.system("mount /boot &> /dev/null")
                        if rc == 0:
                            equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] Mounted /boot successfully")
                            print_info(red("   ##")+brown(" Mounted /boot successfully"))
                        elif rc != 8192: # already mounted
                            equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] Cannot mount /boot automatically !!")
                            print_info(red("   ##")+brown(" Cannot mount /boot automatically !!"))
                        break

def kbuildsycoca(pkgdata):
    kdedirs = ''
    try:
	kdedirs = os.environ['KDEDIRS']
    except:
	pass
    if kdedirs:
	dirs = kdedirs.split(":")
	for builddir in dirs:
	    if os.access(builddir+"/bin/kbuildsycoca",os.X_OK):
		if not os.path.isdir("/usr/share/services"):
		    os.makedirs("/usr/share/services")
		os.chown("/usr/share/services",0,0)
		os.chmod("/usr/share/services",0755)
		equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Running kbuildsycoca to build global KDE database")
		print_info(red("   ##")+brown(" Running kbuildsycoca to build global KDE database"))
		os.system(builddir+"/bin/kbuildsycoca --global --noincremental &> /dev/null")

def gconfinstallschemas(pkgdata):
    gtest = os.system("which gconftool-2 &> /dev/null")
    if gtest == 0:
	schemas = [x for x in pkgdata['content'] if x.startswith("/etc/gconf/schemas") and x.endswith(".schemas")]
	print_info(red("   ##")+brown(" Installing GConf2 schemas..."))
	for schema in schemas:
	    os.system("""
	    unset GCONF_DISABLE_MAKEFILE_SCHEMA_INSTALL
	    export GCONF_CONFIG_SOURCE=$(gconftool-2 --get-default-source)
	    gconftool-2 --makefile-install-rule """+schema+""" 1>/dev/null
	    """)

def pygtksetup(pkgdata):
    python_sym_files = [x for x in pkgdata['content'] if x.endswith("pygtk.py-2.0") or x.endswith("pygtk.pth-2.0")]
    print python_sym_files
    for file in python_sym_files:
	if os.path.isfile(file):
            try:
                if os.path.isfile(file[:-4]):
                    os.remove(file[:-4])
                os.symlink(file,file[:-4])
            except OSError:
                pass

def pygtkremove(pkgdata):
    python_sym_files = [x for x in pkgdata['content'] if x.startswith("/usr/lib/python") and (x.endswith("pygtk.py-2.0") or x.endswith("pygtk.pth-2.0"))]
    for file in python_sym_files:
	if os.path.isfile(file[:-4]):
	    os.remove(file[:-4])

def susetuid(pkgdata):
    if os.path.isfile("/bin/su"):
        print_info(red("   ##")+brown(" Configuring '/bin/su' executable SETUID"))
        os.chown("/bin/su",0,0)
        os.chmod("/bin/su",4755)

def cleanpy(pkgdata):
    pyfiles = [x for x in pkgdata['content'] if x.endswith(".py")]
    for file in pyfiles:
        if os.path.isfile(file+"o"):
            try: os.remove(file+"o")
            except OSError: pass
        if os.path.isfile(file+"c"):
            try: os.remove(file+"c")
            except OSError: pass

def createkernelsym(pkgdata):
    for file in pkgdata['content']:
        if file.startswith("/usr/src/"):
            # extract directory
            try:
                todir = file.split("/")[3]
            except:
                continue
            if os.path.isdir("/usr/src/"+todir):
                # link to /usr/src/linux
		equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Creating kernel symlink /usr/src/linux for /usr/src/"+todir)
		print_info(red("   ##")+brown(" Creating kernel symlink /usr/src/linux for /usr/src/"+todir))
                if os.path.isfile("/usr/src/linux") or os.path.islink("/usr/src/linux"):
                    os.remove("/usr/src/linux")
                os.symlink(todir,"/usr/src/linux")
                break

def run_ldconfig(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Running ldconfig")
    print_info(red("   ##")+brown(" Regenerating /etc/ld.so.cache"))
    os.system("ldconfig &> /dev/null")

def env_update(pkgdata):
    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Running env-update")
    if os.access("/usr/sbin/env-update",os.X_OK):
        print_info(red("   ##")+brown(" Updating environment using env-update"))
        os.system("env-update &> /dev/null")

def add_java_config_2(pkgdata):
    vms = set()
    for vm in pkgdata['content']:
        if vm.startswith("/usr/share/java-config-2/vm/") and os.path.isfile(vm):
            vms.add(vm)
    # sort and get the latter
    if vms:
        vms = list(vms)
        vms.reverse()
        myvm = vms[0].split("/")[-1]
        if myvm:
            if os.access("/usr/bin/java-config",os.X_OK):
                equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring JAVA using java-config with VM: "+myvm)
                # set
                print_info(red("   ##")+brown(" Setting system VM to ")+bold(myvm)+brown("..."))
                os.system("java-config -S "+myvm)
            else:
                equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] ATTENTION /usr/bin/java-config does not exist. I was about to set JAVA VM: "+myvm)
                print_info(red("   ##")+bold(" Attention: ")+brown("/usr/bin/java-config does not exist. Cannot set JAVA VM."))
    del vms

########################################################
####
##   Internal functions
#

'''
   @description: creates Xfont files
   @output: returns int() as exit status
'''
def setup_font_dir(fontdir):
    # mkfontscale
    if os.access('/usr/bin/mkfontscale',os.X_OK):
	os.system('/usr/bin/mkfontscale '+unicode(fontdir))
    # mkfontdir
    if os.access('/usr/bin/mkfontdir',os.X_OK):
	os.system('/usr/bin/mkfontdir -e /usr/share/fonts/encodings -e /usr/share/fonts/encodings/large '+unicode(fontdir))
    return 0

'''
   @description: creates font cache
   @output: returns int() as exit status
'''
def setup_font_cache(fontdir):
    # fc-cache -f gooooo!
    if os.access('/usr/bin/fc-cache',os.X_OK):
	os.system('/usr/bin/fc-cache -f '+unicode(fontdir))
    return 0

'''
   @description: set chosen gcc profile
   @output: returns int() as exit status
'''
def set_gcc_profile(profile):
    if os.access('/usr/bin/gcc-config',os.X_OK):
	os.system('/usr/bin/gcc-config '+profile)
    return 0

'''
   @description: set chosen binutils profile
   @output: returns int() as exit status
'''
def set_binutils_profile(profile):
    if os.access('/usr/bin/binutils-config',os.X_OK):
	os.system('/usr/bin/binutils-config '+profile)
    return 0

'''
   @description: creates/updates icons cache
   @output: returns int() as exit status
'''
def generate_icons_cache(cachedir):
    if os.access('/usr/bin/gtk-update-icon-cache',os.X_OK):
	os.system('/usr/bin/gtk-update-icon-cache -qf '+cachedir)
    return 0

'''
   @description: updates /usr/share/mime database
   @output: returns int() as exit status
'''
def update_mime_db():
    if os.access('/usr/bin/update-mime-database',os.X_OK):
	os.system('/usr/bin/update-mime-database /usr/share/mime')
    return 0

'''
   @description: updates /usr/share/applications database
   @output: returns int() as exit status
'''
def update_mime_desktop_db():
    if os.access('/usr/bin/update-desktop-database',os.X_OK):
	os.system('/usr/bin/update-desktop-database -q /usr/share/applications')
    return 0

'''
   @description: updates /var/lib/scrollkeeper database
   @output: returns int() as exit status
'''
def update_scrollkeeper_db():
    if os.access('/usr/bin/scrollkeeper-update',os.X_OK):
	if not os.path.isdir('/var/lib/scrollkeeper'):
	    os.makedirs('/var/lib/scrollkeeper')
	os.system('/usr/bin/scrollkeeper-update -q -p /var/lib/scrollkeeper')
    return 0

'''
   @description: respawn gconfd-2 if found
   @output: returns int() as exit status
'''
def reload_gconf_db():
    rc = os.system('pgrep -x gconfd-2')
    if (rc == 0):
	pids = getoutput('pgrep -x gconfd-2').split("\n")
	pidsstr = ''
	for pid in pids:
	    if pid:
		pidsstr += pid+' '
	pidsstr = pidsstr.strip()
	if pidsstr:
	    os.system('kill -HUP '+pidsstr)
    return 0

'''
   @description: updates moduledb
   @output: returns int() as exit status
'''
def update_moduledb(item):
    if os.access('/usr/sbin/module-rebuild',os.X_OK):
	if os.path.isfile(MODULEDB_DIR+'moduledb'):
	    f = open(MODULEDB_DIR+'moduledb',"r")
	    moduledb = f.readlines()
            moduledb = entropyTools.listToUtf8(moduledb)
	    f.close()
	    avail = [x for x in moduledb if x.strip() == item]
	    if (not avail):
		f = open(MODULEDB_DIR+'moduledb',"aw")
		f.write(item+"\n")
		f.flush()
		f.close()
    return 0

'''
   @description: insert kernel object into kernel modules db
   @output: returns int() as exit status
'''
def run_depmod(name):
    if os.access('/sbin/depmod',os.X_OK):
	os.system('/sbin/depmod -a -b / -r '+name+' &> /dev/null')
    return 0

'''
   @description: update /usr/bin/python and /usr/bin/python2 symlink
   @output: returns int() as exit status
'''
def python_update_symlink():
    bins = [x for x in os.listdir("/usr/bin") if x.startswith("python2.")]
    versions = [x[6:] for x in bins]
    versions.sort()
    latest = versions[-1]
    os.system('ln -sf /usr/bin/python'+str(latest)+' /usr/bin/python')
    os.system('ln -sf /usr/bin/python'+str(latest)+' /usr/bin/python2')
    return 0

'''
   @description: update /usr/bin/lemon symlink
   @output: returns int() as exit status
'''
def sqlite_update_symlink():
    bins = [x for x in os.listdir("/usr/bin") if x.startswith("lemon-")]
    versions = [x[6:] for x in bins]
    versions.sort()
    latest = versions[-1]
    os.system('ln -sf /usr/bin/lemon-'+str(latest)+' /usr/bin/lemon')
    return 0

'''
   @description: shuts down selected init script, and remove from runlevel
   @output: returns int() as exit status
'''
def initdeactivate(file, running, scheduled):
    if (running):
        os.system(file+' stop --quiet')
    if (scheduled):
	os.system('rc-update del '+os.path.basename(file))
    return 0

'''
   @description: append kernel entry to grub.conf
   @output: returns int() as exit status
'''
def configure_boot_grub(kernel,initramfs):
    if not os.path.isdir("/boot/grub"):
	os.makedirs("/boot/grub")
    if os.path.isfile("/boot/grub/grub.conf"):
	# open in append
	grub = open("/boot/grub/grub.conf","aw")
	# get boot dev
	boot_dev = get_grub_boot_dev()
	# test if entry has been already added
	grubtest = open("/boot/grub/grub.conf","r")
	content = grubtest.readlines()
        content = entropyTools.listToUtf8(content)
        for line in content:
            try: # handle stupidly encoded text
                if line.find("title="+etpConst['systemname']+" ("+os.path.basename(kernel)+")\n") != -1:
                    grubtest.close()
                    return
            except UnicodeDecodeError:
                continue
    else:
	# create
	boot_dev = "(hd0,0)"
	grub = open("/boot/grub/grub.conf","w")
	# write header - guess (hd0,0)... since it is weird having a running system without a bootloader, at least, grub.
	grub_header = '''
default=0
timeout=10
	'''
	grub.write(grub_header)
    cmdline = ' '
    if os.path.isfile("/proc/cmdline"):
	f = open("/proc/cmdline","r")
	cmdline = " "+f.readline().strip()
	params = cmdline.split()
	if "dolvm" not in params: # support new kernels >= 2.6.23
	    cmdline += " dolvm "
	f.close()
    grub.write("title="+etpConst['systemname']+" ("+os.path.basename(kernel)+")\n")
    grub.write("\troot "+boot_dev+"\n")
    grub.write("\tkernel "+kernel+cmdline+"\n")
    if initramfs:
        grub.write("\tinitrd "+initramfs+"\n")
    grub.write("\n")
    grub.flush()
    grub.close()

def remove_boot_grub(kernel,initramfs):
    if os.path.isdir("/boot/grub") and os.path.isfile("/boot/grub/grub.conf"):
	f = open("/boot/grub/grub.conf","r")
	grub_conf = f.readlines()
        grub_conf = entropyTools.listToUtf8(grub_conf)
	kernelname = os.path.basename(kernel)
	new_conf = []
        found = False
        for count in range(len(grub_conf)):
            line = grub_conf[count].strip()
            if (line.find(kernelname) != -1) or (line.find(kernelname) != -1):
                found = True
                # remove previous content up to title
                rlines = 0
                for x in range(len(new_conf))[::-1]:
                    rlines += 1
                    if new_conf[x].strip().startswith("title"):
                        break
                new_conf = new_conf[::-1][rlines:][::-1]
            if (found):
                # check if the parameter belongs to title or it is something else
                line = grub_conf[count].strip().split()[0]
                if line: # skip empty lines
                    if line in ["root","kernel","initrd","hide","unhide","chainloader","makeactive","rootnoverify"]:
                        # skip write
                        continue
                    else:
                        # skip completed
                        found = False
            new_conf.append(grub_conf[count])
	f = open("/boot/grub/grub.conf","w")
	f.writelines(new_conf)
	f.flush()
	f.close()

def get_grub_boot_dev():
    import re
    df_avail = os.system("which df &> /dev/null")
    if df_avail != 0:
	print "DEBUG: cannot find df!! Cannot properly configure kernel! Defaulting to (hd0,0)"
	return "(hd0,0)"
    grub_avail = os.system("which grub &> /dev/null")
    if grub_avail != 0:
	print "DEBUG: cannot find grub!! Cannot properly configure kernel! Defaulting to (hd0,0)"
	return "(hd0,0)"
    
    gboot = getoutput("df /boot").split("\n")[-1].split()[0]
    if gboot.startswith("/dev/"):
	# it's ok - handle /dev/md
	if gboot.startswith("/dev/md"):
	    md = os.path.basename(gboot)
	    if not md.startswith("md"):
		md = "md"+md
	    f = open("/proc/mdstat","r")
	    mdstat = f.readlines()
	    mdstat = [x for x in mdstat if x.startswith(md)]
	    f.close()
	    if mdstat:
		mdstat = mdstat[0].strip().split()
		mddevs = []
		for x in mdstat:
		    if x.startswith("sd"):
			mddevs.append(x[:-3])
		mddevs.sort()
		if mddevs:
		    gboot = "/dev/"+mddevs[0]
		else:
		    gboot = "/dev/sda1"
	    else:
		gboot = "/dev/sda1"
	# get disk
	match = re.subn("[0-9]","",gboot)
	gdisk = match[0]
	match = re.subn("[a-z/]","",gboot)
	gpartnum = str(int(match[0])-1)
	# now match with grub
	device_map = etpConst['packagestmpdir']+"/grub.map"
	if os.path.isfile(device_map):
	    os.remove(device_map)
	# generate device.map
	os.system('echo "quit" | grub --device-map='+device_map+' --no-floppy --batch &> /dev/null')
	if os.path.isfile(device_map):
	    f = open(device_map,"r")
	    device_map_file = f.readlines()
	    f.close()
	    grub_dev = [x for x in device_map_file if (x.find(gdisk) != -1)]
	    if grub_dev:
		grub_disk = grub_dev[0].strip().split()[0]
		grub_dev = grub_disk[:-1]+","+gpartnum+")"
		return grub_dev
	    else:
		print "DEBUG: cannot match grub device with linux one!! Cannot properly configure kernel! Defaulting to (hd0,0)"
		return "(hd0,0)"
	else:
	    print "DEBUG: cannot find generated device.map!! Cannot properly configure kernel! Defaulting to (hd0,0)"
	    return "(hd0,0)"
    else:
	print "DEBUG: cannot run df /boot!! Cannot properly configure kernel! Defaulting to (hd0,0)"
	return "(hd0,0)"
	
