#!/bin/sh
echo "matter pre hook"

is_mounted=$(mount | cut -d" " -f 3 | grep "/proc")
if [ -z "${is_mounted}" ]; then
	echo "mounting /proc, not mounted"
	mount -t proc proc /proc
fi
