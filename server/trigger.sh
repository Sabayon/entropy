#!/usr/sbin/entropy.sh

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

