#!/usr/bin/python
# Copyright Fabio Erculiani - Sabayon Linux 2007

# DESCRIPTION:
# generic tools for all the handlers applications

from entropyVariables import *

# This function extracts all the info from a .tbz2 file and returns them
def extractPkgData(package):

    tbz2File = package

    package = package.split(".tbz2")
    package = package[0].split("-")
    pkgname = ""
    pkglen = len(package)
    if package[pkglen-1].startswith("r"):
        pkgver = package[pkglen-2]+"-"+package[pkglen-1]
	pkglen -= 2
    else:
	pkgver = package[len(package)-1]
	pkglen -= 1
    for i in range(pkglen):
	if i == pkglen-1:
	    pkgname += package[i]
	else:
	    pkgname += package[i]+"-"
    pkgname = pkgname.split("/")[len(pkgname.split("/"))-1]
    
    # Fill Package name and version
    pData['name'] = pkgname
    pData['version'] = pkgver

    import xpak
    tbz2 = xpak.tbz2(tbz2File)
    tbz2TmpDir = pTmpDir+"/"+pData['name']+"-"+pData['version']
    tbz2.decompose(tbz2TmpDir)

    # Fill description
    f = open(tbz2TmpDir+"/"+dbDESCRIPTION,"r")
    pData['description'] = f.readline().strip()
    f.close()

    # Fill homepage
    f = open(tbz2TmpDir+"/"+dbHOMEPAGE,"r")
    pData['homepage'] = f.readline().strip()
    f.close()

    # Fill chost
    f = open(tbz2TmpDir+"/"+dbCHOST,"r")
    pData['chost'] = f.readline().strip()
    f.close()

    # return all the collected info
    return pData