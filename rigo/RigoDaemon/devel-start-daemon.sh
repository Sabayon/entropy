#!/bin/sh

if [ "$(whoami)" != "root" ]; then
	echo "run this as root" >&2
	exit 1
fi

cp dbus/org.sabayon.Rigo.conf /etc/dbus-1/system.d/ || exit 1
chown root:root /etc/dbus-1/system.d/org.sabayon.Rigo.conf || exit 1

cp dbus/org.sabayon.Rigo.xml /usr/share/dbus-1/interfaces/ || exit 1
chown root:root /usr/share/dbus-1/interfaces/org.sabayon.Rigo.xml || exit 1

cd ../ && ./RigoDaemon/app.py --debug
