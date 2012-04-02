#!/bin/sh

if [ "$(whoami)" = "root" ]; then
	echo "run this as user" >&2
	exit 1
fi

sudo cp dbus/org.sabayon.Rigo.conf /etc/dbus-1/system.d/ || exit 1
sudo chown root:root /etc/dbus-1/system.d/org.sabayon.Rigo.conf || exit 1

sudo cp dbus/org.sabayon.Rigo.xml /usr/share/dbus-1/interfaces/ || exit 1
sudo chown root:root /usr/share/dbus-1/interfaces/org.sabayon.Rigo.xml || exit 1

sudo cp polkit/org.sabayon.RigoDaemon.policy /usr/share/polkit-1/actions/ || exit 1

cd ../ || exit 1
# GDB?
# sudo gdb --args python2 ./RigoDaemon/app.py --debug
sudo python2 ./RigoDaemon/app.py --debug
