#!/bin/sh

if [ "$(whoami)" != "root" ]; then
	echo "run this as root" >&2
	exit 1
fi

cp dbus/org.sabayon.Rigo.conf /etc/dbus-1/system.d/ || exit 1
chown root:root /etc/dbus-1/system.d/org.sabayon.Rigo.conf || exit 1

cp dbus/org.sabayon.Rigo.xml /usr/share/dbus-1/interfaces/ || exit 1
chown root:root /usr/share/dbus-1/interfaces/org.sabayon.Rigo.xml || exit 1

cp dbus/org.sabayon.Rigo.service /usr/share/dbus-1/system-services/ || exit 1
chown root:root /usr/share/dbus-1/system-services/org.sabayon.Rigo.service || exit 1

sed -i "s:app.py:app.py --daemon-logging --debug:" \
	/usr/share/dbus-1/system-services/org.sabayon.Rigo.service || exit 1

if [ ! -d "/usr/lib/rigo/RigoDaemon" ]; then
	mkdir -p /usr/lib/rigo/RigoDaemon || exit 1
fi
cp *.py /usr/lib/rigo/RigoDaemon/ -p || exit 1
chmod 755 /usr/lib/rigo/RigoDaemon/app.py || exit 1
