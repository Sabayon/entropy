#!/bin/sh
# Entropy Hardware hash generator

[[ -x "/sbin/ifconfig" ]] || exit 1
[[ -x "/usr/bin/awk" ]] || exit 1
[[ -x "/usr/sbin/lspci" ]] || exit 1
[[ -x "/usr/bin/sha256sum" ]] || exit 1

ifconfig_output=$(/sbin/ifconfig -a | grep HWaddr | awk '{ print $5 }' 2> /dev/null)
lspci_output=$(/usr/sbin/lspci -n | cut -d" " -f 3- 2> /dev/null)
echo $ifconfig_output$lspci_output | /usr/bin/sha256sum | cut -d" " -f 1
