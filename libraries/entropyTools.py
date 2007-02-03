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
    pData['version'] = pkgver  # FIXME: add -etpNN

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

    # Fill url
    pData['download'] = pBinHost+tbz2File

    # Fill category
    f = open(tbz2TmpDir+"/"+dbCATEGORY,"r")
    pData['category'] = f.readline().strip()
    f.close()

    # Fill CFLAGS
    f = open(tbz2TmpDir+"/"+dbCFLAGS,"r")
    pData['cflags'] = f.readline().strip()
    f.close()

    # Fill CXXFLAGS
    f = open(tbz2TmpDir+"/"+dbCXXFLAGS,"r")
    pData['cxxflags'] = f.readline().strip()
    f.close()

    # Fill license
    f = open(tbz2TmpDir+"/"+dbLICENSE,"r")
    pData['license'] = f.readline().strip()
    f.close()

    # Fill sources
    f = open(tbz2TmpDir+"/"+dbSRC_URI,"r")
    pData['sources'] = f.readline().strip()
    f.close()

    # Fill USE
    f = open(tbz2TmpDir+"/"+dbUSE,"r")
    pData['useflags'] = f.readline().strip()
    f.close()

    # Fill dependencies
    # to fill dependencies we use *DEPEND files and then parse the content of:
    # Notes (take the example of mplayer that needed a newer libcaca release):
    # - we can use (from /var/db) "NEEDED" file to catch all the needed libraries to run the binary package
    # - we can use (from /var/db) "CONTENTS" to rapidly search the NEEDED files in the file above


    # return all the collected info
    return pData