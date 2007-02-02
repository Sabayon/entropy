#!/usr/bin/python
# Copyright Fabio Erculiani - Sabayon Linux 2007

# DESCRIPTION:
# Variables container

# Specifications of the content of .etp file go here
pData = {
    'name': "",
    'version': "",
    'description': "",
    'category': "",
    'arch': "",
    'chost': "",
    'homepage': "",
    'useflags': "",
    'license': "",
    'download': "", # get this info from make.conf
    'dependencies': "",
    'conflicts': "",
}

# variables
# should we import these into make.conf ?
pTree = "/var/lib/entropy/packages"
pTmpDir = pTree+"/tmp"
# fetch PORTAGE_BINHOST
f = open("/etc/make.conf","r")
makeConf = f.readlines()
pBinHost = ""
for line in makeConf:
    line = line.strip()
    if line.startswith("PORTAGE_BINHOST"):
	pBinHost = line.split('"')[1]
	break
if (pBinHost == ""):
    # force PORTAGE_BINHOST to our defaults
    pBinHost = "http://www.sabayonlinux.org/binhost/All/"
if not pBinHost.endswith("/"):
    pBinHost += "/"

# Portage /var/db/<pkgcat>/<pkgname-pkgver>/*
# you never know if gentoo devs change these things
dbDESCRIPTION = "DESCRIPTION"
dbHOMEPAGE = "HOMEPAGE"
dbCHOST = "CHOST"
