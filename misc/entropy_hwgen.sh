#!/bin/sh
# Entropy Hardware hash generator

[ -x "/usr/bin/awk" ] || exit 1
[ -x "/usr/sbin/lspci" ] || exit 1

ifconfig_output=$(ifconfig -a | grep HWaddr | awk '{ print $5 }' 2> /dev/null)
lspci_output=$(/usr/sbin/lspci -n | cut -d" " -f 3- 2> /dev/null)
echo $ifconfig_output$lspci_output | sha256sum | cut -d" " -f 1 2> /dev/null
