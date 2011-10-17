#!/usr/sbin/entropy.sh
# Environmental variables available
#
# always available:
#
# ETP_API: Current Entropy client API
# ETP_LOG: Entropy log file path
# ETP_STAGE: Entropy trigger stage (preinstall,postinstall,preremove,postremove)
# ETP_PHASE: Entropy trigger phase, matching Portage ones
#                    (pkg_preinst, pkg_prerm, pkg_preinst, pkg_postinst)
# ETP_BRANCH: Current Entropy client branch
# CATEGORY: Entropy package category
# PN: Entropy package name
# PV: Entropy package version
# PR: Entropy package revision
# PVR: Entropy package version+revision
# PVRTE: Entropy package version+revision+entropy_tag+entropy_rev
# PER: Entropy package revision
# PET: Entropy package tag
# SLOT: Entropy package slot
# PAPI: Entropy package "Entropy API"
# P: Entropy package atom
# CFLAGS: Entropy package CFLAGS
# CXXFLAGS: Entropy package CXXFLAGS
# CHOST: Entropy package CHOST
# WORKDIR: Entropy temporary package unpack/work dir (matching Portage)
# B: Entropy temporary package unpack/work dir
# D: Entropy temporary final package destination dir (before merging to system)
# ENTROPY_TMPDIR: Entropy packages temporary directory
# ROOT: System root directory, "" if /
#

function pkg_preinst() {
    echo "preinst"
    return 0
}

function pkg_postinst() {
    echo "postinst"
    return 0
}

function pkg_prerm() {
    echo "prerm"
    return 0
}

function pkg_postrm() {
    echo "postrm"
    return 0
}

