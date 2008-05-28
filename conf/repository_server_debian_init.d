#! /bin/sh
#
# Entropy Repository Daemon init script
#
#     Created by Fabio Erculiani <lxnay@sabayonlinux.org>
#

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
PYTHONPATH=/home/entropy/communityserver/libraries:/home/entropy/communityserver/serclient
DAEMON=/home/entropy/communityserver/server/sabayonlinux-repository-daemon
NAME=entropy-repository-daemon
DESC=entropy-repository-daemon
PID=/var/run/entropy_repository_daemon.pid
CMDLINE="--nostdout"

set -e

case "$1" in
   start)
      echo -n "Starting $DESC: "
      start-stop-daemon --background --make-pidfile -c entropy:entropy --start --pidfile $PID --quiet --exec $DAEMON -- $CMDLINE
      sleep 3
      if [ -d "/proc/$(cat $PID)" ]; then
         echo "$NAME."
      else
         echo -n "<Failed>"
         exit 1
      fi 
      ;;
   stop)
      echo -n "Stopping $DESC: "
      kill $(cat $PID)
      sleep 8
      if [ ! -d "/proc/$(cat $PID)" ]; then
         echo "$NAME."
      else
         echo -n "<Failed>"
         exit 1
      fi 
      ;;
   restart)
      $0 stop
      sleep 3
      $0 start
      ;;
   *)
      N=/etc/init.d/$NAME
      echo "Usage: $N {start|stop|restart}" >&2
      exit 1
      ;;
esac

exit 0
